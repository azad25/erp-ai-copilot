# UNIBASE ERP AI Copilot Service

A sophisticated, enterprise-grade AI copilot service with robust WebSocket support, designed to integrate seamlessly with existing ERP infrastructure, providing intelligent assistance across all business modules.

## 🚀 Features

### Core Capabilities
- **Multi-Agent Architecture**: Specialized agents for different business functions
- **Real-time Chat**: Robust WebSocket-based conversational interface with production-ready proxy
- **RAG System**: Advanced retrieval-augmented generation with Qdrant integration
- **Multi-Model Support**: OpenAI, Anthropic, and local Ollama models
- **Enterprise Security**: RBAC integration with JWT and gRPC auth service fallback
- **Token Caching**: Redis-based token validation with 30-minute TTL
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

## 📊 Implementation Status

| Feature Category | Status | Completion |
|------------------|--------|------------|
| **Core Agents** | ✅ Complete | 100% |
| **RAG System** | ✅ Complete | 100% |
| **REST API** | ✅ Complete | 100% |
| **WebSocket API** | ✅ Complete | 100% |
| **WebSocket Proxy** | ✅ Complete | 100% |
| **Token Caching** | ✅ Complete | 100% |
| **Database Layer** | ✅ Complete | 100% |
| **Security Framework** | ✅ Complete | 100% |
| **Tool System** | ✅ Complete | 100% |
| **Monitoring** | ✅ Complete | 100% |
| **Event System** | ⚠️ Partial | 75% |
| **Multi-tenant Support** | ⚠️ Partial | 80% |
| **Redis Caching** | ❌ Not Started | 0% |
| **Elasticsearch** | ❌ Not Started | 0% |

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
- **FastAPI**: High-performance web framework with WebSocket support
- **SQLAlchemy**: Database ORM with async support
- **Motor**: Async MongoDB driver
- **Redis**: Token caching and rate limiting
- **Qdrant**: Vector database for RAG system
- **gRPC**: High-performance service communication
- **WebSockets**: Real-time bidirectional communication

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
docker-compose -f ../erp-suite-infrastructure/docker-compose.yml up -d postgres redis mongodb qdrant kafka

# Verify Redis is running (for token caching)
redis-cli ping
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

## 🌟 Recent Updates

### WebSocket & Authentication Improvements
- **Fixed WebSocket Proxy**: Completely rewrote WebSocket proxy implementation for reliable message forwarding
- **Token Caching**: Implemented Redis-based token validation with 30-minute TTL
- **Fallback Authentication**: Added JWT fallback when gRPC auth service is unavailable
- **Connection Management**: Improved WebSocket connection handling and error recovery
- **Performance**: Reduced authentication load with token caching

### Monitoring & Observability
- Added Prometheus metrics for WebSocket connections
- Enhanced logging for better debugging
- Connection health monitoring

## 📖 Documentation

### Developer Documentation
- [Developer Guide](DEVELOPER_DOCUMENTATION.md) - Complete architecture and development guide
- [API Documentation](http://localhost:8080/docs) - Interactive API documentation (when running)
- [Architecture Overview](ai-agent-architechture.md) - Detailed system architecture

### Testing
```bash
# Run all tests
pytest

# Run specific test suite
pytest tests/test_rag_tools.py

# Run with coverage
pytest --cov=app tests/
```

### Code Quality
```bash
# Format code
black app/

# Lint code
flake8 app/

# Type checking
mypy app/
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
```

## 🧪 Testing

### Test Structure
```
tests/
├── unit/
│   ├── test_agents/
│   ├── test_tools/
│   └── test_services/
├── integration/
│   ├── test_api/
│   └── test_database/
└── fixtures/
```

### Running Tests
```bash
# All tests
pytest

# With coverage
pytest --cov=app tests/

# Specific test file
pytest tests/test_rag_tools.py -v

# Integration tests only
pytest tests/integration/ -v
```

## 🐳 Docker Support

### Development
```bash
# Build development image
docker build -t ai-copilot:dev .

# Run with docker-compose
docker-compose -f docker-compose.dev.yml up
```

### Production
```bash
# Build production image
docker build -t ai-copilot:latest .

# Run production stack
docker-compose -f docker-compose.yml up -d
```

## 🚀 Deployment

### Environment Setup
1. **Development**: Local development with hot reload
2. **Staging**: Feature branch testing environment
3. **Production**: Scalable production deployment

### Scaling Considerations
- **Horizontal scaling**: Multiple service instances
- **Database scaling**: Read replicas and sharding
- **Caching**: Redis cluster for high availability
- **Message queue**: Kafka cluster for event processing

## 📊 Monitoring

### Metrics
- **Application metrics**: Prometheus + Grafana
- **Business metrics**: Custom dashboards
- **Performance metrics**: Response times, throughput
- **Error tracking**: Sentry integration

### Health Checks
```bash
# Service health
curl http://localhost:8080/health

# Detailed status
curl http://localhost:8080/health/detailed
```

## 🤝 Contributing

### Development Workflow
1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open pull request

### Code Standards
- Follow PEP 8 style guidelines
- Write comprehensive tests
- Update documentation
- Use conventional commits

### Branch Strategy
- `main`: Production-ready code
- `develop`: Integration branch
- `feature/*`: New features
- `hotfix/*`: Critical fixes

## 🔐 Security

### Authentication & Security
- **Token Validation**: JWT-based authentication with gRPC fallback
- **Token Caching**: Redis-based caching with 30-minute TTL
- **WebSocket Security**: Robust connection management with proper authentication flow
- **Rate Limiting**: Built-in protection against abuse
- **Role-based Access Control**: Fine-grained permissions system (RBAC)

### Data Protection
- Encryption at rest and in transit
- PII data masking
- Audit logging for all actions
- GDPR compliance features

## 📞 Support

### Getting Help
- **Documentation**: Check the [Developer Guide](DEVELOPER_DOCUMENTATION.md)
- **Issues**: Create GitHub issues for bugs or feature requests
- **Discussions**: Use GitHub discussions for questions
- **Slack**: Join our community channel

### Troubleshooting

#### Common Issues
1. **Database connection issues**: Check environment variables
2. **AI model errors**: Verify API keys and quotas
3. **Memory issues**: Increase Docker memory limits
4. **Port conflicts**: Check for conflicting services

#### Debug Mode
```bash
# Enable debug logging
export DEBUG=true

# Verbose API logs
export LOG_LEVEL=DEBUG
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- AI models from [OpenAI](https://openai.com/) and [Anthropic](https://anthropic.com/)
- Vector search powered by [Qdrant](https://qdrant.tech/)
- Database management with [SQLAlchemy](https://www.sqlalchemy.org/)

---

**Built with ❤️ by the UNIBASE ERP Team**

