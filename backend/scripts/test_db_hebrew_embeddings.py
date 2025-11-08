#!/usr/bin/env python3
"""
Test actual Hebrew embeddings stored in the database.

This script tests if the embeddings in the database are correctly matching
against Hebrew queries.
"""

import asyncio
import uuid

from pazpaz.ai.embeddings import get_embedding_service
from pazpaz.ai.vector_store import get_vector_store
from pazpaz.db.base import AsyncSessionLocal


async def test_db_hebrew_embeddings():
    """Test Hebrew embeddings in the database."""

    workspace_id = uuid.UUID("d5f97757-65f0-40fb-a58e-55103d76a8a6")
    client_id = uuid.UUID("85f54236-9eeb-4396-bfdb-0230c8283fd3")

    print("=" * 80)
    print("Testing Hebrew Embeddings in Database")
    print("=" * 80)

    async with AsyncSessionLocal() as db:
        # Get embedding service and vector store
        embedding_service = get_embedding_service(input_type="search_query")
        vector_store = get_vector_store(db)

        # Test query
        query_text = "כאבי צוואר דוד"

        print(f"\n📝 Query: '{query_text}'")
        print("-" * 80)

        # Embed the query
        print("Embedding query...")
        query_embedding = await embedding_service.embed_text(query_text)
        print(f"✅ Query embedded: {len(query_embedding)} dimensions")
        print(f"   First 5 values: {query_embedding[:5]}")

        # Search with different thresholds
        thresholds = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]

        for threshold in thresholds:
            print(f"\n🔍 Searching with min_similarity={threshold}")
            print("-" * 80)

            results = await vector_store.search_similar(
                workspace_id=workspace_id,
                query_embedding=query_embedding,
                limit=10,
                min_similarity=threshold,
            )

            if results:
                print(f"✅ Found {len(results)} results:")
                for i, (vector, similarity) in enumerate(results[:5], 1):
                    print(f"   {i}. {vector.field_name:12} | similarity: {similarity:.4f}")
            else:
                print(f"❌ No results found (all similarities < {threshold})")

        # Get ALL embeddings for this client (no threshold)
        print(f"\n📊 Getting ALL embeddings for client {client_id}")
        print("-" * 80)

        all_results = await vector_store.search_similar(
            workspace_id=workspace_id,
            query_embedding=query_embedding,
            limit=50,
            min_similarity=0.0,  # Get everything
        )

        if all_results:
            print(f"✅ Found {len(all_results)} total embeddings")
            print("\nTop 10 matches:")
            for i, (vector, similarity) in enumerate(all_results[:10], 1):
                print(f"   {i:2}. {vector.field_name:12} | similarity: {similarity:.4f} | session: {str(vector.session_id)[:8]}...")

            # Check if any are above 0.3
            above_threshold = [s for _, s in all_results if s >= 0.3]
            print(f"\n📈 Embeddings above 0.3 threshold: {len(above_threshold)}/{len(all_results)}")

            if not above_threshold:
                print("\n🔴 PROBLEM IDENTIFIED: No embeddings have similarity >= 0.3")
                print("   This explains why queries return no results!")
                highest_similarity = max(s for _, s in all_results)
                print(f"   Highest similarity found: {highest_similarity:.4f}")
        else:
            print("❌ No embeddings found at all in database!")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(test_db_hebrew_embeddings())
