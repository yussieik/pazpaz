"""FastAPI dependencies for authentication and database access."""

from __future__ import annotations

import uuid

import redis.asyncio as redis
from fastapi import Cookie, Depends, HTTPException
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.logging import get_logger
from pazpaz.core.redis import get_redis
from pazpaz.core.security import decode_access_token
from pazpaz.db.base import get_db
from pazpaz.models.client import Client
from pazpaz.models.user import User
from pazpaz.models.workspace import WorkspaceStatus
from pazpaz.services.auth_service import is_token_blacklisted

logger = get_logger(__name__)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    access_token: str | None = Cookie(None),
) -> User:
    """
    Get current authenticated user from JWT token.

    This is the PRIMARY authentication dependency for all protected endpoints.
    Validates JWT token from HttpOnly cookie and returns authenticated user.

    Security:
    - JWT validation with HS256 algorithm
    - Token expiry check (handled by JWT library)
    - Blacklist check (prevents use after logout)
    - User existence and active status validation
    - Workspace context available via user.workspace_id

    Args:
        db: Database session (injected)
        redis_client: Redis client (injected)
        access_token: JWT from HttpOnly cookie

    Returns:
        Authenticated User object

    Raises:
        HTTPException: 401 if token is missing, invalid, blacklisted, or user not found

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

        # Check if token is blacklisted (logout/revocation)
        if await is_token_blacklisted(redis_client, access_token):
            logger.warning(
                "authentication_failed",
                reason="token_blacklisted",
                user_id=user_id_str,
            )
            raise HTTPException(
                status_code=401,
                detail="Token has been revoked",
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

    # Fetch user from database with workspace relationship
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    query = select(User).where(User.id == user_id).options(selectinload(User.workspace))
    result = await db.execute(query)
    user = result.scalar_one_or_none()

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

    # CRITICAL SECURITY CHECK: Verify workspace status
    # Users from SUSPENDED or DELETED workspaces cannot authenticate
    # This provides immediate enforcement when a workspace is suspended
    if user.workspace.status != WorkspaceStatus.ACTIVE:
        logger.warning(
            "authentication_failed_workspace_not_active",
            reason="workspace_suspended_or_deleted",
            user_id=str(user.id),
            workspace_id=str(user.workspace_id),
            workspace_status=user.workspace.status.value,
        )

        # User-friendly error messages based on workspace status
        if user.workspace.status == WorkspaceStatus.SUSPENDED:
            detail = (
                "Your workspace has been suspended. "
                "Please contact support for assistance."
            )
        elif user.workspace.status == WorkspaceStatus.DELETED:
            detail = (
                "Your workspace has been deleted. "
                "Please contact support for assistance."
            )
        else:
            detail = "Your workspace is not active. Please contact support."

        raise HTTPException(
            status_code=403,
            detail=detail,
        )

    logger.debug(
        "user_authenticated",
        user_id=str(user.id),
        workspace_id=str(user.workspace_id),
    )

    return user


# REMOVED: get_current_workspace_id() dependency
#
# This dependency was removed on 2025-10-05 as part of critical security fix.
# It accepted unauthenticated X-Workspace-ID headers, allowing isolation bypass.
#
# VULNERABILITY: CVE-2025-XXXX (CVSS 9.1 - Critical)
# - Accepted ANY workspace UUID from X-Workspace-ID header without authentication
# - No validation that user had access to the workspace
# - Enabled PHI exposure across workspace boundaries
#
# MIGRATION: All endpoints now use get_current_user() which:
# - Validates JWT tokens from HttpOnly cookies
# - Derives workspace_id from authenticated user (server-side, trusted)
# - Prevents cross-workspace data access
#
# If you need workspace_id in an endpoint, use:
#   current_user: User = Depends(get_current_user)
#   workspace_id = current_user.workspace_id


async def get_or_404(
    db: AsyncSession,
    model_class,
    resource_id: uuid.UUID,
    workspace_id: uuid.UUID,
    include_deleted: bool = False,
) -> object:
    """
    Fetch a resource by ID and verify it belongs to the authenticated workspace.

    This helper enforces workspace isolation at the data access layer.
    Returns generic 404 error to prevent information leakage about resource existence.

    For models with soft delete (deleted_at column), excludes soft-deleted resources
    by default unless include_deleted=True is specified.

    Security Principles:
    - Fail closed: 404 for both "not found" and "wrong workspace"
    - Generic errors: Don't reveal whether resource exists in different workspace
    - Server-side logging: Log actual reason for debugging without exposing to client
    - Soft delete filtering: Prevents access to deleted resources by default

    Args:
        db: Database session
        model_class: SQLAlchemy model class to query
        resource_id: UUID of the resource to fetch
        workspace_id: Authenticated workspace ID
        include_deleted: If True, includes soft-deleted resources (default: False)

    Returns:
        Resource instance if found and belongs to workspace

    Raises:
        HTTPException: 404 with generic message for any failure

    Example:
        ```python
        # Normal usage (excludes soft-deleted)
        client = await get_or_404(db, Client, client_id, workspace_id)

        # Include soft-deleted (for restore operations)
        session = await get_or_404(
            db, Session, session_id, workspace_id, include_deleted=True
        )
        ```
    """
    from sqlalchemy import select

    query = select(model_class).where(
        model_class.id == resource_id,
        model_class.workspace_id == workspace_id,
    )

    # Filter out soft-deleted resources by default
    # Only if model has deleted_at column and include_deleted is False
    if hasattr(model_class, "deleted_at") and not include_deleted:
        query = query.where(model_class.deleted_at.is_(None))

    result = await db.execute(query)
    resource = result.scalar_one_or_none()

    if not resource:
        # Log detailed reason server-side for debugging
        logger.info(
            "resource_not_found_or_access_denied",
            model=model_class.__name__,
            resource_id=str(resource_id),
            workspace_id=str(workspace_id),
            include_deleted=include_deleted,
        )
        # Return generic error to client (don't reveal existence)
        raise HTTPException(
            status_code=404,
            detail="Resource not found",
        )

    return resource


async def verify_client_in_workspace(
    db: AsyncSession,
    client_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> Client:
    """
    Verify that a client exists and belongs to the workspace.

    This is a shared utility used by both appointments and sessions endpoints
    to ensure clients are workspace-scoped before operations.

    SECURITY: Returns generic 404 error to prevent information leakage.

    Args:
        db: Database session
        client_id: Client ID to verify
        workspace_id: Expected workspace ID

    Returns:
        Client instance if found and belongs to workspace

    Raises:
        HTTPException: 404 if client not found or belongs to different workspace

    Example:
        ```python
        client = await verify_client_in_workspace(
            db=db,
            client_id=appointment_data.client_id,
            workspace_id=workspace_id,
        )
        ```
    """
    return await get_or_404(db, Client, client_id, workspace_id)


# Re-export for convenience
__all__ = ["get_db", "get_current_user", "get_or_404", "verify_client_in_workspace"]
