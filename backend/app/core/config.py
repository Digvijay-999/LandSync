from functools import lru_cache
import json
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


    # Project metadata
    PROJECT_NAME: str = "LandSync AI"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Server binding
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # Storage & Upload limits
    STORAGE_DIR: str = "storage"
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB default


    # CORS
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # PostgreSQL / PostGIS configuration
    POSTGRES_SERVER: str = "postgres-postgis"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "landsync"
    POSTGRES_USER: str = "landsync"
    POSTGRES_PASSWORD: str = "landsync_secret_dev_pass"

    DATABASE_URL: str = ""
    DATABASE_URL_SYNC: str = ""

    @property
    def async_database_url(self) -> str:
        """Returns asyncpg database URL for FastAPI and async SQLAlchemy."""
        if self.DATABASE_URL:
            # Normalize driver if user passed postgresql://
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        """Returns standard sync database URL for Alembic migrations and sync scripts."""
        if self.DATABASE_URL_SYNC:
            return self.DATABASE_URL_SYNC
        if self.DATABASE_URL and "+asyncpg" in self.DATABASE_URL:
            return self.DATABASE_URL.replace("+asyncpg", "")
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache()
def get_settings() -> Settings:
    """Returns cached settings instance."""
    return Settings()
