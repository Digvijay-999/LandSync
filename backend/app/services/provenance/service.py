import uuid
from typing import Optional, List, Dict, Any, Set
from collections import defaultdict
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.project import Project
from app.models.dataset import Dataset, DatasetVersion
from app.models.feature import CanonicalFeature, SourceFeature
from app.models.matching import MatchRun, FeatureMatch, MatchReview
from app.models.unified import UnifiedLandRecord, UnifiedLandRecordSource
from app.models.provenance import ProvenanceEvent
from app.schemas.provenance import (
    ProvenanceSourceItem,
    ProvenanceRelationshipItem,
    ProvenanceReviewHistoryItem,
    ProvenanceTimelineItem,
    UnifiedRecordProvenanceResponse,
    ProjectProvenanceSummaryResponse,
)


def extract_feature_display_id(cf: Optional[CanonicalFeature]) -> Optional[str]:
    """Helper to extract a friendly identifier from canonical or source feature properties."""
    if not cf:
        return None
    props = cf.canonical_properties or {}
    for key in [
        "parcel_id",
        "asset_id",
        "structure_id",
        "building_id",
        "facility_id",
        "fid",
        "property_id",
        "pin",
        "lot",
        "id",
        "code",
        "name",
    ]:
        if key in props and props[key]:
            return str(props[key]).strip()
    if hasattr(cf, "source_feature") and cf.source_feature and cf.source_feature.source_feature_id:
        return str(cf.source_feature.source_feature_id).strip()
    return str(cf.source_feature_id or cf.id)[:8]


