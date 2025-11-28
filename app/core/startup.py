"""
Application Startup

Initialize all services on application startup.
"""

import logging
from fastapi import FastAPI

from app.services.kafka_service import kafka_service
from app.services.background_task_service import background_task_service

logger = logging.getLogger(__name__)


async def startup_event(app: FastAPI):
    """
    Initialize services on application startup
    """
    logger.info("Starting ERP AI Copilot services...")
    
    try:
        # Initialize Kafka
        logger.info("Initializing Kafka service...")
        await kafka_service.initialize()
        
        # Initialize Background Task Service
        logger.info("Initializing Background Task service...")
        await background_task_service.initialize()
        
        logger.info("All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        # Don't fail the app if optional services fail
        logger.warning("Some services failed to initialize, continuing anyway...")


async def shutdown_event(app: FastAPI):
    """
    Cleanup on application shutdown
    """
    logger.info("Shutting down ERP AI Copilot services...")
    
    try:
        # Close Kafka connections
        await kafka_service.close()
        
        logger.info("All services shut down successfully")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
