#!/bin/bash

# AI Copilot Development Server Startup Script
# This script starts the AI Copilot service for development and testing

set -e

echo "🚀 Starting AI Copilot Development Server..."

# Check if we're in the right directory
if [ ! -f "app/main.py" ]; then
    echo "❌ Error: Please run this script from the erp-ai-copilot directory"
    exit 1
fi

# Check if Python virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies if needed
if [ ! -f ".venv/installed" ]; then
    echo "📥 Installing dependencies..."
    pip install -r requirements.txt
    touch .venv/installed
fi

# Set environment variables for development
export ENVIRONMENT=development
export LOG_LEVEL=debug
export HOST=0.0.0.0
export PORT=8003

# Database configuration (adjust as needed)
export DB_HOST=${DB_HOST:-localhost}
export DB_PORT=${DB_PORT:-5432}
export DB_NAME=${DB_NAME:-erp_ai_copilot}
export DB_USER=${DB_USER:-postgres}
export DB_PASSWORD=${DB_PASSWORD:-postgres}

# MongoDB configuration
export MONGODB_URI=${MONGODB_URI:-mongodb://localhost:27017/}
export MONGODB_DATABASE=${MONGODB_DATABASE:-erp_ai_conversations}

# Redis configuration
export REDIS_HOST=${REDIS_HOST:-localhost}
export REDIS_PORT=${REDIS_PORT:-6379}
export REDIS_PASSWORD=${REDIS_PASSWORD:-}

# JWT configuration
export JWT_SECRET=${JWT_SECRET:-your-super-secret-jwt-key-change-in-production}
export SECURITY_JWT_SECRET=${JWT_SECRET}
export SECURITY_JWT_ALGORITHM=HS256

# AI configuration
export DEFAULT_LLM_PROVIDER=${DEFAULT_LLM_PROVIDER:-gemini}
export DEFAULT_MODEL=${DEFAULT_MODEL:-gemini2.0:flash}
export GEMINI_API_KEY=${GEMINI_API_KEY:-}

# CORS configuration
export CORS_ORIGINS="http://localhost:3000,http://localhost:8000,http://localhost:8003"

echo "🌐 Starting server on http://localhost:8003"
echo "📚 API Documentation: http://localhost:8003/docs"
echo "🔍 Health Check: http://localhost:8003/health"
echo ""
echo "Press Ctrl+C to stop the server"

# Start the server with hot reloading
python -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload --log-level info