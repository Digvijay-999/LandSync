import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.pipeline import PipelineStageExecution
from app.models.provenance import ProvenanceEvent
from app.models.adjudication import HumanReviewDecision
from app.models.conflict import GeospatialConflict
from app.models.validation import ValidationResult
from app.models.matching import FeatureMatch, MatchReview
from app.models.feature import CanonicalFeature
from app.schemas.adjudication import (
    ReviewQueueItem,
    ReviewQueueSummaryResponse,
    ReviewQueueListResponse,
    AdjudicationActionRequest,
    AdjudicationActionResponse,
    Stage11ExecutionResponse,
)


class AdjudicationService:
    """
    Service managing Pipeline Stage 11 — Human Review.
    Provides human-in-the-loop review queue synthesis from Stages 08, 09, 10,
    adjudication decisions, constraint override tracking, provenance, and deterministic completion.
    """

    VALID_ACTIONS = [
        "ACCEPT_SOURCE_A",
        "ACCEPT_SOURCE_B",
        "MERGE_RECONCILE",
        "REJECT_UNRESOLVED",
    ]

    ALLOWED_MERGE_FIELDS = {
        "land_use",
        "mutation_status",
        "risk_level",
        "survey_number",
        "owner_name",
        "area",
        "notes",
    }

    @classmethod
    async def _get_stage10_execution(
        cls, db: AsyncSession, project_id: uuid.UUID
    ) -> PipelineStageExecution:
        exec_stmt = select(PipelineStageExecution).where(
            PipelineStageExecution.project_id == project_id,
            PipelineStageExecution.stage_id == "confidence",
        )
        stage10_exec = (await db.execute(exec_stmt)).scalar_one_or_none()
        if not stage10_exec or stage10_exec.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stage 10 Confidence Scoring must be completed before accessing Stage 11 Human Review.",
            )
        return stage10_exec

    @classmethod
    async def _build_queue_items(
        cls, db: AsyncSession, project_id: uuid.UUID
    ) -> List[ReviewQueueItem]:
        """
        Synthesize the complete review queue for a project from:
        - Stage 10 Confidence Scoring execution results
        - Stage 08 GeospatialConflict records
        - Stage 09 ValidationResult records
        - Stage 11 HumanReviewDecision records
        - CanonicalFeature properties
        """
        stage10_exec = await cls._get_stage10_execution(db, project_id)
        scored_records = stage10_exec.results.get("records_preview", []) if stage10_exec.results else []

        # 1. Fetch all GeospatialConflicts for this project
        conf_stmt = select(GeospatialConflict).where(GeospatialConflict.project_id == project_id)
        all_conflicts = (await db.execute(conf_stmt)).scalars().all()
        conflicts_by_record: Dict[str, List[GeospatialConflict]] = {}
        for c in all_conflicts:
            conflicts_by_record.setdefault(c.harmonized_record_id, []).append(c)

        # 2. Fetch all ValidationResults for this project
        val_stmt = select(ValidationResult).where(ValidationResult.project_id == project_id)
        all_val_results = (await db.execute(val_stmt)).scalars().all()
        val_by_record: Dict[str, ValidationResult] = {
            vr.harmonized_record_id: vr for vr in all_val_results
        }

        # 3. Fetch all HumanReviewDecisions for this project
        dec_stmt = select(HumanReviewDecision).where(HumanReviewDecision.project_id == project_id)
        all_decisions = (await db.execute(dec_stmt)).scalars().all()
        decisions_by_record: Dict[str, HumanReviewDecision] = {
            d.harmonized_record_id: d for d in all_decisions
        }

        # 4. Fetch CanonicalFeatures for property payloads
        feat_ids = set()
        for r in scored_records:
            if r.get("source_feature_id"):
                try:
                    feat_ids.add(uuid.UUID(str(r["source_feature_id"])))
                except (ValueError, TypeError):
                    pass
            if r.get("candidate_feature_id"):
                try:
                    feat_ids.add(uuid.UUID(str(r["candidate_feature_id"])))
                except (ValueError, TypeError):
                    pass

        features_by_id: Dict[uuid.UUID, CanonicalFeature] = {}
        if feat_ids:
            feat_stmt = select(CanonicalFeature).where(CanonicalFeature.id.in_(list(feat_ids)))
            c_feats = (await db.execute(feat_stmt)).scalars().all()
            features_by_id = {f.id: f for f in c_feats}

        # 5. Build ReviewQueueItems
        items: List[ReviewQueueItem] = []
        severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, None: 0}

        for r in scored_records:
            rec_id = r.get("id") or r.get("harmonized_record_id", "")
            rec_conflicts = conflicts_by_record.get(rec_id, [])
            val_res = val_by_record.get(rec_id)
            dec = decisions_by_record.get(rec_id)

            # Determine conflict summary
            open_conflicts = [
                c for c in rec_conflicts
                if str(c.status).upper() in ["OPEN", "UNRESOLVED", "DETECTED"]
            ]
            has_critical = any(c.severity == "CRITICAL" for c in open_conflicts)

            highest_sev = None
            if rec_conflicts:
                highest_sev = max(
                    (c.severity for c in rec_conflicts),
                    key=lambda s: severity_order.get(s, 0),
                    default=None,
                )

            conflict_payloads = [
                {
                    "id": str(c.id),
                    "conflict_type": c.conflict_type,
                    "category": c.category,
                    "severity": c.severity,
                    "severity_reason": c.severity_reason,
                    "status": c.status,
                    "field_name": c.field_name,
                    "source_a": c.source_a,
                    "source_b": c.source_b,
                    "value_a": c.value_a,
                    "value_b": c.value_b,
                    "discrepancy_value": c.discrepancy_value,
                    "discrepancy_percentage": c.discrepancy_percentage,
                    "explanation": c.explanation,
                }
                for c in rec_conflicts
            ]

            # Validation data
            val_status = val_res.overall_status if val_res else r.get("validation_status", "PASS")
            val_failures = val_res.failure_reasons if val_res and val_res.failure_reasons else []
            val_warnings = val_res.warning_reasons if val_res and val_res.warning_reasons else []

            # Spatial metrics
            spatial_metrics = {}
            if val_res and val_res.topology_metrics:
                spatial_metrics.update(val_res.topology_metrics)
            if val_res and val_res.area_metrics:
                spatial_metrics.update(val_res.area_metrics)
            if val_res and val_res.geometry_metrics:
                spatial_metrics.update(val_res.geometry_metrics)

            # Feature attributes
            sf_uuid = None
            cf_uuid = None
            if r.get("source_feature_id"):
                try:
                    sf_uuid = uuid.UUID(str(r["source_feature_id"]))
                except (ValueError, TypeError):
                    pass
            if r.get("candidate_feature_id"):
                try:
                    cf_uuid = uuid.UUID(str(r["candidate_feature_id"]))
                except (ValueError, TypeError):
                    pass

            src_feat = features_by_id.get(sf_uuid) if sf_uuid else None
            cand_feat = features_by_id.get(cf_uuid) if cf_uuid else None

            source_attrs = src_feat.canonical_properties if src_feat and src_feat.canonical_properties else {
                "source_identifier": r.get("source_identifier", "Unknown"),
                "survey_number": r.get("source_identifier", "Unknown"),
            }
            cand_attrs = cand_feat.canonical_properties if cand_feat and cand_feat.canonical_properties else {
                "candidate_identifier": r.get("candidate_identifier", "Unknown"),
            }

            harmonized_attrs = {
                "source_identifier": r.get("source_identifier", "Unknown"),
                "candidate_identifier": r.get("candidate_identifier", "Unknown"),
                "overall_confidence": r.get("overall_confidence", 0.0),
                "confidence_bucket": r.get("confidence_bucket", "LOW"),
                "validation_status": val_status,
            }

            # Mandatory review rule:
            # Requires review if bucket is not HIGH, or has critical conflicts, or validation FAIL
            bucket = r.get("confidence_bucket", "LOW")
            requires_mandatory = (
                bucket in ["LOW", "AMBIGUOUS", "MEDIUM"]
                or has_critical
                or val_status == "FAIL"
            )

            # Adjudication state
            adj_status = dec.adjudication_status if dec else "UNRESOLVED"
            adj_action = dec.action if dec else None
            auth_geom_source = dec.authoritative_geometry_source if dec else None
            auth_attrs = dec.authoritative_attributes if dec else {}
            reviewer = dec.reviewer_name if dec else None
            notes = dec.notes if dec else None
            adj_at = dec.created_at if dec else None
            override_applied = dec.override_applied if dec else False

            # Associated match ID
            fm_uuid = None
            if r.get("feature_match_id"):
                try:
                    fm_uuid = uuid.UUID(str(r["feature_match_id"]))
                except (ValueError, TypeError):
                    pass

            item = ReviewQueueItem(
                id=rec_id,
                harmonized_record_id=rec_id,
                project_id=project_id,
                source_identifier=r.get("source_identifier", "Unknown"),
                candidate_identifier=r.get("candidate_identifier", "Unknown"),
                source_feature_id=sf_uuid,
                candidate_feature_id=cf_uuid,
                feature_match_id=fm_uuid,
                overall_confidence=float(r.get("overall_confidence", 0.0)),
                confidence_bucket=bucket,
                bucket_label=r.get("bucket_label", f"{bucket} BUCKET"),
                confidence_explanation=r.get("explanation"),
                signal_contributions=r.get("contributions", {}),
                reasons=r.get("reasons", []),
                validation_status=val_status,
                validation_failure_reasons=val_failures,
                validation_warning_reasons=val_warnings,
                conflict_count=len(rec_conflicts),
                highest_conflict_severity=highest_sev,
                has_critical_conflicts=has_critical,
                conflicts=conflict_payloads,
                spatial_metrics=spatial_metrics,
                source_attributes=source_attrs,
                candidate_attributes=cand_attrs,
                harmonized_attributes=harmonized_attrs,
                review_status=r.get("review_status", "PENDING"),
                adjudication_status=adj_status,
                adjudication_action=adj_action,
                authoritative_geometry_source=auth_geom_source,
                authoritative_attributes=auth_attrs,
                reviewer_name=reviewer,
                notes=notes,
                adjudicated_at=adj_at,
                override_applied=override_applied,
                requires_mandatory_review=requires_mandatory,
            )
            items.append(item)

        # Sort queue: UNRESOLVED first, then highest conflict severity, then lowest confidence
        def sort_key(it: ReviewQueueItem):
            unres_rank = 0 if it.adjudication_status == "UNRESOLVED" else 1
            sev_rank = -severity_order.get(it.highest_conflict_severity, 0)
            conf_rank = it.overall_confidence
            return (unres_rank, sev_rank, conf_rank)

        items.sort(key=sort_key)
        return items

    @classmethod
    async def get_review_summary(
        cls, db: AsyncSession, project_id: uuid.UUID
    ) -> ReviewQueueSummaryResponse:
        """
        Calculate aggregate summary of human review queue and stage completion progress.
        """
        items = await cls._build_queue_items(db, project_id)
        total_items = len(items)

        mandatory_items = [it for it in items if it.requires_mandatory_review]
        unresolved_mandatory = [it for it in mandatory_items if it.adjudication_status == "UNRESOLVED"]
        resolved_items = [it for it in items if it.adjudication_status != "UNRESOLVED"]

        critical_count = len([it for it in items if it.has_critical_conflicts and it.adjudication_status == "UNRESOLVED"])
        high_conf_count = len([it for it in items if it.highest_conflict_severity == "HIGH"])
        med_conf_count = len([it for it in items if it.highest_conflict_severity == "MEDIUM"])
        low_conf_count = len([it for it in items if it.highest_conflict_severity == "LOW"])

        act_a = len([it for it in items if it.adjudication_action == "ACCEPT_SOURCE_A"])
        act_b = len([it for it in items if it.adjudication_action == "ACCEPT_SOURCE_B"])
        act_merge = len([it for it in items if it.adjudication_action == "MERGE_RECONCILE"])
        act_reject = len([it for it in items if it.adjudication_action == "REJECT_UNRESOLVED"])

        avg_conf = (
            round(sum(it.overall_confidence for it in items) / total_items, 4)
            if total_items > 0
            else 0.0
        )

        # Check existing Stage 11 execution record
        st11_stmt = select(PipelineStageExecution).where(
            PipelineStageExecution.project_id == project_id,
            PipelineStageExecution.stage_id == "review",
        )
        st11_exec = (await db.execute(st11_stmt)).scalar_one_or_none()

        unresolved_count = len(unresolved_mandatory)
        resolved_count = len(resolved_items)
        is_completed = (unresolved_count == 0 and len(mandatory_items) > 0)

        # Progression: 'ready' if 0 resolved, 'running' if some resolved, 'completed' if all mandatory resolved
        if is_completed or (st11_exec and st11_exec.status == "completed"):
            stage_status = "completed"
        elif resolved_count > 0:
            stage_status = "running"
        else:
            stage_status = "ready"

        progress_pct = (
            round((resolved_count / total_items) * 100.0, 1)
            if total_items > 0
            else 0.0
        )

        def _to_utc_timestamp(dt: Optional[datetime]) -> float:
            if not dt:
                return 0.0
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()

        adj_times = [it.adjudicated_at for it in items if it.adjudicated_at]
        last_adj_at = max(adj_times, key=_to_utc_timestamp, default=None)

        return ReviewQueueSummaryResponse(
            project_id=project_id,
            total_review_items=total_items,
            unresolved_count=unresolved_count,
            resolved_count=resolved_count,
            critical_count=critical_count,
            high_conflict_count=high_conf_count,
            medium_conflict_count=med_conf_count,
            low_conflict_count=low_conf_count,
            accept_source_a_count=act_a,
            accept_source_b_count=act_b,
            merged_count=act_merge,
            rejected_count=act_reject,
            average_confidence=avg_conf,
            stage_status=stage_status,
            is_completed=is_completed,
            completion_progress_pct=progress_pct,
            last_adjudication_at=last_adj_at,
        )

    @classmethod
    async def get_review_queue(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        severity: Optional[str] = None,
        conflict_type: Optional[str] = None,
        bucket: Optional[str] = None,
        validation_status: Optional[str] = None,
        adjudication_status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> ReviewQueueListResponse:
        """
        List review queue records with active filters and pagination.
        """
        items = await cls._build_queue_items(db, project_id)

        filtered = items

        # Severity filter
        if severity and severity.upper() != "ALL":
            filtered = [
                it for it in filtered
                if (it.highest_conflict_severity or "NONE").upper() == severity.upper()
            ]

        # Conflict type filter
        if conflict_type and conflict_type.upper() != "ALL":
            filtered = [
                it for it in filtered
                if any(c["conflict_type"].upper() == conflict_type.upper() for c in it.conflicts)
            ]

        # Bucket filter
        if bucket and bucket.upper() != "ALL":
            filtered = [
                it for it in filtered
                if it.confidence_bucket.upper() == bucket.upper()
            ]

        # Validation status filter
        if validation_status and validation_status.upper() != "ALL":
            filtered = [
                it for it in filtered
                if it.validation_status.upper() == validation_status.upper()
            ]

        # Adjudication status filter
        if adjudication_status and adjudication_status.upper() != "ALL":
            filtered = [
                it for it in filtered
                if it.adjudication_status.upper() == adjudication_status.upper()
            ]

        # Search filter
        if search and search.strip():
            q = search.strip().lower()
            filtered = [
                it for it in filtered
                if q in it.source_identifier.lower()
                or q in it.candidate_identifier.lower()
                or q in it.harmonized_record_id.lower()
            ]

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        paged = filtered[start:end]

        return ReviewQueueListResponse(
            items=paged,
            total=total,
            page=page,
            page_size=page_size,
        )

    @classmethod
    async def get_review_item_detail(
        cls, db: AsyncSession, project_id: uuid.UUID, record_id: str
    ) -> ReviewQueueItem:
        """
        Fetch complete inspection details for a single candidate record in the review queue.
        """
        items = await cls._build_queue_items(db, project_id)
        for it in items:
            if it.id == record_id or it.harmonized_record_id == record_id:
                return it

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review queue record '{record_id}' not found in project '{project_id}'.",
        )

    @classmethod
    async def adjudicate_record(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        record_id: str,
        request: AdjudicationActionRequest,
    ) -> AdjudicationActionResponse:
        """
        Record an explicit human review decision on a candidate pair:
        1. Validates note requirements (mandatory for Reject, Merge, and Critical/Fail overrides).
        2. Validates authoritative field selections.
        3. Persists HumanReviewDecision record in database.
        4. Updates associated GeospatialConflict statuses to RESOLVED or UNRESOLVED.
        5. Updates FeatureMatch and writes to MatchReview audit trail if applicable.
        6. Logs ProvenanceEvent (HUMAN_REVIEW_DECISION or HUMAN_REVIEW_OVERRIDE).
        7. Evaluates Stage 11 completion rule and updates PipelineStageExecution.
        """
        if request.action not in cls.VALID_ACTIONS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid adjudication action '{request.action}'. Must be one of: {cls.VALID_ACTIONS}",
            )

        # 1. Fetch the target item from queue
        item = await cls.get_review_item_detail(db, project_id, record_id)

        # 2. Enforce Note/Reason requirements:
        # Notes required for REJECT_UNRESOLVED, MERGE_RECONCILE, or whenever overriding critical conflict or validation FAIL
        has_critical = item.has_critical_conflicts
        val_failed = (item.validation_status == "FAIL")
        is_override = (has_critical or val_failed) and (request.action in ["ACCEPT_SOURCE_A", "ACCEPT_SOURCE_B", "MERGE_RECONCILE"])

        note_required = (
            request.action == "REJECT_UNRESOLVED"
            or request.action == "MERGE_RECONCILE"
            or is_override
        )

        cleaned_notes = (request.notes or "").strip()
        if note_required and not cleaned_notes:
            reason_msg = "Reviewer justification note is strictly mandatory when rejecting, merging, or overriding unresolved critical conflicts/validation failures."
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=reason_msg,
            )

        # 3. Validate Merge/Reconcile fields
        sanitized_attrs: Dict[str, Any] = {}
        if request.action == "MERGE_RECONCILE":
            if not request.authoritative_geometry_source:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="authoritative_geometry_source ('SOURCE_A', 'SOURCE_B', or 'CUSTOM') is required for MERGE_RECONCILE.",
                )
            if request.authoritative_attributes:
                for k, v in request.authoritative_attributes.items():
                    if k in cls.ALLOWED_MERGE_FIELDS:
                        sanitized_attrs[k] = v

        # Determine resulting status
        new_status = "REJECTED" if request.action == "REJECT_UNRESOLVED" else "RESOLVED"
        previous_state = {
            "adjudication_status": item.adjudication_status,
            "adjudication_action": item.adjudication_action,
            "overall_confidence": item.overall_confidence,
            "confidence_bucket": item.confidence_bucket,
            "review_status": item.review_status,
            "validation_status": item.validation_status,
            "conflict_count": item.conflict_count,
        }
        resulting_state = {
            "adjudication_status": new_status,
            "adjudication_action": request.action,
            "review_status": "REJECTED" if request.action == "REJECT_UNRESOLVED" else "ACCEPTED",
            "authoritative_geometry_source": request.authoritative_geometry_source,
            "authoritative_attributes": sanitized_attrs,
            "override_applied": is_override,
        }

        # 4. Upsert HumanReviewDecision in PostgreSQL
        idempotency_key = f"{project_id}_{record_id}"
        dec_stmt = select(HumanReviewDecision).where(
            HumanReviewDecision.project_id == project_id,
            HumanReviewDecision.harmonized_record_id == record_id,
        )
        decision_record = (await db.execute(dec_stmt)).scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if decision_record:
            decision_record.action = request.action
            decision_record.adjudication_status = new_status
            decision_record.reviewer_name = request.reviewer_name or "Lead GIS Adjudicator"
            decision_record.notes = cleaned_notes
            decision_record.authoritative_geometry_source = request.authoritative_geometry_source
            decision_record.authoritative_attributes = sanitized_attrs
            decision_record.previous_state = previous_state
            decision_record.resulting_state = resulting_state
            decision_record.override_applied = is_override
            decision_record.updated_at = now
        else:
            decision_record = HumanReviewDecision(
                id=uuid.uuid4(),
                project_id=project_id,
                harmonized_record_id=record_id,
                source_feature_id=item.source_feature_id,
                candidate_feature_id=item.candidate_feature_id,
                feature_match_id=item.feature_match_id,
                action=request.action,
                adjudication_status=new_status,
                reviewer_name=request.reviewer_name or "Lead GIS Adjudicator",
                notes=cleaned_notes,
                authoritative_geometry_source=request.authoritative_geometry_source,
                authoritative_attributes=sanitized_attrs,
                previous_state=previous_state,
                resulting_state=resulting_state,
                override_applied=is_override,
                idempotency_key=idempotency_key,
                created_at=now,
                updated_at=now,
            )
            db.add(decision_record)

        # 5. Update associated GeospatialConflicts
        conf_stmt = select(GeospatialConflict).where(
            GeospatialConflict.project_id == project_id,
            GeospatialConflict.harmonized_record_id == record_id,
        )
        conflicts = (await db.execute(conf_stmt)).scalars().all()
        for c in conflicts:
            if request.action in ["ACCEPT_SOURCE_A", "ACCEPT_SOURCE_B", "MERGE_RECONCILE"]:
                c.status = "RESOLVED"
            else:
                c.status = "UNRESOLVED"

        # 6. Update FeatureMatch & insert MatchReview if present
        if item.feature_match_id:
            fm_stmt = select(FeatureMatch).where(FeatureMatch.id == item.feature_match_id)
            fm = (await db.execute(fm_stmt)).scalar_one_or_none()
            if fm:
                fm.review_status = "REJECTED" if request.action == "REJECT_UNRESOLVED" else "ACCEPTED"
                match_review = MatchReview(
                    id=uuid.uuid4(),
                    feature_match_id=fm.id,
                    reviewer_id=None,
                    decision="REJECTED" if request.action == "REJECT_UNRESOLVED" else "ACCEPTED",
                    comment=f"Stage 11 [{request.action}]: {cleaned_notes}" if cleaned_notes else f"Stage 11 [{request.action}]",
                    created_at=now,
                    updated_at=now,
                )
                db.add(match_review)

        # 7. Log ProvenanceEvent
        prov_event = ProvenanceEvent(
            id=uuid.uuid4(),
            project_id=project_id,
            unified_land_record_id=None,
            event_type="HUMAN_REVIEW_OVERRIDE" if is_override else "HUMAN_REVIEW_DECISION",
            source_type="PIPELINE_STAGE_11",
            source_id=decision_record.id,
            event_metadata={
                "harmonized_record_id": record_id,
                "action": request.action,
                "status": new_status,
                "reviewer_name": request.reviewer_name or "Lead GIS Adjudicator",
                "notes": cleaned_notes,
                "authoritative_geometry_source": request.authoritative_geometry_source,
                "authoritative_attributes": sanitized_attrs,
                "override_applied": is_override,
                "previous_state": previous_state,
                "resulting_state": resulting_state,
            },
            created_at=now,
        )
        db.add(prov_event)

        await db.commit()

        # 8. Check Stage 11 completion rule & update PipelineStageExecution
        summary = await cls.get_review_summary(db, project_id)
        stage_status_str = summary.stage_status

        st11_stmt = select(PipelineStageExecution).where(
            PipelineStageExecution.project_id == project_id,
            PipelineStageExecution.stage_id == "review",
        )
        st11_exec = (await db.execute(st11_stmt)).scalar_one_or_none()

        results_payload = {
            "total_review_items": summary.total_review_items,
            "resolved_count": summary.resolved_count,
            "unresolved_count": summary.unresolved_count,
            "accept_source_a_count": summary.accept_source_a_count,
            "accept_source_b_count": summary.accept_source_b_count,
            "merged_count": summary.merged_count,
            "rejected_count": summary.rejected_count,
            "average_confidence": summary.average_confidence,
            "completion_progress_pct": summary.completion_progress_pct,
            "last_adjudication_at": now.isoformat(),
        }

        if not st11_exec:
            st11_exec = PipelineStageExecution(
                id=uuid.uuid4(),
                project_id=project_id,
                stage_number=11,
                stage_id="review",
                status=stage_status_str,
                inputs={"enforce_completion_rule": True},
                results=results_payload,
                started_at=now,
                completed_at=now if summary.is_completed else None,
            )
            db.add(st11_exec)
        else:
            st11_exec.status = stage_status_str
            st11_exec.results = results_payload
            st11_exec.completed_at = now if summary.is_completed else None

        # Emit HUMAN_REVIEW_COMPLETED if stage just became completed
        if summary.is_completed and stage_status_str == "completed":
            comp_prov = ProvenanceEvent(
                id=uuid.uuid4(),
                project_id=project_id,
                unified_land_record_id=None,
                event_type="HUMAN_REVIEW_COMPLETED",
                source_type="PIPELINE_STAGE_11",
                source_id=st11_exec.id,
                event_metadata=results_payload,
                created_at=now,
            )
            db.add(comp_prov)

        await db.commit()

        # Fetch updated item
        updated_item = await cls.get_review_item_detail(db, project_id, record_id)

        return AdjudicationActionResponse(
            success=True,
            record_id=record_id,
            action=request.action,
            status=new_status,
            decision=updated_item,
            summary=summary,
            stage_status=stage_status_str,
            is_stage_completed=summary.is_completed,
            message=f"Adjudication decision [{request.action}] successfully recorded for record '{record_id}'.",
        )

    @classmethod
    async def finalize_stage_11(
        cls, db: AsyncSession, project_id: uuid.UUID
    ) -> Stage11ExecutionResponse:
        """
        Evaluate and finalize Stage 11 completion.
        Only transitions to completed when all records requiring mandatory review are adjudicated.
        """
        summary = await cls.get_review_summary(db, project_id)

        now = datetime.now(timezone.utc)
        st11_stmt = select(PipelineStageExecution).where(
            PipelineStageExecution.project_id == project_id,
            PipelineStageExecution.stage_id == "review",
        )
        st11_exec = (await db.execute(st11_stmt)).scalar_one_or_none()

        results_payload = {
            "total_review_items": summary.total_review_items,
            "resolved_count": summary.resolved_count,
            "unresolved_count": summary.unresolved_count,
            "accept_source_a_count": summary.accept_source_a_count,
            "accept_source_b_count": summary.accept_source_b_count,
            "merged_count": summary.merged_count,
            "rejected_count": summary.rejected_count,
            "average_confidence": summary.average_confidence,
            "completion_progress_pct": summary.completion_progress_pct,
            "last_adjudication_at": now.isoformat(),
        }

        if summary.unresolved_count > 0:
            if st11_exec:
                st11_exec.status = "running" if summary.resolved_count > 0 else "ready"
                st11_exec.results = results_payload
            else:
                st11_exec = PipelineStageExecution(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    stage_number=11,
                    stage_id="review",
                    status="running" if summary.resolved_count > 0 else "ready",
                    inputs={"enforce_completion_rule": True},
                    results=results_payload,
                    started_at=now,
                    completed_at=None,
                )
                db.add(st11_exec)
            await db.commit()

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot finalize Stage 11 Human Review: {summary.unresolved_count} out of "
                    f"{summary.total_review_items} items still require mandatory human adjudication."
                ),
            )

        # All mandatory items resolved -> Mark stage completed
        if not st11_exec:
            st11_exec = PipelineStageExecution(
                id=uuid.uuid4(),
                project_id=project_id,
                stage_number=11,
                stage_id="review",
                status="completed",
                inputs={"enforce_completion_rule": True},
                results=results_payload,
                started_at=now,
                completed_at=now,
            )
            db.add(st11_exec)
        else:
            st11_exec.status = "completed"
            st11_exec.results = results_payload
            st11_exec.completed_at = now

        comp_prov = ProvenanceEvent(
            id=uuid.uuid4(),
            project_id=project_id,
            unified_land_record_id=None,
            event_type="HUMAN_REVIEW_COMPLETED",
            source_type="PIPELINE_STAGE_11",
            source_id=st11_exec.id,
            event_metadata=results_payload,
            created_at=now,
        )
        db.add(comp_prov)

        await db.commit()

        summary.stage_status = "completed"
        summary.is_completed = True

        return Stage11ExecutionResponse(
            stage_number=11,
            stage_id="review",
            status="completed",
            records_adjudicated=summary.resolved_count,
            records_pending=0,
            summary=summary,
            message="Stage 11 Human Review successfully completed. Stage 12 Unified Record is now unlocked.",
        )
