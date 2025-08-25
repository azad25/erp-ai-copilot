"""
Integration Tools

Provides tools for integrating with external systems including:
- REST APIs
- Databases
- File systems
- Email services
- Calendar systems
"""

from typing import Dict, List, Optional, Any
import aiohttp
import json
import os
from datetime import datetime
from .base_tool import BaseTool, ToolRequest, ToolResponse, ToolParameter, ToolParameterType, ToolMetadata


class APITool(BaseTool):
    """Tool for making HTTP API calls"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="api_call",
            description="Make HTTP API calls to external services",
            category="Integration",
            parameters=[
                ToolParameter(
                    name="url",
                    type=ToolParameterType.URL,
                    description="API endpoint URL",
                    required=True
                ),
                ToolParameter(
                    name="method",
                    type=ToolParameterType.STRING,
                    description="HTTP method",
                    required=True,
                    enum=["GET", "POST", "PUT", "DELETE", "PATCH"]
                ),
                ToolParameter(
                    name="headers",
                    type=ToolParameterType.OBJECT,
                    description="HTTP headers",
                    required=False,
                    default={}
                ),
                ToolParameter(
                    name="body",
                    type=ToolParameterType.OBJECT,
                    description="Request body for POST/PUT/PATCH",
                    required=False
                ),
                ToolParameter(
                    name="params",
                    type=ToolParameterType.OBJECT,
                    description="URL parameters",
                    required=False,
                    default={}
                ),
                ToolParameter(
                    name="timeout",
                    type=ToolParameterType.INTEGER,
                    description="Request timeout in seconds",
                    required=False,
                    default=30
                )
            ],
            required_permissions=["api.access"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        url = request.parameters.get("url")
        method = request.parameters.get("method", "GET")
        headers = request.parameters.get("headers", {})
        body = request.parameters.get("body")
        params = request.parameters.get("params", {})
        timeout = request.parameters.get("timeout", 30)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    response_data = {
                        "status": response.status,
                        "headers": dict(response.headers),
                        "url": str(response.url)
                    }
                    
                    try:
                        response_data["data"] = await response.json()
                    except:
                        response_data["text"] = await response.text()
                    
                    return ToolResponse(
                        success=response.status < 400,
                        data=response_data
                    )
                    
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"API call failed: {str(e)}"
            )


class DatabaseTool(BaseTool):
    """Tool for database operations"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="database_query",
            description="Execute database queries and operations",
            category="Integration",
            parameters=[
                ToolParameter(
                    name="query",
                    type=ToolParameterType.STRING,
                    description="SQL query to execute",
                    required=True
                ),
                ToolParameter(
                    name="parameters",
                    type=ToolParameterType.OBJECT,
                    description="Query parameters for prepared statements",
                    required=False,
                    default={}
                ),
                ToolParameter(
                    name="operation",
                    type=ToolParameterType.STRING,
                    description="Database operation type",
                    required=True,
                    enum=["select", "insert", "update", "delete", "create"]
                ),
                ToolParameter(
                    name="table",
                    type=ToolParameterType.STRING,
                    description="Target table name",
                    required=False
                ),
                ToolParameter(
                    name="data",
                    type=ToolParameterType.OBJECT,
                    description="Data for insert/update operations",
                    required=False
                )
            ],
            required_permissions=["database.access"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        query = request.parameters.get("query")
        operation = request.parameters.get("operation", "select")
        parameters = request.parameters.get("parameters", {})
        table = request.parameters.get("table")
        data = request.parameters.get("data", {})
        
        try:
            # Mock database operations - replace with actual database integration
            mock_data = {
                "select": [
                    {"id": 1, "name": "Test User", "email": "test@example.com", "created_at": "2024-01-15"},
                    {"id": 2, "name": "Another User", "email": "another@example.com", "created_at": "2024-01-14"}
                ],
                "insert": {"id": 3, "message": "Record inserted successfully"},
                "update": {"affected_rows": 1, "message": "Record updated successfully"},
                "delete": {"affected_rows": 1, "message": "Record deleted successfully"},
                "create": {"message": "Table created successfully"}
            }
            
            result = mock_data.get(operation, [])
            
            return ToolResponse(
                success=True,
                data=result,
                metadata={
                    "operation": operation,
                    "query": query,
                    "parameters_count": len(parameters),
                    "affected_rows": len(result) if isinstance(result, list) else 1
                }
            )
            
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Database operation failed: {str(e)}"
            )


