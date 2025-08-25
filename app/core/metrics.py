"""
Metrics configuration for monitoring and observability.
"""
from prometheus_client import Counter, Histogram, Gauge, Summary, generate_latest
import structlog

logger = structlog.get_logger(__name__)

# Chat metrics
CHAT_REQUESTS = Counter('ai_copilot_chat_requests_total', 'Total chat requests', ['agent_type', 'model'])
CHAT_RESPONSES = Histogram('ai_copilot_chat_response_duration_seconds', 'Chat response time', ['agent_type', 'model'])
CHAT_ERRORS = Counter('ai_copilot_chat_errors_total', 'Total chat errors', ['agent_type', 'error_type'])

# Agent metrics
AGENT_EXECUTIONS = Counter('ai_copilot_agent_executions_total', 'Total agent executions', ['agent_type', 'action_type'])
AGENT_EXECUTION_TIME = Histogram('ai_copilot_agent_execution_duration_seconds', 'Agent execution time', ['agent_type', 'action_type'])
AGENT_SUCCESS_RATE = Gauge('ai_copilot_agent_success_rate', 'Agent success rate', ['agent_type'])

# RAG metrics
RAG_QUERIES = Counter('ai_copilot_rag_queries_total', 'Total RAG queries', ['collection', 'model'])
RAG_QUERY_TIME = Histogram('ai_copilot_rag_query_duration_seconds', 'RAG query time', ['collection', 'model'])
RAG_DOCUMENTS_INGESTED = Counter('ai_copilot_rag_documents_ingested_total', 'Total documents ingested', ['document_type'])

# WebSocket metrics
WS_CONNECTIONS = Gauge('ai_copilot_websocket_connections_total', 'Active WebSocket connections')
WS_MESSAGES = Counter('ai_copilot_websocket_messages_total', 'Total WebSocket messages', ['message_type'])
WS_ERRORS = Counter('ai_copilot_websocket_errors_total', 'Total WebSocket errors', ['error_type'])

# Database metrics
DB_CONNECTIONS = Gauge('ai_copilot_db_connections_active', 'Active database connections', ['database'])
DB_QUERY_TIME = Histogram('ai_copilot_db_query_duration_seconds', 'Database query time', ['database', 'operation'])
DB_ERRORS = Counter('ai_copilot_db_errors_total', 'Total database errors', ['database', 'error_type'])

# Cache metrics
CACHE_HITS = Counter('ai_copilot_cache_hits_total', 'Total cache hits', ['cache_type'])
CACHE_MISSES = Counter('ai_copilot_cache_misses_total', 'Total cache misses', ['cache_type'])
CACHE_SIZE = Gauge('ai_copilot_cache_size_bytes', 'Cache size in bytes', ['cache_type'])

# Task metrics
TASK_QUEUED = Counter('ai_copilot_tasks_queued_total', 'Total tasks queued', ['task_type'])
TASK_PROCESSED = Counter('ai_copilot_tasks_processed_total', 'Total tasks processed', ['task_type'])
TASK_PROCESSING_TIME = Histogram('ai_copilot_task_processing_duration_seconds', 'Task processing time', ['task_type'])
TASK_FAILURES = Counter('ai_copilot_task_failures_total', 'Total task failures', ['task_type'])

# Business metrics
BUSINESS_ACTIONS = Counter('ai_copilot_business_actions_total', 'Total business actions', ['action_type', 'module'])
BUSINESS_ACTION_VALUE = Summary('ai_copilot_business_action_value', 'Business action value', ['action_type', 'module'])
USER_SATISFACTION = Gauge('ai_copilot_user_satisfaction_score', 'User satisfaction score', ['user_type'])

# System metrics
SYSTEM_MEMORY_USAGE = Gauge('ai_copilot_system_memory_bytes', 'System memory usage in bytes')
SYSTEM_CPU_USAGE = Gauge('ai_copilot_system_cpu_percentage', 'System CPU usage percentage')
SYSTEM_DISK_USAGE = Gauge('ai_copilot_system_disk_bytes', 'System disk usage in bytes')

