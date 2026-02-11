"""Unit tests for state API."""
import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from datetime import datetime
from fastapi.testclient import TestClient
from context_service.main import app
from context_service.models.schemas import CheckpointResponse

client = TestClient(app)

@pytest.mark.asyncio
async def test_get_latest_state():
    """Test GET /state/{thread_id}."""
    mock_checkpoint = CheckpointResponse(
        checkpoint_id=uuid4(),
        run_id=uuid4(),
        thread_id="thread-1",
        checkpoint_ns="",
        checkpoint_id_str="chk-1",
        parent_checkpoint_id_str=None,
        state_dump={"key": "value"},
        created_at=datetime.now()
    )
    
    with patch("context_service.api.state.StateRepository.get_latest_checkpoint", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_checkpoint
        
        response = client.get("/state/thread-1")
        
        assert response.status_code == 200
        assert response.json()["thread_id"] == "thread-1"
        mock_get.assert_called_once_with("thread-1")

@pytest.mark.asyncio
async def test_get_latest_state_not_found():
    """Test GET /state/{thread_id} not found."""
    with patch("context_service.api.state.StateRepository.get_latest_checkpoint", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        
        response = client.get("/state/thread-1")
        
        assert response.status_code == 404

@pytest.mark.asyncio
async def test_save_checkpoint():
    """Test POST /state/{thread_id}."""
    mock_checkpoint = CheckpointResponse(
        checkpoint_id=uuid4(),
        run_id=uuid4(),
        thread_id="thread-1",
        checkpoint_ns="",
        checkpoint_id_str="chk-1",
        parent_checkpoint_id_str=None,
        state_dump={"key": "value"},
        created_at=datetime.now()
    )
    
    with patch("context_service.api.state.StateRepository.save_checkpoint", new_callable=AsyncMock) as mock_save:
        mock_save.return_value = mock_checkpoint
        
        response = client.post(
            "/state/thread-1",
            json={
                "checkpoint_id_str": "chk-1",
                "state_dump": {"key": "value"}
            }
        )
        
        assert response.status_code == 201
        assert response.json()["checkpoint_id_str"] == "chk-1"
