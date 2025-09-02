# ERP Suite Infrastructure
## 🛠 Tech Stack

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Architecture](https://img.shields.io/badge/architecture-14--repositories-green.svg)](./05-deployment/multi-repo-microservices-plan.md)
[![Dev-First](https://img.shields.io/badge/dev--first-make%20up-blue.svg)](./03-implementation/dev-first-setup.md)
[![AI-Powered](https://img.shields.io/badge/AI-RAG%20Enabled-purple.svg)](./04-modules/04-ai-module/)

## 🛠️ Technology Stack

### Backend & APIs
![Python](https://img.shields.io/badge/Python_3.11+-3776AB?style=flat&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django_4.2+-092E20?style=flat&logo=django&logoColor=white)
![Django REST](https://img.shields.io/badge/Django_REST_Framework-ff1709?style=flat&logo=django&logoColor=white)
![Go](https://img.shields.io/badge/Go_1.21+-00ADD8?style=flat&logo=go&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Chi Router](https://img.shields.io/badge/Chi_Router-00ADD8?style=flat&logo=go&logoColor=white)

### Frontend & UI
![Next.js](https://img.shields.io/badge/Next.js_14+-000000?style=flat&logo=next.js&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=flat&logo=typescript&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=flat&logo=tailwind-css&logoColor=white)
![Zustand](https://img.shields.io/badge/Zustand-FF6B35?style=flat&logo=react&logoColor=white)
![React Query](https://img.shields.io/badge/React_Query-FF4154?style=flat&logo=react-query&logoColor=white)

### Databases & Storage
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=flat&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat&logo=redis&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-FF6B6B?style=flat&logo=qdrant&logoColor=white)


### DevOps & Infrastructure
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)
![Docker Compose](https://img.shields.io/badge/Docker_Compose-2496ED?style=flat&logo=docker&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=flat&logo=kubernetes&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-623CE4?style=flat&logo=terraform&logoColor=white)
![Helm](https://img.shields.io/badge/Helm-0F1689?style=flat&logo=helm&logoColor=white)
![Air](https://img.shields.io/badge/Air-00ADD8?style=flat&logo=go&logoColor=white)

> **A dev-first, subscription-based SaaS ERP platform with 14 independent microservices and embedded AI capabilities**

![](./preview.png)

Complete infrastructure setup for the ERP Suite development environment with sequential startup, dependency management, reverse proxy support, automatic network detection, and cross-platform compatibility.

## 📦 Repository Structure

### 🏗️ 14-Service Architecture

| Service | Repository | Tech Stack | Purpose |
|---------|------------|------------|---------|
| **Auth Service** | `erp-auth-service` | Go + JWT | Multi-tenant authentication & RBAC |
| **Subscription Service** | `erp-subscription-service` | Django + Stripe | SaaS billing & feature gating |
| **CRM Service** | `erp-crm-service` | Django + DRF | Contact & lead management |
| **HRM Service** | `erp-hrm-service` | Django + DRF | Employee & leave management |
| **Accounting Service** | `erp-accounting-service` | Django + DRF | Financial management & invoicing |
| **Inventory Service** | `erp-inventory-service` | Django + DRF | Product & stock management |
| **Project Service** | `erp-project-service` | Django + DRF | Task & resource management |
| **AI Platform** | `erp-ai-platform` | FastAPI + Ollama | RAG chatbot & ML services |
| **Notification Service** | `erp-notification-service` | Go + WebSocket | Email, SMS, real-time notifications |
| **File Service** | `erp-file-service` | Go + S3 | Document management & PDF generation |
| **API Gateway** | `erp-api-gateway` | Go + Chi | Request routing & rate limiting |
| **Frontend** | `erp-frontend` | Next.js + TypeScript | Subscription-aware UI |
| **Shared Libraries** | `erp-shared-libs` | Python + Go | Common RBAC & utilities |
| **Infrastructure** | `erp-infrastructure` | Terraform + K8s | IaC & deployment configs |

The ERP Suite is composed of multiple microservices, each in its own repository. This infrastructure repository orchestrates all services using Docker Compose.

### 🔗 GitHub Repositories

| Service | Repository | Description | Technology |
|---------|------------|-------------|------------|
| **Infrastructure** | [erp-suite-infrastructure](https://github.com/azad25/erp-suite-infrastructure) | Docker Compose orchestration, NGINX proxy, monitoring | Docker, NGINX |
| **API Gateway** | [erp-api-gateway](https://github.com/azad25/erp-suit-api-gateway) | Main REST API gateway with Django | Python, Django |
| **Auth Service** | [erp-auth-service](https://github.com/azad25/erp-auth-service) | Authentication & authorization service | Go, gRPC |
| **Frontend** | [erp-frontend](https://github.com/azad25/erp-frontend) | Next.js web application | TypeScript, Next.js |
| **Log Service** | [erp-log-service](https://github.com/azad25/erp-log-service) | Centralized logging service | Go, gRPC |
| **GraphQL Gateway** | [erp-graphql-gateway](https://github.com/azad25/erp-graphql-gateway) | GraphQL API gateway | Node.js, Apollo |
| **WebSocket Server** | [erp-websocket-server](https://github.com/azad25/erp-websocket-server) | Real-time communication | Node.js, Socket.IO |

## 🏗️ ERP System Infrastructure Integration Hierarchy

The infrastructure services form the foundation layer that supports the entire multi-tenant ERP system with AI enhancements. Below is the complete integration hierarchy:

```mermaid
graph TB
    subgraph Client["🌐 Client Layer"]
        WEB[Next.js/React Frontend]
        MOBILE[Mobile App]
        API_CLIENTS[External API Clients]
    end
    
    subgraph Gateway["🚪 Gateway & Security Layer"]
        API_GATEWAY[API Gateway - Kong/Nginx]
        AUTH_PROXY[Authentication Proxy]
        RATE_LIMITER[Rate Limiter]
        LOAD_BALANCER[Load Balancer]
    end
    
    subgraph AI["🤖 AI Enhancement Layer"]
        AI_GATEWAY[AI Gateway Service - FastAPI]
        RAG_ENGINE[RAG Engine - Python]
        CONTEXT_MANAGER[Context Manager]
        EMBEDDING_SERVICE[Embedding Service]
    end
    
    subgraph SaaS["💼 SaaS Foundation Layer"]
        SUBSCRIPTION[Subscription Service - Django]
        BILLING[Billing Service - Django]
        FEATURE_GATE[Feature Gating Service]
        USAGE_TRACKER[Usage Tracking Service]
        PAYMENT_PROCESSOR[Payment Processing]
    end
    
    subgraph Security["🔐 Core Security Layer"]
        AUTH_SERVICE[Authentication Service - Django]
        TENANT_SERVICE[Tenant Management - Django]
        RBAC_SERVICE[RBAC Service - Django]
        USER_MGMT[User Management]
    end
    
    subgraph Business["📊 Business Services Layer"]
        HRM[HRM Service - Django]
        CRM[CRM Service - Django]
        FINANCE[Finance Service - Django]
        INVENTORY[Inventory Service - Django]
        PROJECTS[Project Service - Django]
        ANALYTICS[Analytics Service - Django]
    end
    
    subgraph Microservices["⚡ Microservices Layer"]
        INVOICE_GEN[Invoice Generator - Go]
        REPORT_GEN[Report Generator - Go]
        EMAIL_SERVICE[Email Service - Go]
        FILE_PROCESSOR[File Processing - Go]
        SEARCH_SERVICE[Search Service - Go]
        NOTIFICATION[Notification Service - Go]
    end
    
    subgraph Infrastructure["🏗️ Infrastructure Services"]
        POSTGRES[(PostgreSQL 15+)]
        MONGODB[(MongoDB 6+)]
        REDIS[(Redis 7+)]
        QDRANT[(Qdrant Vector DB)]
        KAFKA[Apache Kafka 3.5+]
        ZOOKEEPER[Zookeeper]
        ELASTICSEARCH[(Elasticsearch 8+)]
        KIBANA[Kibana]
        PROMETHEUS[Prometheus]
        GRAFANA[Grafana]
        JAEGER[Jaeger]
        PGADMIN[pgAdmin]
        MONGO_EXPRESS[Mongo Express]
        REDIS_COMMANDER[Redis Commander]
        KAFKA_UI[Kafka UI]
        WEBSOCKET[WebSocket Server]
    end
    
    subgraph External["☁️ External Integrations"]
        GOOGLE_SERVICES[Google Services]
        PAYMENT_GATEWAYS[Payment Gateways]
        LLM_PROVIDERS[LLM Providers]
        CLOUD_STORAGE[Cloud Storage]
    end
    
    subgraph Container["🐳 Container Orchestration"]
        DOCKER[Docker Containers]
        KUBERNETES[Kubernetes Production]
        HELM[Helm Charts]
    end

    %% Client connections
    WEB --> API_GATEWAY
    MOBILE --> API_GATEWAY
    API_CLIENTS --> API_GATEWAY
    
    %% Gateway layer
    API_GATEWAY --> AUTH_PROXY
    AUTH_PROXY --> RATE_LIMITER
    RATE_LIMITER --> LOAD_BALANCER
    
    %% Core authentication flow
    LOAD_BALANCER --> AUTH_SERVICE
    AUTH_SERVICE --> TENANT_SERVICE
    TENANT_SERVICE --> RBAC_SERVICE
    
    %% SaaS foundation integration
    AUTH_SERVICE --> SUBSCRIPTION
    SUBSCRIPTION --> BILLING
    SUBSCRIPTION --> FEATURE_GATE
    BILLING --> PAYMENT_PROCESSOR
    
    %% Business services access control
    FEATURE_GATE --> HRM
    FEATURE_GATE --> CRM
    FEATURE_GATE --> FINANCE
    FEATURE_GATE --> INVENTORY
    FEATURE_GATE --> PROJECTS
    FEATURE_GATE --> ANALYTICS
    
    %% AI layer integration
    LOAD_BALANCER --> AI_GATEWAY
    AI_GATEWAY --> RAG_ENGINE
    RAG_ENGINE --> CONTEXT_MANAGER
    RAG_ENGINE --> EMBEDDING_SERVICE
    
    %% Business services to microservices
    HRM --> INVOICE_GEN
    FINANCE --> REPORT_GEN
    CRM --> EMAIL_SERVICE
    INVENTORY --> FILE_PROCESSOR
    PROJECTS --> SEARCH_SERVICE
    ANALYTICS --> NOTIFICATION
    
    %% Database connections
    AUTH_SERVICE --> POSTGRES
    TENANT_SERVICE --> POSTGRES
    HRM --> POSTGRES
    CRM --> POSTGRES
    FINANCE --> POSTGRES
    INVENTORY --> POSTGRES
    PROJECTS --> POSTGRES
    SUBSCRIPTION --> POSTGRES
    BILLING --> POSTGRES
    
    ANALYTICS --> MONGODB
    EMAIL_SERVICE --> MONGODB
    REPORT_GEN --> MONGODB
    
    AUTH_SERVICE --> REDIS
    TENANT_SERVICE --> REDIS
    WEBSOCKET --> REDIS
    
    AI_GATEWAY --> QDRANT
    RAG_ENGINE --> QDRANT
    EMBEDDING_SERVICE --> QDRANT
    
    %% Search integration
    SEARCH_SERVICE --> ELASTICSEARCH
    KIBANA --> ELASTICSEARCH
    
    %% Event streaming
    HRM --> KAFKA
    CRM --> KAFKA
    FINANCE --> KAFKA
    INVENTORY --> KAFKA
    PROJECTS --> KAFKA
    SUBSCRIPTION --> KAFKA
    
    KAFKA --> ZOOKEEPER
    KAFKA --> INVOICE_GEN
    KAFKA --> REPORT_GEN
    KAFKA --> EMAIL_SERVICE
    KAFKA --> NOTIFICATION
    
    %% Real-time communication
    WEBSOCKET --> REDIS
    NOTIFICATION --> WEBSOCKET
    
    %% External integrations
    EMAIL_SERVICE --> GOOGLE_SERVICES
    FILE_PROCESSOR --> GOOGLE_SERVICES
    CRM --> GOOGLE_SERVICES
    PAYMENT_PROCESSOR --> PAYMENT_GATEWAYS
    AI_GATEWAY --> LLM_PROVIDERS
    FILE_PROCESSOR --> CLOUD_STORAGE
    
    %% Monitoring
    PROMETHEUS --> GRAFANA
    JAEGER --> GRAFANA
    
    %% Container orchestration
    DOCKER --> KUBERNETES
    KUBERNETES --> HELM
    
    %% Development tools connections
    PGADMIN --> POSTGRES
    MONGO_EXPRESS --> MONGODB
    REDIS_COMMANDER --> REDIS
    KAFKA_UI --> KAFKA
```

## 🚀 Complete Setup Guide

### Prerequisites

Before starting, ensure you have the following installed:

- **Docker** (v20.10+) and **Docker Compose** (v2.0+)
- **Git** (v2.30+)
- **Make** (for running commands)
- **curl** (for health checks)

### Step 1: Clone All Repositories

Create a workspace directory and clone all repositories:

```bash
# Create workspace directory
mkdir erp-suite && cd erp-suite

# Clone infrastructure repository (this one)
git clone https://github.com/azad25/erp-suite-infrastructure.git

# Clone all service repositories
git clone https://github.com/azad25/erp-api-gateway.git
git clone https://github.com/azad25/erp-auth-service.git
git clone https://github.com/azad25/erp-frontend.git
git clone https://github.com/azad25/erp-log-viewer-service.git
git clone https://github.com/azad25/erp-graphql-gateway.git
git clone https://github.com/azad25/erp-websocket-server.git
```

### Step 2: Directory Structure

After cloning, your directory structure should look like this:

```
erp-suite/
├── erp-suite-infrastructure/     # This repository
│   ├── docker-compose.yml
│   ├── Makefile
│   ├── nginx/
│   └── README.md
├── erp-api-gateway/              # Django REST API
│   ├── manage.py
│   ├── requirements.txt
│   └── Dockerfile.dev
├── erp-auth-service/             # Go authentication service
│   ├── main.go
│   ├── go.mod
│   └── Dockerfile.dev
├── erp-frontend/                 # Next.js frontend
│   ├── package.json
│   ├── next.config.ts
│   └── Dockerfile.dev
├── erp-log-viewer-service/       # Go logging service
│   ├── main.go
│   ├── go.mod
│   └── Dockerfile.dev
├── erp-graphql-gateway/          # Node.js GraphQL gateway
│   ├── package.json
│   ├── server.js
│   └── Dockerfile.dev
└── erp-websocket-server/         # Node.js WebSocket server
    ├── package.json
    ├── server.js
    └── Dockerfile.dev
```

### Step 3: Quick Start

Navigate to the infrastructure directory and start the complete system:

```bash
cd erp-suite-infrastructure

# Complete setup with automatic network detection
make start-dev
```

This single command will:
1. ✅ Prepare environment files
2. ✅ Check for port conflicts
3. ✅ Detect your network IP automatically
4. ✅ Configure NGINX reverse proxy
5. ✅ Start all infrastructure services
6. ✅ Start all application services
7. ✅ Perform health checks

### Step 4: Verify Installation

After startup, verify all services are running:

```bash
# Check service status
make status

# View all service logs
make logs

# Check specific service
make logs APP=api-gateway
```
## Service Endpoints

### API Layer
| Service | Port | URL | Credentials |
|---------|------|-----|-------------|
| GraphQL Gateway | 4000 | http://localhost:4000/graphql | - |
| GraphQL Playground | 4000 | http://localhost:4000/playground | - |
| gRPC Registry (Consul) | 8500 | http://localhost:8500 | - |
| WebSocket Server | 3001 | http://localhost:3001 | - |

### Infrastructure Services
| Service | Port | URL/Connection | Credentials |
|---------|------|----------------|-------------|
| PostgreSQL | 5432 | localhost:5432 | postgres/postgres |
| MongoDB | 27017 | localhost:27017 | root/password |
| Redis | 6379 | localhost:6379 | password: redispassword |
| Qdrant (HTTP) | 6333 | http://localhost:6333 | - |
| Qdrant (gRPC) | 6334 | grpc://localhost:6334 | - |
| Kafka | 9092 | localhost:9092 | - |
| Elasticsearch | 9200 | http://localhost:9200 | No auth required |

### Development Tools
| Service | Port | URL | Credentials |
|---------|------|-----|-------------|
| pgAdmin | 8081 | http://localhost:8081 | admin@erp.com/admin |
| Mongo Express | 8082 | http://localhost:8082 | admin/pass |
| Redis Commander | 8083 | http://localhost:8083 | - |
| Kafka UI | 8084 | http://localhost:8084 | - |
| Kibana | 5601 | http://localhost:5601 | No auth required |

## 🌍 Custom Network IP Setup
```bash
# Force specific network IP
make start HOST_IP=192.168.1.100

# Start with custom environment
make start ENVIRONMENT=production

# Start with specific profile
make start PROFILE=infrastructure

# Start in development mode
make start-dev

# Access services directly
curl http://localhost:8000/api/v1/health/
curl http://localhost:4000/graphql

# Start in development mode
make start-dev

# Access services directly
curl http://localhost:8000/api/v1/health/
curl http://localhost:4000/graphql

# Start in development mode
make start-dev

# Access services directly
curl http://localhost:8000/api/v1/health/
curl http://localhost:4000/graphql

# Start in development mode
make start-dev

# Access services directly
curl http://localhost:8000/api/v1/health/
curl http://localhost:4000/graphql

# Start in development mode
make start-dev

# Access services directly
curl http://localhost:8000/api/v1/health/
curl http://localhost:4000/graphql

# Custom network configuration
export HOST_IP=192.168.1.100
export NETWORK_SUBNET=172.20.0.0/16

# Then start
make start

```
### What it does:

- ✅ Prepares environment files
- ✅ Checks for port conflicts
- ✅ Detects your network IP automatically
- ✅ Configures NGINX for both localhost and network access
- ✅ Starts all services with reverse proxy
- ✅ Prints access information

### Access URLs:

- Localhost: http://localhost/api/v1/
- Network: http://YOUR_NETWORK_IP/api/v1/

### Credentials:

- Username: admin
- Password: admin123

### URLs:

- Frontend(next.js): http://localhost
- pgAdmin (PostgreSQL): http://localhost/admin/pgadmin/
- Mongo Express (MongoDB): http://localhost/admin/mongo/
- Redis Commander (Redis): http://localhost/admin/redis/
- Kafka UI (Kafka): http://localhost/admin/kafka/
- Kibana (Elasticsearch): http://localhost/admin/kibana/
- Consul (Service Registry): http://localhost/admin/consul/

### ✅ Direct Access (no authentication):
- pgAdmin: http://localhost:8081
- Mongo Express: http://localhost:8082
- Redis Commander: http://localhost:8083
- Kafka UI: http://localhost:8084
- Kibana: http://localhost:5601
- Consul: http://localhost:8500

## 🔧 Alternative Setup Methods

### Method 1: Infrastructure Only

Start just the infrastructure services (databases, message brokers, etc.):

```bash
cd erp-suite-infrastructure
make up PROFILE=infrastructure
```

### Method 2: Development Mode

Start with sequential loading for better resource management:

```bash
cd erp-suite-infrastructure
make start-dev
```

### Method 3: Individual Service Development

Start infrastructure and specific services:

```bash
# Start infrastructure
make up PROFILE=infrastructure

# Start specific service
make up APP=api-gateway

# Or start multiple services
make up APP=api-gateway,auth-service,frontend
```

## 🌐 Access Your Services

After successful startup, access your services through the NGINX reverse proxy:

### 🚀 Primary Access (via NGINX Proxy - Recommended)
- **Frontend**: http://localhost/
- **GraphQL API**: http://localhost/graphql
- **GraphQL Playground**: http://localhost/playground
- **REST API**: http://localhost/api/v1/
- **Auth Service**: http://localhost/auth/
- **Log Service**: http://localhost/logs/
- **WebSocket**: ws://localhost/socket.io/

### 🔧 Direct Service Access (Development Only)
- **Frontend**: http://localhost:3000
- **GraphQL Gateway**: http://localhost:4000/graphql
- **API Gateway**: http://localhost:8000/api/v1/
- **Auth Service**: http://localhost:8080
- **Log Service**: http://localhost:8001

### 🛠️ Admin Tools (Protected)
- **pgAdmin**: http://localhost/admin/pgadmin/ (admin/admin)
- **Mongo Express**: http://localhost/admin/mongo/ (admin/pass)
- **Redis Commander**: http://localhost/admin/redis/
- **Kafka UI**: http://localhost/admin/kafka/
- **Kibana**: http://localhost/admin/kibana/
- **Consul**: http://localhost/admin/consul/

### 🌐 Complete Inter-Service Communication Map
### Architecture Overview

```mermaid
graph TB
    subgraph "API Layer"
        GQL[GraphQL Gateway<br/>Port 4000]
        CONSUL[Service Registry<br/>Consul - Port 8500]
        WS[WebSocket Server<br/>Port 3001]
    end
    
    subgraph "Core Infrastructure"
        PG[(PostgreSQL<br/>Port 5432)]
        MONGO[(MongoDB<br/>Port 27017)]
        REDIS[(Redis<br/>Port 6379)]
        KAFKA[Kafka<br/>Port 9092]
        ES[(Elasticsearch<br/>Port 9200)]
        QDRANT[(Qdrant<br/>Port 6333)]
    end
    
    subgraph "Development Tools"
        PGADMIN[pgAdmin<br/>Port 8081]
        MONGOEXP[Mongo Express<br/>Port 8082]
        REDISCMD[Redis Commander<br/>Port 8083]
        KAFKAUI[Kafka UI<br/>Port 8084]
        KIBANA[Kibana<br/>Port 5601]
    end
    
    GQL --> PG
    GQL --> REDIS
    WS --> REDIS
    KIBANA --> ES
    PGADMIN --> PG
    MONGOEXP --> MONGO
    REDISCMD --> REDIS
    KAFKAUI --> KAFKA
```


## 🔄 Development Workflow

### For New Developers

1. **Clone repositories** (see Step 1 above)
2. **Start infrastructure**: `make start`
3. **Verify services**: `make status`
4. **Start developing**: Choose your service and start coding!

### For Service Development

```bash
# Work on a specific service
cd erp-suite-infrastructure

# Start infrastructure only
make up PROFILE=infrastructure

# Start your service in development mode
cd ../erp-api-gateway  # or any other service
docker compose -f ../erp-suite-infrastructure/docker-compose.yml up api-gateway

# Or use the infrastructure Makefile
cd erp-suite-infrastructure
make up APP=api-gateway
make logs APP=api-gateway
```

### For Frontend Development

```bash
# Start backend services
make up PROFILE=infrastructure
make up APP=api-gateway,auth-service,graphql-gateway

# Start frontend in development mode
cd ../erp-frontend
npm install
npm run dev

# Or use Docker
cd erp-suite-infrastructure
make up APP=erp-frontend
```

## 📋 Repository-Specific Setup

### API Gateway (Django)
```bash
cd erp-api-gateway

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### Auth Service (Go)
```bash
cd erp-auth-service

# Install dependencies
go mod download

# Build the service
go build -o main .

# Run the service
./main
```

### Frontend (Next.js)
```bash
cd erp-frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

### GraphQL Gateway (Node.js)
```bash
cd erp-graphql-gateway

# Install dependencies
npm install

# Start development server
npm run dev

# Start production server
npm start
```

## 🔧 Environment Configuration

### Default Environment Files

The infrastructure automatically creates environment files with sensible defaults:

- `.env` - Main infrastructure configuration
- `.env.frontend` - Frontend-specific variables
- `.env.auth` - Auth service configuration
- `.env.api` - API gateway configuration

### Customizing Configuration

```bash
# Copy example files
cp .env.example .env
cp .env.frontend.example .env.frontend

# Edit configuration
nano .env

# Restart services to apply changes
make restart
```

### Key Configuration Options

```bash
# Network Configuration
HOST_IP=0.0.0.0                    # Auto-detected network IP
COMPOSE_PROJECT_NAME=erp-suite     # Docker project name

# Database Configuration
POSTGRES_DB=erp_system
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Service Ports
FRONTEND_PORT=3000
GRAPHQL_GATEWAY_PORT=4000
API_GATEWAY_PORT=8000
AUTH_SERVICE_HTTP_PORT=8080

# Security
JWT_SECRET=your-super-secret-jwt-key
DJANGO_SECRET_KEY=your-django-secret-key
```

## 🚀 Quick Start

### Option 1: Complete Setup (Recommended)
```bash
# Complete startup with all preparations
make start

# This will:
# 1. Prepare environment files
# 2. Check for port conflicts
# 3. Automatically detect network IP
# 4. Configure network exposure
# 5. Setup reverse proxy with detected IP
# 6. Start all services
```

### Option 2: Development Setup
```bash
# Sequential startup for development
make start-dev

# Access services on localhost
# Frontend: http://localhost:3000
# GraphQL: http://localhost:4000/graphql
# API Gateway: http://localhost:8000/api/v1/
```

### Option 3: Reverse Proxy Setup (Network Access)
```bash
# Start with reverse proxy (exposes all services through NGINX)
make start-with-proxy

# Access all services through single entry point
# Frontend: http://YOUR_DETECTED_IP/
# GraphQL: http://YOUR_DETECTED_IP/graphql
# API Gateway: http://YOUR_DETECTED_IP/api/v1/
```

### Option 4: HTTPS Setup (Production-like)
```bash
# Generate SSL certificates
make generate-ssl

# Enable HTTPS
make enable-https

# Start with proxy
make start-with-proxy

# Access via HTTPS
# https://YOUR_DETECTED_IP/
```

## 🌐 NGINX Reverse Proxy Architecture

The infrastructure uses NGINX as a reverse proxy running on localhost, providing a single entry point for all services:

### How It Works
1. **Single Entry Point**: All traffic goes through NGINX on localhost:80
2. **Service Routing**: NGINX routes requests to appropriate backend services
3. **Load Balancing**: Built-in upstream load balancing for scalability
4. **Security**: Rate limiting, security headers, and admin tool protection

### Architecture Flow
```
Client Request → NGINX Proxy (localhost:80) → Backend Services
```

### Example Usage
```bash
$ make start
🚀 Starting ERP Suite Infrastructure...
✅ NGINX Proxy started on localhost:80
✅ All services accessible through proxy

� Acceess Points:
  Frontend:           http://localhost/
  GraphQL API:        http://localhost/graphql
  GraphQL Playground: http://localhost/playground
  Django API:         http://localhost/api/v1/
  Auth Service:       http://localhost/auth/
  Log Service:        http://localhost/logs/
  WebSocket:          ws://localhost/socket.io/
```

## 📋 Command Reference

### 🚀 Core Commands

| Command | Description |
|---------|-------------|
| `make start` | Complete startup (env prep, port check, network config, proxy setup, start services) |
| `make start-dev` | Development startup with sequential service loading |
| `make start-with-proxy` | Start with reverse proxy (recommended for network access) |
| `make stop` | Stop all services and free ports |
| `make restart` | Complete restart (stop + start) |
| `make reload SERVICE=name` | Reload specific service (e.g., `make reload SERVICE=postgres`) |
| `make pause` | Pause all services |
| `make resume` | Resume all paused services |

### 🔧 Setup Commands

| Command | Description |
|---------|-------------|
| `make setup-proxy` | Setup reverse proxy configuration |
| `make configure-network` | Configure network exposure |
| `make prepare-environment` | Prepare environment files and directories |
| `make check-ports` | Check for port conflicts |
| `make detect-network-ip` | Detect and display network IP |

### 🔨 Build Commands

| Command | Description |
|---------|-------------|
| `make build-service SERVICE=name` | Build specific service |
| `make rebuild-service SERVICE=name` | Rebuild and restart service |
| `make build-all` | Build all services |

### 🌐 Network Commands

| Command | Description |
|---------|-------------|
| `make expose-dev` | Expose services to network |
| `make generate-ssl` | Generate SSL certificates |
| `make enable-https` | Enable HTTPS (requires SSL) |

### 📊 Status Commands

| Command | Description |
|---------|-------------|
| `make status` | Quick status check |
| `make services` | Show running services |
| `make logs` | Show logs from all services |
| `make logs APP=name` | Show logs from specific app |

### 🛠️ Utility Commands

| Command | Description |
|---------|-------------|
| `make force-stop` | Force stop with aggressive cleanup |
| `make full-stop` | Complete shutdown with cleanup |
| `make install-deps SERVICE=name` | Install dependencies for service |

### 🍎 macOS Optimization

| Command | Description |
|---------|-------------|
| `make macos-config` | Switch to macOS-optimized configuration |
| `make macos-performance` | Check Docker performance |
| `make macos-clean` | Clean up Docker for macOS |

## 🌐 Reverse Proxy Architecture

The infrastructure includes an **NGINX reverse proxy** that acts as a single entry point for all client traffic on localhost:

```
┌─────────────────┐
│   Client        │
│   (Browser)     │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│   NGINX Proxy   │
│   localhost:80  │
│   localhost:443 │
└─────────┬───────┘
          │
    ┌─────┼─────┬─────┬─────┐
    ▼     ▼     ▼     ▼     ▼
┌─────┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐
│Front│ │API│ │GQL│ │Auth│ │Log│
│:3000│ │:8k│ │:4k│ │:8080│ │:8001│
└─────┘ └───┘ └───┘ └───┘ └───┘
    │     │     │     │     │
    └─────┼─────┼─────┼─────┘
          ▼     ▼     ▼
┌─────────────────────────────┐
│     Internal Services       │
│    (Docker Network)         │
└─────────────────────────────┘
```

### 🌐 NGINX Proxy Endpoints

| Service | Proxy URL | Direct URL | Description |
|---------|-----------|------------|-------------|
| **Frontend** | `http://localhost/` | `http://localhost:3000` | Next.js web application |
| **GraphQL API** | `http://localhost/graphql` | `http://localhost:4000/graphql` | GraphQL endpoint |
| **GraphQL Playground** | `http://localhost/playground` | `http://localhost:4000/playground` | GraphQL IDE |
| **REST API** | `http://localhost/api/v1/` | `http://localhost:8000/api/v1/` | Django REST API |
| **Auth Service** | `http://localhost/auth/` | `http://localhost:8080/api/v1/` | Authentication API |
| **Log Service** | `http://localhost/logs/` | `http://localhost:8001/api/v1/` | Logging API |
| **WebSocket** | `ws://localhost/socket.io/` | `ws://localhost:3001/socket.io/` | Real-time communication |

### 🛠️ Admin Tools (Protected with Basic Auth)

| Tool | Proxy URL | Direct URL | Credentials |
|------|-----------|------------|-------------|
| **pgAdmin** | `http://localhost/admin/pgadmin/` | `http://localhost:8081` | admin/admin123 |
| **Mongo Express** | `http://localhost/admin/mongo/` | `http://localhost:8082` | admin/admin123 |
| **Redis Commander** | `http://localhost/admin/redis/` | `http://localhost:8083` | admin/admin123 |
| **Kafka UI** | `http://localhost/admin/kafka/` | `http://localhost:8084` | admin/admin123 |
| **Kibana** | `http://localhost/admin/kibana/` | `http://localhost:5601` | admin/admin123 |
| **Consul** | `http://localhost/admin/consul/` | `http://localhost:8500` | admin/admin123 |

### Benefits of Reverse Proxy Setup

1. **Single Entry Point**: All traffic goes through one IP/domain
2. **Security**: Internal services remain on localhost
3. **SSL Termination**: HTTPS handled at proxy level
4. **Load Balancing**: Can easily add multiple instances
5. **Rate Limiting**: Built-in protection against abuse
6. **Caching**: Static assets cached at proxy level
7. **Monitoring**: Centralized logging and metrics
8. **Auto-Configuration**: Automatically detects and configures network IP

## 🔧 Service Management

### Service Reload

```bash
# Basic syntax
make reload SERVICE=service-name

# Examples
make reload SERVICE=postgres
make reload SERVICE=redis
make reload SERVICE=elasticsearch
make reload SERVICE=nginx-proxy
```

### Smart Dependency Management

The `reload` command automatically restarts dependent services:

| Service | Dependents |
|---------|------------|
| postgres | GraphQL Gateway, pgAdmin |
| redis | GraphQL Gateway, WebSocket Server, Redis Commander |
| mongodb | Mongo Express |
| elasticsearch | Kibana |
| kafka | Kafka UI |
| nginx-proxy | All services (restarts proxy) |

### Available Service Names

| Service Name | Description |
|--------------|-------------|
| `postgres` | PostgreSQL database |
| `redis` | Redis cache |
| `mongodb` | MongoDB database |
| `kafka` | Kafka message broker |
| `elasticsearch` | Elasticsearch search |
| `qdrant` | Qdrant vector database |
| `graphql-gateway` | GraphQL API gateway |
| `grpc-registry` | gRPC service registry |
| `websocket-server` | WebSocket server |
| `kibana` | Kibana UI |
| `pgadmin` | pgAdmin UI |
| `mongo-express` | Mongo Express UI |
| `redis-commander` | Redis Commander UI |
| `kafka-ui` | Kafka UI |
| `nginx-proxy` | NGINX reverse proxy |

## 🏗️ Architecture Components

### Infrastructure Services
- **PostgreSQL** - Primary relational database
- **MongoDB** - Analytics, logs, AI conversations
- **Redis** - Cache, sessions, queues
- **Qdrant** - Vector database for AI/RAG
- **Kafka** - Message broker
- **Elasticsearch** - Search engine
- **Kibana** - Elasticsearch visualization

### API Layer
- **GraphQL Gateway** - Main API gateway (port 4000)
- **Django API Gateway** - Secondary gateway with auth proxy (port 8000)
- **WebSocket Server** - Real-time communication (port 3001)
- **gRPC Registry (Consul)** - Service discovery (port 8500)

### Application Services
- **Auth Service** - Authentication and authorization (port 8080)
- **Log Service** - Centralized logging (port 8001)
- **Frontend** - Next.js application (port 3000)

### Development Tools
- **pgAdmin** - PostgreSQL administration (port 8081)
- **Mongo Express** - MongoDB administration (port 8082)
- **Redis Commander** - Redis administration (port 8083)
- **Kafka UI** - Kafka administration (port 8084)
- **Kibana** - Elasticsearch visualization (port 5601)

## 🔄 Sequential Startup System

The `start-dev` command uses a 10-phase sequential startup to reduce resource load and ensure proper dependency management:

### Startup Phases
1. **Phase 1**: Core Databases (PostgreSQL, Redis)
2. **Phase 2**: Document & Vector Stores (MongoDB, Qdrant)
3. **Phase 3**: Message Broker (Kafka)
4. **Phase 4**: Search Engine (Elasticsearch)
5. **Phase 5**: API Layer (GraphQL Gateway, gRPC Registry)
6. **Phase 6**: WebSocket Server
7. **Phase 7**: Logging (Kibana)
8. **Phase 8**: Development Tools
9. **Phase 9**: Core Application Services (Auth, API Gateway, Log Service)
10. **Phase 10**: Frontend

### Benefits
- Reduced resource contention during startup
- Proper dependency ordering ensures stability
- Better error isolation and debugging
- Health checks between phases

## 🔐 Security Features

### Network Security
- **Rate Limiting**: API endpoints protected against abuse
- **Basic Auth**: Admin tools protected with credentials
- **Security Headers**: XSS protection, content type validation
- **Internal Services**: All services run on localhost by default

### SSL/HTTPS Support
```bash
# Generate self-signed certificates
make generate-ssl

# Enable HTTPS
make enable-https

# Access via HTTPS
https://YOUR_DETECTED_IP/
```

## 📊 Monitoring & Health Checks

### Health Check Endpoints
- **Proxy Health**: `http://YOUR_DETECTED_IP/health`
- **Service Status**: `make status`
- **Service Logs**: `make logs`
- **Individual Service**: `make logs APP=service-name`

### Service Health Monitoring
```bash
# Quick status check
make status

# Detailed service status
make services

# Monitor specific service
make logs APP=postgres
```

## 🛠️ Development Workflow

### For New Module Development
```bash
# 1. Start infrastructure
make start-dev

# 2. Create your service
./create-service.sh 8085 finance go

# 3. Start your service
docker compose up -d finance-service

# 4. Check all services are running
make services

# 5. Use development tools:
# - pgAdmin: http://localhost:8081
# - GraphQL Playground: http://localhost:4000/playground
```

### Service Connection Examples

#### Database Connections
```bash
# PostgreSQL
psql -h localhost -p 5432 -U postgres -d erp_system

# MongoDB
mongosh mongodb://root:password@localhost:27017/erp_analytics

# Redis
redis-cli -h localhost -p 6379 -a redispassword
```

#### API Testing
```bash
# GraphQL Health Check
curl http://localhost:4000/health

# Elasticsearch Health
curl http://localhost:9200/_cluster/health

# WebSocket Health Check
curl http://localhost:3001/health

# Consul Services
curl http://localhost:8500/v1/catalog/services
```

## 🔧 Configuration

### Environment Variables

Key environment variables for customization:

```bash
# Network Configuration
HOST_IP=0.0.0.0                    # Network exposure IP
NETWORK_SUBNET=172.20.0.0/16       # Docker network subnet

# Service Ports
POSTGRES_PORT=5432
REDIS_PORT=6379
MONGODB_PORT=27017
KAFKA_PORT=9092
ELASTICSEARCH_PORT=9200
GRAPHQL_GATEWAY_PORT=4000
WEBSOCKET_PORT=3001
FRONTEND_PORT=3000
AUTH_SERVICE_HTTP_PORT=8080
API_GATEWAY_PORT=8000
LOG_SERVICE_HTTP_PORT=8001

# Development Tools Ports
PGADMIN_PORT=8081
MONGO_EXPRESS_PORT=8082
REDIS_COMMANDER_PORT=8083
KAFKA_UI_PORT=8084
KIBANA_PORT=5601
```

### Custom Configuration

```bash
# Custom network IP
make start HOST_IP=192.168.1.100

# Custom environment
make start ENVIRONMENT=staging

# Custom build type
make start BUILD_TYPE=production
```

## 🚨 Troubleshooting

### Common Issues and Solutions

#### Port Conflicts
The system automatically checks for port conflicts before starting:
```bash
# Manual port check
make check-ports

# Kill processes using specific port
sudo lsof -ti:5432 | xargs kill -9
```

#### Service Startup Issues
```bash
# Check service logs
make logs APP=postgres

# Reload specific service
make reload SERVICE=postgres

# Rebuild service
make rebuild-service SERVICE=postgres
```

#### Network Access Issues
```bash
# Check proxy status
curl http://YOUR_DETECTED_IP/health

# Check firewall
sudo ufw status

# Restart proxy
make reload SERVICE=nginx-proxy
```

#### Docker Issues
```bash
# Clean Docker system
make macos-clean

# Force stop all containers
make force-stop

# Check Docker resources
make macos-performance
```

### Performance Optimization

#### macOS Optimization
```bash
# Switch to macOS-optimized config
make macos-config

# Check performance
make macos-performance

# Clean up Docker
make macos-clean
```

#### Resource Allocation
- **PostgreSQL**: 512MB RAM limit, 256MB reserved
- **Elasticsearch**: 1GB RAM limit, 512MB reserved
- **Kafka**: 256MB heap memory
- **Other services**: Default Docker limits

## 📈 Scaling Considerations

### Horizontal Scaling
The infrastructure supports horizontal scaling through:
- **Load Balancing**: NGINX proxy can distribute traffic
- **Service Replication**: Multiple instances of services
- **Database Clustering**: PostgreSQL read replicas, MongoDB replica sets
- **Cache Distribution**: Redis cluster support

### Vertical Scaling
- **Memory Allocation**: Adjust service memory limits in docker-compose.yml
- **CPU Limits**: Configure CPU limits for resource-intensive services
- **Storage**: Increase volume sizes for databases

## 🔄 Backup and Recovery

### Database Backups
```bash
# PostgreSQL backup
docker compose exec postgres pg_dump -U postgres erp_system > backup.sql

# MongoDB backup
docker compose exec mongodb mongodump --out /backup

# Redis backup
docker compose exec redis redis-cli SAVE
```

### Volume Management
```bash
# List volumes
docker volume ls

# Backup volumes
docker run --rm -v erp-suite_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_data.tar.gz -C /data .

# Restore volumes
docker run --rm -v erp-suite_postgres_data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres_data.tar.gz -C /data
```

## 🌐 Complete Inter-Service Communication Map

The ERP Suite uses a sophisticated service mesh architecture where all services communicate using Docker service names for optimal performance, scalability, and maintainability.

```
┌─────────────────────────────────────────────────────────────┐
│                    ERP Suite Service Mesh                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Frontend  │────│    NGINX    │────│  External   │
│ erp-frontend│    │nginx-proxy  │    │   Clients   │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │
       │                   ▼
       │            ┌─────────────┐
       │            │   GraphQL   │
       └────────────│   Gateway   │
                    │graphql-gateway
                    └─────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ API Gateway │    │ Auth Service│    │ WebSocket   │
│api-gateway  │    │auth-service │    │websocket-   │
│             │    │             │    │server       │
└─────────────┘    └─────────────┘    └─────────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ PostgreSQL  │    │    Redis    │    │    Kafka    │
│  postgres   │    │    redis    │    │    kafka    │
└─────────────┘    └─────────────┘    └─────────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Elasticsearch│    │   MongoDB   │    │   Qdrant    │
│elasticsearch│    │   mongodb   │    │   qdrant    │
└─────────────┘    └─────────────┘    └─────────────┘
```

### 📊 Service Communication Matrix

| **From Service** | **To Service** | **Connection Method** | **Status** |
|------------------|----------------|-----------------------|------------|
| **Frontend** | API Gateway | `http://api-gateway:8000` | ✅ Service Name |
| **Frontend** | GraphQL Gateway | `http://graphql-gateway:4000` | ✅ Service Name |
| **API Gateway** | PostgreSQL | `postgres:5432` | ✅ Service Name |
| **API Gateway** | Redis | `redis:6379` | ✅ Service Name |
| **API Gateway** | Elasticsearch | `elasticsearch:9200` | ✅ Service Name |
| **API Gateway** | MongoDB | `mongodb:27017` | ✅ Service Name |
| **API Gateway** | Auth Service | `http://auth-service:8080` | ✅ Service Name |
| **API Gateway** | WebSocket | `http://websocket-server:3001` | ✅ Service Name |
| **GraphQL Gateway** | PostgreSQL | `postgres:5432` | ✅ Service Name |
| **GraphQL Gateway** | Redis | `redis:6379` | ✅ Service Name |
| **GraphQL Gateway** | Auth Service | `auth-service:50051` (gRPC) | ✅ Service Name |
| **Auth Service** | PostgreSQL | `postgres:5432` | ✅ Service Name |
| **Auth Service** | Redis | `redis:6379` | ✅ Service Name |
| **Auth Service** | Kafka | `kafka:29092` | ✅ Service Name |
| **WebSocket** | Redis | `redis:6379` | ✅ Service Name |
| **WebSocket** | GraphQL Gateway | `http://graphql-gateway:4000` | ✅ Service Name |
| **Kibana** | Elasticsearch | `http://elasticsearch:9200` | ✅ Service Name |
| **Admin Tools** | Databases | Service names | ✅ Service Name |

### 🔧 Inter-Service Communication Benefits

1. **Perfect Service Discovery**: All services use Docker's built-in DNS resolution
2. **Network Isolation**: Services communicate within the `erp-network` 
3. **Load Balancing Ready**: Service names support multiple instances
4. **Environment Agnostic**: Works in development, staging, and production
5. **Security**: Internal communication doesn't expose ports externally
6. **Scalability**: Easy to add service replicas behind the same service name

### 🚀 Production-Ready Configuration

Your infrastructure follows Docker and microservices best practices:

- ✅ **Service Names for Inter-Service Communication**
- ✅ **Proper Network Segmentation** 
- ✅ **Health Checks Using Internal Addresses**
- ✅ **Environment Variable Configuration**
- ✅ **CORS Configuration with Service Names**
- ✅ **Database Connection Pooling Support**
- ✅ **gRPC Service Discovery**

### 📋 Quick Verification Commands

Test that services can communicate using service names:

```bash
# Test from API Gateway to Auth Service
docker exec erp-suite-api-gateway curl -f http://auth-service:8080/health

# Test from GraphQL Gateway to PostgreSQL
docker exec erp-suite-graphql-gateway nc -z postgres 5432

# Test from Auth Service to Redis
docker exec erp-suite-auth-service redis-cli -h redis -p 6379 ping

# Test from API Gateway to Elasticsearch
docker exec erp-suite-api-gateway curl -f http://elasticsearch:9200/_cluster/health
```

## 📚 Additional Resources

### Documentation
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [NGINX Configuration](https://nginx.org/en/docs/)
- [GraphQL Documentation](https://graphql.org/learn/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

### Community Support
- GitHub Issues: Report bugs and feature requests
- Documentation: Comprehensive setup and usage guides
- Examples: Sample configurations and use cases

---

**ERP Suite Infrastructure** - Complete development environment with reverse proxy, automatic network detection, monitoring, and cross-platform support.