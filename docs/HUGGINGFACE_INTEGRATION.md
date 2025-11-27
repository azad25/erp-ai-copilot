# HuggingFace Provider Integration

## Overview

The ERP AI Copilot now supports HuggingFace Router API as an LLM provider, giving you access to a wide range of open-source models through a unified interface.

## Features

- **Multiple Model Support**: Access to various models including Llama, Qwen, Mixtral, Gemma, and more
- **OpenAI-Compatible API**: Uses the familiar OpenAI client interface
- **Automatic Fallback**: If one provider fails, automatically falls back to other configured providers
- **Frontend Configuration**: Manage API keys and settings through the web interface
- **Real-time Status**: Monitor provider availability and test connections

## Setup

### 1. Get HuggingFace API Token

1. Go to [HuggingFace](https://huggingface.co/)
2. Sign up or log in
3. Navigate to Settings → Access Tokens
4. Create a new token with read permissions
5. Copy the token (starts with `hf_`)

### 2. Configure via Frontend

1. Navigate to **AI → Settings** in the ERP frontend
2. Find the **HuggingFace Router** provider
3. Click **Edit**
4. Enter your HF token in the API Key field
5. Select a default model
6. Set priority (higher = tried first in fallback)
7. Enable the provider
8. Click **Test** to verify connection

### 3. Configure via Environment (Alternative)

Add to `.env` file:

```bash
HF_TOKEN=hf_your_token_here
```

### 4. Run Database Migration

```bash
cd erp-ai-copilot
./scripts/run_llm_settings_migration.sh
```

## Available Models

The HuggingFace provider supports these models:

- `moonshotai/Kimi-K2-Thinking:novita` - Advanced reasoning model
- `openai/gpt-oss-20b:groq` - Fast GPT-compatible model
- `meta-llama/Llama-3.3-70B-Instruct` - Latest Llama model
- `Qwen/Qwen2.5-72B-Instruct` - Qwen 2.5 instruction model
- `mistralai/Mixtral-8x7B-Instruct-v0.1` - Mixtral MoE model
- `google/gemma-2-9b-it` - Google's Gemma model
- `microsoft/Phi-3-medium-4k-instruct` - Microsoft Phi-3

## Usage

### Via API

```python
from app.services.llm_service import LLMService, LLMRequest, LLMMessage

llm_service = LLMService()

request = LLMRequest(
    messages=[
        LLMMessage(role="user", content="What is the capital of France?")
    ],
    model="meta-llama/Llama-3.3-70B-Instruct",
    temperature=0.7,
    max_tokens=1000
)

response = await llm_service.generate(request)
print(response.content)
```

### Streaming Response

```python
request = LLMRequest(
    messages=[LLMMessage(role="user", content="Explain quantum computing")],
    model="Qwen/Qwen2.5-72B-Instruct",
    stream=True
)

async for chunk in llm_service.generate_stream(request):
    print(chunk, end='', flush=True)
```

## Automatic Fallback

The system automatically tries alternative providers if one fails:

1. **Primary Provider Fails** → System detects error (404, 503, timeout, etc.)
2. **Fallback Triggered** → Tries next available provider based on priority
3. **Model Mapping** → Automatically selects appropriate model for fallback provider
4. **User Notification** → Frontend receives status update

### Fallback Order (Default)

1. HuggingFace (priority: 90)
2. Gemini (priority: 100)
3. OpenAI (priority: 80)
4. Anthropic (priority: 70)
5. Ollama (priority: 60)

You can adjust priorities in the settings page.

## Frontend Settings Page

### Features

- **Provider List**: View all configured LLM providers
- **Status Indicators**: 
  - 🟢 Active - Provider is working
  - 🔴 Unavailable - Provider has issues
  - ⚫ Disabled - Provider is turned off
- **Quick Actions**:
  - Enable/Disable providers
  - Set default provider
  - Test connections
  - Edit configurations
- **Real-time Testing**: Test provider connections without affecting production

### Navigation

```
Dashboard → AI → Settings
```

Or directly:
```
http://localhost:3000/ai/settings
```

## API Endpoints

### Get All Providers
```http
GET /api/llm-settings/providers
```

### Get Provider Status
```http
GET /api/llm-settings/providers/status
```

### Update Provider
```http
PUT /api/llm-settings/providers/{provider_id}
Content-Type: application/json

{
  "api_key": "hf_new_token",
  "is_enabled": true,
  "priority": 95,
  "default_model": "meta-llama/Llama-3.3-70B-Instruct"
}
```

### Test Provider
```http
POST /api/llm-settings/providers/{provider_id}/test
```

## Error Handling

### Common Errors

#### 1. API Key Not Configured
```json
{
  "success": false,
  "message": "Provider not available - check API key and configuration"
}
```

**Solution**: Add HF_TOKEN in settings page

#### 2. Model Not Found
```json
{
  "error": "HuggingFace API error: Model not found"
}
```

**Solution**: Check model name spelling or select from available models list

#### 3. Rate Limit Exceeded
```json
{
  "error": "HuggingFace API error: Rate limit exceeded"
}
```

**Solution**: System automatically falls back to next provider

### Fallback Behavior

When a provider fails, the system:

1. Logs the error
2. Tries the next available provider
3. Maps the model to an equivalent on the fallback provider
4. Returns response with metadata indicating fallback was used

Example response with fallback:
```json
{
  "content": "Paris is the capital of France.",
  "model": "gpt-4o-mini",
  "metadata": {
    "provider": "openai",
    "fallback_from": "huggingface",
    "original_model": "meta-llama/Llama-3.3-70B-Instruct"
  }
}
```

## Monitoring

### Check Provider Health

```bash
curl http://localhost:8003/api/llm-settings/providers/status
```

### View Logs

```bash
# Backend logs
docker logs erp-ai-copilot -f | grep huggingface

# Filter for errors
docker logs erp-ai-copilot -f | grep "HuggingFace.*error"
```

## Best Practices

1. **Enable Multiple Providers**: Configure at least 2-3 providers for redundancy
2. **Set Priorities**: Higher priority for faster/cheaper models
3. **Test Regularly**: Use the test button to verify connections
4. **Monitor Usage**: Check logs for fallback frequency
5. **Secure API Keys**: Never commit tokens to version control

## Troubleshooting

### Provider Shows as Unavailable

1. Check API key is correct
2. Verify HuggingFace account has credits
3. Test connection using the Test button
4. Check backend logs for detailed errors

### Fallback Not Working

1. Ensure at least one other provider is enabled
2. Check priorities are set correctly
3. Verify fallback providers have valid API keys
4. Review logs for fallback attempts

### Frontend Not Loading Settings

1. Check backend is running: `curl http://localhost:8003/health`
2. Verify database migration ran successfully
3. Check browser console for errors
4. Ensure API proxy route is configured

## Security Notes

- API keys are stored in the database (encrypt in production)
- Keys are never exposed in API responses
- Frontend only shows if key is configured (boolean)
- Use environment variables for sensitive data in production

## Performance

- **Latency**: HuggingFace Router typically 1-3s response time
- **Throughput**: Depends on your HuggingFace plan
- **Caching**: Responses can be cached at application level
- **Streaming**: Supported for real-time responses

## Future Enhancements

- [ ] Model performance metrics
- [ ] Cost tracking per provider
- [ ] Custom model additions
- [ ] Provider-specific rate limiting
- [ ] Automatic model selection based on query type
- [ ] A/B testing between providers

## Support

For issues or questions:
1. Check logs: `docker logs erp-ai-copilot`
2. Test provider: Use frontend test button
3. Review documentation: `/docs/LLM_INTEGRATION_GUIDE.md`
4. Check HuggingFace status: https://status.huggingface.co/
