#!/usr/bin/env python3
"""
Backfill script to generate vector embeddings for existing client profiles.

This script iterates through all clients with non-empty medical_history or notes
fields, generates embeddings using Cohere API, and stores them in the client_vectors
table for semantic search.

Usage:
    python scripts/backfill_client_embeddings.py [--workspace-id WORKSPACE_ID] [--limit N] [--dry-run]

Options:
    --workspace-id UUID    Only process clients in this workspace (default: all workspaces)
    --limit N              Limit number of clients to process (default: all)
    --dry-run              Show what would be done without making changes
    --batch-size N         Number of clients to process per batch (default: 10)

Example:
    # Backfill all clients
    python scripts/backfill_client_embeddings.py

    # Backfill specific workspace with dry-run
    python scripts/backfill_client_embeddings.py --workspace-id 123e4567-e89b-12d3-a456-426614174000 --dry-run

    # Backfill first 100 clients
    python scripts/backfill_client_embeddings.py --limit 100

Security:
    - Workspace isolation enforced in all queries
    - PHI decrypted in-memory only (not logged)
    - Embeddings stored unencrypted (lossy transformation)
    - Requires COHERE_API_KEY in environment

Performance:
    - Processes clients in batches to avoid memory issues
    - Uses batch embedding API for efficiency
    - Typical processing time: ~2 seconds per client (with 2 fields)
    - Cohere API rate limits: 10,000 requests/minute
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.ai.embeddings import EmbeddingError, get_embedding_service
from pazpaz.ai.vector_store import VectorStoreError, get_vector_store
from pazpaz.core.logging import get_logger
from pazpaz.db.base import AsyncSessionLocal
from pazpaz.models.client import Client
from pazpaz.models.client_vector import ClientVector

logger = get_logger(__name__)


class BackfillStats:
    """Statistics tracker for backfill operation."""

    def __init__(self):
        self.total_clients = 0
        self.clients_processed = 0
        self.clients_skipped = 0
        self.clients_failed = 0
        self.embeddings_created = 0
        self.start_time = datetime.now()

    def print_progress(self):
        """Print current progress."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.clients_processed / elapsed if elapsed > 0 else 0

        print(
            f"\rProgress: {self.clients_processed}/{self.total_clients} clients | "
            f"Created: {self.embeddings_created} embeddings | "
            f"Skipped: {self.clients_skipped} | "
            f"Failed: {self.clients_failed} | "
            f"Rate: {rate:.1f} clients/sec",
            end="",
            flush=True,
        )

    def print_summary(self):
        """Print final summary."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        print("\n" + "=" * 80)
        print("Backfill Summary:")
        print(f"  Total clients: {self.total_clients}")
        print(f"  Processed: {self.clients_processed}")
        print(f"  Skipped (no fields): {self.clients_skipped}")
        print(f"  Failed: {self.clients_failed}")
        print(f"  Embeddings created: {self.embeddings_created}")
        print(f"  Time elapsed: {elapsed:.1f} seconds")
        print(f"  Average rate: {self.clients_processed / elapsed:.1f} clients/sec")
        print("=" * 80)


async def count_clients(
    db: AsyncSession,
    workspace_id: uuid.UUID | None = None,
) -> int:
    """
    Count total clients to process.

    Args:
        db: Database session
        workspace_id: Optional workspace filter

    Returns:
        Total number of clients with non-empty fields
    """
    query = select(func.count(Client.id)).where(
        (Client.medical_history.isnot(None) & (Client.medical_history != ""))
        | (Client.notes.isnot(None) & (Client.notes != ""))
    )

    if workspace_id:
        query = query.where(Client.workspace_id == workspace_id)

    result = await db.execute(query)
    return result.scalar_one()


async def get_clients_batch(
    db: AsyncSession,
    workspace_id: uuid.UUID | None,
    offset: int,
    batch_size: int,
) -> list[Client]:
    """
    Fetch a batch of clients to process.

    Args:
        db: Database session
        workspace_id: Optional workspace filter
        offset: Offset for pagination
        batch_size: Number of clients to fetch

    Returns:
        List of Client instances
    """
    query = (
        select(Client)
        .where(
            (Client.medical_history.isnot(None) & (Client.medical_history != ""))
            | (Client.notes.isnot(None) & (Client.notes != ""))
        )
        .order_by(Client.created_at)
        .offset(offset)
        .limit(batch_size)
    )

    if workspace_id:
        query = query.where(Client.workspace_id == workspace_id)

    result = await db.execute(query)
    return list(result.scalars().all())


async def process_client(
    db: AsyncSession,
    client: Client,
    stats: BackfillStats,
    dry_run: bool = False,
) -> bool:
    """
    Process a single client - generate and store embeddings.

    Args:
        db: Database session
        client: Client instance to process
        stats: Statistics tracker
        dry_run: If True, don't actually create embeddings

    Returns:
        True if successful, False if failed
    """
    try:
        # Extract fields
        fields = {
            "medical_history": client.medical_history,
            "notes": client.notes,
        }

        # Filter out empty fields
        non_empty_fields = {
            field: text for field, text in fields.items() if text and text.strip()
        }

        if not non_empty_fields:
            logger.debug(
                "client_skipped_no_fields",
                client_id=str(client.id),
                workspace_id=str(client.workspace_id),
            )
            stats.clients_skipped += 1
            return True

        if dry_run:
            logger.info(
                "dry_run_would_embed",
                client_id=str(client.id),
                client_name=client.full_name,
                workspace_id=str(client.workspace_id),
                fields=list(non_empty_fields.keys()),
            )
            stats.clients_processed += 1
            stats.embeddings_created += len(non_empty_fields)
            return True

        # Check if embeddings already exist
        existing_query = (
            select(func.count(ClientVector.id))
            .where(ClientVector.client_id == client.id)
            .where(ClientVector.workspace_id == client.workspace_id)
        )
        result = await db.execute(existing_query)
        existing_count = result.scalar_one()

        if existing_count > 0:
            logger.debug(
                "client_embeddings_already_exist",
                client_id=str(client.id),
                workspace_id=str(client.workspace_id),
                existing_count=existing_count,
            )
            stats.clients_skipped += 1
            return True

        # Generate embeddings
        embedding_service = get_embedding_service()
        embeddings = await embedding_service.embed_client_fields(
            medical_history=fields.get("medical_history"),
            notes=fields.get("notes"),
        )

        # Store embeddings
        vector_store = get_vector_store(db)
        await vector_store.insert_client_embeddings_batch(
            workspace_id=client.workspace_id,
            client_id=client.id,
            embeddings=embeddings,
        )

        # Commit transaction
        await db.commit()

        logger.info(
            "client_embeddings_created",
            client_id=str(client.id),
            client_name=client.full_name,
            workspace_id=str(client.workspace_id),
            fields_embedded=list(embeddings.keys()),
            embeddings_created=len(embeddings),
        )

        stats.clients_processed += 1
        stats.embeddings_created += len(embeddings)
        return True

    except (EmbeddingError, VectorStoreError) as e:
        logger.error(
            "client_embedding_failed",
            client_id=str(client.id),
            workspace_id=str(client.workspace_id),
            error=str(e),
            error_type=type(e).__name__,
        )
        stats.clients_failed += 1
        return False

    except Exception as e:
        logger.error(
            "unexpected_error_processing_client",
            client_id=str(client.id),
            workspace_id=str(client.workspace_id),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        stats.clients_failed += 1
        return False


async def backfill_client_embeddings(
    workspace_id: uuid.UUID | None = None,
    limit: int | None = None,
    batch_size: int = 10,
    dry_run: bool = False,
) -> BackfillStats:
    """
    Backfill client embeddings for all clients with non-empty fields.

    Args:
        workspace_id: Optional workspace filter
        limit: Optional limit on number of clients to process
        batch_size: Number of clients to process per batch
        dry_run: If True, don't actually create embeddings

    Returns:
        BackfillStats with operation statistics
    """
    stats = BackfillStats()

    logger.info(
        "backfill_started",
        workspace_id=str(workspace_id) if workspace_id else "all",
        limit=limit,
        batch_size=batch_size,
        dry_run=dry_run,
    )

    try:
        async with AsyncSessionLocal() as db:
            # Count total clients
            stats.total_clients = await count_clients(db, workspace_id)

            if limit:
                stats.total_clients = min(stats.total_clients, limit)

            print(f"Found {stats.total_clients} clients to process")

            if stats.total_clients == 0:
                print("No clients to process.")
                return stats

            if dry_run:
                print("DRY RUN MODE - No changes will be made")

            # Process in batches
            offset = 0
            while offset < stats.total_clients:
                # Fetch batch
                batch = await get_clients_batch(db, workspace_id, offset, batch_size)

                if not batch:
                    break

                # Process each client in batch
                for client in batch:
                    await process_client(db, client, stats, dry_run)
                    stats.print_progress()

                    # Check limit
                    if limit and stats.clients_processed >= limit:
                        break

                offset += len(batch)

                # Check limit
                if limit and stats.clients_processed >= limit:
                    break

            print()  # New line after progress
            stats.print_summary()

            logger.info(
                "backfill_completed",
                total_clients=stats.total_clients,
                processed=stats.clients_processed,
                skipped=stats.clients_skipped,
                failed=stats.clients_failed,
                embeddings_created=stats.embeddings_created,
            )

            return stats

    except Exception as e:
        logger.error(
            "backfill_failed",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        print(f"\nBackfill failed: {e}", file=sys.stderr)
        sys.exit(1)


async def main():
    """Main entry point for backfill script."""
    parser = argparse.ArgumentParser(
        description="Backfill vector embeddings for existing client profiles"
    )
    parser.add_argument(
        "--workspace-id",
        type=str,
        help="Only process clients in this workspace (UUID)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of clients to process",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of clients to process per batch (default: 10)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    # Parse workspace_id if provided
    workspace_id = None
    if args.workspace_id:
        try:
            workspace_id = uuid.UUID(args.workspace_id)
        except ValueError:
            print(f"Invalid workspace ID: {args.workspace_id}", file=sys.stderr)
            sys.exit(1)

    # Run backfill
    stats = await backfill_client_embeddings(
        workspace_id=workspace_id,
        limit=args.limit,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )

    # Exit with error code if any clients failed
    if stats.clients_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
