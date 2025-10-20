"""
Test session idle timeout implementation.

Security Requirement: HIPAA §164.312(a)(2)(iii) - Automatic Logoff

This test suite verifies that the session idle timeout feature correctly:
1. Tracks user activity in Redis
2. Enforces automatic logout after configured idle period
3. Implements sliding window (activity updates on each request)
4. Invalidates activity records on logout
5. Provides appropriate error messages for timed-out sessions
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
import pytest_asyncio

from pazpaz.core.config import Settings
from pazpaz.core.security import create_access_token
from pazpaz.services.session_activity import (
    check_session_idle_timeout,
    invalidate_session_activity,
    update_session_activity,
)


@pytest_asyncio.fixture
async def auth_token(test_user_ws1):
    """Generate JWT token for testing."""
    token = create_access_token(
        user_id=test_user_ws1.id,
        workspace_id=test_user_ws1.workspace_id,
        email=test_user_ws1.email,
    )
    return token


class TestSessionActivityTracking:
    """Test session activity tracking in Redis."""

    @pytest.mark.asyncio
    async def test_update_session_activity_creates_record(self, redis_client):
        """Should create activity record with ISO 8601 timestamp."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        jti = "abc123def456"

        await update_session_activity(redis_client, user_id, jti)

        # Verify record exists
        key = f"session:activity:{user_id}:{jti}"
        timestamp_str = await redis_client.get(key)

        assert timestamp_str is not None
        # Verify it's a valid ISO 8601 timestamp
        timestamp = datetime.fromisoformat(timestamp_str)
        # Timestamp should be recent (within 5 seconds)
        assert (datetime.now(UTC) - timestamp).total_seconds() < 5

    @pytest.mark.asyncio
    async def test_update_session_activity_sets_ttl(self, redis_client):
        """Activity record should have 7-day TTL matching JWT expiration."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        jti = "abc123def456"

        await update_session_activity(redis_client, user_id, jti)

        key = f"session:activity:{user_id}:{jti}"
        ttl = await redis_client.ttl(key)

        # TTL should be ~7 days (604800 seconds)
        # Allow 100 second tolerance for test execution time
        assert 604700 < ttl <= 604800

    @pytest.mark.asyncio
    async def test_update_session_activity_updates_existing_record(self, redis_client):
        """Should update existing activity record with new timestamp."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        jti = "abc123def456"

        # Create initial record
        await update_session_activity(redis_client, user_id, jti)

        key = f"session:activity:{user_id}:{jti}"
        first_timestamp_str = await redis_client.get(key)

        # Wait a moment and update
        import asyncio

        await asyncio.sleep(1)

        await update_session_activity(redis_client, user_id, jti)

        second_timestamp_str = await redis_client.get(key)

        # Timestamps should be different
        assert first_timestamp_str != second_timestamp_str

        # Second timestamp should be later
        first_ts = datetime.fromisoformat(first_timestamp_str)
        second_ts = datetime.fromisoformat(second_timestamp_str)
        assert second_ts > first_ts

    @pytest.mark.asyncio
    async def test_check_session_idle_timeout_no_record(self, redis_client):
        """Should return active=True if no activity record exists (first request)."""
        user_id = "550e8400-e29b-41d4-a716-446655440001"
        jti = "new-session-token"

        is_active, idle_seconds = await check_session_idle_timeout(
            redis_client, user_id, jti
        )

        assert is_active is True
        assert idle_seconds is None

    @pytest.mark.asyncio
    async def test_check_session_idle_timeout_active_session(self, redis_client):
        """Should return active=True for recent activity (within timeout)."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        jti = "abc123def456"

        # Create activity record (just now)
        await update_session_activity(redis_client, user_id, jti)

        is_active, idle_seconds = await check_session_idle_timeout(
            redis_client, user_id, jti
        )

        assert is_active is True
        assert idle_seconds is not None
        assert idle_seconds < 5  # Should be very recent

    @pytest.mark.asyncio
    async def test_check_session_idle_timeout_expired_session(self, redis_client):
        """Should return active=False if idle timeout exceeded."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        jti = "abc123def456"

        # Create activity record 31 minutes ago (default timeout is 30 min)
        old_timestamp = datetime.now(UTC) - timedelta(minutes=31)
        key = f"session:activity:{user_id}:{jti}"
        await redis_client.setex(key, 3600, old_timestamp.isoformat())

        is_active, idle_seconds = await check_session_idle_timeout(
            redis_client, user_id, jti
        )

        assert is_active is False
        assert idle_seconds is not None
        assert idle_seconds >= 1860  # At least 31 minutes (1860 seconds)

    @pytest.mark.asyncio
    async def test_check_session_idle_timeout_just_before_threshold(self, redis_client):
        """Should return active=True just before timeout threshold."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        jti = "abc123def456"

        # Create activity record 29 minutes ago (just before 30-minute timeout)
        old_timestamp = datetime.now(UTC) - timedelta(minutes=29)
        key = f"session:activity:{user_id}:{jti}"
        await redis_client.setex(key, 3600, old_timestamp.isoformat())

        is_active, idle_seconds = await check_session_idle_timeout(
            redis_client, user_id, jti
        )

        # At 29 minutes (under 30-minute threshold), should still be active
        # Timeout triggers when idle_seconds > timeout_seconds
        assert is_active is True
        assert idle_seconds is not None
        assert 1735 <= idle_seconds <= 1745  # ~29 minutes

    @pytest.mark.asyncio
    async def test_check_session_idle_timeout_redis_error_fails_open(
        self, redis_client
    ):
        """Should fail open (return active=True) on Redis errors."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        jti = "abc123def456"

        # Mock Redis error
        with patch.object(redis_client, "get", side_effect=Exception("Redis error")):
            is_active, idle_seconds = await check_session_idle_timeout(
                redis_client, user_id, jti
            )

        # Should fail open (allow request)
        assert is_active is True
        assert idle_seconds is None

    @pytest.mark.asyncio
    async def test_invalidate_session_activity_removes_record(self, redis_client):
        """Should remove activity record from Redis."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        jti = "abc123def456"

        # Create activity record
        await update_session_activity(redis_client, user_id, jti)

        # Verify it exists
        key = f"session:activity:{user_id}:{jti}"
        exists_before = await redis_client.exists(key)
        assert exists_before == 1

        # Invalidate
        await invalidate_session_activity(redis_client, user_id, jti)

        # Verify it's gone
        exists_after = await redis_client.exists(key)
        assert exists_after == 0

    @pytest.mark.asyncio
    async def test_invalidate_session_activity_idempotent(self, redis_client):
        """Invalidating non-existent activity record should not error."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        jti = "nonexistent"

        # Should not raise error
        await invalidate_session_activity(redis_client, user_id, jti)


