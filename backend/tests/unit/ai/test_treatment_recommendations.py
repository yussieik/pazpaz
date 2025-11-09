"""Unit tests for Treatment Recommendation Engine (ADR 0002 Milestone 1).

This test suite validates:
1. Therapy type detection (_detect_therapy_type_simple)
2. LLM response parsing (_parse_recommendations)
3. Treatment plan generation (recommend_treatment_plan)
4. Integration with existing RAG pipeline
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.ai.agent import get_clinical_agent
from pazpaz.models.client import Client
from pazpaz.models.session import Session
from pazpaz.models.workspace import Workspace


class TestTherapyTypeDetection:
    """Test therapy type detection using keyword matching."""

    @pytest.mark.asyncio
    async def test_detect_massage_therapy(self, db_session: AsyncSession):
        """Should detect massage therapy from clinical terminology."""
        agent = get_clinical_agent(db_session)

        subjective = "Patient reports muscle tension and trigger points"
        objective = "Palpation reveals myofascial restrictions in upper trapezius"
        assessment = "Myofascial pain syndrome"

        therapy_type = agent.treatment_recommender._detect_therapy_type_simple(
            subjective=subjective,
            objective=objective,
            assessment=assessment,
        )

        assert therapy_type == "massage"

    @pytest.mark.asyncio
    async def test_detect_physiotherapy(self, db_session: AsyncSession):
        """Should detect physiotherapy from clinical terminology."""
        agent = get_clinical_agent(db_session)

        subjective = "Patient reports limited range of motion in right shoulder"
        objective = "ROM: 90° flexion, 60° abduction. Strength 3/5 rotator cuff"
        assessment = "Rotator cuff weakness, restricted ROM"

        therapy_type = agent.treatment_recommender._detect_therapy_type_simple(
            subjective=subjective,
            objective=objective,
            assessment=assessment,
        )

        assert therapy_type == "physiotherapy"

    @pytest.mark.asyncio
    async def test_detect_psychotherapy(self, db_session: AsyncSession):
        """Should detect psychotherapy from clinical terminology."""
        agent = get_clinical_agent(db_session)

        subjective = "Patient reports anxiety about work presentation"
        objective = "Elevated heart rate, tense posture, rapid speech"
        assessment = "Generalized anxiety disorder, work-related stress"

        therapy_type = agent.treatment_recommender._detect_therapy_type_simple(
            subjective=subjective,
            objective=objective,
            assessment=assessment,
        )

        assert therapy_type == "psychotherapy"

    @pytest.mark.asyncio
    async def test_detect_generic_fallback(self, db_session: AsyncSession):
        """Should default to generic when no clear therapy type detected."""
        agent = get_clinical_agent(db_session)

        subjective = "Patient complains of general discomfort"
        objective = "Vital signs normal"
        assessment = "General malaise"

        therapy_type = agent.treatment_recommender._detect_therapy_type_simple(
            subjective=subjective,
            objective=objective,
            assessment=assessment,
        )

        assert therapy_type == "generic"

    @pytest.mark.asyncio
    async def test_therapy_type_priority_massage_over_physio(
        self, db_session: AsyncSession
    ):
        """When both massage and physio keywords present, should choose higher count."""
        agent = get_clinical_agent(db_session)

        # More massage keywords (trigger points, myofascial, muscle tension = 3)
        # vs physio (ROM = 1)
        subjective = "Trigger points and muscle tension with limited ROM"
        objective = "Myofascial restrictions palpated"
        assessment = "Myofascial pain"

        therapy_type = agent.treatment_recommender._detect_therapy_type_simple(
            subjective=subjective,
            objective=objective,
            assessment=assessment,
        )

        assert therapy_type == "massage"


class TestRecommendationParsing:
    """Test parsing of LLM responses into structured recommendations."""

    @pytest.mark.asyncio
    async def test_parse_single_recommendation(self, db_session: AsyncSession):
        """Should parse a single well-formatted recommendation."""
        agent = get_clinical_agent(db_session)

        llm_response = """
