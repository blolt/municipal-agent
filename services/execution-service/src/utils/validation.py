"""Input validation utilities."""

from typing import Any

from jsonschema import ValidationError, validate

from src.core.logging import get_logger

logger = get_logger(__name__)


def validate_tool_arguments(tool_schema: dict[str, Any], arguments: dict[str, Any]) -> None:
    """Validate tool arguments against JSON schema.

    Args:
        tool_schema: JSON schema for the tool
        arguments: Arguments to validate

    Raises:
        ValidationError: If validation fails
    """
    try:
        validate(instance=arguments, schema=tool_schema)
        logger.debug("Tool arguments validated successfully")
    except ValidationError as e:
        logger.error(f"Tool argument validation failed: {e.message}")
        raise