# AI Model metrics
AI_MODEL_REQUESTS = Counter('ai_copilot_ai_model_requests_total', 'Total AI model requests', ['provider', 'model'])
AI_MODEL_RESPONSE_TIME = Histogram('ai_copilot_ai_model_response_duration_seconds', 'AI model response time', ['provider', 'model'])
AI_MODEL_TOKENS_USED = Counter('ai_copilot_ai_model_tokens_total', 'Total tokens used', ['provider', 'model'])
AI_MODEL_COSTS = Counter('ai_copilot_ai_model_costs_total', 'Total AI model costs', ['provider', 'model'])


def setup_metrics():
    """Initialize and setup all metrics."""
    try:
        logger.info("Setting up Prometheus metrics")
        
        # Initialize default values for gauges
        WS_CONNECTIONS.set(0)
        DB_CONNECTIONS.labels(database='postgres').set(0)
        DB_CONNECTIONS.labels(database='mongodb').set(0)
        DB_CONNECTIONS.labels(database='redis').set(0)
        DB_CONNECTIONS.labels(database='qdrant').set(0)
        
        # Set initial cache sizes
        CACHE_SIZE.labels(cache_type='redis').set(0)
        CACHE_SIZE.labels(cache_type='memory').set(0)
        
        # Set initial system metrics
        SYSTEM_MEMORY_USAGE.set(0)
        SYSTEM_CPU_USAGE.set(0)
        SYSTEM_DISK_USAGE.set(0)
        
        # Set initial user satisfaction
        USER_SATISFACTION.labels(user_type='end_user').set(0)
        USER_SATISFACTION.labels(user_type='admin').set(0)
        
        logger.info("Prometheus metrics setup completed successfully")
        
    except Exception as e:
        logger.error("Failed to setup metrics", error=str(e))
        raise


def record_chat_metrics(agent_type: str, model: str, response_time: float, success: bool = True):
    """Record chat-related metrics."""
    try:
        CHAT_REQUESTS.labels(agent_type=agent_type, model=model).inc()
        CHAT_RESPONSES.labels(agent_type=agent_type, model=model).observe(response_time)
        
        if not success:
            CHAT_ERRORS.labels(agent_type=agent_type, error_type='response_failure').inc()
            
    except Exception as e:
        logger.error("Failed to record chat metrics", error=str(e))


def record_agent_metrics(agent_type: str, action_type: str, execution_time: float, success: bool = True):
    """Record agent execution metrics."""
    try:
        AGENT_EXECUTIONS.labels(agent_type=agent_type, action_type=action_type).inc()
        AGENT_EXECUTION_TIME.labels(agent_type=agent_type, action_type=action_type).observe(execution_time)
        
        # Update success rate
        if success:
            # This is a simplified approach - in production, you might want more sophisticated success rate calculation
            pass
            
    except Exception as e:
        logger.error("Failed to record agent metrics", error=str(e))


def record_rag_metrics(collection: str, model: str, query_time: float, documents_found: int):
    """Record RAG system metrics."""
    try:
        RAG_QUERIES.labels(collection=collection, model=model).inc()
        RAG_QUERY_TIME.labels(collection=collection, model=model).observe(query_time)
        
    except Exception as e:
        logger.error("Failed to record RAG metrics", error=str(e))


def record_websocket_metrics(message_type: str, success: bool = True):
    """Record WebSocket metrics."""
    try:
        WS_MESSAGES.labels(message_type=message_type).inc()
        
        if not success:
            WS_ERRORS.labels(error_type='message_processing').inc()
            
    except Exception as e:
        logger.error("Failed to record WebSocket metrics", error=str(e))


