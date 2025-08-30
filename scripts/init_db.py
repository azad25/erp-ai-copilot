#!/usr/bin/env python3
"""
Database initialization script for AI Copilot service.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from app.database.connection import DatabaseManager
from app.models.database import Base
from app.config.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)
settings = get_settings()


async def init_database():
    """Initialize the database with all tables."""
    try:
        logger.info("Starting database initialization...")
        
        # Initialize database manager
        db_manager = DatabaseManager()
        await db_manager.initialize()
        
        # Create all tables
        engine = db_manager.get_postgres_client()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database tables created successfully")
        
        # Close connections
        await db_manager.close()
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
        raise


if __name__ == "__main__":
    asyncio.run(init_database())