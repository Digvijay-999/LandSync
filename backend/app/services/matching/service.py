import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, func, desc, case, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from shapely.geometry import mapping

from app.models.project import Project
from app.models.dataset import Dataset, DatasetVersion
from app.models.feature import CanonicalFeature
from app.models.matching import MatchRun, FeatureMatch, MatchReview
from app.services.dataset import extract_shapely_geom
from app.services.matching.config import MatchingConfig
from app.services.matching.candidate_generator import CandidateGenerator
from app.services.matching.signals import MatchingSignals
from app.services.matching.scoring import ScoringEngine
from app.services.matching.ranker import CandidateRanker


def extract_feature_display_id(cf: Optional[CanonicalFeature]) -> Optional[str]:
    if not cf:
        return None
    props = cf.canonical_properties or {}
    for key in ["parcel_id", "asset_id", "structure_id", "building_id", "facility_id", "fid", "property_id", "id", "code"]:
        if key in props and props[key]:
            return str(props[key])
    if hasattr(cf, "source_feature") and cf.source_feature and cf.source_feature.source_feature_id:
        return str(cf.source_feature.source_feature_id)
    return str(cf.source_feature_id or cf.id)


class MatchingService:
    """
    Orchestration service for spatial candidate generation, explainable multi-signal
    matching, classification, and persistent reconciliation records.
    """

    @classmethod
    async def create_and_run_matching(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        source_dataset_id: uuid.UUID,
        candidate_dataset_ids: List[uuid.UUID],
        config: Optional[MatchingConfig] = None,
    ) -> MatchRun:
        """
        Executes a deterministic, explainable cross-dataset feature matching run.
        """
        if config is None:
            config = MatchingConfig()

        # 1. Validation & Security Checks
        project = await db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project with ID '{project_id}' not found.")

        # Validate source dataset
        source_ds = await db.get(Dataset, source_dataset_id)
        if not source_ds or source_ds.project_id != project_id:
            raise ValueError(f"Source dataset '{source_dataset_id}' does not belong to project '{project_id}'.")

        # Validate candidate datasets (prevent cross-project matching)
        if not candidate_dataset_ids:
            raise ValueError("At least one candidate dataset ID must be provided.")

        for cand_id in candidate_dataset_ids:
            cand_ds = await db.get(Dataset, cand_id)
            if not cand_ds or cand_ds.project_id != project_id:
                raise ValueError(f"Candidate dataset '{cand_id}' does not belong to project '{project_id}'.")
            if cand_id == source_dataset_id:
                raise ValueError("Source dataset cannot be compared against itself.")

        # Cache dataset version to dataset ID mapping
        version_to_dataset_map: Dict[uuid.UUID, uuid.UUID] = {}
        for ds_id in [source_dataset_id] + candidate_dataset_ids:
            stmt = select(DatasetVersion.id).where(DatasetVersion.dataset_id == ds_id)
            for v_id in (await db.execute(stmt)).scalars().all():
                version_to_dataset_map[v_id] = ds_id

        # 2. Initialize MatchRun Record
        run_id = uuid.uuid4()
        run = MatchRun(
            id=run_id,
            project_id=project_id,
            source_dataset_id=source_dataset_id,
            candidate_dataset_ids=[str(cid) for cid in candidate_dataset_ids],
            configuration=config.to_dict(),
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        await db.flush()

        try:
            # 3. Spatial Candidate Generation (using PostGIS GIST indexes)
            pairs = await CandidateGenerator.get_candidate_pairs(
                db=db,
                source_dataset_id=source_dataset_id,
                candidate_dataset_ids=candidate_dataset_ids,
                distance_meters=config.candidate_search_distance_meters,
            )

            # 4. Multi-Signal Scoring & Classification
            feature_matches: List[FeatureMatch] = []
            distinct_source_ids = set()
            total_candidates = 0
            matches_count = 0
            possible_count = 0
            conflicts_count = 0
            unmatched_count = 0

            for src_feat, cand_feat in pairs:
                distinct_source_ids.add(src_feat.id)
                cand_ds_id = version_to_dataset_map.get(cand_feat.dataset_version_id) if cand_feat else None

                if cand_feat is None:
                    # Feature with no candidate within spatial tolerance
                    unmatched_count += 1
                    explanation = {
                        "overall_score": 0.0,
                        "status": "unmatched",
                        "reasons": ["No candidate features found within the configured search tolerance."],
                        "component_scores": {
                            "spatial_overlap": None,
                            "centroid_similarity": 0.0,
                            "area_similarity": None,
                            "geometry_similarity": 0.0,
                            "attribute_similarity": 0.0,
                        },
                        "attribute_alignments": [],
                        "scoring_version": config.scoring_version,
                    }
                    fm = FeatureMatch(
                        id=uuid.uuid4(),
                        match_run_id=run_id,
                        project_id=project_id,
                        source_feature_id=src_feat.id,
                        candidate_feature_id=None,
                        source_dataset_id=source_dataset_id,
                        candidate_dataset_id=None,
                        spatial_score=None,
                        centroid_score=0.0,
                        area_score=None,
                        geometry_score=0.0,
                        attribute_score=0.0,
                        overall_score=0.0,
                        status="unmatched",
                        explanation=explanation,
                        scoring_version=config.scoring_version,
                    )
                    feature_matches.append(fm)
                else:
                    total_candidates += 1

                    # Compute individual signals
                    sp_score = MatchingSignals.spatial_overlap(src_feat.geometry, cand_feat.geometry)
                    cent_score = MatchingSignals.centroid_distance(
                        src_feat.geometry, cand_feat.geometry, config.candidate_search_distance_meters
                    )
                    ar_score = MatchingSignals.area_similarity(src_feat.geometry, cand_feat.geometry)
                    geom_score = MatchingSignals.geometry_similarity(
                        src_feat.geometry, cand_feat.geometry, config.candidate_search_distance_meters
                    )
                    attr_score, attr_details = MatchingSignals.attribute_similarity(
                        src_feat.canonical_properties, cand_feat.canonical_properties
                    )

                    # Evaluate overall score, classification, and explanation
                    ov_score, status, explanation = ScoringEngine.evaluate_match(
                        spatial_score=sp_score,
                        centroid_score=cent_score,
                        area_score=ar_score,
                        geometry_score=geom_score,
                        attribute_score=attr_score,
                        attribute_details=attr_details,
                        config=config,
                        geom_type_a=src_feat.geometry_type,
                        geom_type_b=cand_feat.geometry_type,
                    )

                    if status == "matched":
                        matches_count += 1
                    elif status == "possible_match":
                        possible_count += 1
                    elif status == "conflict":
                        conflicts_count += 1
                    else:
                        unmatched_count += 1

                    fm = FeatureMatch(
                        id=uuid.uuid4(),
                        match_run_id=run_id,
                        project_id=project_id,
                        source_feature_id=src_feat.id,
                        candidate_feature_id=cand_feat.id,
                        source_dataset_id=source_dataset_id,
                        candidate_dataset_id=cand_ds_id,
                        spatial_score=sp_score,
                        centroid_score=cent_score,
                        area_score=ar_score,
                        geometry_score=geom_score,
                        attribute_score=attr_score,
                        overall_score=ov_score,
                        status=status,
                        explanation=explanation,
                        scoring_version=config.scoring_version,
                    )
                    feature_matches.append(fm)

            # 5. Milestone 3.1: Candidate Ranking, Roles, and Quality Metrics
            quality_metrics = CandidateRanker.rank_matches_for_run(feature_matches, config)

            # 6. Persist Results Atomically
            run.total_features_processed = len(distinct_source_ids)
            run.total_candidates = total_candidates
            run.total_matches = matches_count
            run.total_possible_matches = possible_count
            run.total_conflicts = conflicts_count
            run.total_unmatched = unmatched_count
            run.quality_metrics = quality_metrics
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)

            db.add_all(feature_matches)
            await db.commit()

            return await cls.get_matching_run(db, run_id)  # type: ignore

        except Exception as exc:
            await db.rollback()
            # Record run failure if possible
            try:
                failed_run = await db.get(MatchRun, run_id)
                if failed_run:
                    failed_run.status = "failed"
                    failed_run.error_message = str(exc)[:990]
                    failed_run.completed_at = datetime.now(timezone.utc)
                    await db.commit()
            except Exception:
                pass
            raise

    @classmethod
    async def list_matching_runs(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[MatchRun], int]:
        total_stmt = (
            select(func.count())
            .select_from(MatchRun)
            .where(MatchRun.project_id == project_id)
        )
        total = (await db.execute(total_stmt)).scalar() or 0

        stmt = (
            select(MatchRun)
            .where(MatchRun.project_id == project_id)
            .order_by(desc(MatchRun.created_at))
            .offset(skip)
            .limit(limit)
        )
        runs = list((await db.execute(stmt)).scalars().all())
        return runs, total

    @classmethod
    async def get_matching_run(
        cls,
        db: AsyncSession,
        run_id: uuid.UUID,
    ) -> Optional[MatchRun]:
        stmt = (
            select(MatchRun)
            .where(MatchRun.id == run_id)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @classmethod
    async def get_run_matches(
        cls,
        db: AsyncSession,
        run_id: uuid.UUID,
        status: Optional[str] = None,
        candidate_role: Optional[str] = None,
        is_best_only: Optional[bool] = None,
        min_confidence: Optional[float] = None,
        max_confidence: Optional[float] = None,
        source_dataset_id: Optional[uuid.UUID] = None,
        candidate_dataset_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[FeatureMatch], int]:
        """
        Retrieves paginated, filtered match results for a given match run.
        """
        base_query = select(FeatureMatch).where(FeatureMatch.match_run_id == run_id)

        if status and status.strip():
            base_query = base_query.where(FeatureMatch.status == status.strip().lower())
        if candidate_role and candidate_role.strip():
            base_query = base_query.where(FeatureMatch.candidate_role == candidate_role.strip().upper())
        if is_best_only is not None and is_best_only:
            base_query = base_query.where(FeatureMatch.is_best_candidate == True)
        if min_confidence is not None:
            base_query = base_query.where(FeatureMatch.overall_score >= min_confidence)
        if max_confidence is not None:
            base_query = base_query.where(FeatureMatch.overall_score <= max_confidence)
        if source_dataset_id:
            base_query = base_query.where(FeatureMatch.source_dataset_id == source_dataset_id)
        if candidate_dataset_id:
            base_query = base_query.where(FeatureMatch.candidate_dataset_id == candidate_dataset_id)

        total_stmt = select(func.count()).select_from(base_query.subquery())
        total = (await db.execute(total_stmt)).scalar() or 0

        stmt = (
            base_query
            .options(
                joinedload(FeatureMatch.source_feature),
                joinedload(FeatureMatch.candidate_feature),
                joinedload(FeatureMatch.source_dataset),
                joinedload(FeatureMatch.candidate_dataset),
            )
            .order_by(desc(FeatureMatch.overall_score), FeatureMatch.rank.asc().nullslast())
            .offset(skip)
            .limit(limit)
        )
        matches = list((await db.execute(stmt)).scalars().all())
        return matches, total

    @classmethod
    async def get_match_detail(
        cls,
        db: AsyncSession,
        match_id: uuid.UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Returns full structured details of a feature match including source and candidate
        geometries (as GeoJSON mappings) for visual reconciliation.
        """
        stmt = (
            select(FeatureMatch)
            .where(FeatureMatch.id == match_id)
            .options(
                joinedload(FeatureMatch.source_feature),
                joinedload(FeatureMatch.candidate_feature),
                joinedload(FeatureMatch.source_dataset),
                joinedload(FeatureMatch.candidate_dataset),
                selectinload(FeatureMatch.reviews),
            )
        )
        fm = (await db.execute(stmt)).scalar_one_or_none()
        if not fm:
            return None

        # Extract source feature geometry
        src_sh = extract_shapely_geom(fm.source_feature.geometry)
        src_geom_dict = mapping(src_sh) if src_sh and not src_sh.is_empty else None

        # Extract candidate feature geometry
        cand_geom_dict = None
        if fm.candidate_feature:
            cand_sh = extract_shapely_geom(fm.candidate_feature.geometry)
            cand_geom_dict = mapping(cand_sh) if cand_sh and not cand_sh.is_empty else None

        # Calculate intersection geometry for visual overlap highlight if both are polygons
        intersection_geom_dict = None
        if src_sh and fm.candidate_feature:
            cand_sh = extract_shapely_geom(fm.candidate_feature.geometry)
            if cand_sh and src_sh.intersects(cand_sh):
                try:
                    inter_sh = src_sh.intersection(cand_sh)
                    if inter_sh and not inter_sh.is_empty:
                        intersection_geom_dict = mapping(inter_sh)
                except Exception:
                    pass

        reviews_list = [
            {
                "id": r.id,
                "feature_match_id": r.feature_match_id,
                "decision": r.decision,
                "comment": r.comment,
                "reviewer_id": r.reviewer_id,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in (fm.reviews or [])
        ]

        return {
            "id": str(fm.id),
            "match_run_id": str(fm.match_run_id),
            "project_id": str(fm.project_id),
            "status": fm.status,
            "overall_score": fm.overall_score,
            "rank": fm.rank,
            "is_best_candidate": fm.is_best_candidate,
            "candidate_role": fm.candidate_role,
            "score_gap": fm.score_gap,
            "candidate_count": fm.candidate_count,
            "review_status": fm.review_status,
            "spatial_score": fm.spatial_score,
            "centroid_score": fm.centroid_score,
            "area_score": fm.area_score,
            "geometry_score": fm.geometry_score,
            "attribute_score": fm.attribute_score,
            "explanation": fm.explanation,
            "scoring_version": fm.scoring_version,
            "created_at": fm.created_at,
            "source_feature": {
                "id": str(fm.source_feature.id),
                "source_feature_id": extract_feature_display_id(fm.source_feature) or str(fm.source_feature.id),
                "geometry_type": fm.source_feature.geometry_type,
                "source_crs": fm.source_feature.source_crs,
                "target_crs": fm.source_feature.target_crs,
                "properties": fm.source_feature.canonical_properties,
                "geometry": src_geom_dict,
                "dataset_name": fm.source_dataset.name if fm.source_dataset else "Source Dataset",
            },
            "candidate_feature": {
                "id": str(fm.candidate_feature.id),
                "source_feature_id": extract_feature_display_id(fm.candidate_feature) or str(fm.candidate_feature.id),
                "geometry_type": fm.candidate_feature.geometry_type,
                "source_crs": fm.candidate_feature.source_crs,
                "target_crs": fm.candidate_feature.target_crs,
                "properties": fm.candidate_feature.canonical_properties,
                "geometry": cand_geom_dict,
                "dataset_name": fm.candidate_dataset.name if fm.candidate_dataset else "Candidate Dataset",
            } if fm.candidate_feature else None,
            "intersection_geometry": intersection_geom_dict,
            "reviews": reviews_list,
        }

    @classmethod
    async def get_source_feature_candidates(
        cls,
        db: AsyncSession,
        run_id: uuid.UUID,
        feature_id: uuid.UUID,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves all evaluated candidate matches for a single source feature,
        ordered by rank ascending.
        """
        stmt = (
            select(FeatureMatch)
            .where(
                FeatureMatch.match_run_id == run_id,
                FeatureMatch.source_feature_id == feature_id,
            )
            .options(
                joinedload(FeatureMatch.candidate_feature),
                joinedload(FeatureMatch.candidate_dataset),
            )
            .order_by(FeatureMatch.rank.asc().nullslast(), desc(FeatureMatch.overall_score))
        )
        matches = list((await db.execute(stmt)).scalars().all())

        results = []
        for m in matches:
            cand_id_str = extract_feature_display_id(m.candidate_feature) if m.candidate_feature else None
            results.append({
                "match_id": m.id,
                "candidate_feature_id": m.candidate_feature_id,
                "candidate_identifier": cand_id_str,
                "candidate_dataset_id": m.candidate_dataset_id,
                "candidate_dataset_name": m.candidate_dataset.name if m.candidate_dataset else None,
                "candidate_geometry_type": m.candidate_feature.geometry_type if m.candidate_feature else None,
                "overall_score": m.overall_score,
                "rank": m.rank,
                "is_best_candidate": m.is_best_candidate,
                "candidate_role": m.candidate_role,
                "score_gap": m.score_gap,
                "status": m.status,
                "spatial_score": m.spatial_score,
                "centroid_score": m.centroid_score,
                "area_score": m.area_score,
                "geometry_score": m.geometry_score,
                "attribute_score": m.attribute_score,
                "explanation": m.explanation,
            })
        return results

    @classmethod
    async def get_source_feature_summary(
        cls,
        db: AsyncSession,
        run_id: uuid.UUID,
        feature_id: uuid.UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves aggregated summary for a source feature with candidates list,
        best candidate, second-best score, and score gap.
        """
        candidates = await cls.get_source_feature_candidates(db, run_id, feature_id)
        if not candidates:
            return None

        # Fetch first match to get source feature details
        stmt = (
            select(FeatureMatch)
            .where(
                FeatureMatch.match_run_id == run_id,
                FeatureMatch.source_feature_id == feature_id,
            )
            .options(
                joinedload(FeatureMatch.source_feature),
                joinedload(FeatureMatch.source_dataset),
            )
        )
        fm = (await db.execute(stmt)).scalars().first()
        if not fm or not fm.source_feature:
            return None

        source_feat = fm.source_feature
        valid_cands = [c for c in candidates if c["candidate_feature_id"] is not None]

        best_cand = valid_cands[0] if valid_cands else None
        second_cand = valid_cands[1] if len(valid_cands) >= 2 else None
        unambiguous_best = next((c for c in valid_cands if c.get("is_best_candidate")), None)

        return {
            "source_feature_id": feature_id,
            "source_identifier": extract_feature_display_id(source_feat) or str(feature_id),
            "source_dataset_id": fm.source_dataset_id,
            "source_dataset_name": fm.source_dataset.name if fm.source_dataset else "Source Dataset",
            "source_geometry_type": source_feat.geometry_type,
            "candidate_count": len(valid_cands),
            "best_candidate_id": unambiguous_best["candidate_feature_id"] if unambiguous_best else None,
            "best_candidate_identifier": unambiguous_best["candidate_identifier"] if unambiguous_best else None,
            "best_score": best_cand["overall_score"] if best_cand else 0.0,
            "second_best_score": second_cand["overall_score"] if second_cand else None,
            "score_gap": fm.score_gap,
            "status": best_cand["status"] if best_cand else fm.status,
            "candidate_role": best_cand["candidate_role"] if best_cand else fm.candidate_role,
            "candidates": candidates,
        }

    @classmethod
    async def record_match_review(
        cls,
        db: AsyncSession,
        match_id: uuid.UUID,
        decision: str,
        comment: Optional[str] = None,
        reviewer_id: Optional[uuid.UUID] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Records an auditable human review decision on a FeatureMatch.
        Preserves machine score, rank, role, and classification without modification.
        Updates review_status on FeatureMatch and appends to MatchReview audit trail.
        """
        stmt = (
            select(FeatureMatch)
            .where(FeatureMatch.id == match_id)
            .options(selectinload(FeatureMatch.reviews))
        )
        fm = (await db.execute(stmt)).scalar_one_or_none()
        if not fm:
            return None

        clean_decision = decision.strip().upper()
        if clean_decision not in {"ACCEPTED", "REJECTED", "FLAGGED"}:
            raise ValueError(f"Invalid decision: '{decision}'. Allowed: ACCEPTED, REJECTED, FLAGGED")

        review = MatchReview(
            id=uuid.uuid4(),
            feature_match_id=match_id,
            reviewer_id=reviewer_id,
            decision=clean_decision,
            comment=comment.strip() if comment else None,
        )
        db.add(review)

        # Update the match's review status
        fm.review_status = clean_decision

        await db.commit()
        await db.refresh(review)

        return {
            "id": review.id,
            "feature_match_id": review.feature_match_id,
            "decision": review.decision,
            "comment": review.comment,
            "reviewer_id": review.reviewer_id,
            "created_at": review.created_at,
            "updated_at": review.updated_at,
        }

    @classmethod
    async def get_review_queue(
        cls,
        db: AsyncSession,
        run_id: uuid.UUID,
        category: Optional[str] = None,
        decision: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Retrieves prioritized relationships for human reconciliation.
        Prioritizes items needing attention:
        1. AMBIGUOUS
        2. CONFLICT
        3. POSSIBLE_MATCH
        4. Others (highest score first)
        """
        # Category badge counters for the entire run
        counts_stmt = (
            select(
                func.count(FeatureMatch.id).label("total"),
                func.count(FeatureMatch.id).filter(FeatureMatch.review_status == "PENDING").label("pending"),
                func.count(FeatureMatch.id).filter(FeatureMatch.candidate_role == "AMBIGUOUS").label("ambiguous"),
                func.count(FeatureMatch.id).filter(
                    or_(FeatureMatch.status == "conflict", FeatureMatch.candidate_role == "CONFLICT")
                ).label("conflict"),
                func.count(FeatureMatch.id).filter(FeatureMatch.status == "possible_match").label("possible"),
                func.count(FeatureMatch.id).filter(
                    FeatureMatch.review_status.in_(["ACCEPTED", "REJECTED", "FLAGGED"])
                ).label("reviewed"),
                func.count(FeatureMatch.id).filter(FeatureMatch.review_status == "ACCEPTED").label("accepted"),
                func.count(FeatureMatch.id).filter(FeatureMatch.review_status == "REJECTED").label("rejected"),
                func.count(FeatureMatch.id).filter(FeatureMatch.review_status == "FLAGGED").label("flagged"),
            )
            .where(FeatureMatch.match_run_id == run_id)
        )
        counts_res = (await db.execute(counts_stmt)).one()

        category_counts = {
            "all": counts_res.total or 0,
            "pending": counts_res.pending or 0,
            "ambiguous": counts_res.ambiguous or 0,
            "conflict": counts_res.conflict or 0,
            "possible": counts_res.possible or 0,
            "reviewed": counts_res.reviewed or 0,
            "accepted": counts_res.accepted or 0,
            "rejected": counts_res.rejected or 0,
            "flagged": counts_res.flagged or 0,
        }

        # Build base filter
        filters = [FeatureMatch.match_run_id == run_id]

        if decision:
            filters.append(FeatureMatch.review_status == decision.strip().upper())
        elif category:
            cat = category.strip().lower()
            if cat == "pending":
                filters.append(FeatureMatch.review_status == "PENDING")
            elif cat == "ambiguous":
                filters.append(FeatureMatch.candidate_role == "AMBIGUOUS")
            elif cat == "conflict":
                filters.append(or_(FeatureMatch.status == "conflict", FeatureMatch.candidate_role == "CONFLICT"))
            elif cat == "possible":
                filters.append(FeatureMatch.status == "possible_match")
            elif cat == "reviewed":
                filters.append(FeatureMatch.review_status.in_(["ACCEPTED", "REJECTED", "FLAGGED"]))
            elif cat == "accepted":
                filters.append(FeatureMatch.review_status == "ACCEPTED")
            elif cat == "rejected":
                filters.append(FeatureMatch.review_status == "REJECTED")
            elif cat == "flagged":
                filters.append(FeatureMatch.review_status == "FLAGGED")

        # Priority rank SQL expression: 1: AMBIGUOUS, 2: CONFLICT, 3: POSSIBLE, 4: OTHER
        priority_rank = case(
            (FeatureMatch.candidate_role == "AMBIGUOUS", 1),
            (or_(FeatureMatch.status == "conflict", FeatureMatch.candidate_role == "CONFLICT"), 2),
            (FeatureMatch.status == "possible_match", 3),
            else_=4,
        )

        # Count total items matching current query
        count_query = select(func.count(FeatureMatch.id)).where(*filters)
        query_total = (await db.execute(count_query)).scalar() or 0

        # Query paginated items
        items_query = (
            select(FeatureMatch, priority_rank.label("computed_priority"))
            .where(*filters)
            .options(
                joinedload(FeatureMatch.source_feature),
                joinedload(FeatureMatch.candidate_feature),
                joinedload(FeatureMatch.source_dataset),
                joinedload(FeatureMatch.candidate_dataset),
                selectinload(FeatureMatch.reviews),
            )
            .order_by(
                priority_rank.asc(),
                desc(FeatureMatch.overall_score),
                FeatureMatch.id.asc(),
            )
            .offset(skip)
            .limit(limit)
        )
        rows = (await db.execute(items_query)).all()

        queue_items = []
        for fm, prio in rows:
            src_id_str = extract_feature_display_id(fm.source_feature) or "N/A"
            cand_id_str = extract_feature_display_id(fm.candidate_feature) if fm.candidate_feature else None
            reasons = (fm.explanation or {}).get("reasons", [])
            primary_reason = reasons[0] if (reasons and len(reasons) > 0) else None

            prio_cat = (
                "AMBIGUOUS" if fm.candidate_role == "AMBIGUOUS" else
                "CONFLICT" if (fm.status == "conflict" or fm.candidate_role == "CONFLICT") else
                "POSSIBLE" if fm.status == "possible_match" else "OTHER"
            )

            # Latest review details if any
            latest_rev = fm.reviews[0] if (fm.reviews and len(fm.reviews) > 0) else None

            queue_items.append({
                "id": fm.id,
                "match_run_id": fm.match_run_id,
                "project_id": fm.project_id,
                "source_feature_id": fm.source_feature_id,
                "candidate_feature_id": fm.candidate_feature_id,
                "source_identifier": src_id_str,
                "candidate_identifier": cand_id_str,
                "source_dataset_name": fm.source_dataset.name if fm.source_dataset else "Source Dataset",
                "candidate_dataset_name": fm.candidate_dataset.name if fm.candidate_dataset else None,
                "source_geometry_type": fm.source_feature.geometry_type if fm.source_feature else "Unknown",
                "candidate_geometry_type": fm.candidate_feature.geometry_type if fm.candidate_feature else None,
                "overall_score": fm.overall_score,
                "status": fm.status,
                "rank": fm.rank,
                "is_best_candidate": fm.is_best_candidate,
                "candidate_role": fm.candidate_role,
                "score_gap": fm.score_gap,
                "candidate_count": fm.candidate_count,
                "review_status": fm.review_status,
                "latest_comment": latest_rev.comment if latest_rev else None,
                "latest_decision_at": latest_rev.created_at if latest_rev else None,
                "reasons": reasons,
                "primary_reason": primary_reason,
                "priority_category": prio_cat,
                "priority_rank": prio,
                "created_at": fm.created_at,
            })

        return {
            "total": query_total,
            "pending_count": counts_res.pending or 0,
            "ambiguous_count": counts_res.ambiguous or 0,
            "conflict_count": counts_res.conflict or 0,
            "possible_count": counts_res.possible or 0,
            "reviewed_count": counts_res.reviewed or 0,
            "category_counts": category_counts,
            "items": queue_items,
        }

    @classmethod
    async def get_review_statistics(
        cls,
        db: AsyncSession,
        run_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Computes run-level human review counts directly from PostgreSQL.
        """
        stmt = (
            select(
                FeatureMatch.review_status,
                func.count(FeatureMatch.id).label("count"),
            )
            .where(FeatureMatch.match_run_id == run_id)
            .group_by(FeatureMatch.review_status)
        )
        rows = (await db.execute(stmt)).all()

        counts = {"PENDING": 0, "ACCEPTED": 0, "REJECTED": 0, "FLAGGED": 0}
        total = 0
        for status_val, count in rows:
            if status_val in counts:
                counts[status_val] = count
            total += count

        reviewed = counts["ACCEPTED"] + counts["REJECTED"] + counts["FLAGGED"]

        return {
            "run_id": run_id,
            "total_candidates": total,
            "pending_review": counts["PENDING"],
            "accepted": counts["ACCEPTED"],
            "rejected": counts["REJECTED"],
            "flagged": counts["FLAGGED"],
            "reviewed": reviewed,
        }

    @classmethod
    async def seed_demo_reviews(
        cls,
        db: AsyncSession,
        run_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Seeds deterministic demo reviews on a run for presentation purposes:
        - 1 match -> ACCEPTED (with rationale)
        - 1 conflict -> REJECTED (with rationale)
        - 1 ambiguous/possible -> FLAGGED (with rationale)
        Leaves remaining relationships PENDING.
        """
        # Find 1 top candidate to ACCEPT
        match_stmt = (
            select(FeatureMatch)
            .where(
                FeatureMatch.match_run_id == run_id,
                FeatureMatch.candidate_feature_id.isnot(None),
                FeatureMatch.status.in_(["matched", "possible_match"]),
            )
            .order_by(FeatureMatch.overall_score.desc())
            .limit(1)
        )
        best_match = (await db.execute(match_stmt)).scalar_one_or_none()
        if not best_match:
            # Any candidate with candidate_feature_id
            any_stmt = (
                select(FeatureMatch)
                .where(
                    FeatureMatch.match_run_id == run_id,
                    FeatureMatch.candidate_feature_id.isnot(None),
                )
                .order_by(FeatureMatch.overall_score.desc())
                .limit(1)
            )
            best_match = (await db.execute(any_stmt)).scalar_one_or_none()

        if best_match:
            await cls.record_match_review(
                db,
                best_match.id,
                decision="ACCEPTED",
                comment="Cadastral boundaries and structural area align with ground survey.",
            )

        # Find 1 conflict to REJECT (or lowest scoring alternative)
        conflict_stmt = (
            select(FeatureMatch)
            .where(
                FeatureMatch.match_run_id == run_id,
                FeatureMatch.candidate_feature_id.isnot(None),
                or_(FeatureMatch.status == "conflict", FeatureMatch.candidate_role == "CONFLICT"),
                FeatureMatch.id != best_match.id if best_match else True,
            )
            .limit(1)
        )
        conf_match = (await db.execute(conflict_stmt)).scalar_one_or_none()
        if not conf_match and best_match:
            # Fallback to lowest scoring candidate
            conf_fallback_stmt = (
                select(FeatureMatch)
                .where(
                    FeatureMatch.match_run_id == run_id,
                    FeatureMatch.candidate_feature_id.isnot(None),
                    FeatureMatch.id != best_match.id,
                )
                .order_by(FeatureMatch.overall_score.asc())
                .limit(1)
            )
            conf_match = (await db.execute(conf_fallback_stmt)).scalar_one_or_none()

        if conf_match:
            await cls.record_match_review(
                db,
                conf_match.id,
                decision="REJECTED",
                comment="Severe area discrepancy (>50%) indicates non-conforming secondary parcel.",
            )

        # Find 1 ambiguous/possible to FLAG
        excluded_ids = [m.id for m in [best_match, conf_match] if m]
        amb_stmt = (
            select(FeatureMatch)
            .where(
                FeatureMatch.match_run_id == run_id,
                FeatureMatch.candidate_feature_id.isnot(None),
                FeatureMatch.candidate_role == "AMBIGUOUS",
                ~FeatureMatch.id.in_(excluded_ids) if excluded_ids else True,
            )
            .limit(1)
        )
        amb_match = (await db.execute(amb_stmt)).scalar_one_or_none()
        if not amb_match:
            amb_fallback_stmt = (
                select(FeatureMatch)
                .where(
                    FeatureMatch.match_run_id == run_id,
                    FeatureMatch.candidate_feature_id.isnot(None),
                    ~FeatureMatch.id.in_(excluded_ids) if excluded_ids else True,
                )
                .limit(1)
            )
            amb_match = (await db.execute(amb_fallback_stmt)).scalar_one_or_none()

        if amb_match:
            await cls.record_match_review(
                db,
                amb_match.id,
                decision="FLAGGED",
                comment="Twin structures within score tolerance; flagged for field verification.",
            )

        return await cls.get_review_statistics(db, run_id)

