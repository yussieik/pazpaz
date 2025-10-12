"""Audit logging middleware for automatic CRUD operation tracking."""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import Request
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

from pazpaz.core.logging import get_logger
from pazpaz.core.security import decode_access_token
from pazpaz.db.base import AsyncSessionLocal
from pazpaz.models.audit_event import AuditAction, ResourceType
from pazpaz.services.audit_service import create_audit_event

logger = get_logger(__name__)

# Prometheus metrics for audit logging
audit_events_total = Counter(
    "audit_events_total",
    "Total audit events created",
    ["resource_type", "action", "workspace_id"],
)

audit_failures_total = Counter(
    "audit_failures_total",
    "Total audit log write failures",
    ["resource_type", "action", "error_type"],
)

audit_latency_seconds = Histogram(
    "audit_latency_seconds",
    "Time spent writing audit events",
    ["action"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware for automatic audit logging of state-changing operations.

    Captures all POST, PUT, PATCH, DELETE requests and logs them to audit_events table.
    Extracts user context from JWT cookie for attribution.

    Design principles:
    - Append-only logging (never updates or deletes audit events)
    - Non-blocking (uses background tasks to avoid request latency)
    - Fail-safe (audit logging errors don't break requests)
    - Context-aware (extracts user_id, workspace_id from JWT)

    Exempted paths:
    - /health endpoints (no audit needed)
    - /auth endpoints (authentication handled separately)
    - /docs, /redoc, /openapi.json (documentation)
    - /api/v1/audit-events (prevent recursive logging)

    Security features:
    - Only logs authenticated requests (requires valid JWT)
    - Captures IP address and user agent for forensics
    - Sanitizes metadata to prevent PII/PHI leakage
    """

    # Paths to exempt from audit logging
    EXEMPT_PATHS = {
        "/health",
        "/api/v1/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/openapi.json",
        "/api/v1/auth/magic-link",
        "/api/v1/auth/verify",
        "/api/v1/auth/logout",
        "/api/v1/audit-events",  # Prevent recursive logging
    }

    # Resource type mapping from URL path to ResourceType
    PATH_TO_RESOURCE: dict[str, ResourceType] = {
        "/api/v1/clients": ResourceType.CLIENT,
        "/api/v1/appointments": ResourceType.APPOINTMENT,
        "/api/v1/sessions": ResourceType.SESSION,
        "/api/v1/services": ResourceType.SERVICE,
        "/api/v1/locations": ResourceType.LOCATION,
        "/api/v1/users": ResourceType.USER,
    }

    # HTTP method to AuditAction mapping
    METHOD_TO_ACTION: dict[str, AuditAction] = {
        "POST": AuditAction.CREATE,
        "PUT": AuditAction.UPDATE,
        "PATCH": AuditAction.UPDATE,
        "DELETE": AuditAction.DELETE,
        "GET": AuditAction.READ,  # Only for PHI resources
    }

    async def dispatch(self, request: Request, call_next):
        """
        Log state-changing operations to audit_events table.

        Args:
            request: FastAPI request object
            call_next: Next middleware in chain

        Returns:
            Response from downstream middleware/endpoint
        """
        # Skip audit logging for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Only log state-changing methods and PHI reads
        should_audit = self._should_audit_request(request)

        if not should_audit:
            return await call_next(request)

        # Extract authentication context from JWT
        auth_context = await self._extract_auth_context(request)

        # If not authenticated, skip audit logging
        # (endpoint will handle authentication error)
        if not auth_context:
            return await call_next(request)

        # Extract resource context from URL
        resource_context = self._extract_resource_context(request)

        # Process request
        response = await call_next(request)

        # Schedule audit event logging as background task
        # Only log successful operations (2xx status codes)
        if 200 <= response.status_code < 300 and resource_context:
            # Extract request data before background task
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            method = request.method
            path = request.url.path
            query_params = dict(request.query_params) if request.query_params else None

            # For POST requests (CREATE), try to extract resource_id from response
            resource_id = resource_context.get("resource_id")
            if method == "POST" and response.status_code == 201:
                resource_id = await self._extract_resource_id_from_response(response)

            # Update resource_context with extracted ID
            resource_context_with_id = {
                "resource_type": resource_context["resource_type"],
                "resource_id": resource_id,
            }

            # Get db_session from request state if available (test mode)
            db_session = getattr(request.state, "db_session", None)

            # Get additional metadata from request state if provided by endpoint
            additional_metadata = getattr(request.state, "audit_metadata", None)

            # Log audit event immediately (synchronously)
            # This ensures the audit event is logged in the same request context
            # Performance impact is minimal (<10ms per the requirements)
            await self._log_audit_event_background(
                auth_context=auth_context,
                resource_context=resource_context_with_id,
                method=method,
                path=path,
                query_params=query_params,
                status_code=response.status_code,
                ip_address=ip_address,
                user_agent=user_agent,
                db_session=db_session,
                additional_metadata=additional_metadata,
            )

        return response

    def _should_audit_request(self, request: Request) -> bool:
        """
        Determine if request should be audited.

        Audit criteria:
        - POST, PUT, PATCH, DELETE (all state-changing operations)
        - GET for PHI resources (Client, Session, PlanOfCare)

        Args:
            request: FastAPI request object

        Returns:
            True if request should be audited
        """
        # Always audit state-changing methods
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return True

        # Audit GET requests for individual PHI resources (not list operations)
        if request.method == "GET":
            path = request.url.path
            # Only audit individual resource reads (with ID in path), not lists
            # Format: /api/v1/clients/{uuid} (has ID) vs /api/v1/clients (no audit)
            phi_resource_prefixes = [
                "/api/v1/clients/",
                "/api/v1/sessions/",  # When implemented
                "/api/v1/plans-of-care/",  # When implemented
            ]
            # Path must start with prefix and have more after it (the ID)
            return any(
                path.startswith(prefix) and len(path) > len(prefix)
                for prefix in phi_resource_prefixes
            )

        return False

    async def _extract_auth_context(self, request: Request) -> dict[str, Any] | None:
        """
        Extract user and workspace context from JWT cookie.

        Args:
            request: FastAPI request object

        Returns:
            Dict with user_id, workspace_id, or None if not authenticated
        """
        # Get JWT from HttpOnly cookie
        access_token = request.cookies.get("access_token")

        if not access_token:
            return None

        try:
            # Decode JWT
            payload = decode_access_token(access_token)
            user_id_str = payload.get("user_id")
            workspace_id_str = payload.get("workspace_id")

            if not user_id_str or not workspace_id_str:
                logger.warning(
                    "audit_middleware_incomplete_jwt",
                    path=request.url.path,
                    has_user_id=bool(user_id_str),
                    has_workspace_id=bool(workspace_id_str),
                )
                return None

            return {
                "user_id": uuid.UUID(user_id_str),
                "workspace_id": uuid.UUID(workspace_id_str),
            }

        except Exception as e:
            logger.warning(
                "audit_middleware_jwt_decode_failed",
                path=request.url.path,
                error=str(e),
            )
            return None

    async def _extract_resource_id_from_response(self, response) -> uuid.UUID | None:
        """
        Extract resource ID from response body (for POST/CREATE operations).

        Reads the response body to find the 'id' field and validates it's a UUID.
        This is safe because it's called after the response is generated but before
        it's sent to the client.

        Args:
            response: Starlette Response object

        Returns:
            UUID of created resource, or None if not found or invalid
        """
        try:
            # Read response body (only works with JSONResponse)
            import json

            body = getattr(response, "body", None)
            if not body:
                logger.debug(
                    "no_body_attribute_on_response",
                    response_type=type(response).__name__,
                )
                return None

            # Handle bytes body
            if isinstance(body, bytes):
                body = body.decode("utf-8")

            # Parse JSON response
            data = json.loads(body)

            # Extract 'id' field
            resource_id_str = data.get("id")
            if not resource_id_str:
                logger.debug(
                    "no_id_field_in_response_body", response_data_keys=list(data.keys())
                )
                return None

            # Validate and return UUID
            resource_uuid = uuid.UUID(resource_id_str)
            logger.debug(
                "extracted_resource_id_from_response", resource_id=str(resource_uuid)
            )
            return resource_uuid

        except Exception as e:
            logger.warning(
                "failed_to_extract_resource_id_from_response",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            return None

    def _extract_resource_context(self, request: Request) -> dict[str, Any] | None:
        """
        Extract resource type and ID from request URL.

        Parses URL path to determine resource type and optional resource ID.

        Args:
            request: FastAPI request object

        Returns:
            Dict with resource_type and optional resource_id, or None if not found

        Examples:
            - POST /api/v1/clients -> {resource_type: CLIENT, resource_id: None}
            - PUT /api/v1/clients/{uuid} -> {resource_type: CLIENT, resource_id: uuid}
            - GET /api/v1/clients/{uuid} -> {resource_type: CLIENT, resource_id: uuid}
        """
        path = request.url.path

        # Match resource type from path
        resource_type = None
        for path_prefix, res_type in self.PATH_TO_RESOURCE.items():
            if path.startswith(path_prefix):
                resource_type = res_type
                break

        if not resource_type:
            return None

        # Extract resource ID from path (if present)
        # Format: /api/v1/clients/{uuid}
        path_parts = path.split("/")
        resource_id = None

        # Last part might be UUID (if not a query endpoint like /conflicts)
        if len(path_parts) > 4:  # /api/v1/resource/{id}
            potential_id = path_parts[-1]
            # Validate it's a UUID, ignore if not valid
            try:
                resource_id = uuid.UUID(potential_id)
            except ValueError:
                # Not a UUID, might be a sub-resource like /conflicts
                resource_id = None

        return {
            "resource_type": resource_type,
            "resource_id": resource_id,
        }

    async def _log_audit_event_background(
        self,
        auth_context: dict[str, Any],
        resource_context: dict[str, Any],
        method: str,
        path: str,
        query_params: dict[str, Any] | None,
        status_code: int,
        ip_address: str | None,
        user_agent: str | None,
        db_session=None,
        additional_metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Background task to create audit event in database with metrics tracking.

        This method runs as a FastAPI background task after the response is sent,
        using its own database session from the connection pool. This ensures:
        - No impact on request latency
        - Proper transaction isolation
        - Works correctly in both production and tests

        Args:
            auth_context: User and workspace IDs from JWT
            resource_context: Resource type and ID from URL
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            path: Request URL path
            query_params: Query parameters (if any)
            status_code: Response status code
            ip_address: Client IP address
            user_agent: User agent string
            db_session: Database session (for test mode)
            additional_metadata: Additional metadata from endpoint
                (e.g., deleted_reason)
        """
        # Determine action from HTTP method
        action = self.METHOD_TO_ACTION.get(method)

        if not action:
            return

        # Build metadata (non-PII context only)
        metadata = {
            "method": method,
            "path": path,
            "status_code": status_code,
        }

        # Add query params for GET requests (sanitized by create_audit_event)
        if method == "GET" and query_params:
            metadata["query_params"] = query_params

        # Merge additional metadata from endpoint if provided
        if additional_metadata:
            metadata.update(additional_metadata)

        # Track latency
        start_time = time.time()

        try:
            # Use provided db_session (from tests) or create new session from pool
            if db_session is not None:
                # Test mode: use provided session (shares transaction with test)
                # Create audit event
                audit_event = await create_audit_event(
                    db=db_session,
                    user_id=auth_context["user_id"],
                    workspace_id=auth_context["workspace_id"],
                    action=action,
                    resource_type=resource_context["resource_type"],
                    resource_id=resource_context.get("resource_id"),
                    ip_address=ip_address,
                    user_agent=user_agent,
                    metadata=metadata,
                )

                # In test mode, flush to make visible in same transaction
                await db_session.flush()

                # Success metrics
                audit_events_total.labels(
                    resource_type=resource_context["resource_type"].value,
                    action=action.value,
                    workspace_id=str(auth_context["workspace_id"]),
                ).inc()

                logger.debug(
                    "audit_event_logged",
                    action=action.value,
                    resource_type=resource_context["resource_type"].value,
                    user_id=str(auth_context["user_id"]),
                    audit_event_id=str(audit_event.id),
                )

            else:
                # Production mode: create new session with proper context manager
                async with AsyncSessionLocal() as db:
                    try:
                        # Create audit event
                        audit_event = await create_audit_event(
                            db=db,
                            user_id=auth_context["user_id"],
                            workspace_id=auth_context["workspace_id"],
                            action=action,
                            resource_type=resource_context["resource_type"],
                            resource_id=resource_context.get("resource_id"),
                            ip_address=ip_address,
                            user_agent=user_agent,
                            metadata=metadata,
                        )

                        # Commit the audit event in its own transaction
                        await db.commit()

                        # Success metrics
                        audit_events_total.labels(
                            resource_type=resource_context["resource_type"].value,
                            action=action.value,
                            workspace_id=str(auth_context["workspace_id"]),
                        ).inc()

                        logger.debug(
                            "audit_event_logged",
                            action=action.value,
                            resource_type=resource_context["resource_type"].value,
                            user_id=str(auth_context["user_id"]),
                            audit_event_id=str(audit_event.id),
                        )

                    except Exception:
                        # Rollback on error
                        await db.rollback()
                        raise

        except Exception as e:
            # Failure metrics
            audit_failures_total.labels(
                resource_type=resource_context["resource_type"].value,
                action=action.value,
                error_type=type(e).__name__,
            ).inc()

            # Log error but don't fail the request (already sent)
            logger.error(
                "audit_middleware_logging_failed",
                error=str(e),
                error_type=type(e).__name__,
                path=path,
                resource_type=resource_context["resource_type"].value,
                action=action.value,
                exc_info=True,
            )

        finally:
            # Track latency regardless of success/failure
            duration = time.time() - start_time
            audit_latency_seconds.labels(action=action.value).observe(duration)
