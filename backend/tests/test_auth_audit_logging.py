"""Test authentication audit logging for HIPAA compliance."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from pazpaz.models.audit_event import AuditAction, AuditEvent, ResourceType
from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace
from pazpaz.services.audit_service import UNAUTHENTICATED_WORKSPACE_ID
from tests.conftest import add_csrf_to_client

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def unauthenticated_workspace(db_session):
    """Create the sentinel workspace for unauthenticated audit events."""
    # Check if it already exists
    query = select(Workspace).where(Workspace.id == UNAUTHENTICATED_WORKSPACE_ID)
    result = await db_session.execute(query)
    existing = result.scalar_one_or_none()

    if not existing:
        workspace = Workspace(
            id=UNAUTHENTICATED_WORKSPACE_ID,
            name="Unauthenticated Events",
            is_active=False,  # Not a real workspace
        )
        db_session.add(workspace)
        await db_session.commit()
        await db_session.refresh(workspace)
        return workspace

    return existing


@pytest.fixture
async def clear_rate_limits(redis_client):
    """Clear all rate limit keys before each test."""
    # Clear all rate limit keys (global and auth-specific)
    keys = await redis_client.keys("rate_limit:*")
    if keys:
        await redis_client.delete(*keys)
    keys = await redis_client.keys("magic_link_rate_limit:*")
    if keys:
        await redis_client.delete(*keys)
    keys = await redis_client.keys("magic_link_rate_limit_email:*")
    if keys:
        await redis_client.delete(*keys)


class TestMagicLinkRequestAuditLogging:
    """Test audit logging for magic link requests."""

    async def test_magic_link_request_creates_audit_event_success(
        self,
        client: AsyncClient,
        db_session,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        unauthenticated_workspace,
        clear_rate_limits,
    ):
        """Verify successful magic link requests create audit events."""
        # Clear audit events
        await db_session.execute(delete(AuditEvent))
        await db_session.commit()

        # Request magic link
        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": test_user_ws1.email},
        )
        assert response.status_code == 200

        # Verify audit event created
        query = (
            select(AuditEvent)
            .where(AuditEvent.user_id == test_user_ws1.id)
            .where(AuditEvent.workspace_id == workspace_1.id)
        )
        result = await db_session.execute(query)
        audit_event = result.scalar_one_or_none()

        assert audit_event is not None
        assert audit_event.action == AuditAction.READ
        assert audit_event.resource_type == ResourceType.USER.value
        assert audit_event.resource_id == test_user_ws1.id
        assert audit_event.event_metadata["action"] == "magic_link_generated"
        assert "token_expiry_seconds" in audit_event.event_metadata
        assert audit_event.ip_address is not None

    async def test_magic_link_request_creates_audit_event_nonexistent_email(
        self,
        client: AsyncClient,
        db_session,
        redis_client,
        unauthenticated_workspace,
        clear_rate_limits,
    ):
        """Verify magic link requests for nonexistent emails create audit events."""
        nonexistent_email = "nonexistent@example.com"

        # Clear audit events
        await db_session.execute(delete(AuditEvent))
        await db_session.commit()

        # Request magic link with nonexistent email
        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": nonexistent_email},
        )
        assert response.status_code == 200  # Generic response

        # Verify audit event created (should use sentinel workspace)
        query = (
            select(AuditEvent)
            .where(AuditEvent.workspace_id == UNAUTHENTICATED_WORKSPACE_ID)
            .where(AuditEvent.user_id.is_(None))
        )
        result = await db_session.execute(query)
        audit_event = result.scalar_one_or_none()

        assert audit_event is not None
        assert audit_event.event_metadata["action"] == "magic_link_request_nonexistent_email"
        # Email is sanitized from metadata (PII)
        assert "email_provided" in audit_event.event_metadata
        assert audit_event.event_metadata["result"] == "user_not_found"

    async def test_magic_link_request_creates_audit_event_inactive_user(
        self,
        client: AsyncClient,
        db_session,
        workspace_1: Workspace,
        redis_client, clear_rate_limits,
        unauthenticated_workspace,
    ):
        """Verify magic link requests for inactive users create audit events."""
        # Create an inactive user
        inactive_user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="inactive@example.com",
            role=UserRole.THERAPIST,
            is_active=False,  # Inactive
        )
        db_session.add(inactive_user)
        await db_session.commit()

        # Clear audit events
        await db_session.execute(delete(AuditEvent))
        await db_session.commit()

        # Request magic link for inactive user
        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": inactive_user.email},
        )
        assert response.status_code == 200  # Generic response

        # Verify audit event created
        query = (
            select(AuditEvent)
            .where(AuditEvent.user_id == inactive_user.id)
            .where(AuditEvent.workspace_id == workspace_1.id)
        )
        result = await db_session.execute(query)
        audit_event = result.scalar_one_or_none()

        assert audit_event is not None
        assert audit_event.event_metadata["action"] == "magic_link_request_inactive_user"
        assert audit_event.event_metadata["result"] == "user_inactive"


class TestMagicLinkVerificationAuditLogging:
    """Test audit logging for magic link verification."""

    async def test_failed_token_verification_creates_audit_event(
        self,
        client: AsyncClient,
        db_session,
        redis_client,
        unauthenticated_workspace,
    ):
        """Verify failed magic link verification creates audit events."""
        # Clear audit events
        await db_session.execute(delete(AuditEvent))
        await db_session.commit()

        # Try to verify invalid token
        response = await client.post(
            "/api/v1/auth/verify",
            json={"token": "invalid_token_12345678901234567890"},
        )
        assert response.status_code in [400, 401]

        # Verify audit event created
        query = (
            select(AuditEvent)
            .where(AuditEvent.workspace_id == UNAUTHENTICATED_WORKSPACE_ID)
            .where(AuditEvent.user_id.is_(None))
        )
        result = await db_session.execute(query)
        audit_event = result.scalar_one_or_none()

        assert audit_event is not None
        assert audit_event.event_metadata["action"] == "magic_link_verification_failed"
        assert audit_event.event_metadata["reason"] == "token_not_found_or_expired"

    async def test_successful_authentication_creates_audit_event(
        self,
        client: AsyncClient,
        db_session,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client, clear_rate_limits,
        unauthenticated_workspace,
    ):
        """Verify successful authentication creates audit events."""
        # Request magic link first
        await client.post(
            "/api/v1/auth/magic-link",
            json={"email": test_user_ws1.email},
        )

        # Get the token from Redis (for testing purposes)
        # In production, this would come from the email
        keys = await redis_client.keys("magic_link:*")
        assert len(keys) > 0
        token = keys[0].decode().split(":")[-1]  # Extract token from key

        # Clear audit events
        await db_session.execute(delete(AuditEvent))
        await db_session.commit()

        # Verify token
        response = await client.post(
            "/api/v1/auth/verify",
            json={"token": token},
        )
        assert response.status_code == 200

        # Verify audit event created
        query = (
            select(AuditEvent)
            .where(AuditEvent.user_id == test_user_ws1.id)
            .where(AuditEvent.workspace_id == workspace_1.id)
        )
        result = await db_session.execute(query)
        audit_event = result.scalar_one_or_none()

        assert audit_event is not None
        assert audit_event.event_metadata["action"] == "user_authenticated"
        assert audit_event.event_metadata["authentication_method"] == "magic_link"
        assert audit_event.event_metadata["jwt_issued"] is True


class TestLogoutAuditLogging:
    """Test audit logging for logout."""

    async def test_logout_creates_audit_event(
        self,
        client: AsyncClient,
        db_session,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client, clear_rate_limits,
    ):
        """Verify logout creates audit events."""
        # Login user first
        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": test_user_ws1.email},
        )
        assert response.status_code == 200

        # Get the token from Redis
        keys = await redis_client.keys("magic_link:*")
        assert len(keys) > 0, "No magic link token found in Redis"
        token = keys[0].decode().split(":")[-1]

        # Verify token (login)
        response = await client.post(
            "/api/v1/auth/verify",
            json={"token": token},
        )
        assert response.status_code == 200

        # Clear audit events after login
        await db_session.execute(delete(AuditEvent))
        await db_session.commit()

        # Add CSRF token for logout
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )

        # Logout
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Verify audit event created
        query = (
            select(AuditEvent)
            .where(AuditEvent.user_id == test_user_ws1.id)
            .where(AuditEvent.workspace_id == workspace_1.id)
        )
        result = await db_session.execute(query)
        audit_event = result.scalar_one_or_none()

        assert audit_event is not None
        assert audit_event.action == AuditAction.UPDATE
        assert audit_event.event_metadata["action"] == "user_logged_out"
        assert audit_event.event_metadata["jwt_blacklisted"] is True


class TestAuthAuditEventsIncludeIPAddress:
    """Test that all auth audit events include IP address."""

    async def test_auth_audit_events_include_ip_address(
        self,
        client: AsyncClient,
        db_session,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client, clear_rate_limits,
        unauthenticated_workspace,
    ):
        """Verify audit events include client IP address."""
        # Clear audit events
        await db_session.execute(delete(AuditEvent))
        await db_session.commit()

        # Request magic link
        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": test_user_ws1.email},
        )
        assert response.status_code == 200

        # Verify audit event has IP address
        query = (
            select(AuditEvent)
            .where(AuditEvent.user_id == test_user_ws1.id)
            .where(AuditEvent.workspace_id == workspace_1.id)
        )
        result = await db_session.execute(query)
        audit_event = result.scalar_one_or_none()

        assert audit_event is not None
        assert audit_event.ip_address is not None
        # Test client IP is typically 127.0.0.1 or testclient
        assert audit_event.ip_address in ["127.0.0.1", "testclient"]
