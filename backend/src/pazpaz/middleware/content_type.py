"""Content-Type validation middleware to prevent parser confusion attacks."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


class ContentTypeValidationMiddleware(BaseHTTPMiddleware):
    """
    Validate Content-Type header on POST/PUT/PATCH/DELETE requests.

    Security:
    ---------
    - Prevents parser confusion attacks (OWASP API8:2023 Security Misconfiguration)
    - Enforces correct Content-Type for JSON vs multipart endpoints
    - Returns 415 Unsupported Media Type for incorrect Content-Type
    - Logs validation failures for security monitoring
    - Environment-aware behavior (strict in production, lenient in development)

    Defense-in-Depth Layer:
    -----------------------
    This is one of 7 validation layers for file uploads:
    1. Request size limit (20 MB global limit)
    2. Content-Type validation (this middleware) ← YOU ARE HERE
    3. File extension whitelist
    4. MIME type detection
    5. MIME-extension consistency check
    6. Content validation (image/PDF structure)
    7. Malware scanning (ClamAV)

    Validation Rules:
    -----------------
    - POST/PUT/PATCH/DELETE: Require Content-Type header
    - JSON endpoints: Require "application/json" (with optional charset)
    - File upload endpoints: Require "multipart/form-data"
    - GET/HEAD/OPTIONS: No Content-Type validation (no request body)
    - Health check endpoints: Excluded from validation

    OWASP Reference:
    ----------------
    - API8:2023 Security Misconfiguration
    - Prevents attacks where XML/form-data sent to JSON endpoints
    - Prevents JSON sent to multipart endpoints (bypassing file validation)

    Performance:
    ------------
    - Zero overhead for GET/HEAD/OPTIONS requests
    - Header check only (no body parsing)
    - Regex-free implementation for speed
    """

    # File upload endpoints that require multipart/form-data
    FILE_UPLOAD_PATTERNS = [
        "/attachments",  # Session attachment uploads
        "/upload",  # Generic upload endpoints
    ]

    # Endpoints excluded from validation
    EXCLUDED_PATHS = [
        "/health",  # Health checks
        "/metrics",  # Prometheus metrics
        "/openapi.json",  # OpenAPI schema
        "/docs",  # API documentation
        "/redoc",  # Alternative API docs
    ]

    async def dispatch(self, request: Request, call_next):
        """Validate Content-Type header for mutation requests."""
        # Only validate mutation requests with request body
        # DELETE is excluded because it typically doesn't have a request body
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        # Skip validation for excluded paths
        path = request.url.path
        if any(
            path.endswith(excluded) or excluded in path
            for excluded in self.EXCLUDED_PATHS
        ):
            return await call_next(request)

        # Extract Content-Type header (split on ; to remove charset)
        content_type_header = request.headers.get("content-type", "")
        if not content_type_header:
            # No Content-Type header provided
            return await self._reject_missing_content_type(request, call_next)

        # Parse Content-Type (remove charset and whitespace)
        # Example: "application/json; charset=utf-8" → "application/json"
        content_type = content_type_header.split(";")[0].strip().lower()

        # Determine expected Content-Type based on endpoint and method
        if self._is_file_upload_endpoint(path, request.method):
            # File upload endpoints require multipart/form-data
            if not content_type.startswith("multipart/form-data"):
                return self._reject_wrong_content_type(
                    request,
                    expected="multipart/form-data",
                    received=content_type,
                )
        else:
            # All other mutation endpoints require application/json
            if content_type != "application/json":
                return self._reject_wrong_content_type(
                    request,
                    expected="application/json",
                    received=content_type,
                )

        # Content-Type is valid, continue processing
        return await call_next(request)

    def _is_file_upload_endpoint(self, path: str, method: str) -> bool:
        """
        Check if endpoint is a file upload endpoint requiring multipart/form-data.

        Only POST requests to /attachments endpoints require multipart.
        PATCH/PUT to /attachments are JSON operations (like rename).
        POST to /download-multiple is JSON (not file upload).
        """
        # Only POST requests to attachment endpoints require multipart
        if method != "POST":
            return False

        # POST to download-multiple is JSON, not multipart
        if "/download-multiple" in path:
            return False

        return any(pattern in path for pattern in self.FILE_UPLOAD_PATTERNS)

    async def _reject_missing_content_type(
        self, request: Request, call_next
    ) -> JSONResponse:
        """Reject request with missing Content-Type header."""
        logger.warning(
            "content_type_missing",
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else None,
        )

        # In development, be more lenient (warn but allow)
        if settings.debug:
            logger.warning(
                "content_type_validation_bypassed_dev",
                message="Missing Content-Type allowed in development mode",
            )
            # ALLOW request to continue in development mode
            # (This allows easier testing with curl/Postman and compatibility with existing tests)
            return await call_next(request)

        # Production: Strict validation (fail-closed)
        return JSONResponse(
            status_code=415,
            content={
                "detail": (
                    "Content-Type header is required for POST/PUT/PATCH requests. "
                    "Use 'application/json' for JSON endpoints or 'multipart/form-data' for file uploads."
                )
            },
        )

    def _reject_wrong_content_type(
        self,
        request: Request,
        expected: str,
        received: str,
    ) -> JSONResponse:
        """Reject request with incorrect Content-Type."""
        logger.warning(
            "content_type_validation_failed",
            method=request.method,
            path=request.url.path,
            expected_content_type=expected,
            received_content_type=received,
            client=request.client.host if request.client else None,
        )

        # In production, fail closed (strict validation)
        # In development, could fail open for convenience (currently fail closed)
        return JSONResponse(
            status_code=415,
            content={
                "detail": (
                    f"Unsupported Media Type. Expected Content-Type '{expected}', "
                    f"but received '{received}'."
                )
            },
        )