def record_database_metrics(database: str, operation: str, query_time: float, success: bool = True):
    """Record database metrics."""
    try:
        DB_QUERY_TIME.labels(database=database, operation=operation).observe(query_time)
        
        if not success:
            DB_ERRORS.labels(database=database, error_type='query_failure').inc()
            
    except Exception as e:
        logger.error("Failed to record database metrics", error=str(e))


def record_cache_metrics(cache_type: str, hit: bool):
    """Record cache metrics."""
    try:
        if hit:
            CACHE_HITS.labels(cache_type=cache_type).inc()
        else:
            CACHE_MISSES.labels(cache_type=cache_type).inc()
            
    except Exception as e:
        logger.error("Failed to record cache metrics", error=str(e))


def record_task_metrics(task_type: str, processing_time: float, success: bool = True):
    """Record background task metrics."""
    try:
        TASK_PROCESSED.labels(task_type=task_type).inc()
        TASK_PROCESSING_TIME.labels(task_type=task_type).observe(processing_time)
        
        if not success:
            TASK_FAILURES.labels(task_type=task_type).inc()
            
    except Exception as e:
        logger.error("Failed to record task metrics", error=str(e))


def record_business_metrics(action_type: str, module: str, value: float = 0.0):
    """Record business action metrics."""
    try:
        BUSINESS_ACTIONS.labels(action_type=action_type, module=module).inc()
        
        if value > 0:
            BUSINESS_ACTION_VALUE.labels(action_type=action_type, module=module).observe(value)
            
    except Exception as e:
        logger.error("Failed to record business metrics", error=str(e))


def record_ai_model_metrics(provider: str, model: str, response_time: float, tokens_used: int, cost: float = 0.0):
    """Record AI model usage metrics."""
    try:
        AI_MODEL_REQUESTS.labels(provider=provider, model=model).inc()
        AI_MODEL_RESPONSE_TIME.labels(provider=provider, model=model).observe(response_time)
        AI_MODEL_TOKENS_USED.labels(provider=provider, model=model).inc(tokens_used)
        
        if cost > 0:
            AI_MODEL_COSTS.labels(provider=provider, model=model).inc(cost)
            
    except Exception as e:
        logger.error("Failed to record AI model metrics", error=str(e))


def update_system_metrics(memory_bytes: int, cpu_percentage: float, disk_bytes: int):
    """Update system resource metrics."""
    try:
        SYSTEM_MEMORY_USAGE.set(memory_bytes)
        SYSTEM_CPU_USAGE.set(cpu_percentage)
        SYSTEM_DISK_USAGE.set(disk_bytes)
        
    except Exception as e:
        logger.error("Failed to update system metrics", error=str(e))


def update_user_satisfaction(user_type: str, score: float):
    """Update user satisfaction metrics."""
    try:
        USER_SATISFACTION.labels(user_type=user_type).set(score)
        
    except Exception as e:
        logger.error("Failed to update user satisfaction metrics", error=str(e))


def get_metrics_summary():
    """Get a summary of current metrics."""
    try:
        return {
            "chat": {
                "total_requests": CHAT_REQUESTS._value.sum(),
                "total_errors": CHAT_ERRORS._value.sum(),
            },
            "agents": {
                "total_executions": AGENT_EXECUTIONS._value.sum(),
                "total_failures": TASK_FAILURES._value.sum(),
            },
            "websocket": {
                "active_connections": WS_CONNECTIONS._value.sum(),
                "total_messages": WS_MESSAGES._value.sum(),
            },
            "rag": {
                "total_queries": RAG_QUERIES._value.sum(),
                "total_documents": RAG_DOCUMENTS_INGESTED._value.sum(),
            },
            "system": {
                "memory_usage": SYSTEM_MEMORY_USAGE._value.sum(),
                "cpu_usage": SYSTEM_CPU_USAGE._value.sum(),
            }
        }
        
    except Exception as e:
        logger.error("Failed to get metrics summary", error=str(e))
        return {}
