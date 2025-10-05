"""FastAPI dependencies for authentication and database access."""

from __future__ import annotations

import uuid

from fastapi import Cookie, Depends, Header, HTTPException
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.logging import get_logger
from pazpaz.core.security import decode_access_token
from pazpaz.db.base import get_db
from pazpaz.models.user import User
from pazpaz.services.auth_service import get_user_by_id

logger = get_logger(__name__)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    access_token: str | None = Cookie(None),
) -> User:
    """
    Get current authenticated user from JWT token.

    This is the PRIMARY authentication dependency for all protected endpoints.
    Validates JWT token from HttpOnly cookie and returns authenticated user.

    Security:
    - JWT validation with HS256 algorithm
    - Token expiry check (handled by JWT library)
    - User existence and active status validation
    - Workspace context available via user.workspace_id

    Args:
        db: Database session (injected)
        access_token: JWT from HttpOnly cookie

    Returns:
        Authenticated User object

    Raises:
        HTTPException: 401 if token is missing, invalid, or user not found

    Example:
        ```python
        @router.get("/protected")
        async def protected_endpoint(
            current_user: Annotated[User, Depends(get_current_user)]
        ):
            # Access user.id, user.workspace_id, etc.
            pass
        ```
    """
    if not access_token:
        logger.warning("authentication_failed", reason="missing_jwt_token")
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    try:
        # Decode and validate JWT
        payload = decode_access_token(access_token)
        user_id_str = payload.get("user_id")

        if not user_id_str:
            logger.warning("authentication_failed", reason="missing_user_id_in_token")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
            )

        user_id = uuid.UUID(user_id_str)

    except JWTError as e:
        logger.warning(
            "authentication_failed",
            reason="jwt_decode_error",
            error=str(e),
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
        ) from e
    except ValueError as e:
        logger.warning(
            "authentication_failed",
            reason="invalid_user_id_format",
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
        ) from e

    # Fetch user from database
    user = await get_user_by_id(db, user_id)

    if not user:
        logger.warning(
            "authentication_failed",
            reason="user_not_found",
            user_id=str(user_id),
        )
        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    if not user.is_active:
        logger.warning(
            "authentication_failed",
            reason="user_inactive",
            user_id=str(user_id),
        )
        raise HTTPException(
            status_code=401,
            detail="User account is inactive",
        )

    logger.debug(
        "user_authenticated",
        user_id=str(user.id),
        workspace_id=str(user.workspace_id),
    )

    return user


async def get_current_workspace_id(
    x_workspace_id: str | None = Header(None, alias="X-Workspace-ID"),
) -> uuid.UUID:
    """
    DEPRECATED: Extract workspace ID from X-Workspace-ID header.

    This is a LEGACY dependency kept for backward compatibility during migration.
    Use get_current_user() instead for production authentication.

    SECURITY WARNING: This provides NO actual authentication!
    Only validates UUID format, not user authorization.

    Migration Path:
    1. Update all endpoints to use get_current_user()
    2. Extract workspace_id from user.workspace_id
    3. Remove this dependency once all endpoints migrated

    Args:
        x_workspace_id: Workspace ID from X-Workspace-ID header (temporary)

    Returns:
        Validated workspace UUID

    Raises:
        HTTPException: 401 if workspace ID is missing or invalid format
    """
    if not x_workspace_id:
        logger.warning("authentication_failed", reason="missing_workspace_id_header")
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    try:
        workspace_uuid = uuid.UUID(x_workspace_id)
        logger.debug("workspace_authenticated", workspace_id=str(workspace_uuid))
        return workspace_uuid
    except ValueError as e:
        logger.warning(
            "authentication_failed",
            reason="invalid_workspace_id_format",
            workspace_id=x_workspace_id,
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
            "resource_not_found_or_access_denied",
            model=model_class.__name__,
            resource_id=str(resource_id),
            workspace_id=str(workspace_id),
        )
        # Return generic error to client (don't reveal existence)
        raise HTTPException(
            status_code=404,
            detail="Resource not found",
        )

    return resource


# Re-export for convenience
__all__ = ["get_db", "get_current_user", "get_current_workspace_id", "get_or_404"]
