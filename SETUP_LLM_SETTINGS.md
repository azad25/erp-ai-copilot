# LLM Provider Settings - Quick Setup Guide

## 🚀 Quick Start

### 1. Run Database Migration

```bash
cd erp-ai-copilot
./scripts/run_llm_settings_migration.sh
```

### 2. Set HuggingFace Token (Optional)

Add to `.env`:
```bash
HF_TOKEN=your_huggingface_token_here
```

Or configure via frontend (recommended).

### 3. Restart Services

```bash
# If using Docker
docker-compose restart erp-ai-copilot

# If running locally
# Stop the service and restart
python main.py
```

### 4. Access Settings Page

Navigate to: `http://localhost:3000/ai/settings`

## 📋 What's New

### Backend Changes

1. **New Provider**: `HuggingFaceProvider` class in `app/services/llm_service.py`
2. **Database Model**: `LLMProviderSettings` in `app/models/llm_provider_settings.py`
3. **API Endpoints**: `/api/llm-settings/*` in `app/api/llm_settings.py`
4. **Migration**: `migrations/create_llm_provider_settings.sql`

### Frontend Changes

1. **Settings Page**: `src/app/(admin)/ai/settings/page.tsx`
2. **API Proxy**: `src/app/api/ai-copilot/llm-settings/[...path]/route.ts`

### Features

✅ HuggingFace Router API integration
✅ Multiple model support (Llama, Qwen, Mixtral, etc.)
✅ Frontend settings management
✅ Automatic fallback between providers
✅ Real-time provider testing
✅ Priority-based provider selection
✅ API key management via UI

## 🔧 Configuration

### Provider Priority (Default)

- Gemini: 100 (highest)
- HuggingFace: 90
- OpenAI: 80
- Anthropic: 70
- Ollama: 60 (lowest)

Higher priority = tried first when fallback is needed.

### Available HuggingFace Models

- `moonshotai/Kimi-K2-Thinking:novita`
- `openai/gpt-oss-20b:groq`
- `meta-llama/Llama-3.3-70B-Instruct` (recommended)
- `Qwen/Qwen2.5-72B-Instruct`
- `mistralai/Mixtral-8x7B-Instruct-v0.1`
- `google/gemma-2-9b-it`
- `microsoft/Phi-3-medium-4k-instruct`

## 🧪 Testing

### Test via Frontend

1. Go to AI → Settings
2. Find HuggingFace provider
3. Click "Test" button
4. Check result message

### Test via API

```bash
# Get provider status
curl http://localhost:8003/api/llm-settings/providers/status

# Test specific provider
curl -X POST http://localhost:8003/api/llm-settings/providers/2/test
```

### Test LLM Request

```python
import asyncio
from app.services.llm_service import LLMService, LLMRequest, LLMMessage

async def test():
    service = LLMService()
    
    request = LLMRequest(
        messages=[LLMMessage(role="user", content="Hello!")],
        model="meta-llama/Llama-3.3-70B-Instruct"
    )
    
    response = await service.generate(request)
    print(response.content)

asyncio.run(test())
```

## 🔄 Fallback Behavior

### Example Scenario

1. User sends message to AI Copilot
2. System tries HuggingFace (priority 90)
3. HuggingFace returns 503 (overloaded)
4. System automatically tries Gemini (priority 100)
5. Gemini responds successfully
6. User receives response with metadata showing fallback occurred

### Error Messages

If all providers fail:
```
"I apologize, but I'm experiencing technical difficulties with all AI providers at the moment. Please try again in a few minutes."
```

## 📊 Monitoring

### Check Logs

```bash
# View all AI Copilot logs
docker logs erp-ai-copilot -f

# Filter HuggingFace logs
docker logs erp-ai-copilot -f | grep huggingface

# Check for errors
docker logs erp-ai-copilot -f | grep "error"
```

### Provider Status

```bash
curl http://localhost:8003/api/llm-settings/providers/status | jq
```

## 🐛 Troubleshooting

### Migration Failed

```bash
# Check if table exists
psql -U postgres -d erp_ai_copilot -c "\dt llm_provider_settings"

# If exists, drop and recreate
psql -U postgres -d erp_ai_copilot -c "DROP TABLE IF EXISTS llm_provider_settings CASCADE;"
./scripts/run_llm_settings_migration.sh
```

### Frontend Not Loading

1. Check backend is running: `curl http://localhost:8003/health`
2. Check frontend proxy: `curl http://localhost:3000/api/ai-copilot/llm-settings/providers`
3. Check browser console for errors
4. Verify NEXT_PUBLIC_AI_COPILOT_URL in frontend .env

### Provider Shows Unavailable

1. Check API key is set
2. Test connection using Test button
3. Check backend logs for errors
4. Verify HuggingFace account status

## 📚 Documentation

- Full guide: `docs/HUGGINGFACE_INTEGRATION.md`
- LLM integration: `docs/LLM_INTEGRATION_GUIDE.md`
- API docs: `http://localhost:8003/docs`

## 🎯 Next Steps

1. ✅ Run migration
2. ✅ Configure HuggingFace token
3. ✅ Test provider connection
4. ✅ Enable multiple providers for redundancy
5. ✅ Set appropriate priorities
6. ✅ Monitor usage and fallback frequency

## 💡 Tips

- Enable at least 2-3 providers for better reliability
- Set faster/cheaper models with higher priority
- Use Test button before enabling in production
- Monitor logs for fallback patterns
- Adjust priorities based on your usage patterns

## 🔐 Security

- API keys stored in database (encrypt in production)
- Keys never exposed in API responses
- Use environment variables for production
- Rotate keys regularly
- Monitor for unauthorized usage
