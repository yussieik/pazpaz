"""Pytest configuration and fixtures for PazPaz backend tests."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from pazpaz.core.config import settings
from pazpaz.db.base import Base, get_db
from pazpaz.main import app
from pazpaz.models.appointment import Appointment, AppointmentStatus, LocationType
from pazpaz.models.client import Client
from pazpaz.models.workspace import Workspace

# Test database URL - use separate test database
TEST_DATABASE_URL = "postgresql+asyncpg://pazpaz:pazpaz@localhost:5432/pazpaz_test"


@pytest.fixture(scope="session")
def event_loop():
    """
    Create an event loop for the entire test session.

    This fixture ensures that async tests have a consistent event loop
    throughout the test session.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db_engine():
    """
    Create a test database engine.

    Uses NullPool to avoid connection pooling issues in tests.
    Each test gets a fresh connection.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create a database session for testing.

    Each test gets a fresh session that is rolled back after the test,
    ensuring test isolation.
    """
    async_session_maker = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Create a test HTTP client.

    Overrides the get_db dependency to use the test database session.
    """

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def workspace_1(db_session: AsyncSession) -> Workspace:
    """
    Create a test workspace (workspace 1).

    This represents a therapist's workspace for testing.
    """
    workspace = Workspace(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        name="Test Workspace 1",
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest_asyncio.fixture(scope="function")
async def workspace_2(db_session: AsyncSession) -> Workspace:
    """
    Create a second test workspace (workspace 2).

    Used to test workspace isolation - data should not leak between workspaces.
    """
    workspace = Workspace(
        id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        name="Test Workspace 2",
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest_asyncio.fixture(scope="function")
async def sample_client_ws1(
    db_session: AsyncSession, workspace_1: Workspace
) -> Client:
    """
    Create a sample client in workspace 1.

    Standard test client with complete data.
    """
    client = Client(
        workspace_id=workspace_1.id,
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone="+1234567890",
        consent_status=True,
        notes="Sample client notes",
        tags=["vip", "massage"],
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest_asyncio.fixture(scope="function")
async def sample_client_ws2(
    db_session: AsyncSession, workspace_2: Workspace
) -> Client:
    """
    Create a sample client in workspace 2.

    Used to test workspace isolation.
    """
    client = Client(
        workspace_id=workspace_2.id,
        first_name="Jane",
        last_name="Smith",
        email="jane.smith@example.com",
        phone="+9876543210",
        consent_status=True,
        notes="Another workspace client",
        tags=["physiotherapy"],
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest_asyncio.fixture(scope="function")
async def sample_appointment_ws1(
    db_session: AsyncSession, workspace_1: Workspace, sample_client_ws1: Client
) -> Appointment:
    """
    Create a sample appointment in workspace 1.

    Scheduled for tomorrow at 10:00 AM.
    """
    tomorrow = datetime.now(UTC).replace(
        hour=10, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        scheduled_start=tomorrow,
        scheduled_end=tomorrow + timedelta(hours=1),
        location_type=LocationType.CLINIC,
        location_details="Room 101",
        status=AppointmentStatus.SCHEDULED,
        notes="Initial consultation",
    )
    db_session.add(appointment)
    await db_session.commit()
    await db_session.refresh(appointment)
    return appointment


@pytest_asyncio.fixture(scope="function")
async def sample_appointment_ws2(
    db_session: AsyncSession, workspace_2: Workspace, sample_client_ws2: Client
) -> Appointment:
    """
    Create a sample appointment in workspace 2.

    Used to test workspace isolation for appointments.
    """
    tomorrow = datetime.now(UTC).replace(
        hour=14, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
    appointment = Appointment(
        workspace_id=workspace_2.id,
        client_id=sample_client_ws2.id,
        scheduled_start=tomorrow,
        scheduled_end=tomorrow + timedelta(hours=1),
        location_type=LocationType.HOME,
        location_details="123 Main St",
        status=AppointmentStatus.SCHEDULED,
        notes="Home visit",
    )
    db_session.add(appointment)
    await db_session.commit()
    await db_session.refresh(appointment)
    return appointment


@pytest_asyncio.fixture(scope="function")
async def cancelled_appointment_ws1(
    db_session: AsyncSession, workspace_1: Workspace, sample_client_ws1: Client
) -> Appointment:
    """
    Create a cancelled appointment in workspace 1.

    Used to test that cancelled appointments don't cause conflicts.
    """
    tomorrow = datetime.now(UTC).replace(
        hour=15, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        scheduled_start=tomorrow,
        scheduled_end=tomorrow + timedelta(hours=1),
        location_type=LocationType.ONLINE,
        location_details="Zoom link",
        status=AppointmentStatus.CANCELLED,
        notes="Client cancelled",
    )
    db_session.add(appointment)
    await db_session.commit()
    await db_session.refresh(appointment)
    return appointment


# Helper functions for tests


def get_auth_headers(workspace_id: uuid.UUID) -> dict[str, str]:
    """
    Get authentication headers for a workspace.

    Args:
        workspace_id: UUID of the workspace

    Returns:
        Dictionary with X-Workspace-ID header
    """
    return {"X-Workspace-ID": str(workspace_id)}