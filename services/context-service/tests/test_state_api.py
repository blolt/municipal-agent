"""Unit tests for state API."""
import pytest
from httpx import AsyncClient, ASGITransport
from context_service.main import app


@pytest.mark.asyncio
async def test_save_and_retrieve_checkpoint():
    """Test saving and retrieving a checkpoint."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Save a checkpoint
        response = await client.post(
            "/state/test-thread-123",
            json={
                "checkpoint_id_str": "checkpoint-1",
                "state_dump": {"messages": [{"role": "user", "content": "hello"}]},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["thread_id"] == "test-thread-123"
        assert data["checkpoint_id_str"] == "checkpoint-1"

        # Retrieve the latest checkpoint
        response = await client.get("/state/test-thread-123")
        assert response.status_code == 200
        retrieved = response.json()
        assert retrieved["thread_id"] == "test-thread-123"
        assert retrieved["state_dump"]["messages"][0]["content"] == "hello"


@pytest.mark.asyncio
async def test_get_checkpoint_not_found():
    """Test retrieving a non-existent checkpoint."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/state/non-existent-thread")
        assert response.status_code == 404
