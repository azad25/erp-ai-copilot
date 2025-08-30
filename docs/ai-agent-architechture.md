# UNIBASE ERP AI Copilot Service

A sophisticated, enterprise-grade AI copilot service designed to integrate seamlessly with existing ERP infrastructure, providing intelligent assistance across all business modules.

## 🚀 Features

### Core Capabilities
- **Multi-Agent Architecture**: Specialized agents for different business functions
- **Real-time Chat**: WebSocket-based conversational interface
- **RAG System**: Advanced retrieval-augmented generation with Qdrant integration
- **Multi-Model Support**: OpenAI, Anthropic, and local Ollama models
- **Enterprise Security**: RBAC integration with existing auth systems
- **Scalable Design**: Microservice architecture with async support

### Agent Types
- **Query Agent**: Information retrieval and reporting
- **Action Agent**: CRUD operations and workflow execution
- **Analytics Agent**: Data analysis and insights generation
- **Scheduler Agent**: Automated task management
- **Compliance Agent**: Regulatory and policy enforcement
- **Help Agent**: User guidance and training 

### Integration Points
- **REST API**: Full CRUD operations for all entities
- **WebSocket**: Real-time chat and notifications
- **gRPC**: High-performance inter-service communication
- **Event Streaming**: Kafka integration for business events
- **Background Tasks**: Celery-based task processing

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        API Layer (FastAPI)                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │   Chat API      │  │  Admin API      │  │ WebSocket API   │    │
│  │ /api/chat/*     │  │ /api/admin/*    │  │ /ws/chat        │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
├─────────────────────────────────────────────────────────────────────┤
│                      Agent Orchestration                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │  Master Agent   │  │ Routing Engine  │  │Context Manager  │    │
│  │ (Coordinator)   │  │(Intent->Agent)  │  │(Memory System)  │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
├─────────────────────────────────────────────────────────────────────┤
│                     Specialized Agents                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │  Query Agent    │  │ Action Agent    │  │Analytics Agent  │    │
│  │ (Read/Report)   │  │(CRUD/Execute)   │  │(Insights/Calc)  │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │Scheduler Agent  │  │Compliance Agent │  │  Help Agent     │    │
│  │(Tasks/Cron)     │  │(Audit/Rules)    │  │ (Guidance)      │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
├─────────────────────────────────────────────────────────────────────┤
│                         Tool System                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │   Tool Registry │  │ ERP Connectors  │  │External APIs    │    │
│  │(Action Catalog) │  │(Service Calls)  │  │(LLM/3rd Party)  │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
├─────────────────────────────────────────────────────────────────────┤
│                        Security Layer                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │  RBAC Engine    │  │  Audit Logger   │  │  Data Filter    │    │
│  │(Permissions)    │  │ (All Actions)   │  │  (Row Level)    │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
├─────────────────────────────────────────────────────────────────────┤
│                      Integration Layer                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │ Auth gRPC Client│  │HTTP ERP Clients │  │Event Publisher  │    │
│  │(Your Auth Svc)  │  │(Business Svcs)  │  │ (Kafka Events)  │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

## 🛠️ Technology Stack

### Backend
- **Python 3.11+**: Modern Python with async support
- **FastAPI**: High-performance web framework
- **SQLAlchemy**: Database ORM with async support
- **Motor**: Async MongoDB driver
- **Redis**: Caching and session management
- **Qdrant**: Vector database for RAG system

### AI/ML
- **OpenAI GPT-4**: Cloud-based language models
- **Anthropic Claude**: Alternative AI provider
- **Ollama**: Local model inference
- **LangChain**: AI application framework
- **Sentence Transformers**: Embedding generation

### Infrastructure
- **Docker**: Containerization
- **Celery**: Background task processing
- **Kafka**: Event streaming
- **Prometheus**: Metrics and monitoring
- **Structlog**: Structured logging

## 📋 Prerequisites

- Python 3.11+
- Docker and Docker Compose
- PostgreSQL 15+
- Redis 7+
- MongoDB 6+
- Qdrant 1.7+
- Kafka 7.4+

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone <repository-url>
cd erp-ai-copilot
```

### 2. Set Environment Variables
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Start Infrastructure
```bash
# Start the required infrastructure services
docker-compose -f ../erp-suit-infrastructure/docker-compose.yml up -d postgres redis mongodb qdrant kafka
```

### 4. Initialize Databases
```bash
# Initialize PostgreSQL
psql -h localhost -U postgres -f scripts/init-ai-copilot-db.sql

# Initialize MongoDB
mongo --host localhost:27017 --username root --password password scripts/init-mongodb.js
```

### 5. Install Dependencies
```bash
pip install -r requirements.txt
```

### 6. Run the Service
```bash
# Development mode
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# Production mode
python -m app.main
```

### 7. Start Background Workers
```bash
# Start Celery worker
celery -A app.core.celery_app worker --loglevel=info

# Start Celery beat (scheduler)
celery -A app.core.celery_app beat --loglevel=info
```

## 🔧 Configuration

### Environment Variables

#### Database Configuration
```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=erp_ai_copilot
DB_USER=postgres
DB_PASSWORD=postgres
```

#### Redis Configuration
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=redispassword
REDIS_DB=2
```

#### AI Model Configuration
```bash
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
OLLAMA_BASE_URL=http://localhost:11434
```

#### Security Configuration
```bash
JWT_SECRET=your-super-secret-jwt-key
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
```

### Service Configuration
```bash
SERVICE_NAME=ai-copilot
SERVICE_VERSION=1.0.0
ENVIRONMENT=development
LOG_LEVEL=info
```

## 📚 API Documentation

### Chat Endpoints

#### Send Chat Message
```http
POST /api/v1/chat/
Content-Type: application/json
Authorization: Bearer <jwt-token>

{
  "message": "What's our current inventory status?",
  "conversation_id": "uuid-optional",
  "agent_type": "query",
  "model": "gpt-4",
  "temperature": 0.7,
  "max_tokens": 4000
}
```

#### Streaming Chat
```http
POST /api/v1/chat/stream
Content-Type: application/json
Authorization: Bearer <jwt-token>

{
  "message": "Generate a financial report",
  "agent_type": "analytics"
}
```

#### WebSocket Chat
```javascript
const ws = new WebSocket('ws://localhost:8080/ws/chat?token=<jwt-token>');

ws.onmessage = function(event) {
  const data = JSON.parse(event.data);
  if (data.type === 'chat_response') {
    console.log('AI Response:', data.content);
  }
};

// Send message
ws.send(JSON.stringify({
  type: 'chat_message',
  message: 'Hello, AI!',
  conversation_id: 'uuid-optional'
}));
```

### Conversation Management

#### Create Conversation
```http
POST /api/v1/chat/conversations
Content-Type: application/json
Authorization: Bearer <jwt-token>

{
  "title": "Financial Analysis Session",
  "context": {"department": "finance", "fiscal_year": "2024"},
  "metadata": {"priority": "high"}
}
```

#### List Conversations
```http
GET /api/v1/chat/conversations?page=1&size=20&status=active
Authorization: Bearer <jwt-token>
```

#### Get Conversation Messages
```http
GET /api/v1/chat/conversations/{conversation_id}/messages?page=1&size=50
Authorization: Bearer <jwt-token>
```

### RAG System

#### Search Knowledge Base
```http
POST /api/v1/rag/search
Content-Type: application/json
Authorization: Bearer <jwt-token>

{
  "query": "employee benefits policy",
  "document_type": "policy",
  "max_results": 10,
  "similarity_threshold": 0.75
}
```

#### Ingest Document
```http
POST /api/v1/rag/documents
Content-Type: application/json
Authorization: Bearer <jwt-token>

{
  "title": "Employee Handbook 2024",
  "content": "Full document content...",
  "document_type": "handbook",
  "access_level": "all",
  "version": "1.0"
}
```

## 🧪 Testing

### Run Tests
```bash
# Run all tests
pytest

# Run specific test categories
pytest -m unit
pytest -m integration
pytest -m api

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_chat_api.py

# Run tests in parallel
pytest -n auto
```

### Test Categories
- **Unit Tests**: Individual component testing
- **Integration Tests**: Service interaction testing
- **API Tests**: Endpoint functionality testing
- **Database Tests**: Data persistence testing
- **WebSocket Tests**: Real-time communication testing

## 📊 Monitoring

### Health Checks
```http
GET /health          # Overall service health
GET /ready          # Readiness probe
GET /metrics        # Prometheus metrics
GET /info           # Service information
```

### Metrics
- Request count and latency
- Database connection status
- AI model usage statistics
- WebSocket connection count
- Background task performance

### Logging
Structured logging with correlation IDs:
```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "info",
  "message": "Chat response generated",
  "conversation_id": "uuid",
  "user_id": "uuid",
  "response_time": 1.5,
  "tokens_used": 25
}
```

## 🔒 Security

### Authentication
- JWT token validation via gRPC auth service
- Organization-based data isolation
- Role-based access control (RBAC)

### Data Protection
- Row-level security
- Audit logging for all actions
- Encrypted communication
- Input validation and sanitization

### Rate Limiting
- Per-user request limits
- Burst protection
- Configurable thresholds

## 🚀 Deployment

### Docker Deployment
```bash
# Build image
docker build -t erp-ai-copilot .

# Run container
docker run -d \
  --name ai-copilot \
  --network erp-network \
  -p 8080:8080 \
  -p 8081:8081 \
  -e DB_HOST=postgres \
  -e REDIS_HOST=redis \
  erp-ai-copilot
```

### Docker Compose
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f ai-copilot

# Scale workers
docker-compose up -d --scale ai-copilot-worker=3
```

### Kubernetes
```bash
# Apply manifests
kubectl apply -f k8s/

# Scale deployment
kubectl scale deployment ai-copilot --replicas=3

# View logs
kubectl logs -f deployment/ai-copilot
```

## 🔄 Development

### Code Quality
```bash
# Format code
black app/
isort app/

# Lint code
flake8 app/
mypy app/

# Run pre-commit hooks
pre-commit run --all-files
```

### Database Migrations
```bash
# Generate migration
alembic revision --autogenerate -m "Add new field"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Adding New Agents
1. Create agent class in `app/agents/`
2. Implement required methods
3. Add to agent registry
4. Create unit tests
5. Update API documentation

## 🤝 Contributing

### Development Workflow
1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Ensure all tests pass
5. Submit pull request

### Code Standards
- Follow PEP 8 style guide
- Write comprehensive docstrings
- Include type hints
- Maintain test coverage >80%
- Update documentation

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Documentation
- [API Reference](docs/api.md)
- [Architecture Guide](docs/architecture.md)
- [Deployment Guide](docs/deployment.md)
- [Troubleshooting](docs/troubleshooting.md)

### Community
- [Issues](https://github.com/your-org/erp-ai-copilot/issues)
- [Discussions](https://github.com/your-org/erp-ai-copilot/discussions)
- [Wiki](https://github.com/your-org/erp-ai-copilot/wiki)

### Contact
- **Email**: support@your-org.com
- **Slack**: #erp-ai-copilot
- **Discord**: [ERP AI Copilot Community](https://discord.gg/your-invite)

## 🗺️ Roadmap

### Phase 1: Core Infrastructure ✅
- [x] Basic FastAPI service
- [x] Database models and connections
- [x] Authentication integration
- [x] Basic agent framework

### Phase 2: Query Agent 🚧
- [x] Read-only operations
- [x] Natural language processing
- [x] Response formatting
- [ ] Advanced reporting

### Phase 3: Action Agent 📋
- [ ] CRUD operations
- [ ] Workflow execution
- [ ] Transaction handling
- [ ] Audit logging

### Phase 4: Advanced Features 📋
- [ ] Analytics and insights
- [ ] Scheduled automation
- [ ] Advanced RAG capabilities
- [ ] Multi-language support

### Phase 5: Production Hardening 📋
- [ ] Performance optimization
- [ ] Security hardening
- [ ] Comprehensive monitoring
- [ ] Disaster recovery

---

**Built with ❤️ by the UNIBASE ERP Team**
