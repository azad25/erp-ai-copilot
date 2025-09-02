# Current ERP Infrastructure Request Flow

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    Frontend     │    │   NGINX Proxy   │    │   API Gateway   │
│   (Next.js)     │◄──►│   Port: 80      │◄──►│   (Go/Gin)      │
│   Port: 3000    │    │                 │    │   Port: 8000    │
└─────────────────┘    └─────────────────┘    └─────────┬───────┘
                                                        │
                        ┌───────────────────────────────┼───────────────────────────────┐
                        │                               │                               │
                        ▼                               ▼                               ▼
              ┌─────────────────┐            ┌─────────────────┐            ┌─────────────────┐
              │ GraphQL Gateway │            │ WebSocket Server│            │  Auth Service   │
              │   (Node.js)     │            │   (Node.js)     │            │     (Go)        │
              │   Port: 4000    │            │   Port: 3001    │            │ HTTP: 8080      │
              └─────────┬───────┘            └─────────┬───────┘            │ gRPC: 50051     │
                        │                              │                    └─────────────────┘
                        │                              │
                        ▼                              ▼
              ┌─────────────────┐            ┌─────────────────┐
              │  Auth Service   │            │     Redis       │
              │    (gRPC)       │            │   Port: 6379    │
              │   Port: 50051   │            │   (Pub/Sub)     │
              └─────────────────┘            └─────────────────┘
```

## 🌊 Request Flow Details

### 1. REST API Requests (Direct gRPC)
```
POST /api/v1/auth/login

Frontend (3000) 
    ↓ HTTP Request
NGINX (80)
    ↓ Proxy to API Gateway
API Gateway (8000)
    ↓ gRPC Call
Auth Service (50051)
    ↓ Response
API Gateway
    ↓ JSON Response
NGINX
    ↓ HTTP Response
Frontend
```

**Flow Steps:**
1. **Frontend** sends HTTP POST to `/api/v1/auth/login`
2. **NGINX** receives request and proxies to API Gateway
3. **API Gateway** validates request and extracts credentials
4. **API Gateway** makes gRPC call to Auth Service
5. **Auth Service** processes authentication and returns gRPC response
6. **API Gateway** converts gRPC response to JSON
7. **NGINX** forwards response back to Frontend

### 2. GraphQL Requests (Proxied)
```
POST /graphql

Frontend (3000)
    ↓ GraphQL Query
NGINX (80)
    ↓ Proxy to API Gateway
API Gateway (8000)
    ↓ HTTP Proxy
GraphQL Gateway (4000)
    ↓ gRPC Call
Auth Service (50051)
    ↓ Response
GraphQL Gateway
    ↓ GraphQL Response
API Gateway
    ↓ Proxy Response
NGINX
    ↓ HTTP Response
Frontend
```

**Flow Steps:**
1. **Frontend** sends GraphQL query to `/graphql`
2. **NGINX** proxies to API Gateway
3. **API Gateway** proxies GraphQL request to GraphQL Gateway
4. **GraphQL Gateway** parses query and makes gRPC calls to services
5. **Auth Service** processes gRPC request and returns data
6. **GraphQL Gateway** formats response according to GraphQL schema
7. **API Gateway** forwards GraphQL response
8. **NGINX** returns response to Frontend

### 3. WebSocket Connections (Proxied)
```
WS /ws

Frontend (3000)
    ↓ WebSocket Upgrade
NGINX (80)
    ↓ WebSocket Proxy
API Gateway (8000)
    ↓ WebSocket Proxy
WebSocket Server (3001)
    ↓ Redis Pub/Sub
Redis (6379)
```

**Flow Steps:**
1. **Frontend** initiates WebSocket connection to `/ws`
2. **NGINX** upgrades connection and proxies to API Gateway
3. **API Gateway** proxies WebSocket connection to WebSocket Server
4. **WebSocket Server** establishes bidirectional connection
5. **WebSocket Server** subscribes to Redis channels for real-time events
6. **Services** publish events to Redis, which are forwarded to Frontend

## 🔧 Service Integration Points

### API Gateway Configuration
```yaml
# erp-api-gateway/config.yaml
graphql:
  gateway_host: "graphql-gateway"
  gateway_port: 4000
  endpoint: "/graphql"
  timeout: "30s"

