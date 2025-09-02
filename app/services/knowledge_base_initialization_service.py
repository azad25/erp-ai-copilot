"""
Knowledge Base Initialization Service

Processes ERP documentation, creates embeddings, and populates the knowledge base
with vector representations for AI Copilot's memory and context understanding.
"""

import os
import asyncio
import logging
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
# import aiofiles  # Temporarily disabled to fix Docker startup
import struct
import hashlib
from datetime import datetime
import json
import re

from app.services.memory_service import memory_service
from app.services.service_discovery_service import service_discovery
from app.database.connection import get_mongodb, get_qdrant

logger = logging.getLogger(__name__)


class KnowledgeBaseInitializationService:
    """
    Knowledge Base Initialization Service
    
    Features:
    - Process all documentation files in docs/ folder
    - Extract structured content from markdown files
    - Generate embeddings for semantic search
    - Store in Qdrant vector database
    - Create knowledge base entries in MongoDB
    - Index ERP architecture and endpoint documentation
    """
    
    def __init__(self):
        self.docs_path = Path("/app/docs")  # Use container path
        self.processed_files: Set[str] = set()
        self.file_hashes: Dict[str, str] = {}  # Track file content hashes
        self.chunk_size = 1000  # Characters per chunk
        self.chunk_overlap = 200  # Overlap between chunks
        
    async def initialize_knowledge_base(self, force_refresh: bool = False):
        """Initialize the complete knowledge base from documentation"""
        try:
            logger.info("Starting knowledge base initialization")
            
            if not force_refresh:
                # Load existing file hashes to avoid reprocessing unchanged files
                await self._load_existing_file_hashes()
            
            if force_refresh:
                await self._clear_existing_knowledge()
            
            # Process all documentation files (with change detection)
            await self._process_docs_folder()
            
            # Process ERP architecture documentation
            await self._process_erp_architecture_docs()
            
            # Index API endpoints and service documentation
            await self._index_api_endpoints()
            
            # Create summary knowledge entries (only if new files processed)
            if self.processed_files or force_refresh:
                await self._create_summary_entries()
            
            # Save file hashes for future runs
            await self._save_file_hashes()
            
            logger.info(f"Knowledge base initialization completed. Processed {len(self.processed_files)} files")
            
        except Exception as e:
            logger.error(f"Knowledge base initialization failed: {e}")
            raise
    
    async def _clear_existing_knowledge(self):
        """Clear existing knowledge base entries"""
        try:
            # Clear MongoDB knowledge entries
            mongodb = await get_mongodb()
            await mongodb.knowledge_base.delete_many({"source_type": "documentation"})
            
            # Clear Qdrant collection
            qdrant = await get_qdrant()
            try:
                await qdrant.delete_collection("erp_knowledge")
            except:
                pass  # Collection might not exist
            
            # Recreate collection
            from qdrant_client.models import Distance, VectorParams
            await qdrant.create_collection(
                collection_name="erp_knowledge",
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
            )
            
            logger.info("Cleared existing knowledge base")
            
        except Exception as e:
            logger.error(f"Failed to clear knowledge base: {e}")
    
    async def _process_docs_folder(self):
        """Process all markdown files in the docs folder"""
        if not self.docs_path.exists():
            logger.warning(f"Docs folder not found: {self.docs_path}")
            return
        
        # Get all markdown files
        md_files = list(self.docs_path.glob("*.md"))
        
        for md_file in md_files:
            await self._process_markdown_file(md_file)
    
    async def _process_markdown_file(self, file_path: Path):
        """Process a single markdown file with change detection"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Calculate file hash to detect changes
            file_hash = hashlib.md5(content.encode()).hexdigest()
            file_key = str(file_path)
            
            # Skip if file hasn't changed since last processing
            if file_key in self.file_hashes and self.file_hashes[file_key] == file_hash:
                logger.debug(f"Skipping unchanged file: {file_path.name}")
                return
            
            # Remove existing entries for this file if it was processed before
            if file_key in self.file_hashes:
                await self._remove_file_from_knowledge_base(file_key)
            
            # Extract metadata
            metadata = self._extract_file_metadata(file_path, content)
            
            # Split content into chunks
            chunks = self._split_content_into_chunks(content)
            
            # Process each chunk
            for i, chunk in enumerate(chunks):
                await self._process_content_chunk(
                    chunk=chunk,
                    file_path=str(file_path),
                    chunk_index=i,
                    total_chunks=len(chunks),
                    metadata=metadata
                )
            
            # Update tracking
            self.processed_files.add(str(file_path))
            self.file_hashes[file_key] = file_hash
            logger.info(f"Processed {file_path.name} - {len(chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")
    
    def _extract_file_metadata(self, file_path: Path, content: str) -> Dict[str, Any]:
        """Extract metadata from markdown file"""
        metadata = {
            "file_name": file_path.name,
            "file_path": str(file_path),
            "file_size": len(content),
            "processed_at": datetime.utcnow().isoformat()
        }
        
        # Extract title from first heading
        lines = content.split('\n')
        for line in lines:
            if line.startswith('# '):
                metadata["title"] = line[2:].strip()
                break
        
        # Extract sections
        sections = []
        for line in lines:
            if line.startswith('## '):
                sections.append(line[3:].strip())
            elif line.startswith('### '):
                sections.append(line[4:].strip())
        
        metadata["sections"] = sections
        
        # Determine document type based on filename
        filename_lower = file_path.name.lower()
        if "api" in filename_lower:
            metadata["doc_type"] = "api_documentation"
        elif "technical" in filename_lower:
            metadata["doc_type"] = "technical_documentation"
        elif "developer" in filename_lower:
            metadata["doc_type"] = "developer_guide"
        elif "infrastructure" in filename_lower:
            metadata["doc_type"] = "infrastructure"
        elif "readme" in filename_lower:
            metadata["doc_type"] = "overview"
        else:
            metadata["doc_type"] = "general_documentation"
        
        # Extract keywords
        metadata["keywords"] = self._extract_keywords(content)
        
        return metadata
    
    def _extract_keywords(self, content: str) -> List[str]:
        """Extract technical keywords from content"""
        keywords = set()
        
        # Technical terms to look for
        tech_terms = {
            'api', 'endpoint', 'service', 'microservice', 'database', 'mongodb', 'postgresql',
            'redis', 'qdrant', 'kafka', 'docker', 'kubernetes', 'fastapi', 'django',
            'authentication', 'authorization', 'jwt', 'oauth', 'rbac', 'cors',
            'websocket', 'grpc', 'rest', 'graphql', 'http', 'https',
            'nginx', 'prometheus', 'grafana', 'elasticsearch', 'kibana',
            'sales', 'inventory', 'finance', 'crm', 'hrm', 'accounting',
            'invoice', 'customer', 'product', 'order', 'payment', 'subscription'
        }
        
        # Convert to lowercase for matching
        content_lower = content.lower()
        
        for term in tech_terms:
            if term in content_lower:
                keywords.add(term)
        
        # Extract API endpoints
        endpoint_pattern = r'(/api/[^\s\)]+|/v\d+/[^\s\)]+)'
        endpoints = re.findall(endpoint_pattern, content)
        keywords.update(endpoints)
        
        # Extract service names
        service_pattern = r'([a-z-]+)-service'
        services = re.findall(service_pattern, content_lower)
        keywords.update(services)
        
        return list(keywords)
    
    def _split_content_into_chunks(self, content: str) -> List[str]:
        """Split content into overlapping chunks for better context"""
        if len(content) <= self.chunk_size:
            return [content]
        
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + self.chunk_size
            
            # Try to break at sentence or paragraph boundary
            if end < len(content):
                # Look for sentence ending
                for i in range(end, max(start + self.chunk_size - 200, start), -1):
                    if content[i] in '.!?\n':
                        end = i + 1
                        break
            
            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start position with overlap
            start = end - self.chunk_overlap
            if start >= len(content):
                break
        
        return chunks
    
    async def _process_content_chunk(
        self,
        chunk: str,
        file_path: str,
        chunk_index: int,
        total_chunks: int,
        metadata: Dict[str, Any]
    ):
        """Process a content chunk and store in knowledge base"""
        try:
            # Create unique chunk ID
            chunk_id = hashlib.md5(f"{file_path}:{chunk_index}:{chunk}".encode()).hexdigest()
            
            # Enhanced metadata for chunk
            chunk_metadata = {
                **metadata,
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
                "chunk_id": chunk_id,
                "content_length": len(chunk)
            }
            
            # Store in memory service (which handles embeddings and Qdrant)
            await memory_service.store_knowledge(
                title=f"{metadata.get('title', 'Unknown')} - Part {chunk_index + 1}",
                content=chunk,
                source=file_path,
                category=metadata.get("doc_type", "documentation"),
                metadata=chunk_metadata
            )
            
        except Exception as e:
            logger.error(f"Failed to process chunk {chunk_index} from {file_path}: {e}")
    
    async def _process_erp_architecture_docs(self):
        """Process ERP architecture documentation from the main docs folder"""
        erp_docs_path = Path("/app/docs")
        
        if erp_docs_path.exists():
            await self._process_directory_recursively(erp_docs_path, "erp_architecture")
    
    async def _process_directory_recursively(self, directory: Path, category: str):
        """Process all markdown files in a directory recursively"""
        for item in directory.rglob("*.md"):
            if item.is_file():
                try:
                    with open(item, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    metadata = self._extract_file_metadata(item, content)
                    metadata["category"] = category
                    metadata["relative_path"] = str(item.relative_to(directory))
                    
                    chunks = self._split_content_into_chunks(content)
                    
                    for i, chunk in enumerate(chunks):
                        await self._process_content_chunk(
                            chunk=chunk,
                            file_path=str(item),
                            chunk_index=i,
                            total_chunks=len(chunks),
                            metadata=metadata
                        )
                    
                    self.processed_files.add(str(item))
                    
                except Exception as e:
                    logger.error(f"Failed to process {item}: {e}")
    
    async def _index_api_endpoints(self):
        """Index API endpoints from service documentation"""
        try:
            # Use service discovery to get API endpoints
            try:
                await service_discovery.initialize()
                services = await service_discovery.get_all_services()
            except FileNotFoundError as e:
                logger.warning(f"Service discovery initialization failed: {e}")
                # Continue without service discovery data
                services = {}
            
            for service_name, service_info in services.items():
                # Create knowledge entry for each service
                service_doc = {
                    "name": service_name,
                    "type": service_info.type,
                    "version": service_info.version,
                    "endpoint": service_info.endpoint,
                    "capabilities": service_info.capabilities,
                    "dependencies": service_info.dependencies,
                    "health_check_url": service_info.health_check_url
                }
                
                await memory_service.store_knowledge(
                    title=f"{service_name} Service Documentation",
                    content=json.dumps(service_doc, indent=2),
                    source=f"service_discovery:{service_name}",
                    category="service_documentation",
                    metadata={
                        "service_name": service_name,
                        "service_type": service_info.type,
                        "capabilities": service_info.capabilities,
                        "auto_generated": True
                    }
                )
            
            logger.info(f"Indexed {len(services)} services in knowledge base")
            
        except Exception as e:
            logger.error(f"Failed to index API endpoints: {e}")
    
    async def _create_summary_entries(self):
        """Create high-level summary entries for the knowledge base"""
        summaries = [
            {
                "title": "ERP Suite Architecture Overview",
                "content": self._generate_architecture_summary(),
                "category": "architecture_summary",
                "metadata": {"type": "overview", "importance": "high"}
            },
            {
                "title": "AI Copilot Capabilities",
                "content": self._generate_copilot_capabilities_summary(),
                "category": "copilot_capabilities",
                "metadata": {"type": "capabilities", "importance": "high"}
            },
            {
                "title": "ERP Service Endpoints Reference",
                "content": await self._generate_endpoints_summary(),
                "category": "api_reference",
                "metadata": {"type": "reference", "importance": "medium"}
            },
            {
                "title": "Database Schema Overview",
                "content": self._generate_database_summary(),
                "category": "database_schema",
                "metadata": {"type": "schema", "importance": "medium"}
            }
        ]
        
        for summary in summaries:
            await memory_service.store_knowledge(
                title=summary["title"],
                content=summary["content"],
                source="knowledge_base_init",
                category=summary["category"],
                metadata=summary["metadata"]
            )
        
        logger.info("Created summary knowledge entries")
    
    async def _load_existing_file_hashes(self):
        """Load existing file hashes from MongoDB to detect changes"""
        try:
            mongodb = await get_mongodb()
            
            # Get file hashes from knowledge base metadata
            cursor = mongodb.knowledge_base.find(
                {"metadata.file_hash": {"$exists": True}},
                {"source": 1, "metadata.file_hash": 1}
            )
            
            async for doc in cursor:
                if "source" in doc and "metadata" in doc and "file_hash" in doc["metadata"]:
                    self.file_hashes[doc["source"]] = doc["metadata"]["file_hash"]
            
            logger.info(f"Loaded {len(self.file_hashes)} existing file hashes")
            
        except Exception as e:
            logger.warning(f"Failed to load existing file hashes: {e}")
            self.file_hashes = {}
    
    async def _save_file_hashes(self):
        """Save current file hashes to MongoDB for future change detection"""
        try:
            mongodb = await get_mongodb()
            
            # Update knowledge base entries with file hashes
            for file_path, file_hash in self.file_hashes.items():
                await mongodb.knowledge_base.update_many(
                    {"source": file_path},
                    {"$set": {"metadata.file_hash": file_hash}}
                )
            
            logger.info(f"Saved {len(self.file_hashes)} file hashes")
            
        except Exception as e:
            logger.error(f"Failed to save file hashes: {e}")
    
    async def _remove_file_from_knowledge_base(self, file_path: str):
        """Remove existing knowledge base entries for a file"""
        try:
            mongodb = await get_mongodb()
            qdrant = await get_qdrant()
            
            # Get existing entries to remove from Qdrant
            cursor = mongodb.knowledge_base.find({"source": file_path})
            qdrant_ids = []
            
            async for doc in cursor:
                if "metadata" in doc and "chunk_id" in doc["metadata"]:
                    qdrant_ids.append(doc["metadata"]["chunk_id"])
            
            # Remove from MongoDB
            result = await mongodb.knowledge_base.delete_many({"source": file_path})
            
            # Remove from Qdrant
            if qdrant_ids and qdrant:
                try:
                    await qdrant.delete(
                        collection_name="erp_knowledge",
                        points_selector={"ids": qdrant_ids}
                    )
                except Exception as e:
                    logger.warning(f"Failed to remove vectors from Qdrant: {e}")
            
            logger.info(f"Removed {result.deleted_count} entries for {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to remove file from knowledge base: {e}")
    
    def _generate_architecture_summary(self) -> str:
        """Generate ERP architecture summary"""
        return """
