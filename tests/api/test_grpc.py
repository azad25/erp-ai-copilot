"""Tests for gRPC API integration.

This module contains tests for the gRPC API integration with the AI Copilot service.
"""

import asyncio
import grpc
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.api.grpc import AICopilotServicerImpl, start_grpc_server, stop_grpc_server
from app.proto.ai_copilot_pb2 import ChatRequest, ChatResponse, HealthCheckRequest


@pytest.fixture
def mock_master_agent():
    """Mock the MasterAgent class."""
    with patch("app.api.grpc.MasterAgent") as mock:
        agent_instance = AsyncMock()
        mock.return_value = agent_instance
        yield agent_instance


@pytest.fixture
def mock_grpc_context():
    """Mock gRPC context."""
    context = MagicMock()
    context.set_code = AsyncMock()
    context.set_details = AsyncMock()
    return context


@pytest.mark.asyncio
async def test_chat_success(mock_master_agent, mock_grpc_context):
    """Test successful chat request."""
    # Setup
    servicer = AICopilotServicerImpl()
    request = ChatRequest(
        message="Hello",
        conversation_id="conv123",
        user_id="user456",
        agent_type="general"
    )
    
    # Mock agent response
    mock_master_agent.process_message.return_value = {
        "content": "Hello, how can I help you?",
        "message_id": "msg789",
        "metadata": "{}",
        "suggested_actions": "[]"
    }
    
    # Execute
    response = await servicer.Chat(request, mock_grpc_context)
    
    # Assert
    assert response.content == "Hello, how can I help you?"
    assert response.conversation_id == "conv123"
    assert response.message_id == "msg789"
    assert response.response_type == "text"
    assert response.error == ""
    
    # Verify agent was called with correct parameters
    mock_master_agent.process_message.assert_called_once_with(
        message="Hello",
        conversation_id="conv123",
        user_id="user456",
        agent_type="general",
        model=None,
        temperature=None,
        max_tokens=None,
        context=None
    )


@pytest.mark.asyncio
async def test_chat_error(mock_master_agent, mock_grpc_context):
    """Test chat request with error."""
    # Setup
    servicer = AICopilotServicerImpl()
    request = ChatRequest(
        message="Hello",
        conversation_id="conv123",
        user_id="user456",
        agent_type="general"
    )
    
    # Mock agent error
    mock_master_agent.process_message.side_effect = Exception("Test error")
    
    # Execute
    response = await servicer.Chat(request, mock_grpc_context)
    
    # Assert
    assert response.content == ""
    assert response.conversation_id == "conv123"
    assert response.response_type == "error"
    assert response.error == "Test error"
    
    # Verify context was updated with error
    mock_grpc_context.set_code.assert_called_once()
    mock_grpc_context.set_details.assert_called_once()


@pytest.mark.asyncio
async def test_stream_chat_success(mock_master_agent, mock_grpc_context):
    """Test successful streaming chat request."""
    # Setup
    servicer = AICopilotServicerImpl()
    request = ChatRequest(
        message="Hello",
        conversation_id="conv123",
        user_id="user456",
        agent_type="general"
    )
    
    # Mock streaming response
    async def mock_stream():
        yield {"content": "Hello", "message_id": "msg1"}
        yield {"content": ", how", "message_id": "msg1"}
        yield {"content": " can I help you?", "message_id": "msg1"}
    
    mock_master_agent.process_stream_message.return_value = mock_stream()
    
    # Execute
    responses = []
    async for response in servicer.StreamChat(request, mock_grpc_context):
        responses.append(response)
    
    # Assert
    assert len(responses) == 3
    assert responses[0].content == "Hello"
    assert responses[1].content == ", how"
    assert responses[2].content == " can I help you?"
    assert all(r.conversation_id == "conv123" for r in responses)
    assert all(r.response_type == "stream" for r in responses)


@pytest.mark.asyncio
async def test_health_check(mock_grpc_context):
    """Test health check request."""
    # Setup
    with patch("app.api.grpc.get_settings") as mock_settings:
        mock_settings.return_value.service.version = "1.0.0"
        
        servicer = AICopilotServicerImpl()
        request = HealthCheckRequest(check_type="basic")
        
        # Execute
        response = await servicer.HealthCheck(request, mock_grpc_context)
        
        # Assert
        assert response.status == "ok"
        assert "healthy" in response.details
        assert response.version == "1.0.0"


@pytest.mark.asyncio
async def test_server_lifecycle():
    """Test server startup and shutdown."""
    # Mock dependencies
    with patch("app.api.grpc.grpc.aio.server") as mock_server, \
         patch("app.api.grpc.get_settings") as mock_settings, \
         patch("app.api.grpc.AICopilotServicerImpl") as mock_servicer, \
         patch("app.api.grpc.add_AICopilotServicer_to_server") as mock_add_servicer:
        
        # Setup mocks
        mock_server_instance = AsyncMock()
        mock_server.return_value = mock_server_instance
        mock_settings.return_value.environment = "development"
        mock_settings.return_value.grpc.port = 50052
        
        # Test startup
        await start_grpc_server()
        
        # Assert server was created and started
        mock_server.assert_called_once()
        mock_servicer.assert_called_once()
        mock_add_servicer.assert_called_once()
        mock_server_instance.add_insecure_port.assert_called_once()
        mock_server_instance.start.assert_called_once()
        
        # Test shutdown
        await stop_grpc_server()
        
        # Assert server was stopped
        mock_server_instance.stop.assert_called_once()
        mock_server_instance.wait_for_termination.assert_called_once()