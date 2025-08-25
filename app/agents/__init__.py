"""
AI Copilot Agents Package

This package contains all agent implementations for the ERP AI Copilot system.
Provides a multi-agent architecture with specialized agents for different domains.
"""

from .base_agent import BaseAgent, AgentRequest, AgentResponse
from .query_agent import QueryAgent
from .action_agent import ActionAgent
from .analytics_agent import AnalyticsAgent
from .scheduler_agent import SchedulerAgent
from .compliance_agent import ComplianceAgent
from .help_agent import HelpAgent
from .master_agent import MasterAgent
from .agent_orchestrator import AgentOrchestrator

__all__ = [
    "BaseAgent",
    "AgentRequest", 
    "AgentResponse",
    "QueryAgent",
    "ActionAgent",
    "AnalyticsAgent",
    "SchedulerAgent",
    "ComplianceAgent",
    "HelpAgent",
    "MasterAgent",
    "AgentOrchestrator"
]