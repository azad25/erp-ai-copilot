"""
Infrastructure management API endpoints.
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
import structlog
from ...core.exceptions import AICopilotException, AuthorizationError
from ...services.infrastructure_service import InfrastructureService
from ...core.command_executor import CommandType, ExecutionLevel
from ...models.api import (
    InfrastructureCommandRequest,
    InfrastructureCommandResponse,
    SystemOverviewResponse,
    SystemMetricsResponse,
    ContainerLogsResponse,
    ContainerActionResponse,
    ErrorResponse
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/infrastructure", tags=["Infrastructure"])


async def get_infrastructure_service() -> InfrastructureService:
    """Dependency to get infrastructure service."""
    return InfrastructureService()


@router.get("/overview", response_model=SystemOverviewResponse)
async def get_system_overview(
    service: InfrastructureService = Depends(get_infrastructure_service)
):
    """Get comprehensive system overview."""
    try:
        overview = await service.get_system_overview()
        return SystemOverviewResponse(
            success=True,
            data=overview,
            message="System overview retrieved successfully"
        )
    except Exception as e:
        logger.error("Failed to get system overview", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", response_model=SystemMetricsResponse)
async def get_system_metrics(
    service: InfrastructureService = Depends(get_infrastructure_service)
):
    """Get real-time system metrics."""
    try:
        metrics = await service.get_system_metrics()
        return SystemMetricsResponse(
            success=True,
            data=metrics,
            message="System metrics retrieved successfully"
        )
    except Exception as e:
        logger.error("Failed to get system metrics", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/command", response_model=InfrastructureCommandResponse)
async def execute_infrastructure_command(
    request: InfrastructureCommandRequest,
    service: InfrastructureService = Depends(get_infrastructure_service)
):
    """Execute an infrastructure command."""
    try:
        # Validate command type
        try:
            command_type = CommandType(request.command_type)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid command type: {request.command_type}"
            )
        
        # Validate execution level
        try:
            execution_level = ExecutionLevel(request.execution_level)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid execution level: {request.execution_level}"
            )
        
        # Execute command
        result = await service.execute_infrastructure_command(
            command=request.command,
            command_type=command_type,
            execution_level=execution_level,
            timeout=request.timeout
        )
        
        return InfrastructureCommandResponse(
            success=True,
            data={
                "success": result.success,
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "execution_time": result.execution_time,
                "command": result.command,
                "command_type": result.command_type.value,
                "execution_level": result.execution_level.value,
                "metadata": result.metadata
            },
            message="Command executed successfully" if result.success else "Command failed"
        )
        
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except AICopilotException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        logger.error("Failed to execute infrastructure command", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/containers", response_model=Dict[str, Any])
async def get_containers(
    service: InfrastructureService = Depends(get_infrastructure_service)
):
    """Get container status information."""
    try:
        overview = await service.get_system_overview()
        containers = overview.get("containers", [])
        
        return {
            "success": True,
            "data": containers,
            "message": f"Retrieved {len(containers)} containers",
            "count": len(containers)
        }
    except Exception as e:
        logger.error("Failed to get containers", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/containers/{container_name}/logs", response_model=ContainerLogsResponse)
async def get_container_logs(
    container_name: str,
    lines: int = Query(100, ge=1, le=1000, description="Number of log lines to retrieve"),
    service: InfrastructureService = Depends(get_infrastructure_service)
):
    """Get container logs."""
    try:
        logs = await service.get_container_logs(container_name, lines)
        
        return ContainerLogsResponse(
            success=True,
            data={
                "container_name": container_name,
                "lines": lines,
                "logs": logs,
                "timestamp": None  # Will be set by response model
            },
            message=f"Retrieved {lines} log lines for container {container_name}"
        )
    except Exception as e:
        logger.error("Failed to get container logs", container=container_name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/containers/{container_name}/restart", response_model=ContainerActionResponse)
async def restart_container(
    container_name: str,
    service: InfrastructureService = Depends(get_infrastructure_service)
):
    """Restart a container."""
    try:
        success = await service.restart_container(container_name)
        
        if success:
            return ContainerActionResponse(
                success=True,
                data={
                    "container_name": container_name,
                    "action": "restart",
                    "status": "success"
                },
                message=f"Container {container_name} restarted successfully"
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to restart container {container_name}"
            )
            
    except Exception as e:
        logger.error("Failed to restart container", container=container_name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/databases", response_model=Dict[str, Any])
async def get_databases(
    service: InfrastructureService = Depends(get_infrastructure_service)
):
    """Get database status information."""
    try:
        overview = await service.get_system_overview()
        databases = overview.get("databases", [])
        
        return {
            "success": True,
            "data": databases,
            "message": f"Retrieved {len(databases)} databases",
            "count": len(databases)
        }
    except Exception as e:
        logger.error("Failed to get databases", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/network", response_model=Dict[str, Any])
async def get_network_status(
    service: InfrastructureService = Depends(get_infrastructure_service)
):
    """Get network status information."""
    try:
        overview = await service.get_system_overview()
        network = overview.get("network", {})
        
        return {
            "success": True,
            "data": network,
            "message": "Network status retrieved successfully"
        }
    except Exception as e:
        logger.error("Failed to get network status", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system", response_model=Dict[str, Any])
async def get_system_info(
    service: InfrastructureService = Depends(get_infrastructure_service)
):
    """Get basic system information."""
    try:
        system_info = service.command_executor.get_system_info()
        
        return {
            "success": True,
            "data": system_info,
            "message": "System information retrieved successfully"
        }
    except Exception as e:
        logger.error("Failed to get system info", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/allowed-commands", response_model=Dict[str, Any])
async def get_allowed_commands(
    service: InfrastructureService = Depends(get_infrastructure_service)
):
    """Get list of allowed commands by type."""
    try:
        allowed_commands = service.command_executor.get_allowed_commands()
        
        return {
            "success": True,
            "data": allowed_commands,
            "message": "Allowed commands retrieved successfully"
        }
    except Exception as e:
        logger.error("Failed to get allowed commands", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache", response_model=Dict[str, Any])
async def clear_cache(
    service: InfrastructureService = Depends(get_infrastructure_service)
):
    """Clear the infrastructure service cache."""
    try:
        service.clear_cache()
        
        return {
            "success": True,
            "data": {"cache_cleared": True},
            "message": "Cache cleared successfully"
        }
    except Exception as e:
        logger.error("Failed to clear cache", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/info", response_model=Dict[str, Any])
async def get_cache_info(
    service: InfrastructureService = Depends(get_infrastructure_service)
):
    """Get cache information."""
    try:
        cache_info = service.get_cache_info()
        
        return {
            "success": True,
            "data": cache_info,
            "message": "Cache information retrieved successfully"
        }
    except Exception as e:
        logger.error("Failed to get cache info", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=Dict[str, Any])
async def infrastructure_health_check(
    service: InfrastructureService = Depends(get_infrastructure_service)
):
    """Health check for infrastructure service."""
    try:
        # Try to get basic system info
        system_info = service.command_executor.get_system_info()
        
        return {
            "success": True,
            "status": "healthy",
            "data": {
                "service": "infrastructure",
                "system_info": system_info,
                "timestamp": None  # Will be set by response model
            },
            "message": "Infrastructure service is healthy"
        }
    except Exception as e:
        logger.error("Infrastructure health check failed", error=str(e))
        return {
            "success": False,
            "status": "unhealthy",
            "data": {
                "service": "infrastructure",
                "error": str(e),
                "timestamp": None
            },
            "message": "Infrastructure service is unhealthy"
        }
