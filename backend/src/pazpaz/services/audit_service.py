"""Audit logging service for HIPAA compliance."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.logging import get_logger
from pazpaz.models.audit_event import AuditAction, AuditEvent, ResourceType

logger = get_logger(__name__)

# Sentinel workspace ID for unauthenticated audit events (failed login attempts)
# This UUID is reserved and should never be used for a real workspace
UNAUTHENTICATED_WORKSPACE_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")

# PII/PHI field patterns to exclude from metadata
SENSITIVE_FIELD_PATTERNS = {
    "password",
    "ssn",
    "social_security",
    "date_of_birth",
    "dob",
    "email",
    "phone",
    "address",
    "medical_history",
    "emergency_contact",
    "first_name",
    "last_name",
    "name",
    "notes",
}


def sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Remove PII/PHI from metadata to ensure audit log compliance.

    Filters out sensitive fields like names, contact info, medical data.
    Only keeps non-sensitive context like field names, counts, statuses.

    Args:
        metadata: Raw metadata dictionary

    Returns:
        Sanitized metadata without PII/PHI, or None if empty

    Examples:
        >>> sanitize_metadata({"first_name": "John", "status": "active"})
        {"status": "active"}

        >>> sanitize_metadata({"updated_fields": ["first_name", "email"]})
        {"updated_fields": ["first_name", "email"]}  # Field names OK, values removed
    """
    if not metadata:
        return None

    sanitized = {}
    for key, value in metadata.items():
        # Skip fields that contain PII/PHI
        if any(pattern in key.lower() for pattern in SENSITIVE_FIELD_PATTERNS):
            continue

        # If value is a list, keep it (e.g., updated_fields list)
        # If value is a dict, recursively sanitize
        if isinstance(value, dict):
            sanitized_value = sanitize_metadata(value)
            if sanitized_value:
                sanitized[key] = sanitized_value
        elif isinstance(value, list):
            # Keep list of field names but not values
            # This allows tracking which fields changed without exposing data
            sanitized[key] = value
        elif not isinstance(value, str) or not any(
            pattern in str(value).lower() for pattern in SENSITIVE_FIELD_PATTERNS
        ):
            # Keep non-string values or strings that don't contain sensitive patterns
            sanitized[key] = value

    return sanitized if sanitized else None


async def create_audit_event(
    db: AsyncSession,
    user_id: uuid.UUID | None,
    workspace_id: uuid.UUID | None,
    action: AuditAction,
    resource_type: ResourceType | str,
    resource_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    """
    Create an audit event for HIPAA compliance logging.

    This is the primary helper function for manual audit logging in endpoints.
    All audit events are append-only and immutable (enforced by database triggers).

    Security guarantees:
    - Automatically sanitizes metadata to remove PII/PHI
    - Validates resource_type is a known enum value
    - Creates immutable audit trail entry

    Args:
        db: Database session (for async insert)
        user_id: User who performed the action (None for system events)
        workspace_id: Workspace context (required for all events)
        action: Type of action (CREATE, READ, UPDATE, DELETE, etc.)
        resource_type: Type of resource (Client, Session, Appointment, etc.)
        resource_id: ID of specific resource being acted upon (optional)
        ip_address: IP address of the request (optional)
        user_agent: User agent string from request (optional)
        metadata: Additional context (will be sanitized to remove PII/PHI)

    Returns:
        Created AuditEvent instance

    Raises:
        ValueError: If resource_type is not a valid ResourceType enum value

    Example:
        ```python
        # Manual audit log for PHI access
        await create_audit_event(
            db=db,
            user_id=current_user.id,
            workspace_id=workspace_id,
            action=AuditAction.READ,
            resource_type=ResourceType.CLIENT,
            resource_id=client_id,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            metadata={"query_params": {"include_inactive": True}},
        )
        ```
    """
    # Normalize resource_type to ResourceType enum
    if isinstance(resource_type, str):
        try:
            resource_type_enum = ResourceType(resource_type)
        except ValueError:
            logger.error(
                "invalid_resource_type",
                resource_type=resource_type,
                valid_types=[rt.value for rt in ResourceType],
            )
            raise ValueError(
                f"Invalid resource_type: {resource_type}. "
                f"Must be one of: {[rt.value for rt in ResourceType]}"
            ) from None
    else:
        resource_type_enum = resource_type

    # Sanitize metadata to remove PII/PHI
    sanitized_metadata = sanitize_metadata(metadata)

    # Generate event_type from resource and action
    # Format: "resource.action" (e.g., "client.read", "session.create")
    event_type = f"{resource_type_enum.value.lower()}.{action.value.lower()}"

    # Use sentinel workspace ID for unauthenticated events
    # This allows us to track failed authentication attempts without a workspace context
    effective_workspace_id = workspace_id or UNAUTHENTICATED_WORKSPACE_ID

    # Create audit event
    audit_event = AuditEvent(
        workspace_id=effective_workspace_id,
        user_id=user_id,
        event_type=event_type,
        resource_type=resource_type_enum.value,
        resource_id=resource_id,
        action=action,
        ip_address=ip_address,
        user_agent=user_agent,
        event_metadata=sanitized_metadata,
    )

    db.add(audit_event)
    await db.flush()  # Flush to get ID without committing transaction

    logger.info(
        "audit_event_created",
        audit_event_id=str(audit_event.id),
        event_type=event_type,
        user_id=str(user_id) if user_id else None,
        workspace_id=str(workspace_id),
        resource_type=resource_type_enum.value,
        resource_id=str(resource_id) if resource_id else None,
        action=action.value,
    )

    return audit_event
