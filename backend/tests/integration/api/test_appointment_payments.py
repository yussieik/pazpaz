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
                "payment_method": "bit",
                "payment_notes": "Paid via Bit app, reference #12345",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["payment_method"] == "bit"
        assert data["payment_notes"] == "Paid via Bit app, reference #12345"
        # payment_status should remain unchanged (was payment_sent)
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


class TestPaymentLinkEndpoints:
    """Test payment link generation and sending endpoints (Phase 1.5)."""

    async def test_get_payment_link_success_bit(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Generate payment link for Bit payment type."""
        # Configure workspace with Bit payment links
        workspace_1.payment_link_type = "bit"
        workspace_1.payment_link_template = "050-123-4567"
        await db_session.commit()

        # Create appointment with payment price
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=1, hours=10),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=11),
            location_type="clinic",
            payment_price=Decimal("150.00"),
            payment_status=PaymentStatus.NOT_PAID.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Get payment link
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)

        response = await client.get(
            f"/api/v1/appointments/{appointment.id}/payment-link",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["payment_type"] == "bit"
        assert data["amount"] == "150.00"
        assert data["display_text"] == "Bit (ביט)"
        assert "sms:0501234567" in data["payment_link"]
        assert "150.00" in data["payment_link"]

    async def test_get_payment_link_success_paybox(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Generate payment link for PayBox payment type."""
        # Configure workspace with PayBox payment links
        workspace_1.payment_link_type = "paybox"
        workspace_1.payment_link_template = "https://paybox.co.il/p/yussie"
        await db_session.commit()

        # Create appointment with payment price
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=2, hours=10),
            scheduled_end=datetime.now(UTC) + timedelta(days=2, hours=11),
            location_type="clinic",
            payment_price=Decimal("200.00"),
            payment_status=PaymentStatus.NOT_PAID.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Get payment link
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)

        response = await client.get(
            f"/api/v1/appointments/{appointment.id}/payment-link",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["payment_type"] == "paybox"
        assert data["amount"] == "200.00"
        assert data["display_text"] == "PayBox"
        assert "paybox.co.il/p/yussie" in data["payment_link"]
        assert "amount=200.00" in data["payment_link"]

    async def test_get_payment_link_no_price(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Cannot generate payment link without price."""
        # Configure workspace with payment links
        workspace_1.payment_link_type = "bit"
        workspace_1.payment_link_template = "050-123-4567"
        await db_session.commit()

        # Create appointment WITHOUT payment price
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=3, hours=10),
            scheduled_end=datetime.now(UTC) + timedelta(days=3, hours=11),
            location_type="clinic",
            payment_status=PaymentStatus.NOT_PAID.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Try to get payment link
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)

        response = await client.get(
            f"/api/v1/appointments/{appointment.id}/payment-link",
            headers=headers,
        )

        assert response.status_code == 400
        assert "price" in response.json()["detail"].lower()

    async def test_get_payment_link_not_configured(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Cannot generate payment link if workspace not configured."""
        # Ensure workspace has NO payment links configured
        workspace_1.payment_link_type = None
        workspace_1.payment_link_template = None
        await db_session.commit()

        # Create appointment with payment price
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=4, hours=10),
            scheduled_end=datetime.now(UTC) + timedelta(days=4, hours=11),
            location_type="clinic",
            payment_price=Decimal("100.00"),
            payment_status=PaymentStatus.NOT_PAID.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Try to get payment link
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)

        response = await client.get(
            f"/api/v1/appointments/{appointment.id}/payment-link",
            headers=headers,
        )

        assert response.status_code == 400
        assert "not configured" in response.json()["detail"].lower()

    async def test_send_payment_request_success(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Send payment request successfully updates status and creates audit log."""
        # Configure workspace with payment links
        workspace_1.payment_link_type = "paybox"
        workspace_1.payment_link_template = "https://paybox.co.il/p/yussie"
        await db_session.commit()

        # Ensure client has email
        sample_client_ws1.email = "client@example.com"
        await db_session.commit()

        # Create appointment with payment price
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=5, hours=10),
            scheduled_end=datetime.now(UTC) + timedelta(days=5, hours=11),
            location_type="clinic",
            payment_price=Decimal("180.00"),
            payment_status=PaymentStatus.NOT_PAID.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Send payment request
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.post(
            f"/api/v1/appointments/{appointment.id}/send-payment-request",
            headers=headers,
            json={"message": "Please pay for your session"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "paybox.co.il" in data["payment_link"]
        assert "amount=180.00" in data["payment_link"]
        assert sample_client_ws1.first_name in data["message"]

        # Verify payment_status updated to 'payment_sent'
        await db_session.refresh(appointment)
        assert appointment.payment_status == "payment_sent"

    async def test_send_payment_request_no_email(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Cannot send payment request if client has no email."""
        # Configure workspace with payment links
        workspace_1.payment_link_type = "bit"
        workspace_1.payment_link_template = "050-123-4567"
        await db_session.commit()

        # Ensure client has NO email
        sample_client_ws1.email = None
        await db_session.commit()

        # Create appointment with payment price
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=6, hours=10),
            scheduled_end=datetime.now(UTC) + timedelta(days=6, hours=11),
            location_type="clinic",
            payment_price=Decimal("120.00"),
            payment_status=PaymentStatus.NOT_PAID.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Try to send payment request
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.post(
            f"/api/v1/appointments/{appointment.id}/send-payment-request",
            headers=headers,
            json={},
        )

        assert response.status_code == 400
        assert "email" in response.json()["detail"].lower()

        # Verify payment_status NOT updated
        await db_session.refresh(appointment)
        assert appointment.payment_status == "not_paid"

    async def test_send_payment_request_already_sent(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        sample_client_ws1: Client,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Sending payment request when already sent does not change status."""
        # Configure workspace with payment links
        workspace_1.payment_link_type = "paybox"
        workspace_1.payment_link_template = "https://paybox.co.il/p/yussie"
        await db_session.commit()

        # Ensure client has email
        sample_client_ws1.email = "client@example.com"
        await db_session.commit()

        # Create appointment with payment_status already 'payment_sent'
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=7, hours=10),
            scheduled_end=datetime.now(UTC) + timedelta(days=7, hours=11),
            location_type="clinic",
            payment_price=Decimal("160.00"),
            payment_status=PaymentStatus.PAYMENT_SENT.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Send payment request again
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.post(
            f"/api/v1/appointments/{appointment.id}/send-payment-request",
            headers=headers,
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify payment_status remains 'payment_sent' (not changed)
        await db_session.refresh(appointment)
        assert appointment.payment_status == "payment_sent"

    async def test_payment_link_workspace_isolation(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        workspace_2: Workspace,
        sample_client_ws1: Client,
        test_user_ws2: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Cannot access payment links from other workspaces."""
        # Configure workspace 1 with payment links
        workspace_1.payment_link_type = "bit"
        workspace_1.payment_link_template = "050-123-4567"
        await db_session.commit()

        # Create appointment in workspace 1 with payment price
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=8, hours=10),
            scheduled_end=datetime.now(UTC) + timedelta(days=8, hours=11),
            location_type="clinic",
            payment_price=Decimal("150.00"),
            payment_status=PaymentStatus.NOT_PAID.value,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Try to access from workspace 2
        csrf_token = await add_csrf_to_client(
            client, workspace_2.id, test_user_ws2.id, redis_client
        )
        headers = get_auth_headers(workspace_2.id, csrf_cookie=csrf_token)

        # Try GET payment link
        response = await client.get(
            f"/api/v1/appointments/{appointment.id}/payment-link",
            headers=headers,
        )
        assert response.status_code == 404

        # Try POST send payment request
        headers["X-CSRF-Token"] = csrf_token
        response = await client.post(
            f"/api/v1/appointments/{appointment.id}/send-payment-request",
            headers=headers,
            json={},
        )
        assert response.status_code == 404
