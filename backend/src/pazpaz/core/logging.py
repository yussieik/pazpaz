"""Structured logging configuration using structlog."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def configure_logging(debug: bool = False) -> None:
    """
    Configure structlog for the application.

    Sets up structured logging with appropriate processors for development
    and production environments. In production, logs are output as JSON for
    easy parsing by log aggregation tools. In development, logs are formatted
    for human readability.

    Args:
        debug: Whether to enable debug mode (human-readable console output)
    """
    # Shared processors for both environments
    shared_processors: list[structlog.typing.Processor] = [
        # Add log level to event dict
        structlog.stdlib.add_log_level,
        # Add logger name to event dict
        structlog.stdlib.add_logger_name,
        # Add timestamp in ISO format
        structlog.processors.TimeStamper(fmt="iso"),
        # Add stack info for exceptions
        structlog.processors.StackInfoRenderer(),
        # Format exception info
        structlog.processors.format_exc_info,
        # Unicode handling
        structlog.processors.UnicodeDecoder(),
    ]

    if debug:
        # Development: human-readable console output with colors
        processors = shared_processors + [
            # Pretty console output with colors
            structlog.dev.ConsoleRenderer(colors=True),
        ]
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=logging.DEBUG,
        )
    else:
        # Production: JSON output for log aggregation
        processors = shared_processors + [
            # JSON renderer for production logs
            structlog.processors.JSONRenderer(),
        ]
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=logging.INFO,
        )

    # Configure structlog
    structlog.configure(
        processors=processors,
        # Use LoggerFactory for stdlib logging integration
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        # Cache logger instances for performance
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structlog logger instance.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Configured structlog logger

    Example:
        ```python
        logger = get_logger(__name__)
        logger.info("user_created", user_id=user.id, workspace_id=workspace.id)
        ```
    """
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """
    Bind context to the current logger.

    Context is attached to all subsequent log messages in the current
    execution context (e.g., request).

    Args:
        **kwargs: Key-value pairs to bind to logger context

    Example:
        ```python
        bind_context(workspace_id=workspace_id, user_id=user_id)
        logger.info("processing_request")  # Will include bound context
        ```
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """
    Clear all bound context from the current logger.

    Should be called at the end of request processing to avoid
    context leaking between requests.
    """
    structlog.contextvars.clear_contextvars()


__all__ = ["configure_logging", "get_logger", "bind_context", "clear_context"]
