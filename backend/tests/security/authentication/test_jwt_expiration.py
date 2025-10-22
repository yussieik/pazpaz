"""Test JWT token expiration validation and blacklist behavior.

This test suite validates JWT expiration security requirements:
- Expired tokens must be rejected with 401 status
- Expiration validation cannot be bypassed
- Token refresh flow must still work
- Blacklist check must validate expiration
- Tokens without expiration claim must be rejected

Security Requirements: OWASP A07:2021 - Identification and Authentication Failures
Reference: Week 1, Task 1.2 - Fix JWT Token Expiration Validation
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import redis.asyncio as redis
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.security import create_access_token, decode_access_token
from pazpaz.models.user import User
from pazpaz.models.workspace import Workspace
from pazpaz.services.auth_service import blacklist_token, is_token_blacklisted

pytestmark = pytest.mark.asyncio


class TestJWTExpirationValidation:
    """Test that JWT expiration is properly validated."""

    async def test_valid_token_is_accepted(
        self, workspace_1: Workspace, test_user_ws1: User
    ):
        """Valid, non-expired token should be accepted."""
        token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
        )

        payload = decode_access_token(token)
        assert payload["user_id"] == str(test_user_ws1.id)
        assert payload["workspace_id"] == str(workspace_1.id)
        assert payload["email"] == test_user_ws1.email

    async def test_expired_token_is_rejected(
        self, workspace_1: Workspace, test_user_ws1: User
    ):
        """Expired token should be rejected with HTTPException."""
        from fastapi import HTTPException

        token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=-1),
        )

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    async def test_token_expiring_in_future_is_valid(
        self, workspace_1: Workspace, test_user_ws1: User
    ):
        """Token expiring in the future should be valid."""
        token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=1),
        )

        payload = decode_access_token(token)
        assert payload["user_id"] == str(test_user_ws1.id)

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

        payload_without_exp = {
            "sub": str(test_user_ws1.id),
            "user_id": str(test_user_ws1.id),
            "workspace_id": str(workspace_1.id),
            "email": test_user_ws1.email,
            "iat": datetime.now(UTC),
            "jti": str(uuid.uuid4()),
        }

        malformed_token = jwt.encode(
            payload_without_exp,
            settings.secret_key,
            algorithm="HS256",
        )

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(malformed_token)

        assert exc_info.value.status_code == 401

    async def test_token_expiring_exactly_now(
        self, workspace_1: Workspace, test_user_ws1: User
    ):
        """Token expiring at current timestamp should be rejected."""
        from fastapi import HTTPException

        token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(seconds=0),
        )

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)

        assert exc_info.value.status_code == 401


class TestTokenBlacklistWithExpiration:
    """Test that token blacklist operations work correctly with expiration validation."""

    async def test_blacklist_check_rejects_expired_token(
        self, workspace_1: Workspace, test_user_ws1: User, redis_client: redis.Redis
    ):
        """is_token_blacklisted should treat expired tokens as blacklisted."""
        expired_token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=-1),
        )

        is_blacklisted = await is_token_blacklisted(redis_client, expired_token)
        assert is_blacklisted is True

    async def test_blacklist_check_accepts_valid_non_blacklisted_token(
        self, workspace_1: Workspace, test_user_ws1: User, redis_client: redis.Redis
    ):
        """is_token_blacklisted should return False for valid, non-blacklisted tokens."""
        valid_token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=1),
        )

        is_blacklisted = await is_token_blacklisted(redis_client, valid_token)
        assert is_blacklisted is False

    async def test_blacklist_check_rejects_blacklisted_token(
        self, workspace_1: Workspace, test_user_ws1: User, redis_client: redis.Redis
    ):
        """is_token_blacklisted should return True for explicitly blacklisted tokens."""
        valid_token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=1),
        )

        await blacklist_token(redis_client, valid_token)

        is_blacklisted = await is_token_blacklisted(redis_client, valid_token)
        assert is_blacklisted is True

    async def test_blacklisting_valid_token_stores_in_redis(
        self, workspace_1: Workspace, test_user_ws1: User, redis_client: redis.Redis
    ):
        """Blacklisting a valid token should store it in Redis."""
        from jose import jwt

        from pazpaz.core.config import settings

        valid_token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=1),
        )

        payload = jwt.decode(valid_token, settings.secret_key, algorithms=["HS256"])
        jti = payload["jti"]

        await blacklist_token(redis_client, valid_token)

        blacklist_key = f"blacklist:jwt:{jti}"
        result = await redis_client.get(blacklist_key)
        assert result is not None

    async def test_token_without_jti_is_treated_as_blacklisted(
        self, workspace_1: Workspace, test_user_ws1: User, redis_client: redis.Redis
    ):
        """Token without JTI claim should be treated as blacklisted."""
        from jose import jwt

        from pazpaz.core.config import settings

        payload_without_jti = {
            "sub": str(test_user_ws1.id),
            "user_id": str(test_user_ws1.id),
            "workspace_id": str(workspace_1.id),
            "email": test_user_ws1.email,
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
        }

        token_without_jti = jwt.encode(
            payload_without_jti,
            settings.secret_key,
            algorithm="HS256",
        )

        is_blacklisted = await is_token_blacklisted(redis_client, token_without_jti)
        assert is_blacklisted is True


class TestJWTExpirationInEndpoints:
    """Test JWT expiration validation in protected endpoints."""

    async def test_expired_token_rejected_in_endpoint(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Expired token should be rejected by protected endpoints with 401."""
        expired_token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=-1),
        )

        client.cookies.set("access_token", expired_token)

        response = await client.get("/api/v1/clients")

        assert response.status_code == 401
        detail = response.json()["detail"].lower()
        assert "invalid" in detail or "expired" in detail or "credentials" in detail

    async def test_valid_token_works_in_endpoint(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Valid token should grant access to protected endpoints."""
        valid_token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=1),
        )

        client.cookies.set("access_token", valid_token)

        response = await client.get("/api/v1/clients")

        assert response.status_code == 200
        assert "items" in response.json()

    async def test_blacklisted_token_rejected_in_endpoint(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        redis_client: redis.Redis,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Blacklisted token should be rejected by endpoints (simulates logout)."""
        valid_token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
            expires_delta=timedelta(hours=1),
        )

        await blacklist_token(redis_client, valid_token)

        client.cookies.set("access_token", valid_token)

        response = await client.get("/api/v1/clients")

        assert response.status_code == 401
        assert "revoked" in response.json()["detail"].lower()
