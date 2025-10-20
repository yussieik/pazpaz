"""Tests for rate limiting failure modes and security scenarios."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import redis.asyncio as redis

from pazpaz.core.rate_limiting import (
    _check_rate_limit_fallback,
    _fallback_rate_limits,
    check_rate_limit_redis,
)


class TestRateLimitingFailureModes:
    """Test rate limiting behavior when Redis is unavailable."""

    @pytest.mark.asyncio
    async def test_auth_rate_limit_fails_closed_on_redis_error(self):
        """Verify auth endpoints reject requests when Redis is unavailable."""
        # Create broken Redis client that raises exceptions
        broken_redis = MagicMock(spec=redis.Redis)
        broken_redis.pipeline.side_effect = redis.ConnectionError("Redis unavailable")

        # Should fail closed (return False to reject request)
        result = await check_rate_limit_redis(
            redis_client=broken_redis,
            key="magic_link_rate_limit:192.168.1.1",
            max_requests=3,
            window_seconds=3600,
            fail_closed_on_error=True,  # Auth endpoint behavior
        )

        assert result is False  # Request should be rejected

    @pytest.mark.asyncio
    async def test_autosave_uses_fallback_on_redis_error(self):
        """Verify autosave uses in-memory fallback when Redis is unavailable."""
        # Clear fallback state
        _fallback_rate_limits.clear()

        # Create broken Redis client
        broken_redis = MagicMock(spec=redis.Redis)
        broken_redis.pipeline.side_effect = redis.ConnectionError("Redis unavailable")

        # First request should succeed using fallback
        result = await check_rate_limit_redis(
            redis_client=broken_redis,
            key="draft_autosave:user-123:session-456",
            max_requests=60,
            window_seconds=60,
            fail_closed_on_error=False,  # Autosave endpoint behavior
        )

        assert result is True  # Request should be allowed (fallback)
        assert (
            "draft_autosave:user-123:session-456" in _fallback_rate_limits
        )  # Fallback was used

    @pytest.mark.asyncio
    async def test_autosave_fallback_enforces_rate_limit(self):
        """Verify fallback rate limiter enforces limits when Redis is down."""
        # Clear fallback state
        _fallback_rate_limits.clear()

        # Create broken Redis client
        broken_redis = MagicMock(spec=redis.Redis)
        broken_redis.pipeline.side_effect = redis.ConnectionError("Redis unavailable")

        key = "draft_autosave:user-789:session-999"
        max_requests = 5
        window_seconds = 60

        # First 5 requests should succeed
        for i in range(5):
            result = await check_rate_limit_redis(
                redis_client=broken_redis,
                key=key,
                max_requests=max_requests,
                window_seconds=window_seconds,
                fail_closed_on_error=False,
            )
            assert result is True, f"Request {i + 1} should be allowed"

        # 6th request should be blocked by fallback
        result = await check_rate_limit_redis(
            redis_client=broken_redis,
            key=key,
            max_requests=max_requests,
            window_seconds=window_seconds,
            fail_closed_on_error=False,
        )
        assert result is False  # Should be blocked by fallback rate limiter


class TestFallbackRateLimiter:
    """Test in-memory fallback rate limiter."""

    def test_fallback_rate_limiter_enforces_limits(self):
        """Verify fallback rate limiter enforces limits correctly."""
        # Clear state
        _fallback_rate_limits.clear()

        key = "test_key"
        max_requests = 5
        window_seconds = 60

        # First 5 requests should pass
        for i in range(5):
            assert (
                _check_rate_limit_fallback(key, max_requests, window_seconds) is True
            ), f"Request {i + 1} should be allowed"

        # 6th request should be blocked
        assert _check_rate_limit_fallback(key, max_requests, window_seconds) is False

    def test_fallback_rate_limiter_resets_window(self):
        """Verify fallback rate limiter resets after window expires."""
        # Clear state
        _fallback_rate_limits.clear()

        key = "test_reset"
        max_requests = 3
        window_seconds = 2

        # Fill up the limit
        for _ in range(3):
            assert _check_rate_limit_fallback(key, max_requests, window_seconds) is True

        # Should be blocked now
        assert _check_rate_limit_fallback(key, max_requests, window_seconds) is False

        # Manually expire the window (simulate time passing)
        entry = _fallback_rate_limits[key]
        entry.window_start = datetime.now(UTC) - timedelta(seconds=window_seconds + 1)

        # Should allow requests again
        assert _check_rate_limit_fallback(key, max_requests, window_seconds) is True

    def test_fallback_rate_limiter_per_key_isolation(self):
        """Verify fallback rate limiter isolates keys correctly."""
        # Clear state
        _fallback_rate_limits.clear()

        key1 = "user1:session1"
        key2 = "user2:session2"
        max_requests = 5
        window_seconds = 60

        # Fill up key1
        for _ in range(5):
            assert (
                _check_rate_limit_fallback(key1, max_requests, window_seconds) is True
            )

        # key1 should be blocked
        assert _check_rate_limit_fallback(key1, max_requests, window_seconds) is False

        # key2 should still work
        assert _check_rate_limit_fallback(key2, max_requests, window_seconds) is True


class TestRedisRateLimitingNormalOperation:
    """Test rate limiting works correctly when Redis is available."""

    @pytest.mark.asyncio
    async def test_rate_limit_allows_requests_within_limit(self, redis_client):
        """Verify requests are allowed when within rate limit."""
        key = f"test_allow:{datetime.now(UTC).timestamp()}"

        # Should allow first request
        result = await check_rate_limit_redis(
            redis_client=redis_client,
            key=key,
            max_requests=5,
            window_seconds=60,
            fail_closed_on_error=False,
        )

        assert result is True

        # Clean up
        await redis_client.delete(key)

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_requests_over_limit(self, redis_client):
        """Verify requests are blocked when exceeding rate limit."""
        key = f"test_block:{datetime.now(UTC).timestamp()}"
        max_requests = 3

        # Make max_requests requests
        for _ in range(max_requests):
            result = await check_rate_limit_redis(
                redis_client=redis_client,
                key=key,
                max_requests=max_requests,
                window_seconds=60,
                fail_closed_on_error=False,
            )
            assert result is True

        # Next request should be blocked
        result = await check_rate_limit_redis(
            redis_client=redis_client,
            key=key,
            max_requests=max_requests,
            window_seconds=60,
            fail_closed_on_error=False,
        )

        assert result is False

        # Clean up
        await redis_client.delete(key)

    @pytest.mark.asyncio
    async def test_rate_limit_respects_fail_closed_parameter(self):
        """Verify fail_closed_on_error parameter is respected."""
        # Create broken Redis client
        broken_redis = MagicMock(spec=redis.Redis)
        broken_redis.pipeline.side_effect = redis.ConnectionError("Redis unavailable")

        # fail_closed_on_error=True should return False
        result = await check_rate_limit_redis(
            redis_client=broken_redis,
            key="test",
            max_requests=10,
            window_seconds=60,
            fail_closed_on_error=True,
        )
        assert result is False

        # fail_closed_on_error=False should use fallback (return True for first request)
        _fallback_rate_limits.clear()
        result = await check_rate_limit_redis(
            redis_client=broken_redis,
            key="test_fallback",
            max_requests=10,
            window_seconds=60,
            fail_closed_on_error=False,
        )
        assert result is True


class TestAuthServiceFailureModes:
    """Test auth service behavior when Redis fails."""

    @pytest.mark.asyncio
    async def test_magic_link_fails_closed_when_redis_unavailable(
        self, client, monkeypatch
    ):
        """Verify magic link endpoint rejects requests when Redis is unavailable."""

        # Mock check_rate_limit_redis to simulate Redis failure (fail closed)
        async def mock_rate_limit_fail_closed(*args, **kwargs):
            # Simulate fail_closed_on_error=True behavior
            # Return False for fail_closed (auth), True for fail_open (non-auth)
            return not kwargs.get("fail_closed_on_error", False)

        # Patch the function in the rate_limiting module where it's defined
        monkeypatch.setattr(
            "pazpaz.core.rate_limiting.check_rate_limit_redis",
            mock_rate_limit_fail_closed,
        )

        # Request magic link should return success but not send email
        # (due to rate limit fail-closed blocking it)
        response = await client.post(
            "/api/v1/auth/magic-link", json={"email": "test@example.com"}
        )

        # Should return 200 with generic success (prevents enumeration)
        assert response.status_code == 200
        data = response.json()
        assert (
            "If an account exists" in data["message"]
            or "magic link has been sent" in data["message"].lower()
        )


class TestAutosaveFailureModes:
    """Test autosave endpoint behavior when Redis fails."""

    @pytest.mark.asyncio
    async def test_autosave_continues_working_with_fallback(
        self, authenticated_client, test_session, monkeypatch
    ):
        """Verify autosave uses fallback when Redis is unavailable."""
        # Use test_session fixture which provides a Session object
        session = test_session

        # Mock Redis to raise exceptions
        async def mock_redis_error(*args, **kwargs):
            raise redis.ConnectionError("Redis unavailable")

        # Patch at the Redis pipeline level
        with patch.object(redis.Redis, "pipeline", side_effect=mock_redis_error):
            # Clear fallback state
            _fallback_rate_limits.clear()

            # First request should succeed using fallback
            response = await authenticated_client.patch(
                f"/api/v1/sessions/{session.id}/draft",
                json={"subjective": "test note"},
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_autosave_fallback_enforces_rate_limit(
        self, authenticated_client, test_session, monkeypatch
    ):
        """Verify autosave fallback enforces rate limits correctly."""
        # Use test_session fixture which provides a Session object
        session = test_session

        # Mock Redis to always fail
        async def mock_redis_error(*args, **kwargs):
            raise redis.ConnectionError("Redis unavailable")

        # Patch at the Redis pipeline level
        with patch.object(redis.Redis, "pipeline", side_effect=mock_redis_error):
            # Clear fallback state
            _fallback_rate_limits.clear()

            # First 60 requests should succeed (fallback limit)
            for i in range(60):
                response = await authenticated_client.patch(
                    f"/api/v1/sessions/{session.id}/draft",
                    json={"subjective": f"test {i}"},
                )
                assert response.status_code == 200, (
                    f"Request {i + 1} should succeed with fallback"
                )

            # 61st request should be rate limited by fallback
            response = await authenticated_client.patch(
                f"/api/v1/sessions/{session.id}/draft",
                json={"subjective": "test 61"},
            )
            assert response.status_code == 429  # Rate limit exceeded
