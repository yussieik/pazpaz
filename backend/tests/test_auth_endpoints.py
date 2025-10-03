"""Test authentication endpoints (magic link and JWT)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.config import settings
from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace

pytestmark = pytest.mark.asyncio


class TestMagicLinkRequest:
    """Test POST /api/v1/auth/magic-link endpoint."""

    async def test_request_magic_link_existing_user(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Request magic link for existing user should return success."""
        # Create a test user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="test@example.com",
            full_name="Test User",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Request magic link
        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 200
        data = response.json()
        assert (
            "magic" in data["message"].lower()
            or "login link" in data["message"].lower()
        )

        # Verify token was stored in Redis
        keys = await redis_client.keys("magic_link:*")
        assert len(keys) == 1

        # Verify token data
        token_data = await redis_client.get(keys[0])
        token_data_dict = json.loads(token_data)
        assert token_data_dict["user_id"] == str(user.id)
        assert token_data_dict["workspace_id"] == str(user.workspace_id)
        assert token_data_dict["email"] == user.email

    async def test_request_magic_link_nonexistent_user(
        self,
        client: AsyncClient,
        redis_client,
    ):
        """Request magic link for non-existent user returns success message."""
        # Request magic link for non-existent email
        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": "nonexistent@example.com"},
        )

        # Should return success to prevent email enumeration
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

        # Verify NO token was stored in Redis
        keys = await redis_client.keys("magic_link:*")
        assert len(keys) == 0

    async def test_request_magic_link_inactive_user(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Request magic link for inactive user returns success (no link sent)."""
        # Create inactive user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="inactive@example.com",
            full_name="Inactive User",
            role=UserRole.OWNER,
            is_active=False,
        )
        db.add(user)
        await db.commit()

        # Request magic link
        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": "inactive@example.com"},
        )

        # Should return success to prevent user status enumeration
        assert response.status_code == 200

        # Verify NO token was stored in Redis
        keys = await redis_client.keys("magic_link:*")
        assert len(keys) == 0

    async def test_request_magic_link_invalid_email(
        self,
        client: AsyncClient,
    ):
        """Request magic link with invalid email format should return 422."""
        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": "not-an-email"},
        )

        assert response.status_code == 422

    async def test_request_magic_link_rate_limit(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Request magic link should be rate limited to 3 per hour per IP."""
        # Create a test user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="ratelimit@example.com",
            full_name="Rate Limit Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Make 3 requests (should all succeed)
        for _ in range(3):
            response = await client.post(
                "/api/v1/auth/magic-link",
                json={"email": "ratelimit@example.com"},
            )
            assert response.status_code == 200

        # 4th request should be rate limited
        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": "ratelimit@example.com"},
        )
        assert response.status_code == 429  # Too Many Requests


