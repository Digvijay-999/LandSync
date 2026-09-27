from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.datasets import router as datasets_router
from app.api.v1.endpoints.matching import router as matching_router
from app.api.v1.endpoints.unified import router as unified_router

__all__ = [
    "health_router",
    "projects_router",
    "datasets_router",
    "matching_router",
    "unified_router",
]

