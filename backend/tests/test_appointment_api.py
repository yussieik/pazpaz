"""Test Appointment CRUD API endpoints and conflict detection."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from pazpaz.models.appointment import Appointment
from pazpaz.models.client import Client
from pazpaz.models.user import User
from pazpaz.models.workspace import Workspace
from tests.conftest import add_csrf_to_client, get_auth_headers

pytestmark = pytest.mark.asyncio


class TestCreateAppointment:
    """Test appointment creation endpoint."""

    async def test_create_appointment_success(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
    ):
        """Happy path: Create an appointment with valid data."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
        tomorrow = datetime.now(UTC).replace(
            hour=14, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        response = await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow + timedelta(hours=1)).isoformat(),
                "location_type": "clinic",
                "location_details": "Room 202",
                "notes": "Follow-up session",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["client_id"] == str(sample_client_ws1.id)
        assert data["location_type"] == "clinic"
        assert data["location_details"] == "Room 202"
        assert data["notes"] == "Follow-up session"
        assert data["status"] == "scheduled"
        assert data["workspace_id"] == str(workspace_1.id)
        assert "id" in data
        assert "client" in data
        assert data["client"]["first_name"] == "John"

    async def test_create_appointment_minimal_fields(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
    ):
        """Create appointment with only required fields."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
        tomorrow = datetime.now(UTC).replace(
            hour=16, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        response = await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow + timedelta(hours=1)).isoformat(),
                "location_type": "online",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["location_details"] is None
        assert data["notes"] is None
        assert data["status"] == "scheduled"

    async def test_create_appointment_validates_end_after_start(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
    ):
        """Scheduled end before or equal to start returns 422."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
        tomorrow = datetime.now(UTC).replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        # End time equals start time
        response = await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": tomorrow.isoformat(),  # Same as start
                "location_type": "clinic",
            },
        )

        assert response.status_code == 422

        # End time before start time
        response = await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow - timedelta(hours=1)).isoformat(),
                "location_type": "clinic",
            },
        )

        assert response.status_code == 422

    async def test_create_appointment_detects_conflicts(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        sample_appointment_ws1: Appointment,
        test_user_ws1: User,
        redis_client,
    ):
        """Creating overlapping appointment returns 409 with conflict details."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Try to create appointment that overlaps with existing one
        start = sample_appointment_ws1.scheduled_start
        end = sample_appointment_ws1.scheduled_end

        response = await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": (start + timedelta(minutes=30)).isoformat(),
                "scheduled_end": (end + timedelta(minutes=30)).isoformat(),
                "location_type": "clinic",
            },
        )

        assert response.status_code == 409
        data = response.json()
        assert "detail" in data
        assert "conflicting_appointments" in data["detail"]
        assert len(data["detail"]["conflicting_appointments"]) > 0
        assert data["detail"]["conflicting_appointments"][0]["id"] == str(
            sample_appointment_ws1.id
        )

    async def test_create_appointment_ignores_cancelled_in_conflicts(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        cancelled_appointment_ws1: Appointment,
        test_user_ws1: User,
        redis_client,
    ):
        """Cancelled appointments don't block new appointments."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Try to create appointment at the same time as cancelled one
        start = cancelled_appointment_ws1.scheduled_start
        end = cancelled_appointment_ws1.scheduled_end

        response = await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": start.isoformat(),
                "scheduled_end": end.isoformat(),
                "location_type": "clinic",
            },
        )

        # Should succeed - cancelled appointments don't cause conflicts
        assert response.status_code == 201

    async def test_create_appointment_client_not_found(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """Creating appointment with non-existent client returns 404."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
        tomorrow = datetime.now(UTC).replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        nonexistent_client_id = uuid.uuid4()

        response = await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(nonexistent_client_id),
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow + timedelta(hours=1)).isoformat(),
                "location_type": "clinic",
            },
        )

        assert response.status_code == 404


class TestGetAppointment:
    """Test get appointment endpoint."""

    async def test_get_appointment_success(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        sample_appointment_ws1: Appointment,
    ):
        """Get existing appointment returns 200 with correct data."""
        headers = get_auth_headers(workspace_1.id)

        response = await client.get(
            f"/api/v1/appointments/{sample_appointment_ws1.id}",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_appointment_ws1.id)
        assert data["workspace_id"] == str(workspace_1.id)
        assert data["location_type"] == "clinic"
        assert "client" in data
        assert data["client"]["first_name"] == "John"

    async def test_get_appointment_not_found(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Non-existent appointment UUID returns 404."""
        headers = get_auth_headers(workspace_1.id)
        nonexistent_id = uuid.uuid4()

        response = await client.get(
            f"/api/v1/appointments/{nonexistent_id}",
            headers=headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"


class TestListAppointments:
    """Test list appointments endpoint."""

    async def test_list_appointments_empty(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """List appointments in empty workspace returns empty list."""
        headers = get_auth_headers(workspace_1.id)

        response = await client.get("/api/v1/appointments", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 50
        assert data["total_pages"] == 0

    async def test_list_appointments_with_data(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        sample_appointment_ws1: Appointment,
    ):
        """List appointments returns existing appointments."""
        headers = get_auth_headers(workspace_1.id)

        response = await client.get("/api/v1/appointments", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(sample_appointment_ws1.id)
        assert data["items"][0]["client"]["first_name"] == "John"

    async def test_list_appointments_with_date_filter(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
    ):
        """Date range filtering works correctly."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Create appointments on different days
        today = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        next_week = today + timedelta(days=7)

        # Create appointment for today
        await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": today.isoformat(),
                "scheduled_end": (today + timedelta(hours=1)).isoformat(),
                "location_type": "clinic",
            },
        )

        # Create appointment for tomorrow
        await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow + timedelta(hours=1)).isoformat(),
                "location_type": "clinic",
            },
        )

        # Create appointment for next week
        await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": next_week.isoformat(),
                "scheduled_end": (next_week + timedelta(hours=1)).isoformat(),
                "location_type": "clinic",
            },
        )

        # Filter for this week only
        response = await client.get(
            "/api/v1/appointments",
            headers=headers,
            params={
                "start_date": today.isoformat(),
                "end_date": (today + timedelta(days=2)).isoformat(),
            },
        )

        assert response.status_code == 200
        data = response.json()
        # Should return today and tomorrow, not next week
        assert data["total"] == 2

    async def test_list_appointments_with_client_filter(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        sample_appointment_ws1: Appointment,
        test_user_ws1: User,
        redis_client,
    ):
        """Client filtering works correctly."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Create another client
        create_response = await client.post(
            "/api/v1/clients",
            headers=headers,
            json={
                "first_name": "Another",
                "last_name": "Client",
                "consent_status": True,
            },
        )
        another_client_id = create_response.json()["id"]

        # Create appointment for another client
        tomorrow = datetime.now(UTC).replace(
            hour=14, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": another_client_id,
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow + timedelta(hours=1)).isoformat(),
                "location_type": "clinic",
            },
        )

        # Filter by original client
        response = await client.get(
            "/api/v1/appointments",
            headers=headers,
            params={"client_id": str(sample_client_ws1.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["client_id"] == str(sample_client_ws1.id)

    async def test_list_appointments_with_status_filter(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        sample_appointment_ws1: Appointment,
        cancelled_appointment_ws1: Appointment,
    ):
        """Status filtering works correctly."""
        headers = get_auth_headers(workspace_1.id)

        # Filter for scheduled only
        response = await client.get(
            "/api/v1/appointments",
            headers=headers,
            params={"status": "scheduled"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "scheduled"

        # Filter for cancelled only
        response = await client.get(
            "/api/v1/appointments",
            headers=headers,
            params={"status": "cancelled"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "cancelled"


class TestUpdateAppointment:
    """Test update appointment endpoint."""

    async def test_update_appointment_success(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_appointment_ws1: Appointment,
        test_user_ws1: User,
        redis_client,
    ):
        """Partial update of appointment fields works correctly."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.put(
            f"/api/v1/appointments/{sample_appointment_ws1.id}",
            headers=headers,
            json={
                "notes": "Updated notes",
                "location_details": "Room 303",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["notes"] == "Updated notes"
        assert data["location_details"] == "Room 303"
        assert data["location_type"] == "clinic"  # Unchanged

    async def test_update_appointment_time_no_conflict(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_appointment_ws1: Appointment,
        test_user_ws1: User,
        redis_client,
    ):
        """Update appointment time to non-conflicting slot."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Move to a different day
        new_start = sample_appointment_ws1.scheduled_start + timedelta(days=7)
        new_end = sample_appointment_ws1.scheduled_end + timedelta(days=7)

        response = await client.put(
            f"/api/v1/appointments/{sample_appointment_ws1.id}",
            headers=headers,
            json={
                "scheduled_start": new_start.isoformat(),
                "scheduled_end": new_end.isoformat(),
            },
        )

        assert response.status_code == 200
        data = response.json()
        # Pydantic serializes UTC datetimes with "Z" suffix instead of "+00:00"
        assert data["scheduled_start"] == new_start.isoformat().replace("+00:00", "Z")
        assert data["scheduled_end"] == new_end.isoformat().replace("+00:00", "Z")

    async def test_update_appointment_rechecks_conflicts(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
    ):
        """Updating time to conflicting slot returns 409."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Create two appointments
        tomorrow = datetime.now(UTC).replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        # First appointment: 10:00-11:00
        await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow + timedelta(hours=1)).isoformat(),
                "location_type": "clinic",
            },
        )

        # Second appointment: 14:00-15:00
        afternoon = tomorrow.replace(hour=14)
        response2 = await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": afternoon.isoformat(),
                "scheduled_end": (afternoon + timedelta(hours=1)).isoformat(),
                "location_type": "clinic",
            },
        )
        appointment2_id = response2.json()["id"]

        # Try to update second appointment to overlap with first
        response = await client.put(
            f"/api/v1/appointments/{appointment2_id}",
            headers=headers,
            json={
                "scheduled_start": (tomorrow + timedelta(minutes=30)).isoformat(),
                "scheduled_end": (
                    tomorrow + timedelta(hours=1, minutes=30)
                ).isoformat(),
            },
        )

        # Should fail with conflict
        assert response.status_code == 409
        data = response.json()
        assert "conflicting_appointments" in data["detail"]

    async def test_update_appointment_validates_end_after_start(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_appointment_ws1: Appointment,
        test_user_ws1: User,
        redis_client,
    ):
        """Update with end before start returns 422."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        tomorrow = datetime.now(UTC).replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        response = await client.put(
            f"/api/v1/appointments/{sample_appointment_ws1.id}",
            headers=headers,
            json={
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow - timedelta(hours=1)).isoformat(),
            },
        )

        assert response.status_code == 422

    async def test_update_appointment_not_found(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """Update non-existent appointment returns 404."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
        nonexistent_id = uuid.uuid4()

        response = await client.put(
            f"/api/v1/appointments/{nonexistent_id}",
            headers=headers,
            json={"notes": "NonExistent"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"

    async def test_update_appointment_allow_conflict(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
    ):
        """Update appointment with allow_conflict=true bypasses conflict detection."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Create two appointments
        tomorrow = datetime.now(UTC).replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        # First appointment: 10:00-11:00
        response1 = await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow + timedelta(hours=1)).isoformat(),
                "location_type": "clinic",
            },
        )
        appt1_id = response1.json()["id"]

        # Second appointment: 14:00-15:00
        afternoon = tomorrow.replace(hour=14)
        response2 = await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": afternoon.isoformat(),
                "scheduled_end": (afternoon + timedelta(hours=1)).isoformat(),
                "location_type": "clinic",
            },
        )
        appt2_id = response2.json()["id"]

        # Try to move second appointment to conflict with first (without allow_conflict)
        response = await client.put(
            f"/api/v1/appointments/{appt2_id}",
            headers=headers,
            json={
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow + timedelta(hours=1)).isoformat(),
            },
        )

        # Should return 409 conflict
        assert response.status_code == 409

        # Now try with allow_conflict=true
        response = await client.put(
            f"/api/v1/appointments/{appt2_id}",
            headers=headers,
            params={"allow_conflict": "true"},
            json={
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow + timedelta(hours=1)).isoformat(),
            },
        )

        # Should succeed even with conflict
        assert response.status_code == 200
        data = response.json()
        assert data["scheduled_start"] == tomorrow.isoformat().replace("+00:00", "Z")


class TestDeleteAppointment:
    """Test delete appointment endpoint."""

    async def test_delete_appointment_success(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_appointment_ws1: Appointment,
        test_user_ws1: User,
        redis_client,
    ):
        """Delete existing appointment returns 204."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.delete(
            f"/api/v1/appointments/{sample_appointment_ws1.id}",
            headers=headers,
        )

        assert response.status_code == 204

        # Verify appointment is deleted
        get_response = await client.get(
            f"/api/v1/appointments/{sample_appointment_ws1.id}",
            headers=headers,
        )
        assert get_response.status_code == 404

    async def test_delete_appointment_not_found(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """Delete non-existent appointment returns 404."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
        nonexistent_id = uuid.uuid4()

        response = await client.delete(
            f"/api/v1/appointments/{nonexistent_id}",
            headers=headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"


class TestConflictCheck:
    """Test conflict check endpoint."""

    async def test_conflict_check_no_conflict(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Conflict check with no conflicts returns has_conflict=False."""
        headers = get_auth_headers(workspace_1.id)
        tomorrow = datetime.now(UTC).replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        response = await client.get(
            "/api/v1/appointments/conflicts",
            headers=headers,
            params={
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow + timedelta(hours=1)).isoformat(),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_conflict"] is False
        assert data["conflicting_appointments"] == []

    async def test_conflict_check_with_conflict(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        sample_appointment_ws1: Appointment,
    ):
        """Conflict check with existing appointment returns has_conflict=True."""
        headers = get_auth_headers(workspace_1.id)

        # Check overlapping time
        start = sample_appointment_ws1.scheduled_start
        end = sample_appointment_ws1.scheduled_end

        response = await client.get(
            "/api/v1/appointments/conflicts",
            headers=headers,
            params={
                "scheduled_start": (start + timedelta(minutes=30)).isoformat(),
                "scheduled_end": (end + timedelta(minutes=30)).isoformat(),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_conflict"] is True
        assert len(data["conflicting_appointments"]) == 1
        assert data["conflicting_appointments"][0]["id"] == str(
            sample_appointment_ws1.id
        )

    async def test_conflict_check_excludes_appointment(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        sample_appointment_ws1: Appointment,
    ):
        """Conflict check can exclude specific appointment (for updates)."""
        headers = get_auth_headers(workspace_1.id)

        start = sample_appointment_ws1.scheduled_start
        end = sample_appointment_ws1.scheduled_end

        # Check same time but exclude the existing appointment
        response = await client.get(
            "/api/v1/appointments/conflicts",
            headers=headers,
            params={
                "scheduled_start": start.isoformat(),
                "scheduled_end": end.isoformat(),
                "exclude_appointment_id": str(sample_appointment_ws1.id),
            },
        )

        assert response.status_code == 200
        data = response.json()
        # Should not report conflict with itself
        assert data["has_conflict"] is False

    async def test_conflict_check_ignores_cancelled(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        cancelled_appointment_ws1: Appointment,
    ):
        """Conflict check ignores cancelled appointments."""
        headers = get_auth_headers(workspace_1.id)

        start = cancelled_appointment_ws1.scheduled_start
        end = cancelled_appointment_ws1.scheduled_end

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
        # Cancelled appointments don't cause conflicts
        assert data["has_conflict"] is False

    async def test_conflict_check_validates_time_range(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Conflict check validates that end is after start."""
        headers = get_auth_headers(workspace_1.id)
        tomorrow = datetime.now(UTC).replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        # End before start
        response = await client.get(
            "/api/v1/appointments/conflicts",
            headers=headers,
            params={
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow - timedelta(hours=1)).isoformat(),
            },
        )

        assert response.status_code == 422

    async def test_conflict_check_allows_back_to_back(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
    ):
        """Back-to-back appointments (end = next start) should NOT conflict."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
        tomorrow = datetime.now(UTC).replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        # Create first appointment: 10:00-11:00
        await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow + timedelta(hours=1)).isoformat(),
                "location_type": "clinic",
            },
        )

        # Check for conflict with back-to-back appointment: 11:00-12:00
        back_to_back_start = tomorrow + timedelta(hours=1)
        back_to_back_end = tomorrow + timedelta(hours=2)

        response = await client.get(
            "/api/v1/appointments/conflicts",
            headers=headers,
            params={
                "scheduled_start": back_to_back_start.isoformat(),
                "scheduled_end": back_to_back_end.isoformat(),
            },
        )

        assert response.status_code == 200
        data = response.json()
        # Back-to-back appointments should NOT cause conflicts
        assert data["has_conflict"] is False
        assert data["conflicting_appointments"] == []

    async def test_conflict_check_returns_client_initials(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
    ):
        """Conflict check returns privacy-preserving client initials, not full names."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
        tomorrow = datetime.now(UTC).replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        # Create appointment for John Doe
        await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow + timedelta(hours=1)).isoformat(),
                "location_type": "clinic",
            },
        )

        # Check overlapping time
        response = await client.get(
            "/api/v1/appointments/conflicts",
            headers=headers,
            params={
                "scheduled_start": (tomorrow + timedelta(minutes=30)).isoformat(),
                "scheduled_end": (
                    tomorrow + timedelta(hours=1, minutes=30)
                ).isoformat(),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_conflict"] is True
        assert len(data["conflicting_appointments"]) == 1

        # Verify client initials are returned (J.D. for John Doe)
        conflict = data["conflicting_appointments"][0]
        assert "client_initials" in conflict
        assert conflict["client_initials"] == "J.D."
        # Ensure full name is NOT exposed
        assert "first_name" not in conflict
        assert "last_name" not in conflict
        assert "full_name" not in conflict

    async def test_conflict_check_ignores_completed_appointments(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
    ):
        """Completed appointments still cause conflicts if times overlap."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
        tomorrow = datetime.now(UTC).replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        # Create and complete an appointment
        create_response = await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow + timedelta(hours=1)).isoformat(),
                "location_type": "clinic",
            },
        )
        appointment_id = create_response.json()["id"]

        # Mark as completed
        await client.put(
            f"/api/v1/appointments/{appointment_id}",
            headers=headers,
            json={"status": "completed"},
        )

        # Check overlapping time
        response = await client.get(
            "/api/v1/appointments/conflicts",
            headers=headers,
            params={
                "scheduled_start": (tomorrow + timedelta(minutes=30)).isoformat(),
                "scheduled_end": (
                    tomorrow + timedelta(hours=1, minutes=30)
                ).isoformat(),
            },
        )

        assert response.status_code == 200
        data = response.json()
        # Completed appointments should still cause conflicts
        assert data["has_conflict"] is True
