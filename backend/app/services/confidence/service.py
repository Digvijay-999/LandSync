import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Project
from app.models.pipeline import PipelineStageExecution
from app.models.validation import ValidationResult
from app.models.conflict import GeospatialConflict
from app.models.matching import MatchRun, FeatureMatch
from app.models.provenance import ProvenanceEvent
from app.schemas.confidence import (
    ConfidenceRecordItem,
    ConfidenceSummaryResponse,
    ConfidenceResultListResponse,
    ConfidenceScoringRunRequest,
    ConfidenceScoringRunResponse,
)


class ConfidenceScoringService:
    """
    Pipeline Stage 10 Service:
    Transparent multi-component confidence scoring with explainable signal breakdown.

    Formula:
      overall_confidence =
          spatial_weight * spatial_score +
          geometry_weight * geometry_score +
          attribute_weight * attribute_score +
          temporal_weight * temporal_score

    Default weights:
      - spatial: 0.30
      - geometry: 0.30
      - attribute: 0.30
      - temporal: 0.10

    Buckets:
      - >= 0.90: HIGH / AUTO-CONFIRM
      - 0.70 - 0.89: MEDIUM / PENDING REVIEW
      - < 0.70: LOW / MANDATORY REVIEW
      - Ambiguous matches: ALWAYS AMBIGUOUS / MANDATORY REVIEW
      - Unresolved CRITICAL conflicts: Capped at MEDIUM / PENDING REVIEW (auto-confirm disabled)
    """

    @classmethod
    async def execute_stage_10(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        req: ConfidenceScoringRunRequest,
    ) -> ConfidenceScoringRunResponse:
        start_time = time.perf_counter()

        project = await db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project with ID '{project_id}' not found.")

        # 1. Prerequisite verification: Stage 09 Validation or Stage 07 Harmonization
        exec_stmt = (
            select(PipelineStageExecution)
            .where(
                PipelineStageExecution.project_id == project_id,
                PipelineStageExecution.stage_id.in_(["validation", "harmonization"]),
                PipelineStageExecution.status == "completed",
            )
        )
        completed_prereqs = list((await db.execute(exec_stmt)).scalars().all())
        has_validation = any(e.stage_id == "validation" for e in completed_prereqs)
        has_harmonization = any(e.stage_id == "harmonization" for e in completed_prereqs)

        if not has_validation and not has_harmonization:
            raise ValueError(
                "Stage 09 Validation (or Stage 07 Harmonization) must be completed before running Stage 10 Confidence Scoring."
            )

        # 2. Fetch candidate inputs from Stage 09 ValidationResult
        val_stmt = (
            select(ValidationResult)
            .where(ValidationResult.project_id == project_id)
            .order_by(ValidationResult.created_at.asc())
        )
        val_results = list((await db.execute(val_stmt)).scalars().all())

        # Load Stage 07 harmonized records lookup for prior signal preservation
        stage7_exec = next((e for e in completed_prereqs if e.stage_id == "harmonization"), None)
        stage7_by_rec: Dict[str, Dict[str, Any]] = {}
        fallback_records: List[Dict[str, Any]] = []
        if stage7_exec and stage7_exec.results:
            fallback_records = stage7_exec.results.get("records_preview", [])
            for r in fallback_records:
                r_id = r.get("id") or f"{r.get('source_feature_id')}_{r.get('candidate_feature_id')}"
                stage7_by_rec[r_id] = r
                if r.get("harmonized_record_id"):
                    stage7_by_rec[r["harmonized_record_id"]] = r

        if not val_results and not fallback_records:
            raise ValueError("No validated or harmonized candidate records found to score.")

        # 3. Fetch Stage 08 Geospatial Conflicts for correlation
        conflicts_stmt = (
            select(GeospatialConflict)
            .where(GeospatialConflict.project_id == project_id)
        )
        conflicts = list((await db.execute(conflicts_stmt)).scalars().all())
        conflicts_by_record: Dict[str, List[GeospatialConflict]] = defaultdict(list)
        for c in conflicts:
            conflicts_by_record[c.harmonized_record_id].append(c)

        # 4. Fetch FeatureMatch records for the project
        matches_stmt = (
            select(FeatureMatch)
            .where(FeatureMatch.project_id == project_id)
        )
        feature_matches = list((await db.execute(matches_stmt)).scalars().all())
        match_by_pair: Dict[str, FeatureMatch] = {}
        for fm in feature_matches:
            if fm.source_feature_id and fm.candidate_feature_id:
                key = f"{fm.source_feature_id}_{fm.candidate_feature_id}"
                match_by_pair[key] = fm

        # 5. Normalize weights
        raw_sum = (
            req.spatial_weight
            + req.geometry_weight
            + req.attribute_weight
            + req.temporal_weight
        )
        if raw_sum <= 0:
            w_spatial = 0.30
            w_geometry = 0.30
            w_attribute = 0.30
            w_temporal = 0.10
        else:
            w_spatial = round(req.spatial_weight / raw_sum, 4)
            w_geometry = round(req.geometry_weight / raw_sum, 4)
            w_attribute = round(req.attribute_weight / raw_sum, 4)
            w_temporal = round(req.temporal_weight / raw_sum, 4)

        weights_dict = {
            "spatial": w_spatial,
            "geometry": w_geometry,
            "attribute": w_attribute,
            "temporal": w_temporal,
        }

        # 6. Score each candidate record
        scored_records: List[ConfidenceRecordItem] = []
        high_count = 0
        medium_count = 0
        low_count = 0
        ambiguous_count = 0
        auto_confirmed_count = 0
        review_required_count = 0
        conf_sum = 0.0

        records_to_process: List[Dict[str, Any]] = []
        if val_results:
            for vr in val_results:
                records_to_process.append({
                    "id": str(vr.id),
                    "harmonized_record_id": vr.harmonized_record_id,
                    "source_feature_id": vr.source_feature_id,
                    "candidate_feature_id": vr.candidate_feature_id,
                    "source_identifier": vr.source_identifier or "Unknown",
                    "candidate_identifier": vr.candidate_identifier or "Unknown",
                    "overall_status": vr.overall_status,
                    "geometry_validity_status": vr.geometry_validity_status,
                    "topology_status": vr.topology_status,
                    "area_status": vr.area_status,
                    "semantic_status": vr.semantic_status,
                    "conflict_status": vr.conflict_status,
                    "geometry_metrics": vr.geometry_metrics or {},
                    "topology_metrics": vr.topology_metrics or {},
                    "area_metrics": vr.area_metrics or {},
                    "semantic_metrics": vr.semantic_metrics or {},
                    "conflict_metrics": vr.conflict_metrics or {},
                })
        else:
            for r in fallback_records:
                rec_id = r.get("id", "")
                parts = rec_id.split("_")
                sf_id = None
                cf_id = None
                if len(parts) >= 2:
                    try:
                        sf_id = uuid.UUID(parts[0])
                        cf_id = uuid.UUID(parts[1])
                    except (ValueError, TypeError):
                        pass

                records_to_process.append({
                    "id": rec_id,
                    "harmonized_record_id": rec_id,
                    "source_feature_id": sf_id,
                    "candidate_feature_id": cf_id,
                    "source_identifier": r.get("source_identifier", "Unknown"),
                    "candidate_identifier": r.get("candidate_identifier", "Unknown"),
                    "overall_status": "PASS" if not r.get("has_conflicts") else "WARNING",
                    "geometry_validity_status": "PASS" if r.get("geometry_status") != "INVALID" else "FAIL",
                    "topology_status": "PASS" if r.get("geometry_status") == "CONGRUENT" else "WARNING",
                    "area_status": "PASS" if (r.get("area_discrepancy_pct") or 0.0) <= 5.0 else ("WARNING" if (r.get("area_discrepancy_pct") or 0.0) <= 15.0 else "FAIL"),
                    "semantic_status": "PASS",
                    "conflict_status": "PASS" if not r.get("has_conflicts") else "WARNING",
                    "geometry_metrics": {"is_valid": r.get("geometry_status") != "INVALID"},
                    "topology_metrics": {"iou_pct": 95.0 if r.get("geometry_status") == "CONGRUENT" else 65.0},
                    "area_metrics": {"discrepancy_pct": r.get("area_discrepancy_pct", 0.0)},
                    "semantic_metrics": {
                        "source_land_use": r.get("source_land_use"),
                        "candidate_land_use": r.get("candidate_land_use"),
                    },
                    "conflict_metrics": {"total_conflicts_associated": r.get("conflict_count", 0)},
                })

        for item in records_to_process:
            rec_id = item["harmonized_record_id"]
            fm = match_by_pair.get(rec_id)
            st7 = stage7_by_rec.get(rec_id, {})

            # Signal 1: Spatial Score (0.0 to 1.0)
            if fm and fm.spatial_score is not None:
                spatial_score = float(fm.spatial_score)
            elif st7.get("spatial_score") is not None:
                spatial_score = float(st7["spatial_score"])
            else:
                top_m = item.get("topology_metrics", {})
                iou = float(top_m.get("iou_pct") or 0.0)
                if top_m.get("overlap_ratio") is not None:
                    spatial_score = float(top_m["overlap_ratio"])
                elif iou > 0:
                    spatial_score = min(1.0, max(0.0, iou / 100.0))
                else:
                    spatial_score = 0.85
            spatial_score = round(min(1.0, max(0.0, spatial_score)), 4)

            # Signal 2: Geometry & Area Score (0.0 to 1.0)
            geom_m = item.get("geometry_metrics", {})
            geom_valid = bool(geom_m.get("is_valid", True))
            if item.get("geometry_validity_status") == "FAIL" or not geom_valid:
                geometry_score = 0.0
            elif fm and fm.geometry_score is not None:
                geometry_score = float(fm.geometry_score)
            elif st7.get("geometry_score") is not None:
                geometry_score = float(st7["geometry_score"])
            else:
                area_m = item.get("area_metrics", {})
                disc = float(area_m.get("discrepancy_pct") or 0.0)
                disc_penalty = min(1.0, disc / 100.0)
                base_geom = 1.0 - (disc_penalty * 0.75)
                if item.get("area_status") == "FAIL":
                    base_geom = min(base_geom, 0.40)
                elif item.get("area_status") == "WARNING":
                    base_geom = min(base_geom, 0.75)
                geometry_score = max(0.0, min(1.0, base_geom))
            geometry_score = round(min(1.0, max(0.0, geometry_score)), 4)

            # Signal 3: Semantic Attribute Score (0.0 to 1.0)
            if fm and fm.attribute_score is not None:
                attribute_score = float(fm.attribute_score)
            elif st7.get("attribute_score") is not None:
                attribute_score = float(st7["attribute_score"])
            else:
                sem_m = item.get("semantic_metrics", {})
                src_lu = str(sem_m.get("source_land_use") or "").strip().lower()
                cand_lu = str(sem_m.get("candidate_land_use") or "").strip().lower()
                sem_score = 0.85
                if src_lu and cand_lu:
                    if src_lu == cand_lu:
                        sem_score = 1.0
                    elif any(w in cand_lu for w in src_lu.split()) or any(w in src_lu for w in cand_lu.split()):
                        sem_score = 0.80
                    else:
                        sem_score = 0.45
                if item.get("semantic_status") == "FAIL":
                    sem_score = min(sem_score, 0.30)
                attribute_score = sem_score
            attribute_score = round(min(1.0, max(0.0, attribute_score)), 4)

            # Signal 4: Temporal Score (0.0 to 1.0)
            if st7.get("temporal_score") is not None:
                temporal_score = float(st7["temporal_score"])
            elif item.get("overall_status") == "PASS":
                temporal_score = 1.0
            elif item.get("overall_status") == "WARNING":
                temporal_score = 0.90
            else:
                temporal_score = 0.80
            temporal_score = round(temporal_score, 4)

            # Weighted Formula Calculation
            spatial_contrib = round(w_spatial * spatial_score, 4)
            geometry_contrib = round(w_geometry * geometry_score, 4)
            attribute_contrib = round(w_attribute * attribute_score, 4)
            temporal_contrib = round(w_temporal * temporal_score, 4)

            raw_confidence = round(
                spatial_contrib + geometry_contrib + attribute_contrib + temporal_contrib,
                4,
            )
            raw_confidence = min(1.0, max(0.0, raw_confidence))

            # Ambiguity & Conflict Checks
            rec_conflicts = conflicts_by_record.get(rec_id, [])
            crit_count = len([
                c for c in rec_conflicts
                if c.severity == "CRITICAL" and str(c.status).upper() in ["OPEN", "UNRESOLVED", "DETECTED"]
            ])
            has_critical = (crit_count > 0)
            has_high = any(
                c.severity == "HIGH" and str(c.status).upper() in ["OPEN", "UNRESOLVED", "DETECTED"]
                for c in rec_conflicts
            )
            validation_failed = (item.get("overall_status") == "FAIL")

            is_ambiguous = bool(st7.get("is_ambiguous", False))
            if fm:
                if fm.candidate_role == "AMBIGUOUS" or getattr(fm, "is_ambiguous", False):
                    is_ambiguous = True
                elif fm.score_gap is not None and fm.score_gap < 0.015 and fm.candidate_count > 1:
                    is_ambiguous = True

            reasons: List[str] = [
                f"Spatial overlap score {spatial_score:.2f} contributes +{spatial_contrib:.3f} (weight {w_spatial:.2f})",
                f"Geometry concordance score {geometry_score:.2f} contributes +{geometry_contrib:.3f} (weight {w_geometry:.2f})",
                f"Attribute alignment score {attribute_score:.2f} contributes +{attribute_contrib:.3f} (weight {w_attribute:.2f})",
                f"Temporal consistency score {temporal_score:.2f} contributes +{temporal_contrib:.3f} (weight {w_temporal:.2f})",
            ]

            overall_conf = raw_confidence

            # Integration of Conflicts & Validation:
            # Cannot auto-confirm if unresolved critical conflicts or validation failure exists
            if req.respect_critical_conflicts and (has_critical or validation_failed):
                overall_conf = min(overall_conf, 0.78)
                reasons.append(
                    "Score capped at 0.78 (MEDIUM) and auto-confirm disabled due to unresolved CRITICAL conflict or validation failure."
                )

            if has_high and overall_conf > 0.85:
                overall_conf = round(overall_conf - 0.05, 4)
                reasons.append("Applied -0.05 confidence penalty for open HIGH severity conflict.")

            # Determine Bucket & Review Status
            if is_ambiguous:
                bucket = "AMBIGUOUS"
                bucket_label = "AMBIGUOUS / MANDATORY REVIEW"
                review_status = "FLAGGED"
                ambiguous_count += 1
                review_required_count += 1
                reasons.append("Mandatory review: competing candidate parcels within tie tolerance.")
            elif overall_conf >= req.high_threshold and not (has_critical or validation_failed):
                bucket = "HIGH"
                bucket_label = "HIGH / AUTO-CONFIRM"
                review_status = "ACCEPTED"
                high_count += 1
                auto_confirmed_count += 1
                reasons.append("High confidence meets auto-confirm threshold (>= 0.90) with no blocking conflicts.")
            elif overall_conf >= req.medium_threshold:
                bucket = "MEDIUM"
                bucket_label = "MEDIUM / PENDING REVIEW"
                review_status = "FLAGGED" if (has_critical or validation_failed) else "PENDING"
                medium_count += 1
                review_required_count += 1
                reasons.append("Medium confidence requires secondary verification before finalization.")
            else:
                bucket = "LOW"
                bucket_label = "LOW / MANDATORY REVIEW"
                review_status = "FLAGGED"
                low_count += 1
                review_required_count += 1
                reasons.append("Low confidence below threshold (< 0.70): manual field adjudication mandated.")

            explanation = (
                f"Overall confidence {overall_conf:.2f} ({bucket_label}). "
                f"Weighted signals: Spatial ({spatial_score:.2f} * {w_spatial:.2f}), "
                f"Geometry ({geometry_score:.2f} * {w_geometry:.2f}), "
                f"Attributes ({attribute_score:.2f} * {w_attribute:.2f}), "
                f"Temporal ({temporal_score:.2f} * {w_temporal:.2f})."
            )

            record_item = ConfidenceRecordItem(
                id=str(item["id"]),
                project_id=project_id,
                record_identifier=f"{item['source_identifier']} ↔ {item['candidate_identifier']}",
                source_identifier=item["source_identifier"],
                candidate_identifier=item.get("candidate_identifier") or "Unknown",
                source_feature_id=str(item["source_feature_id"]) if item.get("source_feature_id") else None,
                candidate_feature_id=str(item["candidate_feature_id"]) if item.get("candidate_feature_id") else None,
                feature_match_id=str(fm.id) if fm and fm.id else None,
                overall_confidence=overall_conf,
                confidence_bucket=bucket,
                bucket_label=bucket_label,
                review_status=review_status,
                spatial_score=spatial_score,
                geometry_score=geometry_score,
                attribute_score=attribute_score,
                temporal_score=temporal_score,
                weights=weights_dict,
                contributions={
                    "spatial": spatial_contrib,
                    "geometry": geometry_contrib,
                    "attribute": attribute_contrib,
                    "temporal": temporal_contrib,
                },
                is_ambiguous=is_ambiguous,
                has_critical_conflicts=has_critical,
                critical_conflict_count=crit_count,
                validation_status=item.get("overall_status", "PASS"),
                explanation=explanation,
                reasons=reasons,
            )
            scored_records.append(record_item)
            conf_sum += overall_conf

            # Update existing FeatureMatch if present
            if fm:
                fm.overall_score = overall_conf
                fm.review_status = review_status
                fm.explanation = {
                    "overall_confidence": overall_conf,
                    "confidence_bucket": bucket,
                    "bucket_label": bucket_label,
                    "review_status": review_status,
                    "component_scores": {
                        "spatial": spatial_score,
                        "geometry": geometry_score,
                        "attribute": attribute_score,
                        "temporal": temporal_score,
                    },
                    "weights": weights_dict,
                    "contributions": {
                        "spatial": spatial_contrib,
                        "geometry": geometry_contrib,
                        "attribute": attribute_contrib,
                        "temporal": temporal_contrib,
                    },
                    "is_ambiguous": is_ambiguous,
                    "has_critical_conflicts": has_critical,
                    "reasons": reasons,
                    "scoring_model": "Multi-Component Explainable Confidence v1.0",
                }

        total_scored = len(scored_records)
        avg_confidence = round(conf_sum / max(1, total_scored), 4)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        now = datetime.now(timezone.utc)

        # 7. Persist Stage 10 execution state in pipeline_stage_executions
        stage10_exec_stmt = (
            select(PipelineStageExecution)
            .where(
                PipelineStageExecution.project_id == project_id,
                PipelineStageExecution.stage_id == "confidence",
            )
        )
        stage10_exec = (await db.execute(stage10_exec_stmt)).scalar_one_or_none()

        results_data = {
            "records_scored": total_scored,
            "total_records_scored": total_scored,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
            "ambiguous_count": ambiguous_count,
            "review_required_count": review_required_count,
            "auto_confirmed_count": auto_confirmed_count,
            "average_confidence": avg_confidence,
            "weights": weights_dict,
            "scoring_model": "Multi-Component Explainable Confidence v1.0",
            "execution_time_ms": duration_ms,
            "records_preview": [r.model_dump(mode="json") for r in scored_records],
        }

        if not stage10_exec:
            stage10_exec = PipelineStageExecution(
                id=uuid.uuid4(),
                project_id=project_id,
                stage_number=10,
                stage_id="confidence",
                status="completed",
                inputs=req.model_dump(mode="json"),
                results=results_data,
                started_at=now,
                completed_at=now,
            )
            db.add(stage10_exec)
        else:
            stage10_exec.status = "completed"
            stage10_exec.inputs = req.model_dump(mode="json")
            stage10_exec.results = results_data
            stage10_exec.completed_at = now

        # 8. Record Provenance Audit Event
        prov_event = ProvenanceEvent(
            id=uuid.uuid4(),
            project_id=project_id,
            event_type="CONFIDENCE_SCORING_EXECUTED",
            source_type="PIPELINE_STAGE_10",
            source_id=stage10_exec.id,
            event_metadata={
                "total_records_scored": total_scored,
                "high_count": high_count,
                "medium_count": medium_count,
                "low_count": low_count,
                "ambiguous_count": ambiguous_count,
                "review_required_count": review_required_count,
                "auto_confirmed_count": auto_confirmed_count,
                "average_confidence": avg_confidence,
                "weights": weights_dict,
                "execution_time_ms": duration_ms,
            },
            created_at=now,
        )
        db.add(prov_event)

        await db.commit()

        return ConfidenceScoringRunResponse(
            stage_id="confidence",
            stage_number=10,
            status="completed",
            project_id=project_id,
            records_scored=total_scored,
            total_records_scored=total_scored,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            ambiguous_count=ambiguous_count,
            review_required_count=review_required_count,
            auto_confirmed_count=auto_confirmed_count,
            average_confidence=avg_confidence,
            execution_time_ms=duration_ms,
            records_preview=scored_records,
        )

    @classmethod
    async def get_confidence_summary(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> ConfidenceSummaryResponse:
        exec_stmt = (
            select(PipelineStageExecution)
            .where(
                PipelineStageExecution.project_id == project_id,
                PipelineStageExecution.stage_id == "confidence",
            )
        )
        stage_exec = (await db.execute(exec_stmt)).scalar_one_or_none()

        if stage_exec and stage_exec.results:
            res = stage_exec.results
            return ConfidenceSummaryResponse(
                project_id=project_id,
                total_records_scored=res.get("total_records_scored", 0),
                high_count=res.get("high_count", 0),
                medium_count=res.get("medium_count", 0),
                low_count=res.get("low_count", 0),
                ambiguous_count=res.get("ambiguous_count", 0),
                review_required_count=res.get("review_required_count", 0),
                auto_confirmed_count=res.get("auto_confirmed_count", 0),
                average_confidence=res.get("average_confidence", 0.0),
                weights=res.get("weights", {"spatial": 0.30, "geometry": 0.30, "attribute": 0.30, "temporal": 0.10}),
                scoring_model=res.get("scoring_model", "Multi-Component Explainable Confidence v1.0"),
                execution_time_ms=res.get("execution_time_ms"),
                last_run_at=stage_exec.completed_at,
            )

        return ConfidenceSummaryResponse(
            project_id=project_id,
            total_records_scored=0,
            high_count=0,
            medium_count=0,
            low_count=0,
            ambiguous_count=0,
            review_required_count=0,
            auto_confirmed_count=0,
            average_confidence=0.0,
            weights={"spatial": 0.30, "geometry": 0.30, "attribute": 0.30, "temporal": 0.10},
            scoring_model="Multi-Component Explainable Confidence v1.0",
        )

    @classmethod
    async def get_confidence_results(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        bucket: Optional[str] = None,
        review_status: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> ConfidenceResultListResponse:
        exec_stmt = (
            select(PipelineStageExecution)
            .where(
                PipelineStageExecution.project_id == project_id,
                PipelineStageExecution.stage_id == "confidence",
            )
        )
        stage_exec = (await db.execute(exec_stmt)).scalar_one_or_none()

        items: List[ConfidenceRecordItem] = []
        if stage_exec and stage_exec.results and "records_preview" in stage_exec.results:
            raw_list = stage_exec.results["records_preview"]
            for r in raw_list:
                item = ConfidenceRecordItem(**r)

                # Filter by bucket (HIGH, MEDIUM, LOW, AMBIGUOUS)
                if bucket and bucket.upper() != "ALL" and item.confidence_bucket.upper() != bucket.upper():
                    continue

                # Filter by review status (ACCEPTED, PENDING, FLAGGED)
                if review_status and review_status.upper() != "ALL" and item.review_status.upper() != review_status.upper():
                    continue

                # Search filter (source/candidate identifier)
                if search and search.strip():
                    q = search.strip().lower()
                    if (
                        q not in item.source_identifier.lower()
                        and q not in item.candidate_identifier.lower()
                        and q not in item.record_identifier.lower()
                    ):
                        continue

                items.append(item)

        total = len(items)
        paged_items = items[skip : skip + limit]
        summary = await cls.get_confidence_summary(db, project_id)

        return ConfidenceResultListResponse(
            items=paged_items,
            total=total,
            skip=skip,
            limit=limit,
            summary=summary,
        )

    @classmethod
    def normalize_weights(cls, weights: Dict[str, float]) -> Dict[str, float]:
        raw_sum = sum(weights.values())
        if raw_sum <= 0:
            return {"spatial": 0.30, "geometry": 0.30, "attribute": 0.30, "temporal": 0.10}
        return {k: round(v / raw_sum, 4) for k, v in weights.items()}

    @classmethod
    def calculate_overall_confidence(
        cls,
        spatial_score: float,
        geometry_score: float,
        attribute_score: float,
        temporal_score: float,
        weights: Optional[Dict[str, float]] = None,
    ) -> Tuple[float, Dict[str, float]]:
        w = weights or {"spatial": 0.30, "geometry": 0.30, "attribute": 0.30, "temporal": 0.10}
        w_spatial = w.get("spatial", 0.30)
        w_geom = w.get("geometry", 0.30)
        w_attr = w.get("attribute", 0.30)
        w_temp = w.get("temporal", 0.10)

        s_contrib = round(w_spatial * spatial_score, 4)
        g_contrib = round(w_geom * geometry_score, 4)
        a_contrib = round(w_attr * attribute_score, 4)
        t_contrib = round(w_temp * temporal_score, 4)

        overall = round(s_contrib + g_contrib + a_contrib + t_contrib, 4)
        contribs = {
            "spatial": s_contrib,
            "geometry": g_contrib,
            "attribute": a_contrib,
            "temporal": t_contrib,
        }
        return overall, contribs

    @classmethod
    def assign_bucket(
        cls,
        overall_confidence: float,
        is_ambiguous: bool = False,
        high_threshold: float = 0.90,
        medium_threshold: float = 0.70,
    ) -> Tuple[str, str]:
        if is_ambiguous:
            return "AMBIGUOUS", "FLAGGED"
        if overall_confidence >= high_threshold:
            return "HIGH", "ACCEPTED"
        if overall_confidence >= medium_threshold:
            return "MEDIUM", "PENDING"
        return "LOW", "FLAGGED"

    @classmethod
    async def get_confidence_result_detail(
        cls,
        db: AsyncSession,
        record_id: Any,
        project_id: Optional[uuid.UUID] = None,
    ) -> Optional[ConfidenceRecordItem]:
        rec_str = str(record_id)
        stmt = (
            select(PipelineStageExecution)
            .where(PipelineStageExecution.stage_id == "confidence")
            .order_by(PipelineStageExecution.completed_at.desc())
        )
        if project_id:
            stmt = stmt.where(PipelineStageExecution.project_id == project_id)

        executions = list((await db.execute(stmt)).scalars().all())
        for stage_exec in executions:
            if stage_exec.results and "records_preview" in stage_exec.results:
                for r in stage_exec.results["records_preview"]:
                    if (
                        str(r.get("id")) == rec_str
                        or str(r.get("feature_match_id")) == rec_str
                        or r.get("record_identifier") == rec_str
                    ):
                        return ConfidenceRecordItem(**r)

        return None

    # Aliases
    get_confidence_detail = get_confidence_result_detail
    list_confidence_results = get_confidence_results

