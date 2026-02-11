"""Path validation and sandboxing utilities."""

import os
from pathlib import Path
from typing import Union

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class PathValidationError(Exception):
    """Raised when a path violates sandbox constraints."""

    pass


def get_sandbox_directory() -> Path:
    """Get the configured sandbox directory as an absolute path.

    Returns:
        Absolute path to sandbox directory

    Raises:
        RuntimeError: If sandbox directory doesn't exist
    """
    sandbox_path = Path(settings.sandbox_directory).resolve()

    # Create sandbox directory if it doesn't exist
    if not sandbox_path.exists():
        logger.info(f"Creating sandbox directory: {sandbox_path}")
        sandbox_path.mkdir(parents=True, exist_ok=True)

    return sandbox_path


def validate_path(path: Union[str, Path]) -> Path:
    """Validate that a path is within the sandbox directory.

    Args:
        path: Path to validate (can be relative or absolute)

    Returns:
        Absolute path within sandbox

    Raises:
        PathValidationError: If path is outside sandbox or invalid
    """
    sandbox_dir = get_sandbox_directory()

    # Convert to Path object
    if isinstance(path, str):
        path = Path(path)

    # Resolve to absolute path
    try:
        # If path is relative, resolve it relative to sandbox
        if not path.is_absolute():
            absolute_path = (sandbox_dir / path).resolve()
        else:
            absolute_path = path.resolve()
    except (ValueError, OSError) as e:
        raise PathValidationError(f"Invalid path: {path}") from e

    # Check if path is within sandbox
    try:
        absolute_path.relative_to(sandbox_dir)
    except ValueError:
        raise PathValidationError(
            f"Path '{path}' is outside sandbox directory '{sandbox_dir}'. "
            f"Resolved to: {absolute_path}"
        )

    logger.debug(f"Path validated: {path} -> {absolute_path}")
    return absolute_path


def validate_paths(paths: list[Union[str, Path]]) -> list[Path]:
    """Validate multiple paths.

    Args:
        paths: List of paths to validate

    Returns:
        List of validated absolute paths

    Raises:
        PathValidationError: If any path is invalid
    """
    return [validate_path(p) for p in paths]


def extract_path_from_arguments(arguments: dict) -> list[str]:
    """Extract file paths from tool arguments.

    Common path argument names: path, file, directory, source, destination, etc.

    Args:
        arguments: Tool arguments dictionary

    Returns:
        List of path values found in arguments
    """
    path_keys = [
        "path",
        "file",
        "filepath",
        "file_path",
        "directory",
        "dir",
        "source",
        "destination",
        "dest",
        "target",
        "paths",  # For tools that accept multiple paths
    ]

    paths = []
    for key in path_keys:
        if key in arguments:
            value = arguments[key]
            # Handle both single paths and lists of paths
            if isinstance(value, list):
                paths.extend(value)
            elif value:
                paths.append(value)

    return paths
