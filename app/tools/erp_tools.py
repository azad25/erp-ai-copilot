"""
ERP System Integration Tools

Provides tools for interacting with various ERP modules including:
- User management
- Inventory management  
- Finance operations
- Human resources
- Sales and CRM
"""

from typing import Dict, List, Optional, Any
import aiohttp
import json
from datetime import datetime
from .base_tool import BaseTool, ToolRequest, ToolResponse, ToolParameter, ToolParameterType, ToolMetadata


class ERPQueryTool(BaseTool):
    """Tool for querying ERP system data"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="erp_query",
            description="Query ERP system for data across different modules",
            category="ERP",
            parameters=[
                ToolParameter(
                    name="module",
                    type=ToolParameterType.STRING,
                    description="ERP module to query (users, inventory, finance, hr, sales)",
                    required=True,
                    enum=["users", "inventory", "finance", "hr", "sales", "crm", "projects"]
                ),
                ToolParameter(
                    name="query_type",
                    type=ToolParameterType.STRING,
                    description="Type of query (list, get, search, aggregate)",
                    required=True,
                    enum=["list", "get", "search", "aggregate", "report"]
                ),
                ToolParameter(
                    name="filters",
                    type=ToolParameterType.OBJECT,
                    description="Query filters and conditions",
                    required=False,
                    default={}
                ),
                ToolParameter(
                    name="fields",
                    type=ToolParameterType.ARRAY,
                    description="Fields to include in response",
                    required=False,
                    default=None
                ),
                ToolParameter(
                    name="limit",
                    type=ToolParameterType.INTEGER,
                    description="Maximum number of results",
                    required=False,
                    default=100
                )
            ],
            required_permissions=["erp.read"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        module = request.parameters.get("module")
        query_type = request.parameters.get("query_type")
        filters = request.parameters.get("filters", {})
        fields = request.parameters.get("fields")
        limit = request.parameters.get("limit", 100)
        
        try:
            # Mock ERP API call - replace with actual ERP integration
            base_url = "http://localhost:8001/api/v1"
            
            if query_type == "list":
                data = await self._get_list_data(module, filters, limit)
            elif query_type == "get":
                data = await self._get_single_item(module, filters)
            elif query_type == "search":
                data = await self._search_data(module, filters, limit)
            elif query_type == "aggregate":
                data = await self._aggregate_data(module, filters)
            else:
                data = await self._generate_report(module, filters)
            
            return ToolResponse(
                success=True,
                data=data,
                metadata={
                    "module": module,
                    "query_type": query_type,
                    "record_count": len(data) if isinstance(data, list) else 1
                }
            )
            
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"ERP query failed: {str(e)}"
            )
    
    async def _get_list_data(self, module: str, filters: Dict, limit: int) -> List[Dict]:
        """Get list data from ERP module"""
        # Mock data - replace with actual ERP API calls
        mock_data = {
            "users": [
                {"id": 1, "name": "John Doe", "email": "john@company.com", "department": "Sales", "role": "Manager"},
                {"id": 2, "name": "Jane Smith", "email": "jane@company.com", "department": "Finance", "role": "Analyst"},
                {"id": 3, "name": "Bob Johnson", "email": "bob@company.com", "department": "IT", "role": "Developer"}
            ],
            "inventory": [
                {"id": 101, "name": "Laptop Dell XPS", "quantity": 50, "price": 1299.99, "category": "Electronics"},
                {"id": 102, "name": "Office Chair", "quantity": 100, "price": 299.99, "category": "Furniture"},
                {"id": 103, "name": "Printer HP", "quantity": 25, "price": 449.99, "category": "Electronics"}
            ],
            "finance": [
                {"id": 1, "type": "invoice", "amount": 5000.0, "status": "paid", "date": "2024-01-15"},
                {"id": 2, "type": "expense", "amount": 1200.0, "status": "pending", "date": "2024-01-20"},
                {"id": 3, "type": "revenue", "amount": 8000.0, "status": "confirmed", "date": "2024-01-18"}
            ]
        }
        
        data = mock_data.get(module, [])
        
        # Apply filters
        if filters:
            filtered_data = []
            for item in data:
                match = True
                for key, value in filters.items():
                    if key in item and item[key] != value:
                        match = False
                        break
                if match:
                    filtered_data.append(item)
            data = filtered_data
        
        return data[:limit]
    
    async def _get_single_item(self, module: str, filters: Dict) -> Dict:
        """Get single item from ERP module"""
        items = await self._get_list_data(module, filters, 1)
        return items[0] if items else {}
    
    async def _search_data(self, module: str, filters: Dict, limit: int) -> List[Dict]:
        """Search data in ERP module"""
        # Implement search logic
        return await self._get_list_data(module, {}, limit)
    
    async def _aggregate_data(self, module: str, filters: Dict) -> Dict:
        """Aggregate data from ERP module"""
        data = await self._get_list_data(module, filters, 1000)
        
        if module == "finance":
            total_amount = sum(item.get("amount", 0) for item in data)
            return {
                "total_records": len(data),
                "total_amount": total_amount,
                "average_amount": total_amount / len(data) if data else 0
            }
        elif module == "inventory":
            total_value = sum(item.get("quantity", 0) * item.get("price", 0) for item in data)
            return {
                "total_items": len(data),
                "total_value": total_value,
                "total_quantity": sum(item.get("quantity", 0) for item in data)
            }
        
        return {"total_records": len(data)}
    
    async def _generate_report(self, module: str, filters: Dict) -> Dict:
        """Generate report from ERP module"""
        return await self._aggregate_data(module, filters)


class ERPActionTool(BaseTool):
    """Tool for performing actions in ERP system"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="erp_action",
            description="Perform actions in ERP system (create, update, delete)",
            category="ERP",
            parameters=[
                ToolParameter(
                    name="action",
                    type=ToolParameterType.STRING,
                    description="Action to perform (create, update, delete, approve)",
                    required=True,
                    enum=["create", "update", "delete", "approve", "reject", "cancel"]
                ),
                ToolParameter(
                    name="module",
                    type=ToolParameterType.STRING,
                    description="ERP module to target",
                    required=True,
                    enum=["users", "inventory", "finance", "hr", "sales", "projects"]
                ),
                ToolParameter(
                    name="data",
                    type=ToolParameterType.OBJECT,
                    description="Data for the action",
                    required=True
                ),
                ToolParameter(
                    name="id",
                    type=ToolParameterType.INTEGER,
                    description="ID of record to update/delete",
                    required=False
                )
            ],
            required_permissions=["erp.write"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        action = request.parameters.get("action")
        module = request.parameters.get("module")
        data = request.parameters.get("data", {})
        record_id = request.parameters.get("id")
        
        try:
            # Mock ERP action - replace with actual ERP integration
            result = {
                "action": action,
                "module": module,
                "success": True,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if action == "create":
                result["id"] = 1000 + hash(str(data)) % 1000  # Mock ID generation
                result["message"] = f"Created new {module} record"
            elif action == "update":
                result["id"] = record_id
                result["message"] = f"Updated {module} record {record_id}"
            elif action == "delete":
                result["id"] = record_id
                result["message"] = f"Deleted {module} record {record_id}"
            
            return ToolResponse(
                success=True,
                data=result
            )
            
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"ERP action failed: {str(e)}"
            )


class UserManagementTool(BaseTool):
    """Tool for user management operations"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="user_management",
            description="Manage users, roles, and permissions in the ERP system",
            category="ERP",
            parameters=[
                ToolParameter(
                    name="operation",
                    type=ToolParameterType.STRING,
                    description="User management operation",
                    required=True,
                    enum=["create_user", "update_user", "delete_user", "assign_role", "list_users", "get_permissions"]
                ),
                ToolParameter(
                    name="user_data",
                    type=ToolParameterType.OBJECT,
                    description="User data for create/update operations",
                    required=False
                ),
                ToolParameter(
                    name="user_id",
                    type=ToolParameterType.INTEGER,
                    description="User ID for specific operations",
                    required=False
                ),
                ToolParameter(
                    name="role",
                    type=ToolParameterType.STRING,
                    description="Role to assign",
                    required=False,
                    enum=["admin", "manager", "analyst", "user", "viewer"]
                )
            ],
            required_permissions=["user.manage"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        operation = request.parameters.get("operation")
        
        try:
            # Mock user management operations
            if operation == "list_users":
                data = [
                    {"id": 1, "name": "Admin User", "email": "admin@company.com", "role": "admin", "active": True},
                    {"id": 2, "name": "Sales Manager", "email": "sales@company.com", "role": "manager", "active": True},
                    {"id": 3, "name": "Finance Analyst", "email": "finance@company.com", "role": "analyst", "active": True}
                ]
            elif operation == "get_permissions":
                data = {
                    "admin": ["all"],
                    "manager": ["read", "write", "approve"],
                    "analyst": ["read", "analyze"],
                    "user": ["read"],
                    "viewer": ["read"]
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
                error=f"User management failed: {str(e)}"
            )


class InventoryTool(BaseTool):
    """Tool for inventory management"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="inventory_management",
            description="Manage inventory items, stock levels, and procurement",
            category="ERP",
            parameters=[
                ToolParameter(
                    name="action",
                    type=ToolParameterType.STRING,
                    description="Inventory action",
                    required=True,
                    enum=["check_stock", "update_quantity", "add_item", "remove_item", "low_stock_alert"]
                ),
                ToolParameter(
                    name="item_id",
                    type=ToolParameterType.INTEGER,
                    description="Item ID",
                    required=False
                ),
                ToolParameter(
                    name="quantity",
                    type=ToolParameterType.INTEGER,
                    description="Quantity for stock updates",
                    required=False
                ),
                ToolParameter(
                    name="item_data",
                    type=ToolParameterType.OBJECT,
                    description="Item data for new inventory items",
                    required=False
                )
            ],
            required_permissions=["inventory.manage"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        action = request.parameters.get("action")
        
        try:
            # Mock inventory operations
            if action == "check_stock":
                data = [
                    {"item_id": 101, "name": "Laptop", "current_stock": 45, "min_stock": 10},
                    {"item_id": 102, "name": "Mouse", "current_stock": 150, "min_stock": 20},
                    {"item_id": 103, "name": "Keyboard", "current_stock": 5, "min_stock": 10, "alert": "low_stock"}
                ]
            elif action == "low_stock_alert":
                data = [
                    {"item_id": 103, "name": "Keyboard", "current_stock": 5, "min_stock": 10}
                ]
            else:
                data = {"action": action, "status": "completed"}
            
            return ToolResponse(
                success=True,
                data=data
            )
            
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Inventory management failed: {str(e)}"
            )


class FinanceTool(BaseTool):
    """Tool for finance operations"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="finance_operations",
            description="Perform finance operations like invoicing, expense tracking, and reporting",
            category="ERP",
            parameters=[
                ToolParameter(
                    name="operation",
                    type=ToolParameterType.STRING,
                    description="Finance operation",
                    required=True,
                    enum=["create_invoice", "record_expense", "generate_report", "get_balance", "list_transactions"]
                ),
                ToolParameter(
                    name="finance_data",
                    type=ToolParameterType.OBJECT,
                    description="Data for finance operations",
                    required=False
                ),
                ToolParameter(
                    name="date_range",
                    type=ToolParameterType.OBJECT,
                    description="Date range for reports",
                    required=False
                )
            ],
            required_permissions=["finance.manage"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        operation = request.parameters.get("operation")
        
        try:
            # Mock finance operations
            if operation == "get_balance":
                data = {
                    "total_balance": 125000.50,
                    "accounts": [
                        {"name": "Operating", "balance": 75000.25},
                        {"name": "Savings", "balance": 50000.25}
                    ]
                }
            elif operation == "list_transactions":
                data = [
                    {"id": 1, "type": "income", "amount": 5000.0, "description": "Client payment", "date": "2024-01-15"},
                    {"id": 2, "type": "expense", "amount": -1200.0, "description": "Office supplies", "date": "2024-01-14"}
                ]
            elif operation == "generate_report":
                data = {
                    "total_income": 25000.0,
                    "total_expenses": 15000.0,
                    "net_profit": 10000.0,
                    "report_period": "January 2024"
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
                error=f"Finance operation failed: {str(e)}"
            )


class HRMTool(BaseTool):
    """Tool for Human Resources Management"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="hrm_operations",
            description="Manage HR operations like employee records, leave requests, and payroll",
            category="ERP",
            parameters=[
                ToolParameter(
                    name="operation",
                    type=ToolParameterType.STRING,
                    description="HR operation",
                    required=True,
                    enum=["list_employees", "get_employee", "request_leave", "process_payroll", "list_departments"]
                ),
                ToolParameter(
                    name="employee_id",
                    type=ToolParameterType.INTEGER,
                    description="Employee ID",
                    required=False
                ),
                ToolParameter(
                    name="leave_data",
                    type=ToolParameterType.OBJECT,
                    description="Leave request data",
                    required=False
                )
            ],
            required_permissions=["hr.manage"]
        )
    
    async def execute(self, request: ToolRequest) -> ToolResponse:
        operation = request.parameters.get("operation")
        
        try:
            # Mock HR operations
            if operation == "list_employees":
                data = [
                    {"id": 1, "name": "Alice Johnson", "department": "Engineering", "position": "Senior Developer", "salary": 95000},
                    {"id": 2, "name": "Bob Williams", "department": "Sales", "position": "Sales Manager", "salary": 85000},
                    {"id": 3, "name": "Carol Davis", "department": "HR", "position": "HR Director", "salary": 90000}
                ]
            elif operation == "list_departments":
                data = [
                    {"name": "Engineering", "employee_count": 25, "budget": 2500000},
                    {"name": "Sales", "employee_count": 15, "budget": 1800000},
                    {"name": "HR", "employee_count": 5, "budget": 500000}
                ]
            elif operation == "get_employee":
                employee_id = request.parameters.get("employee_id")
                data = {"id": employee_id, "name": "Alice Johnson", "department": "Engineering", "position": "Senior Developer"}
            else:
                data = {"operation": operation, "status": "completed"}
            
            return ToolResponse(
                success=True,
                data=data
            )
            
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"HR operation failed: {str(e)}"
            )