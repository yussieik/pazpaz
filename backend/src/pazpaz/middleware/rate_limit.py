"""IP-based rate limiting middleware with Redis backend and rate limit headers.

This middleware provides:
1. Global IP-based rate limiting (100 requests/minute, 1000 requests/hour)
2. Rate limit headers on all responses (X-RateLimit-*)
3. Environment-aware fail-closed/fail-open behavior
4. Redis-backed sliding window algorithm for distributed deployments

Rate Limit Headers:
-------------------
- X-RateLimit-Limit: Maximum requests allowed in current window
- X-RateLimit-Remaining: Requests remaining in current window
- X-RateLimit-Reset: Unix timestamp when the rate limit resets

Security Behavior:
------------------
- Production/Staging: Fail closed (503 error) if Redis is unavailable
- Development/Local: Fail open (allow request) if Redis is unavailable

Architecture:
-------------
- Uses Redis sorted sets for accurate sliding window rate limiting
- Works correctly across multiple API server instances
- Separate counters for minute and hour windows
- TTL on Redis keys prevents memory leaks
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from ipaddress import AddressValueError, ip_address

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger
from pazpaz.core.redis import get_redis

logger = get_logger(__name__)

# Global rate limits (configurable via environment variables in production)
MINUTE_LIMIT = 100  # requests per minute per IP
HOUR_LIMIT = 1000  # requests per hour per IP
MINUTE_WINDOW = 60  # seconds
HOUR_WINDOW = 3600  # seconds


def get_client_ip(request: Request) -> str:
    """
    Extract client IP with X-Forwarded-For validation against trusted proxies.

    Security Model:
    - Only trusts X-Forwarded-For headers from verified reverse proxies
    - Prevents IP spoofing attacks that could bypass rate limiting
    - Uses leftmost IP in X-Forwarded-For chain (original client)
    - Validates IP format to prevent injection attacks
    - Logs potential spoofing attempts for security monitoring

    Trust Model:
    1. Get direct connection IP (immediate client that connected to this server)
    2. If direct IP is in trusted_proxy_ips, trust X-Forwarded-For header
    3. Otherwise, use direct connection IP (ignore any forwarding headers)

    This prevents malicious clients from sending fake X-Forwarded-For headers
    to bypass rate limits, location-based restrictions, or audit logging.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address as string

    Example (trusted proxy):
        Direct connection: 10.0.1.5 (trusted proxy)
        X-Forwarded-For: 203.0.113.1, 198.51.100.1
        Returns: 203.0.113.1 (original client)

    Example (untrusted client attempting spoofing):
        Direct connection: 198.51.100.50 (not in trusted list)
        X-Forwarded-For: 203.0.113.1 (fake header)
        Returns: 198.51.100.50 (direct IP, ignoring fake header)
        Logs: Warning about potential spoofing attempt
    """
    # Get direct connection IP (immediate client that connected to this server)
    # This is the TCP connection source IP, which cannot be spoofed
    direct_ip = request.client.host if request.client else None

    if not direct_ip:
        # This should never happen in practice (FastAPI always provides request.client)
        # Log as warning for debugging
        logger.warning(
            "no_client_ip_in_request",
            message="request.client is None - cannot extract IP address",
        )
        return "unknown"

    # Security: Only trust X-Forwarded-For from verified reverse proxies
    # If direct connection is from a trusted proxy, we can trust its forwarded headers
    if settings.is_trusted_proxy(direct_ip):
        forwarded_for = request.headers.get("X-Forwarded-For")

        if forwarded_for:
            # Parse leftmost IP in chain (original client)
            # Format: X-Forwarded-For: client, proxy1, proxy2, ...
            client_ip = forwarded_for.split(",")[0].strip()

            # Validate IP format to prevent injection attacks
            # Accepts both IPv4 (e.g., 192.0.2.1) and IPv6 (e.g., 2001:db8::1)
            try:
                ip_address(client_ip)  # Raises ValueError if invalid

                logger.debug(
                    "client_ip_from_trusted_proxy",
                    direct_ip=direct_ip,
                    forwarded_ip=client_ip,
                    message="Accepted X-Forwarded-For from trusted proxy",
                )
                return client_ip

            except (ValueError, AddressValueError) as e:
                # Invalid IP format in X-Forwarded-For header
                # This could be a malformed header or an injection attempt
                logger.warning(
                    "invalid_forwarded_ip_format",
                    direct_ip=direct_ip,
                    forwarded_for=forwarded_for,
                    error=str(e),
                    message="Invalid IP in X-Forwarded-For - using direct IP",
                )
                # Fall through to use direct_ip below

        # Trusted proxy didn't send X-Forwarded-For (unusual but valid)
        # Use direct connection IP (proxy itself)
        logger.debug(
            "trusted_proxy_no_forwarded_for",
            direct_ip=direct_ip,
            message="Trusted proxy did not send X-Forwarded-For header",
        )

    else:
        # Direct connection is NOT from a trusted proxy
        # Check if they sent X-Forwarded-For anyway (potential spoofing attempt)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Security Event: Untrusted client sent X-Forwarded-For header
            # This is likely an IP spoofing attempt to bypass rate limits
            logger.warning(
                "untrusted_proxy_sent_forwarded_for",
                direct_ip=direct_ip,
                forwarded_for=forwarded_for,
                message=(
                    "Potential IP spoofing - "
                    "untrusted client sent X-Forwarded-For"
                ),
            )
            # Continue to use direct_ip (ignore the fake header)

    # Default: Use direct connection IP
    # This is used when:
    # 1. Direct connection is not from a trusted proxy
    # 2. Trusted proxy sent invalid X-Forwarded-For
    # 3. No X-Forwarded-For header present
    return direct_ip


async def check_rate_limit_sliding_window(
    redis_client,
    ip_address: str,
    max_requests: int,
    window_seconds: int,
) -> tuple[bool, int, float]:
    """
    Check rate limit using Redis sliding window algorithm.

    This is similar to core.rate_limiting.check_rate_limit_redis but returns
    additional metadata needed for rate limit headers.

    Args:
        redis_client: Redis async client
        ip_address: Client IP address
        max_requests: Maximum requests in window
        window_seconds: Window size in seconds

    Returns:
        Tuple of (allowed, remaining, reset_timestamp)
        - allowed: True if request is within limit
        - remaining: Number of requests remaining in window
        - reset_timestamp: Unix timestamp when window resets (seconds)

    Raises:
        Exception: If Redis operations fail (caller handles fail-closed/open)
    """
    now = datetime.now(UTC).timestamp()
    window_start = now - window_seconds

    # Redis key format: ratelimit:ip:{window}:{ip_address}
    key = f"ratelimit:ip:{window_seconds}:{ip_address}"

    # Use Redis pipeline for atomic operations
    pipe = redis_client.pipeline()

    # 1. Remove requests older than the window
    pipe.zremrangebyscore(key, 0, window_start)

    # 2. Count requests in current window
    pipe.zcard(key)

    # Execute pipeline
    results = await pipe.execute()
    count_in_window = results[1]

    # Calculate remaining requests
    remaining = max(0, max_requests - count_in_window)

    # Calculate reset timestamp (when oldest request in window expires)
    # If window is empty, reset is now + window;
    # otherwise it's when oldest entry expires
    reset_timestamp = now + window_seconds

    # Check if limit exceeded
    if count_in_window >= max_requests:
        logger.debug(
            "rate_limit_exceeded",
            ip_address=ip_address,
            count=count_in_window,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )
        return False, 0, reset_timestamp

    # Add current request to window
    await redis_client.zadd(key, {f"{now}": now})

    # Set TTL to prevent memory leaks
    await redis_client.expire(key, window_seconds + 60)

    # Recalculate remaining after adding current request
    remaining = max(0, max_requests - count_in_window - 1)

    logger.debug(
        "rate_limit_allowed",
        ip_address=ip_address,
        count=count_in_window + 1,
        remaining=remaining,
        max_requests=max_requests,
        window_seconds=window_seconds,
    )

    return True, remaining, reset_timestamp


class IPRateLimitMiddleware(BaseHTTPMiddleware):
    """
    IP-based rate limiting middleware with Redis backend.

    Enforces global rate limits per IP address:
    - 100 requests per minute
    - 1000 requests per hour

    Adds rate limit headers to all responses:
    - X-RateLimit-Limit: Maximum requests in current window
    - X-RateLimit-Remaining: Requests remaining
    - X-RateLimit-Reset: Unix timestamp when limit resets

    Security Behavior:
    - Production/Staging: Fail closed (503) if Redis unavailable
    - Development/Local: Fail open (allow) if Redis unavailable

    Exemptions:
    - Health check endpoints (/health, /api/v1/health)
    - Metrics endpoint (/metrics) for Prometheus scraping
    """

    async def dispatch(self, request: Request, call_next):
        """Process request with IP-based rate limiting."""
        # Skip rate limiting for health checks and metrics
        # These endpoints need to be always available for monitoring
        exempt_paths = [
            "/health",
            f"{settings.api_v1_prefix}/health",
            "/metrics",
        ]
        if request.url.path in exempt_paths:
            return await call_next(request)

        # Get client IP address
        client_ip = get_client_ip(request)

        try:
            # Get Redis client
            redis_client = await get_redis()

            # Check both minute and hour rate limits
            # We enforce BOTH limits (request must be within both)

            # Check minute limit (100/min)
            (
                minute_allowed,
                minute_remaining,
                minute_reset,
            ) = await check_rate_limit_sliding_window(
                redis_client=redis_client,
                ip_address=client_ip,
                max_requests=MINUTE_LIMIT,
                window_seconds=MINUTE_WINDOW,
            )

            # Check hour limit (1000/hr)
            (
                hour_allowed,
                hour_remaining,
                hour_reset,
            ) = await check_rate_limit_sliding_window(
                redis_client=redis_client,
                ip_address=client_ip,
                max_requests=HOUR_LIMIT,
                window_seconds=HOUR_WINDOW,
            )

            # Determine if request is allowed (must pass both limits)
            allowed = minute_allowed and hour_allowed

            # Use the most restrictive remaining count and reset time
            # This ensures clients see the correct limit that's blocking them
            if not minute_allowed:
                # Minute limit is the blocker
                remaining = minute_remaining
                reset_timestamp = minute_reset
                limit = MINUTE_LIMIT
                window = "minute"
            elif not hour_allowed:
                # Hour limit is the blocker
                remaining = hour_remaining
                reset_timestamp = hour_reset
                limit = HOUR_LIMIT
                window = "hour"
            else:
                # Both limits passed - use minute limit for headers (more restrictive)
                remaining = minute_remaining
                reset_timestamp = minute_reset
                limit = MINUTE_LIMIT
                window = "minute"

            # If rate limit exceeded, return 429
            if not allowed:
                logger.warning(
                    "rate_limit_exceeded_ip",
                    ip_address=client_ip,
                    path=request.url.path,
                    method=request.method,
                    limit=limit,
                    window=window,
                )

                # Create 429 response with rate limit headers
                response = Response(
                    content=(
                        f"Rate limit exceeded. Maximum {limit} requests per {window}. "
                        f"Try again in {int(reset_timestamp - time.time())} seconds."
                    ),
                    status_code=429,
                    media_type="text/plain",
                )

                # Add rate limit headers
                response.headers["X-RateLimit-Limit"] = str(limit)
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["X-RateLimit-Reset"] = str(int(reset_timestamp))
                response.headers["Retry-After"] = str(
                    int(reset_timestamp - time.time())
                )

                return response

            # Request allowed - process it
            response = await call_next(request)

            # Add rate limit headers to successful response
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(reset_timestamp))

            return response

        except HTTPException:
            # Re-raise HTTP exceptions (from fail-closed behavior)
            raise

        except Exception as e:
            # Redis connection error or other unexpected error
            logger.error(
                "rate_limit_middleware_error",
                ip_address=client_ip,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )

            # FAIL CLOSED in production/staging
            if settings.environment in ("production", "staging"):
                logger.warning(
                    "rate_limit_middleware_failing_closed",
                    environment=settings.environment,
                    ip_address=client_ip,
                )
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Rate limiting service temporarily unavailable. "
                        "Please try again later."
                    ),
                ) from e

            # FAIL OPEN in development/local
            logger.warning(
                "rate_limit_middleware_failing_open",
                environment=settings.environment,
                ip_address=client_ip,
                message="Allowing request to proceed (development mode)",
            )

            # Process request without rate limiting
            response = await call_next(request)

            # Add informational headers (development only)
            response.headers["X-RateLimit-Limit"] = str(MINUTE_LIMIT)
            response.headers["X-RateLimit-Remaining"] = "N/A"
            response.headers["X-RateLimit-Reset"] = "N/A"

            return response
