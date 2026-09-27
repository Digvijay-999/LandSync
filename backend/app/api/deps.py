from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an active database session for requests."""
    async for session in get_db():
        yield session


SessionDep = Depends(get_db_session)