# ERP Suite Architecture Summary

## Overview
The ERP Suite is a comprehensive microservices-based enterprise resource planning system with 14+ independent services.

## Core Services
- **Auth Service**: User authentication, authorization, JWT management, RBAC
- **API Gateway**: Central routing, service discovery, load balancing
- **Sales Service**: Customer management, orders, invoicing, CRM
- **Inventory Service**: Stock management, product catalog, warehouse operations
- **Finance Service**: Accounting, financial reports, budgeting, transactions
- **Purchase Service**: Vendor management, purchase orders, procurement
- **Invoice Service**: Invoice generation, billing, payment tracking
- **Subscription Service**: SaaS subscription management, billing cycles
- **Document Generator**: PDF generation, report creation, document templates
- **Log Service**: Centralized logging, audit trails, system monitoring
- **AI Copilot**: Intelligent assistant, query processing, automation

## Technology Stack
- **Backend**: Python (Django/FastAPI), Go (Chi Router)
- **Frontend**: Next.js, React, TypeScript, Tailwind CSS
- **Databases**: PostgreSQL, MongoDB, Redis, Qdrant
- **Infrastructure**: Docker, Kubernetes, Nginx, Kafka
- **Monitoring**: Prometheus, Grafana, ELK Stack

## Communication Patterns
- REST APIs for standard operations
- GraphQL for complex queries
- gRPC for internal service communication
- WebSockets for real-time features
- Kafka for event streaming
"""
    
    def _generate_copilot_capabilities_summary(self) -> str:
        """Generate AI Copilot capabilities summary"""
        return """
