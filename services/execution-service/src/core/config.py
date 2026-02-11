"""Configuration management for Execution Service."""

import json
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerConfig(BaseSettings):
    """Configuration for a single MCP server."""

    name: str
    command: str
    args: list[str]
    env: dict[str, str] = Field(default_factory=dict)
    timeout: int = 30
    description: str = ""


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Service auth
    service_auth_secret: str = Field(default="", alias="SERVICE_AUTH_SECRET")

    # Server configuration
    port: int = Field(default=8002, alias="PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="console", alias="LOG_FORMAT")

    # Service info
    service_name: str = Field(default="execution-service", alias="SERVICE_NAME")
    service_version: str = Field(default="0.1.0", alias="SERVICE_VERSION")

    # MCP configuration
    mcp_config_path: str = Field(default="config/mcp_servers.json", alias="MCP_CONFIG_PATH")
    default_timeout: int = Field(default=30, alias="DEFAULT_TIMEOUT")

    # Sandbox configuration
    sandbox_directory: str = Field(default="/tmp/execution-sandbox", alias="SANDBOX_DIRECTORY")

    # CORS
    allowed_origins: str = Field(default="", alias="ALLOWED_ORIGINS")  # Comma-separated

    # Resource limits
    max_concurrent_executions: int = Field(default=10, alias="MAX_CONCURRENT_EXECUTIONS")

    def load_mcp_servers(self) -> list[ServerConfig]:
        """Load MCP server configurations from JSON file."""
        config_path = Path(self.mcp_config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"MCP config file not found: {self.mcp_config_path}")

        with open(config_path) as f:
            data = json.load(f)

        return [ServerConfig(**server) for server in data.get("servers", [])]


# Global settings instance
settings = Settings()
