"""arq worker scheduler for PazPaz notification system.

This module defines the arq WorkerSettings class that configures the background
worker for scheduled notification tasks. The worker handles:

    - Session notes reminders (daily, at user-specified times)
    - Daily appointment digests (morning summaries)
    - Appointment reminders (15min, 30min, 1hr, 2hr, 24hr before appointments)

The worker runs scheduled jobs using cron-like syntax and connects to Redis
for job queue management. All jobs are initially empty and will be implemented
in subsequent phases.

Architecture:
    - arq uses Redis as both job queue and result backend
    - Worker processes run independently of the FastAPI application
    - Jobs are scheduled using cron expressions (timezone-aware)
    - Failed jobs are retried with exponential backoff

Usage:
    Start the worker from the command line:

        $ cd backend
        $ PYTHONPATH=src uv run arq pazpaz.workers.scheduler.WorkerSettings

    Or via Docker Compose:

        services:
          arq-worker:
            build: ./backend
            command: arq pazpaz.workers.scheduler.WorkerSettings
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from arq.connections import RedisSettings

from pazpaz.core.logging import get_logger
from pazpaz.db.base import AsyncSessionLocal
from pazpaz.services.email_service import (
    send_appointment_reminder,
    send_daily_digest,
    send_session_notes_reminder,
)
from pazpaz.services.notification_content_service import (
    build_appointment_reminder_email,
    build_daily_digest_email,
    build_session_notes_reminder_email,
)
from pazpaz.services.notification_query_service import (
    get_appointments_needing_reminders,
    get_distinct_workspace_timezones,
    get_users_needing_daily_digest,
    get_users_needing_session_notes_reminder,
)
from pazpaz.services.reminder_tracking_service import (
    mark_reminder_sent,
    was_reminder_sent,
)
from pazpaz.workers.settings import (
    HEALTH_CHECK_INTERVAL,
    JOB_TIMEOUT,
    MAX_JOBS,
    MAX_TRIES,
    QUEUE_NAME,
    get_redis_settings,
)

if TYPE_CHECKING:
    from arq.cron import CronJob

logger = get_logger(__name__)


# Scheduled Tasks
# These functions will be implemented in Phase 3
# For now, they're empty placeholders to allow worker startup


async def send_session_notes_reminders(ctx: dict) -> dict:
    """
    Send session notes reminders to users at their configured times.

    This task runs every minute to check if any users need a reminder about
    draft session notes in their configured timezone. It handles timezone
    conversion internally to ensure reminders are sent at the correct local
    time for each user.

    Args:
        ctx: arq worker context containing database session factory

    Returns:
        dict: Summary statistics
            - sent: Number of reminders sent successfully
            - errors: Number of errors encountered
            - timezones_checked: Number of timezones processed

    Note:
        Implements proper timezone support - loops through all workspace timezones
        and converts UTC to local time for accurate reminder matching.
    """
    logger.info("session_notes_reminders_task_started")

    sent_count = 0
    error_count = 0
    timezones_checked = 0

    try:
        # Get current time in UTC
        utc_now = datetime.now(UTC)

        # Get database session
        async with AsyncSessionLocal() as db:
            # Get all distinct workspace timezones
            timezones = await get_distinct_workspace_timezones(db)

            logger.info(
                "session_notes_reminders_checking_timezones",
                timezone_count=len(timezones),
                timezones=timezones,
                utc_time=utc_now.strftime("%H:%M"),
            )

            # Process each timezone
            for timezone_name in timezones:
                timezones_checked += 1

                try:
                    # Convert UTC to local time in this timezone
                    tz = ZoneInfo(timezone_name)
                    local_time = utc_now.astimezone(tz).time()

                    logger.debug(
                        "checking_timezone",
                        timezone=timezone_name,
                        utc_time=utc_now.strftime("%H:%M"),
                        local_time=local_time.strftime("%H:%M"),
                    )

                    # Query users in this timezone needing reminders at this local time
                    users = await get_users_needing_session_notes_reminder(
                        db, local_time, timezone_name
                    )

                    if users:
                        logger.info(
                            "session_notes_reminders_users_found",
                            timezone=timezone_name,
                            user_count=len(users),
                            local_time=local_time.strftime("%H:%M"),
                        )

                    # Send reminder to each user
                    for user in users:
                        try:
                            # Build email content
                            email_data = await build_session_notes_reminder_email(
                                db, user
                            )

                            # Extract draft count from subject for logging
                            # Subject format: "You have X draft session note(s)"
                            draft_count = 0
                            if "have" in email_data["subject"]:
                                parts = email_data["subject"].split()
                                for i, part in enumerate(parts):
                                    if part == "have" and i + 1 < len(parts):
                                        try:
                                            draft_count = int(parts[i + 1])
                                        except (ValueError, IndexError):
                                            pass

                            # Send email via email service
                            from pazpaz.core.config import settings

                            await send_session_notes_reminder(
                                email=email_data["to"],
                                draft_count=draft_count,
                                frontend_url=settings.frontend_url,
                            )

                            logger.info(
                                "session_notes_reminder_sent",
                                user_id=str(user.id),
                                email=user.email,
                                draft_count=draft_count,
                                timezone=timezone_name,
                                local_time=local_time.strftime("%H:%M"),
                            )
                            sent_count += 1

                        except Exception as e:
                            logger.error(
                                "session_notes_reminder_failed",
                                user_id=str(user.id),
                                email=user.email,
                                timezone=timezone_name,
                                error=str(e),
                                exc_info=True,
                            )
                            error_count += 1

                except Exception as e:
                    # Log timezone-specific error but continue processing other timezones
                    logger.error(
                        "timezone_processing_failed",
                        timezone=timezone_name,
                        error=str(e),
                        exc_info=True,
                    )
                    error_count += 1

        logger.info(
            "session_notes_reminders_task_completed",
            sent=sent_count,
            errors=error_count,
            timezones_checked=timezones_checked,
        )

        return {
            "sent": sent_count,
            "errors": error_count,
            "timezones_checked": timezones_checked,
        }

    except Exception as e:
        logger.error(
            "session_notes_reminders_task_failed",
            error=str(e),
            exc_info=True,
        )
        raise


async def send_daily_digests(ctx: dict) -> dict:
    """
    Send daily appointment digests to users at their configured times.

    This task runs every minute to check if any users need their daily digest
    (morning summary of today's appointments). It respects user preferences
    for weekend skipping and timezone-specific delivery times.

    Args:
        ctx: arq worker context containing database session factory

    Returns:
        dict: Summary statistics
            - sent: Number of digests sent successfully
            - errors: Number of errors encountered
            - skipped_weekend: Number of users skipped due to weekend setting
            - timezones_checked: Number of timezones processed

    Note:
        Implements proper timezone support - loops through all workspace timezones
        and converts UTC to local time for accurate digest delivery.
    """
    logger.info("daily_digests_task_started")

    sent_count = 0
    error_count = 0
    skipped_weekend_count = 0
    timezones_checked = 0

    try:
        # Get current time in UTC
        utc_now = datetime.now(UTC)

        # Get database session
        async with AsyncSessionLocal() as db:
            # Get all distinct workspace timezones
            timezones = await get_distinct_workspace_timezones(db)

            logger.info(
                "daily_digests_checking_timezones",
                timezone_count=len(timezones),
                timezones=timezones,
                utc_time=utc_now.strftime("%H:%M"),
            )

            # Process each timezone
            for timezone_name in timezones:
                timezones_checked += 1

                try:
                    # Convert UTC to local time in this timezone
                    tz = ZoneInfo(timezone_name)
                    local_now = utc_now.astimezone(tz)
                    local_time = local_now.time()
                    local_day = local_now.weekday()  # 0=Monday, 6=Sunday

                    # Check if today is weekend in this timezone
                    is_weekend = local_day in (5, 6)

                    logger.debug(
                        "checking_timezone",
                        timezone=timezone_name,
                        utc_time=utc_now.strftime("%H:%M"),
                        local_time=local_time.strftime("%H:%M"),
                        local_day=local_day,
                        is_weekend=is_weekend,
                    )

                    # Query users in this timezone needing digest at this local time
                    # Service already filters weekend-skippers on weekends
                    users = await get_users_needing_daily_digest(
                        db, local_time, local_day, timezone_name
                    )

                    if users:
                        logger.info(
                            "daily_digests_users_found",
                            timezone=timezone_name,
                            user_count=len(users),
                            local_time=local_time.strftime("%H:%M"),
                            local_day=local_day,
                            is_weekend=is_weekend,
                        )

                    # Send digest to each user
                    for user in users:
                        try:
                            # Build email content with today's appointments (in local timezone)
                            today = local_now.date()
                            email_data = await build_daily_digest_email(db, user, today)

                            # Parse appointments from email body to get count
                            # This is a workaround - ideally we'd return this from builder
                            appointment_count = email_data["body"].count("  •")

                            # Format appointments for email service
                            # For now, email service expects a simpler format
                            # We'll pass the pre-built content from the builder
                            date_str = today.strftime("%A, %B %d, %Y")

                            from pazpaz.core.config import settings

                            # Note: email service expects different format than builder provides
                            # For Phase 3, we'll use builder's output directly by calling
                            # send_daily_digest with empty appointments (it will build from body)
                            # TODO: Refactor in Phase 4 to align interfaces

                            # Actually, let's query appointments ourselves for the service
                            from pazpaz.models.appointment import (
                                Appointment,
                                AppointmentStatus,
                            )
                            from sqlalchemy import and_, select

                            start_of_day = datetime.combine(today, datetime.min.time())
                            end_of_day = datetime.combine(today, datetime.max.time())

                            appt_stmt = (
                                select(Appointment)
                                .where(
                                    and_(
                                        Appointment.workspace_id == user.workspace_id,
                                        Appointment.scheduled_start >= start_of_day,
                                        Appointment.scheduled_start <= end_of_day,
                                        Appointment.status
                                        == AppointmentStatus.SCHEDULED,
                                    )
                                )
                                .order_by(Appointment.scheduled_start)
                            )

                            result = await db.execute(appt_stmt)
                            appointments = list(result.scalars().all())

                            # Refresh relationships
                            for appt in appointments:
                                await db.refresh(
                                    appt, ["client", "service", "location"]
                                )

                            # Format for email service
                            appointment_dicts = []
                            for appt in appointments:
                                appt_dict = {
                                    "time": appt.scheduled_start.strftime("%I:%M %p"),
                                    "client_name": appt.client.full_name
                                    if appt.client
                                    else "Unknown",
                                }
                                if appt.service:
                                    appt_dict["service"] = appt.service.name
                                if appt.location:
                                    appt_dict["location"] = appt.location.name

                                appointment_dicts.append(appt_dict)

                            # Send email
                            await send_daily_digest(
                                email=user.email,
                                appointments=appointment_dicts,
                                date_str=date_str,
                                frontend_url=settings.frontend_url,
                            )

                            logger.info(
                                "daily_digest_sent",
                                user_id=str(user.id),
                                email=user.email,
                                appointment_count=len(appointment_dicts),
                                date=date_str,
                                timezone=timezone_name,
                                local_time=local_time.strftime("%H:%M"),
                            )
                            sent_count += 1

                        except Exception as e:
                            logger.error(
                                "daily_digest_failed",
                                user_id=str(user.id),
                                email=user.email,
                                timezone=timezone_name,
                                error=str(e),
                                exc_info=True,
                            )
                            error_count += 1

                except Exception as e:
                    # Log timezone-specific error but continue processing other timezones
                    logger.error(
                        "timezone_processing_failed",
                        timezone=timezone_name,
                        error=str(e),
                        exc_info=True,
                    )
                    error_count += 1

        logger.info(
            "daily_digests_task_completed",
            sent=sent_count,
            errors=error_count,
            skipped_weekend=skipped_weekend_count,
            timezones_checked=timezones_checked,
        )

        return {
            "sent": sent_count,
            "errors": error_count,
            "skipped_weekend": skipped_weekend_count,
            "timezones_checked": timezones_checked,
        }

    except Exception as e:
        logger.error(
            "daily_digests_task_failed",
            error=str(e),
            exc_info=True,
        )
        raise


async def send_appointment_reminders(ctx: dict) -> dict:
    """
    Send appointment reminders based on user notification settings.

    This task runs every 5 minutes to check for upcoming appointments and
    sends reminders at configured intervals (15min, 30min, 1hr, 2hr, 24hr
    before appointment start). It prevents duplicate reminders using the
    appointment_reminders_sent tracking table.

    Args:
        ctx: arq worker context containing database session factory

    Returns:
        dict: Summary statistics
            - sent: Number of reminders sent successfully
            - errors: Number of errors encountered
            - already_sent: Number of reminders skipped (already sent)

    Note:
        Phase 4 implementation - includes deduplication tracking.
        Uses simplified UTC-only approach for timezone handling.
        TODO: Add proper timezone support in future phases.
    """
    logger.info("appointment_reminders_task_started")

    sent_count = 0
    error_count = 0
    already_sent_count = 0

    try:
        # Get current time in UTC
        current_time = datetime.now(UTC)

        # Get database session
        async with AsyncSessionLocal() as db:
            # Query appointments needing reminders
            reminders = await get_appointments_needing_reminders(db, current_time)

            logger.info(
                "appointment_reminders_found",
                reminder_count=len(reminders),
                current_time=current_time.isoformat(),
            )

            # Send reminder for each (appointment, user) pair
            for appointment, user in reminders:
                try:
                    # Calculate minutes until appointment
                    time_delta = appointment.scheduled_start - current_time
                    minutes_until = int(time_delta.total_seconds() / 60)

                    # Determine reminder type based on user's setting
                    # The user.notification_settings.reminder_minutes tells us
                    # what interval this user wants reminders for
                    reminder_minutes = user.notification_settings.reminder_minutes

                    # Check if this reminder was already sent
                    already_sent = await was_reminder_sent(
                        db, appointment.id, user.id, reminder_minutes
                    )

                    if already_sent:
                        logger.info(
                            "reminder_already_sent",
                            appointment_id=str(appointment.id),
                            user_id=str(user.id),
                            reminder_minutes=reminder_minutes,
                            minutes_until=minutes_until,
                        )
                        already_sent_count += 1
                        continue

                    # Build email content
                    email_data = await build_appointment_reminder_email(
                        db, appointment, user
                    )

                    # Format appointment data for email service
                    appointment_data = {
                        "appointment_id": str(appointment.id),
                        "client_name": (
                            appointment.client.full_name
                            if appointment.client
                            else "Unknown"
                        ),
                        "time": appointment.scheduled_start.strftime(
                            "%I:%M %p on %A, %B %d, %Y"
                        ),
                    }

                    if appointment.service:
                        appointment_data["service"] = appointment.service.name

                    if appointment.location:
                        appointment_data["location"] = appointment.location.name
                    elif appointment.location_details:
                        appointment_data["location"] = appointment.location_details

                    # Send email
                    await send_appointment_reminder(
                        email=user.email,
                        appointment_data=appointment_data,
                        minutes_until=minutes_until,
                    )

                    # Mark reminder as sent to prevent duplicates
                    await mark_reminder_sent(
                        db, appointment.id, user.id, reminder_minutes
                    )

                    logger.info(
                        "appointment_reminder_sent",
                        appointment_id=str(appointment.id),
                        user_id=str(user.id),
                        email=user.email,
                        client_name=appointment_data["client_name"],
                        minutes_until=minutes_until,
                        reminder_minutes=reminder_minutes,
                    )
                    sent_count += 1

                except Exception as e:
                    logger.error(
                        "appointment_reminder_failed",
                        appointment_id=str(appointment.id),
                        user_id=str(user.id),
                        email=user.email,
                        error=str(e),
                        exc_info=True,
                    )
                    error_count += 1

        logger.info(
            "appointment_reminders_task_completed",
            sent=sent_count,
            errors=error_count,
            already_sent=already_sent_count,
        )

        return {
            "sent": sent_count,
            "errors": error_count,
            "already_sent": already_sent_count,
        }

    except Exception as e:
        logger.error(
            "appointment_reminders_task_failed",
            error=str(e),
            exc_info=True,
        )
        raise


async def startup(ctx: dict) -> None:
    """
    Worker startup hook - executed once when worker starts.

    This function is called when the arq worker initializes. It sets up
    database connections and initializes services.

    Args:
        ctx: arq worker context (shared across all jobs)

    Note:
        The ctx dict is shared across all jobs in the worker process.
        Database sessions are created per-job using AsyncSessionLocal.
    """
    logger.info("arq_worker_starting", queue=QUEUE_NAME)

    # Database connection is managed per-task using AsyncSessionLocal
    # No need to store in ctx since each task creates its own session

    # Verify database connectivity at startup
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text

            result = await db.execute(text("SELECT 1"))
            result.scalar()
            logger.info("arq_worker_database_connection_verified")
    except Exception as e:
        logger.error(
            "arq_worker_database_connection_failed",
            error=str(e),
            exc_info=True,
        )
        raise

    logger.info("arq_worker_startup_complete")


async def shutdown(ctx: dict) -> None:
    """
    Worker shutdown hook - executed once when worker stops.

    This function is called when the arq worker is shutting down (e.g., on
    SIGTERM or SIGINT). Use it to cleanly close database connections,
    flush logs, or perform other cleanup tasks.

    Args:
        ctx: arq worker context containing any shared resources from startup
    """
    logger.info("arq_worker_shutting_down")

    # Close database engine (connection pool)
    try:
        from pazpaz.db.base import engine

        await engine.dispose()
        logger.info("arq_worker_database_connections_closed")
    except Exception as e:
        logger.error(
            "arq_worker_shutdown_error",
            error=str(e),
            exc_info=True,
        )

    logger.info("arq_worker_shutdown_complete")


# arq WorkerSettings Class
# This class is the entry point for the arq worker and defines all configuration


class WorkerSettings:
    """
    arq worker configuration for PazPaz notification scheduler.

    This class defines all worker settings including Redis connection,
    job configurations, scheduled tasks (cron jobs), and lifecycle hooks.

    arq looks for this class when starting the worker:
        $ arq pazpaz.workers.scheduler.WorkerSettings

    Attributes:
        redis_settings: Redis connection configuration
        queue_name: Name of the Redis queue for this worker
        max_jobs: Maximum concurrent jobs
        job_timeout: Maximum time a job can run
        health_check_interval: Interval for worker health checks
        max_tries: Maximum retry attempts for failed jobs
        cron_jobs: List of scheduled tasks (empty in Phase 1)
        on_startup: Function to run when worker starts
        on_shutdown: Function to run when worker stops

    Configuration:
        All settings are imported from pazpaz.workers.settings module,
        which derives them from the main application configuration
        (pazpaz.core.config.settings).

    Example:
        Start the worker:

            $ cd backend
            $ PYTHONPATH=src uv run arq pazpaz.workers.scheduler.WorkerSettings

        Expected output:

            18:30:45: arq worker starting...
            18:30:45: redis_host=localhost redis_port=6379
                      queue_name=pazpaz:notifications
    """

    # Redis Connection
    # Uses settings from pazpaz.core.config.settings.redis_url
    redis_settings = RedisSettings(**get_redis_settings())

    # Queue Configuration
    queue_name = QUEUE_NAME

    # Job Execution Configuration
    max_jobs = MAX_JOBS
    job_timeout = JOB_TIMEOUT

    # Health Check Configuration
    health_check_interval = HEALTH_CHECK_INTERVAL

    # Retry Configuration
    max_tries = MAX_TRIES

    # Scheduled Tasks (Cron Jobs)
    # Phase 3 implementation - scheduled notification tasks
    # Format: cron(function, minute={...}, hour={...}, ...)
    from arq import cron

    cron_jobs: list[CronJob] = [
        # Session notes reminders - every minute
        # Checks if any users need reminder at current time (UTC)
        cron(
            send_session_notes_reminders,
            minute={
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
                27,
                28,
                29,
                30,
                31,
                32,
                33,
                34,
                35,
                36,
                37,
                38,
                39,
                40,
                41,
                42,
                43,
                44,
                45,
                46,
                47,
                48,
                49,
                50,
                51,
                52,
                53,
                54,
                55,
                56,
                57,
                58,
                59,
            },
            run_at_startup=False,
        ),
        # Daily digests - every minute
        # Checks if any users need digest at current time (UTC)
        cron(
            send_daily_digests,
            minute={
                0,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
                27,
                28,
                29,
                30,
                31,
                32,
                33,
                34,
                35,
                36,
                37,
                38,
                39,
                40,
                41,
                42,
                43,
                44,
                45,
                46,
                47,
                48,
                49,
                50,
                51,
                52,
                53,
                54,
                55,
                56,
                57,
                58,
                59,
            },
            run_at_startup=False,
        ),
        # Appointment reminders - every 5 minutes
        # Checks for upcoming appointments that need reminders
        cron(
            send_appointment_reminders,
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            run_at_startup=False,
        ),
    ]

    # Lifecycle Hooks
    on_startup = startup
    on_shutdown = shutdown
