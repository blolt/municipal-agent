"""Unit tests for repositories."""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from datetime import datetime
from context_service.db.repositories import EventRepository, StateRepository, GraphRepository
from context_service.models.schemas import InternalEvent, CheckpointCreate

@pytest.mark.asyncio
async def test_create_event():
    """Test EventRepository.create_event."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {"event_id": uuid4(), "created_at": datetime.now()}
    
    # Mock the context manager
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_conn
    mock_ctx.__aexit__.return_value = None
    
    with patch("context_service.db.repositories.get_db_connection", return_value=mock_ctx):
        event = InternalEvent(
            correlation_id=uuid4(),
            event_type="test",
            source="test",
            payload={"key": "value"}
        )
        result = await EventRepository.create_event(event)
        
        assert "event_id" in result
        mock_conn.fetchrow.assert_called_once()
        # Verify JSON serialization
        args = mock_conn.fetchrow.call_args[0]
        assert json.loads(args[4]) == {"key": "value"}

@pytest.mark.asyncio
async def test_save_checkpoint():
    """Test StateRepository.save_checkpoint."""
    mock_conn = AsyncMock()
    # Mock run creation
    mock_conn.fetchrow.side_effect = [
        {"run_id": uuid4()}, # First call (create run)
        { # Second call (create checkpoint)
            "checkpoint_id": uuid4(),
            "run_id": uuid4(),
            "thread_id": "thread-1",
            "checkpoint_ns": "",
            "checkpoint_id_str": "chk-1",
            "parent_checkpoint_id_str": None,
            "state_dump": '{"key": "value"}', # Returned as string from DB
            "created_at": datetime.now()
        }
    ]
    
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_conn
    
    with patch("context_service.db.repositories.get_db_connection", return_value=mock_ctx):
        checkpoint = CheckpointCreate(
            checkpoint_id_str="chk-1",
            state_dump={"key": "value"}
        )
        result = await StateRepository.save_checkpoint("thread-1", checkpoint)
        
        assert result.checkpoint_id_str == "chk-1"
        assert result.state_dump == {"key": "value"}

@pytest.mark.asyncio
async def test_query_graph():
    """Test GraphRepository.query_graph."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [{"result": '{"name": "Alice"}'}]
    
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_conn
    
    with patch("context_service.db.repositories.get_db_connection", return_value=mock_ctx):
        result = await GraphRepository.query_graph("MATCH (n) RETURN n")
        
        assert len(result) == 1
        assert result[0]["result"] == '{"name": "Alice"}'
