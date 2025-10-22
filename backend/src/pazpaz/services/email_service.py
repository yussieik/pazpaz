"""Email service for sending magic links and notifications."""

from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


async def send_magic_link_email(email: str, token: str) -> None:
    """
    Send magic link email to user.

    Sends email via SMTP (MailHog in development, production SMTP in prod).

    Args:
        email: Recipient email address
        token: Magic link token

    Raises:
        Exception: If email sending fails
    """
    # Construct magic link URL
    base_url = settings.frontend_url
    magic_link = f"{base_url}/auth/verify?token={token}"

    # Create email message
    message = EmailMessage()
    message["From"] = "PazPaz <noreply@pazpaz.app>"
    message["To"] = email
    message["Subject"] = "Your PazPaz Login Link"

    # Email body (plain text)
    message.set_content(f"""
Hello,

Click the link below to log in to PazPaz:

{magic_link}

This link will expire in 10 minutes.

If you didn't request this, you can safely ignore this email.

---
PazPaz - Practice Management for Independent Therapists
""")

    # Send via SMTP
    try:
        async with aiosmtplib.SMTP(
            hostname=settings.smtp_host,
            port=settings.smtp_port,
        ) as smtp:
            # Authenticate if credentials provided (not needed for MailHog)
            if settings.smtp_user:
                await smtp.login(settings.smtp_user, settings.smtp_password)

            await smtp.send_message(message)

        logger.info(
            "magic_link_sent",
            email=email,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
        )

        # Also log to console in debug mode for convenience
        if settings.debug:
            logger.info(
                "magic_link_debug_info",
                email=email,
                mailhog_ui="http://localhost:8025",
                magic_link=magic_link,
            )

    except Exception as e:
        logger.error(
            "failed_to_send_email",
            email=email,
            error=str(e),
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            exc_info=True,
        )
        raise


async def send_invitation_email(email: str, invitation_url: str) -> None:
    """
    Send invitation email to new therapist.

    Sends email via SMTP (MailHog in development, production SMTP in prod).

    Args:
        email: Recipient email address
        invitation_url: Full invitation URL with token

    Raises:
        Exception: If email sending fails
    """
    # Create email message
    message = EmailMessage()
    message["From"] = "PazPaz <noreply@pazpaz.app>"
    message["To"] = email
    message["Subject"] = "Invitation to Join PazPaz"

    # Email body (plain text)
    message.set_content(f"""
Hello,

You've been invited to join PazPaz, a practice management platform
for independent therapists.

Click the link below to accept your invitation and set up your workspace:

{invitation_url}

This invitation link will expire in 7 days.

If you didn't expect this invitation, you can safely ignore this email.

---
PazPaz - Practice Management for Independent Therapists
""")

    # Send via SMTP
    try:
        async with aiosmtplib.SMTP(
            hostname=settings.smtp_host,
            port=settings.smtp_port,
        ) as smtp:
            # Authenticate if credentials provided (not needed for MailHog)
            if settings.smtp_user:
                await smtp.login(settings.smtp_user, settings.smtp_password)

            await smtp.send_message(message)

        logger.info(
            "invitation_email_sent",
            email=email,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
        )

        # Also log to console in debug mode for convenience
        if settings.debug:
            logger.info(
                "invitation_email_debug_info",
                email=email,
                mailhog_ui="http://localhost:8025",
                invitation_url=invitation_url,
            )

    except Exception as e:
        logger.error(
            "failed_to_send_invitation_email",
            email=email,
            error=str(e),
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            exc_info=True,
        )
        raise


async def send_welcome_email(email: str, full_name: str) -> None:
    """
    Send welcome email to new user.

    Args:
        email: Recipient email address
        full_name: User's full name
    """
    logger.info("welcome_email", email=email, full_name=full_name)
    # TODO: Implement welcome email
    pass


