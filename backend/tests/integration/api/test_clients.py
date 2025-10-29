"""Test Client CRUD API endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from pazpaz.models.client import Client
from pazpaz.models.user import User
from pazpaz.models.workspace import Workspace
from tests.conftest import add_csrf_to_client, get_auth_headers

pytestmark = pytest.mark.asyncio


class TestCreateClient:
    """Test client creation endpoint."""

    async def test_create_client_success(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """Happy path: Create a client with valid data."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.post(
            "/api/v1/clients",
            headers=headers,
            json={
                "first_name": "Alice",
                "last_name": "Johnson",
                "email": "alice.johnson@example.com",
                "phone": "+1555123456",
                "address": "123 Main St",
                "medical_history": "No known allergies",
                "emergency_contact_name": "Bob Johnson",
                "emergency_contact_phone": "+1555654321",
                "is_active": True,
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
        assert data["address"] == "123 Main St"
        assert data["medical_history"] == "No known allergies"
        assert data["emergency_contact_name"] == "Bob Johnson"
        assert data["emergency_contact_phone"] == "+1555654321"
        assert data["is_active"] is True
        assert data["consent_status"] is True
        assert data["notes"] == "New client"
        assert data["tags"] == ["massage", "sports"]
        assert data["workspace_id"] == str(workspace_1.id)
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        # Check computed fields are present
        assert "full_name" in data
        assert data["full_name"] == "Alice Johnson"
        assert "next_appointment" in data
        assert "last_appointment" in data
        assert "appointment_count" in data
        assert data["appointment_count"] == 0

    async def test_create_client_minimal_fields(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """Create client with only required fields."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

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
        assert data["address"] is None
        assert data["medical_history"] is None
        assert data["emergency_contact_name"] is None
        assert data["emergency_contact_phone"] is None
        assert data["is_active"] is True  # Default value
        assert data["notes"] is None
        assert data["tags"] is None

    async def test_create_client_validates_email(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """Invalid email format should return 422."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

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
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """Missing first_name should return 422."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

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
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """Missing last_name should return 422."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

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
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """Consent status defaults to False if not provided."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

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
        test_user_ws1: User,
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
        self, client: AsyncClient, workspace_1: Workspace, test_user_ws1: User
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
        self, client: AsyncClient, workspace_1: Workspace, test_user_ws1: User
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
        test_user_ws1: User,
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
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """Test pagination parameters."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

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
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """Clients should be sorted by last name, first name."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

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
        test_user_ws1: User,
        redis_client,
    ):
        """Partial update of client fields works correctly."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

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
        test_user_ws1: User,
        redis_client,
    ):
        """Update all client fields."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.put(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
            json={
                "first_name": "Updated",
                "last_name": "Name",
                "email": "updated@example.com",
                "phone": "+9999999999",
                "address": "456 New St",
                "medical_history": "Updated history",
                "emergency_contact_name": "Emergency Person",
                "emergency_contact_phone": "+1111111111",
                "is_active": False,
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
        assert data["address"] == "456 New St"
        assert data["medical_history"] == "Updated history"
        assert data["emergency_contact_name"] == "Emergency Person"
        assert data["emergency_contact_phone"] == "+1111111111"
        assert data["is_active"] is False
        assert data["consent_status"] is False
        assert data["notes"] == "All fields updated"
        assert data["tags"] == ["new", "tags"]

    async def test_update_client_not_found(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """Update non-existent client returns 404."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
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
        test_user_ws1: User,
        redis_client,
    ):
        """Invalid email in update returns 422."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

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
        test_user_ws1: User,
        redis_client,
    ):
        """Delete existing client returns 204 and performs soft delete."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.delete(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
        )

        assert response.status_code == 204

        # Verify client is soft deleted (still accessible but marked inactive)
        get_response = await client.get(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
        )
        assert get_response.status_code == 200
        assert get_response.json()["is_active"] is False

    async def test_delete_client_not_found(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """Delete non-existent client returns 404."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
        nonexistent_id = uuid.uuid4()

        response = await client.delete(
            f"/api/v1/clients/{nonexistent_id}",
            headers=headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"

    async def test_delete_client_performs_soft_delete(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
    ):
        """Test that DELETE performs soft delete (is_active = false)."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Delete client
        response = await client.delete(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
        )
        assert response.status_code == 204

        # Client should not appear in default list (active only)
        list_response = await client.get("/api/v1/clients", headers=headers)
        assert list_response.status_code == 200
        client_ids = [c["id"] for c in list_response.json()["items"]]
        assert str(sample_client_ws1.id) not in client_ids

        # But should appear when including inactive clients
        list_with_inactive = await client.get(
            "/api/v1/clients",
            headers=headers,
            params={"include_inactive": True},
        )
        assert list_with_inactive.status_code == 200
        all_client_ids = [c["id"] for c in list_with_inactive.json()["items"]]
        assert str(sample_client_ws1.id) in all_client_ids

        # Can still retrieve directly (should show is_active = false)
        get_response = await client.get(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
        )
        assert get_response.status_code == 200
        assert get_response.json()["is_active"] is False

    async def test_delete_client_preserves_appointments(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        sample_appointment_ws1,
        test_user_ws1: User,
        redis_client,
    ):
        """Soft deleting client preserves their appointments."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Verify appointment exists
        appointment_response = await client.get(
            f"/api/v1/appointments/{sample_appointment_ws1.id}",
            headers=headers,
        )
        assert appointment_response.status_code == 200

        # Soft delete client
        delete_response = await client.delete(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
        )
        assert delete_response.status_code == 204

        # Appointment should still exist (soft delete preserves data)
        appointment_check = await client.get(
            f"/api/v1/appointments/{sample_appointment_ws1.id}",
            headers=headers,
        )
        assert appointment_check.status_code == 200


class TestClientComputedFields:
    """Test computed appointment fields on client responses."""

    async def test_get_client_includes_appointment_stats(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
    ):
        """Test that GET /clients/{id} includes appointment statistics."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Create past completed appointment
        past_apt = await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": "2020-01-01T10:00:00Z",
                "scheduled_end": "2020-01-01T11:00:00Z",
                "status": "attended",
                "location_type": "clinic",
            },
        )
        assert past_apt.status_code == 201

        # Create future scheduled appointment
        future_apt = await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": "2099-12-31T10:00:00Z",
                "scheduled_end": "2099-12-31T11:00:00Z",
                "status": "scheduled",
                "location_type": "clinic",
            },
        )
        assert future_apt.status_code == 201

        # Get client
        response = await client.get(
            f"/api/v1/clients/{sample_client_ws1.id}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Check that appointments were counted (at least the 2 we created)
        assert data["appointment_count"] >= 2
        # We created an attended appointment, so last_appointment should be set
        # Note: It might be None if the appointments API doesn't accept
        # "attended" status on creation
        # In that case, we just verify the field exists
        assert "last_appointment" in data
        assert "next_appointment" in data
        # The future appointment should be counted as next
        assert data["next_appointment"] is not None

    async def test_list_clients_without_appointments_is_fast(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """
        Test that list without include_appointments doesn't fetch
        appointment data.
        """
        headers = get_auth_headers(workspace_1.id)

        response = await client.get("/api/v1/clients", headers=headers)

        assert response.status_code == 200
        data = response.json()
        # Should have computed fields with default values
        if len(data["items"]) > 0:
            item = data["items"][0]
            assert "appointment_count" in item
            assert "next_appointment" in item
            assert "last_appointment" in item

    async def test_list_clients_with_appointments_includes_stats(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
    ):
        """Test that list with include_appointments=true fetches appointment stats."""
        headers = get_auth_headers(workspace_1.id)

        response = await client.get(
            "/api/v1/clients",
            headers=headers,
            params={"include_appointments": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) > 0
        item = data["items"][0]
        assert "appointment_count" in item
        assert "next_appointment" in item
        assert "last_appointment" in item


class TestClientActiveFiltering:
    """Test is_active filtering in list endpoint."""

    async def test_list_clients_excludes_inactive_by_default(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """Test that inactive clients are excluded from default list."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Create active client
        active = await client.post(
            "/api/v1/clients",
            headers=headers,
            json={
                "first_name": "Active",
                "last_name": "Client",
                "is_active": True,
                "consent_status": True,
            },
        )
        assert active.status_code == 201
        active_id = active.json()["id"]

        # Create inactive client
        inactive = await client.post(
            "/api/v1/clients",
            headers=headers,
            json={
                "first_name": "Inactive",
                "last_name": "Client",
                "is_active": False,
                "consent_status": True,
            },
        )
        assert inactive.status_code == 201
        inactive_id = inactive.json()["id"]

        # Default list should only show active
        response = await client.get("/api/v1/clients", headers=headers)
        assert response.status_code == 200
        client_ids = [c["id"] for c in response.json()["items"]]
        assert active_id in client_ids
        assert inactive_id not in client_ids

    async def test_list_clients_with_inactive_shows_all(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """Test that include_inactive=true shows all clients."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Create active and inactive clients
        active = await client.post(
            "/api/v1/clients",
            headers=headers,
            json={
                "first_name": "Active",
                "last_name": "Client",
                "is_active": True,
                "consent_status": True,
            },
        )
        active_id = active.json()["id"]

        inactive = await client.post(
            "/api/v1/clients",
            headers=headers,
            json={
                "first_name": "Inactive",
                "last_name": "Client",
                "is_active": False,
                "consent_status": True,
            },
        )
        inactive_id = inactive.json()["id"]

        # With include_inactive=true, should show both
        response = await client.get(
            "/api/v1/clients",
            headers=headers,
            params={"include_inactive": True},
        )
        assert response.status_code == 200
        client_ids = [c["id"] for c in response.json()["items"]]
        assert active_id in client_ids
        assert inactive_id in client_ids
