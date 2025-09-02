"""
Kafka Integration Service

Handles Kafka message processing for scheduled ERP data processing,
event streaming, and real-time data synchronization across services.
"""

from typing import Dict, List, Any, Optional, Callable
import asyncio
import json
import logging
from datetime import datetime, timedelta
from uuid import uuid4
from dataclasses import dataclass, field
import aiokafka
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError

from app.config.settings import get_settings
from app.services.memory_service import memory_service
from app.services.api_gateway_client import api_gateway_client
from app.database.connection import get_mongodb, get_redis

logger = logging.getLogger(__name__)


@dataclass
class KafkaMessage:
    """Kafka message structure"""
    topic: str
    key: str
    value: Dict[str, Any]
    headers: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ProcessingTask:
    """Data processing task"""
    task_id: str
    task_type: str
    source_service: str
    data: Dict[str, Any]
    priority: int = 5
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.utcnow)


class KafkaIntegrationService:
    """
    Kafka Integration Service for ERP Data Processing
    
    Features:
    - Real-time event processing from ERP services
    - Scheduled data synchronization
    - Log aggregation and analysis
    - Cache invalidation events
    - Authentication service events
    - AI training data collection
    """
    
    def __init__(self):
        settings = get_settings()
        self.bootstrap_servers = settings.kafka.brokers_list[0] if settings.kafka.brokers_list else "localhost:9092"
        self.consumer_group = "ai-copilot-group"
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumers: Dict[str, AIOKafkaConsumer] = {}
        self.message_handlers: Dict[str, Callable] = {}
        self.processing_queue: List[ProcessingTask] = []
        self.is_running = False
        
        # Initialize message handlers
        self._setup_message_handlers()
        
    def _setup_message_handlers(self):
        """Setup message handlers for different topics"""
        self.message_handlers = {
            "erp.sales.events": self._handle_sales_events,
            "erp.inventory.events": self._handle_inventory_events,
            "erp.finance.events": self._handle_finance_events,
            "erp.auth.events": self._handle_auth_events,
            "erp.logs.aggregated": self._handle_log_events,
            "erp.cache.invalidation": self._handle_cache_events,
            "erp.system.health": self._handle_health_events,
            "erp.data.sync": self._handle_data_sync_events
        }
    
    async def initialize(self):
        """Initialize Kafka producer and consumers"""
        try:
            # Initialize producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                compression_type="gzip",
                batch_size=16384,
                linger_ms=10
            )
            await self.producer.start()
            
            # Initialize consumers for each topic
            for topic in self.message_handlers.keys():
                consumer = AIOKafkaConsumer(
                    topic,
                    bootstrap_servers=self.bootstrap_servers,
                    group_id=self.consumer_group,
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    key_deserializer=lambda k: k.decode('utf-8') if k else None,
                    auto_offset_reset='latest',
                    enable_auto_commit=True,
                    auto_commit_interval_ms=1000
                )
                await consumer.start()
                self.consumers[topic] = consumer
            
            logger.info("Kafka integration service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Kafka service: {e}")
            raise
    
    async def start_processing(self):
        """Start Kafka message processing"""
        if self.is_running:
            return
            
        self.is_running = True
        
        # Start consumer tasks
        consumer_tasks = []
        for topic, consumer in self.consumers.items():
            task = asyncio.create_task(self._consume_messages(topic, consumer))
            consumer_tasks.append(task)
        
        # Start processing queue task
        queue_task = asyncio.create_task(self._process_queue())
        
        # Start scheduled tasks
        scheduler_task = asyncio.create_task(self._run_scheduled_tasks())
        
        logger.info("Kafka message processing started")
        
        try:
            await asyncio.gather(*consumer_tasks, queue_task, scheduler_task)
        except Exception as e:
            logger.error(f"Error in Kafka processing: {e}")
        finally:
            self.is_running = False
    
    async def _consume_messages(self, topic: str, consumer: AIOKafkaConsumer):
        """Consume messages from a specific topic"""
        handler = self.message_handlers.get(topic)
        if not handler:
            logger.warning(f"No handler found for topic: {topic}")
            return
            
        try:
            async for message in consumer:
                try:
                    kafka_msg = KafkaMessage(
                        topic=message.topic,
                        key=message.key,
                        value=message.value,
                        headers={k: v.decode('utf-8') for k, v in message.headers},
                        timestamp=datetime.fromtimestamp(message.timestamp / 1000)
                    )
                    
                    await handler(kafka_msg)
                    
                except Exception as e:
                    logger.error(f"Error processing message from {topic}: {e}")
                    
        except Exception as e:
            logger.error(f"Error consuming from topic {topic}: {e}")
    
    async def _handle_sales_events(self, message: KafkaMessage):
        """Handle sales service events"""
        event_type = message.value.get("event_type")
        data = message.value.get("data", {})
        
        if event_type == "invoice_created":
            await self._process_invoice_data(data)
        elif event_type == "customer_updated":
            await self._process_customer_data(data)
        elif event_type == "sales_report_generated":
            await self._store_sales_insights(data)
            
        logger.debug(f"Processed sales event: {event_type}")
    
    async def _handle_inventory_events(self, message: KafkaMessage):
        """Handle inventory service events"""
        event_type = message.value.get("event_type")
        data = message.value.get("data", {})
        
        if event_type == "stock_updated":
            await self._process_stock_data(data)
        elif event_type == "product_created":
            await self._process_product_data(data)
        elif event_type == "low_stock_alert":
            await self._create_stock_alert(data)
            
        logger.debug(f"Processed inventory event: {event_type}")
    
    async def _handle_finance_events(self, message: KafkaMessage):
        """Handle finance service events"""
        event_type = message.value.get("event_type")
        data = message.value.get("data", {})
        
        if event_type == "transaction_created":
            await self._process_transaction_data(data)
        elif event_type == "budget_updated":
            await self._process_budget_data(data)
        elif event_type == "financial_report_generated":
            await self._store_financial_insights(data)
            
        logger.debug(f"Processed finance event: {event_type}")
    
    async def _handle_auth_events(self, message: KafkaMessage):
        """Handle authentication service events"""
        event_type = message.value.get("event_type")
        data = message.value.get("data", {})
        
        if event_type == "user_login":
            await self._track_user_activity(data)
        elif event_type == "permission_changed":
            await self._update_user_permissions(data)
        elif event_type == "session_expired":
            await self._cleanup_user_session(data)
            
        logger.debug(f"Processed auth event: {event_type}")
    
    async def _handle_log_events(self, message: KafkaMessage):
        """Handle aggregated log events"""
        log_data = message.value.get("logs", [])
        
        for log_entry in log_data:
            await self._analyze_log_entry(log_entry)
            
        logger.debug(f"Processed {len(log_data)} log entries")
    
    async def _handle_cache_events(self, message: KafkaMessage):
        """Handle cache invalidation events"""
        cache_keys = message.value.get("keys", [])
        service = message.value.get("service")
        
        # Invalidate related AI context
        redis = await get_redis()
        for key in cache_keys:
            if key.startswith("user_context:"):
                await redis.delete(key)
                
        logger.debug(f"Processed cache invalidation for {len(cache_keys)} keys")
    
    async def _handle_health_events(self, message: KafkaMessage):
        """Handle system health events"""
        service_name = message.value.get("service")
        health_status = message.value.get("status")
        metrics = message.value.get("metrics", {})
        
        # Store health metrics for AI analysis
        await self._store_health_metrics(service_name, health_status, metrics)
        
        logger.debug(f"Processed health event for {service_name}: {health_status}")
    
    async def _handle_data_sync_events(self, message: KafkaMessage):
        """Handle data synchronization events"""
        sync_type = message.value.get("sync_type")
        data = message.value.get("data", {})
        
        # Queue for processing
        task = ProcessingTask(
            task_id=str(uuid4()),
            task_type=f"sync_{sync_type}",
            source_service=message.value.get("source", "unknown"),
            data=data,
            priority=3
        )
        
        self.processing_queue.append(task)
        logger.debug(f"Queued data sync task: {sync_type}")
    
    async def _process_queue(self):
        """Process queued tasks"""
        while self.is_running:
            try:
                if self.processing_queue:
                    # Sort by priority (lower number = higher priority)
                    self.processing_queue.sort(key=lambda x: x.priority)
                    
                    task = self.processing_queue.pop(0)
                    await self._execute_processing_task(task)
                else:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in processing queue: {e}")
                await asyncio.sleep(5)
    
    async def _execute_processing_task(self, task: ProcessingTask):
        """Execute a processing task"""
        try:
            if task.task_type.startswith("sync_"):
                await self._execute_sync_task(task)
            elif task.task_type == "analyze_logs":
                await self._execute_log_analysis(task)
            elif task.task_type == "update_knowledge":
                await self._execute_knowledge_update(task)
            else:
                logger.warning(f"Unknown task type: {task.task_type}")
                
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            
            # Retry logic
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                self.processing_queue.append(task)
                logger.info(f"Retrying task {task.task_id} (attempt {task.retry_count})")
    
    async def _execute_sync_task(self, task: ProcessingTask):
        """Execute data synchronization task"""
        sync_type = task.task_type.replace("sync_", "")
        
        if sync_type == "customer_data":
            await self._sync_customer_data(task.data)
        elif sync_type == "product_data":
            await self._sync_product_data(task.data)
        elif sync_type == "financial_data":
            await self._sync_financial_data(task.data)
        
        logger.info(f"Completed sync task: {sync_type}")
    
    async def _run_scheduled_tasks(self):
        """Run scheduled data processing tasks"""
        while self.is_running:
            try:
                current_hour = datetime.utcnow().hour
                
                # Run different tasks at different hours
                if current_hour == 1:  # 1 AM - Daily data sync
                    await self._schedule_daily_sync()
                elif current_hour == 6:  # 6 AM - Generate insights
                    await self._schedule_insight_generation()
                elif current_hour % 4 == 0:  # Every 4 hours - Health check
                    await self._schedule_health_checks()
                
                # Sleep for an hour
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error in scheduled tasks: {e}")
                await asyncio.sleep(300)  # Sleep 5 minutes on error
    
    async def _schedule_daily_sync(self):
        """Schedule daily data synchronization"""
        services = ["sales", "inventory", "finance", "crm", "hrm"]
        
        for service in services:
            task = ProcessingTask(
                task_id=str(uuid4()),
                task_type=f"sync_{service}_data",
                source_service=service,
                data={"sync_date": datetime.utcnow().date().isoformat()},
                priority=2
            )
            self.processing_queue.append(task)
        
        logger.info("Scheduled daily data sync tasks")
    
    async def _schedule_insight_generation(self):
        """Schedule AI insight generation"""
        task = ProcessingTask(
            task_id=str(uuid4()),
            task_type="generate_insights",
            source_service="ai-copilot",
            data={"date": datetime.utcnow().date().isoformat()},
            priority=4
        )
        self.processing_queue.append(task)
        
        logger.info("Scheduled insight generation task")
    
    async def _schedule_health_checks(self):
        """Schedule system health checks"""
        task = ProcessingTask(
            task_id=str(uuid4()),
            task_type="health_check",
            source_service="system",
            data={"timestamp": datetime.utcnow().isoformat()},
            priority=5
        )
        self.processing_queue.append(task)
        
        logger.info("Scheduled health check task")
    
    async def publish_event(
        self,
        topic: str,
        event_type: str,
        data: Dict[str, Any],
        key: Optional[str] = None
    ):
        """Publish an event to Kafka"""
        if not self.producer:
            await self.initialize()
            
        message = {
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "ai-copilot"
        }
        
        try:
            await self.producer.send(topic, value=message, key=key)
            logger.debug(f"Published event {event_type} to {topic}")
            
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
    
    async def _process_invoice_data(self, data: Dict[str, Any]):
        """Process invoice data for AI insights"""
        # Store invoice insights in memory service
        await memory_service.store_memory(
            user_id="system",
            organization_id=data.get("organization_id", "default"),
            memory_type="invoice_insight",
            content=f"Invoice {data.get('invoice_id')} created for {data.get('amount', 0)}",
            context=data,
            importance=0.6
        )
    
    async def _process_stock_data(self, data: Dict[str, Any]):
        """Process stock data for inventory insights"""
        product_id = data.get("product_id")
        new_quantity = data.get("quantity", 0)
        
        if new_quantity < data.get("reorder_level", 10):
            # Create low stock alert
            await self.publish_event(
                "erp.alerts.inventory",
                "low_stock_alert",
                {
                    "product_id": product_id,
                    "current_quantity": new_quantity,
                    "reorder_level": data.get("reorder_level", 10)
                }
            )
    
    async def _store_health_metrics(
        self,
        service_name: str,
        status: str,
        metrics: Dict[str, Any]
    ):
        """Store system health metrics"""
        mongodb = await get_mongodb()
        
        health_doc = {
            "service_name": service_name,
            "status": status,
            "metrics": metrics,
            "timestamp": datetime.utcnow()
        }
        
        await mongodb.system_health.insert_one(health_doc)
    
    async def close(self):
        """Close Kafka connections"""
        self.is_running = False
        
        if self.producer:
            await self.producer.stop()
            
        for consumer in self.consumers.values():
            await consumer.stop()
        
        logger.info("Kafka integration service closed")


# Global Kafka integration service instance
kafka_service = KafkaIntegrationService()
