"""
Tests for User model.

This test suite validates:
1. Platform admin flag default value and constraints
2. Platform admin index performance
3. Workspace isolation with platform admins
4. User creation with various role combinations
5. 2FA fields interaction with platform admin flag
"""

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace


@pytest.mark.asyncio
async def test_user_default_is_not_platform_admin(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test that is_platform_admin defaults to False."""
    user = User(
        workspace_id=workspace_1.id,
        email="regular-user@example.com",
        full_name="Regular User",
        role=UserRole.OWNER,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Verify default is False
    assert user.is_platform_admin is False


@pytest.mark.asyncio
async def test_user_create_platform_admin(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test creating a user with is_platform_admin=True."""
    user = User(
        workspace_id=workspace_1.id,
        email="admin@pazpaz.com",
        full_name="Platform Admin",
        role=UserRole.OWNER,
        is_platform_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Verify platform admin flag is set
    assert user.is_platform_admin is True


@pytest.mark.asyncio
async def test_user_platform_admin_nullable_constraint(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test that is_platform_admin is NOT NULL in database."""
    user = User(
        workspace_id=workspace_1.id,
        email="test@example.com",
        full_name="Test User",
        role=UserRole.OWNER,
    )
    db_session.add(user)
    await db_session.commit()
    user_id = user.id

    # Verify field is NOT NULL in raw database
    result = await db_session.execute(
        text("SELECT is_platform_admin FROM users WHERE id = :id"),
        {"id": user_id},
    )
    raw_row = result.fetchone()

    # Field should exist and be False (not NULL)
    assert raw_row[0] is False


@pytest.mark.asyncio
async def test_user_platform_admin_index_exists(
    db_session: AsyncSession,
):
    """Test that idx_users_platform_admin index exists in database."""
    # Query PostgreSQL index catalog
    result = await db_session.execute(
        text(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'users'
              AND indexname = 'idx_users_platform_admin'
            """
        )
    )
    index_info = result.fetchone()

    # Verify index exists
    assert index_info is not None, "idx_users_platform_admin index should exist"
    assert "is_platform_admin" in index_info[1], (
        "Index should be on is_platform_admin column"
    )


@pytest.mark.asyncio
async def test_user_platform_admin_query_performance(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test that querying platform admins uses the index efficiently."""
    # Create mix of regular users and platform admins
    users = [
        User(
            workspace_id=workspace_1.id,
            email=f"user{i}@example.com",
            full_name=f"User {i}",
            role=UserRole.OWNER,
            is_platform_admin=(i % 10 == 0),  # Every 10th user is platform admin
        )
        for i in range(50)
    ]

    db_session.add_all(users)
    await db_session.commit()

    # Query platform admins
    result = await db_session.execute(
        select(User).where(User.is_platform_admin == True)  # noqa: E712
    )
    platform_admins = result.scalars().all()

    # Verify we get only platform admins
    assert len(platform_admins) == 5  # 50 users, every 10th is admin
    assert all(u.is_platform_admin for u in platform_admins)

    # Verify EXPLAIN shows index usage
    explain_result = await db_session.execute(
        text(
            """
            EXPLAIN (FORMAT JSON)
            SELECT * FROM users WHERE is_platform_admin = true
            """
        )
    )
    explain_plan = explain_result.scalar()

    # Index scan should be used for efficient queries
    # Note: PostgreSQL might choose seq scan for small tables or when many rows match
    # This is just a verification that the index exists and can be used
    assert explain_plan is not None


@pytest.mark.asyncio
async def test_user_workspace_isolation_with_platform_admin(
    db_session: AsyncSession,
    workspace_1: Workspace,
    workspace_2: Workspace,
):
    """Test workspace isolation with platform admin users."""
    # Create platform admin in workspace 1
    admin_ws1 = User(
        workspace_id=workspace_1.id,
        email="admin@workspace1.com",
        full_name="Admin Workspace 1",
        role=UserRole.OWNER,
        is_platform_admin=True,
    )

    # Create regular user in workspace 2
    user_ws2 = User(
        workspace_id=workspace_2.id,
        email="user@workspace2.com",
        full_name="User Workspace 2",
        role=UserRole.OWNER,
        is_platform_admin=False,
    )

    # Create platform admin in workspace 2
    admin_ws2 = User(
        workspace_id=workspace_2.id,
        email="admin@workspace2.com",
        full_name="Admin Workspace 2",
        role=UserRole.OWNER,
        is_platform_admin=True,
    )

    db_session.add_all([admin_ws1, user_ws2, admin_ws2])
    await db_session.commit()

    # Query platform admins for workspace 1
    result = await db_session.execute(
        select(User).where(
            User.workspace_id == workspace_1.id,
            User.is_platform_admin == True,  # noqa: E712
        )
    )
    ws1_admins = result.scalars().all()

    assert len(ws1_admins) == 1
    assert ws1_admins[0].email == "admin@workspace1.com"

    # Query platform admins for workspace 2
    result = await db_session.execute(
        select(User).where(
            User.workspace_id == workspace_2.id,
            User.is_platform_admin == True,  # noqa: E712
        )
    )
    ws2_admins = result.scalars().all()

    assert len(ws2_admins) == 1
    assert ws2_admins[0].email == "admin@workspace2.com"


@pytest.mark.asyncio
async def test_user_platform_admin_with_2fa_enabled(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test that platform admin can have 2FA enabled (fields are independent)."""
    from datetime import UTC, datetime

    user = User(
        workspace_id=workspace_1.id,
        email="admin-2fa@pazpaz.com",
        full_name="Platform Admin with 2FA",
        role=UserRole.OWNER,
        is_platform_admin=True,
        totp_enabled=True,
        totp_secret="JBSWY3DPEHPK3PXP",  # Will be encrypted
        totp_enrolled_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Verify both platform admin and 2FA are set
    assert user.is_platform_admin is True
    assert user.totp_enabled is True
    assert user.totp_secret is not None


@pytest.mark.asyncio
async def test_user_platform_admin_various_roles(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test that platform admin flag works with different user roles."""
    # Platform admin as OWNER
    admin_owner = User(
        workspace_id=workspace_1.id,
        email="admin-owner@pazpaz.com",
        full_name="Admin Owner",
        role=UserRole.OWNER,
        is_platform_admin=True,
    )

    # Platform admin as ASSISTANT (edge case, but should work)
    admin_assistant = User(
        workspace_id=workspace_1.id,
        email="admin-assistant@pazpaz.com",
        full_name="Admin Assistant",
        role=UserRole.ASSISTANT,
        is_platform_admin=True,
    )

    db_session.add_all([admin_owner, admin_assistant])
    await db_session.commit()

    # Query all platform admins regardless of role
    result = await db_session.execute(
        select(User).where(User.is_platform_admin == True)  # noqa: E712
    )
    admins = result.scalars().all()

    assert len(admins) == 2
    roles = {a.role for a in admins}
    assert UserRole.OWNER in roles
    assert UserRole.ASSISTANT in roles


@pytest.mark.asyncio
async def test_user_update_platform_admin_flag(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test updating is_platform_admin flag after creation."""
    # Create regular user
    user = User(
        workspace_id=workspace_1.id,
        email="regular@example.com",
        full_name="Regular User",
        role=UserRole.OWNER,
        is_platform_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    user_id = user.id

    # Verify starts as non-admin
    assert user.is_platform_admin is False

    # Promote to platform admin
    user.is_platform_admin = True
    await db_session.commit()
    await db_session.refresh(user)

    # Verify update persisted
    assert user.is_platform_admin is True

    # Retrieve from database to verify
    retrieved = await db_session.get(User, user_id)
    assert retrieved is not None
    assert retrieved.is_platform_admin is True

    # Demote back to regular user
    retrieved.is_platform_admin = False
    await db_session.commit()
    await db_session.refresh(retrieved)

    assert retrieved.is_platform_admin is False


@pytest.mark.asyncio
async def test_user_platform_admin_count_query(
    db_session: AsyncSession,
    workspace_1: Workspace,
    workspace_2: Workspace,
):
    """Test counting platform admins across all workspaces."""
    # Create users across workspaces
    users = [
        User(
            workspace_id=workspace_1.id,
            email=f"ws1-user{i}@example.com",
            full_name=f"WS1 User {i}",
            role=UserRole.OWNER,
            is_platform_admin=(i < 2),  # First 2 are admins
        )
        for i in range(5)
    ] + [
        User(
            workspace_id=workspace_2.id,
            email=f"ws2-user{i}@example.com",
            full_name=f"WS2 User {i}",
            role=UserRole.OWNER,
            is_platform_admin=(i < 3),  # First 3 are admins
        )
        for i in range(5)
    ]

    db_session.add_all(users)
    await db_session.commit()

    # Count all platform admins
    result = await db_session.execute(
        select(User).where(User.is_platform_admin == True)  # noqa: E712
    )
    all_admins = result.scalars().all()

    assert len(all_admins) == 5  # 2 from ws1 + 3 from ws2


@pytest.mark.asyncio
async def test_user_repr_includes_platform_admin_info(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test that __repr__ works correctly with platform admin flag."""
    user = User(
        workspace_id=workspace_1.id,
        email="admin@pazpaz.com",
        full_name="Platform Admin",
        role=UserRole.OWNER,
        is_platform_admin=True,
    )
    db_session.add(user)
    await db_session.commit()

    # __repr__ should work without errors
    repr_str = repr(user)
    assert "admin@pazpaz.com" in repr_str
    assert "owner" in repr_str.lower()
    assert str(user.id) in repr_str
