import uuid
import numpy as np
import pandas as pd
from typing import List, Tuple, Optional, Dict, Any
from fastapi import UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry
from shapely import from_wkt
from geoalchemy2.shape import to_shape

from app.core.logging import logger
from app.models.project import Project
from app.models.dataset import Dataset, DatasetVersion
from app.models.feature import SourceFeature, CanonicalFeature
from app.services.ingestion.storage import StorageService
from app.services.ingestion.detector import FormatDetector
from app.services.ingestion.reader import DatasetReader
from app.services.ingestion.profiler import DatasetProfiler
from app.services.ingestion.exceptions import ProjectNotFoundError, EmptyDatasetError
from app.services.crs.normalizer import CRSNormalizer, MissingCRSError
from app.schemas.dataset import DatasetProfile, BoundingBox
from app.schemas.feature import (
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    FeatureRead,
    ProjectLayer,
    ProjectLayersResponse,
)


def extract_shapely_geom(geom_val: Any) -> Optional[BaseGeometry]:
    """Safely unwrap geometry from GeoAlchemy2 WKBElement, Shapely geometry, or WKT string."""
    if geom_val is None:
        return None
    if isinstance(geom_val, BaseGeometry):
        return geom_val
    if hasattr(geom_val, "data"):
        try:
            return to_shape(geom_val)
        except Exception:
            pass
    if isinstance(geom_val, str):
        try:
            return from_wkt(geom_val)
        except Exception:
            return None
    try:
        return to_shape(geom_val)
    except Exception:
        return None


def sanitize_value(val: Any) -> Any:
    """Recursively converts property values to JSONB-safe primitives without triggering array truthiness errors."""
    if val is None or val is pd.NA:
        return None
    if isinstance(val, (bool, int, str)):
        return val
    if isinstance(val, (float, np.floating)):
        return None if (np.isnan(val) or np.isinf(val)) else float(val)
    if isinstance(val, np.integer):
        return int(val)
    if isinstance(val, np.bool_):
        return bool(val)
    if isinstance(val, (list, tuple)):
        return [sanitize_value(item) for item in val]
    if isinstance(val, np.ndarray):
        return [sanitize_value(item) for item in val.tolist()]
    if isinstance(val, dict):
        return {str(k): sanitize_value(v) for k, v in val.items()}
    if hasattr(val, "isoformat"):
        try:
            return val.isoformat()
        except Exception:
            return str(val)
    try:
        if np.isscalar(val) and pd.isna(val):
            return None
    except (ValueError, TypeError):
        pass
    return str(val)


def sanitize_properties(row_dict: Dict[str, Any], geom_col_name: str) -> Dict[str, Any]:
    """Sanitizes DataFrame row values into JSON-compliant primitives."""
    clean: Dict[str, Any] = {}
    for k, v in row_dict.items():
        if k == geom_col_name:
            continue
        clean[k] = sanitize_value(v)
    return clean


