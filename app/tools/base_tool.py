"""
Base Tool System

Provides the foundational classes and interfaces for all tools in the AI Copilot system.
Implements common functionality for tool execution, validation, and monitoring.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field
from enum import Enum
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ToolParameterType(str, Enum):
    """Types of tool parameters"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    DATE = "date"
    DATETIME = "datetime"
    EMAIL = "email"
    URL = "url"


class ToolParameter(BaseModel):
    """Definition of a tool parameter"""
    name: str = Field(..., description="Parameter name")
    type: ToolParameterType = Field(..., description="Parameter type")
    description: str = Field(..., description="Parameter description")
    required: bool = Field(True, description="Whether parameter is required")
    default: Any = Field(None, description="Default value if not required")
    enum: Optional[List[str]] = Field(None, description="Allowed values for enum parameters")
    validation: Optional[Dict[str, Any]] = Field(None, description="Validation rules")


class ToolRequest(BaseModel):
    """Request object for tool execution"""
    tool_name: str = Field(..., description="Name of the tool to execute")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    context: Optional[Dict[str, Any]] = Field(None, description="Execution context")
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")


class ToolResponse(BaseModel):
    """Response object from tool execution"""
    success: bool = Field(..., description="Whether execution was successful")
    data: Any = Field(None, description="Tool output data")
    error: Optional[str] = Field(None, description="Error message if failed")
    execution_time: float = Field(0.0, description="Execution time in seconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ToolMetadata(BaseModel):
    """Metadata about a tool"""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    category: str = Field(..., description="Tool category")
    version: str = Field("1.0.0", description="Tool version")
    author: str = Field("AI Copilot Team", description="Tool author")
    parameters: List[ToolParameter] = Field(default_factory=list, description="Tool parameters")
    required_permissions: List[str] = Field(default_factory=list, description="Required permissions")
    rate_limit: Optional[int] = Field(None, description="Rate limit per minute")


class BaseTool(ABC):
    """
    Abstract base class for all tools in the system.
    
    Provides common functionality for:
    - Parameter validation
    - Execution monitoring
    - Error handling
    - Logging
    - Rate limiting
    """
    
    def __init__(self):
        self.metadata = self._get_metadata()
        self.execution_count = 0
        self.last_execution = None
        
    @abstractmethod
    def _get_metadata(self) -> ToolMetadata:
        """Get tool metadata"""
        pass
    
    @abstractmethod
    async def execute(self, request: ToolRequest) -> ToolResponse:
        """Execute the tool with given parameters"""
        pass
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate tool parameters against schema
        
        Args:
            parameters: Parameters to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        for param in self.metadata.parameters:
            if param.required and param.name not in parameters:
                return False, f"Required parameter '{param.name}' is missing"
            
            if param.name in parameters:
                value = parameters[param.name]
                
                # Type validation
                if param.type == ToolParameterType.INTEGER and not isinstance(value, int):
                    return False, f"Parameter '{param.name}' must be an integer"
                elif param.type == ToolParameterType.FLOAT and not isinstance(value, (int, float)):
                    return False, f"Parameter '{param.name}' must be a float"
                elif param.type == ToolParameterType.BOOLEAN and not isinstance(value, bool):
                    return False, f"Parameter '{param.name}' must be a boolean"
                elif param.type == ToolParameterType.STRING and not isinstance(value, str):
                    return False, f"Parameter '{param.name}' must be a string"
                
                # Enum validation
                if param.enum and value not in param.enum:
                    return False, f"Parameter '{param.name}' must be one of {param.enum}"
        
        return True, None
    
    async def _execute_with_monitoring(self, request: ToolRequest) -> ToolResponse:
        """
        Execute tool with monitoring and error handling
        
        Args:
            request: Tool execution request
            
        Returns:
            Tool response with execution details
        """
        start_time = time.time()
        correlation_id = request.correlation_id or f"tool_{int(start_time)}"
        
        logger.info(
            f"Executing tool {self.metadata.name}",
            extra={
                "tool_name": self.metadata.name,
                "correlation_id": correlation_id,
                "parameters": request.parameters
            }
        )
        
        try:
            # Validate parameters
            is_valid, error_msg = self.validate_parameters(request.parameters)
            if not is_valid:
                return ToolResponse(
                    success=False,
                    error=error_msg,
                    execution_time=time.time() - start_time
                )
            
            # Execute tool
            response = await self.execute(request)
            response.execution_time = time.time() - start_time
            
            # Update metrics
            self.execution_count += 1
            self.last_execution = datetime.utcnow()
            
            logger.info(
                f"Tool {self.metadata.name} executed successfully",
                extra={
                    "tool_name": self.metadata.name,
                    "correlation_id": correlation_id,
                    "execution_time": response.execution_time,
                    "success": response.success
                }
            )
            
            return response
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Tool {self.metadata.name} execution failed",
                extra={
                    "tool_name": self.metadata.name,
                    "correlation_id": correlation_id,
                    "error": str(e),
                    "execution_time": execution_time
                }
            )
            
            return ToolResponse(
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for documentation and validation"""
        return {
            "name": self.metadata.name,
            "description": self.metadata.description,
            "category": self.metadata.category,
            "version": self.metadata.version,
            "parameters": [
                {
                    "name": param.name,
                    "type": param.type.value,
                    "description": param.description,
                    "required": param.required,
                    "default": param.default,
                    "enum": param.enum
                }
                for param in self.metadata.parameters
            ],
            "required_permissions": self.metadata.required_permissions
        }
    
    def is_available(self) -> bool:
        """Check if tool is available for execution"""
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on tool dependencies"""
        return {
            "name": self.metadata.name,
            "status": "healthy",
            "last_check": datetime.utcnow().isoformat()
        }