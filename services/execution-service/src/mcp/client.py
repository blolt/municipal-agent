"""MCP client implementation."""

import asyncio
import json
from typing import Any

from src.core.config import ServerConfig
from src.core.logging import get_logger
from src.mcp.runtime import SubprocessRuntime

logger = get_logger(__name__)


class MCPClient:
    """Client for communicating with MCP servers via stdio."""

    def __init__(self, config: ServerConfig, runtime: SubprocessRuntime):
        self.config = config
        self.runtime = runtime
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self._request_id = 0
        self._connected = False

    async def connect(self) -> None:
        """Establish connection to MCP server.

        Performs the standard MCP handshake:
        1. Start subprocess
        2. Send `initialize` request with client info and protocol version
        3. Read server's `initialize` response (capabilities)
        4. Send `notifications/initialized` notification
        """
        if self._connected:
            logger.debug(f"Already connected to {self.config.name}")
            return

        logger.info(f"Connecting to MCP server: {self.config.name}")
        self.reader, self.writer = await self.runtime.start_server(self.config)

        # MCP handshake: initialize
        init_result = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "municipal-agent-execution", "version": "0.1.0"},
        })
        logger.info(
            f"MCP server {self.config.name} initialized: "
            f"protocol={init_result.get('protocolVersion')}, "
            f"server={init_result.get('serverInfo', {}).get('name', 'unknown')}"
        )

        # MCP handshake: notifications/initialized
        await self._send_notification("notifications/initialized")

        self._connected = True
        logger.info(f"Connected to MCP server: {self.config.name}")

    async def disconnect(self) -> None:
        """Disconnect from MCP server."""
        if not self._connected:
            return

        logger.info(f"Disconnecting from MCP server: {self.config.name}")
        await self.runtime.stop_server(self.config.name)
        self._connected = False

    async def _send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send a JSON-RPC notification (no id, no response expected).

        Args:
            method: JSON-RPC method name
            params: Method parameters
        """
        notification: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params:
            notification["params"] = params

        logger.debug(f"Sending notification to {self.config.name}: {method}")
        notification_json = json.dumps(notification) + "\n"
        self.writer.write(notification_json.encode())
        await self.writer.drain()

    async def _send_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a JSON-RPC request to the MCP server.

        Args:
            method: JSON-RPC method name
            params: Method parameters

        Returns:
            JSON-RPC response

        Raises:
            RuntimeError: If not connected or request fails
        """
        if not self.writer or not self.reader:
            raise RuntimeError(f"Not connected to {self.config.name}")

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }

        logger.debug(f"Sending request to {self.config.name}: {method}")

        # Send request
        request_json = json.dumps(request) + "\n"
        self.writer.write(request_json.encode())
        await self.writer.drain()

        # Read response
        try:
            response_line = await asyncio.wait_for(
                self.reader.readline(), timeout=self.config.timeout
            )
            response = json.loads(response_line.decode())

            if "error" in response:
                error = response["error"]
                raise RuntimeError(f"MCP error: {error.get('message', 'Unknown error')}")

            return response.get("result", {})

        except asyncio.TimeoutError:
            raise RuntimeError(f"Request to {self.config.name} timed out after {self.config.timeout}s")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response from {self.config.name}: {e}")

    async def list_tools(self) -> list[dict[str, Any]]:
        """List available tools from the MCP server.

        Returns:
            List of tool definitions
        """
        logger.info(f"Listing tools from {self.config.name}")
        result = await self._send_request("tools/list")
        tools = result.get("tools", [])
        logger.info(f"Found {len(tools)} tools from {self.config.name}")
        return tools

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool on the MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        logger.info(f"Calling tool {tool_name} on {self.config.name}")
        logger.debug(f"Arguments: {arguments}")

        params = {"name": tool_name, "arguments": arguments}
        result = await self._send_request("tools/call", params)

        logger.info(f"Tool {tool_name} executed successfully")
        return result
