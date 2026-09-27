from typing import AsyncGenerator, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from app.core.config import get_settings
from app.core.logging import logger

settings = get_settings()

# Create SQLAlchemy 2.x async engine
engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create sessionmaker for async sessions
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async database session for request lifecycle."""
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> Dict[str, Any]:
    """
    Validates database connectivity and checks PostGIS extension availability.
    Returns structured health metadata.
    """
    health_info: Dict[str, Any] = {
        "connected": False,
        "postgis_installed": False,
        "postgis_version": None,
        "error": None,
    }

    try:
        async with engine.connect() as conn:
            # 1. Check basic connectivity
            res = await conn.execute(text("SELECT 1"))
            if res.scalar() == 1:
                health_info["connected"] = True

            # 2. Check PostGIS extension
            try:
                pg_res = await conn.execute(text("SELECT PostGIS_Full_Version();"))
                version_str = pg_res.scalar()
                if version_str:
                    health_info["postgis_installed"] = True
                    # Take the first concise section of the full version string
                    health_info["postgis_version"] = str(version_str).split("\n")[0]
            except Exception as pg_err:
                # Connected to postgres, but postgis function not found or failed
                health_info["postgis_installed"] = False
                logger.warning("PostGIS check failed or extension not found: %s", pg_err)

    except Exception as exc:
        health_info["connected"] = False
        health_info["error"] = str(exc)
        logger.error("Database health check failed: %s", exc)

    return health_info
