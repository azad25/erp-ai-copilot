"""
RBAC Service - Role-Based Access Control

Manages permissions and access control for AI operations.
"""

import logging
from typing import Dict, List, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class Role(str, Enum):
    """User roles"""
    ADMIN = "admin"
    ORG_ADMIN = "org_admin"
    MANAGER = "manager"
    USER = "user"
    VIEWER = "viewer"


class Permission(str, Enum):
    """System permissions"""
    # Data access
    READ_ALL_DATA = "read_all_data"
    READ_OWN_DATA = "read_own_data"
    READ_DEPARTMENT_DATA = "read_department_data"
    READ_ORG_DATA = "read_org_data"
    
    # Operations
    CREATE_RECORDS = "create_records"
    UPDATE_RECORDS = "update_records"
    DELETE_RECORDS = "delete_records"
    
    # Reports and analytics
    GENERATE_REPORTS = "generate_reports"
    VIEW_ANALYTICS = "view_analytics"
    EXPORT_DATA = "export_data"
    
    # AI operations
    USE_AI_CHAT = "use_ai_chat"
    CREATE_BACKGROUND_TASKS = "create_background_tasks"
    VIEW_FORECASTS = "view_forecasts"
    
    # Organization management
    MANAGE_ORGANIZATION = "manage_organization"
    VIEW_ORG_LOGS = "view_org_logs"
    
    # System
    MANAGE_USERS = "manage_users"
    SYSTEM_COMMANDS = "system_commands"


# Role-Permission mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        Permission.READ_ALL_DATA,
        Permission.READ_ORG_DATA,
        Permission.CREATE_RECORDS,
        Permission.UPDATE_RECORDS,
        Permission.DELETE_RECORDS,
        Permission.GENERATE_REPORTS,
        Permission.VIEW_ANALYTICS,
        Permission.EXPORT_DATA,
        Permission.USE_AI_CHAT,
        Permission.CREATE_BACKGROUND_TASKS,
        Permission.VIEW_FORECASTS,
        Permission.MANAGE_ORGANIZATION,
        Permission.VIEW_ORG_LOGS,
        Permission.MANAGE_USERS,
        Permission.SYSTEM_COMMANDS,
    },
    Role.ORG_ADMIN: {
        Permission.READ_ORG_DATA,
        Permission.CREATE_RECORDS,
        Permission.UPDATE_RECORDS,
        Permission.DELETE_RECORDS,
        Permission.GENERATE_REPORTS,
        Permission.VIEW_ANALYTICS,
        Permission.EXPORT_DATA,
        Permission.USE_AI_CHAT,
        Permission.CREATE_BACKGROUND_TASKS,
        Permission.VIEW_FORECASTS,
        Permission.MANAGE_ORGANIZATION,
        Permission.VIEW_ORG_LOGS,
        Permission.MANAGE_USERS,
    },
    Role.MANAGER: {
        Permission.READ_DEPARTMENT_DATA,
        Permission.CREATE_RECORDS,
        Permission.UPDATE_RECORDS,
        Permission.GENERATE_REPORTS,
        Permission.VIEW_ANALYTICS,
        Permission.EXPORT_DATA,
        Permission.USE_AI_CHAT,
        Permission.CREATE_BACKGROUND_TASKS,
        Permission.VIEW_FORECASTS,
    },
    Role.USER: {
        Permission.READ_OWN_DATA,
        Permission.CREATE_RECORDS,
        Permission.UPDATE_RECORDS,
        Permission.USE_AI_CHAT,
        Permission.VIEW_ANALYTICS,
    },
    Role.VIEWER: {
        Permission.READ_OWN_DATA,
        Permission.USE_AI_CHAT,
        Permission.VIEW_ANALYTICS,
    },
}


