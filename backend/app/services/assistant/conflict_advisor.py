import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conflict import AttributeConflict
from app.models.unified import UnifiedLandRecord
from app.models.feature import CanonicalFeature, SourceFeature
from app.models.dataset import Dataset, DatasetVersion
from app.models.provenance import ProvenanceEvent
from app.schemas.conflict_proposal import ConflictResolutionProposal, ConflictSourceReference
from app.core.logging import logger


class ConflictAdvisorService:
    """
    Controlled AI advisory service generating explainable, evidence-backed
    conflict-resolution proposals. Enforces 100% read-only advisory guarantees
    with explicit human approval requirements.
    """

    AUTHORITY_HIERARCHY: Dict[str, Dict[str, float]] = {
        "zoning": {"cadastral": 0.95, "drone": 0.30, "infrastructure": 0.50},
        "owner_name": {"cadastral": 0.98, "drone": 0.10, "infrastructure": 0.40},
        "parcel_id": {"cadastral": 0.99, "drone": 0.10, "infrastructure": 0.30},
        "area_sqm": {"cadastral": 0.80, "drone": 0.85, "infrastructure": 0.50},
        "structure_height": {"drone": 0.95, "cadastral": 0.20, "infrastructure": 0.40},
    }

    @classmethod
    async def generate_proposal(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        conflict_id: uuid.UUID,
    ) -> Optional[ConflictResolutionProposal]:
        """
        Generates an advisory conflict resolution proposal without mutating any database records.
        """
        # 1. Fetch conflict
        stmt = (
            select(AttributeConflict)
            .join(UnifiedLandRecord, AttributeConflict.unified_land_record_id == UnifiedLandRecord.id)
            .where(
                AttributeConflict.id == conflict_id,
                UnifiedLandRecord.project_id == project_id,
            )
        )
        res = await db.execute(stmt)
        conflict = res.scalar_one_or_none()
        if not conflict:
            logger.warning(f"Conflict {conflict_id} not found in project {project_id}")
            return None

        # 2. Fetch parent unified record
        unif = await db.get(UnifiedLandRecord, conflict.unified_land_record_id)
        record_ident = unif.record_identifier if unif else str(conflict.unified_land_record_id)[:8]

        # 3. Inspect conflicting values
        detected = conflict.detected_values or []
        attr_name = conflict.attribute_name

        source_refs: List[ConflictSourceReference] = []
        cadastral_val = None
        drone_val = None
        best_val = None
        best_source = "Unknown"
        max_authority = 0.0

        for item in detected:
            if isinstance(item, dict):
                src_name = item.get("source_dataset") or item.get("source") or "Unknown"
                val = item.get("value")
                fid = item.get("feature_id") or item.get("source_feature_id")
            else:
                src_name = "Unknown"
                val = item
                fid = None

            # Determine source category weight
            src_lower = src_name.lower()
            src_cat = "other"
            if "cadastral" in src_lower or "registry" in src_lower:
                src_cat = "cadastral"
                cadastral_val = val
            elif "drone" in src_lower or "uav" in src_lower or "ortho" in src_lower:
                src_cat = "drone"
                drone_val = val
            elif "municipal" in src_lower or "asset" in src_lower:
                src_cat = "infrastructure"

            weight = cls.AUTHORITY_HIERARCHY.get(attr_name, {}).get(src_cat, 0.50)
            source_refs.append(
                ConflictSourceReference(
                    source_name=src_name,
                    feature_id=str(fid) if fid else None,
                    value=val,
                    source_type=src_cat,
                    authority_weight=weight,
                )
            )

            if weight > max_authority:
                max_authority = weight
                best_val = val
                best_source = src_name

        if best_val is None and detected:
            first = detected[0]
            best_val = first.get("value") if isinstance(first, dict) else first
            best_source = first.get("source_dataset", "Source A") if isinstance(first, dict) else "Source A"

        # 4. Formulate statements distinguishing FACT, INFERENCE, and RECOMMENDATION
        if attr_name == "zoning":
            fact_stmt = f"Source '{best_source}' specifies legal zoning as '{best_val}', differing from other source observations ({[r.value for r in source_refs if r.value != best_val]})."
            inference_stmt = "Cadastral authorities establish de jure legal zoning classifications, whereas aerial/drone surveys capture current physical site utilization."
            rec_stmt = f"Adopt legal zoning '{best_val}' from primary cadastral registry '{best_source}', and flag differing observed usage for municipal land-use inspection."
            reasoning = "Official administrative records take legal precedence for regulatory zoning designations under standard municipal governance rules."
            conf = 0.94

        elif attr_name == "area_sqm":
            vals = [float(r.value) for r in source_refs if r.value is not None and str(r.value).replace(".", "").isdigit()]
            diff = abs(vals[0] - vals[1]) if len(vals) >= 2 else 0.0
            fact_stmt = f"Recorded parcel area varies by {diff:.1f} m² across contributing sources (values: {', '.join(str(v) for v in vals)} m²)."
            inference_stmt = "Variance reflects methodological divergence between recorded deed boundaries and corrected orthorectified photogrammetric polygon extraction."
            rec_stmt = f"Retain recorded legal area '{best_val}' m² for title synchronization, while registering physical boundary delta of {diff:.1f} m² in audit notes."
            reasoning = "Land title governance mandates recorded survey figures for transaction validation unless formal boundary redelineation is approved."
            conf = 0.88

        else:
            fact_stmt = f"Attribute '{attr_name}' has conflicting values: {', '.join(f'{r.source_name}: {r.value}' for r in source_refs)}."
            inference_stmt = f"Data discrepancy originates from differing capture standards between {len(source_refs)} independent survey systems."
            rec_stmt = f"Accept '{best_val}' from '{best_source}' based on relative source domain reliability ({max_authority * 100:.0f}% confidence)."
            reasoning = f"Source '{best_source}' demonstrates highest domain authority for '{attr_name}' within the current harmonization hierarchy."
            conf = max(0.70, max_authority)

        evidence = [
            f"Observed in conflict record {str(conflict.id)[:8]} on unified record {record_ident}.",
            f"Evaluated {len(source_refs)} contributing source dataset(s): {', '.join(r.source_name for r in source_refs)}.",
            f"Configured domain authority weight for '{best_source}': {max_authority:.2f}.",
        ]

        return ConflictResolutionProposal(
            conflict_id=conflict.id,
            project_id=project_id,
            unified_land_record_id=conflict.unified_land_record_id,
            record_identifier=record_ident,
            attribute_name=attr_name,
            conflicting_values=detected,
            recommended_value=best_val,
            recommended_source=best_source,
            confidence=conf,
            fact_statement=fact_stmt,
            inference_statement=inference_stmt,
            recommendation_statement=rec_stmt,
            reasoning=reasoning,
            supporting_evidence=evidence,
            source_references=source_refs,
            requires_human_approval=True,
            is_advisory_only=True,
        )
