"""Test fail-closed behavior of blacklist checks."""

from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as SQLTimeoutError

from pazpaz.core.blacklist import is_email_blacklisted
from pazpaz.services.platform_onboarding_service import (
    EmailBlacklistedError,
    PlatformOnboardingService,
)


@pytest.mark.asyncio
class TestBlacklistFailClosed:
    """Test that blacklist checks fail closed on errors."""

    async def test_blacklist_check_fails_closed_on_db_error(self, db):
        """Database error should raise RuntimeError (fail closed)."""
        # Simulate database error by making db.scalar raise
        original_scalar = db.scalar

        async def mock_scalar(*args, **kwargs):
            raise OperationalError("DB connection lost", None, None)

        db.scalar = mock_scalar

        try:
            with pytest.raises(
                RuntimeError, match="Unable to verify email blacklist status"
            ):
                await is_email_blacklisted(db, "test@example.com")
        finally:
            # Restore original method
            db.scalar = original_scalar

    async def test_blacklist_check_fails_closed_on_timeout(self, db):
        """Database timeout should raise RuntimeError (fail closed)."""
        # Simulate timeout error
        original_scalar = db.scalar

        async def mock_scalar(*args, **kwargs):
            raise SQLTimeoutError("Query timeout", None, None)

        db.scalar = mock_scalar

        try:
            with pytest.raises(
                RuntimeError, match="Unable to verify email blacklist status"
            ):
                await is_email_blacklisted(db, "test@example.com")
        finally:
            # Restore original method
            db.scalar = original_scalar

    async def test_invitation_blocked_on_blacklist_check_failure(self, db):
        """Invitation should be blocked if blacklist check fails."""
        service = PlatformOnboardingService()

        # Simulate blacklist check failure (patch at the module where it's used)
        with patch(
            "pazpaz.core.blacklist.is_email_blacklisted",
            side_effect=RuntimeError("DB check failed"),
        ), pytest.raises(
            EmailBlacklistedError,
            match="Unable to verify invitation eligibility",
        ):
            await service.create_workspace_and_invite_therapist(
                db=db,
                workspace_name="Test Workspace",
                therapist_email="test@example.com",
                therapist_full_name="Test User",
            )

    async def test_magic_link_blocked_on_blacklist_check_failure(
        self, db, redis_client
    ):
        """Magic link should return 503 if blacklist check fails."""
        from fastapi import HTTPException

        from pazpaz.services.auth_service import request_magic_link

        # Simulate blacklist check failure (patch at the module where it's used)
        with patch(
            "pazpaz.core.blacklist.is_email_blacklisted",
            side_effect=RuntimeError("DB check failed"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await request_magic_link(
                    email="test@example.com",
                    db=db,
                    redis_client=redis_client,
                    request_ip="127.0.0.1",
                )
            assert exc_info.value.status_code == 503
            assert "Service temporarily unavailable" in exc_info.value.detail

    async def test_invitation_acceptance_blocked_on_blacklist_check_failure(self, db):
        """Invitation acceptance should be blocked if blacklist check fails."""
        from pazpaz.services.platform_onboarding_service import (
            InvalidInvitationTokenError,
        )

        service = PlatformOnboardingService()

        # First create a valid invitation
        workspace, user, token = await service.create_workspace_and_invite_therapist(
            db=db,
            workspace_name="Test Workspace",
            therapist_email="test@example.com",
            therapist_full_name="Test User",
        )

        # Now simulate blacklist check failure during acceptance (patch at the module where it's used)
        with patch(
            "pazpaz.core.blacklist.is_email_blacklisted",
            side_effect=RuntimeError("DB check failed"),
        ), pytest.raises(
            InvalidInvitationTokenError,
            match="Unable to verify invitation eligibility",
        ):
            await service.accept_invitation(db=db, token=token)

    async def test_normal_operation_still_works(self, db):
        """Normal blacklist checks should still work."""
        # This should not raise any errors
        result = await is_email_blacklisted(db, "not-blacklisted@example.com")
        assert result is False

    async def test_normal_invitation_still_works(self, db):
        """Normal invitation creation should still work."""
        service = PlatformOnboardingService()

        workspace, user, token = await service.create_workspace_and_invite_therapist(
            db=db,
            workspace_name="Normal Workspace",
            therapist_email="normal@example.com",
            therapist_full_name="Normal User",
        )

        assert workspace is not None
        assert user is not None
        assert token is not None
        assert user.email == "normal@example.com"
        assert user.is_active is False

    async def test_blacklisted_email_detection_still_works(self, db):
        """Blacklisted emails should still be detected correctly."""
        import uuid

        from pazpaz.models.email_blacklist import EmailBlacklist

        # Add email to blacklist (reason is required)
        blacklisted_email = EmailBlacklist(
            id=uuid.uuid4(),
            email="blacklisted@example.com",
            reason="Test blacklist entry",
        )
        db.add(blacklisted_email)
        await db.commit()

        # Check should return True
        result = await is_email_blacklisted(db, "blacklisted@example.com")
        assert result is True

        # Case-insensitive check
        result = await is_email_blacklisted(db, "BLACKLISTED@example.com")
        assert result is True

    async def test_invitation_blocked_for_blacklisted_email(self, db):
        """Invitation creation should be blocked for blacklisted emails."""
        import uuid

        from pazpaz.models.email_blacklist import EmailBlacklist

        # Add email to blacklist (reason is required)
        blacklisted_email = EmailBlacklist(
            id=uuid.uuid4(), email="blocked@example.com", reason="Test block"
        )
        db.add(blacklisted_email)
        await db.commit()

        service = PlatformOnboardingService()

        with pytest.raises(
            EmailBlacklistedError,
            match="is blacklisted and cannot receive invitations",
        ):
            await service.create_workspace_and_invite_therapist(
                db=db,
                workspace_name="Test Workspace",
                therapist_email="blocked@example.com",
                therapist_full_name="Blocked User",
            )
