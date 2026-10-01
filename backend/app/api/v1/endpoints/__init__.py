from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.datasets import router as datasets_router
from app.api.v1.endpoints.matching import router as matching_router
from app.api.v1.endpoints.unified import router as unified_router
from app.api.v1.endpoints.provenance import router as provenance_router
from app.api.v1.endpoints.export import router as export_router
from app.api.v1.endpoints.conflict import router as conflict_router
from app.api.v1.endpoints.assistant import router as assistant_router
from app.api.v1.endpoints.spatial_analysis import router as spatial_analysis_router
from app.api.v1.endpoints.pipeline import router as pipeline_router

__all__ = [
    "health_router",
    "projects_router",
    "datasets_router",
    "matching_router",
    "unified_router",
    "provenance_router",
    "export_router",
    "conflict_router",
    "assistant_router",
    "spatial_analysis_router",
    "pipeline_router",
]

