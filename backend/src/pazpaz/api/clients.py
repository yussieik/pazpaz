"""Client CRUD API endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.api.deps import get_current_user, get_db, get_or_404
from pazpaz.core.logging import get_logger
from pazpaz.models.appointment import Appointment, AppointmentStatus
from pazpaz.models.client import Client
from pazpaz.models.user import User
from pazpaz.schemas.client import (
    ClientCreate,
    ClientListResponse,
    ClientResponse,
    ClientUpdate,
)
from pazpaz.utils.pagination import (
    calculate_pagination_offset,
    calculate_total_pages,
    get_query_total_count,
    validate_pagination_params,
)

router = APIRouter(prefix="/clients", tags=["clients"])
logger = get_logger(__name__)


async def enrich_client_response(
    db: AsyncSession,
    client: Client,
) -> ClientResponse:
    """
    Enrich client response with computed appointment fields.

    Efficiently fetches:
    - next_appointment: Next scheduled appointment after now
    - last_appointment: Most recent completed appointment
    - appointment_count: Total appointments for this client

    Uses 3 optimized queries with proper indexes.

    Args:
        db: Database session
        client: Client model instance

    Returns:
        ClientResponse with computed appointment fields
    """
    # Query 1: Get next scheduled appointment
    next_apt_query = (
        select(Appointment.scheduled_start)
        .where(
            Appointment.workspace_id == client.workspace_id,
            Appointment.client_id == client.id,
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.scheduled_start > datetime.now(UTC),
        )
        .order_by(Appointment.scheduled_start.asc())
        .limit(1)
    )
    next_result = await db.execute(next_apt_query)
    next_appointment = next_result.scalar_one_or_none()

    # Query 2: Get last completed appointment
    last_apt_query = (
        select(Appointment.scheduled_start)
        .where(
            Appointment.workspace_id == client.workspace_id,
            Appointment.client_id == client.id,
            Appointment.status == AppointmentStatus.COMPLETED,
        )
        .order_by(Appointment.scheduled_start.desc())
        .limit(1)
    )
    last_result = await db.execute(last_apt_query)
    last_appointment = last_result.scalar_one_or_none()

    # Query 3: Get total appointment count
    count_query = select(func.count(Appointment.id)).where(
        Appointment.workspace_id == client.workspace_id,
        Appointment.client_id == client.id,
    )
    count_result = await db.execute(count_query)
    appointment_count = count_result.scalar_one()

    # Build response
    response = ClientResponse.model_validate(client)
    response.next_appointment = next_appointment
    response.last_appointment = last_appointment
    response.appointment_count = appointment_count

    return response


@router.post("", response_model=ClientResponse, status_code=201)
async def create_client(
    client_data: ClientCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Client:
    """
    Create a new client.

    Creates a new client record in the authenticated workspace.
    All client data is scoped to the workspace.

    SECURITY: workspace_id is derived from authenticated user's JWT token (server-side).

    Args:
        client_data: Client creation data (without workspace_id)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Created client with all fields

    Raises:
        HTTPException: 401 if not authenticated, 422 if validation fails
    """
    workspace_id = current_user.workspace_id
    logger.info("client_create_started", workspace_id=str(workspace_id))

    # Create new client instance with injected workspace_id
    # Convert date_of_birth from date object to ISO string for encrypted storage
    dob_str = (
        client_data.date_of_birth.isoformat() if client_data.date_of_birth else None
    )

    client = Client(
        workspace_id=workspace_id,
        first_name=client_data.first_name,
        last_name=client_data.last_name,
        email=client_data.email,
        phone=client_data.phone,
        date_of_birth=dob_str,
        address=client_data.address,
        medical_history=client_data.medical_history,
        emergency_contact_name=client_data.emergency_contact_name,
        emergency_contact_phone=client_data.emergency_contact_phone,
        is_active=client_data.is_active,
        consent_status=client_data.consent_status,
        notes=client_data.notes,
        tags=client_data.tags,
    )

    db.add(client)
    await db.commit()
    await db.refresh(client)

    logger.info(
        "client_created",
        client_id=str(client.id),
        workspace_id=str(workspace_id),
    )

    # Enrich with computed fields before returning
    return await enrich_client_response(db, client)


@router.get("", response_model=ClientListResponse)
async def list_clients(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    include_inactive: bool = Query(
        False, description="Include archived/inactive clients"
    ),
    include_appointments: bool = Query(
        False, description="Include appointment stats (slower)"
    ),
) -> ClientListResponse:
    """
    List all clients in the workspace.

    Returns a paginated list of clients, ordered by last name, first name.
    All results are scoped to the authenticated workspace.

    By default, only active clients are returned. Use include_inactive=true
    to see archived clients as well.

    SECURITY: Only returns clients belonging to the authenticated user's
    workspace (from JWT).

    Args:
        current_user: Authenticated user (from JWT token)
        db: Database session
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        include_inactive: If True, include archived/inactive clients
        include_appointments: If True, include appointment stats
            (adds 3 queries per client)

    Returns:
        Paginated list of clients with total count

    Raises:
        HTTPException: 401 if not authenticated
    """
    workspace_id = current_user.workspace_id
    logger.debug(
        "client_list_started",
        workspace_id=str(workspace_id),
        page=page,
        page_size=page_size,
        include_inactive=include_inactive,
        include_appointments=include_appointments,
    )

    # SECURITY: Validate pagination parameters to prevent integer overflow
    # This prevents database crashes from values like page=2**128
    validate_pagination_params(page, page_size)

    # Calculate offset using utility
    offset = calculate_pagination_offset(page, page_size)

    # Build base query with workspace scoping
    base_query = select(Client).where(Client.workspace_id == workspace_id)

    # Filter active clients by default
    if not include_inactive:
        base_query = base_query.where(Client.is_active == True)  # noqa: E712

    # Get total count using utility
    total = await get_query_total_count(db, base_query)

    # IMPORTANT: Cannot sort encrypted fields in database
    # Must fetch all records and sort in Python after decryption
    result = await db.execute(base_query)
    all_clients = result.scalars().all()

    # Sort clients by decrypted last_name, first_name
    # SQLAlchemy decrypts automatically when accessing attributes
    sorted_clients = sorted(
        all_clients,
        key=lambda c: (c.last_name.lower(), c.first_name.lower())
    )

    # Apply pagination to sorted list
    paginated_clients = sorted_clients[offset : offset + page_size]

    # Calculate total pages using utility
    total_pages = calculate_total_pages(total, page_size)

    # Conditionally enrich with appointment data
    if include_appointments:
        items = [await enrich_client_response(db, client) for client in paginated_clients]
    else:
        # Just return basic client data (fast)
        items = [ClientResponse.model_validate(client) for client in paginated_clients]

    logger.debug(
        "client_list_completed",
        workspace_id=str(workspace_id),
        total_clients=total,
        page=page,
    )

    return ClientListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    """
    Get a single client by ID with computed appointment fields.

    Retrieves a client by ID, ensuring it belongs to the authenticated workspace.
    Includes computed fields: next_appointment, last_appointment, appointment_count.

    SECURITY: Returns 404 for both non-existent clients and clients in other
    workspaces to prevent information leakage. workspace_id is derived from
    JWT token (server-side).

    PHI ACCESS: This endpoint accesses Protected Health Information (PHI).
    All access is automatically logged by AuditMiddleware for HIPAA compliance.

    Args:
        client_id: UUID of the client
        request: FastAPI request object
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Client details with computed appointment fields

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace
    """
    workspace_id = current_user.workspace_id
    # Use helper function for workspace-scoped fetch with generic error
    client = await get_or_404(db, Client, client_id, workspace_id)

    # Enrich with computed fields
    # Note: PHI access is automatically logged by AuditMiddleware
    return await enrich_client_response(db, client)


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: uuid.UUID,
    client_data: ClientUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClientResponse:
    """
    Update an existing client.

    Updates client fields. Only provided fields are updated.
    Client must belong to the authenticated workspace.

    SECURITY: Verifies workspace ownership before allowing updates.
    workspace_id is derived from JWT token (server-side).

    Args:
        client_id: UUID of the client to update
        client_data: Fields to update
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Updated client with computed appointment fields

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
            422 if validation fails
    """
    workspace_id = current_user.workspace_id
    # Fetch existing client with workspace scoping (raises 404 if not found)
    client = await get_or_404(db, Client, client_id, workspace_id)

    # Convert date_of_birth from date object to ISO string if present
    update_dict = client_data.model_dump(exclude_unset=True)
    if "date_of_birth" in update_dict and update_dict["date_of_birth"] is not None:
        update_dict["date_of_birth"] = update_dict["date_of_birth"].isoformat()

    # Apply updates to entity
    for field, value in update_dict.items():
        setattr(client, field, value)

    update_data = update_dict

    await db.commit()
    await db.refresh(client)

    logger.info(
        "client_updated",
        client_id=str(client_id),
        workspace_id=str(workspace_id),
        updated_fields=list(update_data.keys()),
    )

    # Enrich with computed fields before returning
    return await enrich_client_response(db, client)


@router.delete("/{client_id}", status_code=204)
async def delete_client(
    client_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Soft delete a client by marking as inactive.

    CHANGED: This now performs a soft delete (is_active = false) instead of
    hard delete to preserve audit trail and appointment history.

    Client must belong to the authenticated workspace. The client will no longer
    appear in default list views but can be retrieved with include_inactive=true.

    SECURITY: Verifies workspace ownership before allowing deletion.
    workspace_id is derived from JWT token (server-side).

    Args:
        client_id: UUID of the client to delete
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        No content (204) on success

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace
    """
    workspace_id = current_user.workspace_id
    # Fetch existing client with workspace scoping (raises 404 if not found)
    client = await get_or_404(db, Client, client_id, workspace_id)

    # Soft delete: mark as inactive
    client.is_active = False
    await db.commit()

    logger.info(
        "client_soft_deleted",
        client_id=str(client_id),
        workspace_id=str(workspace_id),
    )
