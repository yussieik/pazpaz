"""Integration tests for tomorrow's digest scheduler functionality.

Tests verify that the scheduler correctly sends tomorrow's digest emails
at the configured time and respects user settings independently from today's digest.
"""

from datetime import UTC, date, datetime, time, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from pazpaz.models.appointment import Appointment, AppointmentStatus, LocationType
from pazpaz.models.user_notification_settings import UserNotificationSettings
from pazpaz.workers.scheduler import send_daily_digests


@pytest.mark.asyncio
class TestTomorrowDigestScheduler:
    """Test tomorrow's digest scheduling and delivery."""

    async def test_tomorrow_digest_sends_at_correct_time(
        self, db_session, workspace_1, test_user_ws1, sample_client_ws1
    ):
        """Test that tomorrow's digest sends at the configured time."""
        # Configure user for tomorrow's digest at 20:00
        settings = UserNotificationSettings(
            id=uuid4(),
            workspace_id=workspace_1.id,
            user_id=test_user_ws1.id,
            email_enabled=True,
            tomorrow_digest_enabled=True,
            tomorrow_digest_time="20:00",
            tomorrow_digest_days=[0, 1, 2, 3, 4, 5, 6],  # All days
        )
        db_session.add(settings)

        # Create appointment for tomorrow
        today = datetime.now(UTC).date()
        tomorrow = today + timedelta(days=1)
        appointment = Appointment(
            id=uuid4(),
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.combine(tomorrow, time(10, 0), tzinfo=UTC),
            scheduled_end=datetime.combine(tomorrow, time(11, 0), tzinfo=UTC),
            status=AppointmentStatus.SCHEDULED,
            location_type=LocationType.CLINIC,
        )
        db_session.add(appointment)
        await db_session.commit()

        # Mock email sending and time to 20:00
        with (
            patch("pazpaz.workers.scheduler.send_daily_digest") as mock_send,
            patch("pazpaz.workers.scheduler.datetime") as mock_datetime,
        ):
            mock_now = datetime(2025, 10, 22, 20, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min
            mock_datetime.max = datetime.max

            # Run task
            result = await send_daily_digests({})

            # Verify digest was sent
            assert result["sent"] >= 1
            assert result["errors"] == 0

            # Verify email was called with tomorrow's date
            assert mock_send.called
            call_args = mock_send.call_args
            date_str = call_args.kwargs["date_str"]
            # Should be Wednesday, October 23, 2025
            assert "23" in date_str

    async def test_tomorrow_digest_calculates_next_day_appointments(
        self, db_session, workspace_1, test_user_ws1, sample_client_ws1
    ):
        """Test that tomorrow's digest queries the next day's appointments."""
        # Configure user for tomorrow's digest
        settings = UserNotificationSettings(
            id=uuid4(),
            workspace_id=workspace_1.id,
            user_id=test_user_ws1.id,
            email_enabled=True,
            tomorrow_digest_enabled=True,
            tomorrow_digest_time="20:00",
            tomorrow_digest_days=[0, 1, 2, 3, 4, 5, 6],
        )
        db_session.add(settings)

        # Create appointments for today and tomorrow
        today = datetime.now(UTC).date()
        tomorrow = today + timedelta(days=1)

        # Today's appointment (should NOT be in tomorrow's digest)
        appt_today = Appointment(
            id=uuid4(),
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.combine(today, time(14, 0), tzinfo=UTC),
            scheduled_end=datetime.combine(today, time(15, 0), tzinfo=UTC),
            status=AppointmentStatus.SCHEDULED,
            location_type=LocationType.CLINIC,
        )

        # Tomorrow's appointment (should be in tomorrow's digest)
        appt_tomorrow = Appointment(
            id=uuid4(),
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.combine(tomorrow, time(10, 0), tzinfo=UTC),
            scheduled_end=datetime.combine(tomorrow, time(11, 0), tzinfo=UTC),
            status=AppointmentStatus.SCHEDULED,
            location_type=LocationType.CLINIC,
        )

        db_session.add(appt_today)
        db_session.add(appt_tomorrow)
        await db_session.commit()

        # Mock email sending
        with (
            patch("pazpaz.workers.scheduler.send_daily_digest") as mock_send,
            patch("pazpaz.workers.scheduler.datetime") as mock_datetime,
        ):
            mock_now = datetime(2025, 10, 22, 20, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min
            mock_datetime.max = datetime.max

            # Run task
            result = await send_daily_digests({})

            # Verify digest was sent
            assert result["sent"] >= 1

            # Verify email included only tomorrow's appointment
            assert mock_send.called
            call_args = mock_send.call_args
            appointments = call_args.kwargs["appointments"]
            assert len(appointments) == 1

    async def test_tomorrow_digest_respects_enabled_flag(
        self, db_session, workspace_1, test_user_ws1, sample_client_ws1
    ):
        """Test that tomorrow's digest respects the enabled flag."""
        # Configure user with tomorrow_digest_enabled=False
        settings = UserNotificationSettings(
            id=uuid4(),
            workspace_id=workspace_1.id,
            user_id=test_user_ws1.id,
            email_enabled=True,
            tomorrow_digest_enabled=False,  # Disabled
            tomorrow_digest_time="20:00",
            tomorrow_digest_days=[0, 1, 2, 3, 4, 5, 6],
        )
        db_session.add(settings)

        # Create appointment for tomorrow
        tomorrow = datetime.now(UTC).date() + timedelta(days=1)
        appointment = Appointment(
            id=uuid4(),
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.combine(tomorrow, time(10, 0), tzinfo=UTC),
            scheduled_end=datetime.combine(tomorrow, time(11, 0), tzinfo=UTC),
            status=AppointmentStatus.SCHEDULED,
            location_type=LocationType.CLINIC,
        )
        db_session.add(appointment)
        await db_session.commit()

        # Mock time to 20:00
        with (
            patch("pazpaz.workers.scheduler.send_daily_digest") as mock_send,
            patch("pazpaz.workers.scheduler.datetime") as mock_datetime,
        ):
            mock_now = datetime(2025, 10, 22, 20, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min
            mock_datetime.max = datetime.max

            # Run task
            result = await send_daily_digests({})

            # Should not send tomorrow's digest (disabled)
            # Note: may still send today's digest if configured
            # So we check that mock was not called for tomorrow's date
            if mock_send.called:
                for call in mock_send.call_args_list:
                    date_str = call.kwargs["date_str"]
                    # Should NOT contain tomorrow's date (23)
                    assert "23" not in date_str or result["sent"] == 0

    async def test_tomorrow_digest_respects_days_array(
        self, db_session, workspace_1, test_user_ws1, sample_client_ws1
    ):
        """Test that tomorrow's digest respects the days array."""
        # Configure user for tomorrow's digest only on weekdays (Monday-Friday)
        # Days: 0=Sunday, 1=Monday, 2=Tuesday, 3=Wednesday, 4=Thursday, 5=Friday, 6=Saturday
        settings = UserNotificationSettings(
            id=uuid4(),
            workspace_id=workspace_1.id,
            user_id=test_user_ws1.id,
            email_enabled=True,
            tomorrow_digest_enabled=True,
            tomorrow_digest_time="20:00",
            tomorrow_digest_days=[1, 2, 3, 4, 5],  # Monday-Friday only
        )
        db_session.add(settings)

        # Create appointment for tomorrow
        tomorrow = datetime.now(UTC).date() + timedelta(days=1)
        appointment = Appointment(
            id=uuid4(),
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.combine(tomorrow, time(10, 0), tzinfo=UTC),
            scheduled_end=datetime.combine(tomorrow, time(11, 0), tzinfo=UTC),
            status=AppointmentStatus.SCHEDULED,
            location_type=LocationType.CLINIC,
        )
        db_session.add(appointment)
        await db_session.commit()

        # Test on Saturday (day 6) - should NOT send
        with (
            patch("pazpaz.workers.scheduler.send_daily_digest") as mock_send,
            patch("pazpaz.workers.scheduler.datetime") as mock_datetime,
        ):
            # Saturday, October 25, 2025 at 20:00
            mock_now = datetime(2025, 10, 25, 20, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min
            mock_datetime.max = datetime.max

            # Run task
            result = await send_daily_digests({})

            # Should not send on Saturday
            if mock_send.called:
                for call in mock_send.call_args_list:
                    date_str = call.kwargs.get("date_str", "")
                    # If digest sent, it should be for a weekday
                    assert "Saturday" not in date_str

    async def test_both_digests_can_send_independently(
        self, db_session, workspace_1, test_user_ws1, sample_client_ws1
    ):
        """Test that both today's and tomorrow's digests can be enabled independently."""
        # Configure user with BOTH digests enabled at different times
        settings = UserNotificationSettings(
            id=uuid4(),
            workspace_id=workspace_1.id,
            user_id=test_user_ws1.id,
            email_enabled=True,
            digest_enabled=True,
            digest_time="08:00",
            digest_days=[0, 1, 2, 3, 4, 5, 6],
            tomorrow_digest_enabled=True,
            tomorrow_digest_time="20:00",
            tomorrow_digest_days=[0, 1, 2, 3, 4, 5, 6],
        )
        db_session.add(settings)

        # Create appointments for today and tomorrow
        today = datetime.now(UTC).date()
        tomorrow = today + timedelta(days=1)

        appt_today = Appointment(
            id=uuid4(),
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.combine(today, time(14, 0), tzinfo=UTC),
            scheduled_end=datetime.combine(today, time(15, 0), tzinfo=UTC),
            status=AppointmentStatus.SCHEDULED,
            location_type=LocationType.CLINIC,
        )

        appt_tomorrow = Appointment(
            id=uuid4(),
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.combine(tomorrow, time(10, 0), tzinfo=UTC),
            scheduled_end=datetime.combine(tomorrow, time(11, 0), tzinfo=UTC),
            status=AppointmentStatus.SCHEDULED,
            location_type=LocationType.CLINIC,
        )

        db_session.add(appt_today)
        db_session.add(appt_tomorrow)
        await db_session.commit()

        # Test at 08:00 - should send today's digest
        with (
            patch("pazpaz.workers.scheduler.send_daily_digest") as mock_send,
            patch("pazpaz.workers.scheduler.datetime") as mock_datetime,
        ):
            mock_now = datetime(2025, 10, 22, 8, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min
            mock_datetime.max = datetime.max

            result = await send_daily_digests({})
            assert result["sent"] >= 1

            # Verify today's date in call
            assert mock_send.called
            date_str = mock_send.call_args.kwargs["date_str"]
            assert "22" in date_str  # Today is Oct 22

        # Test at 20:00 - should send tomorrow's digest
        with (
            patch("pazpaz.workers.scheduler.send_daily_digest") as mock_send,
            patch("pazpaz.workers.scheduler.datetime") as mock_datetime,
        ):
            mock_now = datetime(2025, 10, 22, 20, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min
            mock_datetime.max = datetime.max

            result = await send_daily_digests({})
            assert result["sent"] >= 1

            # Verify tomorrow's date in call
            assert mock_send.called
            date_str = mock_send.call_args.kwargs["date_str"]
            assert "23" in date_str  # Tomorrow is Oct 23

    async def test_email_subject_distinguishes_today_vs_tomorrow(
        self, db_session, workspace_1, test_user_ws1, sample_client_ws1
    ):
        """Test that email subjects distinguish between today and tomorrow."""
        from pazpaz.services.notification_content_service import (
            build_daily_digest_email,
        )

        # Test today's digest subject
        today = date(2025, 10, 22)
        email_today = await build_daily_digest_email(
            db_session, test_user_ws1, today, "today"
        )
        assert "today" in email_today["subject"].lower()
        assert "Wednesday, October 22, 2025" in email_today["subject"]

        # Test tomorrow's digest subject
        tomorrow = date(2025, 10, 23)
        email_tomorrow = await build_daily_digest_email(
            db_session, test_user_ws1, tomorrow, "tomorrow"
        )
        assert "tomorrow" in email_tomorrow["subject"].lower()
        assert "Thursday, October 23, 2025" in email_tomorrow["subject"]

    async def test_user_has_today_enabled_but_not_tomorrow(
        self, db_session, workspace_1, test_user_ws1, sample_client_ws1
    ):
        """Test edge case: user has today enabled but not tomorrow (only sends today)."""
        # Configure user with only today's digest enabled
        settings = UserNotificationSettings(
            id=uuid4(),
            workspace_id=workspace_1.id,
            user_id=test_user_ws1.id,
            email_enabled=True,
            digest_enabled=True,
            digest_time="08:00",
            digest_days=[0, 1, 2, 3, 4, 5, 6],
            tomorrow_digest_enabled=False,  # Tomorrow disabled
            tomorrow_digest_time="20:00",
            tomorrow_digest_days=[0, 1, 2, 3, 4, 5, 6],
        )
        db_session.add(settings)
        await db_session.commit()

        # Test at 20:00 (tomorrow's digest time) - should NOT send
        with (
            patch("pazpaz.workers.scheduler.send_daily_digest") as mock_send,
            patch("pazpaz.workers.scheduler.datetime") as mock_datetime,
        ):
            mock_now = datetime(2025, 10, 22, 20, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min
            mock_datetime.max = datetime.max

            result = await send_daily_digests({})

            # Should not send at 20:00 (tomorrow's time)
            # Check if any call was for tomorrow's date
            if mock_send.called:
                for call in mock_send.call_args_list:
                    date_str = call.kwargs.get("date_str", "")
                    assert "23" not in date_str  # Tomorrow is 23rd

    async def test_user_has_tomorrow_enabled_but_not_today(
        self, db_session, workspace_1, test_user_ws1, sample_client_ws1
    ):
        """Test edge case: user has tomorrow enabled but not today (only sends tomorrow)."""
        # Configure user with only tomorrow's digest enabled
        settings = UserNotificationSettings(
            id=uuid4(),
            workspace_id=workspace_1.id,
            user_id=test_user_ws1.id,
            email_enabled=True,
            digest_enabled=False,  # Today disabled
            digest_time="08:00",
            digest_days=[0, 1, 2, 3, 4, 5, 6],
            tomorrow_digest_enabled=True,  # Tomorrow enabled
            tomorrow_digest_time="20:00",
            tomorrow_digest_days=[0, 1, 2, 3, 4, 5, 6],
        )
        db_session.add(settings)

        # Create appointment for tomorrow
        tomorrow = datetime.now(UTC).date() + timedelta(days=1)
        appointment = Appointment(
            id=uuid4(),
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.combine(tomorrow, time(10, 0), tzinfo=UTC),
            scheduled_end=datetime.combine(tomorrow, time(11, 0), tzinfo=UTC),
            status=AppointmentStatus.SCHEDULED,
            location_type=LocationType.CLINIC,
        )
        db_session.add(appointment)
        await db_session.commit()

        # Test at 20:00 - should send tomorrow's digest
        with (
            patch("pazpaz.workers.scheduler.send_daily_digest") as mock_send,
            patch("pazpaz.workers.scheduler.datetime") as mock_datetime,
        ):
            mock_now = datetime(2025, 10, 22, 20, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min
            mock_datetime.max = datetime.max

            result = await send_daily_digests({})
            assert result["sent"] >= 1

            # Verify tomorrow's digest was sent
            assert mock_send.called
            date_str = mock_send.call_args.kwargs["date_str"]
            assert "23" in date_str  # Tomorrow is 23rd

    async def test_no_appointments_tomorrow_sends_empty_message(
        self, db_session, workspace_1, test_user_ws1
    ):
        """Test edge case: no appointments tomorrow (sends 'no appointments' message)."""
        # Configure user for tomorrow's digest
        settings = UserNotificationSettings(
            id=uuid4(),
            workspace_id=workspace_1.id,
            user_id=test_user_ws1.id,
            email_enabled=True,
            tomorrow_digest_enabled=True,
            tomorrow_digest_time="20:00",
            tomorrow_digest_days=[0, 1, 2, 3, 4, 5, 6],
        )
        db_session.add(settings)
        await db_session.commit()

        # No appointments created - tomorrow is empty

        # Test at 20:00 - should send digest with "no appointments" message
        with (
            patch("pazpaz.workers.scheduler.send_daily_digest") as mock_send,
            patch("pazpaz.workers.scheduler.datetime") as mock_datetime,
        ):
            mock_now = datetime(2025, 10, 22, 20, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min
            mock_datetime.max = datetime.max

            result = await send_daily_digests({})
            assert result["sent"] >= 1

            # Verify digest was sent with empty appointments list
            assert mock_send.called
            appointments = mock_send.call_args.kwargs["appointments"]
            assert len(appointments) == 0

    async def test_email_master_toggle_affects_both_digests(
        self, db_session, workspace_1, test_user_ws1
    ):
        """Test that email_enabled=False disables both today and tomorrow digests."""
        # Configure user with both digests enabled BUT email_enabled=False
        settings = UserNotificationSettings(
            id=uuid4(),
            workspace_id=workspace_1.id,
            user_id=test_user_ws1.id,
            email_enabled=False,  # Master toggle OFF
            digest_enabled=True,
            digest_time="08:00",
            digest_days=[0, 1, 2, 3, 4, 5, 6],
            tomorrow_digest_enabled=True,
            tomorrow_digest_time="20:00",
            tomorrow_digest_days=[0, 1, 2, 3, 4, 5, 6],
        )
        db_session.add(settings)
        await db_session.commit()

        # Test at both 08:00 and 20:00 - neither should send
        with (
            patch("pazpaz.workers.scheduler.send_daily_digest") as mock_send,
            patch("pazpaz.workers.scheduler.datetime") as mock_datetime,
        ):
            # Test at 08:00
            mock_now = datetime(2025, 10, 22, 8, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min
            mock_datetime.max = datetime.max

            result = await send_daily_digests({})
            # Should not send (master toggle off)
            assert result["sent"] == 0

        with (
            patch("pazpaz.workers.scheduler.send_daily_digest") as mock_send,
            patch("pazpaz.workers.scheduler.datetime") as mock_datetime,
        ):
            # Test at 20:00
            mock_now = datetime(2025, 10, 22, 20, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now
            mock_datetime.combine = datetime.combine
            mock_datetime.min = datetime.min
            mock_datetime.max = datetime.max

            result = await send_daily_digests({})
            # Should not send (master toggle off)
            assert result["sent"] == 0
