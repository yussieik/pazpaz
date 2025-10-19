"""Request size limit middleware to prevent DoS attacks."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Enforce maximum request body size to prevent memory exhaustion DoS attacks.

    Security:
    ---------
    - Checks Content-Length header BEFORE reading request body
    - Prevents attackers from sending extremely large JSON/file payloads
    - Returns 413 Payload Too Large (RFC 7231) with clear error message
    - Logs rejected requests for security monitoring
    - Runs early in middleware stack (before body parsing)

    Size Limits:
    ------------
    - Maximum request size: 20 MB (covers 10 MB file + metadata/form data)
    - File uploads: 10 MB per file (validated separately in file validation)
    - JSON payloads: Covered by same 20 MB limit

    Performance:
    ------------
    - Zero overhead for requests under limit (header check only)
    - No memory consumption until validation passes
    - Prevents memory exhaustion from large payloads

    HIPAA Compliance:
    -----------------
    - Protects availability (164.308(a)(7)(ii)(B))
    - Prevents DoS attacks that could impact PHI availability
    """

    MAX_REQUEST_SIZE = 20 * 1024 * 1024  # 20 MB

    async def dispatch(self, request: Request, call_next):
        """Check Content-Length header before processing request."""
        content_length = request.headers.get("content-length")

        # If Content-Length header is present, validate size
        if content_length:
            try:
                content_length_int = int(content_length)
            except ValueError:
                logger.warning(
                    "invalid_content_length_header",
                    content_length=content_length,
                    client=request.client.host if request.client else None,
                )
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                )

            # Reject if exceeds maximum allowed size
            if content_length_int > self.MAX_REQUEST_SIZE:
                max_size_mb = self.MAX_REQUEST_SIZE // (1024 * 1024)
                provided_size_mb = content_length_int / (1024 * 1024)

                logger.warning(
                    "request_size_limit_exceeded",
                    content_length_mb=round(provided_size_mb, 2),
                    max_allowed_mb=max_size_mb,
                    client=request.client.host if request.client else None,
                    path=request.url.path,
                    method=request.method,
                )

                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            f"Request body too large. Maximum allowed size is {max_size_mb} MB, "
                            f"but received {provided_size_mb:.2f} MB."
                        )
                    },
                )

        # Size is acceptable, continue processing
        return await call_next(request)
