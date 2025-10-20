"""
Session activity tracking middleware for idle timeout enforcement.

Automatically tracks user activity on each request and enforces idle timeout.

HIPAA Compliance: §164.312(a)(2)(iii) - Automatic Logoff

This middleware implements automatic logoff after a period of inactivity
as required by HIPAA for systems accessing Protected Health Information (PHI).

Behavior:
    1. Checks last activity timestamp on each authenticated request
    2. Rejects requests if idle timeout exceeded (401 with specific error)
    3. Updates activity timestamp on successful requests (sliding window)
    4. Exempt paths: auth endpoints, docs, health checks

Architecture:
    - Runs AFTER authentication middleware (requires decoded JWT)
    - Fails open on Redis errors (availability over security)
    - Returns 401 with SESSION_IDLE_TIMEOUT error code for frontend handling

Security Benefits:
    - Stolen JWTs become invalid after idle timeout period
    - Reduces window of opportunity for session hijacking attacks
    - Unattended sessions automatically expire
    - HIPAA §164.312(a)(2)(iii) compliant
"""

from __future__ import annotations

from fastapi import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from pazpaz.core.logging import get_logger
from pazpaz.core.redis import get_redis
from pazpaz.core.security import decode_access_token
from pazpaz.services.session_activity import (
    check_session_idle_timeout,
    update_session_activity,
)

logger = get_logger(__name__)


class SessionActivityMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track session activity and enforce idle timeout.

    HIPAA Compliance: §164.312(a)(2)(iii) - Automatic Logoff

    This middleware checks the last activity timestamp for each authenticated
    request and rejects requests that exceed the configured idle timeout period.

    Exempt Paths:
        - /api/v1/auth/* (authentication endpoints)
        - /docs, /redoc, /openapi.json (API documentation)
        - /health (health check endpoint)

    Error Response Format:
        {
            "detail": "Session expired due to inactivity",
            "error_code": "SESSION_IDLE_TIMEOUT",
            "idle_seconds": 1860
        }

    Frontend Integration:
        Frontend should catch 401 errors with error_code "SESSION_IDLE_TIMEOUT"
        and display user-friendly message with option to re-authenticate.

    Configuration:
        Set SESSION_IDLE_TIMEOUT_MINUTES environment variable (default: 30)
    """

    # Paths that should not track activity or enforce timeout
    # Auth endpoints need to be exempt to allow re-authentication after timeout
    EXEMPT_PATHS = {
        "/api/v1/auth/magic-link",
        "/api/v1/auth/verify",
        "/api/v1/auth/logout",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/api/v1/health",
        "/metrics",
    }

    async def dispatch(self, request: Request, call_next):
        """Check session activity and enforce idle timeout."""

        # Skip exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Extract JWT from cookie
        access_token = request.cookies.get("access_token")

        if not access_token:
            # No token - not authenticated, let auth middleware handle
            return await call_next(request)

        try:
            # Decode JWT to get user_id and jti
            payload = decode_access_token(access_token)
            user_id = payload.get("user_id")
            jti = payload.get("jti")

            if not user_id or not jti:
                # Invalid token - let auth middleware handle
                return await call_next(request)

            # Get Redis client
            redis_client = await get_redis()

            # Check idle timeout
            is_active, idle_seconds = await check_session_idle_timeout(
                redis_client=redis_client,
                user_id=user_id,
                jti=jti,
            )

            if not is_active:
                # Session timed out due to inactivity
                logger.warning(
                    "session_idle_timeout",
                    user_id=user_id,
                    jti=jti,
                    idle_seconds=idle_seconds,
                    path=request.url.path,
                )

                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "Session expired due to inactivity",
                        "error_code": "SESSION_IDLE_TIMEOUT",
                        "idle_seconds": idle_seconds,
                    },
                )

            # Process request
            response = await call_next(request)

            # Update activity timestamp on successful requests (2xx status)
            # This implements sliding window for idle timeout
            if 200 <= response.status_code < 300:
                await update_session_activity(
                    redis_client=redis_client,
                    user_id=user_id,
                    jti=jti,
                )

            return response

        except Exception as e:
            # Error in activity tracking - fail open (allow request)
            # This prevents Redis outages from blocking all authenticated requests
            # The session will still expire via JWT expiration if Redis is down
            logger.error(
                "session_activity_middleware_error",
                error=str(e),
                path=request.url.path,
            )
            return await call_next(request)
