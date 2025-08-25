# UNIBASE ERP AI Copilot - Developer Documentation

## Overview

The UNIBASE ERP AI Copilot is a comprehensive AI-powered assistant system built with FastAPI, featuring a multi-agent architecture that provides intelligent automation, analytics, and assistance for ERP operations. This document provides a complete guide for developers working with the system.

## Architecture Overview

### Core Architecture Components

```
┌─────────────────────────────────────────────────────────────┐
│                        API Layer                             │
├─────────────────────────────────────────────────────────────┤
│  REST API (FastAPI)  │  WebSocket API  │  gRPC API         │
│  /v1/chat            │  /ws/chat       │  AgentService     │
│  /v1/rag             │  /ws/analytics  │  TaskService      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Service Layer                             │
├─────────────────────────────────────────────────────────────┤
│  ChatService         │  RAGService        │  AgentService    │
│  - Conversation Mgmt │  - Document Ingest │  - Task Exec   │
│  - Message Processing │  - Semantic Search │  - Orchestration│
│  - Streaming Support │  - Vector Storage  │  - Monitoring   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Agent Layer                               │
├─────────────────────────────────────────────────────────────┤
│  Master Agent        │  Agent Orchestrator  │  Base Agents  │
│  - Task Routing      │  - Registration      │  - 6 Specialized│
│  - Workflow Mgmt     │  - Load Balancing    │  - Tool Access  │
│  - Result Synthesis  │  - Health Monitoring │  - LLM Integration│
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Tools Layer                               │
├─────────────────────────────────────────────────────────────┤
│  RAG Tools           │  ERP Tools        │  Integration Tools│
│  - Document Search   │  - CRUD Operations │  - External APIs  │
│  - Knowledge Ingest  │  - Workflow Triggers│  - Webhooks      │
│  - Semantic Search   │  - Data Validation │  - Event Processing│
└─────────────────────────────────────────────────────────────┘
```

## Request Flow Architecture

### 1. HTTP Request Flow

```
Client → FastAPI Router → ChatService → AgentOrchestrator → MasterAgent → Specialized Agent → Tool Execution → Response
```

#### Detailed Flow:

1. **API Entry Point** (`app/api/v1/chat.py`)
   - REST endpoints: `/chat`, `/chat/stream`
   - Request validation via Pydantic models
   - Authentication via JWT tokens
   - Rate limiting per user

2. **Chat Service** (`app/services/chat_service.py`)
   - Conversation management
   - Message persistence
   - Context building
   - Agent orchestration integration

3. **Agent Orchestrator** (`app/agents/agent_orchestrator.py`)
   - Agent registration and discovery
   - Load balancing across agents
   - Health monitoring
   - Task queue management

4. **Master Agent** (`app/agents/master_agent.py`)
   - Intelligent task routing
   - Multi-agent workflow orchestration
   - Result synthesis
   - Error handling and recovery

5. **Specialized Agents** (6 types)
   - Query Agent: Information retrieval
   - Action Agent: CRUD operations
   - Analytics Agent: Data analysis
   - Scheduler Agent: Task automation
   - Compliance Agent: Regulatory checks
   - Help Agent: User assistance

### 2. WebSocket Request Flow

```
Client → WebSocket Connection → ChatService → Streaming Response → Real-time Updates
```

- Supports real-time chat with streaming responses
- Bidirectional communication for live updates
- Connection state management

### 3. gRPC Request Flow

```
Client → gRPC Service → AgentService → Direct Agent Access → Response
```

- High-performance agent communication
- Service-to-service calls
- Streaming support for large payloads

## Implementation Status

### ✅ Fully Implemented Features

#### Core Infrastructure
- **FastAPI Application** (`app/main.py`)
  - Complete REST API setup
  - CORS middleware
  - Exception handling
  - Lifespan management

- **Database Layer**
  - Async SQLAlchemy integration
  - Conversation and message models
  - User authentication tables
  - Vector storage for RAG

