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

from app.models.project import Project
from app.models.dataset import Dataset, DatasetVersion
from app.models.feature import CanonicalFeature
from app.models.matching import FeatureMatch
from app.models.unified import UnifiedLandRecord, UnifiedLandRecordSource
from app.services.dataset import extract_shapely_geom
from app.services.matching.service import extract_feature_display_id
from app.schemas.unified import (
    UnifiedRecordSourceResponse,
    UnifiedRecordListItem,
    UnifiedRecordListResponse,
    UnifiedRecordDetailResponse,
    UnifiedRecordBuildResponse,
    UnifiedRecordStatisticsResponse,
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

            # Check if values changed for idempotency tracking
            geom_changed = (
                target_record.geometry_source_feature_id != (selected_feature.id if selected_feature else None)
            )
            status_changed = target_record.status != status
            area_changed = target_record.area != computed_area
            attrs_changed = target_record.canonical_attributes != canonical_attrs

            target_record.geometry_source_feature_id = selected_feature.id if selected_feature else None
            target_record.geometry_source_role = selected_role
            target_record.canonical_geometry = selected_feature.geometry if selected_feature else None
            target_record.area = computed_area
            target_record.status = status
            target_record.canonical_attributes = canonical_attrs

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
        skip: int = 0,
        limit: int = 50,
    ) -> UnifiedRecordListResponse:
        """
        Lists paginated unified land records for a project.
        """
        filters = [UnifiedLandRecord.project_id == project_id]
        if status:
            filters.append(UnifiedLandRecord.status == status.strip().upper())

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
                source_count=len(r.sources),
                geometry_source_role=r.geometry_source_role,
                area=r.area,
                canonical_attributes=r.canonical_attributes or {},
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
            sources=sources_list,
            created_at=record.created_at,
            updated_at=record.updated_at,
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
