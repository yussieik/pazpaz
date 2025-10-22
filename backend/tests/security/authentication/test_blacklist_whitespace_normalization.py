"""Test whitespace normalization in blacklist checks.

This test suite verifies that email addresses are properly normalized
(whitespace stripped) to prevent bypass attacks on the blacklist system.

Security Context:
    Attackers could bypass blacklist checks by adding leading/trailing
    whitespace to blacklisted emails:
    - Blacklisted: "evil@example.com"
    - Bypass: " evil@example.com " (with spaces)
    - Bypass: "evil@example.com\n" (with newline)
    - Bypass: "\tevil@example.com" (with tab)

    This test suite ensures all email normalization includes .strip().lower()
    to prevent these bypass attacks.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.blacklist import is_email_blacklisted
from pazpaz.models.email_blacklist import EmailBlacklist
from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace
from tests.conftest import add_csrf_to_client, get_auth_headers

# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def platform_admin(db: AsyncSession, workspace_1: Workspace) -> User:
    """Create a platform admin user for testing."""
    user = User(
        id=uuid.uuid4(),
        workspace_id=workspace_1.id,
        email="admin@pazpaz.com",
        full_name="Platform Admin",
        role=UserRole.OWNER,
        is_active=True,
        is_platform_admin=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ============================================================================
# Tests
# ============================================================================


@pytest.mark.asyncio
class TestBlacklistWhitespaceNormalization:
    """Test that whitespace is properly normalized in blacklist checks."""

    async def test_leading_whitespace_detected(
        self, db: AsyncSession, platform_admin: User
    ):
        """Emails with leading whitespace should be detected as blacklisted."""
        # Add to blacklist (normalized)
        entry = EmailBlacklist(
            email="evil@example.com", reason="Test", added_by=platform_admin.id
        )
        db.add(entry)
        await db.commit()

        # Check with leading whitespace - should still be detected
        assert await is_email_blacklisted(db, "  evil@example.com") is True
        assert await is_email_blacklisted(db, "\tevil@example.com") is True
        assert await is_email_blacklisted(db, "\n\nevil@example.com") is True

    async def test_trailing_whitespace_detected(
        self, db: AsyncSession, platform_admin: User
    ):
        """Emails with trailing whitespace should be detected as blacklisted."""
        # Add to blacklist (normalized)
        entry = EmailBlacklist(
            email="evil@example.com", reason="Test", added_by=platform_admin.id
        )
        db.add(entry)
        await db.commit()

        # Check with trailing whitespace - should still be detected
        assert await is_email_blacklisted(db, "evil@example.com  ") is True
        assert await is_email_blacklisted(db, "evil@example.com\n") is True
        assert await is_email_blacklisted(db, "evil@example.com\t") is True

    async def test_both_leading_and_trailing_whitespace(
        self, db: AsyncSession, platform_admin: User
    ):
        """Emails with both leading and trailing whitespace should be detected."""
        # Add to blacklist (normalized)
        entry = EmailBlacklist(
            email="evil@example.com", reason="Test", added_by=platform_admin.id
        )
        db.add(entry)
        await db.commit()

        # Check with both leading and trailing whitespace
        assert await is_email_blacklisted(db, "  evil@example.com  ") is True
        assert await is_email_blacklisted(db, "\tevil@example.com\n") is True
        assert await is_email_blacklisted(db, "\n evil@example.com \t") is True

    async def test_multiple_types_of_whitespace(
        self, db: AsyncSession, platform_admin: User
    ):
        """Emails with various types of whitespace should be detected."""
        # Add to blacklist (normalized)
        entry = EmailBlacklist(
            email="evil@example.com", reason="Test", added_by=platform_admin.id
        )
        db.add(entry)
        await db.commit()

        # Check with various whitespace characters
        assert await is_email_blacklisted(db, " \t\nevil@example.com\n\t ") is True

    async def test_whitespace_with_case_variations(
        self, db: AsyncSession, platform_admin: User
    ):
        """Whitespace normalization should work with case variations."""
        # Add to blacklist (normalized to lowercase)
        entry = EmailBlacklist(
            email="evil@example.com", reason="Test", added_by=platform_admin.id
        )
        db.add(entry)
        await db.commit()

        # Check with whitespace AND case variations
        assert await is_email_blacklisted(db, "  EVIL@EXAMPLE.COM  ") is True
        assert await is_email_blacklisted(db, "\tEvil@Example.Com\n") is True

    async def test_add_to_blacklist_with_whitespace(
        self,
        db: AsyncSession,
        client: AsyncClient,
        platform_admin: User,
        redis_client,
    ):
        """Adding email with whitespace should normalize it before storing."""
        # Add CSRF token
        csrf_token = await add_csrf_to_client(
            client, platform_admin.workspace_id, platform_admin.id, redis_client
        )

        headers = get_auth_headers(
            workspace_id=platform_admin.workspace_id,
            user_id=platform_admin.id,
            email=platform_admin.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        response = await client.post(
            "/api/v1/platform-admin/blacklist",
            json={
                "email": "  spam@example.com  ",  # With whitespace
                "reason": "Test spam account",
            },
            headers=headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "spam@example.com"  # Should be normalized

        # Verify stored without whitespace in database
        entry = await db.scalar(
            select(EmailBlacklist).where(EmailBlacklist.email == "spam@example.com")
        )
        assert entry is not None
        assert entry.email == "spam@example.com"  # No whitespace

    async def test_add_to_blacklist_with_tabs_and_newlines(
        self,
        db: AsyncSession,
        client: AsyncClient,
        platform_admin: User,
        redis_client,
    ):
        """Adding email with tabs/newlines should normalize it."""
        # Add CSRF token
        csrf_token = await add_csrf_to_client(
            client, platform_admin.workspace_id, platform_admin.id, redis_client
        )

        headers = get_auth_headers(
            workspace_id=platform_admin.workspace_id,
            user_id=platform_admin.id,
            email=platform_admin.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        response = await client.post(
            "/api/v1/platform-admin/blacklist",
            json={
                "email": "\tspam2@example.com\n",  # With tab and newline
                "reason": "Test spam account",
            },
            headers=headers,
        )
        assert response.status_code == 201

        # Verify stored without whitespace
        entry = await db.scalar(
            select(EmailBlacklist).where(EmailBlacklist.email == "spam2@example.com")
        )
        assert entry is not None
        assert entry.email == "spam2@example.com"  # No whitespace

    async def test_remove_from_blacklist_with_whitespace(
        self,
        db: AsyncSession,
        client: AsyncClient,
        platform_admin: User,
        redis_client,
    ):
        """Removing email with whitespace should normalize it."""
        # Add to blacklist first
        entry = EmailBlacklist(
            email="remove@example.com", reason="Test", added_by=platform_admin.id
        )
        db.add(entry)
        await db.commit()

        # Add CSRF token
        csrf_token = await add_csrf_to_client(
            client, platform_admin.workspace_id, platform_admin.id, redis_client
        )

        headers = get_auth_headers(
            workspace_id=platform_admin.workspace_id,
            user_id=platform_admin.id,
            email=platform_admin.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        # Remove with whitespace in URL path (URL-encoded spaces)
        response = await client.delete(
            "/api/v1/platform-admin/blacklist/%20%20remove@example.com%20%20",
            headers=headers,
        )
        assert response.status_code == 200

        # Verify removed
        entry = await db.scalar(
            select(EmailBlacklist).where(EmailBlacklist.email == "remove@example.com")
        )
        assert entry is None

    async def test_invitation_blocked_with_whitespace(
        self, db: AsyncSession, platform_admin: User
    ):
        """Invitation should be blocked even with whitespace in email."""
        from pazpaz.services.platform_onboarding_service import (
            EmailBlacklistedError,
            PlatformOnboardingService,
        )

        # Blacklist email (normalized)
        entry = EmailBlacklist(
            email="blocked@example.com", reason="Test", added_by=platform_admin.id
        )
        db.add(entry)
        await db.commit()

        # Try to invite with whitespace - should raise EmailBlacklistedError
        service = PlatformOnboardingService()
        with pytest.raises(EmailBlacklistedError):
            await service.create_workspace_and_invite_therapist(
                db=db,
                workspace_name="Test Workspace",
                therapist_email="  blocked@example.com  ",  # With whitespace
                therapist_full_name="Test User",
            )

    async def test_duplicate_blacklist_prevented_with_whitespace(
        self,
        db: AsyncSession,
        client: AsyncClient,
        platform_admin: User,
        redis_client,
    ):
        """Cannot add duplicate email even with different whitespace."""
        # Add CSRF token
        csrf_token = await add_csrf_to_client(
            client, platform_admin.workspace_id, platform_admin.id, redis_client
        )

        headers = get_auth_headers(
            workspace_id=platform_admin.workspace_id,
            user_id=platform_admin.id,
            email=platform_admin.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        # Add to blacklist first
        response = await client.post(
            "/api/v1/platform-admin/blacklist",
            json={"email": "dup@example.com", "reason": "Original"},
            headers=headers,
        )
        assert response.status_code == 201

        # Try to add again with whitespace - should fail
        response = await client.post(
            "/api/v1/platform-admin/blacklist",
            json={"email": "  dup@example.com  ", "reason": "Duplicate attempt"},
            headers=headers,
        )
        assert response.status_code == 400
        assert "already blacklisted" in response.json()["detail"].lower()

    async def test_non_blacklisted_email_with_whitespace(
        self, db: AsyncSession, platform_admin: User
    ):
        """Non-blacklisted email should return False even with whitespace."""
        # Don't add anything to blacklist

        # Check with whitespace - should return False
        assert await is_email_blacklisted(db, "  clean@example.com  ") is False
        assert await is_email_blacklisted(db, "\tclean@example.com\n") is False

    async def test_blacklist_check_with_extreme_whitespace(
        self, db: AsyncSession, platform_admin: User
    ):
        """Blacklist check should handle extreme amounts of whitespace."""
        # Add to blacklist (normalized)
        entry = EmailBlacklist(
            email="evil@example.com", reason="Test", added_by=platform_admin.id
        )
        db.add(entry)
        await db.commit()

        # Check with extreme whitespace
        extreme_whitespace = (
            "          \t\t\t\n\n\n    evil@example.com    \n\n\n\t\t\t          "
        )
        assert await is_email_blacklisted(db, extreme_whitespace) is True
