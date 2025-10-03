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
from pazpaz.core.config import settings
from pazpaz.core.logging import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
)
from pazpaz.core.redis import close_redis
from pazpaz.middleware.csrf import CSRFProtectionMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # Startup
    configure_logging(debug=settings.debug)
    logger = get_logger(__name__)
    logger.info(
        "application_startup",
        app_name=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
    )
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


# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get(f"{settings.api_v1_prefix}/health")
async def api_health_check():
    """API v1 health check endpoint."""
    return {"status": "ok", "version": "v1"}
