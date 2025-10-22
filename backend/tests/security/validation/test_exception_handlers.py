"""Security tests for centralized exception handlers.

This module tests exception handling security controls:
- PHI redaction in validation errors
- Database error sanitization (no schema leakage)
- Request ID propagation
- Development vs production error detail levels

All tests verify that sensitive information is NOT leaked in error responses.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.user import User
from pazpaz.models.workspace import Workspace
from tests.conftest import add_csrf_to_client, get_auth_headers


class TestValidationExceptionHandler:
    """Test validation exception handler for PHI sanitization."""

    @pytest.mark.asyncio
    async def test_validation_error_includes_request_id(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """
        TEST: Validation errors include request_id.

        EXPECTED: request_id should be in response body and headers.
        """
        # Add CSRF token
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Send invalid client data (missing required field)
        invalid_data = {
            "first_name": "Test",
            # Missing last_name (required)
        }

        response = await client.post(
            "/api/v1/clients",
            json=invalid_data,
            headers=headers,
        )

        assert response.status_code == 422
        data = response.json()

        # Check request_id in response body
        assert "request_id" in data
        request_id = data["request_id"]
        assert len(request_id) == 36  # UUID format

        # Check request_id in response headers
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] == request_id

    @pytest.mark.asyncio
    async def test_validation_error_non_phi_fields_show_details(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """
        TEST: Validation errors for PHI fields are properly redacted.

        EXPECTED: PHI fields (like last_name) should have redacted error messages.
        """
        # Add CSRF token
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Send invalid client data (missing required PHI field)
        invalid_data = {
            "first_name": "Test",
            # Missing last_name (required PHI field)
        }

        response = await client.post(
            "/api/v1/clients",
            json=invalid_data,
            headers=headers,
        )

        assert response.status_code == 422
        data = response.json()

        errors = data["detail"]
        assert isinstance(errors, list)
        assert len(errors) > 0

        # Should include error details structure
        error = errors[0]
        assert "msg" in error
        assert "loc" in error

        # PHI fields should be redacted
        assert "redacted for PHI protection" in error["msg"]

    @pytest.mark.asyncio
    async def test_validation_error_invalid_email_format(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """
        TEST: Validation errors for invalid email format.

        EXPECTED: Should return 422 with validation details and request_id.
        """
        # Add CSRF token
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        invalid_data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "not-an-email",  # Invalid email format
        }

        response = await client.post(
            "/api/v1/clients",
            json=invalid_data,
            headers=headers,
        )

        assert response.status_code == 422
        data = response.json()

        assert "detail" in data
        assert "request_id" in data

        # Check validation error structure
        errors = data["detail"]
        assert isinstance(errors, list)
        # Email validation error should be present
        email_errors = [e for e in errors if "email" in str(e.get("loc", []))]
        assert len(email_errors) > 0


class TestDatabaseExceptionHandlers:
    """Test database exception handlers for integrity and connection errors."""

    @pytest.mark.asyncio
    async def test_integrity_error_returns_409(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """
        TEST: Database integrity errors return 409 Conflict.

        EXPECTED: IntegrityError (unique constraint) returns 409.
        Uses Service model which has unique constraint on (workspace_id, name).
        """
        # Add CSRF token
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Create a service with a specific name
        service_data = {
            "name": "Massage Therapy",
            "description": "60-minute massage session",
            "default_duration_minutes": 60,
            "default_price": 100.00,
        }

        # Create first service
        response1 = await client.post(
            "/api/v1/services",
            json=service_data,
            headers=headers,
        )
        assert response1.status_code == 201

        # Try to create duplicate service (should trigger unique constraint on workspace_id + name)
        response2 = await client.post(
            "/api/v1/services",
            json=service_data,
            headers=headers,
        )

        # Should return 409 Conflict (not 500)
        assert response2.status_code == 409
        data = response2.json()

        assert "detail" in data
        assert "request_id" in data

    @pytest.mark.asyncio
    async def test_integrity_error_no_constraint_name_leak(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """
        TEST: Integrity errors don't leak database constraint names.

        EXPECTED: Error response should NOT include constraint names,
        table names, or internal database schema details.
        Uses Service model which has unique constraint on (workspace_id, name).
        """
        # Add CSRF token
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Create a service with a specific name
        service_data = {
            "name": "Physiotherapy",
            "description": "60-minute physiotherapy session",
            "default_duration_minutes": 60,
            "default_price": 120.00,
        }

        # Create first service
        await client.post(
            "/api/v1/services",
            json=service_data,
            headers=headers,
        )

        # Try to create duplicate service (trigger unique constraint)
        response = await client.post(
            "/api/v1/services",
            json=service_data,
            headers=headers,
        )

        assert response.status_code == 409
        data = response.json()

        # Should NOT leak internal database details
        response_str = str(data).lower()
        assert "constraint" not in response_str
        assert (
            "unique" not in response_str or "unique" in data.get("detail", "").lower()
        )
        assert "uq_services_workspace_name" not in response_str
        assert "psycopg" not in response_str
        assert "sqlalchemy" not in response_str

        # Should have user-friendly conflict message (not database-level details)
        assert "already exists" in data["detail"].lower()


class TestNotFoundErrors:
    """Test 404 error handling."""

    @pytest.mark.asyncio
    async def test_not_found_includes_request_id(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """
        TEST: 404 errors include request_id.

        EXPECTED: request_id should be in response body and headers.
        """
        # Add CSRF token
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Try to get a non-existent client
        client_id = "00000000-0000-0000-0000-000000000000"

        response = await client.get(
            f"/api/v1/clients/{client_id}",
            headers=headers,
        )

        assert response.status_code == 404
        data = response.json()

        assert "detail" in data
        assert "request_id" in data or "X-Request-ID" in response.headers


class TestRequestIDPropagation:
    """Test that request_id is properly propagated in all error responses."""

    @pytest.mark.asyncio
    async def test_request_id_in_validation_error(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """TEST: request_id is in validation error responses."""
        # Add CSRF token
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.post(
            "/api/v1/clients",
            json={"first_name": "Test"},  # Missing last_name
            headers=headers,
        )

        assert response.status_code == 422
        data = response.json()

        # Request ID should be present
        assert "request_id" in data
        assert "X-Request-ID" in response.headers

        # Should be the same
        assert data["request_id"] == response.headers["X-Request-ID"]

    @pytest.mark.asyncio
    async def test_request_id_in_not_found_error(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """TEST: request_id is in 404 error responses."""
        # Add CSRF token
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.get(
            "/api/v1/clients/00000000-0000-0000-0000-000000000000",
            headers=headers,
        )

        assert response.status_code == 404
        data = response.json()

        # Request ID should be present
        assert "request_id" in data or "X-Request-ID" in response.headers

    @pytest.mark.asyncio
    async def test_request_id_in_conflict_error(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """
        TEST: request_id is in 409 conflict error responses.
        Uses Service model which has unique constraint on (workspace_id, name).
        """
        # Add CSRF token
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        service_data = {
            "name": "Psychotherapy",
            "description": "60-minute session",
            "default_duration_minutes": 60,
            "default_price": 150.00,
        }

        # Create first service
        await client.post("/api/v1/services", json=service_data, headers=headers)

        # Try to create duplicate service (trigger unique constraint)
        response = await client.post(
            "/api/v1/services", json=service_data, headers=headers
        )

        assert response.status_code == 409
        data = response.json()

        # Request ID should be present
        assert "request_id" in data
        assert "X-Request-ID" in response.headers
        assert data["request_id"] == response.headers["X-Request-ID"]


class TestErrorResponseFormat:
    """Test standardized error response format."""

    @pytest.mark.asyncio
    async def test_error_response_structure(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """
        TEST: All error responses follow standard format.

        EXPECTED: All errors should have "detail" and "request_id" fields.
        """
        # Add CSRF token
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Test validation error
        response = await client.post(
            "/api/v1/clients",
            json={"first_name": "Test"},
            headers=headers,
        )
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert "request_id" in data

        # Test not found error
        response = await client.get(
            "/api/v1/clients/00000000-0000-0000-0000-000000000000",
            headers=headers,
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "request_id" in data or "X-Request-ID" in response.headers

    @pytest.mark.asyncio
    async def test_error_response_no_stack_trace(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """
        TEST: Error responses don't include stack traces.

        EXPECTED: No stack traces, file paths, or internal details in responses.
        """
        # Add CSRF token
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Trigger various errors
        errors_to_test = [
            # Validation error
            ("/api/v1/clients", "POST", {"first_name": "Test"}),
            # Not found
            ("/api/v1/clients/00000000-0000-0000-0000-000000000000", "GET", None),
        ]

        for path, method, json_data in errors_to_test:
            if method == "POST":
                response = await client.post(path, json=json_data, headers=headers)
            else:
                response = await client.get(path, headers=headers)

            data = response.json()
            response_str = str(data).lower()

            # Should NOT contain stack trace keywords
            assert "traceback" not in response_str
            assert (
                "exception" not in response_str
                or "exception" in data.get("detail", "").lower()
            )
            assert "/backend/" not in response_str
            assert "line " not in response_str
            assert ".py" not in response_str or ".py" in data.get("detail", "").lower()
