#!/usr/bin/env python3
"""
Test Hebrew embeddings with different input_type configurations.

This script tests the hypothesis that Hebrew embeddings have low similarity
when using mismatched input_type (search_document vs search_query).
"""

import asyncio

from pazpaz.ai.embeddings import get_embedding_service


async def test_hebrew_embeddings():
    """Test Hebrew embedding similarity with different input types."""

    # Hebrew text samples
    document_text = "דוד לוי מתלונן על כאבי צוואר חדים בצד ימין"
    query_text = "כאבי צוואר דוד"

    print("=" * 80)
    print("Testing Hebrew Embeddings - Input Type Compatibility")
    print("=" * 80)

    # Test 1: Both search_document (current DB embeddings)
    print("\n1️⃣  Test 1: Both using search_document (current situation)")
    print("-" * 80)

    service_doc = get_embedding_service(input_type="search_document")
    doc_embedding = await service_doc.embed_text(document_text)
    query_as_doc_embedding = await service_doc.embed_text(query_text)

    # Calculate cosine similarity
    similarity_doc_to_doc = calculate_cosine_similarity(
        doc_embedding, query_as_doc_embedding
    )
    print(f"Document (search_document): '{document_text}'")
    print(f"Query    (search_document): '{query_text}'")
    print(f"Similarity: {similarity_doc_to_doc:.4f}")

    # Test 2: search_document vs search_query (what we're currently doing)
    print("\n2️⃣  Test 2: search_document (DB) vs search_query (query) - CURRENT SYSTEM")
    print("-" * 80)

    service_query = get_embedding_service(input_type="search_query")
    query_embedding = await service_query.embed_text(query_text)

    similarity_doc_to_query = calculate_cosine_similarity(
        doc_embedding, query_embedding
    )
    print(f"Document (search_document): '{document_text}'")
    print(f"Query    (search_query):    '{query_text}'")
    print(f"Similarity: {similarity_doc_to_query:.4f}")

    # Test 3: Both search_query (wrong, but for comparison)
    print("\n3️⃣  Test 3: Both using search_query (for comparison)")
    print("-" * 80)

    doc_as_query_embedding = await service_query.embed_text(document_text)

    similarity_query_to_query = calculate_cosine_similarity(
        doc_as_query_embedding, query_embedding
    )
    print(f"Document (search_query): '{document_text}'")
    print(f"Query    (search_query): '{query_text}'")
    print(f"Similarity: {similarity_query_to_query:.4f}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ Correct pairing (doc→doc):           {similarity_doc_to_doc:.4f}")
    print(f"❌ Current system (doc→query):          {similarity_doc_to_query:.4f}")
    print(f"⚠️  Wrong but same type (query→query): {similarity_query_to_query:.4f}")

    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)

    if similarity_doc_to_query < 0.3:
        print(
            "🔴 ISSUE CONFIRMED: Current system (doc→query) similarity < 0.3 threshold!"
        )
        print("   This explains why Hebrew queries return no results.")
    else:
        print("🟢 Current system similarity is above threshold - issue elsewhere")

    if similarity_doc_to_doc > similarity_doc_to_query:
        print(
            f"\n💡 Using matching input_types improves similarity by {((similarity_doc_to_doc - similarity_doc_to_query) / similarity_doc_to_query * 100):.1f}%"
        )

    print("\n" + "=" * 80)


def calculate_cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    import math

    # Dot product
    dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=False))

    # Magnitudes
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))

    # Cosine similarity
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)


if __name__ == "__main__":
    asyncio.run(test_hebrew_embeddings())
