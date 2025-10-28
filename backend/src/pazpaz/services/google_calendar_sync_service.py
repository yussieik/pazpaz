"""Google Calendar Sync Service for one-way synchronization (PazPaz → Google Calendar).

This service handles creating, updating, and deleting calendar events in Google Calendar
when appointments are created, modified, or deleted in PazPaz. It implements Phase 2
of the Google Calendar integration feature.

Architecture:
    - One-way sync: PazPaz → Google Calendar (read-only for Phase 2)
    - Automatic token refresh when access tokens expire
    - Transparent timezone handling (workspace timezone → Google Calendar)
    - Privacy-preserving event titles (optional client name syncing)
    - Graceful error handling with detailed logging

Security:
    - All operations enforce workspace scoping
    - Tokens are encrypted at rest (automatic via EncryptedString)
    - API credentials never logged
    - Error messages sanitized to prevent information leakage

Performance:
    - Async operations throughout
    - Minimal database queries (selectinload for relationships)
    - Token refresh only when needed (expiry check)

Usage:
    >>> from pazpaz.services.google_calendar_sync_service import create_calendar_event
    >>> google_event_id = await create_calendar_event(
    ...     db=db,
    ...     appointment_id=appointment.id,
    ...     workspace_id=workspace.id,
    ... )
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pazpaz.core.logging import get_logger
from pazpaz.models.appointment import Appointment
from pazpaz.models.google_calendar_token import GoogleCalendarToken
from pazpaz.services.google_calendar_oauth_service import (
    get_credentials,
    refresh_access_token,
)

if TYPE_CHECKING:
    from google.oauth2.credentials import Credentials

logger = get_logger(__name__)


async def _get_google_calendar_token(
    db: AsyncSession, workspace_id: uuid.UUID
) -> GoogleCalendarToken | None:
    """
    Fetch Google Calendar token for workspace and refresh if expired.

    Helper function to retrieve and validate Google Calendar token for a workspace.
    Automatically refreshes access token if it has expired.

    Args:
        db: Database session
        workspace_id: Workspace ID to fetch token for

    Returns:
        GoogleCalendarToken if exists and enabled, None otherwise

    Raises:
        HTTPException: 401 if refresh token is invalid/revoked
    """
    # Query for active token in workspace
    query = (
        select(GoogleCalendarToken)
        .where(
            GoogleCalendarToken.workspace_id == workspace_id,
            GoogleCalendarToken.enabled == True,  # noqa: E712
        )
        .limit(1)
    )
    result = await db.execute(query)
    token = result.scalar_one_or_none()

    if not token:
        logger.debug(
            "google_calendar_token_not_found",
            workspace_id=str(workspace_id),
        )
        return None

    # Check if token is expired and refresh if needed
    if token.is_expired:
        logger.info(
            "google_calendar_token_expired_refreshing",
            workspace_id=str(workspace_id),
            token_expiry=token.token_expiry.isoformat(),
        )
        token = await refresh_access_token(token, db)

    return token


def _build_google_calendar_event(
    appointment: Appointment,
    workspace_timezone: str,
    sync_client_names: bool,
) -> dict:
    """
    Build Google Calendar event dict from PazPaz appointment.

    Maps PazPaz appointment fields to Google Calendar API event format.
    Handles privacy settings (client name syncing) and timezone conversion.

    Args:
        appointment: PazPaz appointment to sync
        workspace_timezone: IANA timezone name (e.g., 'Asia/Jerusalem')
        sync_client_names: Whether to include client name in event title

    Returns:
        Google Calendar event dict ready for API submission

    Example:
        >>> event = _build_google_calendar_event(
        ...     appointment=appointment,
        ...     workspace_timezone='Asia/Jerusalem',
        ...     sync_client_names=True,
        ... )
        >>> event['summary']
        'Appointment with John Doe'
    """
    # Build event title based on privacy settings
    if sync_client_names and appointment.client:
        client_name = (
            f"{appointment.client.first_name} {appointment.client.last_name}".strip()
        )
        summary = f"Appointment with {client_name}" if client_name else "Appointment"
    else:
        summary = "Appointment"

    # Build event structure
    # Google Calendar API expects RFC 3339 timestamps with timezone
    event = {
        "summary": summary,
        "start": {
            "dateTime": appointment.scheduled_start.isoformat(),
            "timeZone": workspace_timezone,
        },
        "end": {
            "dateTime": appointment.scheduled_end.isoformat(),
            "timeZone": workspace_timezone,
        },
    }

    # Build location field (Google Calendar location field)
    location_parts = []

    # If using saved location, prioritize that
    if appointment.location:
        location_parts.append(appointment.location.name)
        if appointment.location.address:
            location_parts.append(appointment.location.address)
    elif appointment.location_details:
        location_parts.append(appointment.location_details)

    # Add location type as context
    location_type_display = appointment.location_type.value.title()
    if location_parts:
        event["location"] = f"{', '.join(location_parts)} ({location_type_display})"
    else:
        event["location"] = location_type_display

    # Build rich description field
    description_parts = []

    # Add patient/client name (always in description, even if not in title)
    if appointment.client:
        client_name = (
            f"{appointment.client.first_name} {appointment.client.last_name}".strip()
        )
        if client_name:
            description_parts.append(f"📋 Patient: {client_name}")

    # Add location details
    location_desc_parts = []
    location_desc_parts.append(f"📍 Location Type: {location_type_display}")

    if appointment.location:
        if appointment.location.name:
            location_desc_parts.append(f"Location: {appointment.location.name}")
        if appointment.location.address:
            location_desc_parts.append(f"Address: {appointment.location.address}")
        if appointment.location.details:
            location_desc_parts.append(f"Details: {appointment.location.details}")
    elif appointment.location_details:
        location_desc_parts.append(f"Details: {appointment.location_details}")

    description_parts.extend(location_desc_parts)

    # Add service if available
    if appointment.service:
        description_parts.append(f"🏥 Service: {appointment.service.name}")

    # Add therapist notes
    if appointment.notes:
        description_parts.append(f"\n📝 Notes:\n{appointment.notes}")

    event["description"] = "\n".join(description_parts)

    return event


async def create_calendar_event(
    db: AsyncSession, appointment_id: uuid.UUID, workspace_id: uuid.UUID
) -> str | None:
    """
    Create a Google Calendar event for a PazPaz appointment.

    This function:
    1. Fetches the appointment with client relationship
    2. Retrieves and refreshes Google Calendar token if needed
    3. Builds Google Calendar event from appointment data
    4. Creates event via Google Calendar API
    5. Updates appointment with google_event_id

    Args:
        db: Database session
        appointment_id: UUID of the appointment to sync
        workspace_id: Workspace ID for scoping and token lookup

    Returns:
        Google Calendar event ID if successful, None if token not found/enabled

    Raises:
        HTTPException: 401 if refresh token is invalid, 500 for API errors

    Example:
        >>> google_event_id = await create_calendar_event(
        ...     db=db,
        ...     appointment_id=appointment.id,
        ...     workspace_id=workspace.id,
        ... )
        >>> print(f"Created event: {google_event_id}")
    """
    logger.info(
        "google_calendar_create_event_started",
        appointment_id=str(appointment_id),
        workspace_id=str(workspace_id),
    )

    try:
        # Fetch appointment with relationships
        query = (
            select(Appointment)
            .where(
                Appointment.id == appointment_id,
                Appointment.workspace_id == workspace_id,
            )
            .options(
                selectinload(Appointment.client),
                selectinload(Appointment.workspace),
                selectinload(Appointment.location),
                selectinload(Appointment.service),
            )
        )
        result = await db.execute(query)
        appointment = result.scalar_one_or_none()

        if not appointment:
            logger.warning(
                "google_calendar_appointment_not_found",
                appointment_id=str(appointment_id),
                workspace_id=str(workspace_id),
            )
            return None

        # Get Google Calendar token (returns None if not connected/enabled)
        token = await _get_google_calendar_token(db, workspace_id)
        if not token:
            logger.debug(
                "google_calendar_sync_skipped_no_token",
                appointment_id=str(appointment_id),
                workspace_id=str(workspace_id),
            )
            return None

        # Build Google API credentials
        credentials: Credentials = get_credentials(token)

        # Build calendar service
        service = build("calendar", "v3", credentials=credentials)

        # Build event from appointment
        workspace_timezone = appointment.workspace.timezone or "UTC"
        event = _build_google_calendar_event(
            appointment=appointment,
            workspace_timezone=workspace_timezone,
            sync_client_names=token.sync_client_names,
        )

        # Create event in Google Calendar
        created_event = (
            service.events().insert(calendarId="primary", body=event).execute()
        )

        google_event_id = created_event["id"]

        # Update appointment with google_event_id
        appointment.google_event_id = google_event_id
        await db.commit()

        logger.info(
            "google_calendar_event_created",
            appointment_id=str(appointment_id),
            google_event_id=google_event_id,
            workspace_id=str(workspace_id),
            event_summary=event["summary"],
        )

        return google_event_id

    except HttpError as e:
        # Google API error (quota exceeded, permission denied, etc.)
        error_status = e.resp.status if hasattr(e.resp, "status") else "unknown"
        error_reason = e.error_details if hasattr(e, "error_details") else str(e)

        logger.error(
            "google_calendar_create_event_api_error",
            appointment_id=str(appointment_id),
            workspace_id=str(workspace_id),
            error_status=error_status,
            error_reason=error_reason,
            exc_info=True,
        )
        raise

    except Exception as e:
        # Unexpected error
        logger.error(
            "google_calendar_create_event_failed",
            appointment_id=str(appointment_id),
            workspace_id=str(workspace_id),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise


async def update_calendar_event(
    db: AsyncSession, appointment_id: uuid.UUID, workspace_id: uuid.UUID
) -> None:
    """
    Update an existing Google Calendar event for a PazPaz appointment.

    This function:
    1. Fetches the appointment with google_event_id
    2. Retrieves and refreshes Google Calendar token if needed
    3. Builds updated event from current appointment data
    4. Updates event via Google Calendar API
    5. If event not found (404), creates a new event instead

    Args:
        db: Database session
        appointment_id: UUID of the appointment to sync
        workspace_id: Workspace ID for scoping and token lookup

    Returns:
        None

    Raises:
        HTTPException: 401 if refresh token is invalid, 500 for API errors

    Example:
        >>> await update_calendar_event(
        ...     db=db,
        ...     appointment_id=appointment.id,
        ...     workspace_id=workspace.id,
        ... )
    """
    logger.info(
        "google_calendar_update_event_started",
        appointment_id=str(appointment_id),
        workspace_id=str(workspace_id),
    )

    try:
        # Fetch appointment with relationships
        query = (
            select(Appointment)
            .where(
                Appointment.id == appointment_id,
                Appointment.workspace_id == workspace_id,
            )
            .options(
                selectinload(Appointment.client),
                selectinload(Appointment.workspace),
                selectinload(Appointment.location),
                selectinload(Appointment.service),
            )
        )
        result = await db.execute(query)
        appointment = result.scalar_one_or_none()

        if not appointment:
            logger.warning(
                "google_calendar_appointment_not_found",
                appointment_id=str(appointment_id),
                workspace_id=str(workspace_id),
            )
            return

        # Check if appointment has google_event_id
        if not appointment.google_event_id:
            logger.debug(
                "google_calendar_no_event_id_creating_new",
                appointment_id=str(appointment_id),
                workspace_id=str(workspace_id),
            )
            # Create new event instead
            await create_calendar_event(db, appointment_id, workspace_id)
            return

        # Get Google Calendar token (returns None if not connected/enabled)
        token = await _get_google_calendar_token(db, workspace_id)
        if not token:
            logger.debug(
                "google_calendar_sync_skipped_no_token",
                appointment_id=str(appointment_id),
                workspace_id=str(workspace_id),
            )
            return

        # Build Google API credentials
        credentials: Credentials = get_credentials(token)

        # Build calendar service
        service = build("calendar", "v3", credentials=credentials)

        # Build updated event from appointment
        workspace_timezone = appointment.workspace.timezone or "UTC"
        event = _build_google_calendar_event(
            appointment=appointment,
            workspace_timezone=workspace_timezone,
            sync_client_names=token.sync_client_names,
        )

        try:
            # Update event in Google Calendar
            service.events().update(
                calendarId="primary",
                eventId=appointment.google_event_id,
                body=event,
            ).execute()

            logger.info(
                "google_calendar_event_updated",
                appointment_id=str(appointment_id),
                google_event_id=appointment.google_event_id,
                workspace_id=str(workspace_id),
                event_summary=event["summary"],
            )

        except HttpError as e:
            # Event not found (404) - create new event
            if e.resp.status == 404:
                logger.warning(
                    "google_calendar_event_not_found_creating_new",
                    appointment_id=str(appointment_id),
                    google_event_id=appointment.google_event_id,
                    workspace_id=str(workspace_id),
                )
                # Clear old event ID and create new event
                appointment.google_event_id = None
                await db.commit()
                await create_calendar_event(db, appointment_id, workspace_id)
            else:
                raise

    except HttpError as e:
        # Google API error (quota exceeded, permission denied, etc.)
        error_status = e.resp.status if hasattr(e.resp, "status") else "unknown"
        error_reason = e.error_details if hasattr(e, "error_details") else str(e)

        logger.error(
            "google_calendar_update_event_api_error",
            appointment_id=str(appointment_id),
            workspace_id=str(workspace_id),
            error_status=error_status,
            error_reason=error_reason,
            exc_info=True,
        )
        raise

    except Exception as e:
        # Unexpected error
        logger.error(
            "google_calendar_update_event_failed",
            appointment_id=str(appointment_id),
            workspace_id=str(workspace_id),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise


async def delete_calendar_event(
    db: AsyncSession, google_event_id: str, workspace_id: uuid.UUID
) -> None:
    """
    Delete a Google Calendar event.

    This function:
    1. Retrieves and refreshes Google Calendar token if needed
    2. Deletes event via Google Calendar API
    3. Handles "event not found" gracefully (already deleted)

    Args:
        db: Database session
        google_event_id: Google Calendar event ID to delete
        workspace_id: Workspace ID for token lookup

    Returns:
        None

    Raises:
        HTTPException: 401 if refresh token is invalid, 500 for API errors

    Example:
        >>> await delete_calendar_event(
        ...     db=db,
        ...     google_event_id='abc123xyz',
        ...     workspace_id=workspace.id,
        ... )
    """
    logger.info(
        "google_calendar_delete_event_started",
        google_event_id=google_event_id,
        workspace_id=str(workspace_id),
    )

    try:
        # Get Google Calendar token (returns None if not connected/enabled)
        token = await _get_google_calendar_token(db, workspace_id)
        if not token:
            logger.debug(
                "google_calendar_sync_skipped_no_token",
                google_event_id=google_event_id,
                workspace_id=str(workspace_id),
            )
            return

        # Build Google API credentials
        credentials: Credentials = get_credentials(token)

        # Build calendar service
        service = build("calendar", "v3", credentials=credentials)

        try:
            # Delete event from Google Calendar
            service.events().delete(
                calendarId="primary",
                eventId=google_event_id,
            ).execute()

            logger.info(
                "google_calendar_event_deleted",
                google_event_id=google_event_id,
                workspace_id=str(workspace_id),
            )

        except HttpError as e:
            # Event not found (410 Gone or 404 Not Found) - already deleted, this is OK
            if e.resp.status in (404, 410):
                logger.info(
                    "google_calendar_event_already_deleted",
                    google_event_id=google_event_id,
                    workspace_id=str(workspace_id),
                    status_code=e.resp.status,
                )
            else:
                raise

    except HttpError as e:
        # Google API error (quota exceeded, permission denied, etc.)
        error_status = e.resp.status if hasattr(e.resp, "status") else "unknown"
        error_reason = e.error_details if hasattr(e, "error_details") else str(e)

        logger.error(
            "google_calendar_delete_event_api_error",
            google_event_id=google_event_id,
            workspace_id=str(workspace_id),
            error_status=error_status,
            error_reason=error_reason,
            exc_info=True,
        )
        raise

    except Exception as e:
        # Unexpected error
        logger.error(
            "google_calendar_delete_event_failed",
            google_event_id=google_event_id,
            workspace_id=str(workspace_id),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise
