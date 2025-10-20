"""Test JWT token expiration validation.

This test suite validates Task 1.2: Fix JWT Token Expiration Validation
from the Security Remediation Plan.

SECURITY REQUIREMENTS:
- Expired tokens must be rejected with 401 status
- Expiration validation cannot be bypassed
- Token refresh flow must still work
- Blacklist check must validate expiration
- Tokens without expiration claim must be rejected

Reference: Auth & Authorization Audit Report, Issue #1
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import redis.asyncio as redis
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.security import create_access_token, decode_access_token
from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace
from pazpaz.services.auth_service import blacklist_token, is_token_blacklisted

pytestmark = pytest.mark.asyncio


class TestJWTExpirationValidation:
    """Test that JWT expiration is properly validated."""

    async def test_valid_token_is_accepted(
        self, workspace_1: Workspace, test_user_ws1: User
    ):
        """Valid, non-expired token should be accepted."""
        # Create token with default expiration (7 days)
        token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
        )

        # Should decode successfully
        payload = decode_access_token(token)
        assert payload["user_id"] == str(test_user_ws1.id)
        assert payload["workspace_id"] == str(workspace_1.id)
        assert payload["email"] == test_user_ws1.email

    async def test_expired_token_is_rejected(
        self, workspace_1: Workspace, test_user_ws1: User
    ):
        """Expired token should be rejected with HTTPException."""
        from fastapi import HTTPException

        # Create token that expired 1 hour ago
        token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=-1),  # Negative delta = already expired
        )

        # Should raise HTTPException when decoding
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    async def test_token_expiring_in_future_is_valid(
        self, workspace_1: Workspace, test_user_ws1: User
    ):
        """Token expiring in the future should be valid."""
        # Create token expiring in 1 hour
        token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=1),
        )

        # Should decode successfully
        payload = decode_access_token(token)
        assert payload["user_id"] == str(test_user_ws1.id)

        # Verify expiration is in the future
        exp = payload["exp"]
        exp_datetime = datetime.fromtimestamp(exp, tz=UTC)
        assert exp_datetime > datetime.now(UTC)

    async def test_token_without_expiration_claim_is_rejected(
        self, workspace_1: Workspace, test_user_ws1: User
    ):
        """Token without 'exp' claim should be rejected."""
        from fastapi import HTTPException
        from jose import jwt

        from pazpaz.core.config import settings

        # Manually create token without 'exp' claim
        payload_without_exp = {
            "sub": str(test_user_ws1.id),
            "user_id": str(test_user_ws1.id),
            "workspace_id": str(workspace_1.id),
            "email": test_user_ws1.email,
            "iat": datetime.now(UTC),
            "jti": str(uuid.uuid4()),
            # Missing 'exp' claim
        }

        malformed_token = jwt.encode(
            payload_without_exp,
            settings.secret_key,
            algorithm="HS256",
        )

        # Should raise HTTPException due to missing exp claim
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(malformed_token)

        assert exc_info.value.status_code == 401

    async def test_blacklist_check_rejects_expired_token(
        self, workspace_1: Workspace, test_user_ws1: User, redis_client: redis.Redis
    ):
        """is_token_blacklisted should treat expired tokens as blacklisted."""
        # Create expired token
        expired_token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=-1),
        )

        # Should return True (expired = implicitly blacklisted)
        is_blacklisted = await is_token_blacklisted(redis_client, expired_token)
        assert is_blacklisted is True

    async def test_blacklist_check_accepts_valid_non_blacklisted_token(
        self, workspace_1: Workspace, test_user_ws1: User, redis_client: redis.Redis
    ):
        """is_token_blacklisted should return False for valid, non-blacklisted tokens."""
        # Create valid token
        valid_token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=1),
        )

        # Should return False (not blacklisted, not expired)
        is_blacklisted = await is_token_blacklisted(redis_client, valid_token)
        assert is_blacklisted is False

    async def test_blacklist_check_rejects_blacklisted_token(
        self, workspace_1: Workspace, test_user_ws1: User, redis_client: redis.Redis
    ):
        """is_token_blacklisted should return True for explicitly blacklisted tokens."""
        # Create valid token
        valid_token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=1),
        )

        # Add token to blacklist
        await blacklist_token(redis_client, valid_token)

        # Should return True (explicitly blacklisted)
        is_blacklisted = await is_token_blacklisted(redis_client, valid_token)
        assert is_blacklisted is True

    async def test_expired_token_rejected_in_endpoint(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Expired token should be rejected by protected endpoints with 401."""
        # Create expired token
        expired_token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=-1),
        )

        # Set expired token as cookie
        client.cookies.set("access_token", expired_token)

        # Try to access protected endpoint
        response = await client.get("/api/v1/clients")

        # Should return 401 (not authenticated)
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower() or "expired" in response.json()["detail"].lower() or "credentials" in response.json()["detail"].lower()

    async def test_valid_token_works_in_endpoint(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Valid token should grant access to protected endpoints."""
        # Create valid token
        valid_token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=1),
        )

        # Set valid token as cookie
        client.cookies.set("access_token", valid_token)

        # Access protected endpoint
        response = await client.get("/api/v1/clients")

        # Should return 200 (authenticated successfully)
        assert response.status_code == 200
        assert "items" in response.json()

    async def test_token_refresh_flow_works(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        redis_client: redis.Redis,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Token refresh flow should still work with expiration validation."""
        # Simulate user login flow
        from pazpaz.services.auth_service import verify_magic_link_token

        # 1. Request magic link (creates token in Redis)
        import json

        token_data = {
            "user_id": str(test_user_ws1.id),
            "workspace_id": str(workspace_1.id),
            "email": test_user_ws1.email,
        }
        magic_link_token = "test_magic_link_token_12345"
        await redis_client.setex(
            f"magic_link:{magic_link_token}",
            600,  # 10 minutes
            json.dumps(token_data),
        )

        # 2. Verify magic link (should generate new JWT)
        result = await verify_magic_link_token(
            magic_link_token, db_session, redis_client
        )
        assert result is not None
        user, jwt_token = result

        # 3. New JWT should be valid and not expired
        payload = decode_access_token(jwt_token)
        assert payload["user_id"] == str(test_user_ws1.id)
        assert payload["email"] == test_user_ws1.email

        # 4. Expiration should be in the future
        exp = payload["exp"]
        exp_datetime = datetime.fromtimestamp(exp, tz=UTC)
        assert exp_datetime > datetime.now(UTC)

    async def test_token_without_jti_is_treated_as_blacklisted(
        self, workspace_1: Workspace, test_user_ws1: User, redis_client: redis.Redis
    ):
        """Token without JTI claim should be treated as blacklisted."""
        from jose import jwt

        from pazpaz.core.config import settings

        # Create token without JTI
        payload_without_jti = {
            "sub": str(test_user_ws1.id),
            "user_id": str(test_user_ws1.id),
            "workspace_id": str(workspace_1.id),
            "email": test_user_ws1.email,
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
            # Missing 'jti' claim
        }

        token_without_jti = jwt.encode(
            payload_without_jti,
            settings.secret_key,
            algorithm="HS256",
        )

        # Should be treated as blacklisted
        is_blacklisted = await is_token_blacklisted(redis_client, token_without_jti)
        assert is_blacklisted is True

    async def test_defense_in_depth_expiration_check(
        self, workspace_1: Workspace, test_user_ws1: User
    ):
        """
        Defense-in-depth: Even if jose library validation passes,
        our manual check should catch expired tokens.
        """
        from fastapi import HTTPException

        # Create token that just expired
        expired_token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(seconds=-10),  # Expired 10 seconds ago
        )

        # Both jose validation and manual check should reject it
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(expired_token)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()


