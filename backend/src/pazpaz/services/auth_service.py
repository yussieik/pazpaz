"""Authentication service for magic link and JWT management."""

from __future__ import annotations

import json
import secrets
import uuid

import redis.asyncio as redis
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.logging import get_logger
from pazpaz.core.rate_limiting import check_rate_limit_redis
from pazpaz.core.security import create_access_token
from pazpaz.models.user import User
from pazpaz.services.email_service import send_magic_link_email

logger = get_logger(__name__)

# Magic link token expiry (10 minutes)
MAGIC_LINK_EXPIRY_SECONDS = 60 * 10

# Magic link rate limit per email (3 per hour)
RATE_LIMIT_MAX_REQUESTS = 3
RATE_LIMIT_WINDOW_SECONDS = 60 * 60


async def request_magic_link(
    email: str,
    db: AsyncSession,
    redis_client: redis.Redis,
    request_ip: str,
) -> None:
    """
    Generate and send magic link to user email.

    Security features:
    - Rate limiting: 3 requests per hour per IP
    - Generic response to prevent email enumeration
    - 256-bit entropy tokens
    - 10-minute expiry

    Args:
        email: User email address
        db: Database session
        redis_client: Redis client
        request_ip: Request IP address for rate limiting

    Raises:
        HTTPException: If rate limit exceeded
    """
    # Check rate limit by IP (3 requests per hour using sliding window)
    rate_limit_key = f"magic_link_rate_limit:{request_ip}"

    if not await check_rate_limit_redis(
        redis_client=redis_client,
        key=rate_limit_key,
        max_requests=RATE_LIMIT_MAX_REQUESTS,
        window_seconds=RATE_LIMIT_WINDOW_SECONDS,
    ):
        logger.warning(
            "magic_link_rate_limit_exceeded",
            ip=request_ip,
            email=email,
        )
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again in an hour.",
        )

    # Look up user by email
    query = select(User).where(User.email == email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        logger.info(
            "magic_link_requested_nonexistent_email",
            email=email,
        )
        # Return success to prevent email enumeration
        return

    if not user.is_active:
        logger.warning(
            "magic_link_requested_inactive_user",
            email=email,
            user_id=str(user.id),
        )
        # Return success to prevent user status enumeration
        return

    # Generate secure token (256-bit entropy)
    token = secrets.token_urlsafe(32)

    # Store token in Redis with user data
    token_data = {
        "user_id": str(user.id),
        "workspace_id": str(user.workspace_id),
        "email": user.email,
    }

    token_key = f"magic_link:{token}"
    await redis_client.setex(
        token_key,
        MAGIC_LINK_EXPIRY_SECONDS,
        json.dumps(token_data),
    )

    # Send magic link email
    await send_magic_link_email(user.email, token)

    logger.info(
        "magic_link_generated",
        email=email,
        user_id=str(user.id),
    )


async def verify_magic_link_token(
    token: str,
    db: AsyncSession,
    redis_client: redis.Redis,
) -> tuple[User, str] | None:
    """
    Verify magic link token and generate JWT.

    Args:
        token: Magic link token
        db: Database session
        redis_client: Redis client

    Returns:
        Tuple of (User, JWT token) if valid, None if invalid/expired

    Security:
        - Token is single-use (deleted after verification)
        - User existence is revalidated in database
        - JWT contains workspace_id for workspace scoping
    """
    # Retrieve token data from Redis
    token_key = f"magic_link:{token}"
    token_data_str = await redis_client.get(token_key)

    if not token_data_str:
        logger.warning("magic_link_token_not_found_or_expired", token=token[:16])
        return None

    # Parse token data
    try:
        token_data = json.loads(token_data_str)
        user_id = uuid.UUID(token_data["user_id"])
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error("magic_link_token_parse_error", error=str(e))
        return None

    # Validate user still exists and is active
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        logger.warning(
            "magic_link_user_not_found_or_inactive",
            user_id=str(user_id),
        )
        # Delete invalid token
        await redis_client.delete(token_key)
        return None

    # Generate JWT
    jwt_token = create_access_token(
        user_id=user.id,
        workspace_id=user.workspace_id,
        email=user.email,
    )

    # Delete token from Redis (single-use)
    await redis_client.delete(token_key)

    logger.info(
        "magic_link_verified",
        user_id=str(user.id),
        workspace_id=str(user.workspace_id),
    )

    return user, jwt_token


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """
    Get user by email address.

    Args:
        db: Database session
        email: User email address

    Returns:
        User if found, None otherwise
    """
    query = select(User).where(User.email == email)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """
    Get user by ID.

    Args:
        db: Database session
        user_id: User UUID

    Returns:
        User if found, None otherwise
    """
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def blacklist_token(redis_client: redis.Redis, token: str) -> None:
    """
    Add a JWT token to the blacklist.

    Stores the token's JTI (JWT ID) in Redis with TTL equal to token expiry.
    This prevents the token from being used after logout.

    Args:
        redis_client: Redis client instance
        token: JWT token to blacklist

    Raises:
        ValueError: If token is invalid or missing JTI claim
    """
    from datetime import UTC, datetime

    from jose import jwt
    from jose.exceptions import ExpiredSignatureError

    from pazpaz.core.config import settings

    try:
        # Decode token to extract JTI and expiration
        # Use verify_exp=True to validate token before blacklisting
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            options={"verify_exp": True},  # Validate it's not already expired
        )

        jti = payload.get("jti")
        exp = payload.get("exp")

        if not jti or not exp:
            raise ValueError("Token missing JTI or exp claim")

        # Calculate TTL (time until token expires)
        now = datetime.now(UTC).timestamp()
        ttl = int(exp - now)

        if ttl <= 0:
            # Token already expired, no need to blacklist
            logger.debug("token_already_expired_skip_blacklist", jti=jti)
            return

        # Store JTI in Redis with TTL
        blacklist_key = f"blacklist:jwt:{jti}"
        await redis_client.setex(blacklist_key, ttl, "1")

        logger.info("jwt_token_blacklisted", jti=jti, ttl=ttl)

    except ExpiredSignatureError:
        logger.debug("attempted_to_blacklist_expired_token")
        # Don't raise error, just skip blacklisting expired tokens
        return
    except Exception as e:
        logger.error(
            "failed_to_blacklist_token",
            error=str(e),
            exc_info=True,
        )
        raise


async def is_token_blacklisted(redis_client: redis.Redis, token: str) -> bool:
    """
    Check if a JWT token has been blacklisted.

    Args:
        redis_client: Redis client instance
        token: JWT token to check

    Returns:
        True if token is blacklisted, False otherwise
    """
    from jose import jwt
    from jose.exceptions import ExpiredSignatureError

    from pazpaz.core.config import settings

    try:
        # Decode token to extract JTI (WITH expiration validation)
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            # Removed verify_exp=False - use default expiration validation
        )

        jti = payload.get("jti")
        if not jti:
            # Old tokens without JTI should be rejected
            logger.warning("token_missing_jti_treating_as_blacklisted")
            return True

        # Check if JTI exists in blacklist
        blacklist_key = f"blacklist:jwt:{jti}"
        result = await redis_client.get(blacklist_key)

        is_blacklisted = result is not None
        if is_blacklisted:
            logger.info("token_is_blacklisted", jti=jti)

        return is_blacklisted

    except ExpiredSignatureError:
        # Expired tokens are implicitly invalid
        logger.debug("token_expired_treating_as_blacklisted")
        return True
    except Exception as e:
        logger.error(
            "failed_to_check_blacklist",
            error=str(e),
            exc_info=True,
        )
        # Fail closed: if we can't check blacklist, reject token
        return True
