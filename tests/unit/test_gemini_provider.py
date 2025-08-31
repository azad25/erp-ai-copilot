"""Unit tests for Gemini provider system prompt handling."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.llm_service import GeminiProvider, LLMRequest, LLMMessage

@pytest.fixture
def gemini_provider():
    """Fixture providing a GeminiProvider instance with a mock API key."""
    return GeminiProvider(api_key="test-api-key")

@pytest.mark.asyncio
async def test_gemini_system_prompt(gemini_provider):
    """Test that Gemini provider correctly includes system prompt in the request."""
    # Mock the API response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "candidates": [{
            "content": {"parts": [{"text": "Test response"}]}
        }]
    }
    
    # Mock the async client
    with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        # Create a test request with a system prompt
        request = LLMRequest(
            messages=[
                LLMMessage(role="user", content="Hello")
            ],
            model="gemini-1.5-pro",
            system_prompt="You are a helpful assistant."
        )
        
        # Call the generate method
        response = await gemini_provider.generate_content(
            prompt="USER: Hello",
            model="gemini-1.5-pro",
            system_instruction="You are a helpful assistant."
        )
        
        # Verify the API was called with the correct arguments
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        
        # Check that the system instruction was included in the request
        assert "systemInstruction" in kwargs["json"]
        assert kwargs["json"]["systemInstruction"]["parts"][0]["text"] == "You are a helpful assistant."
        
        # Check that the response was parsed correctly
        assert response == "Test response"

@pytest.mark.asyncio
async def test_gemini_no_system_prompt(gemini_provider):
    """Test that Gemini provider works without a system prompt."""
    # Mock the API response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "candidates": [{
            "content": {"parts": [{"text": "Test response"}]}
        }]
    }
    
    # Mock the async client
    with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        # Call the generate method without a system prompt
        response = await gemini_provider.generate_content(
            prompt="USER: Hello",
            model="gemini-1.5-pro"
        )
        
        # Verify the API was called with the correct arguments
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        
        # Check that no system instruction was included
        assert "systemInstruction" not in kwargs["json"]
        
        # Check that the response was parsed correctly
        assert response == "Test response"
