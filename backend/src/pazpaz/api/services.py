"""Service CRUD API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.api.deps import get_current_user, get_db, get_or_404
from pazpaz.core.logging import get_logger
from pazpaz.models.appointment import Appointment
from pazpaz.models.service import Service
from pazpaz.models.user import User
from pazpaz.schemas.service import (
    ServiceCreate,
    ServiceListResponse,
    ServiceResponse,
    ServiceUpdate,
)
from pazpaz.utils.crud_helpers import (
    apply_partial_update,
    check_unique_name_in_workspace,
    soft_delete_with_fk_check,
)
from pazpaz.utils.pagination import (
    calculate_pagination_offset,
    calculate_total_pages,
    get_query_total_count,
)

router = APIRouter(prefix="/services", tags=["services"])
logger = get_logger(__name__)


@router.post("", response_model=ServiceResponse, status_code=201)
async def create_service(
    service_data: ServiceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Service:
    """
    Create a new service.

    Creates a new service record in the authenticated workspace.
    All service data is scoped to the workspace.

    SECURITY: workspace_id is derived from authenticated user's JWT token (server-side).

    Args:
        service_data: Service creation data (without workspace_id)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Created service with all fields

    Raises:
        HTTPException: 401 if not authenticated, 422 if validation fails,
            409 if service name already exists in workspace
    """
    workspace_id = current_user.workspace_id
    logger.info("service_create_started", workspace_id=str(workspace_id))

    # Check if service name already exists in workspace
    await check_unique_name_in_workspace(
        db, Service, workspace_id, service_data.name
    )

    # Create new service instance with injected workspace_id
    service = Service(
        workspace_id=workspace_id,
        name=service_data.name,
        description=service_data.description,
        default_duration_minutes=service_data.default_duration_minutes,
        is_active=service_data.is_active,
    )

    db.add(service)
    await db.commit()
    await db.refresh(service)

    logger.info(
        "service_created",
        service_id=str(service.id),
        workspace_id=str(workspace_id),
        service_name=service_data.name,
    )
    return service


@router.get("", response_model=ServiceListResponse)
async def list_services(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    is_active: bool | None = Query(
        True, description="Filter by active status (default: true)"
    ),
) -> ServiceListResponse:
    """
    List all services in the workspace.

    Returns a paginated list of services, ordered by name.
    All results are scoped to the authenticated workspace.

    SECURITY: Only returns services belonging to the authenticated user's
    workspace (from JWT).

    Args:
        current_user: Authenticated user (from JWT token)
        db: Database session
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        is_active: Filter by active status (default: true, None = all)

    Returns:
        Paginated list of services with total count

    Raises:
        HTTPException: 401 if not authenticated
    """
    workspace_id = current_user.workspace_id
    logger.debug(
        "service_list_started",
        workspace_id=str(workspace_id),
        page=page,
        page_size=page_size,
        is_active=is_active,
    )

    # Calculate offset using utility
    offset = calculate_pagination_offset(page, page_size)

    # Build base query with workspace scoping
    base_query = select(Service).where(Service.workspace_id == workspace_id)

    # Apply is_active filter if specified
    if is_active is not None:
        base_query = base_query.where(Service.is_active == is_active)

    # Get total count using utility
    total = await get_query_total_count(db, base_query)

    # Get paginated results ordered by name
    query = base_query.order_by(Service.name).offset(offset).limit(page_size)
    result = await db.execute(query)
    services = result.scalars().all()

    # Calculate total pages using utility
    total_pages = calculate_total_pages(total, page_size)

    logger.debug(
        "service_list_completed",
        workspace_id=str(workspace_id),
        total_services=total,
        page=page,
    )

    return ServiceListResponse(
        items=services,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{service_id}", response_model=ServiceResponse)
async def get_service(
    service_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Service:
    """
    Get a single service by ID.

    Retrieves a service by ID, ensuring it belongs to the authenticated workspace.

    SECURITY: Returns 404 for non-existent services and services in
    other workspaces to prevent information leakage. workspace_id is derived
    from JWT token.

    Args:
        service_id: UUID of the service
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Service details

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace
    """
    workspace_id = current_user.workspace_id
    # Use helper function for workspace-scoped fetch with generic error
    service = await get_or_404(db, Service, service_id, workspace_id)
    return service


@router.put("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: uuid.UUID,
    service_data: ServiceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Service:
    """
    Update an existing service.

    Updates service fields. Only provided fields are updated.
    Service must belong to the authenticated workspace.

    SECURITY: Verifies workspace ownership before allowing updates.
    workspace_id is derived from JWT token (server-side).

    Args:
        service_id: UUID of the service to update
        service_data: Fields to update
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Updated service

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
            409 if name conflicts with existing service, 422 if validation fails
    """
    workspace_id = current_user.workspace_id
    # Fetch existing service with workspace scoping (raises 404 if not found)
    service = await get_or_404(db, Service, service_id, workspace_id)

    # Apply partial update and get updated fields
    update_data = apply_partial_update(service, service_data)

    # Check for name conflicts if name is being updated
    if "name" in update_data and update_data["name"] != service.name:
        await check_unique_name_in_workspace(
            db, Service, workspace_id, update_data["name"], exclude_id=service_id
        )

    await db.commit()
    await db.refresh(service)

    logger.info(
        "service_updated",
        service_id=str(service_id),
        workspace_id=str(workspace_id),
        updated_fields=list(update_data.keys()),
    )
    return service


@router.delete("/{service_id}", status_code=204)
async def delete_service(
    service_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a service.

    Soft deletes a service by setting is_active=False if referenced by
    appointments.
    Hard deletes if no appointments reference it.
    Service must belong to the authenticated workspace.

    SECURITY: Verifies workspace ownership before allowing deletion.
    workspace_id is derived from JWT token (server-side).

    Args:
        service_id: UUID of the service to delete
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        No content (204) on success

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace
    """
    workspace_id = current_user.workspace_id
    # Fetch existing service with workspace scoping (raises 404 if not found)
    service = await get_or_404(db, Service, service_id, workspace_id)

    # Smart deletion: soft delete if referenced, hard delete if not
    await soft_delete_with_fk_check(
        db,
        service,
        service_id,
        workspace_id,
        Appointment,
        "service_id",
        "service",
    )
