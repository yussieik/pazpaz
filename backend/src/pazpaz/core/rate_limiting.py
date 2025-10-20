"""Redis-based distributed rate limiting using sliding window algorithm."""

from __future__ import annotations

import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import redis.asyncio as redis

from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RateLimitEntry:
    """In-memory rate limit entry for fallback."""

    count: int
    window_start: datetime


# In-memory fallback rate limiter (per-process, less accurate but safe)
_fallback_rate_limits: dict[str, RateLimitEntry] = defaultdict(
    lambda: RateLimitEntry(count=0, window_start=datetime.now(UTC))
)
_fallback_lock = threading.Lock()


def _check_rate_limit_fallback(
    key: str,
    max_requests: int,
    window_seconds: int,
) -> bool:
    """
    In-memory fallback rate limiter (per-process, less accurate but safe).

    This is less accurate than Redis sliding window because:
    - Per-process (not distributed across API instances)
    - Fixed window instead of sliding window
    - Data not persisted across restarts

    But it prevents total rate limit bypass when Redis is down.

    Args:
        key: Rate limit key
        max_requests: Maximum requests allowed in window
        window_seconds: Time window in seconds

    Returns:
        True if request is within rate limit (allowed), False if exceeded (reject)
    """
    with _fallback_lock:
        entry = _fallback_rate_limits[key]
        now = datetime.now(UTC)

        # Reset window if expired
        if now - entry.window_start > timedelta(seconds=window_seconds):
            entry.count = 0
            entry.window_start = now

        # Check limit
        if entry.count >= max_requests:
            logger.debug(
                "rate_limit_exceeded_fallback",
                key=key,
                count=entry.count,
                max_requests=max_requests,
            )
            return False

        # Increment counter
        entry.count += 1

        logger.debug(
            "rate_limit_allowed_fallback",
            key=key,
            count=entry.count,
            max_requests=max_requests,
        )

        return True


async def check_rate_limit_redis(
    redis_client: redis.Redis,
    key: str,
    max_requests: int,
    window_seconds: int,
    fail_closed_on_error: bool = False,
) -> bool:
    """
    Redis-backed sliding window rate limiter with configurable error handling.

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
    - Configurable: Fail closed for auth, fail open with fallback for autosave

    Args:
        redis_client: Redis async client instance
        key: Rate limit key (e.g., "magic_link_rate_limit:{ip}")
        max_requests: Maximum requests allowed in window
        window_seconds: Time window in seconds
        fail_closed_on_error: If True, reject requests on Redis failure
            (for auth endpoints). If False, use in-memory fallback
            (for autosave)

    Returns:
        True if request is within rate limit (allowed), False if exceeded (reject)

    Example:
        # Auth endpoint (fail closed for security)
        allowed = await check_rate_limit_redis(
            redis_client=redis,
            key=f"magic_link_rate_limit:{ip}",
            max_requests=3,
            window_seconds=3600,
            fail_closed_on_error=True,  # CRITICAL: Fail closed for auth
        )
        if not allowed:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        # Autosave endpoint (fail open for availability)
        allowed = await check_rate_limit_redis(
            redis_client=redis,
            key=f"draft_autosave:{user_id}:{session_id}",
            max_requests=60,
            window_seconds=60,
            fail_closed_on_error=False,  # Autosave can fail open
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
        )

        return True

    except Exception as e:
        # Log error with full context for debugging
        logger.error(
            "rate_limit_check_failed",
            key=key,
            error=str(e),
            error_type=type(e).__name__,
            fail_closed=fail_closed_on_error,
            exc_info=True,
        )

        # Decision point: fail closed or use fallback?
        if fail_closed_on_error:
            # Fail closed for security-critical endpoints (auth)
            logger.warning(
                "rate_limit_failing_closed_redis_unavailable",
                key=key,
            )
            return False  # Reject request (safe default for auth)
        else:
            # Use in-memory fallback for availability-critical endpoints (autosave)
            logger.warning(
                "rate_limit_using_fallback_redis_unavailable",
                key=key,
            )
            return _check_rate_limit_fallback(key, max_requests, window_seconds)
