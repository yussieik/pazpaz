"""Service CRUD API endpoints."""

from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.api.deps import get_current_workspace_id, get_db, get_or_404
from pazpaz.core.logging import get_logger
from pazpaz.models.appointment import Appointment
from pazpaz.models.service import Service
from pazpaz.schemas.service import (
    ServiceCreate,
    ServiceListResponse,
    ServiceResponse,
    ServiceUpdate,
)

router = APIRouter(prefix="/services", tags=["services"])
logger = get_logger(__name__)


@router.post("", response_model=ServiceResponse, status_code=201)
async def create_service(
    service_data: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> Service:
    """
    Create a new service.

    Creates a new service record in the authenticated workspace.
    All service data is scoped to the workspace.

    SECURITY: workspace_id is injected from authentication, not from request body.

    Args:
        service_data: Service creation data (without workspace_id)
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        Created service with all fields

    Raises:
        HTTPException: 401 if not authenticated, 422 if validation fails,
            409 if service name already exists in workspace
    """
    logger.info("service_create_started", workspace_id=str(workspace_id))

    # Check if service name already exists in workspace (unique constraint)
    existing_query = select(Service).where(
        Service.workspace_id == workspace_id,
        Service.name == service_data.name,
    )
    existing_result = await db.execute(existing_query)
    existing_service = existing_result.scalar_one_or_none()

    if existing_service:
        logger.info(
            "service_create_conflict",
            workspace_id=str(workspace_id),
            service_name=service_data.name,
        )
        service_name = service_data.name
        raise HTTPException(
            status_code=409,
            detail=f"Service with name '{service_name}' already exists",
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
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    is_active: bool | None = Query(
        True, description="Filter by active status (default: true)"
    ),
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> ServiceListResponse:
    """
    List all services in the workspace.

    Returns a paginated list of services, ordered by name.
    All results are scoped to the authenticated workspace.

    SECURITY: Only returns services belonging to the authenticated workspace.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        is_active: Filter by active status (default: true, None = all)
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        Paginated list of services with total count

    Raises:
        HTTPException: 401 if not authenticated
    """
    logger.debug(
        "service_list_started",
        workspace_id=str(workspace_id),
        page=page,
        page_size=page_size,
        is_active=is_active,
    )

    # Calculate offset
    offset = (page - 1) * page_size

    # Build base query with workspace scoping
    base_query = select(Service).where(Service.workspace_id == workspace_id)

    # Apply is_active filter if specified
    if is_active is not None:
        base_query = base_query.where(Service.is_active == is_active)

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Get paginated results ordered by name
    query = base_query.order_by(Service.name).offset(offset).limit(page_size)
    result = await db.execute(query)
    services = result.scalars().all()

    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 0

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
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> Service:
    """
    Get a single service by ID.

    Retrieves a service by ID, ensuring it belongs to the authenticated workspace.

    SECURITY: Returns 404 for non-existent services and services in
    other workspaces to prevent information leakage.

    Args:
        service_id: UUID of the service
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        Service details

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace
    """
    # Use helper function for workspace-scoped fetch with generic error
    service = await get_or_404(db, Service, service_id, workspace_id)
    return service


@router.put("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: uuid.UUID,
    service_data: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> Service:
    """
    Update an existing service.

    Updates service fields. Only provided fields are updated.
    Service must belong to the authenticated workspace.

    SECURITY: Verifies workspace ownership before allowing updates.

    Args:
        service_id: UUID of the service to update
        service_data: Fields to update
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        Updated service

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
            409 if name conflicts with existing service, 422 if validation fails
    """
    # Fetch existing service with workspace scoping (raises 404 if not found)
    service = await get_or_404(db, Service, service_id, workspace_id)

    # Update only provided fields
    update_data = service_data.model_dump(exclude_unset=True)

    # Check for name conflicts if name is being updated
    if "name" in update_data and update_data["name"] != service.name:
        existing_query = select(Service).where(
            Service.workspace_id == workspace_id,
            Service.name == update_data["name"],
            Service.id != service_id,
        )
        existing_result = await db.execute(existing_query)
        existing_service = existing_result.scalar_one_or_none()

        if existing_service:
            logger.info(
                "service_update_conflict",
                service_id=str(service_id),
                workspace_id=str(workspace_id),
                service_name=update_data["name"],
            )
            service_name = update_data["name"]
            raise HTTPException(
                status_code=409,
                detail=f"Service with name '{service_name}' already exists",
            )

    for field, value in update_data.items():
        setattr(service, field, value)

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
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> None:
    """
    Delete a service.

    Soft deletes a service by setting is_active=False if referenced by
    appointments.
    Hard deletes if no appointments reference it.
    Service must belong to the authenticated workspace.

    SECURITY: Verifies workspace ownership before allowing deletion.

    Args:
        service_id: UUID of the service to delete
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        No content (204) on success

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace
    """
    # Fetch existing service with workspace scoping (raises 404 if not found)
    service = await get_or_404(db, Service, service_id, workspace_id)

    # Check if service is referenced by any appointments
    appointments_query = select(func.count()).where(
        Appointment.service_id == service_id
    )
    appointments_result = await db.execute(appointments_query)
    appointments_count = appointments_result.scalar_one()

    if appointments_count > 0:
        # Soft delete: set is_active to False instead of deleting
        service.is_active = False
        await db.commit()

        logger.info(
            "service_soft_deleted",
            service_id=str(service_id),
            workspace_id=str(workspace_id),
            appointments_count=appointments_count,
        )
    else:
        # Hard delete: no appointments reference this service
        await db.delete(service)
        await db.commit()

        logger.info(
            "service_hard_deleted",
            service_id=str(service_id),
            workspace_id=str(workspace_id),
        )
