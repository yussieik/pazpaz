"""Notification query service - database queries for scheduled notifications.

This service provides efficient batch queries for the arq background worker to
identify users and appointments that need notification emails sent. All queries
respect workspace scoping and use proper indexes for performance.

Design principles:
- Efficient batch queries (no N+1)
- Proper workspace scoping (privacy isolation)
- Timezone-aware time matching
- Indexed queries for performance
- Graceful handling of missing data

See: /docs/backend/NOTIFICATION_SCHEDULER_IMPLEMENTATION_PLAN.md
"""

from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import and_, distinct, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from pazpaz.core.logging import get_logger
from pazpaz.models.appointment import Appointment, AppointmentStatus
from pazpaz.models.user import User
from pazpaz.models.user_notification_settings import UserNotificationSettings
from pazpaz.models.workspace import Workspace

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


async def get_distinct_workspace_timezones(db: AsyncSession) -> list[str]:
    """
    Query all distinct timezone values from active workspaces.

    Returns:
        List of IANA timezone names (e.g., ['UTC', 'Asia/Jerusalem', 'America/New_York'])

    Example:
        >>> timezones = await get_distinct_workspace_timezones(db)
        >>> print(timezones)
        ['UTC', 'Asia/Jerusalem', 'America/New_York']

    Notes:
        - Only queries active workspaces (is_active=True)
        - Defaults NULL timezones to 'UTC'
        - Cached by scheduler for performance
    """
    stmt = select(distinct(Workspace.timezone)).where(Workspace.is_active == True)  # noqa: E712
    result = await db.execute(stmt)
    timezones = [tz or "UTC" for tz in result.scalars().all()]

    logger.debug(
        "distinct_timezones_fetched", timezone_count=len(timezones), timezones=timezones
    )

    return timezones


async def get_users_needing_session_notes_reminder(
    db: AsyncSession,
    current_time: time,
    timezone: str,
) -> list[User]:
    """
    Query users who need session notes reminders at the specified time in a specific timezone.

    Finds users where:
    - notes_reminder_enabled=True
    - email_enabled=True
    - notes_reminder_time matches current_time (hour:minute)
    - workspace.timezone matches the specified timezone

    Args:
        db: Async database session
        current_time: Current local time in the specified timezone (HH:MM format)
        timezone: IANA timezone name (e.g., 'Asia/Jerusalem', 'America/New_York')

    Returns:
        List of User objects with notification_settings and workspace preloaded

    Example:
        >>> # Check users in Israel timezone at 21:00 local time
        >>> users = await get_users_needing_session_notes_reminder(
        ...     db, time(21, 0), "Asia/Jerusalem"
        ... )
        >>> for user in users:
        ...     print(f"Remind {user.email} at 21:00 Israel time")

    Notes:
        - Respects workspace timezone for accurate reminder delivery
        - Uses partial index for efficient filtering
        - Defaults to UTC if workspace.timezone is NULL
    """
    # Format time as HH:MM string for database comparison
    time_str = current_time.strftime("%H:%M")

    logger.debug(
        "querying_session_notes_reminders",
        current_time=time_str,
        timezone=timezone,
    )

    # Query users with matching notification settings and timezone
    stmt = (
        select(User)
        .join(UserNotificationSettings, User.id == UserNotificationSettings.user_id)
        .join(Workspace, User.workspace_id == Workspace.id)
        .where(
            and_(
                UserNotificationSettings.email_enabled == True,  # noqa: E712
                UserNotificationSettings.notes_reminder_enabled == True,  # noqa: E712
                UserNotificationSettings.notes_reminder_time == time_str,
                Workspace.timezone == timezone,
            )
        )
        .options(
            joinedload(User.notification_settings),
            joinedload(User.workspace),
        )
    )

    result = await db.execute(stmt)
    users = list(result.scalars().unique().all())

    logger.info(
        "session_notes_reminders_query_complete",
        current_time=time_str,
        timezone=timezone,
        user_count=len(users),
    )

    return users


