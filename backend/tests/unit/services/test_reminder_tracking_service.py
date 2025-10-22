"""Unit tests for reminder tracking service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pazpaz.models.appointment import Appointment, AppointmentStatus, LocationType
from pazpaz.models.appointment_reminder import AppointmentReminderSent, ReminderType
from pazpaz.models.client import Client
from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace
from pazpaz.services.reminder_tracking_service import (
    _minutes_to_reminder_type,
    cleanup_old_reminders,
    mark_reminder_sent,
    was_reminder_sent,
)


@pytest_asyncio.fixture
async def db_session(test_db_engine) -> AsyncSession:
    """
    Create a fresh database session for each test.

    Uses the session-scoped test_db_engine which has tables already created.
    Each test gets a fresh session with truncated tables.
    """
    async_session_maker = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def workspace(db_session: AsyncSession) -> Workspace:
    """Create a test workspace."""
    workspace = Workspace(
        name="Test Clinic",
        is_active=True,
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest_asyncio.fixture
async def user(db_session: AsyncSession, workspace: Workspace) -> User:
    """Create a test user."""
    user = User(
        workspace_id=workspace.id,
        email="therapist@example.com",
        full_name="Test Therapist",
        role=UserRole.OWNER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, workspace: Workspace) -> Client:
    """Create a test client."""
    client = Client(
        workspace_id=workspace.id,
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest_asyncio.fixture
async def appointment(
    db_session: AsyncSession,
    workspace: Workspace,
    client: Client,
) -> Appointment:
    """Create a test appointment."""
    now = datetime.now(UTC)
    appointment = Appointment(
        workspace_id=workspace.id,
        client_id=client.id,
        scheduled_start=now + timedelta(hours=1),
        scheduled_end=now + timedelta(hours=2),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
    )
    db_session.add(appointment)
    await db_session.commit()
    await db_session.refresh(appointment)
    return appointment


class TestMinutesToReminderType:
    """Test _minutes_to_reminder_type helper function."""

    def test_converts_15_minutes(self):
        """Test conversion of 15 minutes."""
        assert _minutes_to_reminder_type(15) == "15min"

    def test_converts_30_minutes(self):
        """Test conversion of 30 minutes."""
        assert _minutes_to_reminder_type(30) == "30min"

    def test_converts_60_minutes(self):
        """Test conversion of 60 minutes (1 hour)."""
        assert _minutes_to_reminder_type(60) == "1hr"

    def test_converts_120_minutes(self):
        """Test conversion of 120 minutes (2 hours)."""
        assert _minutes_to_reminder_type(120) == "2hr"

    def test_converts_1440_minutes(self):
        """Test conversion of 1440 minutes (24 hours)."""
        assert _minutes_to_reminder_type(1440) == "24hr"

    def test_raises_error_for_invalid_minutes(self):
        """Test that invalid reminder minutes raises ValueError."""
        with pytest.raises(ValueError, match="Invalid reminder interval"):
            _minutes_to_reminder_type(45)

        with pytest.raises(ValueError, match="Invalid reminder interval"):
            _minutes_to_reminder_type(90)

        with pytest.raises(ValueError, match="Invalid reminder interval"):
            _minutes_to_reminder_type(0)


class TestWasReminderSent:
    """Test was_reminder_sent function."""

    @pytest.mark.asyncio
    async def test_returns_false_for_new_reminder(
        self,
        db_session: AsyncSession,
        appointment: Appointment,
        user: User,
    ):
        """Test that was_reminder_sent returns False for new reminders."""
        result = await was_reminder_sent(
            db_session,
            appointment.id,
            user.id,
            reminder_minutes=30,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_after_marking_sent(
        self,
        db_session: AsyncSession,
        appointment: Appointment,
        user: User,
    ):
        """Test that was_reminder_sent returns True after reminder is marked."""
        # Mark reminder as sent
        await mark_reminder_sent(
            db_session,
            appointment.id,
            user.id,
            reminder_minutes=30,
        )
        await db_session.commit()  # Commit after marking

        # Check if reminder was sent
        result = await was_reminder_sent(
            db_session,
            appointment.id,
            user.id,
            reminder_minutes=30,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_different_reminder_types_tracked_separately(
        self,
        db_session: AsyncSession,
        appointment: Appointment,
        user: User,
    ):
        """Test that different reminder types are tracked separately."""
        # Mark 30min reminder as sent
        await mark_reminder_sent(
            db_session,
            appointment.id,
            user.id,
            reminder_minutes=30,
        )
        await db_session.commit()  # Commit after marking

        # Check 30min reminder - should be True
        result_30 = await was_reminder_sent(
            db_session,
            appointment.id,
            user.id,
            reminder_minutes=30,
        )
        assert result_30 is True

        # Check 60min reminder - should be False
        result_60 = await was_reminder_sent(
            db_session,
            appointment.id,
            user.id,
            reminder_minutes=60,
        )
        assert result_60 is False

    @pytest.mark.asyncio
    async def test_different_users_tracked_separately(
        self,
        db_session: AsyncSession,
        appointment: Appointment,
        user: User,
        workspace: Workspace,
    ):
        """Test that reminders for different users are tracked separately."""
        # Create second user
        user2 = User(
            workspace_id=workspace.id,
            email="assistant@example.com",
            full_name="Test Assistant",
            role=UserRole.ASSISTANT,
            is_active=True,
        )
        db_session.add(user2)
        await db_session.commit()
        await db_session.refresh(user2)

        # Mark reminder for first user
        await mark_reminder_sent(
            db_session,
            appointment.id,
            user.id,
            reminder_minutes=30,
        )
        await db_session.commit()  # Commit after marking

        # Check first user - should be True
        result_user1 = await was_reminder_sent(
            db_session,
            appointment.id,
            user.id,
            reminder_minutes=30,
        )
        assert result_user1 is True

        # Check second user - should be False
        result_user2 = await was_reminder_sent(
            db_session,
            appointment.id,
            user2.id,
            reminder_minutes=30,
        )
        assert result_user2 is False

    @pytest.mark.asyncio
    async def test_raises_error_for_invalid_minutes(
        self,
        db_session: AsyncSession,
        appointment: Appointment,
        user: User,
    ):
        """Test that invalid reminder_minutes raises ValueError."""
        with pytest.raises(ValueError, match="Invalid reminder interval"):
            await was_reminder_sent(
                db_session,
                appointment.id,
                user.id,
                reminder_minutes=45,
            )


class TestMarkReminderSent:
    """Test mark_reminder_sent function."""

    @pytest.mark.asyncio
    async def test_creates_reminder_record(
        self,
        db_session: AsyncSession,
        appointment: Appointment,
        user: User,
    ):
        """Test that mark_reminder_sent creates a tracking record."""
        # Mark reminder as sent
        await mark_reminder_sent(
            db_session,
            appointment.id,
            user.id,
            reminder_minutes=30,
        )
        await db_session.commit()  # Commit after marking

        # Verify record exists
        stmt = select(AppointmentReminderSent).where(
            AppointmentReminderSent.appointment_id == appointment.id,
            AppointmentReminderSent.user_id == user.id,
            AppointmentReminderSent.reminder_type == ReminderType.MIN_30,
        )
        result = await db_session.execute(stmt)
        reminder = result.scalar_one_or_none()

        assert reminder is not None
        assert reminder.appointment_id == appointment.id
        assert reminder.user_id == user.id
        assert reminder.reminder_type == ReminderType.MIN_30
        assert reminder.sent_at is not None

    @pytest.mark.asyncio
    async def test_handles_duplicate_gracefully(
        self,
        db_session: AsyncSession,
        appointment: Appointment,
        user: User,
    ):
        """Test that duplicate mark_reminder_sent calls don't raise errors."""
        # Store IDs before session operations
        appointment_id = appointment.id
        user_id = user.id

        # Mark reminder as sent
        await mark_reminder_sent(
            db_session,
            appointment_id,
            user_id,
            reminder_minutes=30,
        )
        await db_session.commit()  # Commit first insert

        # Second attempt should not raise error (handles duplicate gracefully)
        await mark_reminder_sent(
            db_session,
            appointment_id,
            user_id,
            reminder_minutes=30,
        )

        # Verify only one record exists
        stmt = select(AppointmentReminderSent).where(
            AppointmentReminderSent.appointment_id == appointment_id,
            AppointmentReminderSent.user_id == user_id,
            AppointmentReminderSent.reminder_type == ReminderType.MIN_30,
        )
        result = await db_session.execute(stmt)
        reminders = list(result.scalars().all())

        assert len(reminders) == 1

    @pytest.mark.asyncio
    async def test_creates_separate_records_for_different_types(
        self,
        db_session: AsyncSession,
        appointment: Appointment,
        user: User,
    ):
        """Test that different reminder types create separate records."""
        # Mark different reminder types
        await mark_reminder_sent(
            db_session,
            appointment.id,
            user.id,
            reminder_minutes=30,
        )
        await mark_reminder_sent(
            db_session,
            appointment.id,
            user.id,
            reminder_minutes=60,
        )
        await mark_reminder_sent(
            db_session,
            appointment.id,
            user.id,
            reminder_minutes=1440,
        )
        await db_session.commit()  # Commit all changes

        # Verify all records exist
        stmt = select(AppointmentReminderSent).where(
            AppointmentReminderSent.appointment_id == appointment.id,
            AppointmentReminderSent.user_id == user.id,
        )
        result = await db_session.execute(stmt)
        reminders = list(result.scalars().all())

        assert len(reminders) == 3
        reminder_types = {r.reminder_type for r in reminders}
        assert reminder_types == {
            ReminderType.MIN_30,
            ReminderType.HOUR_1,
            ReminderType.HOUR_24,
        }

    @pytest.mark.asyncio
    async def test_raises_error_for_invalid_minutes(
        self,
        db_session: AsyncSession,
        appointment: Appointment,
        user: User,
    ):
        """Test that invalid reminder_minutes raises ValueError."""
        with pytest.raises(ValueError, match="Invalid reminder interval"):
            await mark_reminder_sent(
                db_session,
                appointment.id,
                user.id,
                reminder_minutes=90,
            )


