"""Unit tests for notification query service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pazpaz.models.appointment import Appointment, AppointmentStatus, LocationType
from pazpaz.models.client import Client
from pazpaz.models.session import Session
from pazpaz.models.user import User, UserRole
from pazpaz.models.user_notification_settings import UserNotificationSettings
from pazpaz.models.workspace import Workspace
from pazpaz.services.notification_query_service import (
    get_appointments_needing_reminders,
    get_users_needing_daily_digest,
    get_users_needing_session_notes_reminder,
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
        timezone="UTC",  # Default timezone for tests
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


class TestGetUsersNeedingSessionNotesReminder:
    """Test get_users_needing_session_notes_reminder function."""

    @pytest.mark.asyncio
    async def test_finds_users_with_matching_time(
        self,
        db_session: AsyncSession,
        user: User,
    ):
        """Test that users with matching reminder time are found."""
        # Create notification settings with 18:00 reminder
        settings = UserNotificationSettings(
            user_id=user.id,
            workspace_id=user.workspace_id,
            email_enabled=True,
            notes_reminder_enabled=True,
            notes_reminder_time="18:00",
        )
        db_session.add(settings)
        await db_session.commit()

        # Query for users at 18:00 UTC
        users = await get_users_needing_session_notes_reminder(
            db_session,
            time(18, 0),
            "UTC",
        )

        assert len(users) == 1
        assert users[0].id == user.id
        assert users[0].email == user.email

    @pytest.mark.asyncio
    async def test_excludes_users_with_email_disabled(
        self,
        db_session: AsyncSession,
        user: User,
    ):
        """Test that users with email_enabled=False are excluded."""
        # Create notification settings with email disabled
        settings = UserNotificationSettings(
            user_id=user.id,
            workspace_id=user.workspace_id,
            email_enabled=False,  # Disabled
            notes_reminder_enabled=True,
            notes_reminder_time="18:00",
        )
        db_session.add(settings)
        await db_session.commit()

        # Query for users at 18:00 UTC
        users = await get_users_needing_session_notes_reminder(
            db_session,
            time(18, 0),
            "UTC",
        )

        assert len(users) == 0

    @pytest.mark.asyncio
    async def test_excludes_users_with_reminder_disabled(
        self,
        db_session: AsyncSession,
        user: User,
    ):
        """Test that users with notes_reminder_enabled=False are excluded."""
        # Create notification settings with reminder disabled
        settings = UserNotificationSettings(
            user_id=user.id,
            workspace_id=user.workspace_id,
            email_enabled=True,
            notes_reminder_enabled=False,  # Disabled
            notes_reminder_time="18:00",
        )
        db_session.add(settings)
        await db_session.commit()

        # Query for users at 18:00 UTC
        users = await get_users_needing_session_notes_reminder(
            db_session,
            time(18, 0),
            "UTC",
        )

        assert len(users) == 0

    @pytest.mark.asyncio
    async def test_excludes_users_with_different_time(
        self,
        db_session: AsyncSession,
        user: User,
    ):
        """Test that users with different reminder time are excluded."""
        # Create notification settings with 08:00 reminder
        settings = UserNotificationSettings(
            user_id=user.id,
            workspace_id=user.workspace_id,
            email_enabled=True,
            notes_reminder_enabled=True,
            notes_reminder_time="08:00",  # Different time
        )
        db_session.add(settings)
        await db_session.commit()

        # Query for users at 18:00 UTC
        users = await get_users_needing_session_notes_reminder(
            db_session,
            time(18, 0),
            "UTC",
        )

        assert len(users) == 0


class TestGetUsersNeedingDailyDigest:
    """Test get_users_needing_daily_digest function."""

    @pytest.mark.asyncio
    async def test_finds_users_with_matching_time(
        self,
        db_session: AsyncSession,
        user: User,
    ):
        """Test that users with matching digest time are found."""
        # Create notification settings with 08:00 digest
        settings = UserNotificationSettings(
            user_id=user.id,
            workspace_id=user.workspace_id,
            email_enabled=True,
            digest_enabled=True,
            digest_time="08:00",
            digest_skip_weekends=False,
        )
        db_session.add(settings)
        await db_session.commit()

        # Query for users at 08:00 on Monday (day=0) UTC
        users = await get_users_needing_daily_digest(
            db_session,
            time(8, 0),
            0,  # Monday
            "UTC",
        )

        assert len(users) == 1
        assert users[0].id == user.id

    @pytest.mark.asyncio
    async def test_excludes_users_on_weekend_with_skip_enabled(
        self,
        db_session: AsyncSession,
        user: User,
    ):
        """Test that users with skip_weekends=True are excluded on weekends."""
        # Create notification settings with weekend skip enabled
        settings = UserNotificationSettings(
            user_id=user.id,
            workspace_id=user.workspace_id,
            email_enabled=True,
            digest_enabled=True,
            digest_time="08:00",
            digest_skip_weekends=True,  # Skip weekends
        )
        db_session.add(settings)
        await db_session.commit()

        # Query for users at 08:00 on Saturday (day=5) UTC
        users = await get_users_needing_daily_digest(
            db_session,
            time(8, 0),
            5,  # Saturday
            "UTC",
        )

        assert len(users) == 0

        # Query for users at 08:00 on Sunday (day=6) UTC
        users = await get_users_needing_daily_digest(
            db_session,
            time(8, 0),
            6,  # Sunday
            "UTC",
        )

        assert len(users) == 0

    @pytest.mark.asyncio
    async def test_includes_users_on_weekend_with_skip_disabled(
        self,
        db_session: AsyncSession,
        user: User,
    ):
        """Test that users with skip_weekends=False are included on weekends."""
        # Create notification settings with weekend skip disabled
        settings = UserNotificationSettings(
            user_id=user.id,
            workspace_id=user.workspace_id,
            email_enabled=True,
            digest_enabled=True,
            digest_time="08:00",
            digest_skip_weekends=False,  # Don't skip weekends
        )
        db_session.add(settings)
        await db_session.commit()

        # Query for users at 08:00 on Saturday (day=5) UTC
        users = await get_users_needing_daily_digest(
            db_session,
            time(8, 0),
            5,  # Saturday
            "UTC",
        )

        assert len(users) == 1
        assert users[0].id == user.id

    @pytest.mark.asyncio
    async def test_excludes_users_with_digest_disabled(
        self,
        db_session: AsyncSession,
        user: User,
    ):
        """Test that users with digest_enabled=False are excluded."""
        # Create notification settings with digest disabled
        settings = UserNotificationSettings(
            user_id=user.id,
            workspace_id=user.workspace_id,
            email_enabled=True,
            digest_enabled=False,  # Disabled
            digest_time="08:00",
        )
        db_session.add(settings)
        await db_session.commit()

        # Query for users at 08:00 on Monday UTC
        users = await get_users_needing_daily_digest(
            db_session,
            time(8, 0),
            0,  # Monday
            "UTC",
        )

        assert len(users) == 0


class TestGetAppointmentsNeedingReminders:
    """Test get_appointments_needing_reminders function."""

    @pytest.mark.asyncio
    async def test_finds_appointments_matching_reminder_time(
        self,
        db_session: AsyncSession,
        user: User,
        client: Client,
    ):
        """Test that appointments matching user's reminder time are found."""
        # Create notification settings with 60-minute reminder
        settings = UserNotificationSettings(
            user_id=user.id,
            workspace_id=user.workspace_id,
            email_enabled=True,
            reminder_enabled=True,
            reminder_minutes=60,
        )
        db_session.add(settings)

        # Create appointment 60 minutes in the future
        now = datetime.now(UTC)
        appointment = Appointment(
            workspace_id=user.workspace_id,
            client_id=client.id,
            scheduled_start=now + timedelta(minutes=60),
            scheduled_end=now + timedelta(minutes=90),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
        )
        db_session.add(appointment)
        await db_session.commit()

        # Query for reminders
        reminders = await get_appointments_needing_reminders(db_session, now)

        assert len(reminders) == 1
        assert reminders[0][0].id == appointment.id
        assert reminders[0][1].id == user.id

    @pytest.mark.asyncio
    async def test_uses_tolerance_window(
        self,
        db_session: AsyncSession,
        user: User,
        client: Client,
    ):
        """Test that ±2 minute tolerance window works."""
        # Create notification settings with 60-minute reminder
        settings = UserNotificationSettings(
            user_id=user.id,
            workspace_id=user.workspace_id,
            email_enabled=True,
            reminder_enabled=True,
            reminder_minutes=60,
        )
        db_session.add(settings)

        # Create appointment 58 minutes in the future (within tolerance)
        now = datetime.now(UTC)
        appointment = Appointment(
            workspace_id=user.workspace_id,
            client_id=client.id,
            scheduled_start=now + timedelta(minutes=58),
            scheduled_end=now + timedelta(minutes=88),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
        )
        db_session.add(appointment)
        await db_session.commit()

        # Query for reminders
        reminders = await get_appointments_needing_reminders(db_session, now)

        # Should find appointment within tolerance
        assert len(reminders) == 1

    @pytest.mark.asyncio
    async def test_excludes_past_appointments(
        self,
        db_session: AsyncSession,
        user: User,
        client: Client,
    ):
        """Test that past appointments are excluded."""
        # Create notification settings
        settings = UserNotificationSettings(
            user_id=user.id,
            workspace_id=user.workspace_id,
            email_enabled=True,
            reminder_enabled=True,
            reminder_minutes=60,
        )
        db_session.add(settings)

        # Create appointment in the past
        now = datetime.now(UTC)
        appointment = Appointment(
            workspace_id=user.workspace_id,
            client_id=client.id,
            scheduled_start=now - timedelta(minutes=30),
            scheduled_end=now - timedelta(minutes=0),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
        )
        db_session.add(appointment)
        await db_session.commit()

        # Query for reminders
        reminders = await get_appointments_needing_reminders(db_session, now)

        assert len(reminders) == 0

    @pytest.mark.asyncio
    async def test_excludes_appointments_with_wrong_status(
        self,
        db_session: AsyncSession,
        user: User,
        client: Client,
    ):
        """Test that non-scheduled appointments are excluded."""
        # Create notification settings
        settings = UserNotificationSettings(
            user_id=user.id,
            workspace_id=user.workspace_id,
            email_enabled=True,
            reminder_enabled=True,
            reminder_minutes=60,
        )
        db_session.add(settings)

        # Create cancelled appointment
        now = datetime.now(UTC)
        appointment = Appointment(
            workspace_id=user.workspace_id,
            client_id=client.id,
            scheduled_start=now + timedelta(minutes=60),
            scheduled_end=now + timedelta(minutes=90),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.CANCELLED,  # Cancelled
        )
        db_session.add(appointment)
        await db_session.commit()

        # Query for reminders
        reminders = await get_appointments_needing_reminders(db_session, now)

        assert len(reminders) == 0

    @pytest.mark.asyncio
    async def test_excludes_users_with_reminder_disabled(
        self,
        db_session: AsyncSession,
        user: User,
        client: Client,
    ):
        """Test that users with reminder_enabled=False are excluded."""
        # Create notification settings with reminder disabled
        settings = UserNotificationSettings(
            user_id=user.id,
            workspace_id=user.workspace_id,
            email_enabled=True,
            reminder_enabled=False,  # Disabled
            reminder_minutes=60,
        )
        db_session.add(settings)

        # Create appointment
        now = datetime.now(UTC)
        appointment = Appointment(
            workspace_id=user.workspace_id,
            client_id=client.id,
            scheduled_start=now + timedelta(minutes=60),
            scheduled_end=now + timedelta(minutes=90),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
        )
        db_session.add(appointment)
        await db_session.commit()

        # Query for reminders
        reminders = await get_appointments_needing_reminders(db_session, now)

        assert len(reminders) == 0