async def get_users_needing_daily_digest(
    db: AsyncSession,
    current_time: time,
    current_day: int,
    timezone: str,
) -> list[User]:
    """
    Query users who need daily digest emails at the specified time in a specific timezone.

    Finds users where:
    - digest_enabled=True
    - email_enabled=True
    - digest_time matches current_time (hour:minute)
    - workspace.timezone matches the specified timezone
    - current_day is in user's digest_days array

    Args:
        db: Async database session
        current_time: Current local time in the specified timezone (HH:MM format)
        current_day: Day of week in the specified timezone (0=Sunday, 1=Monday, ..., 6=Saturday)
        timezone: IANA timezone name (e.g., 'Asia/Jerusalem', 'America/New_York')

    Returns:
        List of User objects with notification_settings and workspace preloaded

    Example:
        >>> # Sunday at 08:00 in Israel timezone
        >>> users = await get_users_needing_daily_digest(
        ...     db, time(8, 0), 0, "Asia/Jerusalem"
        ... )
        >>> for user in users:
        ...     print(f"Send digest to {user.email}")

    Notes:
        - Respects workspace timezone for accurate digest delivery
        - Filters by digest_days array (0=Sunday, 6=Saturday)
        - Uses partial index for efficient filtering
        - Defaults to UTC if workspace.timezone is NULL
        - Day numbering changed: current_day is now 0=Sunday (was 0=Monday in old code)
    """
    # Format time as HH:MM string for database comparison
    time_str = current_time.strftime("%H:%M")

    logger.debug(
        "querying_daily_digest",
        current_time=time_str,
        current_day=current_day,
        timezone=timezone,
    )

    # Build query filtering by digest_days array
    # Use PostgreSQL's @> operator to check if array contains the current day
    from sqlalchemy import cast, type_coerce
    from sqlalchemy.dialects.postgresql import ARRAY

    conditions = [
        UserNotificationSettings.email_enabled == True,  # noqa: E712
        UserNotificationSettings.digest_enabled == True,  # noqa: E712
        UserNotificationSettings.digest_time == time_str,
        Workspace.timezone == timezone,
        # Check if current_day is in digest_days array
        UserNotificationSettings.digest_days.contains([current_day]),
    ]

    stmt = (
        select(User)
        .join(UserNotificationSettings, User.id == UserNotificationSettings.user_id)
        .join(Workspace, User.workspace_id == Workspace.id)
        .where(and_(*conditions))
        .options(
            joinedload(User.notification_settings),
            joinedload(User.workspace),
        )
    )

    result = await db.execute(stmt)
    users = list(result.scalars().unique().all())

    logger.info(
        "daily_digest_query_complete",
        current_time=time_str,
        current_day=current_day,
        timezone=timezone,
        user_count=len(users),
    )

    return users


async def get_users_needing_tomorrow_digest(
    db: AsyncSession,
    current_time: time,
    current_day: int,
    timezone: str,
) -> list[User]:
    """
    Query users who need tomorrow's digest emails at the specified time in a specific timezone.

    Finds users where:
    - tomorrow_digest_enabled=True
    - email_enabled=True
    - tomorrow_digest_time matches current_time (hour:minute)
    - workspace.timezone matches the specified timezone
    - current_day is in user's tomorrow_digest_days array

    Args:
        db: Async database session
        current_time: Current local time in the specified timezone (HH:MM format)
        current_day: Day of week in the specified timezone (0=Sunday, 1=Monday, ..., 6=Saturday)
        timezone: IANA timezone name (e.g., 'Asia/Jerusalem', 'America/New_York')

    Returns:
        List of User objects with notification_settings and workspace preloaded

    Example:
        >>> # Sunday at 20:00 in Israel timezone for Monday's schedule
        >>> users = await get_users_needing_tomorrow_digest(
        ...     db, time(20, 0), 0, "Asia/Jerusalem"
        ... )
        >>> for user in users:
        ...     print(f"Send tomorrow's digest to {user.email}")

    Notes:
        - Respects workspace timezone for accurate digest delivery
        - Filters by tomorrow_digest_days array (0=Sunday, 6=Saturday)
        - Uses partial index for efficient filtering
        - Defaults to UTC if workspace.timezone is NULL
        - Day numbering: current_day is 0=Sunday (not tomorrow's day)
    """
    # Format time as HH:MM string for database comparison
    time_str = current_time.strftime("%H:%M")

    logger.debug(
        "querying_tomorrow_digest",
        current_time=time_str,
        current_day=current_day,
        timezone=timezone,
    )

    # Build query filtering by tomorrow_digest_days array
    # Use PostgreSQL's @> operator to check if array contains the current day
    conditions = [
        UserNotificationSettings.email_enabled == True,  # noqa: E712
        UserNotificationSettings.tomorrow_digest_enabled == True,  # noqa: E712
        UserNotificationSettings.tomorrow_digest_time == time_str,
        Workspace.timezone == timezone,
        # Check if current_day is in tomorrow_digest_days array
        UserNotificationSettings.tomorrow_digest_days.contains([current_day]),
    ]

    stmt = (
        select(User)
        .join(UserNotificationSettings, User.id == UserNotificationSettings.user_id)
        .join(Workspace, User.workspace_id == Workspace.id)
        .where(and_(*conditions))
        .options(
            joinedload(User.notification_settings),
            joinedload(User.workspace),
        )
    )

    result = await db.execute(stmt)
    users = list(result.scalars().unique().all())

    logger.info(
        "tomorrow_digest_query_complete",
        current_time=time_str,
        current_day=current_day,
        timezone=timezone,
        user_count=len(users),
    )

    return users


