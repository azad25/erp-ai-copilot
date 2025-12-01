"""
Agent Graph

Main LangGraph workflow for the ERP AI Copilot.
"""

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from app.langgraph.state import AgentState
from app.langgraph.nodes import agent_node, tool_node, should_continue
from app.langchain.tools import get_erp_tools


def create_agent_graph():
    """
    Create the main agent workflow graph
    
    Returns:
        Compiled LangGraph application
    """
    # Create graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    
    # Set entry point
    workflow.set_entry_point("agent")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )
    
    # Add edge from tools back to agent
    workflow.add_edge("tools", "agent")
    
    # Compile the graph with recursion limit to prevent infinite loops
    app = workflow.compile(
        checkpointer=None,  # No checkpointing for now
        interrupt_before=None,
        interrupt_after=None,
        debug=False
    )
    
    return app


# Create global instance
agent_graph = create_agent_graph()
