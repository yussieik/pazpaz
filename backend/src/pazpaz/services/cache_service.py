"""AI cache management service for invalidation."""

import uuid

from redis.asyncio import Redis

from pazpaz.ai.metrics import ai_agent_cache_invalidations_total
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


class AICacheService:
    """Service for managing AI agent cache invalidation."""

    def __init__(self, redis: Redis):
        self.redis = redis

    async def invalidate_client_queries(
        self,
        workspace_id: uuid.UUID,
        client_id: uuid.UUID,
    ) -> int:
        """
        Invalidate all cached queries for a specific client.

        Args:
            workspace_id: The workspace ID
            client_id: The client ID whose queries should be invalidated

        Returns:
            Number of cache keys deleted
        """
        pattern = f"ai:query:{workspace_id}:*:{client_id}"
        deleted = await self._delete_pattern(pattern)

        if deleted > 0:
            ai_agent_cache_invalidations_total.labels(
                workspace_id=str(workspace_id),
                reason="client_data_changed",
            ).inc()

            logger.info(
                "invalidated_client_queries",
                workspace_id=str(workspace_id),
                client_id=str(client_id),
                keys_deleted=deleted,
            )

        return deleted

    async def invalidate_workspace_queries(
        self,
        workspace_id: uuid.UUID,
    ) -> int:
        """
        Invalidate all cached queries for an entire workspace.

        Args:
            workspace_id: The workspace ID whose queries should be invalidated

        Returns:
            Number of cache keys deleted
        """
        pattern = f"ai:query:{workspace_id}:*"
        deleted = await self._delete_pattern(pattern)

        if deleted > 0:
            ai_agent_cache_invalidations_total.labels(
                workspace_id=str(workspace_id),
                reason="workspace_data_changed",
            ).inc()

            logger.info(
                "invalidated_workspace_queries",
                workspace_id=str(workspace_id),
                keys_deleted=deleted,
            )

        return deleted

    async def _delete_pattern(self, pattern: str) -> int:
        """
        Delete all Redis keys matching pattern.

        Args:
            pattern: Redis key pattern (supports * wildcard)

        Returns:
            Number of keys deleted
        """
        deleted = 0
        cursor = 0

        try:
            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)

                if keys:
                    deleted += await self.redis.delete(*keys)

                if cursor == 0:
                    break

        except Exception as e:
            logger.warning(
                "cache_invalidation_error",
                pattern=pattern,
                error=str(e),
            )

        return deleted
