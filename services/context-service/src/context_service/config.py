"""Application settings using Pydantic BaseSettings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database configuration
    database_url: str = "postgresql://postgres:postgres@localhost:5432/agentic_bridge"
    database_pool_min_size: int = 2
    database_pool_max_size: int = 10

    # Service auth
    service_auth_secret: str = ""

    # Application configuration
    log_level: str = "INFO"
    log_format: str = "console"
    debug: bool = False

    # CORS
    allowed_origins: str = ""  # Comma-separated origins, empty = no browser access

    # Service info
    service_name: str = "context-service"
    service_version: str = "0.1.0"


# Global settings instance
settings = Settings()
