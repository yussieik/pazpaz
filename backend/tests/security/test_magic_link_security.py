"""Test magic link authentication security (384-bit tokens, encryption, brute force, CSRF bypass prevention).

This module consolidates all magic link security tests:
- 384-bit token entropy (48 bytes, 64 hex chars)
- Fernet encryption for Redis storage
- Brute force detection (100 attempts = 5-min lockout)
- /verify endpoint POST-only (CSRF bypass prevention)
- Token validation and expiration

Security Requirements:
- OWASP A02:2021 - Cryptographic Failures
- OWASP A07:2021 - Identification and Authentication Failures
- CWE-352 - Cross-Site Request Forgery (CSRF)

References:
- Week 2, Task 2.1 - Increase token entropy to 384 bits
- Week 2, Task 2.2 - Encrypt magic link tokens in Redis
- Week 2, Task 2.3 - Brute force detection
- Week 1, Task 1.4 - Fix /verify CSRF bypass
"""

from __future__ import annotations

import json
import secrets
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace
from pazpaz.services.auth_service import (
    BRUTE_FORCE_LOCKOUT_SECONDS,
    BRUTE_FORCE_THRESHOLD,
    retrieve_magic_link_token,
    store_magic_link_token,
)

pytestmark = pytest.mark.asyncio


