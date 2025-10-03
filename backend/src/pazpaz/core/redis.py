"""Redis connection and utilities."""

from __future__ import annotations

import redis.asyncio as redis

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)

# Global Redis client instance
_redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    """
    Get Redis client instance (dependency injection).

    Returns:
        Redis client instance

    Raises:
        ConnectionError: If Redis connection fails
        RedisError: If Redis authentication fails

    Note:
        This creates a new connection pool on first call with authentication.
        Connection is secured with password from environment variables.
    """
    global _redis_client

    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30,
            )
            # Test connection and authentication
            await _redis_client.ping()
            # Log connection success (hide password in URL)
            safe_url = (
                settings.redis_url.split("@")[1]
                if "@" in settings.redis_url
                else settings.redis_url
            )
            logger.info("redis_connection_initialized", url=safe_url)
        except Exception as e:
            logger.error(
                "redis_connection_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    return _redis_client


async def close_redis():
    """Close Redis connection (cleanup on shutdown)."""
    global _redis_client

    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("redis_connection_closed")


async def check_redis_health() -> bool:
    """
    Check Redis connection health.

    Returns:
        bool: True if Redis is healthy and authenticated, False otherwise
    """
    try:
        client = await get_redis()
        await client.ping()
        return True
    except Exception as e:
        logger.error("redis_health_check_failed", error=str(e))
        return False
