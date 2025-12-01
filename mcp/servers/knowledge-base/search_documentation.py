"""
Search Documentation Tool (MCP Format)

MCP-compatible wrapper for searching project documentation.
"""

from typing import Dict, Any, List, Optional
import os
from pathlib import Path
import structlog

logger = structlog.get_logger(__name__)


async def search_documentation(
    query: str,
    document_type: str = "all",
    max_results: int = 5
) -> Dict[str, Any]:
    """
    Search project documentation and architecture files
    
    Args:
        query: Search query or topic
        document_type: Type of documents ("all", "architecture", "api", "configuration")
        max_results: Maximum number of results to return
        
    Returns:
        Search results with relevant documentation
        
    Example:
        ```python
        from mcp.servers.knowledge_base import search_documentation
        
        results = await search_documentation(
            query="authentication flow",
            document_type="architecture",
            max_results=3
        )
        ```
    """
    logger.info(
        "Searching documentation",
        query=query,
        document_type=document_type
    )
    
    try:
        # Get knowledge base path
        knowledge_base_path = os.getenv(
            "KNOWLEDGE_BASE_PATH",
            "/app/knowledge_source"
        )
        
        # Scan for documents
        documents = await _scan_documents(knowledge_base_path, document_type)
        
        # Search documents
        results = await _search_documents(query, documents, max_results)
        
        logger.info(
            "Documentation search completed",
            query=query,
            results_found=len(results)
        )
        
        return {
            "success": True,
            "query": query,
            "results": results,
            "total_found": len(results)
        }
        
    except Exception as e:
        logger.error(
            "Documentation search failed",
            query=query,
            error=str(e)
        )
        return {
            "success": False,
            "error": str(e),
            "results": []
        }


async def _scan_documents(
    base_path: str,
    document_type: str
) -> List[Dict[str, Any]]:
    """Scan for documentation files"""
    documents = []
    supported_extensions = {'.md', '.txt', '.json'}
    
    if not os.path.exists(base_path):
        return documents
    
    for root, dirs, files in os.walk(base_path):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = Path(file).suffix.lower()
            
            if file_ext in supported_extensions:
                doc_type = _classify_document(file)
                
                if document_type == "all" or doc_type == document_type:
                    documents.append({
                        "path": file_path,
                        "name": file,
                        "type": doc_type
                    })
    
    return documents


def _classify_document(filename: str) -> str:
    """Classify document type"""
    filename_lower = filename.lower()
    
    if any(word in filename_lower for word in ['architecture', 'design']):
        return "architecture"
    elif 'api' in filename_lower:
        return "api"
    elif any(word in filename_lower for word in ['config', 'settings']):
        return "configuration"
    elif any(word in filename_lower for word in ['deploy', 'docker']):
        return "deployment"
    
    return "general"


async def _search_documents(
    query: str,
    documents: List[Dict],
    max_results: int
) -> List[Dict[str, Any]]:
    """Search documents for query"""
    results = []
    query_lower = query.lower()
    
    for doc in documents:
        try:
            with open(doc["path"], 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Calculate relevance score
            score = _calculate_relevance(query_lower, content, doc["name"])
            
            if score > 0:
                # Extract snippet
                snippet = _extract_snippet(query_lower, content)
                
                results.append({
                    "title": doc["name"],
                    "type": doc["type"],
                    "relevance_score": round(score, 2),
                    "snippet": snippet,
                    "path": doc["path"]
                })
        except:
            continue
    
    # Sort by relevance
    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    return results[:max_results]


def _calculate_relevance(query: str, content: str, filename: str) -> float:
    """Calculate relevance score"""
    score = 0.0
    query_words = query.split()
    content_lower = content.lower()
    filename_lower = filename.lower()
    
    # Filename matches
    for word in query_words:
        if word in filename_lower:
            score += 3.0
        content_count = content_lower.count(word)
        score += min(content_count * 0.5, 5.0)
    
    # Exact phrase match
    if query in content_lower:
        score += 10.0
    
    return score


def _extract_snippet(query: str, content: str, max_length: int = 200) -> str:
    """Extract relevant snippet"""
    content_lower = content.lower()
    
    # Find first occurrence
    index = content_lower.find(query)
    if index == -1:
        # Return first part of content
        return content[:max_length] + "..." if len(content) > max_length else content
    
    # Extract context around match
    start = max(0, index - 50)
    end = min(len(content), index + max_length)
    snippet = content[start:end]
    
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."
    
    return snippet


# Tool metadata
__tool_metadata__ = {
    "name": "search_documentation",
    "description": "Search project documentation and architecture files",
    "category": "Knowledge",
    "parameters": {
        "query": {
            "type": "string",
            "description": "Search query",
            "required": True
        },
        "document_type": {
            "type": "string",
            "description": "Type of documents to search",
            "required": False,
            "enum": ["all", "architecture", "api", "configuration", "deployment"],
            "default": "all"
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum results to return",
            "required": False,
            "default": 5
        }
    }
}
