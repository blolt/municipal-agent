"""Logging configuration for Context Service.

Re-exports shared logging utilities from agentic-common.
"""

from agentic_common import bind_context, clear_context, get_logger, setup_logging

__all__ = ["setup_logging", "get_logger", "bind_context", "clear_context"]
