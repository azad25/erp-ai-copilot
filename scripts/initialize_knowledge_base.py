#!/usr/bin/env python3
"""
Knowledge Base Initialization Script

Standalone script to initialize the AI Copilot knowledge base
from ERP documentation and architecture files.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.knowledge_base_initialization_service import knowledge_base_init_service
from app.database.connection import init_database, close_database
from app.services.memory_service import memory_service
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Main initialization function"""
    try:
        logger.info("Starting knowledge base initialization...")
        
        # Initialize database connections
        await init_database()
        logger.info("Database connections initialized")
        
        # Initialize memory service
        await memory_service.initialize()
        logger.info("Memory service initialized")
        
        # Get current status
        status = await knowledge_base_init_service.get_initialization_status()
        logger.info(f"Current knowledge base status: {status}")
        
        # Initialize knowledge base
        force_refresh = "--force" in sys.argv
        await knowledge_base_init_service.initialize_knowledge_base(force_refresh=force_refresh)
        
        # Get final status
        final_status = await knowledge_base_init_service.get_initialization_status()
        logger.info(f"Knowledge base initialization completed!")
        logger.info(f"Final status: {final_status}")
        
        print("\n" + "="*50)
        print("KNOWLEDGE BASE INITIALIZATION SUMMARY")
        print("="*50)
        print(f"Total entries: {final_status.get('total_knowledge_entries', 0)}")
        print(f"Vector count: {final_status.get('vector_count', 0)}")
        print(f"Processed files: {final_status.get('processed_files_count', 0)}")
        print(f"Status: {final_status.get('status', 'unknown')}")
        
        if final_status.get('categories'):
            print("\nCategories:")
            for category, count in final_status['categories'].items():
                print(f"  - {category}: {count} entries")
        
        print("="*50)
        
    except Exception as e:
        logger.error(f"Knowledge base initialization failed: {e}")
        sys.exit(1)
    
    finally:
        # Clean up
        await close_database()
        logger.info("Database connections closed")


if __name__ == "__main__":
    asyncio.run(main())
