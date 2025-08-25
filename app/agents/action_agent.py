"""
Action Agent

Specialized agent for executing CRUD operations and workflows across ERP modules.
Handles data modifications, process automation, and task execution.
"""

from typing import List, Dict, Any
import json
from datetime import datetime

from .base_agent import BaseAgent, AgentRequest, AgentResponse
from app.models.api import AgentType
from app.core.exceptions import AgentError


class ActionAgent(BaseAgent):
    """
    Action Agent for CRUD operations and workflow execution
    
    Capabilities:
    - Create, read, update, delete operations
    - Workflow automation
    - Process execution
    - Data validation and integrity
    - Transaction management
    """

    def __init__(self, model: str = "gpt-4"):
        super().__init__(AgentType.ACTION, model)
        self.supported_actions = [
            "create", "update", "delete", "approve", "reject", 
            "assign", "schedule", "notify", "export", "import"
        ]

    async def execute(self, request: AgentRequest) -> AgentResponse:
        """
        Execute action agent functionality
        
        Args:
            request: AgentRequest with action details
            
        Returns:
            AgentResponse with action results
        """
        if not await self.validate_request(request):
            raise AgentError("Invalid action request")

        # Parse action intent
        action_intent = await self._parse_action_intent(request.message)
        
        # Validate and execute action
        validation_result = await self._validate_action(action_intent)
        if not validation_result["valid"]:
            return AgentResponse(
                response=f"Action validation failed: {validation_result['error']}",
                agent_type=self.agent_type,
                conversation_id=request.conversation_id or "",
                execution_id="",
                metadata={"action": action_intent["action"], "status": "validation_failed"}
            )

        # Execute the action
        try:
            result = await self._execute_action(action_intent, request.context)
            
            return AgentResponse(
                response=result["message"],
                agent_type=self.agent_type,
                conversation_id=request.conversation_id or "",
                execution_id="",
                metadata={
                    "action": action_intent["action"],
                    "entity_type": action_intent["entity_type"],
                    "entity_id": action_intent.get("entity_id"),
                    "changes": result.get("changes", {}),
                    "status": "completed",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
        except Exception as e:
            return AgentResponse(
                response=f"Action execution failed: {str(e)}",
                agent_type=self.agent_type,
                conversation_id=request.conversation_id or "",
                execution_id="",
                metadata={"action": action_intent["action"], "status": "failed", "error": str(e)}
            )

    def get_system_prompt(self) -> str:
        """
        Get system prompt for action agent
        
        Returns:
            System prompt defining the agent's role
        """
        return """
        You are an Action Agent for the UNIBASE ERP system. Your role is to:
        
        1. **CRUD Operations**: Execute create, read, update, and delete operations
        2. **Workflow Automation**: Automate business processes and workflows
        3. **Infrastructure Management**: Execute system commands and manage services
        4. **Data Validation**: Ensure data integrity before making changes
        5. **Transaction Management**: Handle complex multi-step transactions
        6. **Audit Trail**: Maintain complete audit logs for all actions
        
        **Available Actions**:
        - Create new records (customers, products, orders, etc.)
        - Update existing records with validation
        - Delete records with proper authorization
        - Approve or reject requests
        - Assign tasks and responsibilities
        - Schedule events and reminders
        - Send notifications to stakeholders
        - Export and import data
        - Execute system commands (restart services, check status, etc.)
        - Manage infrastructure (Docker, Kubernetes, databases)
        - Monitor application health and logs
        
        **Security Requirements**:
        - Validate user permissions before executing actions
        - Confirm destructive operations with user
        - Maintain data integrity and referential integrity
        - Log all changes for audit purposes
        - Implement proper authorization checks
        - Restrict dangerous commands to authorized users only
        
        **Command Execution**:
        - You can execute system commands for infrastructure management
        - Available command categories: root commands, infrastructure commands, application commands
        - Always validate commands for safety before execution
        - Provide clear output and status information
        - Use appropriate tools for service management (Docker, Kubernetes, etc.)
        
        **Response Guidelines**:
        - Always confirm successful actions
        - Provide clear error messages for failures
        - Include relevant details about changes made
        - Suggest next steps when appropriate
        - Include command output and status for infrastructure commands
        """

    def get_available_tools(self) -> List[str]:
        """
        Get available tools for action agent
        
        Returns:
            List of available tool names
        """
        return [
            "data_validator",
            "permission_checker",
            "audit_logger",
            "transaction_manager",
            "notification_service",
            "workflow_engine",
            "data_mapper",
            "backup_service",
            "command_executor",
            "infrastructure_manager",
            "application_manager"
        ]

    async def _parse_action_intent(self, message: str) -> Dict[str, Any]:
        """
        Parse user message to determine action intent
        
        Args:
            message: User's action request
            
        Returns:
            Dictionary with action details
        """
        message_lower = message.lower()
        
        # Action type detection
        action_patterns = {
            "create": ["create", "add", "new", "register", "insert"],
            "update": ["update", "edit", "modify", "change", "correct"],
            "delete": ["delete", "remove", "cancel", "terminate"],
            "approve": ["approve", "accept", "authorize", "confirm"],
            "reject": ["reject", "decline", "deny", "refuse"],
            "assign": ["assign", "delegate", "transfer", "hand over"],
            "schedule": ["schedule", "book", "reserve", "plan"],
            "notify": ["notify", "send", "alert", "inform"]
        }
        
        action_type = "unknown"
        for action, patterns in action_patterns.items():
            if any(pattern in message_lower for pattern in patterns):
                action_type = action
                break
        
        # Entity type detection
        entity_patterns = {
            "customer": ["customer", "client", "buyer"],
            "product": ["product", "item", "goods", "merchandise"],
            "order": ["order", "purchase", "sale", "transaction"],
            "employee": ["employee", "staff", "worker", "team member"],
            "invoice": ["invoice", "bill", "payment", "charge"],
            "inventory": ["inventory", "stock", "warehouse"],
            "supplier": ["supplier", "vendor", "provider"]
        }
        
        entity_type = "unknown"
        for entity, patterns in entity_patterns.items():
            if any(pattern in message_lower for pattern in patterns):
                entity_type = entity
                break
        
        # Extract entity ID from context or message
        entity_id = None
        context = {}  # This would come from request.context in real implementation
        
        return {
            "action": action_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "original_message": message
        }

    async def _validate_action(self, action_intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the action before execution
        
        Args:
            action_intent: Parsed action details
            
        Returns:
            Validation result
        """
        # Basic validation
        if action_intent["action"] == "unknown":
            return {"valid": False, "error": "Could not determine action type"}
            
        if action_intent["entity_type"] == "unknown":
            return {"valid": False, "error": "Could not determine entity type"}
            
        # Permission validation would happen here
        # For now, assume valid
        return {"valid": True}

    async def _execute_action(self, action_intent: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the validated action
        
        Args:
            action_intent: Action details
            context: Execution context
            
        Returns:
            Action execution result
        """
        action = action_intent["action"]
        entity_type = action_intent["entity_type"]
        
        # Mock implementation - would integrate with actual ERP services
        if action == "create":
            return await self._create_entity(entity_type, action_intent, context)
        elif action == "update":
            return await self._update_entity(entity_type, action_intent, context)
        elif action == "delete":
            return await self._delete_entity(entity_type, action_intent, context)
        elif action == "approve":
            return await self._approve_request(entity_type, action_intent, context)
        elif action == "schedule":
            return await self._schedule_event(entity_type, action_intent, context)
        else:
            return {"message": f"Action '{action}' on '{entity_type}' is not yet implemented", "status": "pending"}

    async def _create_entity(self, entity_type: str, action_intent: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new entity
        
        Args:
            entity_type: Type of entity to create
            action_intent: Action details
            context: Execution context
            
        Returns:
            Creation result
        """
        # Generate mock entity ID
        import uuid
        entity_id = str(uuid.uuid4())[:8]
        
        return {
            "message": f"Successfully created new {entity_type} with ID: {entity_id}",
            "entity_id": entity_id,
            "changes": {
                "entity_type": entity_type,
                "created_at": datetime.utcnow().isoformat(),
                "created_by": context.get("user_id", "system")
            },
            "next_steps": [
                "Configure additional details",
                "Set up permissions",
                "Add to relevant workflows"
            ]
        }

    async def _update_entity(self, entity_type: str, action_intent: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing entity
        
        Args:
            entity_type: Type of entity to update
            action_intent: Action details
            context: Execution context
            
        Returns:
            Update result
        """
        entity_id = action_intent.get("entity_id", "ENT-001")
        
        return {
            "message": f"Successfully updated {entity_type} {entity_id}",
            "entity_id": entity_id,
            "changes": {
                "updated_at": datetime.utcnow().isoformat(),
                "updated_by": context.get("user_id", "system"),
                "fields_updated": ["status", "details", "metadata"]
            },
            "audit_trail": f"Change logged for compliance review"
        }

    async def _delete_entity(self, entity_type: str, action_intent: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete an entity (soft delete with confirmation)
        
        Args:
            entity_type: Type of entity to delete
            action_intent: Action details
            context: Execution context
            
        Returns:
            Deletion result
        """
        entity_id = action_intent.get("entity_id", "ENT-001")
        
        return {
            "message": f"{entity_type} {entity_id} has been marked for deletion",
            "entity_id": entity_id,
            "changes": {
                "status": "deleted",
                "deleted_at": datetime.utcnow().isoformat(),
                "deleted_by": context.get("user_id", "system")
            },
            "confirmation_required": "Contact administrator to permanently delete",
            "backup_created": "Data archived for recovery"
        }

    async def _approve_request(self, entity_type: str, action_intent: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Approve a pending request
        
        Args:
            entity_type: Type of request to approve
            action_intent: Action details
            context: Execution context
            
        Returns:
            Approval result
        """
        request_id = action_intent.get("entity_id", "REQ-001")
        
        return {
            "message": f"Request {request_id} has been approved",
            "request_id": request_id,
            "changes": {
                "status": "approved",
                "approved_at": datetime.utcnow().isoformat(),
                "approved_by": context.get("user_id", "system")
            },
            "notifications_sent": [
                "Requester notified of approval",
                "Relevant teams notified",
                "Workflow triggered for next steps"
            ]
        }

    async def _schedule_event(self, entity_type: str, action_intent: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Schedule an event or appointment
        
        Args:
            entity_type: Type of event to schedule
            action_intent: Action details
            context: Execution context
            
        Returns:
            Scheduling result
        """
        event_id = "EVT-001"  # Would be generated in real implementation
        
        return {
            "message": f"Event scheduled successfully",
            "event_id": event_id,
            "changes": {
                "scheduled_at": datetime.utcnow().isoformat(),
                "scheduled_by": context.get("user_id", "system"),
                "entity_type": entity_type
            },
            "calendar_integration": "Added to team calendar",
            "notifications": "Participants will be notified"
        }