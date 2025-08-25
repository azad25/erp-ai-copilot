"""
Command Execution Tools

Provides secure command execution capabilities for infrastructure and application management.
Optimized for performance with caching and resource management.
"""

from typing import Dict, List, Optional, Any
import asyncio
import subprocess
import json
import os
import shlex
from datetime import datetime, timedelta
import hashlib

from .base_tool import BaseTool, ToolRequest, ToolResponse, ToolParameter, ToolParameterType, ToolMetadata


class CommandExecutorTool(BaseTool):
    """Tool for executing system commands with security and performance optimization"""
    
    def __init__(self):
        super().__init__()
        self._command_cache = {}
        self._cache_timeout = 300  # 5 minutes
        self._max_execution_time = 30  # 30 seconds max
        self._allowed_commands = {
            'ls', 'cat', 'grep', 'find', 'ps', 'top', 'df', 'du', 'netstat', 'ss',
            'systemctl', 'service', 'journalctl', 'docker', 'kubectl', 'git',
            'curl', 'wget', 'ping', 'nslookup', 'dig', 'whoami', 'id', 'env',
            'date', 'uptime', 'free', 'iostat', 'vmstat', 'lscpu', 'lscpu', 'lsmem'
        }
        self._blocked_patterns = [
            'rm -rf', 'sudo', 'su ', 'chmod 777', 'mkfs', 'dd', 'fdisk',
            'iptables', 'ufw', 'iptables', 'useradd', 'userdel', 'passwd'
        ]
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="execute_command",
            description="Execute system commands with security validation and performance optimization",
            category="Infrastructure",
            parameters=[
                ToolParameter(
                    name="command",
                    type=ToolParameterType.STRING,
                    description="Command to execute (will be validated for security)",
                    required=True
                ),
                ToolParameter(
                    name="working_directory",
                    type=ToolParameterType.STRING,
                    description="Working directory for command execution",
                    required=False,
                    default="/tmp"
                ),
                ToolParameter(
                    name="timeout",
                    type=ToolParameterType.INTEGER,
                    description="Command timeout in seconds",
                    required=False,
                    default=30
                ),
                ToolParameter(
                    name="use_cache",
                    type=ToolParameterType.BOOLEAN,
                    description="Use cached results if available",
                    required=False,
                    default=True
                ),
                ToolParameter(
                    name="environment",
                    type=ToolParameterType.OBJECT,
                    description="Environment variables for command",
                    required=False,
                    default={}
                )
            ],
            required_permissions=["infrastructure.commands"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        command = request.parameters.get("command", "").strip()
        working_dir = request.parameters.get("working_directory", "/tmp")
        timeout = min(request.parameters.get("timeout", 30), self._max_execution_time)
        use_cache = request.parameters.get("use_cache", True)
        env_vars = request.parameters.get("environment", {})
        
        # Security validation
        if not self._validate_command(command):
            return ToolResponse(
                success=False,
                error="Command blocked for security reasons"
            )
        
        # Check cache
        cache_key = self._get_cache_key(command, working_dir, env_vars)
        if use_cache and cache_key in self._command_cache:
            cached_result = self._command_cache[cache_key]
            if datetime.now() - cached_result['timestamp'] < timedelta(seconds=self._cache_timeout):
                return ToolResponse(
                    success=True,
                    data=cached_result['data'],
                    metadata={"cached": True, "cache_age": (datetime.now() - cached_result['timestamp']).seconds}
                )
        
        try:
            # Prepare environment
            env = os.environ.copy()
            env.update(env_vars)
            
            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                env=env,
                limit=1024 * 1024  # 1MB output limit
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            
            result = {
                "command": command,
                "exit_code": process.returncode,
                "stdout": stdout.decode('utf-8', errors='ignore').strip(),
                "stderr": stderr.decode('utf-8', errors='ignore').strip(),
                "execution_time": timeout,
                "working_directory": working_dir
            }
            
            # Cache successful results
            if process.returncode == 0:
                self._command_cache[cache_key] = {
                    'data': result,
                    'timestamp': datetime.now()
                }
            
            return ToolResponse(
                success=process.returncode == 0,
                data=result,
                metadata={
                    "cached": False,
                    "cache_key": cache_key,
                    "command_length": len(command),
                    "output_size": len(result['stdout']) + len(result['stderr'])
                }
            )
            
        except asyncio.TimeoutError:
            return ToolResponse(
                success=False,
                error=f"Command timed out after {timeout} seconds"
            )
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Command execution failed: {str(e)}"
            )
    
    def _validate_command(self, command: str) -> bool:
        """Validate command for security"""
        command_lower = command.lower()
        
        # Check blocked patterns
        for pattern in self._blocked_patterns:
            if pattern.lower() in command_lower:
                return False
        
        # Check allowed commands
        cmd_parts = shlex.split(command)
        if not cmd_parts:
            return False
            
        base_cmd = cmd_parts[0]
        if base_cmd not in self._allowed_commands:
            return False
        
        return True
    
    def _get_cache_key(self, command: str, working_dir: str, env_vars: Dict[str, str]) -> str:
        """Generate cache key for command"""
        key_data = f"{command}|{working_dir}|{json.dumps(env_vars, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()


