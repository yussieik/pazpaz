#!/usr/bin/env python3
"""
Create Platform Admin User Script

This script creates a platform admin user for local development.
In production, this should be done via secure deployment process.

Usage:
    cd backend
    env PYTHONPATH=src uv run python scripts/create_platform_admin.py your-email@example.com "Your Name"
"""

import sys
import asyncio
from sqlalchemy import select
from pazpaz.db.base import AsyncSessionLocal
from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace
import uuid


async def create_platform_admin(email: str, full_name: str):
    """Create or update a user to be a platform admin."""
    async with AsyncSessionLocal() as db:
        # Check if user already exists
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user:
            # Update existing user to be platform admin
            user.is_platform_admin = True
            user.is_active = True
            print(f"✅ Updated existing user {email} to platform admin")
            print(f"   User ID: {user.id}")
            print(f"   Workspace ID: {user.workspace_id}")
        else:
            # Create new workspace for platform admin
            workspace = Workspace(
                id=uuid.uuid4(),
                name=f"{full_name}'s Platform Admin Workspace"
            )
            db.add(workspace)
            await db.flush()

            # Create new platform admin user
            user = User(
                id=uuid.uuid4(),
                workspace_id=workspace.id,
                email=email,
                full_name=full_name,
                role=UserRole.OWNER,
                is_active=True,
                is_platform_admin=True,
            )
            db.add(user)
            print(f"✅ Created new platform admin user: {email}")
            print(f"   User ID: {user.id}")
            print(f"   Workspace ID: {workspace.id}")

        await db.commit()
        await db.refresh(user)

        print(f"\n🎉 Platform admin setup complete!")
        print(f"\nNext steps:")
        print(f"1. Go to http://localhost:5173/")
        print(f"2. Click 'Send Magic Link'")
        print(f"3. Enter email: {email}")
        print(f"4. Check MailHog at http://localhost:8025")
        print(f"5. Click the magic link in the email")
        print(f"6. Access platform admin at http://localhost:5173/platform-admin")

        return user


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python create_platform_admin.py <email> <full_name>")
        print("Example: python create_platform_admin.py admin@example.com 'Admin User'")
        sys.exit(1)

    email = sys.argv[1]
    full_name = sys.argv[2]

    print(f"Creating platform admin user...")
    print(f"Email: {email}")
    print(f"Name: {full_name}\n")

    asyncio.run(create_platform_admin(email, full_name))
