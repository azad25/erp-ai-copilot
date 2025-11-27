#!/bin/bash

# Script to run LLM provider settings migration

set -e

echo "🚀 Running LLM Provider Settings Migration..."

# Load environment variables
if [ -f ../.env ]; then
    export $(cat ../.env | grep -v '^#' | xargs)
fi

# Database connection details
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-erp_ai_copilot}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"
CONTAINER_NAME="${POSTGRES_CONTAINER:-postgres}"

# Check if running in Docker environment
if command -v docker &> /dev/null; then
    echo "📊 Running migration via Docker..."
    
    # Check if postgres container exists
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "   Using container: ${CONTAINER_NAME}"
        
        # Copy migration file to container
        docker cp migrations/create_llm_provider_settings.sql ${CONTAINER_NAME}:/tmp/
        
        # Run migration
        docker exec -e PGPASSWORD=$DB_PASSWORD ${CONTAINER_NAME} \
            psql -h localhost -p $DB_PORT -U $DB_USER -d $DB_NAME \
            -f /tmp/create_llm_provider_settings.sql
        
        # Clean up
        docker exec ${CONTAINER_NAME} rm /tmp/create_llm_provider_settings.sql
        
        echo "✅ Migration completed successfully!"
    else
        echo "❌ PostgreSQL container '${CONTAINER_NAME}' not found"
        echo "   Available containers:"
        docker ps --format '{{.Names}}'
        exit 1
    fi
elif command -v psql &> /dev/null; then
    echo "📊 Running migration via psql..."
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME \
        -f migrations/create_llm_provider_settings.sql
    echo "✅ Migration completed successfully!"
else
    echo "❌ Neither Docker nor psql command found"
    echo ""
    echo "Please run the migration manually:"
    echo "1. Copy the SQL file: migrations/create_llm_provider_settings.sql"
    echo "2. Execute it in your PostgreSQL database"
    echo ""
    echo "Or install PostgreSQL client:"
    echo "  Ubuntu/Debian: sudo apt-get install postgresql-client"
    echo "  macOS: brew install postgresql"
    exit 1
fi

echo ""
echo "📝 Default providers have been added:"
echo "  - Gemini (enabled, default)"
echo "  - HuggingFace (disabled)"
echo "  - OpenAI (disabled)"
echo "  - Anthropic (disabled)"
echo "  - Ollama (disabled)"
echo ""
echo "🔧 Next steps:"
echo "  1. Update API keys in the AI Settings page"
echo "  2. Enable desired providers"
echo "  3. Test provider connections"
echo ""