Recommendation 1:
Title: Manual Therapy + Home Exercises
Description: Apply manual therapy to upper trapezius trigger points using sustained pressure (30-60 seconds). Prescribe home exercises: gentle neck stretches (3x daily) and postural corrections. Ice for 15 minutes post-treatment.
"""

        recommendations = agent.treatment_recommender._parse_recommendations(
            llm_response=llm_response,
            therapy_type="massage",
            evidence_type="hybrid",
            similar_cases_count=5,
        )

        assert len(recommendations) == 1
        assert recommendations[0].title == "Manual Therapy + Home Exercises"
        assert "sustained pressure" in recommendations[0].description
        assert recommendations[0].therapy_type == "massage"
        assert recommendations[0].evidence_type == "hybrid"
        assert recommendations[0].similar_cases_count == 5

    @pytest.mark.asyncio
    async def test_parse_two_recommendations(self, db_session: AsyncSession):
        """Should parse two well-formatted recommendations."""
        agent = get_clinical_agent(db_session)

        llm_response = """
Recommendation 1:
Title: Manual Therapy + Stretching
Description: Apply deep tissue massage to upper trapezius and levator scapulae. Follow with passive stretching to improve ROM.

Recommendation 2:
Title: Myofascial Release Technique
Description: Use myofascial release on cervical paraspinals and scalenes. Apply gentle sustained pressure for 90-120 seconds.
"""

        recommendations = agent.treatment_recommender._parse_recommendations(
            llm_response=llm_response,
            therapy_type="massage",
            evidence_type="clinical_guidelines",
            similar_cases_count=0,
        )

        assert len(recommendations) == 2
        assert recommendations[0].title == "Manual Therapy + Stretching"
        assert recommendations[1].title == "Myofascial Release Technique"
        assert all(rec.therapy_type == "massage" for rec in recommendations)
        assert all(rec.similar_cases_count == 0 for rec in recommendations)

    @pytest.mark.asyncio
    async def test_parse_fallback_to_full_response(self, db_session: AsyncSession):
        """Should use full response if parsing fails (malformed LLM output)."""
        agent = get_clinical_agent(db_session)

        # Malformed response (no "Recommendation 1:" structure)
        llm_response = """
I recommend applying manual therapy to the upper trapezius with sustained pressure
and prescribing home exercises including gentle neck stretches.
"""

        recommendations = agent.treatment_recommender._parse_recommendations(
            llm_response=llm_response,
            therapy_type="massage",
            evidence_type="clinical_guidelines",
            similar_cases_count=0,
        )

        # Should fall back to treating entire response as single recommendation
        assert len(recommendations) == 1
        assert recommendations[0].title == "Treatment Plan Recommendation"
        assert "manual therapy" in recommendations[0].description.lower()

    @pytest.mark.asyncio
    async def test_parse_limits_to_two_recommendations(self, db_session: AsyncSession):
        """Should limit to 2 recommendations even if LLM returns more."""
        agent = get_clinical_agent(db_session)

        llm_response = """
Recommendation 1:
Title: First Treatment
Description: First treatment plan details.

Recommendation 2:
Title: Second Treatment
Description: Second treatment plan details.

Recommendation 3:
Title: Third Treatment
Description: Third treatment plan details (should be ignored).
"""

        recommendations = agent.treatment_recommender._parse_recommendations(
            llm_response=llm_response,
            therapy_type="physiotherapy",
            evidence_type="workspace_patterns",
            similar_cases_count=3,
        )

        # Should only return first 2 recommendations
        assert len(recommendations) == 2
        assert recommendations[0].title == "First Treatment"
        assert recommendations[1].title == "Second Treatment"


@pytest.mark.asyncio
class TestRecommendTreatmentPlan:
    """Test end-to-end treatment recommendation generation."""

    @pytest_asyncio.fixture
    async def mock_cohere_recommendations(self):
        """Mock Cohere API for treatment recommendations."""

        def generate_embedding(text: str) -> list[float]:
            """Generate deterministic embedding."""
            text_hash = hash(text)
            base = [(text_hash >> i) % 100 / 100.0 for i in range(1536)]
            magnitude = sum(x * x for x in base) ** 0.5
            return [x / magnitude for x in base]

        with patch("cohere.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            # Mock embed endpoint
            async def mock_embed(texts, model, input_type, embedding_types):
                return MagicMock(
                    embeddings=MagicMock(float_=[generate_embedding(t) for t in texts])
                )

            mock_client.embed = AsyncMock(side_effect=mock_embed)

            # Mock chat endpoint (returns formatted recommendation)
            async def mock_chat(model, messages, temperature, max_tokens):
                # Return realistic treatment recommendation
                response = """
