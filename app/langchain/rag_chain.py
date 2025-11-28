"""
RAG Chain

LangChain RAG implementation with Qdrant vector store.
"""

from typing import Optional, List, Dict, Any
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import Qdrant as LangChainQdrant
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from qdrant_client import QdrantClient

from app.langchain.llm_factory import get_llm, get_embeddings
from app.config.settings import get_settings

settings = get_settings()


def get_qdrant_client() -> QdrantClient:
    """Get Qdrant client instance"""
    return QdrantClient(
        host=settings.qdrant.host,
        port=settings.qdrant.port,
        api_key=settings.qdrant.api_key if settings.qdrant.api_key else None
    )


def get_rag_retriever(
    collection_name: str = "erp_documents",
    search_kwargs: Optional[Dict[str, Any]] = None
):
    """
    Get RAG retriever for document search
    
    Args:
        collection_name: Qdrant collection name
        search_kwargs: Search parameters (k, score_threshold, etc.)
        
    Returns:
        LangChain retriever
    """
    embeddings = get_embeddings()
    qdrant_client = get_qdrant_client()
    
    vectorstore = LangChainQdrant(
        client=qdrant_client,
        collection_name=collection_name,
        embeddings=embeddings
    )
    
    search_kwargs = search_kwargs or {"k": 5, "score_threshold": 0.7}
    
    return vectorstore.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs=search_kwargs
    )


def create_rag_chain(
    llm=None,
    collection_name: str = "erp_documents",
    return_source_documents: bool = True
):
    """
    Create RAG chain for question answering
    
    Args:
        llm: LangChain LLM instance (optional, creates default)
        collection_name: Qdrant collection name
        return_source_documents: Whether to return source documents
        
    Returns:
        LangChain RetrievalQA chain
    """
    if llm is None:
        llm = get_llm()
    
    retriever = get_rag_retriever(collection_name)
    
    # Custom prompt template
    prompt_template = """You are an intelligent ERP system assistant with access to comprehensive documentation.

Use the following pieces of context from the ERP documentation to answer the question at the end.
If you don't know the answer based on the context, say so - don't make up information.
Always cite the sources you used from the context.

Context:
{context}

Question: {question}

Provide a detailed, accurate answer based on the documentation above. Include:
1. Direct answer to the question
2. Relevant details from the documentation
3. Sources/references used

Answer:"""

    PROMPT = PromptTemplate(
        template=prompt_template,
        input_variables=["context", "question"]
    )
    
    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=return_source_documents,
        chain_type_kwargs={"prompt": PROMPT}
    )


async def search_documents(
    query: str,
    collection_name: str = "erp_documents",
    k: int = 5
) -> List[Document]:
    """
    Search documents using RAG retriever
    
    Args:
        query: Search query
        collection_name: Qdrant collection
        k: Number of results
        
    Returns:
        List of relevant documents
    """
    retriever = get_rag_retriever(
        collection_name=collection_name,
        search_kwargs={"k": k}
    )
    
    documents = await retriever.aget_relevant_documents(query)
    return documents
