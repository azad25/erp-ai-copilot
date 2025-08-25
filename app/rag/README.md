# RAG Engine

## Overview

The Retrieval-Augmented Generation (RAG) engine is a comprehensive system for document processing, embedding, storage, and retrieval. It integrates with the ERP AI Copilot to provide knowledge retrieval capabilities for AI agents.

## Architecture

The RAG engine follows a modular architecture with the following components:

### Core Components

1. **RAGEngine** (`engine.py`): The central component that orchestrates document processing, embedding, and retrieval operations.

2. **VectorStore** (`vector_store.py`): Manages interactions with the Qdrant vector database for storing and retrieving document embeddings.

3. **EmbeddingProvider** (`embeddings.py`): Generates vector embeddings for text using SentenceTransformer models.

4. **DocumentProcessor** (`document_processor.py`): Handles document chunking, metadata extraction, and preparation for embedding.

5. **RAGService** (`service.py`): High-level service that integrates all components and provides a unified API for document operations.

### Integration Components

1. **CacheManager** (`cache.py`): Provides caching for search results and document metadata using Redis.

2. **KafkaManager** (`kafka_integration.py`): Manages asynchronous document processing and retrieval operations using Kafka.

3. **API Endpoints** (`api.py`): FastAPI endpoints for document ingestion, retrieval, and search.

## Data Flow

1. **Document Ingestion**:
   - Document is received via API
   - Document is processed and chunked
   - Chunks are embedded and stored in Qdrant
   - Document metadata is stored in MongoDB
   - Document is indexed for retrieval

2. **Document Retrieval**:
   - Query is received via API
   - Query is embedded
   - Similar documents are retrieved from Qdrant
   - Results are filtered based on permissions and metadata
   - Results are returned to the user

## Configuration

The RAG engine is configured via the `settings.py` file, which includes:

- `QdrantSettings`: Configuration for the Qdrant vector database
- `RAGSettings`: Configuration for the RAG engine, including embedding model, collection prefix, etc.

## Usage

### Document Ingestion

```python
from app.rag.models import Document, DocumentType, AccessLevel
from app.rag.service import RAGService
from app.database.connection import get_db_manager

# Initialize RAG service
db_manager = await get_db_manager()
rag_service = RAGService(db_manager)
await rag_service.initialize()

# Create document
document = Document(
    title="Sample Document",
    content="This is a sample document for testing the RAG engine.",
    document_type=DocumentType.GUIDE,
    metadata={"department": "engineering", "tags": ["sample", "test"]},
    access_level=AccessLevel.INTERNAL
)

# Ingest document
success, document_id, vector_ids = await rag_service.ingest_document(document)
```

### Document Search

```python
from app.rag.models import SearchQuery, SearchFilter
from app.rag.service import RAGService
from app.database.connection import get_db_manager

# Initialize RAG service
db_manager = await get_db_manager()
rag_service = RAGService(db_manager)
await rag_service.initialize()

# Create search query
query = SearchQuery(
    query_text="sample document",
    filters=SearchFilter(document_type="guide"),
    max_results=5
)

# Perform search
results = await rag_service.search(query)

# Process results
for result in results:
    print(f"Document: {result.title}")
    print(f"Score: {result.score}")
    print(f"Content: {result.content[:100]}...")
```

## API Endpoints

- `POST /api/v1/rag/documents`: Ingest a new document
- `GET /api/v1/rag/documents/{document_id}`: Retrieve a document by ID
- `PUT /api/v1/rag/documents/{document_id}`: Update an existing document
- `DELETE /api/v1/rag/documents/{document_id}`: Delete a document
- `POST /api/v1/rag/search`: Search documents using semantic search

## Integration with AI Agents

The RAG engine integrates with AI agents through the `DocumentSearchTool`, `KnowledgeIngestionTool`, and `SemanticSearchTool` classes in `rag_tools.py`. These tools provide a standardized interface for agents to interact with the RAG engine.

## Dependencies

- Qdrant: Vector database for storing and retrieving embeddings
- SentenceTransformer: For generating text embeddings
- MongoDB: For storing document metadata
- Redis: For caching search results
- Kafka: For asynchronous document processing