import os
import asyncio
import uuid
from unittest.mock import MagicMock

import pytest

# We need to import GatewayClient from discord-service code.
# The test runner MUST have services/discord-service in PYTHONPATH.
try:
    from src.core.gateway_client import GatewayClient
    from src.events.internal_event import InternalEvent, EventSource, RoutingContext
except ImportError:
    pytest.skip("Discord Service source code not found in PYTHONPATH", allow_module_level=True)

@pytest.mark.asyncio
async def test_discord_client_can_stream_from_orchestrator(orchestrator_service_client, service_auth_secret):
    """Verify that the Discord GatewayClient can successfully stream from the real Orchestrator."""

    # We use the authenticated URL of the orchestrator from the fixture, but the client
    # expects a base_url string.
    orchestrator_url = str(orchestrator_service_client.base_url)

    client = GatewayClient(base_url=orchestrator_url, service_auth_secret=service_auth_secret)
    
    event = InternalEvent(
        correlation_id=str(uuid.uuid4()),
        source=EventSource.DISCORD,
        source_event_id="msg-int-1",
        source_channel_id="channel-int-1",
        source_user_id="user-int-1",
        content="Hello from Discord Integration Test",
        routing=RoutingContext(reply_channel_id="channel-int-1"),
        metadata={"test": True}
    )
    
    chunks = []
    try:
        async for chunk in client.stream_event(event):
            chunks.append(chunk)
    finally:
        await client.close()
        
    assert len(chunks) > 0
    # Depending on the agent response, we might see "thinking" or "Hello" etc.
    # Just asserting we got something back is enough to prove the connection and protocol worked.
