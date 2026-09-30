import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from shapely.geometry import mapping
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from collections import defaultdict
from app.models.project import Project
from app.models.dataset import Dataset, DatasetVersion
from app.models.feature import CanonicalFeature
from app.models.unified import UnifiedLandRecord, UnifiedLandRecordSource
from app.models.conflict import AttributeConflict
from app.models.provenance import ProvenanceEvent
from app.services.dataset import extract_shapely_geom
from app.services.provenance.service import extract_feature_display_id


class ExportService:
    """
    Service responsible for streaming and serializing Unified Land Records into
    standard GeoJSON (RFC 7946) and CSV formats with full metadata and provenance attribution.
    Enforces strict project ownership and isolation.
    """

    @classmethod
    async def export_project_geojson(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Exports all unified records for a project as a standard GeoJSON FeatureCollection.
        Geometry is the authoritative canonical geometry in EPSG:4326.
        """
        # Validate project exists
        project = await db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project with ID '{project_id}' not found.")

        # Query all unified records for this project
        stmt = (
            select(UnifiedLandRecord)
            .where(UnifiedLandRecord.project_id == project_id)
            .options(
                selectinload(UnifiedLandRecord.sources)
                .joinedload(UnifiedLandRecordSource.feature)
                .joinedload(CanonicalFeature.dataset_version)
                .joinedload(DatasetVersion.dataset),
                joinedload(UnifiedLandRecord.geometry_source_feature),
            )
            .order_by(UnifiedLandRecord.record_identifier.asc())
        )
        records = list((await db.execute(stmt)).scalars().all())

        # Batch query conflicts for this project
        conflict_stmt = (
            select(AttributeConflict)
            .where(AttributeConflict.project_id == project_id)
        )
        all_conflicts = list((await db.execute(conflict_stmt)).scalars().all())
        conflicts_by_record = defaultdict(list)
        for c in all_conflicts:
            conflicts_by_record[c.unified_land_record_id].append(c)

        features_geojson: List[Dict[str, Any]] = []

        for r in records:
            geom_dict = None
            if r.canonical_geometry:
                sh_geom = extract_shapely_geom(r.canonical_geometry)
                if sh_geom and not sh_geom.is_empty:
                    geom_dict = mapping(sh_geom)

            # Sources info
            source_roles: List[str] = []
            dataset_names: List[str] = []
            source_identifiers: List[str] = []

            for s in r.sources:
                if s.source_role not in source_roles:
                    source_roles.append(s.source_role)
                cf = s.feature
                if cf:
                    disp_id = extract_feature_display_id(cf) or str(cf.id)[:8]
                    source_identifiers.append(disp_id)
                    if cf.dataset_version and cf.dataset_version.dataset:
                        ds_name = cf.dataset_version.dataset.name
                        if ds_name not in dataset_names:
                            dataset_names.append(ds_name)

            canon_attr = r.canonical_attributes or {}
            conflicts = canon_attr.get("conflicts", [])
            rec_conflicts = conflicts_by_record.get(r.id, [])
            unresolved_count = sum(1 for c in rec_conflicts if c.status == "UNRESOLVED")
            resolved_count = sum(1 for c in rec_conflicts if c.status == "RESOLVED")
            dismissed_count = sum(1 for c in rec_conflicts if c.status == "DISMISSED")
            conflict_status = (
                "UNRESOLVED_CONFLICTS" if unresolved_count > 0
                else "RESOLVED" if (resolved_count > 0 or dismissed_count > 0)
                else "NO_CONFLICTS"
            )
            total_conflict_count = len(rec_conflicts) if rec_conflicts else len(conflicts)

            feature_obj = {
                "type": "Feature",
                "id": r.record_identifier,
                "geometry": geom_dict,
                "properties": {
                    "id": str(r.id),
                    "record_identifier": r.record_identifier,
                    "status": r.status,
                    "area_sqm": r.area,
                    "geometry_source_role": r.geometry_source_role,
                    "geometry_source_feature_id": str(r.geometry_source_feature_id) if r.geometry_source_feature_id else None,
                    "source_count": len(r.sources),
                    "source_roles": source_roles,
                    "source_datasets": dataset_names,
                    "source_feature_identifiers": source_identifiers,
                    "land_use": canon_attr.get("land_use"),
                    "address": canon_attr.get("address"),
                    "conflict_count": total_conflict_count,
                    "unresolved_conflict_count": unresolved_count,
                    "resolved_conflict_count": resolved_count,
                    "conflict_status": conflict_status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                },
            }
            features_geojson.append(feature_obj)

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"landsync-unified-records-{date_str}.geojson"

        # Record audit event
        audit_event = ProvenanceEvent(
            project_id=project.id,
            unified_land_record_id=None,
            event_type="EXPORT_CREATED",
            source_type="PROJECT_EXPORT",
            source_id=project.id,
            event_metadata={
                "export_format": "geojson",
                "record_count": len(features_geojson),
                "filename": filename,
            },
        )
        db.add(audit_event)
        await db.commit()

        feature_collection = {
            "type": "FeatureCollection",
            "metadata": {
                "project_id": str(project.id),
                "project_name": project.name,
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "landsync_version": "0.1.0",
                "crs": "EPSG:4326",
                "record_count": len(features_geojson),
            },
            "features": features_geojson,
        }

        return feature_collection, filename

    @classmethod
    async def export_project_csv(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> Tuple[str, str]:
        """
        Exports all unified records for a project as CSV with provenance columns.
        """
        project = await db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project with ID '{project_id}' not found.")

        stmt = (
            select(UnifiedLandRecord)
            .where(UnifiedLandRecord.project_id == project_id)
            .options(
                selectinload(UnifiedLandRecord.sources)
                .joinedload(UnifiedLandRecordSource.feature)
                .joinedload(CanonicalFeature.dataset_version)
                .joinedload(DatasetVersion.dataset),
            )
            .order_by(UnifiedLandRecord.record_identifier.asc())
        )
        records = list((await db.execute(stmt)).scalars().all())

        # Batch query conflicts for this project
        conflict_stmt = (
            select(AttributeConflict)
            .where(AttributeConflict.project_id == project_id)
        )
        all_conflicts = list((await db.execute(conflict_stmt)).scalars().all())
        conflicts_by_record = defaultdict(list)
        for c in all_conflicts:
            conflicts_by_record[c.unified_land_record_id].append(c)

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        headers = [
            "record_identifier",
            "status",
            "area_sqm",
            "geometry_source_role",
            "geometry_source_feature_id",
            "source_count",
            "source_roles",
            "source_datasets",
            "source_feature_ids",
            "land_use",
            "address",
            "conflict_count",
            "unresolved_conflict_count",
            "resolved_conflict_count",
            "conflict_status",
            "accepted_match_count",
            "created_at",
            "updated_at",
        ]
        writer.writerow(headers)

        for r in records:
            source_roles: List[str] = []
            dataset_names: List[str] = []
            source_fids: List[str] = []
            accepted_match_count = 0

            for s in r.sources:
                if s.source_role not in source_roles:
                    source_roles.append(s.source_role)
                if s.feature_match_id:
                    accepted_match_count += 1
                cf = s.feature
                if cf:
                    disp_id = extract_feature_display_id(cf) or str(cf.id)
                    source_fids.append(disp_id)
                    if cf.dataset_version and cf.dataset_version.dataset:
                        ds_name = cf.dataset_version.dataset.name
                        if ds_name not in dataset_names:
                            dataset_names.append(ds_name)

            canon_attr = r.canonical_attributes or {}
            conflicts = canon_attr.get("conflicts", [])
            rec_conflicts = conflicts_by_record.get(r.id, [])
            unresolved_count = sum(1 for c in rec_conflicts if c.status == "UNRESOLVED")
            resolved_count = sum(1 for c in rec_conflicts if c.status == "RESOLVED")
            dismissed_count = sum(1 for c in rec_conflicts if c.status == "DISMISSED")
            conflict_status = (
                "UNRESOLVED_CONFLICTS" if unresolved_count > 0
                else "RESOLVED" if (resolved_count > 0 or dismissed_count > 0)
                else "NO_CONFLICTS"
            )
            total_conflict_count = len(rec_conflicts) if rec_conflicts else len(conflicts)

            row = [
                r.record_identifier,
                r.status,
                r.area if r.area is not None else "",
                r.geometry_source_role or "",
                str(r.geometry_source_feature_id) if r.geometry_source_feature_id else "",
                len(r.sources),
                ";".join(source_roles),
                ";".join(dataset_names),
                ";".join(source_fids),
                canon_attr.get("land_use") or "",
                canon_attr.get("address") or "",
                total_conflict_count,
                unresolved_count,
                resolved_count,
                conflict_status,
                accepted_match_count,
                r.created_at.isoformat() if r.created_at else "",
                r.updated_at.isoformat() if r.updated_at else "",
            ]
            writer.writerow(row)

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"landsync-unified-records-{date_str}.csv"

        # Record audit event
        audit_event = ProvenanceEvent(
            project_id=project.id,
            unified_land_record_id=None,
            event_type="EXPORT_CREATED",
            source_type="PROJECT_EXPORT",
            source_id=project.id,
            event_metadata={
                "export_format": "csv",
                "record_count": len(records),
                "filename": filename,
            },
        )
        db.add(audit_event)
        await db.commit()

        return output.getvalue(), filename

    @classmethod
    async def export_single_record_geojson(
        cls,
        db: AsyncSession,
        record_id: uuid.UUID,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Exports an individual UnifiedLandRecord as a valid GeoJSON Feature.
        """
        stmt = (
            select(UnifiedLandRecord)
            .where(UnifiedLandRecord.id == record_id)
            .options(
                selectinload(UnifiedLandRecord.sources)
                .joinedload(UnifiedLandRecordSource.feature)
                .joinedload(CanonicalFeature.dataset_version)
                .joinedload(DatasetVersion.dataset),
            )
        )
        record = (await db.execute(stmt)).scalar_one_or_none()
        if not record:
            raise ValueError(f"Unified land record with ID '{record_id}' not found.")

        geom_dict = None
        if record.canonical_geometry:
            sh_geom = extract_shapely_geom(record.canonical_geometry)
            if sh_geom and not sh_geom.is_empty:
                geom_dict = mapping(sh_geom)

        source_roles: List[str] = []
        dataset_names: List[str] = []
        source_identifiers: List[str] = []

        for s in record.sources:
            if s.source_role not in source_roles:
                source_roles.append(s.source_role)
            cf = s.feature
            if cf:
                disp_id = extract_feature_display_id(cf) or str(cf.id)[:8]
                source_identifiers.append(disp_id)
                if cf.dataset_version and cf.dataset_version.dataset:
                    ds_name = cf.dataset_version.dataset.name
                    if ds_name not in dataset_names:
                        dataset_names.append(ds_name)

        canon_attr = record.canonical_attributes or {}
        conflicts = canon_attr.get("conflicts", [])

        # Query conflicts for this record
        conflict_stmt = (
            select(AttributeConflict)
            .where(AttributeConflict.unified_land_record_id == record.id)
        )
        rec_conflicts = list((await db.execute(conflict_stmt)).scalars().all())
        unresolved_count = sum(1 for c in rec_conflicts if c.status == "UNRESOLVED")
        resolved_count = sum(1 for c in rec_conflicts if c.status == "RESOLVED")
        dismissed_count = sum(1 for c in rec_conflicts if c.status == "DISMISSED")
        conflict_status = (
            "UNRESOLVED_CONFLICTS" if unresolved_count > 0
            else "RESOLVED" if (resolved_count > 0 or dismissed_count > 0)
            else "NO_CONFLICTS"
        )
        total_conflict_count = len(rec_conflicts) if rec_conflicts else len(conflicts)

        feature_obj = {
            "type": "Feature",
            "id": record.record_identifier,
            "geometry": geom_dict,
            "properties": {
                "id": str(record.id),
                "project_id": str(record.project_id),
                "record_identifier": record.record_identifier,
                "status": record.status,
                "area_sqm": record.area,
                "geometry_source_role": record.geometry_source_role,
                "geometry_source_feature_id": str(record.geometry_source_feature_id) if record.geometry_source_feature_id else None,
                "source_count": len(record.sources),
                "source_roles": source_roles,
                "source_datasets": dataset_names,
                "source_feature_identifiers": source_identifiers,
                "land_use": canon_attr.get("land_use"),
                "address": canon_attr.get("address"),
                "conflict_count": total_conflict_count,
                "unresolved_conflict_count": unresolved_count,
                "resolved_conflict_count": resolved_count,
                "conflict_status": conflict_status,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "updated_at": record.updated_at.isoformat() if record.updated_at else None,
            },
        }

        filename = f"landsync-{record.record_identifier}.geojson"

        # Record audit event
        audit_event = ProvenanceEvent(
            project_id=record.project_id,
            unified_land_record_id=record.id,
            event_type="EXPORT_CREATED",
            source_type="RECORD_EXPORT",
            source_id=record.id,
            event_metadata={
                "export_format": "geojson",
                "record_identifier": record.record_identifier,
                "filename": filename,
            },
        )
        db.add(audit_event)
        await db.commit()

        return feature_obj, filename

    @classmethod
    async def export_single_record_csv(
        cls,
        db: AsyncSession,
        record_id: uuid.UUID,
    ) -> Tuple[str, str]:
        """
        Exports an individual UnifiedLandRecord as CSV.
        """
        stmt = (
            select(UnifiedLandRecord)
            .where(UnifiedLandRecord.id == record_id)
            .options(
                selectinload(UnifiedLandRecord.sources)
                .joinedload(UnifiedLandRecordSource.feature)
                .joinedload(CanonicalFeature.dataset_version)
                .joinedload(DatasetVersion.dataset),
            )
        )
        record = (await db.execute(stmt)).scalar_one_or_none()
        if not record:
            raise ValueError(f"Unified land record with ID '{record_id}' not found.")

        # Query conflicts for this record
        conflict_stmt = (
            select(AttributeConflict)
            .where(AttributeConflict.unified_land_record_id == record.id)
        )
        rec_conflicts = list((await db.execute(conflict_stmt)).scalars().all())
        unresolved_count = sum(1 for c in rec_conflicts if c.status == "UNRESOLVED")
        resolved_count = sum(1 for c in rec_conflicts if c.status == "RESOLVED")
        dismissed_count = sum(1 for c in rec_conflicts if c.status == "DISMISSED")
        conflict_status = (
            "UNRESOLVED_CONFLICTS" if unresolved_count > 0
            else "RESOLVED" if (resolved_count > 0 or dismissed_count > 0)
            else "NO_CONFLICTS"
        )

        output = io.StringIO()
        writer = csv.writer(output)

        headers = [
            "record_identifier",
            "status",
            "area_sqm",
            "geometry_source_role",
            "geometry_source_feature_id",
            "source_count",
            "source_roles",
            "source_datasets",
            "source_feature_ids",
            "land_use",
            "address",
            "conflict_count",
            "unresolved_conflict_count",
            "resolved_conflict_count",
            "conflict_status",
            "accepted_match_count",
            "created_at",
            "updated_at",
        ]
        writer.writerow(headers)

        source_roles: List[str] = []
        dataset_names: List[str] = []
        source_fids: List[str] = []
        accepted_match_count = 0

        for s in record.sources:
            if s.source_role not in source_roles:
                source_roles.append(s.source_role)
            if s.feature_match_id:
                accepted_match_count += 1
            cf = s.feature
            if cf:
                disp_id = extract_feature_display_id(cf) or str(cf.id)
                source_fids.append(disp_id)
                if cf.dataset_version and cf.dataset_version.dataset:
                    ds_name = cf.dataset_version.dataset.name
                    if ds_name not in dataset_names:
                        dataset_names.append(ds_name)

        canon_attr = record.canonical_attributes or {}
        conflicts = canon_attr.get("conflicts", [])
        total_conflict_count = len(rec_conflicts) if rec_conflicts else len(conflicts)

        row = [
            record.record_identifier,
            record.status,
            record.area if record.area is not None else "",
            record.geometry_source_role or "",
            str(record.geometry_source_feature_id) if record.geometry_source_feature_id else "",
            len(record.sources),
            ";".join(source_roles),
            ";".join(dataset_names),
            ";".join(source_fids),
            canon_attr.get("land_use") or "",
            canon_attr.get("address") or "",
            total_conflict_count,
            unresolved_count,
            resolved_count,
            conflict_status,
            accepted_match_count,
            record.created_at.isoformat() if record.created_at else "",
            record.updated_at.isoformat() if record.updated_at else "",
        ]
        writer.writerow(row)

        filename = f"landsync-{record.record_identifier}.csv"

        # Record audit event
        audit_event = ProvenanceEvent(
            project_id=record.project_id,
            unified_land_record_id=record.id,
            event_type="EXPORT_CREATED",
            source_type="RECORD_EXPORT",
            source_id=record.id,
            event_metadata={
                "export_format": "csv",
                "record_identifier": record.record_identifier,
                "filename": filename,
            },
        )
        db.add(audit_event)
        await db.commit()

        return output.getvalue(), filename