async def send_session_notes_reminder(
    email: str,
    draft_count: int,
    frontend_url: str,
) -> None:
    """
    Send session notes reminder email to user.

    Reminds therapist about draft session notes that need to be completed.

    Args:
        email: Recipient email address
        draft_count: Number of draft session notes
        frontend_url: Frontend base URL for links

    Raises:
        Exception: If email sending fails

    Example:
        >>> await send_session_notes_reminder(
        ...     email="therapist@example.com",
        ...     draft_count=3,
        ...     frontend_url="https://app.pazpaz.com"
        ... )
    """
    # Build sessions page URL
    sessions_url = f"{frontend_url}/sessions"

    # Create email message
    message = EmailMessage()
    message["From"] = "PazPaz <noreply@pazpaz.app>"
    message["To"] = email
    message["Subject"] = (
        f"You have {draft_count} draft session note{'s' if draft_count != 1 else ''}"
    )

    # Email body (plain text)
    if draft_count == 0:
        body_text = f"""Hello,

Great job! You're all caught up on session notes.

You have no pending draft session notes at the moment.

Keep up the excellent documentation!

---
PazPaz - Practice Management for Independent Therapists
{frontend_url}
"""
    elif draft_count == 1:
        body_text = f"""Hello,

You have 1 draft session note waiting to be completed.

Keeping your session notes up to date helps maintain accurate client records
and ensures you don't forget important details from your sessions.

Complete your draft session note:
{sessions_url}

---
PazPaz - Practice Management for Independent Therapists
{frontend_url}
"""
    else:
        body_text = f"""Hello,

You have {draft_count} draft session notes waiting to be completed.

Keeping your session notes up to date helps maintain accurate client records
and ensures you don't forget important details from your sessions.

Complete your draft session notes:
{sessions_url}

---
PazPaz - Practice Management for Independent Therapists
{frontend_url}
"""

    message.set_content(body_text)

    # Send via SMTP
    try:
        async with aiosmtplib.SMTP(
            hostname=settings.smtp_host,
            port=settings.smtp_port,
        ) as smtp:
            # Authenticate if credentials provided (not needed for MailHog)
            if settings.smtp_user:
                await smtp.login(settings.smtp_user, settings.smtp_password)

            await smtp.send_message(message)

        logger.info(
            "session_notes_reminder_sent",
            email=email,
            draft_count=draft_count,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
        )

        # Also log to console in debug mode for convenience
        if settings.debug:
            logger.info(
                "session_notes_reminder_debug_info",
                email=email,
                draft_count=draft_count,
                mailhog_ui="http://localhost:8025",
            )

    except Exception as e:
        logger.error(
            "failed_to_send_session_notes_reminder",
            email=email,
            draft_count=draft_count,
            error=str(e),
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            exc_info=True,
        )
        raise


async def send_daily_digest(
    email: str,
    appointments: list[dict],
    date_str: str,
    frontend_url: str,
) -> None:
    """
    Send daily digest email with appointment schedule.

    Sends a summary of appointments scheduled for a specific date.

    Args:
        email: Recipient email address
        appointments: List of appointment dicts with keys:
            - time: Formatted time string (e.g., "02:30 PM")
            - client_name: Client's full name
            - service: Service name (optional)
            - location: Location info (optional)
        date_str: Formatted date string (e.g., "Monday, October 22, 2025")
        frontend_url: Frontend base URL for links

    Raises:
        Exception: If email sending fails

    Example:
        >>> await send_daily_digest(
        ...     email="therapist@example.com",
        ...     appointments=[
        ...         {"time": "10:00 AM", "client_name": "Jane Doe", "service": "Massage"},
        ...         {"time": "02:00 PM", "client_name": "John Smith"},
        ...     ],
        ...     date_str="Monday, October 22, 2025",
        ...     frontend_url="https://app.pazpaz.com"
        ... )
    """
    # Build calendar page URL
    calendar_url = f"{frontend_url}/calendar"

    # Create email message
    message = EmailMessage()
    message["From"] = "PazPaz <noreply@pazpaz.app>"
    message["To"] = email
    message["Subject"] = f"Your schedule for {date_str}"

    # Build appointment list
    if not appointments:
        appointment_text = "You have no appointments scheduled."
    else:
        lines = []
        for appt in appointments:
            time = appt.get("time", "Unknown time")
            client = appt.get("client_name", "Unknown client")
            service = appt.get("service", "")
            location = appt.get("location", "")

            line = f"  • {time} - {client}"
            if service:
                line += f" - {service}"
            if location:
                line += f" at {location}"

            lines.append(line)

        appointment_text = "\n".join(lines)

    # Email body (plain text)
    if not appointments:
        body_text = f"""Hello,

You have no appointments scheduled for {date_str}.

Enjoy your day off, or use this time to catch up on administrative tasks!

View your calendar:
{calendar_url}

---
PazPaz - Practice Management for Independent Therapists
{frontend_url}
"""
    else:
        count = len(appointments)
        greeting = f"You have {count} appointment{'s' if count != 1 else ''} scheduled for {date_str}:"

        body_text = f"""Hello,

{greeting}

{appointment_text}

View your full calendar:
{calendar_url}

Have a great day!

---
PazPaz - Practice Management for Independent Therapists
{frontend_url}
"""

    message.set_content(body_text)

    # Send via SMTP
    try:
        async with aiosmtplib.SMTP(
            hostname=settings.smtp_host,
            port=settings.smtp_port,
        ) as smtp:
            # Authenticate if credentials provided (not needed for MailHog)
            if settings.smtp_user:
                await smtp.login(settings.smtp_user, settings.smtp_password)

            await smtp.send_message(message)

        logger.info(
            "daily_digest_sent",
            email=email,
            appointment_count=len(appointments),
            date_str=date_str,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
        )

        # Also log to console in debug mode for convenience
        if settings.debug:
            logger.info(
                "daily_digest_debug_info",
                email=email,
                appointment_count=len(appointments),
                mailhog_ui="http://localhost:8025",
            )

    except Exception as e:
        logger.error(
            "failed_to_send_daily_digest",
            email=email,
            appointment_count=len(appointments),
            error=str(e),
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            exc_info=True,
        )
        raise


