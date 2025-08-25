"""
Tool System Package

Provides a comprehensive set of tools for the UNIBASE ERP AI Copilot including:
- Base tool framework and utilities
- ERP-specific tools for business operations
- RAG tools for knowledge management
- Integration tools for external systems
- Command execution tools for infrastructure management
- Documentation tools for knowledge access
"""

from .base_tool import (
    BaseTool,
    ToolParameterType,
    ToolParameter,
    ToolRequest,
    ToolResponse,
    ToolMetadata
)

from .tool_registry import ToolRegistry

from .erp_tools import (
    ERPQueryTool,
    ERPActionTool,
    UserManagementTool,
    InventoryTool,
    FinanceTool,
    HRMTool
)

from .rag_tools import (
    DocumentSearchTool,
    KnowledgeIngestionTool,
    SemanticSearchTool
)

from .integration_tools import (
    APITool,
    DatabaseTool,
    FileSystemTool,
    EmailTool,
    CalendarTool
)

from .command_tools import (
    CommandExecutorTool,
    InfrastructureTool,
    ApplicationTool
)

from .documentation_tools import (
    DocumentationTool,
    ArchitectureTool
)

__all__ = [
    # Base framework
    "BaseTool",
    "ToolParameterType",
    "ToolParameter",
    "ToolRequest",
    "ToolResponse",
    "ToolMetadata",
    "ToolRegistry",
    
    # ERP Tools
    "ERPQueryTool",
    "ERPActionTool",
    "UserManagementTool",
    "InventoryTool",
    "FinanceTool",
    "HRMTool",
    
    # RAG Tools
    "DocumentSearchTool",
    "KnowledgeIngestionTool",
    "SemanticSearchTool",
    
    # Integration Tools
    "APITool",
    "DatabaseTool",
    "FileSystemTool",
    "EmailTool",
    "CalendarTool",
    
    # Command Tools
    "CommandExecutorTool",
    "InfrastructureTool",
    "ApplicationTool",
    
    # Documentation Tools
    "DocumentationTool",
    "ArchitectureTool"
]