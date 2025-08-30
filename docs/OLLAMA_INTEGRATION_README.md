# Ollama Integration with unibase-erp Model

This document explains how to integrate your local Ollama installation with the ERP AI Copilot service using the custom `unibase-erp` model.

## Overview

The ERP AI Copilot service has been enhanced to support local Ollama models, specifically your custom `unibase-erp` model. This integration allows you to:

- Use your local LLM for AI-powered ERP assistance
- Reduce API costs by running models locally
- Customize the AI behavior for your specific ERP needs
- Maintain data privacy by keeping AI processing local

## Prerequisites

1. **Ollama Installed**: Ensure Ollama is installed and running on your system
2. **unibase-erp Model**: Your custom model should be created and available
3. **Python Dependencies**: Install required Python packages

## Quick Start

### 1. Verify Ollama Installation

```bash
# Check if Ollama is running
ollama list

# Verify unibase-erp model is available
ollama run unibase-erp "Hello"
```

### 2. Test the Integration

```bash
# Navigate to the AI Copilot service directory
cd erp-ai-copilot-service

# Run the Ollama integration test
python test_ollama_integration.py
```

### 3. Start the Local Service

```bash
# Start the local AI Copilot service
python run_local.py
```

The service will start on `http://localhost:8003`

## Configuration

### Environment Variables

The service automatically detects and uses your local Ollama installation. Key configuration options:

```bash
# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_LLM_PROVIDER=ollama
DEFAULT_MODEL=unibase-erp

# Service Configuration
LOG_LEVEL=debug
ENVIRONMENT=development
```

### Model Selection

The service automatically selects the best available model:

1. **unibase-erp** (if available) - Your custom ERP model
2. **llama3.1** (fallback) - Latest Llama model
3. **llama3** (fallback) - Llama 3 model
4. **llama2** (fallback) - Llama 2 model

## API Endpoints

### Health Check
```bash
curl http://localhost:8003/health
```

### List Available Models
```bash
curl http://localhost:8003/models
```

### Chat with AI
```bash
curl -X POST http://localhost:8003/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the current inventory status?",
    "model": "unibase-erp"
  }'
```

### Test Ollama Integration
```bash
curl -X POST http://localhost:8003/test
```

## Integration with API Gateway

The AI Copilot service is designed to integrate with the ERP API Gateway. The integration provides:

- **REST API**: HTTP endpoints for AI operations
- **WebSocket**: Real-time chat and streaming
- **gRPC**: High-performance service communication
- **Authentication**: JWT-based security

### API Gateway Configuration

Update your API Gateway configuration to include:

```yaml
# AI Copilot Service Configuration
ai_copilot:
  host: localhost
  port: 8003
  grpc_port: 50051
  websocket_port: 8081
```

## Testing

### 1. Test Ollama Integration

```bash
# Run the comprehensive test suite
python test_ollama_integration.py
```

This will test:
- Ollama connection
- Model availability
- Response generation
- Streaming responses

### 2. Test API Gateway Integration

```bash
# Navigate to API Gateway directory
cd ../erp-api-gateway

# Run the integration test
./test_ai_copilot_integration.sh
```

### 3. Manual Testing

```bash
# Test health endpoint
curl http://localhost:8003/health

# Test chat endpoint
curl -X POST http://localhost:8003/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "model": "unibase-erp"}'

# Test models endpoint
curl http://localhost:8003/models
```

## Troubleshooting

### Common Issues

#### 1. Ollama Connection Failed
```bash
# Check if Ollama is running
ps aux | grep ollama

# Check Ollama port
netstat -tlnp | grep 11434

# Restart Ollama if needed
ollama serve
```

#### 2. Model Not Found
```bash
# List available models
ollama list

# Create the model if missing
ollama create unibase-erp -f ./Modelfile.unibase-erp

# Pull the model
ollama pull unibase-erp
```

#### 3. CUDA Memory Issues
```bash
# Check GPU memory
nvidia-smi

# Use CPU-only mode if needed
export OLLAMA_HOST=0.0.0.0
export OLLAMA_ORIGINS=*
ollama serve
```

#### 4. Python Dependencies
```bash
# Install required packages
pip install -r requirements.txt

# Check Ollama Python client
pip install ollama
```

### Debug Mode

Enable debug logging for troubleshooting:

```bash
export LOG_LEVEL=debug
python run_local.py
```

## Performance Optimization

### 1. Model Optimization
- Use appropriate model size for your hardware
- Consider quantization for memory efficiency
- Monitor GPU/CPU usage

### 2. Service Configuration
- Adjust connection pool sizes
- Configure appropriate timeouts
- Monitor response times

### 3. Caching
- Implement response caching for common queries
- Use Redis for session management
- Cache model responses

## Security Considerations

### 1. Local Deployment
- Models run locally, ensuring data privacy
- No external API calls for sensitive data
- Full control over model behavior

### 2. Access Control
- JWT-based authentication
- Role-based access control
- Rate limiting per user

### 3. Input Validation
- Sanitize user inputs
- Validate model parameters
- Monitor for prompt injection

## Monitoring and Logging

### 1. Service Metrics
- Request/response times
- Error rates
- Model usage statistics

### 2. Logging
- Structured logging with JSON format
- Request/response logging
- Error tracking and debugging

### 3. Health Checks
- Service health monitoring
- Model availability checks
- Connection status monitoring

## Development

### 1. Adding New Models
```python
# In llm_service.py, add to model mapping
"new-model": "ollama"
```

### 2. Customizing Responses
```python
# Modify the system prompt in chat requests
system_prompt="Your custom system prompt here"
```

### 3. Extending Functionality
- Add new API endpoints
- Implement custom agents
- Extend the LLM service

## Support

### 1. Documentation
- Check the main README.md
- Review API documentation
- Check configuration examples

### 2. Issues
- Check the troubleshooting section
- Review error logs
- Test with simple prompts first

### 3. Community
- Check project issues
- Review documentation
- Test with different models

## Next Steps

1. **Test the Integration**: Run the test scripts to verify everything works
2. **Configure API Gateway**: Update your API Gateway to use the AI Copilot service
3. **Customize Responses**: Modify system prompts for your specific ERP needs
4. **Monitor Performance**: Track response times and optimize as needed
5. **Scale Up**: Consider deploying to production with proper monitoring

## Example Usage

### Basic Chat
```python
from app.services.llm_service import LLMService, LLMRequest, LLMMessage

# Initialize service
llm_service = LLMService()

# Create request
request = LLMRequest(
    messages=[LLMMessage(role="user", content="Show me sales data")],
    model="unibase-erp",
    temperature=0.1
)

# Generate response
response = await llm_service.generate(request)
print(response.content)
```

### Streaming Response
```python
# Stream response
async for chunk in llm_service.generate_stream(request):
    print(chunk, end="", flush=True)
```

---

This integration provides a powerful, local AI solution for your ERP system. The `unibase-erp` model is specifically trained for ERP tasks and will provide more relevant and accurate responses for your business needs.
