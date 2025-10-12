"""FastAPI application entry point."""

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
from pazpaz.middleware.csrf import CSRFProtectionMiddleware


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
       - Restricts inline scripts and styles
       - Note: Vue 3 requires 'unsafe-inline' and 'unsafe-eval' in development
       - Future improvement: Use nonce-based CSP in production for stricter security

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
    """

    async def dispatch(self, request: Request, call_next):
        """Add security headers to response."""
        response: Response = await call_next(request)

        # Content Security Policy (XSS prevention)
        # Restricts resource loading to same origin and trusted sources
        # Vue 3 requires 'unsafe-inline' and 'unsafe-eval' for development builds
        # Production builds should use nonce-based CSP with stricter policies
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "  # Default: only same origin
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "  # Vue requires these
            "style-src 'self' 'unsafe-inline'; "  # Allow inline styles for Vue
            "img-src 'self' data: https:; "  # Allow images from self, data URIs, HTTPS
            "font-src 'self'; "  # Fonts only from same origin
            "connect-src 'self'; "  # API calls only to same origin
            "frame-ancestors 'none';"  # Disallow framing (same as X-Frame-Options)
        )

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


# Add security headers middleware (applies to all responses)
app.add_middleware(SecurityHeadersMiddleware)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Add audit logging middleware (before CSRF to ensure auditing happens)
app.add_middleware(AuditMiddleware)

# Add CSRF protection middleware
app.add_middleware(CSRFProtectionMiddleware)

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
