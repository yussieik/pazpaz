"""
Session activity tracking for idle timeout enforcement.

Implements HIPAA §164.312(a)(2)(iii) automatic logoff requirement.

Architecture:
- Track last activity timestamp in Redis per session (user_id + jti)
- Middleware checks activity on each authenticated request
- Auto-logout if idle > configured timeout (default 30 minutes)
- Sliding session: activity timestamp updated on successful requests

Redis Key Structure:
    session:activity:{user_id}:{jti} → ISO 8601 timestamp
    TTL: 7 days (matches JWT expiration)

Security Benefits:
- Stolen JWT becomes invalid after idle timeout period
- Unattended sessions automatically expire
- Reduces attack window for session hijacking
- HIPAA §164.312(a)(2)(iii) compliant
"""

from __future__ import annotations

from datetime import UTC, datetime

import redis.asyncio as redis

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


async def update_session_activity(
    redis_client: redis.Redis,
    user_id: str,
    jti: str,
) -> None:
    """
    Update last activity timestamp for session.

    This function is called on every successful authenticated request
    to update the session's "last seen" timestamp. This implements a
    sliding session window for idle timeout detection.

    Args:
        redis_client: Redis client
        user_id: User ID from JWT
        jti: JWT ID (unique per token)

    Redis Key Format:
        session:activity:{user_id}:{jti}

    Example:
        await update_session_activity(
            redis_client=redis_client,
            user_id="550e8400-e29b-41d4-a716-446655440000",
            jti="abc123def456",
        )
    """
    activity_key = f"session:activity:{user_id}:{jti}"
    timestamp = datetime.now(UTC).isoformat()

    # Set activity timestamp with 7-day TTL (matches JWT expiration)
    # This ensures activity records are cleaned up even if logout fails
    await redis_client.setex(
        activity_key,
        60 * 60 * 24 * 7,  # 7 days in seconds
        timestamp,
    )

    logger.debug(
        "session_activity_updated",
        user_id=user_id,
        jti=jti,
        timestamp=timestamp,
    )


async def check_session_idle_timeout(
    redis_client: redis.Redis,
    user_id: str,
    jti: str,
) -> tuple[bool, int | None]:
    """
    Check if session has exceeded idle timeout.

    This function retrieves the last activity timestamp from Redis
    and compares it to the configured idle timeout period. If the
    session has been idle for too long, it returns False to indicate
    the session should be terminated.

    Args:
        redis_client: Redis client
        user_id: User ID from JWT
        jti: JWT ID

    Returns:
        tuple: (is_active, idle_seconds)
            - is_active: True if session is still active (not timed out)
            - idle_seconds: Seconds since last activity (None if no activity record)

    Behavior:
        - No activity record: Returns (True, None) - allows first request
        - Activity within timeout: Returns (True, idle_seconds)
        - Activity exceeds timeout: Returns (False, idle_seconds)
        - Redis error: Returns (True, None) - fail open for availability

    Example:
        is_active, idle_seconds = await check_session_idle_timeout(
            redis_client=redis_client,
            user_id="550e8400-e29b-41d4-a716-446655440000",
            jti="abc123def456",
        )
        if not is_active:
            # Session timed out - reject request
            raise HTTPException(status_code=401, detail="Session expired")
    """
    activity_key = f"session:activity:{user_id}:{jti}"

    try:
        last_activity_str = await redis_client.get(activity_key)

        if not last_activity_str:
            # No activity record - first request after login OR expired record
            # Allow request and create new activity record
            logger.info(
                "session_no_activity_record",
                user_id=user_id,
                jti=jti,
                action="creating_new_record",
            )
            return True, None

        # Parse last activity timestamp
        last_activity = datetime.fromisoformat(last_activity_str)
        now = datetime.now(UTC)
        idle_seconds = (now - last_activity).total_seconds()

        # Check if idle timeout exceeded
        idle_timeout_seconds = settings.session_idle_timeout_minutes * 60

        if idle_seconds > idle_timeout_seconds:
            logger.warning(
                "session_idle_timeout_exceeded",
                user_id=user_id,
                jti=jti,
                idle_seconds=int(idle_seconds),
                timeout_seconds=idle_timeout_seconds,
            )
            return False, int(idle_seconds)

        # Session still active
        return True, int(idle_seconds)

    except Exception as e:
        # Redis error - fail open (allow request)
        # This prevents Redis outages from blocking all user access
        # The middleware will still attempt to update activity on success
        logger.error(
            "session_activity_check_failed",
            user_id=user_id,
            jti=jti,
            error=str(e),
            action="failing_open",
        )
        return True, None


async def invalidate_session_activity(
    redis_client: redis.Redis,
    user_id: str,
    jti: str,
) -> None:
    """
    Invalidate session activity record (on logout).

    This function removes the activity record from Redis when a user
    logs out. This prevents the session from being reactivated if the
    JWT is somehow reused before expiration.

    Args:
        redis_client: Redis client
        user_id: User ID
        jti: JWT ID

    Note:
        This is called by the logout endpoint to ensure clean session
        termination. Even if this fails, the JWT is still blacklisted
        which provides primary logout security.

    Example:
        await invalidate_session_activity(
            redis_client=redis_client,
            user_id="550e8400-e29b-41d4-a716-446655440000",
            jti="abc123def456",
        )
    """
    activity_key = f"session:activity:{user_id}:{jti}"
    await redis_client.delete(activity_key)

    logger.info(
        "session_activity_invalidated",
        user_id=user_id,
        jti=jti,
    )