async def send_appointment_reminder(
    email: str,
    appointment_data: dict,
    minutes_until: int,
) -> None:
    """
    Send appointment reminder email to user.

    Reminds therapist about an upcoming appointment.

    Args:
        email: Recipient email address
        appointment_data: Dict with appointment details:
            - appointment_id: UUID string (optional, for logging)
            - client_name: Client's full name
            - time: Formatted appointment time (e.g., "02:30 PM on Monday, Oct 22")
            - service: Service name (optional)
            - location: Location info (optional)
        minutes_until: Minutes until appointment starts

    Raises:
        Exception: If email sending fails

    Example:
        >>> await send_appointment_reminder(
        ...     email="therapist@example.com",
        ...     appointment_data={
        ...         "client_name": "Jane Doe",
        ...         "time": "02:30 PM on Monday, October 22, 2025",
        ...         "service": "Deep Tissue Massage",
        ...         "location": "Main Clinic",
        ...     },
        ...     minutes_until=60
        ... )
    """
    # Get appointment details
    client_name = appointment_data.get("client_name", "a client")
    appt_time = appointment_data.get("time", "Unknown time")
    service = appointment_data.get("service", "")
    location = appointment_data.get("location", "")
    appointment_id = appointment_data.get("appointment_id")

    # Create email message
    message = EmailMessage()
    message["From"] = "PazPaz <noreply@pazpaz.app>"
    message["To"] = email

    # Build subject based on time until appointment
    if minutes_until <= 60:
        message["Subject"] = (
            f"Appointment in {minutes_until} minutes with {client_name}"
        )
        urgency = "Your appointment is coming up soon!"
    elif minutes_until <= 1440:
        hours = minutes_until // 60
        message["Subject"] = (
            f"Appointment in {hours} hour{'s' if hours > 1 else ''} with {client_name}"
        )
        urgency = f"Your appointment is in {hours} hour{'s' if hours > 1 else ''}."
    else:
        message["Subject"] = f"Appointment reminder: {client_name}"
        urgency = "Reminder about your upcoming appointment."

    # Build details section
    details = f"Client: {client_name}\nTime: {appt_time}"
    if service:
        details += f"\nService: {service}"
    if location:
        details += f"\nLocation: {location}"

    # Email body (plain text)
    calendar_url = f"{settings.frontend_url}/calendar"

    body_text = f"""Hello,

{urgency}

{details}

View appointment details:
{calendar_url}

See you soon!

---
PazPaz - Practice Management for Independent Therapists
{settings.frontend_url}
"""

    message.set_content(body_text)

    # Send via SMTP
    try:
        async with aiosmtplib.SMTP(
            hostname=settings.smtp_host,
            port=settings.smtp_port,
        ) as smtp:
            # Authenticate if credentials provided (not needed for MailHog)
            if settings.smtp_user:
                await smtp.login(settings.smtp_user, settings.smtp_password)

            await smtp.send_message(message)

        logger.info(
            "appointment_reminder_sent",
            email=email,
            client_name=client_name,
            minutes_until=minutes_until,
            appointment_id=appointment_id,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
        )

        # Also log to console in debug mode for convenience
        if settings.debug:
            logger.info(
                "appointment_reminder_debug_info",
                email=email,
                client_name=client_name,
                minutes_until=minutes_until,
                mailhog_ui="http://localhost:8025",
            )

    except Exception as e:
        logger.error(
            "failed_to_send_appointment_reminder",
            email=email,
            client_name=client_name,
            minutes_until=minutes_until,
            appointment_id=appointment_id,
            error=str(e),
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            exc_info=True,
        )
        raise
