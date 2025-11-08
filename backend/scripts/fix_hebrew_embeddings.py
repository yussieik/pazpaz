#!/usr/bin/env python3
"""
Fix Hebrew embeddings by deleting and regenerating them.

This script:
1. Deletes all existing embeddings for David's sessions
2. Regenerates fresh embeddings using the correct API configuration
"""

import asyncio
import uuid

from pazpaz.ai.embeddings import get_embedding_service
from pazpaz.ai.vector_store import get_vector_store
from pazpaz.db.base import AsyncSessionLocal
from pazpaz.models.session import Session
from sqlalchemy import select


async def fix_hebrew_embeddings():
    """Delete and regenerate Hebrew embeddings for David's sessions."""

    workspace_id = uuid.UUID("d5f97757-65f0-40fb-a58e-55103d76a8a6")
    client_id = uuid.UUID("85f54236-9eeb-4396-bfdb-0230c8283fd3")

    print("=" * 80)
    print("Fixing Hebrew Embeddings for David Levi")
    print("=" * 80)

    async with AsyncSessionLocal() as db:
        vector_store = get_vector_store(db)

        # Step 1: Delete all existing embeddings for this client's sessions
        print("\n1️⃣  Deleting existing embeddings...")
        print("-" * 80)

        # Fetch all sessions for this client
        result = await db.execute(
            select(Session).where(
                Session.workspace_id == workspace_id,
                Session.client_id == client_id,
            )
        )
        sessions = result.scalars().all()

        print(f"Found {len(sessions)} sessions for David")

        total_deleted = 0
        for session in sessions:
            deleted = await vector_store.delete_session_embeddings(
                workspace_id=workspace_id,
                session_id=session.id,
            )
            total_deleted += deleted
            print(f"   Session {str(session.id)[:8]}... - Deleted {deleted} embeddings")

        print(f"\n✅ Deleted {total_deleted} total embeddings")

        # Step 2: Regenerate embeddings with correct configuration
        print("\n2️⃣  Regenerating embeddings...")
        print("-" * 80)

        # Use search_document input type (for indexing)
        embedding_service = get_embedding_service(input_type="search_document")

        total_created = 0
        for session in sessions:
            print(f"\n   Processing session {str(session.id)[:8]}...")
            print(f"   Date: {session.session_date}")

            # Collect non-empty SOAP fields
            soap_fields = {}
            if session.subjective:
                soap_fields["subjective"] = session.subjective
            if session.objective:
                soap_fields["objective"] = session.objective
            if session.assessment:
                soap_fields["assessment"] = session.assessment
            if session.plan:
                soap_fields["plan"] = session.plan

            if not soap_fields:
                print("   ⚠️  No SOAP fields to embed")
                continue

            print(f"   Fields: {', '.join(soap_fields.keys())}")

            # Generate embeddings
            embeddings = await embedding_service.embed_soap_fields(
                subjective=soap_fields.get("subjective"),
                objective=soap_fields.get("objective"),
                assessment=soap_fields.get("assessment"),
                plan=soap_fields.get("plan"),
            )

            # Store embeddings
            await vector_store.insert_embeddings_batch(
                workspace_id=workspace_id,
                session_id=session.id,
                embeddings=embeddings,
            )

            total_created += len(embeddings)
            print(f"   ✅ Created {len(embeddings)} embeddings")

        await db.commit()

        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"✅ Deleted:  {total_deleted} embeddings")
        print(f"✅ Created:  {total_created} embeddings")
        print(f"✅ Sessions: {len(sessions)}")

        print("\n" + "=" * 80)
        print("VERIFICATION")
        print("=" * 80)
        print("Testing query: 'כאבי צוואר דוד'")

        # Test with a query
        query_service = get_embedding_service(input_type="search_query")
        query_embedding = await query_service.embed_text("כאבי צוואר דוד")

        results = await vector_store.search_similar(
            workspace_id=workspace_id,
            query_embedding=query_embedding,
            limit=5,
            min_similarity=0.3,
        )

        if results:
            print(f"\n✅ SUCCESS! Found {len(results)} results above 0.3 threshold:")
            for i, (vector, similarity) in enumerate(results, 1):
                print(f"   {i}. {vector.field_name:12} | similarity: {similarity:.4f}")
        else:
            print("\n❌ STILL NO RESULTS - Issue persists!")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(fix_hebrew_embeddings())
