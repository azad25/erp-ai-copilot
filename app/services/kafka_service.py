"""
Kafka Service for Event-Driven Background Tasks

Handles async task processing, notifications, and event streaming.
"""

import json
import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaError

from app.core.config import settings

logger = logging.getLogger(__name__)


class KafkaService:
    """Kafka service for event-driven architecture"""
    
    def __init__(self):
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumers: Dict[str, AIOKafkaConsumer] = {}
        self.is_initialized = False
        self.bootstrap_servers = getattr(settings, 'KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        
    async def initialize(self):
        """Initialize Kafka producer"""
        if self.is_initialized:
            return
            
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                compression_type='gzip',
                acks='all',
                retries=3
            )
            await self.producer.start()
            self.is_initialized = True
            logger.info(f"Kafka producer initialized: {self.bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            # Don't fail the app if Kafka is unavailable
            self.is_initialized = False

    async def send_event(self, topic: str, event_type: str, data: Dict[str, Any], 
                        key: Optional[str] = None) -> bool:
        """
        Send event to Kafka topic
        
        Args:
            topic: Kafka topic name
            event_type: Type of event (task_created, task_completed, etc.)
            data: Event data
            key: Optional partition key
            
        Returns:
            True if sent successfully
        """
        if not self.is_initialized:
            logger.warning("Kafka not initialized, skipping event")
            return False
            
        try:
            message = {
                'event_type': event_type,
                'timestamp': datetime.utcnow().isoformat(),
                'data': data
            }
            
            await self.producer.send_and_wait(
                topic,
                value=message,
                key=key.encode('utf-8') if key else None
            )
            logger.debug(f"Sent event to {topic}: {event_type}")
            return True
        except KafkaError as e:
            logger.error(f"Kafka error sending event: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending event to Kafka: {e}")
            return False

    async def create_consumer(self, topic: str, group_id: str, 
                             handler: Callable) -> None:
        """
        Create and start a Kafka consumer
        
        Args:
            topic: Topic to consume from
            group_id: Consumer group ID
            handler: Async function to handle messages
        """
        try:
            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True
            )
            
            await consumer.start()
            self.consumers[topic] = consumer
            logger.info(f"Started Kafka consumer for topic: {topic}")
            
            # Start consuming in background
            asyncio.create_task(self._consume_messages(consumer, handler))
            
        except Exception as e:
            logger.error(f"Failed to create Kafka consumer: {e}")

    async def _consume_messages(self, consumer: AIOKafkaConsumer, 
                               handler: Callable) -> None:
        """Internal method to consume messages"""
        try:
            async for message in consumer:
                try:
                    await handler(message.value)
                except Exception as e:
                    logger.error(f"Error handling Kafka message: {e}")
        except Exception as e:
            logger.error(f"Error in Kafka consumer loop: {e}")

    async def send_task_event(self, task_id: str, event_type: str, 
                             task_data: Dict[str, Any]) -> bool:
        """Send background task event"""
        return await self.send_event(
            topic='ai-copilot-tasks',
            event_type=event_type,
            data={
                'task_id': task_id,
                'task_type': task_data.get('task_type'),
                'user_id': task_data.get('user_id'),
                'status': task_data.get('status'),
                'result': task_data.get('result'),
                'error': task_data.get('error')
            },
            key=task_id
        )

    async def send_notification_event(self, user_id: str, notification: Dict[str, Any]) -> bool:
        """Send user notification event"""
        return await self.send_event(
            topic='ai-copilot-notifications',
            event_type='notification',
            data={
                'user_id': user_id,
                'notification': notification
            },
            key=user_id
        )

    async def close(self):
        """Close Kafka connections"""
        try:
            if self.producer:
                await self.producer.stop()
                logger.info("Kafka producer stopped")
                
            for topic, consumer in self.consumers.items():
                await consumer.stop()
                logger.info(f"Kafka consumer stopped for topic: {topic}")
                
            self.is_initialized = False
        except Exception as e:
            logger.error(f"Error closing Kafka connections: {e}")


# Global instance
kafka_service = KafkaService()
