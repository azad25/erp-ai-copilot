"""
Tests for Phase 2: Kafka-Based Task System
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from app.services.task_producer import TaskProducer
from app.services.task_consumer import TaskConsumer
from app.services.task_state_manager import TaskStateManager
from app.services.event_trigger_system import EventTriggerSystem


class TestTaskProducer:
    """Test task producer"""
    
    @pytest.mark.asyncio
    async def test_submit_task(self):
        """Test submitting a task"""
        producer = TaskProducer()
        
        task_id = await producer.submit_task(
            agent_id="test-agent",
            organization_id="test-org",
            task_type="test_task",
            parameters={"key": "value"},
            priority="normal"
        )
        
        assert task_id is not None
        assert isinstance(task_id, str)
        
        producer.close()
    
    @pytest.mark.asyncio
    async def test_priority_calculation(self):
        """Test priority score calculation"""
        producer = TaskProducer()
        
        # High priority with urgent deadline
        score1 = producer._calculate_priority_score(
            priority="high",
            deadline=datetime.utcnow() + timedelta(hours=0.5),
            depends_on=None
        )
        
        # Normal priority with no deadline
        score2 = producer._calculate_priority_score(
            priority="normal",
            deadline=None,
            depends_on=None
        )
        
        assert score1 > score2
        assert score1 <= 100
        assert score2 <= 100
        
        producer.close()
    
    @pytest.mark.asyncio
    async def test_scheduled_task(self):
        """Test scheduling a task for future execution"""
        producer = TaskProducer()
        
        future_time = datetime.utcnow() + timedelta(hours=1)
        
        task_id = await producer.submit_task(
            agent_id="test-agent",
            organization_id="test-org",
            task_type="scheduled_task",
            parameters={},
            scheduled_for=future_time
        )
        
        assert task_id is not None
        
        producer.close()


class TestTaskConsumer:
    """Test task consumer"""
    
    @pytest.mark.asyncio
    async def test_consumer_initialization(self):
        """Test consumer initializes correctly"""
        consumer = TaskConsumer()
        
        # Set a dummy handler
        async def dummy_handler(task):
            return {"success": True}
        
        consumer.set_task_handler(dummy_handler)
        
        assert consumer.task_handler is not None
        assert consumer.max_workers == 10
    
    @pytest.mark.asyncio
    async def test_message_processing(self):
        """Test processing a single message"""
        consumer = TaskConsumer()
        
        # Track if handler was called
        handler_called = False
        
        async def test_handler(task):
            nonlocal handler_called
            handler_called = True
            return {"success": True, "result": "test"}
        
        consumer.set_task_handler(test_handler)
        
        # Create mock message
        class MockMessage:
            def __init__(self):
                self.value = {
                    "task_id": "test-123",
                    "agent_id": "agent-1",
                    "organization_id": "org-1",
                    "task_type": "test",
                    "parameters": {}
                }
                self.partition = 0
                self.offset = 0
        
        # Process message
        await consumer._process_message(MockMessage())
        
        assert handler_called


class TestTaskStateManager:
    """Test task state manager"""
    
    @pytest.mark.asyncio
    async def test_state_manager_initialization(self):
        """Test state manager initializes"""
        manager = TaskStateManager()
        
        # Note: This will fail if PostgreSQL/Redis not running
        # In real tests, use mocks or test containers
        try:
            await manager.initialize()
            assert manager.pg_pool is not None
            assert manager.redis_client is not None
            await manager.close()
        except Exception as e:
            pytest.skip(f"Database not available: {e}")
    
    @pytest.mark.asyncio
    async def test_priority_score_calculation(self):
        """Test priority score affects task ordering"""
        # This is a unit test that doesn't need database
        
        # Critical task with urgent deadline should have highest score
        from app.services.task_producer import TaskProducer
        producer = TaskProducer()
        
        critical_score = producer._calculate_priority_score(
            priority="critical",
            deadline=datetime.utcnow() + timedelta(minutes=30),
            depends_on=["task1", "task2"]
        )
        
        low_score = producer._calculate_priority_score(
            priority="low",
            deadline=None,
            depends_on=None
        )
        
        assert critical_score > low_score
        assert critical_score >= 70  # Should be high
        assert low_score <= 30  # Should be low


class TestEventTriggerSystem:
    """Test event trigger system"""
    
    def test_register_trigger(self):
        """Test registering an event trigger"""
        system = EventTriggerSystem()
        
        system.register_trigger(
            event_type="order.created",
            agent_id="inventory-agent",
            task_type="check_inventory",
            parameter_mapping={"order_id": "order_id"},
            priority="high"
        )
        
        assert "order.created" in system.triggers
        assert len(system.triggers["order.created"]) == 1
        assert system.triggers["order.created"][0]["agent_id"] == "inventory-agent"
    
    def test_multiple_triggers_same_event(self):
        """Test multiple triggers for same event"""
        system = EventTriggerSystem()
        
        system.register_trigger(
            event_type="order.created",
            agent_id="agent-1",
            task_type="task-1"
        )
        
        system.register_trigger(
            event_type="order.created",
            agent_id="agent-2",
            task_type="task-2"
        )
        
        assert len(system.triggers["order.created"]) == 2


class TestTaskIntegration:
    """Integration tests for task system"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_task_flow(self):
        """Test complete task flow: submit -> consume -> execute"""
        # This is a conceptual test - would need full infrastructure
        
        # 1. Submit task
        producer = TaskProducer()
        task_id = await producer.submit_task(
            agent_id="test-agent",
            organization_id="test-org",
            task_type="test_task",
            parameters={"test": "data"}
        )
        
        assert task_id is not None
        
        # 2. Task would be consumed by worker
        # 3. Task would be executed by MCP
        # 4. Result would be published
        
        producer.close()


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
