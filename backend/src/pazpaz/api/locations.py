"""Location CRUD API endpoints."""

from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.api.deps import get_current_workspace_id, get_db, get_or_404
from pazpaz.core.logging import get_logger
from pazpaz.models.appointment import Appointment, LocationType
from pazpaz.models.location import Location
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
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> Location:
    """
    Create a new location.

    Creates a new location record in the authenticated workspace.
    All location data is scoped to the workspace.

    SECURITY: workspace_id is injected from authentication, not from request body.

    Args:
        location_data: Location creation data (without workspace_id)
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        Created location with all fields

    Raises:
        HTTPException: 401 if not authenticated, 422 if validation fails,
            409 if location name already exists in workspace
    """
    logger.info("location_create_started", workspace_id=str(workspace_id))

    # Validate: address is required for clinic or home locations
    if location_data.location_type in [LocationType.CLINIC, LocationType.HOME]:
        if not location_data.address or not location_data.address.strip():
            logger.info(
                "location_create_validation_failed",
                workspace_id=str(workspace_id),
                location_type=location_data.location_type.value,
                reason="address_required",
            )
            raise HTTPException(
                status_code=422,
                detail=f"Address is required for {location_data.location_type.value} locations",
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
        raise HTTPException(
            status_code=409,
            detail=f"Location with name '{location_data.name}' already exists in this workspace",
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
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    is_active: bool | None = Query(
        True, description="Filter by active status (default: true)"
    ),
    location_type: LocationType | None = Query(
        None, description="Filter by location type"
    ),
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> LocationListResponse:
    """
    List all locations in the workspace.

    Returns a paginated list of locations, ordered by name.
    All results are scoped to the authenticated workspace.

    SECURITY: Only returns locations belonging to the authenticated workspace.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        is_active: Filter by active status (default: true, None = all)
        location_type: Filter by location type (clinic, home, online)
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        Paginated list of locations with total count

    Raises:
        HTTPException: 401 if not authenticated
    """
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
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> Location:
    """
    Get a single location by ID.

    Retrieves a location by ID, ensuring it belongs to the authenticated workspace.

    SECURITY: Returns 404 for both non-existent locations and locations in other workspaces
    to prevent information leakage.

    Args:
        location_id: UUID of the location
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        Location details

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace
    """
    # Use helper function for workspace-scoped fetch with generic error
    location = await get_or_404(db, Location, location_id, workspace_id)
    return location


@router.put("/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: uuid.UUID,
    location_data: LocationUpdate,
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> Location:
    """
    Update an existing location.

    Updates location fields. Only provided fields are updated.
    Location must belong to the authenticated workspace.

    SECURITY: Verifies workspace ownership before allowing updates.

    Args:
        location_id: UUID of the location to update
        location_data: Fields to update
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        Updated location

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
            409 if name conflicts with existing location, 422 if validation fails
    """
    # Fetch existing location with workspace scoping (raises 404 if not found)
    location = await get_or_404(db, Location, location_id, workspace_id)

    # Update only provided fields
    update_data = location_data.model_dump(exclude_unset=True)

    # Determine final location_type for validation
    final_location_type = update_data.get("location_type", location.location_type)
    final_address = update_data.get("address", location.address)

    # Validate: address is required for clinic or home locations
    if final_location_type in [LocationType.CLINIC, LocationType.HOME]:
        if not final_address or not final_address.strip():
            logger.info(
                "location_update_validation_failed",
                location_id=str(location_id),
                workspace_id=str(workspace_id),
                location_type=final_location_type.value,
                reason="address_required",
            )
            raise HTTPException(
                status_code=422,
                detail=f"Address is required for {final_location_type.value} locations",
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
            raise HTTPException(
                status_code=409,
                detail=f"Location with name '{update_data['name']}' already exists in this workspace",
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
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> None:
    """
    Delete a location.

    Soft deletes a location by setting is_active=False if it's referenced by appointments.
    Hard deletes if no appointments reference it.
    Location must belong to the authenticated workspace.

    SECURITY: Verifies workspace ownership before allowing deletion.

    Args:
        location_id: UUID of the location to delete
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        No content (204) on success

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace
    """
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
