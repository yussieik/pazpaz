"""
Minimal storage quota race condition fix tests.

Security Requirement: Concurrent uploads must not bypass quota limits (CWE-362).

This is a focused test suite that verifies the atomic quota reservation fix works.
"""

import asyncio
import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.workspace import Workspace
from pazpaz.utils.storage_quota import (
    StorageQuotaExceededError,
    validate_workspace_storage_quota,
)


async def set_workspace_storage(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    quota_bytes: int,
    used_bytes: int,
) -> None:
    """Helper to reliably set workspace storage values in tests."""
    from sqlalchemy import update as sql_update

    stmt = (
        sql_update(Workspace)
        .where(Workspace.id == workspace_id)
        .values(storage_quota_bytes=quota_bytes, storage_used_bytes=used_bytes)
    )
    await db.execute(stmt)
    await db.commit()


@pytest_asyncio.fixture
async def db_session_factory(test_db_engine) -> Any:
    """Provide a database session factory for concurrent tests using test DB."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    # Create sessionmaker using test database engine
    test_session_factory = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    def _factory() -> Any:
        """Create a new database session context manager from test engine."""
        return test_session_factory()

    return _factory


class TestAtomicQuotaReservation:
    """Test atomic quota reservation with row-level locking."""

    @pytest.mark.asyncio
    async def test_quota_reserved_atomically(
        self, db_session: AsyncSession, test_workspace: Workspace
    ) -> None:
        """Quota should be reserved immediately during validation."""
        initial_usage = test_workspace.storage_used_bytes
        file_size = 1000

        # Reserve quota
        await validate_workspace_storage_quota(
            workspace_id=test_workspace.id,
            new_file_size=file_size,
            db=db_session,
        )

        # Flush changes to database (workspace object was modified in-place)
        await db_session.flush()

        # Quota should be incremented immediately (before explicit commit)
        await db_session.refresh(test_workspace)
        assert test_workspace.storage_used_bytes == initial_usage + file_size

        # Clean up for next test
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_quota_reservation_rolled_back_on_error(
        self, db_session: AsyncSession, test_workspace: Workspace
    ) -> None:
        """Quota reservation should roll back if transaction fails."""
        initial_usage = test_workspace.storage_used_bytes
        file_size = 1000

        try:
            # Reserve quota
            await validate_workspace_storage_quota(
                workspace_id=test_workspace.id,
                new_file_size=file_size,
                db=db_session,
            )

            # Simulate error (e.g., S3 upload failure)
            raise RuntimeError("Simulated upload failure")

        except RuntimeError:
            # Rollback transaction
            await db_session.rollback()

        # Quota should be restored to initial value
        await db_session.refresh(test_workspace)
        assert test_workspace.storage_used_bytes == initial_usage

    @pytest.mark.asyncio
    async def test_concurrent_uploads_cannot_bypass_quota(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        db_session_factory: Any,
    ) -> None:
        """Multiple concurrent uploads should not bypass quota limit.

        This is the CORE race condition test. Before the fix, multiple
        concurrent uploads could all pass validation and all upload,
        exceeding the quota. After the fix, only one should succeed.
        """
        # Set quota to allow only 2000 bytes
        await set_workspace_storage(db_session, test_workspace.id, 2000, 0)

        file_size = 1500  # Each file is 1500 bytes
        workspace_id = test_workspace.id

        async def upload_task(task_id: int) -> dict[str, Any]:
            """Simulate a concurrent upload task."""
            # Each task gets its own database session
            async with db_session_factory() as task_db:
                try:
                    # Validate and reserve quota (locks workspace row)
                    await validate_workspace_storage_quota(
                        workspace_id=workspace_id,
                        new_file_size=file_size,
                        db=task_db,
                    )

                    # Simulate S3 upload delay
                    await asyncio.sleep(0.05)

                    # Commit transaction (quota reservation becomes permanent)
                    await task_db.commit()

                    return {"task_id": task_id, "success": True, "error": None}

                except StorageQuotaExceededError as e:
                    await task_db.rollback()
                    return {"task_id": task_id, "success": False, "error": str(e)}

                except Exception as e:
                    await task_db.rollback()
                    return {"task_id": task_id, "success": False, "error": str(e)}
                finally:
                    await task_db.close()

        # Run 3 concurrent upload tasks (total would be 4500 bytes > 2000 quota)
        results = await asyncio.gather(
            upload_task(1),
            upload_task(2),
            upload_task(3),
        )

        # Count successes and failures
        success_count = sum(1 for r in results if r["success"])
        failure_count = sum(1 for r in results if not r["success"])

        # Only 1 upload should succeed (quota allows 1500 bytes, not 4500)
        # This verifies that the row lock prevents concurrent quota bypass
        assert success_count == 1, (
            f"Expected exactly 1 successful upload, got {success_count}. "
            f"This means the race condition is NOT fixed. "
            f"Results: {results}"
        )
        assert failure_count == 2, (
            f"Expected exactly 2 failed uploads, got {failure_count}. "
            f"Results: {results}"
        )

        # Verify final storage usage matches expectations
        await db_session.refresh(test_workspace)
        assert test_workspace.storage_used_bytes == file_size, (
            f"Expected storage usage of {file_size} bytes, "
            f"got {test_workspace.storage_used_bytes} bytes"
        )

        # Clean up
        test_workspace.storage_used_bytes = 0
        test_workspace.storage_quota_bytes = 10 * 1024 * 1024 * 1024
        await db_session.commit()


class TestQuotaExceededError:
    """Test quota exceeded error handling."""

    @pytest.mark.asyncio
    async def test_quota_exceeded_raises_error(
        self, db_session: AsyncSession, test_workspace: Workspace
    ) -> None:
        """Should raise error if quota would be exceeded."""
        # Set quota to 1000 bytes, usage to 500
        await set_workspace_storage(db_session, test_workspace.id, 1000, 500)

        # Try to upload 600 bytes (would exceed quota)
        with pytest.raises(StorageQuotaExceededError) as exc_info:
            await validate_workspace_storage_quota(
                workspace_id=test_workspace.id,
                new_file_size=600,
                db=db_session,
            )

        error_msg = str(exc_info.value).lower()
        assert "quota exceeded" in error_msg
        # Note: Error message shows MB conversions, actual validation logic is correct

        # Clean up
        await db_session.rollback()
        test_workspace.storage_used_bytes = 0
        test_workspace.storage_quota_bytes = 10 * 1024 * 1024 * 1024
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_quota_exactly_at_limit_allowed(
        self, db_session: AsyncSession, test_workspace: Workspace
    ) -> None:
        """Upload that exactly fills quota should be allowed."""
        await set_workspace_storage(db_session, test_workspace.id, 1000, 500)

        # Upload exactly 500 bytes (fills quota to limit)
        await validate_workspace_storage_quota(
            workspace_id=test_workspace.id,
            new_file_size=500,
            db=db_session,
        )

        # Should succeed without error
        await db_session.flush()
        await db_session.refresh(test_workspace)
        assert test_workspace.storage_used_bytes == 1000

        # Clean up
        await db_session.rollback()
        test_workspace.storage_used_bytes = 0
        test_workspace.storage_quota_bytes = 10 * 1024 * 1024 * 1024
        await db_session.commit()


class TestRaceConditionRegression:
    """Regression tests to ensure race condition stays fixed."""

    @pytest.mark.asyncio
    async def test_sequential_uploads_respect_quota(
        self, db_session: AsyncSession, test_workspace: Workspace
    ) -> None:
        """Sequential uploads should correctly accumulate quota usage."""
        await set_workspace_storage(db_session, test_workspace.id, 10000, 0)

        # Upload 1
        await validate_workspace_storage_quota(
            workspace_id=test_workspace.id,
            new_file_size=3000,
            db=db_session,
        )
        await db_session.commit()

        # Upload 2
        await validate_workspace_storage_quota(
            workspace_id=test_workspace.id,
            new_file_size=3000,
            db=db_session,
        )
        await db_session.commit()

        # Upload 3
        await validate_workspace_storage_quota(
            workspace_id=test_workspace.id,
            new_file_size=3000,
            db=db_session,
        )
        await db_session.commit()

        # Total usage should be 9000
        await db_session.refresh(test_workspace)
        assert test_workspace.storage_used_bytes == 9000

        # Upload 4 should fail (9000 + 3000 > 10000)
        with pytest.raises(StorageQuotaExceededError):
            await validate_workspace_storage_quota(
                workspace_id=test_workspace.id,
                new_file_size=3000,
                db=db_session,
            )

        # Clean up
        await db_session.rollback()
        test_workspace.storage_used_bytes = 0
        test_workspace.storage_quota_bytes = 10 * 1024 * 1024 * 1024
        await db_session.commit()
