import time
import uuid
import math
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Set, Tuple
from collections import defaultdict, deque

from sqlalchemy import select, func, desc, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.validation import make_valid
from geoalchemy2.shape import from_shape
from fastapi import HTTPException, status

from app.models.project import Project
from app.models.dataset import Dataset, DatasetVersion
from app.models.feature import CanonicalFeature
from app.models.matching import FeatureMatch
from app.models.unified import UnifiedLandRecord, UnifiedLandRecordSource
from app.models.pipeline import PipelineStageExecution
from app.models.provenance import ProvenanceEvent
from app.models.adjudication import HumanReviewDecision
from app.models.conflict import GeospatialConflict
from app.models.validation import ValidationResult
from app.services.dataset import extract_shapely_geom
from app.services.matching.service import extract_feature_display_id
from app.schemas.unified import (
    UnifiedRecordSourceResponse,
    UnifiedRecordListItem,
    UnifiedRecordListResponse,
    UnifiedRecordDetailResponse,
    UnifiedRecordBuildResponse,
    UnifiedRecordStatisticsResponse,
    Stage12ExecutionResponse,
    Stage12StatusResponse,
)


def detect_source_role(dataset_name: Optional[str], properties: Optional[Dict[str, Any]]) -> str:
    """
    Deterministically determines the semantic source role (CADASTRAL, DRONE, MUNICIPAL, OTHER)
    from dataset naming conventions and canonical feature property schemas.
    """
    d_name = (dataset_name or "").lower()
    props = properties or {}
    p_keys = {k.lower() for k in props.keys()}

    if "cadastr" in d_name or "parcel" in d_name or "parcel_id" in p_keys or "cadastral" in p_keys:
        return "CADASTRAL"
    if "drone" in d_name or "structure" in d_name or "structure_id" in p_keys or "building" in d_name:
        return "DRONE"
    if "muni" in d_name or "mun_" in d_name or "tax" in d_name or "tax_id" in p_keys or "assessment" in p_keys:
        return "MUNICIPAL"
    return "OTHER"


def compute_metric_area(geom: BaseGeometry, explicit_area: Optional[float] = None) -> Optional[float]:
    """
    Computes an estimated metric surface area in square meters (m²) from an explicit source attribute
    or geodesic approximation of a Shapely geometry in EPSG:4326.
    """
    if explicit_area is not None and explicit_area > 0:
        return round(float(explicit_area), 2)

    if not geom or geom.is_empty:
        return None

    geom_type = geom.geom_type.lower()
    if "polygon" not in geom_type:
        return None

    # Centroid latitude for longitude cosine scaling
    lat = geom.centroid.y
    lat_rad = math.radians(lat)
    # 1 deg latitude ≈ 110,540 m; 1 deg longitude ≈ 111,320 m * cos(lat)
    scale_y = 110540.0
    scale_x = 111320.0 * math.cos(lat_rad)
    metric_area = geom.area * scale_x * scale_y
    return round(metric_area, 2)


