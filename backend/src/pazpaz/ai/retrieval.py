"""
RAG retrieval service for semantic search over session SOAP notes.

This module implements the retrieval component of the RAG (Retrieval-Augmented
Generation) pipeline. It handles:
1. Query embedding generation (via Cohere API)
2. Semantic similarity search (via pgvector HNSW index)
3. Session fetching with automatic PHI decryption
4. Context building for LLM consumption

Architecture:
- Workspace-scoped queries (multi-tenant isolation)
- Automatic PHI decryption (EncryptedString type)
- Cosine similarity ranking
- Configurable result limits and similarity thresholds

Security:
- Workspace isolation enforced at database level
- PHI decrypted in-memory only (not logged)
- No PHI stored in vector embeddings (lossy transformation)
- Audit logging via AuditEvent model (caller responsibility)

Performance:
- HNSW index provides <10ms similarity search
- Batch loading via selectinload for relationships
- Configurable limits to control token usage
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pazpaz.ai.embeddings import get_embedding_service
from pazpaz.ai.vector_store import get_vector_store
from pazpaz.core.logging import get_logger
from pazpaz.models.client import Client
from pazpaz.models.client_vector import ClientVector
from pazpaz.models.session import Session
from pazpaz.models.session_vector import SessionVector

logger = get_logger(__name__)


class RetrievalError(Exception):
    """Exception raised when retrieval operations fail."""

    pass


@dataclass
class SessionContext:
    """
    Context about a retrieved session for RAG.

    Contains the session metadata and SOAP content needed for the LLM to
    generate informed responses with proper citations.

    Attributes:
        session_id: UUID of the session
        client_id: UUID of the client
        client_name: Full name of the client (for citation display)
        session_date: When the session occurred
        subjective: Patient-reported symptoms (PHI - decrypted)
        objective: Therapist observations (PHI - decrypted)
        assessment: Clinical assessment (PHI - decrypted)
        plan: Treatment plan (PHI - decrypted)
        similarity_score: Cosine similarity to query (0.0 to 1.0)
        weighted_score: Temporal weighted similarity score (0.0 to 1.0)
        matched_field: Which SOAP field matched the query

    Example:
        >>> context = SessionContext(
        ...     session_id=uuid.uuid4(),
        ...     client_id=uuid.uuid4(),
        ...     client_name="John Doe",
        ...     session_date=datetime.now(),
        ...     subjective="Patient reports back pain...",
        ...     objective="Limited ROM in lumbar spine...",
        ...     assessment="Acute lower back strain...",
        ...     plan="Rest, ice, follow-up in 2 weeks...",
        ...     similarity_score=0.85,
        ...     weighted_score=0.74,  # Temporal weighting applied
        ...     matched_field="subjective",
        ... )
    """

    session_id: uuid.UUID
    client_id: uuid.UUID
    client_name: str
    session_date: datetime
    subjective: str | None
    objective: str | None
    assessment: str | None
    plan: str | None
    similarity_score: float
    weighted_score: float
    matched_field: str


@dataclass
class ClientContext:
    """
    Context about a retrieved client profile for RAG.

    Contains the client metadata and profile fields needed for the LLM to
    generate informed responses with proper citations about client history.

    Attributes:
        client_id: UUID of the client
        client_name: Full name of the client (for citation display)
        medical_history: Client medical history (PHI - decrypted)
        notes: Therapist notes about the client
        similarity_score: Cosine similarity to query (0.0 to 1.0)
        matched_field: Which client field matched the query ('medical_history', 'notes')

    Example:
        >>> context = ClientContext(
        ...     client_id=uuid.uuid4(),
        ...     client_name="Jane Smith",
        ...     medical_history="History of chronic migraines...",
        ...     notes="Prefers morning appointments...",
        ...     similarity_score=0.88,
        ...     matched_field="medical_history",
        ... )
    """

    client_id: uuid.UUID
    client_name: str
    medical_history: str | None
    notes: str | None
    similarity_score: float
    matched_field: str


def apply_temporal_weighting(
    similarity: float,
    session_date: datetime,
    decay_rate: float = 0.02,
) -> float:
    """
    Apply temporal weighting to similarity score.

    Recent sessions get higher weight, older sessions decay exponentially.
    This ensures treatment recommendations prioritize recent clinical history
    while still allowing highly relevant old sessions to contribute.

    Args:
        similarity: Original cosine similarity (0.0 to 1.0)
        session_date: When the session occurred
        decay_rate: Exponential decay rate (default: 0.02 = 35-day half-life)
            - 0.01 = slow decay (~70-day half-life)
            - 0.02 = moderate decay (~35-day half-life) [default]
            - 0.05 = aggressive decay (~14-day half-life)

    Returns:
        Weighted similarity score (0.0 to 1.0)

    Examples:
        With default decay_rate=0.02 (moderate):
        - 7 days ago:   similarity * 0.87
        - 1 month ago:  similarity * 0.55
        - 3 months ago: similarity * 0.17
        - 6 months ago: similarity * 0.03
    """
    # Handle timezone-naive session_date (assume UTC if no timezone)
    if session_date.tzinfo is None:
        session_date = session_date.replace(tzinfo=UTC)

    now = datetime.now(UTC)
    days_ago = (now - session_date).days

    # Exponential decay: exp(-decay_rate * days_ago)
    # Clamp days_ago to 0 minimum (future dates get no penalty)
    recency_weight = math.exp(-decay_rate * max(0, days_ago))

    return similarity * recency_weight


class RetrievalService:
    """
    RAG retrieval service for semantic search over session SOAP notes.

    Provides high-level retrieval methods that combine embedding generation,
    vector similarity search, and session fetching with PHI decryption.

    All operations are workspace-scoped for multi-tenant isolation.

    Example:
        >>> async with get_db_session() as db:
        ...     retrieval = RetrievalService(db)
        ...     results = await retrieval.retrieve_relevant_sessions(
        ...         workspace_id=workspace_id,
        ...         query="What did we discuss about lower back pain?",
        ...         limit=5,
        ...         min_similarity=0.7,
        ...     )
        ...     for context in results:
        ...         print(f"Session {context.session_id}: {context.similarity_score:.2f}")
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize retrieval service.

        Args:
            db: SQLAlchemy async session for database operations
        """
        self.db = db
        # Use "search_query" input type for query embeddings (different from document embeddings)
        self.embedding_service = get_embedding_service(input_type="search_query")
        self.vector_store = get_vector_store(db)

    async def retrieve_relevant_sessions(
        self,
        workspace_id: uuid.UUID,
        query: str,
        limit: int = 5,
        min_similarity: float = 0.3,
        field_filter: str | None = None,
        include_client_context: bool = True,
    ) -> tuple[list[SessionContext], list[ClientContext]]:
        """
        Retrieve sessions AND client profiles relevant to a natural language query.

        This is the main entry point for RAG retrieval. It:
        1. Embeds the query using Cohere API
        2. Searches for similar vectors in BOTH session_vectors AND client_vectors
        3. Fetches full session and client data with PHI decryption
        4. Returns structured context for LLM consumption

        Args:
            workspace_id: Workspace ID (MANDATORY - multi-tenant isolation)
            query: Natural language query (Hebrew or English)
            limit: Maximum number of results per type to retrieve (default: 5, max: 20)
            min_similarity: Minimum cosine similarity threshold (default: 0.7)
            field_filter: Optional SOAP field filter ('subjective', 'objective', etc.)
                         Only applies to session vectors, not client vectors
            include_client_context: Include client profile search (default: True)

        Returns:
            Tuple of (SessionContext list, ClientContext list), both sorted by similarity

        Raises:
            RetrievalError: If retrieval fails
            ValueError: If limit out of range or invalid field_filter

        Example:
            >>> sessions, clients = await retrieval.retrieve_relevant_sessions(
            ...     workspace_id=uuid.uuid4(),
            ...     query="What is the patient's medical history?",
            ...     limit=5,
            ...     min_similarity=0.75,
            ... )
            >>> print(f"Found {len(sessions)} sessions and {len(clients)} clients")
        """
        # Validate limit
        if limit < 1 or limit > 20:
            raise ValueError(f"Invalid limit: {limit}. Must be between 1 and 20.")

        logger.info(
            "retrieval_started",
            workspace_id=str(workspace_id),
            query_length=len(query),
            limit=limit,
            min_similarity=min_similarity,
            field_filter=field_filter,
            include_client_context=include_client_context,
        )

        try:
            # Step 1: Embed the query
            query_embedding = await self.embedding_service.embed_text(query)

            logger.debug(
                "query_embedded",
                workspace_id=str(workspace_id),
                embedding_dim=len(query_embedding),
            )

            # Step 2: Search for similar session vectors
            similar_session_vectors = await self.vector_store.search_similar(
                workspace_id=workspace_id,
                query_embedding=query_embedding,
                limit=limit,
                field_name=field_filter,
                min_similarity=min_similarity,
            )

            logger.info(
                "session_vectors_found",
                workspace_id=str(workspace_id),
                count=len(similar_session_vectors),
            )

            # Step 3: Search for similar client vectors (if enabled)
            similar_client_vectors: list[tuple[ClientVector, float]] = []
            if include_client_context:
                similar_client_vectors = await self.vector_store.search_similar_clients(
                    workspace_id=workspace_id,
                    query_embedding=query_embedding,
                    limit=limit,
                    field_name=None,  # Search both medical_history and notes
                    min_similarity=min_similarity,
                )

                logger.info(
                    "client_vectors_found",
                    workspace_id=str(workspace_id),
                    count=len(similar_client_vectors),
                )

            # Step 4: Build context objects
            session_contexts = []
            if similar_session_vectors:
                session_contexts = await self._build_session_contexts(
                    workspace_id=workspace_id,
                    similar_vectors=similar_session_vectors,
                )

            client_contexts = []
            if similar_client_vectors:
                client_contexts = await self._build_client_contexts(
                    workspace_id=workspace_id,
                    similar_vectors=similar_client_vectors,
                )

            logger.info(
                "retrieval_completed",
                workspace_id=str(workspace_id),
                session_results_count=len(session_contexts),
                client_results_count=len(client_contexts),
            )

            return session_contexts, client_contexts

        except Exception as e:
            logger.error(
                "retrieval_failed",
                workspace_id=str(workspace_id),
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise RetrievalError(f"Failed to retrieve relevant context: {e}") from e

    async def _build_session_contexts(
        self,
        workspace_id: uuid.UUID,
        similar_vectors: list[tuple[SessionVector, float]],
    ) -> list[SessionContext]:
        """
        Build SessionContext objects from similar vectors.

        Fetches full session data with relationships and constructs context
        objects for LLM consumption. PHI is automatically decrypted by the
        EncryptedString SQLAlchemy type.

        Args:
            workspace_id: Workspace ID for isolation verification
            similar_vectors: List of (SessionVector, similarity_score) tuples

        Returns:
            List of SessionContext objects with decrypted PHI

        Raises:
            RetrievalError: If session fetching fails
        """
        # Extract unique session IDs
        session_ids = list({vector.session_id for vector, _ in similar_vectors})

        # Create similarity map for lookup
        similarity_map: dict[tuple[uuid.UUID, str], float] = {
            (vector.session_id, vector.field_name): similarity
            for vector, similarity in similar_vectors
        }

        try:
            # Fetch sessions with relationships (eager loading)
            stmt = (
                select(Session)
                .where(Session.id.in_(session_ids))
                .where(Session.workspace_id == workspace_id)
                .options(
                    selectinload(Session.client),  # Eager load client for name
                )
            )

            result = await self.db.execute(stmt)
            sessions = result.scalars().all()

            # Build context objects
            contexts: list[SessionContext] = []

            for session in sessions:
                # Find the matched field with highest similarity for this session
                matched_field = "subjective"
                max_similarity = 0.0

                for field_name in ["subjective", "objective", "assessment", "plan"]:
                    key = (session.id, field_name)
                    if key in similarity_map:
                        similarity = similarity_map[key]
                        if similarity > max_similarity:
                            max_similarity = similarity
                            matched_field = field_name

                # Apply temporal weighting to prioritize recent sessions
                weighted_score = apply_temporal_weighting(
                    max_similarity, session.session_date
                )

                # Calculate temporal weighting metrics for logging
                session_date_utc = (
                    session.session_date.replace(tzinfo=UTC)
                    if session.session_date.tzinfo is None
                    else session.session_date
                )
                days_ago = (datetime.now(UTC) - session_date_utc).days
                recency_weight = (
                    weighted_score / max_similarity if max_similarity > 0 else 0
                )

                logger.debug(
                    "temporal_weighting_applied",
                    session_id=str(session.id),
                    session_date=session.session_date.isoformat(),
                    days_ago=days_ago,
                    similarity_score=round(max_similarity, 4),
                    recency_weight=round(recency_weight, 4),
                    weighted_score=round(weighted_score, 4),
                    matched_field=matched_field,
                )

                # Build context
                context = SessionContext(
                    session_id=session.id,
                    client_id=session.client_id,
                    client_name=session.client.full_name
                    if session.client
                    else "Unknown",
                    session_date=session.session_date,
                    subjective=session.subjective,  # Auto-decrypted
                    objective=session.objective,  # Auto-decrypted
                    assessment=session.assessment,  # Auto-decrypted
                    plan=session.plan,  # Auto-decrypted
                    similarity_score=max_similarity,
                    weighted_score=weighted_score,
                    matched_field=matched_field,
                )

                contexts.append(context)

            # Sort by weighted similarity (prioritizes recent + relevant sessions)
            contexts.sort(key=lambda c: c.weighted_score, reverse=True)

            # Log final ranking after temporal weighting
            logger.info(
                "sessions_ranked_by_temporal_weighting",
                workspace_id=str(workspace_id),
                total_sessions=len(contexts),
                rankings=[
                    {
                        "session_id": str(c.session_id),
                        "rank": i + 1,
                        "similarity": round(c.similarity_score, 4),
                        "weighted": round(c.weighted_score, 4),
                        "date": c.session_date.isoformat(),
                    }
                    for i, c in enumerate(contexts)
                ],
            )

            return contexts

        except Exception as e:
            logger.error(
                "session_context_building_failed",
                workspace_id=str(workspace_id),
                session_count=len(session_ids),
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise RetrievalError(f"Failed to build session contexts: {e}") from e

    async def _build_client_contexts(
        self,
        workspace_id: uuid.UUID,
        similar_vectors: list[tuple[ClientVector, float]],
    ) -> list[ClientContext]:
        """
        Build ClientContext objects from similar client vectors.

        Fetches full client data with relationships and constructs context
        objects for LLM consumption. PHI is automatically decrypted by the
        EncryptedString SQLAlchemy type.

        Args:
            workspace_id: Workspace ID for isolation verification
            similar_vectors: List of (ClientVector, similarity_score) tuples

        Returns:
            List of ClientContext objects with decrypted PHI

        Raises:
            RetrievalError: If client fetching fails
        """
        # Extract unique client IDs
        client_ids = list({vector.client_id for vector, _ in similar_vectors})

        # Create similarity map for lookup
        similarity_map: dict[tuple[uuid.UUID, str], float] = {
            (vector.client_id, vector.field_name): similarity
            for vector, similarity in similar_vectors
        }

        try:
            # Fetch clients with workspace isolation
            stmt = (
                select(Client)
                .where(Client.id.in_(client_ids))
                .where(Client.workspace_id == workspace_id)
            )

            result = await self.db.execute(stmt)
            clients = result.scalars().all()

            # Build context objects
            contexts: list[ClientContext] = []

            for client in clients:
                # Find the matched field with highest similarity for this client
                matched_field = "medical_history"
                max_similarity = 0.0

                for field_name in ["medical_history", "notes"]:
                    key = (client.id, field_name)
                    if key in similarity_map:
                        similarity = similarity_map[key]
                        if similarity > max_similarity:
                            max_similarity = similarity
                            matched_field = field_name

                # Build context
                context = ClientContext(
                    client_id=client.id,
                    client_name=client.full_name,
                    medical_history=client.medical_history,  # Auto-decrypted
                    notes=client.notes,
                    similarity_score=max_similarity,
                    matched_field=matched_field,
                )

                contexts.append(context)

            # Sort by similarity (highest first)
            contexts.sort(key=lambda c: c.similarity_score, reverse=True)

            return contexts

        except Exception as e:
            logger.error(
                "client_context_building_failed",
                workspace_id=str(workspace_id),
                client_count=len(client_ids),
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise RetrievalError(f"Failed to build client contexts: {e}") from e

    async def retrieve_client_history(
        self,
        workspace_id: uuid.UUID,
        client_id: uuid.UUID,
        query: str,
        limit: int = 5,
        min_similarity: float = 0.3,
    ) -> tuple[list[SessionContext], list[ClientContext]]:
        """
        Retrieve relevant sessions AND client profile for a specific client.

        This is a client-scoped version of retrieve_relevant_sessions().
        It searches both sessions and client profile data for the specified client.

        Args:
            workspace_id: Workspace ID (multi-tenant isolation)
            client_id: Client ID to filter sessions
            query: Natural language query
            limit: Maximum sessions to retrieve (default: 5)
            min_similarity: Minimum similarity threshold (default: 0.6, lower than general)

        Returns:
            Tuple of (SessionContext list, ClientContext list) for this client only

        Example:
            >>> sessions, clients = await retrieval.retrieve_client_history(
            ...     workspace_id=workspace_id,
            ...     client_id=client_id,
            ...     query="How did treatment progress?",
            ...     limit=10,
            ... )
        """
        logger.info(
            "client_history_retrieval_started",
            workspace_id=str(workspace_id),
            client_id=str(client_id),
            query_length=len(query),
        )

        # Retrieve all relevant sessions AND client contexts
        (
            all_session_contexts,
            all_client_contexts,
        ) = await self.retrieve_relevant_sessions(
            workspace_id=workspace_id,
            query=query,
            limit=limit * 2,  # Fetch more, then filter
            min_similarity=min_similarity,
            include_client_context=True,  # Include client profile search
        )

        # Filter sessions to this client only
        session_contexts = [
            context
            for context in all_session_contexts
            if context.client_id == client_id
        ]

        # Filter client contexts to this client only
        client_contexts = [
            context for context in all_client_contexts if context.client_id == client_id
        ]

        # Apply limit after filtering
        session_contexts = session_contexts[:limit]

        logger.info(
            "client_history_retrieval_completed",
            workspace_id=str(workspace_id),
            client_id=str(client_id),
            results_count=len(session_contexts) + len(client_contexts),
        )

        return session_contexts, client_contexts


def get_retrieval_service(db: AsyncSession) -> RetrievalService:
    """
    Factory function to create a RetrievalService instance.

    Args:
        db: SQLAlchemy async session

    Returns:
        Configured RetrievalService instance

    Example:
        >>> async with get_db_session() as db:
        ...     retrieval = get_retrieval_service(db)
        ...     results = await retrieval.retrieve_relevant_sessions(...)
    """
    return RetrievalService(db)