class FileSystemTool(BaseTool):
    """Tool for file system operations"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="filesystem_operations",
            description="Perform file system operations like read, write, list, and delete",
            category="Integration",
            parameters=[
                ToolParameter(
                    name="operation",
                    type=ToolParameterType.STRING,
                    description="File system operation",
                    required=True,
                    enum=["read", "write", "list", "delete", "create_dir", "exists"]
                ),
                ToolParameter(
                    name="path",
                    type=ToolParameterType.STRING,
                    description="File or directory path",
                    required=True
                ),
                ToolParameter(
                    name="content",
                    type=ToolParameterType.STRING,
                    description="Content to write (for write operations)",
                    required=False
                ),
                ToolParameter(
                    name="recursive",
                    type=ToolParameterType.BOOLEAN,
                    description="Recursive listing (for list operations)",
                    required=False,
                    default=False
                ),
                ToolParameter(
                    name="encoding",
                    type=ToolParameterType.STRING,
                    description="File encoding",
                    required=False,
                    default="utf-8"
                )
            ],
            required_permissions=["filesystem.access"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        operation = request.parameters.get("operation")
        path = request.parameters.get("path")
        content = request.parameters.get("content", "")
        recursive = request.parameters.get("recursive", False)
        encoding = request.parameters.get("encoding", "utf-8")
        
        try:
            # Mock file system operations - replace with actual file system access
            mock_filesystem = {
                "/tmp/test.txt": {
                    "name": "test.txt",
                    "content": "This is a test file content",
                    "size": 28,
                    "modified": "2024-01-15T10:30:00"
                },
                "/tmp/documents": [
                    {"name": "report.pdf", "type": "file", "size": 1024000},
                    {"name": "data.csv", "type": "file", "size": 20480},
                    {"name": "images", "type": "directory"}
                ]
            }
            
            if operation == "read":
                if path in mock_filesystem:
                    data = {"content": mock_filesystem[path]["content"]}
                else:
                    data = {"error": "File not found"}
            
            elif operation == "write":
                data = {"message": f"File written successfully to {path}", "bytes_written": len(content.encode(encoding))}
            
            elif operation == "list":
                if path in mock_filesystem:
                    data = {"files": mock_filesystem[path]}
                else:
                    data = {"files": []}
            
            elif operation == "exists":
                data = {"exists": path in mock_filesystem}
            
            else:
                data = {"message": f"Operation {operation} completed on {path}"}
            
            return ToolResponse(
                success=True,
                data=data
            )
            
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"File system operation failed: {str(e)}"
            )


class EmailTool(BaseTool):
    """Tool for email operations"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="email_operations",
            description="Send emails and manage email communications",
            category="Integration",
            parameters=[
                ToolParameter(
                    name="operation",
                    type=ToolParameterType.STRING,
                    description="Email operation",
                    required=True,
                    enum=["send", "schedule", "get_templates", "list_sent"]
                ),
                ToolParameter(
                    name="to",
                    type=ToolParameterType.EMAIL,
                    description="Recipient email address",
                    required=False
                ),
                ToolParameter(
                    name="subject",
                    type=ToolParameterType.STRING,
                    description="Email subject",
                    required=False
                ),
                ToolParameter(
                    name="body",
                    type=ToolParameterType.STRING,
                    description="Email body content",
                    required=False
                ),
                ToolParameter(
                    name="template",
                    type=ToolParameterType.STRING,
                    description="Email template name",
                    required=False
                ),
                ToolParameter(
                    name="variables",
                    type=ToolParameterType.OBJECT,
                    description="Template variables",
                    required=False,
                    default={}
                )
            ],
            required_permissions=["email.send"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        operation = request.parameters.get("operation")
        
        try:
            # Mock email operations
            if operation == "send":
                to_email = request.parameters.get("to")
                subject = request.parameters.get("subject")
                body = request.parameters.get("body")
                
                data = {
                    "message": "Email sent successfully",
                    "to": to_email,
                    "subject": subject,
                    "message_id": f"msg_{hash(to_email + subject) % 10000:06d}",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            elif operation == "get_templates":
                data = [
                    {"name": "welcome", "description": "Welcome new employee email"},
                    {"name": "meeting_reminder", "description": "Meeting reminder template"},
                    {"name": "report_notification", "description": "Weekly report notification"}
                ]
            
            elif operation == "list_sent":
                data = [
                    {"to": "user1@company.com", "subject": "Welcome to the team", "date": "2024-01-15"},
                    {"to": "user2@company.com", "subject": "Meeting reminder", "date": "2024-01-14"}
                ]
            
            else:
                data = {"operation": operation, "status": "completed"}
            
            return ToolResponse(
                success=True,
                data=data
            )
            
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Email operation failed: {str(e)}"
            )


class CalendarTool(BaseTool):
    """Tool for calendar operations"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="calendar_operations",
            description="Manage calendar events and scheduling",
            category="Integration",
            parameters=[
                ToolParameter(
                    name="operation",
                    type=ToolParameterType.STRING,
                    description="Calendar operation",
                    required=True,
                    enum=["create_event", "list_events", "update_event", "delete_event", "get_availability"]
                ),
                ToolParameter(
                    name="event_data",
                    type=ToolParameterType.OBJECT,
                    description="Event data for create/update operations",
                    required=False
                ),
                ToolParameter(
                    name="start_date",
                    type=ToolParameterType.DATETIME,
                    description="Start date for listing events",
                    required=False
                ),
                ToolParameter(
                    name="end_date",
                    type=ToolParameterType.DATETIME,
                    description="End date for listing events",
                    required=False
                ),
                ToolParameter(
                    name="attendees",
                    type=ToolParameterType.ARRAY,
                    description="List of attendee email addresses",
                    required=False,
                    default=[]
                )
            ],
            required_permissions=["calendar.manage"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        operation = request.parameters.get("operation")
        
        try:
            # Mock calendar operations
            if operation == "list_events":
                data = [
                    {
                        "id": "evt_001",
                        "title": "Team Meeting",
                        "start": "2024-01-15T10:00:00",
                        "end": "2024-01-15T11:00:00",
                        "attendees": ["user1@company.com", "user2@company.com"],
                        "location": "Conference Room A"
                    },
                    {
                        "id": "evt_002",
                        "title": "Project Review",
                        "start": "2024-01-16T14:00:00",
                        "end": "2024-01-16T15:30:00",
                        "attendees": ["user1@company.com"],
                        "location": "Virtual"
                    }
                ]
            
            elif operation == "get_availability":
                data = {
                    "available_slots": [
                        {"start": "2024-01-15T09:00:00", "end": "2024-01-15T10:00:00"},
                        {"start": "2024-01-15T11:30:00", "end": "2024-01-15T12:30:00"}
                    ],
                    "busy_slots": [
                        {"start": "2024-01-15T10:00:00", "end": "2024-01-15T11:00:00"}
                    ]
                }
            
            else:
                data = {"operation": operation, "status": "completed"}
            
            return ToolResponse(
                success=True,
                data=data
            )
            
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Calendar operation failed: {str(e)}"
            )