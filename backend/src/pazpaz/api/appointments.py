"""Appointment CRUD API endpoints with conflict detection."""

from __future__ import annotations

import uuid
from datetime import datetime

from arq.connections import ArqRedis
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pazpaz.api.deps import (
    get_arq_pool,
    get_current_user,
    get_db,
    get_or_404,
    verify_client_in_workspace,
)
from pazpaz.core.logging import get_logger
from pazpaz.models.appointment import Appointment, AppointmentStatus
from pazpaz.models.audit_event import AuditAction, ResourceType
from pazpaz.models.client import Client
from pazpaz.models.user import User
from pazpaz.schemas.appointment import (
    AppointmentCreate,
    AppointmentDeleteRequest,
    AppointmentListResponse,
    AppointmentPaymentUpdate,
    AppointmentResponse,
    AppointmentUpdate,
    ConflictCheckResponse,
    ConflictingAppointmentDetail,
    PaymentLinkResponse,
    SendPaymentRequestBody,
    SendPaymentRequestResponse,
)
from pazpaz.services.audit_service import create_audit_event
from pazpaz.services.payment_link_service import (
    generate_payment_link,
    get_payment_link_display_text,
)
from pazpaz.services.payment_service import PaymentService
from pazpaz.utils.appointment_helpers import build_appointment_response_with_client
from pazpaz.utils.pagination import (
    calculate_pagination_offset,
    calculate_total_pages,
    get_query_total_count,
)
from pazpaz.utils.payment_features import PaymentFeatureChecker
from pazpaz.utils.session_helpers import (
    apply_soft_delete,
    get_active_sessions_for_appointment,
    validate_session_not_amended,
)
from pazpaz.workers.settings import QUEUE_NAME

router = APIRouter(prefix="/appointments", tags=["appointments"])
logger = get_logger(__name__)


async def check_conflicts(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    scheduled_start: datetime,
    scheduled_end: datetime,
    exclude_appointment_id: uuid.UUID | None = None,
) -> list[Appointment]:
    """
    Check for conflicting appointments in the given time range.

    Conflict exists if appointments overlap, but NOT if they are exactly back-to-back.

    Overlap logic:
    - Conflicts: scheduled_start < requested_end AND scheduled_end > requested_start
    - Exclude back-to-back: NOT (scheduled_end == requested_start OR
        scheduled_start == requested_end)

    Only SCHEDULED and ATTENDED appointments cause conflicts.
    CANCELLED and NO_SHOW appointments are ignored.

    Args:
        db: Database session
        workspace_id: Workspace to check conflicts in
        scheduled_start: Start time to check
        scheduled_end: End time to check
        exclude_appointment_id: Appointment ID to exclude (for updates)

    Returns:
        List of conflicting appointments
    """
    # Build query for overlapping appointments
    # Uses ix_appointments_workspace_time_range index for performance
    query = select(Appointment).where(
        Appointment.workspace_id == workspace_id,
        Appointment.scheduled_start < scheduled_end,
        Appointment.scheduled_end > scheduled_start,
        # Only SCHEDULED and ATTENDED appointments cause conflicts
        Appointment.status.in_(
            [AppointmentStatus.SCHEDULED, AppointmentStatus.ATTENDED]
        ),
    )

    # Exclude the appointment being updated
    if exclude_appointment_id:
        query = query.where(Appointment.id != exclude_appointment_id)

    # Execute query
    result = await db.execute(query)
    potential_conflicts = result.scalars().all()

    # Filter out back-to-back appointments (exact adjacency is OK)
    conflicts = [
        appt
        for appt in potential_conflicts
        if not (
            appt.scheduled_end == scheduled_start
            or appt.scheduled_start == scheduled_end
        )
    ]

    return conflicts


def get_client_initials(client: Client) -> str:
    """
    Generate privacy-preserving initials from client name.

    Examples:
        'John Doe' -> 'J.D.'
        'Alice' -> 'A.'
        '' -> '?'

    Args:
        client: Client instance with first_name and last_name

    Returns:
        Initials string (e.g., 'J.D.')
    """
    first = client.first_name[0].upper() if client.first_name else ""
    last = client.last_name[0].upper() if client.last_name else ""

    if first and last:
        return f"{first}.{last}."
    elif first:
        return f"{first}."
    elif last:
        return f"{last}."
    else:
        return "?"


