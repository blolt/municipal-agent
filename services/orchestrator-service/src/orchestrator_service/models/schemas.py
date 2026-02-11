"""Pydantic models for API request/response validation."""
from pydantic import BaseModel, Field
from typing import Any, Dict
from uuid import UUID, uuid4


class ProcessEventRequest(BaseModel):
    """Request to process an event through the agent."""
    
    thread_id: str = Field(..., description="Thread ID for conversation continuity")
    message: str = Field(..., description="User message to process")
    correlation_id: UUID = Field(default_factory=uuid4, description="Event correlation ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ProcessEventResponse(BaseModel):
    """Response from processing an event."""
    
    thread_id: str
    response: str
    correlation_id: UUID
    checkpoint_id: str | None = None


class AgentRunRequest(BaseModel):
    """Request to run the agent with streaming."""
    
    input: str = Field(..., description="User input message")
    thread_id: str = Field(..., description="Thread ID for conversation continuity")
    config: Dict[str, Any] = Field(default_factory=dict, description="Additional configuration")
    correlation_id: UUID = Field(default_factory=uuid4, description="Event correlation ID")
