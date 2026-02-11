"""Pytest configuration and fixtures."""

import pytest

from src.core.config import ServerConfig
from src.mcp.runtime import SubprocessRuntime


@pytest.fixture
def subprocess_runtime():
    """Provide a subprocess runtime instance."""
    return SubprocessRuntime()


@pytest.fixture
def sample_server_config():
    """Provide a sample server configuration."""
    return ServerConfig(
        name="test_server",
        command="echo",
        args=["test"],
        env={},
        timeout=5,
        description="Test server",
    )
