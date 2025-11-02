"""Test Manual Payment Tracking endpoints (Phase 1).

This module tests the new PATCH /api/v1/appointments/{id}/payment endpoint
for manual payment tracking. Tests the PaymentService methods:
- mark_as_paid()
- mark_as_unpaid()
- update_payment_price()
"""

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


class TestMarkAppointmentAsPaid:
    """Test PATCH /api/v1/appointments/{id}/payment - marking as paid."""

    async def test_mark_appointment_as_paid_basic(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Mark unpaid appointment as paid using PATCH /payment endpoint."""
        # Create unpaid appointment
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

        # Mark as paid via PATCH endpoint
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        before_update = datetime.now(UTC)
        response = await client.patch(
            f"/api/v1/appointments/{appointment.id}/payment",
            headers=headers,
            json={
                "payment_status": "paid",
                "payment_method": "cash",
            },
        )
        after_update = datetime.now(UTC)

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["payment_status"] == "paid"
        assert data["payment_method"] == "cash"
        assert data["paid_at"] is not None

        # Verify paid_at is within reasonable timeframe (auto-set)
        paid_at = datetime.fromisoformat(data["paid_at"].replace("Z", "+00:00"))
        assert before_update <= paid_at <= after_update

    async def test_mark_as_paid_with_explicit_paid_at(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Mark appointment as paid with explicit paid_at timestamp."""
        # Create appointment
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=2, hours=14),
            scheduled_end=datetime.now(UTC) + timedelta(days=2, hours=15),
            location_type="home",
            payment_price=Decimal("150.00"),
            payment_status=PaymentStatus.NOT_PAID.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Mark as paid with explicit paid_at (e.g., payment received yesterday)
        explicit_paid_at = datetime.now(UTC) - timedelta(days=1)
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.patch(
            f"/api/v1/appointments/{appointment.id}/payment",
            headers=headers,
            json={
                "payment_status": "paid",
                "payment_method": "bank_transfer",
                "paid_at": explicit_paid_at.isoformat(),
            },
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["payment_status"] == "paid"
        assert data["payment_method"] == "bank_transfer"

        # Verify explicit paid_at was used
        returned_paid_at = datetime.fromisoformat(
            data["paid_at"].replace("Z", "+00:00")
        )
        assert abs((returned_paid_at - explicit_paid_at).total_seconds()) < 1

    async def test_mark_as_paid_with_all_payment_fields(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Mark as paid with price, method, notes, and paid_at."""
        # Create appointment without payment info
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=3, hours=10),
            scheduled_end=datetime.now(UTC) + timedelta(days=3, hours=11),
            location_type="online",
            payment_price=None,
            payment_status=PaymentStatus.NOT_PAID.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Mark as paid with all fields
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.patch(
            f"/api/v1/appointments/{appointment.id}/payment",
            headers=headers,
            json={
                "payment_status": "paid",
                "payment_method": "card",
                "payment_price": "175.50",
                "payment_notes": "Invoice #12345, paid via debit card",
            },
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["payment_status"] == "paid"
        assert data["payment_method"] == "card"
        assert data["payment_price"] == "175.50"
        assert data["payment_notes"] == "Invoice #12345, paid via debit card"
        assert data["paid_at"] is not None


class TestMarkAppointmentAsUnpaid:
    """Test PATCH /api/v1/appointments/{id}/payment - marking as unpaid."""

    async def test_mark_paid_appointment_as_unpaid(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Revert paid appointment to unpaid (e.g., payment reversed)."""
        # Create paid appointment
        paid_at_time = datetime.now(UTC) - timedelta(hours=2)
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=1, hours=14),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=15),
            location_type="clinic",
            payment_price=Decimal("180.00"),
            payment_status=PaymentStatus.PAID.value,
            payment_method=PaymentMethod.CASH.value,
            paid_at=paid_at_time,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Mark as unpaid
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.patch(
            f"/api/v1/appointments/{appointment.id}/payment",
            headers=headers,
            json={
                "payment_status": "not_paid",
            },
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["payment_status"] == "not_paid"
        assert data["paid_at"] is None  # Should be cleared
        assert data["payment_method"] is None  # Should be cleared
        assert data["payment_price"] == "180.00"  # Price preserved


class TestUpdatePaymentPrice:
    """Test PATCH /api/v1/appointments/{id}/payment - updating price."""

    async def test_update_payment_price(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Update payment price via PATCH endpoint."""
        # Create appointment with price
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=1, hours=16),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=17),
            location_type="clinic",
            payment_price=Decimal("150.00"),
            payment_status=PaymentStatus.NOT_PAID.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Update price
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.patch(
            f"/api/v1/appointments/{appointment.id}/payment",
            headers=headers,
            json={
                "payment_status": "not_paid",  # Required field
                "payment_price": "175.00",
            },
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["payment_price"] == "175.00"
        assert data["payment_status"] == "not_paid"


class TestPaymentStatusOtherStates:
    """Test PATCH /api/v1/appointments/{id}/payment - other payment states."""

    async def test_mark_as_waived(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Mark payment as waived (pro bono, scholarship)."""
        # Create appointment
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=2, hours=10),
            scheduled_end=datetime.now(UTC) + timedelta(days=2, hours=11),
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

        response = await client.patch(
            f"/api/v1/appointments/{appointment.id}/payment",
            headers=headers,
            json={
                "payment_status": "waived",
                "payment_notes": "Pro bono session - scholarship program",
            },
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["payment_status"] == "waived"
        assert data["payment_notes"] == "Pro bono session - scholarship program"
        assert data["paid_at"] is None  # Waived doesn't set paid_at

    async def test_mark_as_payment_sent(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Mark as payment_sent (payment link sent to client)."""
        # Create appointment
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=3, hours=15),
            scheduled_end=datetime.now(UTC) + timedelta(days=3, hours=16),
            location_type="online",
            payment_price=Decimal("120.00"),
            payment_status=PaymentStatus.NOT_PAID.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Mark as payment_sent
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.patch(
            f"/api/v1/appointments/{appointment.id}/payment",
            headers=headers,
            json={
                "payment_status": "payment_sent",
                "payment_method": "bit",
                "payment_notes": "Bit payment link sent via WhatsApp",
            },
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["payment_status"] == "payment_sent"
        assert data["payment_method"] == "bit"
        assert data["payment_notes"] == "Bit payment link sent via WhatsApp"


class TestPaymentWorkspaceIsolation:
    """Test workspace isolation for payment updates."""

    async def test_cannot_update_payment_from_other_workspace(
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
        """Cannot update payment status from other workspace."""
        # Create appointment in workspace 1
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=1, hours=10),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=11),
            location_type="clinic",
            payment_price=Decimal("250.00"),
            payment_status=PaymentStatus.NOT_PAID.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Try to update from workspace 2
        csrf_token = await add_csrf_to_client(
            client, workspace_2.id, test_user_ws2.id, redis_client
        )
        headers = get_auth_headers(workspace_2.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.patch(
            f"/api/v1/appointments/{appointment.id}/payment",
            headers=headers,
            json={
                "payment_status": "paid",
                "payment_method": "cash",
            },
        )

        # Should get 404 (not found due to workspace scoping)
        assert response.status_code == 404

        # Verify appointment payment status unchanged
        query = select(Appointment).where(Appointment.id == appointment.id)
        result = await db_session.execute(query)
        refreshed_appointment = result.scalar_one()
        assert refreshed_appointment.payment_status == PaymentStatus.NOT_PAID.value


class TestPaymentAuthentication:
    """Test authentication requirements for payment endpoints."""

    async def test_patch_payment_requires_authentication(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        db_session: AsyncSession,
    ):
        """PATCH /payment requires authentication."""
        # Create appointment
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=1, hours=10),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=11),
            location_type="clinic",
            payment_price=Decimal("100.00"),
            payment_status=PaymentStatus.NOT_PAID.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Try without authentication
        response = await client.patch(
            f"/api/v1/appointments/{appointment.id}/payment",
            json={
                "payment_status": "paid",
                "payment_method": "cash",
            },
        )

        # Should get 403 Forbidden (CSRF protection before auth check)
        assert response.status_code == 403
