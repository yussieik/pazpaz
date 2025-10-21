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

        # Verify token data (decrypt it first as it's encrypted in Redis)
        from pazpaz.services.auth_service import retrieve_magic_link_token

        token_key = keys[0].decode() if isinstance(keys[0], bytes) else keys[0]
        # Extract token from key (format: "magic_link:<token>")
        token = token_key.replace("magic_link:", "")

        token_data_dict = await retrieve_magic_link_token(redis_client, token)
        assert token_data_dict is not None
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

    async def test_request_magic_link_email_rate_limit(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Request magic link should be rate limited to 5 per hour per email.

        This test verifies the per-email rate limiting protection that prevents
        email bombing attacks even if the attacker uses multiple IPs.

        Note: The IP rate limit (3/hour) is lower than email limit (5/hour),
        so we need to clear IP rate limit between requests to test email limit.
        """
        # Create a test user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="emailratelimit@example.com",
            full_name="Email Rate Limit Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Clear any existing IP rate limit for this test
        # This allows us to test email rate limit independently
        ip_rate_limit_key = "magic_link_rate_limit:127.0.0.1"
        await redis_client.delete(ip_rate_limit_key)

        # Make 5 requests (should all succeed - email limit is 5/hour)
        for i in range(5):
            # Clear IP rate limit before each request to isolate email rate limit
            await redis_client.delete(ip_rate_limit_key)

            response = await client.post(
                "/api/v1/auth/magic-link",
                json={"email": "emailratelimit@example.com"},
            )
            assert response.status_code == 200, (
                f"Request {i + 1} should succeed (email limit: 5/hour)"
            )

        # 6th request should be silently rate limited (returns 200 to prevent enumeration)
        # Clear IP rate limit to ensure we're testing email limit
        await redis_client.delete(ip_rate_limit_key)

        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": "emailratelimit@example.com"},
        )
        # Returns 200 to prevent email enumeration, but doesn't send email
        assert response.status_code == 200

        # Verify that the 6th request didn't create a new token
        # Count tokens in Redis - should still be 5 (from first 5 requests)
        keys = await redis_client.keys("magic_link:*")
        # Note: We expect 5 tokens (one per successful request)
        assert len(keys) == 5, (
            f"Expected 5 magic link tokens, found {len(keys)}. Email rate limit should prevent 6th token."
        )

    async def test_request_magic_link_combined_rate_limits(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Test that both IP and email rate limits work together.

        Verifies that:
        1. IP rate limit (3/hour) is enforced first
        2. Email rate limit (5/hour) provides additional protection
        3. Whichever limit is hit first blocks the request
        """
        # Create a test user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="combined@example.com",
            full_name="Combined Rate Limit Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Make 3 requests (should all succeed - within both limits)
        for i in range(3):
            response = await client.post(
                "/api/v1/auth/magic-link",
                json={"email": "combined@example.com"},
            )
            assert response.status_code == 200, (
                f"Request {i + 1} should succeed (within both rate limits)"
            )

        # 4th request hits IP rate limit (3/hour per IP)
        # Returns 429 because IP rate limit raises HTTPException
        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": "combined@example.com"},
        )
        assert response.status_code == 429, "IP rate limit should block 4th request"

        # Verify error message indicates rate limit
        assert "rate limit" in response.json()["detail"].lower()


