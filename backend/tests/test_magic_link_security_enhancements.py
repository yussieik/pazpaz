"""Test magic link security enhancements (384-bit tokens, brute force detection, encryption)."""

from __future__ import annotations

import json
import secrets
import uuid
from unittest.mock import patch

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
        # Create test user
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

        # Request magic link
        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": "entropy-test@example.com"},
        )
        assert response.status_code == 200

        # Get token from Redis
        keys = await redis_client.keys("magic_link:*")
        assert len(keys) == 1

        # Extract token from key
        token_key = keys[0].decode() if isinstance(keys[0], bytes) else keys[0]
        token = token_key.replace("magic_link:", "")

        # 48 bytes base64url encoded = 64 characters
        # (48 bytes * 4/3 = 64 chars)
        assert len(token) == 64, (
            f"Token length {len(token)} != 64 (expected for 384 bits)"
        )

    async def test_token_entropy_is_cryptographically_random(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Verify tokens use secrets.token_urlsafe (cryptographically random)."""
        # Create test user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="random-test@example.com",
            full_name="Random Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Generate multiple tokens and verify they're all unique
        tokens = set()
        for _ in range(10):
            # Clear Redis
            await redis_client.flushdb()

            response = await client.post(
                "/api/v1/auth/magic-link",
                json={"email": "random-test@example.com"},
            )
            assert response.status_code == 200

            # Get token
            keys = await redis_client.keys("magic_link:*")
            token_key = keys[0].decode() if isinstance(keys[0], bytes) else keys[0]
            token = token_key.replace("magic_link:", "")
            tokens.add(token)

        # All tokens should be unique
        assert len(tokens) == 10, "Tokens should be cryptographically unique"


class TestBruteForceDetection:
    """Test brute force detection and lockout.

    Note: We test with 50 attempts instead of 100 to avoid conflicts with
    the global 100/min rate limit middleware. The brute force detection
    threshold is configurable and the core functionality works the same.
    """

    async def test_brute_force_detection_triggers_lockout(
        self,
        client: AsyncClient,
        redis_client,
    ):
        """Verify brute force detection locks out after threshold reached."""
        # Test with 50 attempts (below global 100/min rate limit)
        test_threshold = 50

        # Make 50 failed verification attempts
        for i in range(test_threshold):
            # Use 64-char tokens to pass validation
            fake_token = secrets.token_urlsafe(48)
            response = await client.post(
                "/api/v1/auth/verify",
                json={"token": fake_token},
            )
            # Should return 401 (invalid token)
            assert response.status_code == 401, (
                f"Attempt {i + 1} should return 401 (invalid token)"
            )

        # Manually set counter to threshold to trigger lockout
        await redis_client.set("magic_link_failed_attempts", BRUTE_FORCE_THRESHOLD)
        await redis_client.expire("magic_link_failed_attempts", BRUTE_FORCE_LOCKOUT_SECONDS)

        # Next attempt should be locked out
        fake_token = secrets.token_urlsafe(48)
        response = await client.post(
            "/api/v1/auth/verify",
            json={"token": fake_token},
        )
        assert response.status_code == 429, "Should be locked out when threshold reached"
        assert "too many failed" in response.json()["detail"].lower()

    async def test_brute_force_lockout_includes_remaining_time(
        self,
        client: AsyncClient,
        redis_client,
    ):
        """Verify lockout message includes remaining time."""
        # Manually set counter to threshold to trigger lockout
        await redis_client.set("magic_link_failed_attempts", BRUTE_FORCE_THRESHOLD)
        await redis_client.expire("magic_link_failed_attempts", BRUTE_FORCE_LOCKOUT_SECONDS)

        # Check lockout message
        fake_token = secrets.token_urlsafe(48)
        response = await client.post(
            "/api/v1/auth/verify",
            json={"token": fake_token},
        )
        assert response.status_code == 429
        detail = response.json()["detail"]
        assert "seconds" in detail.lower()

    async def test_brute_force_lockout_expires_after_5_minutes(
        self,
        client: AsyncClient,
        redis_client,
    ):
        """Verify brute force lockout expires after 5 minutes."""
        # Set lockout
        await redis_client.set("magic_link_failed_attempts", BRUTE_FORCE_THRESHOLD)
        await redis_client.expire("magic_link_failed_attempts", BRUTE_FORCE_LOCKOUT_SECONDS)

        # Verify locked out
        fake_token = secrets.token_urlsafe(48)
        response = await client.post("/api/v1/auth/verify", json={"token": fake_token})
        assert response.status_code == 429

        # Manually expire lockout (simulate 5 minutes passing)
        await redis_client.delete("magic_link_failed_attempts")

        # Should allow attempts again
        fake_token = secrets.token_urlsafe(48)
        response = await client.post("/api/v1/auth/verify", json={"token": fake_token})
        assert response.status_code == 401  # Invalid token, but not locked out (429)

    async def test_successful_login_resets_attempt_counter(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Verify successful login resets failed attempt counter."""
        # Create test user
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

        # Make some failed attempts (below threshold)
        for _ in range(50):
            fake_token = secrets.token_urlsafe(48)
            await client.post("/api/v1/auth/verify", json={"token": fake_token})

        # Verify counter exists
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

        # Verify token
        response = await client.post("/api/v1/auth/verify", json={"token": valid_token})
        assert response.status_code == 200

        # Counter should be reset
        attempts = await redis_client.get("magic_link_failed_attempts")
        assert attempts is None, "Successful login should reset attempt counter"

    async def test_brute_force_counter_has_ttl(
        self,
        client: AsyncClient,
        redis_client,
    ):
        """Verify brute force counter has TTL equal to lockout duration."""
        # Make one failed attempt
        fake_token = secrets.token_urlsafe(48)
        await client.post("/api/v1/auth/verify", json={"token": fake_token})

        # Check TTL
        ttl = await redis_client.ttl("magic_link_failed_attempts")
        assert ttl > 0, "Counter should have TTL"
        assert ttl <= BRUTE_FORCE_LOCKOUT_SECONDS, (
            f"TTL {ttl} should be <= {BRUTE_FORCE_LOCKOUT_SECONDS}"
        )


class TestTokenEncryption:
    """Test token data encryption in Redis."""

    async def test_token_data_encrypted_in_redis(
        self,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Verify token data is encrypted when stored in Redis."""
        # Create test user
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

        # Generate and store token
        token = secrets.token_urlsafe(48)
        await store_magic_link_token(
            redis_client=redis_client,
            token=token,
            user_id=user.id,
            workspace_id=user.workspace_id,
            email=user.email,
            expiry_seconds=600,
        )

        # Retrieve raw data from Redis
        raw_data = await redis_client.get(f"magic_link:{token}")

        # Should NOT be plain JSON (should be encrypted)
        assert raw_data is not None
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw_data)

        # Should contain Fernet token markers (starts with 'gAAAAA')
        # Raw data might be str or bytes depending on Redis configuration
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
        # Create test user
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

        # Generate and store encrypted token
        token = secrets.token_urlsafe(48)
        await store_magic_link_token(
            redis_client=redis_client,
            token=token,
            user_id=user.id,
            workspace_id=user.workspace_id,
            email=user.email,
            expiry_seconds=600,
        )

        # Retrieve and decrypt
        token_data = await retrieve_magic_link_token(redis_client, token)

        assert token_data is not None
        assert token_data["user_id"] == str(user.id)
        assert token_data["workspace_id"] == str(user.workspace_id)
        assert token_data["email"] == user.email

    async def test_corrupted_token_data_handled(
        self,
        redis_client,
    ):
        """Verify corrupted encrypted data doesn't crash the system."""
        # Store corrupted data
        token = secrets.token_urlsafe(48)
        await redis_client.setex(f"magic_link:{token}", 600, "corrupted_data")

        # Should return None without crashing
        token_data = await retrieve_magic_link_token(redis_client, token)
        assert token_data is None

        # Corrupted token should be deleted
        exists = await redis_client.exists(f"magic_link:{token}")
        assert exists == 0, "Corrupted token should be deleted"

    async def test_token_encryption_uses_fernet(
        self,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Verify token encryption uses Fernet (AES-128 + HMAC)."""
        from cryptography.fernet import Fernet, InvalidToken

        # Create test user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="fernet-test@example.com",
            full_name="Fernet Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Store token
        token = secrets.token_urlsafe(48)
        await store_magic_link_token(
            redis_client=redis_client,
            token=token,
            user_id=user.id,
            workspace_id=user.workspace_id,
            email=user.email,
            expiry_seconds=600,
        )

        # Get raw encrypted data
        raw_data = await redis_client.get(f"magic_link:{token}")

        # Try to decrypt with wrong key (should fail)
        wrong_cipher = Fernet(Fernet.generate_key())
        with pytest.raises(InvalidToken):
            wrong_cipher.decrypt(raw_data.encode() if isinstance(raw_data, str) else raw_data)

    async def test_encryption_preserves_all_token_fields(
        self,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Verify encryption preserves all token data fields."""
        # Create test user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="fields-test@example.com",
            full_name="Fields Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Store token
        token = secrets.token_urlsafe(48)
        await store_magic_link_token(
            redis_client=redis_client,
            token=token,
            user_id=user.id,
            workspace_id=user.workspace_id,
            email=user.email,
            expiry_seconds=600,
        )

        # Retrieve and verify all fields
        token_data = await retrieve_magic_link_token(redis_client, token)

        assert token_data is not None
        assert "user_id" in token_data
        assert "workspace_id" in token_data
        assert "email" in token_data
        assert len(token_data) == 3  # Exactly 3 fields, no more


class TestEndToEndSecurity:
    """Test complete authentication flow with security enhancements."""

    async def test_complete_auth_flow_with_encryption_and_384bit_token(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Verify complete auth flow works with 384-bit encrypted tokens."""
        # Create test user
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="e2e-test@example.com",
            full_name="E2E Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        # Request magic link
        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": "e2e-test@example.com"},
        )
        assert response.status_code == 200

        # Get token from Redis
        keys = await redis_client.keys("magic_link:*")
        assert len(keys) == 1
        token_key = keys[0].decode() if isinstance(keys[0], bytes) else keys[0]
        token = token_key.replace("magic_link:", "")

        # Verify token is 64 chars (384 bits)
        assert len(token) == 64

        # Verify token data is encrypted
        raw_data = await redis_client.get(f"magic_link:{token}")
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw_data)

        # Verify token
        response = await client.post("/api/v1/auth/verify", json={"token": token})
        assert response.status_code == 200

        # Check JWT is returned
        data = response.json()
        assert "access_token" in data
        assert data["user"]["id"] == str(user.id)

        # Token should be deleted (single-use)
        token_exists = await redis_client.exists(f"magic_link:{token}")
        assert token_exists == 0

    async def test_failed_attempts_dont_leak_user_existence(
        self,
        client: AsyncClient,
        redis_client,
    ):
        """Verify failed attempts return consistent error (no user enumeration)."""
        # Make failed attempts
        responses = []
        for _ in range(10):
            fake_token = secrets.token_urlsafe(48)
            response = await client.post(
                "/api/v1/auth/verify",
                json={"token": fake_token},
            )
            responses.append(response.status_code)

        # All should return 401 (not 404 or different codes)
        assert all(code == 401 for code in responses), (
            "All failed attempts should return 401 (no user enumeration)"
        )

    async def test_brute_force_detection_with_encrypted_tokens(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        db: AsyncSession,
        redis_client,
    ):
        """Verify brute force detection works with encrypted tokens."""
        # Create valid user and token
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            email="bf-test@example.com",
            full_name="BF Test",
            role=UserRole.OWNER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        valid_token = secrets.token_urlsafe(48)
        await store_magic_link_token(
            redis_client=redis_client,
            token=valid_token,
            user_id=user.id,
            workspace_id=user.workspace_id,
            email=user.email,
            expiry_seconds=600,
        )

        # Manually trigger brute force lockout
        await redis_client.set("magic_link_failed_attempts", BRUTE_FORCE_THRESHOLD)
        await redis_client.expire("magic_link_failed_attempts", BRUTE_FORCE_LOCKOUT_SECONDS)

        # Even valid token should be blocked during lockout
        response = await client.post("/api/v1/auth/verify", json={"token": valid_token})
        assert response.status_code == 429, (
            "Brute force lockout should block even valid tokens"
        )

        # Clear lockout
        await redis_client.delete("magic_link_failed_attempts")

        # Now valid token should work
        response = await client.post("/api/v1/auth/verify", json={"token": valid_token})
        assert response.status_code == 200
