import uuid
from typing import Dict, Any, Optional, List
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Project
from app.models.dataset import Dataset, DatasetVersion
from app.models.feature import CanonicalFeature, SourceFeature
from app.models.matching import MatchRun, FeatureMatch, MatchReview
from app.models.unified import UnifiedLandRecord, UnifiedLandRecordSource
from app.models.conflict import AttributeConflict, ConflictResolution
from app.models.provenance import ProvenanceEvent
from app.schemas.assistant import AssistantEvidenceSource


async def get_project_summary(
    db: AsyncSession,
    project_id: uuid.UUID,
) -> Dict[str, Any]:
    """
    Retrieves comprehensive project overview including datasets,
    matching runs, unified records, and conflict counts.
    """
    proj = await db.get(Project, project_id)
    if not proj:
        return {"error": f"Project with ID '{project_id}' not found."}

    # Query datasets
    ds_result = await db.execute(
        select(Dataset).where(Dataset.project_id == project_id)
    )
    datasets = ds_result.scalars().all()

    # Query unified records stats
    rec_stats = await db.execute(
        select(
            UnifiedLandRecord.status,
            func.count(UnifiedLandRecord.id),
        )
        .where(UnifiedLandRecord.project_id == project_id)
        .group_by(UnifiedLandRecord.status)
    )
    status_counts = dict(rec_stats.all())

    # Query conflicts stats
    conf_stats = await db.execute(
        select(
            AttributeConflict.status,
            func.count(AttributeConflict.id),
        )
        .where(AttributeConflict.project_id == project_id)
        .group_by(AttributeConflict.status)
    )
    conflict_counts = dict(conf_stats.all())

    # Query runs count
    runs_count = (
        await db.execute(
            select(func.count(MatchRun.id)).where(MatchRun.project_id == project_id)
        )
    ).scalar() or 0

    return {
        "project_id": str(proj.id),
        "name": proj.name,
        "description": proj.description,
        "target_crs": proj.target_crs,
        "status": proj.status,
        "total_datasets": len(datasets),
        "datasets": [
            {
                "id": str(d.id),
                "name": d.name,
                "format": d.source_format,
                "feature_count": d.feature_count,
                "geometry_type": d.geometry_type,
                "detected_crs": d.detected_crs,
            }
            for d in datasets
        ],
        "matching_runs_count": runs_count,
        "unified_records": {
            "total": sum(status_counts.values()),
            "active": status_counts.get("ACTIVE", 0),
            "conflict": status_counts.get("CONFLICT", 0),
            "incomplete": status_counts.get("INCOMPLETE", 0),
        },
        "conflicts": {
            "total": sum(conflict_counts.values()),
            "unresolved": conflict_counts.get("UNRESOLVED", 0),
            "resolved": conflict_counts.get("RESOLVED", 0),
            "dismissed": conflict_counts.get("DISMISSED", 0),
        },
    }


