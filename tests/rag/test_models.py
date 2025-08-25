"""Unit tests for the RAG models module.

Tests the Pydantic models used in the RAG engine.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.rag.models import (
    Document, DocumentType, AccessLevel, DocumentChunk, 
    SearchQuery, SearchFilter, SearchResult, KafkaMessage, MessageType
)


def test_document_model():
    """Test Document model validation."""
    # Valid document
    document = Document(
        title="Test Document",
        content="This is a test document.",
        document_type=DocumentType.GUIDE,
        access_level=AccessLevel.INTERNAL,
        metadata={"department": "engineering", "tags": ["test"]}
    )
    
    assert document.title == "Test Document"
    assert document.content == "This is a test document."
    assert document.document_type == DocumentType.GUIDE
    assert document.access_level == AccessLevel.INTERNAL
    assert document.metadata["department"] == "engineering"
    assert document.metadata["tags"] == ["test"]
    assert document.created_at is not None
    assert document.updated_at is not None
    
    # Test with document_id
    document_with_id = Document(
        document_id="doc123",
        title="Test Document",
        content="This is a test document.",
        document_type=DocumentType.GUIDE,
        access_level=AccessLevel.INTERNAL,
        metadata={"department": "engineering", "tags": ["test"]}
    )
    
    assert document_with_id.document_id == "doc123"
    
    # Test invalid document (missing required fields)
    with pytest.raises(ValidationError):
        Document(title="Test Document")


def test_document_chunk_model():
    """Test DocumentChunk model validation."""
    # Valid document chunk
    chunk = DocumentChunk(
        document_id="doc123",
        chunk_id="chunk1",
        content="This is a chunk of text.",
        metadata={"position": 1, "tokens": 7}
    )
    
    assert chunk.document_id == "doc123"
    assert chunk.chunk_id == "chunk1"
    assert chunk.content == "This is a chunk of text."
    assert chunk.metadata["position"] == 1
    assert chunk.metadata["tokens"] == 7
    
    # Test invalid chunk (missing required fields)
    with pytest.raises(ValidationError):
        DocumentChunk(document_id="doc123")


def test_search_query_model():
    """Test SearchQuery model validation."""
    # Valid search query without filters
    query = SearchQuery(
        query_text="test query",
        max_results=5
    )
    
    assert query.query_text == "test query"
    assert query.max_results == 5
    assert query.filters is None
    
    # Valid search query with filters
    query_with_filters = SearchQuery(
        query_text="test query",
        filters=SearchFilter(
            document_type=DocumentType.GUIDE,
            access_level=AccessLevel.INTERNAL,
            metadata={"department": "engineering"}
        ),
        max_results=10
    )
    
    assert query_with_filters.query_text == "test query"
    assert query_with_filters.max_results == 10
    assert query_with_filters.filters.document_type == DocumentType.GUIDE
    assert query_with_filters.filters.access_level == AccessLevel.INTERNAL
    assert query_with_filters.filters.metadata["department"] == "engineering"
    
    # Test invalid query (missing required fields)
    with pytest.raises(ValidationError):
        SearchQuery(max_results=5)


def test_search_filter_model():
    """Test SearchFilter model validation."""
    # Valid search filter with all fields
    filter_all = SearchFilter(
        document_type=DocumentType.GUIDE,
        access_level=AccessLevel.INTERNAL,
        metadata={"department": "engineering", "tags": ["test"]},
        date_range={"start": datetime.utcnow(), "end": datetime.utcnow()}
    )
    
    assert filter_all.document_type == DocumentType.GUIDE
    assert filter_all.access_level == AccessLevel.INTERNAL
    assert filter_all.metadata["department"] == "engineering"
    assert filter_all.date_range["start"] is not None
    
    # Valid search filter with some fields
    filter_some = SearchFilter(
        document_type=DocumentType.GUIDE
    )
    
    assert filter_some.document_type == DocumentType.GUIDE
    assert filter_some.access_level is None
    assert filter_some.metadata is None
    assert filter_some.date_range is None
    
    # Valid empty search filter
    filter_empty = SearchFilter()
    
    assert filter_empty.document_type is None
    assert filter_empty.access_level is None
    assert filter_empty.metadata is None
    assert filter_empty.date_range is None


def test_search_result_model():
    """Test SearchResult model validation."""
    # Valid search result with all fields
    result = SearchResult(
        document_id="doc123",
        content="This is a test document.",
        score=0.95,
        metadata={"title": "Test Document", "document_type": "guide"}
    )
    
    assert result.document_id == "doc123"
    assert result.content == "This is a test document."
    assert result.score == 0.95
    assert result.metadata["title"] == "Test Document"
    
    # Test invalid result (missing required fields)
    with pytest.raises(ValidationError):
        SearchResult(document_id="doc123")


def test_kafka_message_model():
    """Test KafkaMessage model validation."""
    # Valid message for document ingestion
    ingestion_msg = KafkaMessage(
        message_type=MessageType.DOCUMENT_INGESTION,
        data={
            "document": {
                "title": "Test Document",
                "content": "This is a test document.",
                "document_type": "guide",
                "access_level": "internal",
                "metadata": {"department": "engineering"}
            }
        }
    )
    
    assert ingestion_msg.message_type == MessageType.DOCUMENT_INGESTION
    assert ingestion_msg.data["document"]["title"] == "Test Document"
    
    # Valid message for document search
    search_msg = KafkaMessage(
        message_type=MessageType.DOCUMENT_SEARCH,
        data={
            "query": {
                "query_text": "test query",
                "max_results": 5
            }
        }
    )
    
    assert search_msg.message_type == MessageType.DOCUMENT_SEARCH
    assert search_msg.data["query"]["query_text"] == "test query"
    
    # Valid message for document update
    update_msg = KafkaMessage(
        message_type=MessageType.DOCUMENT_UPDATE,
        data={
            "document_id": "doc123",
            "document": {
                "title": "Updated Document",
                "content": "This is an updated document.",
                "document_type": "guide",
                "access_level": "internal"
            }
        }
    )
    
    assert update_msg.message_type == MessageType.DOCUMENT_UPDATE
    assert update_msg.data["document_id"] == "doc123"
    
    # Valid message for document deletion
    delete_msg = KafkaMessage(
        message_type=MessageType.DOCUMENT_DELETION,
        data={"document_id": "doc123"}
    )
    
    assert delete_msg.message_type == MessageType.DOCUMENT_DELETION
    assert delete_msg.data["document_id"] == "doc123"
    
    # Test invalid message (missing required fields)
    with pytest.raises(ValidationError):
        KafkaMessage(message_type=MessageType.DOCUMENT_INGESTION)
    
    # Test invalid message (missing data fields)
    with pytest.raises(ValidationError):
        KafkaMessage(
            message_type=MessageType.DOCUMENT_INGESTION,
            data={}
        )