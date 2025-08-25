"""
Celery configuration for background tasks in the AI Copilot service.
"""
import os
from celery import Celery
from app.config.settings import get_settings

settings = get_settings()

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('CELERY_CONFIG_MODULE', 'app.core.celery_config')

# Create the Celery app
celery_app = Celery(
    'ai_copilot',
    broker=f"redis://:{settings.redis.password}@{settings.redis.host}:{settings.redis.port}/{settings.redis.db}",
    backend=f"redis://:{settings.redis.password}@{settings.redis.host}:{settings.redis.port}/{settings.redis.db}",
    include=[
        'app.tasks.rag_tasks',
        'app.tasks.agent_tasks',
        'app.tasks.analytics_tasks',
        'app.tasks.maintenance_tasks',
    ]
)

# Configure Celery
celery_app.conf.update(
    # Task serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task routing
    task_routes={
        'app.tasks.rag_tasks.*': {'queue': 'rag'},
        'app.tasks.agent_tasks.*': {'queue': 'agents'},
        'app.tasks.analytics_tasks.*': {'queue': 'analytics'},
        'app.tasks.maintenance_tasks.*': {'queue': 'maintenance'},
    },
    
    # Task execution
    task_always_eager=False,
    task_eager_propagates=True,
    task_ignore_result=False,
    task_store_eager_result=True,
    
    # Worker configuration
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    
    # Task timeouts
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,        # 10 minutes
    
    # Result backend
    result_expires=3600,        # 1 hour
    result_backend_transport_options={
        'master_name': 'mymaster',
        'visibility_timeout': 3600,
    },
    
    # Beat scheduler
    beat_schedule={
        'cleanup-old-conversations': {
            'task': 'app.tasks.maintenance_tasks.cleanup_old_conversations',
            'schedule': 86400.0,  # Daily
        },
        'update-rag-embeddings': {
            'task': 'app.tasks.rag_tasks.update_rag_embeddings',
            'schedule': 3600.0,   # Hourly
        },
        'generate-analytics': {
            'task': 'app.tasks.analytics_tasks.generate_daily_analytics',
            'schedule': 86400.0,  # Daily
        },
        'health-check': {
            'task': 'app.tasks.maintenance_tasks.health_check',
            'schedule': 300.0,    # Every 5 minutes
        },
    },
    
    # Task compression
    task_compression='gzip',
    result_compression='gzip',
    
    # Security
    security_key=settings.security.jwt_secret,
    security_certificate=None,
    security_cert_store=None,
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    event_queue_expires=60,
    event_queue_ttl=5,
    
    # Error handling
    task_annotations={
        '*': {
            'rate_limit': '100/m',
            'retry': True,
            'retry_policy': {
                'max_retries': 3,
                'interval_start': 0,
                'interval_step': 0.2,
                'interval_max': 0.2,
            }
        }
    },
    
    # Logging
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s] [%(task_name)s(%(task_id)s)] %(message)s',
)

# Auto-discover tasks
celery_app.autodiscover_tasks()

if __name__ == '__main__':
    celery_app.start()
