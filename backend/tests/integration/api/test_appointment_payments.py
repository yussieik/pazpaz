"""Test payment tracking functionality in Appointment API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.appointment import Appointment
from pazpaz.models.client import Client
from pazpaz.models.enums import PaymentMethod, PaymentStatus
from pazpaz.models.user import User
from pazpaz.models.workspace import Workspace
from tests.conftest import add_csrf_to_client, get_auth_headers

pytestmark = pytest.mark.asyncio


class TestAppointmentPaymentCreation:
    """Test creating appointments with payment fields."""

    async def test_create_appointment_with_payment_fields(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
    ):
        """Create appointment with full payment information."""
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
                "payment_price": "150.00",
                "payment_status": "not_paid",
                "payment_method": "cash",
                "payment_notes": "Payment expected at end of session",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["payment_price"] == "150.00"
        assert data["payment_status"] == "not_paid"
        assert data["payment_method"] == "cash"
        assert data["payment_notes"] == "Payment expected at end of session"
        assert data["paid_at"] is None

    async def test_create_appointment_with_minimal_payment_info(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
    ):
        """Create appointment with only price, defaults to not_paid."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token
        tomorrow = datetime.now(UTC).replace(
            hour=15, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        response = await client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "client_id": str(sample_client_ws1.id),
                "scheduled_start": tomorrow.isoformat(),
                "scheduled_end": (tomorrow + timedelta(hours=1)).isoformat(),
                "location_type": "online",
                "payment_price": "100.00",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["payment_price"] == "100.00"
        assert data["payment_status"] == "not_paid"
        assert data["payment_method"] is None
        assert data["payment_notes"] is None
        assert data["paid_at"] is None

    async def test_create_appointment_without_payment_info(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
    ):
        """Create appointment without payment info, defaults to not_paid."""
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
                "location_type": "clinic",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["payment_price"] is None
        assert data["payment_status"] == "not_paid"
        assert data["payment_method"] is None
        assert data["payment_notes"] is None
        assert data["paid_at"] is None


class TestAppointmentPaymentUpdate:
    """Test updating payment fields on appointments."""

    async def test_update_payment_status_to_paid_auto_sets_paid_at(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """When marking payment as paid, paid_at should be auto-set."""
        # Create appointment
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=1, hours=10),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=11),
            location_type="clinic",
            payment_price=Decimal("200.00"),
            payment_status=PaymentStatus.NOT_PAID.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Update payment status to paid
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        before_update = datetime.now(UTC)
        response = await client.put(
            f"/api/v1/appointments/{appointment.id}",
            headers=headers,
            json={
                "payment_status": "paid",
                "payment_method": "cash",
            },
        )
        after_update = datetime.now(UTC)

        assert response.status_code == 200
        data = response.json()
        assert data["payment_status"] == "paid"
        assert data["payment_method"] == "cash"
        assert data["paid_at"] is not None

        # Verify paid_at is within reasonable timeframe
        paid_at = datetime.fromisoformat(data["paid_at"].replace("Z", "+00:00"))
        assert before_update <= paid_at <= after_update

    async def test_update_payment_status_with_explicit_paid_at(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """When providing explicit paid_at, it should be used."""
        # Create appointment
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=2, hours=10),
            scheduled_end=datetime.now(UTC) + timedelta(days=2, hours=11),
            location_type="clinic",
            payment_price=Decimal("150.00"),
            payment_status=PaymentStatus.NOT_PAID.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Update with explicit paid_at
        explicit_paid_at = datetime.now(UTC) - timedelta(hours=2)
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.put(
            f"/api/v1/appointments/{appointment.id}",
            headers=headers,
            json={
                "payment_status": "paid",
                "payment_method": "card",
                "paid_at": explicit_paid_at.isoformat(),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["payment_status"] == "paid"
        assert data["payment_method"] == "card"
        returned_paid_at = datetime.fromisoformat(
            data["paid_at"].replace("Z", "+00:00")
        )
        # Allow for slight timestamp differences
        assert abs((returned_paid_at - explicit_paid_at).total_seconds()) < 1

    async def test_update_payment_method_and_notes(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Update payment method and notes independently."""
        # Create appointment with payment
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=3, hours=10),
            scheduled_end=datetime.now(UTC) + timedelta(days=3, hours=11),
            location_type="home",
            payment_price=Decimal("180.00"),
            payment_status=PaymentStatus.PAYMENT_SENT.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Update payment details
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.put(
            f"/api/v1/appointments/{appointment.id}",
            headers=headers,
            json={
                "payment_method": "payment_link",
                "payment_notes": "PayPlus invoice #12345, sent via email",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["payment_method"] == "payment_link"
        assert data["payment_notes"] == "PayPlus invoice #12345, sent via email"
        assert data["payment_status"] == "payment_sent"

    async def test_payment_status_waived(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Mark payment as waived (pro bono, scholarship, etc.)."""
        # Create appointment
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=4, hours=14),
            scheduled_end=datetime.now(UTC) + timedelta(days=4, hours=15),
            location_type="clinic",
            payment_price=Decimal("100.00"),
            payment_status=PaymentStatus.NOT_PAID.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Waive payment
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.put(
            f"/api/v1/appointments/{appointment.id}",
            headers=headers,
            json={
                "payment_status": "waived",
                "payment_notes": "Pro bono session - scholarship program",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["payment_status"] == "waived"
        assert data["payment_notes"] == "Pro bono session - scholarship program"
        assert data["paid_at"] is None  # Waived doesn't require paid_at

    async def test_payment_independent_of_appointment_status(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Payment status should be independent of appointment status."""
        # Create scheduled appointment
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=5, hours=10),
            scheduled_end=datetime.now(UTC) + timedelta(days=5, hours=11),
            location_type="clinic",
            payment_price=Decimal("120.00"),
            payment_status=PaymentStatus.NOT_PAID.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Mark as paid while still scheduled
        response = await client.put(
            f"/api/v1/appointments/{appointment.id}",
            headers=headers,
            json={
                "payment_status": "paid",
                "payment_method": "bank_transfer",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "scheduled"  # Appointment status unchanged
        assert data["payment_status"] == "paid"
        assert data["payment_method"] == "bank_transfer"


class TestPaymentWorkspaceIsolation:
    """Test workspace isolation for payment data."""

    async def test_cannot_access_payment_data_from_other_workspace(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        workspace_2: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        test_user_ws2: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Cannot view or modify payment data from other workspaces."""
        # Create appointment in workspace 1 with payment info
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=1, hours=10),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=11),
            location_type="clinic",
            payment_price=Decimal("250.00"),
            payment_status=PaymentStatus.PAID.value,
            payment_method=PaymentMethod.CASH.value,
            paid_at=datetime.now(UTC),
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Try to access from workspace 2
        csrf_token = await add_csrf_to_client(
            client, workspace_2.id, test_user_ws2.id, redis_client
        )
        headers = get_auth_headers(workspace_2.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Should get 404 (not found)
        response = await client.get(
            f"/api/v1/appointments/{appointment.id}",
            headers=headers,
        )
        assert response.status_code == 404

        # Try to update payment from workspace 2 - should also get 404
        response = await client.put(
            f"/api/v1/appointments/{appointment.id}",
            headers=headers,
            json={"payment_status": "not_paid"},
        )
        assert response.status_code == 404

        # Verify appointment payment data unchanged in workspace 1
        query = select(Appointment).where(Appointment.id == appointment.id)
        result = await db_session.execute(query)
        refreshed_appointment = result.scalar_one()
        assert refreshed_appointment.payment_status == PaymentStatus.PAID.value
        assert refreshed_appointment.payment_method == PaymentMethod.CASH.value
        assert refreshed_appointment.paid_at is not None
