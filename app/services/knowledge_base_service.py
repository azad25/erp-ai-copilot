"""
Knowledge Base Service for AI Copilot
Manages document processing, embeddings, and vector search
"""

import os
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import hashlib
import json

from app.database.connection import get_qdrant, get_mongodb
from app.services.llm_service import llm_service
from app.config.settings import get_settings

logger = logging.getLogger(__name__)

class KnowledgeBaseService:
    """
    Knowledge Base Service for document processing and vector search
    
    Features:
    - Document ingestion and processing
    - Vector embeddings generation
    - Semantic search capabilities
    - Automatic knowledge base updates
    - Document versioning and change detection
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.collection_name = "knowledge_base"
        self.processed_docs = {}
        
    async def initialize(self):
        """Initialize knowledge base service"""
        try:
            # Ensure Qdrant collection exists
            qdrant = await get_qdrant()
            collections = await qdrant.get_collections()
            
            if self.collection_name not in [col.name for col in collections.collections]:
                await qdrant.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={
                        "size": 1536,  # OpenAI embedding size
                        "distance": "Cosine"
                    }
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
            
            # Load processed documents index
            await self._load_processed_docs_index()
            
            logger.info("Knowledge base service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize knowledge base service: {e}")
            
    async def process_document(self, file_path: str, content: str = None) -> Dict[str, Any]:
        """Process a document and add to knowledge base"""
        try:
            if not content:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            
            # Calculate document hash
            doc_hash = hashlib.sha256(content.encode()).hexdigest()
            
            # Check if already processed
            if file_path in self.processed_docs and self.processed_docs[file_path] == doc_hash:
                return {"status": "skipped", "reason": "already_processed"}
            
            # Generate embeddings
            embeddings = await llm_service.generate_embeddings(content)
            
            # Store in Qdrant
            qdrant = await get_qdrant()
            point_id = hashlib.md5(file_path.encode()).hexdigest()
            
            await qdrant.upsert(
                collection_name=self.collection_name,
                points=[{
                    "id": point_id,
                    "vector": embeddings,
                    "payload": {
                        "file_path": file_path,
                        "content": content,
                        "doc_hash": doc_hash,
                        "processed_at": datetime.utcnow().isoformat(),
                        "file_size": len(content),
                        "file_type": os.path.splitext(file_path)[1]
                    }
                }]
            )
            
            # Update processed docs index
            self.processed_docs[file_path] = doc_hash
            await self._save_processed_docs_index()
            
            logger.info(f"Processed document: {file_path}")
            
            return {
                "status": "processed",
                "file_path": file_path,
                "doc_hash": doc_hash,
                "embedding_size": len(embeddings)
            }
            
        except Exception as e:
            logger.error(f"Failed to process document {file_path}: {e}")
            return {"status": "error", "error": str(e)}
    
    async def search_knowledge_base(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search knowledge base using vector similarity"""
        try:
            # Generate query embedding
            query_embedding = await llm_service.generate_embeddings(query)
            
            # Search Qdrant
            qdrant = await get_qdrant()
            search_results = await qdrant.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=0.7
            )
            
            results = []
            for result in search_results:
                results.append({
                    "file_path": result.payload.get("file_path"),
                    "content": result.payload.get("content")[:500] + "...",
                    "score": result.score,
                    "processed_at": result.payload.get("processed_at")
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search knowledge base: {e}")
            return []
    
    async def get_status(self) -> Dict[str, Any]:
        """Get knowledge base status"""
        try:
            qdrant = await get_qdrant()
            collection_info = await qdrant.get_collection(self.collection_name)
            
            return {
                "collection_name": self.collection_name,
                "total_documents": len(self.processed_docs),
                "vector_count": collection_info.vectors_count if collection_info else 0,
                "last_updated": max(
                    [datetime.fromisoformat(doc.get("processed_at", "1970-01-01T00:00:00"))
                     for doc in self.processed_docs.values()],
                    default=datetime.utcnow()
                ).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get knowledge base status: {e}")
            return {"error": str(e)}
    
    async def refresh_knowledge_base(self):
        """Refresh entire knowledge base"""
        try:
            docs_paths = [
                "/app/docs",
                "/app/../erp-suit-technical-docs"
            ]
            
            processed_count = 0
            for docs_path in docs_paths:
                if os.path.exists(docs_path):
                    for root, dirs, files in os.walk(docs_path):
                        for file in files:
                            if file.endswith(('.md', '.markdown')):
                                file_path = os.path.join(root, file)
                                result = await self.process_document(file_path)
                                if result.get("status") == "processed":
                                    processed_count += 1
            
            logger.info(f"Refreshed knowledge base: {processed_count} documents processed")
            return {"processed_documents": processed_count}
            
        except Exception as e:
            logger.error(f"Failed to refresh knowledge base: {e}")
            return {"error": str(e)}
    
    async def _load_processed_docs_index(self):
        """Load processed documents index from MongoDB"""
        try:
            mongodb = await get_mongodb()
            doc = await mongodb.knowledge_base_index.find_one({"_id": "processed_docs"})
            if doc:
                self.processed_docs = doc.get("docs", {})
                
        except Exception as e:
            logger.error(f"Failed to load processed docs index: {e}")
    
    async def _save_processed_docs_index(self):
        """Save processed documents index to MongoDB"""
        try:
            mongodb = await get_mongodb()
            await mongodb.knowledge_base_index.replace_one(
                {"_id": "processed_docs"},
                {
                    "_id": "processed_docs",
                    "docs": self.processed_docs,
                    "updated_at": datetime.utcnow()
                },
                upsert=True
            )
            
        except Exception as e:
            logger.error(f"Failed to save processed docs index: {e}")

# Global knowledge base service instance
knowledge_base_service = KnowledgeBaseService()
