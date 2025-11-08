"""Unit tests for AICacheService."""

import uuid

import pytest
from redis.asyncio import Redis

from pazpaz.services.cache_service import AICacheService


@pytest.mark.asyncio
class TestAICacheService:
    """Test suite for AICacheService cache invalidation."""

    @pytest.fixture
    async def cache_service(self, redis_client):
        """Create AICacheService instance."""
        return AICacheService(redis_client)

    @pytest.fixture
    async def test_workspace_id(self):
        """Generate test workspace ID."""
        return uuid.uuid4()

    @pytest.fixture
    async def test_client_id(self):
        """Generate test client ID."""
        return uuid.uuid4()

    @pytest.fixture
    async def seed_cache_keys(self, redis_client, test_workspace_id, test_client_id):
        """Seed Redis with test cache keys."""
        # Create client-specific keys
        client_keys = [
            f"ai:query:{test_workspace_id}:hash1:{test_client_id}",
            f"ai:query:{test_workspace_id}:hash2:{test_client_id}",
            f"ai:query:{test_workspace_id}:hash3:{test_client_id}",
        ]

        # Create workspace-wide keys (no client_id)
        workspace_keys = [
            f"ai:query:{test_workspace_id}:hash4",
            f"ai:query:{test_workspace_id}:hash5",
        ]

        # Create keys for different workspace (should not be deleted)
        other_workspace_id = uuid.uuid4()
        other_keys = [
            f"ai:query:{other_workspace_id}:hash6",
        ]

        # Set all keys
        all_keys = client_keys + workspace_keys + other_keys
        for key in all_keys:
            await redis_client.set(key, '{"answer": "test"}')

        yield {
            "client_keys": client_keys,
            "workspace_keys": workspace_keys,
            "other_keys": other_keys,
            "total_keys": all_keys,
        }

        # Cleanup
        for key in all_keys:
            await redis_client.delete(key)

    async def test_invalidate_client_queries_deletes_only_client_keys(
        self,
        cache_service,
        redis_client,
        test_workspace_id,
        test_client_id,
        seed_cache_keys,
    ):
        """Test that invalidate_client_queries deletes only client-specific keys."""
        # Invalidate client queries
        deleted = await cache_service.invalidate_client_queries(
            workspace_id=test_workspace_id,
            client_id=test_client_id,
        )

        # Should delete exactly 3 client-specific keys
        assert deleted == 3

        # Verify client keys are deleted
        for key in seed_cache_keys["client_keys"]:
            exists = await redis_client.exists(key)
            assert exists == 0, f"Client key {key} should be deleted"

        # Verify workspace-wide keys still exist
        for key in seed_cache_keys["workspace_keys"]:
            exists = await redis_client.exists(key)
            assert exists == 1, f"Workspace key {key} should still exist"

        # Verify other workspace keys still exist
        for key in seed_cache_keys["other_keys"]:
            exists = await redis_client.exists(key)
            assert exists == 1, f"Other workspace key {key} should still exist"

    async def test_invalidate_workspace_queries_deletes_all_workspace_keys(
        self,
        cache_service,
        redis_client,
        test_workspace_id,
        seed_cache_keys,
    ):
        """Test that invalidate_workspace_queries deletes all workspace keys."""
        # Invalidate all workspace queries
        deleted = await cache_service.invalidate_workspace_queries(
            workspace_id=test_workspace_id,
        )

        # Should delete 5 keys (3 client + 2 workspace-wide)
        assert deleted == 5

        # Verify all workspace keys are deleted
        for key in seed_cache_keys["client_keys"] + seed_cache_keys["workspace_keys"]:
            exists = await redis_client.exists(key)
            assert exists == 0, f"Workspace key {key} should be deleted"

        # Verify other workspace keys still exist
        for key in seed_cache_keys["other_keys"]:
            exists = await redis_client.exists(key)
            assert exists == 1, f"Other workspace key {key} should still exist"

    async def test_invalidate_client_queries_no_matching_keys(
        self,
        cache_service,
        test_workspace_id,
    ):
        """Test invalidation when no matching keys exist."""
        # Try to invalidate for a client with no cached queries
        non_existent_client_id = uuid.uuid4()
        deleted = await cache_service.invalidate_client_queries(
            workspace_id=test_workspace_id,
            client_id=non_existent_client_id,
        )

        # Should delete 0 keys
        assert deleted == 0

    async def test_invalidate_workspace_queries_no_matching_keys(
        self,
        cache_service,
    ):
        """Test invalidation when no matching keys exist."""
        # Try to invalidate for a workspace with no cached queries
        non_existent_workspace_id = uuid.uuid4()
        deleted = await cache_service.invalidate_workspace_queries(
            workspace_id=non_existent_workspace_id,
        )

        # Should delete 0 keys
        assert deleted == 0

    async def test_invalidate_client_queries_handles_redis_errors(
        self,
        test_workspace_id,
        test_client_id,
    ):
        """Test that cache invalidation handles Redis connection errors gracefully."""
        # Create service with invalid Redis connection
        invalid_redis = Redis(host="invalid-host", port=9999, decode_responses=True)
        cache_service = AICacheService(invalid_redis)

        # Should not raise exception, just return 0
        deleted = await cache_service.invalidate_client_queries(
            workspace_id=test_workspace_id,
            client_id=test_client_id,
        )

        assert deleted == 0

        await invalid_redis.aclose()

    async def test_cache_key_pattern_correctness(
        self,
        redis_client,
        test_workspace_id,
        test_client_id,
    ):
        """Test that cache key pattern matching works correctly."""
        # Create keys with specific patterns
        key1 = f"ai:query:{test_workspace_id}:abc123:{test_client_id}"
        key2 = f"ai:query:{test_workspace_id}:def456:{test_client_id}"
        key3 = f"ai:query:{test_workspace_id}:ghi789"  # No client_id

        await redis_client.set(key1, "test1")
        await redis_client.set(key2, "test2")
        await redis_client.set(key3, "test3")

        # Create service
        cache_service = AICacheService(redis_client)

        # Invalidate client queries
        deleted = await cache_service.invalidate_client_queries(
            workspace_id=test_workspace_id,
            client_id=test_client_id,
        )

        # Should delete exactly keys 1 and 2 (have client_id)
        assert deleted == 2

        # Cleanup
        await redis_client.delete(key3)
