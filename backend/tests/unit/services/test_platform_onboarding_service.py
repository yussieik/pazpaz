"""Test platform onboarding service for therapist invitations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pazpaz.models.user import UserRole
from pazpaz.models.workspace import Workspace
from pazpaz.services.platform_onboarding_service import (
    DuplicateEmailError,
    ExpiredInvitationTokenError,
    InvalidInvitationTokenError,
    InvitationAlreadyAcceptedError,
    InvitationNotFoundError,
    PlatformOnboardingService,
    UserAlreadyActiveError,
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
async def service() -> PlatformOnboardingService:
    """Create PlatformOnboardingService instance."""
    return PlatformOnboardingService()


class TestCreateWorkspaceAndInviteTherapist:
    """Test create_workspace_and_invite_therapist method."""

    @pytest.mark.asyncio
    async def test_create_workspace_and_invite_therapist_success(
        self, db_session: AsyncSession, service: PlatformOnboardingService
    ):
        """Test successful workspace and therapist creation."""
        workspace, user, token = await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="Sarah's Massage Therapy",
            therapist_email="sarah@example.com",
            therapist_full_name="Sarah Chen",
        )

        # Verify workspace
        assert workspace.id is not None
        assert workspace.name == "Sarah's Massage Therapy"
        assert workspace.is_active is True

        # Verify user
        assert user.id is not None
        assert user.workspace_id == workspace.id
        assert user.email == "sarah@example.com"
        assert user.full_name == "Sarah Chen"
        assert user.role == UserRole.OWNER
        assert user.is_active is False  # Not yet activated
        assert user.is_platform_admin is False
        assert user.invited_by_platform_admin is True
        assert user.invited_at is not None
        assert user.invitation_token_hash is not None

        # Verify token
        assert token is not None
        assert len(token) > 40  # 256-bit token should be ~43 chars

        # Verify token hash is SHA256 (64 hex chars)
        assert len(user.invitation_token_hash) == 64
        assert all(c in "0123456789abcdef" for c in user.invitation_token_hash)

    @pytest.mark.asyncio
    async def test_create_workspace_generates_unique_token(
        self, db_session: AsyncSession, service: PlatformOnboardingService
    ):
        """Test that each workspace creation generates a unique token."""
        workspace1, user1, token1 = await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="Clinic 1",
            therapist_email="therapist1@example.com",
            therapist_full_name="Therapist One",
        )

        workspace2, user2, token2 = await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="Clinic 2",
            therapist_email="therapist2@example.com",
            therapist_full_name="Therapist Two",
        )

        # Tokens should be different
        assert token1 != token2
        # Token hashes should be different
        assert user1.invitation_token_hash != user2.invitation_token_hash

    @pytest.mark.asyncio
    async def test_create_workspace_sets_invitation_metadata(
        self, db_session: AsyncSession, service: PlatformOnboardingService
    ):
        """Test that invitation metadata is properly set."""
        workspace, user, _token = await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="Wellness Center",
            therapist_email="dr.jones@example.com",
            therapist_full_name="Dr. Jane Jones",
        )

        # Verify invitation metadata
        assert user.invited_by_platform_admin is True
        assert user.invited_at is not None

        # Verify invited_at is recent (within last 5 seconds)
        now = datetime.now(UTC)
        time_diff = (now - user.invited_at).total_seconds()
        assert time_diff < 5

        # Verify invited_at is timezone-aware (UTC)
        assert user.invited_at.tzinfo is not None

    @pytest.mark.asyncio
    async def test_create_workspace_duplicate_email_fails(
        self, db_session: AsyncSession, service: PlatformOnboardingService
    ):
        """Test that creating workspace with duplicate email fails."""
        # Create first workspace
        await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="Clinic 1",
            therapist_email="duplicate@example.com",
            therapist_full_name="First Therapist",
        )

        # Attempt to create second workspace with same email
        with pytest.raises(DuplicateEmailError) as exc_info:
            await service.create_workspace_and_invite_therapist(
                db=db_session,
                workspace_name="Clinic 2",
                therapist_email="duplicate@example.com",
                therapist_full_name="Second Therapist",
            )

        assert "already exists" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_workspace_invalid_inputs(
        self, db_session: AsyncSession, service: PlatformOnboardingService
    ):
        """Test that invalid inputs raise ValueError."""
        # Empty workspace name
        with pytest.raises(ValueError) as exc_info:
            await service.create_workspace_and_invite_therapist(
                db=db_session,
                workspace_name="",
                therapist_email="therapist@example.com",
                therapist_full_name="Therapist Name",
            )
        assert "workspace_name" in str(exc_info.value)

        # Empty email
        with pytest.raises(ValueError) as exc_info:
            await service.create_workspace_and_invite_therapist(
                db=db_session,
                workspace_name="Valid Clinic",
                therapist_email="",
                therapist_full_name="Therapist Name",
            )
        assert "therapist_email" in str(exc_info.value)

        # Empty full name
        with pytest.raises(ValueError) as exc_info:
            await service.create_workspace_and_invite_therapist(
                db=db_session,
                workspace_name="Valid Clinic",
                therapist_email="therapist@example.com",
                therapist_full_name="",
            )
        assert "therapist_full_name" in str(exc_info.value)

        # Whitespace-only inputs
        with pytest.raises(ValueError):
            await service.create_workspace_and_invite_therapist(
                db=db_session,
                workspace_name="   ",
                therapist_email="therapist@example.com",
                therapist_full_name="Therapist Name",
            )

    @pytest.mark.asyncio
    async def test_create_workspace_strips_whitespace(
        self, db_session: AsyncSession, service: PlatformOnboardingService
    ):
        """Test that leading/trailing whitespace is stripped from inputs."""
        workspace, user, _token = await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="  Clinic Name  ",
            therapist_email="  therapist@example.com  ",
            therapist_full_name="  Therapist Name  ",
        )

        assert workspace.name == "Clinic Name"
        assert user.email == "therapist@example.com"
        assert user.full_name == "Therapist Name"

    @pytest.mark.asyncio
    async def test_create_workspace_transaction_rollback(
        self, db_session: AsyncSession, service: PlatformOnboardingService
    ):
        """Test that transaction is rolled back on error."""
        # Create first workspace successfully
        await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="First Clinic",
            therapist_email="first@example.com",
            therapist_full_name="First Therapist",
        )

        # Attempt to create second workspace with duplicate email (should fail)
        with pytest.raises(DuplicateEmailError):
            await service.create_workspace_and_invite_therapist(
                db=db_session,
                workspace_name="Second Clinic",
                therapist_email="first@example.com",  # Duplicate
                therapist_full_name="Second Therapist",
            )

        # Verify that "Second Clinic" workspace was NOT created
        from sqlalchemy import select

        result = await db_session.execute(
            select(Workspace).where(Workspace.name == "Second Clinic")
        )
        second_workspace = result.scalar_one_or_none()
        assert second_workspace is None


class TestAcceptInvitation:
    """Test accept_invitation method."""

    @pytest.mark.asyncio
    async def test_accept_invitation_success(
        self, db_session: AsyncSession, service: PlatformOnboardingService
    ):
        """Test successful invitation acceptance."""
        # Create workspace and user with invitation
        _workspace, user, token = await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="Clinic",
            therapist_email="therapist@example.com",
            therapist_full_name="Therapist Name",
        )

        assert user.is_active is False
        assert user.invitation_token_hash is not None

        # Accept invitation
        activated_user = await service.accept_invitation(db=db_session, token=token)

        # Verify user is activated
        assert activated_user.id == user.id
        assert activated_user.is_active is True
        assert activated_user.invitation_token_hash is None  # Token cleared

    @pytest.mark.asyncio
    async def test_accept_invitation_invalid_token(
        self, db_session: AsyncSession, service: PlatformOnboardingService
    ):
        """Test that invalid token raises InvalidInvitationTokenError."""
        # Create workspace and user
        await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="Clinic",
            therapist_email="therapist@example.com",
            therapist_full_name="Therapist Name",
        )

        # Attempt to accept with invalid token
        with pytest.raises(InvalidInvitationTokenError) as exc_info:
            await service.accept_invitation(db=db_session, token="invalid-token-12345")

        assert "Invalid invitation token" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_accept_invitation_expired_token(
        self, db_session: AsyncSession, service: PlatformOnboardingService
    ):
        """Test that expired token raises ExpiredInvitationTokenError."""
        # Create workspace and user
        _workspace, user, token = await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="Clinic",
            therapist_email="therapist@example.com",
            therapist_full_name="Therapist Name",
        )

        # Manually set invited_at to 8 days ago (expired)
        user.invited_at = datetime.now(UTC) - timedelta(days=8)
        await db_session.commit()

        # Attempt to accept expired invitation
        with pytest.raises(ExpiredInvitationTokenError) as exc_info:
            await service.accept_invitation(db=db_session, token=token)

        assert "expired" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_accept_invitation_already_accepted(
        self, db_session: AsyncSession, service: PlatformOnboardingService
    ):
        """Test that accepting an already-accepted invitation fails."""
        # Create and accept invitation
        _workspace, _user, token = await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="Clinic",
            therapist_email="therapist@example.com",
            therapist_full_name="Therapist Name",
        )

        await service.accept_invitation(db=db_session, token=token)

        # Manually create a new user with same token hash to test the logic
        # (In reality, token is deleted after acceptance)
        (
            _workspace2,
            user2,
            token2,
        ) = await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="Clinic 2",
            therapist_email="therapist2@example.com",
            therapist_full_name="Therapist 2",
        )

        # Manually activate user
        user2.is_active = True
        await db_session.commit()

        # Attempt to accept invitation for already-active user
        with pytest.raises(InvitationAlreadyAcceptedError) as exc_info:
            await service.accept_invitation(db=db_session, token=token2)

        assert "already been accepted" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_accept_invitation_token_cleared_single_use(
        self, db_session: AsyncSession, service: PlatformOnboardingService
    ):
        """Test that token is cleared after acceptance (single-use)."""
        # Create and accept invitation
        _workspace, user, token = await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="Clinic",
            therapist_email="therapist@example.com",
            therapist_full_name="Therapist Name",
        )

        activated_user = await service.accept_invitation(db=db_session, token=token)

        # Verify token hash is cleared
        assert activated_user.invitation_token_hash is None

        # Attempt to use same token again (should fail)
        with pytest.raises(InvalidInvitationTokenError):
            await service.accept_invitation(db=db_session, token=token)


class TestResendInvitation:
    """Test resend_invitation method."""

    @pytest.mark.asyncio
    async def test_resend_invitation_success(
        self, db_session: AsyncSession, service: PlatformOnboardingService
    ):
        """Test successful invitation resend."""
        # Create workspace and user
        (
            _workspace,
            user,
            original_token,
        ) = await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="Clinic",
            therapist_email="therapist@example.com",
            therapist_full_name="Therapist Name",
        )

        original_token_hash = user.invitation_token_hash
        original_invited_at = user.invited_at

        # Resend invitation
        new_token = await service.resend_invitation(db=db_session, user_id=user.id)

        # Refresh user
        await db_session.refresh(user)

        # Verify new token is different
        assert new_token != original_token
        assert user.invitation_token_hash != original_token_hash

        # Verify invited_at is updated
        assert user.invited_at > original_invited_at

        # Verify new token works for acceptance
        activated_user = await service.accept_invitation(db=db_session, token=new_token)
        assert activated_user.is_active is True

    @pytest.mark.asyncio
    async def test_resend_invitation_user_not_found(
        self, db_session: AsyncSession, service: PlatformOnboardingService
    ):
        """Test that resending for non-existent user raises InvitationNotFoundError."""
        non_existent_user_id = uuid.uuid4()

        with pytest.raises(InvitationNotFoundError) as exc_info:
            await service.resend_invitation(db=db_session, user_id=non_existent_user_id)

        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_resend_invitation_user_already_active(
        self, db_session: AsyncSession, service: PlatformOnboardingService
    ):
        """Test that resending for active user raises UserAlreadyActiveError."""
        # Create and accept invitation
        _workspace, user, token = await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="Clinic",
            therapist_email="therapist@example.com",
            therapist_full_name="Therapist Name",
        )

        await service.accept_invitation(db=db_session, token=token)

        # Attempt to resend for active user
        with pytest.raises(UserAlreadyActiveError) as exc_info:
            await service.resend_invitation(db=db_session, user_id=user.id)

        assert "already active" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_resend_invitation_invalidates_old_token(
        self, db_session: AsyncSession, service: PlatformOnboardingService
    ):
        """Test that resending invalidates the old token."""
        # Create workspace and user
        (
            _workspace,
            user,
            original_token,
        ) = await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="Clinic",
            therapist_email="therapist@example.com",
            therapist_full_name="Therapist Name",
        )

        # Resend invitation (generates new token)
        _new_token = await service.resend_invitation(db=db_session, user_id=user.id)

        # Attempt to accept with old token (should fail)
        with pytest.raises(InvalidInvitationTokenError):
            await service.accept_invitation(db=db_session, token=original_token)


class TestTransactionSafety:
    """Test transaction safety and rollback behavior."""

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_create_error(
        self, db_session: AsyncSession, service: PlatformOnboardingService
    ):
        """Test that transaction is rolled back on create error."""
        # Create first workspace
        (
            workspace1,
            _user1,
            _token1,
        ) = await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="First Clinic",
            therapist_email="first@example.com",
            therapist_full_name="First Therapist",
        )

        # Count workspaces before failed attempt
        from sqlalchemy import func, select

        result = await db_session.execute(select(func.count(Workspace.id)))
        count_before = result.scalar()

        # Attempt to create with duplicate email (should fail and rollback)
        with pytest.raises(DuplicateEmailError):
            await service.create_workspace_and_invite_therapist(
                db=db_session,
                workspace_name="Second Clinic",
                therapist_email="first@example.com",
                therapist_full_name="Second Therapist",
            )

        # Count workspaces after failed attempt
        result = await db_session.execute(select(func.count(Workspace.id)))
        count_after = result.scalar()

        # Verify no new workspace was created
        assert count_after == count_before

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_accept_error(
        self, db_session: AsyncSession, service: PlatformOnboardingService
    ):
        """Test that transaction is rolled back on accept error."""
        # Create workspace and user
        _workspace, user, _token = await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="Clinic",
            therapist_email="therapist@example.com",
            therapist_full_name="Therapist Name",
        )

        # Manually expire the invitation
        user.invited_at = datetime.now(UTC) - timedelta(days=8)
        await db_session.commit()

        original_is_active = user.is_active

        # Attempt to accept expired invitation (should fail and rollback)
        try:
            # Use a mock token to trigger the error path
            import hashlib

            mock_token = "mock-token-for-expired-test"
            user.invitation_token_hash = hashlib.sha256(mock_token.encode()).hexdigest()
            await db_session.commit()

            await service.accept_invitation(db=db_session, token=mock_token)
        except ExpiredInvitationTokenError:
            pass

        # Refresh user
        await db_session.refresh(user)

        # Verify user state was rolled back (not activated)
        assert user.is_active == original_is_active
        # Token hash should still be set (not cleared)
        assert user.invitation_token_hash is not None
