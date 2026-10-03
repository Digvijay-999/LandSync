import csv
import io
import json
import os
import hashlib
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, status
from shapely.geometry import mapping
import geopandas as gpd
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from collections import defaultdict
from app.models.project import Project
from app.models.dataset import Dataset, DatasetVersion
from app.models.feature import CanonicalFeature
from app.models.unified import UnifiedLandRecord, UnifiedLandRecordSource
from app.models.conflict import AttributeConflict
from app.models.provenance import ProvenanceEvent, ProvenanceRecord
from app.models.pipeline import PipelineStageExecution
from app.models.export import ExportJob
from app.schemas.export import (
    ExportCreateRequest,
    ExportJobItem,
    ExportJobListResponse,
    ExportManifestResponse,
    Stage14ExecutionResponse,
    Stage14StatusResponse,
)
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

    # =========================================================================
    # STAGE 14: AUTHORITATIVE EXPORTS & DELIVERABLES
    # =========================================================================

    @classmethod
    def _compute_sha256(cls, filepath: str) -> str:
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def _job_to_schema(cls, job: ExportJob) -> ExportJobItem:
        return ExportJobItem(
            id=job.id,
            project_id=job.project_id,
            format=job.format,
            status=job.status,
            filename=job.filename,
            file_size_bytes=job.file_size_bytes,
            record_count=job.record_count,
            authoritative_count=job.authoritative_count,
            quarantined_count=job.quarantined_count,
            include_quarantined=job.include_quarantined,
            crs=job.crs,
            sha256_checksum=job.sha256_checksum,
            manifest_data=job.manifest_data or {},
            download_url=f"/api/v1/projects/{job.project_id}/exports/{job.id}/download",
            error_message=job.error_message,
            created_at=job.created_at,
            completed_at=job.completed_at,
        )

    @classmethod
    async def get_stage14_status(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> Stage14StatusResponse:
        """
        Returns live readiness, metrics, counts, and history for Stage 14 Export.
        """
        project = await db.get(Project, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found.",
            )

        # Check Stage 12 and Stage 13 executions
        s12_stmt = (
            select(PipelineStageExecution)
            .where(
                PipelineStageExecution.project_id == project_id,
                PipelineStageExecution.stage_number == 12,
                PipelineStageExecution.status == "completed",
            )
            .order_by(desc(PipelineStageExecution.created_at))
        )
        stage12_exec = (await db.execute(s12_stmt)).scalars().first()

        s13_stmt = (
            select(PipelineStageExecution)
            .where(
                PipelineStageExecution.project_id == project_id,
                PipelineStageExecution.stage_number == 13,
                PipelineStageExecution.status == "completed",
            )
            .order_by(desc(PipelineStageExecution.created_at))
        )
        stage13_exec = (await db.execute(s13_stmt)).scalars().first()

        # Query ULR records counts
        total_q = (
            select(func.count())
            .select_from(UnifiedLandRecord)
            .where(UnifiedLandRecord.project_id == project_id)
        )
        total_count = (await db.execute(total_q)).scalar() or 0

        auth_q = (
            select(func.count())
            .select_from(UnifiedLandRecord)
            .where(
                UnifiedLandRecord.project_id == project_id,
                UnifiedLandRecord.resolution_status == "UNIFIED",
            )
        )
        auth_count = (await db.execute(auth_q)).scalar() or 0

        quar_q = (
            select(func.count())
            .select_from(UnifiedLandRecord)
            .where(
                UnifiedLandRecord.project_id == project_id,
                UnifiedLandRecord.resolution_status == "REJECTED",
            )
        )
        quar_count = (await db.execute(quar_q)).scalar() or 0

        geom_q = (
            select(func.count())
            .select_from(UnifiedLandRecord)
            .where(
                UnifiedLandRecord.project_id == project_id,
                UnifiedLandRecord.canonical_geometry.isnot(None),
            )
        )
        valid_geom_count = (await db.execute(geom_q)).scalar() or 0

        # Provenance coverage
        prov_q = (
            select(func.count())
            .select_from(ProvenanceRecord)
            .where(ProvenanceRecord.project_id == project_id)
        )
        prov_count = (await db.execute(prov_q)).scalar() or 0
        prov_coverage = (
            round((prov_count / total_count * 100.0), 1)
            if total_count > 0
            else 0.0
        )

        # Check Stage 14 execution
        s14_stmt = (
            select(PipelineStageExecution)
            .where(
                PipelineStageExecution.project_id == project_id,
                PipelineStageExecution.stage_number == 14,
                PipelineStageExecution.status == "completed",
            )
            .order_by(desc(PipelineStageExecution.created_at))
        )
        stage14_exec = (await db.execute(s14_stmt)).scalars().first()

        prereqs_met = bool(
            (stage12_exec or auth_count > 0)
            and (stage13_exec or prov_count > 0)
        )
        prereq_msg = (
            None
            if prereqs_met
            else "Requires Stage 12 Unified Record and Stage 13 Provenance to be completed first."
        )

        if stage14_exec:
            status_val = "completed"
        elif prereqs_met:
            status_val = "ready"
        else:
            status_val = "disabled"

        # Recent exports
        exp_stmt = (
            select(ExportJob)
            .where(ExportJob.project_id == project_id)
            .order_by(desc(ExportJob.created_at))
            .limit(10)
        )
        recent_jobs = list((await db.execute(exp_stmt)).scalars().all())

        return Stage14StatusResponse(
            status=status_val,
            prerequisites_met=prereqs_met,
            prerequisites_message=prereq_msg,
            authoritative_records_count=auth_count,
            quarantined_records_count=quar_count,
            total_records_count=total_count,
            valid_geometry_count=valid_geom_count,
            provenance_coverage_pct=prov_coverage,
            project_crs="EPSG:4326",
            available_formats=["geojson", "gpkg", "csv"],
            recent_exports=[cls._job_to_schema(j) for j in recent_jobs],
            last_run_at=stage14_exec.completed_at if stage14_exec else None,
        )

    @classmethod
    async def create_export_job(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        req: ExportCreateRequest,
    ) -> ExportJobItem:
        """
        Generates authoritative geospatial deliverables (GeoJSON, CSV, GeoPackage)
        and defensible metadata manifest from Stage 12 ULR and Stage 13 Provenance.
        """
        project = await db.get(Project, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found.",
            )

        fmt = req.format.strip().lower()
        if fmt not in ["geojson", "csv", "gpkg"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported export format '{req.format}'. Supported formats: geojson, csv, gpkg.",
            )

        # Prerequisite checks
        s12_stmt = (
            select(PipelineStageExecution)
            .where(
                PipelineStageExecution.project_id == project_id,
                PipelineStageExecution.stage_number == 12,
                PipelineStageExecution.status == "completed",
            )
            .order_by(desc(PipelineStageExecution.created_at))
        )
        stage12_exec = (await db.execute(s12_stmt)).scalars().first()

        s13_stmt = (
            select(PipelineStageExecution)
            .where(
                PipelineStageExecution.project_id == project_id,
                PipelineStageExecution.stage_number == 13,
                PipelineStageExecution.status == "completed",
            )
            .order_by(desc(PipelineStageExecution.created_at))
        )
        stage13_exec = (await db.execute(s13_stmt)).scalars().first()

        auth_q = (
            select(func.count())
            .select_from(UnifiedLandRecord)
            .where(
                UnifiedLandRecord.project_id == project_id,
                UnifiedLandRecord.resolution_status == "UNIFIED",
            )
        )
        auth_count = (await db.execute(auth_q)).scalar() or 0

        quar_q = (
            select(func.count())
            .select_from(UnifiedLandRecord)
            .where(
                UnifiedLandRecord.project_id == project_id,
                UnifiedLandRecord.resolution_status == "REJECTED",
            )
        )
        quar_count = (await db.execute(quar_q)).scalar() or 0

        if not stage12_exec and auth_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prerequisite not met: Stage 12 Unified Land Record must be completed prior to exporting.",
            )
        if not stage13_exec:
            prov_exist = (
                await db.execute(
                    select(func.count())
                    .select_from(ProvenanceRecord)
                    .where(ProvenanceRecord.project_id == project_id)
                )
            ).scalar() or 0
            if prov_exist == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Prerequisite not met: Stage 13 Provenance must be completed prior to exporting.",
                )

        # Query ULR records
        ulr_stmt = select(UnifiedLandRecord).where(
            UnifiedLandRecord.project_id == project_id
        )
        if not req.include_quarantined:
            ulr_stmt = ulr_stmt.where(UnifiedLandRecord.resolution_status == "UNIFIED")

        ulr_stmt = ulr_stmt.options(
            selectinload(UnifiedLandRecord.sources)
        ).order_by(UnifiedLandRecord.record_identifier.asc())

        records = list((await db.execute(ulr_stmt)).scalars().all())

        # Provenance lookup
        prov_stmt = select(ProvenanceRecord).where(ProvenanceRecord.project_id == project_id)
        prov_records = list((await db.execute(prov_stmt)).scalars().all())
        prov_map = {p.unified_land_record_id: p for p in prov_records}

        # Setup storage directory
        base_storage_dir = os.environ.get(
            "EXPORT_STORAGE_PATH",
            os.path.join(tempfile.gettempdir(), "landsync_exports"),
        )
        project_export_dir = os.path.join(base_storage_dir, str(project_id))
        os.makedirs(project_export_dir, exist_ok=True)

        job_id = uuid.uuid4()
        now_dt = datetime.now(timezone.utc)
        date_str = now_dt.strftime("%Y%m%d_%H%M%S")
        project_slug = "".join(c if c.isalnum() else "_" for c in project.name.lower())
        mode_str = "full" if req.include_quarantined else "authoritative"
        base_filename = f"landsync_{project_slug}_{mode_str}_{date_str}_{str(job_id)[:8]}"
        filename = f"{base_filename}.{fmt}"
        file_path = os.path.join(project_export_dir, filename)

        # Deliverable generation
        if fmt == "geojson":
            features = []
            for r in records:
                geom_dict = None
                if r.canonical_geometry:
                    sh_geom = extract_shapely_geom(r.canonical_geometry)
                    if sh_geom and not sh_geom.is_empty:
                        geom_dict = mapping(sh_geom)

                prov = prov_map.get(r.id)
                feat = {
                    "type": "Feature",
                    "id": r.record_identifier,
                    "geometry": geom_dict,
                    "properties": {
                        "unified_record_id": str(r.id),
                        "parcel_id": r.record_identifier,
                        "record_identifier": r.record_identifier,
                        "harmonized_record_id": r.harmonized_record_id,
                        "source_a_reference": r.source_a_reference,
                        "source_b_reference": r.source_b_reference,
                        "geometry_source": r.geometry_source,
                        "land_use": r.land_use,
                        "mutation_status": r.mutation_status,
                        "risk_level": r.risk_level,
                        "area_m2": r.area,
                        "confidence_score": r.confidence_score,
                        "validation_status": r.validation_status,
                        "human_review_decision": r.human_review_decision,
                        "resolution_status": r.resolution_status,
                        "provenance_id": str(prov.id) if prov else None,
                        "source_count": len(r.sources) if r.sources else 0,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    },
                }
                features.append(feat)

            geojson_payload = {
                "type": "FeatureCollection",
                "metadata": {
                    "project_id": str(project.id),
                    "project_name": project.name,
                    "export_id": str(job_id),
                    "export_timestamp": now_dt.isoformat(),
                    "crs": "EPSG:4326",
                    "pipeline_version": "1.0.0",
                    "record_count": len(features),
                    "authoritative_records": auth_count,
                    "quarantined_records": quar_count,
                    "include_quarantined": req.include_quarantined,
                },
                "features": features,
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(geojson_payload, f, indent=2)

        elif fmt == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            headers = [
                "unified_record_id",
                "parcel_id",
                "record_identifier",
                "harmonized_record_id",
                "source_a_reference",
                "source_b_reference",
                "geometry_source",
                "land_use",
                "mutation_status",
                "risk_level",
                "area_m2",
                "confidence_score",
                "validation_status",
                "human_review_decision",
                "resolution_status",
                "provenance_id",
                "centroid_latitude",
                "centroid_longitude",
                "created_at",
            ]
            writer.writerow(headers)

            for r in records:
                prov = prov_map.get(r.id)
                c_lat = ""
                c_lon = ""
                if r.canonical_geometry:
                    sh_geom = extract_shapely_geom(r.canonical_geometry)
                    if sh_geom and not sh_geom.is_empty:
                        c_lat = str(round(sh_geom.centroid.y, 7))
                        c_lon = str(round(sh_geom.centroid.x, 7))

                writer.writerow([
                    str(r.id),
                    r.record_identifier,
                    r.record_identifier,
                    r.harmonized_record_id or "",
                    r.source_a_reference or "",
                    r.source_b_reference or "",
                    r.geometry_source or "",
                    r.land_use or "",
                    r.mutation_status or "",
                    r.risk_level or "",
                    r.area if r.area is not None else "",
                    r.confidence_score if r.confidence_score is not None else "",
                    r.validation_status or "",
                    r.human_review_decision or "",
                    r.resolution_status or "UNIFIED",
                    str(prov.id) if prov else "",
                    c_lat,
                    c_lon,
                    r.created_at.isoformat() if r.created_at else "",
                ])
            with open(file_path, "w", encoding="utf-8", newline="") as f:
                f.write(output.getvalue())

        elif fmt == "gpkg":
            gpkg_rows = []
            for r in records:
                prov = prov_map.get(r.id)
                sh_geom = None
                if r.canonical_geometry:
                    sh_geom = extract_shapely_geom(r.canonical_geometry)

                gpkg_rows.append({
                    "unified_record_id": str(r.id),
                    "parcel_id": r.record_identifier,
                    "record_identifier": r.record_identifier,
                    "harmonized_record_id": r.harmonized_record_id or "",
                    "source_a_reference": r.source_a_reference or "",
                    "source_b_reference": r.source_b_reference or "",
                    "geometry_source": r.geometry_source or "",
                    "land_use": r.land_use or "",
                    "mutation_status": r.mutation_status or "",
                    "risk_level": r.risk_level or "",
                    "area_m2": float(r.area) if r.area is not None else None,
                    "confidence_score": float(r.confidence_score) if r.confidence_score is not None else None,
                    "validation_status": r.validation_status or "",
                    "human_review_decision": r.human_review_decision or "",
                    "resolution_status": r.resolution_status or "UNIFIED",
                    "provenance_id": str(prov.id) if prov else "",
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                    "geometry": sh_geom,
                })

            gdf = gpd.GeoDataFrame(gpkg_rows, crs="EPSG:4326")
            gdf.to_file(file_path, driver="GPKG", layer="unified_land_records")

        file_size = os.path.getsize(file_path)
        checksum = cls._compute_sha256(file_path)

        manifest_dict = {
            "project_id": str(project.id),
            "project_name": project.name,
            "export_id": str(job_id),
            "export_timestamp": now_dt.isoformat(),
            "export_format": fmt,
            "pipeline_version": "1.0.0",
            "crs": "EPSG:4326",
            "total_records": len(records),
            "authoritative_records": auth_count,
            "quarantined_records": quar_count,
            "include_quarantined": req.include_quarantined,
            "stage12_execution_id": str(stage12_exec.id) if stage12_exec else None,
            "stage13_execution_id": str(stage13_exec.id) if stage13_exec else None,
            "data_generation_timestamp": now_dt.isoformat(),
            "schema_version": "1.0.0",
            "file_name": filename,
            "file_size_bytes": file_size,
            "sha256_checksum": checksum,
        }

        manifest_path = os.path.join(project_export_dir, f"{base_filename}_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_dict, f, indent=2)

        # Persist ExportJob
        job = ExportJob(
            id=job_id,
            project_id=project_id,
            format=fmt,
            status="COMPLETED",
            filename=filename,
            file_path=file_path,
            file_size_bytes=file_size,
            record_count=len(records),
            authoritative_count=auth_count,
            quarantined_count=quar_count,
            include_quarantined=req.include_quarantined,
            crs="EPSG:4326",
            sha256_checksum=checksum,
            manifest_data=manifest_dict,
            created_at=now_dt,
            completed_at=now_dt,
        )
        db.add(job)

        # Provenance audit event
        audit_event = ProvenanceEvent(
            project_id=project.id,
            unified_land_record_id=None,
            event_type="EXPORT_CREATED",
            source_type="PROJECT_EXPORT",
            source_id=project.id,
            event_metadata={
                "export_job_id": str(job_id),
                "export_format": fmt,
                "filename": filename,
                "file_size_bytes": file_size,
                "record_count": len(records),
                "include_quarantined": req.include_quarantined,
                "sha256_checksum": checksum,
            },
        )
        db.add(audit_event)
        await db.commit()
        await db.refresh(job)

        return cls._job_to_schema(job)

    @classmethod
    async def execute_stage_14(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> Stage14ExecutionResponse:
        """
        Executes Pipeline Stage 14: Export.
        Validates Stage 12 and 13 completion, generates authoritative deliverable,
        records Stage 14 completion, and registers audit provenance.
        """
        project = await db.get(Project, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found.",
            )

        # Check Stage 12 and Stage 13 prerequisites
        s12_stmt = (
            select(PipelineStageExecution)
            .where(
                PipelineStageExecution.project_id == project_id,
                PipelineStageExecution.stage_number == 12,
                PipelineStageExecution.status == "completed",
            )
            .order_by(desc(PipelineStageExecution.created_at))
        )
        stage12_exec = (await db.execute(s12_stmt)).scalars().first()

        s13_stmt = (
            select(PipelineStageExecution)
            .where(
                PipelineStageExecution.project_id == project_id,
                PipelineStageExecution.stage_number == 13,
                PipelineStageExecution.status == "completed",
            )
            .order_by(desc(PipelineStageExecution.created_at))
        )
        stage13_exec = (await db.execute(s13_stmt)).scalars().first()

        auth_q = (
            select(func.count())
            .select_from(UnifiedLandRecord)
            .where(
                UnifiedLandRecord.project_id == project_id,
                UnifiedLandRecord.resolution_status == "UNIFIED",
            )
        )
        auth_count = (await db.execute(auth_q)).scalar() or 0

        quar_q = (
            select(func.count())
            .select_from(UnifiedLandRecord)
            .where(
                UnifiedLandRecord.project_id == project_id,
                UnifiedLandRecord.resolution_status == "REJECTED",
            )
        )
        quar_count = (await db.execute(quar_q)).scalar() or 0
        total_count = auth_count + quar_count

        if not stage12_exec and auth_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prerequisite not met: Stage 12 Unified Land Record must be completed prior to Stage 14 Export.",
            )
        if not stage13_exec:
            prov_exist = (
                await db.execute(
                    select(func.count())
                    .select_from(ProvenanceRecord)
                    .where(ProvenanceRecord.project_id == project_id)
                )
            ).scalar() or 0
            if prov_exist == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Prerequisite not met: Stage 13 Provenance must be completed prior to Stage 14 Export.",
                )

        # Generate default authoritative GeoJSON export deliverable
        job_item = await cls.create_export_job(
            db=db,
            project_id=project_id,
            req=ExportCreateRequest(format="geojson", include_quarantined=False),
        )

        # Record or update Stage 14 execution in pipeline_stage_executions
        exec_stmt = select(PipelineStageExecution).where(
            PipelineStageExecution.project_id == project_id,
            PipelineStageExecution.stage_number == 14,
        )
        stage14_exec = (await db.execute(exec_stmt)).scalars().first()

        now_dt = datetime.now(timezone.utc)
        results_summary = {
            "authoritative_records_count": auth_count,
            "quarantined_records_count": quar_count,
            "total_records_count": total_count,
            "default_export_id": str(job_item.id),
            "default_export_format": "geojson",
            "filename": job_item.filename,
            "file_size_bytes": job_item.file_size_bytes,
            "crs": job_item.crs,
            "sha256_checksum": job_item.sha256_checksum,
            "download_url": job_item.download_url,
        }

        if stage14_exec:
            stage14_exec.status = "completed"
            stage14_exec.results = results_summary
            stage14_exec.completed_at = now_dt
            stage14_exec.error_message = None
            execution_id = stage14_exec.id
        else:
            new_exec = PipelineStageExecution(
                id=uuid.uuid4(),
                project_id=project_id,
                stage_number=14,
                stage_id="export",
                status="completed",
                results=results_summary,
                completed_at=now_dt,
            )
            db.add(new_exec)
            execution_id = new_exec.id

        await db.commit()

        return Stage14ExecutionResponse(
            execution_id=execution_id,
            stage_id="export",
            stage_number=14,
            status="completed",
            message="Stage 14 Export successfully completed. Authoritative deliverable generated.",
            authoritative_records_count=auth_count,
            quarantined_records_count=quar_count,
            total_records_count=total_count,
            export_job=job_item,
            executed_at=now_dt,
        )

    @classmethod
    async def list_project_exports(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> ExportJobListResponse:
        """
        Lists all persistent export jobs and deliverables for a project.
        """
        project = await db.get(Project, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found.",
            )
        stmt = (
            select(ExportJob)
            .where(ExportJob.project_id == project_id)
            .order_by(desc(ExportJob.created_at))
        )
        jobs = list((await db.execute(stmt)).scalars().all())
        items = [cls._job_to_schema(j) for j in jobs]
        return ExportJobListResponse(items=items, total=len(items))

    @classmethod
    async def get_export_job_item(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        export_id: uuid.UUID,
    ) -> ExportJobItem:
        """
        Retrieves a single export job by ID.
        """
        stmt = select(ExportJob).where(
            ExportJob.id == export_id,
            ExportJob.project_id == project_id,
        )
        job = (await db.execute(stmt)).scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Export deliverable with ID '{export_id}' not found for this project.",
            )
        return cls._job_to_schema(job)

    @classmethod
    async def download_export_file(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        export_id: uuid.UUID,
    ) -> Tuple[str, str, str]:
        """
        Returns (file_path, filename, media_type) for safe deliverable download.
        Guarantees project isolation and verifies physical file availability.
        """
        stmt = select(ExportJob).where(
            ExportJob.id == export_id,
            ExportJob.project_id == project_id,
        )
        job = (await db.execute(stmt)).scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Export deliverable with ID '{export_id}' not found for this project.",
            )
        if not os.path.exists(job.file_path):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="The requested export file is no longer available on disk.",
            )
        media_types = {
            "geojson": "application/geo+json",
            "csv": "text/csv; charset=utf-8",
            "gpkg": "application/geopackage+sqlite3",
        }
        media_type = media_types.get(job.format.lower(), "application/octet-stream")
        return job.file_path, job.filename, media_type

    @classmethod
    async def get_export_manifest(
        cls,
        db: AsyncSession,
        project_id: uuid.UUID,
        export_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Returns defensible manifest dictionary for an export job.
        """
        stmt = select(ExportJob).where(
            ExportJob.id == export_id,
            ExportJob.project_id == project_id,
        )
        job = (await db.execute(stmt)).scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Export deliverable with ID '{export_id}' not found for this project.",
            )
        return job.manifest_data

