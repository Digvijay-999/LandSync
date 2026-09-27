from fastapi import APIRouter, Query
from app.schemas.health import HealthResponse
from app.services.health import HealthService

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System Health Diagnostics",
    description="Returns application status, version, and optional database/PostGIS connectivity check.",
)
async def get_health(
    check_db: bool = Query(default=True, description="Whether to include database & PostGIS diagnostic check")
) -> HealthResponse:
    """Thin endpoint delegating to HealthService."""
    return await HealthService.check_health(check_db=check_db)
