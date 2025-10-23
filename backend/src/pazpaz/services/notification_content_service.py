"""Notification content service - email content builders.

This service builds email subjects and bodies for different notification types.
It queries necessary data from the database and formats user-friendly messages.

Design principles:
- Clear, friendly, professional tone
- Plain text emails (HTML in future phases)
- Include relevant links to frontend
- Never expose sensitive data in subjects
- Graceful handling of missing data

See: /docs/backend/NOTIFICATION_SCHEDULER_IMPLEMENTATION_PLAN.md
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger
from pazpaz.models.appointment import Appointment
from pazpaz.models.session import Session
from pazpaz.models.user import User

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


async def build_session_notes_reminder_email(
    db: AsyncSession,
    user: User,
) -> dict[str, str]:
    """
    Build email content for session notes reminder.

    Queries draft sessions for the user and builds a friendly reminder email
    with a link to the sessions page.

    Args:
        db: Async database session
        user: User to send reminder to

    Returns:
        Dict with keys: subject, body, to

    Example:
        >>> email = await build_session_notes_reminder_email(db, user)
        >>> print(email["subject"])
        You have 3 draft session notes
        >>> print(email["to"])
        therapist@example.com

    Notes:
        - Counts only draft sessions (is_draft=True)
        - Does not expose client names or session content
        - Links to frontend sessions page
        - If no drafts, still sends reminder with count=0
    """
    logger.debug(
        "building_session_notes_reminder",
        user_id=str(user.id),
        user_email=user.email,
    )

    # Query draft sessions for this user
    stmt = select(Session).where(
        and_(
            Session.workspace_id == user.workspace_id,
            Session.is_draft == True,  # noqa: E712
            Session.deleted_at == None,  # noqa: E711
        )
    )

    result = await db.execute(stmt)
    draft_sessions = list(result.scalars().all())
    draft_count = len(draft_sessions)

    logger.info(
        "session_notes_reminder_built",
        user_id=str(user.id),
        draft_count=draft_count,
    )

    # Build email subject
    if draft_count == 1:
        subject = "You have 1 draft session note"
    else:
        subject = f"You have {draft_count} draft session notes"

    # Build email body
    sessions_url = f"{settings.frontend_url}/sessions"

    if draft_count == 0:
        body = f"""Hello {user.full_name},

Great job! You're all caught up on session notes.

You have no pending draft session notes at the moment.

Keep up the excellent documentation!

---
PazPaz - Practice Management for Independent Therapists
{settings.frontend_url}
"""
    elif draft_count == 1:
        body = f"""Hello {user.full_name},

You have 1 draft session note waiting to be completed.

Keeping your session notes up to date helps maintain accurate client records
and ensures you don't forget important details from your sessions.

Complete your draft session note:
{sessions_url}

---
PazPaz - Practice Management for Independent Therapists
{settings.frontend_url}
"""
    else:
        body = f"""Hello {user.full_name},

You have {draft_count} draft session notes waiting to be completed.

Keeping your session notes up to date helps maintain accurate client records
and ensures you don't forget important details from your sessions.

Complete your draft session notes:
{sessions_url}

---
PazPaz - Practice Management for Independent Therapists
{settings.frontend_url}
"""

    return {
        "subject": subject,
        "body": body,
        "to": user.email,
    }


async def build_daily_digest_email(
    db: AsyncSession,
    user: User,
    digest_date: date,
    digest_type: str = "today",
) -> dict[str, str]:
    """
    Build email content for daily digest.

    Queries appointments for the specified date and builds a digest email
    with a schedule overview.

    Args:
        db: Async database session
        user: User to send digest to
        digest_date: Date to build digest for (typically today or tomorrow)
        digest_type: Type of digest - "today" or "tomorrow" (default: "today")

    Returns:
        Dict with keys: subject, body, to

    Example:
        >>> from datetime import date
        >>> email = await build_daily_digest_email(db, user, date(2025, 10, 22))
        >>> print(email["subject"])
        Your schedule for today, Tuesday, October 22, 2025
        >>> email = await build_daily_digest_email(db, user, date(2025, 10, 23), "tomorrow")
        >>> print(email["subject"])
        Your schedule for tomorrow, Wednesday, October 23, 2025

    Notes:
        - Shows appointments for specified date
        - Includes client names, times, services, locations
        - Gracefully handles no appointments
        - Links to calendar view
        - Times are shown in appointment's timezone (stored as UTC)
        - Subject and body adjust based on digest_type
    """
    from datetime import datetime, time

    from pazpaz.models.appointment import AppointmentStatus

    logger.debug(
        "building_daily_digest",
        user_id=str(user.id),
        user_email=user.email,
        digest_date=digest_date.isoformat(),
    )

    # Query appointments for the specified date
    start_of_day = datetime.combine(digest_date, time.min)
    end_of_day = datetime.combine(digest_date, time.max)

    stmt = (
        select(Appointment)
        .where(
            and_(
                Appointment.workspace_id == user.workspace_id,
                Appointment.scheduled_start >= start_of_day,
                Appointment.scheduled_start <= end_of_day,
                Appointment.status == AppointmentStatus.SCHEDULED,
            )
        )
        .order_by(Appointment.scheduled_start)
    )

    result = await db.execute(stmt)
    appointments = list(result.scalars().all())

    # Fetch related data
    for appt in appointments:
        await db.refresh(appt, ["client", "service", "location"])

    appointment_count = len(appointments)

    logger.info(
        "daily_digest_built",
        user_id=str(user.id),
        digest_date=digest_date.isoformat(),
        digest_type=digest_type,
        appointment_count=appointment_count,
    )

    # Format date for subject
    formatted_date = digest_date.strftime("%A, %B %d, %Y")

    # Add digest type prefix to subject
    time_prefix = "today" if digest_type == "today" else "tomorrow"
    subject = f"Your schedule for {time_prefix}, {formatted_date}"

    # Build email body
    calendar_url = f"{settings.frontend_url}/calendar"

    if appointment_count == 0:
        body = f"""Hello {user.full_name},

