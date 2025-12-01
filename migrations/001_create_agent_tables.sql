-- ============================================================================
-- Phase 0: Database Schema Creation for MCP Multi-Agent System
-- ============================================================================
-- This migration creates all necessary tables for the AI Agent Workforce system
-- Run this before starting Phase 1 implementation
-- ============================================================================

-- AI Agents table
CREATE TABLE IF NOT EXISTS ai_agents (
    agent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(100) NOT NULL,  -- data_entry, accountant, pm, inventory, sales
    description TEXT,
    
    -- LLM Configuration
    model_provider VARCHAR(50) NOT NULL,  -- openai, anthropic, gemini, groq, ollama
    model_name VARCHAR(100) NOT NULL,
    temperature FLOAT DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 4000,
    
    -- Behavior
    system_prompt TEXT,
    personality JSONB,  -- tone, style, preferences
    
    -- Tools & Permissions
    allowed_tools TEXT[],  -- Array of tool names
    permissions JSONB,     -- RBAC permissions
    
    -- Scheduling
    triggers JSONB,        -- Event triggers
    schedule JSONB,        -- Cron-like schedules
    
    -- State
    state VARCHAR(50) DEFAULT 'active',  -- active, paused, archived
    memory_config JSONB,   -- Memory settings
    
    -- Metadata
    created_by UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_active_at TIMESTAMP,
    
    -- Limits (set by super admin)
    max_parallel_tasks INTEGER DEFAULT 3,
    max_daily_tokens INTEGER,
    
    CONSTRAINT chk_agent_state CHECK (state IN ('active', 'paused', 'archived'))
);

-- Create indexes for ai_agents
CREATE INDEX IF NOT EXISTS idx_ai_agents_org ON ai_agents(organization_id);
CREATE INDEX IF NOT EXISTS idx_ai_agents_role ON ai_agents(role);
CREATE INDEX IF NOT EXISTS idx_ai_agents_state ON ai_agents(state);
CREATE INDEX IF NOT EXISTS idx_ai_agents_created_at ON ai_agents(created_at);

-- Agent Tasks table
CREATE TABLE IF NOT EXISTS agent_tasks (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES ai_agents(agent_id) ON DELETE CASCADE,
    organization_id UUID NOT NULL,
    
    -- Assignment
    assigned_by UUID,
    assigned_at TIMESTAMP DEFAULT NOW(),
    
    -- Task Details
    task_name VARCHAR(255) NOT NULL,
    task_type VARCHAR(100) NOT NULL,
    description TEXT,
    instructions TEXT,  -- Detailed instructions for agent
    context JSONB,      -- Additional context data
    
    -- Priority & Scheduling
    priority VARCHAR(20) DEFAULT 'normal',  -- critical, high, normal, low
    priority_score INTEGER,  -- Calculated intelligent priority
    scheduled_for TIMESTAMP,
    deadline TIMESTAMP,
    recurrence_rule VARCHAR(100),  -- Cron expression for recurring tasks
    
    -- Dependencies
    depends_on UUID[],  -- Array of task_ids this task depends on
    blocks UUID[],      -- Array of task_ids blocked by this task
    
    -- Execution
    status VARCHAR(50) DEFAULT 'pending',  -- pending, running, completed, failed, paused, suspended
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    paused_at TIMESTAMP,
    execution_time_ms INTEGER,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    
    -- State Preservation (for LLM failover)
    execution_state JSONB,  -- Preserved state for resume
    checkpoint_data JSONB,  -- Checkpoint for recovery
    can_resume BOOLEAN DEFAULT true,
    
    -- LLM Provider
    llm_provider VARCHAR(50),
    llm_model VARCHAR(100),
    llm_fallback_used BOOLEAN DEFAULT false,
    llm_failures INTEGER DEFAULT 0,
    
    -- Results
    result JSONB,
    output_artifacts TEXT[],  -- URLs to generated files, reports, etc.
    error_message TEXT,
    error_analysis JSONB,
    logs TEXT[],
    
    -- Code Execution
    code_generated TEXT,
    code_executed BOOLEAN DEFAULT FALSE,
    
    -- Intelligence
    intent VARCHAR(100),  -- Classified task intent
    complexity_score FLOAT,  -- 0-1 complexity estimate
    estimated_duration_ms INTEGER,
    actual_duration_ms INTEGER,
    
    -- Metrics
    tokens_used INTEGER,
    tools_called TEXT[],
    
    -- Metadata
    tags TEXT[],
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT chk_task_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'paused', 'suspended')),
    CONSTRAINT chk_task_priority CHECK (priority IN ('critical', 'high', 'normal', 'low'))
);

