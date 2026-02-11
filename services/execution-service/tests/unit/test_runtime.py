"""Unit tests for subprocess runtime."""

import pytest

from src.core.config import ServerConfig
from src.mcp.runtime import SubprocessRuntime


@pytest.mark.asyncio
async def test_runtime_initialization():
    """Test that runtime initializes correctly."""
    runtime = SubprocessRuntime()
    assert runtime.processes == {}


@pytest.mark.asyncio
async def test_is_running_returns_false_for_nonexistent_server():
    """Test that is_running returns False for non-existent server."""
    runtime = SubprocessRuntime()
    assert not runtime.is_running("nonexistent")


@pytest.mark.asyncio
async def test_stop_server_handles_nonexistent_server_gracefully():
    """Test that stopping a non-existent server doesn't raise an error."""
    runtime = SubprocessRuntime()
    await runtime.stop_server("nonexistent")  # Should not raise
