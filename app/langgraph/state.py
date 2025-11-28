"""
LangGraph State

State management for agent workflows.
"""

from typing import TypedDict, Annotated, Sequence, Dict, Any
from langchain_core.messages import BaseMessage
import operator


class AgentState(TypedDict):
    """State for the agent graph"""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    conversation_id: str
    user_id: str
    organization_id: str
    user_role: str
    context: Dict[str, Any]
