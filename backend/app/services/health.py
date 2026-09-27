from app.core.config import get_settings
from app.core.database import check_database_health
from app.schemas.health import HealthResponse, DatabaseHealth

settings = get_settings()


class HealthService:
    """Service responsible for aggregating system component statuses."""

    @staticmethod
    async def check_health(check_db: bool = True) -> HealthResponse:
        """
        Executes diagnostic checks across core services (application, database, PostGIS).
        """
        db_health: DatabaseHealth | None = None
        overall_status = "healthy"

        if check_db:
            db_res = await check_database_health()
            db_health = DatabaseHealth(
                connected=db_res["connected"],
                postgis_installed=db_res["postgis_installed"],
                postgis_version=db_res["postgis_version"],
                error=db_res["error"],
            )
            if not db_res["connected"]:
                overall_status = "degraded"

        return HealthResponse(
            status=overall_status,
            app=settings.PROJECT_NAME,
            version=settings.VERSION,
            environment=settings.ENVIRONMENT,
            database=db_health,
        )
