import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Project
from app.models.dataset import Dataset, DatasetVersion
from app.models.feature import CanonicalFeature
from app.models.unified import UnifiedLandRecord, UnifiedLandRecordSource
from app.models.conflict import AttributeConflict, ConflictResolution
from app.models.provenance import ProvenanceEvent
from app.models.matching import FeatureMatch, MatchReview
from app.schemas.assistant import SemanticDocumentCategory


class DocumentBuilder:
    """
    Transforms structured LandSync database entities into rich,
    searchable text documents suitable for semantic embedding and RAG.
    """

    @classmethod
    def build_project_document(cls, project: Project, datasets: List[Dataset], records_count: int, conflicts_count: int) -> Dict[str, Any]:
        content = (
            f"Project: {project.name}\n"
            f"ID: {project.id}\n"
            f"Description: {project.description or 'No description provided'}\n"
            f"Target CRS: {project.target_crs}\n"
            f"Status: {project.status}\n"
            f"Total Ingested Datasets: {len(datasets)}\n"
            f"Datasets: {', '.join([d.name for d in datasets]) if datasets else 'None'}\n"
            f"Total Unified Land Records: {records_count}\n"
            f"Total Attribute Conflicts: {conflicts_count}\n"
        )
        return {
            "document_category": SemanticDocumentCategory.PROJECT.value,
            "entity_id": str(project.id),
            "title": f"Project Overview: {project.name}",
            "content": content,
            "metadata": {
                "project_id": str(project.id),
                "target_crs": project.target_crs,
                "dataset_count": len(datasets),
            },
        }

    @classmethod
    def build_dataset_document(cls, dataset: Dataset, project_id: uuid.UUID) -> Dict[str, Any]:
        content = (
            f"Dataset: {dataset.name}\n"
            f"Dataset ID: {dataset.id}\n"
            f"Source Format: {dataset.source_format}\n"
            f"Detected CRS: {dataset.detected_crs or 'Unknown'}\n"
            f"Geometry Type: {dataset.geometry_type or 'Unknown'}\n"
            f"Feature Count: {dataset.feature_count or 0}\n"
            f"Source Filename: {dataset.source_filename or 'N/A'}\n"
        )
        return {
            "document_category": SemanticDocumentCategory.DATASET.value,
            "entity_id": str(dataset.id),
            "title": f"Dataset: {dataset.name} ({dataset.source_format.upper()})",
            "content": content,
            "metadata": {
                "project_id": str(project_id),
                "dataset_id": str(dataset.id),
                "geometry_type": dataset.geometry_type,
            },
        }

    @classmethod
    def build_unified_record_document(cls, record: UnifiedLandRecord) -> Dict[str, Any]:
        attrs = record.canonical_attributes or {}
        sources_summary = []
        for s in (record.sources or []):
            feat_id = str(s.feature_id)[:8] if s.feature_id else "unknown"
            sources_summary.append(f"{s.source_role} (Feature: {feat_id})")

        content = (
            f"Unified Land Record: {record.record_identifier}\n"
            f"Record ID: {record.id}\n"
            f"Harmonization Status: {record.status}\n"
            f"Canonical Area: {f'{record.area:,.1f} sq meters' if record.area else 'Not calculated'}\n"
            f"Authoritative Geometry Source Role: {record.geometry_source_role}\n"
            f"Primary Land Use: {attrs.get('land_use', 'Unspecified')}\n"
            f"Recorded Address: {attrs.get('address', 'Unspecified')}\n"
            f"Zoning: {attrs.get('zoning', 'Unspecified')}\n"
            f"Owner: {attrs.get('owner', 'Unspecified')}\n"
            f"Contributing Source Features ({len(record.sources or [])}): {', '.join(sources_summary) if sources_summary else 'None'}\n"
        )
        return {
            "document_category": SemanticDocumentCategory.UNIFIED_RECORD.value,
            "entity_id": record.record_identifier,
            "title": f"Unified Land Record: {record.record_identifier} ({record.status})",
            "content": content,
            "metadata": {
                "project_id": str(record.project_id),
                "record_id": str(record.id),
                "record_identifier": record.record_identifier,
                "status": record.status,
                "land_use": attrs.get("land_use"),
            },
        }

    @classmethod
    def build_conflict_document(cls, conflict: AttributeConflict, record_ident: Optional[str] = None) -> Dict[str, Any]:
        val_lines = []
        for dv in (conflict.detected_values or []):
            val_lines.append(f"  - {dv.get('source_role')} ({dv.get('dataset_name')}): {dv.get('value')}")

        resolution_summary = "Unresolved"
        if conflict.status == "RESOLVED" and conflict.resolution:
            res = conflict.resolution
            resolution_summary = f"Resolved to '{res.resolved_value}' via {res.resolution_type} by {res.resolved_by or 'Reviewer'} (Note: {res.comment})"
        elif conflict.status == "DISMISSED":
            dismissal = conflict.resolution.comment if conflict.resolution else "Variance within tolerable limits"
            resolution_summary = f"Dismissed as non-actionable variance: {dismissal}"

        content = (
            f"Attribute Conflict: {conflict.attribute_name}\n"
            f"Conflict ID: {conflict.id}\n"
            f"Associated Unified Record: {record_ident or str(conflict.unified_land_record_id)}\n"
            f"Conflict Type: {conflict.conflict_type}\n"
            f"Severity Tier: {conflict.severity}\n"
            f"Status: {conflict.status}\n"
            f"Contributing Values Disagreement:\n"
            + "\n".join(val_lines) + "\n"
            f"Resolution Audit: {resolution_summary}\n"
        )
        return {
            "document_category": SemanticDocumentCategory.CONFLICT.value,
            "entity_id": f"{record_ident or conflict.unified_land_record_id}:{conflict.attribute_name}",
            "title": f"Conflict on {conflict.attribute_name} [{conflict.status}] ({conflict.severity} Severity)",
            "content": content,
            "metadata": {
                "project_id": str(conflict.project_id),
                "conflict_id": str(conflict.id),
                "attribute_name": conflict.attribute_name,
                "severity": conflict.severity,
                "status": conflict.status,
            },
        }

    @classmethod
    def build_provenance_document(cls, record_ident: str, record_id: uuid.UUID, project_id: uuid.UUID, events: List[ProvenanceEvent]) -> Dict[str, Any]:
        lines = [f"Provenance Audit Trail for Unified Record {record_ident} (ID: {record_id}):"]
        for idx, ev in enumerate(events, 1):
            ts = ev.created_at.strftime("%Y-%m-%d %H:%M:%S") if ev.created_at else "Unknown"
            title = ev.event_metadata.get("title", ev.event_type.replace("_", " ").title())
            desc = ev.event_metadata.get("description", "")
            lines.append(f"{idx}. [{ts}] {title} ({ev.event_type}): {desc}")

        content = "\n".join(lines)
        return {
            "document_category": SemanticDocumentCategory.PROVENANCE.value,
            "entity_id": record_ident,
            "title": f"Provenance Trail: {record_ident} ({len(events)} Lifecycle Events)",
            "content": content,
            "metadata": {
                "project_id": str(project_id),
                "record_id": str(record_id),
                "events_count": len(events),
            },
        }
