"""
AI Copilot Dashboard API endpoints.
"""
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
import structlog

from app.core.database import get_db_session
from app.models.database import Conversation, Message, User, AgentExecution, KnowledgeBase
from app.services.infrastructure_service import InfrastructureService
from app.services.auth_service import get_current_user
from app.core.metrics import get_metrics_summary
from app.models.api import ErrorResponse
from app.models.database import User

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/dashboard")
async def get_ai_copilot_dashboard(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get comprehensive AI Copilot dashboard data.
    
    Returns a complete dashboard view with:
    - Analytical metrics and KPIs
    - System status information
    - Recent activity logs and events
    - Performance characteristics
    """
    try:
        # Get infrastructure service for system metrics
        infra_service = InfrastructureService()
        
        # Get system overview
        system_overview = await infra_service.get_system_overview()
        
        # Get Prometheus metrics
        metrics_summary = get_metrics_summary()
        
        # Get recent conversations and messages
        recent_conversations = await _get_recent_conversations(db)
        
        # Get recent agent executions
        recent_executions = await _get_recent_executions(db)
        
        # Get knowledge base statistics
        kb_stats = await _get_knowledge_base_stats(db)
        
        # Get user engagement metrics
        user_engagement = await _get_user_engagement_metrics(db)
        
        # Get AI model usage statistics
        ai_usage = await _get_ai_usage_stats(db)
        
        # Get system health status
        health_status = await _get_system_health_status()
        
        # Compile dashboard data
        dashboard_data = {
            "timestamp": time.time(),
            "service": {
                "name": "AI Copilot Dashboard",
                "version": "1.0.0",
                "status": "active"
            },
            "metrics": {
                "system": system_overview,
                "performance": metrics_summary,
                "conversations": recent_conversations["metrics"],
                "executions": recent_executions["metrics"],
                "knowledge_base": kb_stats,
                "user_engagement": user_engagement,
                "ai_usage": ai_usage
            },
            "system_status": health_status,
            "recent_activity": {
                "conversations": recent_conversations["items"],
                "executions": recent_executions["items"],
                "system_events": await _get_system_events()
            },
            "kpi": {
                "total_conversations": recent_conversations["metrics"]["total_count"],
                "active_users": user_engagement["active_users"],
                "avg_response_time": metrics_summary.get("request_latency_avg", 0),
                "system_uptime": health_status.get("uptime_percent", 100),
                "kb_documents": kb_stats["total_documents"],
                "success_rate": metrics_summary.get("success_rate", 0)
            }
        }
        
        return dashboard_data
        
    except Exception as e:
        logger.error("Failed to generate dashboard data", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="dashboard_generation_failed",
                message="Failed to generate dashboard data",
                details={"error": str(e)}
            ).dict()
        )


async def _get_recent_conversations(db: AsyncSession) -> Dict[str, Any]:
    """Get recent conversations and their metrics."""
    try:
        # Get conversations from last 7 days
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        # Count total conversations
        total_count_query = select(func.count(Conversation.id))
        total_count_result = await db.execute(total_count_query)
        total_count = total_count_result.scalar()
        
        # Get recent conversations
        recent_query = (
            select(Conversation)
            .where(Conversation.created_at >= seven_days_ago)
            .order_by(desc(Conversation.created_at))
            .limit(10)
        )
        recent_result = await db.execute(recent_query)
        recent_conversations = recent_result.scalars().all()
        
        # Get message counts for recent conversations
        conversation_data = []
        for conv in recent_conversations:
            message_count_query = select(func.count(Message.id)).where(Message.conversation_id == conv.id)
            message_count_result = await db.execute(message_count_query)
            message_count = message_count_result.scalar()
            
            conversation_data.append({
                "id": str(conv.id),
                "title": conv.title,
                "status": conv.status,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
                "message_count": message_count,
                "user_id": str(conv.user_id)
            })
        
        return {
            "items": conversation_data,
            "metrics": {
                "total_count": total_count,
                "recent_count": len(recent_conversations)
            }
        }
        
    except Exception as e:
        logger.error("Failed to get recent conversations", error=str(e))
        return {"items": [], "metrics": {"total_count": 0, "recent_count": 0}}


async def _get_recent_executions(db: AsyncSession) -> Dict[str, Any]:
    """Get recent agent executions."""
    try:
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        # Get recent executions
        executions_query = (
            select(AgentExecution)
            .where(AgentExecution.created_at >= seven_days_ago)
            .order_by(desc(AgentExecution.created_at))
            .limit(10)
        )
        executions_result = await db.execute(executions_query)
        executions = executions_result.scalars().all()
        
        # Count total executions
        total_count_query = select(func.count(AgentExecution.id))
        total_count_result = await db.execute(total_count_query)
        total_count = total_count_result.scalar()
        
        execution_data = []
        for exec in executions:
            execution_data.append({
                "id": str(exec.id),
                "agent_type": exec.agent_type,
                "status": exec.status,
                "created_at": exec.created_at.isoformat(),
                "updated_at": exec.updated_at.isoformat(),
                "user_id": str(exec.user_id),
                "conversation_id": str(exec.conversation_id) if exec.conversation_id else None
            })
        
        return {
            "items": execution_data,
            "metrics": {
                "total_count": total_count,
                "recent_count": len(executions)
            }
        }
        
    except Exception as e:
        logger.error("Failed to get recent executions", error=str(e))
        return {"items": [], "metrics": {"total_count": 0, "recent_count": 0}}


async def _get_knowledge_base_stats(db: AsyncSession) -> Dict[str, Any]:
    """Get knowledge base statistics."""
    try:
        # Count total documents
        total_count_query = select(func.count(KnowledgeBase.id))
        total_count_result = await db.execute(total_count_query)
        total_documents = total_count_result.scalar()
        
        # Get document type distribution
        type_query = select(
            KnowledgeBase.document_type,
            func.count(KnowledgeBase.id).label("count")
        ).group_by(KnowledgeBase.document_type)
        type_result = await db.execute(type_query)
        type_distribution = dict(type_result.fetchall())
        
        # Get recent uploads
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_count_query = select(func.count(KnowledgeBase.id)).where(
            KnowledgeBase.created_at >= seven_days_ago
        )
        recent_count_result = await db.execute(recent_count_query)
        recent_uploads = recent_count_result.scalar()
        
        return {
            "total_documents": total_documents,
            "type_distribution": type_distribution,
            "recent_uploads": recent_uploads
        }
        
    except Exception as e:
        logger.error("Failed to get knowledge base stats", error=str(e))
        return {"total_documents": 0, "type_distribution": {}, "recent_uploads": 0}


async def _get_user_engagement_metrics(db: AsyncSession) -> Dict[str, Any]:
    """Get user engagement metrics."""
    try:
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        # Active users (users with activity in last 7 days)
        active_users_query = select(func.count(func.distinct(User.id))).join(
            Conversation, User.id == Conversation.user_id
        ).where(Conversation.created_at >= seven_days_ago)
        active_users_result = await db.execute(active_users_query)
        active_users = active_users_result.scalar()
        
        # Total users
        total_users_query = select(func.count(User.id))
        total_users_result = await db.execute(total_users_query)
        total_users = total_users_result.scalar()
        
        return {
            "active_users": active_users,
            "total_users": total_users,
            "engagement_rate": (active_users / total_users * 100) if total_users > 0 else 0
        }
        
    except Exception as e:
        logger.error("Failed to get user engagement metrics", error=str(e))
        return {"active_users": 0, "total_users": 0, "engagement_rate": 0}


async def _get_ai_usage_stats(db: AsyncSession) -> Dict[str, Any]:
    """Get AI model usage statistics."""
    try:
        # This would typically come from metrics or logs
        # For now, return placeholder data
        return {
            "total_requests": 0,
            "model_usage": {
                "openai": 0,
                "anthropic": 0,
                "ollama": 0
            },
            "average_tokens_per_request": 0,
            "cost_estimate": 0.0
        }
        
    except Exception as e:
        logger.error("Failed to get AI usage stats", error=str(e))
        return {"total_requests": 0, "model_usage": {}, "average_tokens_per_request": 0, "cost_estimate": 0.0}


async def _get_system_health_status() -> Dict[str, Any]:
    """Get system health status."""
    try:
        # This would check various system health metrics
        return {
            "status": "healthy",
            "uptime_percent": 99.9,
            "last_check": datetime.utcnow().isoformat(),
            "services": {
                "database": "healthy",
                "redis": "healthy",
                "mongodb": "healthy",
                "qdrant": "healthy"
            }
        }
        
    except Exception as e:
        logger.error("Failed to get system health status", error=str(e))
        return {"status": "unknown", "uptime_percent": 0, "services": {}}


async def _get_system_events() -> List[Dict[str, Any]]:
    """Get recent system events."""
    try:
        # This would typically come from system logs or event tracking
        return [
            {
                "type": "system_start",
                "message": "AI Copilot service started",
                "timestamp": datetime.utcnow().isoformat(),
                "severity": "info"
            },
            {
                "type": "database_connected",
                "message": "Database connection established",
                "timestamp": datetime.utcnow().isoformat(),
                "severity": "info"
            }
        ]
        
    except Exception as e:
        logger.error("Failed to get system events", error=str(e))
        return []