"""Location CRUD API endpoints."""

from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.api.deps import get_current_user, get_db, get_or_404
from pazpaz.core.logging import get_logger
from pazpaz.models.appointment import Appointment, LocationType
from pazpaz.models.location import Location
from pazpaz.models.user import User
from pazpaz.schemas.location import (
    LocationCreate,
    LocationListResponse,
    LocationResponse,
    LocationUpdate,
)

router = APIRouter(prefix="/locations", tags=["locations"])
logger = get_logger(__name__)


@router.post("", response_model=LocationResponse, status_code=201)
async def create_location(
    location_data: LocationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Location:
    """
    Create a new location.

    Creates a new location record in the authenticated workspace.
    All location data is scoped to the workspace.

    SECURITY: workspace_id is derived from authenticated user's JWT token (server-side).

    Args:
        location_data: Location creation data (without workspace_id)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Created location with all fields

    Raises:
        HTTPException: 401 if not authenticated, 422 if validation fails,
            409 if location name already exists in workspace
    """
    workspace_id = current_user.workspace_id
    logger.info("location_create_started", workspace_id=str(workspace_id))

    # Validate: address is required for clinic or home locations
    requires_address = location_data.location_type in [
        LocationType.CLINIC,
        LocationType.HOME,
    ]
    if requires_address and (
        not location_data.address or not location_data.address.strip()
    ):
        logger.info(
            "location_create_validation_failed",
            workspace_id=str(workspace_id),
            location_type=location_data.location_type.value,
            reason="address_required",
        )
        location_type = location_data.location_type.value
        raise HTTPException(
            status_code=422,
            detail=f"Address is required for {location_type} locations",
        )

    # Check if location name already exists in workspace (unique constraint)
    existing_query = select(Location).where(
        Location.workspace_id == workspace_id,
        Location.name == location_data.name,
    )
    existing_result = await db.execute(existing_query)
    existing_location = existing_result.scalar_one_or_none()

    if existing_location:
        logger.info(
            "location_create_conflict",
            workspace_id=str(workspace_id),
            location_name=location_data.name,
        )
        location_name = location_data.name
        raise HTTPException(
            status_code=409,
            detail=f"Location with name '{location_name}' already exists",
        )

    # Create new location instance with injected workspace_id
    location = Location(
        workspace_id=workspace_id,
        name=location_data.name,
        location_type=location_data.location_type,
        address=location_data.address,
        details=location_data.details,
        is_active=location_data.is_active,
    )

    db.add(location)
    await db.commit()
    await db.refresh(location)

    logger.info(
        "location_created",
        location_id=str(location.id),
        workspace_id=str(workspace_id),
        location_name=location_data.name,
        location_type=location_data.location_type.value,
    )
    return location


@router.get("", response_model=LocationListResponse)
async def list_locations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    is_active: bool | None = Query(
        True, description="Filter by active status (default: true)"
    ),
    location_type: LocationType | None = Query(
        None, description="Filter by location type"
    ),
) -> LocationListResponse:
    """
    List all locations in the workspace.

    Returns a paginated list of locations, ordered by name.
    All results are scoped to the authenticated workspace.

    SECURITY: Only returns locations belonging to the authenticated user's workspace (from JWT).

    Args:
        current_user: Authenticated user (from JWT token)
        db: Database session
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        is_active: Filter by active status (default: true, None = all)
        location_type: Filter by location type (clinic, home, online)

    Returns:
        Paginated list of locations with total count

    Raises:
        HTTPException: 401 if not authenticated
    """
    workspace_id = current_user.workspace_id
    logger.debug(
        "location_list_started",
        workspace_id=str(workspace_id),
        page=page,
        page_size=page_size,
        is_active=is_active,
        location_type=location_type.value if location_type else None,
    )

    # Calculate offset
    offset = (page - 1) * page_size

    # Build base query with workspace scoping
    base_query = select(Location).where(Location.workspace_id == workspace_id)

    # Apply is_active filter if specified
    if is_active is not None:
        base_query = base_query.where(Location.is_active == is_active)

    # Apply location_type filter if specified
    if location_type is not None:
        base_query = base_query.where(Location.location_type == location_type)

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Get paginated results ordered by name
    query = base_query.order_by(Location.name).offset(offset).limit(page_size)
    result = await db.execute(query)
    locations = result.scalars().all()

    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    logger.debug(
        "location_list_completed",
        workspace_id=str(workspace_id),
        total_locations=total,
        page=page,
    )

    return LocationListResponse(
        items=locations,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{location_id}", response_model=LocationResponse)
async def get_location(
    location_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Location:
    """
    Get a single location by ID.

    Retrieves a location by ID, ensuring it belongs to the authenticated workspace.

    SECURITY: Returns 404 for non-existent locations and locations in
    other workspaces to prevent information leakage. workspace_id is derived from JWT token.

    Args:
        location_id: UUID of the location
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Location details

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace
    """
    workspace_id = current_user.workspace_id
    # Use helper function for workspace-scoped fetch with generic error
    location = await get_or_404(db, Location, location_id, workspace_id)
    return location


@router.put("/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: uuid.UUID,
    location_data: LocationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Location:
    """
    Update an existing location.

    Updates location fields. Only provided fields are updated.
    Location must belong to the authenticated workspace.

    SECURITY: Verifies workspace ownership before allowing updates.
    workspace_id is derived from JWT token (server-side).

    Args:
        location_id: UUID of the location to update
        location_data: Fields to update
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Updated location

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
            409 if name conflicts with existing location, 422 if validation fails
    """
    workspace_id = current_user.workspace_id
    # Fetch existing location with workspace scoping (raises 404 if not found)
    location = await get_or_404(db, Location, location_id, workspace_id)

    # Update only provided fields
    update_data = location_data.model_dump(exclude_unset=True)

    # Determine final location_type for validation
    final_location_type = update_data.get("location_type", location.location_type)
    final_address = update_data.get("address", location.address)

    # Validate: address is required for clinic or home locations
    requires_address = final_location_type in [
        LocationType.CLINIC,
        LocationType.HOME,
    ]
    if requires_address and (not final_address or not final_address.strip()):
        logger.info(
            "location_update_validation_failed",
            location_id=str(location_id),
            workspace_id=str(workspace_id),
            location_type=final_location_type.value,
            reason="address_required",
        )
        location_type = final_location_type.value
        raise HTTPException(
            status_code=422,
            detail=f"Address is required for {location_type} locations",
        )

    # Check for name conflicts if name is being updated
    if "name" in update_data and update_data["name"] != location.name:
        existing_query = select(Location).where(
            Location.workspace_id == workspace_id,
            Location.name == update_data["name"],
            Location.id != location_id,
        )
        existing_result = await db.execute(existing_query)
        existing_location = existing_result.scalar_one_or_none()

        if existing_location:
            logger.info(
                "location_update_conflict",
                location_id=str(location_id),
                workspace_id=str(workspace_id),
                location_name=update_data["name"],
            )
            location_name = update_data["name"]
            raise HTTPException(
                status_code=409,
                detail=f"Location with name '{location_name}' already exists",
            )

    for field, value in update_data.items():
        setattr(location, field, value)

    await db.commit()
    await db.refresh(location)

    logger.info(
        "location_updated",
        location_id=str(location_id),
        workspace_id=str(workspace_id),
        updated_fields=list(update_data.keys()),
    )
    return location


@router.delete("/{location_id}", status_code=204)
async def delete_location(
    location_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a location.

    Soft deletes a location by setting is_active=False if referenced by
    appointments.
    Hard deletes if no appointments reference it.
    Location must belong to the authenticated workspace.

    SECURITY: Verifies workspace ownership before allowing deletion.
    workspace_id is derived from JWT token (server-side).

    Args:
        location_id: UUID of the location to delete
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        No content (204) on success

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace
    """
    workspace_id = current_user.workspace_id
    # Fetch existing location with workspace scoping (raises 404 if not found)
    location = await get_or_404(db, Location, location_id, workspace_id)

    # Check if location is referenced by any appointments
    appointments_query = select(func.count()).where(
        Appointment.location_id == location_id
    )
    appointments_result = await db.execute(appointments_query)
    appointments_count = appointments_result.scalar_one()

    if appointments_count > 0:
        # Soft delete: set is_active to False instead of deleting
        location.is_active = False
        await db.commit()

        logger.info(
            "location_soft_deleted",
            location_id=str(location_id),
            workspace_id=str(workspace_id),
            appointments_count=appointments_count,
        )
    else:
        # Hard delete: no appointments reference this location
        await db.delete(location)
        await db.commit()

        logger.info(
            "location_hard_deleted",
            location_id=str(location_id),
            workspace_id=str(workspace_id),
        )
