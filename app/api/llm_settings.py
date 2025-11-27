"""
LLM Provider Settings API

Endpoints for managing LLM provider configurations.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import structlog

from app.database.connection import get_db_session as get_db
from app.models.llm_provider_settings import LLMProviderSettings
from app.services.llm_service import get_llm_service, initialize_llm_service
import os

logger = structlog.get_logger("llm_settings_api")

router = APIRouter(prefix="/api/llm-settings", tags=["LLM Settings"])


class LLMProviderSettingsCreate(BaseModel):
    """Schema for creating LLM provider settings."""
    provider_name: str = Field(..., description="Provider identifier (e.g., 'openai', 'gemini')")
    display_name: str = Field(..., description="Human-readable provider name")
    api_key: Optional[str] = Field(None, description="API key or token")
    base_url: Optional[str] = Field(None, description="Base URL for API")
    is_enabled: bool = Field(True, description="Whether provider is enabled")
    is_default: bool = Field(False, description="Whether this is the default provider")
    priority: int = Field(0, description="Priority for fallback (higher = tried first)")
    config: Optional[Dict[str, Any]] = Field(None, description="Additional configuration")
    available_models: Optional[List[str]] = Field(None, description="List of available models")
    default_model: Optional[str] = Field(None, description="Default model for this provider")


class LLMProviderSettingsUpdate(BaseModel):
    """Schema for updating LLM provider settings."""
    display_name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    is_enabled: Optional[bool] = None
    is_default: Optional[bool] = None
    priority: Optional[int] = None
    config: Optional[Dict[str, Any]] = None
    available_models: Optional[List[str]] = None
    default_model: Optional[str] = None


class LLMProviderSettingsResponse(BaseModel):
    """Schema for LLM provider settings response."""
    id: int
    provider_name: str
    display_name: str
    api_key_configured: bool  # Don't expose actual key
    base_url: Optional[str]
    is_enabled: bool
    is_default: bool
    priority: int
    config: Optional[Dict[str, Any]]
    available_models: Optional[List[str]]
    default_model: Optional[str]
    
    class Config:
        from_attributes = True


class LLMProviderStatus(BaseModel):
    """Schema for LLM provider status."""
    provider_name: str
    display_name: str
    is_enabled: bool
    is_available: bool
    is_default: bool
    error_message: Optional[str] = None


@router.get("/providers", response_model=List[LLMProviderSettingsResponse])
async def get_all_providers(db: AsyncSession = Depends(get_db)):
    """Get all LLM provider settings."""
    try:
        result = await db.execute(
            select(LLMProviderSettings).order_by(LLMProviderSettings.priority.desc())
        )
        providers = result.scalars().all()
        
        return [
            LLMProviderSettingsResponse(
                id=p.id,
                provider_name=p.provider_name,
                display_name=p.display_name,
                api_key_configured=bool(p.api_key),
                base_url=p.base_url,
                is_enabled=p.is_enabled,
                is_default=p.is_default,
                priority=p.priority,
                config=p.config,
                available_models=p.available_models,
                default_model=p.default_model
            )
            for p in providers
        ]
    except Exception as e:
        logger.error(f"Error fetching providers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers/status", response_model=List[LLMProviderStatus])
async def get_providers_status(db: AsyncSession = Depends(get_db)):
    """Get status of all LLM providers (enabled, available, etc.)."""
    try:
        result = await db.execute(select(LLMProviderSettings))
        providers = result.scalars().all()
        
        llm_service = get_llm_service()
        available_providers = llm_service.get_available_providers() if llm_service else []
        
        statuses = []
        for p in providers:
            is_available = p.provider_name in available_providers
            error_msg = None
            
            if p.is_enabled and not is_available:
                error_msg = "Provider not available - check API key and configuration"
            
            statuses.append(LLMProviderStatus(
                provider_name=p.provider_name,
                display_name=p.display_name,
                is_enabled=p.is_enabled,
                is_available=is_available,
                is_default=p.is_default,
                error_message=error_msg
            ))
        
        return statuses
    except Exception as e:
        logger.error(f"Error fetching provider status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/providers", response_model=LLMProviderSettingsResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    provider: LLMProviderSettingsCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create new LLM provider settings."""
    try:
        # Check if provider already exists
        result = await db.execute(
            select(LLMProviderSettings).where(
                LLMProviderSettings.provider_name == provider.provider_name
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{provider.provider_name}' already exists"
            )
        
        # If this is set as default, unset other defaults
        if provider.is_default:
            await db.execute(
                update(LLMProviderSettings).values(is_default=False)
            )
        
        # Create new provider
        db_provider = LLMProviderSettings(**provider.model_dump())
        db.add(db_provider)
        await db.commit()
        await db.refresh(db_provider)
        
        # Update environment and reinitialize service
        if provider.api_key:
            _update_env_variable(provider.provider_name, provider.api_key)
        
        # Reinitialize LLM service
        initialize_llm_service()
        
        return LLMProviderSettingsResponse(
            id=db_provider.id,
            provider_name=db_provider.provider_name,
            display_name=db_provider.display_name,
            api_key_configured=bool(db_provider.api_key),
            base_url=db_provider.base_url,
            is_enabled=db_provider.is_enabled,
            is_default=db_provider.is_default,
            priority=db_provider.priority,
            config=db_provider.config,
            available_models=db_provider.available_models,
            default_model=db_provider.default_model
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating provider: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/providers/{provider_id}", response_model=LLMProviderSettingsResponse)
async def update_provider(
    provider_id: int,
    provider_update: LLMProviderSettingsUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update LLM provider settings."""
    try:
        result = await db.execute(
            select(LLMProviderSettings).where(LLMProviderSettings.id == provider_id)
        )
        db_provider = result.scalar_one_or_none()
        
        if not db_provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        
        # If setting as default, unset other defaults
        if provider_update.is_default:
            await db.execute(
                update(LLMProviderSettings)
                .where(LLMProviderSettings.id != provider_id)
                .values(is_default=False)
            )
        
        # Update fields
        update_data = provider_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_provider, field, value)
        
        await db.commit()
        await db.refresh(db_provider)
        
        # Update environment if API key changed
        if provider_update.api_key:
            _update_env_variable(db_provider.provider_name, provider_update.api_key)
        
        # Reinitialize LLM service
        initialize_llm_service()
        
        return LLMProviderSettingsResponse(
            id=db_provider.id,
            provider_name=db_provider.provider_name,
            display_name=db_provider.display_name,
            api_key_configured=bool(db_provider.api_key),
            base_url=db_provider.base_url,
            is_enabled=db_provider.is_enabled,
            is_default=db_provider.is_default,
            priority=db_provider.priority,
            config=db_provider.config,
            available_models=db_provider.available_models,
            default_model=db_provider.default_model
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating provider: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    """Delete LLM provider settings."""
    try:
        result = await db.execute(
            select(LLMProviderSettings).where(LLMProviderSettings.id == provider_id)
        )
        db_provider = result.scalar_one_or_none()
        
        if not db_provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        
        await db.delete(db_provider)
        await db.commit()
        
        # Reinitialize LLM service
        initialize_llm_service()
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting provider: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/providers/{provider_id}/test")
async def test_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    """Test LLM provider connection."""
    try:
        result = await db.execute(
            select(LLMProviderSettings).where(LLMProviderSettings.id == provider_id)
        )
        db_provider = result.scalar_one_or_none()
        
        if not db_provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        
        if not db_provider.is_enabled:
            return {
                "success": False,
                "message": "Provider is disabled"
            }
        
        # Test the provider
        llm_service = get_llm_service()
        if not llm_service:
            return {
                "success": False,
                "message": "LLM service not initialized"
            }
        
        if db_provider.provider_name not in llm_service.get_available_providers():
            return {
                "success": False,
                "message": f"Provider '{db_provider.provider_name}' not available"
            }
        
        # Try a simple test query
        from app.services.llm_service import LLMRequest, LLMMessage
        
        test_request = LLMRequest(
            messages=[LLMMessage(role="user", content="Hello")],
            model=db_provider.default_model or "test",
            max_tokens=10
        )
        
        try:
            response = await llm_service.generate(test_request)
            return {
                "success": True,
                "message": "Provider is working correctly",
                "test_response": response.content[:50]
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Provider test failed: {str(e)}"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing provider: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def _update_env_variable(provider_name: str, api_key: str):
    """Update environment variable for provider API key."""
    env_var_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "huggingface": "HF_TOKEN",
        "ollama": None  # No API key needed
    }
    
    env_var = env_var_map.get(provider_name)
    if env_var:
        os.environ[env_var] = api_key