class TestSessionIdleTimeoutMiddleware:
    """Test session activity middleware behavior."""

    @pytest.mark.asyncio
    async def test_middleware_allows_recent_activity(
        self, client, test_user_ws1, auth_headers
    ):
        """Middleware should allow requests with recent activity."""
        # Make request (will create activity record)
        response = await client.get("/api/v1/clients", headers=auth_headers)
        assert response.status_code == 200

        # Make another request immediately (should be allowed)
        response = await client.get("/api/v1/clients", headers=auth_headers)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_middleware_rejects_idle_timeout(
        self, client, redis_client, test_user_ws1, auth_token
    ):
        """Middleware should reject requests after idle timeout."""
        from pazpaz.core.security import decode_access_token

        # Decode token to get jti
        payload = decode_access_token(auth_token)
        jti = payload["jti"]

        # Create old activity record (31 minutes ago)
        old_timestamp = datetime.now(UTC) - timedelta(minutes=31)
        key = f"session:activity:{test_user_ws1.id}:{jti}"
        await redis_client.setex(key, 3600, old_timestamp.isoformat())

        # Make request (should be rejected)
        headers = {"Cookie": f"access_token={auth_token}"}
        response = await client.get("/api/v1/clients", headers=headers)

        assert response.status_code == 401
        data = response.json()
        assert data["error_code"] == "SESSION_IDLE_TIMEOUT"
        assert "inactivity" in data["detail"].lower()
        assert "idle_seconds" in data
        assert data["idle_seconds"] > 1860  # More than 31 minutes

    @pytest.mark.asyncio
    async def test_middleware_updates_activity_on_success(
        self, client, redis_client, test_user_ws1, auth_headers, auth_token
    ):
        """Middleware should update activity timestamp on successful requests."""
        from pazpaz.core.security import decode_access_token

        payload = decode_access_token(auth_token)
        jti = payload["jti"]
        key = f"session:activity:{test_user_ws1.id}:{jti}"

        # Make request
        response = await client.get("/api/v1/clients", headers=auth_headers)
        assert response.status_code == 200

        # Verify activity record was created/updated
        timestamp_str = await redis_client.get(key)
        assert timestamp_str is not None

        timestamp = datetime.fromisoformat(timestamp_str)
        assert (datetime.now(UTC) - timestamp).total_seconds() < 5

    @pytest.mark.asyncio
    async def test_middleware_does_not_update_on_error(
        self, client, redis_client, test_user_ws1, auth_headers, auth_token
    ):
        """Middleware should not update activity on failed requests (4xx/5xx)."""
        from pazpaz.core.security import decode_access_token

        payload = decode_access_token(auth_token)
        jti = payload["jti"]

        # Create activity record 5 minutes ago
        old_timestamp = datetime.now(UTC) - timedelta(minutes=5)
        key = f"session:activity:{test_user_ws1.id}:{jti}"
        await redis_client.setex(key, 3600, old_timestamp.isoformat())

        # Make request to non-existent endpoint (404)
        response = await client.get(
            "/api/v1/nonexistent", headers=auth_headers
        )
        assert response.status_code == 404

        # Verify activity record was NOT updated
        timestamp_str = await redis_client.get(key)
        timestamp = datetime.fromisoformat(timestamp_str)

        # Timestamp should still be old (within 1 second tolerance)
        age = (datetime.now(UTC) - timestamp).total_seconds()
        assert 295 <= age <= 305  # ~5 minutes

    @pytest.mark.asyncio
    async def test_middleware_exempt_paths_not_tracked(self, client):
        """Middleware should skip exempt paths (auth, docs, health)."""
        # Auth endpoints should not track activity
        response = await client.get("/docs")
        assert response.status_code == 200

        response = await client.get("/health")
        assert response.status_code == 200

        # No activity records should be created (no auth token)

    @pytest.mark.asyncio
    async def test_middleware_handles_missing_token(self, client):
        """Middleware should pass through requests without auth token."""
        # Request without auth token should pass through to auth middleware
        response = await client.get("/api/v1/clients")

        # Should fail authentication (not idle timeout)
        assert response.status_code == 401
        data = response.json()
        # Should not have SESSION_IDLE_TIMEOUT error code
        assert data.get("error_code") != "SESSION_IDLE_TIMEOUT"

    @pytest.mark.asyncio
    async def test_logout_invalidates_activity_record(
        self, client, redis_client, test_user_ws1, auth_headers, auth_token
    ):
        """Logout should remove activity record from Redis."""
        from pazpaz.core.security import decode_access_token

        payload = decode_access_token(auth_token)
        jti = payload["jti"]
        key = f"session:activity:{test_user_ws1.id}:{jti}"

        # Create activity record
        await update_session_activity(
            redis_client, str(test_user_ws1.id), jti
        )

        # Verify it exists
        exists_before = await redis_client.exists(key)
        assert exists_before == 1

        # Logout
        response = await client.post("/api/v1/auth/logout", headers=auth_headers)
        assert response.status_code == 200

        # Verify activity record removed
        exists_after = await redis_client.exists(key)
        assert exists_after == 0


