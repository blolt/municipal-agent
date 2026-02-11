"""Tests for the MCP client — specifically the initialize handshake."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.config import ServerConfig
from src.mcp.client import MCPClient
from src.mcp.runtime import SubprocessRuntime


@pytest.fixture
def server_config():
    return ServerConfig(
        name="test-server",
        command="echo",
        args=[],
        timeout=5,
    )


@pytest.fixture
def mock_runtime():
    return AsyncMock(spec=SubprocessRuntime)


def _make_streams(responses: list[dict]) -> tuple[asyncio.StreamReader, MagicMock]:
    """Build a (reader, writer) pair where reader yields JSON lines from `responses`."""
    reader = asyncio.StreamReader()
    for resp in responses:
        reader.feed_data((json.dumps(resp) + "\n").encode())

    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    return reader, writer


class TestMCPClientHandshake:
    """Tests for the MCP initialize handshake in connect()."""

    async def test_connect_sends_initialize_then_notification(
        self, server_config, mock_runtime
    ):
        """connect() sends initialize request, reads response, sends initialized notification."""
        init_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "test-server", "version": "1.0.0"},
            },
        }
        reader, writer = _make_streams([init_response])
        mock_runtime.start_server.return_value = (reader, writer)

        client = MCPClient(server_config, mock_runtime)
        await client.connect()

        # Verify writer.write was called exactly twice:
        # 1) initialize request  2) notifications/initialized notification
        assert writer.write.call_count == 2

        # Parse the first write — should be initialize request with id
        first_msg = json.loads(writer.write.call_args_list[0][0][0].decode())
        assert first_msg["method"] == "initialize"
        assert "id" in first_msg
        assert first_msg["params"]["protocolVersion"] == "2024-11-05"
        assert "clientInfo" in first_msg["params"]

        # Parse the second write — should be notification (no id)
        second_msg = json.loads(writer.write.call_args_list[1][0][0].decode())
        assert second_msg["method"] == "notifications/initialized"
        assert "id" not in second_msg

        # Client should be connected
        assert client._connected is True

    async def test_connect_is_idempotent(self, server_config, mock_runtime):
        """Calling connect() twice does not repeat the handshake."""
        init_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "serverInfo": {"name": "test-server", "version": "1.0.0"},
            },
        }
        reader, writer = _make_streams([init_response])
        mock_runtime.start_server.return_value = (reader, writer)

        client = MCPClient(server_config, mock_runtime)
        await client.connect()
        await client.connect()  # second call should be a no-op

        # start_server called only once
        assert mock_runtime.start_server.call_count == 1

    async def test_connect_raises_on_server_error(self, server_config, mock_runtime):
        """connect() raises if the server returns an error to initialize."""
        error_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32600, "message": "Invalid request"},
        }
        reader, writer = _make_streams([error_response])
        mock_runtime.start_server.return_value = (reader, writer)

        client = MCPClient(server_config, mock_runtime)
        with pytest.raises(RuntimeError, match="MCP error"):
            await client.connect()

        # Should NOT be marked as connected
        assert client._connected is False


class TestMCPClientPostHandshake:
    """Tests for list_tools/call_tool after successful handshake."""

    async def test_list_tools_after_connect(self, server_config, mock_runtime):
        """list_tools works after a successful handshake."""
        init_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "test-server", "version": "1.0.0"},
            },
        }
        tools_response = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "tools": [
                    {"name": "my_tool", "description": "A tool", "inputSchema": {}},
                ],
            },
        }
        reader, writer = _make_streams([init_response, tools_response])
        mock_runtime.start_server.return_value = (reader, writer)

        client = MCPClient(server_config, mock_runtime)
        await client.connect()
        tools = await client.list_tools()

        assert len(tools) == 1
        assert tools[0]["name"] == "my_tool"

    async def test_list_tools_without_connect_raises(self, server_config, mock_runtime):
        """list_tools raises if connect() was never called."""
        client = MCPClient(server_config, mock_runtime)

        with pytest.raises(RuntimeError, match="Not connected"):
            await client.list_tools()
