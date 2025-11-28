"""
RBAC Service

Role-Based Access Control service for AI Copilot.
Handles permission checks, role validation, and organization-based data isolation.
"""

from typing import Dict, Any, List, Optional, Set
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class Role(str, Enum):
    """User roles in the system"""
    SUPER_ADMIN = "super_admin"  # Full system access
    ADMIN = "admin"  # Organization admin
    MANAGER = "manager"  # Department manager
    USER = "user"  # Regular user
    VIEWER = "viewer"  # Read-only access


class Permission(str, Enum):
    """System permissions"""
    # API Access
    API_CALL_ANY = "api:call:any"  # Call any API endpoint
    API_CALL_READ = "api:call:read"  # Call read-only APIs
    API_CALL_WRITE = "api:call:write"  # Call write APIs
    
    # Data Access
    DATA_READ_ALL = "data:read:all"  # Read all data
    DATA_READ_ORG = "data:read:org"  # Read organization data
    DATA_READ_OWN = "data:read:own"  # Read own data
    DATA_WRITE_ALL = "data:write:all"  # Write all data
    DATA_WRITE_ORG = "data:write:org"  # Write organization data
    DATA_WRITE_OWN = "data:write:own"  # Write own data
    
    # User Management
    USER_READ_ALL = "user:read:all"  # Read all users
    USER_READ_ORG = "user:read:org"  # Read org users
    USER_WRITE_ALL = "user:write:all"  # Manage all users
    USER_WRITE_ORG = "user:write:org"  # Manage org users
    
    # Organization Management
    ORG_READ_ALL = "org:read:all"  # Read all organizations
    ORG_READ_OWN = "org:read:own"  # Read own organization
    ORG_WRITE_ALL = "org:write:all"  # Manage all organizations
    ORG_WRITE_OWN = "org:write:own"  # Manage own organization
    
    # AI Features
    AI_QUERY_ANY = "ai:query:any"  # Query any data via AI
    AI_QUERY_ORG = "ai:query:org"  # Query org data via AI
    AI_QUERY_OWN = "ai:query:own"  # Query own data via AI


# Role to permissions mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.SUPER_ADMIN: {
        # Full access to everything
        Permission.API_CALL_ANY,
        Permission.DATA_READ_ALL,
        Permission.DATA_WRITE_ALL,
        Permission.USER_READ_ALL,
        Permission.USER_WRITE_ALL,
        Permission.ORG_READ_ALL,
        Permission.ORG_WRITE_ALL,
        Permission.AI_QUERY_ANY,
    },
    Role.ADMIN: {
        # Organization-level access
        Permission.API_CALL_READ,
        Permission.API_CALL_WRITE,
        Permission.DATA_READ_ORG,
        Permission.DATA_WRITE_ORG,
        Permission.USER_READ_ORG,
        Permission.USER_WRITE_ORG,
        Permission.ORG_READ_OWN,
        Permission.ORG_WRITE_OWN,
        Permission.AI_QUERY_ORG,
    },
    Role.MANAGER: {
        # Department-level access
        Permission.API_CALL_READ,
        Permission.DATA_READ_ORG,
        Permission.DATA_WRITE_OWN,
        Permission.USER_READ_ORG,
        Permission.ORG_READ_OWN,
        Permission.AI_QUERY_ORG,
    },
    Role.USER: {
        # User-level access
        Permission.API_CALL_READ,
        Permission.DATA_READ_OWN,
        Permission.DATA_WRITE_OWN,
        Permission.ORG_READ_OWN,
        Permission.AI_QUERY_OWN,
    },
    Role.VIEWER: {
        # Read-only access
        Permission.API_CALL_READ,
        Permission.DATA_READ_OWN,
        Permission.ORG_READ_OWN,
        Permission.AI_QUERY_OWN,
    }
}


