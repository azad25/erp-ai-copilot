# UNIBASE ERP AI Agent Architecture

## Overview
The UNIBASE ERP AI Copilot system is built on a microservices architecture with specialized AI agents designed to handle different aspects of ERP operations.

## System Architecture

### Core Components

#### 1. AI Agent Layer
- **Query Agent**: Information retrieval and reporting
- **Action Agent**: CRUD operations and workflow execution
- **Chat Agent**: Natural language processing and user interaction
- **Analytics Agent**: Data analysis and insights

#### 2. Service Layer
- **API Gateway**: Central routing and load balancing
- **Authentication Service**: JWT-based auth and RBAC
- **Business Services**: Modular microservices for each domain

#### 3. Data Layer
- **PostgreSQL**: Primary transactional data
- **MongoDB**: Document storage and unstructured data
- **Redis**: Caching and session management
- **Qdrant**: Vector database for RAG system

## AI Agent Capabilities

### Query Agent
- **Database Queries**: Cross-module data retrieval
- **Report Generation**: Custom reports and dashboards
- **Documentation Access**: Project docs and architecture
- **Knowledge Base**: Technical specifications and guides

### Action Agent
- **CRUD Operations**: Create, read, update, delete
- **Workflow Automation**: Business process automation
- **Command Execution**: System and infrastructure management
- **Service Management**: Docker, Kubernetes, database operations

## Infrastructure Management

### Available Commands

#### System Commands
- `system status`: Check overall system health
- `service restart [service]`: Restart specific service
- `logs [service]`: View service logs
- `health [service]`: Check service health

#### Docker Commands
- `docker ps`: List running containers
- `docker restart [container]`: Restart container
- `docker logs [container]`: View container logs
- `docker stats`: Container resource usage

#### Kubernetes Commands
- `kubectl get pods`: List pods
- `kubectl describe [resource]`: Resource details
- `kubectl logs [pod]`: Pod logs
- `kubectl rollout restart [deployment]`: Restart deployment

#### Database Commands
- `db status`: Database connection status
- `db backup`: Create database backup
- `db restore [backup]`: Restore from backup
- `db migrate`: Run database migrations

## API Architecture

### RESTful Endpoints
- `/api/v1/agents/query`: Query agent endpoints
- `/api/v1/agents/action`: Action agent endpoints
- `/api/v1/agents/chat`: Chat agent endpoints
- `/api/v1/agents/analytics`: Analytics agent endpoints

### GraphQL Schema
```graphql
type Query {
  inventoryStatus: InventoryStatus
  salesReport(filters: ReportFilters): SalesReport
  employeeData(filters: EmployeeFilters): EmployeeData
  documentationSearch(query: String): [DocumentationResult]
}

type Mutation {
  executeAction(action: ActionInput): ActionResult
  executeCommand(command: CommandInput): CommandResult
}
```

## Security Model

### Authentication
- JWT tokens with configurable expiration
- Refresh token rotation
- Multi-factor authentication support

### Authorization
- Role-Based Access Control (RBAC)
- Fine-grained permissions per module
- API key management for service-to-service communication

### Data Protection
- Encryption at rest (AES-256)
- TLS 1.3 for data in transit
- Database connection encryption
- Sensitive data masking in logs

## Deployment Strategy

### Environment Setup
1. **Development**: Local Docker Compose
2. **Staging**: Kubernetes cluster with staging namespace
3. **Production**: Multi-region Kubernetes with load balancing

### CI/CD Pipeline
- **GitHub Actions**: Automated testing and deployment
- **Docker Registry**: Container image management
- **Helm Charts**: Kubernetes deployment configuration
- **Blue-Green Deployment**: Zero-downtime deployments

### Monitoring and Observability
- **Prometheus**: Metrics collection
- **Grafana**: Dashboards and visualization
- **ELK Stack**: Centralized logging
- **Jaeger**: Distributed tracing
- **Health Checks**: Service health monitoring

## Performance Optimization

### Caching Strategy
- **Redis**: Application-level caching
- **Database Query Caching**: Query result caching
- **CDN**: Static asset caching
- **API Response Caching**: Response caching with TTL

### Database Optimization
- **Connection Pooling**: Database connection management
- **Query Optimization**: Indexed queries and query plans
- **Read Replicas**: Load distribution for read queries
- **Partitioning**: Data partitioning for large tables

### Resource Management
- **Horizontal Scaling**: Auto-scaling based on load
- **Resource Limits**: CPU and memory limits per service
- **Load Balancing**: Intelligent traffic distribution
- **Circuit Breakers**: Fail-fast mechanisms

## Troubleshooting Guide

### Common Issues
1. **Service Unavailable**: Check service health and dependencies
2. **Database Connection Issues**: Verify connection strings and credentials
3. **Memory Issues**: Check resource limits and memory usage
4. **Slow Queries**: Analyze query performance and indexes

### Debug Commands
```bash
# Check service status
kubectl get pods -n erp-system

# View logs
docker logs erp-ai-copilot

# Check database connection
psql -h localhost -U postgres -d erp_db -c "SELECT 1"

# Monitor resources
docker stats
```

## Development Setup

### Prerequisites
- Docker and Docker Compose
- Python 3.9+
- Node.js 16+
- PostgreSQL 13+
- Redis 6+

### Local Development
```bash
# Clone repository
git clone https://github.com/unibase/erp-ai-copilot.git
cd erp-ai-copilot

# Start development environment
docker-compose up -d

# Run tests
pytest tests/

# Start development server
python -m app.main
```

## API Documentation

### OpenAPI Specification
Available at: `http://localhost:8000/docs`

### Authentication
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'
```

### Query Agent Example
```bash
curl -X POST http://localhost:8000/api/v1/agents/query \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me current inventory levels"}'
```

### Action Agent Example
```bash
curl -X POST http://localhost:8000/api/v1/agents/action \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Restart the database service"}'
```