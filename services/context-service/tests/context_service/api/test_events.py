"""Unit tests for events API."""
import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from datetime import datetime
from fastapi.testclient import TestClient
from context_service.main import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_create_event_endpoint():
    """Test POST /events endpoint."""
    with patch("context_service.api.events.EventRepository.create_event", new_callable=AsyncMock) as mock_create:
        event_id = uuid4()
        mock_create.return_value = {"event_id": event_id, "created_at": datetime.now()}
        
        response = client.post(
            "/events",
            json={
                "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
                "event_type": "test",
                "source": "test",
                "payload": {"key": "value"}
            }
        )
        
        assert response.status_code == 201
        assert response.json()["event_id"] == str(event_id)
        mock_create.assert_called_once()

def test_create_event_invalid_input():
    """Test POST /events with invalid input."""
    response = client.post(
        "/events",
        json={
            "correlation_id": "invalid",
            "event_type": "test",
            "source": "test",
            "payload": {}
        }
    )
    assert response.status_code == 422