async def get_unified_record_evidence(
    db: AsyncSession,
    project_id: uuid.UUID,
    record_identifier_or_id: str,
) -> Dict[str, Any]:
    """
    Retrieves full evidence for a specific unified land record:
    canonical attributes, area, contributing sources, and active conflicts.
    """
    query = (
        select(UnifiedLandRecord)
        .options(
            selectinload(UnifiedLandRecord.sources).selectinload(UnifiedLandRecordSource.feature),
            selectinload(UnifiedLandRecord.sources).selectinload(UnifiedLandRecordSource.feature_match),
        )
        .where(UnifiedLandRecord.project_id == project_id)
    )

    try:
        val_uuid = uuid.UUID(record_identifier_or_id)
        query = query.where(or_(UnifiedLandRecord.id == val_uuid, UnifiedLandRecord.record_identifier == record_identifier_or_id))
    except ValueError:
        query = query.where(UnifiedLandRecord.record_identifier.ilike(record_identifier_or_id.strip()))

    result = await db.execute(query)
    record = result.scalars().first()

    if not record:
        return {"error": f"Unified record '{record_identifier_or_id}' not found in project."}

    # Query conflicts for this record
    conf_result = await db.execute(
        select(AttributeConflict)
        .options(selectinload(AttributeConflict.resolution))
        .where(AttributeConflict.unified_land_record_id == record.id)
    )
    conflicts = conf_result.scalars().all()

    # Query contributing source features details
    sources_info = []
    for s in record.sources:
        feat = s.feature
        props = feat.canonical_properties if feat else {}
        sources_info.append({
            "source_id": str(s.id),
            "feature_id": str(s.feature_id),
            "source_role": s.source_role,
            "feature_identifier": props.get("parcel_id") or props.get("structure_id") or props.get("id") or str(s.feature_id)[:8],
            "geometry_type": feat.geometry_type if feat else "Unknown",
            "properties": {k: v for k, v in props.items() if not k.startswith("_")},
        })

    conflicts_info = []
    for c in conflicts:
        conflicts_info.append({
            "id": str(c.id),
            "attribute_name": c.attribute_name,
            "conflict_type": c.conflict_type,
            "severity": c.severity,
            "status": c.status,
            "detected_values": c.detected_values,
            "resolution": {
                "resolution_type": c.resolution.resolution_type,
                "resolved_value": c.resolution.resolved_value,
                "comment": c.resolution.comment,
                "resolved_by": c.resolution.resolved_by,
                "resolved_at": c.resolution.resolved_at.isoformat() if c.resolution.resolved_at else None,
            } if c.resolution else None,
            "dismissal_reason": c.resolution.comment if (c.resolution and c.resolution.resolution_type == "DISMISSED") else None,
        })

    return {
        "record_id": str(record.id),
        "record_identifier": record.record_identifier,
        "status": record.status,
        "geometry_source_role": record.geometry_source_role,
        "canonical_area": record.area,
        "canonical_attributes": record.canonical_attributes,
        "contributing_sources_count": len(sources_info),
        "contributing_sources": sources_info,
        "conflicts_count": len(conflicts_info),
        "conflicts": conflicts_info,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


async def get_conflict_evidence(
    db: AsyncSession,
    project_id: uuid.UUID,
    attribute_or_conflict_id: str,
    record_id: Optional[uuid.UUID] = None,
) -> Dict[str, Any]:
    """
    Retrieves evidence and detected values for a specific attribute conflict.
    """
    query = (
        select(AttributeConflict)
        .options(
            selectinload(AttributeConflict.resolution),
            selectinload(AttributeConflict.unified_record),
        )
        .where(AttributeConflict.project_id == project_id)
    )

    try:
        conf_uuid = uuid.UUID(attribute_or_conflict_id)
        query = query.where(AttributeConflict.id == conf_uuid)
    except ValueError:
        query = query.where(AttributeConflict.attribute_name.ilike(attribute_or_conflict_id.strip()))
        if record_id:
            query = query.where(AttributeConflict.unified_land_record_id == record_id)

    result = await db.execute(query)
    conflicts = result.scalars().all()

    if not conflicts:
        return {"error": f"No conflict matching '{attribute_or_conflict_id}' found."}

    items = []
    for c in conflicts:
        rec = c.unified_record
        items.append({
            "conflict_id": str(c.id),
            "record_id": str(c.unified_land_record_id),
            "record_identifier": rec.record_identifier if rec else None,
            "attribute_name": c.attribute_name,
            "conflict_type": c.conflict_type,
            "severity": c.severity,
            "status": c.status,
            "detected_values": c.detected_values,
            "resolution": {
                "type": c.resolution.resolution_type,
                "resolved_value": c.resolution.resolved_value,
                "comment": c.resolution.comment,
                "resolved_by": c.resolution.resolved_by,
                "resolved_at": c.resolution.resolved_at.isoformat() if c.resolution.resolved_at else None,
            } if c.resolution else None,
            "dismissal_reason": c.resolution.comment if (c.resolution and c.resolution.resolution_type == "DISMISSED") else None,
        })

    return {"conflicts": items}


async def get_provenance_trail(
    db: AsyncSession,
    project_id: uuid.UUID,
    record_id_or_identifier: str,
) -> Dict[str, Any]:
    """
    Retrieves the complete chronological audit timeline and review history
    associated with a unified land record.
    """
    # First find the record
    rec_data = await get_unified_record_evidence(db, project_id, record_id_or_identifier)
    if "error" in rec_data:
        return rec_data

    record_uuid = uuid.UUID(rec_data["record_id"])

    # Query provenance events
    events_res = await db.execute(
        select(ProvenanceEvent)
        .where(
            ProvenanceEvent.project_id == project_id,
            or_(
                ProvenanceEvent.unified_land_record_id == record_uuid,
                ProvenanceEvent.source_id == record_uuid,
            ),
        )
        .order_by(ProvenanceEvent.created_at.asc())
    )
    events = events_res.scalars().all()

    timeline = [
        {
            "event_type": e.event_type,
            "title": e.event_metadata.get("title", e.event_type.replace("_", " ").title()),
            "description": e.event_metadata.get("description", ""),
            "metadata": e.event_metadata,
            "timestamp": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]

    return {
        "record_identifier": rec_data["record_identifier"],
        "record_id": rec_data["record_id"],
        "status": rec_data["status"],
        "events_count": len(timeline),
        "timeline": timeline,
    }