class TestMagicLinkVerify:
    """Test GET /api/v1/auth/verify endpoint."""

    async def test_verify_valid_token(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Verify valid magic link token should return JWT and user data."""
        # Create a test user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="verify@example.com",
            full_name="Verify Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Create magic link token in Redis
        token = "test-token-12345"
        token_data = {
            "user_id": str(user.id),
            "workspace_id": str(user.workspace_id),
            "email": user.email,
        }
        await redis_client.setex(
            f"magic_link:{token}",
            600,  # 10 minutes
            json.dumps(token_data),
        )

        # Verify token
        response = await client.get(f"/api/v1/auth/verify?token={token}")

        assert response.status_code == 200
        data = response.json()

        # Check JWT token is returned
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Check user data is returned
        assert "user" in data
        assert data["user"]["id"] == str(user.id)
        assert data["user"]["email"] == user.email
        assert data["user"]["workspace_id"] == str(user.workspace_id)

        # Verify JWT token is valid
        decoded = jwt.decode(
            data["access_token"],
            settings.secret_key,
            algorithms=["HS256"],
        )
        assert decoded["user_id"] == str(user.id)
        assert decoded["workspace_id"] == str(user.workspace_id)
        assert decoded["email"] == user.email

        # Verify HttpOnly cookie is set
        assert "set-cookie" in response.headers
        cookie_header = response.headers["set-cookie"]
        assert "access_token=" in cookie_header
        assert "HttpOnly" in cookie_header
        assert "SameSite=lax" in cookie_header

        # Verify token was deleted from Redis (single-use)
        token_exists = await redis_client.exists(f"magic_link:{token}")
        assert token_exists == 0

    async def test_verify_expired_token(
        self,
        client: AsyncClient,
        redis_client,
    ):
        """Verify expired token should return 401."""
        # Don't create token in Redis (simulate expiry)
        response = await client.get("/api/v1/auth/verify?token=expired-token")

        assert response.status_code == 401
        data = response.json()
        assert (
            "invalid" in data["detail"].lower() or "expired" in data["detail"].lower()
        )

    async def test_verify_invalid_token(
        self,
        client: AsyncClient,
        redis_client,
    ):
        """Verify invalid token should return 401."""
        response = await client.get("/api/v1/auth/verify?token=invalid-token-xyz")

        assert response.status_code == 401

    async def test_verify_token_user_not_found(
        self,
        client: AsyncClient,
        redis_client,
    ):
        """Verify token for non-existent user should return 401."""
        # Create token for non-existent user
        token = "orphan-token"
        token_data = {
            "user_id": str(uuid.uuid4()),  # Random UUID
            "workspace_id": str(uuid.uuid4()),
            "email": "ghost@example.com",
        }
        await redis_client.setex(
            f"magic_link:{token}",
            600,
            json.dumps(token_data),
        )

        # Verify token
        response = await client.get(f"/api/v1/auth/verify?token={token}")

        assert response.status_code == 401

        # Verify token was deleted
        token_exists = await redis_client.exists(f"magic_link:{token}")
        assert token_exists == 0


class TestLogout:
    """Test POST /api/v1/auth/logout endpoint."""

    async def test_logout_clears_cookie(
        self,
        client: AsyncClient,
    ):
        """Logout should clear authentication cookie."""
        # Set fake JWT and CSRF token cookies
        csrf_token = "test-csrf-token"
        client.cookies.set("access_token", "fake-jwt-token")
        client.cookies.set("csrf_token", csrf_token)

        # Logout with CSRF token in header
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200
        data = response.json()
        assert "logged out" in data["message"].lower()

        # Verify cookie is cleared
        assert "set-cookie" in response.headers
        cookie_header = response.headers["set-cookie"]
        assert "access_token=" in cookie_header

    async def test_logout_without_token(
        self,
        client: AsyncClient,
    ):
        """Logout without token should still succeed if CSRF is provided."""
        # Set CSRF token
        csrf_token = "test-csrf-token-no-auth"
        client.cookies.set("csrf_token", csrf_token)

        response = await client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200


class TestJWTAuthentication:
    """Test JWT authentication on protected endpoints."""

    async def test_valid_jwt_allows_access(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """Valid JWT in cookie should allow access to protected endpoints."""
        # Create a test user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="jwt@example.com",
            full_name="JWT Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Generate JWT
        token = jwt.encode(
            {
                "sub": str(user.id),
                "user_id": str(user.id),
                "workspace_id": str(user.workspace_id),
                "email": user.email,
                "exp": datetime.now(UTC) + timedelta(days=1),
                "iat": datetime.now(UTC),
            },
            settings.secret_key,
            algorithm="HS256",
        )

        # Set JWT cookie
        client.cookies.set("access_token", token)

        # Access protected endpoint (using legacy X-Workspace-ID for now)
        # TODO: Update when endpoints migrated to use get_current_user
        response = await client.get(
            "/api/v1/clients",
            headers={"X-Workspace-ID": str(workspace_1.id)},
        )

        assert response.status_code == 200

    async def test_missing_jwt_returns_401(
        self,
        client: AsyncClient,
    ):
        """Missing JWT should return 401 on protected endpoints using JWT auth."""
        # This test will be relevant when endpoints are migrated to get_current_user
        # For now, endpoints still use X-Workspace-ID header
        pass

    async def test_expired_jwt_returns_401(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
    ):
        """Expired JWT should return 401."""
        # Create a test user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="expired@example.com",
            full_name="Expired Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Generate expired JWT
        _token = jwt.encode(
            {
                "sub": str(user.id),
                "user_id": str(user.id),
                "workspace_id": str(user.workspace_id),
                "email": user.email,
                "exp": datetime.now(UTC) - timedelta(days=1),  # Expired
                "iat": datetime.now(UTC) - timedelta(days=2),
            },
            settings.secret_key,
            algorithm="HS256",
        )

        # This will be testable once endpoints migrate to get_current_user
        # For now, JWT validation happens in get_current_user dependency
        pass

    async def test_invalid_jwt_signature_returns_401(
        self,
        client: AsyncClient,
    ):
        """Invalid JWT signature should return 401."""
        # Generate JWT with wrong secret
        _token = jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "user_id": str(uuid.uuid4()),
                "workspace_id": str(uuid.uuid4()),
                "email": "test@example.com",
                "exp": datetime.now(UTC) + timedelta(days=1),
                "iat": datetime.now(UTC),
            },
            "wrong-secret-key",
            algorithm="HS256",
        )

        # This will be testable once endpoints migrate to get_current_user
        pass
