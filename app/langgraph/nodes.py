"""
LangGraph Nodes

Node functions for the agent workflow.
"""

from typing import Literal
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langgraph.prebuilt import ToolNode

from app.langchain.llm_factory import get_llm
from app.langchain.tools import get_erp_tools
from app.langchain.prompts import get_agent_prompt
from app.langgraph.state import AgentState


# Get tools and create tool node
tools = get_erp_tools()
tool_node = ToolNode(tools)


def agent_node(state: AgentState) -> AgentState:
    """
    Agent reasoning node - decides what to do next
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with agent's decision
    """
    # Get LLM with function calling
    llm = get_llm(provider="gemini", temperature=0.7)
    llm_with_tools = llm.bind_tools(tools)
    
    # Get prompt
    prompt = get_agent_prompt()
    
    # Format messages for the agent
    messages = state["messages"]
    
    # Invoke LLM with tools
    response = llm_with_tools.invoke(
        prompt.format_messages(
            input=messages[-1].content if messages else "",
            chat_history=messages[:-1] if len(messages) > 1 else [],
            agent_scratchpad=[]
        )
    )
    
    # Return updated state
    return {
        **state,
        "messages": [response]
    }


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """
    Determine if we should continue to tools or end
    
    Args:
        state: Current agent state
        
    Returns:
        Next node to visit
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    # If there are tool calls, continue to tools
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    # Otherwise, end
    return "end"
