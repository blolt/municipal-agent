"""API request/response models."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolSchema(BaseModel):
    """Schema for a tool definition."""

    model_config = {"populate_by_name": True}

    name: str
    description: str
    inputSchema: dict[str, Any] = Field(alias="input_schema")


class ExecuteRequest(BaseModel):
    """Request to execute a tool."""

    tool_name: str
    arguments: dict[str, Any]
    timeout: int | None = None


class ExecuteResponse(BaseModel):
    """Response from tool execution."""

    status: Literal["success", "error"]
    output: dict[str, Any] | None = None
    error: str | None = None
    execution_time_ms: float


class ToolListResponse(BaseModel):
    """Response containing list of available tools."""

    tools: list[ToolSchema]


class HealthResponse(BaseModel):
    """Health check response."""

    status: Literal["healthy", "unhealthy"]
    version: str = "0.1.0"
    mcp_servers: dict[str, str] = Field(default_factory=dict)
