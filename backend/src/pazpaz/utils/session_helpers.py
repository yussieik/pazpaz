"""Utility functions for session note management and soft delete operations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.constants import SESSION_SOFT_DELETE_GRACE_PERIOD
from pazpaz.models.session import Session


def calculate_permanent_delete_after(deleted_at: datetime | None = None) -> datetime:
    """
    Calculate when a session should be permanently deleted.

    Sessions have a 30-day grace period after soft deletion during which
    they can be restored. This function calculates the expiration date.

    Args:
        deleted_at: Deletion timestamp (defaults to now if not provided)

    Returns:
        datetime: Timestamp when session will be permanently purged

    Example:
        permanent_delete_after = calculate_permanent_delete_after()
        # Returns: datetime.now(UTC) + 30 days
    """
    if deleted_at is None:
        deleted_at = datetime.now(UTC)
    return deleted_at + SESSION_SOFT_DELETE_GRACE_PERIOD


def is_grace_period_expired(permanent_delete_after: datetime) -> bool:
    """
    Check if the 30-day grace period for restoring a deleted session has expired.

    Args:
        permanent_delete_after: Timestamp when session will be permanently deleted

    Returns:
        bool: True if grace period has expired, False otherwise

    Example:
        if is_grace_period_expired(session.permanent_delete_after):
            raise HTTPException(
                status_code=410, detail="Cannot restore expired session"
            )
    """
    return datetime.now(UTC) > permanent_delete_after


def apply_soft_delete(
    session: Session,
    deleted_by_user_id: uuid.UUID,
    deletion_reason: str | None = None,
) -> None:
    """
    Apply soft delete to a session with all required fields.

    This function mutates the session object in place by setting:
    - deleted_at timestamp
    - deleted_by_user_id
    - deleted_reason (if provided)
    - permanent_delete_after (deleted_at + 30 days)

    NOTE: This does NOT commit the changes. Caller must call db.commit().

    Args:
        session: Session instance to soft delete
        deleted_by_user_id: UUID of user performing deletion
        deletion_reason: Optional reason for deletion (max 500 chars)

    Example:
        apply_soft_delete(
            session=session,
            deleted_by_user_id=current_user.id,
            deletion_reason="Duplicate entry, will recreate"
        )
        await db.commit()
    """
    now = datetime.now(UTC)
    session.deleted_at = now
    session.deleted_by_user_id = deleted_by_user_id
    session.deleted_reason = deletion_reason
    session.permanent_delete_after = calculate_permanent_delete_after(now)


def validate_session_not_amended(session: Session) -> None:
    """
    Validate that a session has not been amended.

    Amended sessions have medical-legal significance and cannot be deleted.
    This function raises an HTTP 422 error if the session has amendments.

    Args:
        session: Session to validate

    Raises:
        HTTPException: 422 if session has been amended (amendment_count > 0)

    Example:
        validate_session_not_amended(session)
        # Raises HTTPException if session.amendment_count > 0
    """
    if session.amendment_count > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot delete session note: it has been amended "
                f"{session.amendment_count} time(s). Amended notes have "
                "medical-legal significance and cannot be deleted."
            ),
        )


def clear_soft_delete_metadata(session: Session) -> None:
    """
    Clear soft delete metadata to restore a session.

    This function mutates the session object in place by clearing:
    - deleted_at
    - deleted_by_user_id
    - deleted_reason
    - permanent_delete_after

    NOTE: This does NOT commit the changes. Caller must call db.commit().

    Args:
        session: Session instance to restore

    Example:
        clear_soft_delete_metadata(session)
        await db.commit()
    """
    session.deleted_at = None
    session.deleted_by_user_id = None
    session.deleted_reason = None
    session.permanent_delete_after = None


async def get_active_sessions_for_appointment(
    db: AsyncSession,
    appointment_id: uuid.UUID,
) -> list[Session]:
    """
    Get all active (non-deleted) sessions for an appointment.

    This is a centralized query pattern to avoid duplication across endpoints.
    Used by both status transition validation and appointment deletion.

    Args:
        db: Database session
        appointment_id: Appointment ID to query sessions for

    Returns:
        List of active Session instances (empty list if none found)

    Example:
        sessions = await get_active_sessions_for_appointment(db, appointment_id)
        if sessions:
            # Handle sessions
            pass
    """
    query = select(Session).where(
        Session.appointment_id == appointment_id,
        Session.deleted_at.is_(None),
    )
    result = await db.execute(query)
    return list(result.scalars().all())
