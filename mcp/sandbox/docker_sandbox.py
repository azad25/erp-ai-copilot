"""
Docker Sandbox

Executes code in isolated Docker containers for security.
Implements resource limits and network restrictions.
"""

from typing import Dict, Any, Optional
import docker
import structlog
import asyncio
from datetime import datetime

logger = structlog.get_logger(__name__)


class DockerSandbox:
    """
    Docker-based code execution sandbox
    
    Features:
    - Isolated execution environment
    - Resource limits (CPU, memory, timeout)
    - Network restrictions
    - Automatic cleanup
    """
    
    def __init__(self):
        self.client: Optional[docker.DockerClient] = None
        self.image = "python:3.11-slim"
        self.network_mode = "none"  # No network access by default
        
    async def initialize(self):
        """Initialize Docker client"""
        try:
            self.client = docker.from_env()
            
            # Pull image if not exists
            try:
                self.client.images.get(self.image)
                logger.info(f"Docker image {self.image} found")
            except docker.errors.ImageNotFound:
                logger.info(f"Pulling Docker image {self.image}")
                self.client.images.pull(self.image)
                logger.info(f"Docker image {self.image} pulled")
            
            logger.info("Docker sandbox initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Docker sandbox: {e}")
            raise
    
    async def execute(
        self,
        code: str,
        timeout: int = 30,
        memory_limit: str = "512m",
        cpu_limit: float = 1.0,
        allow_network: bool = False
    ) -> Dict[str, Any]:
        """
        Execute code in Docker container
        
        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds
            memory_limit: Memory limit (e.g., "512m", "1g")
            cpu_limit: CPU limit (1.0 = 1 core)
            allow_network: Whether to allow network access
            
        Returns:
            Execution result with output and metadata
        """
        if not self.client:
            return {
                "success": False,
                "error": "Docker client not initialized"
            }
        
        container_id = None
        start_time = datetime.utcnow()
        
        try:
            logger.info(
                "Starting container execution",
                timeout=timeout,
                memory_limit=memory_limit,
                cpu_limit=cpu_limit
            )
            
            # Create container
            container = self.client.containers.run(
                image=self.image,
                command=["python", "-c", code],
                detach=True,
                mem_limit=memory_limit,
                cpu_period=100000,
                cpu_quota=int(cpu_limit * 100000),
                network_mode="bridge" if allow_network else "none",
                remove=False,  # We'll remove manually after getting logs
                stdout=True,
                stderr=True
            )
            
            container_id = container.id
            
            logger.info(
                "Container started",
                container_id=container_id[:12]
            )
            
            # Wait for container with timeout
            try:
                result = container.wait(timeout=timeout)
                exit_code = result['StatusCode']
                
                # Get logs
                logs = container.logs().decode('utf-8')
                
                # Remove container
                container.remove(force=True)
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                logger.info(
                    "Container execution completed",
                    container_id=container_id[:12],
                    exit_code=exit_code,
                    execution_time=execution_time
                )
                
                return {
                    "success": exit_code == 0,
                    "output": logs,
                    "exit_code": exit_code,
                    "execution_time": execution_time,
                    "container_id": container_id[:12]
                }
                
            except Exception as timeout_error:
                # Timeout or execution error
                logger.warning(
                    "Container execution timeout",
                    container_id=container_id[:12],
                    timeout=timeout
                )
                
                # Kill and remove container
                try:
                    container.kill()
                    logs = container.logs().decode('utf-8')
                    container.remove(force=True)
                except:
                    logs = "Failed to retrieve logs"
                
                return {
                    "success": False,
                    "error": f"Execution timeout ({timeout}s)",
                    "output": logs,
                    "exit_code": -1,
                    "container_id": container_id[:12] if container_id else None
                }
                
        except Exception as e:
            logger.error(
                "Container execution failed",
                error=str(e),
                container_id=container_id[:12] if container_id else None
            )
            
            # Cleanup on error
            if container_id:
                try:
                    container = self.client.containers.get(container_id)
                    container.remove(force=True)
                except:
                    pass
            
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "exit_code": -1
            }
    
    async def close(self):
        """Close Docker client"""
        if self.client:
            self.client.close()
            logger.info("Docker sandbox closed")
