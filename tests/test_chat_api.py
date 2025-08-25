"""
Unit tests for the chat API endpoints.
"""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database.models.database import User, Conversation, Message
from app.models.api import ChatRequest, CreateConversationRequest, UpdateConversationRequest
from app.services.chat_service import ChatService

client = TestClient(app)


@pytest.fixture
def mock_user():
    """Mock user for testing."""
    return User(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        username="testuser",
        email="test@example.com",
        role="user",
        permissions=["chat:read", "chat:write"]
    )


@pytest.fixture
def mock_conversation(mock_user):
    """Mock conversation for testing."""
    return Conversation(
        id=uuid.uuid4(),
        organization_id=mock_user.organization_id,
        user_id=mock_user.id,
        title="Test Conversation",
        status="active"
    )


@pytest.fixture
def mock_message(mock_conversation, mock_user):
    """Mock message for testing."""
    return Message(
        id=uuid.uuid4(),
        conversation_id=mock_conversation.id,
        user_id=mock_user.id,
        role="user",
        content="Hello, how can you help me?"
    )


@pytest.fixture
def mock_chat_response():
    """Mock chat response for testing."""
    return {
        "content": "Hello! I'm your AI assistant. How can I help you today?",
        "agent_type": "help",
        "model_used": "gpt-4",
        "tokens_used": 25,
        "execution_time_ms": 1500,
        "metadata": {"confidence": 0.95}
    }


