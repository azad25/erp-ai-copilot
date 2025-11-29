"""
AI Copilot Logs API Endpoints

API endpoints for querying AI Copilot audit logs (admin only).
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from datetime import datetime

from app.services.ai_copilot_logging_service import ai_copilot_logging_service
from app.models.ai_copilot_log import (
    AICopilotLogResponse,
    AICopilotLogQuery,
    AICopilotLogStats
)
from app.services.rbac_service import rbac_service, Permission
from app.middleware.auth import get_current_user_with_org

router = APIRouter()


@router.get("/", response_model=List[AICopilotLogResponse])
async def get_ai_logs(
    organization_id: Optional[str] = Query(None, description="Organization ID (admin only)"),
    user_id: Optional[str] = Query(None, description="User ID"),
    status: Optional[bool] = Query(None, description="Filter by status"),
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    search_prompt: Optional[str] = Query(None, description="Search in prompts"),
    search_response: Optional[str] = Query(None, description="Search in responses"),
    tool_name: Optional[str] = Query(None, description="Filter by tool name"),
    limit: int = Query(50, ge=1, le=100, description="Number of results"),
    skip: int = Query(0, ge=0, description="Number of results to skip"),
    current_user: dict = Depends(get_current_user_with_org)
):
    """
    Get AI Copilot logs
    
    Access control:
    - admin: Can see all logs across all organizations
    - org_admin: Can see only their organization's logs
    - Other roles: Access denied
    """
    try:
        user_role = current_user.get("role", "user")
        user_org_id = current_user.get("organization_id", "default")
        
        # Check if user has permission to view logs
        # Admin can see all, org_admin can see their org
        has_admin_access = rbac_service.has_permission(user_role, Permission.READ_ALL_DATA)
        has_org_admin_access = rbac_service.has_permission(user_role, Permission.VIEW_ORG_LOGS)
        
        if not (has_admin_access or has_org_admin_access):
            raise HTTPException(
                status_code=403,
                detail="Only administrators and organization admins can access AI Copilot logs"
            )
        
        # For org_admin, force their organization_id
        if has_org_admin_access and not has_admin_access:
            # org_admin can only see their own org
            organization_id = user_org_id
        
        # Build query
        query = AICopilotLogQuery(
            organization_id=organization_id,
            user_id=user_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
            search_prompt=search_prompt,
            search_response=search_response,
            tool_name=tool_name,
            limit=limit,
            skip=skip
        )
        
        # Get logs
        logs = await ai_copilot_logging_service.get_logs(
            query=query,
            requester_org_id=user_org_id,
            requester_role=user_role
        )
        
        return logs
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{log_id}", response_model=AICopilotLogResponse)
async def get_ai_log_by_id(
    log_id: str,
    current_user: dict = Depends(get_current_user_with_org)
):
    """
    Get a specific AI Copilot log by ID
    
    Access control:
    - admin: Can see any log
    - org_admin: Can see only logs from their organization
    """
    try:
        user_role = current_user.get("role", "user")
        user_org_id = current_user.get("organization_id", "default")
        
        # Check if user has permission to view logs
        has_admin_access = rbac_service.has_permission(user_role, Permission.READ_ALL_DATA)
        has_org_admin_access = rbac_service.has_permission(user_role, Permission.VIEW_ORG_LOGS)
        
        if not (has_admin_access or has_org_admin_access):
            raise HTTPException(
                status_code=403,
                detail="Only administrators and organization admins can access AI Copilot logs"
            )
        
        log = await ai_copilot_logging_service.get_log_by_id(
            log_id=log_id,
            requester_org_id=user_org_id,
            requester_role=user_role
        )
        
        if not log:
            raise HTTPException(status_code=404, detail="Log not found")
        
        return log
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/usage", response_model=AICopilotLogStats)
async def get_ai_usage_stats(
    organization_id: Optional[str] = Query(None, description="Organization ID (admin only)"),
    user_id: Optional[str] = Query(None, description="User ID"),
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    current_user: dict = Depends(get_current_user_with_org)
):
    """
    Get AI Copilot usage statistics
    
    Access control:
    - admin: Can see stats for any organization
    - org_admin: Can see only their organization's stats
    """
    try:
        user_role = current_user.get("role", "user")
        user_org_id = current_user.get("organization_id", "default")
        
        # Check if user has permission to view stats
        has_admin_access = rbac_service.has_permission(user_role, Permission.READ_ALL_DATA)
        has_org_admin_access = rbac_service.has_permission(user_role, Permission.VIEW_ORG_LOGS)
        
        if not (has_admin_access or has_org_admin_access):
            raise HTTPException(
                status_code=403,
                detail="Only administrators and organization admins can access AI Copilot statistics"
            )
        
        # For org_admin, force their organization_id
        if has_org_admin_access and not has_admin_access:
            org_id = user_org_id
        else:
            # Admin can specify org or default to their own
            org_id = organization_id or user_org_id
        
        stats = await ai_copilot_logging_service.get_stats(
            organization_id=org_id,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to
        )
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent/list", response_model=List[AICopilotLogResponse])
async def get_recent_ai_logs(
    user_id: Optional[str] = Query(None, description="User ID"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    current_user: dict = Depends(get_current_user_with_org)
):
    """
    Get recent AI Copilot logs
    
    Access control:
    - admin: Can see recent logs from any organization
    - org_admin: Can see only their organization's recent logs
    """
    try:
        user_role = current_user.get("role", "user")
        user_org_id = current_user.get("organization_id", "default")
        
        # Check if user has permission to view logs
        has_admin_access = rbac_service.has_permission(user_role, Permission.READ_ALL_DATA)
        has_org_admin_access = rbac_service.has_permission(user_role, Permission.VIEW_ORG_LOGS)
        
        if not (has_admin_access or has_org_admin_access):
            raise HTTPException(
                status_code=403,
                detail="Only administrators and organization admins can access AI Copilot logs"
            )
        
        # org_admin always sees their own org
        logs = await ai_copilot_logging_service.get_recent_logs(
            organization_id=user_org_id,
            user_id=user_id,
            limit=limit
        )
        
        return logs
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
