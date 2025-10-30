"""Test Payment Configuration API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.user import User
from pazpaz.models.workspace import Workspace
from tests.conftest import add_csrf_to_client, get_auth_headers

pytestmark = pytest.mark.asyncio


class TestGetPaymentConfig:
    """Test GET /api/v1/payments/config endpoint."""

    async def test_get_config_payments_disabled(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Test getting payment config when payments are disabled."""
        # Ensure workspace has payments disabled
        workspace_1.payment_provider = None
        workspace_1.payment_auto_send = False
        workspace_1.payment_send_timing = "immediately"
        workspace_1.business_name = None
        workspace_1.vat_registered = False
        db_session.add(workspace_1)
        await db_session.commit()
        await db_session.refresh(workspace_1)

        # Authenticate
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)

        # Request
        response = await client.get(
            "/api/v1/payments/config",
            headers=headers,
        )

        # Verify
        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "enabled" in data
        assert "provider" in data
        assert "auto_send" in data
        assert "send_timing" in data
        assert "business_name" in data
        assert "vat_registered" in data

        # Verify values (payments disabled)
        assert data["enabled"] is False
        assert data["provider"] is None
        assert data["auto_send"] is False
        assert data["send_timing"] == "immediately"
        assert data["business_name"] is None
        assert data["vat_registered"] is False

    async def test_get_config_payments_enabled_payplus(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Test getting payment config when payments are enabled with PayPlus."""
        # Enable payments for workspace
        workspace_1.payment_provider = "payplus"
        workspace_1.payment_auto_send = True
        workspace_1.payment_send_timing = "end_of_day"
        workspace_1.business_name = "Example Therapy Clinic"
        workspace_1.vat_registered = True
        db_session.add(workspace_1)
        await db_session.commit()
        await db_session.refresh(workspace_1)

        # Authenticate
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)

        # Request
        response = await client.get(
            "/api/v1/payments/config",
            headers=headers,
        )

        # Verify
        assert response.status_code == 200
        data = response.json()

        # Verify values (payments enabled)
        assert data["enabled"] is True
        assert data["provider"] == "payplus"
        assert data["auto_send"] is True
        assert data["send_timing"] == "end_of_day"
        assert data["business_name"] == "Example Therapy Clinic"
        assert data["vat_registered"] is True

    async def test_get_config_payments_enabled_meshulam(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Test getting payment config with different provider (Meshulam)."""
        # Enable payments with Meshulam
        workspace_1.payment_provider = "meshulam"
        workspace_1.payment_auto_send = False
        workspace_1.payment_send_timing = "manual"
        workspace_1.business_name = "Professional Services Ltd"
        workspace_1.vat_registered = False
        db_session.add(workspace_1)
        await db_session.commit()
        await db_session.refresh(workspace_1)

        # Authenticate
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)

        # Request
        response = await client.get(
            "/api/v1/payments/config",
            headers=headers,
        )

        # Verify
        assert response.status_code == 200
        data = response.json()

        assert data["enabled"] is True
        assert data["provider"] == "meshulam"
        assert data["auto_send"] is False
        assert data["send_timing"] == "manual"
        assert data["business_name"] == "Professional Services Ltd"
        assert data["vat_registered"] is False

    async def test_get_config_requires_authentication(
        self,
        client: AsyncClient,
    ):
        """Test that endpoint requires authentication."""
        # Request without authentication
        response = await client.get("/api/v1/payments/config")

        # Verify 401 Unauthorized
        assert response.status_code == 401

    async def test_get_config_workspace_isolation(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        workspace_2: Workspace,
        test_user_ws1: User,
        test_user_ws2: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Test workspace isolation - therapist A cannot see therapist B's config."""
        # Configure workspace 1 with payments disabled
        workspace_1.payment_provider = None
        workspace_1.business_name = None
        db_session.add(workspace_1)

        # Configure workspace 2 with payments enabled
        workspace_2.payment_provider = "payplus"
        workspace_2.business_name = "Workspace 2 Business"
        workspace_2.vat_registered = True
        db_session.add(workspace_2)

        await db_session.commit()
        await db_session.refresh(workspace_1)
        await db_session.refresh(workspace_2)

        # ===================================================================
        # Test 1: User from workspace 1 gets workspace 1 config
        # ===================================================================
        csrf_token_ws1 = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers_ws1 = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token_ws1)

        response_ws1 = await client.get(
            "/api/v1/payments/config",
            headers=headers_ws1,
        )

        assert response_ws1.status_code == 200
        data_ws1 = response_ws1.json()
        assert data_ws1["enabled"] is False
        assert data_ws1["provider"] is None
        assert data_ws1["business_name"] is None

        # ===================================================================
        # Test 2: User from workspace 2 gets workspace 2 config
        # ===================================================================
        csrf_token_ws2 = await add_csrf_to_client(
            client, workspace_2.id, test_user_ws2.id, redis_client
        )
        headers_ws2 = get_auth_headers(workspace_2.id, csrf_cookie=csrf_token_ws2)

        response_ws2 = await client.get(
            "/api/v1/payments/config",
            headers=headers_ws2,
        )

        assert response_ws2.status_code == 200
        data_ws2 = response_ws2.json()
        assert data_ws2["enabled"] is True
        assert data_ws2["provider"] == "payplus"
        assert data_ws2["business_name"] == "Workspace 2 Business"
        assert data_ws2["vat_registered"] is True

        # ===================================================================
        # Verify isolation: configs are different and workspace-scoped
        # ===================================================================
        assert data_ws1["enabled"] != data_ws2["enabled"]
        assert data_ws1["provider"] != data_ws2["provider"]
        assert data_ws1["business_name"] != data_ws2["business_name"]

    async def test_get_config_does_not_expose_api_keys(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Test that payment provider config (API keys) is never exposed."""
        # Configure workspace with payment provider and config
        workspace_1.payment_provider = "payplus"
        workspace_1.payment_provider_config = {
            "api_key": "super-secret-api-key-12345",
            "payment_page_uid": "secret-uid",
            "webhook_secret": "webhook-secret-67890",
        }
        db_session.add(workspace_1)
        await db_session.commit()
        await db_session.refresh(workspace_1)

        # Authenticate
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)

        # Request
        response = await client.get(
            "/api/v1/payments/config",
            headers=headers,
        )

        # Verify
        assert response.status_code == 200
        data = response.json()

        # Verify API keys are NOT in response
        assert "payment_provider_config" not in data
        assert "api_key" not in str(data)
        assert "super-secret-api-key" not in str(data)
        assert "webhook_secret" not in str(data)

        # Verify only safe fields returned
        assert data["enabled"] is True
        assert data["provider"] == "payplus"

    async def test_get_config_all_send_timing_options(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Test all payment_send_timing options."""
        send_timings = ["immediately", "end_of_day", "end_of_month", "manual"]

        for timing in send_timings:
            # Update workspace
            workspace_1.payment_provider = "payplus"
            workspace_1.payment_send_timing = timing
            db_session.add(workspace_1)
            await db_session.commit()
            await db_session.refresh(workspace_1)

            # Authenticate
            csrf_token = await add_csrf_to_client(
                client, workspace_1.id, test_user_ws1.id, redis_client
            )
            headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)

            # Request
            response = await client.get(
                "/api/v1/payments/config",
                headers=headers,
            )

            # Verify
            assert response.status_code == 200
            data = response.json()
            assert data["send_timing"] == timing, f"send_timing should be {timing}"

    async def test_get_config_with_hebrew_business_name(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Test payment config with Hebrew business name (Unicode support)."""
        # Configure workspace with Hebrew business name
        workspace_1.payment_provider = "payplus"
        workspace_1.business_name = "טיפול מקצועי"
        workspace_1.business_name_hebrew = "טיפול מקצועי בע״מ"
        db_session.add(workspace_1)
        await db_session.commit()
        await db_session.refresh(workspace_1)

        # Authenticate
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)

        # Request
        response = await client.get(
            "/api/v1/payments/config",
            headers=headers,
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["business_name"] == "טיפול מקצועי"

    async def test_get_config_response_format(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Test response format matches PaymentConfigResponse schema."""
        # Configure workspace
        workspace_1.payment_provider = "payplus"
        db_session.add(workspace_1)
        await db_session.commit()

        # Authenticate
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)

        # Request
        response = await client.get(
            "/api/v1/payments/config",
            headers=headers,
        )

        # Verify
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        data = response.json()

        # Verify all required fields present
        required_fields = [
            "enabled",
            "provider",
            "auto_send",
            "send_timing",
            "business_name",
            "vat_registered",
        ]
        for field in required_fields:
            assert field in data, f"Required field {field} missing from response"

        # Verify field types
        assert isinstance(data["enabled"], bool)
        assert isinstance(data["provider"], (str, type(None)))
        assert isinstance(data["auto_send"], bool)
        assert isinstance(data["send_timing"], str)
        assert isinstance(data["business_name"], (str, type(None)))
        assert isinstance(data["vat_registered"], bool)
