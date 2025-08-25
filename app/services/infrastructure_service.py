"""
Infrastructure management service for the AI Copilot.
"""
import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import structlog
from ..core.command_executor import CommandExecutor, CommandType, ExecutionLevel, CommandResult
from ..core.exceptions import AICopilotException, ValidationError
from ..core.metrics import record_business_metrics

logger = structlog.get_logger(__name__)


@dataclass
class ContainerInfo:
    """Container information."""
    id: str
    name: str
    image: str
    status: str
    ports: List[str]
    created: str
    size: str
    command: str


@dataclass
class SystemResource:
    """System resource information."""
    cpu_percent: float
    memory_percent: float
    memory_used: str
    memory_total: str
    disk_percent: float
    disk_used: str
    disk_total: str
    network_in: str
    network_out: str


@dataclass
class DatabaseStatus:
    """Database status information."""
    name: str
    status: str
    connections: int
    size: str
    uptime: str
    version: str


class InfrastructureService:
    """Service for managing infrastructure and system resources."""
    
    def __init__(self):
        self.command_executor = CommandExecutor()
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 300  # 5 minutes
        
    async def get_system_overview(self) -> Dict[str, Any]:
        """Get comprehensive system overview."""
        try:
            start_time = time.time()
            
            # Get system info
            system_info = self.command_executor.get_system_info()
            
            # Get resource usage
            resources = await self._get_system_resources()
            
            # Get container status
            containers = await self._get_container_status()
            
            # Get database status
            databases = await self._get_database_status()
            
            # Get network status
            network = await self._get_network_status()
            
            execution_time = time.time() - start_time
            
            overview = {
                "system": system_info,
                "resources": resources,
                "containers": containers,
                "databases": databases,
                "network": network,
                "timestamp": time.time(),
                "execution_time": execution_time
            }
            
            # Cache the result
            self.cache["system_overview"] = {
                "data": overview,
                "timestamp": time.time()
            }
            
            record_business_metrics("infrastructure_overview", "system", execution_time)
            
            return overview
            
        except Exception as e:
            logger.error("Failed to get system overview", error=str(e))
            raise AICopilotException(f"Failed to get system overview: {str(e)}")
    
    async def _get_system_resources(self) -> SystemResource:
        """Get system resource usage."""
        try:
            # Get CPU and memory info
            top_result = await self.command_executor.execute_command("top -bn1 | grep 'Cpu(s)'")
            free_result = await self.command_executor.execute_command("free -h")
            df_result = await self.command_executor.execute_command("df -h /")
            
            # Parse CPU usage
            cpu_line = top_result.stdout.strip()
            cpu_percent = 0.0
            if "Cpu(s)" in cpu_line:
                try:
                    cpu_parts = cpu_line.split()
                    cpu_percent = 100.0 - float(cpu_parts[1].replace('%us,', ''))
                except (IndexError, ValueError):
                    pass
            
            # Parse memory info
            memory_lines = free_result.stdout.strip().split('\n')
            memory_used = "0B"
            memory_total = "0B"
            memory_percent = 0.0
            
            if len(memory_lines) > 1:
                mem_line = memory_lines[1].split()
                if len(mem_line) >= 3:
                    memory_total = mem_line[1]
                    memory_used = mem_line[2]
                    try:
                        used = int(mem_line[2])
                        total = int(mem_line[1])
                        memory_percent = (used / total) * 100 if total > 0 else 0
                    except ValueError:
                        pass
            
            # Parse disk info
            disk_lines = df_result.stdout.strip().split('\n')
            disk_used = "0B"
            disk_total = "0B"
            disk_percent = 0.0
            
            if len(disk_lines) > 1:
                disk_line = disk_lines[1].split()
                if len(disk_line) >= 5:
                    disk_total = disk_line[1]
                    disk_used = disk_line[2]
                    try:
                        used = int(disk_line[2])
                        total = int(disk_line[1])
                        disk_percent = (used / total) * 100 if total > 0 else 0
                    except ValueError:
                        pass
            
            return SystemResource(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used=memory_used,
                memory_total=memory_total,
                disk_percent=disk_percent,
                disk_used=disk_used,
                disk_total=disk_total,
                network_in="0B",
                network_out="0B"
            )
            
        except Exception as e:
            logger.error("Failed to get system resources", error=str(e))
            return SystemResource(0.0, 0.0, "0B", "0B", 0.0, "0B", "0B", "0B", "0B")
    
    async def _get_container_status(self) -> List[ContainerInfo]:
        """Get Docker container status."""
        try:
            result = await self.command_executor.execute_docker_command("docker ps -a --format 'table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}\t{{.CreatedAt}}\t{{.Size}}\t{{.Command}}'")
            
            if not result.success:
                return []
            
            containers = []
            lines = result.stdout.strip().split('\n')
            
            # Skip header line
            for line in lines[1:]:
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 8:
                        containers.append(ContainerInfo(
                            id=parts[0],
                            name=parts[1],
                            image=parts[2],
                            status=parts[3],
                            ports=parts[4].split(',') if parts[4] else [],
                            created=parts[5],
                            size=parts[6],
                            command=parts[7]
                        ))
            
            return containers
            
        except Exception as e:
            logger.error("Failed to get container status", error=str(e))
            return []
    
    async def _get_database_status(self) -> List[DatabaseStatus]:
        """Get database status information."""
        try:
            databases = []
            
            # Check PostgreSQL
            try:
                pg_result = await self.command_executor.execute_command("pg_isready -h localhost -p 5432")
                if pg_result.success:
                    # Get more detailed info
                    pg_info = await self.command_executor.execute_command("psql -h localhost -U postgres -c 'SELECT version();'")
                    databases.append(DatabaseStatus(
                        name="PostgreSQL",
                        status="running" if pg_result.success else "stopped",
                        connections=0,  # Would need more complex query
                        size="unknown",
                        uptime="unknown",
                        version=pg_info.stdout.strip() if pg_info.success else "unknown"
                    ))
            except Exception:
                pass
            
            # Check Redis
            try:
                redis_result = await self.command_executor.execute_command("redis-cli ping")
                if redis_result.success and "PONG" in redis_result.stdout:
                    databases.append(DatabaseStatus(
                        name="Redis",
                        status="running",
                        connections=0,
                        size="unknown",
                        uptime="unknown",
                        version="unknown"
                    ))
            except Exception:
                pass
            
            # Check MongoDB
            try:
                mongo_result = await self.command_executor.execute_command("mongosh --eval 'db.runCommand({ping: 1})' --quiet")
                if mongo_result.success and "ok" in mongo_result.stdout:
                    databases.append(DatabaseStatus(
                        name="MongoDB",
                        status="running",
                        connections=0,
                        size="unknown",
                        uptime="unknown",
                        version="unknown"
                    ))
            except Exception:
                pass
            
            return databases
            
        except Exception as e:
            logger.error("Failed to get database status", error=str(e))
            return []
    
    async def _get_network_status(self) -> Dict[str, Any]:
        """Get network status information."""
        try:
            network_info = {}
            
            # Get network interfaces
            if_result = await self.command_executor.execute_command("ip addr show")
            if if_result.success:
                network_info["interfaces"] = self._parse_network_interfaces(if_result.stdout)
            
            # Get active connections
            ss_result = await self.command_executor.execute_command("ss -tuln")
            if ss_result.success:
                network_info["connections"] = self._parse_network_connections(ss_result.stdout)
            
            # Get routing table
            route_result = await self.command_executor.execute_command("ip route show")
            if route_result.success:
                network_info["routes"] = route_result.stdout.strip().split('\n')
            
            return network_info
            
        except Exception as e:
            logger.error("Failed to get network status", error=str(e))
            return {}
    
    def _parse_network_interfaces(self, output: str) -> List[Dict[str, str]]:
        """Parse network interface information."""
        interfaces = []
        current_interface = {}
        
        for line in output.split('\n'):
            line = line.strip()
            if line.startswith('inet '):
                current_interface['ip'] = line.split()[1]
            elif line.startswith('inet6 '):
                current_interface['ipv6'] = line.split()[1]
            elif ':' in line and not line.startswith('inet'):
                if current_interface:
                    interfaces.append(current_interface.copy())
                current_interface = {'name': line.split(':')[0].strip()}
        
        if current_interface:
            interfaces.append(current_interface)
        
        return interfaces
    
    def _parse_network_connections(self, output: str) -> List[Dict[str, str]]:
        """Parse network connection information."""
        connections = []
        
        for line in output.split('\n')[1:]:  # Skip header
            if line.strip():
                parts = line.split()
                if len(parts) >= 4:
                    connections.append({
                        'protocol': parts[0],
                        'state': parts[1],
                        'local': parts[3],
                        'peer': parts[4] if len(parts) > 4 else ''
                    })
        
        return connections
    
    async def execute_infrastructure_command(
        self,
        command: str,
        command_type: CommandType,
        execution_level: ExecutionLevel = ExecutionLevel.USER,
        timeout: Optional[int] = None
    ) -> CommandResult:
        """Execute an infrastructure command."""
        try:
            start_time = time.time()
            
            result = await self.command_executor.execute_command(
                command, command_type, execution_level, timeout
            )
            
            execution_time = time.time() - start_time
            
            # Record metrics
            record_business_metrics(
                "infrastructure_command",
                command_type.value,
                execution_time
            )
            
            return result
            
        except Exception as e:
            logger.error("Infrastructure command failed", command=command, error=str(e))
            raise
    
    async def get_container_logs(self, container_name: str, lines: int = 100) -> str:
        """Get container logs."""
        try:
            command = f"docker logs --tail {lines} {container_name}"
            result = await self.command_executor.execute_docker_command(command)
            
            if result.success:
                return result.stdout
            else:
                return f"Failed to get logs: {result.stderr}"
                
        except Exception as e:
            logger.error("Failed to get container logs", container=container_name, error=str(e))
            return f"Error: {str(e)}"
    
    async def restart_container(self, container_name: str) -> bool:
        """Restart a container."""
        try:
            command = f"docker restart {container_name}"
            result = await self.command_executor.execute_docker_command(command)
            
            if result.success:
                logger.info("Container restarted successfully", container=container_name)
                record_business_metrics("container_restart", "docker", 1.0)
                return True
            else:
                logger.error("Failed to restart container", container=container_name, error=result.stderr)
                return False
                
        except Exception as e:
            logger.error("Failed to restart container", container=container_name, error=str(e))
            return False
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get real-time system metrics."""
        try:
            # Check cache first
            cache_key = "system_metrics"
            if cache_key in self.cache:
                cache_entry = self.cache[cache_key]
                if time.time() - cache_entry["timestamp"] < self.cache_ttl:
                    return cache_entry["data"]
            
            # Get fresh metrics
            metrics = {
                "timestamp": time.time(),
                "load_average": await self._get_load_average(),
                "memory": await self._get_memory_usage(),
                "disk": await self._get_disk_usage(),
                "network": await self._get_network_usage(),
                "processes": await self._get_process_count()
            }
            
            # Cache the result
            self.cache[cache_key] = {
                "data": metrics,
                "timestamp": time.time()
            }
            
            return metrics
            
        except Exception as e:
            logger.error("Failed to get system metrics", error=str(e))
            return {"error": str(e)}
    
    async def _get_load_average(self) -> Dict[str, float]:
        """Get system load average."""
        try:
            result = await self.command_executor.execute_command("cat /proc/loadavg")
            if result.success:
                parts = result.stdout.strip().split()
                return {
                    "1min": float(parts[0]),
                    "5min": float(parts[1]),
                    "15min": float(parts[2])
                }
        except Exception:
            pass
        
        return {"1min": 0.0, "5min": 0.0, "15min": 0.0}
    
    async def _get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage information."""
        try:
            result = await self.command_executor.execute_command("cat /proc/meminfo")
            if result.success:
                meminfo = {}
                for line in result.stdout.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        meminfo[key.strip()] = value.strip()
                
                total = int(meminfo.get('MemTotal', '0 kB').split()[0])
                available = int(meminfo.get('MemAvailable', '0 kB').split()[0])
                used = total - available
                
                return {
                    "total_kb": total,
                    "used_kb": used,
                    "available_kb": available,
                    "usage_percent": (used / total) * 100 if total > 0 else 0
                }
        except Exception:
            pass
        
        return {"total_kb": 0, "used_kb": 0, "available_kb": 0, "usage_percent": 0}
    
    async def _get_disk_usage(self) -> Dict[str, Any]:
        """Get disk usage information."""
        try:
            result = await self.command_executor.execute_command("df -k /")
            if result.success:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 4:
                        total = int(parts[1])
                        used = int(parts[2])
                        available = int(parts[3])
                        
                        return {
                            "total_kb": total,
                            "used_kb": used,
                            "available_kb": available,
                            "usage_percent": (used / total) * 100 if total > 0 else 0
                        }
        except Exception:
            pass
        
        return {"total_kb": 0, "used_kb": 0, "available_kb": 0, "usage_percent": 0}
    
    async def _get_network_usage(self) -> Dict[str, str]:
        """Get network usage information."""
        try:
            result = await self.command_executor.execute_command("cat /proc/net/dev")
            if result.success:
                # Parse network statistics
                # This is a simplified version - in production you'd want more detailed parsing
                return {
                    "interfaces": "multiple",
                    "status": "active"
                }
        except Exception:
            pass
        
        return {"interfaces": "unknown", "status": "unknown"}
    
    async def _get_process_count(self) -> int:
        """Get total process count."""
        try:
            result = await self.command_executor.execute_command("ps aux | wc -l")
            if result.success:
                return int(result.stdout.strip()) - 1  # Subtract header line
        except Exception:
            pass
        
        return 0
    
    def clear_cache(self) -> None:
        """Clear the service cache."""
        self.cache.clear()
        logger.info("Infrastructure service cache cleared")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information."""
        return {
            "entries": len(self.cache),
            "ttl": self.cache_ttl,
            "keys": list(self.cache.keys())
        }
