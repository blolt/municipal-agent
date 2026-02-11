"""Structured logging configuration for Municipal Agent services.

Implements the logging best practices from docs/design/logging_best_practices.md:
- structlog for structured JSON logging
- Context propagation via contextvars (correlation_id, service, version)
- Strict log levels (ERROR, WARNING, INFO, DEBUG)
- App logs to stdout, configurable JSON/console rendering
- Silences noisy library loggers (uvicorn.access, httpx, etc.)
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor


def _add_service_context(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Processor that ensures service and version are in every log entry."""
    # These are bound at setup time and merged via contextvars
    return event_dict


def _filter_health_checks(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Filter out noisy health check logs."""
    # Skip health check logs at DEBUG level
    path = event_dict.get("path", "")
    if "/health" in path and method_name == "debug":
        raise structlog.DropEvent
    return event_dict


def setup_logging(
    service_name: str,
    service_version: str = "0.1.0",
    log_level: str = "INFO",
    log_format: str = "console",
) -> None:
    """Configure structured logging for a service.

    Args:
        service_name: Name of the service (e.g., "orchestrator-service")
        service_version: Service version (e.g., "0.1.0")
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
        log_format: Output format - "json" for production, "console" for development
    """
    # Silence noisy library loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Shared processors for all output formats
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        _filter_health_checks,
    ]

    if log_format == "json":
        # JSON output for production / GCP Cloud Logging
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Colored console output for local development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Bind service context that will appear in all logs
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        service=service_name,
        version=service_version,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a logger instance with optional name binding.

    Args:
        name: Optional logger name (typically __name__)

    Returns:
        A bound structlog logger
    """
    logger = structlog.get_logger()
    if name:
        logger = logger.bind(logger_name=name)
    return logger


def bind_context(**kwargs: Any) -> None:
    """Bind additional context variables to all subsequent logs.

    Common use: binding correlation_id at the start of request processing.

    Example:
        bind_context(correlation_id="abc-123", user_id="user-456")
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bound context variables.

    Call this at the end of request processing to prevent context leaking
    between requests in async environments.
    """
    structlog.contextvars.clear_contextvars()


def unbind_context(*keys: str) -> None:
    """Remove specific context variables.

    Args:
        keys: Names of context variables to remove
    """
    structlog.contextvars.unbind_contextvars(*keys)