class TestChatAPI:
    """Test cases for chat API endpoints."""
    
    @pytest.mark.asyncio
    async def test_chat_endpoint_success(self, mock_user, mock_conversation, mock_chat_response):
        """Test successful chat request."""
        with patch('app.api.v1.chat.get_current_user', return_value=mock_user), \
             patch('app.api.v1.chat.get_db_session') as mock_db_session, \
             patch('app.api.v1.chat.ChatService') as mock_chat_service_class:
            
            # Mock database session
            mock_db = AsyncMock()
            mock_db_session.return_value.__aenter__.return_value = mock_db
            
            # Mock chat service
            mock_chat_service = AsyncMock()
            mock_chat_service.generate_response.return_value = mock_chat_response
            mock_chat_service_class.return_value = mock_chat_service
            
            # Mock database operations
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()
            mock_db.execute = AsyncMock()
            
            # Mock conversation query result
            mock_conversation_result = MagicMock()
            mock_conversation_result.scalar_one_or_none.return_value = mock_conversation
            mock_db.execute.return_value = mock_conversation_result
            
            # Test request
            request_data = {
                "message": "Hello, how can you help me?",
                "conversation_id": str(mock_conversation.id),
                "agent_type": "help"
            }
            
            response = client.post("/api/v1/chat/", json=request_data)
            
            # Assertions
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["content"] == mock_chat_response["content"]
            assert response_data["conversation_id"] == str(mock_conversation.id)
            assert "message_id" in response_data
    
    @pytest.mark.asyncio
    async def test_chat_endpoint_new_conversation(self, mock_user, mock_chat_response):
        """Test chat request with new conversation creation."""
        with patch('app.api.v1.chat.get_current_user', return_value=mock_user), \
             patch('app.api.v1.chat.get_db_session') as mock_db_session, \
             patch('app.api.v1.chat.ChatService') as mock_chat_service_class:
            
            # Mock database session
            mock_db = AsyncMock()
            mock_db_session.return_value.__aenter__.return_value = mock_db
            
            # Mock chat service
            mock_chat_service = AsyncMock()
            mock_chat_service.generate_response.return_value = mock_chat_response
            mock_chat_service_class.return_value = mock_chat_service
            
            # Mock database operations
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()
            
            # Mock new conversation
            new_conversation = Conversation(
                id=uuid.uuid4(),
                organization_id=mock_user.organization_id,
                user_id=mock_user.id,
                title="Hello, how can you help me?...",
                status="active"
            )
            
            # Mock conversation refresh
            def mock_refresh(obj):
                if isinstance(obj, Conversation):
                    obj.id = new_conversation.id
                elif isinstance(obj, Message):
                    obj.id = uuid.uuid4()
            
            mock_db.refresh.side_effect = mock_refresh
            
            # Test request without conversation_id
            request_data = {
                "message": "Hello, how can you help me?",
                "agent_type": "help"
            }
            
            response = client.post("/api/v1/chat/", json=request_data)
            
            # Assertions
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["content"] == mock_chat_response["content"]
            assert "conversation_id" in response_data
            assert "message_id" in response_data
    
    @pytest.mark.asyncio
    async def test_chat_endpoint_conversation_not_found(self, mock_user):
        """Test chat request with non-existent conversation."""
        with patch('app.api.v1.chat.get_current_user', return_value=mock_user), \
             patch('app.api.v1.chat.get_db_session') as mock_db_session:
            
            # Mock database session
            mock_db = AsyncMock()
            mock_db_session.return_value.__aenter__.return_value = mock_db
            
            # Mock conversation query result (not found)
            mock_db.execute = AsyncMock()
            mock_conversation_result = MagicMock()
            mock_conversation_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_conversation_result
            
            # Test request with non-existent conversation
            request_data = {
                "message": "Hello",
                "conversation_id": str(uuid.uuid4()),
                "agent_type": "help"
            }
            
            response = client.post("/api/v1/chat/", json=request_data)
            
            # Assertions
            assert response.status_code == 404
            assert "Conversation not found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_chat_stream_endpoint_success(self, mock_user, mock_conversation):
        """Test successful streaming chat request."""
        with patch('app.api.v1.chat.get_current_user', return_value=mock_user), \
             patch('app.api.v1.chat.get_db_session') as mock_db_session, \
             patch('app.api.v1.chat.ChatService') as mock_chat_service_class:
            
            # Mock database session
            mock_db = AsyncMock()
            mock_db_session.return_value.__aenter__.return_value = mock_db
            
            # Mock chat service streaming
            mock_chat_service = AsyncMock()
            
            async def mock_streaming_response(*args, **kwargs):
                yield "Hello! "
                yield "I'm your AI assistant. "
                yield "How can I help you today?"
            
            mock_chat_service.generate_streaming_response = mock_streaming_response
            mock_chat_service_class.return_value = mock_chat_service
            
            # Mock database operations
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()
            mock_db.execute = AsyncMock()
            
            # Mock conversation query result
            mock_conversation_result = MagicMock()
            mock_conversation_result.scalar_one_or_none.return_value = mock_conversation
            mock_db.execute.return_value = mock_conversation_result
            
            # Test request
            request_data = {
                "message": "Hello",
                "conversation_id": str(mock_conversation.id),
                "agent_type": "help"
            }
            
            response = client.post("/api/v1/chat/stream", json=request_data)
            
            # Assertions
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/x-ndjson"
            assert "X-Conversation-Id" in response.headers
            assert "X-Message-Id" in response.headers
    
    @pytest.mark.asyncio
    async def test_create_conversation_success(self, mock_user):
        """Test successful conversation creation."""
        with patch('app.api.v1.chat.get_current_user', return_value=mock_user), \
             patch('app.api.v1.chat.get_db_session') as mock_db_session:
            
            # Mock database session
            mock_db = AsyncMock()
            mock_db_session.return_value.__aenter__.return_value = mock_db
            
            # Mock database operations
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()
            
            # Mock new conversation
            new_conversation = Conversation(
                id=uuid.uuid4(),
                organization_id=mock_user.organization_id,
                user_id=mock_user.id,
                title="Test Conversation",
                status="active"
            )
            
            # Mock conversation refresh
            def mock_refresh(obj):
                if isinstance(obj, Conversation):
                    obj.id = new_conversation.id
                    obj.created_at = "2024-01-01T00:00:00Z"
                    obj.updated_at = "2024-01-01T00:00:00Z"
            
            mock_db.refresh.side_effect = mock_refresh
            
            # Test request
            request_data = {
                "title": "Test Conversation",
                "context": {"topic": "testing"},
                "metadata": {"source": "test"}
            }
            
            response = client.post("/api/v1/chat/conversations", json=request_data)
            
            # Assertions
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["title"] == "Test Conversation"
            assert response_data["status"] == "active"
            assert "id" in response_data
    
    @pytest.mark.asyncio
    async def test_list_conversations_success(self, mock_user, mock_conversation):
        """Test successful conversation listing."""
        with patch('app.api.v1.chat.get_current_user', return_value=mock_user), \
             patch('app.api.v1.chat.get_db_session') as mock_db_session:
            
            # Mock database session
            mock_db = AsyncMock()
            mock_db_session.return_value.__aenter__.return_value = mock_db
            
            # Mock database queries
            mock_db.execute = AsyncMock()
            
            # Mock count query result
            mock_count_result = MagicMock()
            mock_count_result.scalars.return_value.all.return_value = [mock_conversation]
            mock_db.execute.return_value = mock_count_result
            
            # Mock conversations query result
            mock_conversations_result = MagicMock()
            mock_conversations_result.scalars.return_value.all.return_value = [mock_conversation]
            mock_db.execute.return_value = mock_conversations_result
            
            # Mock message count query
            mock_message_count_result = MagicMock()
            mock_message_count_result.scalars.return_value.all.return_value = [MagicMock()]
            mock_db.execute.return_value = mock_message_count_result
            
            # Test request
            response = client.get("/api/v1/chat/conversations?page=1&size=20")
            
            # Assertions
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["total"] == 1
            assert response_data["page"] == 1
            assert response_data["size"] == 20
            assert len(response_data["conversations"]) == 1
            assert response_data["conversations"][0]["title"] == "Test Conversation"
    
    @pytest.mark.asyncio
    async def test_get_conversation_success(self, mock_user, mock_conversation):
        """Test successful conversation retrieval."""
        with patch('app.api.v1.chat.get_current_user', return_value=mock_user), \
             patch('app.api.v1.chat.get_db_session') as mock_db_session:
            
            # Mock database session
            mock_db = AsyncMock()
            mock_db_session.return_value.__aenter__.return_value = mock_db
            
            # Mock database query
            mock_db.execute = AsyncMock()
            mock_conversation_result = MagicMock()
            mock_conversation_result.scalar_one_or_none.return_value = mock_conversation
            mock_db.execute.return_value = mock_conversation_result
            
            # Test request
            response = client.get(f"/api/v1/chat/conversations/{mock_conversation.id}")
            
            # Assertions
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["id"] == str(mock_conversation.id)
            assert response_data["title"] == "Test Conversation"
            assert response_data["status"] == "active"
    
    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, mock_user):
        """Test conversation retrieval with non-existent conversation."""
        with patch('app.api.v1.chat.get_current_user', return_value=mock_user), \
             patch('app.api.v1.chat.get_db_session') as mock_db_session:
            
            # Mock database session
            mock_db = AsyncMock()
            mock_db_session.return_value.__aenter__.return_value = mock_db
            
            # Mock database query (not found)
            mock_db.execute = AsyncMock()
            mock_conversation_result = MagicMock()
            mock_conversation_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_conversation_result
            
            # Test request
            response = client.get(f"/api/v1/chat/conversations/{uuid.uuid4()}")
            
            # Assertions
            assert response.status_code == 404
            assert "Conversation not found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_update_conversation_success(self, mock_user, mock_conversation):
        """Test successful conversation update."""
        with patch('app.api.v1.chat.get_current_user', return_value=mock_user), \
             patch('app.api.v1.chat.get_db_session') as mock_db_session:
            
            # Mock database session
            mock_db = AsyncMock()
            mock_db_session.return_value.__aenter__.return_value = mock_db
            
            # Mock database queries
            mock_db.execute = AsyncMock()
            mock_conversation_result = MagicMock()
            mock_conversation_result.scalar_one_or_none.return_value = mock_conversation
            mock_db.execute.return_value = mock_conversation_result
            
            # Mock database operations
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()
            
            # Test request
            request_data = {
                "title": "Updated Conversation Title",
                "status": "paused"
            }
            
            response = client.put(f"/api/v1/chat/conversations/{mock_conversation.id}", json=request_data)
            
            # Assertions
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["id"] == str(mock_conversation.id)
            assert response_data["title"] == "Updated Conversation Title"
            assert response_data["status"] == "paused"
    
    @pytest.mark.asyncio
    async def test_delete_conversation_success(self, mock_user, mock_conversation):
        """Test successful conversation deletion."""
        with patch('app.api.v1.chat.get_current_user', return_value=mock_user), \
             patch('app.api.v1.chat.get_db_session') as mock_db_session:
            
            # Mock database session
            mock_db = AsyncMock()
            mock_db_session.return_value.__aenter__.return_value = mock_db
            
            # Mock database queries
            mock_db.execute = AsyncMock()
            mock_conversation_result = MagicMock()
            mock_conversation_result.scalar_one_or_none.return_value = mock_conversation
            mock_db.execute.return_value = mock_conversation_result
            
            # Mock database operations
            mock_db.commit = AsyncMock()
            
            # Test request
            response = client.delete(f"/api/v1/chat/conversations/{mock_conversation.id}")
            
            # Assertions
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["message"] == "Conversation deleted successfully"
    
    @pytest.mark.asyncio
    async def test_get_conversation_messages_success(self, mock_user, mock_conversation, mock_message):
        """Test successful message retrieval."""
        with patch('app.api.v1.chat.get_current_user', return_value=mock_user), \
             patch('app.api.v1.chat.get_db_session') as mock_db_session:
            
            # Mock database session
            mock_db = AsyncMock()
            mock_db_session.return_value.__aenter__.return_value = mock_db
            
            # Mock database queries
            mock_db.execute = AsyncMock()
            
            # Mock conversation verification
            mock_conversation_result = MagicMock()
            mock_conversation_result.scalar_one_or_none.return_value = mock_conversation
            mock_db.execute.return_value = mock_conversation_result
            
            # Mock messages query
            mock_messages_result = MagicMock()
            mock_messages_result.scalars.return_value.all.return_value = [mock_message]
            mock_db.execute.return_value = mock_messages_result
            
            # Test request
            response = client.get(f"/api/v1/chat/conversations/{mock_conversation.id}/messages?page=1&size=50")
            
            # Assertions
            assert response.status_code == 200
            response_data = response.json()
            assert len(response_data) == 1
            assert response_data[0]["content"] == "Hello, how can you help me?"
            assert response_data[0]["role"] == "user"
    
    @pytest.mark.asyncio
    async def test_chat_endpoint_validation_error(self):
        """Test chat endpoint with validation error."""
        # Test request with missing required field
        request_data = {
            "agent_type": "help"
            # Missing "message" field
        }
        
        response = client.post("/api/v1/chat/", json=request_data)
        
        # Assertions
        assert response.status_code == 422
        response_data = response.json()
        assert response_data["error"] == "validation_error"
        assert "Request validation failed" in response_data["message"]
    
    @pytest.mark.asyncio
    async def test_chat_endpoint_invalid_agent_type(self):
        """Test chat endpoint with invalid agent type."""
        request_data = {
            "message": "Hello",
            "agent_type": "invalid_agent_type"
        }
        
        response = client.post("/api/v1/chat/", json=request_data)
        
        # Assertions
        assert response.status_code == 422
        response_data = response.json()
        assert response_data["error"] == "validation_error"
    
    @pytest.mark.asyncio
    async def test_chat_endpoint_invalid_temperature(self):
        """Test chat endpoint with invalid temperature value."""
        request_data = {
            "message": "Hello",
            "temperature": 3.0  # Invalid: should be <= 2.0
        }
        
        response = client.post("/api/v1/chat/", json=request_data)
        
        # Assertions
        assert response.status_code == 422
        response_data = response.json()
        assert response_data["error"] == "validation_error"
    
    @pytest.mark.asyncio
    async def test_chat_endpoint_invalid_max_tokens(self):
        """Test chat endpoint with invalid max_tokens value."""
        request_data = {
            "message": "Hello",
            "max_tokens": 10000  # Invalid: should be <= 8000
        }
        
        response = client.post("/api/v1/chat/", json=request_data)
        
        # Assertions
        assert response.status_code == 422
        response_data = response.json()
        assert response_data["error"] == "validation_error"
    
    @pytest.mark.asyncio
    async def test_conversation_pagination(self, mock_user, mock_conversation):
        """Test conversation listing with pagination."""
        with patch('app.api.v1.chat.get_current_user', return_value=mock_user), \
             patch('app.api.v1.chat.get_db_session') as mock_db_session:
            
            # Mock database session
            mock_db = AsyncMock()
            mock_db_session.return_value.__aenter__.return_value = mock_db
            
            # Mock database queries
            mock_db.execute = AsyncMock()
            
            # Mock count query result (multiple conversations)
            mock_count_result = MagicMock()
            mock_count_result.scalars.return_value.all.return_value = [mock_conversation] * 25
            mock_db.execute.return_value = mock_count_result
            
            # Mock conversations query result (paginated)
            mock_conversations_result = MagicMock()
            mock_conversations_result.scalars.return_value.all.return_value = [mock_conversation] * 20
            mock_db.execute.return_value = mock_conversations_result
            
            # Mock message count query
            mock_message_count_result = MagicMock()
            mock_message_count_result.scalars.return_value.all.return_value = [MagicMock()]
            mock_db.execute.return_value = mock_message_count_result
            
            # Test pagination
            response = client.get("/api/v1/chat/conversations?page=1&size=20")
            
            # Assertions
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["total"] == 25
            assert response_data["page"] == 1
            assert response_data["size"] == 20
            assert response_data["has_next"] == True
            assert response_data["has_previous"] == False
            assert len(response_data["conversations"]) == 20
    
    @pytest.mark.asyncio
    async def test_conversation_status_filtering(self, mock_user, mock_conversation):
        """Test conversation listing with status filtering."""
        with patch('app.api.v1.chat.get_current_user', return_value=mock_user), \
             patch('app.api.v1.chat.get_db_session') as mock_db_session:
            
            # Mock database session
            mock_db = AsyncMock()
            mock_db_session.return_value.__aenter__.return_value = mock_db
            
            # Mock database queries
            mock_db.execute = AsyncMock()
            
            # Mock count query result
            mock_count_result = MagicMock()
            mock_count_result.scalars.return_value.all.return_value = [mock_conversation]
            mock_db.execute.return_value = mock_count_result
            
            # Mock conversations query result
            mock_conversations_result = MagicMock()
            mock_conversations_result.scalars.return_value.all.return_value = [mock_conversation]
            mock_db.execute.return_value = mock_conversations_result
            
            # Mock message count query
            mock_message_count_result = MagicMock()
            mock_message_count_result.scalars.return_value.all.return_value = [MagicMock()]
            mock_db.execute.return_value = mock_message_count_result
            
            # Test status filtering
            response = client.get("/api/v1/chat/conversations?status=active")
            
            # Assertions
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["total"] == 1
            assert len(response_data["conversations"]) == 1
            assert response_data["conversations"][0]["status"] == "active"