Recommendation 1:
Title: Manual Therapy + Home Exercises
Description: Apply manual therapy to upper trapezius trigger points using sustained pressure (30-60 seconds). Prescribe home exercises: gentle neck stretches (3x daily) and postural corrections. Ice for 15 minutes post-treatment.

Recommendation 2:
Title: Progressive Muscle Relaxation
Description: Teach progressive muscle relaxation techniques targeting neck and shoulder muscles. Practice 10-15 minutes daily before bed to reduce tension.
"""
                return MagicMock(message=MagicMock(content=[MagicMock(text=response)]))

            mock_client.chat = AsyncMock(side_effect=mock_chat)

            yield mock_client

    @pytest_asyncio.fixture
    async def massage_clinical_data(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
        mock_cohere_recommendations,
    ) -> tuple[Client, list[Session]]:
        """Create realistic massage therapy clinical data."""
        # Create client
        client = Client(
            workspace_id=workspace_1.id,
            first_name="Sarah",
            last_name="Johnson",
            phone="555-0123",
        )
        db_session.add(client)
        await db_session.flush()

        # Create past sessions with SOAP notes
        sessions = []
        for i in range(3):
            session = Session(
                workspace_id=workspace_1.id,
                client_id=client.id,
                session_date=datetime(2025, 11, 1 + i, 10, 0, tzinfo=UTC),
                subjective="Patient reports upper trapezius tension, 7/10 pain",
                objective="Palpation reveals trigger points in upper trap, limited ROM",
                assessment="Myofascial pain syndrome, upper trapezius",
                plan="Manual therapy, ice therapy, home exercises",
            )
            db_session.add(session)
            sessions.append(session)

        await db_session.commit()
        await db_session.refresh(client)

        return client, sessions

    async def test_recommend_treatment_plan_massage(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
        massage_clinical_data: tuple[Client, list[Session]],
        mock_cohere_recommendations,
    ):
        """Should generate treatment recommendations for massage therapy."""
        client, sessions = massage_clinical_data
        agent = get_clinical_agent(db_session)

        response = await agent.recommend_treatment_plan(
            workspace_id=workspace_1.id,
            subjective="Patient reports severe muscle tension in upper back",
            objective="Trigger points palpated in upper trapezius and rhomboids",
            assessment="Myofascial pain syndrome with muscle tension",
            client_id=client.id,
        )

        # Verify response structure
        assert len(response.recommendations) >= 1  # At least 1 recommendation
        assert len(response.recommendations) <= 2  # At most 2 recommendations
        assert response.therapy_type == "massage"
        assert response.language in ["he", "en"]
        assert response.retrieved_count >= 0
        assert response.processing_time_ms > 0

        # Verify recommendation details
        rec1 = response.recommendations[0]
        assert len(rec1.title) > 0  # Has a title
        assert len(rec1.description) > 0  # Has a description
        assert rec1.therapy_type == "massage"
        assert rec1.evidence_type in [
            "workspace_patterns",
            "clinical_guidelines",
            "hybrid",
        ]

    async def test_recommend_treatment_plan_without_client_context(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
        mock_cohere_recommendations,
    ):
        """Should generate recommendations without patient history (clinical guidelines only)."""
        agent = get_clinical_agent(db_session)

        response = await agent.recommend_treatment_plan(
            workspace_id=workspace_1.id,
            subjective="Patient reports anxiety about upcoming exam",
            objective="Elevated heart rate, tense posture, rapid speech",
            assessment="Situational anxiety, stress management needed",
            client_id=None,  # No patient context
        )

        # Should still generate recommendations (LLM clinical knowledge)
        assert len(response.recommendations) >= 1
        assert len(response.recommendations) <= 2
        assert response.therapy_type == "psychotherapy"
        assert response.retrieved_count == 0  # No patient context retrieved
        # Verify all recommendations have clinical_guidelines evidence (no patient context)
        for rec in response.recommendations:
            assert rec.evidence_type == "clinical_guidelines"

    async def test_recommend_treatment_plan_detects_hebrew(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
        mock_cohere_recommendations,
    ):
        """Should detect Hebrew language in SOAP inputs."""
        agent = get_clinical_agent(db_session)

        response = await agent.recommend_treatment_plan(
            workspace_id=workspace_1.id,
            subjective="המטופל מדווח על כאבי גב תחתון",
            objective="מגבלה בטווח תנועה",
            assessment="תסמונת כאב מיופשיאלית",
            client_id=None,
        )

        # Should detect Hebrew
        assert response.language == "he"

    async def test_recommend_treatment_plan_workspace_isolation(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
        workspace_2: Workspace,
        massage_clinical_data: tuple[Client, list[Session]],
        mock_cohere_recommendations,
    ):
        """Should enforce workspace isolation (no cross-workspace data leakage)."""
        client, sessions = massage_clinical_data
        agent = get_clinical_agent(db_session)

        # Query with workspace_2 should NOT retrieve workspace_1's sessions
        response = await agent.recommend_treatment_plan(
            workspace_id=workspace_2.id,  # Different workspace!
            subjective="Patient reports muscle tension",
            objective="Trigger points palpated",
            assessment="Myofascial pain syndrome",
            client_id=client.id,  # Client belongs to workspace_1
        )

        # Should generate recommendations but with 0 retrieved context
        # (workspace isolation prevents accessing workspace_1's data)
        assert response.retrieved_count == 0
        # Verify all recommendations have clinical_guidelines evidence (no patient context due to workspace isolation)
        for rec in response.recommendations:
            assert rec.evidence_type == "clinical_guidelines"


class TestPromptIntegration:
    """Test therapy-specific prompt selection."""

    @pytest.mark.asyncio
    async def test_massage_prompt_selection(self):
        """Should use massage-specific prompt for massage therapy."""
        from pazpaz.ai.prompts import get_treatment_prompt

        prompt = get_treatment_prompt("massage")

        assert "massage" in prompt.lower()
        assert "trigger points" in prompt.lower()
        assert "myofascial" in prompt.lower()

    @pytest.mark.asyncio
    async def test_physiotherapy_prompt_selection(self):
        """Should use physiotherapy-specific prompt."""
        from pazpaz.ai.prompts import get_treatment_prompt

        prompt = get_treatment_prompt("physiotherapy")

        assert "physiotherapy" in prompt.lower()
        assert "range of motion" in prompt.lower() or "rom" in prompt.lower()
        assert "exercise" in prompt.lower()

    @pytest.mark.asyncio
    async def test_psychotherapy_prompt_selection(self):
        """Should use psychotherapy-specific prompt."""
        from pazpaz.ai.prompts import get_treatment_prompt

        prompt = get_treatment_prompt("psychotherapy")

        assert "psychotherapy" in prompt.lower()
        assert "cbt" in prompt.lower() or "cognitive" in prompt.lower()

    @pytest.mark.asyncio
    async def test_generic_fallback_prompt(self):
        """Should use generic prompt for unknown therapy types."""
        from pazpaz.ai.prompts import get_treatment_prompt

        prompt = get_treatment_prompt("unknown_therapy_type")

        # Should default to generic
        assert "clinical treatment planning" in prompt.lower()