async def validate_status_transition(
    db: AsyncSession,
    appointment: Appointment,
    new_status: AppointmentStatus,
) -> None:
    """
    Validate appointment status transitions according to business rules.

    Valid transitions:
    - scheduled → attended (always allowed)
    - scheduled → cancelled (always allowed)
    - scheduled → no_show (always allowed)
    - attended → no_show (allowed - correction)
    - attended → cancelled (blocked if session exists - data protection)
    - cancelled → scheduled (allowed - restore)
    - no_show → scheduled (allowed - correction)
    - no_show → attended (allowed - correction)

    Invalid transitions:
    - attended → scheduled (data integrity)
    - attended → cancelled (if session exists - data protection)

    Args:
        db: Database session
        appointment: Current appointment
        new_status: Desired new status

    Raises:
        HTTPException: 400 if transition is invalid
    """
    current_status = appointment.status

    # No change - always valid
    if current_status == new_status:
        return

    # Transitions from SCHEDULED - all allowed
    if current_status == AppointmentStatus.SCHEDULED:
        return

    # Transitions from ATTENDED
    if current_status == AppointmentStatus.ATTENDED:
        # attended → no_show: allowed (correction)
        if new_status == AppointmentStatus.NO_SHOW:
            return

        # attended → cancelled: check for session
        if new_status == AppointmentStatus.CANCELLED:
            # Check if session exists using centralized helper
            sessions = await get_active_sessions_for_appointment(db, appointment.id)

            if sessions:
                logger.warning(
                    "status_transition_blocked",
                    appointment_id=str(appointment.id),
                    current_status=current_status.value,
                    new_status=new_status.value,
                    reason="session_exists",
                )
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Cannot cancel attended appointment with existing "
                        "session note. Delete the session note first to "
                        "maintain data integrity."
                    ),
                )
            return

        # attended → scheduled: not allowed
        if new_status == AppointmentStatus.SCHEDULED:
            logger.warning(
                "status_transition_blocked",
                appointment_id=str(appointment.id),
                current_status=current_status.value,
                new_status=new_status.value,
                reason="invalid_transition",
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot change attended appointment back to scheduled. "
                    "This prevents data integrity issues."
                ),
            )

    # Transitions from CANCELLED
    if current_status == AppointmentStatus.CANCELLED:
        # cancelled → scheduled: allowed (restore)
        if new_status == AppointmentStatus.SCHEDULED:
            return
        # Other transitions not typically needed but allow them
        return

    # Transitions from NO_SHOW
    if current_status == AppointmentStatus.NO_SHOW:
        # no_show → scheduled: allowed (correction)
        # no_show → completed: allowed (correction)
        return


@router.post("", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    appointment_data: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> AppointmentResponse:
    """
    Create a new appointment with conflict detection.

    Creates a new appointment after verifying:
    1. Client belongs to the workspace
    2. No conflicting appointments exist in the time slot

    SECURITY: workspace_id is derived from authenticated user's JWT token (server-side).

    Args:
        appointment_data: Appointment creation data (without workspace_id)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Created appointment with client information

    Raises:
        HTTPException: 401 if not authenticated, 404 if client not found,
            409 if conflict exists, 422 if validation fails
    """
    workspace_id = current_user.workspace_id
    logger.info("appointment_create_started", workspace_id=str(workspace_id))

    # Verify client exists and belongs to workspace
    await verify_client_in_workspace(
        db=db,
        client_id=appointment_data.client_id,
        workspace_id=workspace_id,
    )

    # Check for conflicts
    conflicts = await check_conflicts(
        db=db,
        workspace_id=workspace_id,
        scheduled_start=appointment_data.scheduled_start,
        scheduled_end=appointment_data.scheduled_end,
    )

    if conflicts:
        logger.info(
            "appointment_conflict_detected",
            workspace_id=str(workspace_id),
            conflict_count=len(conflicts),
        )
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Appointment conflicts with existing appointments",
                "conflicting_appointments": [
                    {
                        "id": str(conflict.id),
                        "scheduled_start": conflict.scheduled_start.isoformat(),
                        "scheduled_end": conflict.scheduled_end.isoformat(),
                        "status": conflict.status.value,
                    }
                    for conflict in conflicts
                ],
            },
        )

    # Create new appointment with injected workspace_id
    appointment = Appointment(
        workspace_id=workspace_id,
        client_id=appointment_data.client_id,
        scheduled_start=appointment_data.scheduled_start,
        scheduled_end=appointment_data.scheduled_end,
        location_type=appointment_data.location_type,
        location_details=appointment_data.location_details,
        notes=appointment_data.notes,
        status=AppointmentStatus.SCHEDULED,
        payment_price=appointment_data.payment_price,
        payment_status=appointment_data.payment_status.value,
        payment_method=appointment_data.payment_method.value
        if appointment_data.payment_method
        else None,
        payment_notes=appointment_data.payment_notes,
    )

    db.add(appointment)
    await db.commit()
    await db.refresh(appointment)

    # Load client relationship for response
    query = (
        select(Appointment)
        .where(Appointment.id == appointment.id)
        .options(selectinload(Appointment.client))
    )
    result = await db.execute(query)
    appointment_with_client = result.scalar_one()

    # Build response with client summary
    response_data = build_appointment_response_with_client(appointment_with_client)

    # Enqueue Google Calendar sync task (non-blocking)
    # This will sync the appointment to Google Calendar if integration is enabled
    try:
        await arq_pool.enqueue_job(
            "sync_appointment_to_google_calendar",
            appointment_id=str(appointment.id),
            action="create",
            _queue_name=QUEUE_NAME,
        )
        logger.debug(
            "google_calendar_sync_task_enqueued",
            appointment_id=str(appointment.id),
            action="create",
        )
    except Exception as e:
        # Log error but don't fail appointment creation
        logger.error(
            "google_calendar_sync_enqueue_failed",
            appointment_id=str(appointment.id),
            action="create",
            error=str(e),
            exc_info=True,
        )

    logger.info(
        "appointment_created",
        appointment_id=str(appointment.id),
        workspace_id=str(workspace_id),
        client_id=str(appointment_data.client_id),
    )
    return response_data


