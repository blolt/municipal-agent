"""Tests for DiscordGatewayHandler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.gateway_client import GatewayClient
from src.handlers.discord import DiscordGatewayHandler


@pytest.fixture
def mock_gateway_client():
    """Create a mock GatewayClient."""
    client = MagicMock(spec=GatewayClient)
    client.send_event = AsyncMock()
    return client


@pytest.fixture
def handler(mock_gateway_client):
    """Create a DiscordGatewayHandler with mocked dependencies."""
    return DiscordGatewayHandler(gateway_client=mock_gateway_client)


def _make_discord_message(**overrides):
    """Create a mock Discord message with sensible defaults."""
    message = MagicMock()
    message.author.bot = overrides.get("bot", False)
    message.content = overrides.get("content", "Hello world")
    message.id = overrides.get("id", "12345")
    message.channel.id = overrides.get("channel_id", "67890")
    message.author.id = overrides.get("author_id", "11111")
    message.author.display_name = overrides.get("display_name", "Test User")
    message.attachments = overrides.get("attachments", [])
    message.guild.id = overrides.get("guild_id", "99999")
    message.guild.name = overrides.get("guild_name", "Test Guild")
    message.reference = overrides.get("reference", None)
    message.thread = overrides.get("thread", None)
    message.mentions = overrides.get("mentions", [])
    return message


@pytest.mark.asyncio
async def test_on_message_fires_and_forgets(handler, mock_gateway_client):
    """Test that incoming messages are forwarded via fire-and-forget."""
    message = _make_discord_message()

    # Simulate receiving message
    await handler.on_message(message)

    # Allow the background task to run
    import asyncio
    await asyncio.sleep(0.01)

    # Verify send_event was called (not stream_event)
    mock_gateway_client.send_event.assert_called_once()

    # Verify the event was properly normalized
    event = mock_gateway_client.send_event.call_args[0][0]
    assert event.content == "Hello world"
    assert event.source_channel_id == "67890"
    assert event.source_user_id == "11111"
    assert event.metadata["source"] == "discord"


@pytest.mark.asyncio
async def test_on_message_ignores_bots(handler, mock_gateway_client):
    """Test that bot messages are ignored."""
    message = _make_discord_message(bot=True)

    await handler.on_message(message)

    mock_gateway_client.send_event.assert_not_called()


@pytest.mark.asyncio
async def test_on_message_no_streaming_no_placeholder(handler, mock_gateway_client):
    """Test that the handler does NOT send 'Thinking...' or edit messages."""
    message = _make_discord_message()

    await handler.on_message(message)

    # The handler should NOT call channel.send() (no "Thinking..." placeholder)
    message.channel.send.assert_not_called()


@pytest.mark.asyncio
async def test_on_message_includes_source_metadata(handler, mock_gateway_client):
    """Test that metadata includes source='discord' for fallback detection."""
    message = _make_discord_message()

    await handler.on_message(message)

    import asyncio
    await asyncio.sleep(0.01)

    event = mock_gateway_client.send_event.call_args[0][0]
    assert event.metadata["source"] == "discord"
    assert event.metadata["guild_id"] == "99999"
    assert event.metadata["guild_name"] == "Test Guild"


@pytest.mark.asyncio
async def test_forward_event_handles_error(handler, mock_gateway_client):
    """Test that errors in forwarding are logged, not raised."""
    mock_gateway_client.send_event = AsyncMock(side_effect=Exception("Connection refused"))
    message = _make_discord_message()

    # Should not raise — error is caught in _forward_event
    await handler.on_message(message)

    import asyncio
    await asyncio.sleep(0.01)

    # send_event was called but failed — handler should have logged the error
    mock_gateway_client.send_event.assert_called_once()
