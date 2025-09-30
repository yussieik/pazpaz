"""Test Client CRUD API endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from pazpaz.models.client import Client
from pazpaz.models.workspace import Workspace
from tests.conftest import get_auth_headers

pytestmark = pytest.mark.asyncio


class TestCreateClient:
    """Test client creation endpoint."""

    async def test_create_client_success(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """Happy path: Create a client with valid data."""
        headers = get_auth_headers(workspace_1.id)

        response = await client.post(
            "/api/v1/clients",
            headers=headers,
            json={
                "first_name": "Alice",
                "last_name": "Johnson",
                "email": "alice.johnson@example.com",
                "phone": "+1555123456",
                "consent_status": True,
                "notes": "New client",
                "tags": ["massage", "sports"],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == "Alice"
        assert data["last_name"] == "Johnson"
        assert data["email"] == "alice.johnson@example.com"
        assert data["phone"] == "+1555123456"
        assert data["consent_status"] is True
        assert data["notes"] == "New client"
        assert data["tags"] == ["massage", "sports"]
        assert data["workspace_id"] == str(workspace_1.id)
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_client_minimal_fields(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """Create client with only required fields."""
        headers = get_auth_headers(workspace_1.id)

        response = await client.post(
            "/api/v1/clients",
            headers=headers,
            json={
                "first_name": "Bob",
                "last_name": "Smith",
                "consent_status": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == "Bob"
        assert data["last_name"] == "Smith"
        assert data["consent_status"] is True
        assert data["email"] is None
        assert data["phone"] is None
        assert data["notes"] is None
        assert data["tags"] is None

    async def test_create_client_validates_email(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """Invalid email format should return 422."""
        headers = get_auth_headers(workspace_1.id)

        response = await client.post(
            "/api/v1/clients",
            headers=headers,
            json={
                "first_name": "Invalid",
                "last_name": "Email",
                "email": "not-an-email",
                "consent_status": True,
            },
        )

        assert response.status_code == 422

    async def test_create_client_requires_first_name(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """Missing first_name should return 422."""
        headers = get_auth_headers(workspace_1.id)

        response = await client.post(
            "/api/v1/clients",
            headers=headers,
            json={
                "last_name": "NoFirstName",
                "consent_status": True,
            },
        )

        assert response.status_code == 422

    async def test_create_client_requires_last_name(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """Missing last_name should return 422."""
        headers = get_auth_headers(workspace_1.id)

        response = await client.post(
            "/api/v1/clients",
            headers=headers,
            json={
                "first_name": "NoLastName",
                "consent_status": True,
            },
        )

        assert response.status_code == 422

    async def test_create_client_default_consent_false(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """Consent status defaults to False if not provided."""
        headers = get_auth_headers(workspace_1.id)

        response = await client.post(
            "/api/v1/clients",
            headers=headers,
            json={
                "first_name": "Default",
                "last_name": "Consent",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["consent_status"] is False


class TestGetClient:
    """Test get client endpoint."""

    async def test_get_client_success(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
    ):
        """Get existing client returns 200 with correct data."""
        headers = get_auth_headers(workspace_1.id)

        response = await client.get(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_client_ws1.id)
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        assert data["email"] == "john.doe@example.com"
        assert data["workspace_id"] == str(workspace_1.id)

    async def test_get_client_not_found(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """Non-existent client UUID returns 404."""
        headers = get_auth_headers(workspace_1.id)
        nonexistent_id = uuid.uuid4()

        response = await client.get(
            f"/api/v1/clients/{nonexistent_id}",
            headers=headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"


class TestListClients:
    """Test list clients endpoint."""

    async def test_list_clients_empty(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """List clients in empty workspace returns empty list."""
        headers = get_auth_headers(workspace_1.id)

        response = await client.get("/api/v1/clients", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 50
        assert data["total_pages"] == 0

    async def test_list_clients_with_data(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
    ):
        """List clients returns existing clients."""
        headers = get_auth_headers(workspace_1.id)

        response = await client.get("/api/v1/clients", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(sample_client_ws1.id)

    async def test_list_clients_pagination(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """Test pagination parameters."""
        headers = get_auth_headers(workspace_1.id)

        # Create multiple clients
        for i in range(5):
            await client.post(
                "/api/v1/clients",
                headers=headers,
                json={
                    "first_name": f"Client{i}",
                    "last_name": f"Test{i}",
                    "consent_status": True,
                },
            )

        # Request page 1 with page_size 2
        response = await client.get(
            "/api/v1/clients",
            headers=headers,
            params={"page": 1, "page_size": 2},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 3

        # Request page 2
        response = await client.get(
            "/api/v1/clients",
            headers=headers,
            params={"page": 2, "page_size": 2},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["page"] == 2

    async def test_list_clients_sorted_by_name(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """Clients should be sorted by last name, first name."""
        headers = get_auth_headers(workspace_1.id)

        # Create clients in non-alphabetical order
        await client.post(
            "/api/v1/clients",
            headers=headers,
            json={"first_name": "Zoe", "last_name": "Adams", "consent_status": True},
        )
        await client.post(
            "/api/v1/clients",
            headers=headers,
            json={"first_name": "Alice", "last_name": "Baker", "consent_status": True},
        )
        await client.post(
            "/api/v1/clients",
            headers=headers,
            json={"first_name": "Bob", "last_name": "Adams", "consent_status": True},
        )

        response = await client.get("/api/v1/clients", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3

        # Should be sorted: Adams, Bob -> Adams, Zoe -> Baker, Alice
        assert data["items"][0]["last_name"] == "Adams"
        assert data["items"][0]["first_name"] == "Bob"
        assert data["items"][1]["last_name"] == "Adams"
        assert data["items"][1]["first_name"] == "Zoe"
        assert data["items"][2]["last_name"] == "Baker"
        assert data["items"][2]["first_name"] == "Alice"


class TestUpdateClient:
    """Test update client endpoint."""

    async def test_update_client_success(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
    ):
        """Partial update of client fields works correctly."""
        headers = get_auth_headers(workspace_1.id)

        response = await client.put(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
            json={
                "first_name": "Jonathan",
                "notes": "Updated notes",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Jonathan"  # Updated
        assert data["last_name"] == "Doe"  # Unchanged
        assert data["notes"] == "Updated notes"  # Updated
        assert data["email"] == "john.doe@example.com"  # Unchanged

    async def test_update_client_all_fields(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
    ):
        """Update all client fields."""
        headers = get_auth_headers(workspace_1.id)

        response = await client.put(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
            json={
                "first_name": "Updated",
                "last_name": "Name",
                "email": "updated@example.com",
                "phone": "+9999999999",
                "consent_status": False,
                "notes": "All fields updated",
                "tags": ["new", "tags"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"
        assert data["last_name"] == "Name"
        assert data["email"] == "updated@example.com"
        assert data["phone"] == "+9999999999"
        assert data["consent_status"] is False
        assert data["notes"] == "All fields updated"
        assert data["tags"] == ["new", "tags"]

    async def test_update_client_not_found(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """Update non-existent client returns 404."""
        headers = get_auth_headers(workspace_1.id)
        nonexistent_id = uuid.uuid4()

        response = await client.put(
            f"/api/v1/clients/{nonexistent_id}",
            headers=headers,
            json={"first_name": "NonExistent"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"

    async def test_update_client_validates_email(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
    ):
        """Invalid email in update returns 422."""
        headers = get_auth_headers(workspace_1.id)

        response = await client.put(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
            json={"email": "invalid-email"},
        )

        assert response.status_code == 422


class TestDeleteClient:
    """Test delete client endpoint."""

    async def test_delete_client_success(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
    ):
        """Delete existing client returns 204."""
        headers = get_auth_headers(workspace_1.id)

        response = await client.delete(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
        )

        assert response.status_code == 204

        # Verify client is deleted
        get_response = await client.get(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
        )
        assert get_response.status_code == 404

    async def test_delete_client_not_found(
        self, client: AsyncClient, workspace_1: Workspace
    ):
        """Delete non-existent client returns 404."""
        headers = get_auth_headers(workspace_1.id)
        nonexistent_id = uuid.uuid4()

        response = await client.delete(
            f"/api/v1/clients/{nonexistent_id}",
            headers=headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"

    async def test_delete_client_cascades_to_appointments(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        sample_appointment_ws1,
    ):
        """Deleting client also deletes their appointments (cascade)."""
        headers = get_auth_headers(workspace_1.id)

        # Verify appointment exists
        appointment_response = await client.get(
            f"/api/v1/appointments/{sample_appointment_ws1.id}",
            headers=headers,
        )
        assert appointment_response.status_code == 200

        # Delete client
        delete_response = await client.delete(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
        )
        assert delete_response.status_code == 204

        # Verify appointment is also deleted (cascade)
        appointment_check = await client.get(
            f"/api/v1/appointments/{sample_appointment_ws1.id}",
            headers=headers,
        )
        assert appointment_check.status_code == 404
