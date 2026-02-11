"""Configuration for Discord Service using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Discord
    discord_bot_token: str = Field(..., description="Discord bot token")
    discord_application_id: str = Field(default="", description="Discord application ID")

    # Orchestrator Service
    gateway_service_url: str = Field(
        default="http://orchestrator-service:8000", description="Orchestrator Service URL"
    )
    service_auth_secret: str = Field(..., description="Shared secret for JWT service auth")

    # Queue (Deprecated - will be removed)
    # queue_backend: Literal["redis", "pubsub", "memory"] = Field(
    #     default="redis", description="Queue backend to use"
    # )
    # redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")
    queue_topic: str = Field(default="ingress.events", description="Queue topic/stream name")
    # queue_consumer_group: str = Field(
    #     default="orchestrator-primary", description="Consumer group name"
    # )

    # Health check server
    health_port: int = Field(default=8003, description="Port for health check endpoint")

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )
    log_format: Literal["json", "console"] = Field(
        default="console", description="Log output format"
    )

    # Service info
    service_name: str = Field(default="discord-service", description="Service name for logging")
    service_version: str = Field(default="0.1.0", description="Service version")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
