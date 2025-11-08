"""
Background tasks for AI embedding generation.

This module contains arq tasks for generating and managing vector embeddings
of SOAP note fields using Cohere API and storing them in pgvector.

Tasks:
    - generate_session_embeddings: Generate embeddings for a session's SOAP fields

Architecture:
    - Async task execution via arq + Redis
    - Database access via AsyncSessionLocal (connection pooling)
    - Error handling with retries (arq automatic retry on failure)
    - Workspace isolation enforced in all queries

Usage:
    Tasks are enqueued from API endpoints:

        await arq_pool.enqueue_job(
            'generate_session_embeddings',
            session_id=str(session.id),
            workspace_id=str(workspace_id),
        )

    The arq worker processes jobs in the background.
"""

from __future__ import annotations

import uuid
from typing import Any

from pazpaz.ai.embeddings import get_embedding_service
from pazpaz.ai.vector_store import get_vector_store
from pazpaz.core.logging import get_logger
from pazpaz.db.base import AsyncSessionLocal
from pazpaz.models.client import Client
from pazpaz.models.session import Session

logger = get_logger(__name__)


async def generate_session_embeddings(
    ctx: dict[str, Any],
    session_id: str,
    workspace_id: str,
) -> dict[str, Any]:
    """
    Generate vector embeddings for a session's SOAP note fields.

    This task:
    1. Fetches the session from the database (with PHI decryption)
    2. Generates embeddings for each non-empty SOAP field (subjective, objective, assessment, plan)
    3. Stores embeddings in session_vectors table for semantic search

    Args:
        ctx: arq worker context (unused, but required by arq signature)
        session_id: UUID string of the session to generate embeddings for
        workspace_id: UUID string of the workspace (for multi-tenant isolation)

    Returns:
        dict: Task execution summary
            - session_id: Session UUID
            - workspace_id: Workspace UUID
            - fields_embedded: List of SOAP fields that were embedded
            - embeddings_created: Number of embeddings created
            - status: "success" or "error"
            - error: Error message (if status == "error")

    Raises:
        Exception: Propagated to arq for automatic retry

    Example arq job:
        >>> await arq_pool.enqueue_job(
        ...     'generate_session_embeddings',
        ...     session_id='550e8400-e29b-41d4-a716-446655440000',
        ...     workspace_id='123e4567-e89b-12d3-a456-426614174000',
        ... )

    Security:
        - Workspace isolation enforced in database queries
        - PHI decrypted in-memory only (not logged)
        - Embeddings stored unencrypted (lossy transformation, semantic search requires plaintext)
        - API key loaded from environment (not passed as parameter)

    Performance:
        - Uses batch embedding API (1 Cohere call for up to 4 SOAP fields)
        - Database transaction for atomic insert
        - Typical execution time: <2 seconds for 4 fields

    Error Handling:
        - Session not found: Log warning and return success (idempotent)
        - Cohere API error: Propagate exception → arq retries up to max_tries
        - Database error: Propagate exception → arq retries
        - Empty SOAP fields: Skip embedding (no error)
    """
    logger.info(
        "generate_session_embeddings_started",
        session_id=session_id,
        workspace_id=workspace_id,
    )

    try:
        # Convert string UUIDs to uuid.UUID
        session_uuid = uuid.UUID(session_id)
        workspace_uuid = uuid.UUID(workspace_id)

        # Get database session
        async with AsyncSessionLocal() as db:
            # Fetch session with workspace isolation
            from sqlalchemy import select

            stmt = (
                select(Session)
                .where(Session.id == session_uuid)
                .where(Session.workspace_id == workspace_uuid)
            )

            result = await db.execute(stmt)
            session = result.scalar_one_or_none()

            if session is None:
                # Session not found - may have been deleted between creation and job execution
                # This is not an error, just log and return success (idempotent)
                logger.warning(
                    "generate_session_embeddings_session_not_found",
                    session_id=session_id,
                    workspace_id=workspace_id,
                    message="Session not found, may have been deleted",
                )
                return {
                    "session_id": session_id,
                    "workspace_id": workspace_id,
                    "fields_embedded": [],
                    "embeddings_created": 0,
                    "status": "success",
                    "note": "session_not_found",
                }

            # Extract SOAP fields
            # Note: These are automatically decrypted by EncryptedString SQLAlchemy type
            soap_fields = {
                "subjective": session.subjective,
                "objective": session.objective,
                "assessment": session.assessment,
                "plan": session.plan,
            }

            # Filter out None and empty strings
            non_empty_fields = {
                field: text
                for field, text in soap_fields.items()
                if text and text.strip()
            }

            if not non_empty_fields:
                # No SOAP fields to embed - this is normal for draft notes
                logger.info(
                    "generate_session_embeddings_no_fields",
                    session_id=session_id,
                    workspace_id=workspace_id,
                    message="No non-empty SOAP fields to embed",
                )
                return {
                    "session_id": session_id,
                    "workspace_id": workspace_id,
                    "fields_embedded": [],
                    "embeddings_created": 0,
                    "status": "success",
                    "note": "no_fields_to_embed",
                }

            # Generate embeddings using Cohere API
            embedding_service = get_embedding_service()

            # Use embed_soap_fields() for batch efficiency
            embeddings = await embedding_service.embed_soap_fields(
                subjective=soap_fields.get("subjective"),
                objective=soap_fields.get("objective"),
                assessment=soap_fields.get("assessment"),
                plan=soap_fields.get("plan"),
            )

            # Store embeddings in session_vectors table
            vector_store = get_vector_store(db)

            await vector_store.insert_embeddings_batch(
                workspace_id=workspace_uuid,
                session_id=session_uuid,
                embeddings=embeddings,
            )

            # Commit transaction
            await db.commit()

            logger.info(
                "generate_session_embeddings_completed",
                session_id=session_id,
                workspace_id=workspace_id,
                fields_embedded=list(embeddings.keys()),
                embeddings_created=len(embeddings),
            )

            return {
                "session_id": session_id,
                "workspace_id": workspace_id,
                "fields_embedded": list(embeddings.keys()),
                "embeddings_created": len(embeddings),
                "status": "success",
            }

    except Exception as e:
        logger.error(
            "generate_session_embeddings_failed",
            session_id=session_id,
            workspace_id=workspace_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )

        # Propagate exception → arq will retry the job
        # (up to max_tries configured in WorkerSettings)
        raise