class TestChatServiceIntegration:
    """Integration tests for chat service with API."""
    
    @pytest.mark.asyncio
    async def test_chat_service_integration(self, mock_user, mock_conversation):
        """Test integration between chat API and chat service."""
        with patch('app.api.v1.chat.get_current_user', return_value=mock_user), \
             patch('app.api.v1.chat.get_db_session') as mock_db_session, \
             patch('app.api.v1.chat.ChatService') as mock_chat_service_class:
            
            # Mock database session
            mock_db = AsyncMock()
            mock_db_session.return_value.__aenter__.return_value = mock_db
            
            # Mock chat service
            mock_chat_service = AsyncMock()
            mock_chat_service_class.return_value = mock_chat_service
            
            # Test different agent types
            agent_types = ["query", "action", "analytics", "scheduler", "compliance", "help"]
            
            for agent_type in agent_types:
                # Mock response for this agent type
                mock_response = {
                    "content": f"Response from {agent_type} agent",
                    "agent_type": agent_type,
                    "model_used": "gpt-4",
                    "tokens_used": 20,
                    "execution_time_ms": 1000
                }
                mock_chat_service.generate_response.return_value = mock_response
                
                # Mock database operations
                mock_db.add = MagicMock()
                mock_db.commit = AsyncMock()
                mock_db.refresh = AsyncMock()
                mock_db.execute = AsyncMock()
                
                # Mock conversation query result
                mock_conversation_result = MagicMock()
                mock_conversation_result.scalar_one_or_none.return_value = mock_conversation
                mock_db.execute.return_value = mock_conversation_result
                
                # Test request
                request_data = {
                    "message": f"Test message for {agent_type} agent",
                    "conversation_id": str(mock_conversation.id),
                    "agent_type": agent_type
                }
                
                response = client.post("/api/v1/chat/", json=request_data)
                
                # Assertions
                assert response.status_code == 200
                response_data = response.json()
                assert response_data["agent_type"] == agent_type
                assert response_data["content"] == f"Response from {agent_type} agent"
                
                # Verify chat service was called correctly
                mock_chat_service.generate_response.assert_called_with(
                    conversation_id=mock_conversation.id,
                    user_message=f"Test message for {agent_type} agent",
                    agent_type=agent_type,
                    model=None,
                    temperature=0.7,
                    max_tokens=4000,
                    context={}
                )
    
    @pytest.mark.asyncio
    async def test_chat_service_error_handling(self, mock_user, mock_conversation):
        """Test error handling in chat service integration."""
        with patch('app.api.v1.chat.get_current_user', return_value=mock_user), \
             patch('app.api.v1.chat.get_db_session') as mock_db_session, \
             patch('app.api.v1.chat.ChatService') as mock_chat_service_class:
            
            # Mock database session
            mock_db = AsyncMock()
            mock_db_session.return_value.__aenter__.return_value = mock_db
            
            # Mock chat service that raises an exception
            mock_chat_service = AsyncMock()
            mock_chat_service.generate_response.side_effect = Exception("AI service unavailable")
            mock_chat_service_class.return_value = mock_chat_service
            
            # Mock database operations
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()
            mock_db.execute = AsyncMock()
            
            # Mock conversation query result
            mock_conversation_result = MagicMock()
            mock_conversation_result.scalar_one_or_none.return_value = mock_conversation
            mock_db.execute.return_value = mock_conversation_result
            
            # Test request
            request_data = {
                "message": "Test message",
                "conversation_id": str(mock_conversation.id),
                "agent_type": "help"
            }
            
            response = client.post("/api/v1/chat/", json=request_data)
            
            # Assertions
            assert response.status_code == 500
            response_data = response.json()
            assert "Failed to generate response" in response_data["detail"]
            assert "AI service unavailable" in response_data["detail"]
