"""FastAPI application entry point."""

import secrets
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from pazpaz.api import api_router
from pazpaz.api.metrics import router as metrics_router
from pazpaz.core.config import settings
from pazpaz.core.logging import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
)
from pazpaz.core.redis import close_redis
from pazpaz.middleware.audit import AuditMiddleware
from pazpaz.middleware.content_type import ContentTypeValidationMiddleware
from pazpaz.middleware.csrf import CSRFProtectionMiddleware
from pazpaz.middleware.request_size import RequestSizeLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # Startup
    configure_logging(debug=settings.debug)
    logger = get_logger(__name__)

    # Validate SECRET_KEY configuration
    if settings.secret_key == "change-me-in-production":
        if not settings.debug:
            # Production mode: REJECT default key
            raise ValueError(
                "CRITICAL SECURITY ERROR: SECRET_KEY must be changed in production!\n"
                "Generate a strong key with: openssl rand -base64 64\n"
                "Set SECRET_KEY in environment or .env file."
            )
        else:
            # Development mode: WARN but allow
            logger.warning(
                "🚨 SECURITY WARNING: Using default SECRET_KEY",
                extra={
                    "message": "This is acceptable ONLY in development mode",
                    "action_required": "Set SECRET_KEY in .env for production",
                    "generate_key": "openssl rand -base64 64",
                },
            )

    logger.info(
        "application_startup",
        app_name=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
    )

    # Verify database SSL/TLS connection (HIPAA requirement)
    try:
        from pazpaz.db.base import verify_ssl_connection

        logger.info("Verifying database SSL/TLS connection...")
        ssl_enabled = await verify_ssl_connection()
        if ssl_enabled:
            logger.info(
                "Database SSL/TLS connection verified",
                extra={
                    "ssl_mode": settings.db_ssl_mode,
                    "environment": settings.environment,
                },
            )
        else:
            logger.warning(
                "Database SSL/TLS is disabled",
                extra={
                    "environment": settings.environment,
                    "message": "Enable SSL for HIPAA compliance in production",
                },
            )
    except Exception as e:
        logger.error(
            "Database SSL/TLS verification failed",
            extra={"error": str(e)},
        )
        # In production/staging, fail-closed (re-raise exception)
        # In development, allow startup but log error
        if settings.environment in ("production", "staging"):
            raise RuntimeError(
                f"Database SSL/TLS verification failed: {e}. "
                "Cannot start application without secure database connection."
            )

    # Initialize S3/MinIO storage (create bucket if not exists)
    try:
        from pazpaz.core.storage import verify_bucket_exists

        logger.info("Initializing S3/MinIO storage...")
        verify_bucket_exists()
        logger.info(
            "S3/MinIO storage ready",
            extra={
                "endpoint": settings.s3_endpoint_url,
                "bucket": settings.s3_bucket_name,
            },
        )
    except Exception as e:
        logger.error(
            "Failed to initialize S3/MinIO storage. "
            "Run 'python scripts/create_storage_buckets.py' to create bucket.",
            extra={"error": str(e)},
        )
        # Don't crash on startup - allow app to start but log error
        # File upload endpoints will fail until bucket is created

    yield
    # Shutdown
    logger.info("application_shutdown", app_name=settings.app_name)
    await close_redis()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    lifespan=lifespan,
)

