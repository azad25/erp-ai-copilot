"""
Documentation Tools

Provides access to project documentation, architecture files, and knowledge base
for the QUERY AGENT to retrieve contextual information about the application.
"""

from typing import Dict, List, Optional, Any
import os
import json
import re
from datetime import datetime
import asyncio
from pathlib import Path

from .base_tool import BaseTool, ToolRequest, ToolResponse, ToolParameter, ToolParameterType, ToolMetadata


class DocumentationTool(BaseTool):
    """Tool for accessing project documentation and architecture files"""
    
    def __init__(self):
        super().__init__()
        self.knowledge_base_path = "/Users/ferdousazad/Documents/erp-suite/erp-ai-copilot/knowledge_source"
        self.supported_extensions = {'.md', '.txt', '.json', '.yaml', '.yml', '.py', '.go'}
        self._cache = {}
        self._cache_timeout = 600  # 10 minutes
        
        # Ensure knowledge source directory exists
        os.makedirs(self.knowledge_base_path, exist_ok=True)
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="documentation_search",
            description="Search and retrieve information from project documentation and architecture files",
            category="Knowledge",
            parameters=[
                ToolParameter(
                    name="query",
                    type=ToolParameterType.STRING,
                    description="Search query or topic to find in documentation",
                    required=True
                ),
                ToolParameter(
                    name="document_type",
                    type=ToolParameterType.STRING,
                    description="Type of documents to search",
                    required=False,
                    enum=["all", "architecture", "api", "configuration", "deployment", "troubleshooting"],
                    default="all"
                ),
                ToolParameter(
                    name="max_results",
                    type=ToolParameterType.INTEGER,
                    description="Maximum number of results to return",
                    required=False,
                    default=5
                ),
                ToolParameter(
                    name="include_snippets",
                    type=ToolParameterType.BOOLEAN,
                    description="Include code snippets and configuration examples",
                    required=False,
                    default=True
                )
            ],
            required_permissions=["knowledge.access"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        query = request.parameters.get("query", "").lower()
        document_type = request.parameters.get("document_type", "all")
        max_results = min(request.parameters.get("max_results", 5), 20)
        include_snippets = request.parameters.get("include_snippets", True)
        
        try:
            # Scan knowledge base
            documents = await self._scan_knowledge_base(document_type)
            
            # Search for relevant content
            results = await self._search_documents(query, documents, max_results)
            
            # Format results
            formatted_results = await self._format_results(results, include_snippets)
            
            return ToolResponse(
                success=True,
                data={
                    "query": query,
                    "results": formatted_results,
                    "total_found": len(results),
                    "document_types": list(set([r.get('type', 'unknown') for r in results]))
                },
                metadata={
                    "search_time": datetime.now().isoformat(),
                    "knowledge_base_size": len(documents),
                    "cache_hit": False
                }
            )
            
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Documentation search failed: {str(e)}"
            )
    
    async def _scan_knowledge_base(self, document_type: str) -> List[Dict[str, Any]]:
        """Scan knowledge base for documents"""
        documents = []
        
        # Define document type mappings
        type_mappings = {
            "architecture": ["ai-agent-architechture.md", "architecture", "design"],
            "api": ["api", "endpoint", "rest", "graphql"],
            "configuration": ["config", "settings", "env", "yaml", "json"],
            "deployment": ["deploy", "docker", "k8s", "kubernetes", "compose"],
            "troubleshooting": ["troubleshoot", "debug", "error", "fix", "guide"]
        }
        
        # Scan directories
        search_paths = [
            "/Users/ferdousazad/Documents/erp-suite/erp-ai-copilot",
            "/Users/ferdousazad/Documents/erp-suite",
            self.knowledge_base_path
        ]
        
        for base_path in search_paths:
            if not os.path.exists(base_path):
                continue
                
            for root, dirs, files in os.walk(base_path):
                # Skip common non-documentation directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {
                    '__pycache__', 'node_modules', '.git', 'venv', '.venv'
                }]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    file_ext = Path(file).suffix.lower()
                    
                    if file_ext in self.supported_extensions:
                        doc_type = self._classify_document(file, file_path, type_mappings)
                        
                        if document_type == "all" or doc_type == document_type:
                            documents.append({
                                "path": file_path,
                                "name": file,
                                "type": doc_type,
                                "size": os.path.getsize(file_path),
                                "modified": datetime.fromtimestamp(os.path.getmtime(file_path))
                            })
        
        return documents
    
    def _classify_document(self, filename: str, filepath: str, type_mappings: Dict[str, List[str]]) -> str:
        """Classify document type based on filename and content"""
        filename_lower = filename.lower()
        
        for doc_type, keywords in type_mappings.items():
            if any(keyword.lower() in filename_lower for keyword in keywords):
                return doc_type
        
        # Default classification based on filename patterns
        if any(word in filename_lower for word in ['readme', 'guide', 'tutorial']):
            return "troubleshooting"
        elif any(ext in filename_lower for ext in ['.yaml', '.yml', '.json', '.env']):
            return "configuration"
        elif 'docker' in filename_lower or 'compose' in filename_lower:
            return "deployment"
        elif 'api' in filename_lower or 'rest' in filename_lower:
            return "api"
        
        return "general"
    
    async def _search_documents(self, query: str, documents: List[Dict], max_results: int) -> List[Dict[str, Any]]:
        """Search documents for relevant content"""
        results = []
        
        for doc in documents:
            try:
                with open(doc["path"], 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Simple keyword matching with scoring
                score = self._calculate_relevance(query, content, doc["name"])
                
                if score > 0:
                    # Extract relevant snippets
                    snippets = self._extract_snippets(query, content)
                    
                    results.append({
                        "document": doc,
                        "score": score,
                        "snippets": snippets,
                        "content_preview": content[:500] + "..." if len(content) > 500 else content
                    })
                    
            except Exception:
                continue  # Skip unreadable files
        
        # Sort by relevance score
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]
    
    def _calculate_relevance(self, query: str, content: str, filename: str) -> float:
        """Calculate relevance score for document"""
        score = 0.0
        query_words = query.lower().split()
        content_lower = content.lower()
        filename_lower = filename.lower()
        
        # Title matches get higher weight
        for word in query_words:
            if word in filename_lower:
                score += 3.0
            
            # Content matches
            content_count = content_lower.count(word)
            score += min(content_count * 0.5, 5.0)  # Cap at 5 points per word
        
        # Exact phrase matches
        if query in content_lower:
            score += 10.0
        
        return score
    
    def _extract_snippets(self, query: str, content: str, max_snippets: int = 3) -> List[str]:
        """Extract relevant code snippets around search terms"""
        snippets = []
        query_lower = query.lower()
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            if query_lower in line.lower():
                # Get context around the match
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                snippet = '\n'.join(lines[start:end])
                
                if len(snippet.strip()) > 10:  # Skip very short snippets
                    snippets.append(snippet.strip())
                
                if len(snippets) >= max_snippets:
                    break
        
        return snippets
    
    async def _format_results(self, results: List[Dict], include_snippets: bool) -> List[Dict[str, Any]]:
        """Format search results for display"""
        formatted = []
        
        for result in results:
            doc = result["document"]
            
            formatted_result = {
                "title": doc["name"],
                "path": doc["path"],
                "type": doc["type"],
                "relevance_score": round(result["score"], 2),
                "last_modified": doc["modified"].isoformat(),
                "size_bytes": doc["size"],
                "preview": result["content_preview"]
            }
            
            if include_snippets and result["snippets"]:
                formatted_result["snippets"] = result["snippets"]
            
            formatted.append(formatted_result)
        
        return formatted


