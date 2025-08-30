#!/usr/bin/env python3
"""
Startup script for AI Copilot service with database initialization.
"""
import asyncio
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.init_db import init_database
import structlog

# Import main from cmd.server with proper path handling
import importlib.util

server_path = project_root / "cmd" / "server.py"
spec = importlib.util.spec_from_file_location("server", server_path)
server_module = importlib.util.module_from_spec(spec)
sys.modules["server"] = server_module
spec.loader.exec_module(server_module)
main = server_module.main

logger = structlog.get_logger(__name__)


async def start_service():
    """Start the AI Copilot service with proper initialization."""
    try:
        logger.info("Starting AI Copilot service initialization...")
        
        # Wait for database to be ready
        max_retries = 30
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                await init_database()
                logger.info("Database initialization successful")
                break
            except Exception as e:
                retry_count += 1
                logger.warning(f"Database initialization attempt {retry_count}/{max_retries} failed", error=str(e))
                if retry_count >= max_retries:
                    logger.error("Database initialization failed after maximum retries")
                    raise
                await asyncio.sleep(5)
        
        # Start the main service
        logger.info("Starting main AI Copilot service...")
        await main()
        
    except Exception as e:
        logger.error("Service startup failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(start_service())