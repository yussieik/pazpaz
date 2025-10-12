"""Test authentication requirements for all API endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from pazpaz.models.user import User
from pazpaz.models.workspace import Workspace
from tests.conftest import get_auth_headers

pytestmark = pytest.mark.asyncio


class TestAuthenticationRequired:
    """Test that all endpoints require authentication."""

    async def test_missing_workspace_header_returns_401_clients_list(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """List clients without X-Workspace-ID header should return 401."""
        response = await client.get("/api/v1/clients")
        assert response.status_code == 401
        assert "authentication required" in response.json()["detail"].lower()

    async def test_missing_workspace_header_returns_401_clients_get(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """Get client without X-Workspace-ID header should return 401."""
        client_id = uuid.uuid4()
        response = await client.get(f"/api/v1/clients/{client_id}")
        assert response.status_code == 401
        assert "authentication required" in response.json()["detail"].lower()

    async def test_missing_workspace_header_returns_401_clients_create(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """Create client without X-Workspace-ID header should return 401."""
        # Add CSRF token (required for POST requests)
        csrf_token = "test-csrf-token"
        client.cookies.set("csrf_token", csrf_token)

        response = await client.post(
            "/api/v1/clients",
            json={
                "first_name": "Test",
                "last_name": "User",
                "consent_status": True,
            },
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 401
        assert "authentication required" in response.json()["detail"].lower()

    async def test_missing_workspace_header_returns_401_clients_update(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """Update client without X-Workspace-ID header should return 401."""
        # Add CSRF token (required for PUT requests)
        csrf_token = "test-csrf-token-update"
        client.cookies.set("csrf_token", csrf_token)

        client_id = uuid.uuid4()
        response = await client.put(
            f"/api/v1/clients/{client_id}",
            json={"first_name": "Updated"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 401
        assert "authentication required" in response.json()["detail"].lower()

    async def test_missing_workspace_header_returns_401_clients_delete(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """Delete client without X-Workspace-ID header should return 401."""
        # Add CSRF token (required for DELETE requests)
        csrf_token = "test-csrf-token-delete"
        client.cookies.set("csrf_token", csrf_token)

        client_id = uuid.uuid4()
        response = await client.delete(
            f"/api/v1/clients/{client_id}",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 401
        assert "authentication required" in response.json()["detail"].lower()

    async def test_missing_workspace_header_returns_401_appointments_list(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """List appointments without X-Workspace-ID header should return 401."""
        response = await client.get("/api/v1/appointments")
        assert response.status_code == 401
        assert "authentication required" in response.json()["detail"].lower()

    async def test_missing_workspace_header_returns_401_appointments_create(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """Create appointment without X-Workspace-ID header should return 401."""
        # Add CSRF token (required for POST requests)
        csrf_token = "test-csrf-token-appt"
        client.cookies.set("csrf_token", csrf_token)

        response = await client.post(
            "/api/v1/appointments",
            json={
                "client_id": str(uuid.uuid4()),
                "scheduled_start": "2025-10-01T10:00:00Z",
                "scheduled_end": "2025-10-01T11:00:00Z",
                "location_type": "clinic",
            },
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 401
        assert "authentication required" in response.json()["detail"].lower()

    async def test_missing_workspace_header_returns_401_conflicts_check(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """Check conflicts without X-Workspace-ID header should return 401."""
        response = await client.get(
            "/api/v1/appointments/conflicts",
            params={
                "scheduled_start": "2025-10-01T10:00:00Z",
                "scheduled_end": "2025-10-01T11:00:00Z",
            },
        )
        assert response.status_code == 401
        assert "authentication required" in response.json()["detail"].lower()


class TestInvalidWorkspaceID:
    """Test that invalid workspace IDs are rejected."""

    async def test_invalid_workspace_uuid_returns_401(
        self, client: AsyncClient, workspace_1: Workspace, test_user_ws1: User
    ):
        """Invalid UUID format should return 401."""
        response = await client.get(
            "/api/v1/clients",
            headers={"X-Workspace-ID": "not-a-uuid"},
        )
        assert response.status_code == 401
        assert "authentication required" in response.json()["detail"].lower()

    async def test_empty_workspace_header_returns_401(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """Empty workspace header should return 401."""
        response = await client.get(
            "/api/v1/clients",
            headers={"X-Workspace-ID": ""},
        )
        assert response.status_code == 401
        assert "authentication required" in response.json()["detail"].lower()

    async def test_malformed_uuid_returns_401(
        self, client: AsyncClient, workspace_1: Workspace, test_user_ws1: User
    ):
        """Malformed UUID should return 401."""
        response = await client.get(
            "/api/v1/clients",
            headers={"X-Workspace-ID": "12345"},
        )
        assert response.status_code == 401
        assert "authentication required" in response.json()["detail"].lower()


class TestValidAuthentication:
    """Test that valid authentication works correctly."""

    async def test_valid_workspace_id_allows_access(
        self, client: AsyncClient, workspace_1: Workspace, test_user_ws1: User
    ):
        """Valid workspace ID should allow access to endpoints."""
        headers = get_auth_headers(workspace_1.id)
        response = await client.get("/api/v1/clients", headers=headers)
        # Should return 200 with empty list, not 401
        assert response.status_code == 200
        assert "items" in response.json()

    async def test_nonexistent_workspace_id_format_valid(
        self, client: AsyncClient, db_session
    ):
        """
        Non-existent but valid UUID should authenticate but return no data.

        This tests that authentication only validates format, not existence.
        The workspace validation happens at the data access layer.
        """
        # Create a workspace and user for testing, but use a different workspace ID in the JWT
        from pazpaz.models.user import User, UserRole
        from pazpaz.models.workspace import Workspace

        nonexistent_workspace_id = uuid.UUID("99999999-9999-9999-9999-999999999999")
        nonexistent_user_id = uuid.UUID("99999999-9999-9999-9999-999999999991")

        # Create workspace and user with nonexistent IDs
        ws = Workspace(id=nonexistent_workspace_id, name="Nonexistent Workspace")
        db_session.add(ws)
        await db_session.commit()

        user = User(
            id=nonexistent_user_id,
            workspace_id=nonexistent_workspace_id,
            email="nonexistent@example.com",
            full_name="Nonexistent User",
            role=UserRole.OWNER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        headers = get_auth_headers(
            nonexistent_workspace_id, nonexistent_user_id, "nonexistent@example.com"
        )

        response = await client.get("/api/v1/clients", headers=headers)

        # Should return 200 with empty list (workspace doesn't have clients)
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
