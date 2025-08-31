-- Drop user and organization tables from AI Copilot database
-- These will be accessed via gRPC from auth service instead

-- Drop foreign key constraints first
ALTER TABLE IF EXISTS conversations DROP CONSTRAINT IF EXISTS conversations_user_id_fkey;
ALTER TABLE IF EXISTS conversations DROP CONSTRAINT IF EXISTS conversations_organization_id_fkey;
ALTER TABLE IF EXISTS messages DROP CONSTRAINT IF EXISTS messages_user_id_fkey;
ALTER TABLE IF EXISTS agent_executions DROP CONSTRAINT IF EXISTS agent_executions_user_id_fkey;
ALTER TABLE IF EXISTS knowledge_base DROP CONSTRAINT IF EXISTS knowledge_base_organization_id_fkey;
ALTER TABLE IF EXISTS scheduled_tasks DROP CONSTRAINT IF EXISTS scheduled_tasks_user_id_fkey;
ALTER TABLE IF EXISTS scheduled_tasks DROP CONSTRAINT IF EXISTS scheduled_tasks_organization_id_fkey;
ALTER TABLE IF EXISTS audit_logs DROP CONSTRAINT IF EXISTS audit_logs_user_id_fkey;
ALTER TABLE IF EXISTS audit_logs DROP CONSTRAINT IF EXISTS audit_logs_organization_id_fkey;

-- Drop tables (if they exist)
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS organizations CASCADE;

-- Add comments to remaining tables
COMMENT ON COLUMN conversations.user_id IS 'References auth service users table via gRPC';
COMMENT ON COLUMN conversations.organization_id IS 'References auth service organizations table via gRPC';
COMMENT ON COLUMN messages.user_id IS 'References auth service users table via gRPC';
COMMENT ON COLUMN agent_executions.user_id IS 'References auth service users table via gRPC';
COMMENT ON COLUMN knowledge_base.organization_id IS 'References auth service organizations table via gRPC';
COMMENT ON COLUMN scheduled_tasks.user_id IS 'References auth service users table via gRPC';
COMMENT ON COLUMN scheduled_tasks.organization_id IS 'References auth service organizations table via gRPC';
COMMENT ON COLUMN audit_logs.user_id IS 'References auth service users table via gRPC';
COMMENT ON COLUMN audit_logs.organization_id IS 'References auth service organizations table via gRPC';
