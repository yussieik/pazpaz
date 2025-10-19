"""
Storage quota enforcement utilities.

This module provides workspace storage quota validation and tracking to prevent
storage abuse and enforce resource limits per HIPAA §164.308(a)(7)(ii)(B).

Key Features:
- Quota validation BEFORE file upload (fail fast)
- Atomic storage updates using SELECT FOR UPDATE (prevents race conditions)
- Increment/decrement operations for upload/delete
- Comprehensive logging for monitoring and audit

Usage:
    from pazpaz.utils.storage_quota import (
        validate_workspace_storage_quota,
        update_workspace_storage,
        get_workspace_storage_usage,
    )

    # Before upload: Validate quota (fail fast if exceeded)
    await validate_workspace_storage_quota(
        workspace_id=workspace.id,
        new_file_size=file_size,
        db=db,
    )

    # After successful upload: Increment usage
    await update_workspace_storage(
        workspace_id=workspace.id,
        bytes_delta=file_size,  # Positive for upload
        db=db,
    )

    # After file deletion: Decrement usage
    await update_workspace_storage(
        workspace_id=workspace.id,
        bytes_delta=-file_size,  # Negative for delete
        db=db,
    )

    # View current usage
    usage = await get_workspace_storage_usage(workspace_id=workspace.id, db=db)
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from pazpaz.core.logging import get_logger
from pazpaz.models.workspace import Workspace

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class StorageQuotaExceededError(Exception):
    """Raised when workspace storage quota is exceeded."""

    pass


async def validate_workspace_storage_quota(
    workspace_id: uuid.UUID,
    new_file_size: int,
    db: AsyncSession,
) -> None:
    """
    Validate that adding a new file will not exceed workspace storage quota.

    This function performs a quota check BEFORE file upload to fail fast and
    avoid uploading files that will be rejected due to quota limits.

    CRITICAL: Call this BEFORE uploading to S3 to prevent wasted bandwidth
    and API costs.

    Args:
        workspace_id: Workspace UUID
        new_file_size: Size of file to be uploaded (bytes)
        db: Database session

    Raises:
        StorageQuotaExceededError: If adding file would exceed quota
        ValueError: If workspace not found

    Example:
        >>> await validate_workspace_storage_quota(
        ...     workspace_id=uuid.UUID("..."),
        ...     new_file_size=5_000_000,  # 5 MB
        ...     db=db,
        ... )
        # Returns None if quota OK, raises StorageQuotaExceededError if not
    """
    # Fetch workspace with current storage usage
    stmt = select(Workspace).where(Workspace.id == workspace_id)
    result = await db.execute(stmt)
    workspace = result.scalar_one_or_none()

    if not workspace:
        logger.error(
            "workspace_not_found",
            workspace_id=str(workspace_id),
        )
        raise ValueError(f"Workspace {workspace_id} not found")

    # Calculate projected storage after upload
    projected_usage = workspace.storage_used_bytes + new_file_size

    # Check if projected usage exceeds quota
    if projected_usage > workspace.storage_quota_bytes:
        usage_mb = workspace.storage_used_bytes / (1024 * 1024)
        quota_mb = workspace.storage_quota_bytes / (1024 * 1024)
        new_file_mb = new_file_size / (1024 * 1024)
        projected_mb = projected_usage / (1024 * 1024)

        logger.warning(
            "storage_quota_exceeded",
            workspace_id=str(workspace_id),
            current_usage_mb=round(usage_mb, 2),
            quota_mb=round(quota_mb, 2),
            new_file_mb=round(new_file_mb, 2),
            projected_usage_mb=round(projected_mb, 2),
            action="upload_rejected",
        )

        raise StorageQuotaExceededError(
            f"Workspace storage quota exceeded. "
            f"Current usage: {usage_mb:.1f} MB, "
            f"Quota: {quota_mb:.1f} MB, "
            f"New file: {new_file_mb:.1f} MB. "
            f"Projected usage ({projected_mb:.1f} MB) exceeds quota. "
            f"Please delete some files or contact support to increase quota."
        )

    logger.debug(
        "storage_quota_validated",
        workspace_id=str(workspace_id),
        current_usage_bytes=workspace.storage_used_bytes,
        quota_bytes=workspace.storage_quota_bytes,
        new_file_bytes=new_file_size,
        projected_usage_bytes=projected_usage,
        remaining_bytes=workspace.storage_quota_bytes - projected_usage,
    )


async def update_workspace_storage(
    workspace_id: uuid.UUID,
    bytes_delta: int,
    db: AsyncSession,
) -> None:
    """
    Update workspace storage usage (atomic operation).

    This function uses SELECT FOR UPDATE to ensure atomic updates and prevent
    race conditions when multiple files are uploaded/deleted concurrently.

    CRITICAL: Always call this in the SAME transaction as file metadata creation/deletion
    to ensure consistency between S3 storage and database tracking.

    Args:
        workspace_id: Workspace UUID
        bytes_delta: Bytes to add (positive) or remove (negative)
        db: Database session (must be in transaction)

    Raises:
        ValueError: If workspace not found or invalid bytes_delta

    Example:
        >>> # After successful file upload
        >>> await update_workspace_storage(
        ...     workspace_id=workspace.id,
        ...     bytes_delta=5_000_000,  # +5 MB
        ...     db=db,
        ... )
        >>>
        >>> # After file deletion
        >>> await update_workspace_storage(
        ...     workspace_id=workspace.id,
        ...     bytes_delta=-5_000_000,  # -5 MB
        ...     db=db,
        ... )
    """
    # Atomic update: SELECT FOR UPDATE locks row until transaction commits
    stmt = (
        select(Workspace)
        .where(Workspace.id == workspace_id)
        .with_for_update()  # Row-level lock
    )
    result = await db.execute(stmt)
    workspace = result.scalar_one_or_none()

    if not workspace:
        logger.error(
            "workspace_not_found",
            workspace_id=str(workspace_id),
        )
        raise ValueError(f"Workspace {workspace_id} not found")

    # Calculate new storage usage
    old_usage = workspace.storage_used_bytes
    new_usage = old_usage + bytes_delta

    # Prevent negative storage usage
    if new_usage < 0:
        logger.warning(
            "storage_usage_would_be_negative",
            workspace_id=str(workspace_id),
            old_usage_bytes=old_usage,
            bytes_delta=bytes_delta,
            action="clamping_to_zero",
        )
        new_usage = 0

    # Update workspace storage
    workspace.storage_used_bytes = new_usage

    # Log storage update
    operation = "upload" if bytes_delta > 0 else "delete"
    logger.info(
        "workspace_storage_updated",
        workspace_id=str(workspace_id),
        operation=operation,
        old_usage_bytes=old_usage,
        new_usage_bytes=new_usage,
        bytes_delta=bytes_delta,
        quota_bytes=workspace.storage_quota_bytes,
        usage_percentage=round(workspace.storage_usage_percentage, 2),
    )

    # Note: Caller must commit transaction to persist changes


async def get_workspace_storage_usage(
    workspace_id: uuid.UUID,
    db: AsyncSession,
) -> dict[str, int | float]:
    """
    Get current workspace storage usage statistics.

    Args:
        workspace_id: Workspace UUID
        db: Database session

    Returns:
        Dictionary with storage statistics:
        - used_bytes: Total bytes used
        - quota_bytes: Maximum bytes allowed
        - remaining_bytes: Bytes remaining (can be negative)
        - usage_percentage: Percentage of quota used (0-100+)
        - is_quota_exceeded: Boolean indicating if quota exceeded

    Raises:
        ValueError: If workspace not found

    Example:
        >>> usage = await get_workspace_storage_usage(workspace.id, db)
        >>> print(f"Using {usage['usage_percentage']:.1f}% of quota")
        Using 47.3% of quota
    """
    stmt = select(Workspace).where(Workspace.id == workspace_id)
    result = await db.execute(stmt)
    workspace = result.scalar_one_or_none()

    if not workspace:
        logger.error(
            "workspace_not_found",
            workspace_id=str(workspace_id),
        )
        raise ValueError(f"Workspace {workspace_id} not found")

    return {
        "used_bytes": workspace.storage_used_bytes,
        "quota_bytes": workspace.storage_quota_bytes,
        "remaining_bytes": workspace.storage_remaining_bytes,
        "usage_percentage": workspace.storage_usage_percentage,
        "is_quota_exceeded": workspace.is_quota_exceeded,
    }
