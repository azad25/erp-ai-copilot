"""RAG API Module

This module provides API endpoints for the RAG engine, including document
ingestion, search, and management.
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel

from app.config.settings import get_settings
from app.database.connection import get_db_manager
from app.rag.models import Document, SearchQuery, SearchResult, SearchFilter
from app.rag.service import RAGService

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/rag", tags=["rag"])


# Initialize RAG service
async def get_rag_service():
    """Get RAG service instance."""
    db_manager = await get_db_manager()
    service = RAGService(db_manager)
    await service.initialize()
    return service


# API Models
class DocumentResponse(BaseModel):
    """Document response model."""
    id: str
    title: str
    document_type: str
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]
    version: Optional[str] = None
    access_level: Optional[str] = None


class DocumentIngestionResponse(BaseModel):
    """Document ingestion response model."""
    success: bool
    document_id: Optional[str] = None
    chunks_created: Optional[int] = None
    vector_ids: Optional[List[str]] = None
    error: Optional[str] = None


class SearchResponse(BaseModel):
    """Search response model."""
    results: List[SearchResult]
    query: str
    total_results: int
    processing_time_ms: float


# API Endpoints
@router.post("/documents", response_model=DocumentIngestionResponse)
async def ingest_document(
    document: Document,
    background_tasks: BackgroundTasks,
    async_processing: bool = Query(False, description="Process document asynchronously"),
    rag_service: RAGService = Depends(get_rag_service)
):
    """Ingest a document into the RAG system."""
    try:
        if async_processing:
            # Process document asynchronously
            background_tasks.add_task(rag_service.ingest_document, document)
            
            return DocumentIngestionResponse(
                success=True,
                document_id=document.id,
                chunks_created=None,
                vector_ids=None
            )
        else:
            # Process document synchronously
            start_time = datetime.utcnow()
            success, document_id, vector_ids = await rag_service.ingest_document(document)
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            if success:
                return DocumentIngestionResponse(
                    success=True,
                    document_id=document_id,
                    chunks_created=len(vector_ids) if vector_ids else 0,
                    vector_ids=vector_ids,
                )
            else:
                return DocumentIngestionResponse(
                    success=False,
                    error="Document ingestion failed"
                )
                
    except Exception as e:
        logger.error("Error ingesting document", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error ingesting document: {str(e)}")


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Get a document by ID."""
    try:
        document = await rag_service.get_document(document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
        
        return DocumentResponse(
            id=document.id,
            title=document.title,
            document_type=document.document_type,
            created_at=document.created_at,
            updated_at=document.updated_at,
            metadata=document.metadata,
            version=document.version,
            access_level=document.access_level
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting document", document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error getting document: {str(e)}")


@router.put("/documents/{document_id}", response_model=DocumentIngestionResponse)
async def update_document(
    document_id: str,
    document: Document,
    background_tasks: BackgroundTasks,
    async_processing: bool = Query(False, description="Process document asynchronously"),
    rag_service: RAGService = Depends(get_rag_service)
):
    """Update a document."""
    try:
        # Ensure document ID matches path parameter
        if document.id and document.id != document_id:
            raise HTTPException(status_code=400, detail="Document ID in body does not match path parameter")
        
        # Set document ID
        document.id = document_id
        
        if async_processing:
            # Process document asynchronously
            background_tasks.add_task(rag_service.update_document, document)
            
            return DocumentIngestionResponse(
                success=True,
                document_id=document_id,
                chunks_created=None,
                vector_ids=None
            )
        else:
            # Process document synchronously
            success = await rag_service.update_document(document)
            
            if success:
                return DocumentIngestionResponse(
                    success=True,
                    document_id=document_id
                )
            else:
                return DocumentIngestionResponse(
                    success=False,
                    error="Document update failed"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating document", document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error updating document: {str(e)}")


@router.delete("/documents/{document_id}", response_model=Dict[str, Any])
async def delete_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    async_processing: bool = Query(False, description="Process deletion asynchronously"),
    rag_service: RAGService = Depends(get_rag_service)
):
    """Delete a document."""
    try:
        if async_processing:
            # Process deletion asynchronously
            background_tasks.add_task(rag_service.delete_document, document_id)
            
            return {"success": True, "message": "Document deletion scheduled"}
        else:
            # Process deletion synchronously
            success = await rag_service.delete_document(document_id)
            
            if success:
                return {"success": True, "message": "Document deleted successfully"}
            else:
                return {"success": False, "message": "Document not found or deletion failed"}
                
    except Exception as e:
        logger.error("Error deleting document", document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")


@router.post("/search", response_model=SearchResponse)
async def search(
    query: SearchQuery,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Search for documents matching the query."""
    try:
        start_time = datetime.utcnow()
        results = await rag_service.search(query)
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return SearchResponse(
            results=results,
            query=query.query_text,
            total_results=len(results),
            processing_time_ms=processing_time
        )
        
    except Exception as e:
        logger.error("Error searching documents", query=query.query_text, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error searching documents: {str(e)}")