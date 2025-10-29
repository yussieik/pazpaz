"""End-to-end integration tests for Google Calendar sync with client notifications.

Tests focus on the full sync flow from appointment creation/update to Google Calendar API calls,
specifically testing the notify_clients feature and sendUpdates parameter.
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
# End-to-End Tests - Create Event with Notifications
# ============================================================================


@pytest.mark.asyncio
@patch("pazpaz.services.google_calendar_sync_service.build")
async def test_create_event_with_notify_clients_sends_updates(
    mock_build,
    db_session: AsyncSession,
    workspace_1: Workspace,
    test_user_ws1,
    sample_client_ws1: Client,
):
    """Test that create_calendar_event calls Google API with sendUpdates='all' when notify_clients=True."""
    # Setup: Create token with notify_clients enabled
    token = GoogleCalendarToken(
        workspace_id=workspace_1.id,
        user_id=test_user_ws1.id,
        access_token="ya29.test_token",
        refresh_token="1//test_refresh",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=True,
        sync_client_names=True,
        notify_clients=True,  # Enable client notifications
    )
    db_session.add(token)

    # Ensure client has valid email
    sample_client_ws1.email = "client@example.com"
    db_session.add(sample_client_ws1)

    # Create appointment
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        scheduled_start=datetime.now(UTC) + timedelta(days=1),
        scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    db_session.add(appointment)
    await db_session.commit()

    # Mock Google Calendar API
    mock_service = MagicMock()
    mock_events = MagicMock()
    mock_insert = MagicMock()
    mock_execute = MagicMock(return_value={"id": "gcal_event_123"})

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

    # Assert: Event was created
    assert google_event_id == "gcal_event_123"

    # Assert: insert() was called with sendUpdates="all"
    mock_events.insert.assert_called_once()
    call_kwargs = mock_events.insert.call_args[1]
    assert call_kwargs["sendUpdates"] == "all"
    assert call_kwargs["calendarId"] == "primary"
    assert "body" in call_kwargs

    # Assert: Event body includes attendees
    event_body = call_kwargs["body"]
    assert "attendees" in event_body
    assert event_body["attendees"][0]["email"] == "client@example.com"


@pytest.mark.asyncio
@patch("pazpaz.services.google_calendar_sync_service.build")
async def test_create_event_without_notify_clients_no_updates(
    mock_build,
    db_session: AsyncSession,
    workspace_1: Workspace,
    test_user_ws1,
    sample_client_ws1: Client,
):
    """Test that create_calendar_event calls Google API with sendUpdates='none' when notify_clients=False."""
    # Setup: Create token with notify_clients disabled
    token = GoogleCalendarToken(
        workspace_id=workspace_1.id,
        user_id=test_user_ws1.id,
        access_token="ya29.test_token",
        refresh_token="1//test_refresh",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=True,
        sync_client_names=True,
        notify_clients=False,  # Disable client notifications
    )
    db_session.add(token)

    # Ensure client has valid email (but shouldn't be used)
    sample_client_ws1.email = "client@example.com"
    db_session.add(sample_client_ws1)

    # Create appointment
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        scheduled_start=datetime.now(UTC) + timedelta(days=1),
        scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    db_session.add(appointment)
    await db_session.commit()

    # Mock Google Calendar API
    mock_service = MagicMock()
    mock_events = MagicMock()
    mock_insert = MagicMock()
    mock_execute = MagicMock(return_value={"id": "gcal_event_456"})

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

    # Assert: Event was created
    assert google_event_id == "gcal_event_456"

    # Assert: insert() was called with sendUpdates="none"
    mock_events.insert.assert_called_once()
    call_kwargs = mock_events.insert.call_args[1]
    assert call_kwargs["sendUpdates"] == "none"

    # Assert: Event body does NOT include attendees
    event_body = call_kwargs["body"]
    assert "attendees" not in event_body


# ============================================================================
# End-to-End Tests - Update Event with Notifications
# ============================================================================


@pytest.mark.asyncio
@patch("pazpaz.services.google_calendar_sync_service.build")
async def test_update_event_with_notify_clients_sends_updates(
    mock_build,
    db_session: AsyncSession,
    workspace_1: Workspace,
    test_user_ws1,
    sample_client_ws1: Client,
):
    """Test that update_calendar_event calls Google API with sendUpdates='all' when notify_clients=True."""
    # Setup: Create token with notify_clients enabled
    token = GoogleCalendarToken(
        workspace_id=workspace_1.id,
        user_id=test_user_ws1.id,
        access_token="ya29.test_token",
        refresh_token="1//test_refresh",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=True,
        sync_client_names=True,
        notify_clients=True,  # Enable client notifications
    )
    db_session.add(token)

    # Ensure client has valid email
    sample_client_ws1.email = "client@example.com"
    db_session.add(sample_client_ws1)

    # Create appointment with existing google_event_id
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        scheduled_start=datetime.now(UTC) + timedelta(days=1),
        scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
        google_event_id="existing_gcal_event_789",
    )
    db_session.add(appointment)
    await db_session.commit()

    # Mock Google Calendar API
    mock_service = MagicMock()
    mock_events = MagicMock()
    mock_update = MagicMock()
    mock_execute = MagicMock(return_value={"id": "existing_gcal_event_789"})

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
    call_kwargs = mock_events.update.call_args[1]
    assert call_kwargs["sendUpdates"] == "all"
    assert call_kwargs["calendarId"] == "primary"
    assert call_kwargs["eventId"] == "existing_gcal_event_789"

    # Assert: Event body includes attendees
    event_body = call_kwargs["body"]
    assert "attendees" in event_body
    assert event_body["attendees"][0]["email"] == "client@example.com"


@pytest.mark.asyncio
@patch("pazpaz.services.google_calendar_sync_service.build")
async def test_update_event_without_notify_clients_no_updates(
    mock_build,
    db_session: AsyncSession,
    workspace_1: Workspace,
    test_user_ws1,
    sample_client_ws1: Client,
):
    """Test that update_calendar_event calls Google API with sendUpdates='none' when notify_clients=False."""
    # Setup: Create token with notify_clients disabled
    token = GoogleCalendarToken(
        workspace_id=workspace_1.id,
        user_id=test_user_ws1.id,
        access_token="ya29.test_token",
        refresh_token="1//test_refresh",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=True,
        sync_client_names=True,
        notify_clients=False,  # Disable client notifications
    )
    db_session.add(token)

    # Ensure client has valid email (but shouldn't be used)
    sample_client_ws1.email = "client@example.com"
    db_session.add(sample_client_ws1)

    # Create appointment with existing google_event_id
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        scheduled_start=datetime.now(UTC) + timedelta(days=1),
        scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
        google_event_id="existing_gcal_event_999",
    )
    db_session.add(appointment)
    await db_session.commit()

    # Mock Google Calendar API
    mock_service = MagicMock()
    mock_events = MagicMock()
    mock_update = MagicMock()
    mock_execute = MagicMock(return_value={"id": "existing_gcal_event_999"})

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

    # Assert: update() was called with sendUpdates="none"
    mock_events.update.assert_called_once()
    call_kwargs = mock_events.update.call_args[1]
    assert call_kwargs["sendUpdates"] == "none"

    # Assert: Event body does NOT include attendees
    event_body = call_kwargs["body"]
    assert "attendees" not in event_body


# ============================================================================
# End-to-End Tests - Edge Cases
# ============================================================================


@pytest.mark.asyncio
@patch("pazpaz.services.google_calendar_sync_service.build")
async def test_create_event_client_no_email_no_error(
    mock_build,
    db_session: AsyncSession,
    workspace_1: Workspace,
    test_user_ws1,
    sample_client_ws1: Client,
):
    """Test that create_calendar_event completes successfully when client has no email."""
    # Setup: Create token with notify_clients enabled
    token = GoogleCalendarToken(
        workspace_id=workspace_1.id,
        user_id=test_user_ws1.id,
        access_token="ya29.test_token",
        refresh_token="1//test_refresh",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=True,
        sync_client_names=True,
        notify_clients=True,  # Enable notifications (but client has no email)
    )
    db_session.add(token)

    # Client has NO email
    sample_client_ws1.email = None
    db_session.add(sample_client_ws1)

    # Create appointment
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        scheduled_start=datetime.now(UTC) + timedelta(days=1),
        scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    db_session.add(appointment)
    await db_session.commit()

    # Mock Google Calendar API
    mock_service = MagicMock()
    mock_events = MagicMock()
    mock_insert = MagicMock()
    mock_execute = MagicMock(return_value={"id": "gcal_event_no_email"})

    mock_insert.execute = mock_execute
    mock_events.insert.return_value = mock_insert
    mock_service.events.return_value = mock_events
    mock_build.return_value = mock_service

    # Execute: Create calendar event (should NOT crash)
    google_event_id = await create_calendar_event(
        db=db_session,
        appointment_id=appointment.id,
        workspace_id=workspace_1.id,
    )

    # Assert: Event was created successfully
    assert google_event_id == "gcal_event_no_email"

    # Assert: sendUpdates should still be "all" (even though no attendees)
    mock_events.insert.assert_called_once()
    call_kwargs = mock_events.insert.call_args[1]
    assert call_kwargs["sendUpdates"] == "all"

    # Assert: Event body does NOT include attendees (no email)
    event_body = call_kwargs["body"]
    assert "attendees" not in event_body


@pytest.mark.asyncio
@patch("pazpaz.services.google_calendar_sync_service.build")
async def test_sync_multiple_appointments_mixed_settings(
    mock_build,
    db_session: AsyncSession,
    workspace_1: Workspace,
    test_user_ws1,
):
    """Test syncing multiple appointments with mixed client email scenarios."""
    # Setup: Create token with notify_clients enabled
    token = GoogleCalendarToken(
        workspace_id=workspace_1.id,
        user_id=test_user_ws1.id,
        access_token="ya29.test_token",
        refresh_token="1//test_refresh",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=True,
        sync_client_names=True,
        notify_clients=True,
    )
    db_session.add(token)

    # Client 1: Has valid email
    client_1 = Client(
        workspace_id=workspace_1.id,
        first_name="Client",
        last_name="WithEmail",
        email="client1@example.com",
    )
    db_session.add(client_1)

    # Client 2: No email
    client_2 = Client(
        workspace_id=workspace_1.id,
        first_name="Client",
        last_name="NoEmail",
        email=None,
    )
    db_session.add(client_2)

    # Client 3: Invalid email
    client_3 = Client(
        workspace_id=workspace_1.id,
        first_name="Client",
        last_name="InvalidEmail",
        email="invalid@",
    )
    db_session.add(client_3)

    await db_session.commit()

    # Create appointments
    appointment_1 = Appointment(
        workspace_id=workspace_1.id,
        client_id=client_1.id,
        scheduled_start=datetime.now(UTC) + timedelta(days=1),
        scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    appointment_2 = Appointment(
        workspace_id=workspace_1.id,
        client_id=client_2.id,
        scheduled_start=datetime.now(UTC) + timedelta(days=2),
        scheduled_end=datetime.now(UTC) + timedelta(days=2, hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    appointment_3 = Appointment(
        workspace_id=workspace_1.id,
        client_id=client_3.id,
        scheduled_start=datetime.now(UTC) + timedelta(days=3),
        scheduled_end=datetime.now(UTC) + timedelta(days=3, hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    db_session.add_all([appointment_1, appointment_2, appointment_3])
    await db_session.commit()

    # Mock Google Calendar API
    mock_service = MagicMock()
    mock_events = MagicMock()
    call_count = 0

    def mock_insert_execute():
        nonlocal call_count
        call_count += 1
        return {"id": f"gcal_event_{call_count}"}

    mock_insert = MagicMock()
    mock_insert.execute = mock_insert_execute
    mock_events.insert.return_value = mock_insert
    mock_service.events.return_value = mock_events
    mock_build.return_value = mock_service

    # Execute: Create all three calendar events
    result_1 = await create_calendar_event(
        db=db_session, appointment_id=appointment_1.id, workspace_id=workspace_1.id
    )
    result_2 = await create_calendar_event(
        db=db_session, appointment_id=appointment_2.id, workspace_id=workspace_1.id
    )
    result_3 = await create_calendar_event(
        db=db_session, appointment_id=appointment_3.id, workspace_id=workspace_1.id
    )

    # Assert: All events created successfully
    assert result_1 == "gcal_event_1"
    assert result_2 == "gcal_event_2"
    assert result_3 == "gcal_event_3"

    # Assert: insert() was called 3 times
    assert mock_events.insert.call_count == 3

    # Assert: First appointment has attendees
    first_call_kwargs = mock_events.insert.call_args_list[0][1]
    assert "attendees" in first_call_kwargs["body"]
    assert first_call_kwargs["body"]["attendees"][0]["email"] == "client1@example.com"

    # Assert: Second appointment has NO attendees (no email)
    second_call_kwargs = mock_events.insert.call_args_list[1][1]
    assert "attendees" not in second_call_kwargs["body"]

    # Assert: Third appointment has NO attendees (invalid email)
    third_call_kwargs = mock_events.insert.call_args_list[2][1]
    assert "attendees" not in third_call_kwargs["body"]


@pytest.mark.asyncio
@patch("pazpaz.services.google_calendar_sync_service.build")
async def test_create_event_when_sync_disabled_returns_none(
    mock_build,
    db_session: AsyncSession,
    workspace_1: Workspace,
    test_user_ws1,
    sample_client_ws1: Client,
):
    """Test that create_calendar_event returns None when sync is disabled."""
    # Setup: Create token with enabled=False
    token = GoogleCalendarToken(
        workspace_id=workspace_1.id,
        user_id=test_user_ws1.id,
        access_token="ya29.test_token",
        refresh_token="1//test_refresh",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=False,  # Sync disabled
        sync_client_names=True,
        notify_clients=True,
    )
    db_session.add(token)

    # Create appointment
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        scheduled_start=datetime.now(UTC) + timedelta(days=1),
        scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    db_session.add(appointment)
    await db_session.commit()

    # Execute: Create calendar event
    google_event_id = await create_calendar_event(
        db=db_session,
        appointment_id=appointment.id,
        workspace_id=workspace_1.id,
    )

    # Assert: No event created (sync disabled)
    assert google_event_id is None

    # Assert: Google Calendar API was never called
    mock_build.assert_not_called()
