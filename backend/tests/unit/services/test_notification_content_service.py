"""Unit tests for notification content service."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pazpaz.models.appointment import Appointment, AppointmentStatus, LocationType
from pazpaz.models.client import Client
from pazpaz.models.session import Session
from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace
from pazpaz.services.notification_content_service import (
    build_appointment_reminder_email,
    build_daily_digest_email,
    build_session_notes_reminder_email,
)


@pytest_asyncio.fixture
async def db_session(test_db_engine) -> AsyncSession:
    """Create a fresh database session for each test."""
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
        full_name="Dr. Sarah Thompson",
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


class TestBuildSessionNotesReminderEmail:
    """Test build_session_notes_reminder_email function."""

    @pytest.mark.asyncio
    async def test_builds_email_with_drafts(
        self,
        db_session: AsyncSession,
        user: User,
        client: Client,
    ):
        """Test building email when user has draft sessions."""
        # Create 3 draft sessions
        for i in range(3):
            session = Session(
                workspace_id=user.workspace_id,
                client_id=client.id,
                session_date=datetime.now(UTC),
                is_draft=True,
                created_by_user_id=user.id,
            )
            db_session.add(session)

        await db_session.commit()

        # Build email
        email = await build_session_notes_reminder_email(db_session, user)

        # Verify email structure
        assert email["to"] == user.email
        assert "3 draft session notes" in email["subject"]
        assert user.full_name in email["body"]
        assert "3 draft session notes" in email["body"]
        assert "/sessions" in email["body"]

    @pytest.mark.asyncio
    async def test_builds_email_with_one_draft(
        self,
        db_session: AsyncSession,
        user: User,
        client: Client,
    ):
        """Test building email when user has one draft session."""
        # Create 1 draft session
        session = Session(
            workspace_id=user.workspace_id,
            client_id=client.id,
            session_date=datetime.now(UTC),
            is_draft=True,
            created_by_user_id=user.id,
        )
        db_session.add(session)
        await db_session.commit()

        # Build email
        email = await build_session_notes_reminder_email(db_session, user)

        # Verify singular form
        assert "1 draft session note" in email["subject"]
        assert "1 draft session note" in email["body"]

    @pytest.mark.asyncio
    async def test_builds_email_with_no_drafts(
        self,
        db_session: AsyncSession,
        user: User,
    ):
        """Test building email when user has no draft sessions."""
        # No draft sessions

        # Build email
        email = await build_session_notes_reminder_email(db_session, user)

        # Verify email encourages user
        assert "0 draft session notes" in email["subject"]
        assert "all caught up" in email["body"].lower()
        assert "no pending draft" in email["body"].lower()

    @pytest.mark.asyncio
    async def test_excludes_deleted_sessions(
        self,
        db_session: AsyncSession,
        user: User,
        client: Client,
    ):
        """Test that deleted draft sessions are not counted."""
        # Create 2 draft sessions, one deleted
        session1 = Session(
            workspace_id=user.workspace_id,
            client_id=client.id,
            session_date=datetime.now(UTC),
            is_draft=True,
            created_by_user_id=user.id,
        )
        session2 = Session(
            workspace_id=user.workspace_id,
            client_id=client.id,
            session_date=datetime.now(UTC),
            is_draft=True,
            deleted_at=datetime.now(UTC),  # Deleted
            created_by_user_id=user.id,
        )
        db_session.add_all([session1, session2])
        await db_session.commit()

        # Build email
        email = await build_session_notes_reminder_email(db_session, user)

        # Should only count non-deleted session
        assert "1 draft session note" in email["subject"]


class TestBuildDailyDigestEmail:
    """Test build_daily_digest_email function."""

    @pytest.mark.asyncio
    async def test_builds_email_with_appointments(
        self,
        db_session: AsyncSession,
        user: User,
        client: Client,
    ):
        """Test building digest with appointments."""
        # Create appointments for today
        today = date.today()
        start1 = datetime.combine(today, datetime.min.time()).replace(
            hour=10, tzinfo=UTC
        )
        start2 = datetime.combine(today, datetime.min.time()).replace(
            hour=14, tzinfo=UTC
        )

        appt1 = Appointment(
            workspace_id=user.workspace_id,
            client_id=client.id,
            scheduled_start=start1,
            scheduled_end=start1 + timedelta(hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
        )
        appt2 = Appointment(
            workspace_id=user.workspace_id,
            client_id=client.id,
            scheduled_start=start2,
            scheduled_end=start2 + timedelta(hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
        )
        db_session.add_all([appt1, appt2])
        await db_session.commit()

        # Build email
        email = await build_daily_digest_email(db_session, user, today)

        # Verify email structure
        assert email["to"] == user.email
        assert today.strftime("%A") in email["subject"]
        assert "2 appointments" in email["body"]
        assert client.full_name in email["body"]
        assert "/calendar" in email["body"]

    @pytest.mark.asyncio
    async def test_builds_email_with_no_appointments(
        self,
        db_session: AsyncSession,
        user: User,
    ):
        """Test building digest with no appointments."""
        # No appointments
        today = date.today()

        # Build email
        email = await build_daily_digest_email(db_session, user, today)

        # Verify email structure
        assert "no appointments" in email["body"].lower()
        assert "day off" in email["body"].lower()

    @pytest.mark.asyncio
    async def test_builds_email_with_one_appointment(
        self,
        db_session: AsyncSession,
        user: User,
        client: Client,
    ):
        """Test building digest with one appointment (singular form)."""
        today = date.today()
        start = datetime.combine(today, datetime.min.time()).replace(
            hour=10, tzinfo=UTC
        )

        appt = Appointment(
            workspace_id=user.workspace_id,
            client_id=client.id,
            scheduled_start=start,
            scheduled_end=start + timedelta(hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
        )
        db_session.add(appt)
        await db_session.commit()

        # Build email
        email = await build_daily_digest_email(db_session, user, today)

        # Verify singular form
        assert "1 appointment" in email["body"]


class TestBuildAppointmentReminderEmail:
    """Test build_appointment_reminder_email function."""

    @pytest.mark.asyncio
    async def test_builds_email_for_upcoming_appointment(
        self,
        db_session: AsyncSession,
        user: User,
        client: Client,
    ):
        """Test building reminder for appointment in 60 minutes."""
        # Create appointment 60 minutes in the future
        now = datetime.now(UTC)
        start = now + timedelta(minutes=60)

        appointment = Appointment(
            workspace_id=user.workspace_id,
            client_id=client.id,
            scheduled_start=start,
            scheduled_end=start + timedelta(hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment, ["client"])

        # Build email
        email = await build_appointment_reminder_email(db_session, appointment, user)

        # Verify email structure
        assert email["to"] == user.email
        # Allow for slight timing differences (59-61 minutes)
        assert "minutes" in email["subject"]
        assert client.full_name in email["subject"]
        assert client.full_name in email["body"]
        assert "/calendar" in email["body"]

    @pytest.mark.asyncio
    async def test_formats_subject_for_different_time_windows(
        self,
        db_session: AsyncSession,
        user: User,
        client: Client,
    ):
        """Test subject line changes based on time until appointment."""
        now = datetime.now(UTC)

        # Test 30 minutes (should say "30 minutes")
        start30 = now + timedelta(minutes=30)
        appt30 = Appointment(
            workspace_id=user.workspace_id,
            client_id=client.id,
            scheduled_start=start30,
            scheduled_end=start30 + timedelta(hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
        )
        db_session.add(appt30)
        await db_session.commit()
        await db_session.refresh(appt30, ["client"])

        email30 = await build_appointment_reminder_email(db_session, appt30, user)
        assert "minutes" in email30["subject"]

        # Test 3 hours (should say "3 hours")
        start3h = now + timedelta(hours=3)
        appt3h = Appointment(
            workspace_id=user.workspace_id,
            client_id=client.id,
            scheduled_start=start3h,
            scheduled_end=start3h + timedelta(hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
        )
        db_session.add(appt3h)
        await db_session.commit()
        await db_session.refresh(appt3h, ["client"])

        email3h = await build_appointment_reminder_email(db_session, appt3h, user)
        assert "hour" in email3h["subject"]

    @pytest.mark.asyncio
    async def test_includes_service_and_location_if_available(
        self,
        db_session: AsyncSession,
        user: User,
        client: Client,
    ):
        """Test that service and location are included when present."""
        now = datetime.now(UTC)
        start = now + timedelta(minutes=60)

        appointment = Appointment(
            workspace_id=user.workspace_id,
            client_id=client.id,
            scheduled_start=start,
            scheduled_end=start + timedelta(hours=1),
            location_type=LocationType.CLINIC,
            location_details="Room 101",
            status=AppointmentStatus.SCHEDULED,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment, ["client"])

        # Build email
        email = await build_appointment_reminder_email(db_session, appointment, user)

        # Verify location is included
        assert "Room 101" in email["body"]
        assert "Location:" in email["body"]
