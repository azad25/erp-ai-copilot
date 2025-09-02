"""
System Commands API routes for AI Copilot
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, List, Any
import logging

from app.services.system_command_service import system_command_service
from app.services.auth_service import get_current_user
from app.models.api import User, SystemCommandRequest, SystemCommandResponse

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/execute", response_model=SystemCommandResponse)
async def execute_system_command(
    request: SystemCommandRequest,
    current_user: User = Depends(get_current_user)
):
    """Execute a system command with RBAC enforcement"""
    try:
        # Check permissions
        has_permission = await system_command_service.check_permissions(
            user_id=current_user.id,
            command=request.command,
            organization_id=current_user.organization_id
        )
        
        if not has_permission:
            raise HTTPException(
                status_code=403, 
                detail="Insufficient permissions to execute this command"
            )
        
        # Execute command
        result = await system_command_service.execute_command(
            command=request.command,
            user_id=current_user.id,
            working_directory=request.working_directory,
            timeout=request.timeout,
            environment=request.environment
        )
        
        return SystemCommandResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute system command: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/permissions", response_model=Dict[str, Any])
async def get_user_permissions(
    current_user: User = Depends(get_current_user)
):
    """Get user's system command permissions"""
    try:
        permissions = await system_command_service.get_user_permissions(
            user_id=current_user.id,
            organization_id=current_user.organization_id
        )
        
        return {
            "user_id": current_user.id,
            "permissions": permissions,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get user permissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history", response_model=List[Dict[str, Any]])
async def get_command_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Get user's command execution history"""
    try:
        history = await system_command_service.get_command_history(
            user_id=current_user.id,
            limit=limit
        )
        
        return history
        
    except Exception as e:
        logger.error(f"Failed to get command history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate", response_model=Dict[str, Any])
async def validate_command(
    request: SystemCommandRequest,
    current_user: User = Depends(get_current_user)
):
    """Validate a command without executing it"""
    try:
        validation = await system_command_service.validate_command(
            command=request.command,
            user_id=current_user.id,
            organization_id=current_user.organization_id
        )
        
        return validation
        
    except Exception as e:
        logger.error(f"Failed to validate command: {e}")
        raise HTTPException(status_code=500, detail=str(e))
