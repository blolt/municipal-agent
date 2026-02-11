"""Tests for the Discord MCP server (FastMCP)."""

import json
from unittest.mock import patch, AsyncMock

import pytest

from mcp_servers.discord_server import (
    discord_send_message,
    discord_edit_message,
    discord_add_reaction,
)


class TestSendMessage:
    """Tests for discord_send_message tool."""

    @patch("mcp_servers.discord_server._discord_request", new_callable=AsyncMock)
    async def test_send_message_success(self, mock_request):
        """Send message returns message_id on success."""
        mock_request.return_value = {"id": "msg-999", "content": "Hello"}

        result = await discord_send_message(channel_id="ch-123", content="Hello")

        mock_request.assert_called_once_with(
            "POST",
            "/channels/ch-123/messages",
            {"content": "Hello"},
        )
        parsed = json.loads(result)
        assert parsed["message_id"] == "msg-999"
        assert parsed["channel_id"] == "ch-123"

    @patch("mcp_servers.discord_server._discord_request", new_callable=AsyncMock)
    async def test_send_message_api_error(self, mock_request):
        """Send message raises on API failure."""
        mock_request.side_effect = RuntimeError("Discord API error 403: Forbidden")

        with pytest.raises(RuntimeError, match="403"):
            await discord_send_message(channel_id="ch-123", content="Hello")


class TestEditMessage:
    """Tests for discord_edit_message tool."""

    @patch("mcp_servers.discord_server._discord_request", new_callable=AsyncMock)
    async def test_edit_message_success(self, mock_request):
        """Edit message returns success text."""
        mock_request.return_value = {"id": "msg-999", "content": "Updated"}

        result = await discord_edit_message(
            channel_id="ch-123", message_id="msg-999", content="Updated"
        )

        mock_request.assert_called_once_with(
            "PATCH",
            "/channels/ch-123/messages/msg-999",
            {"content": "Updated"},
        )
        assert "edited successfully" in result


class TestAddReaction:
    """Tests for discord_add_reaction tool."""

    @patch("mcp_servers.discord_server._discord_request", new_callable=AsyncMock)
    async def test_add_reaction_success(self, mock_request):
        """Add reaction returns success text."""
        mock_request.return_value = {}

        result = await discord_add_reaction(
            channel_id="ch-123", message_id="msg-999", emoji="\u2764\ufe0f"
        )

        # Verify the emoji was URL-encoded in the path
        call_args = mock_request.call_args
        assert "/reactions/" in call_args[0][1]
        assert "added successfully" in result
