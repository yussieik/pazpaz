"""
Test workspace status security enforcement in authentication.

CRITICAL SECURITY TEST: Verify that users from SUSPENDED or DELETED workspaces
cannot authenticate via any method (magic link, 2FA, invitation).

Security Requirements:
1. Magic link REQUEST must reject SUSPENDED/DELETED workspaces (no email sent)
2. Magic link VERIFICATION must reject SUSPENDED/DELETED workspaces (defense-in-depth)
3. 2FA verification must reject SUSPENDED/DELETED workspaces
4. Invitation acceptance must reject SUSPENDED/DELETED workspaces
5. get_current_user dependency must reject SUSPENDED/DELETED workspaces
6. Existing JWT sessions must be immediately invalidated when workspace is suspended

HIPAA Compliance:
- Immediate enforcement of workspace suspension (no grace period)
- Audit logging for all rejected authentication attempts
- Clear error messages for legitimate users
- UX improvement: Users don't receive magic links they can't use
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.security import create_access_token
from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace, WorkspaceStatus

pytestmark = pytest.mark.asyncio


class TestMagicLinkWorkspaceStatus:
    """Test workspace status validation in magic link authentication."""

    async def test_magic_link_rejects_suspended_workspace(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        redis_client,
    ):
        """Magic link REQUEST must reject SUSPENDED workspaces."""
        # Create a SUSPENDED workspace
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Suspended Workspace",
            status=WorkspaceStatus.SUSPENDED,
        )
        db_session.add(workspace)

        # Create active user in suspended workspace
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            email="suspended@example.com",
            full_name="Suspended User",
            role=UserRole.OWNER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        # Request magic link - should fail with 403 (workspace suspended)
        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": "suspended@example.com"},
        )

        # Should fail immediately at REQUEST stage (not verification)
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert "workspace has been suspended" in detail.lower()
        assert "contact support" in detail.lower()

        # Verify NO token was created in Redis (no email sent)
        keys = await redis_client.keys("magic_link:*")
        assert len(keys) == 0

    async def test_magic_link_rejects_deleted_workspace(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        redis_client,
    ):
        """Magic link REQUEST must reject DELETED workspaces."""
        # Create a DELETED workspace
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Deleted Workspace",
            status=WorkspaceStatus.DELETED,
            deleted_at=datetime.now(UTC),
        )
        db_session.add(workspace)

        # Create active user in deleted workspace
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            email="deleted@example.com",
            full_name="Deleted User",
            role=UserRole.OWNER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        # Request magic link - should fail with 403 (workspace deleted)
        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": "deleted@example.com"},
        )

        # Should fail immediately at REQUEST stage (not verification)
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert "workspace has been deleted" in detail.lower()
        assert "contact support" in detail.lower()

        # Verify NO token was created in Redis (no email sent)
        keys = await redis_client.keys("magic_link:*")
        assert len(keys) == 0

    async def test_magic_link_allows_active_workspace(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        redis_client,
    ):
        """Magic link verification must allow ACTIVE workspaces."""
        # Create an ACTIVE workspace (default)
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Active Workspace",
            status=WorkspaceStatus.ACTIVE,
        )
        db_session.add(workspace)

        # Create active user in active workspace
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            email="active@example.com",
            full_name="Active User",
            role=UserRole.OWNER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        # Request magic link
        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": "active@example.com"},
        )
        assert response.status_code == 200

        # Extract token from Redis
        keys = await redis_client.keys("magic_link:*")
        assert len(keys) == 1
        token_key = keys[0].decode() if isinstance(keys[0], bytes) else keys[0]
        token = token_key.replace("magic_link:", "")

        # Verify magic link - should succeed
        response = await client.post(
            "/api/v1/auth/verify",
            json={"token": token},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "active@example.com"

        # Verify JWT cookie was set
        assert "access_token" in response.cookies


class TestInvitationAcceptanceWorkspaceStatus:
    """Test workspace status validation in invitation acceptance."""

    async def test_invitation_rejects_suspended_workspace(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Invitation acceptance must reject SUSPENDED workspaces."""
        # Create a SUSPENDED workspace
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Suspended Invitation Workspace",
            status=WorkspaceStatus.SUSPENDED,
        )
        db_session.add(workspace)

        # Create invited user (is_active=False) in suspended workspace
        import hashlib

        invitation_token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(invitation_token.encode()).hexdigest()

        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            email="invited-suspended@example.com",
            full_name="Invited Suspended User",
            role=UserRole.OWNER,
            is_active=False,  # Not yet accepted
            invitation_token_hash=token_hash,
            invited_at=datetime.now(UTC),
        )
        db_session.add(user)
        await db_session.commit()

        # Accept invitation - should fail with 404 (generic error)
        response = await client.get(
            "/api/v1/auth/accept-invite",
            params={"token": invitation_token},
        )

        assert response.status_code == 404
        detail = response.json()["detail"]
        assert "invalid invitation token" in detail.lower()

    async def test_invitation_rejects_deleted_workspace(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Invitation acceptance must reject DELETED workspaces."""
        # Create a DELETED workspace
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Deleted Invitation Workspace",
            status=WorkspaceStatus.DELETED,
            deleted_at=datetime.now(UTC),
        )
        db_session.add(workspace)

        # Create invited user in deleted workspace
        import hashlib

        invitation_token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(invitation_token.encode()).hexdigest()

        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            email="invited-deleted@example.com",
            full_name="Invited Deleted User",
            role=UserRole.OWNER,
            is_active=False,
            invitation_token_hash=token_hash,
            invited_at=datetime.now(UTC),
        )
        db_session.add(user)
        await db_session.commit()

        # Accept invitation - should fail
        response = await client.get(
            "/api/v1/auth/accept-invite",
            params={"token": invitation_token},
        )

        assert response.status_code == 404
        detail = response.json()["detail"]
        assert "invalid invitation token" in detail.lower()

    async def test_invitation_allows_active_workspace(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        redis_client,
    ):
        """Invitation acceptance must allow ACTIVE workspaces."""
        # Create an ACTIVE workspace
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Active Invitation Workspace",
            status=WorkspaceStatus.ACTIVE,
        )
        db_session.add(workspace)

        # Create invited user in active workspace
        import hashlib

        invitation_token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(invitation_token.encode()).hexdigest()

        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            email="invited-active@example.com",
            full_name="Invited Active User",
            role=UserRole.OWNER,
            is_active=False,
            invitation_token_hash=token_hash,
            invited_at=datetime.now(UTC),
        )
        db_session.add(user)
        await db_session.commit()

        # Accept invitation - should succeed
        response = await client.get(
            "/api/v1/auth/accept-invite",
            params={"token": invitation_token},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "invitation accepted" in data["message"].lower()
        assert data["user"]["email"] == "invited-active@example.com"


class TestExistingSessionWorkspaceStatus:
    """
    Test that existing JWT sessions are immediately invalidated.

    Verifies that when a workspace is suspended, all existing sessions
    are immediately blocked.
    """

    async def test_existing_jwt_rejected_after_workspace_suspended(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """GET /auth/me must reject JWTs from SUSPENDED workspaces."""
        # Create an ACTIVE workspace with a user
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Soon-to-be-Suspended Workspace",
            status=WorkspaceStatus.ACTIVE,
        )
        db_session.add(workspace)

        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            email="session-test@example.com",
            full_name="Session Test User",
            role=UserRole.OWNER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        # Generate JWT for the user
        jwt_token = create_access_token(
            user_id=user.id,
            workspace_id=user.workspace_id,
            email=user.email,
        )

        # Set JWT cookie
        client.cookies.set("access_token", jwt_token)

        # Verify /auth/me works with ACTIVE workspace
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 200
        assert response.json()["email"] == "session-test@example.com"

        # NOW: Suspend the workspace
        workspace.status = WorkspaceStatus.SUSPENDED
        await db_session.commit()

        # Verify /auth/me now returns 403 (workspace suspended)
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert "workspace has been suspended" in detail.lower()

    async def test_existing_jwt_rejected_after_workspace_deleted(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """GET /auth/me must reject JWTs from DELETED workspaces."""
        # Create an ACTIVE workspace with a user
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Soon-to-be-Deleted Workspace",
            status=WorkspaceStatus.ACTIVE,
        )
        db_session.add(workspace)

        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            email="session-delete-test@example.com",
            full_name="Session Delete Test User",
            role=UserRole.OWNER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        # Generate JWT for the user
        jwt_token = create_access_token(
            user_id=user.id,
            workspace_id=user.workspace_id,
            email=user.email,
        )

        client.cookies.set("access_token", jwt_token)

        # Verify /auth/me works initially
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 200

        # Delete the workspace
        workspace.status = WorkspaceStatus.DELETED
        workspace.deleted_at = datetime.now(UTC)
        await db_session.commit()

        # Verify /auth/me now returns 403
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert "workspace has been deleted" in detail.lower()

    async def test_protected_endpoint_rejects_suspended_workspace(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """All protected endpoints must reject SUSPENDED workspaces."""
        # Create workspace and user
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Protected Endpoint Test Workspace",
            status=WorkspaceStatus.ACTIVE,
        )
        db_session.add(workspace)

        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            email="protected-test@example.com",
            full_name="Protected Test User",
            role=UserRole.OWNER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        # Generate JWT
        jwt_token = create_access_token(
            user_id=user.id,
            workspace_id=user.workspace_id,
            email=user.email,
        )

        client.cookies.set("access_token", jwt_token)

        # Test a few protected endpoints work with ACTIVE workspace
        response = await client.get("/api/v1/clients")
        assert response.status_code == 200

        # Suspend workspace
        workspace.status = WorkspaceStatus.SUSPENDED
        await db_session.commit()

        # All protected endpoints should now return 403
        response = await client.get("/api/v1/clients")
        assert response.status_code == 403
        assert "workspace has been suspended" in response.json()["detail"].lower()

        response = await client.get("/api/v1/appointments")
        assert response.status_code == 403

        response = await client.get("/api/v1/sessions")
        assert response.status_code == 403
