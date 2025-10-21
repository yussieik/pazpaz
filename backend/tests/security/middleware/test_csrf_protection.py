"""Test CSRF protection middleware and implementation."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.middleware.csrf import generate_csrf_token, validate_csrf_token
from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace

pytestmark = pytest.mark.asyncio


class TestCSRFMiddleware:
    """Test CSRF protection middleware."""

    async def test_get_request_bypasses_csrf_check(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
    ):
        """GET requests should bypass CSRF validation."""
        # Make GET request without CSRF token
        response = await client.get("/api/v1/health")

        assert response.status_code == 200

    async def test_head_request_bypasses_csrf_check(
        self,
        client: AsyncClient,
    ):
        """HEAD requests should bypass CSRF validation."""
        # Make HEAD request without CSRF token
        response = await client.head("/api/v1/health")

        # HEAD may not be supported (405), but shouldn't be CSRF rejected (403)
        assert response.status_code != 403

    async def test_options_request_bypasses_csrf_check(
        self,
        client: AsyncClient,
    ):
        """OPTIONS requests should bypass CSRF validation."""
        # Make OPTIONS request without CSRF token
        response = await client.options("/api/v1/health")

        # OPTIONS may not be supported (405), but shouldn't be CSRF rejected (403)
        assert response.status_code != 403

    async def test_docs_endpoints_exempt_from_csrf(
        self,
        client: AsyncClient,
    ):
        """Documentation endpoints should be exempt from CSRF validation."""
        # OpenAPI docs
        response = await client.get("/api/v1/openapi.json")
        assert response.status_code == 200

    async def test_post_without_csrf_token_returns_403(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """POST request without CSRF token should return 403."""
        # Note: /auth/magic-link is exempt (entry point for authentication)
        # Test with a protected endpoint instead (logout requires CSRF)

        # Attempt POST to logout without CSRF token
        try:
            response = await client.post("/api/v1/auth/logout")
            # Middleware should return 403
            assert response.status_code == 403
            assert "CSRF token missing" in response.json()["detail"]
        except Exception as e:
            # In some test configurations, exception might be raised
            assert "CSRF token missing" in str(e)

    async def test_post_with_missing_csrf_header_returns_403(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """POST request with cookie but no header should return 403."""
        # Set CSRF cookie but don't include header
        client.cookies.set("csrf_token", "test-token-value")

        try:
            response = await client.post("/api/v1/auth/logout")
            assert response.status_code == 403
            assert "CSRF token missing" in response.json()["detail"]
        except Exception as e:
            assert "CSRF token missing" in str(e)

    async def test_post_with_missing_csrf_cookie_returns_403(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """POST request with header but no cookie should return 403."""
        # Include header but no cookie
        try:
            response = await client.post(
                "/api/v1/auth/logout",
                headers={"X-CSRF-Token": "test-token-value"},
            )
            assert response.status_code == 403
            assert "CSRF token missing" in response.json()["detail"]
        except Exception as e:
            assert "CSRF token missing" in str(e)

    async def test_post_with_mismatched_csrf_tokens_returns_403(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """POST request with mismatched cookie and header should return 403."""
        # Set different values for cookie and header
        client.cookies.set("csrf_token", "token-in-cookie")

        try:
            response = await client.post(
                "/api/v1/auth/logout",
                headers={"X-CSRF-Token": "different-token-in-header"},
            )
            assert response.status_code == 403
            assert "CSRF token mismatch" in response.json()["detail"]
        except Exception as e:
            assert "CSRF token mismatch" in str(e)

    async def test_post_with_valid_csrf_token_succeeds(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """POST request with matching cookie and header should succeed."""
        # Set matching CSRF token in cookie and header
        csrf_token = "valid-csrf-token-12345"
        client.cookies.set("csrf_token", csrf_token)

        response = await client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )

        # Should succeed (not 403 CSRF error)
        assert response.status_code == 200

    async def test_magic_link_request_exempt_from_csrf(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """Magic link request endpoint should be exempt from CSRF (entry point)."""
        # Create a test user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="csrf-exempt-test@example.com",
            full_name="CSRF Exempt Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Request magic link without CSRF token (should succeed)
        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": "csrf-exempt-test@example.com"},
        )

        # Should not be rejected by CSRF (200 or 429 for rate limit, but not 403)
        assert response.status_code in (200, 429)
        assert response.status_code != 403


class TestCSRFTokenGeneration:
    """Test CSRF token generation and validation functions."""

    async def test_generate_csrf_token(
        self,
        redis_client,
        workspace_1: Workspace,
    ):
        """Should generate and store CSRF token in Redis."""
        user_id = uuid.uuid4()

        token = await generate_csrf_token(
            user_id=user_id,
            workspace_id=workspace_1.id,
            redis_client=redis_client,
        )

        # Token should be URL-safe and non-empty
        assert token
        assert len(token) > 32  # URL-safe base64 encoding of 32 bytes

        # Token should be stored in Redis
        redis_key = f"csrf:{workspace_1.id}:{user_id}"
        stored_token = await redis_client.get(redis_key)
        assert stored_token == token

    async def test_validate_csrf_token_valid(
        self,
        redis_client,
        workspace_1: Workspace,
    ):
        """Should validate correct CSRF token."""
        user_id = uuid.uuid4()

        # Generate token
        token = await generate_csrf_token(
            user_id=user_id,
            workspace_id=workspace_1.id,
            redis_client=redis_client,
        )

        # Validate token
        is_valid = await validate_csrf_token(
            token=token,
            user_id=user_id,
            workspace_id=workspace_1.id,
            redis_client=redis_client,
        )

        assert is_valid is True

    async def test_validate_csrf_token_invalid(
        self,
        redis_client,
        workspace_1: Workspace,
    ):
        """Should reject invalid CSRF token."""
        user_id = uuid.uuid4()

        # Generate token
        await generate_csrf_token(
            user_id=user_id,
            workspace_id=workspace_1.id,
            redis_client=redis_client,
        )

        # Attempt to validate with wrong token
        is_valid = await validate_csrf_token(
            token="wrong-token",
            user_id=user_id,
            workspace_id=workspace_1.id,
            redis_client=redis_client,
        )

        assert is_valid is False

    async def test_validate_csrf_token_not_found(
        self,
        redis_client,
        workspace_1: Workspace,
    ):
        """Should reject token that doesn't exist in Redis."""
        user_id = uuid.uuid4()

        # Attempt to validate without generating token first
        is_valid = await validate_csrf_token(
            token="nonexistent-token",
            user_id=user_id,
            workspace_id=workspace_1.id,
            redis_client=redis_client,
        )

        assert is_valid is False

    async def test_csrf_token_expires_with_session(
        self,
        redis_client,
        workspace_1: Workspace,
    ):
        """CSRF token should have TTL set in Redis."""
        user_id = uuid.uuid4()

        # Generate token
        await generate_csrf_token(
            user_id=user_id,
            workspace_id=workspace_1.id,
            redis_client=redis_client,
        )

        # Check TTL is set
        redis_key = f"csrf:{workspace_1.id}:{user_id}"
        ttl = await redis_client.ttl(redis_key)

        # TTL should be set (7 days = 604800 seconds)
        # Allow some tolerance for test execution time
        assert ttl > 604000  # > 7 days - 800 seconds tolerance
        assert ttl <= 604800  # <= 7 days


