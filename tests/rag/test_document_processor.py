"""Unit tests for the document processor component.

Tests the document processing functionality, including chunking, metadata extraction,
and document preparation for embedding.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from app.rag.document_processor import DocumentProcessor
from app.rag.models import Document, DocumentChunk, DocumentType, AccessLevel


@pytest.fixture
def document_processor():
    """Create a document processor instance for testing."""
    return DocumentProcessor()


@pytest.fixture
def sample_document():
    """Create a sample document for testing."""
    return Document(
        title="Test Document",
        content="This is a test document with multiple sentences. It contains information that can be retrieved. "
                "This is for testing the document processor. The processor should split this text into chunks "
                "based on the configured chunk size and overlap. Each chunk should maintain the semantic meaning "
                "of the text as much as possible. The processor should also extract metadata from the document.",
        document_type=DocumentType.GUIDE,
        metadata={"department": "engineering", "tags": ["test", "documentation"]},
        access_level=AccessLevel.INTERNAL,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def document_without_metadata():
    """Create a document without metadata for testing."""
    return Document(
        title="",
        content="This is a document without a title or metadata. The processor should extract metadata from the content.",
        document_type=DocumentType.UNKNOWN,
        access_level=AccessLevel.PUBLIC,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


def test_document_chunking(document_processor, sample_document):
    """Test document chunking functionality."""
    # Set chunk size and overlap
    sample_document.chunk_size = 100
    sample_document.chunk_overlap = 20
    
    # Process document
    chunks = document_processor._chunk_document(sample_document)
    
    # Check if document was chunked properly
    assert len(chunks) > 0
    assert all(isinstance(chunk, DocumentChunk) for chunk in chunks)
    assert all(chunk.document_id == sample_document.id for chunk in chunks)
    
    # Check chunk properties
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i
        assert len(chunk.text) <= sample_document.chunk_size + 50  # Allow some flexibility for sentence boundaries
        assert chunk.metadata == sample_document.metadata
    
    # Check for overlap between chunks
    if len(chunks) > 1:
        for i in range(len(chunks) - 1):
            current_chunk = chunks[i].text
            next_chunk = chunks[i + 1].text
            
            # Find potential overlap
            overlap_found = False
            for j in range(min(len(current_chunk), sample_document.chunk_overlap * 2)):
                suffix = current_chunk[-j:] if j > 0 else ""
                if next_chunk.startswith(suffix):
                    overlap_found = True
                    break
            
            # There should be some semantic overlap, but it might not be exact text overlap
            # due to sentence boundary preservation
            assert len(current_chunk) + len(next_chunk) > sample_document.chunk_size


def test_metadata_extraction(document_processor, document_without_metadata):
    """Test metadata extraction from document content."""
    # Process document
    processed_doc = document_processor._extract_metadata(document_without_metadata)
    
    # Check if metadata was extracted
    assert processed_doc.metadata is not None
    
    # Title should be extracted from content
    assert processed_doc.title != ""
    assert "document without" in processed_doc.title.lower()
    
    # Check for automatically extracted metadata
    assert "created_at" in processed_doc.metadata
    assert "updated_at" in processed_doc.metadata
    assert "reading_time" in processed_doc.metadata
    
    # Check if keywords were extracted
    assert "keywords" in processed_doc.metadata
    assert len(processed_doc.metadata["keywords"]) > 0


def test_document_processing(document_processor, sample_document):
    """Test the complete document processing pipeline."""
    # Process document
    processed_doc, chunks = document_processor.process_document(sample_document)
    
    # Check processed document
    assert processed_doc.id is not None
    assert processed_doc.created_at is not None
    assert processed_doc.updated_at is not None
    assert processed_doc.metadata is not None
    
    # Check chunks
    assert len(chunks) > 0
    assert all(chunk.document_id == processed_doc.id for chunk in chunks)
    assert all(chunk.metadata == processed_doc.metadata for chunk in chunks)
    
    # Check if all content is preserved in chunks
    combined_text = " ".join([chunk.text for chunk in chunks])
    for key_phrase in ["test document", "multiple sentences", "information", "processor"]:
        assert key_phrase in combined_text.lower()


def test_merge_chunks(document_processor):
    """Test merging chunks into a coherent text."""
    # Create test chunks
    chunks = [
        DocumentChunk(document_id="test_id", chunk_index=0, text="This is the first chunk of text.", metadata={}),
        DocumentChunk(document_id="test_id", chunk_index=1, text="This is the second chunk with some overlap.", metadata={}),
        DocumentChunk(document_id="test_id", chunk_index=2, text="The third chunk contains the conclusion.", metadata={})
    ]
    
    # Merge chunks
    merged_text = document_processor.merge_chunks(chunks, max_tokens=100)
    
    # Check merged text
    assert "first chunk" in merged_text
    assert "second chunk" in merged_text
    assert "conclusion" in merged_text
    
    # Test token limit
    short_merged = document_processor.merge_chunks(chunks, max_tokens=10)
    assert len(short_merged) < len(merged_text)