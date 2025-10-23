"""Integration tests for arq worker scheduler tasks.

Tests for Phase 3 & 4 implementation including reminder deduplication.
These tests verify that scheduled tasks execute correctly and that
appointment reminders are not sent multiple times.
"""

from datetime import UTC, datetime, time, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from pazpaz.models.appointment import Appointment, AppointmentStatus, LocationType
from pazpaz.models.appointment_reminder import AppointmentReminderSent
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
            digest_days=[0, 1, 2, 3, 4, 5, 6],  # All days
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
            assert "timezones_checked" in result
            assert isinstance(result["sent"], int)
            assert isinstance(result["errors"], int)
            assert isinstance(result["timezones_checked"], int)

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


@pytest.mark.asyncio
class TestAppointmentReminderDeduplication:
    """Test appointment reminder deduplication tracking (Phase 4)."""

    async def test_reminder_not_sent_twice(
        self, db_session, workspace_1, test_user_ws1, sample_client_ws1
    ):
        """Test that same reminder is not sent twice."""
        # Configure user notification settings for 30-minute reminders
        settings = UserNotificationSettings(
            id=uuid4(),
            workspace_id=workspace_1.id,
            user_id=test_user_ws1.id,
            email_enabled=True,
            reminder_enabled=True,
            reminder_minutes=30,
        )
        db_session.add(settings)

        # Create appointment 30 minutes from now
        now = datetime.now(UTC)
        appointment_time = now + timedelta(minutes=30)
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
        await db_session.refresh(appointment)
        await db_session.refresh(sample_client_ws1)

        # Mock email sending
        with patch(
            "pazpaz.workers.scheduler.send_appointment_reminder"
        ) as mock_send, patch(
            "pazpaz.workers.scheduler.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = now

            # First run - should send reminder
            result1 = await send_appointment_reminders({})
            assert result1["sent"] == 1
            assert result1["errors"] == 0
            assert result1["already_sent"] == 0

            # Verify reminder was marked as sent
            stmt = select(AppointmentReminderSent).where(
                AppointmentReminderSent.appointment_id == appointment.id,
                AppointmentReminderSent.user_id == test_user_ws1.id,
            )
            result = await db_session.execute(stmt)
            reminder_record = result.scalar_one_or_none()
            assert reminder_record is not None

            # Second run (simulating worker running again) - should NOT send
            result2 = await send_appointment_reminders({})
            assert result2["sent"] == 0
            assert result2["errors"] == 0
            assert result2["already_sent"] == 1

            # Verify email was only sent once
            assert mock_send.call_count == 1

    async def test_different_reminder_types_tracked_separately(
        self, db_session, workspace_1, test_user_ws1, sample_client_ws1
    ):
        """Test that different reminder types can be sent for same appointment."""
        # Configure user for 60-minute reminders initially
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
        await db_session.refresh(appointment)
        await db_session.refresh(sample_client_ws1)

        with patch(
            "pazpaz.workers.scheduler.send_appointment_reminder"
        ) as mock_send, patch(
            "pazpaz.workers.scheduler.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = now

            # Send 60-minute reminder
            result1 = await send_appointment_reminders({})
            assert result1["sent"] == 1
            assert result1["already_sent"] == 0

            # Change user preference to 30-minute reminders
            settings.reminder_minutes = 30
            db_session.add(settings)
            await db_session.commit()

            # Move time forward to 30 minutes before appointment
            later_time = now + timedelta(minutes=30)
            mock_datetime.now.return_value = later_time
            appointment.scheduled_start = later_time + timedelta(minutes=30)
            db_session.add(appointment)
            await db_session.commit()

            # Send 30-minute reminder - should succeed (different type)
            result2 = await send_appointment_reminders({})
            assert result2["sent"] == 1
            assert result2["already_sent"] == 0

            # Verify both reminders tracked
            stmt = select(AppointmentReminderSent).where(
                AppointmentReminderSent.appointment_id == appointment.id,
                AppointmentReminderSent.user_id == test_user_ws1.id,
            )
            result = await db_session.execute(stmt)
            reminders = list(result.scalars().all())
            assert len(reminders) == 2

    async def test_multiple_users_tracked_separately(
        self, db_session, workspace_1, test_user_ws1, sample_client_ws1
    ):
        """Test that reminders for different users are tracked independently."""
        from pazpaz.models.user import User, UserRole

        # Create second user
        user2 = User(
            id=uuid4(),
            workspace_id=workspace_1.id,
            email="assistant@test.com",
            full_name="Test Assistant",
            role=UserRole.ASSISTANT,
            is_active=True,
        )
        db_session.add(user2)
        await db_session.commit()
        await db_session.refresh(user2)

        # Configure notification settings for both users
        settings1 = UserNotificationSettings(
            id=uuid4(),
            workspace_id=workspace_1.id,
            user_id=test_user_ws1.id,
            email_enabled=True,
            reminder_enabled=True,
            reminder_minutes=30,
        )
        settings2 = UserNotificationSettings(
            id=uuid4(),
            workspace_id=workspace_1.id,
            user_id=user2.id,
            email_enabled=True,
            reminder_enabled=True,
            reminder_minutes=30,
        )
        db_session.add(settings1)
        db_session.add(settings2)

        # Create appointment
        now = datetime.now(UTC)
        appointment_time = now + timedelta(minutes=30)
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
        await db_session.refresh(appointment)
        await db_session.refresh(sample_client_ws1)

        with patch(
            "pazpaz.workers.scheduler.send_appointment_reminder"
        ) as mock_send, patch(
            "pazpaz.workers.scheduler.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = now

            # First run - should send to both users
            result1 = await send_appointment_reminders({})
            assert result1["sent"] == 2
            assert result1["already_sent"] == 0

            # Second run - should not send to either user
            result2 = await send_appointment_reminders({})
            assert result2["sent"] == 0
            assert result2["already_sent"] == 2

            # Verify separate tracking records
            stmt = select(AppointmentReminderSent).where(
                AppointmentReminderSent.appointment_id == appointment.id
            )
            result = await db_session.execute(stmt)
            reminders = list(result.scalars().all())
            assert len(reminders) == 2

            user_ids = {r.user_id for r in reminders}
            assert test_user_ws1.id in user_ids
            assert user2.id in user_ids