- **Agent System**
  - **Agent Orchestrator**: Complete with registration, health checks, load balancing
  - **Master Agent**: Full orchestration with 6 specialized agents
  - **All 6 Agent Types**: Query, Action, Analytics, Scheduler, Compliance, Help
  - **Base Agent Framework**: Abstract base class with tool integration

- **API Endpoints**
  - **Chat API**: Complete with streaming support
  - **RAG API**: Document ingestion and search
  - **Agent API**: Direct agent execution
  - **Dashboard API**: Analytics and metrics

- **RAG System**
  - **Document Processing**: PDF, DOCX, TXT support
  - **Vector Storage**: ChromaDB integration
  - **Semantic Search**: Embedding-based search
  - **Knowledge Ingestion**: Automated document ingestion

- **Tools Implementation**
  - **RAG Tools**: Document search, knowledge ingestion, semantic search
  - **ERP Tools**: CRUD operations, workflow triggers
  - **Integration Tools**: External API calls, webhooks
  - **Command Tools**: System command execution

- **Security Features**
  - JWT-based authentication
  - Rate limiting per user
  - Input validation
  - SQL injection protection

- **Monitoring & Observability**
  - Prometheus metrics integration
  - Structured logging with correlation IDs
  - Health check endpoints
  - Performance monitoring

### ⚠️ Partially Implemented Features

#### Event System
- **Kafka Integration**: Infrastructure exists but not fully wired
- **Async Processing**: Celery tasks defined but limited usage
- **Real-time Notifications**: WebSocket infrastructure ready

#### Advanced Features
- **Multi-tenant Support**: Database schema supports it, full implementation pending
- **Advanced Analytics**: Basic metrics implemented, deep analytics pending
- **Compliance Reporting**: Framework exists, specific reports pending

### ❌ Not Yet Implemented

- **Advanced Caching**: Redis caching layer
- **CDN Integration**: Static asset serving
- **Advanced Search**: Elasticsearch integration
- **ML Model Serving**: Dedicated model serving infrastructure
- **Advanced Security**: OAuth2, SAML integration

## Code Structure

```
erp-ai-copilot/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── api/
│   │   └── v1/                 # API endpoints
│   │       ├── chat.py         # Chat endpoints
│   │       ├── rag.py          # RAG endpoints
│   │       ├── dashboard.py    # Analytics endpoints
│   │       └── infrastructure.py # System endpoints
│   ├── services/
│   │   ├── chat_service.py     # Chat business logic
│   │   └── rag_service.py      # RAG business logic
│   ├── agents/                 # Multi-agent system
│   │   ├── agent_orchestrator.py # Agent management
│   │   ├── master_agent.py     # Master orchestrator
│   │   ├── base_agent.py       # Base agent class
│   │   └── [6 specialized agents]
│   ├── tools/                  # Agent tools
│   │   ├── base_tool.py        # Base tool class
│   │   ├── rag_tools.py        # RAG-specific tools
│   │   ├── erp_tools.py        # ERP operations
│   │   └── tool_registry.py    # Tool registration
│   ├── rag/                    # RAG system
│   │   ├── service.py          # RAG service layer
│   │   ├── vector_store.py     # Vector storage
│   │   └── document_processor.py # Document processing
│   ├── core/                   # Core utilities
│   │   ├── exceptions.py       # Custom exceptions
│   │   ├── metrics.py        # Prometheus metrics
│   │   └── cache_manager.py   # Caching utilities
│   └── models/                 # Data models
│       └── api.py             # Pydantic models
├── tests/                      # Test suite
└── requirements.txt           # Dependencies
```

## Development Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- ChromaDB (for vector storage)
- Redis (for caching and sessions)

### Installation

```bash
# Clone repository
git clone <repository-url>
cd erp-ai-copilot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Initialize database
alembic upgrade head

# Run tests
pytest tests/ -v

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost/erp_ai

# OpenAI
OPENAI_API_KEY=your_openai_key

# Vector Storage
CHROMA_PERSIST_DIRECTORY=./chroma_db

# Redis
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your_secret_key
JWT_SECRET_KEY=your_jwt_secret

# Monitoring
PROMETHEUS_PORT=9090
```

