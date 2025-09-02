"""
System Command Execution Service

Handles secure execution of system commands with RBAC validation.
Provides Docker, sudo, and other system-level operations for AI Copilot.
"""

from typing import Dict, List, Any, Optional, Tuple
import asyncio
import subprocess
import logging
import shlex
import os
from datetime import datetime
from uuid import uuid4
from dataclasses import dataclass
import json

from app.core.config import settings
from app.services.auth_service import AuthService
from app.database.connection import get_mongodb

logger = logging.getLogger(__name__)


@dataclass
class CommandExecution:
    """Command execution record"""
    execution_id: str
    user_id: str
    organization_id: str
    command: str
    args: List[str]
    working_directory: str
    user_role: str
    status: str
    return_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    execution_time: float = 0.0
    created_at: datetime = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class SystemCommandService:
    """
    System Command Execution Service with RBAC
    
    Features:
    - Secure command execution with role-based access control
    - Docker container management
    - System administration commands
    - Command logging and audit trail
    - Sandboxed execution environment
    - Resource limits and timeouts
    """
    
    def __init__(self):
        self.auth_service = AuthService()
        self.allowed_commands = self._initialize_allowed_commands()
        self.command_timeout = 300  # 5 minutes default timeout
        self.max_output_size = 1024 * 1024  # 1MB max output
        
    def _initialize_allowed_commands(self) -> Dict[str, Dict[str, Any]]:
        """Initialize allowed commands by role"""
        return {
            "admin": {
                "docker": {
                    "subcommands": ["ps", "images", "logs", "stats", "inspect", "exec", "restart", "stop", "start"],
                    "description": "Docker container management",
                    "requires_sudo": False
                },
                "systemctl": {
                    "subcommands": ["status", "restart", "start", "stop", "reload"],
                    "description": "System service management",
                    "requires_sudo": True
                },
                "kubectl": {
                    "subcommands": ["get", "describe", "logs", "exec", "apply", "delete"],
                    "description": "Kubernetes cluster management",
                    "requires_sudo": False
                },
                "git": {
                    "subcommands": ["status", "log", "diff", "pull", "push", "checkout", "branch"],
                    "description": "Git repository management",
                    "requires_sudo": False
                },
                "ls": {
                    "subcommands": [],
                    "description": "List directory contents",
                    "requires_sudo": False
                },
                "cat": {
                    "subcommands": [],
                    "description": "Display file contents",
                    "requires_sudo": False
                },
                "tail": {
                    "subcommands": [],
                    "description": "Display file tail",
                    "requires_sudo": False
                },
                "grep": {
                    "subcommands": [],
                    "description": "Search text patterns",
                    "requires_sudo": False
                },
                "find": {
                    "subcommands": [],
                    "description": "Find files and directories",
                    "requires_sudo": False
                },
                "df": {
                    "subcommands": [],
                    "description": "Display filesystem usage",
                    "requires_sudo": False
                },
                "free": {
                    "subcommands": [],
                    "description": "Display memory usage",
                    "requires_sudo": False
                },
                "top": {
                    "subcommands": [],
                    "description": "Display running processes",
                    "requires_sudo": False
                },
                "ps": {
                    "subcommands": [],
                    "description": "Display process status",
                    "requires_sudo": False
                }
            },
            "manager": {
                "docker": {
                    "subcommands": ["ps", "images", "logs", "stats", "inspect"],
                    "description": "Docker monitoring commands",
                    "requires_sudo": False
                },
                "kubectl": {
                    "subcommands": ["get", "describe", "logs"],
                    "description": "Kubernetes monitoring commands",
                    "requires_sudo": False
                },
                "git": {
                    "subcommands": ["status", "log", "diff"],
                    "description": "Git read-only commands",
                    "requires_sudo": False
                },
                "ls": {
                    "subcommands": [],
                    "description": "List directory contents",
                    "requires_sudo": False
                },
                "cat": {
                    "subcommands": [],
                    "description": "Display file contents",
                    "requires_sudo": False
                },
                "tail": {
                    "subcommands": [],
                    "description": "Display file tail",
                    "requires_sudo": False
                },
                "grep": {
                    "subcommands": [],
                    "description": "Search text patterns",
                    "requires_sudo": False
                },
                "df": {
                    "subcommands": [],
                    "description": "Display filesystem usage",
                    "requires_sudo": False
                },
                "free": {
                    "subcommands": [],
                    "description": "Display memory usage",
                    "requires_sudo": False
                }
            },
            "user": {
                "docker": {
                    "subcommands": ["ps", "logs", "stats"],
                    "description": "Basic Docker monitoring",
                    "requires_sudo": False
                },
                "ls": {
                    "subcommands": [],
                    "description": "List directory contents",
                    "requires_sudo": False
                },
                "cat": {
                    "subcommands": [],
                    "description": "Display file contents (limited paths)",
                    "requires_sudo": False
                },
                "df": {
                    "subcommands": [],
                    "description": "Display filesystem usage",
                    "requires_sudo": False
                }
            }
        }
    
    async def execute_command(
        self,
        user_id: str,
        organization_id: str,
        user_role: str,
        command: str,
        args: List[str],
        working_directory: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> CommandExecution:
        """
        Execute a system command with RBAC validation
        
        Args:
            user_id: User identifier
            organization_id: Organization identifier
            user_role: User role for RBAC
            command: Command to execute
            args: Command arguments
            working_directory: Working directory for command execution
            timeout: Command timeout in seconds
            
        Returns:
            Command execution result
        """
        execution_id = str(uuid4())
        execution = CommandExecution(
            execution_id=execution_id,
            user_id=user_id,
            organization_id=organization_id,
            command=command,
            args=args,
            working_directory=working_directory or "/tmp",
            user_role=user_role,
            status="pending"
        )
        
        try:
            # Validate command permissions
            if not await self._validate_command_permission(user_role, command, args):
                execution.status = "forbidden"
                execution.stderr = f"Command '{command}' not allowed for role '{user_role}'"
                execution.return_code = 1
                await self._log_execution(execution)
                return execution
            
            # Sanitize and prepare command
            sanitized_args = await self._sanitize_arguments(command, args, user_role)
            if not sanitized_args:
                execution.status = "invalid"
                execution.stderr = "Invalid or dangerous arguments detected"
                execution.return_code = 1
                await self._log_execution(execution)
                return execution
            
            # Execute command
            execution.status = "running"
            start_time = datetime.utcnow()
            
            result = await self._execute_system_command(
                command,
                sanitized_args,
                working_directory or "/tmp",
                timeout or self.command_timeout
            )
            
            execution.completed_at = datetime.utcnow()
            execution.execution_time = (execution.completed_at - start_time).total_seconds()
            execution.return_code = result["return_code"]
            execution.stdout = result["stdout"]
            execution.stderr = result["stderr"]
            execution.status = "completed" if result["return_code"] == 0 else "failed"
            
        except Exception as e:
            execution.status = "error"
            execution.stderr = str(e)
            execution.return_code = -1
            execution.completed_at = datetime.utcnow()
            logger.error(f"Command execution error: {e}")
        
        # Log execution
        await self._log_execution(execution)
        
        return execution
    
    async def _validate_command_permission(
        self,
        user_role: str,
        command: str,
        args: List[str]
    ) -> bool:
        """Validate if user role can execute the command"""
        role_commands = self.allowed_commands.get(user_role, {})
        command_config = role_commands.get(command)
        
        if not command_config:
            return False
        
        # Check subcommands if specified
        allowed_subcommands = command_config.get("subcommands", [])
        if allowed_subcommands and args:
            first_arg = args[0]
            if first_arg not in allowed_subcommands:
                return False
        
        return True
    
    async def _sanitize_arguments(
        self,
        command: str,
        args: List[str],
        user_role: str
    ) -> Optional[List[str]]:
        """Sanitize command arguments to prevent injection attacks"""
        sanitized = []
        
        # Block dangerous patterns
        dangerous_patterns = [
            ";", "&&", "||", "|", ">", ">>", "<", "`", "$(",
            "$(", "rm -rf", "dd if=", ":(){ :|:& };:", "fork()"
        ]
        
        for arg in args:
            # Check for dangerous patterns
            if any(pattern in arg for pattern in dangerous_patterns):
                logger.warning(f"Dangerous pattern detected in argument: {arg}")
                return None
            
            # Escape shell metacharacters
            sanitized.append(shlex.quote(arg))
        
        # Command-specific validation
        if command == "cat" and user_role != "admin":
            # Restrict file access for non-admin users
            for arg in args:
                if not self._is_safe_file_path(arg):
                    logger.warning(f"Unsafe file path for user role {user_role}: {arg}")
                    return None
        
        return sanitized
    
    def _is_safe_file_path(self, path: str) -> bool:
        """Check if file path is safe for non-admin access"""
        safe_prefixes = [
            "/tmp/",
            "/var/log/erp-suite/",
            "/app/logs/",
            "/home/erp-user/"
        ]
        
        dangerous_paths = [
            "/etc/passwd",
            "/etc/shadow",
            "/root/",
            "/var/lib/",
            "/sys/",
            "/proc/"
        ]
        
        # Check if path starts with safe prefix
        if not any(path.startswith(prefix) for prefix in safe_prefixes):
            return False
        
        # Check for dangerous paths
        if any(dangerous in path for dangerous in dangerous_paths):
            return False
        
        return True
    
    async def _execute_system_command(
        self,
        command: str,
        args: List[str],
        working_directory: str,
        timeout: int
    ) -> Dict[str, Any]:
        """Execute the actual system command"""
        cmd_list = [command] + args
        
        try:
            # Create subprocess with security restrictions
            process = await asyncio.create_subprocess_exec(
                *cmd_list,
                cwd=working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=self.max_output_size
            )
            
            # Wait for completion with timeout
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            return {
                "return_code": process.returncode,
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace')
            }
            
        except asyncio.TimeoutError:
            # Kill the process if it times out
            try:
                process.kill()
                await process.wait()
            except:
                pass
            
            return {
                "return_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds"
            }
        
        except Exception as e:
            return {
                "return_code": -1,
                "stdout": "",
                "stderr": f"Execution error: {str(e)}"
            }
    
    async def _log_execution(self, execution: CommandExecution):
        """Log command execution to database"""
        try:
            mongodb = await get_mongodb()
            
            execution_doc = {
                "execution_id": execution.execution_id,
                "user_id": execution.user_id,
                "organization_id": execution.organization_id,
                "command": execution.command,
                "args": execution.args,
                "working_directory": execution.working_directory,
                "user_role": execution.user_role,
                "status": execution.status,
                "return_code": execution.return_code,
                "stdout": execution.stdout[:1000],  # Truncate for storage
                "stderr": execution.stderr[:1000],  # Truncate for storage
                "execution_time": execution.execution_time,
                "created_at": execution.created_at,
                "completed_at": execution.completed_at
            }
            
            await mongodb.command_executions.insert_one(execution_doc)
            
        except Exception as e:
            logger.error(f"Failed to log command execution: {e}")
    
    async def get_docker_containers(self, user_role: str) -> Optional[List[Dict[str, Any]]]:
        """Get Docker container information"""
        if not await self._validate_command_permission(user_role, "docker", ["ps"]):
            return None
        
        execution = await self.execute_command(
            user_id="system",
            organization_id="system",
            user_role=user_role,
            command="docker",
            args=["ps", "--format", "json"]
        )
        
        if execution.status == "completed" and execution.return_code == 0:
            try:
                containers = []
                for line in execution.stdout.strip().split('\n'):
                    if line:
                        containers.append(json.loads(line))
                return containers
            except Exception as e:
                logger.error(f"Failed to parse docker output: {e}")
        
        return None
    
    async def get_system_stats(self, user_role: str) -> Optional[Dict[str, Any]]:
        """Get system statistics"""
        stats = {}
        
        # Memory usage
        if await self._validate_command_permission(user_role, "free", []):
            mem_exec = await self.execute_command(
                user_id="system",
                organization_id="system",
                user_role=user_role,
                command="free",
                args=["-m"]
            )
            if mem_exec.status == "completed":
                stats["memory"] = mem_exec.stdout
        
        # Disk usage
        if await self._validate_command_permission(user_role, "df", []):
            disk_exec = await self.execute_command(
                user_id="system",
                organization_id="system",
                user_role=user_role,
                command="df",
                args=["-h"]
            )
            if disk_exec.status == "completed":
                stats["disk"] = disk_exec.stdout
        
        return stats if stats else None
    
    async def get_service_logs(
        self,
        service_name: str,
        user_role: str,
        lines: int = 100
    ) -> Optional[str]:
        """Get service logs"""
        if not await self._validate_command_permission(user_role, "docker", ["logs"]):
            return None
        
        execution = await self.execute_command(
            user_id="system",
            organization_id="system",
            user_role=user_role,
            command="docker",
            args=["logs", "--tail", str(lines), service_name]
        )
        
        if execution.status == "completed":
            return execution.stdout
        
        return None
    
    async def restart_service(
        self,
        service_name: str,
        user_id: str,
        organization_id: str,
        user_role: str
    ) -> bool:
        """Restart a service (admin only)"""
        if user_role != "admin":
            return False
        
        execution = await self.execute_command(
            user_id=user_id,
            organization_id=organization_id,
            user_role=user_role,
            command="docker",
            args=["restart", service_name]
        )
        
        return execution.status == "completed" and execution.return_code == 0
    
    async def get_execution_history(
        self,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get command execution history"""
        try:
            mongodb = await get_mongodb()
            
            query = {}
            if user_id:
                query["user_id"] = user_id
            if organization_id:
                query["organization_id"] = organization_id
            
            cursor = mongodb.command_executions.find(query).sort("created_at", -1).limit(limit)
            
            history = []
            async for doc in cursor:
                history.append({
                    "execution_id": doc["execution_id"],
                    "user_id": doc["user_id"],
                    "command": doc["command"],
                    "args": doc["args"],
                    "status": doc["status"],
                    "return_code": doc.get("return_code"),
                    "execution_time": doc.get("execution_time", 0),
                    "created_at": doc["created_at"].isoformat()
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Failed to get execution history: {e}")
            return []

    async def check_permissions(self, user_id: str, command: str, organization_id: str = None) -> bool:
        """Check if user has permission to execute command"""
        try:
            # Get user permissions from auth service
            permissions = await self.auth_service.get_user_permissions(user_id, organization_id)
            
            # Check command against permissions
            if "system_admin" in permissions.get("roles", []):
                return True
            
            # Check specific command permissions
            allowed_commands = permissions.get("system_commands", [])
            
            # Check if command is in allowed list or matches pattern
            for allowed in allowed_commands:
                if command.startswith(allowed):
                    return True
            
            # Default deny
            return False
            
        except Exception as e:
            logger.error(f"Error checking permissions: {e}")
            return False

    async def _audit_command_execution(self, command: str, user_id: str, result: Dict[str, Any]):
        """Audit command execution for security and compliance"""
        try:
            audit_entry = {
                "user_id": user_id,
                "command": command,
                "timestamp": datetime.utcnow().isoformat(),
                "success": result.get("success", False),
                "exit_code": result.get("exit_code"),
                "output_length": len(result.get("output", "")),
                "execution_time": result.get("execution_time", 0)
            }
            
            # Store in audit log collection
            mongodb = await get_mongodb()
            await mongodb.audit_logs.insert_one(audit_entry)
            
            logger.info(f"Command execution audited: {command} by user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to audit command execution: {e}")


# Global system command service instance
system_command_service = SystemCommandService()