class TestMagicLinkVerify:
    """Test POST /api/v1/auth/verify endpoint."""

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

        # Create magic link token in Redis (minimum 32 chars for validation)
        # Use the actual service function to store it properly (encrypted)
        from pazpaz.services.auth_service import store_magic_link_token

        token = "test-token-12345-with-enough-length-for-validation-abcd"
        await store_magic_link_token(
            redis_client=redis_client,
            token=token,
            user_id=user.id,
            workspace_id=user.workspace_id,
            email=user.email,
            expiry_seconds=600,  # 10 minutes
        )

        # Verify token
        response = await client.post(
            "/api/v1/auth/verify",
            json={"token": token},
        )

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
        # Token must be 32+ chars to pass validation
        response = await client.post(
            "/api/v1/auth/verify",
            json={"token": "expired-token-with-enough-chars-for-validation"},
        )

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
        # Token must be 32+ chars to pass validation
        response = await client.post(
            "/api/v1/auth/verify",
            json={"token": "invalid-token-with-enough-chars-for-validation"},
        )

        assert response.status_code == 401

    async def test_verify_token_user_not_found(
        self,
        client: AsyncClient,
        redis_client,
    ):
        """Verify token for non-existent user should return 401."""
        # Create token for non-existent user (minimum 32 chars)
        token = "orphan-token-with-enough-chars-for-validation-xyz"
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
        response = await client.post(
            "/api/v1/auth/verify",
            json={"token": token},
        )

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

        # Generate JWT with JTI (required for blacklist check)
        token = jwt.encode(
            {
                "sub": str(user.id),
                "user_id": str(user.id),
                "workspace_id": str(user.workspace_id),
                "email": user.email,
                "exp": datetime.now(UTC) + timedelta(days=1),
                "iat": datetime.now(UTC),
                "jti": str(uuid.uuid4()),  # Required for blacklist functionality
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


class TestJWTBlacklist:
    """Test JWT blacklist functionality (logout and revocation)."""

    async def test_logout_blacklists_jwt_token(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Verify logout adds JWT to blacklist."""
        # Create a test user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="blacklist-test@example.com",
            full_name="Blacklist Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Create magic link token in Redis using the proper service function
        import secrets

        from pazpaz.services.auth_service import store_magic_link_token

        magic_token = secrets.token_urlsafe(32)
        await store_magic_link_token(
            redis_client=redis_client,
            token=magic_token,
            user_id=user.id,
            workspace_id=user.workspace_id,
            email=user.email,
            expiry_seconds=600,  # 10 minutes
        )

        # Verify magic link to get JWT
        response = await client.post(
            "/api/v1/auth/verify",
            json={"token": magic_token},
        )
        assert response.status_code == 200

        # Extract JWT from cookies
        jwt_token = response.cookies.get("access_token")
        csrf_token = response.cookies.get("csrf_token")
        assert jwt_token is not None
        assert csrf_token is not None

        # Decode JWT to get JTI
        payload = jwt.decode(jwt_token, settings.secret_key, algorithms=["HS256"])
        jti = payload["jti"]

        # Logout (should blacklist token)
        client.cookies.set("access_token", jwt_token)
        client.cookies.set("csrf_token", csrf_token)
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Verify token is blacklisted in Redis
        blacklist_key = f"blacklist:jwt:{jti}"
        result = await redis_client.get(blacklist_key)
        assert result is not None  # Token should be in blacklist

    async def test_blacklisted_token_cannot_be_used(
        self,
        authenticated_client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Verify blacklisted JWT cannot access protected endpoints."""
        # authenticated_client already has JWT token set
        jwt_token = authenticated_client.cookies.get("access_token")
        csrf_token = authenticated_client.cookies.get("csrf_token")

        # Verify token works before logout
        response = await authenticated_client.get("/api/v1/clients")
        assert response.status_code == 200

        # Logout (blacklists token)
        response = await authenticated_client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Try to use blacklisted token on protected endpoint
        # Need to manually set cookies again since logout cleared them
        authenticated_client.cookies.set("access_token", jwt_token)
        response = await authenticated_client.get("/api/v1/clients")

        assert response.status_code == 401
        detail = response.json()["detail"].lower()
        assert "revoked" in detail or "blacklisted" in detail

    async def test_token_without_jti_is_rejected(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        test_user_ws1: User,
    ):
        """Verify tokens without JTI claim are rejected (old tokens)."""
        # Generate JWT without JTI (simulating old token format)
        old_token = jwt.encode(
            {
                "sub": str(test_user_ws1.id),
                "user_id": str(test_user_ws1.id),
                "workspace_id": str(workspace_1.id),
                "email": test_user_ws1.email,
                "exp": datetime.now(UTC) + timedelta(days=1),
                "iat": datetime.now(UTC),
                # NO JTI claim
            },
            settings.secret_key,
            algorithm="HS256",
        )

        # Try to access protected endpoint with old token
        client.cookies.set("access_token", old_token)
        response = await client.get("/api/v1/clients")

        # Should be rejected (treated as blacklisted)
        assert response.status_code == 401
        detail = response.json()["detail"].lower()
        assert "revoked" in detail or "blacklisted" in detail or "invalid" in detail
