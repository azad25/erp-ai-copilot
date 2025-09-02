"""
Service Discovery and ERP Documentation Access Service

Handles service discovery, ERP documentation indexing, codebase analysis,
and architecture understanding for AI Copilot intelligent assistance.
"""

from typing import Dict, List, Any, Optional, Set
import asyncio
import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
import aiofiles
import yaml
from dataclasses import dataclass, field

from app.config.settings import get_settings
from app.services.memory_service import memory_service
from app.services.api_gateway_client import api_gateway_client
from app.database.connection import get_mongodb, get_redis

logger = logging.getLogger(__name__)


@dataclass
class ServiceInfo:
    """Service information structure"""
    name: str
    type: str
    version: str
    status: str
    endpoint: str
    health_check_url: str
    dependencies: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    documentation_path: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DocumentationIndex:
    """Documentation index structure"""
    file_path: str
    content_type: str
    title: str
    summary: str
    sections: List[str] = field(default_factory=list)
    keywords: Set[str] = field(default_factory=set)
    last_indexed: datetime = field(default_factory=datetime.utcnow)


class ServiceDiscoveryService:
    """
    Service Discovery and Documentation Service
    
    Features:
    - Automatic service discovery from docker-compose and k8s configs
    - ERP documentation indexing and search
    - Codebase analysis and understanding
    - Architecture mapping and service relationships
    - API endpoint discovery and documentation
    - Real-time service health monitoring
    """
    
    def __init__(self):
        self.services: Dict[str, ServiceInfo] = {}
        self.documentation_index: Dict[str, DocumentationIndex] = {}
        self.service_relationships: Dict[str, List[str]] = {}
        settings = get_settings()
        self.erp_suite_path = "/app"
        self.documentation_paths = [
            "erp-suit-technical-docs",
            "service-designs",
            "README.md",
            "*.md"
        ]
        
    async def refresh_services(self):
        """Refresh service discovery data"""
        await self.initialize()
    
    async def initialize(self):
        """Initialize service discovery and documentation indexing"""
        try:
            await self._discover_services()
            await self._index_documentation()
            await self._analyze_codebase()
            await self._map_service_relationships()
            
            logger.info("Service discovery and documentation service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize service discovery: {e}")
            raise
    
    async def _discover_services(self):
        """Discover ERP services from configuration files"""
        # Discover from docker-compose files
        await self._discover_from_docker_compose()
        
        # Discover from service directories
        await self._discover_from_directories()
        
        # Discover from API Gateway
        await self._discover_from_api_gateway()
        
        logger.info(f"Discovered {len(self.services)} services")
    
    async def _discover_from_docker_compose(self):
        """Discover services from docker-compose files"""
        compose_files = [
            "docker-compose.yml",
            "docker-compose.dev.yml",
            "docker-compose.prod.yml"
        ]
        
        for compose_file in compose_files:
            compose_path = Path(self.erp_suite_path) / compose_file
            if compose_path.exists():
                try:
                    async with aiofiles.open(compose_path, 'r') as f:
                        content = await f.read()
                        compose_data = yaml.safe_load(content)
                        
                    services_config = compose_data.get('services', {})
                    for service_name, config in services_config.items():
                        await self._register_service_from_compose(service_name, config)
                        
                except Exception as e:
                    logger.error(f"Failed to parse {compose_file}: {e}")
    
    async def _register_service_from_compose(self, name: str, config: Dict[str, Any]):
        """Register service from docker-compose configuration"""
        ports = config.get('ports', [])
        environment = config.get('environment', {})
        
        # Extract port information
        endpoint = "http://localhost"
        if ports:
            port = str(ports[0]).split(':')[-1]
            endpoint = f"http://localhost:{port}"
        
        service = ServiceInfo(
            name=name,
            type="microservice",
            version=environment.get('VERSION', '1.0.0'),
            status="unknown",
            endpoint=endpoint,
            health_check_url=f"{endpoint}/health",
            dependencies=config.get('depends_on', []),
            capabilities=self._extract_capabilities_from_config(config)
        )
        
        self.services[name] = service
    
    async def _discover_from_directories(self):
        """Discover services from directory structure"""
        erp_path = Path(self.erp_suite_path)
        
        for item in erp_path.iterdir():
            if item.is_dir() and item.name.endswith('-service'):
                service_name = item.name
                
                # Check for service configuration
                config_files = ['config.yml', 'service.yml', 'app.yml']
                service_config = {}
                
                for config_file in config_files:
                    config_path = item / config_file
                    if config_path.exists():
                        try:
                            async with aiofiles.open(config_path, 'r') as f:
                                content = await f.read()
                                service_config = yaml.safe_load(content)
                                break
                        except Exception as e:
                            logger.warning(f"Failed to read {config_path}: {e}")
                
                # Register service
                if service_name not in self.services:
                    await self._register_service_from_directory(service_name, item, service_config)
    
    async def _register_service_from_directory(
        self,
        name: str,
        path: Path,
        config: Dict[str, Any]
    ):
        """Register service from directory analysis"""
        # Analyze service structure
        capabilities = await self._analyze_service_capabilities(path)
        
        service = ServiceInfo(
            name=name,
            type=config.get('type', 'microservice'),
            version=config.get('version', '1.0.0'),
            status="unknown",
            endpoint=config.get('endpoint', f"http://localhost:8000"),
            health_check_url=config.get('health_check', f"http://localhost:8000/health"),
            capabilities=capabilities,
            documentation_path=str(path / "README.md") if (path / "README.md").exists() else None
        )
        
        self.services[name] = service
    
    async def _discover_from_api_gateway(self):
        """Discover services from API Gateway"""
        try:
            services = await api_gateway_client.discover_services()
            
            for service_data in services:
                service_name = service_data.get('name')
                if service_name and service_name not in self.services:
                    service = ServiceInfo(
                        name=service_name,
                        type="microservice",
                        version=service_data.get('version', '1.0.0'),
                        status=service_data.get('status', 'unknown'),
                        endpoint=service_data.get('endpoint', ''),
                        health_check_url=service_data.get('health_url', ''),
                        capabilities=service_data.get('capabilities', [])
                    )
                    self.services[service_name] = service
                    
        except Exception as e:
            logger.warning(f"Failed to discover services from API Gateway: {e}")
    
    async def _analyze_service_capabilities(self, service_path: Path) -> List[str]:
        """Analyze service capabilities from code structure"""
        capabilities = []
        
        # Check for common patterns
        if (service_path / "api").exists():
            capabilities.append("REST API")
        if (service_path / "graphql").exists():
            capabilities.append("GraphQL")
        if (service_path / "proto").exists():
            capabilities.append("gRPC")
        if (service_path / "migrations").exists():
            capabilities.append("Database")
        if (service_path / "auth").exists():
            capabilities.append("Authentication")
        
        # Check for specific service types
        if "auth" in service_path.name:
            capabilities.extend(["User Management", "JWT", "RBAC"])
        elif "sales" in service_path.name:
            capabilities.extend(["CRM", "Invoicing", "Customer Management"])
        elif "inventory" in service_path.name:
            capabilities.extend(["Stock Management", "Product Catalog"])
        elif "finance" in service_path.name:
            capabilities.extend(["Accounting", "Financial Reports"])
        
        return capabilities
    
    async def _index_documentation(self):
        """Index all ERP documentation for search"""
        erp_path = Path(self.erp_suite_path)
        
        # Index technical documentation
        docs_path = erp_path / "erp-suit-technical-docs"
        if docs_path.exists():
            await self._index_directory_docs(docs_path, "technical")
        
        # Index service designs
        designs_path = erp_path / "service-designs"
        if designs_path.exists():
            await self._index_directory_docs(designs_path, "design")
        
        # Index README files
        for readme_path in erp_path.rglob("README.md"):
            await self._index_markdown_file(readme_path, "readme")
        
        # Index other markdown files
        for md_path in erp_path.rglob("*.md"):
            if md_path.name != "README.md":
                await self._index_markdown_file(md_path, "documentation")
        
        logger.info(f"Indexed {len(self.documentation_index)} documentation files")
    
    async def _index_directory_docs(self, directory: Path, doc_type: str):
        """Index documentation in a directory"""
        for file_path in directory.rglob("*.md"):
            await self._index_markdown_file(file_path, doc_type)
    
    async def _index_markdown_file(self, file_path: Path, content_type: str):
        """Index a markdown file"""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # Extract title and sections
            lines = content.split('\n')
            title = self._extract_title(lines)
            sections = self._extract_sections(lines)
            keywords = self._extract_keywords(content)
            summary = self._generate_summary(content)
            
            doc_index = DocumentationIndex(
                file_path=str(file_path),
                content_type=content_type,
                title=title,
                summary=summary,
                sections=sections,
                keywords=keywords
            )
            
            self.documentation_index[str(file_path)] = doc_index
            
            # Store in memory service for semantic search
            await memory_service.store_knowledge(
                title=title,
                content=content,
                source=str(file_path),
                category=content_type,
                metadata={
                    "sections": sections,
                    "keywords": list(keywords),
                    "file_type": "markdown"
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to index {file_path}: {e}")
    
    def _extract_title(self, lines: List[str]) -> str:
        """Extract title from markdown content"""
        for line in lines:
            if line.startswith('# '):
                return line[2:].strip()
        return "Untitled"
    
    def _extract_sections(self, lines: List[str]) -> List[str]:
        """Extract section headers from markdown"""
        sections = []
        for line in lines:
            if line.startswith('## '):
                sections.append(line[3:].strip())
            elif line.startswith('### '):
                sections.append(line[4:].strip())
        return sections
    
    def _extract_keywords(self, content: str) -> Set[str]:
        """Extract keywords from content"""
        # Simple keyword extraction
        words = content.lower().split()
        keywords = set()
        
        # Technical keywords
        tech_keywords = {
            'api', 'database', 'service', 'microservice', 'authentication',
            'authorization', 'jwt', 'oauth', 'rest', 'graphql', 'grpc',
            'mongodb', 'postgresql', 'redis', 'kafka', 'docker', 'kubernetes',
            'nginx', 'prometheus', 'grafana', 'elasticsearch', 'kibana'
        }
        
        for word in words:
            if word in tech_keywords:
                keywords.add(word)
        
        return keywords
    
    def _generate_summary(self, content: str) -> str:
        """Generate summary from content"""
        lines = content.split('\n')
        summary_lines = []
        
        for line in lines:
            if line.strip() and not line.startswith('#'):
                summary_lines.append(line.strip())
                if len(summary_lines) >= 3:
                    break
        
        return ' '.join(summary_lines)[:200] + "..." if summary_lines else "No summary available"
    
    async def _analyze_codebase(self):
        """Analyze ERP codebase structure and patterns"""
        erp_path = Path(self.erp_suite_path)
        
        # Analyze each service
        for service_name, service_info in self.services.items():
            service_path = erp_path / service_name
            if service_path.exists():
                analysis = await self._analyze_service_codebase(service_path)
                
                # Store analysis in memory
                await memory_service.store_knowledge(
                    title=f"{service_name} Codebase Analysis",
                    content=json.dumps(analysis, indent=2),
                    source=f"codebase:{service_name}",
                    category="codebase_analysis",
                    metadata={
                        "service": service_name,
                        "analysis_type": "structure",
                        "file_count": analysis.get("file_count", 0)
                    }
                )
    
    async def _analyze_service_codebase(self, service_path: Path) -> Dict[str, Any]:
        """Analyze individual service codebase"""
        analysis = {
            "service_path": str(service_path),
            "language": "unknown",
            "framework": "unknown",
            "file_count": 0,
            "directories": [],
            "key_files": [],
            "api_endpoints": [],
            "database_models": [],
            "configuration_files": []
        }
        
        try:
            # Detect language and framework
            if (service_path / "go.mod").exists():
                analysis["language"] = "Go"
                analysis["framework"] = await self._detect_go_framework(service_path)
            elif (service_path / "requirements.txt").exists() or (service_path / "pyproject.toml").exists():
                analysis["language"] = "Python"
                analysis["framework"] = await self._detect_python_framework(service_path)
            elif (service_path / "package.json").exists():
                analysis["language"] = "JavaScript/TypeScript"
                analysis["framework"] = await self._detect_js_framework(service_path)
            
            # Count files and directories
            for item in service_path.rglob("*"):
                if item.is_file():
                    analysis["file_count"] += 1
                    
                    # Identify key files
                    if item.name in ["main.go", "server.py", "app.py", "index.js", "main.ts"]:
                        analysis["key_files"].append(str(item.relative_to(service_path)))
                    elif item.suffix in [".proto", ".graphql", ".sql"]:
                        analysis["key_files"].append(str(item.relative_to(service_path)))
                elif item.is_dir() and item.parent == service_path:
                    analysis["directories"].append(item.name)
            
            # Extract API endpoints
            analysis["api_endpoints"] = await self._extract_api_endpoints(service_path)
            
            # Extract database models
            analysis["database_models"] = await self._extract_database_models(service_path)
            
        except Exception as e:
            logger.error(f"Failed to analyze {service_path}: {e}")
        
        return analysis
    
    async def _detect_go_framework(self, service_path: Path) -> str:
        """Detect Go framework"""
        go_mod_path = service_path / "go.mod"
        if go_mod_path.exists():
            try:
                async with aiofiles.open(go_mod_path, 'r') as f:
                    content = await f.read()
                
                if "gin-gonic/gin" in content:
                    return "Gin"
                elif "gorilla/mux" in content:
                    return "Gorilla Mux"
                elif "echo" in content:
                    return "Echo"
                elif "fiber" in content:
                    return "Fiber"
                
            except Exception as e:
                logger.error(f"Failed to read go.mod: {e}")
        
        return "Standard Library"
    
    async def _detect_python_framework(self, service_path: Path) -> str:
        """Detect Python framework"""
        requirements_files = ["requirements.txt", "pyproject.toml", "Pipfile"]
        
        for req_file in requirements_files:
            req_path = service_path / req_file
            if req_path.exists():
                try:
                    async with aiofiles.open(req_path, 'r') as f:
                        content = await f.read()
                    
                    if "fastapi" in content.lower():
                        return "FastAPI"
                    elif "django" in content.lower():
                        return "Django"
                    elif "flask" in content.lower():
                        return "Flask"
                    elif "tornado" in content.lower():
                        return "Tornado"
                    
                except Exception as e:
                    logger.error(f"Failed to read {req_file}: {e}")
        
        return "Unknown"
    
    async def _detect_js_framework(self, service_path: Path) -> str:
        """Detect JavaScript/TypeScript framework"""
        package_json_path = service_path / "package.json"
        if package_json_path.exists():
            try:
                async with aiofiles.open(package_json_path, 'r') as f:
                    content = await f.read()
                    package_data = json.loads(content)
                
                dependencies = {**package_data.get('dependencies', {}), **package_data.get('devDependencies', {})}
                
                if 'next' in dependencies:
                    return "Next.js"
                elif 'react' in dependencies:
                    return "React"
                elif 'vue' in dependencies:
                    return "Vue.js"
                elif 'express' in dependencies:
                    return "Express.js"
                elif '@nestjs/core' in dependencies:
                    return "NestJS"
                
            except Exception as e:
                logger.error(f"Failed to read package.json: {e}")
        
        return "Unknown"
    
    async def _extract_api_endpoints(self, service_path: Path) -> List[str]:
        """Extract API endpoints from service code"""
        endpoints = []
        
        # Look for route definitions in common files
        route_files = list(service_path.rglob("*route*")) + list(service_path.rglob("*handler*"))
        
        for file_path in route_files:
            if file_path.suffix in ['.py', '.go', '.js', '.ts']:
                try:
                    async with aiofiles.open(file_path, 'r') as f:
                        content = await f.read()
                    
                    # Simple endpoint extraction (can be enhanced)
                    lines = content.split('\n')
                    for line in lines:
                        if any(method in line.lower() for method in ['@app.get', '@app.post', 'router.get', 'router.post', 'app.get', 'app.post']):
                            endpoints.append(line.strip())
                        elif 'http.HandleFunc' in line or 'router.HandleFunc' in line:
                            endpoints.append(line.strip())
                
                except Exception as e:
                    logger.error(f"Failed to analyze {file_path}: {e}")
        
        return endpoints[:20]  # Limit to first 20 endpoints
    
    async def _extract_database_models(self, service_path: Path) -> List[str]:
        """Extract database models from service code"""
        models = []
        
        # Look for model definitions
        model_files = list(service_path.rglob("*model*")) + list(service_path.rglob("*schema*"))
        
        for file_path in model_files:
            if file_path.suffix in ['.py', '.go', '.js', '.ts']:
                try:
                    async with aiofiles.open(file_path, 'r') as f:
                        content = await f.read()
                    
                    # Extract model names (simple pattern matching)
                    lines = content.split('\n')
                    for line in lines:
                        if 'class ' in line and ('Model' in line or 'Schema' in line):
                            models.append(line.strip())
                        elif 'type ' in line and 'struct' in line:
                            models.append(line.strip())
                
                except Exception as e:
                    logger.error(f"Failed to analyze {file_path}: {e}")
        
        return models[:10]  # Limit to first 10 models
    
    async def _map_service_relationships(self):
        """Map relationships between services"""
        for service_name, service_info in self.services.items():
            relationships = []
            
            # Add dependencies
            relationships.extend(service_info.dependencies)
            
            # Analyze service communication patterns
            service_path = Path(self.erp_suite_path) / service_name
            if service_path.exists():
                comm_patterns = await self._analyze_service_communication(service_path)
                relationships.extend(comm_patterns)
            
            self.service_relationships[service_name] = list(set(relationships))
    
    async def _analyze_service_communication(self, service_path: Path) -> List[str]:
        """Analyze how service communicates with others"""
        communications = []
        
        # Look for service calls in configuration and code
        config_files = list(service_path.rglob("*.yml")) + list(service_path.rglob("*.yaml"))
        
        for config_file in config_files:
            try:
                async with aiofiles.open(config_file, 'r') as f:
                    content = await f.read()
                
                # Look for service references
                for service_name in self.services.keys():
                    if service_name in content and service_name != service_path.name:
                        communications.append(service_name)
                
            except Exception as e:
                logger.error(f"Failed to analyze {config_file}: {e}")
        
        return list(set(communications))
    
    async def search_documentation(
        self,
        query: str,
        doc_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search documentation using semantic search"""
        try:
            # Use memory service for semantic search
            results = await memory_service.search_knowledge(
                query=query,
                category=doc_type,
                limit=limit
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Documentation search failed: {e}")
            return []
    
    async def get_service_info(self, service_name: str) -> Optional[ServiceInfo]:
        """Get information about a specific service"""
        return self.services.get(service_name)
    
    async def get_all_services(self) -> Dict[str, ServiceInfo]:
        """Get all discovered services"""
        return self.services.copy()
    
    async def get_service_relationships(self, service_name: str) -> List[str]:
        """Get service relationships"""
        return self.service_relationships.get(service_name, [])
    
    async def refresh_service_discovery(self):
        """Refresh service discovery and documentation index"""
        self.services.clear()
        self.documentation_index.clear()
        self.service_relationships.clear()
        
        await self.initialize()
        logger.info("Service discovery refreshed")


# Global service discovery instance
service_discovery = ServiceDiscoveryService()
