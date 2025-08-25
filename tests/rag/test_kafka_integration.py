"""Unit tests for the Kafka integration component.

Tests the Kafka message handling functionality, including message publishing,
consumer registration, and message processing.
"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch

from app.rag.kafka_integration import KafkaManager, KafkaMessage
from app.rag.models import Document, DocumentType, AccessLevel


@pytest.fixture
def mock_kafka_producer():
    """Create a mock Kafka producer for testing."""
    producer = MagicMock()
    producer.send_and_wait = AsyncMock()
    producer.start = AsyncMock()
    producer.stop = AsyncMock()
    return producer


@pytest.fixture
def mock_kafka_consumer():
    """Create a mock Kafka consumer for testing."""
    consumer = MagicMock()
    consumer.start = AsyncMock()
    consumer.stop = AsyncMock()
    return consumer


@pytest.fixture
def mock_aiokafka():
    """Create a mock aiokafka module for testing."""
    with patch("app.rag.kafka_integration.AIOKafkaProducer", return_value=mock_kafka_producer()), \
         patch("app.rag.kafka_integration.AIOKafkaConsumer", return_value=mock_kafka_consumer()):
        yield


@pytest.fixture
def kafka_manager(mock_aiokafka):
    """Create a Kafka manager for testing."""
    return KafkaManager(bootstrap_servers="localhost:9092")


@pytest.fixture
def sample_document():
    """Create a sample document for testing."""
    return Document(
        title="Test Document",
        content="This is a test document for Kafka integration testing.",
        document_type=DocumentType.GUIDE,
        access_level=AccessLevel.INTERNAL,
        metadata={"department": "engineering", "tags": ["test", "kafka"]}
    )


@pytest.mark.asyncio
async def test_initialize_and_shutdown(kafka_manager):
    """Test Kafka manager initialization and shutdown."""
    # Initialize Kafka manager
    await kafka_manager.initialize()
    
    # Check if producer was started
    kafka_manager.producer.start.assert_called_once()
    
    # Shutdown Kafka manager
    await kafka_manager.shutdown()
    
    # Check if producer was stopped
    kafka_manager.producer.stop.assert_called_once()


@pytest.mark.asyncio
async def test_send_document_ingestion_message(kafka_manager, sample_document):
    """Test sending a document ingestion message."""
    # Send message
    await kafka_manager.send_document_ingestion_message(sample_document)
    
    # Check if message was sent correctly
    kafka_manager.producer.send_and_wait.assert_called_once()
    args, _ = kafka_manager.producer.send_and_wait.call_args
    
    # Check topic
    assert args[0] == "document_ingestion"
    
    # Check message content
    message_value = args[1]
    message_dict = json.loads(message_value)
    assert "message_type" in message_dict
    assert message_dict["message_type"] == "document_ingestion"
    assert "document" in message_dict
    assert message_dict["document"]["title"] == sample_document.title


@pytest.mark.asyncio
async def test_send_document_search_message(kafka_manager):
    """Test sending a document search message."""
    # Test data
    query = "test query"
    filters = {"document_type": "guide"}
    
    # Send message
    await kafka_manager.send_document_search_message(query, filters)
    
    # Check if message was sent correctly
    kafka_manager.producer.send_and_wait.assert_called_once()
    args, _ = kafka_manager.producer.send_and_wait.call_args
    
    # Check topic
    assert args[0] == "document_search"
    
    # Check message content
    message_value = args[1]
    message_dict = json.loads(message_value)
    assert "message_type" in message_dict
    assert message_dict["message_type"] == "document_search"
    assert "query" in message_dict
    assert message_dict["query"] == query
    assert "filters" in message_dict
    assert message_dict["filters"] == filters


@pytest.mark.asyncio
async def test_send_document_update_message(kafka_manager, sample_document):
    """Test sending a document update message."""
    # Send message
    document_id = "doc123"
    await kafka_manager.send_document_update_message(document_id, sample_document)
    
    # Check if message was sent correctly
    kafka_manager.producer.send_and_wait.assert_called_once()
    args, _ = kafka_manager.producer.send_and_wait.call_args
    
    # Check topic
    assert args[0] == "document_update"
    
    # Check message content
    message_value = args[1]
    message_dict = json.loads(message_value)
    assert "message_type" in message_dict
    assert message_dict["message_type"] == "document_update"
    assert "document_id" in message_dict
    assert message_dict["document_id"] == document_id
    assert "document" in message_dict


@pytest.mark.asyncio
async def test_send_document_deletion_message(kafka_manager):
    """Test sending a document deletion message."""
    # Send message
    document_id = "doc123"
    await kafka_manager.send_document_deletion_message(document_id)
    
    # Check if message was sent correctly
    kafka_manager.producer.send_and_wait.assert_called_once()
    args, _ = kafka_manager.producer.send_and_wait.call_args
    
    # Check topic
    assert args[0] == "document_deletion"
    
    # Check message content
    message_value = args[1]
    message_dict = json.loads(message_value)
    assert "message_type" in message_dict
    assert message_dict["message_type"] == "document_deletion"
    assert "document_id" in message_dict
    assert message_dict["document_id"] == document_id


@pytest.mark.asyncio
async def test_register_consumer(kafka_manager):
    """Test registering a consumer for a topic."""
    # Test data
    topic = "test_topic"
    group_id = "test_group"
    handler = AsyncMock()
    
    # Register consumer
    await kafka_manager.register_consumer(topic, group_id, handler)
    
    # Check if consumer was registered and started
    assert topic in kafka_manager.consumers
    kafka_manager.consumers[topic].start.assert_called_once()


@pytest.mark.asyncio
async def test_kafka_message_model():
    """Test the KafkaMessage model."""
    # Create a message
    message = KafkaMessage(
        message_type="test_type",
        data={"key": "value"},
        timestamp="2023-01-01T12:00:00"
    )
    
    # Check message properties
    assert message.message_type == "test_type"
    assert message.data == {"key": "value"}
    assert message.timestamp == "2023-01-01T12:00:00"
    
    # Test serialization
    serialized = message.model_dump_json()
    deserialized = KafkaMessage.model_validate_json(serialized)
    
    assert deserialized.message_type == message.message_type
    assert deserialized.data == message.data
    assert deserialized.timestamp == message.timestamp