class InfrastructureTool(BaseTool):
    """Tool for infrastructure management commands"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="infrastructure_command",
            description="Execute infrastructure-specific commands for application management",
            category="Infrastructure",
            parameters=[
                ToolParameter(
                    name="service",
                    type=ToolParameterType.STRING,
                    description="Service name (app, database, redis, etc.)",
                    required=True,
                    enum=["app", "database", "redis", "nginx", "docker", "kubernetes"]
                ),
                ToolParameter(
                    name="action",
                    type=ToolParameterType.STRING,
                    description="Action to perform",
                    required=True,
                    enum=["status", "restart", "logs", "health", "metrics", "config"]
                ),
                ToolParameter(
                    name="environment",
                    type=ToolParameterType.STRING,
                    description="Environment (dev, staging, prod)",
                    required=False,
                    default="dev"
                )
            ],
            required_permissions=["infrastructure.manage"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        service = request.parameters.get("service")
        action = request.parameters.get("action")
        environment = request.parameters.get("environment", "dev")
        
        commands = {
            "app": {
                "status": "systemctl status erp-ai-copilot",
                "restart": "systemctl restart erp-ai-copilot",
                "logs": "journalctl -u erp-ai-copilot -f",
                "health": "curl -f http://localhost:8080/health || echo 'Service unhealthy'",
                "metrics": "curl -s http://localhost:8080/metrics",
                "config": "cat /etc/erp-ai-copilot/config.yaml"
            },
            "database": {
                "status": "systemctl status postgresql",
                "restart": "systemctl restart postgresql",
                "logs": "journalctl -u postgresql -f",
                "health": "pg_isready -h localhost -p 5432",
                "metrics": "psql -c 'SELECT * FROM pg_stat_activity;'",
                "config": "cat /etc/postgresql/*/main/postgresql.conf"
            },
            "redis": {
                "status": "systemctl status redis",
                "restart": "systemctl restart redis",
                "logs": "journalctl -u redis -f",
                "health": "redis-cli ping",
                "metrics": "redis-cli info",
                "config": "cat /etc/redis/redis.conf"
            },
            "docker": {
                "status": "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'",
                "restart": "docker-compose restart",
                "logs": "docker-compose logs -f --tail=100",
                "health": "docker-compose ps",
                "metrics": "docker stats --no-stream",
                "config": "docker-compose config"
            },
            "kubernetes": {
                "status": "kubectl get pods -n erp-system",
                "restart": "kubectl rollout restart deployment/erp-ai-copilot -n erp-system",
                "logs": "kubectl logs -f deployment/erp-ai-copilot -n erp-system",
                "health": "kubectl get pods -n erp-system -o wide",
                "metrics": "kubectl top pods -n erp-system",
                "config": "kubectl get configmap erp-config -n erp-system -o yaml"
            }
        }
        
        if service not in commands or action not in commands[service]:
            return ToolResponse(
                success=False,
                error=f"Unsupported service/action combination: {service}/{action}"
            )
        
        command = commands[service][action]
        
        # Use the CommandExecutorTool for actual execution
        executor = CommandExecutorTool()
        return await executor.execute(ToolRequest(
            tool_name="execute_command",
            parameters={
                "command": command,
                "use_cache": True,
                "timeout": 15
            }
        ))


class ApplicationTool(BaseTool):
    """Tool for application-level commands"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="application_command",
            description="Execute application-level commands for management and debugging",
            category="Application",
            parameters=[
                ToolParameter(
                    name="component",
                    type=ToolParameterType.STRING,
                    description="Application component",
                    required=True,
                    enum=["celery", "cache", "database", "queue", "logs", "config"]
                ),
                ToolParameter(
                    name="operation",
                    type=ToolParameterType.STRING,
                    description="Operation to perform",
                    required=True,
                    enum=["status", "clear", "reset", "stats", "size", "list"]
                ),
                ToolParameter(
                    name="target",
                    type=ToolParameterType.STRING,
                    description="Specific target within component",
                    required=False
                )
            ],
            required_permissions=["application.manage"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        component = request.parameters.get("component")
        operation = request.parameters.get("operation")
        target = request.parameters.get("target")
        
        commands = {
            "celery": {
                "status": "celery -A app.core.celery_app inspect active",
                "stats": "celery -A app.core.celery_app inspect stats",
                "clear": "celery -A app.core.celery_app purge",
                "list": "celery -A app.core.celery_app inspect registered",
                "reset": "celery -A app.core.celery_app control shutdown"
            },
            "cache": {
                "status": "redis-cli ping",
                "stats": "redis-cli info stats",
                "clear": "redis-cli FLUSHALL",
                "size": "redis-cli DBSIZE",
                "list": "redis-cli KEYS *"
            },
            "database": {
                "status": "psql -c \"SELECT version();\"",
                "stats": "psql -c \"SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database;\"",
                "size": "psql -c \"SELECT pg_size_pretty(pg_total_relation_size('public.*'));\"",
                "list": "psql -c \"\dt\""
            },
            "logs": {
                "status": "tail -n 50 /var/log/erp-ai-copilot/app.log",
                "clear": "echo '' > /var/log/erp-ai-copilot/app.log",
                "stats": "wc -l /var/log/erp-ai-copilot/app.log",
                "size": "du -h /var/log/erp-ai-copilot/app.log"
            }
        }
        
        if component not in commands or operation not in commands[component]:
            return ToolResponse(
                success=False,
                error=f"Unsupported component/operation: {component}/{operation}"
            )
        
        command = commands[component][operation]
        if target:
            command = f"{command} {target}"
        
        executor = CommandExecutorTool()
        return await executor.execute(ToolRequest(
            tool_name="execute_command",
            parameters={
                "command": command,
                "use_cache": True,
                "timeout": 10
            }
        ))