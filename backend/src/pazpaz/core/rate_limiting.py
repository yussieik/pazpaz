"""Redis-based distributed rate limiting using sliding window algorithm."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import redis.asyncio as redis
from fastapi import HTTPException

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


async def check_rate_limit_redis(
    redis_client: redis.Redis,
    key: str,
    max_requests: int,
    window_seconds: int,
) -> bool:
    """
    Redis-backed sliding window rate limiter.

    Uses Redis sorted sets to implement a sliding window rate limiter that works
    correctly across multiple API server instances (distributed deployment).

    Algorithm:
    1. Remove requests older than the time window (cleanup)
    2. Count remaining requests in the current window
    3. If count < max_requests, allow request and add current timestamp
    4. Set TTL on the key to prevent memory leaks

    This implementation is:
    - Distributed: Works across multiple API instances
    - Accurate: True sliding window (not fixed buckets)
    - Efficient: O(log N) operations using sorted sets
    - Memory-safe: TTL prevents unbounded growth

    Args:
        redis_client: Redis async client instance
        key: Rate limit key (e.g., "draft_autosave:{user_id}:{session_id}")
        max_requests: Maximum requests allowed in window
        window_seconds: Time window in seconds

    Returns:
        True if request is within rate limit (allowed), False if exceeded (reject)

    Example:
        # Allow 60 requests per minute per user per session
        allowed = await check_rate_limit_redis(
            redis_client=redis,
            key=f"draft_autosave:{user_id}:{session_id}",
            max_requests=60,
            window_seconds=60,
        )
        if not allowed:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    """
    now = datetime.now(UTC).timestamp()
    window_start = now - window_seconds

    try:
        # Use Redis pipeline for atomic operations
        pipe = redis_client.pipeline()

        # 1. Remove requests older than the window (cleanup)
        pipe.zremrangebyscore(key, 0, window_start)

        # 2. Count requests in current window
        pipe.zcard(key)

        # Execute pipeline and get results
        results = await pipe.execute()
        count_before = results[1]  # Number of requests in window before current request

        # 3. Check if limit exceeded
        if count_before >= max_requests:
            logger.debug(
                "rate_limit_exceeded",
                key=key,
                count=count_before,
                max_requests=max_requests,
                window_seconds=window_seconds,
            )
            return False

        # 4. Add current request to window
        await redis_client.zadd(key, {str(uuid.uuid4()): now})

        # 5. Set TTL to prevent memory leaks (window + buffer)
        await redis_client.expire(key, window_seconds + 10)

        logger.debug(
            "rate_limit_allowed",
            key=key,
            count=count_before + 1,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )

        return True

    except Exception as e:
        # Log error with full context for debugging
        logger.error(
            "rate_limit_check_failed",
            key=key,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )

        # FAIL CLOSED in production/staging (security priority)
        # Prevents rate limit bypass when Redis is unavailable
        if settings.environment in ("production", "staging"):
            logger.warning(
                "rate_limit_failing_closed",
                environment=settings.environment,
                reason="redis_unavailable",
            )
            raise HTTPException(
                status_code=503,
                detail=(
                    "Rate limiting service temporarily unavailable. "
                    "Please try again later."
                ),
            ) from e

        # FAIL OPEN in development/local (availability priority)
        # Allows development to continue even if Redis is down
        # Trade-off: Temporary rate limit bypass vs. developer experience
        logger.warning(
            "rate_limit_failing_open",
            environment=settings.environment,
            reason="redis_unavailable",
            message="Allowing request to proceed (development mode)",
        )
        return True
