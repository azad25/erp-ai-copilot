"""
Core database module providing session management and utilities.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db_session

# Re-export the get_db_session function
__all__ = ["get_db_session", "get_db"]

@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async DB session.
    
    Yields:
        AsyncSession: An async database session
    """
    db = await get_db_session()
    try:
        yield db
    finally:
        await db.close()
