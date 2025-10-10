#!/usr/bin/env python3
"""
Development database seeding script.

Creates test workspace and users for local development.

Usage:
    cd backend
    PYTHONPATH=src uv run python seed_dev_data.py
"""

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from pazpaz.core.config import settings
from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace


async def seed_dev_data():
    """Create test workspace and users for development."""
    # Create async engine
    engine = create_async_engine(settings.database_url, echo=False)
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        # Check if test workspace already exists
        result = await session.execute(
            select(Workspace).where(Workspace.name == "Test Workspace")
        )
        workspace = result.scalar_one_or_none()

        if workspace:
            print("✅ Test workspace already exists")
            print(f"   Workspace ID: {workspace.id}")
        else:
            # Create test workspace
            workspace = Workspace(
                id=uuid.uuid4(),
                name="Test Workspace",
                is_active=True,
            )
            session.add(workspace)
            await session.flush()
            print(f"✅ Created test workspace: {workspace.id}")

        # Check if test user already exists
        result = await session.execute(
            select(User).where(
                User.workspace_id == workspace.id, User.email == "test@example.com"
            )
        )
        test_user = result.scalar_one_or_none()

        if test_user:
            print("✅ Test user already exists")
            print(f"   Email: {test_user.email}")
            print(f"   User ID: {test_user.id}")
        else:
            # Create test user (owner)
            test_user = User(
                id=uuid.uuid4(),
                workspace_id=workspace.id,
                email="test@example.com",
                full_name="Test Therapist",
                role=UserRole.OWNER,
                is_active=True,
            )
            session.add(test_user)
            await session.flush()
            print(f"✅ Created test user: {test_user.email}")
            print(f"   User ID: {test_user.id}")

        # Check if second test user exists
        result = await session.execute(
            select(User).where(
                User.workspace_id == workspace.id, User.email == "assistant@example.com"
            )
        )
        assistant_user = result.scalar_one_or_none()

        if assistant_user:
            print("✅ Assistant user already exists")
            print(f"   Email: {assistant_user.email}")
            print(f"   User ID: {assistant_user.id}")
        else:
            # Create assistant user
            assistant_user = User(
                id=uuid.uuid4(),
                workspace_id=workspace.id,
                email="assistant@example.com",
                full_name="Test Assistant",
                role=UserRole.ASSISTANT,
                is_active=True,
            )
            session.add(assistant_user)
            await session.flush()
            print(f"✅ Created assistant user: {assistant_user.email}")
            print(f"   User ID: {assistant_user.id}")

        await session.commit()

    await engine.dispose()

    print("\n" + "=" * 80)
    print("🎉 Development data seeded successfully!")
    print("=" * 80)
    print("\nYou can now use dev_login.py to request a magic link:")
    print("   PYTHONPATH=src uv run python dev_login.py")
    print("\nTest users created:")
    print("   • test@example.com (Owner)")
    print("   • assistant@example.com (Assistant)")
    print("\nMailHog UI: http://localhost:8025")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(seed_dev_data())
