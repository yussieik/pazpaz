"""FastAPI dependencies for authentication and database access."""

from __future__ import annotations

import logging
import uuid

from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.db.base import get_db

logger = logging.getLogger(__name__)


async def get_current_workspace_id(
    x_workspace_id: str | None = Header(None, alias="X-Workspace-ID"),
) -> uuid.UUID:
    """
    Extract and validate workspace ID from request headers.

    SECURITY NOTE: This is a TEMPORARY implementation for M1 milestone.
    For production, this MUST be replaced with proper JWT-based authentication
    where workspace_id is extracted from the verified JWT token.

    Current Implementation (M1 - TESTING ONLY):
    - Accepts X-Workspace-ID header for testing purposes
    - Validates UUID format
    - NO actual authentication or authorization

    Production TODO:
    - Replace with JWT token validation
    - Extract workspace_id from verified JWT claims
    - Validate user has access to the workspace
    - Implement session management
    - Add rate limiting

    Args:
        x_workspace_id: Workspace ID from X-Workspace-ID header (temporary)

    Returns:
        Validated workspace UUID

    Raises:
        HTTPException: 401 if workspace ID is missing or invalid format

    Example (TESTING ONLY):
        ```bash
        curl -H "X-Workspace-ID: 00000000-0000-0000-0000-000000000001" \\
             http://localhost:8000/api/v1/clients
        ```
    """
    if not x_workspace_id:
        logger.warning("Authentication failed: Missing X-Workspace-ID header")
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    try:
        workspace_uuid = uuid.UUID(x_workspace_id)
        logger.debug(f"Workspace authenticated: {workspace_uuid}")
        return workspace_uuid
    except ValueError as e:
        logger.warning(
            f"Authentication failed: Invalid workspace ID format: {x_workspace_id}"
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
        ) from e


async def get_or_404(
    db: AsyncSession,
    model_class,
    resource_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> object:
    """
    Fetch a resource by ID and verify it belongs to the authenticated workspace.

    This helper enforces workspace isolation at the data access layer.
    Returns generic 404 error to prevent information leakage about resource existence.

    Security Principles:
    - Fail closed: 404 for both "not found" and "wrong workspace"
    - Generic errors: Don't reveal whether resource exists in different workspace
    - Server-side logging: Log actual reason for debugging without exposing to client

    Args:
        db: Database session
        model_class: SQLAlchemy model class to query
        resource_id: UUID of the resource to fetch
        workspace_id: Authenticated workspace ID

    Returns:
        Resource instance if found and belongs to workspace

    Raises:
        HTTPException: 404 with generic message for any failure

    Example:
        ```python
        client = await get_or_404(db, Client, client_id, workspace_id)
        ```
    """
    from sqlalchemy import select

    query = select(model_class).where(
        model_class.id == resource_id,
        model_class.workspace_id == workspace_id,
    )
    result = await db.execute(query)
    resource = result.scalar_one_or_none()

    if not resource:
        # Log detailed reason server-side for debugging
        logger.info(
            f"Resource not found or access denied: "
            f"model={model_class.__name__}, "
            f"resource_id={resource_id}, "
            f"workspace_id={workspace_id}"
        )
        # Return generic error to client (don't reveal existence)
        raise HTTPException(
            status_code=404,
            detail="Resource not found",
        )

    return resource


# Re-export get_db for convenience
__all__ = ["get_db", "get_current_workspace_id", "get_or_404"]
