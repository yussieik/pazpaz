#!/usr/bin/env python
"""
Create test data for PazPaz: workspace, client, and appointment.

This script creates:
1. A test workspace (therapist account)
2. A test client
3. An appointment for Friday, October 3, 2025 at 10:00 AM

Run with: uv run python create_test_appointment.py
"""

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from pazpaz.models.appointment import Appointment, AppointmentStatus, LocationType
from pazpaz.models.client import Client
from pazpaz.models.workspace import Workspace

# Database URL from .env
DATABASE_URL = "postgresql+asyncpg://pazpaz:pazpaz@localhost:5432/pazpaz"

# Fixed UUIDs for consistent testing
WORKSPACE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
CLIENT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
APPOINTMENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


async def create_test_data():
    """Create test workspace, client, and appointment."""
    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check if workspace already exists
        from sqlalchemy import select

        existing_workspace = await session.execute(
            select(Workspace).where(Workspace.id == WORKSPACE_ID)
        )
        workspace = existing_workspace.scalar_one_or_none()

        if not workspace:
            print(f"Creating workspace: {WORKSPACE_ID}")
            workspace = Workspace(
                id=WORKSPACE_ID,
                name="Test Therapist Workspace",
                is_active=True,
            )
            session.add(workspace)
            await session.commit()
            await session.refresh(workspace)
            print(f"✓ Created workspace: {workspace.name}")
        else:
            print(f"✓ Workspace already exists: {workspace.name}")

        # Check if client already exists
        existing_client = await session.execute(
            select(Client).where(Client.id == CLIENT_ID)
        )
        client = existing_client.scalar_one_or_none()

        if not client:
            print(f"Creating client: {CLIENT_ID}")
            client = Client(
                id=CLIENT_ID,
                workspace_id=WORKSPACE_ID,
                first_name="John",
                last_name="Doe",
                email="john.doe@example.com",
                phone="+1-555-0100",
                consent_status=True,
                notes="Test client for development",
                tags=["test", "development"],
            )
            session.add(client)
            await session.commit()
            await session.refresh(client)
            print(f"✓ Created client: {client.full_name}")
        else:
            print(f"✓ Client already exists: {client.full_name}")

        # Check if appointment already exists
        existing_appointment = await session.execute(
            select(Appointment).where(Appointment.id == APPOINTMENT_ID)
        )
        appointment = existing_appointment.scalar_one_or_none()

        if not appointment:
            print(f"Creating appointment: {APPOINTMENT_ID}")
            # Friday, October 3, 2025 at 10:00 AM UTC
            appointment_start = datetime(2025, 10, 3, 10, 0, 0, tzinfo=timezone.utc)
            appointment_end = datetime(2025, 10, 3, 11, 0, 0, tzinfo=timezone.utc)

            appointment = Appointment(
                id=APPOINTMENT_ID,
                workspace_id=WORKSPACE_ID,
                client_id=CLIENT_ID,
                scheduled_start=appointment_start,
                scheduled_end=appointment_end,
                location_type=LocationType.CLINIC,
                location_details="Main Office, Room 101",
                status=AppointmentStatus.SCHEDULED,
                notes="Initial consultation - full assessment",
            )
            session.add(appointment)
            await session.commit()
            await session.refresh(appointment)
            print(f"✓ Created appointment: {appointment.scheduled_start} - {appointment.scheduled_end}")
        else:
            print(
                f"✓ Appointment already exists: {appointment.scheduled_start} - {appointment.scheduled_end}"
            )

    await engine.dispose()

    print("\n" + "=" * 60)
    print("Test Data Summary")
    print("=" * 60)
    print(f"Workspace ID: {WORKSPACE_ID}")
    print(f"Client ID:    {CLIENT_ID}")
    print(f"Appointment:  Friday, October 3, 2025 at 10:00 AM UTC")
    print("=" * 60)
    print("\nTest the API with:")
    print(f'curl -H "X-Workspace-ID: {WORKSPACE_ID}" http://localhost:8000/api/v1/appointments')
    print("\nView in calendar at:")
    print("http://localhost:5173/calendar")
    print("\nIMPORTANT: Make sure your frontend uses workspace ID:", WORKSPACE_ID)
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(create_test_data())
