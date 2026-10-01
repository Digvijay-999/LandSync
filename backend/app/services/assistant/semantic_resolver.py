import re
import uuid
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import Dataset, DatasetVersion
from app.models.feature import CanonicalFeature
from app.core.logging import logger


class DatasetSemanticMatch(BaseModel):
    dataset_id: uuid.UUID
    dataset_name: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str
    geometry_type: Optional[str] = None
    feature_count: int = 0


class SpatialIntentPlan(BaseModel):
    intent: str = "spatial_analysis"
    analysis_type: str = "proximity"  # proximity, intersection, buffer, comparison, conflicts, nearest
    target_dataset_id: Optional[uuid.UUID] = None
    target_dataset_name: Optional[str] = None
    reference_dataset_id: Optional[uuid.UUID] = None
    reference_dataset_name: Optional[str] = None
    reference_feature_id: Optional[str] = None
    distance: float = 100.0
    unit: str = "meters"
    confidence: float = 1.0
    is_ambiguous: bool = False
    ambiguity_reason: Optional[str] = None
    clarification_prompt: Optional[str] = None


class DatasetSemanticResolver:
    """
    Semantic resolution layer mapping natural-language query tokens to
    concrete, validated project datasets using schema metadata, geometry types,
    and profile attributes.
    """

    KEYWORD_MAPPINGS: Dict[str, Dict[str, Any]] = {
        "cadastral": {"terms": ["cadastral", "cadastre", "parcel", "parcels", "lot", "boundary", "land"], "geom": ["Polygon", "MultiPolygon"]},
        "drone": {"terms": ["drone", "ortho", "uav", "structure", "structures", "building", "footprint"], "geom": ["Polygon", "MultiPolygon"]},
        "infrastructure": {"terms": ["asset", "assets", "municipal", "infrastructure", "utility", "hydrant", "pole", "facility", "point"], "geom": ["Point", "MultiPoint"]},
        "zoning": {"terms": ["zone", "zoning", "district", "admin", "boundary", "sector"], "geom": ["Polygon", "MultiPolygon"]},
    }

    @classmethod
    async def resolve_dataset_for_term(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        term: str,
    ) -> Optional[DatasetSemanticMatch]:
        """
        Resolves a single term or phrase (e.g. 'parcels', 'municipal assets') to the best-matching dataset.
        """
        stmt = select(Dataset).where(Dataset.project_id == project_id)
        res = await db.execute(stmt)
        datasets = res.scalars().all()
        if not datasets:
            return None

        clean_term = term.lower().strip()
        best_match: Optional[DatasetSemanticMatch] = None
        best_score = 0.0

        for ds in datasets:
            score = 0.0
            reasons = []
            ds_name_lower = ds.name.lower()
            ds_geom = ds.geometry_type or "Unknown"

            # 1. Exact or substring name match
            if clean_term in ds_name_lower:
                score += 0.55
                reasons.append(f"Name '{ds.name}' contains term '{clean_term}'")
            elif any(token in ds_name_lower for token in clean_term.split()):
                score += 0.35
                reasons.append(f"Name '{ds.name}' matches keyword in '{clean_term}'")

            # 2. Semantic category keyword match
            for cat, info in cls.KEYWORD_MAPPINGS.items():
                if any(t in clean_term for t in info["terms"]):
                    # If dataset name also matches category
                    if any(t in ds_name_lower for t in info["terms"]):
                        score += 0.30
                        reasons.append(f"Semantic match to '{cat}' category")
                    # If geometry matches expected category geometry
                    if ds_geom in info["geom"]:
                        score += 0.15
                        reasons.append(f"Geometry type '{ds_geom}' matches '{cat}' domain expectation")

            # 3. Attribute profile inspection
            profile = ds.profile_metadata or {}
            attrs = [a.lower() for a in profile.get("attributes", {}).get("names", [])]
            if "parcel" in clean_term and any("parcel" in a or "pin" in a for a in attrs):
                score += 0.20
                reasons.append("Attribute columns include parcel identifier fields")
            if "asset" in clean_term and any("asset" in a or "facility" in a for a in attrs):
                score += 0.20
                reasons.append("Attribute columns include asset identifier fields")

            score = min(1.0, score)
            if score > best_score:
                best_score = score
                best_match = DatasetSemanticMatch(
                    dataset_id=ds.id,
                    dataset_name=ds.name,
                    confidence=round(best_score, 2),
                    reason="; ".join(reasons) if reasons else "Default project dataset selection",
                    geometry_type=ds_geom,
                    feature_count=ds.feature_count or 0,
                )

        if best_match and best_match.confidence >= 0.35:
            return best_match
        return None

    @classmethod
    async def resolve_spatial_query_plan(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        query: str,
    ) -> SpatialIntentPlan:
        """
        Parses a natural-language query and deterministically resolves target and reference datasets.
        Separates target dataset (features to return) from reference dataset (geometries to measure against).
        """
        q_lower = query.lower()

        # Parse distance & units
        dist = 100.0
        unit = "meters"
        dist_match = re.search(r"(\d+(?:\.\d+)?)\s*(meters?|m|km|kilometers?|ft|feet)\b", q_lower)
        if dist_match:
            dist = float(dist_match.group(1))
            raw_unit = dist_match.group(2)
            if raw_unit in ("km", "kilometers", "kilometer"):
                dist *= 1000.0
                unit = "meters"
            elif raw_unit in ("ft", "feet"):
                dist *= 0.3048
                unit = "meters"
            else:
                unit = "meters"
        else:
            # Fallback numeric search
            num_match = re.search(r"\b(\d{2,4})\b", q_lower)
            if num_match:
                dist = float(num_match.group(1))

        # Detect analysis type
        analysis_type = "proximity"
        if any(w in q_lower for w in ["overlap", "intersect", "intersection", "intersections"]):
            analysis_type = "intersection"
        elif any(w in q_lower for w in ["compare", "comparison", "difference"]):
            analysis_type = "comparison"
        elif any(w in q_lower for w in ["conflict", "conflicts", "concentrated", "hotspot"]):
            analysis_type = "conflicts"
        elif any(w in q_lower for w in ["nearest", "closest"]):
            analysis_type = "nearest"
        elif any(w in q_lower for w in ["buffer", "zone", "corridor"]):
            analysis_type = "buffer"

        # Extract target vs reference candidate phrases
        target_phrase = None
        reference_phrase = None

        # Pattern: "find <target> within <dist> of <reference>"
        within_match = re.search(r"(?:find|get|show|which)\s+(.*?)\s+(?:within|near|around|closest to)\s+.*?of\s+(.*)", q_lower)
        if within_match:
            target_phrase = within_match.group(1).strip()
            reference_phrase = within_match.group(2).strip()
        else:
            # Alternative: "which <target> overlap <reference>"
            overlap_match = re.search(r"(?:which|find|show)\s+(.*?)\s+(?:overlap|intersect with|cross)\s+(.*)", q_lower)
            if overlap_match:
                target_phrase = overlap_match.group(1).strip()
                reference_phrase = overlap_match.group(2).strip()
            else:
                # Default token splitting
                if "parcel" in q_lower:
                    target_phrase = "parcels"
                elif "structure" in q_lower:
                    target_phrase = "structures"

                if "asset" in q_lower or "municipal" in q_lower:
                    reference_phrase = "municipal assets"
                elif "drone" in q_lower:
                    reference_phrase = "drone structures"

        # Resolve Target Dataset
        target_match = None
        if target_phrase:
            target_match = await cls.resolve_dataset_for_term(db, project_id, target_phrase)

        # Resolve Reference Dataset
        ref_match = None
        if reference_phrase:
            ref_match = await cls.resolve_dataset_for_term(db, project_id, reference_phrase)

        # Ambiguity and fallback resolution
        all_ds_res = await db.execute(select(Dataset).where(Dataset.project_id == project_id))
        all_datasets = all_ds_res.scalars().all()

        is_ambiguous = False
        ambiguity_reason = None
        clarification_prompt = None

        if not target_match:
            if len(all_datasets) == 1:
                # Sole dataset in project - safe unambiguous default
                selected = all_datasets[0]
                target_match = DatasetSemanticMatch(
                    dataset_id=selected.id,
                    dataset_name=selected.name,
                    confidence=0.85,
                    reason="Single dataset available in project.",
                    geometry_type=selected.geometry_type,
                    feature_count=selected.feature_count or 0,
                )
            elif len(all_datasets) > 1:
                # Multiple datasets exist and query terms are ambiguous - do NOT silently guess!
                is_ambiguous = True
                ambiguity_reason = "Could not unambiguously identify target dataset from query terms."
                names = [d.name for d in all_datasets]
                clarification_prompt = f"Please specify which dataset you want to inspect: {', '.join(names)}."

        # Ensure target and reference datasets are not accidentally identical
        if target_match and ref_match and target_match.dataset_id == ref_match.dataset_id:
            # Query might be referencing features within the same dataset
            ref_match = None

        return SpatialIntentPlan(
            intent="spatial_analysis",
            analysis_type=analysis_type,
            target_dataset_id=target_match.dataset_id if target_match else None,
            target_dataset_name=target_match.dataset_name if target_match else None,
            reference_dataset_id=ref_match.dataset_id if ref_match else None,
            reference_dataset_name=ref_match.dataset_name if ref_match else None,
            distance=dist,
            unit=unit,
            confidence=min(target_match.confidence if target_match else 0.5, ref_match.confidence if ref_match else 1.0),
            is_ambiguous=is_ambiguous,
            ambiguity_reason=ambiguity_reason,
            clarification_prompt=clarification_prompt,
        )
