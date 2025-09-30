"""Client CRUD API endpoints."""

from __future__ import annotations

import logging
import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.api.deps import get_current_workspace_id, get_db, get_or_404
from pazpaz.models.client import Client
from pazpaz.schemas.client import (
    ClientCreate,
    ClientListResponse,
    ClientResponse,
    ClientUpdate,
)

router = APIRouter(prefix="/clients", tags=["clients"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ClientResponse, status_code=201)
async def create_client(
    client_data: ClientCreate,
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> Client:
    """
    Create a new client.

    Creates a new client record in the authenticated workspace.
    All client data is scoped to the workspace.

    SECURITY: workspace_id is injected from authentication, not from request body.

    Args:
        client_data: Client creation data (without workspace_id)
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        Created client with all fields

    Raises:
        HTTPException: 401 if not authenticated, 422 if validation fails
    """
    logger.info(f"Creating client in workspace {workspace_id}")

    # Create new client instance with injected workspace_id
    client = Client(
        workspace_id=workspace_id,
        first_name=client_data.first_name,
        last_name=client_data.last_name,
        email=client_data.email,
        phone=client_data.phone,
        date_of_birth=client_data.date_of_birth,
        consent_status=client_data.consent_status,
        notes=client_data.notes,
        tags=client_data.tags,
    )

    db.add(client)
    await db.commit()
    await db.refresh(client)

    logger.info(f"Created client {client.id} in workspace {workspace_id}")
    return client


@router.get("", response_model=ClientListResponse)
async def list_clients(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> ClientListResponse:
    """
    List all clients in the workspace.

    Returns a paginated list of clients, ordered by last name, first name.
    All results are scoped to the authenticated workspace.

    SECURITY: Only returns clients belonging to the authenticated workspace.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        Paginated list of clients with total count

    Raises:
        HTTPException: 401 if not authenticated
    """
    logger.debug(f"Listing clients for workspace {workspace_id}, page {page}")

    # Calculate offset
    offset = (page - 1) * page_size

    # Build base query with workspace scoping
    base_query = select(Client).where(Client.workspace_id == workspace_id)

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Get paginated results ordered by name
    query = (
        base_query.order_by(Client.last_name, Client.first_name)
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    clients = result.scalars().all()

    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    logger.debug(f"Found {total} clients in workspace {workspace_id}")

    return ClientListResponse(
        items=clients,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> Client:
    """
    Get a single client by ID.

    Retrieves a client by ID, ensuring it belongs to the authenticated workspace.

    SECURITY: Returns 404 for both non-existent clients and clients in other workspaces
    to prevent information leakage.

    Args:
        client_id: UUID of the client
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        Client details

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace
    """
    # Use helper function for workspace-scoped fetch with generic error
    client = await get_or_404(db, Client, client_id, workspace_id)
    return client


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: uuid.UUID,
    client_data: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> Client:
    """
    Update an existing client.

    Updates client fields. Only provided fields are updated.
    Client must belong to the authenticated workspace.

    SECURITY: Verifies workspace ownership before allowing updates.

    Args:
        client_id: UUID of the client to update
        client_data: Fields to update
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        Updated client

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
            422 if validation fails
    """
    # Fetch existing client with workspace scoping (raises 404 if not found)
    client = await get_or_404(db, Client, client_id, workspace_id)

    # Update only provided fields
    update_data = client_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)

    await db.commit()
    await db.refresh(client)

    logger.info(f"Updated client {client_id} in workspace {workspace_id}")
    return client


@router.delete("/{client_id}", status_code=204)
async def delete_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace_id),
) -> None:
    """
    Delete a client.

    Permanently deletes a client and all associated data (appointments, sessions, etc.)
    due to CASCADE delete. Client must belong to the authenticated workspace.

    SECURITY: Verifies workspace ownership before allowing deletion.

    Args:
        client_id: UUID of the client to delete
        db: Database session
        workspace_id: Authenticated workspace ID (from auth dependency)

    Returns:
        No content (204) on success

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace
    """
    # Fetch existing client with workspace scoping (raises 404 if not found)
    client = await get_or_404(db, Client, client_id, workspace_id)

    await db.delete(client)
    await db.commit()

    logger.info(f"Deleted client {client_id} from workspace {workspace_id}")