class TestTokenEntropy:
    """Test that magic link tokens have 384-bit entropy."""

    async def test_magic_link_token_has_384_bit_entropy(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Verify magic link tokens have 384-bit entropy (48 bytes = 64 chars)."""
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="entropy-test@example.com",
            full_name="Entropy Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": "entropy-test@example.com"},
        )
        assert response.status_code == 200

        keys = await redis_client.keys("magic_link:*")
        assert len(keys) == 1

        token_key = keys[0].decode() if isinstance(keys[0], bytes) else keys[0]
        token = token_key.replace("magic_link:", "")

        # 48 bytes base64url encoded = 64 characters
        assert len(token) == 64, f"Token length {len(token)} != 64 (expected for 384 bits)"


class TestTokenEncryption:
    """Test token data encryption in Redis."""

    async def test_token_data_encrypted_in_redis(
        self,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Verify token data is encrypted when stored in Redis."""
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="encryption-test@example.com",
            full_name="Encryption Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        token = secrets.token_urlsafe(48)
        await store_magic_link_token(
            redis_client=redis_client,
            token=token,
            user_id=user.id,
            workspace_id=user.workspace_id,
            email=user.email,
            expiry_seconds=600,
        )

        raw_data = await redis_client.get(f"magic_link:{token}")

        assert raw_data is not None
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw_data)

        # Should contain Fernet token markers
        if isinstance(raw_data, bytes):
            assert raw_data.startswith(b"gAAAAA"), "Should be Fernet-encrypted"
        else:
            assert raw_data.startswith("gAAAAA"), "Should be Fernet-encrypted"

    async def test_token_retrieval_decrypts_correctly(
        self,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Verify encrypted token data can be decrypted."""
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="decrypt-test@example.com",
            full_name="Decrypt Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        token = secrets.token_urlsafe(48)
        await store_magic_link_token(
            redis_client=redis_client,
            token=token,
            user_id=user.id,
            workspace_id=user.workspace_id,
            email=user.email,
            expiry_seconds=600,
        )

        token_data = await retrieve_magic_link_token(redis_client, token)

        assert token_data is not None
        assert token_data["user_id"] == str(user.id)
        assert token_data["workspace_id"] == str(user.workspace_id)
        assert token_data["email"] == user.email


class TestBruteForceDetection:
    """Test brute force detection and lockout."""

    async def test_brute_force_detection_triggers_lockout(
        self,
        client: AsyncClient,
        redis_client,
    ):
        """Verify brute force detection locks out after threshold reached."""
        # Manually set counter to threshold to trigger lockout
        await redis_client.set("magic_link_failed_attempts", BRUTE_FORCE_THRESHOLD)
        await redis_client.expire("magic_link_failed_attempts", BRUTE_FORCE_LOCKOUT_SECONDS)

        fake_token = secrets.token_urlsafe(48)
        response = await client.post(
            "/api/v1/auth/verify",
            json={"token": fake_token},
        )
        assert response.status_code == 429, "Should be locked out when threshold reached"
        assert "too many failed" in response.json()["detail"].lower()

    async def test_successful_login_resets_attempt_counter(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Verify successful login resets failed attempt counter."""
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="reset-test@example.com",
            full_name="Reset Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Make some failed attempts
        for _ in range(50):
            fake_token = secrets.token_urlsafe(48)
            await client.post("/api/v1/auth/verify", json={"token": fake_token})

        attempts = await redis_client.get("magic_link_failed_attempts")
        assert attempts is not None
        assert int(attempts) == 50

        # Generate valid token
        valid_token = secrets.token_urlsafe(48)
        await store_magic_link_token(
            redis_client=redis_client,
            token=valid_token,
            user_id=user.id,
            workspace_id=user.workspace_id,
            email=user.email,
            expiry_seconds=600,
        )

        response = await client.post("/api/v1/auth/verify", json={"token": valid_token})
        assert response.status_code == 200

        attempts = await redis_client.get("magic_link_failed_attempts")
        assert attempts is None, "Successful login should reset attempt counter"


class TestVerifyEndpointMethod:
    """Test that /verify endpoint only accepts POST requests."""

    async def test_verify_endpoint_is_post_not_get(
        self,
        client: AsyncClient,
    ):
        """GET request should be rejected with 405 Method Not Allowed."""
        response = await client.get("/api/v1/auth/verify?token=test")
        assert response.status_code == 405, (
            "GET request should be rejected with 405 Method Not Allowed. "
            "The /verify endpoint MUST be POST to prevent CSRF bypass."
        )

    async def test_verify_post_method_allowed(
        self,
        client: AsyncClient,
    ):
        """POST method should be allowed."""
        response = await client.post(
            "/api/v1/auth/verify",
            json={"token": "x" * 32},
        )

        assert response.status_code != 405
        assert response.status_code in [400, 401, 422]


class TestVerifyCSRFExemption:
    """Test that /verify endpoint is exempt from CSRF protection."""

    async def test_verify_endpoint_exempt_from_csrf(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """POST should succeed without X-CSRF-Token header."""
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="csrf-exempt@example.com",
            full_name="CSRF Exempt Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        token = secrets.token_urlsafe(48)
        token_data = {
            "user_id": str(user.id),
            "workspace_id": str(user.workspace_id),
            "email": user.email,
        }
        await redis_client.setex(
            f"magic_link:{token}",
            600,
            json.dumps(token_data),
        )

        response = await client.post(
            "/api/v1/auth/verify",
            json={"token": token},
        )

        assert response.status_code != 403
        assert response.status_code == 200


class TestVerifySchemaValidation:
    """Test request body schema validation."""

    async def test_verify_requires_token_field(
        self,
        client: AsyncClient,
    ):
        """Missing token field should return 422."""
        response = await client.post("/api/v1/auth/verify", json={})
        assert response.status_code == 422

    async def test_verify_token_length_validation_too_short(
        self,
        client: AsyncClient,
    ):
        """Token shorter than 32 chars should fail validation."""
        short_token = "x" * 31
        response = await client.post(
            "/api/v1/auth/verify",
            json={"token": short_token},
        )
        assert response.status_code == 422

    async def test_verify_token_length_validation_too_long(
        self,
        client: AsyncClient,
    ):
        """Token longer than 128 chars should fail validation."""
        long_token = "a" * 150
        response = await client.post(
            "/api/v1/auth/verify",
            json={"token": long_token},
        )
        assert response.status_code == 422