# AI Copilot Capabilities Summary

## Core Features
- **Natural Language Processing**: Understand user queries in plain English
- **Database Query Generation**: Convert questions to SQL/NoSQL queries
- **Multi-Service Data Retrieval**: Access data across all ERP services
- **Real-time Analytics**: Generate insights and KPIs on demand
- **Report Generation**: Create formatted reports with visualizations
- **Conversation Memory**: Maintain context across chat sessions
- **Reasoning Display**: Show step-by-step AI thinking process

## Supported Queries
- Sales analytics and trends
- Inventory levels and movements
- Financial reports and KPIs
- Customer and vendor information
- Production schedules and metrics
- HR data and analytics
- System health and monitoring

## Integration Capabilities
- API Gateway communication for data access
- Kafka event processing for real-time updates
- Third-party API integrations (OpenAI, Slack, etc.)
- System command execution with RBAC
- Document and knowledge base search
- Service discovery and health monitoring

## Security Features
- Role-based access control (RBAC)
- JWT authentication
- Encrypted credential storage
- Audit logging
- Rate limiting
- Input validation and sanitization
"""
    
    async def _generate_endpoints_summary(self) -> str:
        """Generate API endpoints summary"""
        try:
            services = await service_discovery.get_all_services()
            
            endpoints_summary = "# ERP API Endpoints Reference\n\n"
            
            for service_name, service_info in services.items():
                endpoints_summary += f"## {service_name}\n"
                endpoints_summary += f"- **Base URL**: {service_info.endpoint}\n"
                endpoints_summary += f"- **Health Check**: {service_info.health_check_url}\n"
                endpoints_summary += f"- **Capabilities**: {', '.join(service_info.capabilities)}\n"
                
                if service_info.dependencies:
                    endpoints_summary += f"- **Dependencies**: {', '.join(service_info.dependencies)}\n"
                
                endpoints_summary += "\n"
            
            return endpoints_summary
            
        except Exception as e:
            logger.error(f"Failed to generate endpoints summary: {e}")
            return "# ERP API Endpoints Reference\n\nEndpoints information not available."
    
    def _generate_database_summary(self) -> str:
        """Generate database schema summary"""
        return """
