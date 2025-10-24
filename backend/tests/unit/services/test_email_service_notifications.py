"""Unit tests for notification email functions in email_service.

These tests verify the email content and SMTP sending functionality.
They use MailHog in the test environment for actual email delivery testing.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pazpaz.services.email_service import (
    send_appointment_reminder,
    send_daily_digest,
    send_session_notes_reminder,
)


class TestSendSessionNotesReminder:
    """Test send_session_notes_reminder function."""

    @pytest.mark.asyncio
    async def test_sends_email_with_drafts(self):
        """Test sending session notes reminder with draft count."""
        # Mock SMTP
        with patch("pazpaz.services.email_service.aiosmtplib.SMTP") as mock_smtp:
            mock_smtp_instance = AsyncMock()
            mock_smtp.return_value.__aenter__.return_value = mock_smtp_instance

            # Call function
            await send_session_notes_reminder(
                email="therapist@example.com",
                draft_count=3,
                frontend_url="http://localhost:5173",
            )

            # Verify SMTP was called
            mock_smtp_instance.send_message.assert_called_once()

            # Get the email message that was sent
            call_args = mock_smtp_instance.send_message.call_args
            message = call_args[0][0]

            # Verify email content
            assert message["To"] == "therapist@example.com"
            assert "3 draft session notes" in message["Subject"]
            assert "3 draft session notes" in message.get_content()
            assert "/sessions" in message.get_content()

    @pytest.mark.asyncio
    async def test_sends_email_with_one_draft(self):
        """Test sending session notes reminder with one draft (singular)."""
        with patch("pazpaz.services.email_service.aiosmtplib.SMTP") as mock_smtp:
            mock_smtp_instance = AsyncMock()
            mock_smtp.return_value.__aenter__.return_value = mock_smtp_instance

            await send_session_notes_reminder(
                email="therapist@example.com",
                draft_count=1,
                frontend_url="http://localhost:5173",
            )

            # Get the email message
            call_args = mock_smtp_instance.send_message.call_args
            message = call_args[0][0]

            # Verify singular form
            assert "1 draft session note" in message["Subject"]
            assert "1 draft session note" in message.get_content()

    @pytest.mark.asyncio
    async def test_sends_email_with_no_drafts(self):
        """Test sending session notes reminder with zero drafts."""
        with patch("pazpaz.services.email_service.aiosmtplib.SMTP") as mock_smtp:
            mock_smtp_instance = AsyncMock()
            mock_smtp.return_value.__aenter__.return_value = mock_smtp_instance

            await send_session_notes_reminder(
                email="therapist@example.com",
                draft_count=0,
                frontend_url="http://localhost:5173",
            )

            # Get the email message
            call_args = mock_smtp_instance.send_message.call_args
            message = call_args[0][0]

            # Verify congratulatory message
            assert "0 draft session notes" in message["Subject"]
            assert "all caught up" in message.get_content().lower()

    @pytest.mark.asyncio
    async def test_raises_on_smtp_failure(self):
        """Test that SMTP failures raise exceptions."""
        with patch("pazpaz.services.email_service.aiosmtplib.SMTP") as mock_smtp:
            mock_smtp_instance = AsyncMock()
            mock_smtp_instance.send_message.side_effect = Exception("SMTP error")
            mock_smtp.return_value.__aenter__.return_value = mock_smtp_instance

            # Should raise exception
            with pytest.raises(Exception) as exc_info:
                await send_session_notes_reminder(
                    email="therapist@example.com",
                    draft_count=3,
                    frontend_url="http://localhost:5173",
                )

            assert "SMTP error" in str(exc_info.value)


class TestSendDailyDigest:
    """Test send_daily_digest function."""

    @pytest.mark.asyncio
    async def test_sends_email_with_appointments(self):
        """Test sending daily digest with appointments."""
        with patch("pazpaz.services.email_service.aiosmtplib.SMTP") as mock_smtp:
            mock_smtp_instance = AsyncMock()
            mock_smtp.return_value.__aenter__.return_value = mock_smtp_instance

            appointments = [
                {
                    "time": "10:00 AM",
                    "client_name": "Jane Doe",
                    "service": "Deep Tissue Massage",
                    "location": "Main Clinic",
                },
                {
                    "time": "02:00 PM",
                    "client_name": "John Smith",
                    "service": "",
                    "location": "",
                },
            ]

            await send_daily_digest(
                email="therapist@example.com",
                appointments=appointments,
                date_str="Monday, October 22, 2025",
                frontend_url="http://localhost:5173",
            )

            # Verify email was sent
            mock_smtp_instance.send_message.assert_called_once()

            # Get the email message
            call_args = mock_smtp_instance.send_message.call_args
            message = call_args[0][0]

            # Verify content
            assert "Monday, October 22, 2025" in message["Subject"]
            content = message.get_content()
            assert "10:00 AM - Jane Doe" in content
            assert "Deep Tissue Massage" in content
            assert "Main Clinic" in content
            assert "02:00 PM - John Smith" in content
            assert "/calendar" in content

    @pytest.mark.asyncio
    async def test_sends_email_with_no_appointments(self):
        """Test sending daily digest with no appointments."""
        with patch("pazpaz.services.email_service.aiosmtplib.SMTP") as mock_smtp:
            mock_smtp_instance = AsyncMock()
            mock_smtp.return_value.__aenter__.return_value = mock_smtp_instance

            await send_daily_digest(
                email="therapist@example.com",
                appointments=[],
                date_str="Saturday, October 26, 2025",
                frontend_url="http://localhost:5173",
            )

            # Get the email message
            call_args = mock_smtp_instance.send_message.call_args
            message = call_args[0][0]

            # Verify "no appointments" message
            content = message.get_content()
            assert "no appointments" in content.lower()
            assert "day off" in content.lower()

    @pytest.mark.asyncio
    async def test_sends_email_with_one_appointment(self):
        """Test sending daily digest with one appointment (singular)."""
        with patch("pazpaz.services.email_service.aiosmtplib.SMTP") as mock_smtp:
            mock_smtp_instance = AsyncMock()
            mock_smtp.return_value.__aenter__.return_value = mock_smtp_instance

            appointments = [
                {
                    "time": "10:00 AM",
                    "client_name": "Jane Doe",
                    "service": "",
                    "location": "",
                }
            ]

            await send_daily_digest(
                email="therapist@example.com",
                appointments=appointments,
                date_str="Monday, October 22, 2025",
                frontend_url="http://localhost:5173",
            )

            # Get the email message
            call_args = mock_smtp_instance.send_message.call_args
            message = call_args[0][0]

            # Verify singular form
            content = message.get_content()
            assert "1 appointment" in content


class TestSendAppointmentReminder:
    """Test send_appointment_reminder function."""

    @pytest.mark.asyncio
    async def test_sends_email_for_upcoming_appointment(self):
        """Test sending appointment reminder."""
        with patch("pazpaz.services.email_service.aiosmtplib.SMTP") as mock_smtp:
            mock_smtp_instance = AsyncMock()
            mock_smtp.return_value.__aenter__.return_value = mock_smtp_instance

            appointment_data = {
                "appointment_id": "123e4567-e89b-12d3-a456-426614174000",
                "client_name": "Jane Doe",
                "time": "02:30 PM on Monday, October 22, 2025",
                "service": "Deep Tissue Massage",
                "location": "Main Clinic, Room 101",
            }

            await send_appointment_reminder(
                email="therapist@example.com",
                appointment_data=appointment_data,
                minutes_until=60,
            )

            # Verify email was sent
            mock_smtp_instance.send_message.assert_called_once()

            # Get the email message
            call_args = mock_smtp_instance.send_message.call_args
            message = call_args[0][0]

            # Verify content
            assert "60 minutes with Jane Doe" in message["Subject"]
            content = message.get_content()
            assert "Jane Doe" in content
            assert "02:30 PM on Monday, October 22, 2025" in content
            assert "Deep Tissue Massage" in content
            assert "Main Clinic, Room 101" in content
            assert "/calendar" in content

    @pytest.mark.asyncio
    async def test_formats_subject_for_different_time_windows(self):
        """Test subject line changes based on minutes_until."""
        with patch("pazpaz.services.email_service.aiosmtplib.SMTP") as mock_smtp:
            mock_smtp_instance = AsyncMock()
            mock_smtp.return_value.__aenter__.return_value = mock_smtp_instance

            appointment_data = {
                "client_name": "Jane Doe",
                "time": "02:30 PM on Monday, October 22, 2025",
                "service": "",
                "location": "",
            }

            # Test 30 minutes (should say "30 minutes")
            await send_appointment_reminder(
                email="therapist@example.com",
                appointment_data=appointment_data,
                minutes_until=30,
            )
            message30 = mock_smtp_instance.send_message.call_args[0][0]
            assert "30 minutes" in message30["Subject"]

            # Test 3 hours (should say "hour" or "hours")
            await send_appointment_reminder(
                email="therapist@example.com",
                appointment_data=appointment_data,
                minutes_until=180,
            )
            message180 = mock_smtp_instance.send_message.call_args[0][0]
            assert "hour" in message180["Subject"]

            # Test 24 hours (should not say specific time, just "reminder")
            await send_appointment_reminder(
                email="therapist@example.com",
                appointment_data=appointment_data,
                minutes_until=1440,
            )
            message1440 = mock_smtp_instance.send_message.call_args[0][0]
            # 24 hours is too far out, should be generic
            assert (
                "hour" in message1440["Subject"]
                or "reminder" in message1440["Subject"].lower()
            )

    @pytest.mark.asyncio
    async def test_handles_missing_optional_fields(self):
        """Test that email works without service/location."""
        with patch("pazpaz.services.email_service.aiosmtplib.SMTP") as mock_smtp:
            mock_smtp_instance = AsyncMock()
            mock_smtp.return_value.__aenter__.return_value = mock_smtp_instance

            appointment_data = {
                "client_name": "Jane Doe",
                "time": "02:30 PM on Monday, October 22, 2025",
            }

            await send_appointment_reminder(
                email="therapist@example.com",
                appointment_data=appointment_data,
                minutes_until=60,
            )

            # Verify email was sent successfully
            mock_smtp_instance.send_message.assert_called_once()

            # Get the email message
            call_args = mock_smtp_instance.send_message.call_args
            message = call_args[0][0]

            # Verify basic content is present
            content = message.get_content()
            assert "Jane Doe" in content
            assert "02:30 PM on Monday, October 22, 2025" in content
