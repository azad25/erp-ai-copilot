"""
Database module providing SQLAlchemy session management.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from .connection import get_db_manager

# Re-export the get_db_session from connection
from .connection import get_db_session

# Create a global session maker
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
