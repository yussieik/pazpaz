"""Authentication endpoints."""

from __future__ import annotations

from typing import Annotated

import redis.asyncio as redis
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger
from pazpaz.core.redis import get_redis
from pazpaz.db.base import get_db
from pazpaz.middleware.csrf import generate_csrf_token
from pazpaz.schemas.auth import (
    LogoutResponse,
    MagicLinkRequest,
    MagicLinkResponse,
    TokenVerifyRequest,
    TokenVerifyResponse,
    UserInToken,
)
from pazpaz.services.auth_service import request_magic_link, verify_magic_link_token

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/magic-link",
    response_model=MagicLinkResponse,
    status_code=200,
    summary="Request magic link",
    description="""
    Request a magic link to be sent to the provided email address.

    Security features:
    - Rate limited to 3 requests per hour per IP address
    - Rate limited to 5 requests per hour per email address (prevents email bombing)
    - Returns generic success message to prevent email enumeration
    - Tokens are 256-bit entropy with 10-minute expiry
    - Single-use tokens (deleted after verification)

    If an active user exists with the email, they will receive a login link.
    Otherwise, no email is sent but the same success message is returned.
    """,
)
async def request_magic_link_endpoint(
    data: MagicLinkRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> MagicLinkResponse:
    """
    Request a magic link login email with enhanced protection.

    Rate limited by:
    - IP address: 3 requests per hour (handled by request_magic_link service)
    - Email address: 5 requests per hour (prevents email bombing attacks)
    """
    from pazpaz.core.rate_limiting import check_rate_limit_redis

    # Get request IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"

    # ADDITIONAL PROTECTION: Per-email rate limiting (5 requests per hour)
    # Prevents email bombing even if attacker uses multiple IPs/proxies
    # This check happens BEFORE IP rate limiting to provide earliest protection
    email_rate_limit_key = f"magic_link_rate_limit_email:{data.email}"

    if not await check_rate_limit_redis(
        redis_client=redis_client,
        key=email_rate_limit_key,
        max_requests=5,  # Max 5 requests per email per hour
        window_seconds=3600,  # 1 hour
    ):
        logger.warning(
            "magic_link_rate_limit_exceeded_for_email",
            email=data.email,
            ip=client_ip,
        )
        # Return generic success to prevent email enumeration
        # Even though rate limit is exceeded, we don't reveal this to the attacker
        # But we log the event for security monitoring
        return MagicLinkResponse()

    # Request magic link (handles IP-based rate limiting internally)
    await request_magic_link(
        email=data.email,
        db=db,
        redis_client=redis_client,
        request_ip=client_ip,
    )

    # Always return success to prevent email enumeration
    return MagicLinkResponse()


@router.post(
    "/verify",
    response_model=TokenVerifyResponse,
    status_code=200,
    summary="Verify magic link token",
    description="""
    Verify a magic link token and receive a JWT access token.

    Security features:
    - Single-use tokens (deleted after successful verification)
    - User existence revalidated in database
    - JWT contains user_id and workspace_id for authorization
    - JWT stored in HttpOnly cookie for XSS protection
    - 7-day JWT expiry
    - Uses POST method to prevent CSRF attacks (state-changing operation)

    The token parameter is received from the email link and sent in request body.
    On success, a JWT is set as an HttpOnly cookie and returned in response.
    """,
)
async def verify_magic_link_endpoint(
    data: TokenVerifyRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> TokenVerifyResponse:
    """
    Verify magic link token and issue JWT.

    Args:
        data: Token verification request containing magic link token
        response: FastAPI response object (for setting cookie)
        db: Database session
        redis_client: Redis client

    Returns:
        JWT access token and user information

    Raises:
        HTTPException: 401 if token is invalid or expired
    """
    # Verify token and get JWT
    result = await verify_magic_link_token(
        token=data.token,
        db=db,
        redis_client=redis_client,
    )

    if not result:
        logger.warning("magic_link_verification_failed", token=data.token[:16])
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired magic link token",
        )

    user, jwt_token = result

    # Generate CSRF token
    csrf_token = await generate_csrf_token(
        user_id=user.id,
        workspace_id=user.workspace_id,
        redis_client=redis_client,
    )

    # Set JWT as HttpOnly cookie (XSS protection)
    # SameSite=Lax for CSRF protection while allowing navigation
    # Secure flag auto-enabled in production (settings.debug=False)
    response.set_cookie(
        key="access_token",
        value=jwt_token,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,  # Auto-enable in production
        max_age=60 * 60 * 24 * 7,  # 7 days
    )

    # Set CSRF token as cookie (not HttpOnly, JS needs to read)
    # SameSite=Strict for additional CSRF protection
    # Secure flag auto-enabled in production (settings.debug=False)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # Allow JS to read for X-CSRF-Token header
        samesite="strict",  # Stricter than JWT cookie for CSRF prevention
        secure=not settings.debug,  # Auto-enable in production
        max_age=60 * 60 * 24 * 7,  # 7 days (match JWT)
    )

    logger.info(
        "user_authenticated",
        user_id=str(user.id),
        workspace_id=str(user.workspace_id),
    )

    return TokenVerifyResponse(
        access_token=jwt_token,
        user=UserInToken.model_validate(user),
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=200,
    summary="Logout",
    description="""
    Logout by clearing the JWT cookie and blacklisting the token.

    Security features:
    - Clears HttpOnly authentication cookie
    - Blacklists JWT token in Redis (prevents reuse)
    - Clears CSRF token cookie
    - Requires CSRF token for protection against logout CSRF attacks

    The blacklisted token cannot be used even if stolen, providing
    enhanced security compared to client-side-only logout.
    """,
)
async def logout_endpoint(
    response: Response,
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    access_token: str | None = Cookie(None),
) -> LogoutResponse:
    """
    Logout user by clearing authentication cookie and blacklisting JWT.

    Args:
        response: FastAPI response object (for clearing cookie)
        redis_client: Redis client for token blacklisting
        access_token: Current JWT from cookie (optional)

    Returns:
        Success message
    """
    from pazpaz.services.auth_service import blacklist_token

    # Blacklist the JWT token (if present)
    if access_token:
        try:
            await blacklist_token(redis_client, access_token)
            logger.info("jwt_token_blacklisted_on_logout")
        except Exception as e:
            # Log error but don't fail logout
            # User experience is that logout succeeds even if blacklisting fails
            logger.error(
                "failed_to_blacklist_token_on_logout",
                error=str(e),
                exc_info=True,
            )

    # Clear authentication cookie
    response.delete_cookie(key="access_token")

    # Clear CSRF token cookie
    response.delete_cookie(key="csrf_token")

    logger.info("user_logged_out")

    return LogoutResponse()