@router.get("", response_model=AppointmentListResponse)
async def list_appointments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    start_date: datetime | None = Query(
        None, description="Filter by start date (inclusive)"
    ),
    end_date: datetime | None = Query(
        None, description="Filter by end date (inclusive)"
    ),
    client_id: uuid.UUID | None = Query(None, description="Filter by client ID"),
    status: AppointmentStatus | None = Query(None, description="Filter by status"),
) -> AppointmentListResponse:
    """
    List appointments in the workspace with optional filters.

    Returns a paginated list of appointments, ordered by scheduled_start descending.
    All results are scoped to the authenticated workspace.

    SECURITY: Only returns appointments belonging to the authenticated user's
    workspace (from JWT).

    Args:
        current_user: Authenticated user (from JWT token)
        db: Database session
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        start_date: Filter appointments starting on or after this date
        end_date: Filter appointments starting on or before this date
        client_id: Filter by specific client
        status: Filter by appointment status

    Returns:
        Paginated list of appointments with client information

    Raises:
        HTTPException: 401 if not authenticated
    """
    workspace_id = current_user.workspace_id
    logger.debug(
        "appointment_list_started",
        workspace_id=str(workspace_id),
        page=page,
        page_size=page_size,
        filters={
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "client_id": str(client_id) if client_id else None,
            "status": status.value if status else None,
        },
    )

    # Calculate offset using utility
    offset = calculate_pagination_offset(page, page_size)

    # Build base query with workspace scoping
    base_query = select(Appointment).where(Appointment.workspace_id == workspace_id)

    # Apply date range filters (uses ix_appointments_workspace_time_range index)
    if start_date:
        base_query = base_query.where(Appointment.scheduled_start >= start_date)
    if end_date:
        base_query = base_query.where(Appointment.scheduled_start <= end_date)

    # Apply client filter
    if client_id:
        base_query = base_query.where(Appointment.client_id == client_id)

    # Apply status filter
    if status:
        base_query = base_query.where(Appointment.status == status)

    # Get total count using utility
    total = await get_query_total_count(db, base_query)

    # Get paginated results ordered by scheduled_start descending
    query = (
        base_query.options(selectinload(Appointment.client))
        .order_by(Appointment.scheduled_start.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    appointments = result.scalars().all()

    # Build response with client summaries
    items = [
        build_appointment_response_with_client(appointment)
        for appointment in appointments
    ]

    # Calculate total pages using utility
    total_pages = calculate_total_pages(total, page_size)

    return AppointmentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/conflicts", response_model=ConflictCheckResponse)
async def check_appointment_conflicts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    scheduled_start: datetime = Query(..., description="Start time to check"),
    scheduled_end: datetime = Query(..., description="End time to check"),
    exclude_appointment_id: uuid.UUID | None = Query(
        None,
        description="Appointment ID to exclude (for updates)",
    ),
) -> ConflictCheckResponse:
    """
    Check for appointment conflicts in a time range.

    Used by frontend to validate appointment times before submission.

    SECURITY: Only checks conflicts within the authenticated user's workspace
    (from JWT).

    Args:
        current_user: Authenticated user (from JWT token)
        db: Database session
        scheduled_start: Start time to check
        scheduled_end: End time to check
        exclude_appointment_id: Appointment to exclude (when updating)

    Returns:
        Conflict check result with list of conflicting appointments

    Raises:
        HTTPException: 401 if not authenticated,
            422 if scheduled_end is not after scheduled_start
    """
    workspace_id = current_user.workspace_id

    # Validate time range
    if scheduled_end <= scheduled_start:
        raise HTTPException(
            status_code=422,
            detail="scheduled_end must be after scheduled_start",
        )

    logger.debug(
        "conflict_check_started",
        workspace_id=str(workspace_id),
        scheduled_start=scheduled_start.isoformat(),
        scheduled_end=scheduled_end.isoformat(),
        exclude_appointment_id=str(exclude_appointment_id)
        if exclude_appointment_id
        else None,
    )

    # Check for conflicts
    conflicts = await check_conflicts(
        db=db,
        workspace_id=workspace_id,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        exclude_appointment_id=exclude_appointment_id,
    )

    # Load client relationships for conflicts and build privacy-preserving response
    if conflicts:
        conflict_ids = [c.id for c in conflicts]
        query = (
            select(Appointment)
            .where(Appointment.id.in_(conflict_ids))
            .options(selectinload(Appointment.client))
        )
        result = await db.execute(query)
        conflicts_with_clients = result.scalars().all()

        # Build response items with client initials (privacy-preserving)
        conflict_responses = []
        for appointment in conflicts_with_clients:
            client_initials = (
                get_client_initials(appointment.client) if appointment.client else "?"
            )
            conflict_detail = ConflictingAppointmentDetail(
                id=appointment.id,
                scheduled_start=appointment.scheduled_start,
                scheduled_end=appointment.scheduled_end,
                client_initials=client_initials,
                location_type=appointment.location_type,
                status=appointment.status,
            )
            conflict_responses.append(conflict_detail)
    else:
        conflict_responses = []

    return ConflictCheckResponse(
        has_conflict=len(conflicts) > 0,
        conflicting_appointments=conflict_responses,
    )


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    """
    Get a single appointment by ID.

    Retrieves an appointment by ID, ensuring it belongs to the authenticated workspace.

    SECURITY: Returns 404 for both non-existent appointments and appointments
    in other workspaces to prevent information leakage. workspace_id is derived
    from JWT token.

    Args:
        appointment_id: UUID of the appointment
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Appointment details with client information

    Raises:
        HTTPException: 401 if not authenticated,
            404 if not found or wrong workspace
    """
    workspace_id = current_user.workspace_id
    # Fetch with workspace scoping using generic helper
    # (Validates existence and workspace access)
    await get_or_404(db, Appointment, appointment_id, workspace_id)

    # Load client relationship for response
    query = (
        select(Appointment)
        .where(Appointment.id == appointment_id)
        .options(selectinload(Appointment.client))
    )
    result = await db.execute(query)
    appointment_with_client = result.scalar_one()

    # Build response with client summary
    return build_appointment_response_with_client(appointment_with_client)


@router.put("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: uuid.UUID,
    appointment_data: AppointmentUpdate,
    allow_conflict: bool = Query(
        False,
        description="Allow update even if conflicts exist (for 'Keep Both' scenario)",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> AppointmentResponse:
    """
    Update an existing appointment with conflict detection.

    Updates appointment fields. Only provided fields are updated.
    If time is changed, conflict detection is performed unless allow_conflict=True.
    Appointment must belong to the authenticated workspace.

    SECURITY: Verifies workspace ownership before allowing updates.
    workspace_id is derived from JWT token (server-side).

    Args:
        appointment_id: UUID of the appointment to update
        appointment_data: Fields to update
        allow_conflict: Allow update even if conflicts exist (default: False)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Updated appointment with client information

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
            409 if conflict (and allow_conflict=False), 422 if validation fails
    """
    workspace_id = current_user.workspace_id
    # Fetch existing appointment with workspace scoping (raises 404 if not found)
    appointment = await get_or_404(db, Appointment, appointment_id, workspace_id)

    # Load client relationship
    query = (
        select(Appointment)
        .where(Appointment.id == appointment_id)
        .options(selectinload(Appointment.client))
    )
    result = await db.execute(query)
    appointment = result.scalar_one()

    # Get update data
    update_data = appointment_data.model_dump(exclude_unset=True)

    # If client_id is being updated, verify new client belongs to workspace
    if "client_id" in update_data:
        await verify_client_in_workspace(
            db=db,
            client_id=update_data["client_id"],
            workspace_id=workspace_id,
        )

    # If status is being updated, validate the transition
    if "status" in update_data:
        await validate_status_transition(
            db=db,
            appointment=appointment,
            new_status=update_data["status"],
        )

    # Handle payment status changes and auto-set paid_at
    if "payment_status" in update_data:
        # Convert enum to string for database storage
        if hasattr(update_data["payment_status"], "value"):
            update_data["payment_status"] = update_data["payment_status"].value

        # Auto-set paid_at when marking as paid (if not already provided)
        if (
            update_data["payment_status"] == "paid"
            and "paid_at" not in update_data
            and appointment.payment_status != "paid"
        ):
            update_data["paid_at"] = datetime.now()
            logger.debug(
                "auto_set_paid_at",
                appointment_id=str(appointment_id),
                paid_at=update_data["paid_at"].isoformat(),
            )

    # Convert payment_method enum to string if provided
    if "payment_method" in update_data and update_data["payment_method"] is not None:
        if hasattr(update_data["payment_method"], "value"):
            update_data["payment_method"] = update_data["payment_method"].value

    # Determine final scheduled times for conflict check
    final_start = update_data.get("scheduled_start", appointment.scheduled_start)
    final_end = update_data.get("scheduled_end", appointment.scheduled_end)

    # Validate end is after start
    if final_end <= final_start:
        raise HTTPException(
            status_code=422,
            detail="scheduled_end must be after scheduled_start",
        )

    # Check for conflicts if time changed (unless allow_conflict=True)
    time_changed = "scheduled_start" in update_data or "scheduled_end" in update_data
    if time_changed and not allow_conflict:
        conflicts = await check_conflicts(
            db=db,
            workspace_id=workspace_id,
            scheduled_start=final_start,
            scheduled_end=final_end,
            exclude_appointment_id=appointment_id,
        )

        if conflicts:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Updated time conflicts with existing appointments",
                    "conflicting_appointments": [
                        {
                            "id": str(conflict.id),
                            "scheduled_start": conflict.scheduled_start.isoformat(),
                            "scheduled_end": conflict.scheduled_end.isoformat(),
                            "status": conflict.status.value,
                        }
                        for conflict in conflicts
                    ],
                },
            )

    # Track field-level changes for audit log
    changes = {}
    for field, new_value in update_data.items():
        old_value = getattr(appointment, field)
        if old_value != new_value:
            # Format values for audit log (convert enums, datetimes to strings)
            if hasattr(old_value, "value"):  # Enum
                old_str = old_value.value
            elif hasattr(old_value, "isoformat"):  # datetime
                old_str = old_value.isoformat()
            else:
                old_str = str(old_value)

            if hasattr(new_value, "value"):  # Enum
                new_str = new_value.value
            elif hasattr(new_value, "isoformat"):  # datetime
                new_str = new_value.isoformat()
            else:
                new_str = str(new_value)

            changes[field] = {"old": old_str, "new": new_str}

    # Update fields
    for field, value in update_data.items():
        setattr(appointment, field, value)

    # Update edit tracking if there were actual changes
    if changes:
        appointment.edited_at = datetime.now()
        appointment.edit_count += 1
        # Note: Audit logging handled automatically by AuditMiddleware
        # Field-level changes are tracked in the changes dict above

    await db.commit()
    await db.refresh(appointment)

    # Reload with client relationship and workspace (needed for payment feature check)
    query = (
        select(Appointment)
        .where(Appointment.id == appointment.id)
        .options(
            selectinload(Appointment.client),
            selectinload(Appointment.workspace),
        )
    )
    result = await db.execute(query)
    appointment = result.scalar_one()

    # ============================================================================
    # PHASE 0: Payment Feature Flag Check (STUB - NO ACTUAL PAYMENT PROCESSING)
    # ============================================================================
    # Check if appointment was just marked as attended (completed)
    # If payments are enabled and auto-send is configured, this is where we would
    # trigger payment request creation in Phase 1.
    #
    # Phase 0: Only log the detection, don't trigger any payment actions
    # Phase 1: Will implement actual payment request creation here
    if "status" in changes and changes["status"]["new"] == "attended":
        # Check if payment request should be sent
        can_send, reason = PaymentFeatureChecker.can_send_payment_request(appointment)

        if can_send:
            # Check workspace auto-send settings (appointment can override workspace default)
            should_auto_send = (
                appointment.payment_auto_send
                if appointment.payment_auto_send is not None
                else appointment.workspace.payment_auto_send
            )

            if should_auto_send:
                # PHASE 0 STUB: Just log that payment request would be triggered
                # PHASE 1 TODO: Replace this with actual payment request creation
                logger.info(
                    "payment_request_would_be_sent",
                    appointment_id=str(appointment.id),
                    workspace_id=str(appointment.workspace_id),
                    payment_price=str(appointment.payment_price),
                    payment_provider=appointment.workspace.payment_provider,
                    send_timing=appointment.workspace.payment_send_timing,
                    extra={"structured": True, "phase": "phase_0_stub"},
                )
                # TODO PHASE 1: Implement payment request creation
                # await create_payment_request(appointment)
            else:
                logger.debug(
                    "payment_auto_send_disabled",
                    appointment_id=str(appointment.id),
                    workspace_id=str(appointment.workspace_id),
                    extra={"structured": True},
                )
        else:
            # Log why payment request cannot be sent
            logger.debug(
                "payment_request_cannot_be_sent",
                appointment_id=str(appointment.id),
                workspace_id=str(appointment.workspace_id),
                reason=reason,
                extra={"structured": True},
            )
    # ============================================================================
    # END PHASE 0 STUB
    # ============================================================================

    # Enqueue Google Calendar sync task (non-blocking)
    # Only sync if there were actual changes
    if changes:
        try:
            await arq_pool.enqueue_job(
                "sync_appointment_to_google_calendar",
                appointment_id=str(appointment.id),
                action="update",
                _queue_name=QUEUE_NAME,
            )
            logger.debug(
                "google_calendar_sync_task_enqueued",
                appointment_id=str(appointment.id),
                action="update",
            )
        except Exception as e:
            # Log error but don't fail appointment update
            logger.error(
                "google_calendar_sync_enqueue_failed",
                appointment_id=str(appointment.id),
                action="update",
                error=str(e),
                exc_info=True,
            )

    # Build response with client summary
    return build_appointment_response_with_client(appointment)


@router.delete("/{appointment_id}", status_code=204)
async def delete_appointment(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
    deletion_request: AppointmentDeleteRequest | None = Body(None),
) -> None:
    """
    Delete an appointment with optional session note handling.

    Permanently deletes an appointment. If appointment has attached session notes,
    you can choose to:
    - soft delete them (30-day grace period for restoration)
    - keep them unchanged (default)

    SOFT DELETE: Session notes are soft-deleted with 30-day grace period.
    After 30 days, they will be permanently purged by a background job.

    VALIDATION: Cannot delete session notes that have been amended (amendment_count > 0)
    due to medical-legal significance.

    SECURITY: Verifies workspace ownership before allowing deletion.
    workspace_id is derived from JWT token (server-side).

    AUDIT: Comprehensive audit logging includes:
    - Appointment status at deletion
    - Whether session note existed and action taken
    - Optional deletion reasons (appointment and session)
    - Client/service context for forensic review

    Args:
        appointment_id: UUID of the appointment to delete
        deletion_request: Optional deletion reason and session note action
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        No content (204) on success

    Raises:
        HTTPException: 401 if not authenticated,
            404 if not found or wrong workspace,
            422 if trying to delete amended session notes

    Example:
        DELETE /api/v1/appointments/{uuid}
        {
          "reason": "Duplicate entry - scheduled twice by mistake",
          "session_note_action": "delete",
          "deletion_reason": "Incorrect session data, will recreate"
        }
    """
    workspace_id = current_user.workspace_id

    # Fetch existing appointment with workspace scoping (raises 404 if not found)
    # Load client relationship for audit logging
    query = (
        select(Appointment)
        .where(
            Appointment.id == appointment_id,
            Appointment.workspace_id == workspace_id,
        )
        .options(selectinload(Appointment.client))
    )
    result = await db.execute(query)
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(status_code=404, detail="Resource not found")

    # Check if session note(s) exist using centralized helper
    # Get ALL sessions (not just first) to handle edge case of multiple sessions
    sessions = await get_active_sessions_for_appointment(db, appointment_id)
    had_session_note = len(sessions) > 0

    # Log warning if multiple sessions found (edge case that shouldn't happen)
    if len(sessions) > 1:
        logger.warning(
            "multiple_sessions_on_appointment",
            appointment_id=str(appointment_id),
            session_count=len(sessions),
            workspace_id=str(workspace_id),
            session_ids=[str(s.id) for s in sessions],
            extra={"structured": True},
        )

    # Gather deletion context
    appointment_deletion_reason = deletion_request.reason if deletion_request else None
    session_note_action = (
        deletion_request.session_note_action if deletion_request else None
    )
    session_deletion_reason = (
        deletion_request.deletion_reason if deletion_request else None
    )

    # Handle session note deletion if requested
    session_was_soft_deleted = False
    if had_session_note and session_note_action == "delete":
        # Validate: cannot delete amended notes (medical-legal significance)
        # Check ALL sessions - if ANY has been amended, block deletion using utility
        for session in sessions:
            validate_session_not_amended(session)

        # Soft delete ALL sessions using utility function
        for session in sessions:
            apply_soft_delete(
                session=session,
                deleted_by_user_id=current_user.id,
                deletion_reason=session_deletion_reason,
            )

            # Create audit log for each session soft delete
            await create_audit_event(
                db=db,
                user_id=current_user.id,
                workspace_id=workspace_id,
                action=AuditAction.DELETE,
                resource_type=ResourceType.SESSION,
                resource_id=session.id,
                metadata={
                    "soft_delete": True,
                    "deleted_with_appointment": True,
                    "appointment_id": str(appointment_id),
                    "permanent_delete_after": (
                        session.permanent_delete_after.isoformat()
                    ),
                    "deleted_reason": session_deletion_reason,
                    "was_finalized": session.finalized_at is not None,
                },
            )

            logger.info(
                "session_soft_deleted_with_appointment",
                session_id=str(session.id),
                appointment_id=str(appointment_id),
                workspace_id=str(workspace_id),
                permanent_delete_after=session.permanent_delete_after.isoformat(),
            )

        session_was_soft_deleted = True

    # Create comprehensive audit log entry for appointment deletion
    await create_audit_event(
        db=db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        action=AuditAction.DELETE,
        resource_type=ResourceType.APPOINTMENT,
        resource_id=appointment_id,
        metadata={
            "appointment_status": appointment.status.value,
            "had_session_note": had_session_note,
            "session_note_action": session_note_action or "keep",
            "session_was_soft_deleted": session_was_soft_deleted,
            "scheduled_start": appointment.scheduled_start.isoformat(),
            "scheduled_end": appointment.scheduled_end.isoformat(),
            "location_type": appointment.location_type.value,
            "deletion_provided": appointment_deletion_reason is not None,
        },
    )

    # Enqueue Google Calendar sync task BEFORE deleting appointment
    # Pass google_event_id and workspace_id since appointment will be deleted
    if appointment.google_event_id:
        try:
            await arq_pool.enqueue_job(
                "sync_appointment_to_google_calendar",
                appointment_id=str(appointment.id),
                action="delete",
                google_event_id=appointment.google_event_id,
                workspace_id=str(workspace_id),
                _queue_name=QUEUE_NAME,
            )
            logger.debug(
                "google_calendar_sync_task_enqueued",
                appointment_id=str(appointment.id),
                action="delete",
                google_event_id=appointment.google_event_id,
            )
        except Exception as e:
            # Log error but don't fail appointment deletion
            logger.error(
                "google_calendar_sync_enqueue_failed",
                appointment_id=str(appointment.id),
                action="delete",
                error=str(e),
                exc_info=True,
            )

    # Delete appointment (CASCADE will NOT delete soft-deleted sessions since
    # appointment_id is SET NULL on delete, not CASCADE)
    # If session was soft-deleted, it stays in DB but unlinked from appointment
    # If action was "keep" (or not specified), sessions stay active and linked
    if had_session_note and session_note_action != "delete":
        # Unlink ALL sessions from appointment (SET NULL) but keep them active
        for session in sessions:
            session.appointment_id = None

    await db.delete(appointment)
    await db.commit()

    logger.info(
        "appointment_deleted",
        appointment_id=str(appointment_id),
        workspace_id=str(workspace_id),
        status=appointment.status.value,
        had_session_note=had_session_note,
        session_note_action=session_note_action or "keep",
        session_was_soft_deleted=session_was_soft_deleted,
        deletion_reason_provided=appointment_deletion_reason is not None,
    )


@router.patch("/{appointment_id}/payment", response_model=AppointmentResponse)
async def update_appointment_payment(
    appointment_id: uuid.UUID,
    payment_update: AppointmentPaymentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    """
    Update payment status for an appointment (Phase 1: Manual payment tracking).

    This endpoint allows therapists to manually mark appointments as paid/unpaid
    and update payment details (method, price, notes).

    **Phase 1 Behavior:**
    - Manual payment tracking only (no automated payment processing)
    - Therapist manually marks appointments as paid/unpaid
    - Auto-sets paid_at timestamp when marking as paid
    - Uses simplified PaymentService methods

    **Workspace Scoping:**
    - Automatically scoped to authenticated user's workspace
    - workspace_id derived from JWT token (server-side, trusted)

    **Audit Logging:**
    - Payment status changes are logged to audit trail
    - Includes old and new payment status for reconciliation

    Args:
        appointment_id: UUID of the appointment to update
        payment_update: Payment status update data
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        AppointmentResponse with updated payment details

    Raises:
        HTTPException: 401 if not authenticated, 404 if appointment not found

    Example Request:
        ```json
        {
            "payment_status": "paid",
            "payment_method": "bit",
            "payment_price": 150.00,
            "payment_notes": "Paid via Bit app"
        }
        ```

    Example Response:
        ```json
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "payment_status": "paid",
            "payment_method": "bit",
            "payment_price": 150.00,
            "payment_notes": "Paid via Bit app",
            "paid_at": "2025-11-02T10:00:00Z",
            ...
        }
        ```
    """
    workspace_id = current_user.workspace_id

    logger.info(
        "appointment_payment_update_requested",
        appointment_id=str(appointment_id),
        workspace_id=str(workspace_id),
        user_id=str(current_user.id),
        payment_status=payment_update.payment_status,
    )

    # Fetch existing appointment with workspace scoping (raises 404 if not found)
    # Load client relationship for response
    query = (
        select(Appointment)
        .where(
            Appointment.id == appointment_id,
            Appointment.workspace_id == workspace_id,
        )
        .options(selectinload(Appointment.client))
    )
    result = await db.execute(query)
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(status_code=404, detail="Resource not found")

    # Store old payment status for audit logging
    old_payment_status = appointment.payment_status

    # Use PaymentService to update payment fields
    service = PaymentService(db)

    # Update payment status using service methods
    if payment_update.payment_status == "paid":
        # Mark as paid (will auto-set paid_at if not provided)
        # payment_method is required when marking as paid
        if not payment_update.payment_method:
            raise HTTPException(
                status_code=400,
                detail="payment_method is required when marking appointment as paid",
            )
        await service.mark_as_paid(
            appointment=appointment,
            payment_method=payment_update.payment_method,
            notes=payment_update.payment_notes,
            paid_at=payment_update.paid_at,
        )
    elif payment_update.payment_status == "not_paid":
        # Mark as unpaid (will clear paid_at)
        await service.mark_as_unpaid(appointment=appointment)
    else:
        # For payment_sent or waived, update status directly
        appointment.payment_status = payment_update.payment_status
        if payment_update.payment_method:
            appointment.payment_method = payment_update.payment_method

    # Update price if provided
    if payment_update.payment_price is not None:
        await service.update_payment_price(
            appointment=appointment,
            price=payment_update.payment_price,
        )

    # Update payment notes if provided (if not already set by mark_as_paid)
    if (
        payment_update.payment_notes is not None
        and payment_update.payment_status != "paid"
    ):
        appointment.payment_notes = payment_update.payment_notes

    # Commit changes
    await db.commit()
    await db.refresh(appointment)

    # Audit log the payment status change
    await create_audit_event(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        resource_type=ResourceType.APPOINTMENT,
        resource_id=appointment_id,
        action=AuditAction.UPDATE,
        metadata={
            "old_payment_status": old_payment_status,
            "new_payment_status": appointment.payment_status,
            "payment_method": appointment.payment_method,
            "payment_price": str(appointment.payment_price)
            if appointment.payment_price
            else None,
            "paid_at": appointment.paid_at.isoformat() if appointment.paid_at else None,
        },
    )

    logger.info(
        "appointment_payment_updated",
        appointment_id=str(appointment_id),
        workspace_id=str(workspace_id),
        old_payment_status=old_payment_status,
        new_payment_status=appointment.payment_status,
        payment_method=appointment.payment_method,
    )

    # Return response with client information
    return build_appointment_response_with_client(appointment)


@router.get("/{appointment_id}/payment-link", response_model=PaymentLinkResponse)
async def get_payment_link(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentLinkResponse:
    """
    Preview or regenerate payment link without sending email.

    Generates a payment link for the appointment based on workspace configuration.
    This endpoint does NOT send an email or change appointment status.

    **Use Cases:**
    - Preview payment link before sending
    - Regenerate payment link for manual sharing
    - Test payment link generation

    **Validation:**
    - Appointment must belong to authenticated user's workspace
    - Appointment must have a price set
    - Workspace must have payment links configured

    **Workspace Scoping:**
    - Automatically scoped to authenticated user's workspace
    - workspace_id derived from JWT token (server-side, trusted)

    Args:
        appointment_id: UUID of the appointment
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        PaymentLinkResponse with payment link details

    Raises:
        HTTPException: 401 if not authenticated,
            404 if appointment not found or wrong workspace,
            400 if no price set or payment links not configured
    """
    workspace_id = current_user.workspace_id

    logger.info(
        "payment_link_preview_requested",
        appointment_id=str(appointment_id),
        workspace_id=str(workspace_id),
        user_id=str(current_user.id),
    )

    # Fetch appointment with workspace scoping and relationships
    query = (
        select(Appointment)
        .where(
            Appointment.id == appointment_id,
            Appointment.workspace_id == workspace_id,
        )
        .options(
            selectinload(Appointment.workspace),
            selectinload(Appointment.client),
        )
    )
    result = await db.execute(query)
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(status_code=404, detail="Resource not found")

    # Validate appointment has a price
    if not appointment.payment_price or appointment.payment_price <= 0:
        raise HTTPException(
            status_code=400,
            detail="Appointment must have a price set to generate payment link",
        )

    # Validate workspace has payment links configured
    if not appointment.workspace.payment_link_template:
        raise HTTPException(
            status_code=400,
            detail="Payment links not configured for this workspace. Configure payment links in Settings > Payments.",
        )

    # Generate payment link
    payment_link = generate_payment_link(appointment.workspace, appointment)

    if not payment_link:
        logger.error(
            "payment_link_generation_failed",
            appointment_id=str(appointment_id),
            workspace_id=str(workspace_id),
            payment_link_type=appointment.workspace.payment_link_type,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to generate payment link. Please check your payment configuration.",
        )

    # Get display text for payment method
    display_text = get_payment_link_display_text(appointment.workspace)

    logger.info(
        "payment_link_generated",
        appointment_id=str(appointment_id),
        workspace_id=str(workspace_id),
        payment_link_type=appointment.workspace.payment_link_type,
    )

    return PaymentLinkResponse(
        payment_link=payment_link,
        payment_type=appointment.workspace.payment_link_type or "unknown",
        amount=appointment.payment_price,
        display_text=display_text,
    )


@router.post(
    "/{appointment_id}/send-payment-request",
    response_model=SendPaymentRequestResponse,
)
async def send_payment_request(
    appointment_id: uuid.UUID,
    request_body: SendPaymentRequestBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SendPaymentRequestResponse:
    """
    Send payment request to client via email.

    Generates a payment link and sends it to the client via email.
    Updates appointment payment_status from 'not_paid' to 'payment_sent'.

    **Workflow:**
    1. Validate appointment and workspace configuration
    2. Generate payment link
    3. Send email to client with payment link (Step 7 will implement email service)
    4. Update payment_status to 'payment_sent' if currently 'not_paid'
    5. Create audit log entry

    **Validation:**
    - Appointment must belong to authenticated user's workspace
    - Appointment must have a price set
    - Workspace must have payment links configured
    - Client must have an email address

    **Workspace Scoping:**
    - Automatically scoped to authenticated user's workspace
    - workspace_id derived from JWT token (server-side, trusted)

    **Audit Logging:**
    - Logs payment request sent event with amount, client_id, payment_type

    Args:
        appointment_id: UUID of the appointment
        request_body: Optional custom message to include in email
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        SendPaymentRequestResponse with success status and payment link

    Raises:
        HTTPException: 401 if not authenticated,
            404 if appointment not found or wrong workspace,
            400 if no price, no email, or payment links not configured
    """
    workspace_id = current_user.workspace_id

    logger.info(
        "payment_request_send_started",
        appointment_id=str(appointment_id),
        workspace_id=str(workspace_id),
        user_id=str(current_user.id),
    )

    # Fetch appointment with workspace scoping and relationships
    query = (
        select(Appointment)
        .where(
            Appointment.id == appointment_id,
            Appointment.workspace_id == workspace_id,
        )
        .options(
            selectinload(Appointment.workspace),
            selectinload(Appointment.client),
        )
    )
    result = await db.execute(query)
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(status_code=404, detail="Resource not found")

    # Validate appointment has a price
    if not appointment.payment_price or appointment.payment_price <= 0:
        raise HTTPException(
            status_code=400,
            detail="Appointment must have a price set to send payment request",
        )

    # Validate workspace has payment links configured
    if not appointment.workspace.payment_link_template:
        raise HTTPException(
            status_code=400,
            detail="Payment links not configured for this workspace. Configure payment links in Settings > Payments.",
        )

    # Validate client has email address
    if not appointment.client or not appointment.client.email:
        raise HTTPException(
            status_code=400,
            detail="Client must have an email address to receive payment request",
        )

    # Generate payment link
    payment_link = generate_payment_link(appointment.workspace, appointment)

    if not payment_link:
        logger.error(
            "payment_link_generation_failed",
            appointment_id=str(appointment_id),
            workspace_id=str(workspace_id),
            payment_link_type=appointment.workspace.payment_link_type,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to generate payment link. Please check your payment configuration.",
        )

    # Send payment request email to client
    from pazpaz.services.email_service import send_payment_request_email

    # Note: appointment.client.email is already decrypted by EncryptedString type
    # No need to call decrypt_field() manually
    client_email = appointment.client.email

    try:
        await send_payment_request_email(
            appointment=appointment,
            workspace=appointment.workspace,
            payment_link=payment_link,
            client_email=client_email,
        )
        logger.info(
            "payment_request_email_sent_successfully",
            appointment_id=str(appointment_id),
            workspace_id=str(workspace_id),
            client_email_hash=hash(client_email),
            payment_amount=str(appointment.payment_price),
            payment_link_type=appointment.workspace.payment_link_type,
        )
    except Exception as e:
        # Log error but don't fail the request - payment link was generated
        logger.error(
            "payment_request_email_failed",
            appointment_id=str(appointment_id),
            workspace_id=str(workspace_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to send payment request email. Please try again or send the payment link manually.",
        )

    # Update payment_status to 'payment_sent' if currently 'not_paid'
    old_payment_status = appointment.payment_status
    if appointment.payment_status == "not_paid":
        appointment.payment_status = "payment_sent"
        await db.commit()
        await db.refresh(appointment)

        logger.info(
            "payment_status_updated",
            appointment_id=str(appointment_id),
            workspace_id=str(workspace_id),
            old_status=old_payment_status,
            new_status=appointment.payment_status,
        )

    # Create audit log entry
    await create_audit_event(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        resource_type=ResourceType.APPOINTMENT,
        resource_id=appointment_id,
        action=AuditAction.UPDATE,
        metadata={
            "action": "payment_request_sent",
            "amount": str(appointment.payment_price),
            "client_id": str(appointment.client.id),
            "payment_type": appointment.workspace.payment_link_type,
            "old_payment_status": old_payment_status,
            "new_payment_status": appointment.payment_status,
        },
    )

    logger.info(
        "payment_request_sent",
        appointment_id=str(appointment_id),
        workspace_id=str(workspace_id),
        client_id=str(appointment.client.id),
        payment_amount=str(appointment.payment_price),
        payment_link_type=appointment.workspace.payment_link_type,
    )

    return SendPaymentRequestResponse(
        success=True,
        payment_link=payment_link,
        message=f"Payment request sent to {appointment.client.full_name}",
    )
