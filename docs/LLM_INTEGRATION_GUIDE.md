# LLM Integration Guide

This guide covers the implementation and usage of the LLM integration in the ERP AI Copilot system.

## Overview

The ERP AI Copilot now supports multiple LLM providers:
- **Ollama**: Local model inference (recommended for development)
- **OpenAI**: GPT-3.5, GPT-4, and GPT-4-turbo
- **Anthropic**: Claude-3 models (Haiku, Sonnet, Opus)

## Architecture

### Core Components

1. **LLM Service** (`services/llm_service.py`)
   - Unified interface for all LLM providers
   - Provider-specific implementations
   - Streaming support
   - Error handling and retries

2. **Configuration** (`config/llm_config.py`)
   - Environment-based configuration
   - Provider selection
   - Model recommendations

3. **Agent Integration**
   - All agents use the unified LLM service
   - Easy provider switching
   - Consistent API across providers

## Quick Setup

### 1. Choose Your Provider

#### Option 1: Ollama (Local - Recommended for Development)
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull models
ollama pull llama2
ollama pull codellama
ollama pull mistral

# Start server
ollama serve
```

#### Option 2: OpenAI (Cloud)
```bash
# Add to .env
OPENAI_API_KEY=your_api_key_here
DEFAULT_LLM_PROVIDER=openai
```

#### Option 3: Anthropic (Cloud)
```bash
# Add to .env
ANTHROPIC_API_KEY=your_api_key_here
DEFAULT_LLM_PROVIDER=anthropic
```

### 2. Test Your Setup

```bash
# Run interactive test
python main.py

# Test specific provider
python main.py --provider ollama --model llama2

# Test API mode
python main.py --mode api --port 8000
```

## Usage Examples

### Basic Query

```python
from services.llm_service import LLMService
import asyncio

async def example():
    service = LLMService()
    response = await service.generate({
        "messages": [{"role": "user", "content": "What is ERP?"}],
        "model": "llama2",
        "max_tokens": 100
    })
    print(response['content'])

asyncio.run(example())
```

### ERP-Specific Query

```python
from agents.master_agent import MasterAgent

async def erp_query():
    llm_service = LLMService()
    master_agent = MasterAgent(llm_service=llm_service)
    
    response = await master_agent.execute({
        "query": "Show me inventory levels for electronics",
        "user_id": "admin"
    })
    
    print(response['response'])
```

### Streaming Response

```python
async def streaming_example():
    service = LLMService()
    
    async for chunk in service.stream({
        "messages": [{"role": "user", "content": "Explain ERP benefits"}],
        "model": "llama2"
    }):
        print(chunk['content'], end='')
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `DEFAULT_LLM_PROVIDER` | Default provider | `ollama` |
| `DEFAULT_MODEL` | Default model | `llama2` |

### Provider-Specific Models

#### Ollama Models
- `llama2`: General-purpose model
- `codellama`: Code-focused model
- `mistral`: Fast and efficient
- `tinyllama`: Lightweight for quick responses

#### OpenAI Models
- `gpt-4`: Most capable
- `gpt-3.5-turbo`: Faster and cheaper
- `gpt-4-turbo`: Latest GPT-4 with improvements

#### Anthropic Models
- `claude-3-sonnet-20240229`: Balanced performance
- `claude-3-haiku-20240307`: Fast and cost-effective
- `claude-3-opus-20240229`: Most capable

## API Reference

### LLM Service Methods

#### generate()
Generate a single response:

```python
response = await llm_service.generate({
    "messages": [{"role": "user", "content": "Hello"}],
    "model": "llama2",
    "max_tokens": 150,
    "temperature": 0.7
})
```

#### stream()
Generate streaming response:

```python
async for chunk in llm_service.stream({
    "messages": [...],
    "model": "llama2"
}):
    print(chunk['content'])
```

### HTTP API

#### POST /query
Process natural language query:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is our inventory status?"}'
```

#### GET /providers
List available providers:

```bash
curl http://localhost:8000/providers
```

## Troubleshooting

### Common Issues

#### Ollama Connection
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Check available models
ollama list
```

#### API Key Issues
```bash
# Test provider availability
python -c "
from config.llm_config import LLMConfig
config = LLMConfig()
print('Available:', list(config.get_available_providers().keys()))
"
```

#### Model Not Found
```bash
# List available models for Ollama
ollama list

# Pull missing model
ollama pull llama2
```

### Debug Mode

Enable detailed logging:
```bash
export LOG_LEVEL=DEBUG
python main.py
```

## Performance Tips

### Local (Ollama)
- Use `tinyllama` for quick responses
- Increase timeout for complex queries
- Monitor system resources

### Cloud Providers
- Set appropriate token limits
- Use streaming for long responses
- Monitor API usage and costs

## Migration Guide

### From Single Provider to Multi-Provider

The new LLM service is backward compatible. Existing code will continue to work with the default provider.

### Configuration Update

Update your `.env` file:
```bash
# Old format
MODEL=gpt-4

# New format
DEFAULT_LLM_PROVIDER=openai
DEFAULT_MODEL=gpt-4
OPENAI_API_KEY=your_key
```

## Best Practices

### Development
1. Start with Ollama for development
2. Use streaming for better UX
3. Implement proper error handling
4. Monitor token usage

### Production
1. Use cloud providers for reliability
2. Implement rate limiting
3. Cache responses when appropriate
4. Monitor costs and performance

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review logs with `LOG_LEVEL=DEBUG`
3. Test with `examples/llm_usage_example.py`
4. Check provider-specific documentation