async def get_appointments_needing_reminders(
    db: AsyncSession,
    current_time: datetime,
) -> list[tuple[Appointment, User]]:
    """
    Query appointments that need reminder emails sent now.

    Finds scheduled appointments where:
    - Appointment is in the future (not started yet)
    - Time until appointment matches user's reminder_minutes setting
    - User has reminder_enabled=True and email_enabled=True
    - Allows ±2 minute tolerance for matching

    Args:
        db: Async database session
        current_time: Current datetime (UTC)

    Returns:
        List of (Appointment, User) tuples with relationships preloaded

    Example:
        >>> now = datetime.now(UTC)
        >>> reminders = await get_appointments_needing_reminders(db, now)
        >>> for appointment, user in reminders:
        ...     minutes_until = (appointment.scheduled_start - now).seconds // 60
        ...     print(f"Remind {user.email} about appointment in {minutes_until} min")

    Notes:
        - TODO: Phase 4 will add deduplication tracking
        - Currently may send duplicate reminders if worker runs multiple times
        - Uses ±2 minute tolerance to handle worker scheduling variance
        - Valid reminder_minutes: 15, 30, 60, 120, 1440 (24 hours)
        - Fetches all upcoming appointments and filters in-memory
          (efficient for typical workload, < 1000 appointments per hour)
    """
    logger.debug(
        "querying_appointment_reminders",
        current_time=current_time.isoformat(),
    )

    # Query scheduled appointments in the next 24 hours (max reminder window)
    # We'll filter by exact timing in Python to handle ±2 minute tolerance
    from datetime import timedelta

    max_window = current_time + timedelta(hours=24, minutes=5)

    stmt = (
        select(Appointment)
        .join(User, Appointment.workspace_id == User.workspace_id)
        .join(UserNotificationSettings, User.id == UserNotificationSettings.user_id)
        .where(
            and_(
                Appointment.status == AppointmentStatus.SCHEDULED,
                Appointment.scheduled_start > current_time,
                Appointment.scheduled_start <= max_window,
                UserNotificationSettings.email_enabled == True,  # noqa: E712
                UserNotificationSettings.reminder_enabled == True,  # noqa: E712
            )
        )
        .options(
            joinedload(Appointment.client),
            joinedload(Appointment.service),
            joinedload(Appointment.location),
            joinedload(Appointment.workspace),
        )
    )

    result = await db.execute(stmt)
    appointments = list(result.scalars().unique().all())

    logger.debug(
        "appointments_fetched",
        appointment_count=len(appointments),
    )

    # Now match appointments to users with correct reminder timing
    reminders: list[tuple[Appointment, User]] = []

    for appointment in appointments:
        # Get users in this workspace with reminder settings
        user_stmt = (
            select(User)
            .join(UserNotificationSettings, User.id == UserNotificationSettings.user_id)
            .where(
                and_(
                    User.workspace_id == appointment.workspace_id,
                    UserNotificationSettings.email_enabled == True,  # noqa: E712
                    UserNotificationSettings.reminder_enabled == True,  # noqa: E712
                )
            )
            .options(joinedload(User.notification_settings))
        )

        user_result = await db.execute(user_stmt)
        users = list(user_result.scalars().unique().all())

        # Calculate minutes until appointment
        time_delta = appointment.scheduled_start - current_time
        minutes_until = int(time_delta.total_seconds() / 60)

        # Match against user's reminder_minutes setting with ±2 minute tolerance
        for user in users:
            if (
                user.notification_settings
                and user.notification_settings.reminder_minutes
            ):
                target_minutes = user.notification_settings.reminder_minutes
                # Allow ±2 minute tolerance
                if abs(minutes_until - target_minutes) <= 2:
                    reminders.append((appointment, user))
                    logger.debug(
                        "appointment_reminder_matched",
                        appointment_id=str(appointment.id),
                        user_id=str(user.id),
                        minutes_until=minutes_until,
                        target_minutes=target_minutes,
                    )

    logger.info(
        "appointment_reminders_query_complete",
        current_time=current_time.isoformat(),
        reminder_count=len(reminders),
    )

    return reminders
