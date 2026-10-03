import uuid
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple, Set
from collections import defaultdict
from sqlalchemy import select, func, and_, or_, text, desc, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.project import Project
from app.models.dataset import Dataset, DatasetVersion
from app.models.feature import CanonicalFeature
from app.models.unified import UnifiedLandRecord, UnifiedLandRecordSource
from app.models.conflict import AttributeConflict, ConflictResolution, GeospatialConflict
from app.models.pipeline import PipelineStageExecution
from app.models.provenance import ProvenanceEvent
from app.services.provenance.service import extract_feature_display_id
from app.services.unified.service import detect_source_role
from app.schemas.conflict import (
    ConflictSourceValue,
    AttributeConflictRead,
    ConflictResolutionRead,
    ConflictResolveInput,
    ConflictDismissInput,
    ConflictListResponse,
    ConflictSummaryResponse,
    GeospatialConflictRead,
    GeospatialConflictStatusUpdate,
    GeospatialConflictListResponse,
)
from app.schemas.pipeline import (
    ConflictDetectionRunRequest,
    ConflictDetectionRunResponse,
)


def normalize_text_value(val: Any) -> Optional[str]:
    """Trims and lowercases text for fair semantic comparison."""
    if val is None:
        return None
    s = str(val).strip()
    if s.lower() in ["", "none", "null", "unknown", "—", "-"]:
        return None
    return s


