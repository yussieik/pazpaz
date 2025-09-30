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
from pazpaz.models.workspace import Workspace
from tests.conftest import get_auth_headers

pytestmark = pytest.mark.asyncio


class TestClientWorkspaceIsolation:
    """Test that clients are isolated between workspaces."""

    async def test_cannot_access_client_from_different_workspace(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        workspace_2: Workspace,
        sample_client_ws1: Client,
    ):
        """
        SECURITY CRITICAL: Cannot access client from different workspace.

        Create client in workspace 1, try to access with workspace 2 header.
        Must return 404 (not 403) to avoid information leakage.
        """
        # Try to access workspace 1's client with workspace 2 credentials
        headers = get_auth_headers(workspace_2.id)
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
        workspace_2: Workspace,
        sample_client_ws1: Client,
        sample_client_ws2: Client,
    ):
        """
        SECURITY CRITICAL: List only returns clients from own workspace.

        Create clients in both workspaces, verify each workspace only sees
        their own clients.
        """
        # List clients in workspace 1 - should see only workspace 1's client
        headers_ws1 = get_auth_headers(workspace_1.id)
        response_ws1 = await client.get("/api/v1/clients", headers=headers_ws1)

        assert response_ws1.status_code == 200
        data_ws1 = response_ws1.json()
        assert data_ws1["total"] == 1
        assert len(data_ws1["items"]) == 1
        assert data_ws1["items"][0]["id"] == str(sample_client_ws1.id)
        assert data_ws1["items"][0]["first_name"] == "John"

        # List clients in workspace 2 - should see only workspace 2's client
        headers_ws2 = get_auth_headers(workspace_2.id)
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
        workspace_2: Workspace,
        sample_client_ws1: Client,
    ):
        """
        SECURITY CRITICAL: Cannot update client from different workspace.

        Create client in workspace 1, try to update with workspace 2 header.
        Must return 404.
        """
        # Try to update workspace 1's client with workspace 2 credentials
        headers = get_auth_headers(workspace_2.id)
        response = await client.put(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
            json={"first_name": "Hacked"},
        )

        # Must return 404
        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"

        # Verify client was not modified
        headers_ws1 = get_auth_headers(workspace_1.id)
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
        workspace_2: Workspace,
        sample_client_ws1: Client,
    ):
        """
        SECURITY CRITICAL: Cannot delete client from different workspace.

        Create client in workspace 1, try to delete with workspace 2 header.
        Must return 404 and not delete.
        """
        # Try to delete workspace 1's client with workspace 2 credentials
        headers = get_auth_headers(workspace_2.id)
        response = await client.delete(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
        )

        # Must return 404
        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"

        # Verify client still exists
        headers_ws1 = get_auth_headers(workspace_1.id)
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
        workspace_2: Workspace,
        sample_appointment_ws1: Appointment,
    ):
        """
        SECURITY CRITICAL: Cannot access appointment from different workspace.

        Create appointment in workspace 1, try to access with workspace 2 header.
        Must return 404.
        """
        # Try to access workspace 1's appointment with workspace 2 credentials
        headers = get_auth_headers(workspace_2.id)
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
        workspace_2: Workspace,
        sample_appointment_ws1: Appointment,
        sample_appointment_ws2: Appointment,
    ):
        """
        SECURITY CRITICAL: List only returns appointments from own workspace.

        Create appointments in both workspaces, verify each workspace only
        sees their own appointments.
        """
        # List appointments in workspace 1 - should see only workspace 1's appointment
        headers_ws1 = get_auth_headers(workspace_1.id)
        response_ws1 = await client.get("/api/v1/appointments", headers=headers_ws1)

        assert response_ws1.status_code == 200
        data_ws1 = response_ws1.json()
        assert data_ws1["total"] == 1
        assert len(data_ws1["items"]) == 1
        assert data_ws1["items"][0]["id"] == str(sample_appointment_ws1.id)

        # List appointments in workspace 2 - should see only workspace 2's appointment
        headers_ws2 = get_auth_headers(workspace_2.id)
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
        workspace_2: Workspace,
        sample_appointment_ws1: Appointment,
    ):
        """
        SECURITY CRITICAL: Cannot update appointment from different workspace.

        Create appointment in workspace 1, try to update with workspace 2 header.
        Must return 404.
        """
        # Try to update workspace 1's appointment with workspace 2 credentials
        headers = get_auth_headers(workspace_2.id)
        response = await client.put(
            f"/api/v1/appointments/{sample_appointment_ws1.id}",
            headers=headers,
            json={"notes": "Hacked notes"},
        )

        # Must return 404
        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"

        # Verify appointment was not modified
        headers_ws1 = get_auth_headers(workspace_1.id)
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
        workspace_2: Workspace,
        sample_appointment_ws1: Appointment,
    ):
        """
        SECURITY CRITICAL: Cannot delete appointment from different workspace.

        Create appointment in workspace 1, try to delete with workspace 2 header.
        Must return 404 and not delete.
        """
        # Try to delete workspace 1's appointment with workspace 2 credentials
        headers = get_auth_headers(workspace_2.id)
        response = await client.delete(
            f"/api/v1/appointments/{sample_appointment_ws1.id}",
            headers=headers,
        )

        # Must return 404
        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"

        # Verify appointment still exists
        headers_ws1 = get_auth_headers(workspace_1.id)
        verify_response = await client.get(
            f"/api/v1/appointments/{sample_appointment_ws1.id}",
            headers=headers_ws1,
        )
        assert verify_response.status_code == 200

    async def test_appointment_client_must_be_in_same_workspace(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        workspace_2: Workspace,
        sample_client_ws1: Client,
    ):
        """
        SECURITY CRITICAL: Cannot create appointment with client from
        different workspace.

        Create client in workspace 1, try to create appointment in
        workspace 2 referencing that client. Must return 404 (client
        not found in workspace 2).
        """
        # Try to create appointment in workspace 2 with workspace 1's client
        headers = get_auth_headers(workspace_2.id)
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
        workspace_2: Workspace,
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
        headers = get_auth_headers(workspace_2.id)
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
        workspace_2: Workspace,
        sample_client_ws1: Client,
        sample_appointment_ws1: Appointment,
    ):
        """
        SECURITY CRITICAL: Filtering by client_id is scoped to workspace.

        Try to filter appointments in workspace 2 by workspace 1's client ID.
        Should return empty list, not an error or workspace 1's appointments.
        """
        # Try to list appointments in workspace 2 filtered by workspace 1's client
        headers = get_auth_headers(workspace_2.id)
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
