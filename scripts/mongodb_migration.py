"""
MongoDB Migration Script for AI Copilot Service

This script provides programmatic database initialization and migration capabilities
for the AI Copilot MongoDB collections. It can be run independently or integrated
into the application startup process.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MongoDBMigration:
    """MongoDB migration manager for AI Copilot collections."""
    
    def __init__(self, connection_string: str, database_name: str = "erp_ai_conversations"):
        self.connection_string = connection_string
        self.database_name = database_name
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self._initialize_collections_config()
    
    async def connect(self):
        """Connect to MongoDB."""
        try:
            self.client = AsyncIOMotorClient(
                self.connection_string,
                maxPoolSize=5,
                serverSelectionTimeoutMS=30000,
                connectTimeoutMS=30000,
                socketTimeoutMS=30000
            )
            self.db = self.client[self.database_name]
            
            # Test connection
            await self.client.admin.command('ping')
            logger.info(f"Connected to MongoDB database: {self.database_name}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from MongoDB."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    def _initialize_collections_config(self):
        """Initialize collections configuration."""
        collections_config = [
            {
                "name": "conversations",
                "indexes": [
                    {"key": {"organization_id": 1, "user_id": 1}, "name": "org_user_idx"},
                    {"key": {"created_at": -1}, "name": "created_at_idx"},
                    {"key": {"status": 1}, "name": "status_idx"},
                    {"key": {"title": "text"}, "name": "title_text_idx"}
                ]
            },
            {
                "name": "messages",
                "indexes": [
                    {"key": {"conversation_id": 1}, "name": "conversation_idx"},
                    {"key": {"user_id": 1}, "name": "user_idx"},
                    {"key": {"created_at": -1}, "name": "created_at_idx"},
                    {"key": {"role": 1}, "name": "role_idx"},
                    {"key": {"content": "text"}, "name": "content_text_idx"},
                    {"key": {"conversation_id": 1, "created_at": -1}, "name": "conversation_timeline_idx"}
                ]
            },
            {
                "name": "memories",
                "indexes": [
                    {"key": {"organization_id": 1, "user_id": 1}, "name": "org_user_idx"},
                    {"key": {"memory_type": 1}, "name": "memory_type_idx"},
                    {"key": {"importance": -1}, "name": "importance_idx"},
                    {"key": {"created_at": -1}, "name": "created_at_idx"},
                    {"key": {"content": "text"}, "name": "content_text_idx"},
                    {"key": {"tags": 1}, "name": "tags_idx"},
                    {"key": {"expires_at": 1}, "name": "expires_at_idx"}
                ]
            },
            {
                "name": "contexts",
                "indexes": [
                    {"key": {"organization_id": 1, "user_id": 1}, "name": "org_user_idx"},
                    {"key": {"context_type": 1}, "name": "context_type_idx"},
                    {"key": {"conversation_id": 1}, "name": "conversation_idx"},
                    {"key": {"created_at": -1}, "name": "created_at_idx"},
                    {"key": {"relevance_score": -1}, "name": "relevance_idx"},
                    {"key": {"expires_at": 1}, "name": "expires_at_idx"}
                ]
            },
            {
                "name": "knowledge_base",
                "indexes": [
                    {"key": {"organization_id": 1}, "name": "org_idx"},
                    {"key": {"document_type": 1}, "name": "doc_type_idx"},
                    {"key": {"source": 1}, "name": "source_idx"},
                    {"key": {"created_at": -1}, "name": "created_at_idx"},
                    {"key": {"title": "text", "content": "text"}, "name": "content_text_idx"},
                    {"key": {"tags": 1}, "name": "tags_idx"},
                    {"key": {"version": -1}, "name": "version_idx"}
                ]
            },
            {
                "name": "reasoning_sessions",
                "indexes": [
                    {"key": {"organization_id": 1, "user_id": 1}, "name": "org_user_idx"},
                    {"key": {"conversation_id": 1}, "name": "conversation_idx"},
                    {"key": {"session_id": 1}, "name": "session_idx", "unique": True},
                    {"key": {"created_at": -1}, "name": "created_at_idx"},
                    {"key": {"status": 1}, "name": "status_idx"}
                ]
            },
            {
                "name": "reasoning_steps",
                "indexes": [
                    {"key": {"session_id": 1}, "name": "session_idx"},
                    {"key": {"conversation_id": 1}, "name": "conversation_idx"},
                    {"key": {"step_number": 1}, "name": "step_number_idx"},
                    {"key": {"step_type": 1}, "name": "step_type_idx"},
                    {"key": {"status": 1}, "name": "status_idx"},
                    {"key": {"timestamp": -1}, "name": "timestamp_idx"},
                    {"key": {"user_id": 1}, "name": "user_idx"},
                    {"key": {"organization_id": 1}, "name": "org_idx"},
                    {"key": {"session_id": 1, "step_number": 1}, "name": "session_steps_idx"}
                ]
            },
            {
                "name": "background_jobs",
                "indexes": [
                    {"key": {"organization_id": 1}, "name": "org_idx"},
                    {"key": {"job_type": 1}, "name": "job_type_idx"},
                    {"key": {"status": 1}, "name": "status_idx"},
                    {"key": {"priority": -1}, "name": "priority_idx"},
                    {"key": {"scheduled_at": 1}, "name": "scheduled_at_idx"},
                    {"key": {"created_at": -1}, "name": "created_at_idx"},
                    {"key": {"status": 1, "priority": -1, "scheduled_at": 1}, "name": "job_processing_idx"}
                ]
            },
            {
                "name": "vector_embeddings",
                "indexes": [
                    {"key": {"document_id": 1}, "name": "document_idx"},
                    {"key": {"organization_id": 1}, "name": "org_idx"},
                    {"key": {"embedding_type": 1}, "name": "embedding_type_idx"},
                    {"key": {"created_at": -1}, "name": "created_at_idx"},
                    {"key": {"metadata": 1}, "name": "metadata_idx"},
                    {"key": {"organization_id": 1, "embedding_type": 1}, "name": "org_embedding_type_idx"}
                ]
            },
            {
                "name": "file_monitoring",
                "indexes": [
                    {"key": {"file_path": 1}, "name": "file_path_idx", "unique": True},
                    {"key": {"organization_id": 1}, "name": "org_idx"},
                    {"key": {"file_type": 1}, "name": "file_type_idx"},
                    {"key": {"last_modified": -1}, "name": "last_modified_idx"},
                    {"key": {"status": 1}, "name": "status_idx"},
                    {"key": {"created_at": -1}, "name": "created_at_idx"},
                    {"key": {"organization_id": 1, "status": 1}, "name": "org_file_status_idx"}
                ]
            },
            {
                "name": "user_sessions",
                "indexes": [
                    {"key": {"session_id": 1}, "name": "session_idx", "unique": True},
                    {"key": {"user_id": 1}, "name": "user_idx"},
                    {"key": {"organization_id": 1}, "name": "org_idx"},
                    {"key": {"created_at": -1}, "name": "created_at_idx"},
                    {"key": {"last_activity": -1}, "name": "last_activity_idx"},
                    {"key": {"expires_at": 1}, "name": "expires_at_idx"}
                ]
            },
            {
                "name": "agent_executions",
                "indexes": [
                    {"key": {"execution_id": 1}, "name": "execution_idx", "unique": True},
                    {"key": {"conversation_id": 1}, "name": "conversation_idx"},
                    {"key": {"user_id": 1}, "name": "user_idx"},
                    {"key": {"organization_id": 1}, "name": "org_idx"},
                    {"key": {"agent_type": 1}, "name": "agent_type_idx"},
                    {"key": {"action_type": 1}, "name": "action_type_idx"},
                    {"key": {"status": 1}, "name": "status_idx"},
                    {"key": {"created_at": -1}, "name": "created_at_idx"},
                    {"key": {"completed_at": -1}, "name": "completed_at_idx"}
                ]
            },
            {
                "name": "system_commands",
                "indexes": [
                    {"key": {"organization_id": 1, "user_id": 1}, "name": "org_user_idx"},
                    {"key": {"command": 1}, "name": "command_idx"},
                    {"key": {"status": 1}, "name": "status_idx"},
                    {"key": {"executed_at": -1}, "name": "executed_at_idx"},
                    {"key": {"success": 1}, "name": "success_idx"}
                ]
            },
            {
                "name": "api_access_logs",
                "indexes": [
                    {"key": {"organization_id": 1, "user_id": 1}, "name": "org_user_idx"},
                    {"key": {"endpoint": 1}, "name": "endpoint_idx"},
                    {"key": {"method": 1}, "name": "method_idx"},
                    {"key": {"status_code": 1}, "name": "status_code_idx"},
                    {"key": {"timestamp": -1}, "name": "timestamp_idx"}
                ]
            },
            {
                "name": "third_party_api_logs",
                "indexes": [
                    {"key": {"organization_id": 1, "user_id": 1}, "name": "org_user_idx"},
                    {"key": {"api_provider": 1}, "name": "api_provider_idx"},
                    {"key": {"endpoint": 1}, "name": "endpoint_idx"},
                    {"key": {"status_code": 1}, "name": "status_code_idx"},
                    {"key": {"timestamp": -1}, "name": "timestamp_idx"},
                    {"key": {"rate_limit_key": 1}, "name": "rate_limit_idx"}
                ]
            },
            {
                "name": "training_data",
                "indexes": [
                    {"key": {"organization_id": 1}, "name": "org_idx"},
                    {"key": {"data_type": 1}, "name": "data_type_idx"},
                    {"key": {"quality_score": -1}, "name": "quality_idx"},
                    {"key": {"created_at": -1}, "name": "created_at_idx"}
                ]
            },
            {
                "name": "embeddings",
                "indexes": [
                    {"key": {"organization_id": 1}, "name": "org_idx"},
                    {"key": {"document_type": 1}, "name": "doc_type_idx"},
                    {"key": {"created_at": -1}, "name": "created_at_idx"}
                ]
            },
            {
                "name": "erp_knowledge",
                "indexes": [
                    {"key": {"organization_id": 1}, "name": "org_idx"},
                    {"key": {"document_type": 1}, "name": "doc_type_idx"},
                    {"key": {"source_type": 1}, "name": "source_type_idx"},
                    {"key": {"category": 1}, "name": "category_idx"},
                    {"key": {"created_at": -1}, "name": "created_at_idx"},
                    {"key": {"updated_at": -1}, "name": "updated_at_idx"},
                    {"key": {"title": "text", "content": "text"}, "name": "content_text_idx"},
                    {"key": {"tags": 1}, "name": "tags_idx"},
                    {"key": {"version": -1}, "name": "version_idx"},
                    {"key": {"file_path": 1}, "name": "file_path_idx"},
                    {"key": {"file_hash": 1}, "name": "file_hash_idx"},
                    {"key": {"embedding_id": 1}, "name": "embedding_idx", "sparse": True},
                    {"key": {"organization_id": 1, "source_type": 1}, "name": "org_source_idx"},
                    {"key": {"organization_id": 1, "category": 1}, "name": "org_category_idx"}
                ]
            },
            {
                "name": "agent_logs",
                "indexes": [
                    {"key": {"organization_id": 1}, "name": "org_idx"},
                    {"key": {"agent_type": 1}, "name": "agent_type_idx"},
                    {"key": {"status": 1}, "name": "status_idx"},
                    {"key": {"created_at": -1}, "name": "created_at_idx"}
                ]
            },
            {
                "name": "user_preferences",
                "indexes": [
                    {"key": {"organization_id": 1, "user_id": 1}, "name": "org_user_idx", "unique": True},
                    {"key": {"preferences": 1}, "name": "preferences_idx"}
                ]
            },
            {
                "name": "conversation_analytics",
                "indexes": [
                    {"key": {"organization_id": 1}, "name": "org_idx"},
                    {"key": {"date": 1}, "name": "date_idx"},
                    {"key": {"user_id": 1}, "name": "user_idx"},
                    {"key": {"metrics": 1}, "name": "metrics_idx"}
                ]
            }
        ]
        
        self.collections_config = collections_config
    
    async def create_collections_and_indexes(self):
        """Create all collections and their indexes."""
        for collection_config in self.collections_config:
            collection_name = collection_config["name"]
            
            try:
                # Create collection if it doesn't exist
                existing_collections = await self.db.list_collection_names()
                if collection_name not in existing_collections:
                    await self.db.create_collection(collection_name)
                    logger.info(f"Created collection: {collection_name}")
                else:
                    logger.info(f"Collection already exists: {collection_name}")
                
                # Create indexes
                collection = self.db[collection_name]
                for index_config in collection_config["indexes"]:
                    try:
                        index_options = {
                            "name": index_config["name"],
                            "background": True
                        }
                        
                        if index_config.get("unique"):
                            index_options["unique"] = True
                        
                        if index_config.get("sparse"):
                            index_options["sparse"] = True
                        
                        await collection.create_index(
                            list(index_config["key"].items()),
                            **index_options
                        )
                        logger.info(f"Created index: {index_config['name']} on {collection_name}")
                        
                    except Exception as e:
                        if "already exists" not in str(e).lower():
                            logger.warning(f"Could not create index {index_config['name']} on {collection_name}: {e}")
                
            except Exception as e:
                logger.error(f"Failed to create collection {collection_name}: {e}")
                raise
    
    async def run_migration(self, insert_sample_data: bool = True):
        """Run the complete migration process."""
        try:
            await self.connect()
            
            logger.info("Starting AI Copilot MongoDB migration...")
            
            # Create collections and indexes
            await self.create_collections_and_indexes()
            
            # Create TTL indexes
            await self.create_ttl_indexes()
            
            # Create analytical views
            await self.create_analytical_views()
            
            # Insert sample data if requested
            if insert_sample_data:
                await self.insert_sample_data()
            
            # Create additional performance indexes
            await self.create_performance_indexes()
            
            logger.info("MongoDB migration completed successfully!")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
        finally:
            await self.disconnect()
    
    
    async def create_ttl_indexes(self):
        """Create TTL (Time To Live) indexes for automatic cleanup."""
        ttl_configs = [
            {"collection": "memories", "field": "expires_at", "seconds": 0},
            {"collection": "contexts", "field": "expires_at", "seconds": 0},
            {"collection": "user_sessions", "field": "expires_at", "seconds": 0},
            {"collection": "reasoning_sessions", "field": "created_at", "seconds": 7 * 24 * 60 * 60},  # 7 days
            {"collection": "reasoning_steps", "field": "timestamp", "seconds": 7 * 24 * 60 * 60},  # 7 days
            {"collection": "background_jobs", "field": "created_at", "seconds": 30 * 24 * 60 * 60},  # 30 days
            {"collection": "system_commands", "field": "executed_at", "seconds": 90 * 24 * 60 * 60},  # 90 days
            {"collection": "api_access_logs", "field": "timestamp", "seconds": 30 * 24 * 60 * 60},  # 30 days
            {"collection": "third_party_api_logs", "field": "timestamp", "seconds": 30 * 24 * 60 * 60},  # 30 days
            {"collection": "erp_knowledge", "field": "updated_at", "seconds": 365 * 24 * 60 * 60},  # 1 year
        ]
        
        for ttl_config in ttl_configs:
            try:
                collection = self.db[ttl_config["collection"]]
                await collection.create_index(
                    ttl_config["field"],
                    expireAfterSeconds=ttl_config["seconds"],
                    name=f"{ttl_config['field']}_ttl_idx"
                )
                logger.info(f"Created TTL index on {ttl_config['collection']}.{ttl_config['field']}")
                
            except Exception as e:
                if "already exists" not in str(e).lower():
                    logger.warning(f"Could not create TTL index on {ttl_config['collection']}: {e}")
    
    async def create_performance_indexes(self):
        """Create additional performance optimization indexes."""
        performance_indexes = [
            {"collection": "messages", "key": {"reasoning_steps": 1}, "name": "reasoning_sparse_idx", "sparse": True},
            {"collection": "agent_executions", "key": {"error_message": 1}, "name": "error_sparse_idx", "sparse": True},
        ]
        
        for index_config in performance_indexes:
            try:
                collection = self.db[index_config["collection"]]
                index_options = {
                    "name": index_config["name"],
                    "background": True
                }
                
                if index_config.get("sparse"):
                    index_options["sparse"] = True
                
                await collection.create_index(
                    list(index_config["key"].items()),
                    **index_options
                )
                logger.info(f"Created performance index: {index_config['name']}")
                
            except Exception as e:
                if "already exists" not in str(e).lower():
                    logger.warning(f"Could not create performance index {index_config['name']}: {e}")
    
    async def create_analytical_views(self):
        """Create analytical views for reporting."""
        views = [
            {
                "name": "conversation_stats",
                "source": "conversations",
                "pipeline": [
                    {
                        "$group": {
                            "_id": {
                                "organization_id": "$organization_id",
                                "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}
                            },
                            "total_conversations": {"$sum": 1},
                            "active_conversations": {"$sum": {"$cond": [{"$eq": ["$status", "active"]}, 1, 0]}},
                            "avg_messages": {"$avg": "$message_count"}
                        }
                    },
                    {"$sort": {"_id.date": -1}}
                ]
            },
            {
                "name": "reasoning_analytics",
                "source": "reasoning_sessions",
                "pipeline": [
                    {
                        "$group": {
                            "_id": {
                                "organization_id": "$organization_id",
                                "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}
                            },
                            "total_sessions": {"$sum": 1},
                            "avg_steps": {"$avg": "$total_steps"},
                            "avg_processing_time": {"$avg": "$processing_time"},
                            "completed_sessions": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}}
                        }
                    },
                    {"$sort": {"_id.date": -1}}
                ]
            }
        ]
        
        for view_config in views:
            try:
                # Drop view if it exists
                try:
                    await self.db.drop_collection(view_config["name"])
                except:
                    pass  # View doesn't exist
                
                # Create view
                await self.db.create_collection(
                    view_config["name"],
                    viewOn=view_config["source"],
                    pipeline=view_config["pipeline"]
                )
                logger.info(f"Created analytical view: {view_config['name']}")
                
            except Exception as e:
                logger.warning(f"Could not create view {view_config['name']}: {e}")
    
    async def insert_sample_data(self):
        """Insert sample data for testing."""
        try:
            # Sample conversation
            sample_conversation_id = str(uuid.uuid4())
            sample_user_id = "00000000-0000-0000-0000-000000000002"
            sample_org_id = "00000000-0000-0000-0000-000000000001"
            
            # Sample ERP knowledge entry
            sample_knowledge_entry = {
                "_id": ObjectId(),
                "organization_id": sample_org_id,
                "document_type": "documentation",
                "source_type": "technical_docs",
                "category": "api_reference",
                "title": "ERP Suite API Gateway Documentation",
                "content": "The ERP Suite API Gateway provides centralized routing and authentication for all microservices. It handles JWT token validation, rate limiting, and service discovery.",
                "file_path": "/docs/api-gateway.md",
                "file_hash": "abc123def456",
                "tags": ["api", "gateway", "authentication", "microservices"],
                "version": 1,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "metadata": {
                    "author": "ERP Development Team",
                    "last_reviewer": "system",
                    "review_status": "approved"
                }
            }
            
            sample_conversation = {
                "_id": ObjectId(),
                "conversation_id": sample_conversation_id,
                "organization_id": sample_org_id,
                "user_id": sample_user_id,
                "title": "AI Copilot Test Conversation",
                "status": "active",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "metadata": {
                    "source": "migration_script",
                    "tags": ["test", "sample"],
                    "priority": "low"
                }
            }
            
            # Sample reasoning session
            reasoning_session_id = f"reasoning_{int(datetime.utcnow().timestamp())}"
            sample_reasoning_session = {
                "_id": ObjectId(),
                "session_id": reasoning_session_id,
                "organization_id": sample_org_id,
                "user_id": sample_user_id,
                "conversation_id": sample_conversation_id,
                "steps": [
                    {
                        "step_number": 1,
                        "step_type": "thinking",
                        "title": "Analyzing user request",
                        "description": "Processing user message and determining approach",
                        "source": "AI Reasoning Engine",
                        "status": "completed",
                        "processing_time": 0.2
                    }
                ],
                "status": "completed",
                "total_steps": 5,
                "processing_time": 2.1,
                "created_at": datetime.utcnow()
            }
            
            # Insert sample data
            await self.db.conversations.insert_one(sample_conversation)
            await self.db.reasoning_sessions.insert_one(sample_reasoning_session)
            await self.db.erp_knowledge.insert_one(sample_knowledge_entry)
            
            logger.info("Inserted sample data for testing")
            
        except Exception as e:
            logger.warning(f"Could not insert sample data: {e}")
    
    async def check_migration_status(self) -> Dict[str, Any]:
        """Check the status of the migration."""
        try:
            await self.connect()
            
            existing_collections = await self.db.list_collection_names()
            expected_collections = [config["name"] for config in self.collections_config]
            
            missing_collections = [name for name in expected_collections if name not in existing_collections]
            
            # Check indexes for each collection
            index_status = {}
            for collection_config in self.collections_config:
                collection_name = collection_config["name"]
                if collection_name in existing_collections:
                    collection = self.db[collection_name]
                    existing_indexes = await collection.list_indexes().to_list(length=None)
                    existing_index_names = [idx["name"] for idx in existing_indexes]
                    
                    expected_indexes = [idx["name"] for idx in collection_config["indexes"]]
                    missing_indexes = [name for name in expected_indexes if name not in existing_index_names]
                    
                    index_status[collection_name] = {
                        "total_indexes": len(expected_indexes),
                        "existing_indexes": len(existing_index_names),
                        "missing_indexes": missing_indexes
                    }
            
            status = {
                "total_collections": len(expected_collections),
                "existing_collections": len(existing_collections),
                "missing_collections": missing_collections,
                "index_status": index_status,
                "migration_complete": len(missing_collections) == 0
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to check migration status: {e}")
            return {"error": str(e)}
        finally:
            await self.disconnect()


async def main():
    """Main migration function."""
    import os
    
    # Get MongoDB connection string from environment or use default
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    database_name = os.getenv("MONGODB_DATABASE", "erp_ai_conversations")
    
    migration = MongoDBMigration(mongodb_uri, database_name)
    
    try:
        # Check current status
        logger.info("Checking current migration status...")
        status = await migration.check_migration_status()
        
        if status.get("migration_complete"):
            logger.info("Migration already complete!")
            return
        
        # Run migration
        await migration.run_migration(insert_sample_data=True)
        
        # Verify migration
        final_status = await migration.check_migration_status()
        logger.info(f"Migration verification: {final_status}")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
