"""Reminder tracking service - prevents duplicate appointment reminder sends.

This service manages the appointment_reminders_sent table to ensure each
reminder type (15min, 30min, 1hr, 2hr, 24hr) is sent only once per appointment
per user, even when the scheduler runs multiple times within the tolerance window.

Functions:
    - was_reminder_sent: Check if a reminder was already sent
    - mark_reminder_sent: Record that a reminder was sent
    - cleanup_old_reminders: Delete old tracking records to prevent bloat

Example Usage:
    >>> from pazpaz.services.reminder_tracking_service import (
    ...     was_reminder_sent,
    ...     mark_reminder_sent,
    ... )
    >>>
    >>> # Before sending reminder
    >>> already_sent = await was_reminder_sent(
    ...     db, appointment_id, user_id, reminder_minutes=30
    ... )
    >>> if already_sent:
    ...     logger.info("reminder_already_sent", appointment_id=appointment_id)
    ...     return
    >>>
    >>> # Send reminder email...
    >>>
    >>> # After successful send
    >>> await mark_reminder_sent(db, appointment_id, user_id, reminder_minutes=30)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from pazpaz.core.logging import get_logger
from pazpaz.models.appointment_reminder import AppointmentReminderSent, ReminderType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


def _minutes_to_reminder_type(minutes: int) -> str:
    """
    Convert reminder minutes to reminder type string.

    Args:
        minutes: Number of minutes before appointment (15, 30, 60, 120, 1440)

    Returns:
        Reminder type string ('15min', '30min', '1hr', '2hr', '24hr')

    Raises:
        ValueError: If minutes is not a valid reminder interval
    """
    mapping = {
        15: ReminderType.MIN_15.value,
        30: ReminderType.MIN_30.value,
        60: ReminderType.HOUR_1.value,
        120: ReminderType.HOUR_2.value,
        1440: ReminderType.HOUR_24.value,
    }

    if minutes not in mapping:
        msg = (
            f"Invalid reminder interval: {minutes} minutes. "
            f"Valid values: {list(mapping.keys())}"
        )
        raise ValueError(msg)

    return mapping[minutes]


async def was_reminder_sent(
    db: AsyncSession,
    appointment_id: UUID,
    user_id: UUID,
    reminder_minutes: int,
) -> bool:
    """
    Check if a reminder was already sent for an appointment.

    This function queries the appointment_reminders_sent table to determine
    if a reminder of the specified type has already been sent to the user
    for the given appointment.

    Args:
        db: Database session
        appointment_id: ID of the appointment
        user_id: ID of the user who should receive the reminder
        reminder_minutes: Reminder interval in minutes (15, 30, 60, 120, 1440)

    Returns:
        True if reminder was already sent, False otherwise

    Raises:
        ValueError: If reminder_minutes is not a valid interval

    Example:
        >>> already_sent = await was_reminder_sent(
        ...     db,
        ...     appointment_id=uuid4(),
        ...     user_id=uuid4(),
        ...     reminder_minutes=30,
        ... )
        >>> if already_sent:
        ...     print("Reminder already sent, skipping")
    """
    try:
        # Convert minutes to reminder type
        reminder_type = _minutes_to_reminder_type(reminder_minutes)

        # Query for existing reminder record
        stmt = select(AppointmentReminderSent).where(
            AppointmentReminderSent.appointment_id == appointment_id,
            AppointmentReminderSent.user_id == user_id,
            AppointmentReminderSent.reminder_type == reminder_type,
        )

        result = await db.execute(stmt)
        reminder = result.scalar_one_or_none()

        return reminder is not None

    except ValueError:
        # Invalid reminder_minutes - let it propagate
        raise
    except Exception as e:
        # Log unexpected errors but don't fail the reminder send
        logger.error(
            "reminder_check_failed",
            appointment_id=str(appointment_id),
            user_id=str(user_id),
            reminder_minutes=reminder_minutes,
            error=str(e),
            exc_info=True,
        )
        # Return False to allow reminder send (fail-open for availability)
        return False


async def mark_reminder_sent(
    db: AsyncSession,
    appointment_id: UUID,
    user_id: UUID,
    reminder_minutes: int,
) -> None:
    """
    Mark a reminder as sent to prevent duplicate sends.

    This function inserts a record into the appointment_reminders_sent table
    to track that a reminder was sent. If a record already exists (due to
    race conditions), the unique constraint violation is handled gracefully.

    Note:
        This function does NOT commit the transaction. The caller is responsible
        for committing after all operations complete. This allows it to be used
        within larger transactions.

    Args:
        db: Database session
        appointment_id: ID of the appointment
        user_id: ID of the user who received the reminder
        reminder_minutes: Reminder interval in minutes (15, 30, 60, 120, 1440)

    Raises:
        ValueError: If reminder_minutes is not a valid interval

    Example:
        >>> # After successfully sending a reminder email
        >>> await mark_reminder_sent(
        ...     db,
        ...     appointment_id=appointment.id,
        ...     user_id=user.id,
        ...     reminder_minutes=30,
        ... )
        >>> await db.flush()  # Or let the caller commit
    """
    try:
        # Convert minutes to reminder type
        reminder_type = _minutes_to_reminder_type(reminder_minutes)

        # Create tracking record
        reminder_record = AppointmentReminderSent(
            appointment_id=appointment_id,
            user_id=user_id,
            reminder_type=reminder_type,
            sent_at=datetime.now(UTC),
        )

        db.add(reminder_record)
        await db.flush()  # Flush to database but don't commit

        logger.info(
            "reminder_marked_sent",
            appointment_id=str(appointment_id),
            user_id=str(user_id),
            reminder_type=reminder_type,
        )

    except IntegrityError as e:
        # Unique constraint violation - reminder already marked as sent
        # This can happen in race conditions where multiple workers try
        # to send the same reminder simultaneously
        await db.rollback()  # Must rollback after IntegrityError
        logger.warning(
            "reminder_already_marked_sent",
            appointment_id=str(appointment_id),
            user_id=str(user_id),
            reminder_minutes=reminder_minutes,
            error=str(e),
        )
        # Not an error - deduplication is working as intended

    except ValueError:
        # Invalid reminder_minutes - let it propagate
        raise

    except Exception as e:
        # Log unexpected errors
        logger.error(
            "reminder_marking_failed",
            appointment_id=str(appointment_id),
            user_id=str(user_id),
            reminder_minutes=reminder_minutes,
            error=str(e),
            exc_info=True,
        )
        # Don't raise - we already sent the reminder, just failed to track it
        # This is fail-open for availability (prefer duplicate over missed reminder)


async def cleanup_old_reminders(
    db: AsyncSession,
    days_old: int = 30,
) -> int:
    """
    Delete old reminder tracking records to prevent table bloat.

    This function removes reminder records older than the specified number
    of days. Since reminders are only relevant until the appointment occurs,
    old records can be safely deleted.

    Should be run periodically (e.g., weekly) via a scheduled task.

    Args:
        db: Database session
        days_old: Delete records older than this many days (default: 30)

    Returns:
        Number of records deleted

    Example:
        >>> # Run cleanup in a scheduled task
        >>> deleted_count = await cleanup_old_reminders(db, days_old=30)
        >>> logger.info("reminder_cleanup_completed", deleted=deleted_count)
    """
    try:
        # Calculate cutoff date
        cutoff_date = datetime.now(UTC) - timedelta(days=days_old)

        # Delete old records
        stmt = delete(AppointmentReminderSent).where(
            AppointmentReminderSent.sent_at < cutoff_date
        )

        result = await db.execute(stmt)
        deleted_count = result.rowcount

        await db.commit()

        logger.info(
            "reminder_cleanup_completed",
            deleted_count=deleted_count,
            cutoff_date=cutoff_date.isoformat(),
            days_old=days_old,
        )

        return deleted_count

    except Exception as e:
        await db.rollback()
        logger.error(
            "reminder_cleanup_failed",
            days_old=days_old,
            error=str(e),
            exc_info=True,
        )
        raise