# Initialize rate limiter and attach to app state
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.

    Security Headers:
    -----------------
    1. Content-Security-Policy (CSP):
       - Prevents XSS attacks by controlling resource loading
       - Production: Nonce-based CSP (no unsafe-inline, no unsafe-eval)
       - Development: Permissive CSP (allows unsafe-inline/eval for Vite HMR)
       - Nonce rotates per request (cryptographically secure random)

    2. X-Content-Type-Options:
       - Prevents MIME type sniffing attacks
       - Forces browsers to respect declared Content-Type

    3. X-XSS-Protection:
       - Legacy XSS filter for older browsers
       - Modern browsers rely on CSP instead

    4. X-Frame-Options:
       - Prevents clickjacking attacks
       - Disallows embedding site in iframes

    5. Strict-Transport-Security (HSTS):
       - Forces HTTPS connections for future requests
       - Only enabled for non-localhost domains (production)
       - Protects against protocol downgrade attacks

    6. X-CSP-Nonce (Custom):
       - Returns CSP nonce for frontend to use in inline scripts
       - Frontend must include nonce in script/style tags: <script nonce={nonce}>
    """

    async def dispatch(self, request: Request, call_next):
        """Add security headers to response with nonce-based CSP."""
        # Generate cryptographically secure nonce (32 bytes = 256 bits)
        # Base64url encoding makes it safe for HTTP headers and HTML attributes
        nonce = secrets.token_urlsafe(32)

        # Store nonce in request state for access by other middleware/endpoints
        request.state.csp_nonce = nonce

        # Process request
        response: Response = await call_next(request)

        # Content Security Policy (XSS prevention)
        if settings.debug or settings.environment == "local":
            # DEVELOPMENT: Permissive CSP for Vite HMR
            # Allows unsafe-inline and unsafe-eval for development convenience
            # Vite dev server uses eval() for module hot reloading
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' http://localhost:* ws://localhost:*; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https: http://localhost:*; "
                "font-src 'self' data:; "
                "connect-src 'self' ws://localhost:* http://localhost:*; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self';"
            )
        else:
            # PRODUCTION: Nonce-based CSP (strict security)
            # NO unsafe-inline, NO unsafe-eval
            # Only scripts/styles with matching nonce attribute will execute
            response.headers["Content-Security-Policy"] = (
                f"default-src 'self'; "
                f"script-src 'self' 'nonce-{nonce}'; "
                f"style-src 'self' 'nonce-{nonce}'; "
                f"img-src 'self' data: https:; "
                f"font-src 'self' data:; "
                f"connect-src 'self'; "
                f"frame-ancestors 'none'; "
                f"base-uri 'self'; "
                f"form-action 'self'; "
                f"upgrade-insecure-requests;"
            )

        # Return nonce to frontend via custom header
        # Frontend can access via response.headers.get('X-CSP-Nonce')
        # and inject into script/style tags: <script nonce={nonce}>
        response.headers["X-CSP-Nonce"] = nonce

        # Prevent MIME type sniffing
        # Browsers must respect the declared Content-Type header
        # Prevents attackers from disguising malicious files as safe types
        response.headers["X-Content-Type-Options"] = "nosniff"

        # XSS Protection for legacy browsers
        # Modern browsers use CSP instead, but this provides defense-in-depth
        # Mode 'block' stops page rendering on XSS detection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Clickjacking protection
        # Prevents site from being embedded in iframes
        # DENY = no framing allowed at all
        response.headers["X-Frame-Options"] = "DENY"

        # HTTP Strict Transport Security (HSTS)
        # Forces browsers to use HTTPS for all future requests
        # Only enable for production domains, not localhost or test environments
        # max-age=31536000 = 1 year; includeSubDomains = apply to all subdomains
        if request.url.hostname not in ["localhost", "127.0.0.1", "testserver"]:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Referrer Policy
        # Controls how much referrer information is included with requests
        # strict-origin-when-cross-origin: Send full URL for same-origin,
        # origin only for cross-origin HTTPS, nothing for HTTP downgrade
        # Prevents leaking sensitive data in URLs (session IDs, tokens, PHI)
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy (formerly Feature-Policy)
        # Disables browser features that could be exploited or leak sensitive data
        # geolocation=() - No location tracking (HIPAA privacy)
        # microphone=() - No audio recording (PHI protection)
        # camera=() - No video recording (PHI protection)
        # payment=() - No payment APIs (not needed for this app)
        # usb=() - No USB device access (security)
        # Note: Some features like fullscreen, clipboard-write are allowed by default
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        )

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request/response logging."""

    async def dispatch(self, request: Request, call_next):
        """Log request and response with structured context."""
        # Skip logging for health check endpoints to avoid noise
        if request.url.path in ["/health", f"{settings.api_v1_prefix}/health"]:
            return await call_next(request)

        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Bind request context for all logs in this request
        bind_context(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        logger = get_logger(__name__)

        # Log request start
        start_time = time.time()
        logger.info(
            "request_started",
            client_host=request.client.host if request.client else None,
        )

        try:
            # Process request
            response: Response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log response
            logger.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as exc:
            # Log error
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "request_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                duration_ms=round(duration_ms, 2),
                exc_info=True,
            )
            raise

        finally:
            # Clear context to avoid leaking between requests
            clear_context()


# MIDDLEWARE ORDERING (executed OUTER to INNER, i.e., bottom to top):
# 1. SecurityHeadersMiddleware - Add security headers to ALL responses
# 2. RequestLoggingMiddleware - Log requests/responses (skip /health)
# 3. RequestSizeLimitMiddleware - Check Content-Length BEFORE parsing body (DoS protection)
# 4. ContentTypeValidationMiddleware - Validate Content-Type header (prevent parser confusion)
# 5. CSRFProtectionMiddleware - Validate CSRF tokens on state-changing operations
# 6. AuditMiddleware - Log data access/modifications (AFTER CSRF validation)
#
# Why this order?
# - Size limit FIRST: Reject huge payloads before any processing (DoS prevention)
# - Content-Type validation AFTER size check: Validate header before body parsing
# - CSRF BEFORE Audit: Only audit legitimate requests
# - Logging wraps everything to track all requests

# Add security headers middleware (applies to all responses)
app.add_middleware(SecurityHeadersMiddleware)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Add CSRF protection middleware (BEFORE Audit to validate state-changing operations)
app.add_middleware(CSRFProtectionMiddleware)

# Add audit logging middleware (AFTER CSRF to ensure only valid requests are audited)
app.add_middleware(AuditMiddleware)

# Add Content-Type validation middleware (AFTER size limit, BEFORE CSRF)
# Validates Content-Type header to prevent parser confusion attacks
app.add_middleware(ContentTypeValidationMiddleware)

# Add request size limit middleware (FIRST - before everything else to prevent DoS)
# This must be LAST in add_middleware calls (executes FIRST due to middleware order)
app.add_middleware(RequestSizeLimitMiddleware)

# Add rate limiting middleware
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS for development
if settings.debug:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],  # Vite dev server
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include API routes
app.include_router(api_router, prefix=settings.api_v1_prefix)

# Include metrics endpoint (no auth, no prefix for Prometheus scraping)
app.include_router(metrics_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get(f"{settings.api_v1_prefix}/health")
async def api_health_check():
    """API v1 health check endpoint."""
    return {"status": "ok", "version": "v1"}
