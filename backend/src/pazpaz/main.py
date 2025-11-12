"""FastAPI application entry point."""

import secrets
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from pazpaz.api import api_router
from pazpaz.api.metrics import router as metrics_router
from pazpaz.core.config import settings
from pazpaz.core.constants import PHI_FIELDS
from pazpaz.core.logging import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
)
from pazpaz.core.redis import close_redis
from pazpaz.db.base import get_db
from pazpaz.middleware.audit import AuditMiddleware
from pazpaz.middleware.content_type import ContentTypeValidationMiddleware
from pazpaz.middleware.csrf import CSRFProtectionMiddleware
from pazpaz.middleware.json_depth import JSONDepthValidationMiddleware
from pazpaz.middleware.rate_limit import IPRateLimitMiddleware
from pazpaz.middleware.request_size import RequestSizeLimitMiddleware
from pazpaz.middleware.session_activity import SessionActivityMiddleware
from pazpaz.monitoring.sentry_config import init_sentry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # Startup
    configure_logging(debug=settings.debug)
    logger = get_logger(__name__)

    # Initialize Sentry error tracking (with HIPAA-compliant PII stripping)
    init_sentry()
    if settings.sentry_dsn:
        logger.info(
            "sentry_initialized",
            environment=settings.environment,
            message="Sentry error tracking enabled with PII stripping",
        )
    else:
        logger.info(
            "sentry_not_configured",
            message="Sentry DSN not configured, error tracking disabled (acceptable in local dev)",
        )

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

    # Log registered exception handlers
    logger.info(
        "exception_handlers_registered",
        handlers=[
            "Exception (generic)",
            "IntegrityError (database)",
            "DBAPIError (database)",
            "HTTPException (HTTP errors)",
            "RequestValidationError (validation)",
        ],
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
    # In production/staging, validate endpoint uses HTTPS (HIPAA requirement)
    try:
        from pazpaz.core.storage import get_s3_client, verify_bucket_exists

        logger.info("Initializing S3/MinIO storage...")

        # Validate S3 endpoint configuration in production/staging
        if settings.environment in ("production", "staging"):
            try:
                # This will raise ValueError if endpoint is not HTTPS
                s3_client = get_s3_client()

                # Verify S3 connectivity with a simple list_buckets call
                s3_client.list_buckets()

                logger.info(
                    "s3_endpoint_validation_passed",
                    endpoint_url=settings.s3_endpoint_url,
                    environment=settings.environment,
                    tls_enforced=True,
                )
            except ValueError as e:
                # Endpoint validation failed - critical error
                logger.error(
                    "s3_endpoint_validation_failed",
                    environment=settings.environment,
                    error=str(e),
                )
                # Fail startup if S3 endpoint is insecure in production
                raise
            except Exception as e:
                # S3 connectivity failed - warning (may be temporary)
                logger.warning(
                    "s3_connectivity_check_failed",
                    environment=settings.environment,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # Don't fail startup for connectivity issues (may be temporary)

        # Verify bucket exists
        verify_bucket_exists()
        logger.info(
            "S3/MinIO storage ready",
            extra={
                "endpoint": settings.s3_endpoint_url,
                "bucket": settings.s3_bucket_name,
            },
        )
    except ValueError:
        # Re-raise endpoint validation errors (fail-closed in production)
        raise
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

# Initialize rate limiter for slowapi decorator (used in specific routes)
# Note: Global IP-based rate limiting is handled by IPRateLimitMiddleware
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Prometheus HTTP metrics instrumentation (AFTER app initialization)
# Reuses existing /metrics endpoint (backend/src/pazpaz/api/metrics.py)
Instrumentator(
    should_group_status_codes=False,  # Track 200, 201, 404, 500 separately (not 2xx, 4xx)
    should_ignore_untemplated=True,  # Ignore dynamic paths like /api/v1/clients/{uuid}
    should_respect_env_var=True,  # Disable in tests via ENABLE_METRICS=false
    excluded_handlers=["/metrics", "/health"],  # Don't track monitoring endpoints
    env_var_name="ENABLE_METRICS",
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True,
).instrument(app).expose(app, include_in_schema=False, endpoint="/metrics")


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

        # Store request_id in request.state for exception handler access
        request.state.request_id = request_id

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


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================
# Centralized exception handling to prevent information disclosure and
# sanitize error responses. All handlers include request_id for traceability
# and remove sensitive information (PHI, stack traces, internal details).
# PHI_FIELDS imported from pazpaz.core.constants for reuse across modules.


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Handle all uncaught exceptions with sanitized error response.

    Security Measures:
    - Log full error server-side with stack trace for debugging
    - Return sanitized error to client (no stack trace, no internal details)
    - Include request_id for correlation with logs
    - Development: Include error type for debugging
    - Production: Generic message only

    Args:
        request: FastAPI request object
        exc: Unhandled exception

    Returns:
        JSONResponse with sanitized error message and request_id
    """
    logger = get_logger(__name__)

    # Get request ID from state (set by RequestLoggingMiddleware)
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())

    # Log full error server-side with stack trace
    logger.error(
        "unhandled_exception",
        request_id=request_id,
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
        exc_info=True,  # Include full stack trace in logs
    )

    # Return sanitized error to client
    if settings.debug and settings.environment == "local":
        # Development: Include error type for debugging (but no stack trace)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error",
                "error_type": type(exc).__name__,
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )
    else:
        # Production: Generic message only
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An unexpected error occurred. Please contact support with this request ID.",
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """
    Handle database integrity errors (unique constraints, foreign keys).

    Security Measures:
    - Don't expose database constraint names or internal schema
    - Log full error server-side for debugging
    - Return generic conflict message to client

    Args:
        request: FastAPI request object
        exc: SQLAlchemy IntegrityError

    Returns:
        JSONResponse with 409 Conflict status and sanitized message
    """
    logger = get_logger(__name__)

    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())

    logger.error(
        "database_integrity_error",
        request_id=request_id,
        error=str(exc),
        path=request.url.path,
        method=request.method,
        exc_info=True,
    )

    # Don't expose database constraint names or internal schema
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": "A conflict occurred. The requested operation violates data constraints.",
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(DBAPIError)
async def database_error_handler(request: Request, exc: DBAPIError):
    """
    Handle database connection/query errors.

    Security Measures:
    - Don't expose database connection strings or query details
    - Log full error server-side for debugging
    - Return generic service unavailable message to client

    Args:
        request: FastAPI request object
        exc: SQLAlchemy DBAPIError

    Returns:
        JSONResponse with 503 Service Unavailable status and sanitized message
    """
    logger = get_logger(__name__)

    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())

    logger.error(
        "database_error",
        request_id=request_id,
        error=str(exc),
        path=request.url.path,
        method=request.method,
        exc_info=True,
    )

    # Don't expose database connection details
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "Database service temporarily unavailable. Please try again later.",
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Handle FastAPI HTTPExceptions with request_id propagation.

    This handler intercepts HTTPExceptions raised by endpoints (e.g., 409 conflicts,
    404 not found, 403 forbidden) and adds request_id for traceability.

    Args:
        request: FastAPI request object
        exc: FastAPI HTTPException

    Returns:
        JSONResponse with original status code, detail message, and request_id
    """
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())

    # Return response with request_id added
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle Pydantic validation errors with PHI sanitization.

    Security Measures:
    - Redact input values for PHI fields (subjective, objective, etc.)
    - Remove input field from error details for PHI fields
    - Log sanitized errors (never log PHI values)
    - Include request_id for traceability

    Args:
        request: FastAPI request object
        exc: Pydantic RequestValidationError

    Returns:
        JSONResponse with 422 Unprocessable Entity status and sanitized errors
    """
    logger = get_logger(__name__)

    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())

    # Sanitize error details - remove PHI field values
    sanitized_errors = []
    for error in exc.errors():
        # Get the field name from the location tuple
        # loc is like ('body', 'subjective') or ('query', 'email')
        field = error.get("loc", [])[-1] if error.get("loc") else None

        # Create a copy of the error dict to avoid modifying original
        sanitized_error = dict(error)

        if field in PHI_FIELDS:
            # Redact input value for PHI fields
            sanitized_error["msg"] = (
                "Invalid value (details redacted for PHI protection)"
            )
            # Remove input value from error details
            sanitized_error.pop("input", None)

        sanitized_errors.append(sanitized_error)

    logger.warning(
        "validation_error",
        request_id=request_id,
        path=request.url.path,
        method=request.method,
        error_count=len(sanitized_errors),
        # Don't log the actual error details (may contain PHI)
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": sanitized_errors,
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )


# ============================================================================
# MIDDLEWARE ORDERING (executed OUTER to INNER, i.e., bottom to top):
# In FastAPI, middleware is executed in REVERSE order of how they are added:
# - Last added middleware executes FIRST (outer layer)
# - First added middleware executes LAST (inner layer, closest to route handler)
#
# Execution Order (request flows through these layers):
# 1. SecurityHeadersMiddleware - Add security headers to ALL responses
# 2. RequestLoggingMiddleware - Log requests/responses (skip /health)
# 3. IPRateLimitMiddleware - Global IP-based rate limiting (100/min, 1000/hr)
# 4. RequestSizeLimitMiddleware - Check Content-Length BEFORE parsing body (DoS protection)
# 5. JSONDepthValidationMiddleware - Validate JSON nesting depth (DoS protection, NEW)
# 6. ContentTypeValidationMiddleware - Validate Content-Type header (prevent parser confusion)
# 7. SessionActivityMiddleware - Track activity and enforce idle timeout (HIPAA §164.312(a)(2)(iii))
# 8. CSRFProtectionMiddleware - Validate CSRF tokens on state-changing operations (CRITICAL: BEFORE Audit)
# 9. AuditMiddleware - Log data access/modifications (ONLY logs requests that pass CSRF validation)
#
# Why this order?
# - Rate limiting EARLY: Block excessive requests before processing (DoS prevention)
# - Size limit AFTER rate limiting: Reject huge payloads before any parsing
# - JSON depth AFTER size limit: Validate depth before Pydantic parsing (stack overflow prevention)
# - Content-Type validation AFTER JSON depth: Validate header before further processing
# - Session Activity AFTER Content-Type: Check session before CSRF (invalid sessions don't need CSRF check)
# - CSRF BEFORE Audit (CRITICAL): Only audit legitimate requests, prevents audit log pollution
# - Logging wraps everything to track all requests (including rate-limited)

# Add security headers middleware (applies to all responses)
app.add_middleware(SecurityHeadersMiddleware)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Add IP-based rate limiting middleware (EARLY to block excessive requests)
# Global limits: 100 requests/minute, 1000 requests/hour per IP
# Fail-closed in production (503 if Redis down), fail-open in development
app.add_middleware(IPRateLimitMiddleware)

# Add request size limit middleware (AFTER rate limiting to prevent DoS)
app.add_middleware(RequestSizeLimitMiddleware)

# Add JSON depth validation middleware (AFTER size limit, BEFORE Content-Type)
# Prevents deeply nested JSON DoS attacks (stack overflow)
app.add_middleware(JSONDepthValidationMiddleware)

# Add Content-Type validation middleware (AFTER JSON depth, BEFORE session activity)
# Validates Content-Type header to prevent parser confusion attacks
app.add_middleware(ContentTypeValidationMiddleware)

# Add session activity tracking middleware (HIPAA §164.312(a)(2)(iii))
# Enforces automatic logoff after idle timeout (default 30 minutes)
# AFTER Content-Type validation, BEFORE CSRF (invalid sessions don't need CSRF check)
app.add_middleware(SessionActivityMiddleware)

# CRITICAL SECURITY FIX: CSRF must execute BEFORE Audit
# This prevents audit log pollution from invalid CSRF requests
# Add audit logging middleware FIRST (executes LAST, after CSRF validation)
app.add_middleware(AuditMiddleware)

# Add CSRF protection middleware AFTER Audit (executes BEFORE Audit, validates first)
# CSRF validation must happen BEFORE audit logging to prevent log pollution
app.add_middleware(CSRFProtectionMiddleware)

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


@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint for uptime monitoring.

    Supports GET and HEAD methods for compatibility with uptime monitoring services.

    Verifies:
    - Application is running
    - Database connection is alive

    Returns:
        200: Healthy (all systems operational)
        503: Unhealthy (database unavailable)
    """
    logger = get_logger(__name__)

    try:
        # Verify database connection with simple query
        result = await db.execute(text("SELECT 1"))
        result.scalar_one()  # Ensure query executed successfully

        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(
            "health_check_failed",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        ) from e


@app.get(f"{settings.api_v1_prefix}/health")
async def api_health_check():
    """API v1 health check endpoint."""
    return {"status": "ok", "version": "v1"}


@app.get("/test/sentry")
async def test_sentry():
    """
    Test endpoint to verify Sentry error capture.

    This endpoint intentionally raises an exception to test that:
    1. Errors are captured and sent to Sentry
    2. PII stripping is working (no PHI in error details)
    3. Request context (request_id, endpoint) is included

    **Security:** This endpoint should be removed or protected in production.

    Raises:
        ValueError: Test exception for Sentry verification
    """
    raise ValueError(
        "Test error for Sentry - if you see this in Sentry dashboard, error tracking is working!"
    )
