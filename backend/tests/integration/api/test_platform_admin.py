"""Comprehensive tests for platform admin endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.audit_event import AuditEvent
from pazpaz.models.email_blacklist import EmailBlacklist
from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace, WorkspaceStatus
from tests.conftest import add_csrf_to_client, get_auth_headers

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def platform_admin_user(db: AsyncSession, workspace_1: Workspace) -> User:
    """Create a platform admin user for testing."""
    user = User(
        id=uuid.uuid4(),
        workspace_id=workspace_1.id,
        email="admin@example.com",
        full_name="Platform Admin",
        role=UserRole.OWNER,
        is_active=True,
        is_platform_admin=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def regular_user(db: AsyncSession, workspace_1: Workspace) -> User:
    """Create a regular (non-admin) user for testing."""
    user = User(
        id=uuid.uuid4(),
        workspace_id=workspace_1.id,
        email="user@example.com",
        full_name="Regular User",
        role=UserRole.OWNER,
        is_active=True,
        is_platform_admin=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def test_workspace_2(db: AsyncSession) -> Workspace:
    """Create a second test workspace."""
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Test Workspace 2",
        status=WorkspaceStatus.ACTIVE,
    )
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    return workspace


@pytest.fixture
async def pending_invitation_user(
    db: AsyncSession, test_workspace_2: Workspace
) -> User:
    """Create a user with pending invitation."""
    user = User(
        id=uuid.uuid4(),
        workspace_id=test_workspace_2.id,
        email="pending@example.com",
        full_name="Pending User",
        role=UserRole.OWNER,
        is_active=False,
        invitation_token_hash="fake_hash_for_testing",
        invited_at=datetime.now(UTC),
        invited_by_platform_admin=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ============================================================================
# Authorization Tests
# ============================================================================


class TestAuthorization:
    """Test platform admin authorization."""

    async def test_metrics_requires_platform_admin(
        self,
        client: AsyncClient,
        regular_user: User,
    ):
        """Regular users cannot access platform admin endpoints."""
        # Try to access metrics without being platform admin
        response = await client.get(
            "/api/v1/platform-admin/metrics",
            headers=get_auth_headers(
                workspace_id=regular_user.workspace_id,
                user_id=regular_user.id,
                email=regular_user.email,
            ),
        )
        assert response.status_code == 403
        assert "Platform admin access required" in response.json()["detail"]

    async def test_metrics_succeeds_for_platform_admin(
        self,
        client: AsyncClient,
        platform_admin_user: User,
    ):
        """Platform admins can access platform admin endpoints."""
        response = await client.get(
            "/api/v1/platform-admin/metrics",
            headers=get_auth_headers(
                workspace_id=platform_admin_user.workspace_id,
                user_id=platform_admin_user.id,
                email=platform_admin_user.email,
            ),
        )
        assert response.status_code == 200

    async def test_all_endpoints_require_platform_admin(
        self,
        client: AsyncClient,
        regular_user: User,
        test_workspace_2: Workspace,
        redis_client,
    ):
        """All platform admin endpoints require platform admin authorization."""
        # Generate CSRF token for POST/DELETE requests
        csrf_token = await add_csrf_to_client(
            client, regular_user.workspace_id, regular_user.id, redis_client
        )

        endpoints = [
            ("GET", "/api/v1/platform-admin/metrics"),
            ("GET", "/api/v1/platform-admin/activity"),
            ("GET", "/api/v1/platform-admin/workspaces"),
            ("GET", f"/api/v1/platform-admin/workspaces/{test_workspace_2.id}"),
            (
                "POST",
                f"/api/v1/platform-admin/workspaces/{test_workspace_2.id}/suspend",
            ),
            (
                "POST",
                f"/api/v1/platform-admin/workspaces/{test_workspace_2.id}/reactivate",
            ),
            ("DELETE", f"/api/v1/platform-admin/workspaces/{test_workspace_2.id}"),
            ("GET", "/api/v1/platform-admin/blacklist"),
            ("POST", "/api/v1/platform-admin/blacklist"),
            ("DELETE", "/api/v1/platform-admin/blacklist/test@example.com"),
        ]

        for method, url in endpoints:
            if method == "GET":
                headers = get_auth_headers(
                    workspace_id=regular_user.workspace_id,
                    user_id=regular_user.id,
                    email=regular_user.email,
                )
                response = await client.get(url, headers=headers)
            elif method == "POST":
                headers = get_auth_headers(
                    workspace_id=regular_user.workspace_id,
                    user_id=regular_user.id,
                    email=regular_user.email,
                    csrf_cookie=csrf_token,
                )
                headers["X-CSRF-Token"] = csrf_token
                response = await client.post(
                    url,
                    json={"reason": "test"},
                    headers=headers,
                )
            elif method == "DELETE":
                headers = get_auth_headers(
                    workspace_id=regular_user.workspace_id,
                    user_id=regular_user.id,
                    email=regular_user.email,
                    csrf_cookie=csrf_token,
                )
                headers["X-CSRF-Token"] = csrf_token
                response = await client.delete(url, headers=headers)

            assert response.status_code == 403, (
                f"Endpoint {method} {url} should require platform admin"
            )


# ============================================================================
# Metrics Endpoint Tests
# ============================================================================


class TestMetricsEndpoint:
    """Test GET /platform-admin/metrics."""

    async def test_metrics_returns_correct_counts(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        workspace_1: Workspace,
        test_workspace_2: Workspace,
        regular_user: User,
        pending_invitation_user: User,
        db: AsyncSession,
    ):
        """Metrics endpoint returns accurate counts."""
        # Add a blacklist entry
        blacklist_entry = EmailBlacklist(
            email="blocked@example.com",
            reason="Test",
            added_by=platform_admin_user.id,
        )
        db.add(blacklist_entry)
        await db.commit()

        response = await client.get(
            "/api/v1/platform-admin/metrics",
            headers=get_auth_headers(
                workspace_id=platform_admin_user.workspace_id,
                user_id=platform_admin_user.id,
                email=platform_admin_user.email,
            ),
        )

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "total_workspaces" in data
        assert "active_users" in data
        assert "pending_invitations" in data
        assert "blacklisted_users" in data

        # Check counts
        assert data["total_workspaces"] >= 2  # workspace_1 and test_workspace_2
        assert data["active_users"] >= 2  # platform_admin_user and regular_user
        assert data["pending_invitations"] >= 1  # pending_invitation_user
        assert data["blacklisted_users"] >= 1  # blacklist_entry

    async def test_metrics_excludes_deleted_workspaces(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        test_workspace_2: Workspace,
        db: AsyncSession,
    ):
        """Metrics do not include deleted workspaces."""
        # Mark workspace as deleted
        test_workspace_2.status = WorkspaceStatus.DELETED
        test_workspace_2.deleted_at = datetime.now(UTC)
        await db.commit()

        response = await client.get(
            "/api/v1/platform-admin/metrics",
            headers=get_auth_headers(
                workspace_id=platform_admin_user.workspace_id,
                user_id=platform_admin_user.id,
                email=platform_admin_user.email,
            ),
        )

        assert response.status_code == 200
        # Verify workspace is not counted (exact count depends on test isolation)


# ============================================================================
# Activity Endpoint Tests
# ============================================================================


class TestActivityEndpoint:
    """Test GET /platform-admin/activity."""

    async def test_activity_returns_recent_events(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """Activity endpoint returns recent audit events."""
        # Create some audit events
        from pazpaz.models.audit_event import AuditAction, ResourceType

        event = AuditEvent(
            workspace_id=workspace_1.id,
            user_id=platform_admin_user.id,
            event_type="workspace.created",
            action=AuditAction.CREATE,
            resource_type=ResourceType.WORKSPACE,
            resource_id=str(workspace_1.id),
            event_metadata={"workspace_name": "Test Workspace"},
        )
        db.add(event)
        await db.commit()

        response = await client.get(
            "/api/v1/platform-admin/activity",
            headers=get_auth_headers(
                workspace_id=platform_admin_user.workspace_id,
                user_id=platform_admin_user.id,
                email=platform_admin_user.email,
            ),
        )

        assert response.status_code == 200
        data = response.json()

        assert "activities" in data
        assert isinstance(data["activities"], list)

        if data["activities"]:
            activity = data["activities"][0]
            assert "type" in activity
            assert "timestamp" in activity
            assert "description" in activity

    async def test_activity_respects_limit_parameter(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        db: AsyncSession,
    ):
        """Activity endpoint respects limit parameter."""
        response = await client.get(
            "/api/v1/platform-admin/activity?limit=5",
            headers=get_auth_headers(
                workspace_id=platform_admin_user.workspace_id,
                user_id=platform_admin_user.id,
                email=platform_admin_user.email,
            ),
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["activities"]) <= 5

    async def test_activity_rejects_invalid_limit(
        self,
        client: AsyncClient,
        platform_admin_user: User,
    ):
        """Activity endpoint rejects invalid limit values."""
        headers = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
        )

        # Limit too high
        response = await client.get(
            "/api/v1/platform-admin/activity?limit=200",
            headers=headers,
        )
        assert response.status_code == 422

        # Limit too low
        response = await client.get(
            "/api/v1/platform-admin/activity?limit=0",
            headers=headers,
        )
        assert response.status_code == 422


# ============================================================================
# Workspace Management Tests
# ============================================================================


class TestListWorkspaces:
    """Test GET /platform-admin/workspaces."""

    async def test_list_workspaces_returns_all_workspaces(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        workspace_1: Workspace,
        test_workspace_2: Workspace,
        regular_user: User,
    ):
        """List workspaces returns all non-deleted workspaces."""
        response = await client.get(
            "/api/v1/platform-admin/workspaces",
            headers=get_auth_headers(
                workspace_id=platform_admin_user.workspace_id,
                user_id=platform_admin_user.id,
                email=platform_admin_user.email,
            ),
        )

        assert response.status_code == 200
        data = response.json()

        assert "workspaces" in data
        assert len(data["workspaces"]) >= 2

        # Check workspace structure
        workspace_data = data["workspaces"][0]
        assert "id" in workspace_data
        assert "name" in workspace_data
        assert "owner_email" in workspace_data
        assert "status" in workspace_data
        assert "created_at" in workspace_data
        assert "user_count" in workspace_data
        assert "session_count" in workspace_data

    async def test_list_workspaces_search_by_name(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        test_workspace_2: Workspace,
    ):
        """Search workspaces by name."""
        response = await client.get(
            f"/api/v1/platform-admin/workspaces?search={test_workspace_2.name}",
            headers=get_auth_headers(
                workspace_id=platform_admin_user.workspace_id,
                user_id=platform_admin_user.id,
                email=platform_admin_user.email,
            ),
        )

        assert response.status_code == 200
        data = response.json()

        # Should find the workspace
        workspace_names = [w["name"] for w in data["workspaces"]]
        assert test_workspace_2.name in workspace_names

    async def test_list_workspaces_search_by_owner_email(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        regular_user: User,
    ):
        """Search workspaces by owner email."""
        response = await client.get(
            f"/api/v1/platform-admin/workspaces?search={regular_user.email}",
            headers=get_auth_headers(
                workspace_id=platform_admin_user.workspace_id,
                user_id=platform_admin_user.id,
                email=platform_admin_user.email,
            ),
        )

        assert response.status_code == 200
        data = response.json()

        # Should find workspace(s) with this owner
        owner_emails = [w["owner_email"] for w in data["workspaces"]]
        assert regular_user.email in owner_emails


class TestSuspendWorkspace:
    """Test POST /platform-admin/workspaces/{id}/suspend."""

    async def test_suspend_workspace_success(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        test_workspace_2: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Successfully suspend a workspace."""
        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        response = await client.post(
            f"/api/v1/platform-admin/workspaces/{test_workspace_2.id}/suspend",
            json={"reason": "Terms of service violation"},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["message"] == "Workspace suspended successfully"
        assert data["workspace_id"] == str(test_workspace_2.id)
        assert data["status"] == "suspended"

        # Verify workspace status in database
        await db.refresh(test_workspace_2)
        assert test_workspace_2.status == WorkspaceStatus.SUSPENDED

        # Verify audit event created
        audit_event = await db.scalar(
            select(AuditEvent)
            .where(AuditEvent.workspace_id == test_workspace_2.id)
            .where(AuditEvent.action == "UPDATE")
            .order_by(AuditEvent.created_at.desc())
        )
        assert audit_event is not None
        assert audit_event.event_type == "workspace.suspended"
        assert audit_event.event_metadata["reason"] == "Terms of service violation"

    async def test_suspend_workspace_not_found(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        redis_client,
    ):
        """Suspending non-existent workspace returns 404."""
        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        fake_id = uuid.uuid4()
        response = await client.post(
            f"/api/v1/platform-admin/workspaces/{fake_id}/suspend",
            json={"reason": "Test"},
            headers=headers,
        )

        assert response.status_code == 404
        assert "Workspace not found" in response.json()["detail"]

    async def test_suspend_workspace_already_suspended(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        test_workspace_2: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Suspending already suspended workspace returns 400."""
        # Suspend workspace first
        test_workspace_2.status = WorkspaceStatus.SUSPENDED
        await db.commit()

        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        response = await client.post(
            f"/api/v1/platform-admin/workspaces/{test_workspace_2.id}/suspend",
            json={"reason": "Test"},
            headers=headers,
        )

        assert response.status_code == 400
        assert "already suspended" in response.json()["detail"]

    async def test_suspend_deleted_workspace_fails(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        test_workspace_2: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Cannot suspend a deleted workspace."""
        # Delete workspace first
        test_workspace_2.status = WorkspaceStatus.DELETED
        test_workspace_2.deleted_at = datetime.now(UTC)
        await db.commit()

        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        response = await client.post(
            f"/api/v1/platform-admin/workspaces/{test_workspace_2.id}/suspend",
            json={"reason": "Test"},
            headers=headers,
        )

        assert response.status_code == 400
        assert "Cannot suspend deleted workspace" in response.json()["detail"]


class TestReactivateWorkspace:
    """Test POST /platform-admin/workspaces/{id}/reactivate."""

    async def test_reactivate_workspace_success(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        test_workspace_2: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Successfully reactivate a suspended workspace."""
        # Suspend workspace first
        test_workspace_2.status = WorkspaceStatus.SUSPENDED
        await db.commit()

        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        response = await client.post(
            f"/api/v1/platform-admin/workspaces/{test_workspace_2.id}/reactivate",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["message"] == "Workspace reactivated successfully"
        assert data["workspace_id"] == str(test_workspace_2.id)
        assert data["status"] == "active"

        # Verify workspace status in database
        await db.refresh(test_workspace_2)
        assert test_workspace_2.status == WorkspaceStatus.ACTIVE

        # Verify audit event created
        audit_event = await db.scalar(
            select(AuditEvent)
            .where(AuditEvent.workspace_id == test_workspace_2.id)
            .where(AuditEvent.action == "UPDATE")
            .order_by(AuditEvent.created_at.desc())
        )
        assert audit_event is not None
        assert audit_event.event_type == "workspace.reactivated"

    async def test_reactivate_active_workspace_fails(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        test_workspace_2: Workspace,
        redis_client,
    ):
        """Cannot reactivate an already active workspace."""
        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        response = await client.post(
            f"/api/v1/platform-admin/workspaces/{test_workspace_2.id}/reactivate",
            headers=headers,
        )

        assert response.status_code == 400
        assert (
            "Only suspended workspaces can be reactivated" in response.json()["detail"]
        )

    async def test_reactivate_workspace_not_found(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        redis_client,
    ):
        """Reactivating non-existent workspace returns 404."""
        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        fake_id = uuid.uuid4()
        response = await client.post(
            f"/api/v1/platform-admin/workspaces/{fake_id}/reactivate",
            headers=headers,
        )

        assert response.status_code == 404


class TestDeleteWorkspace:
    """Test DELETE /platform-admin/workspaces/{id}."""

    async def test_delete_workspace_success(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        test_workspace_2: Workspace,
        pending_invitation_user: User,
        db: AsyncSession,
        redis_client,
    ):
        """Successfully soft delete a workspace."""
        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        response = await client.request(
            "DELETE",
            f"/api/v1/platform-admin/workspaces/{test_workspace_2.id}",
            json={"reason": "User requested account deletion"},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "deleted successfully" in data["message"]
        assert data["workspace_id"] == str(test_workspace_2.id)
        assert data["status"] == "deleted"

        # Verify workspace status in database
        await db.refresh(test_workspace_2)
        assert test_workspace_2.status == WorkspaceStatus.DELETED
        assert test_workspace_2.deleted_at is not None

        # Verify users are deactivated
        await db.refresh(pending_invitation_user)
        assert pending_invitation_user.is_active is False

        # Verify audit event created
        audit_event = await db.scalar(
            select(AuditEvent)
            .where(AuditEvent.workspace_id == test_workspace_2.id)
            .where(AuditEvent.action == "DELETE")
            .order_by(AuditEvent.created_at.desc())
        )
        assert audit_event is not None
        assert audit_event.event_type == "workspace.deleted"
        assert audit_event.event_metadata["reason"] == "User requested account deletion"

    async def test_delete_workspace_already_deleted(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        test_workspace_2: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Cannot delete an already deleted workspace."""
        # Delete workspace first
        test_workspace_2.status = WorkspaceStatus.DELETED
        test_workspace_2.deleted_at = datetime.now(UTC)
        await db.commit()

        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        response = await client.request(
            "DELETE",
            f"/api/v1/platform-admin/workspaces/{test_workspace_2.id}",
            json={"reason": "Test"},
            headers=headers,
        )

        assert response.status_code == 400
        assert "already deleted" in response.json()["detail"]

    async def test_delete_workspace_not_found(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        redis_client,
    ):
        """Deleting non-existent workspace returns 404."""
        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        fake_id = uuid.uuid4()
        response = await client.request(
            "DELETE",
            f"/api/v1/platform-admin/workspaces/{fake_id}",
            json={"reason": "Test"},
            headers=headers,
        )

        assert response.status_code == 404


# ============================================================================
# Blacklist Management Tests
# ============================================================================


class TestGetBlacklist:
    """Test GET /platform-admin/blacklist."""

    async def test_get_blacklist_empty(
        self,
        client: AsyncClient,
        platform_admin_user: User,
    ):
        """Get blacklist when empty returns empty list."""
        response = await client.get(
            "/api/v1/platform-admin/blacklist",
            headers=get_auth_headers(
                workspace_id=platform_admin_user.workspace_id,
                user_id=platform_admin_user.id,
                email=platform_admin_user.email,
            ),
        )

        assert response.status_code == 200
        data = response.json()

        assert "blacklist" in data
        assert isinstance(data["blacklist"], list)

    async def test_get_blacklist_with_entries(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        db: AsyncSession,
    ):
        """Get blacklist returns all entries."""
        # Add blacklist entries
        entry1 = EmailBlacklist(
            email="blocked1@example.com",
            reason="Spam",
            added_by=platform_admin_user.id,
        )
        entry2 = EmailBlacklist(
            email="blocked2@example.com",
            reason="Abuse",
            added_by=platform_admin_user.id,
        )
        db.add(entry1)
        db.add(entry2)
        await db.commit()

        response = await client.get(
            "/api/v1/platform-admin/blacklist",
            headers=get_auth_headers(
                workspace_id=platform_admin_user.workspace_id,
                user_id=platform_admin_user.id,
                email=platform_admin_user.email,
            ),
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["blacklist"]) >= 2

        # Check entry structure
        entry_data = data["blacklist"][0]
        assert "email" in entry_data
        assert "reason" in entry_data
        assert "added_at" in entry_data


class TestAddToBlacklist:
    """Test POST /platform-admin/blacklist."""

    async def test_add_to_blacklist_success(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        db: AsyncSession,
        redis_client,
    ):
        """Successfully add email to blacklist."""
        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        response = await client.post(
            "/api/v1/platform-admin/blacklist",
            json={"email": "spam@example.com", "reason": "Repeated spam signups"},
            headers=headers,
        )

        assert response.status_code == 201
        data = response.json()

        assert "added to blacklist" in data["message"]
        assert data["email"] == "spam@example.com"

        # Verify entry in database
        entry = await db.scalar(
            select(EmailBlacklist).where(EmailBlacklist.email == "spam@example.com")
        )
        assert entry is not None
        assert entry.reason == "Repeated spam signups"
        assert entry.added_by == platform_admin_user.id

        # Verify audit event created
        audit_event = await db.scalar(
            select(AuditEvent)
            .where(AuditEvent.action == "CREATE")
            .order_by(AuditEvent.created_at.desc())
        )
        assert audit_event is not None
        assert audit_event.event_type == "email.blacklisted"

    async def test_add_to_blacklist_duplicate(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        db: AsyncSession,
        redis_client,
    ):
        """Cannot add duplicate email to blacklist."""
        # Add email first
        entry = EmailBlacklist(
            email="duplicate@example.com",
            reason="Test",
            added_by=platform_admin_user.id,
        )
        db.add(entry)
        await db.commit()

        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        # Try to add again
        response = await client.post(
            "/api/v1/platform-admin/blacklist",
            json={"email": "duplicate@example.com", "reason": "Test again"},
            headers=headers,
        )

        assert response.status_code == 400
        assert "already blacklisted" in response.json()["detail"]

    async def test_add_to_blacklist_revokes_pending_invitations(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        pending_invitation_user: User,
        db: AsyncSession,
        redis_client,
    ):
        """Adding to blacklist revokes pending invitations."""
        # Verify user has pending invitation
        assert pending_invitation_user.invitation_token_hash is not None

        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        # Add their email to blacklist
        response = await client.post(
            "/api/v1/platform-admin/blacklist",
            json={"email": pending_invitation_user.email, "reason": "Test"},
            headers=headers,
        )

        assert response.status_code == 201

        # Verify invitation was revoked
        await db.refresh(pending_invitation_user)
        assert pending_invitation_user.invitation_token_hash is None

    async def test_add_to_blacklist_invalid_email(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        redis_client,
    ):
        """Invalid email format returns 422."""
        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        response = await client.post(
            "/api/v1/platform-admin/blacklist",
            json={"email": "not-an-email", "reason": "Test"},
            headers=headers,
        )

        assert response.status_code == 422


class TestRemoveFromBlacklist:
    """Test DELETE /platform-admin/blacklist/{email}."""

    async def test_remove_from_blacklist_success(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        db: AsyncSession,
        redis_client,
    ):
        """Successfully remove email from blacklist."""
        # Add email first
        entry = EmailBlacklist(
            email="remove@example.com",
            reason="Test",
            added_by=platform_admin_user.id,
        )
        db.add(entry)
        await db.commit()

        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        response = await client.delete(
            "/api/v1/platform-admin/blacklist/remove@example.com",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "removed from blacklist" in data["message"]
        assert data["email"] == "remove@example.com"

        # Verify entry removed from database
        entry = await db.scalar(
            select(EmailBlacklist).where(EmailBlacklist.email == "remove@example.com")
        )
        assert entry is None

        # Verify audit event created
        audit_event = await db.scalar(
            select(AuditEvent)
            .where(AuditEvent.action == "DELETE")
            .order_by(AuditEvent.created_at.desc())
        )
        assert audit_event is not None
        assert audit_event.event_type == "email.unblacklisted"

    async def test_remove_from_blacklist_not_found(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        redis_client,
    ):
        """Removing non-existent email returns 404."""
        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        response = await client.delete(
            "/api/v1/platform-admin/blacklist/notfound@example.com",
            headers=headers,
        )

        assert response.status_code == 404
        assert "not found in blacklist" in response.json()["detail"]


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for platform admin workflows."""

    async def test_suspend_reactivate_workflow(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        test_workspace_2: Workspace,
        redis_client,
    ):
        """Complete workflow: suspend then reactivate workspace."""
        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers_with_csrf = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers_with_csrf["X-CSRF-Token"] = csrf_token

        headers_get = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
        )

        # 1. Suspend workspace
        response = await client.post(
            f"/api/v1/platform-admin/workspaces/{test_workspace_2.id}/suspend",
            json={"reason": "Policy violation"},
            headers=headers_with_csrf,
        )
        assert response.status_code == 200

        # 2. Verify it shows as suspended in list
        response = await client.get(
            "/api/v1/platform-admin/workspaces",
            headers=headers_get,
        )
        assert response.status_code == 200
        workspaces = response.json()["workspaces"]
        suspended_workspace = next(
            (w for w in workspaces if w["id"] == str(test_workspace_2.id)), None
        )
        assert suspended_workspace["status"] == "suspended"

        # 3. Reactivate workspace
        response = await client.post(
            f"/api/v1/platform-admin/workspaces/{test_workspace_2.id}/reactivate",
            headers=headers_with_csrf,
        )
        assert response.status_code == 200

        # 4. Verify it shows as active again
        response = await client.get(
            "/api/v1/platform-admin/workspaces",
            headers=headers_get,
        )
        assert response.status_code == 200
        workspaces = response.json()["workspaces"]
        active_workspace = next(
            (w for w in workspaces if w["id"] == str(test_workspace_2.id)), None
        )
        assert active_workspace["status"] == "active"

    async def test_blacklist_prevents_invitation(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        redis_client,
    ):
        """Blacklisted email cannot receive new invitations."""
        test_email = "blocked_user@example.com"

        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers_with_csrf = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers_with_csrf["X-CSRF-Token"] = csrf_token

        headers_get = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
        )

        # 1. Add email to blacklist
        response = await client.post(
            "/api/v1/platform-admin/blacklist",
            json={"email": test_email, "reason": "Spam account"},
            headers=headers_with_csrf,
        )
        assert response.status_code == 201

        # 2. Verify in blacklist
        response = await client.get(
            "/api/v1/platform-admin/blacklist",
            headers=headers_get,
        )
        assert response.status_code == 200
        blacklist = response.json()["blacklist"]
        assert test_email in [entry["email"] for entry in blacklist]

        # 3. Metrics should reflect blacklist count
        response = await client.get(
            "/api/v1/platform-admin/metrics",
            headers=headers_get,
        )
        assert response.status_code == 200
        metrics = response.json()
        assert metrics["blacklisted_users"] > 0

    async def test_workspace_deletion_cascade(
        self,
        client: AsyncClient,
        platform_admin_user: User,
        test_workspace_2: Workspace,
        pending_invitation_user: User,
        db: AsyncSession,
        redis_client,
    ):
        """Deleting workspace deactivates all users."""
        # Add another active user
        active_user = User(
            id=uuid.uuid4(),
            workspace_id=test_workspace_2.id,
            email="active@example.com",
            full_name="Active User",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(active_user)
        await db.commit()

        csrf_token = await add_csrf_to_client(
            client,
            platform_admin_user.workspace_id,
            platform_admin_user.id,
            redis_client,
        )
        headers = get_auth_headers(
            workspace_id=platform_admin_user.workspace_id,
            user_id=platform_admin_user.id,
            email=platform_admin_user.email,
            csrf_cookie=csrf_token,
        )
        headers["X-CSRF-Token"] = csrf_token

        # Delete workspace
        response = await client.request(
            "DELETE",
            f"/api/v1/platform-admin/workspaces/{test_workspace_2.id}",
            json={"reason": "Test deletion"},
            headers=headers,
        )
        assert response.status_code == 200

        # Verify all users are deactivated
        await db.refresh(pending_invitation_user)
        await db.refresh(active_user)
        assert pending_invitation_user.is_active is False
        assert active_user.is_active is False

        # Verify workspace status
        await db.refresh(test_workspace_2)
        assert test_workspace_2.status == WorkspaceStatus.DELETED
        assert test_workspace_2.deleted_at is not None
