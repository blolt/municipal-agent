"""Tests for InternalEvent model."""

from datetime import datetime, timezone

import pytest

from src.events import ContentType, EventSource, InternalEvent, RoutingContext


class TestRoutingContext:
    """Tests for RoutingContext model."""

    def test_minimal_routing_context(self):
        """Test creating routing context with required fields only."""
        routing = RoutingContext(reply_channel_id="123456")
        
        assert routing.reply_channel_id == "123456"
        assert routing.reply_thread_id is None
        assert routing.forward_to == []
        assert routing.conversation_id is None

    def test_full_routing_context(self):
        """Test creating routing context with all fields."""
        routing = RoutingContext(
            reply_channel_id="123456",
            reply_thread_id="thread-1",
            reply_metadata={"guild_id": "789"},
            forward_to=["slack:C123", "email:user@example.com"],
            conversation_id="conv-1",
            parent_message_id="msg-0",
        )
        
        assert routing.reply_channel_id == "123456"
        assert routing.reply_thread_id == "thread-1"
        assert routing.reply_metadata == {"guild_id": "789"}
        assert routing.forward_to == ["slack:C123", "email:user@example.com"]


class TestInternalEvent:
    """Tests for InternalEvent model."""

    def test_create_minimal_event(self):
        """Test creating event with required fields only."""
        routing = RoutingContext(reply_channel_id="123456")
        event = InternalEvent(
            source=EventSource.DISCORD,
            source_event_id="msg-123",
            source_channel_id="123456",
            source_user_id="user-1",
            content="Hello, world!",
            routing=routing,
        )
        
        assert event.source == EventSource.DISCORD
        assert event.source_event_id == "msg-123"
        assert event.source_channel_id == "123456"
        assert event.source_user_id == "user-1"
        assert event.content == "Hello, world!"
        assert event.content_type == ContentType.TEXT
        assert event.correlation_id  # Auto-generated
        assert event.timestamp <= datetime.now(timezone.utc)

    def test_create_full_event(self):
        """Test creating event with all fields."""
        routing = RoutingContext(
            reply_channel_id="123456",
            conversation_id="conv-1",
        )
        event = InternalEvent(
            correlation_id="corr-123",
            parent_correlation_id="corr-parent",
            source=EventSource.DISCORD,
            source_event_id="msg-123",
            source_channel_id="123456",
            source_user_id="user-1",
            source_user_name="Test User",
            content_type=ContentType.TEXT,
            content="Hello, world!",
            attachments=[{"id": "att-1", "url": "https://example.com/file.png"}],
            routing=routing,
            metadata={"guild_name": "Test Guild"},
        )
        
        assert event.correlation_id == "corr-123"
        assert event.parent_correlation_id == "corr-parent"
        assert event.source_user_name == "Test User"
        assert len(event.attachments) == 1
        assert event.metadata["guild_name"] == "Test Guild"

    def test_serialization_roundtrip(self):
        """Test that events can be serialized and deserialized."""
        routing = RoutingContext(reply_channel_id="123456")
        original = InternalEvent(
            source=EventSource.DISCORD,
            source_event_id="msg-123",
            source_channel_id="123456",
            source_user_id="user-1",
            content="Hello, world!",
            routing=routing,
            metadata={"key": "value"},
        )
        
        # Serialize to dict
        data = original.to_queue_message()
        
        # Deserialize back
        restored = InternalEvent.from_queue_message(data)
        
        assert restored.correlation_id == original.correlation_id
        assert restored.source == original.source
        assert restored.content == original.content
        assert restored.routing.reply_channel_id == original.routing.reply_channel_id
        assert restored.metadata == original.metadata

    def test_all_event_sources(self):
        """Test all event source types."""
        for source in EventSource:
            routing = RoutingContext(reply_channel_id="123")
            event = InternalEvent(
                source=source,
                source_event_id="123",
                source_channel_id="456",
                source_user_id="789",
                content="test",
                routing=routing,
            )
            assert event.source == source
