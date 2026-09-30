import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple, Set
from collections import defaultdict
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.project import Project
from app.models.dataset import Dataset, DatasetVersion
from app.models.feature import CanonicalFeature
from app.models.unified import UnifiedLandRecord, UnifiedLandRecordSource
from app.models.conflict import AttributeConflict, ConflictResolution
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
