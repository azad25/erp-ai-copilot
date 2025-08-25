"""
Command execution layer for infrastructure and host management.
"""
import asyncio
import subprocess
import shlex
import os
import signal
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import structlog
from .exceptions import AICopilotException, AuthorizationError, ValidationError

logger = structlog.get_logger(__name__)


class CommandType(Enum):
    """Types of commands that can be executed."""
    SYSTEM = "system"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    DATABASE = "database"
    NETWORK = "network"
    MONITORING = "monitoring"
    BACKUP = "backup"
    SECURITY = "security"
    CUSTOM = "custom"


class ExecutionLevel(Enum):
    """Execution privilege levels."""
    USER = "user"
    ELEVATED = "elevated"
    ROOT = "root"
    CONTAINER = "container"


@dataclass
class CommandResult:
    """Result of command execution."""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float
    command: str
    command_type: CommandType
    execution_level: ExecutionLevel
    metadata: Dict[str, Any]


class CommandExecutor:
    """Secure command execution system."""
    
    def __init__(self):
        self.allowed_commands: Dict[CommandType, List[str]] = {
            CommandType.SYSTEM: [
                "ps", "top", "htop", "df", "du", "free", "uptime", "who", "w",
                "ls", "cat", "head", "tail", "grep", "find", "stat", "file",
                "date", "cal", "bc", "echo", "printf", "seq", "shuf"
            ],
            CommandType.DOCKER: [
                "docker", "docker-compose", "docker system", "docker info",
                "docker stats", "docker logs", "docker ps", "docker images"
            ],
            CommandType.DATABASE: [
                "psql", "mysql", "mongosh", "redis-cli", "sqlite3"
            ],
            CommandType.NETWORK: [
                "ping", "traceroute", "netstat", "ss", "ip", "ifconfig",
                "curl", "wget", "telnet", "nc", "nslookup", "dig"
            ],
            CommandType.MONITORING: [
                "htop", "iotop", "nethogs", "iftop", "atop", "dstat"
            ]
        }
        
        self.blocked_patterns: List[str] = [
            "rm -rf", "dd if=", "mkfs", "fdisk", "parted",
            "chmod 777", "chown root", "passwd", "useradd",
            "systemctl", "service", "init", "telinit"
        ]
        
        self.max_execution_time = 300  # 5 minutes
        self.max_output_size = 10 * 1024 * 1024  # 10MB
        
    async def execute_command(
        self,
        command: str,
        command_type: CommandType = CommandType.SYSTEM,
        execution_level: ExecutionLevel = ExecutionLevel.USER,
        timeout: Optional[int] = None,
        working_dir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        user_id: Optional[str] = None
    ) -> CommandResult:
        """Execute a command with security checks."""
        
        start_time = time.time()
        
        try:
            # Security validation
            self._validate_command(command, command_type, execution_level)
            
            # Prepare execution environment
            exec_env = self._prepare_environment(environment, user_id)
            exec_timeout = timeout or self.max_execution_time
            
            # Execute command
            result = await self._execute_async(
                command, exec_env, exec_timeout, working_dir
            )
            
            execution_time = time.time() - start_time
            
            return CommandResult(
                success=result["success"],
                exit_code=result["exit_code"],
                stdout=result["stdout"],
                stderr=result["stderr"],
                execution_time=execution_time,
                command=command,
                command_type=command_type,
                execution_level=execution_level,
                metadata=result.get("metadata", {})
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error("Command execution failed", command=command, error=str(e))
            
            return CommandResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                execution_time=execution_time,
                command=command,
                command_type=command_type,
                execution_level=execution_level,
                metadata={"error": str(e)}
            )
    
    def _validate_command(
        self, 
        command: str, 
        command_type: CommandType, 
        execution_level: ExecutionLevel
    ) -> None:
        """Validate command for security and permissions."""
        
        # Check blocked patterns
        for pattern in self.blocked_patterns:
            if pattern in command.lower():
                raise ValidationError(
                    f"Command blocked due to dangerous pattern: {pattern}",
                    details={"command": command, "blocked_pattern": pattern}
                )
        
        # Check allowed commands for type
        if command_type in self.allowed_commands:
            allowed = self.allowed_commands[command_type]
            command_base = command.split()[0]
            
            if not any(command_base.startswith(allowed_cmd) for allowed_cmd in allowed):
                raise ValidationError(
                    f"Command not allowed for type {command_type}",
                    details={"command": command, "command_type": command_type}
                )
        
        # Check execution level permissions
        if execution_level == ExecutionLevel.ROOT:
            if not self._has_root_permissions():
                raise AuthorizationError(
                    "Root execution level requires elevated permissions",
                    details={"execution_level": execution_level}
                )
    
    def _has_root_permissions(self) -> bool:
        """Check if current process has root permissions."""
        return os.geteuid() == 0
    
    def _prepare_environment(
        self, 
        environment: Optional[Dict[str, str]], 
        user_id: Optional[str]
    ) -> Dict[str, str]:
        """Prepare execution environment."""
        env = os.environ.copy()
        
        if environment:
            env.update(environment)
        
        # Set safe defaults
        env.update({
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "TERM": "xterm-256color",
            "LANG": "en_US.UTF-8",
            "LC_ALL": "en_US.UTF-8"
        })
        
        return env
    
    async def _execute_async(
        self,
        command: str,
        environment: Dict[str, str],
        timeout: int,
        working_dir: Optional[str]
    ) -> Dict[str, Any]:
        """Execute command asynchronously."""
        
        try:
            # Parse command
            if isinstance(command, str):
                cmd_parts = shlex.split(command)
            else:
                cmd_parts = command
            
            # Create process
            process = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=environment,
                cwd=working_dir,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            
            # Execute with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                # Kill process group on timeout
                if os.name != 'nt':
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                else:
                    process.terminate()
                
                await asyncio.sleep(1)
                if process.returncode is None:
                    if os.name != 'nt':
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    else:
                        process.kill()
                
                raise ValidationError(
                    f"Command execution timed out after {timeout} seconds",
                    details={"command": command, "timeout": timeout}
                )
            
            # Decode output
            stdout_str = stdout.decode('utf-8', errors='replace')
            stderr_str = stderr.decode('utf-8', errors='replace')
            
            # Check output size limits
            if len(stdout_str) > self.max_output_size:
                stdout_str = stdout_str[:self.max_output_size] + "\n... [truncated]"
            
            if len(stderr_str) > self.max_output_size:
                stderr_str = stderr_str[:self.max_output_size] + "\n... [truncated]"
            
            return {
                "success": process.returncode == 0,
                "exit_code": process.returncode or 0,
                "stdout": stdout_str,
                "stderr": stderr_str,
                "metadata": {
                    "pid": process.pid,
                    "command_parts": cmd_parts
                }
            }
            
        except Exception as e:
            logger.error("Async command execution failed", command=command, error=str(e))
            raise
    
    async def execute_docker_command(
        self, 
        command: str, 
        timeout: Optional[int] = None
    ) -> CommandResult:
        """Execute Docker-related commands."""
        return await self.execute_command(
            command, 
            CommandType.DOCKER, 
            ExecutionLevel.USER, 
            timeout
        )
    
    async def execute_database_command(
        self, 
        command: str, 
        timeout: Optional[int] = None
    ) -> CommandResult:
        """Execute database-related commands."""
        return await self.execute_command(
            command, 
            CommandType.DATABASE, 
            ExecutionLevel.USER, 
            timeout
        )
    
    async def execute_network_command(
        self, 
        command: str, 
        timeout: Optional[int] = None
    ) -> CommandResult:
        """Execute network-related commands."""
        return await self.execute_command(
            command, 
            CommandType.NETWORK, 
            ExecutionLevel.USER, 
            timeout
        )
    
    async def execute_monitoring_command(
        self, 
        command: str, 
        timeout: Optional[int] = None
    ) -> CommandResult:
        """Execute monitoring commands."""
        return await self.execute_command(
            command, 
            CommandType.MONITORING, 
            ExecutionLevel.USER, 
            timeout
        )
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get basic system information."""
        try:
            info = {}
            
            # OS info
            info["os"] = {
                "name": os.name,
                "platform": os.platform,
                "release": os.uname().release if hasattr(os, 'uname') else "unknown"
            }
            
            # User info
            info["user"] = {
                "uid": os.getuid(),
                "gid": os.getgid(),
                "username": os.getlogin(),
                "home": os.path.expanduser("~")
            }
            
            # Process info
            info["process"] = {
                "pid": os.getpid(),
                "ppid": os.getppid(),
                "cwd": os.getcwd()
            }
            
            return info
            
        except Exception as e:
            logger.error("Failed to get system info", error=str(e))
            return {"error": str(e)}
    
    def get_allowed_commands(self) -> Dict[str, List[str]]:
        """Get list of allowed commands by type."""
        return {cmd_type.value: commands for cmd_type, commands in self.allowed_commands.items()}
    
    def add_allowed_command(self, command_type: CommandType, command: str) -> None:
        """Add a new allowed command."""
        if command_type not in self.allowed_commands:
            self.allowed_commands[command_type] = []
        
        if command not in self.allowed_commands[command_type]:
            self.allowed_commands[command_type].append(command)
            logger.info("Added allowed command", command_type=command_type.value, command=command)
    
    def remove_allowed_command(self, command_type: CommandType, command: str) -> None:
        """Remove an allowed command."""
        if command_type in self.allowed_commands and command in self.allowed_commands[command_type]:
            self.allowed_commands[command_type].remove(command)
            logger.info("Removed allowed command", command_type=command_type.value, command=command)
    
    def add_blocked_pattern(self, pattern: str) -> None:
        """Add a new blocked pattern."""
        if pattern not in self.blocked_patterns:
            self.blocked_patterns.append(pattern)
            logger.info("Added blocked pattern", pattern=pattern)
    
    def remove_blocked_pattern(self, pattern: str) -> None:
        """Remove a blocked pattern."""
        if pattern in self.blocked_patterns:
            self.blocked_patterns.remove(pattern)
            logger.info("Removed blocked pattern", pattern=pattern)
