"""
Health check endpoints with circuit breaker and resilience monitoring.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import structlog

from app.database.connection import check_database_health
from app.core.circuit_breaker import circuit_manager
from app.core.resilience import health_checker, degradation_manager
from app.core.exceptions import handle_exception
from app.services.connection_health_service import connection_health_service

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint."""
    try:
        return {
            "status": "healthy",
            "service": "ai-copilot",
            "message": "Service is running"
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=500, detail="Health check failed")


@router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check including all services and circuit breakers."""
    try:
        # Get comprehensive health status from both sources
        circuit_health = await health_checker.check_all_services()
        connection_health = await connection_health_service.check_all_connections()
        
        # Merge health statuses
        health_status = {
            "service": "ai-copilot",
            "timestamp": None,  # Will be set by middleware
            "version": "1.0.0",
            "circuit_breakers": circuit_health,
            "connections": connection_health,
            "diagnostics": await connection_health_service.diagnose_connection_issues()
        }
        
        # Determine overall status
        connection_summary = await connection_health_service.get_health_summary()
        overall_status = connection_summary.get("overall_status", "unknown")
        health_status["overall_status"] = overall_status
        
        if overall_status == "critical":
            raise HTTPException(status_code=503, detail=health_status)
        elif overall_status == "degraded":
            health_status["warning"] = "Some services are degraded"
        
        return health_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Detailed health check failed", error=str(e))
        error_response = handle_exception(e)
        raise HTTPException(
            status_code=error_response["status_code"],
            detail=error_response
        )


@router.get("/circuit-breakers")
async def circuit_breaker_status() -> Dict[str, Any]:
    """Get status of all circuit breakers."""
    try:
        return {
            "circuit_breakers": circuit_manager.get_all_states(),
            "timestamp": None
        }
    except Exception as e:
        logger.error("Circuit breaker status check failed", error=str(e))
        raise HTTPException(status_code=500, detail="Circuit breaker status unavailable")


@router.post("/circuit-breakers/reset")
async def reset_circuit_breakers() -> Dict[str, Any]:
    """Reset all circuit breakers (admin operation)."""
    try:
        await circuit_manager.reset_all()
        logger.info("All circuit breakers reset via API")
        
        return {
            "message": "All circuit breakers have been reset",
            "status": "success"
        }
    except Exception as e:
        logger.error("Failed to reset circuit breakers", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to reset circuit breakers")


@router.post("/circuit-breakers/{breaker_name}/reset")
async def reset_specific_circuit_breaker(breaker_name: str) -> Dict[str, Any]:
    """Reset a specific circuit breaker."""
    try:
        await circuit_manager.reset_breaker(breaker_name)
        logger.info("Circuit breaker reset via API", breaker_name=breaker_name)
        
        return {
            "message": f"Circuit breaker '{breaker_name}' has been reset",
            "status": "success"
        }
    except Exception as e:
        logger.error("Failed to reset circuit breaker", breaker_name=breaker_name, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to reset circuit breaker '{breaker_name}'")


@router.get("/degradation")
async def service_degradation_status() -> Dict[str, Any]:
    """Get service degradation status."""
    try:
        return {
            "degradation_status": degradation_manager.get_service_status(),
            "timestamp": None
        }
    except Exception as e:
        logger.error("Service degradation status check failed", error=str(e))
        raise HTTPException(status_code=500, detail="Service degradation status unavailable")


@router.get("/readiness")
async def readiness_check() -> Dict[str, Any]:
    """Kubernetes-style readiness probe."""
    try:
        health_status = await health_checker.check_all_services()
        overall_status = health_status.get("overall_status", "unknown")
        
        # Service is ready if it's healthy or degraded (but not critical)
        if overall_status in ["healthy", "degraded"]:
            return {
                "status": "ready",
                "overall_status": overall_status
            }
        else:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "not_ready",
                    "overall_status": overall_status,
                    "reason": "Critical services are unavailable"
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Readiness check failed")


@router.get("/connections")
async def connection_diagnostics() -> Dict[str, Any]:
    """Connection diagnostics for API Gateway and service connectivity."""
    try:
        health_summary = await connection_health_service.get_health_summary()
        diagnostics = await connection_health_service.diagnose_connection_issues()
        
        return {
            "connection_summary": health_summary,
            "diagnostics": diagnostics,
            "timestamp": None
        }
        
    except Exception as e:
        logger.error("Connection diagnostics failed", error=str(e))
        raise HTTPException(status_code=500, detail="Connection diagnostics failed")


@router.get("/liveness")
async def liveness_check() -> Dict[str, Any]:
    """Kubernetes-style liveness probe."""
    try:
        # Simple check to ensure the service is alive
        # This should not depend on external services
        return {
            "status": "alive",
            "service": "ai-copilot"
        }
    except Exception as e:
        logger.error("Liveness check failed", error=str(e))
        raise HTTPException(status_code=500, detail="Liveness check failed")
