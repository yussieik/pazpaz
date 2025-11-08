"""
Vector store operations for pgvector session embeddings.

This module provides CRUD operations for SessionVector embeddings,
enabling semantic search across SOAP notes within a workspace.

Security:
- All queries enforce workspace_id filtering (multi-tenant isolation)
- Uses async SQLAlchemy for connection pooling
- pgvector HNSW index for fast cosine similarity search

Performance:
- Batch operations for inserting multiple embeddings
- Index-optimized similarity search (<10ms for <100k vectors)
- Connection pooling via existing database session

Architecture:
- Workspace-scoped (MANDATORY filtering on all queries)
- SOAP field granularity (one vector per field: subjective, objective, assessment, plan)
- Automatic cascade deletion (when session or workspace deleted)
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.logging import get_logger
from pazpaz.models.client_vector import ClientVector
from pazpaz.models.session_vector import SessionVector

logger = get_logger(__name__)


class VectorStoreError(Exception):
    """Exception raised when vector store operations fail."""

    pass


class VectorStore:
    """
    Vector store for session SOAP note embeddings.

    Provides CRUD operations for SessionVector with workspace isolation
    and semantic similarity search capabilities.

    All operations are workspace-scoped for multi-tenant security.

    Example:
        >>> async with get_db_session() as db:
        ...     store = VectorStore(db)
        ...     await store.insert_embedding(
        ...         workspace_id=workspace_id,
        ...         session_id=session_id,
        ...         field_name="subjective",
        ...         embedding=[0.1, 0.2, ...],  # 1536 dimensions
        ...     )
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize vector store with database session.

        Args:
            db: SQLAlchemy async session for database operations
        """
        self.db = db

    async def insert_embedding(
        self,
        workspace_id: uuid.UUID,
        session_id: uuid.UUID,
        field_name: str,
        embedding: list[float],
    ) -> SessionVector:
        """
        Insert a single embedding vector for a SOAP field.

        Args:
            workspace_id: Workspace ID (multi-tenant isolation)
            session_id: Session ID (foreign key to sessions table)
            field_name: SOAP field name ('subjective', 'objective', 'assessment', 'plan')
            embedding: 1536-dimensional vector from Cohere embed-v4.0

        Returns:
            Created SessionVector instance

        Raises:
            VectorStoreError: If insertion fails
            ValueError: If field_name is invalid or embedding dimensions incorrect

        Example:
            >>> vector = await store.insert_embedding(
            ...     workspace_id=uuid.uuid4(),
            ...     session_id=uuid.uuid4(),
            ...     field_name="subjective",
            ...     embedding=[0.1] * 1536,
            ... )
        """
        # Validate field_name
        valid_fields = {"subjective", "objective", "assessment", "plan"}
        if field_name not in valid_fields:
            raise ValueError(
                f"Invalid field_name: {field_name}. Must be one of {valid_fields}"
            )

        # Validate embedding dimensions
        if len(embedding) != 1536:
            raise ValueError(
                f"Invalid embedding dimensions: {len(embedding)}. Expected 1536."
            )

        try:
            vector = SessionVector(
                workspace_id=workspace_id,
                session_id=session_id,
                field_name=field_name,
                embedding=embedding,  # type: ignore[arg-type]
            )

            self.db.add(vector)
            await self.db.flush()
            await self.db.refresh(vector)

            logger.info(
                "embedding_inserted",
                vector_id=str(vector.id),
                workspace_id=str(workspace_id),
                session_id=str(session_id),
                field_name=field_name,
            )

            return vector

        except Exception as e:
            logger.error(
                "embedding_insertion_failed",
                error=str(e),
                error_type=type(e).__name__,
                workspace_id=str(workspace_id),
                session_id=str(session_id),
                field_name=field_name,
            )
            raise VectorStoreError(f"Failed to insert embedding: {e}") from e

    async def insert_embeddings_batch(
        self,
        workspace_id: uuid.UUID,
        session_id: uuid.UUID,
        embeddings: dict[str, list[float]],
    ) -> list[SessionVector]:
        """
        Insert multiple embeddings for a session in a single transaction.

        This is more efficient than calling insert_embedding() multiple times.

        Args:
            workspace_id: Workspace ID (multi-tenant isolation)
            session_id: Session ID (foreign key to sessions table)
            embeddings: Dict mapping field names to embedding vectors
                       Example: {"subjective": [...], "objective": [...]}

        Returns:
            List of created SessionVector instances

        Raises:
            VectorStoreError: If batch insertion fails
            ValueError: If any field_name is invalid or embedding dimensions incorrect

        Example:
            >>> vectors = await store.insert_embeddings_batch(
            ...     workspace_id=uuid.uuid4(),
            ...     session_id=uuid.uuid4(),
            ...     embeddings={
            ...         "subjective": [0.1] * 1536,
            ...         "objective": [0.2] * 1536,
            ...         "assessment": [0.3] * 1536,
            ...         "plan": [0.4] * 1536,
            ...     },
            ... )
        """
        valid_fields = {"subjective", "objective", "assessment", "plan"}

        # Validate all field names and dimensions
        for field_name, embedding in embeddings.items():
            if field_name not in valid_fields:
                raise ValueError(
                    f"Invalid field_name: {field_name}. Must be one of {valid_fields}"
                )
            if len(embedding) != 1536:
                raise ValueError(
                    f"Invalid embedding dimensions for {field_name}: "
                    f"{len(embedding)}. Expected 1536."
                )

        try:
            vectors = []
            for field_name, embedding in embeddings.items():
                vector = SessionVector(
                    workspace_id=workspace_id,
                    session_id=session_id,
                    field_name=field_name,
                    embedding=embedding,  # type: ignore[arg-type]
                )
                vectors.append(vector)
                self.db.add(vector)

            await self.db.flush()

            # Refresh all vectors to get IDs
            for vector in vectors:
                await self.db.refresh(vector)

            logger.info(
                "embeddings_batch_inserted",
                count=len(vectors),
                workspace_id=str(workspace_id),
                session_id=str(session_id),
                fields=list(embeddings.keys()),
            )

            return vectors

        except Exception as e:
            logger.error(
                "embeddings_batch_insertion_failed",
                error=str(e),
                error_type=type(e).__name__,
                workspace_id=str(workspace_id),
                session_id=str(session_id),
                fields=list(embeddings.keys()),
            )
            raise VectorStoreError(f"Failed to insert embeddings batch: {e}") from e

    async def search_similar(
        self,
        workspace_id: uuid.UUID,
        query_embedding: list[float],
        limit: int = 10,
        field_name: str | None = None,
        min_similarity: float = 0.3,
    ) -> list[tuple[SessionVector, float]]:
        """
        Search for similar embeddings using cosine similarity.

        This uses pgvector's HNSW index for fast approximate nearest neighbor search.

        Args:
            workspace_id: Workspace ID (MANDATORY - multi-tenant isolation)
            query_embedding: 1536-dimensional query vector
            limit: Maximum number of results to return (default: 10, max: 100)
            field_name: Optional filter by SOAP field ('subjective', 'objective', etc.)
            min_similarity: Minimum cosine similarity threshold (0.0 to 1.0, default: 0.7)

        Returns:
            List of (SessionVector, similarity_score) tuples, sorted by similarity desc

        Raises:
            VectorStoreError: If search fails
            ValueError: If query_embedding dimensions incorrect or limit out of range

        Example:
            >>> results = await store.search_similar(
            ...     workspace_id=uuid.uuid4(),
            ...     query_embedding=[0.1] * 1536,
            ...     limit=5,
            ...     field_name="subjective",
            ...     min_similarity=0.8,
            ... )
            >>> for vector, similarity in results:
            ...     print(f"Session {vector.session_id}: {similarity:.2f}")
        """
        # Validate query_embedding dimensions
        if len(query_embedding) != 1536:
            raise ValueError(
                f"Invalid query embedding dimensions: {len(query_embedding)}. "
                f"Expected 1536."
            )

        # Validate limit
        if limit < 1 or limit > 100:
            raise ValueError(f"Invalid limit: {limit}. Must be between 1 and 100.")

        # Validate min_similarity
        if not 0.0 <= min_similarity <= 1.0:
            raise ValueError(
                f"Invalid min_similarity: {min_similarity}. Must be between 0.0 and 1.0."
            )

        # Validate field_name if provided
        if field_name is not None:
            valid_fields = {"subjective", "objective", "assessment", "plan"}
            if field_name not in valid_fields:
                raise ValueError(
                    f"Invalid field_name: {field_name}. Must be one of {valid_fields}"
                )

        try:
            # Calculate cosine similarity using pgvector's <=> operator
            # (1 - cosine_distance) = cosine_similarity
            similarity = 1 - SessionVector.embedding.cosine_distance(query_embedding)

            # Build query with workspace isolation
            query = (
                select(SessionVector, similarity.label("similarity"))
                .where(SessionVector.workspace_id == workspace_id)
                .where(similarity >= min_similarity)
            )

            # Optional field filter
            if field_name is not None:
                query = query.where(SessionVector.field_name == field_name)

            # Order by similarity descending and limit results
            query = query.order_by(desc("similarity")).limit(limit)

            result = await self.db.execute(query)
            rows = result.all()

            results = [(row.SessionVector, float(row.similarity)) for row in rows]

            logger.info(
                "similarity_search_completed",
                workspace_id=str(workspace_id),
                results_count=len(results),
                limit=limit,
                field_name=field_name,
                min_similarity=min_similarity,
            )

            return results

        except Exception as e:
            logger.error(
                "similarity_search_failed",
                error=str(e),
                error_type=type(e).__name__,
                workspace_id=str(workspace_id),
                limit=limit,
                field_name=field_name,
            )
            raise VectorStoreError(f"Failed to search similar embeddings: {e}") from e

    async def get_session_embeddings(
        self,
        workspace_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> Sequence[SessionVector]:
        """
        Get all embeddings for a specific session.

        Args:
            workspace_id: Workspace ID (MANDATORY - multi-tenant isolation)
            session_id: Session ID to retrieve embeddings for

        Returns:
            List of SessionVector instances for the session (may be empty)

        Raises:
            VectorStoreError: If retrieval fails

        Example:
            >>> vectors = await store.get_session_embeddings(
            ...     workspace_id=uuid.uuid4(),
            ...     session_id=uuid.uuid4(),
            ... )
            >>> for vector in vectors:
            ...     print(f"{vector.field_name}: {len(vector.embedding)} dims")
        """
        try:
            query = (
                select(SessionVector)
                .where(SessionVector.workspace_id == workspace_id)
                .where(SessionVector.session_id == session_id)
            )

            result = await self.db.execute(query)
            vectors = result.scalars().all()

            logger.info(
                "session_embeddings_retrieved",
                workspace_id=str(workspace_id),
                session_id=str(session_id),
                count=len(vectors),
            )

            return vectors

        except Exception as e:
            logger.error(
                "session_embeddings_retrieval_failed",
                error=str(e),
                error_type=type(e).__name__,
                workspace_id=str(workspace_id),
                session_id=str(session_id),
            )
            raise VectorStoreError(f"Failed to retrieve session embeddings: {e}") from e

    async def delete_session_embeddings(
        self,
        workspace_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> int:
        """
        Delete all embeddings for a specific session.

        Note: Normally CASCADE delete handles this automatically when a session
        is deleted. This method is for explicit cleanup or re-embedding scenarios.

        Args:
            workspace_id: Workspace ID (MANDATORY - multi-tenant isolation)
            session_id: Session ID to delete embeddings for

        Returns:
            Number of embeddings deleted

        Raises:
            VectorStoreError: If deletion fails

        Example:
            >>> count = await store.delete_session_embeddings(
            ...     workspace_id=uuid.uuid4(),
            ...     session_id=uuid.uuid4(),
            ... )
            >>> print(f"Deleted {count} embeddings")
        """
        try:
            stmt = delete(SessionVector).where(
                SessionVector.workspace_id == workspace_id,
                SessionVector.session_id == session_id,
            )

            result = await self.db.execute(stmt)
            deleted_count = result.rowcount or 0

            logger.info(
                "session_embeddings_deleted",
                workspace_id=str(workspace_id),
                session_id=str(session_id),
                count=deleted_count,
            )

            return deleted_count

        except Exception as e:
            logger.error(
                "session_embeddings_deletion_failed",
                error=str(e),
                error_type=type(e).__name__,
                workspace_id=str(workspace_id),
                session_id=str(session_id),
            )
            raise VectorStoreError(f"Failed to delete session embeddings: {e}") from e

    async def count_workspace_embeddings(self, workspace_id: uuid.UUID) -> int:
        """
        Count total embeddings in a workspace.

        Useful for monitoring and quota enforcement.

        Args:
            workspace_id: Workspace ID (MANDATORY - multi-tenant isolation)

        Returns:
            Total number of embeddings in workspace

        Raises:
            VectorStoreError: If count fails

        Example:
            >>> count = await store.count_workspace_embeddings(workspace_id)
            >>> print(f"Workspace has {count} embeddings")
        """
        try:
            query = select(func.count(SessionVector.id)).where(
                SessionVector.workspace_id == workspace_id
            )

            result = await self.db.execute(query)
            count = result.scalar_one()

            logger.info(
                "workspace_embeddings_counted",
                workspace_id=str(workspace_id),
                count=count,
            )

            return count

        except Exception as e:
            logger.error(
                "workspace_embeddings_count_failed",
                error=str(e),
                error_type=type(e).__name__,
                workspace_id=str(workspace_id),
            )
            raise VectorStoreError(f"Failed to count workspace embeddings: {e}") from e

    # ============================================================================
    # Client Vector Operations
    # ============================================================================

    async def insert_client_embedding(
        self,
        workspace_id: uuid.UUID,
        client_id: uuid.UUID,
        field_name: str,
        embedding: list[float],
    ) -> ClientVector:
        """
        Insert a single embedding vector for a client field.

        Args:
            workspace_id: Workspace ID (multi-tenant isolation)
            client_id: Client ID (foreign key to clients table)
            field_name: Client field name ('medical_history', 'notes')
            embedding: 1536-dimensional vector from Cohere embed-v4.0

        Returns:
            Created ClientVector instance

        Raises:
            VectorStoreError: If insertion fails
            ValueError: If field_name is invalid or embedding dimensions incorrect

        Example:
            >>> vector = await store.insert_client_embedding(
            ...     workspace_id=uuid.uuid4(),
            ...     client_id=uuid.uuid4(),
            ...     field_name="medical_history",
            ...     embedding=[0.1] * 1536,
            ... )
        """
        # Validate field_name
        valid_fields = {"medical_history", "notes"}
        if field_name not in valid_fields:
            raise ValueError(
                f"Invalid field_name: {field_name}. Must be one of {valid_fields}"
            )

        # Validate embedding dimensions
        if len(embedding) != 1536:
            raise ValueError(
                f"Invalid embedding dimensions: {len(embedding)}. Expected 1536."
            )

        try:
            vector = ClientVector(
                workspace_id=workspace_id,
                client_id=client_id,
                field_name=field_name,
                embedding=embedding,  # type: ignore[arg-type]
            )

            self.db.add(vector)
            await self.db.flush()
            await self.db.refresh(vector)

            logger.info(
                "client_embedding_inserted",
                vector_id=str(vector.id),
                workspace_id=str(workspace_id),
                client_id=str(client_id),
                field_name=field_name,
            )

            return vector

        except Exception as e:
            logger.error(
                "client_embedding_insertion_failed",
                error=str(e),
                error_type=type(e).__name__,
                workspace_id=str(workspace_id),
                client_id=str(client_id),
                field_name=field_name,
            )
            raise VectorStoreError(f"Failed to insert client embedding: {e}") from e

    async def insert_client_embeddings_batch(
        self,
        workspace_id: uuid.UUID,
        client_id: uuid.UUID,
        embeddings: dict[str, list[float]],
    ) -> list[ClientVector]:
        """
        Insert multiple embeddings for a client in a single transaction.

        This is more efficient than calling insert_client_embedding() multiple times.

        Args:
            workspace_id: Workspace ID (multi-tenant isolation)
            client_id: Client ID (foreign key to clients table)
            embeddings: Dict mapping field names to embedding vectors
                       Example: {"medical_history": [...], "notes": [...]}

        Returns:
            List of created ClientVector instances

        Raises:
            VectorStoreError: If batch insertion fails
            ValueError: If any field_name is invalid or embedding dimensions incorrect

        Example:
            >>> vectors = await store.insert_client_embeddings_batch(
            ...     workspace_id=uuid.uuid4(),
            ...     client_id=uuid.uuid4(),
            ...     embeddings={
            ...         "medical_history": [0.1] * 1536,
            ...         "notes": [0.2] * 1536,
            ...     },
            ... )
        """
        valid_fields = {"medical_history", "notes"}

        # Validate all field names and dimensions
        for field_name, embedding in embeddings.items():
            if field_name not in valid_fields:
                raise ValueError(
                    f"Invalid field_name: {field_name}. Must be one of {valid_fields}"
                )
            if len(embedding) != 1536:
                raise ValueError(
                    f"Invalid embedding dimensions for {field_name}: "
                    f"{len(embedding)}. Expected 1536."
                )

        try:
            vectors = []
            for field_name, embedding in embeddings.items():
                vector = ClientVector(
                    workspace_id=workspace_id,
                    client_id=client_id,
                    field_name=field_name,
                    embedding=embedding,  # type: ignore[arg-type]
                )
                vectors.append(vector)
                self.db.add(vector)

            await self.db.flush()

            # Refresh all vectors to get IDs
            for vector in vectors:
                await self.db.refresh(vector)

            logger.info(
                "client_embeddings_batch_inserted",
                count=len(vectors),
                workspace_id=str(workspace_id),
                client_id=str(client_id),
                fields=list(embeddings.keys()),
            )

            return vectors

        except Exception as e:
            logger.error(
                "client_embeddings_batch_insertion_failed",
                error=str(e),
                error_type=type(e).__name__,
                workspace_id=str(workspace_id),
                client_id=str(client_id),
                fields=list(embeddings.keys()),
            )
            raise VectorStoreError(
                f"Failed to insert client embeddings batch: {e}"
            ) from e

    async def search_similar_clients(
        self,
        workspace_id: uuid.UUID,
        query_embedding: list[float],
        limit: int = 10,
        field_name: str | None = None,
        min_similarity: float = 0.3,
    ) -> list[tuple[ClientVector, float]]:
        """
        Search for similar client embeddings using cosine similarity.

        This uses pgvector's HNSW index for fast approximate nearest neighbor search.

        Args:
            workspace_id: Workspace ID (MANDATORY - multi-tenant isolation)
            query_embedding: 1536-dimensional query vector
            limit: Maximum number of results to return (default: 10, max: 100)
            field_name: Optional filter by client field ('medical_history', 'notes')
            min_similarity: Minimum cosine similarity threshold (0.0 to 1.0, default: 0.7)

        Returns:
            List of (ClientVector, similarity_score) tuples, sorted by similarity desc

        Raises:
            VectorStoreError: If search fails
            ValueError: If query_embedding dimensions incorrect or limit out of range

        Example:
            >>> results = await store.search_similar_clients(
            ...     workspace_id=uuid.uuid4(),
            ...     query_embedding=[0.1] * 1536,
            ...     limit=5,
            ...     field_name="medical_history",
            ...     min_similarity=0.8,
            ... )
            >>> for vector, similarity in results:
            ...     print(f"Client {vector.client_id}: {similarity:.2f}")
        """
        # Validate query_embedding dimensions
        if len(query_embedding) != 1536:
            raise ValueError(
                f"Invalid query embedding dimensions: {len(query_embedding)}. "
                f"Expected 1536."
            )

        # Validate limit
        if limit < 1 or limit > 100:
            raise ValueError(f"Invalid limit: {limit}. Must be between 1 and 100.")

        # Validate min_similarity
        if not 0.0 <= min_similarity <= 1.0:
            raise ValueError(
                f"Invalid min_similarity: {min_similarity}. Must be between 0.0 and 1.0."
            )

        # Validate field_name if provided
        if field_name is not None:
            valid_fields = {"medical_history", "notes"}
            if field_name not in valid_fields:
                raise ValueError(
                    f"Invalid field_name: {field_name}. Must be one of {valid_fields}"
                )

        try:
            # Calculate cosine similarity using pgvector's <=> operator
            # (1 - cosine_distance) = cosine_similarity
            similarity = 1 - ClientVector.embedding.cosine_distance(query_embedding)

            # Build query with workspace isolation
            query = (
                select(ClientVector, similarity.label("similarity"))
                .where(ClientVector.workspace_id == workspace_id)
                .where(similarity >= min_similarity)
            )

            # Optional field filter
            if field_name is not None:
                query = query.where(ClientVector.field_name == field_name)

            # Order by similarity descending and limit results
            query = query.order_by(desc("similarity")).limit(limit)

            result = await self.db.execute(query)
            rows = result.all()

            results = [(row.ClientVector, float(row.similarity)) for row in rows]

            logger.info(
                "client_similarity_search_completed",
                workspace_id=str(workspace_id),
                results_count=len(results),
                limit=limit,
                field_name=field_name,
                min_similarity=min_similarity,
            )

            return results

        except Exception as e:
            logger.error(
                "client_similarity_search_failed",
                error=str(e),
                error_type=type(e).__name__,
                workspace_id=str(workspace_id),
                limit=limit,
                field_name=field_name,
            )
            raise VectorStoreError(
                f"Failed to search similar client embeddings: {e}"
            ) from e

    async def get_client_embeddings(
        self,
        workspace_id: uuid.UUID,
        client_id: uuid.UUID,
    ) -> Sequence[ClientVector]:
        """
        Get all embeddings for a specific client.

        Args:
            workspace_id: Workspace ID (MANDATORY - multi-tenant isolation)
            client_id: Client ID to retrieve embeddings for

        Returns:
            List of ClientVector instances for the client (may be empty)

        Raises:
            VectorStoreError: If retrieval fails

        Example:
            >>> vectors = await store.get_client_embeddings(
            ...     workspace_id=uuid.uuid4(),
            ...     client_id=uuid.uuid4(),
            ... )
            >>> for vector in vectors:
            ...     print(f"{vector.field_name}: {len(vector.embedding)} dims")
        """
        try:
            query = (
                select(ClientVector)
                .where(ClientVector.workspace_id == workspace_id)
                .where(ClientVector.client_id == client_id)
            )

            result = await self.db.execute(query)
            vectors = result.scalars().all()

            logger.info(
                "client_embeddings_retrieved",
                workspace_id=str(workspace_id),
                client_id=str(client_id),
                count=len(vectors),
            )

            return vectors

        except Exception as e:
            logger.error(
                "client_embeddings_retrieval_failed",
                error=str(e),
                error_type=type(e).__name__,
                workspace_id=str(workspace_id),
                client_id=str(client_id),
            )
            raise VectorStoreError(f"Failed to retrieve client embeddings: {e}") from e

    async def delete_client_embeddings(
        self,
        workspace_id: uuid.UUID,
        client_id: uuid.UUID,
    ) -> int:
        """
        Delete all embeddings for a specific client.

        Note: Normally CASCADE delete handles this automatically when a client
        is deleted. This method is for explicit cleanup or re-embedding scenarios.

        Args:
            workspace_id: Workspace ID (MANDATORY - multi-tenant isolation)
            client_id: Client ID to delete embeddings for

        Returns:
            Number of embeddings deleted

        Raises:
            VectorStoreError: If deletion fails

        Example:
            >>> count = await store.delete_client_embeddings(
            ...     workspace_id=uuid.uuid4(),
            ...     client_id=uuid.uuid4(),
            ... )
            >>> print(f"Deleted {count} embeddings")
        """
        try:
            stmt = delete(ClientVector).where(
                ClientVector.workspace_id == workspace_id,
                ClientVector.client_id == client_id,
            )

            result = await self.db.execute(stmt)
            deleted_count = result.rowcount or 0

            logger.info(
                "client_embeddings_deleted",
                workspace_id=str(workspace_id),
                client_id=str(client_id),
                count=deleted_count,
            )

            return deleted_count

        except Exception as e:
            logger.error(
                "client_embeddings_deletion_failed",
                error=str(e),
                error_type=type(e).__name__,
                workspace_id=str(workspace_id),
                client_id=str(client_id),
            )
            raise VectorStoreError(f"Failed to delete client embeddings: {e}") from e


def get_vector_store(db: AsyncSession) -> VectorStore:
    """
    Factory function to create a VectorStore instance.

    Args:
        db: SQLAlchemy async session

    Returns:
        Configured VectorStore instance

    Example:
        >>> async with get_db_session() as db:
        ...     store = get_vector_store(db)
        ...     results = await store.search_similar(...)
    """
    return VectorStore(db)
