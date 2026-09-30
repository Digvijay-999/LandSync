import uuid
from typing import Dict, Any, Optional, List
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.unified import UnifiedLandRecord
from app.models.feature import CanonicalFeature
from app.models.conflict import AttributeConflict
from app.models.dataset import Dataset, DatasetVersion


async def search_unified_records_by_attributes(
    db: AsyncSession,
    project_id: uuid.UUID,
    query_text: str,
    limit: int = 15,
) -> Dict[str, Any]:
    """
    Searches unified land records by text matching against record_identifier,
    land_use, address, zoning, owner, or other canonical properties.
    """
    records_res = await db.execute(
        select(UnifiedLandRecord).where(UnifiedLandRecord.project_id == project_id)
    )
    records = records_res.scalars().all()

    q_lower = query_text.lower().strip()
    matching_records = []

    for r in records:
        matched = False
        match_field = None

        if q_lower in r.record_identifier.lower():
            matched = True
            match_field = "record_identifier"
        elif q_lower in r.status.lower():
            matched = True
            match_field = "status"
        else:
            attrs = r.canonical_attributes or {}
            for k, v in attrs.items():
                if v and q_lower in str(v).lower():
                    matched = True
                    match_field = k
                    break

        if matched:
            matching_records.append({
                "record_id": str(r.id),
                "record_identifier": r.record_identifier,
                "status": r.status,
                "matched_field": match_field,
                "canonical_area": r.area,
                "land_use": r.canonical_attributes.get("land_use"),
                "address": r.canonical_attributes.get("address"),
            })

    return {
        "search_term": query_text,
        "results_count": len(matching_records[:limit]),
        "records": matching_records[:limit],
    }


async def search_source_features(
    db: AsyncSession,
    project_id: uuid.UUID,
    query_text: str,
    limit: int = 15,
) -> Dict[str, Any]:
    """
    Searches underlying source/canonical features across datasets in a project.
    """
    features_res = await db.execute(
        select(CanonicalFeature)
        .join(DatasetVersion, CanonicalFeature.dataset_version_id == DatasetVersion.id)
        .join(Dataset, DatasetVersion.dataset_id == Dataset.id)
        .where(Dataset.project_id == project_id)
        .options(selectinload(CanonicalFeature.dataset_version).selectinload(DatasetVersion.dataset))
    )
    features = features_res.scalars().all()

    q_lower = query_text.lower().strip()
    matching_features = []

    for f in features:
        props = f.canonical_properties or {}
        matched = False
        matched_attr = None

        for k, v in props.items():
            if not k.startswith("_") and v and q_lower in str(v).lower():
                matched = True
                matched_attr = k
                break

        if matched:
            ds = f.dataset_version.dataset if f.dataset_version else None
            matching_features.append({
                "feature_id": str(f.id),
                "dataset_name": ds.name if ds else "Unknown",
                "geometry_type": f.geometry_type,
                "matched_property": matched_attr,
                "matched_value": props.get(matched_attr),
                "properties": {k: v for k, v in props.items() if not k.startswith("_")},
            })

    return {
        "search_term": query_text,
        "results_count": len(matching_features[:limit]),
        "features": matching_features[:limit],
    }
