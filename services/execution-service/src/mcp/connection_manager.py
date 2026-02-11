"""Connection manager for MCP servers."""

from typing import Any

from src.api.models import ToolSchema
from src.core.config import ServerConfig, settings
from src.core.logging import get_logger
from src.mcp.client import MCPClient
from src.mcp.runtime import SubprocessRuntime

logger = get_logger(__name__)


class ConnectionManager:
    """Manages connections to multiple MCP servers."""

    def __init__(self):
        self.runtime = SubprocessRuntime()
        self.clients: dict[str, MCPClient] = {}
        self.tool_registry: dict[str, str] = {}  # tool_name -> server_name

    async def initialize(self) -> None:
        """Initialize connections to all configured MCP servers."""
        logger.info("Initializing MCP connections...")
        server_configs = settings.load_mcp_servers()

        for config in server_configs:
            try:
                client = MCPClient(config, self.runtime)
                await client.connect()
                self.clients[config.name] = client
                logger.info(f"Initialized connection to {config.name}")
            except Exception as e:
                logger.error(f"Failed to initialize {config.name}: {e}")

        # Build tool registry
        await self._build_tool_registry()
        logger.info(f"Connection manager initialized with {len(self.clients)} servers")

    async def _build_tool_registry(self) -> None:
        """Build registry mapping tool names to server names."""
        logger.info("Building tool registry...")
        self.tool_registry.clear()

        for server_name, client in self.clients.items():
            try:
                tools = await client.list_tools()
                for tool in tools:
                    tool_name = tool.get("name")
                    if tool_name:
                        if tool_name in self.tool_registry:
                            logger.warning(
                                f"Tool {tool_name} already registered by "
                                f"{self.tool_registry[tool_name]}, overwriting with {server_name}"
                            )
                        self.tool_registry[tool_name] = server_name
                        logger.debug(f"Registered tool {tool_name} from {server_name}")
            except Exception as e:
                logger.error(f"Failed to list tools from {server_name}: {e}")

        logger.info(f"Tool registry built with {len(self.tool_registry)} tools")

    async def get_all_tools(self) -> list[ToolSchema]:
        """Get all available tools from all MCP servers.

        Returns:
            List of tool schemas
        """
        all_tools = []

        for server_name, client in self.clients.items():
            try:
                tools = await client.list_tools()
                for tool in tools:
                    all_tools.append(
                        ToolSchema(
                            name=tool.get("name", ""),
                            description=tool.get("description", ""),
                            input_schema=tool.get("inputSchema", {}),
                        )
                    )
            except Exception as e:
                logger.error(f"Failed to get tools from {server_name}: {e}")

        return all_tools

    async def execute_tool(
        self, tool_name: str, arguments: dict[str, Any], timeout: int | None = None
    ) -> dict[str, Any]:
        """Execute a tool by routing to the appropriate MCP server.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            timeout: Optional timeout override

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found or path validation fails
            RuntimeError: If execution fails
        """
        # Import here to avoid circular dependency
        from src.utils.path_validation import (
            PathValidationError,
            extract_path_from_arguments,
            validate_paths,
        )

        # Validate paths in arguments for filesystem tools
        filesystem_tools = [
            "read_file",
            "read_text_file",
            "read_media_file",
            "write_file",
            "edit_file",
            "create_directory",
            "list_directory",
            "move_file",
            "search_files",
            "get_file_info",
            "delete_file",
            "delete_directory",
            "read_multiple_files",
        ]

        if tool_name in filesystem_tools:
            logger.info(f"Validating paths for filesystem tool: {tool_name}")
            paths = extract_path_from_arguments(arguments)

            if paths:
                try:
                    validated_paths = validate_paths(paths)
                    logger.info(f"Validated {len(validated_paths)} paths for {tool_name}")

                    # Update arguments with validated absolute paths
                    # This ensures the MCP server receives safe, absolute paths
                    for key in ["path", "file", "filepath", "file_path", "directory", "dir"]:
                        if key in arguments and arguments[key] in paths:
                            idx = paths.index(arguments[key])
                            arguments[key] = str(validated_paths[idx])

                except PathValidationError as e:
                    logger.error(f"Path validation failed for {tool_name}: {e}")
                    raise ValueError(f"Path validation failed: {e}") from e

        # Find server for this tool
        server_name = self.tool_registry.get(tool_name)
        if not server_name:
            raise ValueError(f"Tool {tool_name} not found in registry")

        client = self.clients.get(server_name)
        if not client:
            raise RuntimeError(f"Server {server_name} not available")

        # Execute tool
        logger.info(f"Executing tool {tool_name} on server {server_name}")
        result = await client.call_tool(tool_name, arguments)
        return result

    async def shutdown(self) -> None:
        """Shutdown all MCP connections."""
        logger.info("Shutting down connection manager...")
        for server_name, client in self.clients.items():
            try:
                await client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting from {server_name}: {e}")

        self.clients.clear()
        self.tool_registry.clear()
        logger.info("Connection manager shutdown complete")

    def get_server_status(self) -> dict[str, str]:
        """Get status of all servers.

        Returns:
            Dict mapping server name to status
        """
        status = {}
        for server_name in self.clients.keys():
            is_running = self.runtime.is_running(server_name)
            status[server_name] = "running" if is_running else "stopped"
        return status
