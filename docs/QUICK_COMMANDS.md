# Quick Service Commands

## From Service Directory

### Run/Build Service
```bash
# Go service
cd erp-crm-service
make run          # Run locally
make build        # Build binary
make deps         # Update dependencies

# Python service  
cd erp-hrm-service
make run          # Run locally
make install      # Install packages

# Node.js service
cd erp-inventory-service
make run          # Run locally
make dev          # Run with auto-reload
make install      # Install packages
```

### Docker Operations
```bash
# From any service directory
make docker-build    # Build container
make docker-run      # Start container
make docker-logs     # View logs
make docker-restart  # Restart container
make health          # Check health
```

## From Infrastructure Directory

### Service Management
```bash
cd erp-suit-infrastructure

# Start services
docker compose up -d crm-service
docker compose up -d hrm-service  
docker compose up -d inventory-service

# Rebuild and start
docker compose up -d --build crm-service

# View logs
docker compose logs -f crm-service

# Restart
docker compose restart crm-service
```

## Package Management

### Go (from service directory)
```bash
# Add package
go get github.com/gorilla/mux
go mod tidy

# Remove package (edit go.mod, then)
go mod tidy
```

### Python (from service directory)
```bash
# Add package
echo 'requests==2.31.0' >> requirements.txt
pip install -r requirements.txt

# Or directly
pip install requests
pip freeze > requirements.txt
```

### Node.js (from service directory)
```bash
# Add package
npm install express-validator

# Add dev dependency
npm install --save-dev nodemon

# Remove package
npm uninstall express-validator
```

## Testing Services

```bash
# Health checks
curl http://localhost:8082/health  # CRM
curl http://localhost:8083/health  # HRM  
curl http://localhost:8084/health  # Inventory

# API tests
curl http://localhost:8082/api/v1/crm
curl -X POST http://localhost:8082/api/v1/crm -d '{"name":"test"}'
```

That's it! Simple commands for all service operations.