class TestConfigurationValidation:
    """Test idle timeout configuration validation."""

    def test_validate_idle_timeout_minimum(self):
        """Idle timeout must be at least 5 minutes."""
        with pytest.raises(ValueError, match="at least 5 minutes"):
            Settings(session_idle_timeout_minutes=4)

    def test_validate_idle_timeout_maximum(self):
        """Idle timeout cannot exceed 8 hours (480 minutes)."""
        with pytest.raises(ValueError, match="cannot exceed 8 hours"):
            Settings(session_idle_timeout_minutes=481)

    def test_validate_idle_timeout_valid_range(self):
        """Valid timeout values should be accepted."""
        # 15 minutes (common HIPAA recommendation)
        settings = Settings(session_idle_timeout_minutes=15)
        assert settings.session_idle_timeout_minutes == 15

        # 30 minutes (default)
        settings = Settings(session_idle_timeout_minutes=30)
        assert settings.session_idle_timeout_minutes == 30

        # 60 minutes (1 hour)
        settings = Settings(session_idle_timeout_minutes=60)
        assert settings.session_idle_timeout_minutes == 60

        # 480 minutes (8 hours - maximum)
        settings = Settings(session_idle_timeout_minutes=480)
        assert settings.session_idle_timeout_minutes == 480


class TestSlidingWindowBehavior:
    """Test sliding window session timeout behavior."""

    @pytest.mark.asyncio
    async def test_sliding_window_extends_session(
        self, client, redis_client, test_user_ws1, auth_headers, auth_token
    ):
        """Activity should extend session lifetime (sliding window)."""
        from pazpaz.core.security import decode_access_token

        payload = decode_access_token(auth_token)
        jti = payload["jti"]
        key = f"session:activity:{test_user_ws1.id}:{jti}"

        # Create activity record 25 minutes ago
        old_timestamp = datetime.now(UTC) - timedelta(minutes=25)
        await redis_client.setex(key, 3600, old_timestamp.isoformat())

        # Make request (should update activity)
        response = await client.get("/api/v1/clients", headers=auth_headers)
        assert response.status_code == 200

        # Verify activity was updated to recent timestamp
        new_timestamp_str = await redis_client.get(key)
        new_timestamp = datetime.fromisoformat(new_timestamp_str)

        # New timestamp should be very recent
        assert (datetime.now(UTC) - new_timestamp).total_seconds() < 5

    @pytest.mark.asyncio
    async def test_inactive_session_does_not_extend(
        self, client, redis_client, test_user_ws1, auth_token
    ):
        """Session that exceeds timeout should not be extended."""
        from pazpaz.core.security import decode_access_token

        payload = decode_access_token(auth_token)
        jti = payload["jti"]

        # Create old activity record (31 minutes ago - past timeout)
        old_timestamp = datetime.now(UTC) - timedelta(minutes=31)
        key = f"session:activity:{test_user_ws1.id}:{jti}"
        await redis_client.setex(key, 3600, old_timestamp.isoformat())

        # Make request (should be rejected)
        headers = {"Cookie": f"access_token={auth_token}"}
        response = await client.get("/api/v1/clients", headers=headers)
        assert response.status_code == 401

        # Verify activity was NOT updated (timestamp unchanged)
        timestamp_str = await redis_client.get(key)
        timestamp = datetime.fromisoformat(timestamp_str)

        # Timestamp should still be old
        assert (datetime.now(UTC) - timestamp).total_seconds() > 1860
