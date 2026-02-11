"""Unit tests for Pydantic models."""
import pytest
from uuid import uuid4
from datetime import datetime
from pydantic import ValidationError
from context_service.models.schemas import InternalEvent, CheckpointCreate, CheckpointResponse

def test_internal_event_valid():
    """Test creating a valid InternalEvent."""
    event = InternalEvent(
        correlation_id=uuid4(),
        event_type="test.event",
        source="test",
        payload={"key": "value"}
    )
    assert event.event_type == "test.event"
    assert event.payload["key"] == "value"

def test_internal_event_invalid_uuid():
    """Test InternalEvent validation with invalid UUID."""
    with pytest.raises(ValidationError):
        InternalEvent(
            correlation_id="invalid-uuid",
            event_type="test",
            source="test",
            payload={}
        )

def test_checkpoint_create_valid():
    """Test creating a valid CheckpointCreate."""
    checkpoint = CheckpointCreate(
        checkpoint_id_str="chk-1",
        state_dump={"key": "value"}
    )
    assert checkpoint.checkpoint_id_str == "chk-1"
    assert checkpoint.state_dump["key"] == "value"
    assert checkpoint.checkpoint_ns == ""  # Default value

def test_checkpoint_response_valid():
    """Test creating a valid CheckpointResponse."""
    checkpoint = CheckpointResponse(
        checkpoint_id=uuid4(),
        run_id=uuid4(),
        thread_id="thread-1",
        checkpoint_ns="",
        checkpoint_id_str="chk-1",
        parent_checkpoint_id_str=None,
        state_dump={"key": "value"},
        created_at=datetime.now()
    )
    assert checkpoint.thread_id == "thread-1"
