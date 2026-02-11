"""Subprocess runtime for MCP servers."""

import asyncio
import os
import signal
from typing import Any

from src.core.config import ServerConfig
from src.core.logging import get_logger

logger = get_logger(__name__)


class SubprocessRuntime:
    """Manages MCP server subprocesses."""

    def __init__(self):
        self.processes: dict[str, asyncio.subprocess.Process] = {}

    async def start_server(self, config: ServerConfig) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Start an MCP server subprocess and return stdio streams.

        Args:
            config: Server configuration

        Returns:
            Tuple of (stdout reader, stdin writer)

        Raises:
            RuntimeError: If server fails to start
        """
        logger.info(f"Starting MCP server: {config.name}")
        logger.debug(f"Command: {config.command} {' '.join(config.args)}")

        try:
            # Prepare environment
            env = os.environ.copy()
            env.update(config.env)

            # Start subprocess
            process = await asyncio.create_subprocess_exec(
                config.command,
                *config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            self.processes[config.name] = process
            logger.info(f"MCP server {config.name} started with PID {process.pid}")

            # Return streams for communication
            return process.stdout, process.stdin

        except Exception as e:
            logger.error(f"Failed to start MCP server {config.name}: {e}")
            raise RuntimeError(f"Failed to start MCP server {config.name}") from e

    async def stop_server(self, server_name: str) -> None:
        """Stop an MCP server subprocess.

        Args:
            server_name: Name of the server to stop
        """
        if server_name not in self.processes:
            logger.warning(f"Server {server_name} not found in active processes")
            return

        process = self.processes[server_name]
        logger.info(f"Stopping MCP server: {server_name} (PID {process.pid})")

        try:
            # Try graceful shutdown first
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
                logger.info(f"Server {server_name} terminated gracefully")
            except asyncio.TimeoutError:
                # Force kill if graceful shutdown fails
                logger.warning(f"Server {server_name} did not terminate, killing...")
                process.kill()
                await process.wait()
                logger.info(f"Server {server_name} killed")

        except Exception as e:
            logger.error(f"Error stopping server {server_name}: {e}")

        finally:
            del self.processes[server_name]

    async def stop_all_servers(self) -> None:
        """Stop all running MCP servers."""
        logger.info("Stopping all MCP servers...")
        server_names = list(self.processes.keys())
        for server_name in server_names:
            await self.stop_server(server_name)
        logger.info("All MCP servers stopped")

    def is_running(self, server_name: str) -> bool:
        """Check if a server is currently running.

        Args:
            server_name: Name of the server

        Returns:
            True if server is running, False otherwise
        """
        if server_name not in self.processes:
            return False

        process = self.processes[server_name]
        return process.returncode is None
