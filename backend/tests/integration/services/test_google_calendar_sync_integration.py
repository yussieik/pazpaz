"""End-to-end integration tests for Google Calendar sync service.

Tests the full flow from appointment creation/update to Google Calendar API calls,
verifying that client notifications are sent correctly with sendUpdates parameter.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.appointment import Appointment, AppointmentStatus, LocationType
from pazpaz.models.client import Client
from pazpaz.models.google_calendar_token import GoogleCalendarToken
from pazpaz.models.workspace import Workspace
from pazpaz.services.google_calendar_sync_service import (
    create_calendar_event,
    update_calendar_event,
)

# ============================================================================
# End-to-End Sync Tests with Client Notifications
# ============================================================================


@pytest.mark.asyncio
@patch("pazpaz.services.google_calendar_sync_service.build")
async def test_create_appointment_with_notify_clients_sends_updates_all(
    mock_build,
    db_session: AsyncSession,
    workspace_1: Workspace,
    test_user_ws1,
    sample_client_ws1: Client,
):
    """Test creating appointment with notify_clients=true calls sendUpdates='all'."""
    # Setup: Create Google Calendar token with notify_clients enabled
    token = GoogleCalendarToken(
        workspace_id=workspace_1.id,
        user_id=test_user_ws1.id,
        access_token="ya29.test_access_token",
        refresh_token="1//test_refresh_token",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=True,
        sync_client_names=True,
        notify_clients=True,  # Enabled
    )
    db_session.add(token)
    await db_session.commit()

    # Update client with valid email
    sample_client_ws1.email = "client@example.com"
    await db_session.commit()

    # Create appointment
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    db_session.add(appointment)
    await db_session.commit()

    # Mock Google Calendar API
    mock_service = MagicMock()
    mock_events = MagicMock()
    mock_insert = MagicMock()
    mock_execute = MagicMock(return_value={"id": "google_event_123"})

    mock_insert.execute = mock_execute
    mock_events.insert.return_value = mock_insert
    mock_service.events.return_value = mock_events
    mock_build.return_value = mock_service

    # Execute: Create calendar event
    google_event_id = await create_calendar_event(
        db=db_session,
        appointment_id=appointment.id,
        workspace_id=workspace_1.id,
    )

    # Assert: Google event created
    assert google_event_id == "google_event_123"

    # Assert: insert() was called with sendUpdates="all"
    mock_events.insert.assert_called_once()
    call_kwargs = mock_events.insert.call_args.kwargs
    assert call_kwargs["sendUpdates"] == "all"

    # Assert: Event body includes attendees
    event_body = call_kwargs["body"]
    assert "attendees" in event_body
    assert len(event_body["attendees"]) == 1
    assert event_body["attendees"][0]["email"] == "client@example.com"

    # Assert: Reminders configured
    assert "reminders" in event_body
    assert event_body["reminders"]["useDefault"] is False
    assert len(event_body["reminders"]["overrides"]) == 2


@pytest.mark.asyncio
@patch("pazpaz.services.google_calendar_sync_service.build")
async def test_update_appointment_with_notify_clients_sends_updates_all(
    mock_build,
    db_session: AsyncSession,
    workspace_1: Workspace,
    test_user_ws1,
    sample_client_ws1: Client,
):
    """Test updating appointment with notify_clients=true calls sendUpdates='all'."""
    # Setup: Create Google Calendar token with notify_clients enabled
    token = GoogleCalendarToken(
        workspace_id=workspace_1.id,
        user_id=test_user_ws1.id,
        access_token="ya29.test_access_token",
        refresh_token="1//test_refresh_token",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=True,
        sync_client_names=True,
        notify_clients=True,  # Enabled
    )
    db_session.add(token)

    # Update client with valid email
    sample_client_ws1.email = "client@example.com"

    # Create appointment with existing google_event_id
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
        google_event_id="existing_google_event_456",
    )
    db_session.add(appointment)
    await db_session.commit()

    # Mock Google Calendar API
    mock_service = MagicMock()
    mock_events = MagicMock()
    mock_update = MagicMock()
    mock_execute = MagicMock(return_value={"id": "existing_google_event_456"})

    mock_update.execute = mock_execute
    mock_events.update.return_value = mock_update
    mock_service.events.return_value = mock_events
    mock_build.return_value = mock_service

    # Execute: Update calendar event
    await update_calendar_event(
        db=db_session,
        appointment_id=appointment.id,
        workspace_id=workspace_1.id,
    )

    # Assert: update() was called with sendUpdates="all"
    mock_events.update.assert_called_once()
    call_kwargs = mock_events.update.call_args.kwargs
    assert call_kwargs["sendUpdates"] == "all"
    assert call_kwargs["eventId"] == "existing_google_event_456"

    # Assert: Event body includes attendees
    event_body = call_kwargs["body"]
    assert "attendees" in event_body
    assert event_body["attendees"][0]["email"] == "client@example.com"


@pytest.mark.asyncio
@patch("pazpaz.services.google_calendar_sync_service.build")
async def test_create_appointment_with_notify_clients_disabled_sends_updates_none(
    mock_build,
    db_session: AsyncSession,
    workspace_1: Workspace,
    test_user_ws1,
    sample_client_ws1: Client,
):
    """Test creating appointment with notify_clients=false calls sendUpdates='none'."""
    # Setup: Create Google Calendar token with notify_clients disabled
    token = GoogleCalendarToken(
        workspace_id=workspace_1.id,
        user_id=test_user_ws1.id,
        access_token="ya29.test_access_token",
        refresh_token="1//test_refresh_token",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=True,
        sync_client_names=True,
        notify_clients=False,  # Disabled
    )
    db_session.add(token)

    # Update client with valid email (but notifications disabled)
    sample_client_ws1.email = "client@example.com"

    # Create appointment
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    db_session.add(appointment)
    await db_session.commit()

    # Mock Google Calendar API
    mock_service = MagicMock()
    mock_events = MagicMock()
    mock_insert = MagicMock()
    mock_execute = MagicMock(return_value={"id": "google_event_789"})

    mock_insert.execute = mock_execute
    mock_events.insert.return_value = mock_insert
    mock_service.events.return_value = mock_events
    mock_build.return_value = mock_service

    # Execute: Create calendar event
    await create_calendar_event(
        db=db_session,
        appointment_id=appointment.id,
        workspace_id=workspace_1.id,
    )

    # Assert: insert() was called with sendUpdates="none"
    call_kwargs = mock_events.insert.call_args.kwargs
    assert call_kwargs["sendUpdates"] == "none"

    # Assert: Event body does NOT include attendees
    event_body = call_kwargs["body"]
    assert "attendees" not in event_body


@pytest.mark.asyncio
@patch("pazpaz.services.google_calendar_sync_service.build")
async def test_create_appointment_client_missing_email_no_error(
    mock_build,
    db_session: AsyncSession,
    workspace_1: Workspace,
    test_user_ws1,
):
    """Test creating appointment with notify_clients=true but client.email=None succeeds."""
    # Setup: Create Google Calendar token with notify_clients enabled
    token = GoogleCalendarToken(
        workspace_id=workspace_1.id,
        user_id=test_user_ws1.id,
        access_token="ya29.test_access_token",
        refresh_token="1//test_refresh_token",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=True,
        sync_client_names=True,
        notify_clients=True,  # Enabled
    )
    db_session.add(token)

    # Create client WITHOUT email
    client = Client(
        workspace_id=workspace_1.id,
        first_name="No",
        last_name="Email",
        email=None,  # No email
    )
    db_session.add(client)
    await db_session.commit()  # Commit client first to get ID

    # Create appointment
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=client.id,
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    db_session.add(appointment)
    await db_session.commit()

    # Mock Google Calendar API
    mock_service = MagicMock()
    mock_events = MagicMock()
    mock_insert = MagicMock()
    mock_execute = MagicMock(return_value={"id": "google_event_no_email"})

    mock_insert.execute = mock_execute
    mock_events.insert.return_value = mock_insert
    mock_service.events.return_value = mock_events
    mock_build.return_value = mock_service

    # Execute: Create calendar event (should not crash)
    google_event_id = await create_calendar_event(
        db=db_session,
        appointment_id=appointment.id,
        workspace_id=workspace_1.id,
    )

    # Assert: Event created successfully
    assert google_event_id == "google_event_no_email"

    # Assert: Event body does NOT include attendees
    event_body = mock_events.insert.call_args.kwargs["body"]
    assert "attendees" not in event_body

    # Assert: sendUpdates still set correctly (doesn't crash)
    assert mock_events.insert.call_args.kwargs["sendUpdates"] == "all"


@pytest.mark.asyncio
@patch("pazpaz.services.google_calendar_sync_service.build")
async def test_create_appointment_client_invalid_email_no_error(
    mock_build,
    db_session: AsyncSession,
    workspace_1: Workspace,
    test_user_ws1,
):
    """Test creating appointment with invalid client email succeeds without attendee."""
    # Setup: Create Google Calendar token with notify_clients enabled
    token = GoogleCalendarToken(
        workspace_id=workspace_1.id,
        user_id=test_user_ws1.id,
        access_token="ya29.test_access_token",
        refresh_token="1//test_refresh_token",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=True,
        sync_client_names=True,
        notify_clients=True,  # Enabled
    )
    db_session.add(token)

    # Create client with INVALID email
    client = Client(
        workspace_id=workspace_1.id,
        first_name="Invalid",
        last_name="Email",
        email="not-an-email",  # Invalid format
    )
    db_session.add(client)
    await db_session.commit()  # Commit client first to get ID

    # Create appointment
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=client.id,
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    db_session.add(appointment)
    await db_session.commit()

    # Mock Google Calendar API
    mock_service = MagicMock()
    mock_events = MagicMock()
    mock_insert = MagicMock()
    mock_execute = MagicMock(return_value={"id": "google_event_invalid_email"})

    mock_insert.execute = mock_execute
    mock_events.insert.return_value = mock_insert
    mock_service.events.return_value = mock_events
    mock_build.return_value = mock_service

    # Execute: Create calendar event (should not crash)
    google_event_id = await create_calendar_event(
        db=db_session,
        appointment_id=appointment.id,
        workspace_id=workspace_1.id,
    )

    # Assert: Event created successfully
    assert google_event_id == "google_event_invalid_email"

    # Assert: Event body does NOT include attendees (invalid email skipped)
    event_body = mock_events.insert.call_args.kwargs["body"]
    assert "attendees" not in event_body


# ============================================================================
# Edge Case Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_appointment_sync_disabled_no_event_created(
    db_session: AsyncSession,
    workspace_1: Workspace,
    test_user_ws1,
    sample_client_ws1: Client,
):
    """Test that no event is created when sync is disabled."""
    # Setup: Create Google Calendar token with sync DISABLED
    token = GoogleCalendarToken(
        workspace_id=workspace_1.id,
        user_id=test_user_ws1.id,
        access_token="ya29.test_access_token",
        refresh_token="1//test_refresh_token",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=False,  # Disabled
        sync_client_names=True,
        notify_clients=True,
    )
    db_session.add(token)

    # Update client with valid email
    sample_client_ws1.email = "client@example.com"

    # Create appointment
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    db_session.add(appointment)
    await db_session.commit()

    # Execute: Try to create calendar event
    google_event_id = await create_calendar_event(
        db=db_session,
        appointment_id=appointment.id,
        workspace_id=workspace_1.id,
    )

    # Assert: No event created (returns None)
    assert google_event_id is None


@pytest.mark.asyncio
async def test_create_appointment_no_token_no_event_created(
    db_session: AsyncSession,
    workspace_1: Workspace,
    sample_client_ws1: Client,
):
    """Test that no event is created when Google Calendar not connected."""
    # Setup: No token in database

    # Update client with valid email
    sample_client_ws1.email = "client@example.com"
    await db_session.commit()

    # Create appointment
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    db_session.add(appointment)
    await db_session.commit()

    # Execute: Try to create calendar event
    google_event_id = await create_calendar_event(
        db=db_session,
        appointment_id=appointment.id,
        workspace_id=workspace_1.id,
    )

    # Assert: No event created (returns None)
    assert google_event_id is None


@pytest.mark.asyncio
@patch("pazpaz.services.google_calendar_sync_service.build")
async def test_workspace_isolation_different_workspace_token_not_used(
    mock_build,
    db_session: AsyncSession,
    workspace_1: Workspace,
    workspace_2: Workspace,
    test_user_ws2,
    sample_client_ws1: Client,
):
    """Test that workspace 1 appointment doesn't use workspace 2's token."""
    # Setup: Create token for workspace 2 (different workspace)
    token_ws2 = GoogleCalendarToken(
        workspace_id=workspace_2.id,
        user_id=test_user_ws2.id,
        access_token="ya29.workspace2_token",
        refresh_token="1//workspace2_refresh",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=True,
        sync_client_names=True,
        notify_clients=True,
    )
    db_session.add(token_ws2)
    await db_session.commit()

    # Create appointment in workspace 1
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    db_session.add(appointment)
    await db_session.commit()

    # Execute: Try to create calendar event (should not use workspace 2's token)
    google_event_id = await create_calendar_event(
        db=db_session,
        appointment_id=appointment.id,
        workspace_id=workspace_1.id,
    )

    # Assert: No event created (no token for workspace 1)
    assert google_event_id is None

    # Assert: Google API was NOT called
    mock_build.assert_not_called()
