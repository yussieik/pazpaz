"""CSRF protection middleware using double-submit cookie pattern."""

from __future__ import annotations

import secrets
import uuid

import redis.asyncio as redis
from fastapi import Cookie, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)

# CSRF token expiry (should match JWT expiry - 7 days)
CSRF_TOKEN_EXPIRE_SECONDS = settings.csrf_token_expire_minutes * 60


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware using double-submit cookie pattern.

    Security approach:
    - Generate CSRF token on authentication (stored in Redis with session key)
    - Set CSRF token as cookie (not HttpOnly, SameSite=Strict for reading by JS)
    - Validate X-CSRF-Token header matches cookie value on state-changing requests
    - Exempt safe methods (GET, HEAD, OPTIONS) and docs endpoints

    This prevents CSRF attacks because:
    1. Attacker cannot read cookie from another origin (SameSite=Strict)
    2. Attacker cannot set custom headers in cross-origin requests
    3. Token must match both cookie and header (double-submit)
    """

    async def dispatch(self, request: Request, call_next):
        """Validate CSRF token on state-changing requests."""
        # Exempt safe methods (GET, HEAD, OPTIONS)
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        # Exempt documentation and auth entry endpoints
        # SECURITY NOTE: These endpoints are exempt from CSRF protection because:
        # 1. /docs, /redoc, /openapi.json - Read-only API documentation
        # 2. /auth/magic-link - Cannot require CSRF token before authentication
        #    Protected by:
        #    - IP-based rate limiting (3 requests/hour per IP)
        #    - Email-based rate limiting (5 requests/hour per email)
        #    - Generic responses (prevent email enumeration)
        #    - Optional CAPTCHA in production (TODO: implement for v2)
        # 3. /auth/verify - Magic link verification (single-use tokens)
        #    Protected by:
        #    - Single-use tokens (deleted after verification)
        #    - 10-minute token expiry
        #    - User existence revalidation
        # 4. /payments/webhook/* - External payment provider webhooks
        #    Protected by:
        #    - HMAC-SHA256 signature verification (webhook_secret)
        #    - Idempotency checks (Redis, 24h TTL)
        #    - Provider transaction ID validation
        #    - Workspace scoping (transaction → appointment → workspace)
        # 5. /payments/test-credentials - Test payment credentials without storing
        #    Protected by:
        #    - Rate limiting (prevents credential brute-forcing)
        #    - No credentials logged or stored
        #    - Minimal test API call (no real payment)
        #    - Error sanitization (prevents credential leakage)
        exempt_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            f"{settings.api_v1_prefix}/openapi.json",
            f"{settings.api_v1_prefix}/auth/magic-link",  # Entry point for auth
            f"{settings.api_v1_prefix}/auth/verify",  # Magic link verification (POST)
            f"{settings.api_v1_prefix}/payments/test-credentials",  # Test payment credentials
        ]

        if request.url.path in exempt_paths:
            return await call_next(request)

        # Exempt payment provider webhooks (external callbacks)
        # These endpoints have their own security via HMAC signature verification
        if request.url.path.startswith(f"{settings.api_v1_prefix}/payments/webhook/"):
            return await call_next(request)

        # Validate CSRF token on state-changing methods (POST, PUT, PATCH, DELETE)
        csrf_cookie = request.cookies.get("csrf_token")
        csrf_header = request.headers.get("x-csrf-token")

        # Both cookie and header must be present
        if not csrf_cookie or not csrf_header:
            logger.warning(
                "csrf_validation_failed_missing_token",
                path=request.url.path,
                method=request.method,
                has_cookie=bool(csrf_cookie),
                has_header=bool(csrf_header),
            )
            # Return JSONResponse directly instead of raising HTTPException
            # This avoids Python 3.13 ExceptionGroup issues in middleware
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "CSRF token missing. Both cookie and header required."
                },
            )

        # Tokens must match
        # Use constant-time comparison to prevent timing attacks
        # secrets.compare_digest() prevents attackers from brute-forcing tokens
        # by measuring response times (timing side-channel attack)
        if not secrets.compare_digest(csrf_cookie, csrf_header):
            logger.warning(
                "csrf_validation_failed_token_mismatch",
                path=request.url.path,
                method=request.method,
            )
            # Return JSONResponse directly instead of raising HTTPException
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "CSRF token mismatch. Cookie and header must match."
                },
            )

        logger.debug(
            "csrf_validation_success",
            path=request.url.path,
            method=request.method,
        )

        return await call_next(request)


async def generate_csrf_token(
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    redis_client: redis.Redis,
) -> str:
    """
    Generate CSRF token and store in Redis with workspace scoping.

    Args:
        user_id: User UUID
        workspace_id: Workspace UUID
        redis_client: Redis client

    Returns:
        Generated CSRF token (32 bytes, URL-safe)

    Security:
        - 256-bit entropy (32 bytes)
        - Stored with workspace_id and user_id for scoping
        - Expires with session (7 days by default)
    """
    # Generate cryptographically secure token
    token = secrets.token_urlsafe(32)

    # Store in Redis with workspace scoping
    # Key format: csrf:{workspace_id}:{user_id}
    redis_key = f"csrf:{workspace_id}:{user_id}"

    await redis_client.setex(
        redis_key,
        CSRF_TOKEN_EXPIRE_SECONDS,
        token,
    )

    logger.info(
        "csrf_token_generated",
        user_id=str(user_id),
        workspace_id=str(workspace_id),
    )

    return token


async def validate_csrf_token(
    token: str,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    redis_client: redis.Redis,
) -> bool:
    """
    Validate CSRF token against stored value in Redis.

    Args:
        token: CSRF token to validate
        user_id: User UUID
        workspace_id: Workspace UUID
        redis_client: Redis client

    Returns:
        True if token is valid, False otherwise
    """
    redis_key = f"csrf:{workspace_id}:{user_id}"
    stored_token = await redis_client.get(redis_key)

    if not stored_token:
        logger.warning(
            "csrf_token_not_found",
            user_id=str(user_id),
            workspace_id=str(workspace_id),
        )
        return False

    # Constant-time comparison to prevent timing attacks
    return secrets.compare_digest(token, stored_token)


async def get_csrf_token(
    csrf_token: str | None = Cookie(None),
) -> str | None:
    """
    FastAPI dependency to get CSRF token from cookie.

    Args:
        csrf_token: CSRF token from cookie

    Returns:
        CSRF token if present, None otherwise

    Usage:
        @app.get("/csrf-token")
        async def get_token(token: str = Depends(get_csrf_token)):
            return {"csrf_token": token}
    """
    return csrf_token
