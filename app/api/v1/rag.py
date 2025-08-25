"""RAG API endpoints for document search and management.

Provides endpoints for document ingestion, retrieval, and semantic search.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from typing import List, Optional

from app.rag.api import (
    DocumentResponse, 
    DocumentIngestionResponse, 
    SearchResponse,
    DocumentUpdateRequest
)
from app.rag.models import Document, SearchQuery, SearchFilter
from app.rag.dependencies import get_rag_service
from app.rag.service import RAGService

router = APIRouter()


@router.post("/documents", response_model=DocumentIngestionResponse, status_code=status.HTTP_201_CREATED)
async def ingest_document(
    document: Document,
    background_tasks: BackgroundTasks,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Ingest a new document into the RAG system.
    
    The document will be processed, chunked, embedded, and stored in the vector database.
    For large documents, processing happens in the background.
    """
    # For large documents, process in background
    if len(document.content) > 10000:  # Threshold for background processing
        background_tasks.add_task(rag_service.ingest_document, document)
        return DocumentIngestionResponse(
            success=True,
            document_id=None,  # Will be generated asynchronously
            message="Document queued for processing",
            status="processing"
        )
    
    # For smaller documents, process immediately
    success, document_id, vector_ids = await rag_service.ingest_document(document)
    
    if not success or not document_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest document"
        )
    
    return DocumentIngestionResponse(
        success=True,
        document_id=document_id,
        message="Document processed successfully",
        status="completed",
        chunks_created=len(vector_ids) if vector_ids else 0
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Retrieve a document by its ID."""
    document = await rag_service.get_document(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )
    
    return DocumentResponse(
        document_id=document.id,
        title=document.title,
        content=document.content,
        document_type=document.document_type,
        metadata=document.metadata,
        created_at=document.created_at,
        updated_at=document.updated_at
    )


@router.put("/documents/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: str,
    update_data: DocumentUpdateRequest,
    background_tasks: BackgroundTasks,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Update an existing document.
    
    Updates document content and/or metadata and re-processes it.
    """
    # First check if document exists
    existing_doc = await rag_service.get_document(document_id)
    
    if not existing_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )
    
    # Update document fields
    if update_data.title is not None:
        existing_doc.title = update_data.title
    
    if update_data.content is not None:
        existing_doc.content = update_data.content
    
    if update_data.document_type is not None:
        existing_doc.document_type = update_data.document_type
    
    if update_data.metadata is not None:
        existing_doc.metadata.update(update_data.metadata)
    
    if update_data.access_level is not None:
        existing_doc.access_level = update_data.access_level
    
    # Process update in background for large documents
    if len(existing_doc.content) > 10000:
        background_tasks.add_task(rag_service.update_document, document_id, existing_doc)
        return DocumentResponse(
            document_id=document_id,
            title=existing_doc.title,
            content=existing_doc.content,
            document_type=existing_doc.document_type,
            metadata=existing_doc.metadata,
            created_at=existing_doc.created_at,
            updated_at=existing_doc.updated_at,
            status="updating"
        )
    
    # For smaller documents, update immediately
    success = await rag_service.update_document(document_id, existing_doc)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update document"
        )
    
    # Get the updated document
    updated_doc = await rag_service.get_document(document_id)
    
    return DocumentResponse(
        document_id=updated_doc.id,
        title=updated_doc.title,
        content=updated_doc.content,
        document_type=updated_doc.document_type,
        metadata=updated_doc.metadata,
        created_at=updated_doc.created_at,
        updated_at=updated_doc.updated_at,
        status="updated"
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Delete a document and its vector embeddings."""
    success = await rag_service.delete_document(document_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document"
        )
    
    return None


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    query: SearchQuery,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Search documents using semantic search.
    
    Performs vector similarity search based on the query text and optional filters.
    """
    results = await rag_service.search(query)
    
    return SearchResponse(
        results=results,
        query=query.query_text,
        total=len(results)
    )