class TestCleanupOldReminders:
    """Test cleanup_old_reminders function."""

    @pytest.mark.asyncio
    async def test_deletes_old_reminders(
        self,
        db_session: AsyncSession,
        appointment: Appointment,
        user: User,
    ):
        """Test that old reminders are deleted."""
        # Create old reminder (35 days old)
        old_reminder = AppointmentReminderSent(
            appointment_id=appointment.id,
            user_id=user.id,
            reminder_type=ReminderType.MIN_30,
            sent_at=datetime.now(UTC) - timedelta(days=35),
        )
        db_session.add(old_reminder)
        await db_session.commit()

        # Run cleanup (default 30 days)
        deleted_count = await cleanup_old_reminders(db_session, days_old=30)

        # Verify old reminder was deleted
        assert deleted_count == 1

        stmt = select(AppointmentReminderSent).where(
            AppointmentReminderSent.id == old_reminder.id
        )
        result = await db_session.execute(stmt)
        reminder = result.scalar_one_or_none()

        assert reminder is None

    @pytest.mark.asyncio
    async def test_keeps_recent_reminders(
        self,
        db_session: AsyncSession,
        appointment: Appointment,
        user: User,
    ):
        """Test that recent reminders are not deleted."""
        # Create recent reminder (5 days old)
        recent_reminder = AppointmentReminderSent(
            appointment_id=appointment.id,
            user_id=user.id,
            reminder_type=ReminderType.MIN_30,
            sent_at=datetime.now(UTC) - timedelta(days=5),
        )
        db_session.add(recent_reminder)
        await db_session.commit()

        # Run cleanup (30 days)
        deleted_count = await cleanup_old_reminders(db_session, days_old=30)

        # Verify recent reminder was NOT deleted
        assert deleted_count == 0

        stmt = select(AppointmentReminderSent).where(
            AppointmentReminderSent.id == recent_reminder.id
        )
        result = await db_session.execute(stmt)
        reminder = result.scalar_one_or_none()

        assert reminder is not None

    @pytest.mark.asyncio
    async def test_deletes_multiple_old_reminders(
        self,
        db_session: AsyncSession,
        appointment: Appointment,
        user: User,
        workspace: Workspace,
        client: Client,
    ):
        """Test that multiple old reminders are deleted."""
        # Create multiple old reminders
        old_date = datetime.now(UTC) - timedelta(days=40)

        # Create second appointment
        appointment2 = Appointment(
            workspace_id=workspace.id,
            client_id=client.id,
            scheduled_start=datetime.now(UTC) + timedelta(hours=3),
            scheduled_end=datetime.now(UTC) + timedelta(hours=4),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
        )
        db_session.add(appointment2)
        await db_session.commit()

        # Create old reminders
        for appt in [appointment, appointment2]:
            for reminder_type in [ReminderType.MIN_30, ReminderType.HOUR_1]:
                reminder = AppointmentReminderSent(
                    appointment_id=appt.id,
                    user_id=user.id,
                    reminder_type=reminder_type,
                    sent_at=old_date,
                )
                db_session.add(reminder)

        await db_session.commit()

        # Run cleanup
        deleted_count = await cleanup_old_reminders(db_session, days_old=30)

        # Verify all 4 old reminders were deleted
        assert deleted_count == 4

        stmt = select(AppointmentReminderSent)
        result = await db_session.execute(stmt)
        remaining_reminders = list(result.scalars().all())

        assert len(remaining_reminders) == 0

    @pytest.mark.asyncio
    async def test_respects_custom_days_old_parameter(
        self,
        db_session: AsyncSession,
        appointment: Appointment,
        user: User,
    ):
        """Test that custom days_old parameter works correctly."""
        # Create reminder that is 8 days old
        reminder = AppointmentReminderSent(
            appointment_id=appointment.id,
            user_id=user.id,
            reminder_type=ReminderType.MIN_30,
            sent_at=datetime.now(UTC) - timedelta(days=8),
        )
        db_session.add(reminder)
        await db_session.commit()

        # Cleanup with 10 days - should NOT delete
        deleted_count = await cleanup_old_reminders(db_session, days_old=10)
        assert deleted_count == 0

        # Cleanup with 7 days - should delete
        deleted_count = await cleanup_old_reminders(db_session, days_old=7)
        assert deleted_count == 1
