"""
User Context Management

Thread-safe context management for current user and organization.
"""

from contextvars import ContextVar
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Context variables for request-scoped data
_current_user_id: ContextVar[Optional[str]] = ContextVar('current_user_id', default=None)
_current_organization_id: ContextVar[Optional[str]] = ContextVar('current_organization_id', default=None)
_current_user_role: ContextVar[Optional[str]] = ContextVar('current_user_role', default=None)
_current_user_permissions: ContextVar[Optional[list]] = ContextVar('current_user_permissions', default=None)
_current_department_id: ContextVar[Optional[str]] = ContextVar('current_department_id', default=None)


@dataclass
class UserContext:
    """User context data"""
    user_id: str
    organization_id: str
    role: str
    permissions: list
    department_id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None


def set_current_user_context(
    user_id: str,
    organization_id: str,
    role: str,
    permissions: list,
    department_id: Optional[str] = None
):
    """
    Set current user context for the request
    
    Args:
        user_id: User ID
        organization_id: Organization ID
        role: User role
        permissions: List of permissions
        department_id: Optional department ID
    """
    _current_user_id.set(user_id)
    _current_organization_id.set(organization_id)
    _current_user_role.set(role)
    _current_user_permissions.set(permissions)
    if department_id:
        _current_department_id.set(department_id)


def get_current_user_id() -> Optional[str]:
    """Get current user ID from context"""
    return _current_user_id.get()


def get_current_organization_id() -> Optional[str]:
    """Get current organization ID from context"""
    return _current_organization_id.get()


def get_current_user_role() -> Optional[str]:
    """Get current user role from context"""
    return _current_user_role.get()


def get_current_user_permissions() -> Optional[list]:
    """Get current user permissions from context"""
    return _current_user_permissions.get()


def get_current_department_id() -> Optional[str]:
    """Get current department ID from context"""
    return _current_department_id.get()


def get_current_user_context() -> Optional[UserContext]:
    """
    Get complete user context
    
    Returns:
        UserContext object or None if not set
    """
    user_id = get_current_user_id()
    org_id = get_current_organization_id()
    role = get_current_user_role()
    permissions = get_current_user_permissions()
    
    if not all([user_id, org_id, role]):
        return None
    
    return UserContext(
        user_id=user_id,
        organization_id=org_id,
        role=role,
        permissions=permissions or [],
        department_id=get_current_department_id()
    )


def clear_current_user_context():
    """Clear current user context"""
    _current_user_id.set(None)
    _current_organization_id.set(None)
    _current_user_role.set(None)
    _current_user_permissions.set(None)
    _current_department_id.set(None)


def require_organization_match(organization_id: str) -> bool:
    """
    Validate that the provided organization_id matches current user's org
    
    Args:
        organization_id: Organization ID to validate
        
    Returns:
        True if matches, False otherwise
        
    Raises:
        PermissionError: If org_id doesn't match
    """
    current_org_id = get_current_organization_id()
    
    if not current_org_id:
        raise PermissionError("No organization context set")
    
    if current_org_id != organization_id:
        raise PermissionError(
            f"Organization mismatch: user belongs to {current_org_id}, "
            f"but trying to access {organization_id}"
        )
    
    return True


def get_org_filtered_query(base_filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Get query filters with organization_id automatically added
    
    Args:
        base_filters: Optional base filters
        
    Returns:
        Filters with organization_id added
    """
    filters = base_filters.copy() if base_filters else {}
    
    org_id = get_current_organization_id()
    if org_id:
        filters['organization_id'] = org_id
    
    return filters
