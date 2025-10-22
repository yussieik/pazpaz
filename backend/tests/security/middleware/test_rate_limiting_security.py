"""Test rate limiting failure modes and security scenarios.

Tests fail-closed (auth) and fail-open with fallback (autosave) behaviors.

Security Requirements:
- Auth endpoints must fail closed when Redis is unavailable
- Autosave endpoints fall back to in-memory rate limiting
- Rate limits are enforced correctly in both modes

Reference: Week 2, Task 2.4 - Rate Limiting Failure Modes
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
import redis.asyncio as redis

from pazpaz.core.rate_limiting import (
    _fallback_rate_limits,
    check_rate_limit_redis,
)


class TestRateLimitingFailureModes:
    """Test rate limiting behavior when Redis is unavailable."""

    @pytest.mark.asyncio
    async def test_auth_rate_limit_fails_closed_on_redis_error(self):
        """Verify auth endpoints reject requests when Redis is unavailable."""
        broken_redis = MagicMock(spec=redis.Redis)
        broken_redis.pipeline.side_effect = redis.ConnectionError("Redis unavailable")

        result = await check_rate_limit_redis(
            redis_client=broken_redis,
            key="magic_link_rate_limit:192.168.1.1",
            max_requests=3,
            window_seconds=3600,
            fail_closed_on_error=True,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_autosave_uses_fallback_on_redis_error(self):
        """Verify autosave uses in-memory fallback when Redis is unavailable."""
        _fallback_rate_limits.clear()

        broken_redis = MagicMock(spec=redis.Redis)
        broken_redis.pipeline.side_effect = redis.ConnectionError("Redis unavailable")

        result = await check_rate_limit_redis(
            redis_client=broken_redis,
            key="draft_autosave:user-123:session-456",
            max_requests=60,
            window_seconds=60,
            fail_closed_on_error=False,
        )

        assert result is True
        assert "draft_autosave:user-123:session-456" in _fallback_rate_limits

    @pytest.mark.asyncio
    async def test_autosave_fallback_enforces_rate_limit(self):
        """Verify fallback rate limiter enforces limits when Redis is down."""
        _fallback_rate_limits.clear()

        broken_redis = MagicMock(spec=redis.Redis)
        broken_redis.pipeline.side_effect = redis.ConnectionError("Redis unavailable")

        key = "draft_autosave:user-789:session-999"
        max_requests = 5
        window_seconds = 60

        for i in range(5):
            result = await check_rate_limit_redis(
                redis_client=broken_redis,
                key=key,
                max_requests=max_requests,
                window_seconds=window_seconds,
                fail_closed_on_error=False,
            )
            assert result is True, f"Request {i + 1} should be allowed"

        result = await check_rate_limit_redis(
            redis_client=broken_redis,
            key=key,
            max_requests=max_requests,
            window_seconds=window_seconds,
            fail_closed_on_error=False,
        )
        assert result is False


class TestRedisRateLimitingNormalOperation:
    """Test rate limiting works correctly when Redis is available."""

    @pytest.mark.asyncio
    async def test_rate_limit_allows_requests_within_limit(self, redis_client):
        """Verify requests are allowed when within rate limit."""
        key = f"test_allow:{datetime.now(UTC).timestamp()}"

        result = await check_rate_limit_redis(
            redis_client=redis_client,
            key=key,
            max_requests=5,
            window_seconds=60,
            fail_closed_on_error=False,
        )

        assert result is True
        await redis_client.delete(key)

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_requests_over_limit(self, redis_client):
        """Verify requests are blocked when exceeding rate limit."""
        key = f"test_block:{datetime.now(UTC).timestamp()}"
        max_requests = 3

        for _ in range(max_requests):
            result = await check_rate_limit_redis(
                redis_client=redis_client,
                key=key,
                max_requests=max_requests,
                window_seconds=60,
                fail_closed_on_error=False,
            )
            assert result is True

        result = await check_rate_limit_redis(
            redis_client=redis_client,
            key=key,
            max_requests=max_requests,
            window_seconds=60,
            fail_closed_on_error=False,
        )

        assert result is False
        await redis_client.delete(key)