-- Create indexes for agent_tasks
CREATE INDEX IF NOT EXISTS idx_agent_tasks_agent ON agent_tasks(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_org ON agent_tasks(organization_id);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_priority ON agent_tasks(priority);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_created_at ON agent_tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_scheduled ON agent_tasks(scheduled_for);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_deadline ON agent_tasks(deadline);

-- Agent Messages table (Inter-agent communication)
CREATE TABLE IF NOT EXISTS agent_messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    
    -- Sender & Receiver
    sender_agent_id UUID REFERENCES ai_agents(agent_id),
    sender_user_id UUID,  -- If sent by user
    receiver_agent_id UUID REFERENCES ai_agents(agent_id),
    receiver_user_id UUID,  -- If sent to user
    
    -- Message Details
    message_type VARCHAR(50) NOT NULL,  -- agent_to_agent, agent_to_user, request_help, share_data
    subject VARCHAR(255),
    content TEXT NOT NULL,
    
    -- Data Sharing
    shared_data JSONB,  -- Data shared between agents
    attachments TEXT[],  -- File references
    
    -- Context
    related_task_id UUID REFERENCES agent_tasks(task_id),
    conversation_thread_id UUID,  -- For threaded conversations
    
    -- Status
    status VARCHAR(50) DEFAULT 'sent',  -- sent, delivered, read, replied
    read_at TIMESTAMP,
    replied_at TIMESTAMP,
    
    -- Priority
    priority VARCHAR(20) DEFAULT 'normal',  -- low, normal, high, urgent
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,  -- Optional expiration
    
    CONSTRAINT chk_message_type CHECK (message_type IN ('agent_to_agent', 'agent_to_user', 'request_help', 'share_data')),
    CONSTRAINT chk_message_status CHECK (status IN ('sent', 'delivered', 'read', 'replied'))
);

