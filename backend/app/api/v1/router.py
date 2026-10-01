from fastapi import APIRouter
from app.api.v1.endpoints import (
    health_router,
    projects_router,
    datasets_router,
    matching_router,
    unified_router,
    provenance_router,
    export_router,
    conflict_router,
    assistant_router,
    spatial_analysis_router,
    pipeline_router,
)

api_v1_router = APIRouter()

# Mount feature endpoints
api_v1_router.include_router(health_router, tags=["Health"])
api_v1_router.include_router(projects_router, prefix="/projects", tags=["Projects"])
api_v1_router.include_router(datasets_router, tags=["Datasets"])
api_v1_router.include_router(matching_router, tags=["Matching"])
api_v1_router.include_router(unified_router, tags=["Unified Land Records"])
api_v1_router.include_router(provenance_router, tags=["Provenance & Audit"])
api_v1_router.include_router(export_router, tags=["Exports"])
api_v1_router.include_router(conflict_router, tags=["Attribute Conflicts"])
api_v1_router.include_router(assistant_router, prefix="/assistant", tags=["Evidence Assistant"])
api_v1_router.include_router(spatial_analysis_router, prefix="/analysis", tags=["Spatial Analysis"])
api_v1_router.include_router(pipeline_router, tags=["Pipeline Workflow"])


