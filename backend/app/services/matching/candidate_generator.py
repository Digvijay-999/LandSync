import uuid
from typing import List, Dict, Tuple, Optional
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from shapely.geometry.base import BaseGeometry
from shapely import make_valid

from app.models.feature import CanonicalFeature
from app.models.dataset import Dataset, DatasetVersion
from app.services.dataset import extract_shapely_geom
from app.services.matching.signals import compute_centroid_distance_meters


class CandidateGenerator:
    """
    Spatially filters and indexes features to find candidate pairs
    between source dataset and candidate datasets using PostGIS GIST indexes.
    Avoids O(n²) exhaustive feature comparisons.
    """

    @classmethod
    async def get_candidate_pairs(
        cls,
        db: AsyncSession,
        source_dataset_id: uuid.UUID,
        candidate_dataset_ids: List[uuid.UUID],
        distance_meters: float = 50.0,
    ) -> List[Tuple[CanonicalFeature, Optional[CanonicalFeature]]]:
        """
        Retrieves candidate feature pairs (source, candidate).
        If a source feature has no spatial candidates within distance_meters,
        emits (source, None) to ensure full classification traceability (UNMATCHED).
        """
        # 1. Fetch latest version IDs for source and candidate datasets
        source_version_id = await cls._get_latest_version_id(db, source_dataset_id)
        if not source_version_id:
            return []

        cand_version_ids = []
        for c_id in candidate_dataset_ids:
            v_id = await cls._get_latest_version_id(db, c_id)
            if v_id:
                cand_version_ids.append(v_id)

        if not cand_version_ids:
            # Source features with no candidate datasets
            src_features = await cls._get_features_by_version(db, source_version_id)
            return [(sf, None) for sf in src_features]

        # 2. Query based on database dialect (PostgreSQL PostGIS vs SQLite test fallback)
        bind = db.bind
        dialect_name = bind.dialect.name if bind else "postgresql"

        if dialect_name == "postgresql":
            return await cls._postgis_candidate_search(
                db=db,
                source_version_id=source_version_id,
                candidate_version_ids=cand_version_ids,
                distance_meters=distance_meters,
            )
        else:
            return await cls._fallback_spatial_candidate_search(
                db=db,
                source_version_id=source_version_id,
                candidate_version_ids=cand_version_ids,
                distance_meters=distance_meters,
            )

    @classmethod
    async def _postgis_candidate_search(
        cls,
        db: AsyncSession,
        source_version_id: uuid.UUID,
        candidate_version_ids: List[uuid.UUID],
        distance_meters: float,
    ) -> List[Tuple[CanonicalFeature, Optional[CanonicalFeature]]]:
        """
        Executes PostGIS ST_DWithin query using GIST spatial indexes.
        LEFT JOIN ensures source features without candidates are still returned for UNMATCHED processing.
        """
        cand_ids_str = ", ".join(f"'{str(v)}'::uuid" for v in candidate_version_ids)

        # Uses GIST spatial index on geography/geometry with ST_DWithin
        query = text(f"""
            SELECT 
                sf.id AS src_id,
                cf.id AS cand_id
            FROM canonical_features sf
            LEFT JOIN canonical_features cf ON (
                cf.dataset_version_id IN ({cand_ids_str})
                AND sf.id != cf.id
                AND ST_DWithin(sf.geometry::geography, cf.geometry::geography, :dist_m)
            )
            WHERE sf.dataset_version_id = :src_ver_id
            ORDER BY sf.id, cf.id;
        """)

        result = await db.execute(query, {
            "src_ver_id": source_version_id,
            "dist_m": distance_meters,
        })
        rows = result.fetchall()

        # Collect unique feature IDs to load
        feature_ids = set()
        for src_id, cand_id in rows:
            feature_ids.add(src_id)
            if cand_id:
                feature_ids.add(cand_id)

        features_map = await cls._load_features_by_ids(db, list(feature_ids))

        pairs: List[Tuple[CanonicalFeature, Optional[CanonicalFeature]]] = []
        for src_id, cand_id in rows:
            src_feat = features_map.get(src_id)
            cand_feat = features_map.get(cand_id) if cand_id else None
            if src_feat:
                pairs.append((src_feat, cand_feat))

        return pairs

    @classmethod
    async def _fallback_spatial_candidate_search(
        cls,
        db: AsyncSession,
        source_version_id: uuid.UUID,
        candidate_version_ids: List[uuid.UUID],
        distance_meters: float,
    ) -> List[Tuple[CanonicalFeature, Optional[CanonicalFeature]]]:
        """
        In-memory bounding box and centroid distance candidate generation
        for SQLite unit tests.
        """
        src_features = await cls._get_features_by_version(db, source_version_id)
        cand_features: List[CanonicalFeature] = []
        for v_id in candidate_version_ids:
            cand_features.extend(await cls._get_features_by_version(db, v_id))

        pairs: List[Tuple[CanonicalFeature, Optional[CanonicalFeature]]] = []

        # Convert distance meters to rough bounding box buffer in degrees (~111km per deg)
        deg_buffer = distance_meters / 100000.0

        for sf in src_features:
            sh_sf = extract_shapely_geom(sf.geometry)
            if sh_sf is None or sh_sf.is_empty:
                pairs.append((sf, None))
                continue

            sf_bounds = sh_sf.bounds  # (minx, miny, maxx, maxy)
            buffered_bounds = (
                sf_bounds[0] - deg_buffer,
                sf_bounds[1] - deg_buffer,
                sf_bounds[2] + deg_buffer,
                sf_bounds[3] + deg_buffer,
            )

            found_any = False
            for cf in cand_features:
                if sf.id == cf.id:
                    continue
                sh_cf = extract_shapely_geom(cf.geometry)
                if sh_cf is None or sh_cf.is_empty:
                    continue

                cf_bounds = sh_cf.bounds
                # Fast Bounding-box intersection check
                if not (
                    buffered_bounds[0] <= cf_bounds[2] and
                    buffered_bounds[2] >= cf_bounds[0] and
                    buffered_bounds[1] <= cf_bounds[3] and
                    buffered_bounds[3] >= cf_bounds[1]
                ):
                    continue

                # Detailed centroid/boundary distance check
                dist_m = compute_centroid_distance_meters(sh_sf, sh_cf)
                if dist_m <= distance_meters or sh_sf.intersects(sh_cf):
                    pairs.append((sf, cf))
                    found_any = True

            if not found_any:
                pairs.append((sf, None))

        return pairs

    @classmethod
    async def _get_latest_version_id(cls, db: AsyncSession, dataset_id: uuid.UUID) -> Optional[uuid.UUID]:
        stmt = (
            select(DatasetVersion.id)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version_number.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @classmethod
    async def _get_features_by_version(cls, db: AsyncSession, version_id: uuid.UUID) -> List[CanonicalFeature]:
        stmt = (
            select(CanonicalFeature)
            .where(CanonicalFeature.dataset_version_id == version_id)
        )
        return list((await db.execute(stmt)).scalars().all())

    @classmethod
    async def _load_features_by_ids(cls, db: AsyncSession, ids: List[uuid.UUID]) -> Dict[uuid.UUID, CanonicalFeature]:
        if not ids:
            return {}
        stmt = select(CanonicalFeature).where(CanonicalFeature.id.in_(ids))
        res = await db.execute(stmt)
        return {f.id: f for f in res.scalars().all()}
