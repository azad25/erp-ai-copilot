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


async def _get_default_provider_settings():
    """Get default LLM provider settings from database."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from app.database.connection import get_db_session
        from app.models.llm_provider_settings import LLMProviderSettings
        from sqlalchemy import select
        
        # Use async for to iterate over the generator
        async for db in get_db_session():
            try:
                # Get default provider
                result = await db.execute(
                    select(LLMProviderSettings)
                    .where(LLMProviderSettings.is_enabled == True)
                    .where(LLMProviderSettings.is_default == True)
                )
                provider = result.scalar_one_or_none()
                
                if not provider:
                    logger.info("No default provider found, looking for highest priority enabled provider")
                    # Fallback to highest priority enabled provider
                    result = await db.execute(
                        select(LLMProviderSettings)
                        .where(LLMProviderSettings.is_enabled == True)
                        .order_by(LLMProviderSettings.priority.desc())
                    )
                    provider = result.scalar_one_or_none()
                
                if provider:
                    logger.info(f"Found provider in database: {provider.provider_name}, "
                               f"model: {provider.default_model}, "
                               f"has_api_key: {bool(provider.api_key)}")
                    return {
                        "provider": provider.provider_name,
                        "model": provider.default_model,
                        "api_key": provider.api_key,
                        "base_url": provider.base_url,
                        "config": provider.config or {}
                    }
                
                # No provider found in database
                break
            finally:
                # Session cleanup is handled by the generator
                pass
        
        # Final fallback to settings
        logger.warning("No provider found in database, falling back to settings")
        from app.config.settings import get_settings
        settings = get_settings()
        return {
            "provider": settings.llm.default_provider,
            "model": settings.llm.default_model,
            "api_key": None,
            "base_url": None,
            "config": {}
        }
    except Exception as e:
        # Fallback to settings on any error
        logger.error(f"Error loading provider settings from database: {e}", exc_info=True)
        from app.config.settings import get_settings
        settings = get_settings()
        return {
            "provider": settings.llm.default_provider,
            "model": settings.llm.default_model,
            "api_key": None,
            "base_url": None,
            "config": {}
        }


def agent_node(state: AgentState) -> AgentState:
    """
    Agent reasoning node - decides what to do next
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with agent's decision
    """
    # Get LLM with function calling - use configured provider from database
    import asyncio
    import os
    import logging
    
    logger = logging.getLogger(__name__)
    provider_settings = asyncio.run(_get_default_provider_settings())
    
    # Debug logging
    logger.info(f"Provider settings loaded: provider={provider_settings['provider']}, "
                f"model={provider_settings['model']}, "
                f"base_url={provider_settings.get('base_url')}, "
                f"has_api_key={bool(provider_settings['api_key'])}")
    
    # Set API key in environment if provided (must be done before get_llm call)
    if provider_settings["api_key"]:
        # Clean the API key (remove whitespace and quotes)
        clean_api_key = provider_settings["api_key"].strip().strip('"').strip("'")
        
        if provider_settings["provider"] == "huggingface":
            os.environ["HUGGINGFACEHUB_API_TOKEN"] = clean_api_key
            os.environ["HF_TOKEN"] = clean_api_key
            logger.info(f"Set HuggingFace API token in environment (length: {len(clean_api_key)})")
        elif provider_settings["provider"] == "openai":
            os.environ["OPENAI_API_KEY"] = clean_api_key
        elif provider_settings["provider"] == "anthropic":
            os.environ["ANTHROPIC_API_KEY"] = clean_api_key
        elif provider_settings["provider"] == "gemini":
            os.environ["GOOGLE_API_KEY"] = clean_api_key
        elif provider_settings["provider"] == "groq":
            os.environ["GROQ_API_KEY"] = clean_api_key
            logger.info(f"Set Groq API token in environment (length: {len(clean_api_key)})")
        
        # Update provider_settings with cleaned key
        provider_settings["api_key"] = clean_api_key
    else:
        logger.warning(f"No API key found for provider {provider_settings['provider']}")
    
    # Pass api_key and base_url directly to get_llm
    llm = get_llm(
        provider=provider_settings["provider"],
        model=provider_settings["model"],
        temperature=0.7,
        api_key=provider_settings["api_key"],
        base_url=provider_settings.get("base_url")
    )
    
    # Bind tools with auto tool choice - let the model decide when to use tools
    try:
        # Some providers (like Ollama) may not support tool binding
        if hasattr(llm, 'bind_tools'):
            llm_with_tools = llm.bind_tools(tools, tool_choice="auto")
            logger.info(f"Successfully bound {len(tools)} tools to LLM")
        else:
            logger.warning(f"Provider {provider_settings['provider']} does not support tool binding, using LLM without tools")
            llm_with_tools = llm
    except Exception as e:
        # If binding tools fails, fall back to no tools
        logger.warning(f"Failed to bind tools: {str(e)}, using LLM without tools")
        llm_with_tools = llm
    
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
    
    # Check if there are tool calls
    has_tool_calls = hasattr(last_message, "tool_calls") and last_message.tool_calls and len(last_message.tool_calls) > 0
    
    # If there are tool calls, continue to tools
    if has_tool_calls:
        return "tools"
    
    # Otherwise, end immediately - don't loop
    return "end"