class RBACService:
    """RBAC service for permission management"""
    
    def __init__(self):
        self.role_permissions = ROLE_PERMISSIONS
    
    def has_permission(self, user_role: str, permission: Permission) -> bool:
        """
        Check if user role has specific permission
        
        Args:
            user_role: User's role
            permission: Permission to check
            
        Returns:
            True if user has permission
        """
        try:
            role = Role(user_role.lower())
            permissions = self.role_permissions.get(role, set())
            return permission in permissions
        except ValueError:
            logger.warning(f"Invalid role: {user_role}")
            return False
    
    def has_any_permission(self, user_role: str, permissions: List[Permission]) -> bool:
        """Check if user has any of the specified permissions"""
        return any(self.has_permission(user_role, perm) for perm in permissions)
    
    def has_all_permissions(self, user_role: str, permissions: List[Permission]) -> bool:
        """Check if user has all of the specified permissions"""
        return all(self.has_permission(user_role, perm) for perm in permissions)
    
    def get_user_permissions(self, user_role: str) -> Set[Permission]:
        """Get all permissions for a user role"""
        try:
            role = Role(user_role.lower())
            return self.role_permissions.get(role, set())
        except ValueError:
            return set()
    
    def can_access_data(self, user_role: str, user_id: str, 
                       resource_owner_id: str, department_id: Optional[str] = None) -> bool:
        """
        Check if user can access specific data
        
        Args:
            user_role: User's role
            user_id: User's ID
            resource_owner_id: ID of resource owner
            department_id: Department ID (optional)
            
        Returns:
            True if user can access the data
        """
        # Admin can access all data
        if self.has_permission(user_role, Permission.READ_ALL_DATA):
            return True
        
        # Manager can access department data
        if self.has_permission(user_role, Permission.READ_DEPARTMENT_DATA):
            # Would need to check if user and resource are in same department
            return True
        
        # User can access own data
        if self.has_permission(user_role, Permission.READ_OWN_DATA):
            return user_id == resource_owner_id
        
        return False
    
    def can_create_background_task(self, user_role: str, task_type: str) -> bool:
        """Check if user can create specific background task"""
        if not self.has_permission(user_role, Permission.CREATE_BACKGROUND_TASKS):
            return False
        
        # Additional task-specific checks
        if task_type in ['bulk_export', 'system_report']:
            return self.has_permission(user_role, Permission.EXPORT_DATA)
        
        return True
    
    def filter_query_by_role(self, user_role: str, user_id: str, 
                            department_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get query filters based on user role
        
        Returns:
            Dictionary of filters to apply to queries
        """
        filters = {}
        
        if self.has_permission(user_role, Permission.READ_ALL_DATA):
            # No filters - can see all data
            pass
        elif self.has_permission(user_role, Permission.READ_DEPARTMENT_DATA):
            if department_id:
                filters['department_id'] = department_id
        elif self.has_permission(user_role, Permission.READ_OWN_DATA):
            filters['user_id'] = user_id
        
        return filters
    
    def get_allowed_operations(self, user_role: str) -> List[str]:
        """Get list of allowed operations for user role"""
        operations = []
        
        if self.has_permission(user_role, Permission.CREATE_RECORDS):
            operations.append('create')
        if self.has_permission(user_role, Permission.UPDATE_RECORDS):
            operations.append('update')
        if self.has_permission(user_role, Permission.DELETE_RECORDS):
            operations.append('delete')
        if self.has_permission(user_role, Permission.GENERATE_REPORTS):
            operations.append('generate_report')
        if self.has_permission(user_role, Permission.EXPORT_DATA):
            operations.append('export')
        
        return operations


# Global instance
rbac_service = RBACService()


# Decorator for permission checking
def require_permission(permission: Permission):
    """Decorator to check permission before executing function"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs or args
            user = kwargs.get('user') or (args[0] if args else None)
            
            if not user:
                raise PermissionError("User not found in request")
            
            user_role = getattr(user, 'role', 'user')
            
            if not rbac_service.has_permission(user_role, permission):
                raise PermissionError(
                    f"User role '{user_role}' does not have permission: {permission}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
