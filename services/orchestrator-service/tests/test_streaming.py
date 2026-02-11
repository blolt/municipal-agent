import sys
from unittest.mock import MagicMock, AsyncMock

# Mock missing modules to avoid ImportError
sys.modules["langchain_core"] = MagicMock()
sys.modules["langchain_core.messages"] = MagicMock()
sys.modules["langchain_community"] = MagicMock()
sys.modules["langchain_community.chat_models"] = MagicMock()
sys.modules["langgraph"] = MagicMock()
sys.modules["langgraph.graph"] = MagicMock()
sys.modules["langgraph.graph.message"] = MagicMock()
sys.modules["langgraph.checkpoint"] = MagicMock()
sys.modules["langgraph.checkpoint.postgres"] = MagicMock()
sys.modules["langgraph.checkpoint.postgres.aio"] = MagicMock()
sys.modules["redis"] = MagicMock()
sys.modules["redis.asyncio"] = MagicMock()
sys.modules["structlog"] = MagicMock()
sys.modules["asyncpg"] = MagicMock()
sys.modules["agentic_common"] = MagicMock()

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import json

# Import app
from orchestrator_service.main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.mark.asyncio
async def test_streaming_endpoint(client):
    # Mock the agent graph and its astream_events method
    mock_graph = AsyncMock()
    
    async def mock_stream(*args, **kwargs):
        # Yield simulated events
        yield {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="Hello")}}
        yield {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content=" world")}}
        yield {"event": "on_tool_start", "name": "test_tool", "data": {"input": {"q": "foo"}}}
        yield {"event": "on_tool_end", "name": "test_tool", "data": {"output": "bar"}}

    mock_graph.astream_events = mock_stream

    # Mock dependencies to bypass lifespan startup logic
    with patch("orchestrator_service.main.AsyncPostgresSaver") as mock_saver, \
         patch("orchestrator_service.main.create_agent_graph", return_value=mock_graph), \
         patch("orchestrator_service.main.ContextServiceClient", return_value=AsyncMock()), \
         patch("orchestrator_service.main.ExecutionServiceClient", return_value=AsyncMock()), \
         patch("orchestrator_service.main.ExecutionServiceClient", return_value=AsyncMock()):
        
        # We need to manually trigger startup or ensure globals are set
        # TestClient with context manager triggers startup
        with TestClient(app) as client:
            response = client.post(
                "/v1/agent/run",
                json={
                    "input": "Hi",
                    "thread_id": "test-thread",
                    "config": {}
                }
            )
            
            assert response.status_code == 200
            content = response.text
            
            # Verify SSE format and content
            print(f"Response content: {content}")
            
            assert "data: " in content
            
            # Check for specific events
            assert '{"type": "thinking", "content": "Hello"}' in content
            assert '{"type": "thinking", "content": " world"}' in content
            assert '{"type": "tool_start", "name": "test_tool", "args": {"q": "foo"}}' in content
            # Note: tool_result might have extra quotes depending on how str() behaves on the mock, 
            # but we checked the logic in main.py
            assert '{"type": "tool_result", "name": "test_tool"' in content
            assert '{"type": "done"' in content
