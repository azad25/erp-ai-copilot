"""Unit tests for error handling in the RAG API endpoints.

Tests the error handling capabilities of the RAG API endpoints.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.rag.api import router as rag_router
from app.rag.service import RAGService
from app.rag.dependencies import get_rag_service


@pytest.fixture
def mock_rag_service_with_errors():
    """Create a mock RAG service that raises errors."""
    service = MagicMock(spec=RAGService)
    
    # Configure methods to raise exceptions
    service.ingest_document = AsyncMock(side_effect=Exception("Ingestion error"))
    service.get_document = AsyncMock(side_effect=Exception("Retrieval error"))
    service.update_document = AsyncMock(side_effect=Exception("Update error"))
    service.delete_document = AsyncMock(side_effect=Exception("Deletion error"))
    service.search = AsyncMock(side_effect=Exception("Search error"))
    
    return service


@pytest.fixture
def app_with_error_service(mock_rag_service_with_errors):
    """Create a FastAPI app with RAG router and error-raising service."""
    app = FastAPI()
    
    # Override dependency
    async def override_get_rag_service():
        return mock_rag_service_with_errors
    
    app.dependency_overrides[get_rag_service] = override_get_rag_service
    app.include_router(rag_router)
    return app


@pytest.fixture
def error_client(app_with_error_service):
    """Create a test client for the app with error service."""
    return TestClient(app_with_error_service)


def test_document_ingestion_error_handling(error_client):
    """Test error handling in document ingestion endpoint."""
    # Test data
    document_data = {
        "title": "Test Document",
        "content": "This is a test document for error handling.",
        "document_type": "guide",
        "access_level": "internal",
        "metadata": {"department": "engineering"}
    }
    
    # Make request
    response = error_client.post("/documents", json=document_data)
    
    # Check response
    assert response.status_code == 500
    assert "detail" in response.json()
    assert "Error ingesting document" in response.json()["detail"]


def test_document_retrieval_error_handling(error_client):
    """Test error handling in document retrieval endpoint."""
    # Make request
    response = error_client.get("/documents/doc123")
    
    # Check response
    assert response.status_code == 500
    assert "detail" in response.json()
    assert "Error retrieving document" in response.json()["detail"]


def test_document_update_error_handling(error_client):
    """Test error handling in document update endpoint."""
    # Test data
    document_data = {
        "title": "Updated Document",
        "content": "This is an updated test document for error handling.",
        "document_type": "guide",
        "access_level": "internal",
        "metadata": {"department": "engineering"}
    }
    
    # Make request
    response = error_client.put("/documents/doc123", json=document_data)
    
    # Check response
    assert response.status_code == 500
    assert "detail" in response.json()
    assert "Error updating document" in response.json()["detail"]


def test_document_deletion_error_handling(error_client):
    """Test error handling in document deletion endpoint."""
    # Make request
    response = error_client.delete("/documents/doc123")
    
    # Check response
    assert response.status_code == 500
    assert "detail" in response.json()
    assert "Error deleting document" in response.json()["detail"]


def test_document_search_error_handling(error_client):
    """Test error handling in document search endpoint."""
    # Test data
    search_data = {
        "query_text": "test query",
        "filters": {
            "document_type": "guide",
            "access_level": "internal"
        },
        "max_results": 5
    }
    
    # Make request
    response = error_client.post("/search", json=search_data)
    
    # Check response
    assert response.status_code == 500
    assert "detail" in response.json()
    assert "Error searching documents" in response.json()["detail"]


@pytest.fixture
def mock_rag_service_with_validation_errors():
    """Create a mock RAG service that returns validation errors."""
    service = MagicMock(spec=RAGService)
    
    # Configure methods to return validation errors
    service.ingest_document = AsyncMock(return_value=(False, None, None))
    service.get_document = AsyncMock(return_value=None)
    service.update_document = AsyncMock(return_value=False)
    service.delete_document = AsyncMock(return_value=False)
    service.search = AsyncMock(return_value=[])
    
    return service


@pytest.fixture
def app_with_validation_errors(mock_rag_service_with_validation_errors):
    """Create a FastAPI app with RAG router and validation error service."""
    app = FastAPI()
    
    # Override dependency
    async def override_get_rag_service():
        return mock_rag_service_with_validation_errors
    
    app.dependency_overrides[get_rag_service] = override_get_rag_service
    app.include_router(rag_router)
    return app


@pytest.fixture
def validation_client(app_with_validation_errors):
    """Create a test client for the app with validation error service."""
    return TestClient(app_with_validation_errors)


def test_document_ingestion_validation_error(validation_client):
    """Test validation error handling in document ingestion endpoint."""
    # Test data with missing required fields
    document_data = {
        "title": "Test Document"
        # Missing content and other required fields
    }
    
    # Make request
    response = validation_client.post("/documents", json=document_data)
    
    # Check response
    assert response.status_code == 422  # Unprocessable Entity
    assert "detail" in response.json()


def test_document_update_validation_error(validation_client):
    """Test validation error handling in document update endpoint."""
    # Test data with missing required fields
    document_data = {
        "title": "Updated Document"
        # Missing content and other required fields
    }
    
    # Make request
    response = validation_client.put("/documents/doc123", json=document_data)
    
    # Check response
    assert response.status_code == 422  # Unprocessable Entity
    assert "detail" in response.json()


def test_document_search_validation_error(validation_client):
    """Test validation error handling in document search endpoint."""
    # Test data with missing required fields
    search_data = {
        # Missing query_text
        "max_results": 5
    }
    
    # Make request
    response = validation_client.post("/search", json=search_data)
    
    # Check response
    assert response.status_code == 422  # Unprocessable Entity
    assert "detail" in response.json()


@pytest.fixture
def mock_rag_service_unavailable():
    """Create a mock function that raises service unavailable exception."""
    async def mock_get_rag_service():
        raise HTTPException(status_code=503, detail="RAG service unavailable")
    return mock_get_rag_service


@pytest.fixture
def app_with_unavailable_service(mock_rag_service_unavailable):
    """Create a FastAPI app with RAG router and unavailable service."""
    app = FastAPI()
    
    # Override dependency
    app.dependency_overrides[get_rag_service] = mock_rag_service_unavailable
    app.include_router(rag_router)
    return app


@pytest.fixture
def unavailable_client(app_with_unavailable_service):
    """Create a test client for the app with unavailable service."""
    return TestClient(app_with_unavailable_service)


def test_service_unavailable(unavailable_client):
    """Test handling of service unavailable errors."""
    # Test document ingestion
    document_data = {
        "title": "Test Document",
        "content": "This is a test document.",
        "document_type": "guide",
        "access_level": "internal"
    }
    
    response = unavailable_client.post("/documents", json=document_data)
    assert response.status_code == 503
    assert "RAG service unavailable" in response.json()["detail"]
    
    # Test document retrieval
    response = unavailable_client.get("/documents/doc123")
    assert response.status_code == 503
    assert "RAG service unavailable" in response.json()["detail"]
    
    # Test document update
    response = unavailable_client.put("/documents/doc123", json=document_data)
    assert response.status_code == 503
    assert "RAG service unavailable" in response.json()["detail"]
    
    # Test document deletion
    response = unavailable_client.delete("/documents/doc123")
    assert response.status_code == 503
    assert "RAG service unavailable" in response.json()["detail"]
    
    # Test document search
    search_data = {"query_text": "test query"}
    response = unavailable_client.post("/search", json=search_data)
    assert response.status_code == 503
    assert "RAG service unavailable" in response.json()["detail"]