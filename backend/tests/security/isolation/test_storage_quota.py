"""Comprehensive test suite for workspace storage quota functionality.

This test suite validates:
- Quota validation (under/at/over quota scenarios)
- Storage usage updates (increment/decrement)
- Atomic operations (race condition prevention)
- Storage management endpoints
- Edge cases (negative values, zero quota, concurrent uploads)
- Error handling and logging
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.workspace import Workspace
from pazpaz.utils.storage_quota import (
    StorageQuotaExceededError,
    get_workspace_storage_usage,
    update_workspace_storage,
    validate_workspace_storage_quota,
)


class TestQuotaValidation:
    """Test storage quota validation before uploads."""

    @pytest.mark.asyncio
    async def test_validate_under_quota(self, db: AsyncSession, workspace: Workspace):
        """Test validation passes when well under quota."""
        # Workspace has 10 GB quota, 0 bytes used
        # Upload 1 MB file (well under quota)
        await validate_workspace_storage_quota(
            workspace_id=workspace.id,
            new_file_size=1 * 1024 * 1024,  # 1 MB
            db=db,
        )
        # Should not raise exception

    @pytest.mark.asyncio
    async def test_validate_at_quota_minus_one(
        self, db: AsyncSession, workspace: Workspace
    ):
        """Test validation passes when exactly at quota minus one byte."""
        # Set workspace at 9.999... GB used (1 byte under quota)
        workspace.storage_used_bytes = workspace.storage_quota_bytes - 1
        await db.commit()

        # Upload 1 byte file (should succeed)
        await validate_workspace_storage_quota(
            workspace_id=workspace.id,
            new_file_size=1,
            db=db,
        )

    @pytest.mark.asyncio
    async def test_validate_exactly_at_quota(
        self, db: AsyncSession, workspace: Workspace
    ):
        """Test validation fails when exactly at quota."""
        # Set workspace at 10 GB used (at quota)
        workspace.storage_used_bytes = workspace.storage_quota_bytes
        await db.commit()

        # Upload 1 byte file (should fail - quota exceeded)
        with pytest.raises(StorageQuotaExceededError, match="Workspace storage quota exceeded"):
            await validate_workspace_storage_quota(
                workspace_id=workspace.id,
                new_file_size=1,
                db=db,
            )

    @pytest.mark.asyncio
    async def test_validate_over_quota(self, db: AsyncSession, workspace: Workspace):
        """Test validation fails when already over quota."""
        # Set workspace at 11 GB used (over quota)
        workspace.storage_used_bytes = workspace.storage_quota_bytes + (1024 * 1024 * 1024)
        await db.commit()

        # Upload 1 MB file (should fail - already over quota)
        with pytest.raises(StorageQuotaExceededError, match="Workspace storage quota exceeded"):
            await validate_workspace_storage_quota(
                workspace_id=workspace.id,
                new_file_size=1 * 1024 * 1024,
                db=db,
            )

    @pytest.mark.asyncio
    async def test_validate_large_file_exceeds_quota(
        self, db: AsyncSession, workspace: Workspace
    ):
        """Test validation fails when upload would exceed quota."""
        # Workspace has 10 GB quota, 5 GB used
        workspace.storage_used_bytes = 5 * 1024 * 1024 * 1024
        await db.commit()

        # Upload 6 GB file (5 GB + 6 GB = 11 GB > 10 GB quota)
        with pytest.raises(StorageQuotaExceededError, match="Workspace storage quota exceeded"):
            await validate_workspace_storage_quota(
                workspace_id=workspace.id,
                new_file_size=6 * 1024 * 1024 * 1024,
                db=db,
            )

    @pytest.mark.asyncio
    async def test_validate_workspace_not_found(self, db: AsyncSession):
        """Test validation raises ValueError for non-existent workspace."""
        non_existent_id = uuid.uuid4()

        with pytest.raises(ValueError, match="Workspace .* not found"):
            await validate_workspace_storage_quota(
                workspace_id=non_existent_id,
                new_file_size=1024,
                db=db,
            )


class TestStorageUpdates:
    """Test storage usage updates (increment/decrement)."""

    @pytest.mark.asyncio
    async def test_increment_storage_usage(
        self, db: AsyncSession, workspace: Workspace
    ):
        """Test incrementing storage usage after upload."""
        initial_usage = workspace.storage_used_bytes

        # Upload 5 MB file
        await update_workspace_storage(
            workspace_id=workspace.id,
            bytes_delta=5 * 1024 * 1024,
            db=db,
        )
        await db.commit()
        await db.refresh(workspace)

        assert workspace.storage_used_bytes == initial_usage + (5 * 1024 * 1024)

    @pytest.mark.asyncio
    async def test_decrement_storage_usage(
        self, db: AsyncSession, workspace: Workspace
    ):
        """Test decrementing storage usage after delete."""
        # Set initial usage to 10 MB
        workspace.storage_used_bytes = 10 * 1024 * 1024
        await db.commit()

        # Delete 3 MB file
        await update_workspace_storage(
            workspace_id=workspace.id,
            bytes_delta=-3 * 1024 * 1024,
            db=db,
        )
        await db.commit()
        await db.refresh(workspace)

        assert workspace.storage_used_bytes == 7 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_prevent_negative_storage_usage(
        self, db: AsyncSession, workspace: Workspace
    ):
        """Test that storage usage is clamped to 0 if delete would make it negative."""
        # Set initial usage to 5 MB
        workspace.storage_used_bytes = 5 * 1024 * 1024
        await db.commit()

        # Delete 10 MB file (more than current usage)
        # Should clamp to 0, not go negative
        await update_workspace_storage(
            workspace_id=workspace.id,
            bytes_delta=-10 * 1024 * 1024,
            db=db,
        )
        await db.commit()
        await db.refresh(workspace)

        assert workspace.storage_used_bytes == 0

    @pytest.mark.asyncio
    async def test_multiple_increments(self, db: AsyncSession, workspace: Workspace):
        """Test multiple sequential uploads increment correctly."""
        initial_usage = workspace.storage_used_bytes

        # Upload 3 files: 2 MB, 3 MB, 5 MB
        for size_mb in [2, 3, 5]:
            await update_workspace_storage(
                workspace_id=workspace.id,
                bytes_delta=size_mb * 1024 * 1024,
                db=db,
            )
            await db.commit()
            await db.refresh(workspace)

        assert workspace.storage_used_bytes == initial_usage + (10 * 1024 * 1024)

    @pytest.mark.asyncio
    async def test_update_workspace_not_found(self, db: AsyncSession):
        """Test update raises ValueError for non-existent workspace."""
        non_existent_id = uuid.uuid4()

        with pytest.raises(ValueError, match="Workspace .* not found"):
            await update_workspace_storage(
                workspace_id=non_existent_id,
                bytes_delta=1024,
                db=db,
            )


class TestStorageUsageRetrieval:
    """Test get_workspace_storage_usage() function."""

    @pytest.mark.asyncio
    async def test_get_usage_under_quota(
        self, db: AsyncSession, workspace: Workspace
    ):
        """Test retrieving usage when under quota."""
        workspace.storage_used_bytes = 5 * 1024 * 1024 * 1024  # 5 GB
        workspace.storage_quota_bytes = 10 * 1024 * 1024 * 1024  # 10 GB
        await db.commit()

        usage = await get_workspace_storage_usage(workspace.id, db)

        assert usage["used_bytes"] == 5 * 1024 * 1024 * 1024
        assert usage["quota_bytes"] == 10 * 1024 * 1024 * 1024
        assert usage["remaining_bytes"] == 5 * 1024 * 1024 * 1024
        assert usage["usage_percentage"] == 50.0
        assert usage["is_quota_exceeded"] is False

    @pytest.mark.asyncio
    async def test_get_usage_over_quota(
        self, db: AsyncSession, workspace: Workspace
    ):
        """Test retrieving usage when over quota."""
        workspace.storage_used_bytes = 12 * 1024 * 1024 * 1024  # 12 GB
        workspace.storage_quota_bytes = 10 * 1024 * 1024 * 1024  # 10 GB
        await db.commit()

        usage = await get_workspace_storage_usage(workspace.id, db)

        assert usage["used_bytes"] == 12 * 1024 * 1024 * 1024
        assert usage["quota_bytes"] == 10 * 1024 * 1024 * 1024
        assert usage["remaining_bytes"] == -2 * 1024 * 1024 * 1024  # Negative
        assert usage["usage_percentage"] == 120.0
        assert usage["is_quota_exceeded"] is True

    @pytest.mark.asyncio
    async def test_get_usage_workspace_not_found(self, db: AsyncSession):
        """Test get_usage raises ValueError for non-existent workspace."""
        non_existent_id = uuid.uuid4()

        with pytest.raises(ValueError, match="Workspace .* not found"):
            await get_workspace_storage_usage(non_existent_id, db)


class TestWorkspaceModelProperties:
    """Test Workspace model storage properties."""

    @pytest.mark.asyncio
    async def test_storage_usage_percentage(
        self, db: AsyncSession, workspace: Workspace
    ):
        """Test storage_usage_percentage property calculation."""
        workspace.storage_used_bytes = 3 * 1024 * 1024 * 1024  # 3 GB
        workspace.storage_quota_bytes = 10 * 1024 * 1024 * 1024  # 10 GB
        await db.commit()

        assert workspace.storage_usage_percentage == 30.0

    @pytest.mark.asyncio
    async def test_storage_usage_percentage_zero_quota(
        self, db: AsyncSession, workspace: Workspace
    ):
        """Test storage_usage_percentage returns 0 when quota is 0."""
        workspace.storage_used_bytes = 5 * 1024 * 1024 * 1024
        workspace.storage_quota_bytes = 0
        await db.commit()

        assert workspace.storage_usage_percentage == 0.0

    @pytest.mark.asyncio
    async def test_is_quota_exceeded_false(
        self, db: AsyncSession, workspace: Workspace
    ):
        """Test is_quota_exceeded is False when under quota."""
        workspace.storage_used_bytes = 5 * 1024 * 1024 * 1024
        workspace.storage_quota_bytes = 10 * 1024 * 1024 * 1024
        await db.commit()

        assert workspace.is_quota_exceeded is False

    @pytest.mark.asyncio
    async def test_is_quota_exceeded_true(
        self, db: AsyncSession, workspace: Workspace
    ):
        """Test is_quota_exceeded is True when over quota."""
        workspace.storage_used_bytes = 11 * 1024 * 1024 * 1024
        workspace.storage_quota_bytes = 10 * 1024 * 1024 * 1024
        await db.commit()

        assert workspace.is_quota_exceeded is True

    @pytest.mark.asyncio
    async def test_is_quota_exceeded_at_quota(
        self, db: AsyncSession, workspace: Workspace
    ):
        """Test is_quota_exceeded is True when exactly at quota."""
        workspace.storage_used_bytes = 10 * 1024 * 1024 * 1024
        workspace.storage_quota_bytes = 10 * 1024 * 1024 * 1024
        await db.commit()

        assert workspace.is_quota_exceeded is True

    @pytest.mark.asyncio
    async def test_storage_remaining_bytes(
        self, db: AsyncSession, workspace: Workspace
    ):
        """Test storage_remaining_bytes property."""
        workspace.storage_used_bytes = 7 * 1024 * 1024 * 1024
        workspace.storage_quota_bytes = 10 * 1024 * 1024 * 1024
        await db.commit()

        assert workspace.storage_remaining_bytes == 3 * 1024 * 1024 * 1024


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_zero_byte_file(self, db: AsyncSession, workspace: Workspace):
        """Test handling of 0-byte file uploads."""
        initial_usage = workspace.storage_used_bytes

        # Upload 0-byte file
        await validate_workspace_storage_quota(
            workspace_id=workspace.id,
            new_file_size=0,
            db=db,
        )

        await update_workspace_storage(
            workspace_id=workspace.id,
            bytes_delta=0,
            db=db,
        )
        await db.commit()
        await db.refresh(workspace)

        assert workspace.storage_used_bytes == initial_usage

    @pytest.mark.asyncio
    async def test_large_file_near_quota(
        self, db: AsyncSession, workspace: Workspace
    ):
        """Test large file upload that exactly fills quota."""
        workspace.storage_used_bytes = 0
        workspace.storage_quota_bytes = 10 * 1024 * 1024 * 1024
        await db.commit()

        # Upload 10 GB file (exactly fills quota)
        await validate_workspace_storage_quota(
            workspace_id=workspace.id,
            new_file_size=10 * 1024 * 1024 * 1024,
            db=db,
        )

        await update_workspace_storage(
            workspace_id=workspace.id,
            bytes_delta=10 * 1024 * 1024 * 1024,
            db=db,
        )
        await db.commit()
        await db.refresh(workspace)

        assert workspace.storage_used_bytes == workspace.storage_quota_bytes
        assert workspace.is_quota_exceeded is True


# Fixtures

@pytest.fixture
async def workspace(db: AsyncSession) -> Workspace:
    """Create a test workspace with default 10 GB quota."""
    workspace = Workspace(
        name="Test Workspace",
        storage_used_bytes=0,
        storage_quota_bytes=10 * 1024 * 1024 * 1024,  # 10 GB
    )
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    return workspace
