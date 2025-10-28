"""ARQ background tasks for Google Calendar synchronization.

This module contains background tasks for syncing PazPaz appointments to Google Calendar.
Tasks are enqueued from the appointments API when CREATE/UPDATE/DELETE operations occur.

Architecture:
    - Ad-hoc tasks (not cron-scheduled) - triggered by appointment lifecycle events
    - Async execution - appointment CRUD succeeds even if sync fails
    - Automatic retry with exponential backoff (3 attempts)
    - Graceful handling of disconnected/disabled Google Calendar integration

Task Flow:
    1. Appointment API enqueues sync task (non-blocking)
    2. ARQ worker picks up task from Redis queue
    3. Task fetches appointment and Google Calendar token
    4. Task calls appropriate sync service function (create/update/delete)
    5. Task updates token's last_sync_* fields for observability
    6. On failure, ARQ automatically retries with backoff

Error Handling:
    - If token not found/disabled: Skip silently (no error)
    - If API error: Log and retry (ARQ handles retry logic)
    - If token expired: Automatic refresh in sync service
    - If refresh token invalid: Log error, don't retry

Usage:
    Enqueue from appointment API:

    >>> from arq import create_pool
    >>> from pazpaz.workers.settings import get_redis_settings
    >>>
    >>> redis = await create_pool(RedisSettings(**get_redis_settings()))
    >>> await redis.enqueue_job(
    ...     'sync_appointment_to_google_calendar',
    ...     appointment_id=str(appointment.id),
    ...     action='create',
    ... )
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from pazpaz.core.logging import get_logger
from pazpaz.db.base import AsyncSessionLocal
from pazpaz.models.google_calendar_token import GoogleCalendarToken
from pazpaz.services.google_calendar_sync_service import (
    create_calendar_event,
    delete_calendar_event,
    update_calendar_event,
)

logger = get_logger(__name__)


async def sync_appointment_to_google_calendar(
    ctx: dict,
    appointment_id: str,
    action: str,
    google_event_id: str | None = None,
    workspace_id: str | None = None,
) -> dict:
    """
    Sync a PazPaz appointment to Google Calendar.

    This ARQ background task is enqueued when appointments are created, updated,
    or deleted. It calls the appropriate sync service function based on the action
    parameter.

    Task Lifecycle:
    1. Validates action parameter (create/update/delete)
    2. Fetches appointment and workspace from database (or uses provided workspace_id)
    3. Checks if Google Calendar is connected and enabled for workspace
    4. Calls appropriate sync service function
    5. Updates token's last_sync_* fields for observability
    6. Returns status dict with success/error information

    Retry Logic:
    - ARQ automatically retries failed tasks 3 times with exponential backoff
    - Base delay: 60 seconds (configured in WorkerSettings)
    - Backoff: 60s, 120s, 240s (exponential)
    - After 3 failures, task is marked as failed and logged

    Args:
        ctx: ARQ worker context (contains shared resources)
        appointment_id: UUID of appointment to sync (as string)
        action: Sync action - "create", "update", or "delete"
        google_event_id: Optional Google Calendar event ID (for delete action)
        workspace_id: Optional workspace UUID (for delete action when appointment is deleted)

    Returns:
        dict: Status information
            - status: "success", "skipped", or "error"
            - google_event_id: Google Calendar event ID (if created/updated)
            - error: Error message (if failed)

    Example:
        >>> # Enqueue create task
        >>> await redis.enqueue_job(
        ...     'sync_appointment_to_google_calendar',
        ...     appointment_id='550e8400-e29b-41d4-a716-446655440000',
        ...     action='create',
        ... )

        >>> # Enqueue delete task (with event ID and workspace ID)
        >>> await redis.enqueue_job(
        ...     'sync_appointment_to_google_calendar',
        ...     appointment_id='550e8400-e29b-41d4-a716-446655440000',
        ...     action='delete',
        ...     google_event_id='abc123xyz',
        ...     workspace_id='550e8400-e29b-41d4-a716-446655440000',
        ... )

        >>> # Task executes asynchronously
        >>> # Returns: {"status": "success", "google_event_id": "abc123xyz"}
    """
    logger.info(
        "google_calendar_sync_task_started",
        appointment_id=appointment_id,
        action=action,
    )

    # Validate action parameter
    if action not in ("create", "update", "delete"):
        logger.error(
            "google_calendar_sync_invalid_action",
            appointment_id=appointment_id,
            action=action,
        )
        return {
            "status": "error",
            "error": f"Invalid action: {action}. Must be 'create', 'update', or 'delete'.",
        }

    try:
        # Convert appointment_id string to UUID
        try:
            appt_id_uuid = uuid.UUID(appointment_id)
        except ValueError as e:
            logger.error(
                "google_calendar_sync_invalid_uuid",
                appointment_id=appointment_id,
                error=str(e),
            )
            return {
                "status": "error",
                "error": f"Invalid UUID format: {appointment_id}",
            }

        # Get database session
        async with AsyncSessionLocal() as db:
            # For delete action with provided workspace_id, skip appointment fetch
            if action == "delete" and workspace_id:
                # Convert workspace_id string to UUID
                try:
                    workspace_id_uuid = uuid.UUID(workspace_id)
                except ValueError as e:
                    logger.error(
                        "google_calendar_sync_invalid_workspace_uuid",
                        workspace_id=workspace_id,
                        error=str(e),
                    )
                    return {
                        "status": "error",
                        "error": f"Invalid workspace UUID format: {workspace_id}",
                    }
                appointment = None  # Appointment already deleted
            else:
                # Fetch appointment to get workspace_id
                from sqlalchemy.orm import selectinload

                from pazpaz.models.appointment import Appointment

                query = (
                    select(Appointment)
                    .where(Appointment.id == appt_id_uuid)
                    .options(selectinload(Appointment.workspace))
                )
                result = await db.execute(query)
                appointment = result.scalar_one_or_none()

                if not appointment:
                    logger.warning(
                        "google_calendar_sync_appointment_not_found",
                        appointment_id=appointment_id,
                    )
                    return {
                        "status": "error",
                        "error": f"Appointment not found: {appointment_id}",
                    }

                workspace_id_uuid = appointment.workspace_id

            # Fetch Google Calendar token for workspace
            query = (
                select(GoogleCalendarToken)
                .where(
                    GoogleCalendarToken.workspace_id == workspace_id_uuid,
                )
                .limit(1)
            )
            result = await db.execute(query)
            token = result.scalar_one_or_none()

            # If token not exists or not enabled, skip sync silently
            if not token or not token.enabled:
                logger.debug(
                    "google_calendar_sync_skipped_not_enabled",
                    appointment_id=appointment_id,
                    workspace_id=str(workspace_id_uuid),
                    token_exists=token is not None,
                    token_enabled=token.enabled if token else False,
                )
                return {
                    "status": "skipped",
                    "reason": "Google Calendar not connected or disabled",
                }

            # Perform sync based on action
            result_google_event_id = None

            if action == "create":
                result_google_event_id = await create_calendar_event(
                    db=db,
                    appointment_id=appt_id_uuid,
                    workspace_id=workspace_id_uuid,
                )

            elif action == "update":
                await update_calendar_event(
                    db=db,
                    appointment_id=appt_id_uuid,
                    workspace_id=workspace_id_uuid,
                )
                # google_event_id remains on appointment record
                result_google_event_id = appointment.google_event_id

            elif action == "delete":
                # For delete, use provided google_event_id or get from appointment
                event_id_to_delete = google_event_id or (
                    appointment.google_event_id if appointment else None
                )

                if event_id_to_delete:
                    await delete_calendar_event(
                        db=db,
                        google_event_id=event_id_to_delete,
                        workspace_id=workspace_id_uuid,
                    )
                    result_google_event_id = event_id_to_delete
                else:
                    logger.debug(
                        "google_calendar_sync_delete_skipped_no_event_id",
                        appointment_id=appointment_id,
                        workspace_id=str(workspace_id_uuid),
                    )

            # Update token's last_sync_* fields for observability
            token.last_sync_at = datetime.now(UTC)
            token.last_sync_status = "success"
            token.last_sync_error = None
            await db.commit()

            logger.info(
                "google_calendar_sync_task_completed",
                appointment_id=appointment_id,
                action=action,
                google_event_id=result_google_event_id,
                workspace_id=str(workspace_id_uuid),
            )

            return {
                "status": "success",
                "action": action,
                "google_event_id": result_google_event_id,
            }

    except Exception as e:
        # Log error and update token's last_sync_error
        logger.error(
            "google_calendar_sync_task_failed",
            appointment_id=appointment_id,
            action=action,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )

        # Try to update token's last_sync_error field
        try:
            async with AsyncSessionLocal() as db:
                # Fetch appointment to get workspace_id
                from pazpaz.models.appointment import Appointment

                query = select(Appointment).where(Appointment.id == appt_id_uuid)
                result = await db.execute(query)
                appointment = result.scalar_one_or_none()

                if appointment:
                    workspace_id = appointment.workspace_id

                    # Fetch token
                    query = (
                        select(GoogleCalendarToken)
                        .where(
                            GoogleCalendarToken.workspace_id == workspace_id,
                        )
                        .limit(1)
                    )
                    result = await db.execute(query)
                    token = result.scalar_one_or_none()

                    if token:
                        token.last_sync_at = datetime.now(UTC)
                        token.last_sync_status = "error"
                        token.last_sync_error = f"{type(e).__name__}: {str(e)}"
                        await db.commit()
        except Exception as update_error:
            # If updating token fails, just log it
            logger.error(
                "google_calendar_sync_token_update_failed",
                appointment_id=appointment_id,
                error=str(update_error),
                exc_info=True,
            )

        # Return error status (ARQ will retry)
        return {
            "status": "error",
            "action": action,
            "error": f"{type(e).__name__}: {str(e)}",
        }
