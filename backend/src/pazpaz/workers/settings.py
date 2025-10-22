"""Worker configuration for arq task queue.

This module defines configuration settings for the arq background worker,
including job execution limits, timeouts, health check settings, and Redis
connection parameters.

The configuration is designed to handle scheduled notification tasks with
appropriate timeouts and concurrency limits to ensure reliable delivery
without overwhelming the system.
"""

from __future__ import annotations

from pazpaz.core.config import settings

# Worker Configuration
MAX_JOBS = 10
"""Maximum number of concurrent jobs the worker can execute."""

JOB_TIMEOUT = 300
"""Maximum time (seconds) a single job can run before being terminated."""

HEALTH_CHECK_INTERVAL = 60
"""Interval (seconds) between worker health checks."""

QUEUE_NAME = "pazpaz:notifications"
"""Redis queue name for notification tasks."""

# Job Retry Configuration
MAX_TRIES = 3
"""Maximum number of retry attempts for failed jobs."""

RETRY_DELAY = 60
"""Base delay (seconds) between retry attempts (uses exponential backoff)."""


def get_redis_settings() -> dict:
    """
    Get Redis connection settings from application config.

    This function extracts Redis connection parameters from the main
    application settings and formats them for arq worker usage.

    Returns:
        dict: Redis connection parameters including:
            - host: Redis server hostname
            - port: Redis server port
            - password: Redis authentication password
            - database: Redis database number (default: 0)

    Example:
        >>> redis_settings = get_redis_settings()
        >>> redis_settings["host"]
        'localhost'
    """
    # Parse Redis URL from settings (format: redis://:password@host:port/db)
    # Example: redis://:change-me@localhost:6379/0
    redis_url = settings.redis_url

    # Extract components from Redis URL
    # Format: redis://[:password@]host:port[/database]
    url_parts = redis_url.replace("redis://", "").split("@")

    if len(url_parts) == 2:
        # URL has password: redis://:password@host:port/db
        password = url_parts[0].lstrip(":")
        host_port_db = url_parts[1]
    else:
        # URL has no password: redis://host:port/db
        password = None
        host_port_db = url_parts[0]

    # Split host:port/db
    if "/" in host_port_db:
        host_port, db = host_port_db.split("/", 1)
    else:
        host_port = host_port_db
        db = "0"

    # Split host:port
    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
    else:
        host = host_port
        port = "6379"

    redis_settings = {
        "host": host,
        "port": int(port),
        "database": int(db),
    }

    if password:
        redis_settings["password"] = password

    return redis_settings
