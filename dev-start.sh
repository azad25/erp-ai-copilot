#!/bin/bash

# AI Copilot Development Server with Hot Reloading
# This script starts the AI Copilot service with automatic code reloading

set -e

echo "🚀 Starting AI Copilot Development Server with Hot Reloading..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Check if the ERP network exists
if ! docker network ls | grep -q erp-network; then
    echo "📡 Creating ERP network..."
    docker network create erp-network
fi

# Function to handle cleanup
cleanup() {
    echo "🛑 Stopping AI Copilot development server..."
    docker-compose -f docker-compose.dev.yml down
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start the development environment
echo "🔧 Building and starting AI Copilot with hot reloading..."
docker-compose -f docker-compose.dev.yml up --build

# Keep the script running
wait