class RBACService:
    """Role-Based Access Control Service"""
    
    def __init__(self):
        self.role_permissions = ROLE_PERMISSIONS
    
    def get_user_permissions(self, role: str) -> Set[Permission]:
        """Get permissions for a user role"""
        try:
            user_role = Role(role.lower())
            return self.role_permissions.get(user_role, set())
        except ValueError:
            logger.warning(f"Unknown role: {role}")
            return set()
    
    def has_permission(
        self,
        user_role: str,
        required_permission: Permission
    ) -> bool:
        """Check if user has a specific permission"""
        user_permissions = self.get_user_permissions(user_role)
        has_perm = required_permission in user_permissions
        
        logger.debug(
            "Permission check",
            role=user_role,
            permission=required_permission.value,
            granted=has_perm
        )
        
        return has_perm
    
    def can_call_api(
        self,
        user_role: str,
        method: str,
        endpoint: str
    ) -> tuple[bool, Optional[str]]:
        """
        Check if user can call a specific API endpoint
        
        Returns:
            (allowed, reason) tuple
        """
        # Super admin can call anything
        if user_role.lower() == Role.SUPER_ADMIN.value:
            return True, None
        
        # Check if it's a write operation
        is_write = method.upper() in ["POST", "PUT", "PATCH", "DELETE"]
        
        # Check permissions
        if is_write:
            if self.has_permission(user_role, Permission.API_CALL_WRITE):
                return True, None
            else:
                return False, "Write API access not permitted for your role"
        else:
            if self.has_permission(user_role, Permission.API_CALL_READ):
                return True, None
            else:
                return False, "API access not permitted for your role"
    
    def can_access_data(
        self,
        user_role: str,
        user_org_id: str,
        data_org_id: Optional[str],
        data_user_id: Optional[str],
        user_id: str,
        operation: str = "read"
    ) -> tuple[bool, Optional[str]]:
        """
        Check if user can access specific data
        
        Args:
            user_role: User's role
            user_org_id: User's organization ID
            data_org_id: Organization ID of the data
            data_user_id: User ID of the data owner
            user_id: Current user's ID
            operation: "read" or "write"
            
        Returns:
            (allowed, reason) tuple
        """
        # Super admin can access all data
        if user_role.lower() == Role.SUPER_ADMIN.value:
            return True, None
        
        # Check operation type
        if operation == "read":
            # Check read permissions
            if self.has_permission(user_role, Permission.DATA_READ_ALL):
                return True, None
            
            if self.has_permission(user_role, Permission.DATA_READ_ORG):
                if data_org_id == user_org_id:
                    return True, None
                else:
                    return False, "Can only access data from your organization"
            
            if self.has_permission(user_role, Permission.DATA_READ_OWN):
                if data_user_id == user_id:
                    return True, None
                else:
                    return False, "Can only access your own data"
            
            return False, "No read permission for this data"
        
        elif operation == "write":
            # Check write permissions
            if self.has_permission(user_role, Permission.DATA_WRITE_ALL):
                return True, None
            
            if self.has_permission(user_role, Permission.DATA_WRITE_ORG):
                if data_org_id == user_org_id:
                    return True, None
                else:
                    return False, "Can only modify data from your organization"
            
            if self.has_permission(user_role, Permission.DATA_WRITE_OWN):
                if data_user_id == user_id:
                    return True, None
                else:
                    return False, "Can only modify your own data"
            
            return False, "No write permission for this data"
        
        return False, "Invalid operation"
    
    def filter_data_by_access(
        self,
        user_role: str,
        user_org_id: str,
        user_id: str,
        data_list: List[Dict[str, Any]],
        org_id_field: str = "organization_id",
        user_id_field: str = "user_id"
    ) -> List[Dict[str, Any]]:
        """
        Filter data list based on user's access permissions
        
        Args:
            user_role: User's role
            user_org_id: User's organization ID
            user_id: User's ID
            data_list: List of data items to filter
            org_id_field: Field name for organization ID
            user_id_field: Field name for user ID
            
        Returns:
            Filtered data list
        """
        # Super admin sees everything
        if user_role.lower() == Role.SUPER_ADMIN.value:
            return data_list
        
        # Admin sees organization data
        if self.has_permission(user_role, Permission.DATA_READ_ORG):
            return [
                item for item in data_list
                if item.get(org_id_field) == user_org_id
            ]
        
        # User sees only own data
        if self.has_permission(user_role, Permission.DATA_READ_OWN):
            return [
                item for item in data_list
                if item.get(user_id_field) == user_id
            ]
        
        # No access
        return []
    
    def get_data_filter_query(
        self,
        user_role: str,
        user_org_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get database query filter based on user permissions
        
        Returns:
            Dictionary with filter conditions
        """
        # Super admin - no filter
        if user_role.lower() == Role.SUPER_ADMIN.value:
            return {}
        
        # Admin - organization filter
        if self.has_permission(user_role, Permission.DATA_READ_ORG):
            return {"organization_id": user_org_id}
        
        # User - own data filter
        if self.has_permission(user_role, Permission.DATA_READ_OWN):
            return {"user_id": user_id}
        
        # No access - impossible filter
        return {"_id": None}
    
    def can_query_ai(
        self,
        user_role: str,
        query_scope: str = "own"
    ) -> tuple[bool, Optional[str]]:
        """
        Check if user can make AI queries with specific scope
        
        Args:
            user_role: User's role
            query_scope: "any", "org", or "own"
            
        Returns:
            (allowed, reason) tuple
        """
        if query_scope == "any":
            if self.has_permission(user_role, Permission.AI_QUERY_ANY):
                return True, None
            return False, "Cannot query all data via AI"
        
        elif query_scope == "org":
            if self.has_permission(user_role, Permission.AI_QUERY_ORG):
                return True, None
            return False, "Cannot query organization data via AI"
        
        elif query_scope == "own":
            if self.has_permission(user_role, Permission.AI_QUERY_OWN):
                return True, None
            return False, "Cannot query data via AI"
        
        return False, "Invalid query scope"
    
    def get_role_description(self, role: str) -> str:
        """Get human-readable description of role capabilities"""
        descriptions = {
            Role.SUPER_ADMIN: "Full system access - can view and modify all data across all organizations",
            Role.ADMIN: "Organization admin - can manage users and data within their organization",
            Role.MANAGER: "Department manager - can view organization data and manage their own data",
            Role.USER: "Regular user - can view and manage their own data",
            Role.VIEWER: "Read-only user - can view their own data only"
        }
        
        try:
            user_role = Role(role.lower())
            return descriptions.get(user_role, "Unknown role")
        except ValueError:
            return "Unknown role"


# Global instance
_rbac_service: Optional[RBACService] = None


def get_rbac_service() -> RBACService:
    """Get or create RBAC Service instance"""
    global _rbac_service
    
    if _rbac_service is None:
        _rbac_service = RBACService()
    
    return _rbac_service
