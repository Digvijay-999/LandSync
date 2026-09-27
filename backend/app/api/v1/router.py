from fastapi import APIRouter
from app.api.v1.endpoints import (
    health_router,
    projects_router,
    datasets_router,
    matching_router,
    unified_router,
)

api_v1_router = APIRouter()

# Mount feature endpoints
api_v1_router.include_router(health_router, tags=["Health"])
api_v1_router.include_router(projects_router, prefix="/projects", tags=["Projects"])
api_v1_router.include_router(datasets_router, tags=["Datasets"])
api_v1_router.include_router(matching_router, tags=["Matching"])
api_v1_router.include_router(unified_router, tags=["Unified Land Records"])


