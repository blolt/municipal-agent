"""Pydantic models for API request/response validation."""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class InternalEvent(BaseModel):
    """Normalized event schema for all ingress/egress signals."""

    correlation_id: UUID
    event_type: str = Field(..., max_length=50)
    source: str = Field(..., max_length=100)
    payload: Dict[str, Any]


class InternalEventResponse(BaseModel):
    """Response after ingesting an event."""

    event_id: UUID
    created_at: datetime


class CheckpointCreate(BaseModel):
    """Request to save a new checkpoint."""

    run_id: Optional[UUID] = None
    checkpoint_ns: str = ""
    checkpoint_id_str: str
    parent_checkpoint_id_str: Optional[str] = None
    state_dump: Dict[str, Any]


class CheckpointResponse(BaseModel):
    """Response with checkpoint data."""

    checkpoint_id: UUID
    run_id: UUID
    thread_id: str
    checkpoint_ns: str
    checkpoint_id_str: str
    parent_checkpoint_id_str: Optional[str]
    state_dump: Dict[str, Any]
    created_at: datetime


class AgentState(BaseModel):
    """LangGraph state structure (simplified for MVP)."""

    messages: list[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeQuery(BaseModel):
    """Query parameters for knowledge retrieval."""

    query: str
    strategies: list[str] = Field(default=["graph"])
    filters: Optional[Dict[str, Any]] = None


class KnowledgeQueryResponse(BaseModel):
    """Response from knowledge query."""

    results: list[Dict[str, Any]]
    metadata: Dict[str, Any] = Field(default_factory=dict)