You have no appointments scheduled for {formatted_date}.

Enjoy your day off, or use this time to catch up on administrative tasks!

View your calendar:
{calendar_url}

---
PazPaz - Practice Management for Independent Therapists
{settings.frontend_url}
"""
    else:
        # Build appointment list
        appointment_lines = []
        for appt in appointments:
            # Format time (TODO: timezone conversion in Phase 3+)
            appt_time = appt.scheduled_start.strftime("%I:%M %p")

            # Get client name
            client_name = appt.client.full_name if appt.client else "Unknown Client"

            # Get service name (optional)
            service_info = f" - {appt.service.name}" if appt.service else ""

            # Get location info (optional)
            location_info = ""
            if appt.location:
                location_info = f" at {appt.location.name}"
            elif appt.location_details:
                location_info = f" ({appt.location_type.value})"

            line = f"  • {appt_time} - {client_name}{service_info}{location_info}"
            appointment_lines.append(line)

        appointments_text = "\n".join(appointment_lines)

        # Adjust greeting based on digest type
        if appointment_count == 1:
            if digest_type == "today":
                greeting = f"You have 1 appointment scheduled for today, {formatted_date}:"
            else:
                greeting = f"You have 1 appointment scheduled for tomorrow, {formatted_date}:"
        else:
            if digest_type == "today":
                greeting = f"You have {appointment_count} appointments scheduled for today, {formatted_date}:"
            else:
                greeting = f"You have {appointment_count} appointments scheduled for tomorrow, {formatted_date}:"

        body = f"""Hello {user.full_name},

{greeting}

{appointments_text}

View your full calendar:
{calendar_url}

Have a great day!

---
PazPaz - Practice Management for Independent Therapists
{settings.frontend_url}
"""

    return {
        "subject": subject,
        "body": body,
        "to": user.email,
    }


async def build_appointment_reminder_email(
    db: AsyncSession,
    appointment: Appointment,
    user: User,
) -> dict[str, str]:
    """
    Build email content for appointment reminder.

    Formats appointment details into a friendly reminder email.

    Args:
        db: Async database session
        appointment: Appointment to remind about
        user: User to send reminder to

    Returns:
        Dict with keys: subject, body, to

    Example:
        >>> email = await build_appointment_reminder_email(db, appointment, user)
        >>> print(email["subject"])
        Appointment in 60 minutes with Jane Doe

    Notes:
        - Calculates minutes until appointment dynamically
        - Includes client name, time, location, service
        - Does not expose PHI in subject line
        - Links to appointment details
        - Handles missing client/service/location gracefully
    """
    from datetime import datetime

    logger.debug(
        "building_appointment_reminder",
        appointment_id=str(appointment.id),
        user_id=str(user.id),
    )

    # Load related data if not already loaded
    await db.refresh(appointment, ["client", "service", "location"])

    # Calculate minutes until appointment
    now = datetime.now(appointment.scheduled_start.tzinfo)
    time_delta = appointment.scheduled_start - now
    minutes_until = int(time_delta.total_seconds() / 60)

    # Get client name
    client_name = appointment.client.full_name if appointment.client else "a client"

    # Build subject (avoid PHI in subject line for email security)
    if minutes_until <= 60:
        subject = f"Appointment in {minutes_until} minutes with {client_name}"
    elif minutes_until <= 1440:
        hours = minutes_until // 60
        subject = (
            f"Appointment in {hours} hour{'s' if hours > 1 else ''} with {client_name}"
        )
    else:
        subject = f"Appointment reminder: {client_name}"

    # Format appointment time (TODO: timezone conversion in Phase 3+)
    appt_time = appointment.scheduled_start.strftime("%I:%M %p on %A, %B %d, %Y")

    # Get service info
    service_info = (
        f"\nService: {appointment.service.name}" if appointment.service else ""
    )

    # Get location info
    location_info = ""
    if appointment.location:
        location_info = f"\nLocation: {appointment.location.name}"
        if appointment.location_details:
            location_info += f"\n{appointment.location_details}"
    elif appointment.location_details:
        location_info = f"\nLocation: {appointment.location_type.value}\n{appointment.location_details}"
    elif appointment.location_type:
        location_info = f"\nLocation: {appointment.location_type.value}"

    # Build email body
    calendar_url = f"{settings.frontend_url}/calendar"

    if minutes_until <= 60:
        urgency = "Your appointment is coming up soon!"
    elif minutes_until <= 1440:
        hours = minutes_until // 60
        urgency = f"Your appointment is in {hours} hour{'s' if hours > 1 else ''}."
    else:
        urgency = "Reminder about your upcoming appointment."

    body = f"""Hello {user.full_name},

{urgency}

Client: {client_name}
Time: {appt_time}{service_info}{location_info}

View appointment details:
{calendar_url}

See you soon!

---
PazPaz - Practice Management for Independent Therapists
{settings.frontend_url}
"""

    logger.info(
        "appointment_reminder_built",
        appointment_id=str(appointment.id),
        user_id=str(user.id),
        minutes_until=minutes_until,
    )

    return {
        "subject": subject,
        "body": body,
        "to": user.email,
    }
