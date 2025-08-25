"""Kafka Integration for RAG Engine

This module provides Kafka integration for asynchronous document processing
and retrieval operations in the RAG engine.
"""

import json
from typing import Dict, List, Optional, Any, Union, Callable
import asyncio
from datetime import datetime

import structlog
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from pydantic import BaseModel, ValidationError

from app.config.settings import get_settings
from app.rag.models import Document, SearchQuery

logger = structlog.get_logger(__name__)
settings = get_settings()


class KafkaMessage(BaseModel):
    """Base model for Kafka messages."""
    message_id: str
    message_type: str
    timestamp: datetime
    payload: Dict[str, Any]


class KafkaManager:
    """Manager for Kafka integration with RAG engine."""
    
    # Topic names
    DOCUMENT_INGESTION_TOPIC = "rag-document-ingestion"
    DOCUMENT_SEARCH_TOPIC = "rag-document-search"
    DOCUMENT_UPDATE_TOPIC = "rag-document-update"
    DOCUMENT_DELETE_TOPIC = "rag-document-delete"
    
    def __init__(self):
        """Initialize the Kafka manager."""
        self.bootstrap_servers = settings.kafka.bootstrap_servers
        self.producer = None
        self.consumers = {}
        self.handlers = {}
        self.running = False
    
    async def initialize(self):
        """Initialize Kafka producer and consumers."""
        try:
            # Initialize producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            await self.producer.start()
            
            logger.info("Kafka producer initialized", bootstrap_servers=self.bootstrap_servers)
            return True
            
        except Exception as e:
            logger.error(
                "Failed to initialize Kafka producer",
                bootstrap_servers=self.bootstrap_servers,
                error=str(e)
            )
            return False
    
    async def shutdown(self):
        """Shutdown Kafka producer and consumers."""
        self.running = False
        
        # Stop all consumers
        for topic, consumer in self.consumers.items():
            try:
                await consumer.stop()
                logger.info("Kafka consumer stopped", topic=topic)
            except Exception as e:
                logger.error("Error stopping Kafka consumer", topic=topic, error=str(e))
        
        # Stop producer
        if self.producer:
            try:
                await self.producer.stop()
                logger.info("Kafka producer stopped")
            except Exception as e:
                logger.error("Error stopping Kafka producer", error=str(e))
    
    async def send_document_ingestion_message(self, document: Document) -> bool:
        """Send document ingestion message to Kafka.
        
        Args:
            document: Document to ingest
            
        Returns:
            Success status
        """
        message = KafkaMessage(
            message_id=document.id or str(datetime.utcnow().timestamp()),
            message_type="document_ingestion",
            timestamp=datetime.utcnow(),
            payload=document.dict()
        )
        
        return await self._send_message(self.DOCUMENT_INGESTION_TOPIC, message.dict())
    
    async def send_document_search_message(self, query: SearchQuery) -> bool:
        """Send document search message to Kafka.
        
        Args:
            query: Search query
            
        Returns:
            Success status
        """
        message = KafkaMessage(
            message_id=str(datetime.utcnow().timestamp()),
            message_type="document_search",
            timestamp=datetime.utcnow(),
            payload=query.dict()
        )
        
        return await self._send_message(self.DOCUMENT_SEARCH_TOPIC, message.dict())
    
    async def send_document_update_message(self, document: Document) -> bool:
        """Send document update message to Kafka.
        
        Args:
            document: Document to update
            
        Returns:
            Success status
        """
        message = KafkaMessage(
            message_id=document.id,
            message_type="document_update",
            timestamp=datetime.utcnow(),
            payload=document.dict()
        )
        
        return await self._send_message(self.DOCUMENT_UPDATE_TOPIC, message.dict())
    
    async def send_document_delete_message(self, document_id: str) -> bool:
        """Send document delete message to Kafka.
        
        Args:
            document_id: ID of document to delete
            
        Returns:
            Success status
        """
        message = KafkaMessage(
            message_id=document_id,
            message_type="document_delete",
            timestamp=datetime.utcnow(),
            payload={"document_id": document_id}
        )
        
        return await self._send_message(self.DOCUMENT_DELETE_TOPIC, message.dict())
    
    async def _send_message(self, topic: str, message: Dict[str, Any]) -> bool:
        """Send message to Kafka topic.
        
        Args:
            topic: Kafka topic
            message: Message to send
            
        Returns:
            Success status
        """
        if not self.producer:
            logger.error("Kafka producer not initialized")
            return False
        
        try:
            await self.producer.send_and_wait(topic, message)
            logger.debug(
                "Message sent to Kafka",
                topic=topic,
                message_id=message.get("message_id"),
                message_type=message.get("message_type")
            )
            return True
            
        except Exception as e:
            logger.error(
                "Failed to send message to Kafka",
                topic=topic,
                message_id=message.get("message_id"),
                error=str(e)
            )
            return False
    
    async def register_consumer(self, topic: str, handler: Callable):
        """Register a consumer for a Kafka topic.
        
        Args:
            topic: Kafka topic to consume
            handler: Callback function to handle messages
        """
        self.handlers[topic] = handler
        
        # Create consumer if not exists
        if topic not in self.consumers:
            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=f"rag-engine-{topic}",
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            self.consumers[topic] = consumer
            
            # Start consumer
            await consumer.start()
            logger.info("Kafka consumer started", topic=topic)
            
            # Start consumer task
            asyncio.create_task(self._consume_messages(topic))
    
    async def _consume_messages(self, topic: str):
        """Consume messages from Kafka topic.
        
        Args:
            topic: Kafka topic to consume
        """
        consumer = self.consumers.get(topic)
        handler = self.handlers.get(topic)
        
        if not consumer or not handler:
            logger.error("Consumer or handler not found", topic=topic)
            return
        
        self.running = True
        
        try:
            async for message in consumer:
                if not self.running:
                    break
                    
                try:
                    # Process message
                    value = message.value
                    logger.debug(
                        "Received message from Kafka",
                        topic=topic,
                        message_id=value.get("message_id"),
                        message_type=value.get("message_type")
                    )
                    
                    # Call handler
                    await handler(value)
                    
                except ValidationError as e:
                    logger.error(
                        "Invalid message format",
                        topic=topic,
                        error=str(e)
                    )
                except Exception as e:
                    logger.error(
                        "Error processing Kafka message",
                        topic=topic,
                        error=str(e)
                    )
                    
        except Exception as e:
            logger.error(
                "Error consuming Kafka messages",
                topic=topic,
                error=str(e)
            )
        finally:
            if self.running:
                # Restart consumer if still running
                logger.info("Restarting Kafka consumer", topic=topic)
                asyncio.create_task(self._consume_messages(topic))