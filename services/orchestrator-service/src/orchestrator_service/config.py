"""Application settings using Pydantic BaseSettings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database configuration (same as Context Service)
    database_url: str = "postgresql://postgres:postgres@localhost:5433/municipal_agent"

    # Context Service integration
    context_service_url: str = "http://localhost:8001"

    # Execution Service integration
    execution_service_url: str = "http://localhost:8002"



    # Service auth
    service_auth_secret: str = ""

    # CORS
    allowed_origins: str = ""  # Comma-separated origins, empty = no browser access

    # LLM API keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Ollama configuration
    ollama_base_url: str = "http://localhost:11434"

    # Application configuration
    port: int = 8000
    log_level: str = "INFO"
    log_format: str = "console"
    debug: bool = False

    # Service info
    service_name: str = "orchestrator-service"
    service_version: str = "0.1.0"


# Global settings instance
settings = Settings()