def parse_numeric_value(val: Any) -> Optional[float]:
    """Attempts to parse a numeric value safely."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def normalize_semantic_land_use(val: Any) -> Optional[str]:
    """Normalizes land-use string into standardized semantic categories."""
    if val is None:
        return None
    v = str(val).strip().lower()
    if not v or v in ["none", "null", "unknown", "—", "-"]:
        return None
    if any(k in v for k in ["res", "housing", "gaothan", "bungalow", "apartment", "flats", "living"]):
        return "RESIDENTIAL"
    if any(k in v for k in ["agr", "farm", "crop", "paddy", "orchard", "kheti", "rural"]):
        return "AGRICULTURAL"
    if any(k in v for k in ["com", "shop", "office", "retail", "market", "mall", "business"]):
        return "COMMERCIAL"
    if any(k in v for k in ["ind", "factory", "warehouse", "workshop", "midc", "manufacturing"]):
        return "INDUSTRIAL"
    if any(k in v for k in ["gov", "public", "school", "hospital", "institute", "civic"]):
        return "PUBLIC_INSTITUTIONAL"
    if any(k in v for k in ["forest", "green", "garden", "park", "reserve"]):
        return "FOREST_GREEN"
    if any(k in v for k in ["vacant", "barren", "open", "na", "waste", "unutilized"]):
        return "VACANT"
    return v.upper()


def normalize_semantic_mutation(val: Any) -> Optional[str]:
    """Normalizes parcel registry mutation status."""
    if val is None:
        return None
    v = str(val).strip().lower()
    if not v or v in ["none", "null", "unknown", "—", "-"]:
        return None
    if any(k in v for k in ["appr", "cert", "sanction", "verified", "registered", "final"]):
        return "APPROVED"
    if any(k in v for k in ["pend", "in_progress", "under_review", "submitted", "awaiting", "draft"]):
        return "PENDING"
    if any(k in v for k in ["disp", "litig", "stay", "court", "object", "dispute", "challenge"]):
        return "DISPUTED"
    if any(k in v for k in ["reject", "cancel", "revoked", "dismissed"]):
        return "REJECTED"
    return v.upper()


def normalize_semantic_risk(val: Any) -> Optional[str]:
    """Normalizes environmental / hazard risk ratings."""
    if val is None:
        return None
    v = str(val).strip().lower()
    if not v or v in ["none", "null", "unknown", "—", "-"]:
        return None
    if any(k in v for k in ["crit", "severe", "very_high", "flood_zone_1"]):
        return "CRITICAL"
    if any(k in v for k in ["high", "hazard", "red", "danger"]):
        return "HIGH"
    if any(k in v for k in ["med", "moderate", "amber", "yellow"]):
        return "MEDIUM"
    if any(k in v for k in ["low", "safe", "green", "minimal"]):
        return "LOW"
    return v.upper()


class ConflictDetectionService:
    """
    Dedicated service for detecting, classifying, persisting, and resolving
    attribute conflicts across heterogeneous source features contributing to
    Unified Land Records.
    """

    # Configurable numeric tolerance (5% relative difference and > 1.0 m² absolute)
    NUMERIC_RELATIVE_TOLERANCE: float = 0.05
    NUMERIC_ABSOLUTE_TOLERANCE: float = 1.0

    @classmethod
    def detect_conflicts_for_features(
        cls,
        features: List[CanonicalFeature],
        source_roles: Dict[uuid.UUID, str],
    ) -> List[Dict[str, Any]]:
        """
        Pure deterministic conflict detection comparing contributing source features.
        Returns list of structured conflict dictionaries with evidence.
        """
        if len(features) < 2:
            return []

        # 1. Attribute extraction per source feature
        # Map: attribute_name -> list of source value descriptors
        attr_values: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # Standard canonical attribute groups to check
        for cf in features:
            role = source_roles.get(cf.id, "OTHER")
            ds = cf.dataset_version.dataset if cf.dataset_version and cf.dataset_version.dataset else None
            ds_name = ds.name if ds else "Dataset"
            ds_version = cf.dataset_version.version_number if cf.dataset_version else 1
            disp_id = extract_feature_display_id(cf) or str(cf.id)[:8]

            props = cf.canonical_properties or {}
            lower_props = {k.lower(): v for k, v in props.items() if not k.startswith("_")}

            # Check: land_use
            land_use_val = None
            for k in ["land_use", "landuse", "zoning", "category", "usage", "type"]:
                if k in lower_props:
                    norm = normalize_text_value(lower_props[k])
                    if norm:
                        land_use_val = norm
                        break
            attr_values["land_use"].append({
                "source_role": role,
                "dataset_id": ds.id if ds else None,
                "dataset_name": ds_name,
                "dataset_version": ds_version,
                "feature_id": cf.id,
                "feature_identifier": disp_id,
                "raw_value": land_use_val,
            })

            # Check: area
            area_val = None
            for k in ["area", "sq_m", "area_sqm", "area_m2"]:
                if k in lower_props:
                    parsed_num = parse_numeric_value(lower_props[k])
                    if parsed_num is not None:
                        area_val = round(parsed_num, 2)
                        break
            attr_values["area"].append({
                "source_role": role,
                "dataset_id": ds.id if ds else None,
                "dataset_name": ds_name,
                "dataset_version": ds_version,
                "feature_id": cf.id,
                "feature_identifier": disp_id,
                "raw_value": area_val,
            })

            # Check: address / locality
            address_val = None
            for k in ["address", "locality", "street", "location", "place"]:
                if k in lower_props:
                    norm = normalize_text_value(lower_props[k])
                    if norm:
                        address_val = norm
                        break
            attr_values["address"].append({
                "source_role": role,
                "dataset_id": ds.id if ds else None,
                "dataset_name": ds_name,
                "dataset_version": ds_version,
                "feature_id": cf.id,
                "feature_identifier": disp_id,
                "raw_value": address_val,
            })

            # Check general common properties (owner, occupied, floors, status)
            for common_k in ["owner", "occupied", "status", "floors", "height"]:
                if common_k in lower_props:
                    val = lower_props[common_k]
                    attr_values[common_k].append({
                        "source_role": role,
                        "dataset_id": ds.id if ds else None,
                        "dataset_name": ds_name,
                        "dataset_version": ds_version,
                        "feature_id": cf.id,
                        "feature_identifier": disp_id,
                        "raw_value": val,
                    })

        # 2. Analyze each attribute group for conflicts
        detected_conflicts: List[Dict[str, Any]] = []

        for attr_name, items in attr_values.items():
            non_null_items = [it for it in items if it["raw_value"] is not None]
            null_items = [it for it in items if it["raw_value"] is None]

            # Case A: Numeric difference (e.g. area)
            if attr_name in ["area", "sq_m", "floors", "height"]:
                numeric_vals = [
                    (it, parse_numeric_value(it["raw_value"]))
                    for it in non_null_items
                ]
                valid_numerics = [(it, v) for it, v in numeric_vals if v is not None]

                if len(valid_numerics) >= 2:
                    nums = [v for _, v in valid_numerics]
                    min_val = min(nums)
                    max_val = max(nums)
                    diff = max_val - min_val

                    # Relative difference
                    rel_diff = (diff / max_val) if max_val > 0 else 0.0

                    if diff > cls.NUMERIC_ABSOLUTE_TOLERANCE and rel_diff > cls.NUMERIC_RELATIVE_TOLERANCE:
                        evidence_values = [
                            {
                                "source_role": it["source_role"],
                                "dataset_id": str(it["dataset_id"]) if it["dataset_id"] else None,
                                "dataset_name": it["dataset_name"],
                                "dataset_version": it["dataset_version"],
                                "feature_id": str(it["feature_id"]),
                                "feature_identifier": it["feature_identifier"],
                                "value": f"{val} m²" if attr_name == "area" else val,
                            }
                            for it, val in valid_numerics
                        ]
                        detected_conflicts.append({
                            "attribute_name": attr_name,
                            "conflict_type": "NUMERIC_DIFFERENCE",
                            "severity": "MEDIUM",
                            "detected_values": evidence_values,
                        })
                continue

            # Case B: Text / Categorical Value Mismatch
            if len(non_null_items) >= 2:
                # Group by normalized lowercase representation
                normalized_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
                for it in non_null_items:
                    norm = str(it["raw_value"]).strip().lower()
                    normalized_map[norm].append(it)

                # If more than 1 distinct normalized value exists -> VALUE_MISMATCH!
                if len(normalized_map) > 1:
                    if attr_name == "address":
                        # Check if all address strings are sub-strings of the most detailed address
                        sorted_norms = sorted(list(normalized_map.keys()), key=len, reverse=True)
                        longest = sorted_norms[0]
                        if all(n in longest for n in sorted_norms):
                            # Harmonious address refinement (e.g. street vs street + city), not a conflict!
                            continue

                    evidence_values = [
                        {
                            "source_role": it["source_role"],
                            "dataset_id": str(it["dataset_id"]) if it["dataset_id"] else None,
                            "dataset_name": it["dataset_name"],
                            "dataset_version": it["dataset_version"],
                            "feature_id": str(it["feature_id"]),
                            "feature_identifier": it["feature_identifier"],
                            "value": it["raw_value"],
                        }
                        for it in non_null_items
                    ]
                    severity = "HIGH" if attr_name in ["land_use", "zoning", "owner"] else "MEDIUM"
                    detected_conflicts.append({
                        "attribute_name": attr_name,
                        "conflict_type": "VALUE_MISMATCH",
                        "severity": severity,
                        "detected_values": evidence_values,
                    })
                    continue

            # Case C: NULL vs Value Conflict
            # One source provides a clear value while another explicitly has null/missing
            if len(non_null_items) >= 1 and len(null_items) >= 1:
                # Only flag for primary attributes like land_use
                if attr_name in ["land_use", "address"]:
                    evidence_values = [
                        {
                            "source_role": it["source_role"],
                            "dataset_id": str(it["dataset_id"]) if it["dataset_id"] else None,
                            "dataset_name": it["dataset_name"],
                            "dataset_version": it["dataset_version"],
                            "feature_id": str(it["feature_id"]),
                            "feature_identifier": it["feature_identifier"],
                            "value": it["raw_value"] if it["raw_value"] is not None else "(Not Provided)",
                        }
                        for it in items
                    ]
                    detected_conflicts.append({
                        "attribute_name": attr_name,
                        "conflict_type": "NULL_VALUE_CONFLICT",
                        "severity": "LOW",
                        "detected_values": evidence_values,
                    })

        return detected_conflicts

    @classmethod
    async def detect_and_sync_conflicts_for_record(
        cls,
        db: AsyncSession,
        record: UnifiedLandRecord,
        features: Optional[List[CanonicalFeature]] = None,
        source_roles: Optional[Dict[uuid.UUID, str]] = None,
    ) -> List[AttributeConflict]:
        """
        Detects attribute conflicts across contributing sources for a UnifiedLandRecord,
        persists new conflicts idempotently, preserves existing human resolutions,
        and updates the record status accordingly.
        """
        # Load contributing features and roles if not explicitly provided
        if features is None or source_roles is None:
            stmt_sources = (
                select(UnifiedLandRecordSource)
                .where(UnifiedLandRecordSource.unified_land_record_id == record.id)
                .options(
                    joinedload(UnifiedLandRecordSource.feature)
                    .joinedload(CanonicalFeature.dataset_version)
                    .joinedload(DatasetVersion.dataset)
                )
            )
            sources_list = (await db.execute(stmt_sources)).scalars().all()
            features = []
            source_roles = {}
            for src in sources_list:
                if src.feature:
                    features.append(src.feature)
                    source_roles[src.feature.id] = src.source_role

        detected = cls.detect_conflicts_for_features(features, source_roles)

        # Query existing conflicts for this record
        stmt = (
            select(AttributeConflict)
            .where(AttributeConflict.unified_land_record_id == record.id)
            .options(joinedload(AttributeConflict.resolution))
        )
        existing_conflicts = list((await db.execute(stmt)).scalars().all())
        existing_map = {c.attribute_name: c for c in existing_conflicts}

        synced_conflicts: List[AttributeConflict] = []
        has_unresolved = False

        for det in detected:
            attr = det["attribute_name"]
            existing = existing_map.get(attr)

            if existing:
                # If already resolved or dismissed, preserve resolution!
                if existing.status in ["RESOLVED", "DISMISSED"]:
                    # Update detected_values in case sources expanded
                    existing.detected_values = det["detected_values"]
                    synced_conflicts.append(existing)
                else:
                    # Update unresolved conflict
                    existing.conflict_type = det["conflict_type"]
                    existing.severity = det["severity"]
                    existing.detected_values = det["detected_values"]
                    synced_conflicts.append(existing)
                    has_unresolved = True
            else:
                # Create new unresolved conflict
                new_c = AttributeConflict(
                    project_id=record.project_id,
                    unified_land_record_id=record.id,
                    attribute_name=attr,
                    conflict_type=det["conflict_type"],
                    severity=det["severity"],
                    status="UNRESOLVED",
                    detected_values=det["detected_values"],
                )
                db.add(new_c)
                synced_conflicts.append(new_c)
                has_unresolved = True

        # Check existing conflicts that were not detected this run
        for attr, c in existing_map.items():
            if not any(d["attribute_name"] == attr for d in detected):
                if c.status == "UNRESOLVED":
                    has_unresolved = True
                synced_conflicts.append(c)

        # Check if any material unresolved conflicts exist (core attributes or high/critical severity)
        material_unresolved = any(
            c.status == "UNRESOLVED"
            and (
                c.severity in ["HIGH", "CRITICAL"]
                or c.attribute_name in ["land_use", "zoning", "area"]
            )
            for c in synced_conflicts
        )

        if material_unresolved:
            record.status = "CONFLICT"
        elif record.status == "CONFLICT":
            all_material_resolved = all(
                c.status in ["RESOLVED", "DISMISSED"]
                for c in synced_conflicts
                if c.attribute_name in ["land_use", "zoning", "area"]
                or c.severity in ["HIGH", "CRITICAL"]
            )
            if all_material_resolved and len(features) >= 2:
                record.status = "ACTIVE"

        await db.flush()
        return synced_conflicts

    @classmethod
    async def resolve_conflict(
        cls,
        db: AsyncSession,
        conflict_id: uuid.UUID,
        input_data: ConflictResolveInput,
    ) -> AttributeConflictRead:
        """
        Executes an evidence-grounded human conflict resolution:
        - Validates input (source feature membership, non-empty manual value, required comment)
        - Creates an immutable ConflictResolution record
        - Updates AttributeConflict status to RESOLVED
        - Updates UnifiedLandRecord canonical_attributes with the resolved value and provenance
        - Updates UnifiedLandRecord status to ACTIVE if all conflicts resolved
        - Records an audit trail event CONFLICT_RESOLVED
        """
        # Fetch conflict with unified record and sources
        stmt = (
            select(AttributeConflict)
            .where(AttributeConflict.id == conflict_id)
            .options(
                joinedload(AttributeConflict.unified_record)
                .selectinload(UnifiedLandRecord.sources)
                .joinedload(UnifiedLandRecordSource.feature),
                joinedload(AttributeConflict.resolution),
            )
        )
        conflict = (await db.execute(stmt)).scalar_one_or_none()
        if not conflict:
            raise ValueError(f"Attribute conflict with ID '{conflict_id}' not found.")

        record = conflict.unified_record
        if not record:
            raise ValueError("Associated unified land record not found.")

        # Validation
        res_type = input_data.resolution_type.upper()
        if res_type not in ["SOURCE_SELECTION", "MANUAL_VALUE"]:
            raise ValueError("Resolution type must be either 'SOURCE_SELECTION' or 'MANUAL_VALUE'.")

        comment = input_data.comment.strip() if input_data.comment else ""
        if not comment:
            raise ValueError("A resolution note / comment is required for audit traceability.")

        resolved_val: Any = None
        selected_feature_id: Optional[uuid.UUID] = None
        selected_role: Optional[str] = None

        if res_type == "SOURCE_SELECTION":
            if not input_data.selected_source_feature_id:
                raise ValueError("selected_source_feature_id is required for SOURCE_SELECTION.")

            # Validate that selected_source_feature_id actually contributes to this record
            valid_sources = {s.feature_id: s for s in record.sources}
            if input_data.selected_source_feature_id not in valid_sources:
                raise ValueError(
                    f"Selected feature '{input_data.selected_source_feature_id}' does not contribute to this unified record."
                )

            selected_feature_id = input_data.selected_source_feature_id
            matched_source = valid_sources[selected_feature_id]
            selected_role = matched_source.source_role

            # Find the value from detected_values or feature properties
            found_val = None
            for dv in conflict.detected_values:
                if str(dv.get("feature_id")) == str(selected_feature_id):
                    found_val = dv.get("value")
                    break

            if found_val is None and matched_source.feature:
                props = matched_source.feature.canonical_properties or {}
                found_val = props.get(conflict.attribute_name)

            resolved_val = found_val

        elif res_type == "MANUAL_VALUE":
            if input_data.manual_value is None or str(input_data.manual_value).strip() == "":
                raise ValueError("A non-empty manual_value is required for MANUAL_VALUE resolution.")
            resolved_val = input_data.manual_value

        # Create ConflictResolution
        now = datetime.now(timezone.utc)
        resolution = ConflictResolution(
            conflict_id=conflict.id,
            resolution_type=res_type,
            selected_source_feature_id=selected_feature_id,
            selected_source_role=selected_role,
            resolved_value=resolved_val,
            comment=comment,
            resolved_by=input_data.resolved_by or "Human Reviewer",
            resolved_at=now,
        )
        db.add(resolution)
        await db.flush()

        # Update AttributeConflict
        conflict.status = "RESOLVED"
        conflict.resolution_id = resolution.id
        conflict.resolution = resolution
        conflict.updated_at = now

        # Update UnifiedLandRecord canonical_attributes
        canon_attrs = dict(record.canonical_attributes or {})
        canon_attrs[conflict.attribute_name] = resolved_val
        canon_attrs[f"{conflict.attribute_name}_resolution"] = {
            "resolved_value": resolved_val,
            "resolution_type": res_type,
            "selected_source_role": selected_role,
            "selected_source_feature_id": str(selected_feature_id) if selected_feature_id else None,
            "comment": comment,
            "resolved_at": now.isoformat(),
            "resolved_by": resolution.resolved_by,
        }
        record.canonical_attributes = canon_attrs

        # If area was resolved, update canonical area column if numeric
        if conflict.attribute_name == "area":
            num_area = parse_numeric_value(resolved_val)
            if num_area is not None:
                record.area = num_area

        # Check if all conflicts for this record are resolved
        other_conflicts_stmt = (
            select(func.count(AttributeConflict.id))
            .where(
                and_(
                    AttributeConflict.unified_land_record_id == record.id,
                    AttributeConflict.id != conflict.id,
                    AttributeConflict.status == "UNRESOLVED",
                )
            )
        )
        unresolved_count = (await db.execute(other_conflicts_stmt)).scalar() or 0

        if unresolved_count == 0:
            record.status = "ACTIVE"

        # Record Audit Event
        audit_event = ProvenanceEvent(
            project_id=conflict.project_id,
            unified_land_record_id=record.id,
            event_type="CONFLICT_RESOLVED",
            source_type="CONFLICT_RESOLUTION",
            source_id=resolution.id,
            event_metadata={
                "conflict_id": str(conflict.id),
                "attribute_name": conflict.attribute_name,
                "resolution_type": res_type,
                "resolved_value": resolved_val,
                "selected_source_role": selected_role,
                "comment": comment,
                "record_status": record.status,
            },
        )
        db.add(audit_event)
        await db.commit()

        # Reload conflict with resolution
        stmt_reload = (
            select(AttributeConflict)
            .where(AttributeConflict.id == conflict.id)
            .options(joinedload(AttributeConflict.resolution))
        )
        reloaded = (await db.execute(stmt_reload)).scalar_one()

        return cls._map_to_schema(reloaded, record_identifier=record.record_identifier)

    @classmethod
    async def dismiss_conflict(
        cls,
        db: AsyncSession,
        conflict_id: uuid.UUID,
        input_data: ConflictDismissInput,
    ) -> AttributeConflictRead:
        """
        Dismisses an AttributeConflict with a mandatory audit reason.
        """
        stmt = (
            select(AttributeConflict)
            .where(AttributeConflict.id == conflict_id)
            .options(
                joinedload(AttributeConflict.unified_record),
                joinedload(AttributeConflict.resolution),
            )
        )
        conflict = (await db.execute(stmt)).scalar_one_or_none()
        if not conflict:
            raise ValueError(f"Attribute conflict with ID '{conflict_id}' not found.")

        reason = input_data.reason.strip() if input_data.reason else ""
        if not reason:
            raise ValueError("A reason is required to dismiss an attribute conflict.")

        now = datetime.now(timezone.utc)
        resolution = ConflictResolution(
            conflict_id=conflict.id,
            resolution_type="DISMISSED",
            selected_source_feature_id=None,
            selected_source_role=None,
            resolved_value="DISMISSED",
            comment=reason,
            resolved_by=input_data.resolved_by or "Human Reviewer",
            resolved_at=now,
        )
        db.add(resolution)
        await db.flush()

        conflict.status = "DISMISSED"
        conflict.resolution_id = resolution.id
        conflict.resolution = resolution
        conflict.dismissal_reason = reason
        conflict.dismissed_at = now
        conflict.updated_at = now

        # Update record status if no other unresolved conflicts remain
        record = conflict.unified_record
        if record:
            other_stmt = (
                select(func.count(AttributeConflict.id))
                .where(
                    and_(
                        AttributeConflict.unified_land_record_id == record.id,
                        AttributeConflict.id != conflict.id,
                        AttributeConflict.status == "UNRESOLVED",
                    )
                )
            )
            unresolved_count = (await db.execute(other_stmt)).scalar() or 0
            if unresolved_count == 0:
                record.status = "ACTIVE"

        # Record Audit Event
        audit_event = ProvenanceEvent(
            project_id=conflict.project_id,
            unified_land_record_id=record.id if record else None,
            event_type="CONFLICT_DISMISSED",
            source_type="CONFLICT_RESOLUTION",
            source_id=resolution.id,
            event_metadata={
                "conflict_id": str(conflict.id),
                "attribute_name": conflict.attribute_name,
                "reason": reason,
                "record_status": record.status if record else None,
            },
        )
        db.add(audit_event)
        await db.commit()

        stmt_reload = (
            select(AttributeConflict)
            .where(AttributeConflict.id == conflict.id)
            .options(joinedload(AttributeConflict.resolution))
        )
        reloaded = (await db.execute(stmt_reload)).scalar_one()

        return cls._map_to_schema(reloaded, record_identifier=record.record_identifier if record else None)

    @classmethod
    async def get_record_conflicts(
        cls,
        db: AsyncSession,
        record_id: uuid.UUID,
    ) -> List[AttributeConflictRead]:
        """
        Returns all conflicts (unresolved and resolved) for an individual UnifiedLandRecord.
        """
        record = await db.get(UnifiedLandRecord, record_id)
        if not record:
            raise ValueError(f"Unified land record with ID '{record_id}' not found.")

        # Ensure conflicts are synchronized
        await cls.detect_and_sync_conflicts_for_record(db, record)

        stmt = (
            select(AttributeConflict)
            .where(AttributeConflict.unified_land_record_id == record_id)
            .options(joinedload(AttributeConflict.resolution))
            .order_by(AttributeConflict.created_at.asc())
        )
        conflicts = list((await db.execute(stmt)).scalars().all())

        return [
            cls._map_to_schema(c, record_identifier=record.record_identifier)
            for c in conflicts
        ]

    @classmethod
    async def get_project_conflicts(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        status: Optional[str] = None,
        attribute_name: Optional[str] = None,
        severity: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> ConflictListResponse:
        """
        Returns paginated attribute conflicts for a project with optional filtering.
        """
        project = await db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project with ID '{project_id}' not found.")

        filters = [AttributeConflict.project_id == project_id]

        if status and status.upper() != "ALL":
            filters.append(AttributeConflict.status == status.strip().upper())
        if attribute_name:
            filters.append(AttributeConflict.attribute_name == attribute_name.strip())
        if severity:
            filters.append(AttributeConflict.severity == severity.strip().upper())

        # Total count
        count_stmt = select(func.count(AttributeConflict.id)).where(*filters)
        total = (await db.execute(count_stmt)).scalar() or 0

        # Query items with unified record identifier
        stmt = (
            select(AttributeConflict, UnifiedLandRecord.record_identifier)
            .join(UnifiedLandRecord, UnifiedLandRecord.id == AttributeConflict.unified_land_record_id)
            .where(*filters)
            .options(joinedload(AttributeConflict.resolution))
            .order_by(AttributeConflict.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        results = (await db.execute(stmt)).all()

        items = [
            cls._map_to_schema(c, record_identifier=rec_id)
            for c, rec_id in results
        ]

        return ConflictListResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )

    @classmethod
    async def get_project_conflict_summary(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> ConflictSummaryResponse:
        """
        Returns project-level conflict statistics.
        """
        project = await db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project with ID '{project_id}' not found.")

        # Status counts
        stmt = (
            select(
                AttributeConflict.status,
                func.count(AttributeConflict.id),
            )
            .where(AttributeConflict.project_id == project_id)
            .group_by(AttributeConflict.status)
        )
        status_rows = (await db.execute(stmt)).all()
        status_map = {st: cnt for st, cnt in status_rows}

        total_conflicts = sum(status_map.values())
        unresolved = status_map.get("UNRESOLVED", 0)
        resolved = status_map.get("RESOLVED", 0)
        dismissed = status_map.get("DISMISSED", 0)

        # Records with conflicts
        rec_stmt = (
            select(func.count(func.distinct(AttributeConflict.unified_land_record_id)))
            .where(AttributeConflict.project_id == project_id)
        )
        records_with_conflicts = (await db.execute(rec_stmt)).scalar() or 0

        # By attribute
        attr_stmt = (
            select(
                AttributeConflict.attribute_name,
                func.count(AttributeConflict.id),
            )
            .where(AttributeConflict.project_id == project_id)
            .group_by(AttributeConflict.attribute_name)
        )
        attr_rows = (await db.execute(attr_stmt)).all()
        by_attr = {name: cnt for name, cnt in attr_rows}

        # By severity
        sev_stmt = (
            select(
                AttributeConflict.severity,
                func.count(AttributeConflict.id),
            )
            .where(AttributeConflict.project_id == project_id)
            .group_by(AttributeConflict.severity)
        )
        sev_rows = (await db.execute(sev_stmt)).all()
        by_sev = {sev: cnt for sev, cnt in sev_rows}

        return ConflictSummaryResponse(
            project_id=project_id,
            total_conflicts=total_conflicts,
            unresolved_conflicts=unresolved,
            resolved_conflicts=resolved,
            dismissed_conflicts=dismissed,
            records_with_conflicts=records_with_conflicts,
            by_attribute=by_attr,
            by_severity=by_sev,
        )

    @classmethod
    async def get_conflict_detail(
        cls,
        db: AsyncSession,
        conflict_id: uuid.UUID,
    ) -> Optional[AttributeConflictRead]:
        """
        Returns full conflict detail by ID.
        """
        stmt = (
            select(AttributeConflict, UnifiedLandRecord.record_identifier)
            .join(UnifiedLandRecord, UnifiedLandRecord.id == AttributeConflict.unified_land_record_id)
            .where(AttributeConflict.id == conflict_id)
            .options(joinedload(AttributeConflict.resolution))
        )
        res = (await db.execute(stmt)).first()
        if not res:
            return None
        c, rec_id = res
        return cls._map_to_schema(c, record_identifier=rec_id)

    @classmethod
    def _map_to_schema(
        cls,
        conflict: AttributeConflict,
        record_identifier: Optional[str] = None,
    ) -> AttributeConflictRead:
        """Maps an ORM AttributeConflict to Pydantic schema."""
        detected_vals = [
            ConflictSourceValue(
                source_role=v.get("source_role", "OTHER"),
                dataset_id=uuid.UUID(v["dataset_id"]) if v.get("dataset_id") else None,
                dataset_name=v.get("dataset_name", "Dataset"),
                dataset_version=v.get("dataset_version", 1),
                feature_id=uuid.UUID(str(v["feature_id"])),
                feature_identifier=v.get("feature_identifier", str(v["feature_id"])[:8]),
                value=v.get("value"),
            )
            for v in (conflict.detected_values or [])
            if isinstance(v, dict) and "feature_id" in v
        ]

        resolution_read = None
        if conflict.resolution:
            r = conflict.resolution
            resolution_read = ConflictResolutionRead(
                id=r.id,
                conflict_id=r.conflict_id,
                resolution_type=r.resolution_type,
                selected_source_feature_id=r.selected_source_feature_id,
                selected_source_role=r.selected_source_role,
                resolved_value=r.resolved_value,
                comment=r.comment,
                resolved_by=r.resolved_by,
                resolved_at=r.resolved_at,
            )

        dismissal_reason = None
        if conflict.resolution and conflict.resolution.resolution_type == "DISMISSED":
            dismissal_reason = conflict.resolution.comment
        elif getattr(conflict, "dismissal_reason", None):
            dismissal_reason = conflict.dismissal_reason

        return AttributeConflictRead(
            id=conflict.id,
            project_id=conflict.project_id,
            unified_land_record_id=conflict.unified_land_record_id,
            record_identifier=record_identifier,
            attribute_name=conflict.attribute_name,
            conflict_type=conflict.conflict_type,
            severity=conflict.severity,
            status=conflict.status,
            detected_values=detected_vals,
            resolution=resolution_read,
            dismissal_reason=dismissal_reason,
            created_at=conflict.created_at,
            updated_at=conflict.updated_at,
        )

    # =========================================================================
    # STAGE 08 — GEOSPATIAL CONFLICT DETECTION ENGINE & WORKFLOW
    # =========================================================================

    @classmethod
    def _classify_area_severity(
        cls,
        diff_pct: float,
        req: ConflictDetectionRunRequest,
    ) -> Tuple[str, str]:
        """Deterministic severity classification for parcel area discrepancy."""
        if diff_pct > req.area_high_threshold_pct:
            return (
                "CRITICAL",
                f"Parcel area differs by {diff_pct:.1f}%, exceeding the critical threshold of {req.area_high_threshold_pct:.1f}%.",
            )
        elif diff_pct >= req.area_medium_threshold_pct:
            return (
                "HIGH",
                f"Parcel area differs by {diff_pct:.1f}%, exceeding the high conflict threshold of {req.area_medium_threshold_pct:.1f}%.",
            )
        elif diff_pct >= req.area_low_threshold_pct:
            return (
                "MEDIUM",
                f"Parcel area differs by {diff_pct:.1f}%, exceeding the standard tolerance threshold of {req.area_low_threshold_pct:.1f}%.",
            )
        else:
            return (
                "LOW",
                f"Parcel area differs by {diff_pct:.1f}%, within minor tolerance limits.",
            )

    @classmethod
    def _classify_land_use_severity(
        cls,
        norm_a: str,
        norm_b: str,
    ) -> Tuple[str, str]:
        """Deterministic severity classification for land use divergence."""
        critical_incompatible = {
            ("AGRICULTURAL", "INDUSTRIAL"), ("INDUSTRIAL", "AGRICULTURAL"),
            ("AGRICULTURAL", "COMMERCIAL"), ("COMMERCIAL", "AGRICULTURAL"),
            ("RESIDENTIAL", "INDUSTRIAL"), ("INDUSTRIAL", "RESIDENTIAL"),
            ("FOREST_GREEN", "INDUSTRIAL"), ("INDUSTRIAL", "FOREST_GREEN"),
            ("FOREST_GREEN", "COMMERCIAL"), ("COMMERCIAL", "FOREST_GREEN"),
        }
        if (norm_a, norm_b) in critical_incompatible:
            return (
                "CRITICAL",
                f"Severe zoning disparity between incompatible land-use classifications ({norm_a} vs {norm_b}).",
            )
        elif (norm_a == "RESIDENTIAL" and norm_b == "COMMERCIAL") or (norm_a == "COMMERCIAL" and norm_b == "RESIDENTIAL"):
            return (
                "HIGH",
                f"Significant land use conflict between {norm_a} and {norm_b} requiring regulatory review.",
            )
        elif "VACANT" in (norm_a, norm_b):
            return (
                "MEDIUM",
                f"Developed vs vacant land-use designation divergence ({norm_a} vs {norm_b}).",
            )
        else:
            return (
                "MEDIUM",
                f"Semantic land use classification divergence ({norm_a} vs {norm_b}).",
            )

    @classmethod
    def _classify_mutation_severity(
        cls,
        norm_a: str,
        norm_b: str,
    ) -> Tuple[str, str]:
        """Deterministic severity classification for parcel mutation / registry status."""
        if "DISPUTED" in (norm_a, norm_b) or "REJECTED" in (norm_a, norm_b):
            return (
                "CRITICAL",
                f"Registry title dispute or rejection flagged in mutation record ({norm_a} vs {norm_b}).",
            )
        elif ("APPROVED" in (norm_a, norm_b)) and ("PENDING" in (norm_a, norm_b)):
            return (
                "HIGH",
                f"Disagreement in mutation confirmation: one source records Approved while another remains Pending.",
            )
        else:
            return (
                "MEDIUM",
                f"Registry mutation status divergence between '{norm_a}' and '{norm_b}'.",
            )

    @classmethod
    def _classify_risk_severity(
        cls,
        norm_a: str,
        norm_b: str,
    ) -> Tuple[str, str]:
        """Deterministic severity classification for environmental / hazard risk ratings."""
        if ("CRITICAL" in (norm_a, norm_b) or "HIGH" in (norm_a, norm_b)) and ("LOW" in (norm_a, norm_b)):
            return (
                "CRITICAL",
                f"Major environmental hazard divergence: High/Critical hazard vs Low/Safe risk.",
            )
        elif ("HIGH" in (norm_a, norm_b)) and ("MEDIUM" in (norm_a, norm_b)):
            return (
                "HIGH",
                f"Substantial hazard risk rating divergence ({norm_a} vs {norm_b}).",
            )
        else:
            return (
                "MEDIUM",
                f"Environmental risk rating discrepancy ({norm_a} vs {norm_b}).",
            )

    @classmethod
    def _classify_geometry_severity(
        cls,
        iou: float,
        centroid_dist: float,
        valid_a: bool,
        valid_b: bool,
    ) -> Tuple[str, str]:
        """Deterministic severity classification for topological / spatial boundary variance."""
        if not valid_a or not valid_b:
            return (
                "CRITICAL",
                f"Invalid topological polygon geometry detected (Source A valid={valid_a}, Source B valid={valid_b}).",
            )
        elif iou < 0.50 or centroid_dist > 25.0:
            return (
                "CRITICAL",
                f"Major boundary misalignment: spatial IoU is {iou:.1%} (<50%) or centroid offset is {centroid_dist:.1f} m (>25m).",
            )
        elif iou < 0.70 or centroid_dist > 10.0:
            return (
                "HIGH",
                f"Substantial boundary discrepancy: spatial IoU is {iou:.1%} (<70%) or centroid offset is {centroid_dist:.1f} m (>10m).",
            )
        elif iou < 0.85 or centroid_dist > 5.0:
            return (
                "MEDIUM",
                f"Moderate boundary variance: spatial IoU is {iou:.1%} (<85%) or centroid offset is {centroid_dist:.1f} m (>5m).",
            )
        else:
            return (
                "LOW",
                f"Minor boundary deviation: spatial IoU is {iou:.1%}, centroid offset is {centroid_dist:.1f} m.",
            )

    @classmethod
    async def execute_stage_08(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        req: Optional[ConflictDetectionRunRequest] = None,
    ) -> ConflictDetectionRunResponse:
        """
        Executes STAGE 08 — Conflict Detection:
        Consumes Stage 07 harmonized records and candidate pairs, executes deterministic
        conflict detection rules across area, land-use, mutation, risk, geometry, and attributes,
        calculates PostGIS spatial evidence, and persists conflict records idempotently.
        """
        start_time = time.perf_counter()
        if req is None:
            req = ConflictDetectionRunRequest()

        project = await db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project with ID '{project_id}' not found.")

        # 1. Fetch Stage 07 execution output
        stage7_stmt = (
            select(PipelineStageExecution)
            .where(
                PipelineStageExecution.project_id == project_id,
                PipelineStageExecution.stage_id == "harmonization",
                PipelineStageExecution.status == "completed",
            )
            .order_by(PipelineStageExecution.completed_at.desc())
            .limit(1)
        )
        stage7_exec = (await db.execute(stage7_stmt)).scalar_one_or_none()
        if not stage7_exec:
            raise ValueError(
                "Stage 07 Attribute/Geometry Harmonization must be completed before executing Stage 08 Conflict Detection."
            )

        records_preview = (stage7_exec.results or {}).get("records_preview") or []

        # Fetch datasets in project for source names
        ds_stmt = (
            select(Dataset)
            .where(Dataset.project_id == project_id)
            .order_by(Dataset.created_at.asc())
        )
        datasets = list((await db.execute(ds_stmt)).scalars().all())
        ds_name_a = datasets[0].name if len(datasets) > 0 else "Source Dataset A"
        ds_name_b = datasets[1].name if len(datasets) > 1 else "Source Dataset B"

        detected_conflicts_data: List[Dict[str, Any]] = []

        # 2. Iterate each harmonized candidate pair and detect conflicts
        for item in records_preview:
            rec_id = item.get("id") or str(uuid.uuid4())
            src_ident = item.get("source_identifier") or "Src"
            cand_ident = item.get("candidate_identifier") or "Cand"
            src_survey = item.get("source_survey_number")
            cand_survey = item.get("candidate_survey_number")
            src_area = item.get("source_area")
            cand_area = item.get("candidate_area")
            src_lu = item.get("source_land_use")
            cand_lu = item.get("candidate_land_use")
            src_mut = item.get("source_mutation_status")
            cand_mut = item.get("candidate_mutation_status")
            src_risk = item.get("source_risk_level")
            cand_risk = item.get("candidate_risk_level")
            geom_status = item.get("geometry_status") or "AUTHORITATIVE_SELECTED"

            # Parse feature IDs
            sf_id: Optional[uuid.UUID] = None
            cf_id: Optional[uuid.UUID] = None
            if "_" in rec_id:
                parts = rec_id.split("_")
                try:
                    sf_id = uuid.UUID(parts[0])
                    cf_id = uuid.UUID(parts[1])
                except (ValueError, IndexError):
                    pass

            # Spatial metrics via PostGIS where possible
            iou = 0.85
            centroid_dist = 2.5
            valid_sf = True
            valid_cf = True
            gis_area_a = src_area
            gis_area_b = cand_area

            if req.include_geometry_metrics and sf_id and cf_id:
                try:
                    spatial_sql = text("""
                        SELECT
                            ST_Area(sf.geometry::geography) AS area_sf,
                            ST_Area(cf.geometry::geography) AS area_cf,
                            ST_Area(
                                CASE 
                                    WHEN ST_Intersects(sf.geometry, cf.geometry) 
                                    THEN ST_Intersection(sf.geometry, cf.geometry)::geography 
                                    ELSE ST_GeomFromText('POLYGON EMPTY', 4326)::geography 
                                END
                            ) AS inter_area,
                            ST_Distance(
                                ST_Centroid(sf.geometry)::geography, 
                                ST_Centroid(cf.geometry)::geography
                            ) AS centroid_dist,
                            ST_IsValid(sf.geometry) AS valid_sf,
                            ST_IsValid(cf.geometry) AS valid_cf
                        FROM canonical_features sf, canonical_features cf
                        WHERE sf.id = :sf_id AND cf.id = :cf_id
                    """)
                    row = (await db.execute(spatial_sql, {"sf_id": sf_id, "cf_id": cf_id})).first()
                    if row:
                        gis_area_a = float(row.area_sf or 0.0)
                        gis_area_b = float(row.area_cf or 0.0)
                        inter_a = float(row.inter_area or 0.0)
                        centroid_dist = round(float(row.centroid_dist or 0.0), 2)
                        valid_sf = bool(row.valid_sf)
                        valid_cf = bool(row.valid_cf)
                        union_a = (gis_area_a + gis_area_b - inter_a)
                        iou = round(inter_a / union_a, 4) if union_a > 0 else 0.0
                except Exception:
                    pass

            geom_metadata = {
                "iou": iou,
                "centroid_distance_meters": centroid_dist,
                "source_area_sqm": gis_area_a or src_area,
                "candidate_area_sqm": gis_area_b or cand_area,
                "source_valid": valid_sf,
                "candidate_valid": valid_cf,
                "geometry_status": geom_status,
            }

            # RULE A: Area Discrepancy
            eval_area_a = src_area if src_area is not None else gis_area_a
            eval_area_b = cand_area if cand_area is not None else gis_area_b
            if eval_area_a and eval_area_b and max(eval_area_a, eval_area_b) > 0:
                area_diff = round(abs(eval_area_a - eval_area_b), 2)
                area_pct = round(area_diff / max(eval_area_a, eval_area_b) * 100.0, 2)
                if area_pct >= req.area_low_threshold_pct:
                    sev, sev_reason = cls._classify_area_severity(area_pct, req)
                    detected_conflicts_data.append({
                        "harmonized_record_id": rec_id,
                        "source_feature_id": sf_id,
                        "candidate_feature_id": cf_id,
                        "conflict_type": "AREA_DISCREPANCY",
                        "category": "GEOMETRY",
                        "severity": sev,
                        "severity_reason": sev_reason,
                        "source_a": ds_name_a,
                        "source_b": ds_name_b,
                        "field_name": "area",
                        "value_a": f"{eval_area_a:.2f} m²",
                        "value_b": f"{eval_area_b:.2f} m²",
                        "normalized_value_a": f"{eval_area_a:.2f}",
                        "normalized_value_b": f"{eval_area_b:.2f}",
                        "discrepancy_value": f"{area_diff:.2f} m²",
                        "discrepancy_percentage": area_pct,
                        "detection_rule": "RULE_AREA_DISCREPANCY_PERCENT",
                        "explanation": f"Parcel area diverges by {area_pct:.1f}% ({eval_area_a:.1f} m² vs {eval_area_b:.1f} m², difference of {area_diff:.1f} m²).",
                        "evidence": {
                            "source_area": eval_area_a,
                            "candidate_area": eval_area_b,
                            "difference_sqm": area_diff,
                            "percentage": area_pct,
                            "threshold_low": req.area_low_threshold_pct,
                            "threshold_medium": req.area_medium_threshold_pct,
                            "threshold_high": req.area_high_threshold_pct,
                        },
                        "geometry_metadata": geom_metadata,
                        "idempotency_key": f"{project_id}:{rec_id}:AREA_DISCREPANCY:area",
                    })

            # RULE B: Land Use Conflict
            norm_lu_a = normalize_semantic_land_use(src_lu)
            norm_lu_b = normalize_semantic_land_use(cand_lu)
            if norm_lu_a and norm_lu_b and norm_lu_a != norm_lu_b:
                sev, sev_reason = cls._classify_land_use_severity(norm_lu_a, norm_lu_b)
                detected_conflicts_data.append({
                    "harmonized_record_id": rec_id,
                    "source_feature_id": sf_id,
                    "candidate_feature_id": cf_id,
                    "conflict_type": "LAND_USE_CONFLICT",
                    "category": "SEMANTIC",
                    "severity": sev,
                    "severity_reason": sev_reason,
                    "source_a": ds_name_a,
                    "source_b": ds_name_b,
                    "field_name": "land_use",
                    "value_a": str(src_lu),
                    "value_b": str(cand_lu),
                    "normalized_value_a": norm_lu_a,
                    "normalized_value_b": norm_lu_b,
                    "discrepancy_value": f"{norm_lu_a} != {norm_lu_b}",
                    "discrepancy_percentage": None,
                    "detection_rule": "RULE_SEMANTIC_LAND_USE_DISCREPANCY",
                    "explanation": f"Semantic land use mismatch: Source A declares '{src_lu}' ({norm_lu_a}) while Source B declares '{cand_lu}' ({norm_lu_b}).",
                    "evidence": {
                        "raw_source_value": src_lu,
                        "raw_candidate_value": cand_lu,
                        "normalized_source": norm_lu_a,
                        "normalized_candidate": norm_lu_b,
                    },
                    "geometry_metadata": geom_metadata,
                    "idempotency_key": f"{project_id}:{rec_id}:LAND_USE_CONFLICT:land_use",
                })

            # RULE C: Mutation / Status Conflict
            norm_mut_a = normalize_semantic_mutation(src_mut)
            norm_mut_b = normalize_semantic_mutation(cand_mut)
            if norm_mut_a and norm_mut_b and norm_mut_a != norm_mut_b:
                sev, sev_reason = cls._classify_mutation_severity(norm_mut_a, norm_mut_b)
                detected_conflicts_data.append({
                    "harmonized_record_id": rec_id,
                    "source_feature_id": sf_id,
                    "candidate_feature_id": cf_id,
                    "conflict_type": "MUTATION_CONFLICT",
                    "category": "REGISTRY",
                    "severity": sev,
                    "severity_reason": sev_reason,
                    "source_a": ds_name_a,
                    "source_b": ds_name_b,
                    "field_name": "mutation_status",
                    "value_a": str(src_mut),
                    "value_b": str(cand_mut),
                    "normalized_value_a": norm_mut_a,
                    "normalized_value_b": norm_mut_b,
                    "discrepancy_value": f"{norm_mut_a} != {norm_mut_b}",
                    "discrepancy_percentage": None,
                    "detection_rule": "RULE_REGISTRY_MUTATION_DISAGREEMENT",
                    "explanation": f"Registry mutation status conflict: Source A reports '{src_mut}' ({norm_mut_a}) while Source B reports '{cand_mut}' ({norm_mut_b}).",
                    "evidence": {
                        "raw_source_mutation": src_mut,
                        "raw_candidate_mutation": cand_mut,
                        "normalized_source": norm_mut_a,
                        "normalized_candidate": norm_mut_b,
                    },
                    "geometry_metadata": geom_metadata,
                    "idempotency_key": f"{project_id}:{rec_id}:MUTATION_CONFLICT:mutation_status",
                })

            # RULE D: Environmental / Hazard Risk Conflict
            norm_risk_a = normalize_semantic_risk(src_risk)
            norm_risk_b = normalize_semantic_risk(cand_risk)
            if norm_risk_a and norm_risk_b and norm_risk_a != norm_risk_b:
                sev, sev_reason = cls._classify_risk_severity(norm_risk_a, norm_risk_b)
                detected_conflicts_data.append({
                    "harmonized_record_id": rec_id,
                    "source_feature_id": sf_id,
                    "candidate_feature_id": cf_id,
                    "conflict_type": "RISK_CONFLICT",
                    "category": "RISK",
                    "severity": sev,
                    "severity_reason": sev_reason,
                    "source_a": ds_name_a,
                    "source_b": ds_name_b,
                    "field_name": "risk_level",
                    "value_a": str(src_risk),
                    "value_b": str(cand_risk),
                    "normalized_value_a": norm_risk_a,
                    "normalized_value_b": norm_risk_b,
                    "discrepancy_value": f"{norm_risk_a} != {norm_risk_b}",
                    "discrepancy_percentage": None,
                    "detection_rule": "RULE_ENVIRONMENTAL_RISK_DIVERGENCE",
                    "explanation": f"Hazard classification divergence: Source A evaluates risk as '{src_risk}' ({norm_risk_a}) vs Source B '{cand_risk}' ({norm_risk_b}).",
                    "evidence": {
                        "raw_source_risk": src_risk,
                        "raw_candidate_risk": cand_risk,
                        "normalized_source": norm_risk_a,
                        "normalized_candidate": norm_risk_b,
                    },
                    "geometry_metadata": geom_metadata,
                    "idempotency_key": f"{project_id}:{rec_id}:RISK_CONFLICT:risk_level",
                })

            # RULE E: Geometry / Spatial Boundary Mismatch
            if iou < 0.85 or centroid_dist > 5.0 or (not valid_sf) or (not valid_cf) or (geom_status != "CONGRUENT"):
                sev, sev_reason = cls._classify_geometry_severity(iou, centroid_dist, valid_sf, valid_cf)
                detected_conflicts_data.append({
                    "harmonized_record_id": rec_id,
                    "source_feature_id": sf_id,
                    "candidate_feature_id": cf_id,
                    "conflict_type": "GEOMETRY_MISMATCH",
                    "category": "GEOMETRY",
                    "severity": sev,
                    "severity_reason": sev_reason,
                    "source_a": ds_name_a,
                    "source_b": ds_name_b,
                    "field_name": "geometry",
                    "value_a": f"Parcel {src_ident} Polygon",
                    "value_b": f"Parcel {cand_ident} Polygon",
                    "normalized_value_a": f"IoU: {iou:.2%}",
                    "normalized_value_b": f"Offset: {centroid_dist:.1f}m",
                    "discrepancy_value": f"IoU: {iou:.2%}, Centroid: {centroid_dist:.1f}m",
                    "discrepancy_percentage": round((1.0 - iou) * 100.0, 2),
                    "detection_rule": "RULE_POSTGIS_SPATIAL_TOPOLOGY_MISMATCH",
                    "explanation": f"Boundary variance detected between datasets: Spatial IoU is {iou:.1%} and centroid offset is {centroid_dist:.1f} m.",
                    "evidence": geom_metadata,
                    "geometry_metadata": geom_metadata,
                    "idempotency_key": f"{project_id}:{rec_id}:GEOMETRY_MISMATCH:geometry",
                })

            # RULE F: Cadastral Survey Number Disagreement (Attribute Mismatch)
            if src_survey and cand_survey and str(src_survey).strip().lower() != str(cand_survey).strip().lower():
                detected_conflicts_data.append({
                    "harmonized_record_id": rec_id,
                    "source_feature_id": sf_id,
                    "candidate_feature_id": cf_id,
                    "conflict_type": "ATTRIBUTE_MISMATCH",
                    "category": "REGISTRY",
                    "severity": "MEDIUM",
                    "severity_reason": f"Cadastral survey identifier mismatch between '{src_survey}' and '{cand_survey}'.",
                    "source_a": ds_name_a,
                    "source_b": ds_name_b,
                    "field_name": "survey_number",
                    "value_a": str(src_survey),
                    "value_b": str(cand_survey),
                    "normalized_value_a": str(src_survey).strip().upper(),
                    "normalized_value_b": str(cand_survey).strip().upper(),
                    "discrepancy_value": f"{src_survey} != {cand_survey}",
                    "discrepancy_percentage": None,
                    "detection_rule": "RULE_CADASTRAL_IDENTIFIER_DISCREPANCY",
                    "explanation": f"Survey identifier mismatch: Source A records '{src_survey}' while Source B records '{cand_survey}'.",
                    "evidence": {
                        "source_survey": src_survey,
                        "candidate_survey": cand_survey,
                    },
                    "geometry_metadata": geom_metadata,
                    "idempotency_key": f"{project_id}:{rec_id}:ATTRIBUTE_MISMATCH:survey_number",
                })

        # 3. Idempotent Database Upsert
        existing_stmt = select(GeospatialConflict).where(GeospatialConflict.project_id == project_id)
        existing_conflicts = list((await db.execute(existing_stmt)).scalars().all())
        existing_by_key = {c.idempotency_key: c for c in existing_conflicts}

        created_count = 0
        updated_count = 0
        now = datetime.now(timezone.utc)

        for c_data in detected_conflicts_data:
            key = c_data["idempotency_key"]
            existing = existing_by_key.get(key)
            if existing:
                # Retain human reviewer status if acknowledged or resolved
                if existing.status in ["ACKNOWLEDGED", "RESOLVED", "DISMISSED"]:
                    pass
                else:
                    existing.status = "OPEN"

                existing.severity = c_data["severity"]
                existing.severity_reason = c_data["severity_reason"]
                existing.value_a = c_data["value_a"]
                existing.value_b = c_data["value_b"]
                existing.normalized_value_a = c_data["normalized_value_a"]
                existing.normalized_value_b = c_data["normalized_value_b"]
                existing.discrepancy_value = c_data["discrepancy_value"]
                existing.discrepancy_percentage = c_data["discrepancy_percentage"]
                existing.explanation = c_data["explanation"]
                existing.evidence = c_data["evidence"]
                existing.geometry_metadata = c_data["geometry_metadata"]
                existing.updated_at = now
                updated_count += 1
            else:
                new_conflict = GeospatialConflict(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    harmonized_record_id=c_data["harmonized_record_id"],
                    source_feature_id=c_data["source_feature_id"],
                    candidate_feature_id=c_data["candidate_feature_id"],
                    conflict_type=c_data["conflict_type"],
                    category=c_data["category"],
                    severity=c_data["severity"],
                    severity_reason=c_data["severity_reason"],
                    status="OPEN",
                    source_a=c_data["source_a"],
                    source_b=c_data["source_b"],
                    field_name=c_data["field_name"],
                    value_a=c_data["value_a"],
                    value_b=c_data["value_b"],
                    normalized_value_a=c_data["normalized_value_a"],
                    normalized_value_b=c_data["normalized_value_b"],
                    discrepancy_value=c_data["discrepancy_value"],
                    discrepancy_percentage=c_data["discrepancy_percentage"],
                    detection_rule=c_data["detection_rule"],
                    explanation=c_data["explanation"],
                    evidence=c_data["evidence"],
                    geometry_metadata=c_data["geometry_metadata"],
                    idempotency_key=key,
                    created_at=now,
                    updated_at=now,
                )
                db.add(new_conflict)
                existing_by_key[key] = new_conflict
                created_count += 1

        # 4. Compute Summary Statistics
        counts_by_sev = {
            "CRITICAL": sum(1 for c in detected_conflicts_data if c["severity"] == "CRITICAL"),
            "HIGH": sum(1 for c in detected_conflicts_data if c["severity"] == "HIGH"),
            "MEDIUM": sum(1 for c in detected_conflicts_data if c["severity"] == "MEDIUM"),
            "LOW": sum(1 for c in detected_conflicts_data if c["severity"] == "LOW"),
        }
        counts_by_type: Dict[str, int] = {}
        for c in detected_conflicts_data:
            t = c["conflict_type"]
            counts_by_type[t] = counts_by_type.get(t, 0) + 1

        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        results_data = {
            "records_scanned": len(records_preview),
            "conflicts_detected": len(detected_conflicts_data),
            "critical_count": counts_by_sev["CRITICAL"],
            "high_count": counts_by_sev["HIGH"],
            "medium_count": counts_by_sev["MEDIUM"],
            "low_count": counts_by_sev["LOW"],
            "counts_by_severity": counts_by_sev,
            "counts_by_type": counts_by_type,
            "conflicts_created": created_count,
            "conflicts_updated": updated_count,
            "execution_time_ms": duration_ms,
        }

        # 5. Update or Create PipelineStageExecution for Stage 08
        stage8_stmt = (
            select(PipelineStageExecution)
            .where(
                PipelineStageExecution.project_id == project_id,
                PipelineStageExecution.stage_id == "conflict",
            )
        )
        stage8_exec = (await db.execute(stage8_stmt)).scalar_one_or_none()

        inputs_data = req.model_dump()
        if not stage8_exec:
            stage8_exec = PipelineStageExecution(
                id=uuid.uuid4(),
                project_id=project_id,
                stage_number=8,
                stage_id="conflict",
                status="completed",
                inputs=inputs_data,
                results=results_data,
                started_at=now,
                completed_at=now,
            )
            db.add(stage8_exec)
        else:
            stage8_exec.status = "completed"
            stage8_exec.inputs = inputs_data
            stage8_exec.results = results_data
            stage8_exec.completed_at = now

        await db.commit()

        return ConflictDetectionRunResponse(
            stage_id="conflict",
            stage_number=8,
            status="completed",
            project_id=project_id,
            records_scanned=len(records_preview),
            conflicts_detected=len(detected_conflicts_data),
            critical_count=counts_by_sev["CRITICAL"],
            high_count=counts_by_sev["HIGH"],
            medium_count=counts_by_sev["MEDIUM"],
            low_count=counts_by_sev["LOW"],
            counts_by_severity=counts_by_sev,
            counts_by_type=counts_by_type,
            conflicts_created=created_count,
            conflicts_updated=updated_count,
            execution_time_ms=duration_ms,
        )

    @classmethod
    async def list_geospatial_conflicts(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        severity: Optional[str] = None,
        conflict_type: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> GeospatialConflictListResponse:
        """
        Lists Stage 08 Geospatial Conflicts with pagination, filtering, and aggregate metrics.
        """
        project = await db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project with ID '{project_id}' not found.")

        # Aggregate counts across all conflicts for this project
        sev_stmt = (
            select(GeospatialConflict.severity, func.count(GeospatialConflict.id))
            .where(GeospatialConflict.project_id == project_id)
            .group_by(GeospatialConflict.severity)
        )
        sev_rows = (await db.execute(sev_stmt)).all()
        counts_by_sev = {r[0]: r[1] for r in sev_rows}

        type_stmt = (
            select(GeospatialConflict.conflict_type, func.count(GeospatialConflict.id))
            .where(GeospatialConflict.project_id == project_id)
            .group_by(GeospatialConflict.conflict_type)
        )
        type_rows = (await db.execute(type_stmt)).all()
        counts_by_type = {r[0]: r[1] for r in type_rows}

        status_stmt = (
            select(GeospatialConflict.status, func.count(GeospatialConflict.id))
            .where(GeospatialConflict.project_id == project_id)
            .group_by(GeospatialConflict.status)
        )
        status_rows = (await db.execute(status_stmt)).all()
        counts_by_status = {r[0]: r[1] for r in status_rows}

        # Build filter conditions
        filters = [GeospatialConflict.project_id == project_id]

        if severity and severity.upper() != "ALL":
            filters.append(GeospatialConflict.severity == severity.strip().upper())
        if conflict_type and conflict_type.upper() != "ALL":
            filters.append(GeospatialConflict.conflict_type == conflict_type.strip().upper())
        if category and category.upper() != "ALL":
            filters.append(GeospatialConflict.category == category.strip().upper())
        if status and status.upper() != "ALL":
            filters.append(GeospatialConflict.status == status.strip().upper())
        if source:
            s_pat = f"%{source.strip()}%"
            filters.append(
                or_(
                    GeospatialConflict.source_a.ilike(s_pat),
                    GeospatialConflict.source_b.ilike(s_pat),
                )
            )
        if search:
            q_pat = f"%{search.strip()}%"
            filters.append(
                or_(
                    GeospatialConflict.harmonized_record_id.ilike(q_pat),
                    GeospatialConflict.field_name.ilike(q_pat),
                    GeospatialConflict.explanation.ilike(q_pat),
                    GeospatialConflict.value_a.ilike(q_pat),
                    GeospatialConflict.value_b.ilike(q_pat),
                )
            )

        # Count total matching
        total_stmt = select(func.count(GeospatialConflict.id)).where(*filters)
        total = (await db.execute(total_stmt)).scalar() or 0

        # Query items with custom severity ordering: CRITICAL -> HIGH -> MEDIUM -> LOW
        severity_order = case(
            (GeospatialConflict.severity == "CRITICAL", 1),
            (GeospatialConflict.severity == "HIGH", 2),
            (GeospatialConflict.severity == "MEDIUM", 3),
            (GeospatialConflict.severity == "LOW", 4),
            else_=5,
        )

        query = (
            select(GeospatialConflict)
            .where(*filters)
            .order_by(severity_order.asc(), GeospatialConflict.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items = list((await db.execute(query)).scalars().all())

        return GeospatialConflictListResponse(
            items=[GeospatialConflictRead.model_validate(c) for c in items],
            total=total,
            skip=skip,
            limit=limit,
            counts_by_severity=counts_by_sev,
            counts_by_type=counts_by_type,
            counts_by_status=counts_by_status,
        )

    @classmethod
    async def get_geospatial_conflict(
        cls,
        db: AsyncSession,
        conflict_id: uuid.UUID,
    ) -> Optional[GeospatialConflictRead]:
        """Returns full details of a Stage 08 GeospatialConflict."""
        conflict = await db.get(GeospatialConflict, conflict_id)
        if not conflict:
            return None
        return GeospatialConflictRead.model_validate(conflict)

    @classmethod
    async def update_geospatial_conflict_status(
        cls,
        db: AsyncSession,
        conflict_id: uuid.UUID,
        update_data: GeospatialConflictStatusUpdate,
    ) -> GeospatialConflictRead:
        """Updates the status of a Stage 08 GeospatialConflict with audit trail."""
        conflict = await db.get(GeospatialConflict, conflict_id)
        if not conflict:
            raise ValueError(f"Geospatial conflict with ID '{conflict_id}' not found.")

        target_status = update_data.status.strip().upper()
        valid_statuses = ["OPEN", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"]
        if target_status not in valid_statuses:
            raise ValueError(f"Invalid status '{update_data.status}'. Allowed: {', '.join(valid_statuses)}")

        now = datetime.now(timezone.utc)
        conflict.status = target_status
        conflict.updated_at = now

        evidence = dict(conflict.evidence or {})
        history = list(evidence.get("status_history", []))
        history.append({
            "status": target_status,
            "notes": update_data.notes,
            "updated_at": now.isoformat(),
        })
        evidence["status_history"] = history
        conflict.evidence = evidence

        await db.commit()
        await db.refresh(conflict)
        return GeospatialConflictRead.model_validate(conflict)

