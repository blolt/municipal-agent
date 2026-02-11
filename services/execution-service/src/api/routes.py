"""API routes for Execution Service."""

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from agentic_common.auth import ServiceAuthDependency, ServiceIdentity
from src.api.models import ExecuteRequest, ExecuteResponse, HealthResponse, ToolListResponse
from src.core.config import settings
from src.core.logging import get_logger
from src.mcp.connection_manager import ConnectionManager

logger = get_logger(__name__)

router = APIRouter()

# Auth dependency — only orchestrator-service may call Execution Service
require_service_auth = ServiceAuthDependency(
    secret=settings.service_auth_secret,
    allowed_services=["orchestrator-service"],
)

# Global connection manager instance
connection_manager: ConnectionManager | None = None


def set_connection_manager(manager: ConnectionManager) -> None:
    """Set the global connection manager instance."""
    global connection_manager
    connection_manager = manager


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    if connection_manager is None:
        return HealthResponse(status="unhealthy", mcp_servers={})

    server_status = connection_manager.get_server_status()
    all_healthy = all(status == "running" for status in server_status.values())

    return HealthResponse(
        status="healthy" if all_healthy else "unhealthy",
        mcp_servers=server_status,
    )


@router.get("/tools", response_model=ToolListResponse)
async def list_tools(
    caller: ServiceIdentity = Depends(require_service_auth),
) -> ToolListResponse:
    """List all available tools from all MCP servers."""
    if connection_manager is None:
        raise HTTPException(status_code=503, detail="Connection manager not initialized")

    try:
        tools = await connection_manager.get_all_tools()
        logger.info(f"Returning {len(tools)} tools")
        return ToolListResponse(tools=tools)
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute", response_model=ExecuteResponse)
async def execute_tool(
    request: ExecuteRequest,
    caller: ServiceIdentity = Depends(require_service_auth),
) -> ExecuteResponse:
    """Execute a tool on the appropriate MCP server."""
    if connection_manager is None:
        raise HTTPException(status_code=503, detail="Connection manager not initialized")

    start_time = time.time()

    try:
        logger.info(f"Executing tool: {request.tool_name}")
        result = await connection_manager.execute_tool(
            tool_name=request.tool_name,
            arguments=request.arguments,
            timeout=request.timeout,
        )

        execution_time_ms = (time.time() - start_time) * 1000

        return ExecuteResponse(
            status="success",
            output=result,
            execution_time_ms=execution_time_ms,
        )

    except ValueError as e:
        # Tool not found
        logger.error(f"Tool not found: {e}")
        execution_time_ms = (time.time() - start_time) * 1000
        return ExecuteResponse(
            status="error",
            error=str(e),
            execution_time_ms=execution_time_ms,
        )

    except Exception as e:
        # Execution error
        logger.error(f"Tool execution failed: {e}")
        execution_time_ms = (time.time() - start_time) * 1000
        return ExecuteResponse(
            status="error",
            error=str(e),
            execution_time_ms=execution_time_ms,
        )
