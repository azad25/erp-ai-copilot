"""
Event Trigger System

Listens to business events and triggers agent tasks automatically.
Supports event matching, agent selection, and trigger configuration.
"""

from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import asyncio
import json
import structlog
from kafka import KafkaConsumer
from kafka.errors import KafkaError

logger = structlog.get_logger(__name__)


class EventTriggerSystem:
    """
    Event-driven task triggering system
    
    Listens to business events (order created, inventory low, etc.)
    and automatically creates agent tasks based on configured triggers.
    """
    
    def __init__(self, bootstrap_servers: List[str] = None):
        """
        Initialize event trigger system
        
        Args:
            bootstrap_servers: List of Kafka broker addresses
        """
        self.bootstrap_servers = bootstrap_servers or ['localhost:9092']
        self.consumer = None
        self.running = False
        self.triggers: Dict[str, List[Dict]] = {}  # event_type -> list of triggers
        self.task_producer = None
    
    def register_trigger(
        self,
        event_type: str,
        agent_id: str,
        task_type: str,
        condition: Optional[Callable] = None,
        parameter_mapping: Optional[Dict[str, str]] = None,
        priority: str = "normal"
    ):
        """
        Register an event trigger
        
        Args:
            event_type: Type of event to listen for
            agent_id: Agent to trigger
            task_type: Type of task to create
            condition: Optional condition function to filter events
            parameter_mapping: Map event fields to task parameters
            priority: Task priority
        """
        if event_type not in self.triggers:
            self.triggers[event_type] = []
        
        trigger = {
            "agent_id": agent_id,
            "task_type": task_type,
            "condition": condition,
            "parameter_mapping": parameter_mapping or {},
            "priority": priority
        }
        
        self.triggers[event_type].append(trigger)
        
        logger.info(
            "Trigger registered",
            event_type=event_type,
            agent_id=agent_id,
            task_type=task_type
        )
    
    async def load_triggers_from_database(self):
        """
        Load trigger configurations from database
        
        Loads all active triggers for agents with event-based scheduling.
        """
        # TODO: Implement database loading
        # For now, register some example triggers
        
        # Example: Order created trigger
        self.register_trigger(
            event_type="order.created",
            agent_id="inventory-agent",
            task_type="check_inventory",
            parameter_mapping={
                "order_id": "order_id",
                "items": "items"
            },
            priority="high"
        )
        
        # Example: Inventory low trigger
        self.register_trigger(
            event_type="inventory.low",
            agent_id="inventory-agent",
            task_type="restock_alert",
            parameter_mapping={
                "product_id": "product_id",
                "current_stock": "current_stock",
                "threshold": "threshold"
            },
            priority="critical"
        )
        
        logger.info("Triggers loaded from database", count=len(self.triggers))
    
    async def start_listening(self):
        """
        Start listening to business events
        
        Subscribes to event topics and processes events.
        """
        from app.services.task_producer import get_task_producer
        self.task_producer = get_task_producer()
        
        # Load triggers
        await self.load_triggers_from_database()
        
        # Initialize Kafka consumer
        try:
            self.consumer = KafkaConsumer(
                'agent.events.triggers',
                'business.events.*',  # Subscribe to all business events
                bootstrap_servers=self.bootstrap_servers,
                group_id='event-trigger-system',
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True
            )
            logger.info("Event trigger system initialized")
        except Exception as e:
            logger.error("Failed to initialize event consumer", error=str(e))
            raise
        
        self.running = True
        
        logger.info("Starting event listening...")
        
        try:
            while self.running:
                # Poll for events
                message_batch = self.consumer.poll(timeout_ms=1000)
                
                if not message_batch:
                    await asyncio.sleep(0.1)
                    continue
                
                # Process events
                for topic_partition, messages in message_batch.items():
                    for message in messages:
                        await self._process_event(message)
        
        except Exception as e:
            logger.error("Event listening error", error=str(e))
            raise
        finally:
            if self.consumer:
                self.consumer.close()
    
    async def _process_event(self, message):
        """
        Process a business event
        
        Args:
            message: Kafka message containing event data
        """
        event = message.value
        event_type = event.get('event_type')
        
        logger.info(
            "Processing event",
            event_type=event_type,
            event_id=event.get('event_id')
        )
        
        # Find matching triggers
        matching_triggers = self.triggers.get(event_type, [])
        
        if not matching_triggers:
            logger.debug("No triggers for event type", event_type=event_type)
            return
        
        # Execute each matching trigger
        for trigger in matching_triggers:
            try:
                # Check condition if specified
                if trigger['condition']:
                    if not trigger['condition'](event):
                        logger.debug(
                            "Trigger condition not met",
                            event_type=event_type,
                            agent_id=trigger['agent_id']
                        )
                        continue
                
                # Create task
                await self._create_triggered_task(event, trigger)
                
            except Exception as e:
                logger.error(
                    "Failed to execute trigger",
                    event_type=event_type,
                    agent_id=trigger['agent_id'],
                    error=str(e)
                )
    
    async def _create_triggered_task(self, event: Dict, trigger: Dict):
        """
        Create task from event trigger
        
        Args:
            event: Event data
            trigger: Trigger configuration
        """
        # Map event data to task parameters
        parameters = {}
        for task_param, event_field in trigger['parameter_mapping'].items():
            if event_field in event:
                parameters[task_param] = event[event_field]
        
        # Add event context
        context = {
            "triggered_by_event": True,
            "event_type": event.get('event_type'),
            "event_id": event.get('event_id'),
            "event_timestamp": event.get('timestamp')
        }
        
        # Submit task
        task_id = await self.task_producer.submit_task(
            agent_id=trigger['agent_id'],
            organization_id=event.get('organization_id'),
            task_type=trigger['task_type'],
            parameters=parameters,
            context=context,
            priority=trigger['priority'],
            task_name=f"Auto: {trigger['task_type']} (triggered by {event.get('event_type')})",
            description=f"Automatically triggered by {event.get('event_type')} event"
        )
        
        logger.info(
            "Task created from event trigger",
            task_id=task_id,
            event_type=event.get('event_type'),
            agent_id=trigger['agent_id'],
            task_type=trigger['task_type']
        )
    
    def stop(self):
        """Stop listening to events"""
        self.running = False
        logger.info("Event trigger system stopped")


# Global instance
_event_trigger_system: Optional[EventTriggerSystem] = None


def get_event_trigger_system() -> EventTriggerSystem:
    """Get or create event trigger system instance"""
    global _event_trigger_system
    
    if _event_trigger_system is None:
        _event_trigger_system = EventTriggerSystem()
    
    return _event_trigger_system
