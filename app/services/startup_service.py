"""
Startup Service for AI Copilot

Handles initialization of services, knowledge base, and prevents duplicate data loading.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Any

from app.services.memory_service import memory_service
from app.services.knowledge_base_service import knowledge_base_service
from app.services.api_gateway_client import api_gateway_client
from app.database.connection import get_mongodb, get_redis, get_qdrant

logger = logging.getLogger(__name__)


class StartupService:
    """
    Startup Service for AI Copilot initialization
    
    Features:
    - Initialize all required services
    - Load knowledge base without duplicates
    - Verify database connections
    - Setup caching and vector stores
    """
    
    def __init__(self):
        self.initialization_complete = False
        self.services_status = {}
        
    async def initialize_all_services(self) -> Dict[str, Any]:
        """Initialize all AI Copilot services"""
        logger.info("Starting AI Copilot service initialization...")
        
        initialization_results = {
            "started_at": datetime.utcnow().isoformat(),
            "services": {},
            "errors": []
        }
        
        # 1. Initialize database connections
        try:
            logger.info("Initializing database connections...")
            await self._initialize_databases()
            initialization_results["services"]["databases"] = "initialized"
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            initialization_results["errors"].append(f"Database: {str(e)}")
            initialization_results["services"]["databases"] = "failed"
        
        # 2. Initialize memory service
        try:
            logger.info("Initializing memory service...")
            await memory_service.initialize()
            initialization_results["services"]["memory_service"] = "initialized"
        except Exception as e:
            logger.error(f"Memory service initialization failed: {e}")
            initialization_results["errors"].append(f"Memory Service: {str(e)}")
            initialization_results["services"]["memory_service"] = "failed"
        
        # 3. Initialize knowledge base (with duplicate prevention)
        try:
            logger.info("Initializing knowledge base...")
            kb_result = await self._initialize_knowledge_base()
            initialization_results["services"]["knowledge_base"] = kb_result
        except Exception as e:
            logger.error(f"Knowledge base initialization failed: {e}")
            initialization_results["errors"].append(f"Knowledge Base: {str(e)}")
            initialization_results["services"]["knowledge_base"] = "failed"
        
        # 4. Initialize API Gateway client
        try:
            logger.info("Initializing API Gateway client...")
            await api_gateway_client.initialize()
            initialization_results["services"]["api_gateway"] = "initialized"
        except Exception as e:
            logger.warning(f"API Gateway initialization failed (non-critical): {e}")
            initialization_results["errors"].append(f"API Gateway: {str(e)}")
            initialization_results["services"]["api_gateway"] = "failed"
        
        # 5. Verify all services
        try:
            logger.info("Verifying service health...")
            health_status = await self._verify_services_health()
            initialization_results["health_check"] = health_status
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            initialization_results["errors"].append(f"Health Check: {str(e)}")
        
        self.initialization_complete = True
        initialization_results["completed_at"] = datetime.utcnow().isoformat()
        
        logger.info(f"AI Copilot initialization completed. Status: {initialization_results}")
        return initialization_results
    
    async def _initialize_databases(self):
        """Initialize database connections"""
        # Test MongoDB connection
        mongodb = await get_mongodb()
        await mongodb.command("ping")
        logger.info("MongoDB connection verified")
        
        # Test Redis connection
        redis = await get_redis()
        await redis.ping()
        logger.info("Redis connection verified")
        
        # Test Qdrant connection
        qdrant = await get_qdrant()
        collections = await qdrant.get_collections()
        logger.info(f"Qdrant connection verified. Collections: {len(collections.collections)}")
    
    async def _initialize_knowledge_base(self) -> str:
        """Initialize knowledge base with duplicate prevention"""
        try:
            # Initialize knowledge base service
            await knowledge_base_service.initialize()
            
            # Check if knowledge base is already populated
            status = await knowledge_base_service.get_status()
            existing_docs = status.get("total_documents", 0)
            
            if existing_docs > 0:
                logger.info(f"Knowledge base already contains {existing_docs} documents. Skipping initial load.")
                return f"already_populated_with_{existing_docs}_documents"
            
            # Load knowledge base from documentation
            logger.info("Loading knowledge base from documentation...")
            result = await self._load_initial_knowledge()
            
            return f"loaded_{result.get('processed_documents', 0)}_documents"
            
        except Exception as e:
            logger.error(f"Knowledge base initialization error: {e}")
            return f"failed: {str(e)}"
    
    async def _load_initial_knowledge(self) -> Dict[str, Any]:
        """Load initial knowledge from documentation files"""
        processed_count = 0
        skipped_count = 0
        error_count = 0
        
        # Define documentation paths
        docs_paths = [
            "/app/knowledge_source",
            "/app/docs", 
            "/app/../erp-suit-technical-docs",
            "/app/../docs"
        ]
        
        for docs_path in docs_paths:
            if not os.path.exists(docs_path):
                logger.debug(f"Documentation path not found: {docs_path}")
                continue
                
            logger.info(f"Processing documentation in: {docs_path}")
            
            for root, dirs, files in os.walk(docs_path):
                for file in files:
                    if file.endswith(('.md', '.markdown', '.txt')):
                        file_path = os.path.join(root, file)
                        
                        try:
                            # Process document with duplicate checking
                            result = await knowledge_base_service.process_document(file_path)
                            
                            if result.get("status") == "processed":
                                processed_count += 1
                                logger.debug(f"Processed: {file_path}")
                            elif result.get("status") == "skipped":
                                skipped_count += 1
                                logger.debug(f"Skipped (already exists): {file_path}")
                            else:
                                error_count += 1
                                logger.warning(f"Error processing {file_path}: {result.get('error')}")
                                
                        except Exception as e:
                            error_count += 1
                            logger.error(f"Failed to process {file_path}: {e}")
        
        # Also load ERP-specific knowledge
        await self._load_erp_knowledge()
        
        logger.info(f"Knowledge base loading completed. Processed: {processed_count}, Skipped: {skipped_count}, Errors: {error_count}")
        
        return {
            "processed_documents": processed_count,
            "skipped_documents": skipped_count,
            "error_count": error_count
        }
    
    async def _load_erp_knowledge(self):
        """Load ERP-specific knowledge entries"""
        try:
            # Add ERP system knowledge
            erp_knowledge_entries = [
                {
                    "title": "ERP System Overview",
                    "content": """
