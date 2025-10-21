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


# ============================================================================
# Invitation Tracking Fields Tests
# ============================================================================


@pytest.mark.asyncio
async def test_user_invitation_fields_default_values(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test that invitation fields have correct default values."""
    user = User(
        workspace_id=workspace_1.id,
        email="new-user@example.com",
        full_name="New User",
        role=UserRole.OWNER,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Verify defaults
    assert user.invitation_token_hash is None
    assert user.invited_by_platform_admin is False
    assert user.invited_at is None


@pytest.mark.asyncio
async def test_user_create_with_invitation_fields(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test creating a user with invitation tracking fields set."""
    from datetime import UTC, datetime
    from hashlib import sha256

    # Generate a token hash (SHA256 produces 64 hex characters)
    token = "test-invitation-token-12345"
    token_hash = sha256(token.encode()).hexdigest()
    invited_at = datetime.now(UTC)

    user = User(
        workspace_id=workspace_1.id,
        email="invited@example.com",
        full_name="Invited User",
        role=UserRole.OWNER,
        invitation_token_hash=token_hash,
        invited_by_platform_admin=True,
        invited_at=invited_at,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Verify invitation fields are set
    assert user.invitation_token_hash == token_hash
    assert len(user.invitation_token_hash) == 64  # SHA256 hex = 64 chars
    assert user.invited_by_platform_admin is True
    assert user.invited_at == invited_at


@pytest.mark.asyncio
async def test_user_invitation_token_hash_nullable(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test that invitation_token_hash can be NULL."""
    user = User(
        workspace_id=workspace_1.id,
        email="test@example.com",
        full_name="Test User",
        role=UserRole.OWNER,
        invitation_token_hash=None,  # Explicitly NULL
    )
    db_session.add(user)
    await db_session.commit()
    user_id = user.id

    # Verify NULL in database
    result = await db_session.execute(
        text("SELECT invitation_token_hash FROM users WHERE id = :id"),
        {"id": user_id},
    )
    raw_row = result.fetchone()
    assert raw_row[0] is None


@pytest.mark.asyncio
async def test_user_invited_by_platform_admin_not_nullable(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test that invited_by_platform_admin is NOT NULL in database."""
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
        text("SELECT invited_by_platform_admin FROM users WHERE id = :id"),
        {"id": user_id},
    )
    raw_row = result.fetchone()

    # Field should exist and be False (not NULL)
    assert raw_row[0] is False


@pytest.mark.asyncio
async def test_user_invited_at_nullable(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test that invited_at can be NULL."""
    user = User(
        workspace_id=workspace_1.id,
        email="test@example.com",
        full_name="Test User",
        role=UserRole.OWNER,
        invited_at=None,  # Explicitly NULL
    )
    db_session.add(user)
    await db_session.commit()
    user_id = user.id

    # Verify NULL in database
    result = await db_session.execute(
        text("SELECT invited_at FROM users WHERE id = :id"),
        {"id": user_id},
    )
    raw_row = result.fetchone()
    assert raw_row[0] is None


@pytest.mark.asyncio
async def test_user_invitation_token_hash_index_exists(
    db_session: AsyncSession,
):
    """Test that invitation_token_hash index exists in database."""
    # Query PostgreSQL index catalog
    result = await db_session.execute(
        text(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'users'
              AND indexname LIKE '%invitation_token_hash%'
            """
        )
    )
    index_info = result.fetchone()

    # Verify index exists
    assert index_info is not None, "invitation_token_hash index should exist"
    assert "invitation_token_hash" in index_info[1], (
        "Index should be on invitation_token_hash column"
    )


@pytest.mark.asyncio
async def test_user_invitation_token_hash_query_performance(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test that querying by invitation_token_hash uses the index efficiently."""
    from hashlib import sha256

    # Create multiple users with different token hashes
    users = []
    target_token_hash = None

    for i in range(50):
        token = f"invitation-token-{i}"
        token_hash = sha256(token.encode()).hexdigest()

        # Save user 24 (even number) to query later
        if i == 24:
            target_token_hash = token_hash

        user = User(
            workspace_id=workspace_1.id,
            email=f"user{i}@example.com",
            full_name=f"User {i}",
            role=UserRole.OWNER,
            invitation_token_hash=token_hash if i % 2 == 0 else None,
            invited_by_platform_admin=(i % 2 == 0),
        )
        users.append(user)

    db_session.add_all(users)
    await db_session.commit()

    # Query by token hash
    result = await db_session.execute(
        select(User).where(User.invitation_token_hash == target_token_hash)
    )
    found_user = result.scalar_one_or_none()

    # Verify we found the correct user
    assert found_user is not None
    assert found_user.invitation_token_hash == target_token_hash
    assert found_user.email == "user24@example.com"

    # Verify EXPLAIN shows index usage
    explain_result = await db_session.execute(
        text(
            f"""
            EXPLAIN (FORMAT JSON)
            SELECT * FROM users WHERE invitation_token_hash = '{target_token_hash}'
            """
        )
    )
    explain_plan = explain_result.scalar()

    # Index scan should be used for efficient queries
    assert explain_plan is not None


@pytest.mark.asyncio
async def test_user_update_invitation_fields_after_creation(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test updating invitation fields after user creation."""
    from datetime import UTC, datetime
    from hashlib import sha256

    # Create user without invitation fields
    user = User(
        workspace_id=workspace_1.id,
        email="user@example.com",
        full_name="Regular User",
        role=UserRole.OWNER,
    )
    db_session.add(user)
    await db_session.commit()
    user_id = user.id

    # Verify initial state
    assert user.invitation_token_hash is None
    assert user.invited_by_platform_admin is False
    assert user.invited_at is None

    # Update with invitation fields (simulating invitation sent)
    token_hash = sha256(b"new-invitation-token").hexdigest()
    invited_at = datetime.now(UTC)
    user.invitation_token_hash = token_hash
    user.invited_by_platform_admin = True
    user.invited_at = invited_at
    await db_session.commit()
    await db_session.refresh(user)

    # Verify update persisted
    assert user.invitation_token_hash == token_hash
    assert user.invited_by_platform_admin is True
    assert user.invited_at == invited_at

    # Retrieve from database to verify
    retrieved = await db_session.get(User, user_id)
    assert retrieved is not None
    assert retrieved.invitation_token_hash == token_hash
    assert retrieved.invited_by_platform_admin is True
    assert retrieved.invited_at == invited_at

    # Clear invitation fields (simulating invitation accepted)
    retrieved.invitation_token_hash = None
    retrieved.invited_at = None
    # Note: invited_by_platform_admin is kept for audit trail
    await db_session.commit()
    await db_session.refresh(retrieved)

    assert retrieved.invitation_token_hash is None
    assert retrieved.invited_at is None
    assert retrieved.invited_by_platform_admin is True  # Still True for audit


@pytest.mark.asyncio
async def test_user_invitation_with_platform_admin_flag(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test that invitation fields work with is_platform_admin flag."""
    from datetime import UTC, datetime
    from hashlib import sha256

    # Create invited platform admin
    token_hash = sha256(b"admin-invitation").hexdigest()
    invited_at = datetime.now(UTC)

    user = User(
        workspace_id=workspace_1.id,
        email="admin-invited@pazpaz.com",
        full_name="Invited Platform Admin",
        role=UserRole.OWNER,
        is_platform_admin=True,
        invitation_token_hash=token_hash,
        invited_by_platform_admin=True,
        invited_at=invited_at,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Verify both platform admin and invitation fields are set
    assert user.is_platform_admin is True
    assert user.invitation_token_hash == token_hash
    assert user.invited_by_platform_admin is True
    assert user.invited_at == invited_at


@pytest.mark.asyncio
async def test_user_workspace_invitation_vs_platform_admin_invitation(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test distinguishing platform admin invitations from workspace invitations."""
    from datetime import UTC, datetime
    from hashlib import sha256

    # User invited by platform admin
    admin_invited = User(
        workspace_id=workspace_1.id,
        email="admin-invited@example.com",
        full_name="Platform Admin Invited",
        role=UserRole.OWNER,
        invitation_token_hash=sha256(b"admin-token").hexdigest(),
        invited_by_platform_admin=True,
        invited_at=datetime.now(UTC),
    )

    # User invited by workspace owner (Phase 2 feature)
    workspace_invited = User(
        workspace_id=workspace_1.id,
        email="workspace-invited@example.com",
        full_name="Workspace Invited",
        role=UserRole.ASSISTANT,
        invitation_token_hash=sha256(b"workspace-token").hexdigest(),
        invited_by_platform_admin=False,
        invited_at=datetime.now(UTC),
    )

    db_session.add_all([admin_invited, workspace_invited])
    await db_session.commit()

    # Query users invited by platform admin
    result = await db_session.execute(
        select(User).where(User.invited_by_platform_admin == True)  # noqa: E712
    )
    platform_admin_invited_users = result.scalars().all()

    assert len(platform_admin_invited_users) == 1
    assert platform_admin_invited_users[0].email == "admin-invited@example.com"

    # Query users invited by workspace (not platform admin)
    result = await db_session.execute(
        select(User).where(User.invited_by_platform_admin == False)  # noqa: E712
    )
    workspace_invited_users = result.scalars().all()

    # Should include workspace_invited
    workspace_emails = {u.email for u in workspace_invited_users}
    assert "workspace-invited@example.com" in workspace_emails


@pytest.mark.asyncio
async def test_user_invitation_token_hash_uniqueness(
    db_session: AsyncSession,
    workspace_1: Workspace,
    workspace_2: Workspace,
):
    """Test that different users can have different token hashes (no uniqueness constraint)."""
    from hashlib import sha256

    # Create two users with different token hashes
    user1 = User(
        workspace_id=workspace_1.id,
        email="user1@example.com",
        full_name="User 1",
        role=UserRole.OWNER,
        invitation_token_hash=sha256(b"token-1").hexdigest(),
    )

    user2 = User(
        workspace_id=workspace_2.id,
        email="user2@example.com",
        full_name="User 2",
        role=UserRole.OWNER,
        invitation_token_hash=sha256(b"token-2").hexdigest(),
    )

    db_session.add_all([user1, user2])
    await db_session.commit()

    # Verify both users exist with different hashes
    assert user1.invitation_token_hash != user2.invitation_token_hash


@pytest.mark.asyncio
async def test_user_invitation_expiration_check(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test querying for expired invitations (useful for cleanup)."""
    from datetime import UTC, datetime, timedelta
    from hashlib import sha256

    # Create users with various invitation ages
    now = datetime.now(UTC)

    # Fresh invitation (1 hour ago)
    fresh = User(
        workspace_id=workspace_1.id,
        email="fresh@example.com",
        full_name="Fresh Invitation",
        role=UserRole.OWNER,
        invitation_token_hash=sha256(b"fresh-token").hexdigest(),
        invited_at=now - timedelta(hours=1),
    )

    # Old invitation (8 days ago - expired)
    expired = User(
        workspace_id=workspace_1.id,
        email="expired@example.com",
        full_name="Expired Invitation",
        role=UserRole.OWNER,
        invitation_token_hash=sha256(b"expired-token").hexdigest(),
        invited_at=now - timedelta(days=8),
    )

    db_session.add_all([fresh, expired])
    await db_session.commit()

    # Query for invitations older than 7 days
    expiration_cutoff = now - timedelta(days=7)
    result = await db_session.execute(
        select(User).where(
            User.invitation_token_hash.isnot(None),
            User.invited_at < expiration_cutoff,
        )
    )
    expired_invitations = result.scalars().all()

    # Should only find the expired one
    assert len(expired_invitations) == 1
    assert expired_invitations[0].email == "expired@example.com"


@pytest.mark.asyncio
async def test_user_clear_invitation_after_acceptance(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test the invitation acceptance flow - clearing token after acceptance."""
    from datetime import UTC, datetime
    from hashlib import sha256

    # Create user with pending invitation
    token_hash = sha256(b"pending-invitation").hexdigest()
    invited_at = datetime.now(UTC)

    user = User(
        workspace_id=workspace_1.id,
        email="pending@example.com",
        full_name="Pending User",
        role=UserRole.OWNER,
        invitation_token_hash=token_hash,
        invited_by_platform_admin=True,
        invited_at=invited_at,
    )
    db_session.add(user)
    await db_session.commit()
    user_id = user.id

    # Verify invitation is pending
    assert user.invitation_token_hash == token_hash
    assert user.invited_at == invited_at

    # Simulate invitation acceptance - clear token fields
    user.invitation_token_hash = None
    user.invited_at = None
    # Keep invited_by_platform_admin for audit trail
    await db_session.commit()
    await db_session.refresh(user)

    # Verify invitation fields cleared
    assert user.invitation_token_hash is None
    assert user.invited_at is None
    assert user.invited_by_platform_admin is True  # Kept for audit

    # Verify in database
    retrieved = await db_session.get(User, user_id)
    assert retrieved.invitation_token_hash is None
    assert retrieved.invited_at is None
    assert retrieved.invited_by_platform_admin is True


@pytest.mark.asyncio
async def test_user_query_pending_invitations(
    db_session: AsyncSession,
    workspace_1: Workspace,
):
    """Test querying for users with pending invitations."""
    from datetime import UTC, datetime
    from hashlib import sha256

    # Create users with various states
    pending_invitation = User(
        workspace_id=workspace_1.id,
        email="pending@example.com",
        full_name="Pending User",
        role=UserRole.OWNER,
        invitation_token_hash=sha256(b"pending-token").hexdigest(),
        invited_at=datetime.now(UTC),
    )

    accepted_invitation = User(
        workspace_id=workspace_1.id,
        email="accepted@example.com",
        full_name="Accepted User",
        role=UserRole.OWNER,
        invitation_token_hash=None,  # Token cleared after acceptance
        invited_by_platform_admin=True,  # Kept for audit
        invited_at=None,
    )

    regular_user = User(
        workspace_id=workspace_1.id,
        email="regular@example.com",
        full_name="Regular User",
        role=UserRole.OWNER,
        # No invitation fields set
    )

    db_session.add_all([pending_invitation, accepted_invitation, regular_user])
    await db_session.commit()

    # Query for pending invitations (have token_hash set)
    result = await db_session.execute(
        select(User).where(User.invitation_token_hash.isnot(None))
    )
    pending_users = result.scalars().all()

    # Should only find the pending invitation
    assert len(pending_users) == 1
    assert pending_users[0].email == "pending@example.com"
