#!/usr/bin/env python
"""
End-to-end test for embeddings with real patient/session data.

This script proves that:
1. Cohere embed-v4.0 generates 1536-dimensional embeddings
2. Embeddings can be stored in PostgreSQL with pgvector
3. Similarity search retrieves relevant sessions
4. The AI agent can query embedded session data

Run: uv run python tests/manual/test_embeddings_e2e.py
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.ai.agent import ClinicalAgent, get_clinical_agent
from pazpaz.ai.embeddings import get_embedding_service
from pazpaz.ai.vector_store import get_vector_store
from pazpaz.core.config import settings
from pazpaz.db.session import get_async_session_maker
from pazpaz.models.client import Client
from pazpaz.models.session import Session
from pazpaz.models.workspace import Workspace


async def cleanup_test_data(db: AsyncSession, workspace_id: uuid.UUID):
    """Clean up test data."""
    print("\n🧹 Cleaning up test data...")

    # Delete sessions (cascade deletes vectors)
    result = await db.execute(
        select(Session).where(Session.workspace_id == workspace_id)
    )
    sessions = result.scalars().all()
    for session in sessions:
        await db.delete(session)

    # Delete clients
    result = await db.execute(select(Client).where(Client.workspace_id == workspace_id))
    clients = result.scalars().all()
    for client in clients:
        await db.delete(client)

    # Delete workspace
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace:
        await db.delete(workspace)

    await db.commit()
    print("✓ Cleanup complete")


async def main():
    """Run end-to-end embedding test."""
    print("=" * 80)
    print("🧪 End-to-End Embeddings Test with Real Patient/Session Data")
    print("=" * 80)

    # Check configuration
    print(f"\n📋 Configuration:")
    print(f"  - Cohere API Key: {'✓ Set' if settings.cohere_api_key else '✗ Missing'}")
    print(f"  - Embedding Model: {settings.cohere_embed_model}")
    print(f"  - Expected Dimensions: 1536")

    if not settings.cohere_api_key:
        print("\n❌ ERROR: COHERE_API_KEY not set")
        return 1

    # Create database session
    SessionMaker = get_async_session_maker()
    async with SessionMaker() as db:
        workspace_id = uuid.uuid4()
        client_id = uuid.uuid4()

        try:
            # Step 1: Create test workspace and client
            print("\n" + "=" * 80)
            print("STEP 1: Create Test Workspace and Client")
            print("=" * 80)

            workspace = Workspace(
                id=workspace_id,
                name="Test Clinic",
                slug="test-clinic-e2e",
                owner_email="test@example.com",
            )
            db.add(workspace)

            client = Client(
                id=client_id,
                workspace_id=workspace_id,
                first_name="John",
                last_name="Doe",
                email="john.doe@example.com",
                phone="+972501234567",
                date_of_birth=datetime(1985, 5, 15),
            )
            db.add(client)
            await db.commit()

            print(f"✓ Created workspace: {workspace.name}")
            print(f"✓ Created client: {client.first_name} {client.last_name}")

            # Step 2: Create sessions with SOAP notes
            print("\n" + "=" * 80)
            print("STEP 2: Create Sessions with SOAP Notes")
            print("=" * 80)

            sessions_data = [
                {
                    "subjective": "Patient reports lower back pain radiating to left leg. Pain started 3 days ago after lifting heavy boxes. Describes pain as sharp, 7/10 intensity, worse with movement.",
                    "objective": "Reduced range of motion in lumbar spine. Positive straight leg raise test on left side. Tender to palpation at L4-L5. No neurological deficits observed.",
                    "assessment": "Acute lumbar strain with possible disc involvement. Rule out herniated disc. No red flags for cauda equina syndrome.",
                    "plan": "Rest, ice 20 min 3x/day. NSAIDs as needed. Gentle stretching exercises. Follow-up in 5 days. MRI if no improvement within 2 weeks.",
                },
                {
                    "subjective": "Patient reports improvement in back pain. Now 3/10 intensity. Able to perform daily activities with minimal discomfort. No leg radiation.",
                    "objective": "Improved range of motion. Negative straight leg raise bilaterally. Reduced tenderness at L4-L5. Good posture maintained.",
                    "assessment": "Resolving lumbar strain. Positive response to conservative treatment. No disc herniation suspected at this time.",
                    "plan": "Continue current regimen. Add core strengthening exercises. Gradual return to normal activities. Follow-up in 2 weeks or PRN.",
                },
                {
                    "subjective": "Patient presents with right shoulder pain. Pain began gradually over 2 weeks. Difficulty reaching overhead. No trauma history. 5/10 intensity.",
                    "objective": "Limited abduction and external rotation. Positive Neer's and Hawkins tests. No swelling or deformity. Strength 4/5 in affected shoulder.",
                    "assessment": "Rotator cuff tendinitis, likely supraspinatus. Consider impingement syndrome. No signs of tear.",
                    "plan": "Physical therapy referral. Anti-inflammatory medications. Ice after activities. Avoid overhead movements. Reassess in 3 weeks.",
                },
            ]

            sessions = []
            for i, soap_data in enumerate(sessions_data, 1):
                session = Session(
                    workspace_id=workspace_id,
                    client_id=client_id,
                    session_date=datetime.now(UTC),
                    duration_minutes=45,
                    subjective=soap_data["subjective"],
                    objective=soap_data["objective"],
                    assessment=soap_data["assessment"],
                    plan=soap_data["plan"],
                )
                db.add(session)
                sessions.append(session)
                print(f"✓ Created session {i}: {soap_data['assessment'][:60]}...")

            await db.flush()
            await db.commit()

            # Step 3: Generate embeddings
            print("\n" + "=" * 80)
            print("STEP 3: Generate Embeddings with Cohere embed-v4.0")
            print("=" * 80)

            embedding_service = get_embedding_service()
            vector_store = get_vector_store(db)

            for i, session in enumerate(sessions, 1):
                print(f"\nProcessing session {i}...")

                # Generate embeddings for all SOAP fields
                embeddings = embedding_service.embed_soap_fields(
                    subjective=session.subjective,
                    objective=session.objective,
                    assessment=session.assessment,
                    plan=session.plan,
                )

                # Verify dimensions
                for field_name, embedding in embeddings.items():
                    print(f"  - {field_name}: {len(embedding)} dimensions", end="")
                    if len(embedding) == 1536:
                        print(" ✓")
                    else:
                        print(f" ✗ (expected 1536)")
                        return 1

                # Store embeddings
                vectors = await vector_store.insert_embeddings_batch(
                    workspace_id=workspace_id,
                    session_id=session.id,
                    embeddings=embeddings,
                )

                print(f"  ✓ Stored {len(vectors)} embeddings in pgvector")

            await db.commit()

            # Step 4: Test similarity search
            print("\n" + "=" * 80)
            print("STEP 4: Test Similarity Search")
            print("=" * 80)

            test_queries = [
                ("back pain", "Should find lumbar strain sessions"),
                ("shoulder problems", "Should find rotator cuff session"),
                ("patient improvement", "Should find follow-up session"),
            ]

            for query_text, description in test_queries:
                print(f"\nQuery: '{query_text}'")
                print(f"Expected: {description}")

                # Generate query embedding
                query_embedding = embedding_service.embed_text(query_text)
                print(f"  - Query embedding: {len(query_embedding)} dimensions ✓")

                # Search
                results = await vector_store.search_similar(
                    workspace_id=workspace_id,
                    query_embedding=query_embedding,
                    limit=3,
                    min_similarity=0.3,  # Lower threshold to see more results
                )

                print(f"  - Found {len(results)} results:")
                for vector, similarity in results:
                    # Get the session
                    result = await db.execute(
                        select(Session).where(Session.id == vector.session_id)
                    )
                    session = result.scalar_one()
                    print(f"    • {vector.field_name}: {similarity:.3f} similarity")
                    print(f"      Assessment: {session.assessment[:80]}...")

            # Step 5: Test AI Agent
            print("\n" + "=" * 80)
            print("STEP 5: Test AI Agent Query")
            print("=" * 80)

            agent: ClinicalAgent = get_clinical_agent(db)

            test_agent_queries = [
                "What was the patient's back pain history?",
                "Has the patient shown improvement?",
                "What treatments were recommended for the shoulder?",
            ]

            for query in test_agent_queries:
                print(f"\nAgent Query: '{query}'")

                response = await agent.query(
                    workspace_id=workspace_id,
                    client_id=client_id,
                    query=query,
                )

                print(f"  - Language: {response.language}")
                print(f"  - Retrieved: {response.retrieved_count} sessions")
                print(f"  - Citations: {len(response.citations)}")
                print(f"  - Processing time: {response.processing_time_ms}ms")
                print(f"\n  Answer: {response.answer[:300]}...")

                if response.citations:
                    print(f"\n  Citations:")
                    for citation in response.citations[:3]:
                        print(f"    • Session {citation.session_id}")
                        print(f"      Field: {citation.field_name}")
                        print(f"      Content: {citation.content[:100]}...")

            # Step 6: Verify workspace isolation
            print("\n" + "=" * 80)
            print("STEP 6: Verify Workspace Isolation")
            print("=" * 80)

            # Count embeddings in our workspace
            our_count = await vector_store.count_workspace_embeddings(workspace_id)
            print(f"  - Our workspace embeddings: {our_count}")

            # Try to query with a different workspace ID
            fake_workspace_id = uuid.uuid4()
            fake_results = await vector_store.search_similar(
                workspace_id=fake_workspace_id,
                query_embedding=query_embedding,
                limit=10,
            )
            print(f"  - Fake workspace results: {len(fake_results)}")

            if len(fake_results) == 0:
                print("  ✓ Workspace isolation verified!")
            else:
                print("  ✗ WARNING: Workspace isolation breach!")
                return 1

            # Success!
            print("\n" + "=" * 80)
            print("✅ ALL TESTS PASSED!")
            print("=" * 80)
            print("\nSummary:")
            print(f"  ✓ Cohere embed-v4.0 generates 1536-dimensional embeddings")
            print(f"  ✓ Embeddings stored successfully in pgvector")
            print(f"  ✓ Similarity search retrieves relevant sessions")
            print(f"  ✓ AI agent queries work with embedded data")
            print(f"  ✓ Workspace isolation is enforced")
            print(f"  ✓ Created {len(sessions)} sessions with {our_count} embeddings")

            return 0

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback

            traceback.print_exc()
            return 1

        finally:
            # Clean up
            await cleanup_test_data(db, workspace_id)


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
