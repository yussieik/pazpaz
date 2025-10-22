"""Integration tests for arq worker scheduler tasks.

Simplified tests for Phase 3 implementation focusing on basic functionality.
These tests verify that scheduled tasks can execute without errors.
"""

from datetime import UTC, datetime, time, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest

from pazpaz.models.appointment import Appointment, AppointmentStatus, LocationType
from pazpaz.models.session import Session
from pazpaz.models.user_notification_settings import UserNotificationSettings
from pazpaz.workers.scheduler import (
    send_appointment_reminders,
    send_daily_digests,
    send_session_notes_reminders,
)


@pytest.mark.asyncio
class TestSchedulerTasks:
    """Test arq scheduler tasks can execute successfully."""

    async def test_session_notes_reminders_executes(
        self, db_session, workspace_1, test_user_ws1, sample_client_ws1
    ):
        """Test send_session_notes_reminders task executes without error."""
        # Configure user notification settings for 18:00
        settings = UserNotificationSettings(
            id=uuid4(),
            workspace_id=workspace_1.id,
            user_id=test_user_ws1.id,
            email_enabled=True,
            notes_reminder_enabled=True,
            notes_reminder_time="18:00",
        )
        db_session.add(settings)

        # Create draft session with all required fields
        session = Session(
            id=uuid4(),
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            session_date=datetime.now(UTC),
            is_draft=True,
        )
        db_session.add(session)
        await db_session.commit()

        # Mock email sending and time
        with patch(
            "pazpaz.workers.scheduler.send_session_notes_reminder"
        ) as mock_send, patch(
            "pazpaz.workers.scheduler.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = datetime(
                2025, 10, 22, 18, 0, 0, tzinfo=UTC
            )

            # Run task - should not raise exceptions
            result = await send_session_notes_reminders({})

            # Verify result structure
            assert "sent" in result
            assert "errors" in result
            assert isinstance(result["sent"], int)
            assert isinstance(result["errors"], int)

            # Verify email was attempted
            assert mock_send.called or result["sent"] == 1

    async def test_daily_digests_executes(
        self, db_session, workspace_1, test_user_ws1, sample_client_ws1
    ):
        """Test send_daily_digests task executes without error."""
        # Configure user notification settings
        settings = UserNotificationSettings(
            id=uuid4(),
            workspace_id=workspace_1.id,
            user_id=test_user_ws1.id,
            email_enabled=True,
            digest_enabled=True,
            digest_time="08:00",
            digest_skip_weekends=False,
        )
        db_session.add(settings)

        # Create appointment for today
        today = datetime.now(UTC).date()
        appointment = Appointment(
            id=uuid4(),
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.combine(today, time(10, 0), tzinfo=UTC),
            scheduled_end=datetime.combine(today, time(11, 0), tzinfo=UTC),
            status=AppointmentStatus.SCHEDULED,
            location_type=LocationType.CLINIC,
        )
        db_session.add(appointment)
        await db_session.commit()

        # Mock email sending and time
        with patch("pazpaz.workers.scheduler.send_daily_digest") as mock_send, patch(
            "pazpaz.workers.scheduler.datetime"
        ) as mock_datetime:
            mock_now = datetime(2025, 10, 22, 8, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min
            mock_datetime.max = datetime.max

            # Run task - should not raise exceptions
            result = await send_daily_digests({})

            # Verify result structure
            assert "sent" in result
            assert "errors" in result
            assert "skipped_weekend" in result
            assert isinstance(result["sent"], int)
            assert isinstance(result["errors"], int)

    async def test_appointment_reminders_executes(
        self, db_session, workspace_1, test_user_ws1, sample_client_ws1
    ):
        """Test send_appointment_reminders task executes without error."""
        # Configure user notification settings
        settings = UserNotificationSettings(
            id=uuid4(),
            workspace_id=workspace_1.id,
            user_id=test_user_ws1.id,
            email_enabled=True,
            reminder_enabled=True,
            reminder_minutes=60,
        )
        db_session.add(settings)

        # Create appointment 60 minutes from now
        now = datetime.now(UTC)
        appointment_time = now + timedelta(minutes=60)
        appointment = Appointment(
            id=uuid4(),
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=appointment_time,
            scheduled_end=appointment_time + timedelta(hours=1),
            status=AppointmentStatus.SCHEDULED,
            location_type=LocationType.CLINIC,
        )
        db_session.add(appointment)
        await db_session.commit()

        # Mock email sending and time
        with patch(
            "pazpaz.workers.scheduler.send_appointment_reminder"
        ) as mock_send, patch(
            "pazpaz.workers.scheduler.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = now

            # Run task - should not raise exceptions
            result = await send_appointment_reminders({})

            # Verify result structure
            assert "sent" in result
            assert "errors" in result
            assert isinstance(result["sent"], int)
            assert isinstance(result["errors"], int)

    async def test_tasks_handle_empty_results(self, db_session):
        """Test that tasks handle no matching users/appointments gracefully."""
        # Run all tasks with no matching data
        with patch("pazpaz.workers.scheduler.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(
                2025, 10, 22, 3, 0, 0, tzinfo=UTC
            )

            # All should return zero sent
            result_notes = await send_session_notes_reminders({})
            assert result_notes["sent"] == 0
            assert result_notes["errors"] == 0

            result_digest = await send_daily_digests({})
            assert result_digest["sent"] == 0
            assert result_digest["errors"] == 0

            result_appt = await send_appointment_reminders({})
            assert result_appt["sent"] == 0
            assert result_appt["errors"] == 0
