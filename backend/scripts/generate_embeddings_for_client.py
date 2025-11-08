#!/usr/bin/env python3
"""
Generate Embeddings for Existing Client Sessions

This script manually generates embeddings for a client's sessions.
Useful when sessions were created directly in the database.

Usage:
    cd backend
    env PYTHONPATH=src uv run python scripts/generate_embeddings_for_client.py <client_id>
"""

import asyncio
import sys

from sqlalchemy import select

from pazpaz.ai.embeddings import EmbeddingService
from pazpaz.ai.vector_store import VectorStore
from pazpaz.db.base import AsyncSessionLocal
from pazpaz.models.client import Client
from pazpaz.models.session import Session


async def generate_embeddings_for_client(client_id: str):
    """Generate embeddings for all sessions of a client."""
    async with AsyncSessionLocal() as db:
        # Fetch client
        result = await db.execute(
            select(Client).where(Client.id == client_id)
        )
        client = result.scalar_one_or_none()

        if not client:
            print(f"❌ Client {client_id} not found")
            return

        print(f"✅ Found client: {client.first_name} {client.last_name}")
        print(f"   Workspace ID: {client.workspace_id}")

        # Fetch all sessions for this client
        result = await db.execute(
            select(Session).where(
                Session.client_id == client_id,
                Session.workspace_id == client.workspace_id
            )
        )
        sessions = result.scalars().all()

        if not sessions:
            print(f"❌ No sessions found for client {client_id}")
            return

        print(f"\n✅ Found {len(sessions)} sessions")

        # Initialize services
        embedding_service = EmbeddingService()
        vector_store = VectorStore(db)

        # Process each session
        for i, session in enumerate(sessions, 1):
            print(f"\n📝 Processing session {i}/{len(sessions)}...")
            print(f"   Session ID: {session.id}")
            print(f"   Date: {session.session_date}")

            # Collect SOAP fields
            fields_to_embed = {}
            if session.subjective:
                fields_to_embed['subjective'] = session.subjective
            if session.objective:
                fields_to_embed['objective'] = session.objective
            if session.assessment:
                fields_to_embed['assessment'] = session.assessment
            if session.plan:
                fields_to_embed['plan'] = session.plan

            if not fields_to_embed:
                print("   ⚠️  No SOAP fields to embed, skipping...")
                continue

            print(f"   Fields to embed: {', '.join(fields_to_embed.keys())}")

            # Generate embeddings
            try:
                embeddings = await embedding_service.embed_soap_fields(
                    subjective=fields_to_embed.get('subjective'),
                    objective=fields_to_embed.get('objective'),
                    assessment=fields_to_embed.get('assessment'),
                    plan=fields_to_embed.get('plan'),
                )
                print(f"   ✅ Generated {len(embeddings)} embeddings")

                # Store in vector store
                await vector_store.insert_embeddings_batch(
                    workspace_id=client.workspace_id,
                    session_id=session.id,
                    embeddings=embeddings,
                )
                print(f"   ✅ Stored embeddings in database")

            except Exception as e:
                print(f"   ❌ Error generating embeddings: {e}")
                continue

        await db.commit()

        print(f"\n🎉 Embedding generation complete!")
        print(f"\n📊 Summary:")
        print(f"   Client: {client.first_name} {client.last_name}")
        print(f"   Sessions processed: {len(sessions)}")
        print(f"   Total embeddings: {len(sessions) * 4} (assuming 4 SOAP fields per session)")

        print("\n✅ Ready to test AI agent with queries like:")
        print("   - 'When did Sarah's back pain start?'")
        print("   - 'What treatments helped Sarah the most?'")
        print("   - 'Did Sarah have any leg pain?'")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_embeddings_for_client.py <client_id>")
        sys.exit(1)

    client_id = sys.argv[1]

    print("Generating embeddings for client sessions...")
    print(f"Client ID: {client_id}\n")

    asyncio.run(generate_embeddings_for_client(client_id))
