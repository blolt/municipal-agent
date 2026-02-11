"""Unit tests for events API."""
import pytest
from httpx import AsyncClient, ASGITransport
from context_service.main import app


@pytest.mark.asyncio
async def test_create_event():
    """Test event ingestion endpoint."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/events",
            json={
                "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
                "event_type": "webhook.test",
                "source": "test_client",
                "payload": {"message": "test event"},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "event_id" in data
        assert "created_at" in data


@pytest.mark.asyncio
async def test_create_event_validation_error():
    """Test event ingestion with invalid data."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/events",
            json={
                "correlation_id": "invalid-uuid",  # Invalid UUID
                "event_type": "test",
                "source": "test",
                "payload": {},
            },
        )

        assert response.status_code == 422  # Validation error
