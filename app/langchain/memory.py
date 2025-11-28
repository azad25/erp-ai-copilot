"""
Memory Management

LangChain memory for conversation history.
"""

from typing import Optional
from langchain.memory import ConversationBufferMemory, ConversationSummaryMemory
from langchain.memory.chat_memory import BaseChatMemory

from app.langchain.llm_factory import get_llm


def get_conversation_memory(
    memory_type: str = "buffer",
    max_token_limit: int = 2000,
    return_messages: bool = True
) -> BaseChatMemory:
    """
    Get conversation memory for chat history
    
    Args:
        memory_type: Type of memory (buffer, summary)
        max_token_limit: Maximum tokens to store
        return_messages: Whether to return as messages
        
    Returns:
        LangChain memory instance
    """
    if memory_type == "summary":
        llm = get_llm(temperature=0)
        return ConversationSummaryMemory(
            llm=llm,
            max_token_limit=max_token_limit,
            return_messages=return_messages,
            memory_key="chat_history"
        )
    else:
        return ConversationBufferMemory(
            max_token_limit=max_token_limit,
            return_messages=return_messages,
            memory_key="chat_history"
        )
