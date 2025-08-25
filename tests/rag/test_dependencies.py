"""Unit tests for the RAG dependencies module.

Tests the dependency injection functionality for the RAG service.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from app.rag.dependencies import get_rag_service
from app.rag.service import RAGService


@pytest.mark.asyncio
async def test_get_rag_service_from_app_state():
    """Test getting RAG service from app state."""
    # Create mock request with app state containing RAG service
    mock_rag_service = MagicMock(spec=RAGService)
    mock_app = MagicMock()
    mock_app.state.rag_service = mock_rag_service
    mock_request = MagicMock()
    mock_request.app = mock_app
    
    # Get RAG service
    with patch("app.rag.dependencies.RAGService", return_value=MagicMock()):
        service = await get_rag_service(mock_request)
    
    # Check if correct service was returned
    assert service == mock_rag_service


@pytest.mark.asyncio
async def test_get_rag_service_initialize_new():
    """Test initializing a new RAG service when not in app state."""
    # Create mock request without RAG service in app state
    mock_app = MagicMock()
    mock_app.state = MagicMock(spec=[])
    mock_request = MagicMock()
    mock_request.app = mock_app
    
    # Create mock database manager and RAG service
    mock_db_manager = MagicMock()
    mock_rag_service = MagicMock(spec=RAGService)
    mock_rag_service.initialize = MagicMock()
    
    # Get RAG service
    with patch("app.rag.dependencies.get_db_manager", return_value=mock_db_manager), \
         patch("app.rag.dependencies.RAGService", return_value=mock_rag_service):
        service = await get_rag_service(mock_request)
    
    # Check if new service was created and initialized
    assert service == mock_rag_service
    mock_rag_service.initialize.assert_called_once()
    
    # Check if service was stored in app state
    assert mock_app.state.rag_service == mock_rag_service


@pytest.mark.asyncio
async def test_get_rag_service_initialization_error():
    """Test error handling when RAG service initialization fails."""
    # Create mock request without RAG service in app state
    mock_app = MagicMock()
    mock_app.state = MagicMock(spec=[])
    mock_request = MagicMock()
    mock_request.app = mock_app
    
    # Create mock database manager and RAG service that raises an exception on initialization
    mock_db_manager = MagicMock()
    mock_rag_service = MagicMock(spec=RAGService)
    mock_rag_service.initialize = MagicMock(side_effect=Exception("Initialization error"))
    
    # Get RAG service
    with patch("app.rag.dependencies.get_db_manager", return_value=mock_db_manager), \
         patch("app.rag.dependencies.RAGService", return_value=mock_rag_service), \
         pytest.raises(HTTPException) as excinfo:
        await get_rag_service(mock_request)
    
    # Check if HTTP exception was raised with correct status code
    assert excinfo.value.status_code == 503
    assert "RAG service unavailable" in str(excinfo.value.detail)