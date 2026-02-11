"""Unit tests for configuration."""
import os
from context_service.config import Settings

def test_settings_defaults():
    """Test default settings."""
    # Temporarily unset env vars to test defaults
    # Note: Pydantic reads env vars, so we might need to mock os.environ
    # But Settings() is instantiated at module level in config.py.
    # Here we instantiate a new one.
    settings = Settings(_env_file=None) # Ignore .env file for defaults check if needed, but defaults are in class
    assert settings.database_pool_min_size == 2
    assert settings.log_level == "INFO"

def test_settings_from_env():
    """Test settings from environment variables."""
    os.environ["DATABASE_POOL_MIN_SIZE"] = "5"
    os.environ["LOG_LEVEL"] = "DEBUG"
    
    settings = Settings(_env_file=None)
    assert settings.database_pool_min_size == 5
    assert settings.log_level == "DEBUG"
    
    # Cleanup
    del os.environ["DATABASE_POOL_MIN_SIZE"]
    del os.environ["LOG_LEVEL"]
