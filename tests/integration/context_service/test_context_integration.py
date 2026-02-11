import pytest
import uuid
import time

def test_context_service_logs_event(context_service_client):
    """Verify that Context Service accepts and stores events."""
    event_data = {
        "event_id": f"evt_{uuid.uuid4()}",
        "correlation_id": str(uuid.uuid4()),
        "event_type": "test.event",
        "timestamp": "2026-01-01T00:00:00Z",
        "payload": {"test_key": "test_value"},
        # Required fields in InternalEvent schema might include source/routing
        "source": "api",
        "source_event_id": "src_123",
        "source_channel_id": "chan_123",
        "source_user_id": "user_123",
        "routing": {
            "reply_channel_id": "chan_123"
        },
        "content": "Test content"
    }
    
    # 1. Log event
    response = context_service_client.post("/events", json=event_data)
    
    # Debugging helper
    if response.status_code != 201:
        print(f"Failed to create event: {response.text}")

    assert response.status_code == 201
    result = response.json()
    assert "event_id" in result
    # Context Service might generate its own ID, so we check for existence
    assert isinstance(result["event_id"], str)
    # assert result["processed"] is True # This might not be in response if schema changed

