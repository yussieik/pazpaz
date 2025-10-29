"""Unit tests for Google Calendar Sync Service - Event Building Logic.

Tests focus on the _build_google_calendar_event function and email validation,
specifically covering the client notification feature (Phase 6).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pazpaz.models.appointment import Appointment, AppointmentStatus, LocationType
from pazpaz.models.client import Client
from pazpaz.models.location import Location
from pazpaz.models.service import Service
from pazpaz.models.workspace import Workspace
from pazpaz.services.google_calendar_sync_service import (
    _build_google_calendar_event,
    _is_valid_email,
)

# ============================================================================
# Email Validation Tests
# ============================================================================


@pytest.mark.parametrize(
    "email,expected",
    [
        # Valid emails
        ("test@example.com", True),
        ("user+tag@domain.co.uk", True),
        ("user.name@example.com", True),
        ("user_name@example.com", True),
        ("user-name@example.com", True),
        ("user123@example.com", True),
        ("test.email+tag@subdomain.example.com", True),
        # Invalid emails
        (None, False),
        ("", False),
        ("   ", False),
        ("invalid", False),
        ("no@domain", False),
        ("@domain.com", False),
        ("user@", False),
        ("user @example.com", False),
        ("user@domain .com", False),
        # Edge cases
        ("user@localhost", False),  # No TLD
        ("user@@example.com", False),
        ("user..name@example.com", True),  # Double dots are valid
    ],
)
def test_is_valid_email(email: str | None, expected: bool):
    """Test email validation with various valid and invalid formats."""
    assert _is_valid_email(email) == expected


def test_is_valid_email_with_whitespace():
    """Test email validation strips leading/trailing whitespace."""
    # Email with whitespace should be valid (validation strips it)
    # Note: _is_valid_email strips whitespace before validation
    assert _is_valid_email("  test@example.com  ") is True


# ============================================================================
# Event Building Tests - Client Notifications Enabled
# ============================================================================


def test_build_event_with_client_notification_enabled(caplog):
    """Test event building with client notification enabled and valid email."""
    # Setup: Create appointment with client that has valid email
    workspace = Workspace(
        id="00000000-0000-0000-0000-000000000001",
        name="Test Workspace",
        timezone="America/New_York",
    )
    client = Client(
        id="11111111-1111-1111-1111-111111111111",
        workspace_id=workspace.id,
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
    )
    appointment = Appointment(
        id="22222222-2222-2222-2222-222222222222",
        workspace_id=workspace.id,
        client_id=client.id,
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.CLINIC,
        location_details="Room 101",
        status=AppointmentStatus.SCHEDULED,
    )
    appointment.client = client
    appointment.workspace = workspace

    # Execute: Build event with notify_client=True
    event = _build_google_calendar_event(
        appointment=appointment,
        workspace_timezone="America/New_York",
        sync_client_names=True,
        notify_client=True,
    )

    # Assert: Attendees array should be present
    assert "attendees" in event
    assert len(event["attendees"]) == 1
    assert event["attendees"][0]["email"] == "john.doe@example.com"

    # Assert: Custom reminders should be set
    assert "reminders" in event
    assert event["reminders"]["useDefault"] is False
    assert len(event["reminders"]["overrides"]) == 2
    # Check for 24-hour (1440 minutes) and 1-hour (60 minutes) reminders
    reminder_minutes = [r["minutes"] for r in event["reminders"]["overrides"]]
    assert 1440 in reminder_minutes
    assert 60 in reminder_minutes

    # Assert: Log message should indicate notification enabled
    assert "client_notification_enabled" in caplog.text


def test_build_event_with_client_notification_disabled():
    """Test event building with client notification disabled."""
    # Setup: Create appointment with client that has email
    workspace = Workspace(
        id="00000000-0000-0000-0000-000000000001",
        name="Test Workspace",
        timezone="UTC",
    )
    client = Client(
        id="11111111-1111-1111-1111-111111111111",
        workspace_id=workspace.id,
        first_name="Jane",
        last_name="Smith",
        email="jane.smith@example.com",
    )
    appointment = Appointment(
        id="22222222-2222-2222-2222-222222222222",
        workspace_id=workspace.id,
        client_id=client.id,
        scheduled_start=datetime(2025, 11, 1, 14, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 15, 0, tzinfo=UTC),
        location_type=LocationType.ONLINE,
        status=AppointmentStatus.SCHEDULED,
    )
    appointment.client = client
    appointment.workspace = workspace

    # Execute: Build event with notify_client=False
    event = _build_google_calendar_event(
        appointment=appointment,
        workspace_timezone="UTC",
        sync_client_names=False,
        notify_client=False,
    )

    # Assert: Attendees array should NOT be present
    assert "attendees" not in event

    # Assert: Custom reminders should NOT be present
    assert "reminders" not in event


def test_build_event_client_missing_email(caplog):
    """Test event building when client has no email (notify_client=True)."""
    # Setup: Create appointment with client that has NO email
    workspace = Workspace(
        id="00000000-0000-0000-0000-000000000001",
        name="Test Workspace",
        timezone="UTC",
    )
    client = Client(
        id="11111111-1111-1111-1111-111111111111",
        workspace_id=workspace.id,
        first_name="No",
        last_name="Email",
        email=None,  # No email
    )
    appointment = Appointment(
        id="22222222-2222-2222-2222-222222222222",
        workspace_id=workspace.id,
        client_id=client.id,
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.HOME,
        status=AppointmentStatus.SCHEDULED,
    )
    appointment.client = client
    appointment.workspace = workspace

    # Execute: Build event with notify_client=True (should not crash)
    event = _build_google_calendar_event(
        appointment=appointment,
        workspace_timezone="UTC",
        sync_client_names=True,
        notify_client=True,
    )

    # Assert: Event should be created successfully (no crash)
    assert event is not None
    assert event["summary"] == "Appointment with No Email"

    # Assert: Attendees should NOT be added
    assert "attendees" not in event

    # Assert: Log message should indicate no email
    assert "client_notification_skipped_no_email" in caplog.text


def test_build_event_client_invalid_email(caplog):
    """Test event building when client has invalid email format."""
    # Setup: Create appointment with client that has invalid email
    workspace = Workspace(
        id="00000000-0000-0000-0000-000000000001",
        name="Test Workspace",
        timezone="UTC",
    )
    client = Client(
        id="11111111-1111-1111-1111-111111111111",
        workspace_id=workspace.id,
        first_name="Invalid",
        last_name="Email",
        email="invalid@",  # Invalid format
    )
    appointment = Appointment(
        id="22222222-2222-2222-2222-222222222222",
        workspace_id=workspace.id,
        client_id=client.id,
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    appointment.client = client
    appointment.workspace = workspace

    # Execute: Build event with notify_client=True
    event = _build_google_calendar_event(
        appointment=appointment,
        workspace_timezone="UTC",
        sync_client_names=True,
        notify_client=True,
    )

    # Assert: Event should be created successfully
    assert event is not None

    # Assert: Attendees should NOT be added (invalid email)
    assert "attendees" not in event

    # Assert: Log message should indicate invalid email
    assert "client_notification_skipped_invalid_email" in caplog.text


# ============================================================================
# Event Building Tests - Reminders Configuration
# ============================================================================


def test_build_event_reminders_configuration():
    """Test that reminders are configured correctly when notify_client=True."""
    # Setup
    workspace = Workspace(
        id="00000000-0000-0000-0000-000000000001",
        name="Test Workspace",
        timezone="UTC",
    )
    client = Client(
        id="11111111-1111-1111-1111-111111111111",
        workspace_id=workspace.id,
        first_name="Test",
        last_name="Client",
        email="test@example.com",
    )
    appointment = Appointment(
        id="22222222-2222-2222-2222-222222222222",
        workspace_id=workspace.id,
        client_id=client.id,
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    appointment.client = client
    appointment.workspace = workspace

    # Execute
    event = _build_google_calendar_event(
        appointment=appointment,
        workspace_timezone="UTC",
        sync_client_names=True,
        notify_client=True,
    )

    # Assert: Reminders structure
    assert event["reminders"]["useDefault"] is False
    assert len(event["reminders"]["overrides"]) == 2

    # Assert: 24-hour reminder (1440 minutes)
    reminder_24h = next(
        r for r in event["reminders"]["overrides"] if r["minutes"] == 1440
    )
    assert reminder_24h["method"] == "email"

    # Assert: 1-hour reminder (60 minutes)
    reminder_1h = next(r for r in event["reminders"]["overrides"] if r["minutes"] == 60)
    assert reminder_1h["method"] == "email"


# ============================================================================
# Event Building Tests - Edge Cases
# ============================================================================


def test_build_event_client_email_with_whitespace():
    """Test that client email with leading/trailing whitespace is handled."""
    # Setup
    workspace = Workspace(
        id="00000000-0000-0000-0000-000000000001",
        name="Test Workspace",
        timezone="UTC",
    )
    client = Client(
        id="11111111-1111-1111-1111-111111111111",
        workspace_id=workspace.id,
        first_name="Whitespace",
        last_name="Email",
        email="  test@example.com  ",  # Whitespace
    )
    appointment = Appointment(
        id="22222222-2222-2222-2222-222222222222",
        workspace_id=workspace.id,
        client_id=client.id,
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    appointment.client = client
    appointment.workspace = workspace

    # Execute
    event = _build_google_calendar_event(
        appointment=appointment,
        workspace_timezone="UTC",
        sync_client_names=True,
        notify_client=True,
    )

    # Assert: Email should be stripped of whitespace
    assert "attendees" in event
    assert event["attendees"][0]["email"] == "test@example.com"


def test_build_event_client_empty_string_email(caplog):
    """Test that empty string email is handled gracefully."""
    # Setup
    workspace = Workspace(
        id="00000000-0000-0000-0000-000000000001",
        name="Test Workspace",
        timezone="UTC",
    )
    client = Client(
        id="11111111-1111-1111-1111-111111111111",
        workspace_id=workspace.id,
        first_name="Empty",
        last_name="Email",
        email="",  # Empty string
    )
    appointment = Appointment(
        id="22222222-2222-2222-2222-222222222222",
        workspace_id=workspace.id,
        client_id=client.id,
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    appointment.client = client
    appointment.workspace = workspace

    # Execute
    event = _build_google_calendar_event(
        appointment=appointment,
        workspace_timezone="UTC",
        sync_client_names=True,
        notify_client=True,
    )

    # Assert: No attendees should be added
    assert "attendees" not in event


def test_build_event_no_client_with_notify_enabled():
    """Test event building when notify_client=True but appointment has no client."""
    # Setup: Appointment without client
    workspace = Workspace(
        id="00000000-0000-0000-0000-000000000001",
        name="Test Workspace",
        timezone="UTC",
    )
    appointment = Appointment(
        id="22222222-2222-2222-2222-222222222222",
        workspace_id=workspace.id,
        client_id=None,  # No client
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    appointment.client = None
    appointment.workspace = workspace

    # Execute
    event = _build_google_calendar_event(
        appointment=appointment,
        workspace_timezone="UTC",
        sync_client_names=True,
        notify_client=True,
    )

    # Assert: No crash, attendees not added
    assert event is not None
    assert "attendees" not in event


# ============================================================================
# Event Building Tests - General Event Structure
# ============================================================================


def test_build_event_basic_structure():
    """Test that basic event structure is correct."""
    # Setup
    workspace = Workspace(
        id="00000000-0000-0000-0000-000000000001",
        name="Test Workspace",
        timezone="Asia/Jerusalem",
    )
    client = Client(
        id="11111111-1111-1111-1111-111111111111",
        workspace_id=workspace.id,
        first_name="Test",
        last_name="Client",
    )
    appointment = Appointment(
        id="22222222-2222-2222-2222-222222222222",
        workspace_id=workspace.id,
        client_id=client.id,
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.CLINIC,
        location_details="Room 202",
        status=AppointmentStatus.SCHEDULED,
    )
    appointment.client = client
    appointment.workspace = workspace

    # Execute
    event = _build_google_calendar_event(
        appointment=appointment,
        workspace_timezone="Asia/Jerusalem",
        sync_client_names=True,
        notify_client=False,
    )

    # Assert: Required fields
    assert "summary" in event
    assert "start" in event
    assert "end" in event
    assert event["start"]["timeZone"] == "Asia/Jerusalem"
    assert event["end"]["timeZone"] == "Asia/Jerusalem"
    assert "description" in event
    assert "location" in event


def test_build_event_with_sync_client_names_enabled():
    """Test event summary includes client name when sync_client_names=True."""
    # Setup
    workspace = Workspace(
        id="00000000-0000-0000-0000-000000000001",
        name="Test Workspace",
        timezone="UTC",
    )
    client = Client(
        id="11111111-1111-1111-1111-111111111111",
        workspace_id=workspace.id,
        first_name="John",
        last_name="Doe",
    )
    appointment = Appointment(
        id="22222222-2222-2222-2222-222222222222",
        workspace_id=workspace.id,
        client_id=client.id,
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    appointment.client = client
    appointment.workspace = workspace

    # Execute
    event = _build_google_calendar_event(
        appointment=appointment,
        workspace_timezone="UTC",
        sync_client_names=True,
        notify_client=False,
    )

    # Assert: Summary includes client name
    assert event["summary"] == "Appointment with John Doe"


def test_build_event_with_sync_client_names_disabled():
    """Test event summary does NOT include client name when sync_client_names=False."""
    # Setup
    workspace = Workspace(
        id="00000000-0000-0000-0000-000000000001",
        name="Test Workspace",
        timezone="UTC",
    )
    client = Client(
        id="11111111-1111-1111-1111-111111111111",
        workspace_id=workspace.id,
        first_name="John",
        last_name="Doe",
    )
    appointment = Appointment(
        id="22222222-2222-2222-2222-222222222222",
        workspace_id=workspace.id,
        client_id=client.id,
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    appointment.client = client
    appointment.workspace = workspace

    # Execute
    event = _build_google_calendar_event(
        appointment=appointment,
        workspace_timezone="UTC",
        sync_client_names=False,
        notify_client=False,
    )

    # Assert: Summary is generic
    assert event["summary"] == "Appointment"


def test_build_event_with_location_and_service():
    """Test event includes location and service in description."""
    # Setup
    workspace = Workspace(
        id="00000000-0000-0000-0000-000000000001",
        name="Test Workspace",
        timezone="UTC",
    )
    client = Client(
        id="11111111-1111-1111-1111-111111111111",
        workspace_id=workspace.id,
        first_name="Test",
        last_name="Client",
    )
    location = Location(
        id="33333333-3333-3333-3333-333333333333",
        workspace_id=workspace.id,
        name="Downtown Clinic",
        address="123 Main St",
    )
    service = Service(
        id="44444444-4444-4444-4444-444444444444",
        workspace_id=workspace.id,
        name="Massage Therapy",
    )
    appointment = Appointment(
        id="22222222-2222-2222-2222-222222222222",
        workspace_id=workspace.id,
        client_id=client.id,
        location_id=location.id,
        service_id=service.id,
        scheduled_start=datetime(2025, 11, 1, 10, 0, tzinfo=UTC),
        scheduled_end=datetime(2025, 11, 1, 11, 0, tzinfo=UTC),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
        notes="First session",
    )
    appointment.client = client
    appointment.workspace = workspace
    appointment.location = location
    appointment.service = service

    # Execute
    event = _build_google_calendar_event(
        appointment=appointment,
        workspace_timezone="UTC",
        sync_client_names=True,
        notify_client=False,
    )

    # Assert: Description includes service and location
    assert "Massage Therapy" in event["description"]
    assert "Downtown Clinic" in event["description"]
    assert "123 Main St" in event["location"]
    assert "First session" in event["description"]