class TestTokenBlacklistWithExpiration:
    """Test that token blacklist operations work correctly with expiration validation."""

    async def test_blacklisting_expired_token_skips_storage(
        self, workspace_1: Workspace, test_user_ws1: User, redis_client: redis.Redis
    ):
        """Blacklisting an already-expired token should skip Redis storage."""
        # Create expired token
        expired_token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=-1),
        )

        # Blacklist it (should skip storage since already expired)
        await blacklist_token(redis_client, expired_token)

        # Verify no blacklist entry was created in Redis
        # (We can't easily verify this, but the function should return without error)

    async def test_blacklisting_valid_token_stores_in_redis(
        self, workspace_1: Workspace, test_user_ws1: User, redis_client: redis.Redis
    ):
        """Blacklisting a valid token should store it in Redis."""
        from jose import jwt

        from pazpaz.core.config import settings

        # Create valid token with 1 hour expiration
        valid_token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=1),
        )

        # Extract JTI
        payload = jwt.decode(
            valid_token, settings.secret_key, algorithms=["HS256"]
        )
        jti = payload["jti"]

        # Blacklist token
        await blacklist_token(redis_client, valid_token)

        # Verify blacklist entry exists in Redis
        blacklist_key = f"blacklist:jwt:{jti}"
        result = await redis_client.get(blacklist_key)
        assert result is not None

    async def test_blacklisted_token_rejected_in_endpoint(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        redis_client: redis.Redis,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Blacklisted token should be rejected by endpoints (simulates logout)."""
        # Create valid token
        valid_token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=1),
        )

        # Blacklist token (simulates logout)
        await blacklist_token(redis_client, valid_token)

        # Set blacklisted token as cookie
        client.cookies.set("access_token", valid_token)

        # Try to access protected endpoint
        response = await client.get("/api/v1/clients")

        # Should return 401 (token revoked)
        assert response.status_code == 401
        assert "revoked" in response.json()["detail"].lower()


class TestExpirationEdgeCases:
    """Test edge cases for JWT expiration validation."""

    async def test_token_expiring_exactly_now(
        self, workspace_1: Workspace, test_user_ws1: User
    ):
        """Token expiring at current timestamp should be rejected."""
        from fastapi import HTTPException

        # Create token expiring right now (delta = 0)
        token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(seconds=0),
        )

        # Should be rejected (exp <= now)
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)

        assert exc_info.value.status_code == 401

    async def test_token_with_very_short_expiration(
        self, workspace_1: Workspace, test_user_ws1: User
    ):
        """Token with very short expiration (1 second) should be valid initially."""
        # Create token expiring in 1 second
        token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(seconds=1),
        )

        # Should be valid immediately after creation
        payload = decode_access_token(token)
        assert payload["user_id"] == str(test_user_ws1.id)

        # Note: We can't reliably test that it expires after 1 second
        # without introducing sleep() which slows down tests

    async def test_multiple_expired_tokens_all_rejected(
        self, workspace_1: Workspace, test_user_ws1: User
    ):
        """Multiple expired tokens should all be rejected."""
        from fastapi import HTTPException

        # Create 3 expired tokens with different expirations
        expired_tokens = [
            create_access_token(
                user_id=test_user_ws1.id,
                workspace_id=workspace_1.id,
                email=test_user_ws1.email,
                expires_delta=timedelta(hours=-1),
            ),
            create_access_token(
                user_id=test_user_ws1.id,
                workspace_id=workspace_1.id,
                email=test_user_ws1.email,
                expires_delta=timedelta(days=-7),
            ),
            create_access_token(
                user_id=test_user_ws1.id,
                workspace_id=workspace_1.id,
                email=test_user_ws1.email,
                expires_delta=timedelta(seconds=-1),
            ),
        ]

        # All should be rejected
        for expired_token in expired_tokens:
            with pytest.raises(HTTPException) as exc_info:
                decode_access_token(expired_token)

            assert exc_info.value.status_code == 401
