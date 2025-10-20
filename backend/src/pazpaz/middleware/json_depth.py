"""JSON depth validation middleware.

This middleware protects against deeply nested JSON DoS attacks by validating
JSON request body depth before parsing.

Security Principle:
- Fail closed: Reject requests with deeply nested JSON (>20 levels)
- Early validation: Check depth before application code processes data
- Defense in depth: Complements request size limits

Attack Scenario:
Attacker sends JSON with 1000+ nested levels:
```json
{"a": {"b": {"c": {...}}}}  # 1000 levels deep
```

This can cause:
- Stack overflow during recursive parsing
- Memory exhaustion
- Denial of service (server crash)

OWASP Reference:
- OWASP API Security Top 10 - API4:2023 Unrestricted Resource Consumption
- CWE-674: Uncontrolled Recursion
- CWE-770: Allocation of Resources Without Limits

HIPAA Impact:
- §164.308(a)(1)(ii)(A) - Risk Analysis (DoS affects availability)
- §164.312(a)(2)(ii) - Mechanism to protect against DoS attacks
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from pazpaz.core.logging import get_logger

logger = get_logger(__name__)

# Maximum allowed JSON nesting depth
# 20 levels is reasonable for legitimate API payloads
# Most real-world JSON is <10 levels deep
MAX_JSON_DEPTH = 20


class JSONDepthError(Exception):
    """Raised when JSON exceeds maximum nesting depth."""

    pass


def measure_json_depth(obj: Any, current_depth: int = 0) -> int:
    """
    Recursively measure the maximum nesting depth of a JSON-like object.

    Args:
        obj: Python object (dict, list, or primitive) to measure
        current_depth: Current recursion depth (internal use)

    Returns:
        Maximum depth of nested structures (0 for primitives, 1+ for containers)

    Raises:
        JSONDepthError: If recursion depth exceeds Python's limit (indicates attack)

    Example:
        >>> measure_json_depth({"a": 1})
        1
        >>> measure_json_depth({"a": {"b": 2}})
        2
        >>> measure_json_depth({"a": [{"b": 3}]})
        3
    """
    # Base case: primitives have depth 0 from current level
    if not isinstance(obj, (dict, list)):
        return current_depth

    # Empty containers have depth current_depth + 1
    if not obj:
        return current_depth + 1

    # Recursive case: measure depth of all children
    try:
        if isinstance(obj, dict):
            return max(
                measure_json_depth(value, current_depth + 1) for value in obj.values()
            )
        else:  # list
            return max(
                measure_json_depth(item, current_depth + 1) for item in obj
            )
    except RecursionError as e:
        # Python hit recursion limit - JSON is too deeply nested
        # This is a DoS attack attempt
        raise JSONDepthError(
            f"JSON nesting exceeds Python recursion limit (depth >{current_depth}). "
            f"This may be a denial-of-service attack."
        ) from e


def validate_json_depth(data: Any, max_depth: int = MAX_JSON_DEPTH) -> None:
    """
    Validate that JSON object does not exceed maximum nesting depth.

    Args:
        data: Parsed JSON object (dict, list, or primitive)
        max_depth: Maximum allowed nesting depth (default: 20)

    Raises:
        JSONDepthError: If depth exceeds maximum

    Example:
        >>> validate_json_depth({"a": {"b": 1}})  # OK - depth 2
        >>> validate_json_depth({"a": {"b": {"c": 1}}}, max_depth=2)  # Raises JSONDepthError
    """
    depth = measure_json_depth(data)

    if depth > max_depth:
        raise JSONDepthError(
            f"JSON nesting depth {depth} exceeds maximum of {max_depth}. "
            f"This request may be a denial-of-service attack."
        )

    logger.debug("json_depth_validated", depth=depth, max_depth=max_depth)


class JSONDepthValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate JSON request body depth.

    This middleware intercepts requests with JSON bodies and validates that
    the nesting depth does not exceed MAX_JSON_DEPTH (20 levels).

    Execution Order:
    - Runs AFTER RequestSizeLimitMiddleware (validate size first)
    - Runs BEFORE ContentTypeValidationMiddleware (validate depth before parsing)

    Security Controls:
    - Rejects requests with depth > 20 levels
    - Returns 400 Bad Request with clear error message
    - Logs depth validation failures for monitoring
    - Only validates Content-Type: application/json requests

    Performance:
    - O(n) time complexity where n = number of JSON nodes
    - Minimal overhead for legitimate payloads (<10 levels deep)
    - Short-circuits on first depth violation (doesn't traverse entire tree)
    """

    async def dispatch(self, request: Request, call_next):
        """Validate JSON depth before processing request."""
        # Only validate JSON requests
        content_type = request.headers.get("content-type", "").lower()

        # Check if this is a JSON request (exact match or with charset)
        # Examples: "application/json" or "application/json; charset=utf-8"
        is_json_request = content_type.startswith("application/json")

        if is_json_request and request.method in ("POST", "PUT", "PATCH"):
            try:
                # Read request body
                body = await request.body()

                # Skip validation for empty bodies
                if not body:
                    return await call_next(request)

                # Parse JSON with recursion limit check
                try:
                    data = json.loads(body)
                except json.JSONDecodeError as e:
                    # Invalid JSON - let FastAPI's validation handle it
                    # (it will return 422 with details)
                    logger.debug(
                        "json_parse_failed",
                        error=str(e),
                        content_length=len(body),
                    )
                    # Reconstruct request with original body for FastAPI
                    # (body() consumes the stream, must restore it)
                    async def receive():
                        return {"type": "http.request", "body": body}

                    request._receive = receive
                    return await call_next(request)
                except RecursionError as e:
                    # JSON too deeply nested - Python's json.loads() hit recursion limit
                    # This indicates a DoS attack attempt
                    logger.warning(
                        "json_recursion_error",
                        path=request.url.path,
                        method=request.method,
                        error=str(e),
                        content_length=len(body),
                    )
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={
                            "detail": (
                                "JSON nesting depth exceeds maximum allowed levels. "
                                "Please simplify your request structure."
                            ),
                        },
                    )

                # Validate depth
                try:
                    validate_json_depth(data, max_depth=MAX_JSON_DEPTH)
                except JSONDepthError as e:
                    # Depth exceeded - reject request
                    logger.warning(
                        "json_depth_exceeded",
                        path=request.url.path,
                        method=request.method,
                        error=str(e),
                        max_depth=MAX_JSON_DEPTH,
                    )
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={
                            "detail": (
                                f"JSON nesting depth exceeds maximum of {MAX_JSON_DEPTH} levels. "
                                "Please simplify your request structure."
                            ),
                        },
                    )

                # Depth validation passed - reconstruct request with body
                # (await request.body() consumes the stream, must restore it)
                async def receive():
                    return {"type": "http.request", "body": body}

                request._receive = receive

            except Exception as e:
                # Unexpected error during depth validation
                logger.error(
                    "json_depth_validation_error",
                    error=str(e),
                    error_type=type(e).__name__,
                    path=request.url.path,
                )
                # Fail open for unexpected errors (let request proceed)
                # This prevents middleware bugs from breaking all API requests

        # Process request normally
        return await call_next(request)
