"""
CRITICAL: Workspace isolation security tests.

These tests verify that data from one workspace cannot be accessed,
modified, or deleted by requests authenticated with a different workspace ID.

This is the #1 security requirement for a healthcare application - PII/PHI
must never leak between workspaces.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from pazpaz.models.appointment import Appointment
from pazpaz.models.client import Client
from pazpaz.models.user import User
from pazpaz.models.workspace import Workspace
from tests.conftest import add_csrf_to_client, get_auth_headers

pytestmark = pytest.mark.asyncio


class TestUnauthenticatedRequestRejection:
    """
    CRITICAL SECURITY: Test that unauthenticated requests are rejected.

    These tests verify the fix for CVE-2025-XXXX (CVSS 9.1) - workspace isolation bypass.
    Previously, endpoints accepted X-Workspace-ID headers without JWT validation.
    Now all endpoints require valid JWT authentication via get_current_user().
    """

    async def test_cannot_list_clients_without_jwt(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Verify GET /clients requires JWT authentication, ignores X-Workspace-ID header."""
        # Try to access clients with ONLY X-Workspace-ID header (no JWT cookie)
        response = await client.get(
            "/api/v1/clients",
            headers={"X-Workspace-ID": str(workspace_1.id)},
        )

        # Must return 401 Unauthorized (no JWT = no authentication)
        assert response.status_code == 401
        assert "authentication" in response.json()["detail"].lower()

    async def test_cannot_get_client_without_jwt(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        sample_client_ws1: Client,
    ):
        """Verify GET /clients/{id} requires JWT authentication."""
        # Try to access client with ONLY X-Workspace-ID header (no JWT cookie)
        response = await client.get(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers={"X-Workspace-ID": str(workspace_1.id)},
        )

        # Must return 401 Unauthorized
        assert response.status_code == 401
        assert "authentication" in response.json()["detail"].lower()

    async def test_cannot_list_appointments_without_jwt(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Verify GET /appointments requires JWT authentication."""
        # Try to access appointments with ONLY X-Workspace-ID header (no JWT cookie)
        response = await client.get(
            "/api/v1/appointments",
            headers={"X-Workspace-ID": str(workspace_1.id)},
        )

        # Must return 401 Unauthorized
        assert response.status_code == 401
        assert "authentication" in response.json()["detail"].lower()

    async def test_cannot_check_conflicts_without_jwt(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Verify GET /appointments/conflicts requires JWT authentication."""
        tomorrow = datetime.now(UTC).replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        # Try to check conflicts with ONLY X-Workspace-ID header (no JWT cookie)
        response = await client.get(
            "/api/v1/appointments/conflicts",
            headers={"X-Workspace-ID": str(workspace_1.id)},
            params={
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow + timedelta(hours=1)).isoformat(),
            },
        )

        # Must return 401 Unauthorized
        assert response.status_code == 401
        assert "authentication" in response.json()["detail"].lower()

    async def test_workspace_id_header_ignored_with_valid_jwt(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        workspace_2: Workspace,
        test_user_ws1: User,
        test_user_ws2: User,
        sample_client_ws1: Client,
        sample_client_ws2: Client,
    ):
        """
        CRITICAL: Verify workspace_id comes from JWT, not X-Workspace-ID header.

        Even if a user sends a different workspace UUID in the header,
        the server must use the workspace_id from the JWT token.
        """
        # Authenticate as workspace 1 user (JWT cookie)
        headers_ws1 = get_auth_headers(workspace_1.id, test_user_ws1.id, test_user_ws1.email)

        # But send workspace 2's ID in the X-Workspace-ID header (attack attempt)
        headers_ws1["X-Workspace-ID"] = str(workspace_2.id)

        # List clients - should return workspace 1's clients (from JWT), not workspace 2
        response = await client.get("/api/v1/clients", headers=headers_ws1)

        assert response.status_code == 200
        data = response.json()

        # Verify we got workspace 1's client, NOT workspace 2's
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(sample_client_ws1.id)
        assert data["items"][0]["first_name"] == "John"  # Workspace 1's client

        # Verify we did NOT get workspace 2's client
        client_ids = [item["id"] for item in data["items"]]
        assert str(sample_client_ws2.id) not in client_ids