class ProvenanceService:
    """
    Service responsible for constructing deterministic, evidence-grounded provenance
    chains and audit timelines for unified land records.
    Never fabricates data: every entry directly references authoritative database records.
    """

    @classmethod
    async def get_record_provenance(
        cls,
        db: AsyncSession,
        record_id: uuid.UUID,
    ) -> Optional[UnifiedRecordProvenanceResponse]:
        """
        Resolves the comprehensive provenance chain for an individual UnifiedLandRecord:
        - Source features & originating datasets/versions
        - Match relationships & machine-calculated scores
        - Candidate ranking, quality tier, and signals
        - Human review decisions & audit history
        - Chronological lifecycle timeline
        """
        # 1. Fetch UnifiedLandRecord with sources and features
        stmt = (
            select(UnifiedLandRecord)
            .where(UnifiedLandRecord.id == record_id)
            .options(
                selectinload(UnifiedLandRecord.sources)
                .joinedload(UnifiedLandRecordSource.feature)
                .joinedload(CanonicalFeature.dataset_version)
                .joinedload(DatasetVersion.dataset),
                selectinload(UnifiedLandRecord.sources)
                .joinedload(UnifiedLandRecordSource.feature)
                .joinedload(CanonicalFeature.source_feature),
                joinedload(UnifiedLandRecord.geometry_source_feature)
                .joinedload(CanonicalFeature.dataset_version)
                .joinedload(DatasetVersion.dataset),
            )
        )
        record = (await db.execute(stmt)).scalar_one_or_none()
        if not record:
            return None

        # 2. Build Sources List
        sources_list: List[ProvenanceSourceItem] = []
        feature_ids: List[uuid.UUID] = []
        feature_map: Dict[uuid.UUID, CanonicalFeature] = {}
        dataset_versions_seen: Dict[uuid.UUID, DatasetVersion] = {}

        for src in record.sources:
            cf = src.feature
            if not cf:
                continue

            feature_ids.append(cf.id)
            feature_map[cf.id] = cf

            dv = cf.dataset_version
            ds = dv.dataset if dv else None
            if dv and dv.id not in dataset_versions_seen:
                dataset_versions_seen[dv.id] = dv

            display_id = extract_feature_display_id(cf) or str(cf.id)[:8]

            sources_list.append(
                ProvenanceSourceItem(
                    role=src.source_role,
                    dataset_id=ds.id if ds else None,
                    dataset_name=ds.name if ds else "Unknown Dataset",
                    dataset_version=dv.version_number if dv else None,
                    dataset_format=ds.source_format if ds else None,
                    feature_id=cf.id,
                    feature_identifier=display_id,
                    source_feature_id=cf.source_feature_id,
                    properties=cf.canonical_properties or {},
                    geometry_type=cf.geometry_type or "Unknown",
                )
            )

        # 3. Resolve Match Relationships
        # Collect matches referenced directly by sources or connecting source feature IDs
        direct_match_ids = [s.feature_match_id for s in record.sources if s.feature_match_id]

        match_filters = []
        if direct_match_ids:
            match_filters.append(FeatureMatch.id.in_(direct_match_ids))
        if len(feature_ids) >= 2:
            match_filters.append(
                and_(
                    FeatureMatch.source_feature_id.in_(feature_ids),
                    FeatureMatch.candidate_feature_id.in_(feature_ids),
                )
            )

        matches: List[FeatureMatch] = []
        if match_filters:
            match_stmt = (
                select(FeatureMatch)
                .where(
                    and_(
                        FeatureMatch.review_status == "ACCEPTED",
                        or_(*match_filters),
                    )
                )
                .options(selectinload(FeatureMatch.reviews))
                .order_by(FeatureMatch.created_at.asc())
            )
            matches = list((await db.execute(match_stmt)).scalars().all())

        relationships_list: List[ProvenanceRelationshipItem] = []
        reviews_list: List[ProvenanceReviewHistoryItem] = []
        seen_matches: Set[uuid.UUID] = set()

        for m in matches:
            if m.id in seen_matches:
                continue
            seen_matches.add(m.id)

            tier = (
                "HIGH_CONFIDENCE"
                if m.overall_score >= 0.8
                else "MEDIUM_CONFIDENCE"
                if m.overall_score >= 0.6
                else "LOW_CONFIDENCE"
            )
            is_ambig = m.candidate_role == "AMBIGUOUS_CANDIDATE" or (
                m.candidate_count > 1 and (m.score_gap is not None and m.score_gap < 0.15)
            )

            relationships_list.append(
                ProvenanceRelationshipItem(
                    match_id=m.id,
                    source_feature_id=m.source_feature_id,
                    candidate_feature_id=m.candidate_feature_id,
                    target_feature_id=m.candidate_feature_id,
                    machine_score=float(m.overall_score),
                    classification=m.status,
                    match_tier=tier,
                    candidate_rank=m.rank,
                    candidate_role=m.candidate_role,
                    is_best_candidate=m.is_best_candidate,
                    is_ambiguous=is_ambig,
                    human_decision=m.review_status,
                    reasons=m.explanation or {},
                )
            )

            # Collect human review decisions
            for rev in sorted(m.reviews, key=lambda r: r.created_at):
                reviews_list.append(
                    ProvenanceReviewHistoryItem(
                        id=rev.id,
                        match_id=rev.feature_match_id,
                        decision=rev.decision,
                        comment=rev.comment,
                        reviewer_id=rev.reviewer_id,
                        created_at=rev.created_at,
                    )
                )

        # 4. Fetch any audit / export events for this record
        event_stmt = (
            select(ProvenanceEvent)
            .where(
                or_(
                    ProvenanceEvent.unified_land_record_id == record.id,
                    and_(
                        ProvenanceEvent.source_type == "RECORD_EXPORT",
                        ProvenanceEvent.source_id == record.id,
                    ),
                )
            )
            .order_by(ProvenanceEvent.created_at.asc())
        )
        provenance_events = list((await db.execute(event_stmt)).scalars().all())

        # 5. Build Chronological Lifecycle Timeline from real database evidence
        timeline: List[ProvenanceTimelineItem] = []

        # (a) Datasets Ingested
        for dv in dataset_versions_seen.values():
            ds_name = dv.dataset.name if dv.dataset else "Dataset"
            ds_fmt = dv.dataset.source_format if dv.dataset else "Geospatial"
            timeline.append(
                ProvenanceTimelineItem(
                    event_type="DATA_INGESTED",
                    title=f"Dataset Ingested: {ds_name} (v{dv.version_number})",
                    description=f"Raw {ds_fmt} dataset '{ds_name}' version {dv.version_number} ingested.",
                    timestamp=dv.created_at,
                    entity_type="DATASET",
                    entity_id=str(dv.dataset_id),
                    metadata={"version": dv.version_number, "format": ds_fmt},
                )
            )

        # (b) Features Canonicalized
        for cf in feature_map.values():
            disp_id = extract_feature_display_id(cf) or str(cf.id)[:8]
            timeline.append(
                ProvenanceTimelineItem(
                    event_type="FEATURE_CANONICALIZED",
                    title=f"Feature Normalized: {disp_id}",
                    description=f"Source feature {disp_id} canonicalized to EPSG:4326.",
                    timestamp=cf.created_at,
                    entity_type="FEATURE",
                    entity_id=str(cf.id),
                    metadata={"geometry_type": cf.geometry_type, "crs": cf.target_crs},
                )
            )

        # (c) Matches Generated
        for m in matches:
            tier = (
                "HIGH_CONFIDENCE"
                if m.overall_score >= 0.8
                else "MEDIUM_CONFIDENCE"
                if m.overall_score >= 0.6
                else "LOW_CONFIDENCE"
            )
            timeline.append(
                ProvenanceTimelineItem(
                    event_type="MATCH_GENERATED",
                    title=f"Candidate Match: {m.overall_score:.0%} Match",
                    description=(
                        f"Machine matching algorithm generated match with score "
                        f"{m.overall_score:.2f} ({m.status}, rank #{m.rank or 1})."
                    ),
                    timestamp=m.created_at,
                    entity_type="MATCH",
                    entity_id=str(m.id),
                    metadata={
                        "score": m.overall_score,
                        "status": m.status,
                        "rank": m.rank,
                        "tier": tier,
                    },
                )
            )

        # (d) Human Reviews
        for rev in reviews_list:
            timeline.append(
                ProvenanceTimelineItem(
                    event_type="MATCH_REVIEWED",
                    title=f"Human Review: {rev.decision}",
                    description=(
                        f"Human reviewer confirmed decision: {rev.decision}"
                        + (f' ("{rev.comment}")' if rev.comment else "")
                    ),
                    timestamp=rev.created_at,
                    entity_type="REVIEW",
                    entity_id=str(rev.id),
                    metadata={"decision": rev.decision, "comment": rev.comment},
                )
            )

        # (e) Record Creation
        timeline.append(
            ProvenanceTimelineItem(
                event_type="RECORD_SYNTHESIZED",
                title=f"Unified Record Created: {record.record_identifier}",
                description=(
                    f"Synthesized canonical record from {len(record.sources)} accepted source features "
                    f"with status {record.status}."
                ),
                timestamp=record.created_at,
                entity_type="RECORD",
                entity_id=str(record.id),
                metadata={
                    "identifier": record.record_identifier,
                    "status": record.status,
                    "sources_count": len(record.sources),
                },
            )
        )

        # (f) First-Class Attribute Conflict Lifecycle Events
        from app.models.conflict import AttributeConflict
        conflict_stmt = (
            select(AttributeConflict)
            .where(AttributeConflict.unified_land_record_id == record.id)
            .options(joinedload(AttributeConflict.resolution))
            .order_by(AttributeConflict.created_at.asc())
        )
        db_conflicts = list((await db.execute(conflict_stmt)).scalars().all())

        for c in db_conflicts:
            timeline.append(
                ProvenanceTimelineItem(
                    event_type="CONFLICT_DETECTED",
                    title=f"Conflict Detected: {c.attribute_name}",
                    description=(
                        f"Attribute conflict in '{c.attribute_name}' ({c.conflict_type}, severity: {c.severity}) "
                        f"detected across {len(c.detected_values or [])} sources."
                    ),
                    timestamp=c.created_at,
                    entity_type="CONFLICT",
                    entity_id=str(c.id),
                    metadata={
                        "attribute": c.attribute_name,
                        "conflict_type": c.conflict_type,
                        "severity": c.severity,
                        "status": c.status,
                    },
                )
            )

        # (g) Audit & Provenance Events
        for pe in provenance_events:
            if pe.event_type in ["RECORD_EXPORT", "EXPORT_GENERATED"]:
                fmt = pe.event_metadata.get("export_format", "FILE").upper()
                timeline.append(
                    ProvenanceTimelineItem(
                        event_type="EXPORT_GENERATED",
                        title=f"Export Created: {fmt}",
                        description=f"Unified record exported in {fmt} format.",
                        timestamp=pe.created_at,
                        entity_type="EXPORT",
                        entity_id=str(pe.id),
                        metadata=pe.event_metadata,
                    )
                )
            elif pe.event_type == "CONFLICT_RESOLVED":
                attr = pe.event_metadata.get("attribute_name", "attribute")
                val = pe.event_metadata.get("resolved_value", "")
                rtype = pe.event_metadata.get("resolution_type", "SOURCE_SELECTION")
                note = pe.event_metadata.get("comment", "")
                timeline.append(
                    ProvenanceTimelineItem(
                        event_type="CONFLICT_RESOLVED",
                        title=f"Conflict Resolved: {attr}",
                        description=(
                            f"Human reviewer resolved '{attr}' to '{val}' via {rtype}"
                            + (f' ("{note}")' if note else "")
                        ),
                        timestamp=pe.created_at,
                        entity_type="CONFLICT",
                        entity_id=str(pe.source_id),
                        metadata=pe.event_metadata,
                    )
                )
            elif pe.event_type == "CONFLICT_DISMISSED":
                attr = pe.event_metadata.get("attribute_name", "attribute")
                reason = pe.event_metadata.get("reason", "")
                timeline.append(
                    ProvenanceTimelineItem(
                        event_type="CONFLICT_DISMISSED",
                        title=f"Conflict Dismissed: {attr}",
                        description=(
                            f"Human reviewer dismissed conflict on '{attr}'"
                            + (f' ("{reason}")' if reason else "")
                        ),
                        timestamp=pe.created_at,
                        entity_type="CONFLICT",
                        entity_id=str(pe.source_id),
                        metadata=pe.event_metadata,
                    )
                )

        # Sort timeline chronologically
        timeline.sort(key=lambda t: t.timestamp)

        # 6. Canonical Geometry Source Details
        geom_feat = record.geometry_source_feature
        geom_source_info = {
            "role": record.geometry_source_role or "UNKNOWN",
            "feature_id": str(record.geometry_source_feature_id) if record.geometry_source_feature_id else None,
            "feature_identifier": extract_feature_display_id(geom_feat) if geom_feat else None,
            "dataset_name": (
                geom_feat.dataset_version.dataset.name
                if geom_feat and geom_feat.dataset_version and geom_feat.dataset_version.dataset
                else None
            ),
        }

        # Build comprehensive conflict summary list
        conflicts_output: List[Dict[str, Any]] = []
        for c in db_conflicts:
            vals_by_role = {}
            for dv in (c.detected_values or []):
                vals_by_role[dv.get("source_role", "UNKNOWN")] = dv.get("value")

            res_info = None
            if c.resolution:
                res_info = {
                    "resolution_type": c.resolution.resolution_type,
                    "resolved_value": c.resolution.resolved_value,
                    "selected_source_role": c.resolution.selected_source_role,
                    "comment": c.resolution.comment,
                    "resolved_by": c.resolution.resolved_by,
                    "resolved_at": c.resolution.resolved_at.isoformat() if c.resolution.resolved_at else None,
                }

            conflicts_output.append({
                "id": str(c.id),
                "field": c.attribute_name,
                "type": c.conflict_type,
                "severity": c.severity,
                "status": c.status,
                "values": vals_by_role,
                "resolution": res_info,
                "dismissal_reason": (
                    c.resolution.comment
                    if c.resolution and c.resolution.resolution_type == "DISMISSED"
                    else getattr(c, "dismissal_reason", None)
                ),
            })

        if not conflicts_output and isinstance(record.canonical_attributes, dict):
            conflicts_output = record.canonical_attributes.get("conflicts", [])

        return UnifiedRecordProvenanceResponse(
            record_id=record.record_identifier,
            record_uuid=record.id,
            project_id=record.project_id,
            status=record.status,
            canonical_geometry_source=geom_source_info,
            area_sqm=record.area,
            sources=sources_list,
            relationships=relationships_list,
            review_history=reviews_list,
            timeline=timeline,
            conflicts=conflicts_output,
        )

    @classmethod
    async def get_project_provenance_summary(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> ProjectProvenanceSummaryResponse:
        """
        Calculates aggregate project-level provenance and audit summary.
        """
        # Validate project exists
        project = await db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project with ID '{project_id}' not found.")

        # 1. Total unified records
        total_records_stmt = (
            select(func.count(UnifiedLandRecord.id))
            .where(UnifiedLandRecord.project_id == project_id)
        )
        total_records = (await db.execute(total_records_stmt)).scalar() or 0

        # 2. Total sources
        total_sources_stmt = (
            select(func.count(UnifiedLandRecordSource.id))
            .join(UnifiedLandRecord, UnifiedLandRecord.id == UnifiedLandRecordSource.unified_land_record_id)
            .where(UnifiedLandRecord.project_id == project_id)
        )
        total_sources = (await db.execute(total_sources_stmt)).scalar() or 0

        # 3. Total accepted matches
        total_matches_stmt = (
            select(func.count(FeatureMatch.id))
            .join(MatchRun, MatchRun.id == FeatureMatch.match_run_id)
            .where(
                and_(
                    MatchRun.project_id == project_id,
                    FeatureMatch.review_status == "ACCEPTED",
                )
            )
        )
        total_accepted_matches = (await db.execute(total_matches_stmt)).scalar() or 0

        # 4. Total reviews
        total_reviews_stmt = (
            select(func.count(MatchReview.id))
            .join(FeatureMatch, FeatureMatch.id == MatchReview.feature_match_id)
            .join(MatchRun, MatchRun.id == FeatureMatch.match_run_id)
            .where(MatchRun.project_id == project_id)
        )
        total_reviews = (await db.execute(total_reviews_stmt)).scalar() or 0

        # 5. Datasets involved
        datasets_stmt = (
            select(Dataset)
            .where(Dataset.project_id == project_id)
            .options(selectinload(Dataset.versions))
            .order_by(Dataset.name.asc())
        )
        datasets = list((await db.execute(datasets_stmt)).scalars().all())

        dataset_items = [
            {
                "id": str(d.id),
                "name": d.name,
                "format": d.source_format,
                "feature_count": d.feature_count,
                "versions_count": len(d.versions),
            }
            for d in datasets
        ]

        # 6. Latest audit events
        events_stmt = (
            select(ProvenanceEvent)
            .where(ProvenanceEvent.project_id == project_id)
            .order_by(ProvenanceEvent.created_at.desc())
            .limit(10)
        )
        events = list((await db.execute(events_stmt)).scalars().all())

        latest_events = [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "source_type": e.source_type,
                "metadata": e.event_metadata,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ]

        return ProjectProvenanceSummaryResponse(
            project_id=project.id,
            project_name=project.name,
            total_unified_records=total_records,
            total_sources=total_sources,
            total_accepted_matches=total_accepted_matches,
            total_reviews=total_reviews,
            datasets=dataset_items,
            latest_events=latest_events,
        )