websocket:
  server_host: "websocket-server"
  server_port: 3001
  endpoint: "/socket.io"
  timeout: "30s"

grpc:
  auth_service:
    host: "auth-service"
    port: 50051
```

### NGINX Configuration
```nginx
# nginx/nginx.conf
location / {
    proxy_pass http://frontend_backend;
}

location /graphql {
    proxy_pass http://api_gateway_backend;
}

location /ws {
    proxy_pass http://api_gateway_backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}

location ~ ^/(auth|api)/ {
    proxy_pass http://api_gateway_backend;
}
```

## 📊 Port Mapping

| Service | HTTP Port | gRPC Port | WebSocket Port | Purpose |
|---------|-----------|-----------|----------------|---------|
| NGINX | 80 | - | - | Reverse Proxy |
| Frontend | 3000 | - | - | Next.js App |
| API Gateway | 8000 | - | - | Central Entry Point |
| GraphQL Gateway | 4000 | - | - | GraphQL Schema Union |
| WebSocket Server | 3001 | - | 3001 | Real-time Communication |
| Auth Service | 8080 | 50051 | - | Authentication |
| Redis | - | - | - | Cache & Pub/Sub (6379) |
| PostgreSQL | - | - | - | Database (5432) |

## 🔄 Data Flow Examples

### Login Request
```
1. Frontend → POST /api/v1/auth/login
2. NGINX → API Gateway:8000/api/v1/auth/login
3. API Gateway → Auth Service:50051 (gRPC)
4. Auth Service → PostgreSQL (user validation)
5. Auth Service → Redis (session storage)
6. Response: Auth Service → API Gateway → NGINX → Frontend
```

### GraphQL Query
```
1. Frontend → POST /graphql { me { id, name } }
2. NGINX → API Gateway:8000/graphql
3. API Gateway → GraphQL Gateway:4000/graphql
4. GraphQL Gateway → Auth Service:50051 (gRPC GetUser)
5. Auth Service → PostgreSQL (user data)
6. Response: Auth Service → GraphQL Gateway → API Gateway → NGINX → Frontend
```

### Real-time Event
```
1. Auth Service → Redis PUBLISH "user_login" event
2. WebSocket Server ← Redis SUBSCRIBE receives event
3. WebSocket Server → Frontend (via established WS connection)
4. Frontend updates UI in real-time
```

## 🛡️ Security Flow

### Authentication
1. **Frontend** includes JWT token in Authorization header
2. **API Gateway** validates JWT token
3. **API Gateway** extracts user context (user_id, organization_id)
4. **API Gateway** forwards user context to downstream services
5. **Services** use user context for authorization

### CORS & Security Headers
1. **NGINX** applies security headers
2. **API Gateway** handles CORS for API endpoints
3. **GraphQL Gateway** inherits authentication from API Gateway
4. **WebSocket Server** validates JWT tokens for connections

## 🔍 Monitoring & Logging

### Request Tracing
- Each request gets a unique trace ID
- Logs flow through: NGINX → API Gateway → Services
- Centralized logging via Elasticsearch
- Metrics exposed via Prometheus endpoints

### Health Checks
```
GET /health → API Gateway health
GET /ready → API Gateway readiness (checks downstream services)
```

This architecture provides:
- ✅ **Centralized Entry Point** (API Gateway)
- ✅ **Service Isolation** (Each service has specific responsibility)
- ✅ **Scalability** (Services can be scaled independently)
- ✅ **Flexibility** (Multiple API patterns: REST, GraphQL, WebSocket)
- ✅ **Fallback Options** (Local handlers if infrastructure services fail)