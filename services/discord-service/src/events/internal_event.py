"""Internal event schema and routing context for Municipal Agent.

This module defines the canonical event format used throughout the system.
All external events are normalized to InternalEvent before being published to the queue.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EventSource(str, Enum):
    """Supported event sources."""

    DISCORD = "discord"
    SLACK = "slack"
    TWILIO = "twilio"
    IMAP = "imap"
    API = "api"


class ContentType(str, Enum):
    """Content types for event payloads."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    FILE = "file"
    REACTION = "reaction"
    EDIT = "edit"


class RoutingContext(BaseModel):
    """Context needed to route responses back to source or to other destinations.

    This enables many-to-many routing between sources and destinations.
    """

    # Source reply context (how to reply to the original source)
    reply_channel_id: str = Field(..., description="Channel/conversation to send reply")
    reply_thread_id: str | None = Field(default=None, description="Thread ID for threading")
    reply_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Platform-specific reply data"
    )

    # Alternative destinations (for many-to-many routing)
    forward_to: list[str] = Field(
        default_factory=list,
        description="Forward destinations, e.g. ['slack:C123', 'email:user@example.com']",
    )

    # Conversation context
    conversation_id: str | None = Field(
        default=None, description="Groups related messages across turns"
    )
    parent_message_id: str | None = Field(
        default=None, description="Parent message for threading"
    )


class InternalEvent(BaseModel):
    """Canonical event schema for the Municipal Agent system.

    All external payloads are normalized to this format before processing.
    """

    # Identity
    correlation_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique ID for distributed tracing",
    )
    parent_correlation_id: str | None = Field(
        default=None, description="Parent correlation ID for threaded conversations"
    )

    # Source information
    source: EventSource = Field(..., description="Platform that generated this event")
    source_event_id: str = Field(..., description="Original event ID from the platform")
    source_channel_id: str = Field(..., description="Channel/room/thread ID on source platform")
    source_user_id: str = Field(..., description="User who triggered the event")
    source_user_name: str | None = Field(default=None, description="Display name of the user")

    # Content
    content_type: ContentType = Field(default=ContentType.TEXT, description="Type of content")
    content: str = Field(..., description="The actual message content")
    attachments: list[dict[str, Any]] = Field(
        default_factory=list, description="Attached files/media"
    )

    # Routing
    routing: RoutingContext = Field(..., description="Routing context for responses")

    # Metadata
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event timestamp",
    )
    raw_payload: dict[str, Any] | None = Field(
        default=None, description="Original webhook/event payload for debugging"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional platform-specific metadata"
    )

    def to_queue_message(self) -> dict[str, Any]:
        """Serialize event for queue transport."""
        return self.model_dump(mode="json")

    @classmethod
    def from_queue_message(cls, data: dict[str, Any]) -> "InternalEvent":
        """Deserialize event from queue message."""
        return cls.model_validate(data)
