"""RAG (Retrieval-Augmented Generation) Tools

Provides tools for document search, knowledge ingestion, and semantic search
capabilities for the AI Copilot's knowledge management system.
"""

from typing import Dict, List, Optional, Any
import aiohttp
import json
from datetime import datetime

import structlog

from .base_tool import BaseTool, ToolRequest, ToolResponse, ToolParameter, ToolParameterType, ToolMetadata
from app.config.settings import get_settings
from app.database.connection import get_db_manager
from app.rag.models import Document, SearchQuery, SearchFilter, DocumentType, AccessLevel
from app.rag.service import RAGService

logger = structlog.get_logger(__name__)
settings = get_settings()


class DocumentSearchTool(BaseTool):
    """Tool for searching documents in the knowledge base"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="document_search",
            description="Search documents in the knowledge base using various criteria",
            category="RAG",
            parameters=[
                ToolParameter(
                    name="query",
                    type=ToolParameterType.STRING,
                    description="Search query",
                    required=True
                ),
                ToolParameter(
                    name="document_type",
                    type=ToolParameterType.STRING,
                    description="Type of documents to search",
                    required=False,
                    enum=["policy", "procedure", "manual", "report", "guide", "faq", "all"],
                    default="all"
                ),
                ToolParameter(
                    name="department",
                    type=ToolParameterType.STRING,
                    description="Department-specific documents",
                    required=False,
                    enum=["hr", "finance", "sales", "it", "operations", "all"],
                    default="all"
                ),
                ToolParameter(
                    name="limit",
                    type=ToolParameterType.INTEGER,
                    description="Maximum number of results",
                    required=False,
                    default=10
                ),
                ToolParameter(
                    name="date_from",
                    type=ToolParameterType.DATE,
                    description="Search documents from this date",
                    required=False
                ),
                ToolParameter(
                    name="date_to",
                    type=ToolParameterType.DATE,
                    description="Search documents until this date",
                    required=False
                )
            ],
            required_permissions=["knowledge.search"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        query = request.parameters.get("query", "")
        document_type = request.parameters.get("document_type", "all")
        department = request.parameters.get("department", "all")
        limit = request.parameters.get("limit", 10)
        date_from = request.parameters.get("date_from")
        date_to = request.parameters.get("date_to")
        
        try:
            # Initialize RAG service
            db_manager = await get_db_manager()
            rag_service = RAGService(db_manager)
            await rag_service.initialize()
            
            # Create search filters
            filters = []
            
            if document_type != "all":
                filters.append(SearchFilter(
                    field="document_type",
                    value=document_type,
                    operator="=="
                ))
                
            if department != "all":
                filters.append(SearchFilter(
                    field="department",
                    value=department,
                    operator="=="
                ))
                
            if date_from or date_to:
                if date_from:
                    filters.append(SearchFilter(
                        field="created_at",
                        value=date_from,
                        operator=">="
                    ))
                if date_to:
                    filters.append(SearchFilter(
                        field="created_at",
                        value=date_to,
                        operator="<="
                    ))
            
            # Create search query
            search_query = SearchQuery(
                query=query,
                filters=[{"field": f.field, "value": f.value, "operator": f.operator} for f in filters],
                max_results=limit
            )
            
            # Perform search
            results = await rag_service.search(search_query)
            
            # Format results for tool response
            formatted_results = []
            for result in results:
                formatted_result = {
                    "id": result.document_id,
                    "title": result.title,
                    "content": result.content,
                    "type": result.document_type,
                    "relevance_score": result.score,
                    "metadata": result.metadata
                }
                
                # Add department if available
                if result.metadata and "department" in result.metadata:
                    formatted_result["department"] = result.metadata["department"]
                    
                formatted_results.append(formatted_result)
            
            return ToolResponse(
                success=True,
                data={
                    "results": formatted_results,
                    "total_found": len(results),
                    "query": query,
                    "filters": {
                        "document_type": document_type,
                        "department": department
                    }
                }
            )
            
        except Exception as e:
            logger.error("Document search failed", error=str(e))
            return ToolResponse(
                success=False,
                error=f"Document search failed: {str(e)}"
            )


class KnowledgeIngestionTool(BaseTool):
    """Tool for ingesting new documents into the knowledge base"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="knowledge_ingestion",
            description="Ingest new documents into the knowledge base",
            category="RAG",
            parameters=[
                ToolParameter(
                    name="content",
                    type=ToolParameterType.STRING,
                    description="Document content to ingest",
                    required=True
                ),
                ToolParameter(
                    name="title",
                    type=ToolParameterType.STRING,
                    description="Document title",
                    required=True
                ),
                ToolParameter(
                    name="document_type",
                    type=ToolParameterType.STRING,
                    description="Type of document",
                    required=True,
                    enum=["policy", "procedure", "manual", "report", "guide", "faq"]
                ),
                ToolParameter(
                    name="department",
                    type=ToolParameterType.STRING,
                    description="Department this document belongs to",
                    required=True,
                    enum=["hr", "finance", "sales", "it", "operations"]
                ),
                ToolParameter(
                    name="tags",
                    type=ToolParameterType.ARRAY,
                    description="Tags for categorization",
                    required=False,
                    default=[]
                ),
                ToolParameter(
                    name="metadata",
                    type=ToolParameterType.OBJECT,
                    description="Additional metadata",
                    required=False,
                    default={}
                ),
                ToolParameter(
                    name="access_level",
                    type=ToolParameterType.STRING,
                    description="Access level for the document",
                    required=False,
                    enum=["public", "internal", "confidential", "restricted"],
                    default="internal"
                )
            ],
            required_permissions=["knowledge.write"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        content = request.parameters.get("content", "")
        title = request.parameters.get("title", "")
        document_type = request.parameters.get("document_type")
        department = request.parameters.get("department")
        tags = request.parameters.get("tags", [])
        metadata = request.parameters.get("metadata", {})
        access_level = request.parameters.get("access_level", "internal")
        
        try:
            # Initialize RAG service
            db_manager = await get_db_manager()
            rag_service = RAGService(db_manager)
            await rag_service.initialize()
            
            # Add department and tags to metadata
            if not metadata:
                metadata = {}
                
            metadata["department"] = department
            metadata["tags"] = tags
            
            # Create document
            document = Document(
                title=title,
                content=content,
                document_type=document_type,
                metadata=metadata,
                access_level=access_level,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Ingest document
            success, document_id, vector_ids = await rag_service.ingest_document(document)
            
            if not success or not document_id:
                return ToolResponse(
                    success=False,
                    error="Document ingestion failed"
                )
            
            # Get processed document
            processed_doc = await rag_service.get_document(document_id)
            
            if not processed_doc:
                return ToolResponse(
                    success=True,
                    data={
                        "id": document_id,
                        "title": title,
                        "content": content[:100] + "...",  # Truncate for response
                        "type": document_type,
                        "department": department,
                        "tags": tags,
                        "metadata": metadata,
                        "ingestion_date": datetime.utcnow().isoformat(),
                        "status": "processed"
                    },
                    metadata={
                        "document_id": document_id,
                        "chunks_created": len(vector_ids) if vector_ids else 0,
                        "vector_ids": vector_ids
                    }
                )
            
            # Format response
            ingested_doc = {
                "id": processed_doc.id,
                "title": processed_doc.title,
                "content": processed_doc.content[:100] + "...",  # Truncate for response
                "type": processed_doc.document_type,
                "department": department,
                "tags": tags,
                "metadata": processed_doc.metadata,
                "ingestion_date": processed_doc.created_at.isoformat(),
                "word_count": len(processed_doc.content.split()),
                "status": "processed"
            }
            
            return ToolResponse(
                success=True,
                data=ingested_doc,
                metadata={
                    "document_id": document_id,
                    "chunks_created": len(vector_ids) if vector_ids else 0,
                    "vector_ids": vector_ids
                }
            )
            
        except Exception as e:
            logger.error("Knowledge ingestion failed", error=str(e))
            return ToolResponse(
                success=False,
                error=f"Knowledge ingestion failed: {str(e)}"
            )


class SemanticSearchTool(BaseTool):
    """Tool for semantic search using vector embeddings"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="semantic_search",
            description="Perform semantic search using vector embeddings and similarity matching",
            category="RAG",
            parameters=[
                ToolParameter(
                    name="query",
                    type=ToolParameterType.STRING,
                    description="Semantic search query",
                    required=True
                ),
                ToolParameter(
                    name="threshold",
                    type=ToolParameterType.FLOAT,
                    description="Similarity threshold (0.0-1.0)",
                    required=False,
                    default=0.7
                ),
                ToolParameter(
                    name="limit",
                    type=ToolParameterType.INTEGER,
                    description="Maximum number of results",
                    required=False,
                    default=5
                ),
                ToolParameter(
                    name="include_content",
                    type=ToolParameterType.BOOLEAN,
                    description="Include full document content in results",
                    required=False,
                    default=False
                ),
                ToolParameter(
                    name="context_window",
                    type=ToolParameterType.INTEGER,
                    description="Context window size for snippets",
                    required=False,
                    default=200
                )
            ],
            required_permissions=["knowledge.search"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        query = request.parameters.get("query", "")
        threshold = request.parameters.get("threshold", 0.7)
        limit = request.parameters.get("limit", 5)
        include_content = request.parameters.get("include_content", False)
        context_window = request.parameters.get("context_window", 200)
        
        try:
            # Initialize RAG service
            db_manager = await get_db_manager()
            rag_service = RAGService(db_manager)
            await rag_service.initialize()
            
            # Create search query
            search_query = SearchQuery(
                query=query,
                similarity_threshold=threshold,
                max_results=limit
            )
            
            # Perform search
            start_time = datetime.utcnow()
            results = await rag_service.search(search_query)
            search_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Format results for tool response
            final_results = []
            for result in results:
                formatted_result = {
                    "id": result.document_id,
                    "title": result.title,
                    "similarity_score": result.score,
                    "metadata": result.metadata
                }
                
                # Handle content based on include_content flag
                if include_content:
                    formatted_result["content"] = result.content
                else:
                    # Create snippet
                    content = result.content
                    if len(content) > context_window:
                        # Find relevant snippet around query terms
                        snippet = content[:context_window] + "..."
                        formatted_result["snippet"] = snippet
                    else:
                        formatted_result["snippet"] = content
                
                final_results.append(formatted_result)
            
            return ToolResponse(
                success=True,
                data={
                    "query": query,
                    "results": final_results,
                    "total_found": len(results),
                    "threshold_used": threshold,
                    "search_metadata": {
                        "search_time": f"{search_time:.2f}s",
                        "embedding_model": settings.rag.embedding_model
                    }
                }
            )
            
        except Exception as e:
            logger.error("Semantic search failed", error=str(e))
            return ToolResponse(
                success=False,
                error=f"Semantic search failed: {str(e)}"
            )