-- Create indexes for agent_messages
CREATE INDEX IF NOT EXISTS idx_agent_messages_org ON agent_messages(organization_id);
CREATE INDEX IF NOT EXISTS idx_agent_messages_sender_agent ON agent_messages(sender_agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_messages_receiver_agent ON agent_messages(receiver_agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_messages_created_at ON agent_messages(created_at);

-- Agent Collaboration table
CREATE TABLE IF NOT EXISTS agent_collaborations (
    collaboration_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    
    -- Collaboration Details
    name VARCHAR(255) NOT NULL,
    description TEXT,
    collaboration_type VARCHAR(50),  -- joint_task, data_sharing, workflow
    
    -- Participating Agents
    agent_ids UUID[] NOT NULL,  -- Array of agent IDs
    coordinator_agent_id UUID REFERENCES ai_agents(agent_id),
    
    -- Task Context
    shared_goal TEXT,
    shared_data JSONB,
    
    -- Status
    status VARCHAR(50) DEFAULT 'active',  -- active, completed, cancelled
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    
    -- Results
    collaboration_result JSONB,
    
    CONSTRAINT chk_collaboration_status CHECK (status IN ('active', 'completed', 'cancelled'))
);

-- Create indexes for agent_collaborations
CREATE INDEX IF NOT EXISTS idx_agent_collaborations_org ON agent_collaborations(organization_id);
CREATE INDEX IF NOT EXISTS idx_agent_collaborations_coordinator ON agent_collaborations(coordinator_agent_id);

-- LLM Provider Status table
CREATE TABLE IF NOT EXISTS llm_provider_status (
    status_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_name VARCHAR(50) NOT NULL,
    model_name VARCHAR(100),
    
    -- Status
    is_available BOOLEAN DEFAULT true,
    last_check_at TIMESTAMP DEFAULT NOW(),
    last_success_at TIMESTAMP,
    last_failure_at TIMESTAMP,
    
    -- Failure Tracking
    consecutive_failures INTEGER DEFAULT 0,
    total_failures_24h INTEGER DEFAULT 0,
    
    -- Performance
    avg_response_time_ms INTEGER,
    success_rate_24h DECIMAL(5, 2),
    
    -- Circuit Breaker
    circuit_breaker_status VARCHAR(20) DEFAULT 'closed',  -- closed, open, half_open
    circuit_breaker_opened_at TIMESTAMP,
    
    -- Metadata
    error_message TEXT,
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(provider_name, model_name),
    CONSTRAINT chk_circuit_breaker_status CHECK (circuit_breaker_status IN ('closed', 'open', 'half_open'))
);

-- Create indexes for llm_provider_status
CREATE INDEX IF NOT EXISTS idx_llm_provider_status_provider ON llm_provider_status(provider_name);
CREATE INDEX IF NOT EXISTS idx_llm_provider_status_available ON llm_provider_status(is_available);

-- Organization Agent Limits table (Super Admin control)
CREATE TABLE IF NOT EXISTS organization_agent_limits (
    organization_id UUID PRIMARY KEY,
    max_agents INTEGER DEFAULT 5,
    max_parallel_tasks_per_agent INTEGER DEFAULT 3,
    max_daily_tokens_per_org INTEGER DEFAULT 1000000,
    features JSONB,  -- enabled features
    updated_by UUID,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Agent Billing table
CREATE TABLE IF NOT EXISTS agent_billing (
    billing_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    agent_id UUID NOT NULL REFERENCES ai_agents(agent_id) ON DELETE CASCADE,
    billing_period_start TIMESTAMP NOT NULL,
    billing_period_end TIMESTAMP NOT NULL,
    
    -- Usage Metrics
    total_tasks_executed INTEGER DEFAULT 0,
    total_tokens_used BIGINT DEFAULT 0,
    total_execution_time_ms BIGINT DEFAULT 0,
    total_api_calls INTEGER DEFAULT 0,
    
    -- Cost Breakdown
    base_agent_cost DECIMAL(10, 2) DEFAULT 0.00,      -- Fixed monthly cost per agent
    token_cost DECIMAL(10, 2) DEFAULT 0.00,           -- Variable cost based on tokens
    execution_cost DECIMAL(10, 2) DEFAULT 0.00,       -- Cost based on compute time
    api_call_cost DECIMAL(10, 2) DEFAULT 0.00,        -- Cost for external API calls
    storage_cost DECIMAL(10, 2) DEFAULT 0.00,         -- Cost for memory/storage
    total_cost DECIMAL(10, 2) DEFAULT 0.00,
    
    -- Billing Status
    status VARCHAR(50) DEFAULT 'pending',  -- pending, invoiced, paid, overdue
    invoice_id VARCHAR(255),
    payment_date TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT chk_billing_status CHECK (status IN ('pending', 'invoiced', 'paid', 'overdue'))
);

-- Create indexes for agent_billing
CREATE INDEX IF NOT EXISTS idx_agent_billing_org ON agent_billing(organization_id);
CREATE INDEX IF NOT EXISTS idx_agent_billing_agent ON agent_billing(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_billing_period ON agent_billing(billing_period_start, billing_period_end);

-- Agent Usage Logs table (for detailed billing)
CREATE TABLE IF NOT EXISTS agent_usage_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    task_id UUID REFERENCES agent_tasks(task_id),
    
    -- Usage Details
    timestamp TIMESTAMP DEFAULT NOW(),
    tokens_used INTEGER DEFAULT 0,
    execution_time_ms INTEGER DEFAULT 0,
    api_calls_made INTEGER DEFAULT 0,
    tools_used TEXT[],
    
    -- Cost Calculation
    token_cost DECIMAL(10, 4) DEFAULT 0.0000,
    execution_cost DECIMAL(10, 4) DEFAULT 0.0000,
    api_call_cost DECIMAL(10, 4) DEFAULT 0.0000,
    total_cost DECIMAL(10, 4) DEFAULT 0.0000,
    
    -- Metadata
    model_used VARCHAR(100),
    provider VARCHAR(50)
);

-- Create indexes for agent_usage_logs
CREATE INDEX IF NOT EXISTS idx_agent_usage_logs_org_agent_timestamp ON agent_usage_logs(organization_id, agent_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_agent_usage_logs_billing_period ON agent_usage_logs(timestamp);

-- Organization Knowledge Base Configuration
CREATE TABLE IF NOT EXISTS organization_knowledge_base (
    kb_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    
    -- Configuration
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_enabled BOOLEAN DEFAULT true,
    
    -- Source Configuration
    source_service VARCHAR(100),  -- document-service, legal-service, etc.
    source_api_endpoint TEXT,
    source_auth_config JSONB,    -- API keys, tokens, etc.
    
    -- Sync Configuration
    sync_frequency VARCHAR(50) DEFAULT 'daily',  -- realtime, hourly, daily, weekly
    last_sync_at TIMESTAMP,
    next_sync_at TIMESTAMP,
    sync_status VARCHAR(50) DEFAULT 'pending',  -- pending, syncing, completed, failed
    
    -- Document Filters
    document_types TEXT[],        -- contracts, reports, policies, etc.
    department_filter TEXT[],     -- finance, legal, hr, etc.
    date_range_filter JSONB,      -- {from: date, to: date}
    custom_filters JSONB,
    
    -- Processing Configuration
    embedding_model VARCHAR(100) DEFAULT 'text-embedding-3-small',
    chunk_size INTEGER DEFAULT 1000,
    chunk_overlap INTEGER DEFAULT 200,
    
    -- Statistics
    total_documents INTEGER DEFAULT 0,
    total_chunks INTEGER DEFAULT 0,
    total_size_bytes BIGINT DEFAULT 0,
    
    -- Metadata
    created_by UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT chk_kb_sync_status CHECK (sync_status IN ('pending', 'syncing', 'completed', 'failed'))
);

-- Create indexes for organization_knowledge_base
CREATE INDEX IF NOT EXISTS idx_org_kb_org ON organization_knowledge_base(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_kb_enabled ON organization_knowledge_base(is_enabled);

-- ============================================================================
-- Comments and Documentation
-- ============================================================================

COMMENT ON TABLE ai_agents IS 'AI agents created by organizations for autonomous task execution';
COMMENT ON TABLE agent_tasks IS 'Tasks assigned to or executed by AI agents';
COMMENT ON TABLE agent_messages IS 'Messages exchanged between agents and users';
COMMENT ON TABLE agent_collaborations IS 'Multi-agent collaboration sessions';
COMMENT ON TABLE llm_provider_status IS 'Health status and availability of LLM providers';
COMMENT ON TABLE organization_agent_limits IS 'Organization-level limits for agent usage';
COMMENT ON TABLE agent_billing IS 'Billing records for agent usage';
COMMENT ON TABLE agent_usage_logs IS 'Detailed usage logs for billing calculations';
COMMENT ON TABLE organization_knowledge_base IS 'Organization-specific knowledge base configuration';

-- ============================================================================
-- Migration Complete
-- ============================================================================

-- Insert default LLM provider status records
INSERT INTO llm_provider_status (provider_name, model_name, is_available) VALUES
    ('openai', 'gpt-4o', true),
    ('openai', 'gpt-4o-mini', true),
    ('anthropic', 'claude-sonnet-4-5-20250929', true),
    ('anthropic', 'claude-3-5-haiku-20241022', true),
    ('gemini', 'gemini-2.5-pro', true),
    ('gemini', 'gemini-2.5-flash', true),
    ('groq', 'llama-3.3-70b-versatile', true),
    ('groq', 'llama-3.1-8b-instant', true),
    ('ollama', 'llama3.1:8b', true)
ON CONFLICT (provider_name, model_name) DO NOTHING;

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✅ Phase 0 database migration completed successfully!';
    RAISE NOTICE 'Created tables: ai_agents, agent_tasks, agent_messages, agent_collaborations, llm_provider_status, organization_agent_limits, agent_billing, agent_usage_logs, organization_knowledge_base';
END $$;
