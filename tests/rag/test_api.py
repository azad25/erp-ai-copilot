"""Unit tests for the RAG API endpoints.

Tests the API endpoints for document ingestion, retrieval, update, deletion, and search.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI, BackgroundTasks
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.rag.api import router as rag_router
from app.rag.models import Document, DocumentType, AccessLevel, SearchQuery, SearchFilter, SearchResult
from app.rag.service import RAGService
from app.rag.dependencies import get_rag_service


@pytest.fixture
def mock_rag_service():
    """Create a mock RAG service."""
    service = MagicMock(spec=RAGService)
    service.ingest_document = AsyncMock(return_value=(True, "doc123", ["vector1", "vector2"]))
    service.get_document = AsyncMock(return_value={
        "_id": "doc123",
        "title": "Test Document",
        "content": "Test content",
        "document_type": "guide",
        "access_level": "internal",
        "metadata": {"department": "engineering", "tags": ["test", "api"]},
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    })
    service.update_document = AsyncMock(return_value=True)
    service.delete_document = AsyncMock(return_value=True)
    service.search = AsyncMock(return_value=[
        SearchResult(document_id="doc1", content="Test content 1", score=0.95, metadata={"title": "Test Document 1"}),
        SearchResult(document_id="doc2", content="Test content 2", score=0.85, metadata={"title": "Test Document 2"})
    ])
    return service


@pytest.fixture
def app(mock_rag_service):
    """Create a FastAPI app with RAG router."""
    app = FastAPI()
    
    # Override dependency
    async def override_get_rag_service():
        return mock_rag_service
    
    app.dependency_overrides[get_rag_service] = override_get_rag_service
    app.include_router(rag_router)
    return app


@pytest.fixture
def client(app):
    """Create a test client for the app."""
    return TestClient(app)


def test_document_ingestion(client, mock_rag_service):
    """Test document ingestion endpoint."""
    # Test data
    document_data = {
        "title": "Test Document",
        "content": "This is a test document for API testing.",
        "document_type": "guide",
        "access_level": "internal",
        "metadata": {"department": "engineering", "tags": ["test", "api"]}
    }
    
    # Make request
    response = client.post("/documents", json=document_data)
    
    # Check response
    assert response.status_code == 202
    assert response.json()["success"] is True
    assert response.json()["document_id"] == "doc123"
    assert "vector_ids" in response.json()
    
    # Check if service was called
    mock_rag_service.ingest_document.assert_called_once()


def test_document_retrieval(client, mock_rag_service):
    """Test document retrieval endpoint."""
    # Make request
    response = client.get("/documents/doc123")
    
    # Check response
    assert response.status_code == 200
    assert response.json()["id"] == "doc123"
    assert response.json()["title"] == "Test Document"
    assert "content" in response.json()
    assert "metadata" in response.json()
    
    # Check if service was called
    mock_rag_service.get_document.assert_called_with("doc123")


def test_document_retrieval_not_found(client, mock_rag_service):
    """Test document retrieval endpoint when document is not found."""
    # Set up mock to return None
    mock_rag_service.get_document.return_value = None
    
    # Make request
    response = client.get("/documents/nonexistent")
    
    # Check response
    assert response.status_code == 404
    assert "detail" in response.json()
    
    # Check if service was called
    mock_rag_service.get_document.assert_called_with("nonexistent")


def test_document_update(client, mock_rag_service):
    """Test document update endpoint."""
    # Test data
    document_data = {
        "title": "Updated Document",
        "content": "This is an updated test document.",
        "document_type": "guide",
        "access_level": "internal",
        "metadata": {"department": "engineering", "tags": ["test", "api", "updated"]}
    }
    
    # Make request
    response = client.put("/documents/doc123", json=document_data)
    
    # Check response
    assert response.status_code == 202
    assert response.json()["success"] is True
    assert response.json()["document_id"] == "doc123"
    
    # Check if service was called
    mock_rag_service.update_document.assert_called_once()


def test_document_deletion(client, mock_rag_service):
    """Test document deletion endpoint."""
    # Make request
    response = client.delete("/documents/doc123")
    
    # Check response
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["document_id"] == "doc123"
    
    # Check if service was called
    mock_rag_service.delete_document.assert_called_with("doc123")


def test_document_deletion_failed(client, mock_rag_service):
    """Test document deletion endpoint when deletion fails."""
    # Set up mock to return False
    mock_rag_service.delete_document.return_value = False
    
    # Make request
    response = client.delete("/documents/doc123")
    
    # Check response
    assert response.status_code == 404
    assert "detail" in response.json()
    
    # Check if service was called
    mock_rag_service.delete_document.assert_called_with("doc123")


def test_document_search(client, mock_rag_service):
    """Test document search endpoint."""
    # Test data
    search_data = {
        "query_text": "test query",
        "filters": {
            "document_type": "guide",
            "access_level": "internal",
            "metadata": {"department": "engineering"}
        },
        "max_results": 5
    }
    
    # Make request
    response = client.post("/search", json=search_data)
    
    # Check response
    assert response.status_code == 200
    assert "results" in response.json()
    assert len(response.json()["results"]) == 2
    assert response.json()["results"][0]["document_id"] == "doc1"
    assert response.json()["results"][1]["document_id"] == "doc2"
    
    # Check if service was called
    mock_rag_service.search.assert_called_once()


@pytest.mark.asyncio
async def test_background_document_ingestion(app, mock_rag_service):
    """Test background document ingestion."""
    # Test data
    document_data = {
        "title": "Test Document",
        "content": "This is a test document for API testing.",
        "document_type": "guide",
        "access_level": "internal",
        "metadata": {"department": "engineering", "tags": ["test", "api"]}
    }
    
    # Make request
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/documents", json=document_data)
    
    # Check response
    assert response.status_code == 202
    
    # Check if background task was added
    # Note: We can't directly test if the background task was executed,
    # but we can check if the service method was called
    mock_rag_service.ingest_document.assert_called_once()


@pytest.mark.asyncio
async def test_background_document_update(app, mock_rag_service):
    """Test background document update."""
    # Test data
    document_data = {
        "title": "Updated Document",
        "content": "This is an updated test document.",
        "document_type": "guide",
        "access_level": "internal",
        "metadata": {"department": "engineering", "tags": ["test", "api", "updated"]}
    }
    
    # Make request
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.put("/documents/doc123", json=document_data)
    
    # Check response
    assert response.status_code == 202
    
    # Check if background task was added
    mock_rag_service.update_document.assert_called_once()