class DatasetService:
    """
    Coordinates dataset lifecycle: ingestion, storage, profiling,
    CRS normalization, source feature retention, canonical feature generation,
    and PostGIS spatial indexing.
    """

    storage = StorageService()
    LAYER_COLORS = ["#06b6d4", "#f59e0b", "#10b981", "#8b5cf6", "#ec4899", "#3b82f6"]

    @classmethod
    async def ingest_dataset(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        file: UploadFile,
        custom_name: Optional[str] = None,
        custom_crs: Optional[str] = None,
    ) -> Dataset:
        # 1. Verify project exists
        project = await db.get(Project, project_id)
        if not project:
            raise ProjectNotFoundError(f"Project with ID '{project_id}' not found.")

        target_crs = project.target_crs or "EPSG:4326"
        dataset_id = uuid.uuid4()
        version_id = uuid.uuid4()
        source_filename = file.filename or "uploaded_data"

        # 2. Persist uploaded file to structured storage
        saved_path, file_size, checksum = await cls.storage.save_upload(
            file=file,
            project_id=str(project_id),
            dataset_id=str(dataset_id),
            version_id=str(version_id),
        )

        try:
            # 3. Format detection and path validation
            format_info = FormatDetector.detect_format(saved_path)

            if custom_crs:
                CRSNormalizer.parse_crs(custom_crs)

            # 4. Read geospatial vector data into GeoDataFrame
            gdf = DatasetReader.read_dataset(format_info, custom_crs=custom_crs)

            # 5. Profile dataset (geometry, spatial, attributes, quality)
            profile: DatasetProfile = DatasetProfiler.profile(
                gdf=gdf,
                filename=source_filename,
                source_format=format_info["format"],
                file_size=file_size,
            )

            # Ensure dataset contains at least one valid or non-empty geometry
            non_empty_count = profile.geometry.valid_geometry_count + profile.geometry.invalid_geometry_count
            if profile.general.feature_count == 0 or non_empty_count == 0:
                raise EmptyDatasetError("Dataset contains no valid spatial features.")

            # 6. Verify and normalize CRS
            source_crs = custom_crs or (profile.spatial.crs if profile.spatial else None)
            if not source_crs:
                if format_info["format"] == "geojson":
                    source_crs = "EPSG:4326"
                else:
                    raise MissingCRSError(
                        "Dataset CRS could not be detected. Please specify an authoritative source CRS."
                    )

            norm_source_crs = CRSNormalizer.normalize_crs_code(source_crs)
            norm_target_crs = CRSNormalizer.normalize_crs_code(target_crs)

            # Log comprehensive profiling metrics
            logger.info(
                f"Dataset ingestion profiling completed for '{source_filename}':\n"
                f"  - filename: {source_filename}\n"
                f"  - detected format: {format_info['format']}\n"
                f"  - feature count: {profile.general.feature_count}\n"
                f"  - geometry types: {profile.geometry.geometry_type} ({profile.geometry.geometry_type_distribution})\n"
                f"  - CRS: {norm_source_crs}\n"
                f"  - valid geometry count: {profile.geometry.valid_geometry_count}\n"
                f"  - empty geometry count: {profile.geometry.empty_geometry_count}\n"
                f"  - target CRS: {norm_target_crs}"
            )

            # 7. Prepare dataset entity
            dataset_name = custom_name.strip() if custom_name and custom_name.strip() else saved_path.stem
            bbox_dict = profile.spatial.bounds.model_dump() if profile.spatial.bounds else None

            dataset = Dataset(
                id=dataset_id,
                project_id=project_id,
                name=dataset_name,
                source_filename=source_filename,
                source_format=format_info["format"],
                source_type=format_info["source_type"],
                status="ready",
                feature_count=profile.general.feature_count,
                geometry_type=profile.geometry.geometry_type,
                detected_crs=norm_source_crs,
                bounding_box=bbox_dict,
                file_size=file_size,
                profile_metadata=profile.model_dump(),
            )

            # 8. Prepare version snapshot entity
            version = DatasetVersion(
                id=version_id,
                dataset_id=dataset_id,
                version_number=1,
                storage_path=str(saved_path),
                file_size=file_size,
                checksum=checksum,
                profile_summary={
                    "feature_count": profile.general.feature_count,
                    "geometry_type": profile.geometry.geometry_type,
                    "crs": norm_source_crs,
                    "validity_percentage": profile.geometry.validity_percentage,
                },
            )

            # 9. Extract and transform features (SourceFeature and CanonicalFeature)
            geom_col_name = gdf.geometry.name if hasattr(gdf, "geometry") else "geometry"
            source_features: List[SourceFeature] = []
            canonical_features: List[CanonicalFeature] = []

            for idx, row in gdf.iterrows():
                geom = row[geom_col_name]
                clean_props = sanitize_properties(dict(row), geom_col_name)

                # Identify feature identifier safely without evaluating containers in boolean context
                fid = None
                for key in ["id", "fid", "parcel_id", "structure_id", "asset_id", "facility_id", "code"]:
                    if key in clean_props:
                        val = clean_props[key]
                        if val is not None and not (isinstance(val, (list, tuple, dict, str)) and len(val) == 0):
                            fid = str(val).strip()
                            if fid:
                                break
                if not fid:
                    fid = f"feat_{idx}"

                is_geom_valid = isinstance(geom, BaseGeometry) and not geom.is_empty
                geom_type = geom.geom_type if is_geom_valid else "Unknown"
                src_feat_id = uuid.uuid4()

                # Source Feature (immutable source CRS representation)
                src_feat = SourceFeature(
                    id=src_feat_id,
                    dataset_version_id=version_id,
                    source_feature_id=fid,
                    geometry=geom if is_geom_valid else None,
                    properties=clean_props,
                    source_crs=norm_source_crs,
                    geometry_type=geom_type,
                )
                source_features.append(src_feat)

                # Canonical Feature (project target CRS representation)
                if not is_geom_valid:
                    can_geom = None
                    can_geom_type = geom_type
                elif norm_source_crs == norm_target_crs:
                    can_geom = geom
                    can_geom_type = geom_type
                else:
                    can_geom = CRSNormalizer.transform_geometry(
                        geom=geom,
                        source_crs_str=norm_source_crs,
                        target_crs_str=norm_target_crs,
                    )
                    can_geom_type = can_geom.geom_type if isinstance(can_geom, BaseGeometry) and not can_geom.is_empty else geom_type

                can_feat = CanonicalFeature(
                    id=uuid.uuid4(),
                    dataset_version_id=version_id,
                    source_feature_id=src_feat_id,
                    geometry=can_geom,
                    geometry_type=can_geom_type,
                    canonical_properties=clean_props,
                    source_crs=norm_source_crs,
                    target_crs=norm_target_crs,
                )
                canonical_features.append(can_feat)

            # 10. Atomic batch persistence
            db.add(dataset)
            db.add(version)
            db.add_all(source_features)
            db.add_all(canonical_features)
            await db.commit()

            logger.info(
                f"PostGIS insertion result: Successfully persisted dataset '{dataset_name}' ({dataset_id}) "
                f"with {len(source_features)} source features and {len(canonical_features)} canonical features."
            )

            reloaded_query = (
                select(Dataset)
                .where(Dataset.id == dataset_id)
                .options(selectinload(Dataset.versions))
            )
            reloaded = (await db.execute(reloaded_query)).scalar_one()
            return reloaded

        except Exception:
            await db.rollback()
            cls.storage.delete_dataset_storage(str(project_id), str(dataset_id))
            raise

    @classmethod
    async def list_datasets(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Dataset], int]:
        total_stmt = (
            select(func.count())
            .select_from(Dataset)
            .where(Dataset.project_id == project_id)
        )
        total = (await db.execute(total_stmt)).scalar() or 0

        query = (
            select(Dataset)
            .where(Dataset.project_id == project_id)
            .order_by(Dataset.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        items = list(result.scalars().all())
        return items, total

    @classmethod
    async def get_dataset(
        cls,
        db: AsyncSession,
        dataset_id: uuid.UUID,
    ) -> Optional[Dataset]:
        query = (
            select(Dataset)
            .where(Dataset.id == dataset_id)
            .options(selectinload(Dataset.versions))
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def delete_dataset(
        cls,
        db: AsyncSession,
        dataset_id: uuid.UUID,
    ) -> bool:
        dataset = await cls.get_dataset(db, dataset_id)
        if not dataset:
            return False

        project_id = dataset.project_id
        await db.delete(dataset)
        await db.commit()

        cls.storage.delete_dataset_storage(str(project_id), str(dataset_id))
        return True

    @classmethod
    async def get_dataset_features_geojson(
        cls,
        db: AsyncSession,
        dataset_id: uuid.UUID,
        representation: str = "canonical",
        limit: int = 5000,
    ) -> GeoJSONFeatureCollection:
        """
        Builds a standard GeoJSON FeatureCollection for a dataset's features.
        Defaults to canonical projection (project target CRS).
        """
        dataset = await cls.get_dataset(db, dataset_id)
        if not dataset:
            raise ValueError(f"Dataset with ID '{dataset_id}' not found.")

        if not dataset.versions:
            return GeoJSONFeatureCollection(features=[], total=0)

        latest_version_id = dataset.versions[0].id
        geojson_features: List[GeoJSONFeature] = []

        if representation == "source":
            stmt = (
                select(SourceFeature)
                .where(SourceFeature.dataset_version_id == latest_version_id)
                .limit(limit)
            )
            result = await db.execute(stmt)
            features = list(result.scalars().all())
            for sf in features:
                sh_geom = extract_shapely_geom(sf.geometry)
                geom_dict = mapping(sh_geom) if sh_geom is not None and not sh_geom.is_empty else None
                props = dict(sf.properties)
                props["_source_feature_id"] = sf.source_feature_id
                props["_geometry_type"] = sf.geometry_type
                props["_source_crs"] = sf.source_crs
                props["_dataset_name"] = dataset.name
                props["_dataset_id"] = str(dataset.id)
                geojson_features.append(
                    GeoJSONFeature(
                        id=str(sf.id),
                        geometry=geom_dict,
                        properties=props,
                    )
                )
        else:
            stmt = (
                select(CanonicalFeature)
                .where(CanonicalFeature.dataset_version_id == latest_version_id)
                .limit(limit)
            )
            result = await db.execute(stmt)
            features = list(result.scalars().all())
            for cf in features:
                sh_geom = extract_shapely_geom(cf.geometry)
                geom_dict = mapping(sh_geom) if sh_geom is not None and not sh_geom.is_empty else None
                props = dict(cf.canonical_properties)
                props["_source_feature_id"] = str(cf.source_feature_id)
                props["_geometry_type"] = cf.geometry_type
                props["_source_crs"] = cf.source_crs
                props["_target_crs"] = cf.target_crs
                props["_dataset_name"] = dataset.name
                props["_dataset_id"] = str(dataset.id)
                geojson_features.append(
                    GeoJSONFeature(
                        id=str(cf.id),
                        geometry=geom_dict,
                        properties=props,
                    )
                )

        return GeoJSONFeatureCollection(
            features=geojson_features,
            total=len(geojson_features),
            crs={"type": "name", "properties": {"name": dataset.detected_crs or "EPSG:4326"}},
        )

    @classmethod
    async def get_project_layers(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> ProjectLayersResponse:
        """
        Retrieves all active dataset spatial layers in a project with extents and layer metadata.
        """
        project = await db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project with ID '{project_id}' not found.")

        datasets, _ = await cls.list_datasets(db, project_id=project_id, limit=100)
        ready_datasets = [d for d in datasets if d.status == "ready" and d.feature_count > 0]

        layers: List[ProjectLayer] = []
        min_x_vals = []
        min_y_vals = []
        max_x_vals = []
        max_y_vals = []

        for idx, ds in enumerate(ready_datasets):
            color = cls.LAYER_COLORS[idx % len(cls.LAYER_COLORS)]
            bbox = BoundingBox(**ds.bounding_box) if ds.bounding_box else None

            if bbox:
                min_x_vals.append(bbox.min_x)
                min_y_vals.append(bbox.min_y)
                max_x_vals.append(bbox.max_x)
                max_y_vals.append(bbox.max_y)

            layers.append(
                ProjectLayer(
                    id=str(ds.id),
                    dataset_id=str(ds.id),
                    name=ds.name,
                    source_format=ds.source_format,
                    geometry_type=ds.geometry_type,
                    feature_count=ds.feature_count,
                    source_crs=ds.detected_crs or "EPSG:4326",
                    target_crs=project.target_crs or "EPSG:4326",
                    bounds=bbox,
                    geojson_url=f"/api/v1/datasets/{ds.id}/features/geojson",
                    color=color,
                )
            )

        combined_bbox = None
        if min_x_vals and min_y_vals and max_x_vals and max_y_vals:
            combined_bbox = BoundingBox(
                min_x=round(float(min(min_x_vals)), 6),
                min_y=round(float(min(min_y_vals)), 6),
                max_x=round(float(max(max_x_vals)), 6),
                max_y=round(float(max(max_y_vals)), 6),
            )

        return ProjectLayersResponse(
            project_id=project.id,
            project_name=project.name,
            target_crs=project.target_crs,
            combined_bounds=combined_bbox,
            layers=layers,
        )

    @classmethod
    async def get_project_combined_geojson(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> GeoJSONFeatureCollection:
        """
        Returns combined GeoJSON FeatureCollection across all active project datasets for map rendering.
        """
        project = await db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project with ID '{project_id}' not found.")

        datasets, _ = await cls.list_datasets(db, project_id=project_id, limit=100)
        ready_datasets = [d for d in datasets if d.status == "ready" and d.feature_count > 0]

        all_features: List[GeoJSONFeature] = []
        for ds in ready_datasets:
            fc = await cls.get_dataset_features_geojson(db, ds.id, representation="canonical")
            all_features.extend(fc.features)

        return GeoJSONFeatureCollection(
            features=all_features,
            total=len(all_features),
            crs={"type": "name", "properties": {"name": project.target_crs or "EPSG:4326"}},
        )

    @classmethod
    async def get_dataset_features(
        cls,
        db: AsyncSession,
        dataset_id: uuid.UUID,
        representation: str = "canonical",
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[FeatureRead], int]:
        """
        Retrieves paginated features (source or canonical) for a dataset.
        """
        dataset = await cls.get_dataset(db, dataset_id)
        if not dataset:
            raise ValueError(f"Dataset with ID '{dataset_id}' not found.")

        if not dataset.versions:
            return [], 0

        latest_version_id = dataset.versions[0].id
        items: List[FeatureRead] = []

        if representation == "source":
            total_stmt = (
                select(func.count())
                .select_from(SourceFeature)
                .where(SourceFeature.dataset_version_id == latest_version_id)
            )
            total = (await db.execute(total_stmt)).scalar() or 0

            stmt = (
                select(SourceFeature)
                .where(SourceFeature.dataset_version_id == latest_version_id)
                .offset(skip)
                .limit(limit)
            )
            result = await db.execute(stmt)
            features = list(result.scalars().all())

            for sf in features:
                items.append(
                    FeatureRead(
                        id=sf.id,
                        dataset_version_id=sf.dataset_version_id,
                        source_feature_id=sf.source_feature_id,
                        geometry_type=sf.geometry_type,
                        properties=sf.properties,
                        source_crs=sf.source_crs,
                        target_crs=None,
                        created_at=sf.created_at,
                    )
                )
        else:
            total_stmt = (
                select(func.count())
                .select_from(CanonicalFeature)
                .where(CanonicalFeature.dataset_version_id == latest_version_id)
            )
            total = (await db.execute(total_stmt)).scalar() or 0

            stmt = (
                select(CanonicalFeature)
                .where(CanonicalFeature.dataset_version_id == latest_version_id)
                .offset(skip)
                .limit(limit)
            )
            result = await db.execute(stmt)
            features = list(result.scalars().all())

            for cf in features:
                items.append(
                    FeatureRead(
                        id=cf.id,
                        dataset_version_id=cf.dataset_version_id,
                        source_feature_id=str(cf.source_feature_id),
                        geometry_type=cf.geometry_type,
                        properties=cf.canonical_properties,
                        source_crs=cf.source_crs,
                        target_crs=cf.target_crs,
                        created_at=cf.created_at,
                    )
                )

        return items, total
