"""
Code Executor

Executes generated code in a secure sandbox environment.
Implements security validation and resource limits.
"""

from typing import Dict, Any, Optional
import structlog
import asyncio
import sys
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

logger = structlog.get_logger(__name__)


class CodeExecutor:
    """
    Secure code execution engine
    
    Executes generated Python code with:
    - Security validation
    - Resource limits
    - Sandboxing (Docker in production)
    """
    
    def __init__(self):
        self.sandbox = None
        self.security_validator = None
        self.use_docker = False  # Set to True for production
        
    async def initialize(self):
        """Initialize code executor"""
        from ..sandbox.security_rules import SecurityValidator
        
        self.security_validator = SecurityValidator()
        
        # Initialize Docker sandbox if enabled
        if self.use_docker:
            from ..sandbox.docker_sandbox import DockerSandbox
            self.sandbox = DockerSandbox()
            await self.sandbox.initialize()
            logger.info("Docker sandbox initialized")
        else:
            logger.info("Using local execution (development mode)")
    
    async def execute(
        self,
        code: str,
        user_context: Dict[str, Any],
        execution_id: str,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Execute code securely
        
        Args:
            code: Python code to execute
            user_context: User context for permissions
            execution_id: Unique execution ID
            timeout: Execution timeout in seconds
            
        Returns:
            Execution result with output and metadata
        """
        logger.info(
            "Executing code",
            execution_id=execution_id,
            code_length=len(code),
            use_docker=self.use_docker
        )
        
        try:
            # Step 1: Validate code security
            is_safe, violations = self.security_validator.validate(code)
            
            if not is_safe:
                logger.warning(
                    "Code validation failed",
                    execution_id=execution_id,
                    violations=violations
                )
                return {
                    "success": False,
                    "error": "Code validation failed",
                    "violations": violations,
                    "execution_id": execution_id
                }
            
            # Step 2: Execute code
            if self.use_docker:
                result = await self._execute_in_docker(
                    code=code,
                    user_context=user_context,
                    timeout=timeout
                )
            else:
                result = await self._execute_locally(
                    code=code,
                    user_context=user_context,
                    timeout=timeout
                )
            
            result["execution_id"] = execution_id
            
            logger.info(
                "Code execution completed",
                execution_id=execution_id,
                success=result.get("success", False)
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Code execution failed",
                execution_id=execution_id,
                error=str(e)
            )
            return {
                "success": False,
                "error": str(e),
                "execution_id": execution_id
            }
    
    async def _execute_locally(
        self,
        code: str,
        user_context: Dict[str, Any],
        timeout: int
    ) -> Dict[str, Any]:
        """
        Execute code locally (development mode)
        
        WARNING: This is for development only. Use Docker sandbox in production.
        """
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        
        try:
            # Create execution namespace
            namespace = {
                "__builtins__": __builtins__,
                "user_context": user_context,
            }
            
            # Execute with timeout
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                # Use asyncio.wait_for for timeout
                await asyncio.wait_for(
                    self._run_code(code, namespace),
                    timeout=timeout
                )
            
            stdout_output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()
            
            return {
                "success": True,
                "output": stdout_output,
                "error_output": stderr_output,
                "exit_code": 0
            }
            
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Execution timeout ({timeout}s)",
                "output": stdout_capture.getvalue(),
                "error_output": stderr_capture.getvalue()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "output": stdout_capture.getvalue(),
                "error_output": stderr_capture.getvalue()
            }
    
    async def _run_code(self, code: str, namespace: Dict):
        """Run code in namespace"""
        exec(code, namespace)
    
    async def _execute_in_docker(
        self,
        code: str,
        user_context: Dict[str, Any],
        timeout: int
    ) -> Dict[str, Any]:
        """Execute code in Docker sandbox"""
        if not self.sandbox:
            return {
                "success": False,
                "error": "Docker sandbox not initialized"
            }
        
        return await self.sandbox.execute(
            code=code,
            timeout=timeout,
            memory_limit="512m",
            cpu_limit=1.0
        )
    
    async def close(self):
        """Close executor and cleanup"""
        if self.sandbox:
            await self.sandbox.close()
