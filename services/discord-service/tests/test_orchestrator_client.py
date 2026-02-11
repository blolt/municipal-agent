"""Tests for GatewayClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.core.gateway_client import GatewayClient
from src.events.internal_event import InternalEvent, EventSource, RoutingContext


@pytest.fixture
def sample_event() -> InternalEvent:
    """Create a sample event for testing."""
    return InternalEvent(
        correlation_id="test-corr-123",
        source=EventSource.DISCORD,
        source_event_id="msg-123",
        source_channel_id="channel-456",
        source_user_id="user-789",
        content="Test message content",
        routing=RoutingContext(reply_channel_id="channel-456"),
        metadata={"source": "discord", "test_key": "test_value"},
    )


@pytest.mark.asyncio
async def test_send_event_success(sample_event: InternalEvent):
    """Test sending an event successfully."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
        client = GatewayClient(
            base_url="http://test-orchestrator",
            service_auth_secret="test-secret",
        )

        await client.send_event(sample_event)

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "/process"
        json_payload = kwargs["json"]
        assert json_payload["message"] == "Test message content"
        assert json_payload["thread_id"] == "channel-456"
        assert json_payload["correlation_id"] == "test-corr-123"
        assert json_payload["metadata"]["source"] == "discord"


@pytest.mark.asyncio
async def test_send_event_timeout():
    """Test that the client uses 120s timeout for agent processing."""
    client = GatewayClient(
        base_url="http://test-orchestrator",
        service_auth_secret="test-secret",
    )
    assert client.client.timeout.read == 120.0
    await client.close()
