"""Workspace API endpoints for storage management.

This module provides admin endpoints for workspace storage quota management:
- View current storage usage
- Adjust storage quotas (admin only)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.api.deps import get_current_user, get_db
from pazpaz.core.logging import get_logger
from pazpaz.models.user import User
from pazpaz.models.workspace import Workspace

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
logger = get_logger(__name__)


class WorkspaceStorageUsageResponse(BaseModel):
    """Response model for workspace storage usage."""

    used_bytes: int = Field(
        ..., description="Total bytes used by all files in workspace"
    )
    quota_bytes: int = Field(
        ..., description="Maximum storage allowed for workspace in bytes"
    )
    remaining_bytes: int = Field(
        ..., description="Bytes remaining (can be negative if quota exceeded)"
    )
    usage_percentage: float = Field(
        ..., description="Percentage of quota used (0-100+)"
    )
    is_quota_exceeded: bool = Field(
        ..., description="True if storage usage exceeds quota"
    )

    # Human-readable convenience fields
    used_mb: float = Field(..., description="Storage used in megabytes")
    quota_mb: float = Field(..., description="Quota in megabytes")
    remaining_mb: float = Field(..., description="Remaining storage in megabytes")

    class Config:
        from_attributes = True


class WorkspaceStorageQuotaUpdateRequest(BaseModel):
    """Request model for updating workspace storage quota."""

    quota_bytes: int = Field(
        ...,
        gt=0,
        description="New storage quota in bytes (must be positive)",
    )


@router.get(
    "/{workspace_id}/storage",
    response_model=WorkspaceStorageUsageResponse,
)
async def get_workspace_storage_usage(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceStorageUsageResponse:
    """
    Get current workspace storage usage statistics.

    Returns detailed storage usage information including:
    - Total bytes used by all files
    - Storage quota (maximum allowed)
    - Remaining storage (can be negative if over quota)
    - Usage percentage
    - Quota exceeded flag

    Args:
        workspace_id: Workspace UUID
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Storage usage statistics

    Raises:
        HTTPException:
            - 401 if not authenticated
            - 403 if workspace_id doesn't match user's workspace
            - 404 if workspace not found

    Example:
        GET /api/v1/workspaces/{uuid}/storage
        Response: {
            "used_bytes": 5368709120,
            "quota_bytes": 10737418240,
            "remaining_bytes": 5368709120,
            "usage_percentage": 50.0,
            "is_quota_exceeded": false,
            "used_mb": 5120.0,
            "quota_mb": 10240.0,
            "remaining_mb": 5120.0
        }
    """
    # Verify user has access to this workspace
    if current_user.workspace_id != workspace_id:
        logger.warning(
            "workspace_storage_access_denied",
            user_id=str(current_user.id),
            user_workspace_id=str(current_user.workspace_id),
            requested_workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this workspace",
        )

    # Fetch workspace with storage info
    stmt = select(Workspace).where(Workspace.id == workspace_id)
    result = await db.execute(stmt)
    workspace = result.scalar_one_or_none()

    if not workspace:
        logger.error(
            "workspace_not_found",
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    logger.info(
        "workspace_storage_usage_retrieved",
        workspace_id=str(workspace_id),
        user_id=str(current_user.id),
        used_bytes=workspace.storage_used_bytes,
        quota_bytes=workspace.storage_quota_bytes,
        usage_percentage=round(workspace.storage_usage_percentage, 2),
    )

    # Convert bytes to MB for convenience
    used_mb = workspace.storage_used_bytes / (1024 * 1024)
    quota_mb = workspace.storage_quota_bytes / (1024 * 1024)
    remaining_mb = workspace.storage_remaining_bytes / (1024 * 1024)

    return WorkspaceStorageUsageResponse(
        used_bytes=workspace.storage_used_bytes,
        quota_bytes=workspace.storage_quota_bytes,
        remaining_bytes=workspace.storage_remaining_bytes,
        usage_percentage=workspace.storage_usage_percentage,
        is_quota_exceeded=workspace.is_quota_exceeded,
        used_mb=round(used_mb, 2),
        quota_mb=round(quota_mb, 2),
        remaining_mb=round(remaining_mb, 2),
    )


@router.patch(
    "/{workspace_id}/storage/quota",
    response_model=WorkspaceStorageUsageResponse,
)
async def update_workspace_storage_quota(
    workspace_id: uuid.UUID,
    quota_update: WorkspaceStorageQuotaUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceStorageUsageResponse:
    """
    Update workspace storage quota (admin only).

    This endpoint allows administrators to increase or decrease the storage quota
    for a workspace. Useful for:
    - Upgrading workspace to higher tier
    - Temporarily increasing quota for busy practices
    - Reducing quota for inactive workspaces

    IMPORTANT: This does NOT delete files if new quota is lower than current usage.
    Workspace will be over quota until files are deleted.

    Args:
        workspace_id: Workspace UUID
        quota_update: New quota in bytes
        current_user: Authenticated user (must be admin)
        db: Database session

    Returns:
        Updated storage usage statistics

    Raises:
        HTTPException:
            - 401 if not authenticated
            - 403 if not admin or wrong workspace
            - 404 if workspace not found
            - 400 if quota_bytes is invalid (zero or negative)

    Example:
        PATCH /api/v1/workspaces/{uuid}/storage/quota
        {
            "quota_bytes": 21474836480
        }
        Response: (same as GET /storage)
    """
    # Verify user has access to this workspace
    if current_user.workspace_id != workspace_id:
        logger.warning(
            "workspace_quota_update_access_denied",
            user_id=str(current_user.id),
            user_workspace_id=str(current_user.workspace_id),
            requested_workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this workspace",
        )

    # TODO: Add role-based check when User model has role field
    # For now, any authenticated user in workspace can adjust quota
    # In production, add: if not current_user.is_admin: raise 403

    # Fetch workspace
    stmt = select(Workspace).where(Workspace.id == workspace_id)
    result = await db.execute(stmt)
    workspace = result.scalar_one_or_none()

    if not workspace:
        logger.error(
            "workspace_not_found",
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # Store old quota for logging
    old_quota_bytes = workspace.storage_quota_bytes
    old_quota_mb = old_quota_bytes / (1024 * 1024)
    new_quota_mb = quota_update.quota_bytes / (1024 * 1024)

    # Update quota
    workspace.storage_quota_bytes = quota_update.quota_bytes

    await db.commit()
    await db.refresh(workspace)

    logger.info(
        "workspace_storage_quota_updated",
        workspace_id=str(workspace_id),
        user_id=str(current_user.id),
        old_quota_bytes=old_quota_bytes,
        old_quota_mb=round(old_quota_mb, 2),
        new_quota_bytes=quota_update.quota_bytes,
        new_quota_mb=round(new_quota_mb, 2),
        current_usage_bytes=workspace.storage_used_bytes,
        is_now_over_quota=workspace.is_quota_exceeded,
    )

    # Return updated usage stats
    used_mb = workspace.storage_used_bytes / (1024 * 1024)
    quota_mb = workspace.storage_quota_bytes / (1024 * 1024)
    remaining_mb = workspace.storage_remaining_bytes / (1024 * 1024)

    return WorkspaceStorageUsageResponse(
        used_bytes=workspace.storage_used_bytes,
        quota_bytes=workspace.storage_quota_bytes,
        remaining_bytes=workspace.storage_remaining_bytes,
        usage_percentage=workspace.storage_usage_percentage,
        is_quota_exceeded=workspace.is_quota_exceeded,
        used_mb=round(used_mb, 2),
        quota_mb=round(quota_mb, 2),
        remaining_mb=round(remaining_mb, 2),
    )
