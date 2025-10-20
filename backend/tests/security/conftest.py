"""Security test fixtures with comprehensive rate limit handling.

This module provides fixtures to prevent test failures due to rate limiting:
1. clear_rate_limits - Clears all rate limit keys before each test
2. rate_limit_delay - Adds small delays between tests to avoid bursts
3. mock_rate_limit_bypass - Bypasses rate limiting entirely for specific tests

CRITICAL: These fixtures prevent the 429 (Too Many Requests) errors that occur
when tests exceed the 1000 requests/hour global rate limit.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def clear_rate_limits(redis_client):
    """Clear all rate limit keys before each test.

    This fixture automatically runs before each security test to ensure
    clean rate limit state. Prevents cascading failures when running
    full test suite.

    Clears:
    - rate_limit:* - Global rate limits
    - magic_link_* - Magic link specific counters
    - magic_link_failed_attempts - Brute force detection counter
    - draft_autosave:* - Autosave rate limits
    """
    # Clear all rate limit keys
    keys = await redis_client.keys("rate_limit:*")
    if keys:
        await redis_client.delete(*keys)

    # Clear magic link rate limits
    keys = await redis_client.keys("magic_link_rate_limit:*")
    if keys:
        await redis_client.delete(*keys)

    keys = await redis_client.keys("magic_link_rate_limit_email:*")
    if keys:
        await redis_client.delete(*keys)

    # Clear brute force counter
    await redis_client.delete("magic_link_failed_attempts")

    # Clear autosave rate limits
    keys = await redis_client.keys("draft_autosave:*")
    if keys:
        await redis_client.delete(*keys)

    yield  # Run test

    # Optional: Clear again after test (for paranoid cleanup)
    keys = await redis_client.keys("rate_limit:*")
    if keys:
        await redis_client.delete(*keys)


@pytest_asyncio.fixture
async def rate_limit_delay():
    """Add small delay to avoid rate limit bursts.

    Use this fixture in tests that make many rapid requests.
    The delay is small enough to not significantly impact test speed
    but large enough to prevent hitting burst limits.

    Usage:
        async def test_something(rate_limit_delay):
            # Test runs after delay
            ...
    """
    await asyncio.sleep(0.05)  # 50ms delay


@pytest.fixture
def mock_rate_limit_bypass(monkeypatch):
    """Bypass rate limiting for tests that need many requests.

    This fixture mocks the rate limiting function to always return True,
    effectively disabling rate limiting for the test.

    Usage:
        async def test_something(mock_rate_limit_bypass):
            # All requests pass rate limiting
            for i in range(1000):
                await make_request()
    """

    async def always_allow(*args, **kwargs):
        """Mock function that always allows requests."""
        return True

    # Patch the rate limiting function
    monkeypatch.setattr(
        "pazpaz.core.rate_limiting.check_rate_limit_redis", always_allow
    )


@pytest_asyncio.fixture
async def clear_brute_force_counter(redis_client):
    """Clear brute force detection counter.

    Use this fixture in tests that involve failed authentication attempts
    to ensure the brute force counter doesn't carry over between tests.

    Usage:
        async def test_auth_failure(clear_brute_force_counter):
            # Brute force counter is cleared
            ...
    """
    await redis_client.delete("magic_link_failed_attempts")
    yield
    await redis_client.delete("magic_link_failed_attempts")


@pytest_asyncio.fixture
async def unauthenticated_workspace(db_session):
    """Create the sentinel workspace for unauthenticated audit events.

    This workspace is used for audit events that occur before authentication,
    such as failed login attempts or invalid token submissions.
    """
    from sqlalchemy import select

    from pazpaz.models.workspace import Workspace
    from pazpaz.services.audit_service import UNAUTHENTICATED_WORKSPACE_ID

    # Check if it already exists
    query = select(Workspace).where(Workspace.id == UNAUTHENTICATED_WORKSPACE_ID)
    result = await db_session.execute(query)
    existing = result.scalar_one_or_none()

    if not existing:
        workspace = Workspace(
            id=UNAUTHENTICATED_WORKSPACE_ID,
            name="Unauthenticated Events",
            is_active=False,  # Not a real workspace
        )
        db_session.add(workspace)
        await db_session.commit()
        await db_session.refresh(workspace)
        return workspace

    return existing


@pytest.fixture
def mock_redis_failure(monkeypatch):
    """Mock Redis to simulate connection failures.

    Use this fixture to test fail-closed and fallback behaviors
    when Redis is unavailable.

    Usage:
        async def test_redis_failure(mock_redis_failure):
            # Redis operations will raise ConnectionError
            ...
    """
    import redis.asyncio as redis

    async def raise_connection_error(*args, **kwargs):
        raise redis.ConnectionError("Redis unavailable")

    # Patch Redis pipeline to fail
    monkeypatch.setattr("redis.asyncio.Redis.pipeline", raise_connection_error)


@pytest_asyncio.fixture
async def clear_all_test_data(redis_client, db_session):
    """Clear all test data from Redis and database.

    Nuclear option fixture for tests that need absolutely clean state.
    This is slower than individual fixtures, so use sparingly.

    Usage:
        async def test_clean_slate(clear_all_test_data):
            # Everything is cleared
            ...
    """
    # Clear Redis
    await redis_client.flushdb()

    # Truncate all database tables
    from sqlalchemy import text

    result = await db_session.execute(
        text(
            """
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
        """
        )
    )
    tables = [row[0] for row in result.fetchall()]

    if tables:
        tables_str = ", ".join(tables)
        await db_session.execute(
            text(f"TRUNCATE TABLE {tables_str} RESTART IDENTITY CASCADE")
        )
        await db_session.commit()

    yield

    # Cleanup after test
    await redis_client.flushdb()
