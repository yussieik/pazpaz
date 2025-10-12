"""Audit event API endpoints for HIPAA compliance reporting."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.api.deps import get_current_user, get_db
from pazpaz.core.logging import get_logger
from pazpaz.models.audit_event import AuditAction, AuditEvent, ResourceType
from pazpaz.models.user import User, UserRole
from pazpaz.schemas.audit import AuditEventListResponse, AuditEventResponse
from pazpaz.utils.pagination import (
    calculate_pagination_offset,
    calculate_total_pages,
    get_query_total_count,
)

router = APIRouter(prefix="/audit-events", tags=["audit"])
logger = get_logger(__name__)


@router.get("", response_model=AuditEventListResponse)
async def list_audit_events(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    user_id: uuid.UUID | None = Query(None, description="Filter by user"),
    resource_type: ResourceType | None = Query(
        None, description="Filter by resource type"
    ),
    resource_id: uuid.UUID | None = Query(None, description="Filter by resource ID"),
    action: AuditAction | None = Query(None, description="Filter by action type"),
    start_date: datetime | None = Query(
        None, description="Filter events on or after this date"
    ),
    end_date: datetime | None = Query(
        None, description="Filter events on or before this date"
    ),
    phi_only: bool = Query(False, description="Filter to only PHI access events"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuditEventListResponse:
    """
    List audit events for the workspace with optional filters.

    Returns a paginated list of audit events, ordered by created_at descending.
    All results are scoped to the authenticated workspace.

    SECURITY:
    - Requires JWT authentication
    - Only workspace OWNER can access audit logs (HIPAA compliance requirement)
    - Returns audit events belonging only to authenticated workspace

    HIPAA Compliance:
    - Audit events are immutable (enforced by database triggers)
    - All PHI access is logged (Client, Session, PlanOfCare reads)
    - Metadata is sanitized to prevent PII/PHI leakage
    - Access to audit logs is restricted to workspace owners

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        user_id: Filter by user who performed action
        resource_type: Filter by resource type (Client, Session, etc.)
        resource_id: Filter by specific resource ID
        action: Filter by action type (CREATE, READ, UPDATE, DELETE)
        start_date: Filter events on or after this date
        end_date: Filter events on or before this date
        phi_only: If True, only show PHI access events (Client/Session/PlanOfCare reads)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Paginated list of audit events with total count

    Raises:
        HTTPException: 401 if not authenticated, 403 if not owner

    Examples:
        - GET /api/v1/audit-events?page=1&page_size=50
        - GET /api/v1/audit-events?user_id={uuid}&action=READ
        - GET /api/v1/audit-events?resource_type=Client&phi_only=true
        - GET /api/v1/audit-events?start_date=2025-01-01T00:00:00Z
          &end_date=2025-12-31T23:59:59Z
    """
    # Extract workspace_id from authenticated user
    workspace_id = current_user.workspace_id

    # Restrict audit log access to workspace owners only
    if current_user.role != UserRole.OWNER:
        logger.warning(
            "audit_access_denied",
            user_id=str(current_user.id),
            user_role=current_user.role.value,
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=403,
            detail=(
                "Insufficient permissions to view audit logs. "
                "Only workspace owners can access audit events."
            ),
        )
    logger.debug(
        "audit_events_list_started",
        workspace_id=str(workspace_id),
        page=page,
        page_size=page_size,
        filters={
            "user_id": str(user_id) if user_id else None,
            "resource_type": resource_type.value if resource_type else None,
            "resource_id": str(resource_id) if resource_id else None,
            "action": action.value if action else None,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "phi_only": phi_only,
        },
    )

    # Calculate offset using utility
    offset = calculate_pagination_offset(page, page_size)

    # Build base query with workspace scoping
    base_query = select(AuditEvent).where(AuditEvent.workspace_id == workspace_id)

    # Apply filters
    if user_id:
        base_query = base_query.where(AuditEvent.user_id == user_id)

    if resource_type:
        base_query = base_query.where(AuditEvent.resource_type == resource_type.value)

    if resource_id:
        base_query = base_query.where(AuditEvent.resource_id == resource_id)

    if action:
        base_query = base_query.where(AuditEvent.action == action)

    if start_date:
        base_query = base_query.where(AuditEvent.created_at >= start_date)

    if end_date:
        base_query = base_query.where(AuditEvent.created_at <= end_date)

    # PHI-only filter: READ actions on Client, Session, PlanOfCare
    if phi_only:
        phi_resources = [
            ResourceType.CLIENT.value,
            ResourceType.SESSION.value,
            ResourceType.PLAN_OF_CARE.value,
        ]
        base_query = base_query.where(
            AuditEvent.action == AuditAction.READ,
            AuditEvent.resource_type.in_(phi_resources),
        )

    # Get total count using utility
    total = await get_query_total_count(db, base_query)

    # Get paginated results ordered by created_at descending
    # Uses ix_audit_events_workspace_created index for performance
    query = (
        base_query.order_by(AuditEvent.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    audit_events = result.scalars().all()

    # Build response
    items = [AuditEventResponse.model_validate(event) for event in audit_events]

    # Calculate total pages using utility
    total_pages = calculate_total_pages(total, page_size)

    logger.debug(
        "audit_events_list_completed",
        workspace_id=str(workspace_id),
        total_events=total,
        page=page,
    )

    return AuditEventListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{audit_event_id}", response_model=AuditEventResponse)
async def get_audit_event(
    audit_event_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuditEventResponse:
    """
    Get a single audit event by ID.

    Retrieves an audit event by ID, ensuring it belongs to the authenticated workspace.

    SECURITY:
    - Requires JWT authentication
    - Only workspace OWNER can access audit logs (HIPAA compliance requirement)
    - Returns 404 for both non-existent events and events in other workspaces
      to prevent information leakage

    Args:
        audit_event_id: UUID of the audit event
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Audit event details

    Raises:
        HTTPException: 401 if not authenticated, 403 if not owner,
                      404 if not found or wrong workspace
    """
    from pazpaz.api.deps import get_or_404

    # Extract workspace_id from authenticated user
    workspace_id = current_user.workspace_id

    # Restrict audit log access to workspace owners only
    if current_user.role != UserRole.OWNER:
        logger.warning(
            "audit_access_denied",
            user_id=str(current_user.id),
            user_role=current_user.role.value,
            workspace_id=str(workspace_id),
            audit_event_id=str(audit_event_id),
        )
        raise HTTPException(
            status_code=403,
            detail=(
                "Insufficient permissions to view audit logs. "
                "Only workspace owners can access audit events."
            ),
        )

    # Use helper function for workspace-scoped fetch with generic error
    audit_event = await get_or_404(db, AuditEvent, audit_event_id, workspace_id)

    return AuditEventResponse.model_validate(audit_event)