## API Usage Examples

### Basic Chat

```python
import requests

# Send chat message
response = requests.post(
    "http://localhost:8000/v1/chat",
    json={
        "message": "Show me sales data for Q3",
        "agent_type": "query"
    },
    headers={"Authorization": "Bearer YOUR_JWT_TOKEN"}
)
```

### Streaming Chat

```python
import asyncio
import aiohttp

async def stream_chat():
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:8000/v1/chat/stream",
            json={"message": "Generate compliance report"},
            headers={"Authorization": "Bearer YOUR_JWT_TOKEN"}
        ) as response:
            async for line in response.content:
                print(line.decode())
```

### Document Ingestion

```python
# Upload document for RAG
with open("document.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/v1/rag/ingest",
        files={"file": f},
        data={"department": "sales", "access_level": "all"}
    )
```

## Testing Strategy

### Test Structure

```
tests/
├── unit/              # Unit tests for individual components
├── integration/       # Integration tests for service interactions
├── api/              # API endpoint tests
├── agents/           # Agent-specific tests
└── fixtures/         # Test data and mocks
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test suite
pytest tests/api/test_chat.py -v

# Run with coverage
pytest --cov=app tests/

# Run integration tests only
pytest tests/integration/ -v
```

## Performance Considerations

### Optimization Strategies

1. **Database Optimization**
   - Async SQLAlchemy with connection pooling
   - Indexed columns for search queries
   - Batch operations for bulk data

2. **Caching Strategy**
   - Redis for session management
   - Query result caching
   - Agent response caching

3. **Agent Optimization**
   - Load balancing across agent instances
   - Health-based routing
   - Connection pooling for LLM calls

4. **Vector Storage**
   - Optimized embedding dimensions
   - HNSW indexing for fast similarity search
   - Batch processing for document ingestion

### Monitoring

- **Prometheus Metrics**: Response times, error rates, agent usage
- **Structured Logging**: Request tracing, error tracking
- **Health Checks**: Database, agent, and service health
- **Performance Profiling**: Response time analysis

## Deployment

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: erp-ai-copilot
spec:
  replicas: 3
  selector:
    matchLabels:
      app: erp-ai-copilot
  template:
    metadata:
      labels:
        app: erp-ai-copilot
    spec:
      containers:
      - name: app
        image: erp-ai-copilot:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
```

## Contributing Guidelines

### Code Style

- Follow PEP 8 guidelines
- Use type hints throughout
- Comprehensive docstrings
- Async/await patterns for I/O operations

### Pull Request Process

1. Create feature branch from `develop`
2. Write tests for new functionality
3. Ensure all tests pass
4. Update documentation
5. Submit PR with detailed description

### Code Review Checklist

- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Performance impact considered
- [ ] Security implications reviewed
- [ ] Error handling implemented
- [ ] Logging added appropriately

## Troubleshooting

### Common Issues

1. **Database Connection Issues**
   - Check DATABASE_URL format
   - Verify PostgreSQL is running
   - Check connection pool settings

2. **Agent Timeout Errors**
   - Increase timeout values in configuration
   - Check LLM API rate limits
   - Monitor agent health status

3. **Vector Storage Issues**
   - Verify ChromaDB is accessible
   - Check disk space for vector storage
   - Review embedding model configuration

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with debug mode
uvicorn app.main:app --reload --log-level debug
```

### Health Check Endpoints

```bash
# System health
curl http://localhost:8000/health

# Agent health
curl http://localhost:8000/v1/agents/health

# Database health
curl http://localhost:8000/v1/health/db
```

## Support and Resources

- **Documentation**: This file and inline code documentation
- **API Documentation**: Swagger UI at `http://localhost:8000/docs`
- **Test Coverage**: Report available at `htmlcov/index.html`
- **Performance Metrics**: Prometheus metrics at `http://localhost:9090`

For additional support, please refer to the project README or create an issue in the repository.