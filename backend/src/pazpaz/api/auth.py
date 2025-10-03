"""Authentication endpoints."""

from __future__ import annotations

from typing import Annotated

import redis.asyncio as redis
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.logging import get_logger
from pazpaz.core.redis import get_redis
from pazpaz.db.base import get_db
from pazpaz.middleware.csrf import generate_csrf_token
from pazpaz.schemas.auth import (
    LogoutResponse,
    MagicLinkRequest,
    MagicLinkResponse,
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
    Request a magic link login email.

    Rate limited to 3 requests per hour per IP address.
    """
    # Get request IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"

    # Request magic link (handles rate limiting internally too)
    await request_magic_link(
        email=data.email,
        db=db,
        redis_client=redis_client,
        request_ip=client_ip,
    )

    # Always return success to prevent email enumeration
    return MagicLinkResponse()


@router.get(
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

    The token parameter is typically received via email link.
    On success, a JWT is set as an HttpOnly cookie and returned in response.
    """,
)
async def verify_magic_link_endpoint(
    token: str,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> TokenVerifyResponse:
    """
    Verify magic link token and issue JWT.

    Args:
        token: Magic link token from email
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
        token=token,
        db=db,
        redis_client=redis_client,
    )

    if not result:
        logger.warning("magic_link_verification_failed", token=token[:16])
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

    # Set JWT as HttpOnly cookie
    # SameSite=Lax for CSRF protection while allowing navigation
    # Secure=True in production (HTTPS only)
    response.set_cookie(
        key="access_token",
        value=jwt_token,
        httponly=True,
        samesite="lax",
        secure=False,  # Set to True in production with HTTPS
        max_age=60 * 60 * 24 * 7,  # 7 days
    )

    # Set CSRF token as cookie (not HttpOnly, so JS can read it)
    # SameSite=Strict for additional CSRF protection
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # Allow JS to read for X-CSRF-Token header
        samesite="strict",  # Stricter than JWT cookie for CSRF prevention
        secure=False,  # Set to True in production with HTTPS
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
    Logout by clearing the JWT cookie.

    This invalidates the client-side session by clearing the HttpOnly cookie.
    For enhanced security (JWT blacklisting), consider adding the JWT to a
    Redis blacklist with TTL matching the token expiry.
    """,
)
async def logout_endpoint(
    response: Response,
    access_token: str | None = Cookie(None),
) -> LogoutResponse:
    """
    Logout user by clearing authentication cookie.

    Args:
        response: FastAPI response object (for clearing cookie)
        access_token: Current JWT from cookie (optional)

    Returns:
        Success message
    """
    # Clear authentication cookie
    response.delete_cookie(key="access_token")

    # Clear CSRF token cookie
    response.delete_cookie(key="csrf_token")

    # Optional: Add JWT to blacklist in Redis
    # This prevents token reuse until natural expiry
    # if access_token:
    #     # Extract exp from token and calculate TTL
    #     # Add to Redis: blacklist:{token_hash} with TTL
    #     pass

    logger.info("user_logged_out")

    return LogoutResponse()
