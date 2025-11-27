-- Migration: Create LLM Provider Settings Table
-- Description: Stores configuration for different LLM providers

CREATE TABLE IF NOT EXISTS llm_provider_settings (
    id SERIAL PRIMARY KEY,
    provider_name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    api_key TEXT,
    base_url VARCHAR(255),
    is_enabled BOOLEAN DEFAULT TRUE NOT NULL,
    is_default BOOLEAN DEFAULT FALSE NOT NULL,
    priority INTEGER DEFAULT 0 NOT NULL,
    config JSONB,
    available_models JSONB,
    default_model VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Create index on provider_name for faster lookups
CREATE INDEX IF NOT EXISTS idx_llm_provider_name ON llm_provider_settings(provider_name);

-- Create index on is_enabled for filtering
CREATE INDEX IF NOT EXISTS idx_llm_provider_enabled ON llm_provider_settings(is_enabled);

-- Insert default providers
INSERT INTO llm_provider_settings (provider_name, display_name, is_enabled, is_default, priority, available_models, default_model)
VALUES 
    ('gemini', 'Google Gemini', TRUE, TRUE, 100, '["gemini2.0:flash", "gemini2.5:pro"]'::jsonb, 'gemini2.0:flash'),
    ('huggingface', 'HuggingFace Router', FALSE, FALSE, 90, '["moonshotai/Kimi-K2-Thinking:novita", "openai/gpt-oss-20b:groq", "meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen2.5-72B-Instruct", "mistralai/Mixtral-8x7B-Instruct-v0.1", "google/gemma-2-9b-it", "microsoft/Phi-3-medium-4k-instruct"]'::jsonb, 'meta-llama/Llama-3.3-70B-Instruct'),
    ('openai', 'OpenAI', FALSE, FALSE, 80, '["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4o", "gpt-4o-mini"]'::jsonb, 'gpt-4o-mini'),
    ('anthropic', 'Anthropic Claude', FALSE, FALSE, 70, '["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"]'::jsonb, 'claude-3-5-haiku-20241022'),
    ('ollama', 'Ollama (Local)', FALSE, FALSE, 60, '["unibase-erp", "llama2", "llama3", "mistral", "codellama"]'::jsonb, 'llama2')
ON CONFLICT (provider_name) DO NOTHING;

-- Add comment to table
COMMENT ON TABLE llm_provider_settings IS 'Configuration and API keys for LLM providers';
