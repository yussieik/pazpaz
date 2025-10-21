"""Tests for invitation acceptance endpoint (GET /api/v1/auth/accept-invite)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.config import settings
from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace
from pazpaz.services.platform_onboarding_service import (
    ExpiredInvitationTokenError,
    InvalidInvitationTokenError,
    InvitationAlreadyAcceptedError,
)

pytestmark = pytest.mark.asyncio


class TestAcceptInvitationSuccess:
    """Test successful invitation acceptance flow."""

    async def test_accept_invitation_success_redirects_to_app(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """Valid invitation token should activate user and redirect to app."""
        # Create inactive user with invitation token
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="newtherapist@example.com",
            full_name="New Therapist",
            role=UserRole.OWNER,
            is_active=False,
            invitation_token_hash="test_hash",
            invited_at=datetime.now(UTC),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Mock the service to return activated user
        with patch(
            "pazpaz.api.auth.PlatformOnboardingService.accept_invitation"
        ) as mock_accept:
            # Return activated user
            activated_user = User(
                id=user.id,
                workspace_id=user.workspace_id,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                is_active=True,
                invitation_token_hash=None,
                invited_at=user.invited_at,
            )
            mock_accept.return_value = activated_user

            # Accept invitation
            response = await client.get(
                "/api/v1/auth/accept-invite",
                params={"token": "valid_invitation_token_123"},
                follow_redirects=False,
            )

            # Should redirect to root
            assert response.status_code == 303
            assert response.headers["location"] == "/"

            # Verify service was called
            mock_accept.assert_called_once()
            call_args = mock_accept.call_args
            assert call_args[0][1] == "valid_invitation_token_123"

    async def test_accept_invitation_success_creates_session(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """Successful invitation acceptance should create JWT session."""
        # Create inactive user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="newuser@example.com",
            full_name="New User",
            role=UserRole.OWNER,
            is_active=False,
            invitation_token_hash="test_hash",
            invited_at=datetime.now(UTC),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Mock the service
        with patch(
            "pazpaz.api.auth.PlatformOnboardingService.accept_invitation"
        ) as mock_accept:
            activated_user = User(
                id=user.id,
                workspace_id=user.workspace_id,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                is_active=True,
            )
            mock_accept.return_value = activated_user

            response = await client.get(
                "/api/v1/auth/accept-invite",
                params={"token": "valid_token"},
                follow_redirects=False,
            )

            assert response.status_code == 303

            # Verify JWT token is present in cookies
            assert "access_token" in response.cookies
            jwt_token = response.cookies["access_token"]

            # Decode and verify JWT contents
            decoded = jwt.decode(jwt_token, settings.secret_key, algorithms=["HS256"])
            assert decoded["user_id"] == str(user.id)
            assert decoded["workspace_id"] == str(user.workspace_id)
            assert decoded["email"] == user.email

    async def test_accept_invitation_success_sets_cookies(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """Successful invitation acceptance should set HttpOnly cookies."""
        # Create inactive user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="cookie@example.com",
            full_name="Cookie Test",
            role=UserRole.OWNER,
            is_active=False,
            invitation_token_hash="test_hash",
            invited_at=datetime.now(UTC),
        )
        db.add(user)
        await db.commit()

        # Mock the service
        with patch(
            "pazpaz.api.auth.PlatformOnboardingService.accept_invitation"
        ) as mock_accept:
            activated_user = User(
                id=user.id,
                workspace_id=user.workspace_id,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                is_active=True,
            )
            mock_accept.return_value = activated_user

            response = await client.get(
                "/api/v1/auth/accept-invite",
                params={"token": "valid_token"},
                follow_redirects=False,
            )

            assert response.status_code == 303

            # Verify access_token cookie
            assert "access_token" in response.cookies
            # Note: httpx.AsyncClient doesn't expose cookie attributes
            # We test cookie attributes in integration tests

            # Verify CSRF token cookie
            assert "csrf_token" in response.cookies


class TestAcceptInvitationErrors:
    """Test error handling for invitation acceptance."""

    async def test_accept_invitation_invalid_token_redirects_to_login(
        self,
        client: AsyncClient,
    ):
        """Invalid token should redirect to login with error code."""
        # Mock service to raise InvalidInvitationTokenError
        with patch(
            "pazpaz.api.auth.PlatformOnboardingService.accept_invitation"
        ) as mock_accept:
            mock_accept.side_effect = InvalidInvitationTokenError("Invalid token")

            response = await client.get(
                "/api/v1/auth/accept-invite",
                params={"token": "invalid_token"},
                follow_redirects=False,
            )

            assert response.status_code == 303
            assert response.headers["location"] == "/login?error=invalid_token"

    async def test_accept_invitation_expired_token_redirects_to_login(
        self,
        client: AsyncClient,
    ):
        """Expired token should redirect to login with error code."""
        # Mock service to raise ExpiredInvitationTokenError
        with patch(
            "pazpaz.api.auth.PlatformOnboardingService.accept_invitation"
        ) as mock_accept:
            mock_accept.side_effect = ExpiredInvitationTokenError("Token expired")

            response = await client.get(
                "/api/v1/auth/accept-invite",
                params={"token": "expired_token"},
                follow_redirects=False,
            )

            assert response.status_code == 303
            assert response.headers["location"] == "/login?error=expired_token"

    async def test_accept_invitation_already_accepted_redirects_to_login(
        self,
        client: AsyncClient,
    ):
        """Already accepted invitation should redirect to login with info."""
        # Mock service to raise InvitationAlreadyAcceptedError
        with patch(
            "pazpaz.api.auth.PlatformOnboardingService.accept_invitation"
        ) as mock_accept:
            mock_accept.side_effect = InvitationAlreadyAcceptedError("Already accepted")

            response = await client.get(
                "/api/v1/auth/accept-invite",
                params={"token": "already_accepted_token"},
                follow_redirects=False,
            )

            assert response.status_code == 303
            assert response.headers["location"] == "/login?error=already_accepted"

    async def test_accept_invitation_missing_token_returns_422(
        self,
        client: AsyncClient,
    ):
        """Missing token parameter should return 422 validation error."""
        response = await client.get(
            "/api/v1/auth/accept-invite",
            # No token parameter
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    async def test_accept_invitation_generic_error_redirects_to_login(
        self,
        client: AsyncClient,
    ):
        """Unexpected errors should redirect to login with generic error."""
        # Mock service to raise unexpected exception
        with patch(
            "pazpaz.api.auth.PlatformOnboardingService.accept_invitation"
        ) as mock_accept:
            mock_accept.side_effect = Exception("Unexpected database error")

            response = await client.get(
                "/api/v1/auth/accept-invite",
                params={"token": "some_token"},
                follow_redirects=False,
            )

            assert response.status_code == 303
            assert response.headers["location"] == "/login?error=unknown"


class TestAcceptInvitationSecurity:
    """Test security features of invitation acceptance."""

    async def test_accept_invitation_cookie_is_httponly(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """Access token cookie must have HttpOnly flag for XSS protection."""
        # Create inactive user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="security@example.com",
            full_name="Security Test",
            role=UserRole.OWNER,
            is_active=False,
        )
        db.add(user)
        await db.commit()

        # Mock the service
        with patch(
            "pazpaz.api.auth.PlatformOnboardingService.accept_invitation"
        ) as mock_accept:
            activated_user = User(
                id=user.id,
                workspace_id=user.workspace_id,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                is_active=True,
            )
            mock_accept.return_value = activated_user

            response = await client.get(
                "/api/v1/auth/accept-invite",
                params={"token": "valid_token"},
                follow_redirects=False,
            )

            assert response.status_code == 303

            # Check Set-Cookie headers
            set_cookie_headers = response.headers.get_list("set-cookie")
            access_token_cookie = [
                h for h in set_cookie_headers if "access_token=" in h
            ][0]

            assert "HttpOnly" in access_token_cookie
            assert "SameSite=lax" in access_token_cookie

    async def test_accept_invitation_cookie_is_secure_in_production(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """Cookie should have Secure flag in production mode."""
        # Create inactive user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="prod@example.com",
            full_name="Prod Test",
            role=UserRole.OWNER,
            is_active=False,
        )
        db.add(user)
        await db.commit()

        # Mock the service
        with patch(
            "pazpaz.api.auth.PlatformOnboardingService.accept_invitation"
        ) as mock_accept:
            activated_user = User(
                id=user.id,
                workspace_id=user.workspace_id,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                is_active=True,
            )
            mock_accept.return_value = activated_user

            # Temporarily set debug=False to simulate production
            original_debug = settings.debug
            try:
                settings.debug = False

                response = await client.get(
                    "/api/v1/auth/accept-invite",
                    params={"token": "valid_token"},
                    follow_redirects=False,
                )

                assert response.status_code == 303

                # Check Set-Cookie headers
                set_cookie_headers = response.headers.get_list("set-cookie")
                access_token_cookie = [
                    h for h in set_cookie_headers if "access_token=" in h
                ][0]

                assert "Secure" in access_token_cookie

            finally:
                settings.debug = original_debug

    async def test_accept_invitation_cookie_has_samesite(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """Cookie should have SameSite attribute for CSRF protection."""
        # Create inactive user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="samesite@example.com",
            full_name="SameSite Test",
            role=UserRole.OWNER,
            is_active=False,
        )
        db.add(user)
        await db.commit()

        # Mock the service
        with patch(
            "pazpaz.api.auth.PlatformOnboardingService.accept_invitation"
        ) as mock_accept:
            activated_user = User(
                id=user.id,
                workspace_id=user.workspace_id,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                is_active=True,
            )
            mock_accept.return_value = activated_user

            response = await client.get(
                "/api/v1/auth/accept-invite",
                params={"token": "valid_token"},
                follow_redirects=False,
            )

            assert response.status_code == 303

            # Check Set-Cookie headers
            set_cookie_headers = response.headers.get_list("set-cookie")
            access_token_cookie = [
                h for h in set_cookie_headers if "access_token=" in h
            ][0]

            assert "SameSite=lax" in access_token_cookie

    async def test_accept_invitation_no_token_in_error_message(
        self,
        client: AsyncClient,
    ):
        """Error messages should not leak token values."""
        # Mock service to raise error
        with patch(
            "pazpaz.api.auth.PlatformOnboardingService.accept_invitation"
        ) as mock_accept:
            mock_accept.side_effect = InvalidInvitationTokenError("Invalid token")

            sensitive_token = "very_sensitive_token_should_not_leak"
            response = await client.get(
                "/api/v1/auth/accept-invite",
                params={"token": sensitive_token},
                follow_redirects=False,
            )

            assert response.status_code == 303
            # Verify token is not in redirect URL
            location = response.headers["location"]
            assert sensitive_token not in location
            # Only generic error code should be present
            assert "error=invalid_token" in location

    async def test_accept_invitation_audit_logging(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """Successful invitation acceptance should create audit event."""
        # Create inactive user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="audit@example.com",
            full_name="Audit Test",
            role=UserRole.OWNER,
            is_active=False,
        )
        db.add(user)
        await db.commit()

        # Mock both service and audit service
        # Note: create_audit_event is imported inside the endpoint function
        with (
            patch(
                "pazpaz.api.auth.PlatformOnboardingService.accept_invitation"
            ) as mock_accept,
            patch("pazpaz.services.audit_service.create_audit_event") as mock_audit,
        ):
            activated_user = User(
                id=user.id,
                workspace_id=user.workspace_id,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                is_active=True,
            )
            mock_accept.return_value = activated_user

            response = await client.get(
                "/api/v1/auth/accept-invite",
                params={"token": "valid_token"},
                follow_redirects=False,
            )

            assert response.status_code == 303

            # Verify audit event was created
            mock_audit.assert_called_once()
            call_kwargs = mock_audit.call_args[1]
            assert call_kwargs["user_id"] == user.id
            assert call_kwargs["workspace_id"] == user.workspace_id
            assert call_kwargs["metadata"]["action"] == "invitation_accepted"
            assert call_kwargs["metadata"]["user_activated"] is True
            assert call_kwargs["metadata"]["jwt_issued"] is True