class ArchitectureTool(BaseTool):
    """Tool for accessing architecture-specific documentation"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="architecture_info",
            description="Get specific architecture and design information",
            category="Knowledge",
            parameters=[
                ToolParameter(
                    name="topic",
                    type=ToolParameterType.STRING,
                    description="Architecture topic to query",
                    required=True,
                    enum=["microservices", "database", "api", "security", "deployment", "monitoring"]
                ),
                ToolParameter(
                    name="detail_level",
                    type=ToolParameterType.STRING,
                    description="Level of detail required",
                    required=False,
                    enum=["overview", "detailed", "code_examples"],
                    default="overview"
                )
            ],
            required_permissions=["knowledge.access"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        topic = request.parameters.get("topic")
        detail_level = request.parameters.get("detail_level", "overview")
        
        architecture_docs = {
            "microservices": {
                "overview": """
                The UNIBASE ERP system uses a microservices architecture with the following services:
                - erp-ai-copilot: AI-powered assistance and chat
                - erp-api-gateway: Central API routing and load balancing
                - erp-auth-service: Authentication and authorization
                - erp-sales-service: Sales and CRM functionality
                - erp-log-service: Centralized logging and monitoring
                - inventory-service: Inventory management
                - invoice-service: Invoice and billing management
                - purchase-service: Purchase order management
                """,
                "detailed": """
                Microservices communicate via:
                - REST APIs for synchronous communication
                - gRPC for high-performance service-to-service calls
                - Kafka for event-driven asynchronous communication
                - WebSocket for real-time updates
                
                Service Discovery: Consul for service registration and discovery
                Load Balancing: NGINX and Kubernetes ingress controllers
                """,
                "code_examples": """
                Example service communication:
                ```python
                # gRPC client example
                channel = grpc.insecure_channel('erp-auth-service:50051')
                stub = auth_pb2_grpc.AuthServiceStub(channel)
                response = stub.ValidateToken(auth_pb2.TokenRequest(token=jwt_token))
                ```
                """
            },
            "database": {
                "overview": """
                Multi-database architecture:
                - PostgreSQL: Primary transactional data
                - MongoDB: Document storage and unstructured data
                - Redis: Caching and session management
                - Qdrant: Vector database for RAG system
                """,
                "detailed": """
                Database per service pattern:
                - Each microservice owns its database
                - Event sourcing for data consistency
                - CQRS (Command Query Responsibility Segregation)
                - Database migrations with Alembic (PostgreSQL)
                """
            },
            "api": {
                "overview": """
                API architecture:
                - RESTful APIs with OpenAPI/Swagger documentation
                - GraphQL for complex queries
                - Rate limiting and throttling
                - API versioning strategy
                """,
                "detailed": """
                API Gateway features:
                - Request routing and load balancing
                - Authentication and authorization
                - Rate limiting and throttling
                - Request/response transformation
                - API documentation and testing
                """
            },
            "security": {
                "overview": """
                Security architecture:
                - JWT-based authentication
                - RBAC (Role-Based Access Control)
                - OAuth 2.0 integration
                - API key management
                - Data encryption at rest and in transit
                """
            },
            "deployment": {
                "overview": """
                Deployment strategy:
                - Docker containers for all services
                - Kubernetes orchestration
                - CI/CD with GitHub Actions
                - Blue-green deployment
                - Infrastructure as Code (Terraform)
                """
            },
            "monitoring": {
                "overview": """
                Monitoring and observability:
                - Prometheus for metrics collection
                - Grafana for visualization
                - ELK stack for log aggregation
                - Jaeger for distributed tracing
                - Health checks and alerting
                """
            }
        }
        
        if topic not in architecture_docs:
            return ToolResponse(
                success=False,
                error=f"Unknown architecture topic: {topic}"
            )
        
        content = architecture_docs[topic].get(detail_level, architecture_docs[topic]["overview"])
        
        return ToolResponse(
            success=True,
            data={
                "topic": topic,
                "detail_level": detail_level,
                "content": content,
                "related_topics": [k for k in architecture_docs.keys() if k != topic]
            }
        )