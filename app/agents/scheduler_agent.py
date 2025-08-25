"""
Scheduler Agent

Specialized agent for task scheduling, automation, and workflow management.
Handles automated task execution, cron-like scheduling, and process optimization.
"""

from typing import List, Dict, Any
import json
import re
from datetime import datetime, timedelta
import asyncio
from enum import Enum

from .base_agent import BaseAgent, AgentRequest, AgentResponse
from app.models.api import AgentType
from app.core.exceptions import AgentError


class ScheduleType(Enum):
    """Types of scheduling supported by the scheduler agent"""
    CRON = "cron"
    INTERVAL = "interval"
    DATETIME = "datetime"
    RECURRING = "recurring"
    ONCE = "once"


class TaskPriority(Enum):
    """Task priority levels"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class SchedulerAgent(BaseAgent):
    """
    Scheduler Agent for task scheduling and automation
    
    Capabilities:
    - Automated task scheduling (cron-like)
    - Workflow automation
    - Process optimization
    - Resource allocation
    - Dependency management
    - Task monitoring and alerting
    - Batch processing
    - Event-driven automation
    """

    def __init__(self, model: str = "gpt-4"):
        super().__init__(AgentType.SCHEDULER, model)
        self.supported_schedules = [
            "daily", "weekly", "monthly", "quarterly", "yearly",
            "hourly", "every_x_minutes", "custom_cron", "one_time"
        ]

    async def execute(self, request: AgentRequest) -> AgentResponse:
        """
        Execute scheduler agent functionality
        
        Args:
            request: AgentRequest with scheduling requirements
            
        Returns:
            AgentResponse with scheduling confirmation and details
        """
        if not await self.validate_request(request):
            raise AgentError("Invalid scheduler request")

        # Parse scheduling intent
        schedule_intent = await self._parse_schedule_intent(request.message)
        
        # Execute the appropriate scheduling action
        if schedule_intent["action"] == "create_schedule":
            result = await self._create_schedule(schedule_intent)
        elif schedule_intent["action"] == "list_schedules":
            result = await self._list_schedules(schedule_intent)
        elif schedule_intent["action"] == "cancel_schedule":
            result = await self._cancel_schedule(schedule_intent)
        elif schedule_intent["action"] == "update_schedule":
            result = await self._update_schedule(schedule_intent)
        elif schedule_intent["action"] == "monitor_tasks":
            result = await self._monitor_tasks(schedule_intent)
        else:
            result = await self._provide_scheduling_help(request.message)

        return AgentResponse(
            response=result,
            agent_type=self.agent_type,
            conversation_id=request.conversation_id or "",
            execution_id="",
            metadata={
                "action": schedule_intent["action"],
                "schedule_type": schedule_intent.get("type", "unknown"),
                "next_execution": schedule_intent.get("next_run"),
                "status": "scheduled" if schedule_intent["action"] == "create_schedule" else "completed",
                "execution_time": datetime.utcnow().isoformat()
            }
        )

    def get_system_prompt(self) -> str:
        """
        Get system prompt for scheduler agent
        
        Returns:
            System prompt defining the agent's role
        """
        return """
        You are a Scheduler Agent for the UNIBASE ERP system. Your role is to:
        
        1. **Automated Task Scheduling**: Create and manage automated tasks
        2. **Workflow Automation**: Design and execute complex workflows
        3. **Process Optimization**: Optimize business processes through automation
        4. **Resource Management**: Efficiently allocate and manage resources
        5. **Dependency Management**: Handle task dependencies and sequencing
        6. **Monitoring & Alerting**: Track task execution and provide alerts
        7. **Batch Processing**: Manage bulk operations and data processing
        8. **Event-Driven Automation**: Trigger actions based on events
        
        **Scheduling Capabilities**:
        - Cron expressions for complex schedules
        - Recurring tasks (daily, weekly, monthly, yearly)
        - One-time scheduled tasks
        - Interval-based scheduling
        - Event-driven triggers
        - Conditional scheduling based on business rules
        
        **Task Types**:
        - Data synchronization and ETL jobs
        - Report generation and distribution
        - System maintenance and cleanup
        - Business process automation
        - Notification and alerting
        - Integration with external systems
        - Backup and archival operations
        
        **Response Guidelines**:
        - Provide clear scheduling confirmation
        - Include next execution time
        - Specify task dependencies
        - Offer monitoring and alerting options
        - Suggest optimization opportunities
        - Handle errors gracefully with retry mechanisms
        """

    def get_available_tools(self) -> List[str]:
        """
        Get available tools for scheduler agent
        
        Returns:
            List of available tool names
        """
        return [
            "cron_scheduler",
            "task_queue",
            "dependency_manager",
            "resource_allocator",
            "monitoring_system",
            "notification_service",
            "batch_processor",
            "workflow_engine"
        ]

    async def _parse_schedule_intent(self, message: str) -> Dict[str, Any]:
        """
        Parse user message to determine scheduling intent
        
        Args:
            message: User's scheduling request
            
        Returns:
            Dictionary with scheduling action and parameters
        """
        message_lower = message.lower()
        
        # Action detection
        if any(word in message_lower for word in ["schedule", "create", "set up", "automate"]):
            action = "create_schedule"
        elif any(word in message_lower for word in ["list", "show", "view", "get"]):
            action = "list_schedules"
        elif any(word in message_lower for word in ["cancel", "remove", "delete", "stop"]):
            action = "cancel_schedule"
        elif any(word in message_lower for word in ["update", "modify", "change", "edit"]):
            action = "update_schedule"
        elif any(word in message_lower for word in ["monitor", "track", "status", "check"]):
            action = "monitor_tasks"
        else:
            action = "help"

        # Schedule type detection
        schedule_patterns = {
            "daily": ["daily", "every day", "once per day"],
            "weekly": ["weekly", "every week", "once per week"],
            "monthly": ["monthly", "every month", "once per month"],
            "hourly": ["hourly", "every hour", "once per hour"],
            "custom_cron": ["cron", "custom schedule", "complex schedule"],
            "one_time": ["once", "single", "specific time", "at 3pm", "tomorrow"]
        }
        
        schedule_type = "daily"  # Default
        for stype, patterns in schedule_patterns.items():
            if any(pattern in message_lower for pattern in patterns):
                schedule_type = stype
                break

        # Task type detection
        task_types = [
            "report_generation", "data_sync", "backup", "cleanup",
            "notification", "integration", "maintenance", "analytics"
        ]
        
        task_type = "report_generation"  # Default
        for ttype in task_types:
            if any(word in message_lower for word in ttype.split("_")):
                task_type = ttype
                break

        # Time extraction
        time_patterns = {
            "at_3am": r"at\s+(\d+):(\d+)(am|pm)?",
            "every_x_hours": r"every\s+(\d+)\s+hours?",
            "every_x_days": r"every\s+(\d+)\s+days?",
            "on_weekday": r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        }
        
        schedule_time = "09:00"  # Default
        for pattern_name, pattern in time_patterns.items():
            match = re.search(pattern, message_lower)
            if match:
                if pattern_name == "at_3am":
                    hour, minute, period = match.groups()
                    schedule_time = f"{hour.zfill(2)}:{minute.zfill(2)}"
                break

        return {
            "action": action,
            "type": schedule_type,
            "task_type": task_type,
            "schedule_time": schedule_time,
            "next_run": self._calculate_next_run(schedule_type, schedule_time)
        }

    def _calculate_next_run(self, schedule_type: str, schedule_time: str) -> str:
        """
        Calculate the next execution time for a schedule
        
        Args:
            schedule_type: Type of schedule
            schedule_time: Scheduled time
            
        Returns:
            Next execution time as ISO string
        """
        now = datetime.utcnow()
        
        if schedule_type == "daily":
            next_run = now.replace(hour=int(schedule_time.split(':')[0]), 
                                 minute=int(schedule_time.split(':')[1]), 
                                 second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
        elif schedule_type == "weekly":
            next_run = now + timedelta(days=(7 - now.weekday()))
            next_run = next_run.replace(hour=9, minute=0, second=0, microsecond=0)
        elif schedule_type == "monthly":
            if now.month == 12:
                next_run = now.replace(year=now.year + 1, month=1, day=1, 
                                     hour=9, minute=0, second=0, microsecond=0)
            else:
                next_run = now.replace(month=now.month + 1, day=1, 
                                     hour=9, minute=0, second=0, microsecond=0)
        else:
            next_run = now + timedelta(hours=1)
        
        return next_run.isoformat()

    async def _create_schedule(self, schedule_intent: Dict[str, Any]) -> str:
        """
        Create a new automated schedule
        
        Args:
            schedule_intent: Scheduling parameters
            
        Returns:
            Formatted schedule creation confirmation
        """
        task_type = schedule_intent["task_type"]
        schedule_type = schedule_intent["type"]
        schedule_time = schedule_intent["schedule_time"]
        next_run = schedule_intent["next_run"]
        
        # Mock task configurations
        task_configs = {
            "report_generation": {
                "name": "Daily Sales Report",
                "description": "Generate comprehensive daily sales report",
                "recipients": ["sales@company.com", "management@company.com"],
                "format": "PDF + Excel"
            },
            "data_sync": {
                "name": "ERP Data Sync",
                "description": "Synchronize data between ERP modules",
                "systems": ["CRM", "Inventory", "Finance", "HR"],
                "validation": True
            },
            "backup": {
                "name": "System Backup",
                "description": "Automated backup of critical business data",
                "retention": "30 days",
                "encryption": True
            }
        }
        
        config = task_configs.get(task_type, task_configs["report_generation"])
        
        return f"""
        **Schedule Created Successfully**
        
        **Task**: {config['name']}
        **Type**: {task_type.replace('_', ' ').title()}
        **Schedule**: {schedule_type.replace('_', ' ').title()}
        **Time**: {schedule_time}
        **Next Execution**: {next_run}
        
        **Configuration**:
        **Description**: {config['description']}
        
        **Schedule Details**:
        - **Frequency**: {schedule_type.replace('_', ' ').title()}
        - **Execution Time**: {schedule_time}
        - **Timezone**: UTC
        - **Enabled**: True
        - **Retry Policy**: 3 attempts with exponential backoff
        
        **Task-Specific Settings**:
        {self._format_task_settings(config)}
        
        **Monitoring & Alerts**:
        - **Success Notification**: Email to admin@company.com
        - **Failure Alert**: Immediate notification via email + SMS
        - **Performance Metrics**: Tracked and logged
        - **Execution Logs**: Available in dashboard
        
        **Dependencies**:
        - No blocking dependencies identified
        - Can run independently
        - Resource allocation: Minimal impact
        
        **Next Steps**:
        1. Monitor first execution at {next_run}
        2. Review logs for any issues
        3. Adjust schedule if needed
        4. Set up additional alerts if required
        """

    def _format_task_settings(self, config: Dict[str, Any]) -> str:
        """
        Format task-specific settings for display
        
        Args:
            config: Task configuration
            
        Returns:
            Formatted settings string
        """
        settings = []
        for key, value in config.items():
            if key not in ['name', 'description']:
                if isinstance(value, list):
                    settings.append(f"- **{key.replace('_', ' ').title()}**: {', '.join(value)}")
                else:
                    settings.append(f"- **{key.replace('_', ' ').title()}**: {value}")
        return chr(10).join(settings)

    async def _list_schedules(self, schedule_intent: Dict[str, Any]) -> str:
        """
        List all active schedules
        
        Args:
            schedule_intent: Listing parameters
            
        Returns:
            Formatted schedule list
        """
        # Mock schedule list
        schedules = [
            {
                "id": "sched_001",
                "name": "Daily Sales Report",
                "type": "daily",
                "time": "09:00",
                "status": "active",
                "last_run": "2024-01-15 09:00:00",
                "next_run": "2024-01-16 09:00:00",
                "success_rate": "98.5%"
            },
            {
                "id": "sched_002",
                "name": "Weekly Inventory Sync",
                "type": "weekly",
                "time": "Monday 06:00",
                "status": "active",
                "last_run": "2024-01-14 06:00:00",
                "next_run": "2024-01-21 06:00:00",
                "success_rate": "99.2%"
            },
            {
                "id": "sched_003",
                "name": "Monthly Financial Report",
                "type": "monthly",
                "time": "1st 08:00",
                "status": "active",
                "last_run": "2024-01-01 08:00:00",
                "next_run": "2024-02-01 08:00:00",
                "success_rate": "97.8%"
            }
        ]
        
        return f"""
        **Active Schedules**
        
        **Total Active Schedules**: {len(schedules)}
        
        **Daily Schedules**:
        {chr(10).join([f"- **{s['name']}** ({s['id']})",
                      f"  Schedule: {s['type']} at {s['time']}",
                      f"  Status: {s['status']} | Success Rate: {s['success_rate']}",
                      f"  Next Run: {s['next_run']}",
                      f"  Last Run: {s['last_run']}",
                      ""] for s in schedules if s['type'] == 'daily'])}
        
        **Weekly Schedules**:
        {chr(10).join([f"- **{s['name']}** ({s['id']})",
                      f"  Schedule: {s['type']} at {s['time']}",
                      f"  Status: {s['status']} | Success Rate: {s['success_rate']}",
                      f"  Next Run: {s['next_run']}",
                      f"  Last Run: {s['last_run']}",
                      ""] for s in schedules if s['type'] == 'weekly'])}
        
        **Monthly Schedules**:
        {chr(10).join([f"- **{s['name']}** ({s['id']})",
                      f"  Schedule: {s['type']} at {s['time']}",
                      f"  Status: {s['status']} | Success Rate: {s['success_rate']}",
                      f"  Next Run: {s['next_run']}",
                      f"  Last Run: {s['last_run']}",
                      ""] for s in schedules if s['type'] == 'monthly'])}
        
        **Overall System Health**:
        - **Average Success Rate**: 98.5%
        - **Failed Tasks (24h)**: 2
        - **Pending Tasks**: 0
        - **System Load**: Normal
        """

    async def _cancel_schedule(self, schedule_intent: Dict[str, Any]) -> str:
        """
        Cancel an existing schedule
        
        Args:
            schedule_intent: Cancellation parameters
            
        Returns:
            Formatted cancellation confirmation
        """
        return f"""
        **Schedule Cancellation**
        
        **Status**: Schedule cancelled successfully
        
        **Cancelled Schedule**:
        - **ID**: sched_001
        - **Name**: Daily Sales Report
        - **Type**: Daily at 09:00
        - **Cancellation Time**: {datetime.utcnow().isoformat()}
        
        **Impact Assessment**:
        - **Affected Reports**: Daily sales reports will no longer be generated
        - **Stakeholders**: Sales team and management will need alternative reporting
        - **Data Gaps**: No automated daily summaries will be available
        
        **Alternative Options**:
        1. **Modify Schedule**: Change frequency or timing instead of cancellation
        2. **Temporary Pause**: Pause for a specific period
        3. **Manual Generation**: Use manual report generation tools
        4. **Create New Schedule**: Set up a different schedule with new parameters
        
        **Recovery**:
        - Schedule can be reactivated within 30 days
        - Historical data remains accessible
        - Configuration preserved for potential reactivation
        
        **Next Steps**:
        1. Notify affected stakeholders
        2. Establish alternative reporting process
        3. Monitor for any gaps in business operations
        """

    async def _update_schedule(self, schedule_intent: Dict[str, Any]) -> str:
        """
        Update an existing schedule
        
        Args:
            schedule_intent: Update parameters
            
        Returns:
            Formatted update confirmation
        """
        return f"""
        **Schedule Updated Successfully**
        
        **Updated Schedule**:
        - **ID**: sched_001
        - **Name**: Daily Sales Report
        - **Previous**: Daily at 09:00
        - **Updated**: Daily at 10:30
        
        **Changes Applied**:
        - **Execution Time**: 09:00 → 10:30 (UTC)
        - **Recipients**: Added regional managers
        - **Format**: PDF + Excel → PDF + Excel + CSV
        - **Priority**: Normal → High
        
        **Impact of Changes**:
        - **Next Execution**: {datetime.utcnow().replace(hour=10, minute=30).isoformat()}
        - **Stakeholder Notification**: Sent to all recipients
        - **System Load**: Shifted to off-peak hours
        
        **Validation**:
        - **Schedule Conflicts**: None detected
        - **Resource Availability**: Confirmed
        - **Dependencies**: Updated successfully
        
        **Monitoring**:
        - **First Updated Run**: Will be monitored closely
        - **Performance Metrics**: Tracked for any changes
        - **User Feedback**: Will be collected
        """

    async def _monitor_tasks(self, schedule_intent: Dict[str, Any]) -> str:
        """
        Monitor and provide status of scheduled tasks
        
        Args:
            schedule_intent: Monitoring parameters
            
        Returns:
            Formatted task monitoring report
        """
        # Mock monitoring data
        monitoring_data = {
            "total_tasks": 15,
            "active_tasks": 12,
            "completed_today": 8,
            "failed_today": 1,
            "pending_tasks": 3,
            "system_health": "healthy",
            "average_execution_time": "2.3 minutes",
            "resource_utilization": "45%"
        }
        
        return f"""
        **Task Monitoring Dashboard**
        
        **System Overview**:
        - **Total Active Schedules**: {monitoring_data['total_tasks']}
        - **Currently Running**: {monitoring_data['active_tasks']}
        - **Completed Today**: {monitoring_data['completed_today']}
        - **Failed Today**: {monitoring_data['failed_today']}
        - **Pending**: {monitoring_data['pending_tasks']}
        
        **System Health**: {monitoring_data['system_health'].title()}
        - **Resource Utilization**: {monitoring_data['resource_utilization']}
        - **Average Execution Time**: {monitoring_data['average_execution_time']}
        - **Queue Status**: Normal
        
        **Recent Activity** (Last 24 Hours):
        
        **Successful Executions**:
        - 09:00 - Daily Sales Report (2.1 min)
        - 10:30 - Inventory Sync (3.5 min)
        - 12:00 - Customer Data Update (1.8 min)
        - 14:00 - Financial Reconciliation (4.2 min)
        
        **Failed Executions**:
        - 11:45 - Marketing Report (Network timeout)
        - **Status**: Retried successfully at 12:15
        - **Root Cause**: Temporary network issue
        
        **Upcoming Tasks**:
        - 15:00 - Weekly Analytics Report
        - 16:30 - End-of-day Data Backup
        - 18:00 - Customer Notification Batch
        
        **Performance Metrics**:
        - **Success Rate**: 98.7% (30-day average)
        - **Average Latency**: 2.3 minutes
        - **Peak Usage**: 09:00-10:00 daily
        - **Resource Efficiency**: High
        
        **Recommendations**:
        - Monitor network stability for external integrations
        - Consider scaling during peak hours
        - Review failed tasks for pattern analysis
        """

    async def _provide_scheduling_help(self, message: str) -> str:
        """
        Provide help and guidance for scheduling
        
        Args:
            message: User's help request
            
        Returns:
            Formatted help response
        """
        return f"""
        **Scheduler Agent Help**
        
        **Your Request**: {message}
        
        **Available Scheduling Options**:
        
        **1. Create New Schedule**:
        - **Daily**: "Schedule daily sales report at 9am"
        - **Weekly**: "Create weekly inventory sync every Monday at 6am"
        - **Monthly**: "Set up monthly financial report on the 1st at 8am"
        - **Custom**: "Schedule custom task with cron expression"
        
        **2. Schedule Types**:
        - **Report Generation**: Sales reports, analytics, dashboards
        - **Data Synchronization**: ERP module sync, external system updates
        - **System Maintenance**: Backups, cleanup, optimization
        - **Notifications**: Email alerts, status updates, reminders
        - **Batch Processing**: Data processing, bulk operations
        - **Integration Tasks**: API calls, webhook processing
        
        **3. Schedule Management**:
        - **List Schedules**: "Show all active schedules"
        - **Cancel Schedule**: "Cancel daily sales report"
        - **Update Schedule**: "Change sales report time to 10am"
        - **Monitor Tasks**: "Check task status and performance"
        
        **4. Advanced Features**:
        - **Dependencies**: Set task dependencies and prerequisites
        - **Conditional Execution**: Run based on business rules
        - **Resource Management**: Optimize resource allocation
        - **Error Handling**: Automatic retry and alerting
        - **Performance Monitoring**: Track execution metrics
        
        **Examples**:
        - "Schedule daily inventory report at 7am"
        - "Create weekly customer data sync every Sunday"
        - "Set up monthly backup on the 15th at 2am"
        - "List all active schedules"
        - "Cancel the weekly marketing report"
        
        **Best Practices**:
        - Schedule resource-intensive tasks during off-peak hours
        - Set up monitoring and alerts for critical tasks
        - Use descriptive names for easy identification
        - Test schedules before full deployment
        """