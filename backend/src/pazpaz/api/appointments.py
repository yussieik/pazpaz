"""Appointment CRUD API endpoints with conflict detection."""

from __future__ import annotations

import math
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pazpaz.api.deps import get_current_workspace_id, get_db, get_or_404
from pazpaz.core.logging import get_logger
from pazpaz.models.appointment import Appointment, AppointmentStatus
from pazpaz.models.client import Client
from pazpaz.schemas.appointment import (
    AppointmentCreate,
    AppointmentListResponse,
    AppointmentResponse,
    AppointmentUpdate,
    ClientSummary,
    ConflictCheckResponse,
)

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

    Conflict exists if appointments overlap:
    scheduled_start < requested_end AND scheduled_end > requested_start

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
        # Exclude CANCELLED and NO_SHOW from conflict check
        Appointment.status.not_in(
            [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]
        ),
    )

    # Exclude the appointment being updated
    if exclude_appointment_id:
        query = query.where(Appointment.id != exclude_appointment_id)

    # Execute query
    result = await db.execute(query)
    conflicts = result.scalars().all()

    return list(conflicts)


async def verify_client_in_workspace(
    db: AsyncSession,
    client_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> Client:
    """
    Verify that a client exists and belongs to the workspace.

    SECURITY: Returns generic 404 error to prevent information leakage.

    Args:
        db: Database session
        client_id: Client ID to verify
        workspace_id: Expected workspace ID

    Returns:
        Client instance

    Raises:
        HTTPException: 404 if client not found or belongs to different workspace
    """
    # Use generic helper for workspace-scoped fetch
    return await get_or_404(db, Client, client_id, workspace_id)


@router.post("", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    appointment_data: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> AppointmentResponse:
    """
    Create a new appointment with conflict detection.

    Creates a new appointment after verifying:
    1. Client belongs to the workspace
    2. No conflicting appointments exist in the time slot

    SECURITY: workspace_id is injected from authentication, not from request body.

    Args:
        appointment_data: Appointment creation data (without workspace_id)
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        Created appointment with client information

    Raises:
        HTTPException: 401 if not authenticated, 404 if client not found,
            409 if conflict exists, 422 if validation fails
    """
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
    response_data = AppointmentResponse.model_validate(appointment_with_client)
    if appointment_with_client.client:
        response_data.client = ClientSummary(
            id=appointment_with_client.client.id,
            first_name=appointment_with_client.client.first_name,
            last_name=appointment_with_client.client.last_name,
            full_name=appointment_with_client.client.full_name,
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
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> AppointmentListResponse:
    """
    List appointments in the workspace with optional filters.

    Returns a paginated list of appointments, ordered by scheduled_start descending.
    All results are scoped to the authenticated workspace.

    SECURITY: Only returns appointments belonging to the authenticated workspace.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        start_date: Filter appointments starting on or after this date
        end_date: Filter appointments starting on or before this date
        client_id: Filter by specific client
        status: Filter by appointment status
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        Paginated list of appointments with client information

    Raises:
        HTTPException: 401 if not authenticated
    """
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

    # Calculate offset
    offset = (page - 1) * page_size

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

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

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
    items = []
    for appointment in appointments:
        response_data = AppointmentResponse.model_validate(appointment)
        if appointment.client:
            response_data.client = ClientSummary(
                id=appointment.client.id,
                first_name=appointment.client.first_name,
                last_name=appointment.client.last_name,
                full_name=appointment.client.full_name,
            )
        items.append(response_data)

    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return AppointmentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/conflicts", response_model=ConflictCheckResponse)
async def check_appointment_conflicts(
    scheduled_start: datetime = Query(..., description="Start time to check"),
    scheduled_end: datetime = Query(..., description="End time to check"),
    exclude_appointment_id: uuid.UUID | None = Query(
        None,
        description="Appointment ID to exclude (for updates)",
    ),
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> ConflictCheckResponse:
    """
    Check for appointment conflicts in a time range.

    Used by frontend to validate appointment times before submission.

    SECURITY: Only checks conflicts within the authenticated workspace.

    Args:
        scheduled_start: Start time to check
        scheduled_end: End time to check
        exclude_appointment_id: Appointment to exclude (when updating)
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        Conflict check result with list of conflicting appointments

    Raises:
        HTTPException: 401 if not authenticated,
            422 if scheduled_end is not after scheduled_start
    """
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

    # Load client relationships for conflicts
    if conflicts:
        conflict_ids = [c.id for c in conflicts]
        query = (
            select(Appointment)
            .where(Appointment.id.in_(conflict_ids))
            .options(selectinload(Appointment.client))
        )
        result = await db.execute(query)
        conflicts_with_clients = result.scalars().all()

        # Build response items
        conflict_responses = []
        for appointment in conflicts_with_clients:
            response_data = AppointmentResponse.model_validate(appointment)
            if appointment.client:
                response_data.client = ClientSummary(
                    id=appointment.client.id,
                    first_name=appointment.client.first_name,
                    last_name=appointment.client.last_name,
                    full_name=appointment.client.full_name,
                )
            conflict_responses.append(response_data)
    else:
        conflict_responses = []

    return ConflictCheckResponse(
        has_conflict=len(conflicts) > 0,
        conflicting_appointments=conflict_responses,
    )


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> AppointmentResponse:
    """
    Get a single appointment by ID.

    Retrieves an appointment by ID, ensuring it belongs to the authenticated workspace.

    SECURITY: Returns 404 for both non-existent appointments and appointments
    in other workspaces to prevent information leakage.

    Args:
        appointment_id: UUID of the appointment
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        Appointment details with client information

    Raises:
        HTTPException: 401 if not authenticated,
            404 if not found or wrong workspace
    """
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
    response_data = AppointmentResponse.model_validate(appointment_with_client)
    if appointment_with_client.client:
        response_data.client = ClientSummary(
            id=appointment_with_client.client.id,
            first_name=appointment_with_client.client.first_name,
            last_name=appointment_with_client.client.last_name,
            full_name=appointment_with_client.client.full_name,
        )

    return response_data


@router.put("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: uuid.UUID,
    appointment_data: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> AppointmentResponse:
    """
    Update an existing appointment with conflict detection.

    Updates appointment fields. Only provided fields are updated.
    If time is changed, conflict detection is performed.
    Appointment must belong to the authenticated workspace.

    SECURITY: Verifies workspace ownership before allowing updates.

    Args:
        appointment_id: UUID of the appointment to update
        appointment_data: Fields to update
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        Updated appointment with client information

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
            409 if conflict, 422 if validation fails
    """
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

    # Determine final scheduled times for conflict check
    final_start = update_data.get("scheduled_start", appointment.scheduled_start)
    final_end = update_data.get("scheduled_end", appointment.scheduled_end)

    # Validate end is after start
    if final_end <= final_start:
        raise HTTPException(
            status_code=422,
            detail="scheduled_end must be after scheduled_start",
        )

    # Check for conflicts if time changed
    time_changed = "scheduled_start" in update_data or "scheduled_end" in update_data
    if time_changed:
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

    # Update fields
    for field, value in update_data.items():
        setattr(appointment, field, value)

    await db.commit()
    await db.refresh(appointment)

    # Reload with client relationship
    query = (
        select(Appointment)
        .where(Appointment.id == appointment.id)
        .options(selectinload(Appointment.client))
    )
    result = await db.execute(query)
    appointment = result.scalar_one()

    # Build response with client summary
    response_data = AppointmentResponse.model_validate(appointment)
    if appointment.client:
        response_data.client = ClientSummary(
            id=appointment.client.id,
            first_name=appointment.client.first_name,
            last_name=appointment.client.last_name,
            full_name=appointment.client.full_name,
        )

    return response_data


@router.delete("/{appointment_id}", status_code=204)
async def delete_appointment(
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> None:
    """
    Delete an appointment.

    Permanently deletes an appointment and associated data (sessions, etc.)
    due to CASCADE delete. Appointment must belong to the authenticated workspace.

    SECURITY: Verifies workspace ownership before allowing deletion.

    Args:
        appointment_id: UUID of the appointment to delete
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        No content (204) on success

    Raises:
        HTTPException: 401 if not authenticated,
            404 if not found or wrong workspace
    """
    # Fetch existing appointment with workspace scoping (raises 404 if not found)
    appointment = await get_or_404(db, Appointment, appointment_id, workspace_id)

    await db.delete(appointment)
    await db.commit()

    logger.info(
        "appointment_deleted",
        appointment_id=str(appointment_id),
        workspace_id=str(workspace_id),
    )