class TestClientWorkspaceIsolation:
    """Test that clients are isolated between workspaces."""

    async def test_cannot_access_client_from_different_workspace(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        workspace_2: Workspace,
        test_user_ws1: User,
        test_user_ws2: User,
        sample_client_ws1: Client,
    ):
        """
        SECURITY CRITICAL: Cannot access client from different workspace.

        Create client in workspace 1, try to access with workspace 2 header.
        Must return 404 (not 403) to avoid information leakage.
        """
        # Try to access workspace 1's client with workspace 2 credentials
        headers = get_auth_headers(workspace_2.id, test_user_ws2.id, test_user_ws2.email)
        response = await client.get(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
        )

        # Must return 404, not 403, to avoid leaking existence of resource
        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"

    async def test_cannot_list_clients_from_different_workspace(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        workspace_2: Workspace,
        test_user_ws2: User,
        sample_client_ws1: Client,
        sample_client_ws2: Client,
    ):
        """
        SECURITY CRITICAL: List only returns clients from own workspace.

        Create clients in both workspaces, verify each workspace only sees
        their own clients.
        """
        # List clients in workspace 1 - should see only workspace 1's client
        headers_ws1 = get_auth_headers(workspace_1.id, test_user_ws1.id, test_user_ws1.email)
        response_ws1 = await client.get("/api/v1/clients", headers=headers_ws1)

        assert response_ws1.status_code == 200
        data_ws1 = response_ws1.json()
        assert data_ws1["total"] == 1
        assert len(data_ws1["items"]) == 1
        assert data_ws1["items"][0]["id"] == str(sample_client_ws1.id)
        assert data_ws1["items"][0]["first_name"] == "John"

        # List clients in workspace 2 - should see only workspace 2's client
        headers_ws2 = get_auth_headers(workspace_2.id, test_user_ws2.id, test_user_ws2.email)
        response_ws2 = await client.get("/api/v1/clients", headers=headers_ws2)

        assert response_ws2.status_code == 200
        data_ws2 = response_ws2.json()
        assert data_ws2["total"] == 1
        assert len(data_ws2["items"]) == 1
        assert data_ws2["items"][0]["id"] == str(sample_client_ws2.id)
        assert data_ws2["items"][0]["first_name"] == "Jane"

    async def test_cannot_update_client_from_different_workspace(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        workspace_2: Workspace,
        sample_client_ws1: Client,
        test_user_ws2: User,
        redis_client,
    ):
        """
        SECURITY CRITICAL: Cannot update client from different workspace.

        Create client in workspace 1, try to update with workspace 2 header.
        Must return 404.
        """
        # Add CSRF token for workspace 2
        csrf_token = await add_csrf_to_client(
            client, workspace_2.id, test_user_ws2.id, redis_client
        )

        # Try to update workspace 1's client with workspace 2 credentials
        # Set JWT cookie on client
        from pazpaz.core.security import create_access_token
        jwt_token = create_access_token(
            user_id=test_user_ws2.id,
            workspace_id=workspace_2.id,
            email=test_user_ws2.email,
        )
        client.cookies.set("access_token", jwt_token)
        headers = get_auth_headers(workspace_2.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
        response = await client.put(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
            json={"first_name": "Hacked"},
        )

        # Must return 404
        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"

        # Verify client was not modified
        headers_ws1 = get_auth_headers(workspace_1.id, test_user_ws1.id, test_user_ws1.email)
        verify_response = await client.get(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers_ws1,
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["first_name"] == "John"  # Unchanged

    async def test_cannot_delete_client_from_different_workspace(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        workspace_2: Workspace,
        sample_client_ws1: Client,
        test_user_ws2: User,
        redis_client,
    ):
        """
        SECURITY CRITICAL: Cannot delete client from different workspace.

        Create client in workspace 1, try to delete with workspace 2 header.
        Must return 404 and not delete.
        """
        # Add CSRF token for workspace 2
        csrf_token = await add_csrf_to_client(
            client, workspace_2.id, test_user_ws2.id, redis_client
        )

        # Try to delete workspace 1's client with workspace 2 credentials
        # Set JWT cookie on client
        from pazpaz.core.security import create_access_token
        jwt_token = create_access_token(
            user_id=test_user_ws2.id,
            workspace_id=workspace_2.id,
            email=test_user_ws2.email,
        )
        client.cookies.set("access_token", jwt_token)
        headers = get_auth_headers(workspace_2.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
        response = await client.delete(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
        )

        # Must return 404
        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"

        # Verify client still exists
        headers_ws1 = get_auth_headers(workspace_1.id, test_user_ws1.id, test_user_ws1.email)
        verify_response = await client.get(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers_ws1,
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["first_name"] == "John"


class TestAppointmentWorkspaceIsolation:
    """Test that appointments are isolated between workspaces."""

    async def test_cannot_access_appointment_from_different_workspace(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        workspace_2: Workspace,
        test_user_ws2: User,
        sample_appointment_ws1: Appointment,
    ):
        """
        SECURITY CRITICAL: Cannot access appointment from different workspace.

        Create appointment in workspace 1, try to access with workspace 2 header.
        Must return 404.
        """
        # Try to access workspace 1's appointment with workspace 2 credentials
        headers = get_auth_headers(workspace_2.id, test_user_ws2.id, test_user_ws2.email)
        response = await client.get(
            f"/api/v1/appointments/{sample_appointment_ws1.id}",
            headers=headers,
        )

        # Must return 404
        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"

    async def test_cannot_list_appointments_from_different_workspace(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        workspace_2: Workspace,
        test_user_ws2: User,
        sample_appointment_ws1: Appointment,
        sample_appointment_ws2: Appointment,
    ):
        """
        SECURITY CRITICAL: List only returns appointments from own workspace.

        Create appointments in both workspaces, verify each workspace only
        sees their own appointments.
        """
        # List appointments in workspace 1 - should see only workspace 1's appointment
        headers_ws1 = get_auth_headers(workspace_1.id, test_user_ws1.id, test_user_ws1.email)
        response_ws1 = await client.get("/api/v1/appointments", headers=headers_ws1)

        assert response_ws1.status_code == 200
        data_ws1 = response_ws1.json()
        assert data_ws1["total"] == 1
        assert len(data_ws1["items"]) == 1
        assert data_ws1["items"][0]["id"] == str(sample_appointment_ws1.id)

        # List appointments in workspace 2 - should see only workspace 2's appointment
        headers_ws2 = get_auth_headers(workspace_2.id, test_user_ws2.id, test_user_ws2.email)
        response_ws2 = await client.get("/api/v1/appointments", headers=headers_ws2)

        assert response_ws2.status_code == 200
        data_ws2 = response_ws2.json()
        assert data_ws2["total"] == 1
        assert len(data_ws2["items"]) == 1
        assert data_ws2["items"][0]["id"] == str(sample_appointment_ws2.id)

    async def test_cannot_update_appointment_from_different_workspace(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        workspace_2: Workspace,
        sample_appointment_ws1: Appointment,
        test_user_ws2: User,
        redis_client,
    ):
        """
        SECURITY CRITICAL: Cannot update appointment from different workspace.

        Create appointment in workspace 1, try to update with workspace 2 header.
        Must return 404.
        """
        # Add CSRF token for workspace 2
        csrf_token = await add_csrf_to_client(
            client, workspace_2.id, test_user_ws2.id, redis_client
        )

        # Try to update workspace 1's appointment with workspace 2 credentials
        # Set JWT cookie on client
        from pazpaz.core.security import create_access_token
        jwt_token = create_access_token(
            user_id=test_user_ws2.id,
            workspace_id=workspace_2.id,
            email=test_user_ws2.email,
        )
        client.cookies.set("access_token", jwt_token)
        headers = get_auth_headers(workspace_2.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
        response = await client.put(
            f"/api/v1/appointments/{sample_appointment_ws1.id}",
            headers=headers,
            json={"notes": "Hacked notes"},
        )

        # Must return 404
        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"

        # Verify appointment was not modified
        headers_ws1 = get_auth_headers(workspace_1.id, test_user_ws1.id, test_user_ws1.email)
        verify_response = await client.get(
            f"/api/v1/appointments/{sample_appointment_ws1.id}",
            headers=headers_ws1,
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["notes"] == "Initial consultation"  # Unchanged

    async def test_cannot_delete_appointment_from_different_workspace(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        workspace_2: Workspace,
        sample_appointment_ws1: Appointment,
        test_user_ws2: User,
        redis_client,
    ):
        """
        SECURITY CRITICAL: Cannot delete appointment from different workspace.

        Create appointment in workspace 1, try to delete with workspace 2 header.
        Must return 404 and not delete.
        """
        # Add CSRF token for workspace 2
        csrf_token = await add_csrf_to_client(
            client, workspace_2.id, test_user_ws2.id, redis_client
        )

        # Try to delete workspace 1's appointment with workspace 2 credentials
        # Set JWT cookie on client
        from pazpaz.core.security import create_access_token
        jwt_token = create_access_token(
            user_id=test_user_ws2.id,
            workspace_id=workspace_2.id,
            email=test_user_ws2.email,
        )
        client.cookies.set("access_token", jwt_token)
        headers = get_auth_headers(workspace_2.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
        response = await client.delete(
            f"/api/v1/appointments/{sample_appointment_ws1.id}",
            headers=headers,
        )

        # Must return 404
        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"

        # Verify appointment still exists
        headers_ws1 = get_auth_headers(workspace_1.id, test_user_ws1.id, test_user_ws1.email)
        verify_response = await client.get(
            f"/api/v1/appointments/{sample_appointment_ws1.id}",
            headers=headers_ws1,
        )
        assert verify_response.status_code == 200

    async def test_appointment_client_must_be_in_same_workspace(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        workspace_2: Workspace,
        sample_client_ws1: Client,
        test_user_ws2: User,
        redis_client,
    ):
        """
        SECURITY CRITICAL: Cannot create appointment with client from
        different workspace.

        Create client in workspace 1, try to create appointment in
        workspace 2 referencing that client. Must return 404 (client
        not found in workspace 2).
        """
        # Add CSRF token for workspace 2
        csrf_token = await add_csrf_to_client(
            client, workspace_2.id, test_user_ws2.id, redis_client
        )

        # Try to create appointment in workspace 2 with workspace 1's client
        # Set JWT cookie on client
        from pazpaz.core.security import create_access_token
        jwt_token = create_access_token(
            user_id=test_user_ws2.id,
            workspace_id=workspace_2.id,
            email=test_user_ws2.email,
        )
        client.cookies.set("access_token", jwt_token)
        headers = get_auth_headers(workspace_2.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
        tomorrow = datetime.now(UTC).replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        response = await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow + timedelta(hours=1)).isoformat(),
                "location_type": "clinic",
            },
        )

        # Must return 404 - client not found in workspace 2
        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"

    async def test_conflicts_check_scoped_to_workspace(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        workspace_2: Workspace,
        test_user_ws2: User,
        sample_appointment_ws1: Appointment,
        sample_appointment_ws2: Appointment,
    ):
        """
        SECURITY CRITICAL: Conflict check only considers same workspace.

        Create overlapping appointments in different workspaces.
        Conflict check should not report cross-workspace conflicts.
        """
        # Get the time range of workspace 1's appointment
        start = sample_appointment_ws1.scheduled_start
        end = sample_appointment_ws1.scheduled_end

        # Check conflicts in workspace 2 for the same time slot
        # Should not report workspace 1's appointment as a conflict
        headers = get_auth_headers(workspace_2.id, test_user_ws2.id, test_user_ws2.email)
        response = await client.get(
            "/api/v1/appointments/conflicts",
            headers=headers,
            params={
                "scheduled_start": start.isoformat(),
                "scheduled_end": end.isoformat(),
            },
        )

        assert response.status_code == 200
        data = response.json()
        # No conflict because workspace 1's appointment is not visible to workspace 2
        assert data["has_conflict"] is False
        assert len(data["conflicting_appointments"]) == 0


class TestWorkspaceIsolationWithFilters:
    """Test that filtering doesn't leak data across workspaces."""

    async def test_client_filter_in_appointments_scoped_to_workspace(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        workspace_2: Workspace,
        test_user_ws2: User,
        sample_client_ws1: Client,
        sample_appointment_ws1: Appointment,
    ):
        """
        SECURITY CRITICAL: Filtering by client_id is scoped to workspace.

        Try to filter appointments in workspace 2 by workspace 1's client ID.
        Should return empty list, not an error or workspace 1's appointments.
        """
        # Try to list appointments in workspace 2 filtered by workspace 1's client
        headers = get_auth_headers(workspace_2.id, test_user_ws2.id, test_user_ws2.email)
        response = await client.get(
            "/api/v1/appointments",
            headers=headers,
            params={"client_id": str(sample_client_ws1.id)},
        )

        assert response.status_code == 200
        data = response.json()
        # Should return empty - client doesn't exist in workspace 2's context
        assert data["total"] == 0
        assert len(data["items"]) == 0