class TestCSRFAuthenticationFlow:
    """Test CSRF token is set on authentication."""

    async def test_csrf_token_set_on_magic_link_verification(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """CSRF token should be set as cookie on successful authentication."""
        # Create a test user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="auth-csrf-test@example.com",
            full_name="Auth CSRF Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Manually create a magic link token in Redis
        import json
        import secrets
        from pazpaz.services.auth_service import get_token_cipher

        magic_token = secrets.token_urlsafe(32)
        token_data = {
            "user_id": str(user.id),
            "workspace_id": str(user.workspace_id),
            "email": user.email,
        }
        # Encrypt token data before storing (application expects encrypted data)
        cipher = get_token_cipher()
        encrypted_data = cipher.encrypt(json.dumps(token_data).encode())
        await redis_client.setex(
            f"magic_link:{magic_token}",
            600,  # 10 minutes
            encrypted_data.decode(),
        )

        # Verify magic link (should set CSRF token)
        response = await client.post(
            "/api/v1/auth/verify",
            json={"token": magic_token},
        )

        assert response.status_code == 200

        # Check that CSRF token cookie is set
        csrf_cookie = response.cookies.get("csrf_token")
        assert csrf_cookie is not None
        assert len(csrf_cookie) > 32

        # Verify CSRF token is stored in Redis
        redis_key = f"csrf:{user.workspace_id}:{user.id}"
        stored_token = await redis_client.get(redis_key)
        assert stored_token == csrf_cookie

    async def test_logout_requires_csrf_token(
        self,
        client: AsyncClient,
    ):
        """Verify logout endpoint requires CSRF token (not exempt)."""
        # Set valid CSRF cookie but NO header
        csrf_token = "test-csrf-token-value"
        client.cookies.set("csrf_token", csrf_token)
        client.cookies.set("access_token", "fake-jwt-token")

        # Try to logout without CSRF header
        try:
            response = await client.post("/api/v1/auth/logout")
            # Should be rejected by CSRF middleware
            assert response.status_code == 403
            assert "CSRF token missing" in response.json()["detail"]
        except Exception as e:
            # Middleware might raise exception instead of returning response
            assert "CSRF token missing" in str(e)

        # Now try with valid CSRF token in header
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )

        # Should succeed
        assert response.status_code == 200

    async def test_csrf_token_cleared_on_logout(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """CSRF token cookie should be cleared on logout."""
        # Create a test user and authenticate
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="logout-csrf-test@example.com",
            full_name="Logout CSRF Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Set CSRF cookie and token
        csrf_token = "test-csrf-token-for-logout"
        client.cookies.set("csrf_token", csrf_token)
        client.cookies.set("access_token", "test-jwt-token")

        # Logout with CSRF token in header
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        # CSRF cookie should be deleted
        # In httpx, deleted cookies have empty value or are removed
        csrf_cookie = response.cookies.get("csrf_token")
        assert csrf_cookie is None or csrf_cookie == ""