# Database Schema Overview

## PostgreSQL Databases
- **Auth DB**: Users, roles, permissions, organizations, sessions
- **Sales DB**: Customers, orders, invoices, products, transactions
- **Inventory DB**: Products, stock levels, warehouses, movements
- **Finance DB**: Accounts, transactions, budgets, financial reports
- **Purchase DB**: Vendors, purchase orders, bills, procurement
- **Subscription DB**: Plans, subscriptions, billing, usage metrics

## MongoDB Collections
- **Conversations**: AI chat sessions and metadata
- **Messages**: Chat messages with reasoning steps
- **Knowledge Base**: Documentation and embeddings
- **User Preferences**: Personalization settings
- **System Logs**: Application and audit logs

## Redis Cache
- **Session Cache**: Active user sessions and context
- **API Cache**: Frequently accessed data
- **Rate Limiting**: Request counters and limits
- **User Preferences**: Quick access to settings

## Qdrant Vector Database
- **Document Embeddings**: Semantic search vectors
- **Knowledge Vectors**: AI memory and context
- **Conversation Embeddings**: Chat history vectors
"""
    
    async def _extract_api_endpoints_from_content(self, content: str) -> List[Dict[str, Any]]:
        """Extract API endpoint information from documentation content"""
        endpoints = []
        
        # Patterns to match API endpoints
        patterns = [
            r'(GET|POST|PUT|DELETE|PATCH)\s+(/api/[^\s\)]+)',
            r'`(GET|POST|PUT|DELETE|PATCH)\s+([^`]+)`',
            r'```\s*(GET|POST|PUT|DELETE|PATCH)\s+([^\s\n]+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if len(match) == 2:
                    method, path = match
                    endpoints.append({
                        "method": method.upper(),
                        "path": path.strip(),
                        "source": "documentation"
                    })
        
        return endpoints
    
    async def _create_endpoint_knowledge_entries(self, endpoints: List[Dict[str, Any]], source_file: str):
        """Create knowledge entries for discovered endpoints"""
        if not endpoints:
            return
        
        # Group endpoints by service
        services = {}
        for endpoint in endpoints:
            path_parts = endpoint["path"].split('/')
            service_name = "unknown"
            
            # Try to determine service from path
            if len(path_parts) > 2:
                if path_parts[1] == "api" and len(path_parts) > 3:
                    service_name = path_parts[3]
                elif path_parts[1].startswith("v"):
                    service_name = path_parts[2] if len(path_parts) > 2 else "unknown"
            
            if service_name not in services:
                services[service_name] = []
            services[service_name].append(endpoint)
        
        # Create knowledge entries for each service's endpoints
        for service_name, service_endpoints in services.items():
            content = f"# {service_name} API Endpoints\n\n"
            
            for endpoint in service_endpoints:
                content += f"- **{endpoint['method']}** `{endpoint['path']}`\n"
            
            await memory_service.store_knowledge(
                title=f"{service_name} API Endpoints",
                content=content,
                source=source_file,
                category="api_endpoints",
                metadata={
                    "service_name": service_name,
                    "endpoint_count": len(service_endpoints),
                    "extracted_from": source_file
                }
            )
    
    async def get_initialization_status(self) -> Dict[str, Any]:
        """Get knowledge base initialization status"""
        try:
            mongodb = await get_mongodb()
            
            # Count knowledge entries by category
            pipeline = [
                {"$group": {"_id": "$category", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            
            cursor = mongodb.knowledge_base.aggregate(pipeline)
            categories = {}
            total_entries = 0
            
            async for doc in cursor:
                categories[doc["_id"]] = doc["count"]
                total_entries += doc["count"]
            
            # Get Qdrant collection info
            try:
                qdrant_client = await get_qdrant()
                if qdrant_client is not None:
                    collection_info = await qdrant_client.get_collection("erp_knowledge")
                    vector_count = collection_info.vectors_count if collection_info else 0
                else:
                    vector_count = 0
            except Exception as e:
                logger.warning(f"Failed to get Qdrant collection info: {e}")
                vector_count = 0
            
            return {
                "total_knowledge_entries": total_entries,
                "categories": categories,
                "vector_count": vector_count,
                "processed_files_count": len(self.processed_files),
                "last_updated": datetime.utcnow().isoformat(),
                "status": "ready" if total_entries > 0 else "not_initialized"
            }
            
        except Exception as e:
            logger.error(f"Failed to get initialization status: {e}")
            return {"status": "error", "error": str(e)}
    
    async def refresh_knowledge_base(self):
        """Refresh the entire knowledge base"""
        await self.initialize_knowledge_base(force_refresh=True)
    
    async def add_new_documentation(self, file_path: str):
        """Add new documentation file to knowledge base"""
        path = Path(file_path)
        if path.exists() and path.suffix == '.md':
            await self._process_markdown_file(path)
            logger.info(f"Added new documentation: {file_path}")
        else:
            logger.warning(f"File not found or not markdown: {file_path}")


# Global knowledge base initialization service
knowledge_base_init_service = KnowledgeBaseInitializationService()
