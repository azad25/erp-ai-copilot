"""
LangChain Integration Layer

Provides LangChain components for the ERP AI Copilot:
- LLM factory for multiple providers
- RAG chains with Qdrant
- Tools for API calls and data access
- Memory management
"""

from .llm_factory import get_llm, get_embeddings
from .rag_chain import create_rag_chain, get_rag_retriever
from .tools import get_erp_tools
from .memory import get_conversation_memory

__all__ = [
    "get_llm",
    "get_embeddings",
    "create_rag_chain",
    "get_rag_retriever",
    "get_erp_tools",
    "get_conversation_memory",
]
