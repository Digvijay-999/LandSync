from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.logging import setup_logging, logger
from app.core.database import check_database_health
from app.api.v1.router import api_v1_router
from app.api.v1.endpoints.health import router as direct_health_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle management for startup and graceful shutdown."""
    setup_logging()
    logger.info("Initializing %s v%s (%s)", settings.PROJECT_NAME, settings.VERSION, settings.ENVIRONMENT)

    # Initial diagnostic check on startup
    db_health = await check_database_health()
    if db_health["connected"]:
        logger.info(
            "Database connected successfully. PostGIS available: %s (version: %s)",
            db_health["postgis_installed"],
            db_health["postgis_version"] or "N/A",
        )
    else:
        logger.warning("Database not immediately reachable: %s", db_health.get("error"))

    yield

    logger.info("Shutting down %s", settings.PROJECT_NAME)


def create_app() -> FastAPI:
    """Application factory for LandSync AI backend."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Geospatial Data Harmonization Platform API",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Structured error handling
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        logger.warning("HTTP %d error on %s: %s", exc.status_code, request.url.path, exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.status_code,
                    "message": exc.detail,
                    "path": request.url.path,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning("Validation error on %s: %s", request.url.path, exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": 422,
                    "message": "Request validation failed",
                    "details": jsonable_encoder(exc.errors()),
                    "path": request.url.path,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled server error on %s: %s", request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": 500,
                    "message": "Internal server error",
                    "path": request.url.path,
                }
            },
        )

    # Health check route mounted directly at /api/health (satisfies exact spec)
    app.include_router(direct_health_router, prefix="/api")

    # API v1 feature routes
    app.include_router(api_v1_router, prefix=settings.API_V1_STR)

    @app.get("/", tags=["Root"])
    async def root():
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "status": "online",
            "docs": f"{settings.API_V1_STR}/docs",
            "health": "/api/health",
        }

    return app


app = create_app()