class UnifiedRecordService:
    """
    Service responsible for building, updating, and querying Unified Land Records
    from human-accepted reconciliation matches.
    """

    ROLE_PRIORITY: Dict[str, int] = {
        "CADASTRAL": 1,
        "DRONE": 2,
        "MUNICIPAL": 3,
        "OTHER": 4,
    }

    @classmethod
    async def build_records_from_accepted_matches(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> UnifiedRecordBuildResponse:
        """
        Idempotent build operation:
        1. Queries all ACCEPTED matches for project_id.
        2. Groups accepted features into connected components.
        3. For each component, creates or updates a UnifiedLandRecord.
        4. Selects canonical geometry using source priority rule (Cadastral > Drone > Municipal > Other).
        5. Computes canonical area and extracts canonical attributes.
        6. Detects attribute conflicts and assigns status (ACTIVE, INCOMPLETE, CONFLICT).
        7. Guarantees no duplicates on repeated builds.
        """
        # Validate project exists
        project = await db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project with ID '{project_id}' not found.")

        # 1. Fetch all human-accepted matches for this project
        stmt = (
            select(FeatureMatch)
            .where(
                FeatureMatch.project_id == project_id,
                FeatureMatch.review_status == "ACCEPTED",
                FeatureMatch.candidate_feature_id.isnot(None),
            )
            .order_by(FeatureMatch.created_at.asc())
        )
        accepted_matches = (await db.execute(stmt)).scalars().all()

        if not accepted_matches:
            # Query existing records counts if any
            stats = await cls.get_statistics(db, project_id)
            return UnifiedRecordBuildResponse(
                project_id=project_id,
                records_created=0,
                records_updated=0,
                records_unchanged=stats.total_records,
                accepted_relationships_processed=0,
                conflict_records=stats.conflict,
                incomplete_records=stats.incomplete,
                active_records=stats.active,
                total_records=stats.total_records,
            )

        # 2. Build adjacency graph of connected canonical features
        adj: Dict[uuid.UUID, Set[uuid.UUID]] = defaultdict(set)
        match_lookup: Dict[frozenset, uuid.UUID] = {}

        for fm in accepted_matches:
            src_id = fm.source_feature_id
            cand_id = fm.candidate_feature_id
            if cand_id:
                adj[src_id].add(cand_id)
                adj[cand_id].add(src_id)
                pair_key = frozenset([src_id, cand_id])
                if pair_key not in match_lookup:
                    match_lookup[pair_key] = fm.id

        # 3. Find connected components (disjoint sets of feature IDs)
        visited: Set[uuid.UUID] = set()
        components: List[Set[uuid.UUID]] = []

        all_nodes = sorted(list(adj.keys()))
        for node in all_nodes:
            if node not in visited:
                comp: Set[uuid.UUID] = set()
                queue = deque([node])
                visited.add(node)
                while queue:
                    curr = queue.popleft()
                    comp.add(curr)
                    for neighbor in adj[curr]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                components.append(comp)

        # 4. Fetch all relevant CanonicalFeatures with datasets
        all_comp_feature_ids = set.union(*components) if components else set()
        feat_stmt = (
            select(CanonicalFeature)
            .where(CanonicalFeature.id.in_(all_comp_feature_ids))
            .options(
                joinedload(CanonicalFeature.dataset_version).joinedload(DatasetVersion.dataset),
                joinedload(CanonicalFeature.source_feature),
            )
        )
        features_map = {cf.id: cf for cf in (await db.execute(feat_stmt)).scalars().all()}

        # 5. Determine existing sequence number for record_identifier
        seq_stmt = (
            select(func.count(UnifiedLandRecord.id))
            .where(UnifiedLandRecord.project_id == project_id)
        )
        existing_count = (await db.execute(seq_stmt)).scalar() or 0
        next_seq = existing_count + 1

        records_created = 0
        records_updated = 0
        records_unchanged = 0

        # Process each connected component
        for comp_features in components:
            # Check if any feature in this component is already attached to an existing UnifiedLandRecord
            sources_stmt = (
                select(UnifiedLandRecordSource)
                .where(UnifiedLandRecordSource.feature_id.in_(comp_features))
                .options(joinedload(UnifiedLandRecordSource.unified_record))
            )
            existing_sources = (await db.execute(sources_stmt)).scalars().all()
            existing_record_ids = {
                s.unified_land_record_id for s in existing_sources if s.unified_record and s.unified_record.project_id == project_id
            }

            target_record: Optional[UnifiedLandRecord] = None
            is_new = False

            if not existing_record_ids:
                # Create a new UnifiedLandRecord
                record_id_str = f"ULR-{next_seq:06d}"
                next_seq += 1

                target_record = UnifiedLandRecord(
                    project_id=project_id,
                    record_identifier=record_id_str,
                    status="ACTIVE",
                    canonical_attributes={},
                )
                db.add(target_record)
                await db.flush()  # Generate UUID
                is_new = True
                records_created += 1
            elif len(existing_record_ids) == 1:
                # Exactly one existing record matches
                rec_id = list(existing_record_ids)[0]
                target_record = await db.get(UnifiedLandRecord, rec_id)
            else:
                # Multiple existing records touched (connected by new accepted match) -> Merge into the first!
                rec_ids_sorted = sorted(list(existing_record_ids))
                primary_id = rec_ids_sorted[0]
                redundant_ids = rec_ids_sorted[1:]

                target_record = await db.get(UnifiedLandRecord, primary_id)
                # Re-assign redundant sources to primary_id
                for s in existing_sources:
                    if s.unified_land_record_id in redundant_ids:
                        s.unified_land_record_id = primary_id

                # Delete redundant records
                for r_id in redundant_ids:
                    del_stmt = delete(UnifiedLandRecord).where(UnifiedLandRecord.id == r_id)
                    await db.execute(del_stmt)

                records_updated += 1

            if not target_record:
                continue

            # Ensure all features in this component have UnifiedLandRecordSource entries
            current_feature_ids = {
                s.feature_id for s in existing_sources if s.unified_land_record_id == target_record.id
            }
            new_sources_added = False

            for fid in comp_features:
                if fid not in current_feature_ids:
                    feat_obj = features_map.get(fid)
                    ds_name = (
                        feat_obj.dataset_version.dataset.name
                        if feat_obj and feat_obj.dataset_version and feat_obj.dataset_version.dataset
                        else None
                    )
                    role = detect_source_role(ds_name, feat_obj.canonical_properties if feat_obj else None)

                    # Find contributing match reference if any
                    m_id = None
                    for other_fid in comp_features:
                        if other_fid != fid:
                            pair = frozenset([fid, other_fid])
                            if pair in match_lookup:
                                m_id = match_lookup[pair]
                                break

                    new_source = UnifiedLandRecordSource(
                        unified_land_record_id=target_record.id,
                        feature_id=fid,
                        feature_match_id=m_id,
                        source_role=role,
                    )
                    db.add(new_source)
                    current_feature_ids.add(fid)
                    new_sources_added = True

            await db.flush()

            # 6. Select Canonical Geometry based on deterministic source priority
            comp_feature_objs = [features_map[fid] for fid in comp_features if fid in features_map]
            selected_feature, selected_role = cls._select_canonical_geometry(comp_feature_objs)

            # 7. Compute Canonical Area
            explicit_area_val = None
            if selected_feature and selected_feature.canonical_properties:
                for a_key in ["area", "sq_m", "area_sqm", "area_m2"]:
                    if a_key in selected_feature.canonical_properties:
                        try:
                            explicit_area_val = float(selected_feature.canonical_properties[a_key])
                            break
                        except (ValueError, TypeError):
                            pass

            shapely_geom = extract_shapely_geom(selected_feature.geometry) if selected_feature else None
            computed_area = compute_metric_area(shapely_geom, explicit_area_val)

            # 8. Extract Canonical Attributes and Detect Conflicts
            canonical_attrs, status = cls._extract_attributes_and_detect_conflicts(
                comp_feature_objs,
                target_record.record_identifier,
                computed_area,
                selected_feature.geometry_type if selected_feature else "Unknown",
            )

            # Record initial state for idempotency tracking
            initial_status = target_record.status
            initial_geom_src = target_record.geometry_source_feature_id
            initial_area = target_record.area
            initial_attrs = dict(target_record.canonical_attributes or {})

            # Preserve existing human resolutions on rebuild
            if not is_new and target_record.canonical_attributes:
                for k, v in target_record.canonical_attributes.items():
                    if k.endswith("_resolution"):
                        base_attr = k[:-11]
                        if base_attr in target_record.canonical_attributes:
                            canonical_attrs[base_attr] = target_record.canonical_attributes[base_attr]
                        canonical_attrs[k] = v

            target_record.geometry_source_feature_id = selected_feature.id if selected_feature else None
            target_record.geometry_source_role = selected_role
            target_record.canonical_geometry = selected_feature.geometry if selected_feature else None
            target_record.area = computed_area
            if is_new or not target_record.status:
                target_record.status = status
            target_record.canonical_attributes = canonical_attrs

            # Milestone 7: First-class Conflict Detection & Synchronization
            from app.services.conflict.service import ConflictDetectionService
            comp_source_roles = {
                cf.id: detect_source_role(
                    cf.dataset_version.dataset.name if cf.dataset_version and cf.dataset_version.dataset else None,
                    cf.canonical_properties,
                )
                for cf in comp_feature_objs
            }
            await ConflictDetectionService.detect_and_sync_conflicts_for_record(
                db,
                target_record,
                features=comp_feature_objs,
                source_roles=comp_source_roles,
            )

            # Check if values actually changed after conflict detection & sync
            geom_changed = (
                target_record.geometry_source_feature_id != initial_geom_src
            )
            status_changed = target_record.status != initial_status
            area_changed = target_record.area != initial_area
            attrs_changed = target_record.canonical_attributes != initial_attrs

            if not is_new:
                if new_sources_added or geom_changed or status_changed or area_changed or attrs_changed:
                    records_updated += 1
                else:
                    records_unchanged += 1

        await db.commit()

        # Query updated statistics
        stats = await cls.get_statistics(db, project_id)

        return UnifiedRecordBuildResponse(
            project_id=project_id,
            records_created=records_created,
            records_updated=records_updated,
            records_unchanged=records_unchanged,
            accepted_relationships_processed=len(accepted_matches),
            conflict_records=stats.conflict,
            incomplete_records=stats.incomplete,
            active_records=stats.active,
            total_records=stats.total_records,
        )

    @classmethod
    def _select_canonical_geometry(
        cls,
        features: List[CanonicalFeature],
    ) -> Tuple[Optional[CanonicalFeature], Optional[str]]:
        """
        Selects canonical geometry using deterministic source priority:
        1. CADASTRAL
        2. DRONE
        3. MUNICIPAL
        4. OTHER
        """
        candidates: List[Tuple[int, CanonicalFeature, str]] = []

        for cf in features:
            if not cf.geometry:
                continue
            ds_name = (
                cf.dataset_version.dataset.name
                if cf.dataset_version and cf.dataset_version.dataset
                else ""
            )
            role = detect_source_role(ds_name, cf.canonical_properties)
            priority = cls.ROLE_PRIORITY.get(role, 99)
            candidates.append((priority, cf, role))

        if not candidates:
            return None, None

        # Lowest priority number = highest rank
        candidates.sort(key=lambda x: (x[0], str(x[1].id)))
        _, best_cf, best_role = candidates[0]
        return best_cf, best_role

    @classmethod
    def _extract_attributes_and_detect_conflicts(
        cls,
        features: List[CanonicalFeature],
        record_identifier: str,
        canonical_area: Optional[float],
        geom_type: str,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Extracts canonical attributes and performs deterministic conflict detection.
        Assigns record status:
        - CONFLICT: Material disagreement in land use, zoning, or area (>30%)
        - INCOMPLETE: Single source feature or missing geometry
        - ACTIVE: Harmonized with no material conflicts
        """
        source_identifiers: Dict[str, List[str]] = defaultdict(list)
        dataset_names: Set[str] = set()
        land_use_by_source: Dict[str, str] = {}
        area_by_source: Dict[str, float] = {}
        address_by_source: Dict[str, str] = {}
        conflicts: List[Dict[str, Any]] = []

        for cf in features:
            ds_name = (
                cf.dataset_version.dataset.name
                if cf.dataset_version and cf.dataset_version.dataset
                else "Dataset"
            )
            dataset_names.add(ds_name)
            role = detect_source_role(ds_name, cf.canonical_properties)
            display_id = extract_feature_display_id(cf)
            if display_id:
                source_identifiers[role].append(display_id)

            props = cf.canonical_properties or {}
            # Normalize keys to lowercase
            lower_props = {k.lower(): v for k, v in props.items()}

            # Land Use / Zoning
            for lu_key in ["land_use", "landuse", "type", "zoning", "category", "usage"]:
                if lu_key in lower_props and lower_props[lu_key]:
                    val = str(lower_props[lu_key]).strip()
                    if val and val.lower() not in ["null", "none", "unknown"]:
                        land_use_by_source[role] = val
                        break

            # Area
            for a_key in ["area", "sq_m", "area_sqm", "area_m2"]:
                if a_key in lower_props and lower_props[a_key]:
                    try:
                        area_by_source[role] = float(lower_props[a_key])
                        break
                    except (ValueError, TypeError):
                        pass

            # Address / Locality
            for addr_key in ["address", "locality", "street", "location", "place"]:
                if addr_key in lower_props and lower_props[addr_key]:
                    val = str(lower_props[addr_key]).strip()
                    if val and val.lower() not in ["null", "none", "unknown"]:
                        address_by_source[role] = val
                        break

        # Conflict 1: Land Use Disagreement
        unique_land_uses = {v.lower(): v for v in land_use_by_source.values()}
        primary_land_use = None
        if len(unique_land_uses) > 1:
            conflicts.append({
                "field": "land_use",
                "type": "disagreement",
                "message": "Sources provide conflicting land use classifications.",
                "values": land_use_by_source,
            })
            # Pick from priority source role for display
            for r in ["CADASTRAL", "MUNICIPAL", "DRONE", "OTHER"]:
                if r in land_use_by_source:
                    primary_land_use = land_use_by_source[r]
                    break
        elif len(unique_land_uses) == 1:
            primary_land_use = list(unique_land_uses.values())[0]

        # Conflict 2: Area Discrepancy (>30% difference between sources)
        if len(area_by_source) >= 2:
            areas = list(area_by_source.values())
            min_a = min(areas)
            max_a = max(areas)
            if max_a > 0:
                diff_ratio = (max_a - min_a) / max_a
                if diff_ratio > 0.30:
                    conflicts.append({
                        "field": "area",
                        "type": "discrepancy",
                        "discrepancy_pct": round(diff_ratio * 100, 1),
                        "message": f"Area discrepancy exceeds 30% threshold ({round(diff_ratio * 100, 1)}% difference).",
                        "values": area_by_source,
                    })

        # Primary Address
        primary_address = None
        for r in ["CADASTRAL", "MUNICIPAL", "DRONE", "OTHER"]:
            if r in address_by_source:
                primary_address = address_by_source[r]
                break

        # Status Assignment Rule
        if conflicts:
            status = "CONFLICT"
        elif len(features) < 2 or canonical_area is None:
            status = "INCOMPLETE"
        else:
            status = "ACTIVE"

        canonical_attributes = {
            "record_identifier": record_identifier,
            "land_use": primary_land_use,
            "area_sqm": canonical_area,
            "address": primary_address,
            "source_count": len(features),
            "dataset_names": sorted(list(dataset_names)),
            "geometry_type": geom_type,
            "source_feature_identifiers": dict(source_identifiers),
            "land_use_by_source": land_use_by_source,
            "area_by_source": area_by_source,
            "address_by_source": address_by_source,
            "conflicts": conflicts,
        }

        return canonical_attributes, status

    @classmethod
    async def get_records(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        status: Optional[str] = None,
        resolution_status: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> UnifiedRecordListResponse:
        """
        Lists paginated unified land records for a project with optional filters.
        """
        filters = [UnifiedLandRecord.project_id == project_id]
        if status:
            filters.append(UnifiedLandRecord.status == status.strip().upper())
        if resolution_status:
            filters.append(UnifiedLandRecord.resolution_status == resolution_status.strip().upper())
        if search:
            s_term = f"%{search.strip()}%"
            filters.append(
                or_(
                    UnifiedLandRecord.record_identifier.ilike(s_term),
                    UnifiedLandRecord.harmonized_record_id.ilike(s_term),
                    UnifiedLandRecord.source_a_reference.ilike(s_term),
                    UnifiedLandRecord.source_b_reference.ilike(s_term),
                    UnifiedLandRecord.land_use.ilike(s_term),
                )
            )

        # Count total
        count_stmt = select(func.count(UnifiedLandRecord.id)).where(*filters)
        total = (await db.execute(count_stmt)).scalar() or 0

        # Query records with eager loaded sources
        stmt = (
            select(UnifiedLandRecord)
            .where(*filters)
            .options(selectinload(UnifiedLandRecord.sources))
            .order_by(UnifiedLandRecord.record_identifier.asc())
            .offset(skip)
            .limit(limit)
        )
        records = (await db.execute(stmt)).scalars().all()

        items = [
            UnifiedRecordListItem(
                id=r.id,
                project_id=r.project_id,
                record_identifier=r.record_identifier,
                status=r.status,
                source_count=len(r.sources) if r.sources else 0,
                geometry_source_role=r.geometry_source_role,
                area=r.area,
                canonical_attributes=r.canonical_attributes or {},
                harmonized_record_id=r.harmonized_record_id,
                source_a_reference=r.source_a_reference,
                source_b_reference=r.source_b_reference,
                geometry_source=r.geometry_source,
                land_use=r.land_use,
                mutation_status=r.mutation_status,
                risk_level=r.risk_level,
                confidence_score=r.confidence_score,
                validation_status=r.validation_status,
                human_review_decision=r.human_review_decision,
                resolution_status=r.resolution_status,
                metadata_trail=r.metadata_trail or {},
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in records
        ]

        return UnifiedRecordListResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )

    @classmethod
    async def get_record_detail(
        cls,
        db: AsyncSession,
        record_id: uuid.UUID,
    ) -> Optional[UnifiedRecordDetailResponse]:
        """
        Fetches detailed information for a single UnifiedLandRecord, including
        canonical geometry as GeoJSON, attributes, and contributing source features.
        """
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
                joinedload(UnifiedLandRecord.geometry_source_feature),
            )
        )
        record = (await db.execute(stmt)).scalar_one_or_none()
        if not record:
            return None

        # Convert canonical geometry to GeoJSON
        geom_json = None
        if record.canonical_geometry:
            shapely_geom = extract_shapely_geom(record.canonical_geometry)
            if shapely_geom:
                geom_json = mapping(shapely_geom)

        # Build sources list
        sources_list: List[UnifiedRecordSourceResponse] = []
        for s in record.sources:
            feat = s.feature
            src_geom_json = None
            if feat and feat.geometry:
                s_geom = extract_shapely_geom(feat.geometry)
                if s_geom:
                    src_geom_json = mapping(s_geom)

            ds = (
                feat.dataset_version.dataset
                if feat and feat.dataset_version and feat.dataset_version.dataset
                else None
            )

            sources_list.append(
                UnifiedRecordSourceResponse(
                    id=s.id,
                    feature_id=s.feature_id,
                    feature_match_id=s.feature_match_id,
                    source_role=s.source_role,
                    dataset_id=ds.id if ds else None,
                    dataset_name=ds.name if ds else "Unknown Dataset",
                    source_identifier=extract_feature_display_id(feat) or str(s.feature_id)[:8],
                    geometry_type=feat.geometry_type if feat else "Unknown",
                    properties=feat.canonical_properties if feat else {},
                    geometry=src_geom_json,
                    created_at=s.created_at,
                )
            )

        return UnifiedRecordDetailResponse(
            id=record.id,
            project_id=record.project_id,
            record_identifier=record.record_identifier,
            status=record.status,
            canonical_geometry=geom_json,
            geometry_source_feature_id=record.geometry_source_feature_id,
            geometry_source_role=record.geometry_source_role,
            area=record.area,
            canonical_attributes=record.canonical_attributes or {},
            harmonized_record_id=record.harmonized_record_id,
            source_a_reference=record.source_a_reference,
            source_b_reference=record.source_b_reference,
            geometry_source=record.geometry_source,
            land_use=record.land_use,
            mutation_status=record.mutation_status,
            risk_level=record.risk_level,
            confidence_score=record.confidence_score,
            validation_status=record.validation_status,
            human_review_decision=record.human_review_decision,
            resolution_status=record.resolution_status,
            metadata_trail=record.metadata_trail or {},
            sources=sources_list,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @classmethod
    async def synthesize_stage_12(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> Stage12ExecutionResponse:
        """
        Executes PIPELINE STAGE 12: Unified Record.
        Synthesizes the authoritative master land records by combining:
        - Stage 07 harmonized records
        - Stage 08 geospatial conflicts
        - Stage 09 validation results
        - Stage 10 multi-component confidence scores
        - Stage 11 human review decisions (strict human review precedence)

        Enforces:
        - Prerequisite: Stage 11 must be completed and finalized.
        - Authoritative geometry validation via Shapely / PostGIS with EPSG:4326.
        - Deterministic resolution status: UNIFIED or REJECTED.
        - Strict idempotency: Upserts existing records, guaranteeing 0 duplicates.
        - Provenance readiness: Detailed metadata_trail with lineage trace.
        """
        start_time = time.perf_counter()
        now = datetime.now(timezone.utc)

        # 1. Validate project existence
        project = await db.get(Project, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found.",
            )

        # 2. Enforce Stage 11 completed prerequisite
        st11_stmt = select(PipelineStageExecution).where(
            PipelineStageExecution.project_id == project_id,
            PipelineStageExecution.stage_id == "review",
        )
        st11_exec = (await db.execute(st11_stmt)).scalar_one_or_none()
        if not st11_exec or st11_exec.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stage 11 Human Review must be completed before executing Stage 12 Unified Record.",
            )

        # 3. Load Stage 10 Confidence Scoring results (or Stage 07 fallback)
        st10_stmt = select(PipelineStageExecution).where(
            PipelineStageExecution.project_id == project_id,
            PipelineStageExecution.stage_id.in_(["confidence", "scoring"]),
        )
        st10_exec = (await db.execute(st10_stmt)).scalar_one_or_none()
        scored_records = (
            st10_exec.results.get("records_preview", [])
            if st10_exec and st10_exec.results
            else []
        )

        # 4. Load Stage 07 Harmonization results
        st7_stmt = select(PipelineStageExecution).where(
            PipelineStageExecution.project_id == project_id,
            PipelineStageExecution.stage_id == "harmonization",
        )
        st7_exec = (await db.execute(st7_stmt)).scalar_one_or_none()
        stage7_records = (
            st7_exec.results.get("records_preview", [])
            if st7_exec and st7_exec.results
            else []
        )
        stage7_by_rec: Dict[str, Dict[str, Any]] = {}
        for r in stage7_records:
            rid = r.get("id") or r.get("harmonized_record_id")
            if rid:
                stage7_by_rec[rid] = r

        # If scored_records is empty but stage7_records exists, use stage7_records as base
        records_to_process = scored_records if scored_records else stage7_records
        if not records_to_process:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No harmonized or confidence-scored records found for this project.",
            )

        # 5. Load Stage 08 Conflicts
        conf_stmt = select(GeospatialConflict).where(
            GeospatialConflict.project_id == project_id
        )
        all_conflicts = list((await db.execute(conf_stmt)).scalars().all())
        conflicts_by_record: Dict[str, List[GeospatialConflict]] = defaultdict(list)
        for c in all_conflicts:
            conflicts_by_record[c.harmonized_record_id].append(c)

        # 6. Load Stage 09 Validation Results
        val_stmt = select(ValidationResult).where(
            ValidationResult.project_id == project_id
        )
        all_val = list((await db.execute(val_stmt)).scalars().all())
        val_by_record: Dict[str, ValidationResult] = {
            v.harmonized_record_id: v for v in all_val
        }

        # 7. Load Stage 11 Human Review Decisions
        dec_stmt = select(HumanReviewDecision).where(
            HumanReviewDecision.project_id == project_id
        )
        all_dec = list((await db.execute(dec_stmt)).scalars().all())
        decisions_by_record: Dict[str, HumanReviewDecision] = {
            d.harmonized_record_id: d for d in all_dec
        }

        # 8. Batch query CanonicalFeatures for geometry and properties
        feat_ids: Set[uuid.UUID] = set()
        for r in records_to_process:
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

        for d in all_dec:
            if d.source_feature_id:
                feat_ids.add(d.source_feature_id)
            if d.candidate_feature_id:
                feat_ids.add(d.candidate_feature_id)

        features_by_id: Dict[uuid.UUID, CanonicalFeature] = {}
        if feat_ids:
            cf_stmt = (
                select(CanonicalFeature)
                .where(CanonicalFeature.id.in_(list(feat_ids)))
                .options(
                    selectinload(CanonicalFeature.dataset_version).joinedload(
                        DatasetVersion.dataset
                    )
                )
            )
            c_feats = (await db.execute(cf_stmt)).scalars().all()
            features_by_id = {f.id: f for f in c_feats}

        # 9. Query existing UnifiedLandRecords for idempotency
        existing_stmt = (
            select(UnifiedLandRecord)
            .where(UnifiedLandRecord.project_id == project_id)
            .options(selectinload(UnifiedLandRecord.sources))
        )
        existing_records_list = list((await db.execute(existing_stmt)).scalars().all())
        existing_by_rec_id: Dict[str, UnifiedLandRecord] = {
            ur.harmonized_record_id: ur
            for ur in existing_records_list
            if ur.harmonized_record_id
        }

        saved_records: List[UnifiedLandRecord] = []
        valid_geometries_count = 0
        unified_count = 0
        rejected_count = 0
        confidence_sum = 0.0

        for r in records_to_process:
            rec_id = r.get("id") or r.get("harmonized_record_id", "")
            s7 = stage7_by_rec.get(rec_id, {})
            rec_confs = conflicts_by_record.get(rec_id, [])
            val_res = val_by_record.get(rec_id)
            dec = decisions_by_record.get(rec_id)

            sf_uuid: Optional[uuid.UUID] = None
            cf_uuid: Optional[uuid.UUID] = None
            fm_uuid: Optional[uuid.UUID] = None

            if r.get("source_feature_id"):
                try:
                    sf_uuid = uuid.UUID(str(r["source_feature_id"]))
                except (ValueError, TypeError):
                    pass
            elif dec and dec.source_feature_id:
                sf_uuid = dec.source_feature_id

            if r.get("candidate_feature_id"):
                try:
                    cf_uuid = uuid.UUID(str(r["candidate_feature_id"]))
                except (ValueError, TypeError):
                    pass
            elif dec and dec.candidate_feature_id:
                cf_uuid = dec.candidate_feature_id

            if r.get("feature_match_id"):
                try:
                    fm_uuid = uuid.UUID(str(r["feature_match_id"]))
                except (ValueError, TypeError):
                    pass
            elif dec and dec.feature_match_id:
                fm_uuid = dec.feature_match_id

            src_feat = features_by_id.get(sf_uuid) if sf_uuid else None
            cand_feat = features_by_id.get(cf_uuid) if cf_uuid else None

            src_ref = (
                r.get("source_identifier")
                or (extract_feature_display_id(src_feat) if src_feat else None)
                or (src_feat.canonical_properties.get("parcel_id") if src_feat and src_feat.canonical_properties else None)
                or "Unknown Source A"
            )
            cand_ref = (
                r.get("candidate_identifier")
                or (extract_feature_display_id(cand_feat) if cand_feat else None)
                or (cand_feat.canonical_properties.get("parcel_id") if cand_feat and cand_feat.canonical_properties else None)
                or "Unknown Source B"
            )

            # Confidence and validation propagation
            conf_score = float(r.get("overall_confidence", 0.0))
            val_status = (
                val_res.overall_status
                if val_res
                else r.get("validation_status", "PASS")
            )

            # Synthesis based on human review decision
            chosen_feature: Optional[CanonicalFeature] = None
            geom_source: str = "SOURCE_A"
            land_use: Optional[str] = None
            mutation_status: Optional[str] = None
            risk_level: Optional[str] = None
            area_val: Optional[float] = None
            resolution_status: str = "UNIFIED"
            human_decision_str: str = "AUTO_CONFIRMED"

            if dec:
                human_decision_str = dec.action
                if dec.action == "ACCEPT_SOURCE_A":
                    resolution_status = "UNIFIED"
                    geom_source = "SOURCE_A"
                    chosen_feature = src_feat
                    land_use = (
                        src_feat.canonical_properties.get("land_use")
                        if src_feat and src_feat.canonical_properties
                        else None
                    ) or s7.get("source_land_use") or s7.get("harmonized_land_use")
                    mutation_status = (
                        src_feat.canonical_properties.get("mutation_status")
                        if src_feat and src_feat.canonical_properties
                        else None
                    ) or s7.get("source_mutation_status") or s7.get("harmonized_mutation_status")
                    risk_level = (
                        src_feat.canonical_properties.get("risk_level")
                        if src_feat and src_feat.canonical_properties
                        else None
                    ) or s7.get("source_risk_level") or s7.get("harmonized_risk_level")
                    area_val = s7.get("source_area") or s7.get("harmonized_area")

                elif dec.action == "ACCEPT_SOURCE_B":
                    resolution_status = "UNIFIED"
                    geom_source = "SOURCE_B"
                    chosen_feature = cand_feat
                    land_use = (
                        cand_feat.canonical_properties.get("land_use")
                        if cand_feat and cand_feat.canonical_properties
                        else None
                    ) or s7.get("candidate_land_use") or s7.get("harmonized_land_use")
                    mutation_status = (
                        cand_feat.canonical_properties.get("mutation_status")
                        if cand_feat and cand_feat.canonical_properties
                        else None
                    ) or s7.get("candidate_mutation_status") or s7.get("harmonized_mutation_status")
                    risk_level = (
                        cand_feat.canonical_properties.get("risk_level")
                        if cand_feat and cand_feat.canonical_properties
                        else None
                    ) or s7.get("candidate_risk_level") or s7.get("harmonized_risk_level")
                    area_val = s7.get("candidate_area") or s7.get("harmonized_area")

                elif dec.action == "MERGE_RECONCILE":
                    resolution_status = "UNIFIED"
                    geom_source = (
                        dec.authoritative_geometry_source
                        or s7.get("authoritative_geometry_source", "SOURCE_A")
                    )
                    chosen_feature = cand_feat if geom_source == "SOURCE_B" else src_feat
                    reconciled = dec.authoritative_attributes or {}
                    land_use = reconciled.get("land_use") or s7.get("harmonized_land_use")
                    mutation_status = reconciled.get("mutation_status") or s7.get("harmonized_mutation_status")
                    risk_level = reconciled.get("risk_level") or s7.get("harmonized_risk_level")
                    if reconciled.get("area") is not None:
                        try:
                            area_val = float(reconciled["area"])
                        except (ValueError, TypeError):
                            area_val = s7.get("harmonized_area")
                    else:
                        area_val = s7.get("harmonized_area")

                elif dec.action == "REJECT_UNRESOLVED":
                    resolution_status = "REJECTED"
                    geom_source = "REJECTED"
                    chosen_feature = None
                    land_use = None
                    mutation_status = None
                    risk_level = "CRITICAL"
                    area_val = None

            else:
                # Auto-confirmed record (no human decision required)
                resolution_status = "UNIFIED"
                human_decision_str = "AUTO_CONFIRMED"
                s7_geom_src = s7.get("authoritative_geometry_source", "SOURCE_A")
                geom_source = s7_geom_src
                chosen_feature = cand_feat if s7_geom_src in ["SOURCE_B", "DRONE"] else src_feat
                land_use = s7.get("harmonized_land_use")
                mutation_status = s7.get("harmonized_mutation_status")
                risk_level = s7.get("harmonized_risk_level")
                area_val = s7.get("harmonized_area")

            # PostGIS Geometry handling
            canonical_geom = None
            computed_area = None
            is_valid_geom = False
            geom_source_feat_id = None
            geom_role = None

            if resolution_status == "UNIFIED" and chosen_feature and chosen_feature.geometry:
                geom_source_feat_id = chosen_feature.id
                ds = (
                    chosen_feature.dataset_version.dataset
                    if chosen_feature.dataset_version and chosen_feature.dataset_version.dataset
                    else None
                )
                geom_role = detect_source_role(
                    ds.name if ds else None,
                    chosen_feature.canonical_properties,
                )
                sh_geom = extract_shapely_geom(chosen_feature.geometry)
                if sh_geom and not sh_geom.is_empty:
                    if not sh_geom.is_valid:
                        sh_geom = make_valid(sh_geom)
                    is_valid_geom = sh_geom.is_valid
                    computed_area = compute_metric_area(sh_geom, explicit_area=area_val)
                    canonical_geom = from_shape(sh_geom, srid=4326)
                    valid_geometries_count += 1

            if computed_area is None:
                computed_area = area_val

            # Lineage / Metadata Trail
            metadata_trail = {
                "source_a_reference": src_ref,
                "source_b_reference": cand_ref,
                "source_feature_id": str(sf_uuid) if sf_uuid else None,
                "candidate_feature_id": str(cf_uuid) if cf_uuid else None,
                "feature_match_id": str(fm_uuid) if fm_uuid else None,
                "harmonized_record_id": rec_id,
                "pipeline_lineage": {
                    "matching": {
                        "feature_match_id": str(fm_uuid) if fm_uuid else None,
                        "source_identifier": src_ref,
                        "candidate_identifier": cand_ref,
                    },
                    "harmonization": {
                        "authoritative_geometry_source": s7.get("authoritative_geometry_source"),
                        "geometry_status": s7.get("geometry_status"),
                        "harmonized_area": s7.get("harmonized_area"),
                        "area_discrepancy_pct": s7.get("area_discrepancy_pct"),
                        "harmonized_land_use": s7.get("harmonized_land_use"),
                        "harmonized_mutation_status": s7.get("harmonized_mutation_status"),
                        "harmonized_risk_level": s7.get("harmonized_risk_level"),
                    },
                    "conflicts": {
                        "conflict_count": len(rec_confs),
                        "conflict_types": [c.conflict_type for c in rec_confs],
                        "severities": [c.severity for c in rec_confs],
                    },
                    "validation": {
                        "overall_status": val_status,
                        "failure_reasons": val_res.failure_reasons if val_res else [],
                        "warning_reasons": val_res.warning_reasons if val_res else [],
                    },
                    "confidence": {
                        "overall_confidence": conf_score,
                        "confidence_bucket": r.get("confidence_bucket"),
                        "contributions": r.get("contributions", {}),
                        "reasons": r.get("reasons", []),
                    },
                    "human_review": {
                        "decision": human_decision_str,
                        "adjudicated": dec is not None,
                        "reviewer_name": dec.reviewer_name if dec else None,
                        "notes": dec.notes if dec else None,
                        "adjudicated_at": dec.created_at.isoformat() if dec and dec.created_at else None,
                        "override_applied": dec.override_applied if dec else False,
                        "authoritative_geometry_source": dec.authoritative_geometry_source if dec else None,
                        "authoritative_attributes": dec.authoritative_attributes if dec else {},
                    },
                },
                "unified_at": now.isoformat(),
            }

            canonical_attributes = {
                "land_use": land_use,
                "mutation_status": mutation_status,
                "risk_level": risk_level,
                "area": computed_area,
                "survey_number": src_ref,
                "source_a_reference": src_ref,
                "source_b_reference": cand_ref,
                "geometry_valid": is_valid_geom,
            }

            # Record status
            if resolution_status == "REJECTED":
                record_status = "CONFLICT"
                rejected_count += 1
            else:
                record_status = "ACTIVE" if (is_valid_geom and computed_area is not None) else "INCOMPLETE"
                unified_count += 1
                confidence_sum += conf_score

            rec_identifier = f"ULR-{rec_id}"

            # Idempotent Upsert into unified_land_records
            unified_rec = existing_by_rec_id.get(rec_id)
            if not unified_rec:
                unified_rec = UnifiedLandRecord(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    record_identifier=rec_identifier,
                    status=record_status,
                    canonical_geometry=canonical_geom,
                    geometry_source_feature_id=geom_source_feat_id,
                    geometry_source_role=geom_role,
                    area=computed_area,
                    canonical_attributes=canonical_attributes,
                    harmonized_record_id=rec_id,
                    source_a_reference=src_ref,
                    source_b_reference=cand_ref,
                    geometry_source=geom_source,
                    land_use=land_use,
                    mutation_status=mutation_status,
                    risk_level=risk_level,
                    confidence_score=conf_score,
                    validation_status=val_status,
                    human_review_decision=human_decision_str,
                    resolution_status=resolution_status,
                    metadata_trail=metadata_trail,
                )
                db.add(unified_rec)
            else:
                unified_rec.status = record_status
                unified_rec.canonical_geometry = canonical_geom
                unified_rec.geometry_source_feature_id = geom_source_feat_id
                unified_rec.geometry_source_role = geom_role
                unified_rec.area = computed_area
                unified_rec.canonical_attributes = canonical_attributes
                unified_rec.source_a_reference = src_ref
                unified_rec.source_b_reference = cand_ref
                unified_rec.geometry_source = geom_source
                unified_rec.land_use = land_use
                unified_rec.mutation_status = mutation_status
                unified_rec.risk_level = risk_level
                unified_rec.confidence_score = conf_score
                unified_rec.validation_status = val_status
                unified_rec.human_review_decision = human_decision_str
                unified_rec.resolution_status = resolution_status
                unified_rec.metadata_trail = metadata_trail
                unified_rec.updated_at = now

            saved_records.append(unified_rec)

        # Flush to generate IDs for new records
        await db.flush()

        # Idempotently update UnifiedLandRecordSource rows
        saved_rec_ids = [ur.id for ur in saved_records]
        existing_srcs_stmt = select(UnifiedLandRecordSource).where(
            UnifiedLandRecordSource.unified_land_record_id.in_(saved_rec_ids)
        )
        all_existing_srcs = list((await db.execute(existing_srcs_stmt)).scalars().all())
        existing_srcs_by_rec = defaultdict(dict)
        sources_count_by_rec = defaultdict(int)
        for s in all_existing_srcs:
            existing_srcs_by_rec[s.unified_land_record_id][s.feature_id] = s
            sources_count_by_rec[s.unified_land_record_id] += 1

        for ur in saved_records:
            existing_sources = existing_srcs_by_rec[ur.id]

            # Source A feature
            r_sf = ur.metadata_trail.get("source_feature_id")
            if r_sf:
                sf_id = uuid.UUID(r_sf)
                if sf_id not in existing_sources:
                    s_role = "CADASTRAL"
                    if sf_id in features_by_id:
                        f = features_by_id[sf_id]
                        ds = f.dataset_version.dataset if f.dataset_version and f.dataset_version.dataset else None
                        s_role = detect_source_role(ds.name if ds else None, f.canonical_properties)
                    db.add(
                        UnifiedLandRecordSource(
                            id=uuid.uuid4(),
                            unified_land_record_id=ur.id,
                            feature_id=sf_id,
                            feature_match_id=uuid.UUID(ur.metadata_trail["feature_match_id"]) if ur.metadata_trail.get("feature_match_id") else None,
                            source_role=s_role,
                            created_at=now,
                        )
                    )
                    sources_count_by_rec[ur.id] += 1

            # Candidate feature
            r_cf = ur.metadata_trail.get("candidate_feature_id")
            if r_cf:
                cf_id = uuid.UUID(r_cf)
                if cf_id not in existing_sources:
                    c_role = "DRONE"
                    if cf_id in features_by_id:
                        f = features_by_id[cf_id]
                        ds = f.dataset_version.dataset if f.dataset_version and f.dataset_version.dataset else None
                        c_role = detect_source_role(ds.name if ds else None, f.canonical_properties)
                    db.add(
                        UnifiedLandRecordSource(
                            id=uuid.uuid4(),
                            unified_land_record_id=ur.id,
                            feature_id=cf_id,
                            feature_match_id=uuid.UUID(ur.metadata_trail["feature_match_id"]) if ur.metadata_trail.get("feature_match_id") else None,
                            source_role=c_role,
                            created_at=now,
                        )
                    )
                    sources_count_by_rec[ur.id] += 1

        # 10. Record PipelineStageExecution for Stage 12
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        avg_confidence = round(confidence_sum / max(1, unified_count), 4)

        results_payload = {
            "records_considered": len(records_to_process),
            "records_unified": unified_count,
            "records_rejected": rejected_count,
            "average_confidence": avg_confidence,
            "valid_geometries_count": valid_geometries_count,
            "execution_time_ms": duration_ms,
            "last_executed_at": now.isoformat(),
        }

        st12_exec_stmt = select(PipelineStageExecution).where(
            PipelineStageExecution.project_id == project_id,
            PipelineStageExecution.stage_id.in_(["record", "unified"]),
        )
        st12_exec = (await db.execute(st12_exec_stmt)).scalar_one_or_none()

        if not st12_exec:
            st12_exec = PipelineStageExecution(
                id=uuid.uuid4(),
                project_id=project_id,
                stage_number=12,
                stage_id="record",
                status="completed",
                inputs={"enforce_stage11_gate": True},
                results=results_payload,
                started_at=now,
                completed_at=now,
            )
            db.add(st12_exec)
        else:
            st12_exec.stage_id = "record"
            st12_exec.stage_number = 12
            st12_exec.status = "completed"
            st12_exec.results = results_payload
            st12_exec.completed_at = now

        # 11. Emit ProvenanceEvent
        comp_prov = ProvenanceEvent(
            id=uuid.uuid4(),
            project_id=project_id,
            unified_land_record_id=None,
            event_type="UNIFIED_RECORD_SYNTHESIS_COMPLETED",
            source_type="PIPELINE_STAGE_12",
            source_id=st12_exec.id,
            event_metadata=results_payload,
            created_at=now,
        )
        db.add(comp_prov)

        await db.commit()

        # Build preview items
        preview_items: List[UnifiedRecordListItem] = [
            UnifiedRecordListItem(
                id=r.id,
                project_id=r.project_id,
                record_identifier=r.record_identifier,
                status=r.status,
                source_count=sources_count_by_rec.get(r.id, 0),
                geometry_source_role=r.geometry_source_role,
                area=r.area,
                canonical_attributes=r.canonical_attributes or {},
                harmonized_record_id=r.harmonized_record_id,
                source_a_reference=r.source_a_reference,
                source_b_reference=r.source_b_reference,
                geometry_source=r.geometry_source,
                land_use=r.land_use,
                mutation_status=r.mutation_status,
                risk_level=r.risk_level,
                confidence_score=r.confidence_score,
                validation_status=r.validation_status,
                human_review_decision=r.human_review_decision,
                resolution_status=r.resolution_status,
                metadata_trail=r.metadata_trail or {},
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in saved_records[:50]
        ]

        return Stage12ExecutionResponse(
            stage_number=12,
            stage_id="record",
            status="completed",
            project_id=project_id,
            records_considered=len(records_to_process),
            records_unified=unified_count,
            records_rejected=rejected_count,
            average_confidence=avg_confidence,
            valid_geometries_count=valid_geometries_count,
            execution_time_ms=duration_ms,
            message=(
                f"Stage 12 Unified Record successfully synthesized {unified_count} authoritative "
                f"master records ({rejected_count} rejected/unresolved). Stage 13 Provenance is now unlocked."
            ),
            records_preview=preview_items,
        )

    @classmethod
    async def get_stage12_status(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> Stage12StatusResponse:
        """
        Calculates live status and metrics for Stage 12: Unified Record.
        """
        # Check Stage 11 completed
        st11_stmt = select(PipelineStageExecution).where(
            PipelineStageExecution.project_id == project_id,
            PipelineStageExecution.stage_id == "review",
        )
        st11_exec = (await db.execute(st11_stmt)).scalar_one_or_none()
        st11_completed = bool(st11_exec and st11_exec.status == "completed")

        # Check Stage 12 execution
        st12_stmt = select(PipelineStageExecution).where(
            PipelineStageExecution.project_id == project_id,
            PipelineStageExecution.stage_id.in_(["record", "unified"]),
        )
        st12_exec = (await db.execute(st12_stmt)).scalar_one_or_none()
        is_completed = bool(st12_exec and st12_exec.status == "completed")

        if is_completed:
            stage_status = "completed"
        elif st11_completed:
            stage_status = "ready"
        else:
            stage_status = "disabled"

        records_considered = 0
        records_unified = 0
        records_rejected = 0
        avg_confidence = 0.0
        valid_geometries_count = 0
        last_executed_at = None

        if st12_exec and st12_exec.results:
            res = st12_exec.results
            records_considered = res.get("records_considered", 0)
            records_unified = res.get("records_unified", 0)
            records_rejected = res.get("records_rejected", 0)
            avg_confidence = res.get("average_confidence", 0.0)
            valid_geometries_count = res.get("valid_geometries_count", 0)
            last_executed_at = st12_exec.completed_at or st12_exec.updated_at
        elif is_completed:
            count_stmt = select(func.count(UnifiedLandRecord.id)).where(
                UnifiedLandRecord.project_id == project_id
            )
            records_considered = (await db.execute(count_stmt)).scalar() or 0
            u_stmt = select(func.count(UnifiedLandRecord.id)).where(
                UnifiedLandRecord.project_id == project_id,
                UnifiedLandRecord.resolution_status == "UNIFIED",
            )
            records_unified = (await db.execute(u_stmt)).scalar() or 0
            records_rejected = records_considered - records_unified

        return Stage12StatusResponse(
            project_id=project_id,
            stage_status=stage_status,
            is_completed=is_completed,
            is_runnable=st11_completed,
            records_considered=records_considered,
            records_unified=records_unified,
            records_rejected=records_rejected,
            average_confidence=avg_confidence,
            valid_geometries_count=valid_geometries_count,
            last_executed_at=last_executed_at,
        )

    @classmethod
    async def get_record_sources(
        cls,
        db: AsyncSession,
        record_id: uuid.UUID,
    ) -> List[UnifiedRecordSourceResponse]:
        """
        Retrieves contributing source features and geometries for a unified land record.
        """
        detail = await cls.get_record_detail(db, record_id)
        if not detail:
            return []
        return detail.sources

    @classmethod
    async def get_statistics(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> UnifiedRecordStatisticsResponse:
        """
        Computes project-level metrics for unified land records directly from PostgreSQL.
        """
        # Status counts
        status_stmt = (
            select(
                UnifiedLandRecord.status,
                func.count(UnifiedLandRecord.id).label("count"),
            )
            .where(UnifiedLandRecord.project_id == project_id)
            .group_by(UnifiedLandRecord.status)
        )
        status_rows = (await db.execute(status_stmt)).all()

        counts = {"ACTIVE": 0, "INCOMPLETE": 0, "CONFLICT": 0}
        total = 0
        for st, c in status_rows:
            if st in counts:
                counts[st] = c
            total += c

        # Source role distribution
        role_stmt = (
            select(
                UnifiedLandRecordSource.source_role,
                func.count(func.distinct(UnifiedLandRecordSource.unified_land_record_id)),
            )
            .join(UnifiedLandRecord, UnifiedLandRecord.id == UnifiedLandRecordSource.unified_land_record_id)
            .where(UnifiedLandRecord.project_id == project_id)
            .group_by(UnifiedLandRecordSource.source_role)
        )
        role_rows = (await db.execute(role_stmt)).all()
        role_counts = {r: c for r, c in role_rows}

        # Average sources per record
        total_sources_stmt = (
            select(func.count(UnifiedLandRecordSource.id))
            .join(UnifiedLandRecord, UnifiedLandRecord.id == UnifiedLandRecordSource.unified_land_record_id)
            .where(UnifiedLandRecord.project_id == project_id)
        )
        total_sources = (await db.execute(total_sources_stmt)).scalar() or 0
        avg_sources = round(total_sources / total, 2) if total > 0 else 0.0

        return UnifiedRecordStatisticsResponse(
            project_id=project_id,
            total_records=total,
            active=counts["ACTIVE"],
            incomplete=counts["INCOMPLETE"],
            conflict=counts["CONFLICT"],
            average_sources_per_record=avg_sources,
            records_with_cadastral=role_counts.get("CADASTRAL", 0),
            records_with_drone=role_counts.get("DRONE", 0),
            records_with_municipal=role_counts.get("MUNICIPAL", 0),
        )
