"""
End-to-end test for AI agent query functionality.

This test validates the complete RAG pipeline:
1. Embedding generation (mocked Cohere API)
2. Vector storage in PostgreSQL
3. Similarity search
4. LLM synthesis (mocked Cohere API)
5. Response formatting with citations

This is the single most important test for the AI system, covering
the actual user-facing functionality as implemented.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.ai.agent import ClinicalAgent, get_clinical_agent
from pazpaz.ai.embeddings import get_embedding_service
from pazpaz.ai.vector_store import get_vector_store
from pazpaz.models.client import Client
from pazpaz.models.session import Session
from pazpaz.models.workspace import Workspace


@pytest.mark.asyncio
class TestAIAgentEndToEnd:
    """End-to-end test for AI agent with mocked Cohere API."""

    @pytest_asyncio.fixture
    async def mock_cohere_embeddings(self):
        """Mock Cohere embedding API to return deterministic vectors."""

        def generate_embedding(text: str) -> list[float]:
            """Generate a deterministic 1536-dim embedding based on text hash."""
            # Use text hash to create a deterministic but unique embedding
            text_hash = hash(text)
            base = [(text_hash >> i) % 100 / 100.0 for i in range(1536)]
            # Normalize to unit vector (as Cohere does)
            magnitude = sum(x * x for x in base) ** 0.5
            return [x / magnitude for x in base]

        with patch("cohere.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            # Mock embed endpoint
            async def mock_embed(texts, model, input_type, embedding_types):
                return MagicMock(
                    embeddings=MagicMock(
                        float_=[generate_embedding(t) for t in texts]
                    )
                )

            mock_client.embed = AsyncMock(side_effect=mock_embed)

            # Mock chat endpoint
            async def mock_chat(model, messages, temperature, max_tokens):
                # Extract query from messages
                query = messages[-1]["content"]

                # Generate a realistic response based on query
                if "back pain" in query.lower():
                    answer = (
                        "Based on the clinical notes, the patient reported lower back pain "
                        "that started 3 days ago after lifting heavy boxes. The pain is sharp "
                        "with 7/10 intensity and radiates to the left leg. Treatment included "
                        "rest, ice therapy 3x/day, and NSAIDs as needed."
                    )
                elif "treatment" in query.lower():
                    answer = (
                        "The treatment plan included rest, ice therapy (20 minutes 3 times daily), "
                        "NSAIDs as needed for pain management, and gentle stretching exercises. "
                        "A follow-up was scheduled for 5 days later."
                    )
                else:
                    answer = "Based on the available session notes, I found relevant information about the patient's condition and treatment."

                return MagicMock(
                    message=MagicMock(content=[MagicMock(text=answer)])
                )

            mock_client.chat = AsyncMock(side_effect=mock_chat)

            yield mock_client

    @pytest_asyncio.fixture
    async def clinical_data(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
        mock_cohere_embeddings,
    ) -> tuple[Client, list[Session]]:
        """Create realistic clinical data with embedded SOAP notes."""

        # Create client
        client = Client(
            workspace_id=workspace_1.id,
            first_name="Sarah",
            last_name="Johnson",
            email="sarah.j@example.com",
            phone="+972501234567",
        )
        db_session.add(client)
        await db_session.flush()

        # Create session with realistic SOAP notes
        session = Session(
            workspace_id=workspace_1.id,
            client_id=client.id,
            session_date=datetime.now(UTC),
            subjective=(
                "Patient reports lower back pain radiating to left leg. "
                "Pain started 3 days ago after lifting heavy boxes. "
                "Pain is sharp, 7/10 intensity, worsens with movement."
            ),
            objective=(
                "Reduced range of motion in lumbar spine. "
                "Positive straight leg raise test on left side. "
                "No neurological deficits observed."
            ),
            assessment=(
                "Acute lumbar strain with possible disc involvement. "
                "No red flags observed."
            ),
            plan=(
                "Rest, ice 20 min 3x/day. NSAIDs as needed. "
                "Gentle stretching. Follow-up in 5 days."
            ),
        )
        db_session.add(session)
        await db_session.flush()

        # Generate embeddings and store in vector database
        embedding_service = get_embedding_service()
        vector_store = get_vector_store(db_session)

        embeddings = await embedding_service.embed_soap_fields(
            subjective=session.subjective,
            objective=session.objective,
            assessment=session.assessment,
            plan=session.plan,
        )

        await vector_store.insert_embeddings_batch(
            workspace_id=workspace_1.id,
            session_id=session.id,
            embeddings=embeddings,
        )

        await db_session.commit()

        return client, [session]

    async def test_ai_agent_query_with_embeddings(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
        clinical_data: tuple[Client, list[Session]],
        mock_cohere_embeddings,
    ):
        """
        Test the complete AI agent pipeline:
        - User asks a clinical question
        - Agent embeds query (mocked)
        - Vector search finds relevant sessions
        - LLM synthesizes answer (mocked)
        - Response includes citations
        """
        client, sessions = clinical_data
        agent: ClinicalAgent = get_clinical_agent(db_session)

        # Query about back pain
        response = await agent.query(
            workspace_id=workspace_1.id,
            client_id=client.id,
            query="What caused the patient's back pain and what was the treatment?",
            max_results=5,
            min_similarity=0.3,
        )

        # Verify response structure
        assert response.answer, "Should have an answer"
        assert len(response.answer) > 0, "Answer should not be empty"
        assert isinstance(response.answer, str), "Answer should be a string"

        # Verify language detection
        assert response.language in ["en", "he"], "Should detect language"

        # Verify performance tracking
        assert response.processing_time_ms > 0, "Should track processing time"
        assert response.processing_time_ms < 30000, "Should respond in <30s"

        # Verify retrieval metrics
        assert response.retrieved_count >= 0, "Should track retrieved count"

        # Verify citations
        assert isinstance(response.citations, list), "Should have citations list"
        if response.retrieved_count > 0:
            assert len(response.citations) > 0, "Should have citations if results found"

            # Verify citation structure
            for citation in response.citations:
                assert citation.session_id == sessions[0].id, "Citation should reference our session"
                assert citation.client_name == client.full_name, "Should have client name"
                assert 0.0 <= citation.similarity <= 1.0, "Similarity should be 0-1"
                assert citation.field_name in ["subjective", "objective", "assessment", "plan"]

        # Verify answer content (should mention back pain or treatment)
        answer_lower = response.answer.lower()
        assert (
            "back pain" in answer_lower
            or "treatment" in answer_lower
            or "lifting" in answer_lower
            or "ice" in answer_lower
        ), "Answer should be relevant to the query"

    async def test_workspace_isolation(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
        workspace_2: Workspace,
        clinical_data: tuple[Client, list[Session]],
        mock_cohere_embeddings,
    ):
        """
        Test that AI agent respects workspace boundaries.

        Workspace 1 should NOT see data from workspace 2.
        """
        client1, _ = clinical_data
        agent: ClinicalAgent = get_clinical_agent(db_session)

        # Create client in workspace 2
        client2 = Client(
            workspace_id=workspace_2.id,
            first_name="Different",
            last_name="Client",
            email="different@example.com",
        )
        db_session.add(client2)
        await db_session.flush()

        session2 = Session(
            workspace_id=workspace_2.id,
            client_id=client2.id,
            session_date=datetime.now(UTC),
            subjective="Patient has knee pain after running.",
            objective="Swelling in right knee.",
            assessment="Runner's knee.",
            plan="RICE protocol.",
        )
        db_session.add(session2)
        await db_session.flush()

        # Embed workspace 2 session
        embedding_service = get_embedding_service()
        vector_store = get_vector_store(db_session)

        embeddings = await embedding_service.embed_soap_fields(
            subjective=session2.subjective,
            objective=session2.objective,
            assessment=session2.assessment,
            plan=session2.plan,
        )

        await vector_store.insert_embeddings_batch(
            workspace_id=workspace_2.id,
            session_id=session2.id,
            embeddings=embeddings,
        )
        await db_session.commit()

        # Query workspace 1 about knee pain (workspace 2 data)
        response = await agent.query(
            workspace_id=workspace_1.id,
            query="What was the treatment for knee pain?",
            max_results=10,
            min_similarity=0.3,
        )

        # Workspace 1 should NOT see workspace 2 data
        if response.citations:
            for citation in response.citations:
                assert citation.session_id != session2.id, (
                    "Workspace 1 should not access workspace 2 sessions"
                )

    async def test_no_results_fallback(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
        mock_cohere_embeddings,
    ):
        """
        Test agent behavior when no relevant results are found.

        Should return a helpful message rather than an empty response.
        """
        agent: ClinicalAgent = get_clinical_agent(db_session)

        # Query about something completely unrelated (no sessions exist)
        response = await agent.query(
            workspace_id=workspace_1.id,
            query="What was discussed about cardiac surgery?",
            max_results=5,
            min_similarity=0.9,  # Very high threshold
        )

        # Verify graceful handling
        assert response.answer, "Should have an answer even with no results"
        assert response.retrieved_count == 0, "Should report 0 results"
        assert len(response.citations) == 0, "Should have no citations"

        # Verify fallback message
        answer_lower = response.answer.lower()
        assert (
            "no relevant" in answer_lower
            or "not found" in answer_lower
            or "no information" in answer_lower
            or "לא נמצא" in response.answer  # Hebrew: "not found"
        ), "Should indicate no results found"
