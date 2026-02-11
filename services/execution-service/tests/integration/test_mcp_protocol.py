"""Integration tests for the MCP protocol — real subprocess, real handshake.

These tests spawn an actual FastMCP server as a subprocess and verify the
full MCP lifecycle through MCPClient:
  1. Subprocess start
  2. initialize handshake (client → server → client)
  3. tools/list
  4. Graceful disconnect

No Docker required. No external API calls (tools/list returns schemas only).
"""

import sys
from pathlib import Path

import pytest

from src.core.config import ServerConfig
from src.mcp.client import MCPClient
from src.mcp.runtime import SubprocessRuntime

# Resolve path to the MCP servers directory
MCP_SERVERS_DIR = Path(__file__).resolve().parents[2] / "mcp_servers"


@pytest.fixture
def runtime():
    """Provide a real SubprocessRuntime (not mocked)."""
    rt = SubprocessRuntime()
    yield rt
    # Cleanup: stop any servers that weren't explicitly stopped
    import asyncio
    asyncio.get_event_loop().run_until_complete(rt.stop_all_servers())


def _server_config(name: str, script: str, timeout: int = 10) -> ServerConfig:
    """Build a ServerConfig that runs a Python MCP server script."""
    return ServerConfig(
        name=name,
        command=sys.executable,
        args=[str(MCP_SERVERS_DIR / script)],
        timeout=timeout,
    )


class TestMunicodeServerProtocol:
    """Test standard MCP protocol against the real municode FastMCP server."""

    async def test_handshake_and_list_tools(self, runtime):
        """Full lifecycle: connect (handshake) → list_tools → disconnect."""
        config = _server_config("municode", "municode_server.py")
        client = MCPClient(config, runtime)

        await client.connect()
        assert client._connected is True

        tools = await client.list_tools()

        # Municode server exposes exactly 7 tools
        assert len(tools) == 7
        tool_names = {t["name"] for t in tools}
        assert tool_names == {
            "municode_get_state_info",
            "municode_list_municipalities",
            "municode_get_municipality_info",
            "municode_get_code_structure",
            "municode_get_code_section",
            "municode_search_codes",
            "municode_get_url",
        }

        # Each tool should have a description and input schema
        for tool in tools:
            assert "description" in tool
            assert len(tool["description"]) > 0
            assert "inputSchema" in tool

        await client.disconnect()
        assert client._connected is False

    async def test_handshake_sets_protocol_version(self, runtime):
        """Server responds with a valid protocol version during handshake."""
        config = _server_config("municode-proto", "municode_server.py")
        client = MCPClient(config, runtime)

        # Patch connect to capture the init result before it's discarded
        original_send = client._send_request

        captured_init = {}

        async def capturing_send(method, params=None):
            result = await original_send(method, params)
            if method == "initialize":
                captured_init.update(result)
            return result

        client._send_request = capturing_send

        await client.connect()

        assert "protocolVersion" in captured_init
        assert "serverInfo" in captured_init
        assert captured_init["serverInfo"]["name"] == "municode"

        await client.disconnect()


class TestDiscordServerProtocol:
    """Test standard MCP protocol against the real discord FastMCP server."""

    async def test_handshake_and_list_tools(self, runtime):
        """Full lifecycle: connect (handshake) → list_tools → disconnect."""
        config = _server_config("discord", "discord_server.py")
        client = MCPClient(config, runtime)

        await client.connect()
        assert client._connected is True

        tools = await client.list_tools()

        # Discord server exposes exactly 3 tools
        assert len(tools) == 3
        tool_names = {t["name"] for t in tools}
        assert tool_names == {
            "discord_send_message",
            "discord_edit_message",
            "discord_add_reaction",
        }

        for tool in tools:
            assert "description" in tool
            assert "inputSchema" in tool

        await client.disconnect()
        assert client._connected is False


class TestMultipleServers:
    """Test that MCPClient can manage multiple concurrent server connections."""

    async def test_connect_two_servers_sequentially(self, runtime):
        """Two independent MCPClient instances can connect to different servers."""
        municode_config = _server_config("municode-multi", "municode_server.py")
        discord_config = _server_config("discord-multi", "discord_server.py")

        municode_client = MCPClient(municode_config, runtime)
        discord_client = MCPClient(discord_config, runtime)

        await municode_client.connect()
        await discord_client.connect()

        municode_tools = await municode_client.list_tools()
        discord_tools = await discord_client.list_tools()

        assert len(municode_tools) == 7
        assert len(discord_tools) == 3

        await municode_client.disconnect()
        await discord_client.disconnect()