# UniBase ERP System

UniBase ERP is a comprehensive enterprise resource planning system that includes:

## Core Modules
- **Sales Management**: Handle sales orders, invoices, and customer relationships
- **Inventory Management**: Track products, stock levels, and warehouse operations
- **Financial Management**: Manage accounts, transactions, and financial reporting
- **Customer Relationship Management (CRM)**: Manage customer data, leads, and opportunities
- **Human Resource Management (HRM)**: Employee management, payroll, and attendance
- **Purchase Management**: Handle purchase orders, suppliers, and procurement

## Key Features
- Real-time data synchronization across all modules
- Role-based access control and security
- Comprehensive reporting and analytics
- API-first architecture for integrations
- Multi-tenant support for organizations

## AI Copilot Integration
The AI Copilot can access data from all ERP modules through:
- Direct database queries (read-only for safety)
- API Gateway integration for real-time data
- Knowledge base search for documentation and procedures
- Step-by-step reasoning for complex business queries
                    """,
                    "source": "system_knowledge",
                    "category": "erp_overview"
                },
                {
                    "title": "API Gateway Usage",
                    "content": """
# API Gateway Integration

The AI Copilot integrates with the ERP system through the API Gateway:

## Available Services
- **Sales Service**: `/api/v1/sales/*` - Sales data, orders, invoices
- **Inventory Service**: `/api/v1/inventory/*` - Product and stock data
- **CRM Service**: `/api/v1/crm/*` - Customer and lead data
- **Finance Service**: `/api/v1/finance/*` - Financial data and reports
- **HRM Service**: `/api/v1/hrm/*` - Employee and payroll data

## Authentication
- Uses JWT tokens for secure API access
- Automatic token refresh and retry logic
- Role-based permissions enforced at API level

## Data Access Patterns
- Read operations for data retrieval and analysis
- Write operations for creating records (with proper permissions)
- Bulk operations for data import/export
- Real-time data streaming for live updates
                    """,
                    "source": "system_knowledge",
                    "category": "api_integration"
                },
                {
                    "title": "Database Schema Overview",
                    "content": """
# Database Schema

The ERP system uses PostgreSQL for transactional data:

## Core Tables
- **customers**: Customer information and contact details
- **sales_orders**: Sales transactions and order data
- **inventory_items**: Product catalog and stock information
- **invoices**: Billing and payment information
- **employees**: Staff information and organizational structure
- **accounts**: Chart of accounts and financial structure

## Data Relationships
- Customers → Sales Orders → Invoices (sales flow)
- Products → Inventory Items → Stock Movements (inventory flow)
- Employees → Departments → Organizations (HR structure)

## AI Copilot Access
- Read-only access to prevent data corruption
- Optimized queries for common business questions
- Aggregated data for reporting and analytics
- Real-time data for current status queries
                    """,
                    "source": "system_knowledge", 
                    "category": "database_schema"
                }
            ]
            
            for entry in erp_knowledge_entries:
                await memory_service.store_knowledge(
                    title=entry["title"],
                    content=entry["content"],
                    source=entry["source"],
                    category=entry["category"],
                    organization_id="system"
                )
            
            logger.info(f"Loaded {len(erp_knowledge_entries)} ERP knowledge entries")
            
        except Exception as e:
            logger.error(f"Failed to load ERP knowledge: {e}")
    
    async def _verify_services_health(self) -> Dict[str, Any]:
        """Verify health of all services"""
        health_status = {
            "mongodb": False,
            "redis": False,
            "qdrant": False,
            "memory_service": False,
            "knowledge_base": False,
            "api_gateway": False
        }
        
        # Check MongoDB
        try:
            mongodb = await get_mongodb()
            await mongodb.command("ping")
            health_status["mongodb"] = True
        except Exception as e:
            logger.error(f"MongoDB health check failed: {e}")
        
        # Check Redis
        try:
            redis = await get_redis()
            await redis.ping()
            health_status["redis"] = True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
        
        # Check Qdrant
        try:
            qdrant = await get_qdrant()
            await qdrant.get_collections()
            health_status["qdrant"] = True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
        
        # Check Memory Service
        try:
            # Test memory service functionality
            test_result = await memory_service.search_knowledge("test", limit=1)
            health_status["memory_service"] = True
        except Exception as e:
            logger.error(f"Memory service health check failed: {e}")
        
        # Check Knowledge Base
        try:
            kb_status = await knowledge_base_service.get_status()
            health_status["knowledge_base"] = "error" not in kb_status
        except Exception as e:
            logger.error(f"Knowledge base health check failed: {e}")
        
        # Check API Gateway (non-critical)
        try:
            gateway_health = await api_gateway_client.get_all_services_health()
            health_status["api_gateway"] = any(gateway_health.values())
        except Exception as e:
            logger.warning(f"API Gateway health check failed (non-critical): {e}")
        
        return health_status
    
    def get_initialization_status(self) -> Dict[str, Any]:
        """Get current initialization status"""
        return {
            "initialization_complete": self.initialization_complete,
            "services_status": self.services_status,
            "timestamp": datetime.utcnow().isoformat()
        }


# Global startup service instance
startup_service = StartupService()