async def generate_client_embeddings(
    ctx: dict[str, Any],
    client_id: str,
    workspace_id: str,
) -> dict[str, Any]:
    """
    Generate vector embeddings for a client's profile fields.

    This task:
    1. Fetches the client from the database (with PHI decryption)
    2. Generates embeddings for each non-empty client field (medical_history, notes)
    3. Stores embeddings in client_vectors table for semantic search

    Args:
        ctx: arq worker context (unused, but required by arq signature)
        client_id: UUID string of the client to generate embeddings for
        workspace_id: UUID string of the workspace (for multi-tenant isolation)

    Returns:
        dict: Task execution summary
            - client_id: Client UUID
            - workspace_id: Workspace UUID
            - fields_embedded: List of client fields that were embedded
            - embeddings_created: Number of embeddings created
            - status: "success" or "error"
            - error: Error message (if status == "error")

    Raises:
        Exception: Propagated to arq for automatic retry

    Example arq job:
        >>> await arq_pool.enqueue_job(
        ...     'generate_client_embeddings',
        ...     client_id='550e8400-e29b-41d4-a716-446655440000',
        ...     workspace_id='123e4567-e89b-12d3-a456-426614174000',
        ... )

    Security:
        - Workspace isolation enforced in database queries
        - PHI decrypted in-memory only (not logged)
        - Embeddings stored unencrypted (lossy transformation, semantic search requires plaintext)
        - API key loaded from environment (not passed as parameter)

    Performance:
        - Uses batch embedding API (1 Cohere call for up to 2 client fields)
        - Database transaction for atomic insert
        - Typical execution time: <2 seconds for 2 fields

    Error Handling:
        - Client not found: Log warning and return success (idempotent)
        - Cohere API error: Propagate exception → arq retries up to max_tries
        - Database error: Propagate exception → arq retries
        - Empty client fields: Skip embedding (no error)
    """
    logger.info(
        "generate_client_embeddings_started",
        client_id=client_id,
        workspace_id=workspace_id,
    )

    try:
        # Convert string UUIDs to uuid.UUID
        client_uuid = uuid.UUID(client_id)
        workspace_uuid = uuid.UUID(workspace_id)

        # Get database session
        async with AsyncSessionLocal() as db:
            # Fetch client with workspace isolation
            from sqlalchemy import select

            stmt = (
                select(Client)
                .where(Client.id == client_uuid)
                .where(Client.workspace_id == workspace_uuid)
            )

            result = await db.execute(stmt)
            client = result.scalar_one_or_none()

            if client is None:
                # Client not found - may have been deleted between creation and job execution
                # This is not an error, just log and return success (idempotent)
                logger.warning(
                    "generate_client_embeddings_client_not_found",
                    client_id=client_id,
                    workspace_id=workspace_id,
                    message="Client not found, may have been deleted",
                )
                return {
                    "client_id": client_id,
                    "workspace_id": workspace_id,
                    "fields_embedded": [],
                    "embeddings_created": 0,
                    "status": "success",
                    "note": "client_not_found",
                }

            # Extract client fields
            # Note: medical_history is automatically decrypted by EncryptedString SQLAlchemy type
            # notes is not encrypted (general therapist notes, not PHI)
            client_fields = {
                "medical_history": client.medical_history,
                "notes": client.notes,
            }

            # Filter out None and empty strings
            non_empty_fields = {
                field: text
                for field, text in client_fields.items()
                if text and text.strip()
            }

            if not non_empty_fields:
                # No client fields to embed - this is normal for new clients
                logger.info(
                    "generate_client_embeddings_no_fields",
                    client_id=client_id,
                    workspace_id=workspace_id,
                    message="No non-empty client fields to embed",
                )
                return {
                    "client_id": client_id,
                    "workspace_id": workspace_id,
                    "fields_embedded": [],
                    "embeddings_created": 0,
                    "status": "success",
                    "note": "no_fields_to_embed",
                }

            # Generate embeddings using Cohere API
            embedding_service = get_embedding_service()

            # Use embed_client_fields() for batch efficiency
            embeddings = await embedding_service.embed_client_fields(
                medical_history=client_fields.get("medical_history"),
                notes=client_fields.get("notes"),
            )

            # Store embeddings in client_vectors table
            vector_store = get_vector_store(db)

            # Delete existing embeddings for this client (if any) to avoid duplicates
            # This handles the case of updating client profile
            await vector_store.delete_client_embeddings(
                workspace_id=workspace_uuid,
                client_id=client_uuid,
            )

            # Insert new embeddings
            await vector_store.insert_client_embeddings_batch(
                workspace_id=workspace_uuid,
                client_id=client_uuid,
                embeddings=embeddings,
            )

            # Commit transaction
            await db.commit()

            logger.info(
                "generate_client_embeddings_completed",
                client_id=client_id,
                workspace_id=workspace_id,
                fields_embedded=list(embeddings.keys()),
                embeddings_created=len(embeddings),
            )

            return {
                "client_id": client_id,
                "workspace_id": workspace_id,
                "fields_embedded": list(embeddings.keys()),
                "embeddings_created": len(embeddings),
                "status": "success",
            }

    except Exception as e:
        logger.error(
            "generate_client_embeddings_failed",
            client_id=client_id,
            workspace_id=workspace_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )

        # Propagate exception → arq will retry the job
        # (up to max_tries configured in WorkerSettings)
        raise
