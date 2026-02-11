"""Unit tests for validation utilities."""

import pytest
from jsonschema import ValidationError

from src.utils.validation import validate_tool_arguments


def test_validate_tool_arguments_with_valid_data():
    """Test that valid arguments pass validation."""
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"}
        },
        "required": ["path"]
    }
    arguments = {"path": "/tmp/test.txt"}
    
    # Should not raise
    validate_tool_arguments(schema, arguments)


def test_validate_tool_arguments_with_missing_required_field():
    """Test that missing required field raises ValidationError."""
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"}
        },
        "required": ["path"]
    }
    arguments = {}  # Missing 'path'
    
    with pytest.raises(ValidationError):
        validate_tool_arguments(schema, arguments)


def test_validate_tool_arguments_with_wrong_type():
    """Test that wrong type raises ValidationError."""
    schema = {
        "type": "object",
        "properties": {
            "count": {"type": "number"}
        }
    }
    arguments = {"count": "not a number"}
    
    with pytest.raises(ValidationError):
        validate_tool_arguments(schema, arguments)
