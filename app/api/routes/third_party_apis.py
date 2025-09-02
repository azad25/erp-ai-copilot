"""
Third-party APIs proxy routes for AI Copilot
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, List, Any, Optional
import logging

from app.services.third_party_api_service import third_party_api_service
from app.services.auth_service import get_current_user
from app.models.api import User, ThirdPartyAPIRequest, ThirdPartyAPIResponse

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/call", response_model=ThirdPartyAPIResponse)
async def call_third_party_api(
    request: ThirdPartyAPIRequest,
    current_user: User = Depends(get_current_user)
):
    """Make a call to a third-party API through the secure proxy"""
    try:
        result = await third_party_api_service.make_api_call(
            api_name=request.api_name,
            endpoint=request.endpoint,
            method=request.method,
            data=request.data,
            headers=request.headers,
            user_id=current_user.id,
            organization_id=current_user.organization_id
        )
        
        return ThirdPartyAPIResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to call third-party API: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/available", response_model=List[Dict[str, Any]])
async def get_available_apis(
    current_user: User = Depends(get_current_user)
):
    """Get list of available third-party APIs for the user"""
    try:
        apis = await third_party_api_service.get_available_apis(
            user_id=current_user.id,
            organization_id=current_user.organization_id
        )
        
        return apis
        
    except Exception as e:
        logger.error(f"Failed to get available APIs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/configure", response_model=Dict[str, Any])
async def configure_api_credentials(
    api_name: str,
    credentials: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Configure API credentials for a third-party service"""
    try:
        result = await third_party_api_service.configure_api_credentials(
            api_name=api_name,
            credentials=credentials,
            user_id=current_user.id,
            organization_id=current_user.organization_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to configure API credentials: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/usage/{api_name}", response_model=Dict[str, Any])
async def get_api_usage_stats(
    api_name: str,
    current_user: User = Depends(get_current_user)
):
    """Get usage statistics for a third-party API"""
    try:
        stats = await third_party_api_service.get_usage_stats(
            api_name=api_name,
            user_id=current_user.id,
            organization_id=current_user.organization_id
        )
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get API usage stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
