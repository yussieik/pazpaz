"""Tests for Session search functionality."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.audit_event import AuditAction, AuditEvent
from pazpaz.models.session import Session


class TestSessionSearch:
    """Test session search API endpoint."""

    async def test_search_in_subjective_field(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
    ):
        """Search finds sessions by subjective content."""
        # Create session with specific subjective content
        session = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=1),
            subjective="Patient reports shoulder pain in right arm",
            objective="ROM testing performed",
            assessment="Rotator cuff strain",
            plan="Physical therapy twice weekly",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )
        db_session.add(session)
        await db_session.commit()

        # Search for term in subjective
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "shoulder pain",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(session.id)
        assert "shoulder pain" in data["items"][0]["subjective"]

    async def test_search_in_objective_field(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
    ):
        """Search finds sessions by objective content."""
        session = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=1),
            subjective="Patient complaints",
            objective="Limited ROM 45 degrees shoulder abduction",
            assessment="Joint stiffness",
            plan="Continue treatment",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )
        db_session.add(session)
        await db_session.commit()

        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "shoulder abduction",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert "shoulder abduction" in data["items"][0]["objective"]

    async def test_search_in_assessment_field(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
    ):
        """Search finds sessions by assessment content."""
        session = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=1),
            subjective="Pain reported",
            objective="Examination performed",
            assessment="Diagnosed with rotator cuff tendinitis",
            plan="Rest and ice",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )
        db_session.add(session)
        await db_session.commit()

        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "rotator cuff",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert "rotator cuff" in data["items"][0]["assessment"]

    async def test_search_in_plan_field(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
    ):
        """Search finds sessions by plan content."""
        session = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=1),
            subjective="Pain continues",
            objective="Swelling observed",
            assessment="Inflammation present",
            plan="Continue physical therapy exercises three times per week",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )
        db_session.add(session)
        await db_session.commit()

        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "physical therapy",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert "physical therapy" in data["items"][0]["plan"]

    async def test_search_case_insensitive(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
    ):
        """Search is case-insensitive."""
        session = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=1),
            subjective="Patient reports shoulder pain",
            objective="Examination done",
            assessment="Diagnosis",
            plan="Treatment",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )
        db_session.add(session)
        await db_session.commit()

        # Search with uppercase
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "SHOULDER PAIN",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1

        # Search with mixed case
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "ShOuLdEr PaIn",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1

    async def test_search_partial_match(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
    ):
        """Search matches partial strings."""
        session = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=1),
            subjective="Patient reports left shoulder pain continued from last week",
            objective="Testing",
            assessment="Diagnosis",
            plan="Treatment",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )
        db_session.add(session)
        await db_session.commit()

        # Search with partial term
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "should",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1

        # Search with substring
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "pain contin",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1

    async def test_search_returns_multiple_matches(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
    ):
        """Search returns all matching sessions."""
        # Create 3 sessions with "shoulder", 2 without
        session1 = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=5),
            subjective="Right shoulder pain",
            objective="Exam",
            assessment="Diagnosis",
            plan="Treatment",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )
        session2 = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=4),
            subjective="Left shoulder pain",
            objective="Exam",
            assessment="Diagnosis",
            plan="Treatment",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )
        session3 = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=3),
            subjective="Knee pain reported",
            objective="Exam",
            assessment="Diagnosis",
            plan="Treatment",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )
        session4 = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=2),
            subjective="Back pain",
            objective="Exam",
            assessment="Diagnosis",
            plan="Treatment",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )
        session5 = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=1),
            subjective="General discomfort",
            objective="Shoulder ROM limited",
            assessment="Diagnosis",
            plan="Treatment",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )

        db_session.add_all([session1, session2, session3, session4, session5])
        await db_session.commit()

        # Search "shoulder" returns 3 sessions
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "shoulder",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

        # Verify correct sessions returned (sorted by session_date desc)
        returned_ids = {item["id"] for item in data["items"]}
        expected_ids = {str(session1.id), str(session2.id), str(session5.id)}
        assert returned_ids == expected_ids

    async def test_search_with_pagination(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
    ):
        """Search works with pagination."""
        # Create 25 sessions with "pain"
        sessions = []
        for i in range(25):
            session = Session(
                workspace_id=test_workspace.id,
                client_id=test_client.id,
                created_by_user_id=test_user.id,
                session_date=datetime.now(UTC) - timedelta(days=i),
                subjective=f"Patient reports pain in session {i}",
                objective="Exam",
                assessment="Diagnosis",
                plan="Treatment",
                is_draft=False,
                finalized_at=datetime.now(UTC),
            )
            sessions.append(session)

        db_session.add_all(sessions)
        await db_session.commit()

        # Search "pain" with page_size=10
        # Page 1 has 10 items
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "pain",
                "page": 1,
                "page_size": 10,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 25
        assert len(data["items"]) == 10
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert data["total_pages"] == 3

        # Page 2 has 10 items
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "pain",
                "page": 2,
                "page_size": 10,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 25
        assert len(data["items"]) == 10
        assert data["page"] == 2

        # Page 3 has 5 items
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "pain",
                "page": 3,
                "page_size": 10,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 25
        assert len(data["items"]) == 5
        assert data["page"] == 3

    async def test_search_respects_client_filter(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        sample_client_ws1,
        test_user,
    ):
        """Search only searches within specified client."""
        # Create another client
        from pazpaz.models.client import Client

        client_a = sample_client_ws1
        client_b = Client(
            workspace_id=test_workspace.id,
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            consent_status=True,
        )
        db_session.add(client_b)
        await db_session.commit()

        # Create sessions for both clients with "pain"
        session_a = Session(
            workspace_id=test_workspace.id,
            client_id=client_a.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=1),
            subjective="Client A has pain",
            objective="Exam",
            assessment="Diagnosis",
            plan="Treatment",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )
        session_b = Session(
            workspace_id=test_workspace.id,
            client_id=client_b.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=1),
            subjective="Client B has pain",
            objective="Exam",
            assessment="Diagnosis",
            plan="Treatment",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )

        db_session.add_all([session_a, session_b])
        await db_session.commit()

        # Search client A for "pain"
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(client_a.id),
                "search": "pain",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(session_a.id)
        assert "Client A" in data["items"][0]["subjective"]

    async def test_search_respects_workspace_isolation(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_workspace2,
        sample_client_ws1,
        sample_client_ws2,
        test_user,
        test_user2,
    ):
        """Search only searches within user's workspace."""
        # Create sessions in workspace 1 and workspace 2
        session_ws1 = Session(
            workspace_id=test_workspace.id,
            client_id=sample_client_ws1.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=1),
            subjective="Workspace 1 pain report",
            objective="Exam",
            assessment="Diagnosis",
            plan="Treatment",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )
        session_ws2 = Session(
            workspace_id=test_workspace2.id,
            client_id=sample_client_ws2.id,
            created_by_user_id=test_user2.id,
            session_date=datetime.now(UTC) - timedelta(days=1),
            subjective="Workspace 2 pain report",
            objective="Exam",
            assessment="Diagnosis",
            plan="Treatment",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )

        db_session.add_all([session_ws1, session_ws2])
        await db_session.commit()

        # User 1 searches "pain" - should only see workspace 1 sessions
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(sample_client_ws1.id),
                "search": "pain",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(session_ws1.id)
        assert "Workspace 1" in data["items"][0]["subjective"]

    async def test_search_respects_is_draft_filter(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
    ):
        """Search works with is_draft filter."""
        # Create draft and finalized sessions with "pain"
        draft_session = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=2),
            subjective="Draft session with pain",
            objective="Exam",
            assessment="Diagnosis",
            plan="Treatment",
            is_draft=True,
        )
        finalized_session = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=1),
            subjective="Finalized session with pain",
            objective="Exam",
            assessment="Diagnosis",
            plan="Treatment",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )

        db_session.add_all([draft_session, finalized_session])
        await db_session.commit()

        # Search "pain" with is_draft=true
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "pain",
                "is_draft": True,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(draft_session.id)
        assert data["items"][0]["is_draft"] is True

        # Search "pain" with is_draft=false
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "pain",
                "is_draft": False,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(finalized_session.id)
        assert data["items"][0]["is_draft"] is False

    async def test_search_no_results(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
    ):
        """Search returns empty list when no matches."""
        # Create sessions without "xyz123"
        session = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=1),
            subjective="Patient reports shoulder pain",
            objective="Exam",
            assessment="Diagnosis",
            plan="Treatment",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )
        db_session.add(session)
        await db_session.commit()

        # Search "xyz123"
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "xyz123",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["total_pages"] == 0

    async def test_search_empty_string_behaves_normally(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
    ):
        """Empty/whitespace search string returns validation error."""
        # Create a session
        session = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=1),
            subjective="Patient reports pain",
            objective="Exam",
            assessment="Diagnosis",
            plan="Treatment",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )
        db_session.add(session)
        await db_session.commit()

        # Search with empty string should fail validation (min_length=1)
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "",
            },
        )

        # FastAPI validation should reject empty string
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_search_special_characters_escaped(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
    ):
        """Search handles special characters safely."""
        # Create session with special characters
        session = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=1),
            subjective="Patient reports 50% improvement in pain & stiffness",
            objective="ROM improved",
            assessment="Progress noted",
            plan="Continue treatment",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )
        db_session.add(session)
        await db_session.commit()

        # Search with special characters
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "pain & stiffness",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1

        # Search with percentage
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "50% improvement",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1

    async def test_search_very_long_query(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
    ):
        """Search handles max length queries."""
        # Create session
        long_text = "a" * 200
        session = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=1),
            subjective=f"Patient reports {long_text}",
            objective="Exam",
            assessment="Diagnosis",
            plan="Treatment",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )
        db_session.add(session)
        await db_session.commit()

        # Search with 200 character string (max allowed)
        search_query = "a" * 200
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": search_query,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1

    async def test_search_query_too_long_rejected(
        self,
        authenticated_client: AsyncClient,
        test_client,
    ):
        """Search rejects queries over max length."""
        # Search with 201 character string (exceeds max)
        search_query = "a" * 201
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": search_query,
            },
        )

        # Should return 422 validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_search_audit_logged(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
    ):
        """Search queries are audit logged."""
        # Create session
        session = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(days=1),
            subjective="Patient reports shoulder pain",
            objective="Exam",
            assessment="Diagnosis",
            plan="Treatment",
            is_draft=False,
            finalized_at=datetime.now(UTC),
        )
        db_session.add(session)
        await db_session.commit()

        # Perform search
        search_query = "shoulder pain"
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": search_query,
            },
        )

        assert response.status_code == status.HTTP_200_OK

        # Query AuditEvent table
        result = await db_session.execute(
            select(AuditEvent)
            .where(AuditEvent.workspace_id == test_workspace.id)
            .where(AuditEvent.user_id == test_user.id)
            .where(AuditEvent.resource_type == "Session")
            .where(AuditEvent.action == AuditAction.READ)
        )
        audit_events = result.scalars().all()

        # Find audit event with search action
        search_audit = None
        for event in audit_events:
            if (
                event.event_metadata
                and event.event_metadata.get("action") == "search"
            ):
                search_audit = event
                break

        assert search_audit is not None, "Search audit event not found"
        assert search_audit.event_metadata["search_query"] == search_query
        assert search_audit.event_metadata["client_id"] == str(test_client.id)
        assert search_audit.event_metadata["results_count"] == 1
        assert search_audit.event_metadata["sessions_scanned"] >= 1

    async def test_search_performance_100_sessions(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
    ):
        """Search completes within performance budget for 100 sessions."""
        # Create 100 sessions
        sessions = []
        for i in range(100):
            session = Session(
                workspace_id=test_workspace.id,
                client_id=test_client.id,
                created_by_user_id=test_user.id,
                session_date=datetime.now(UTC) - timedelta(days=i),
                subjective=f"Session {i} patient reports various symptoms",
                objective=f"Examination {i} performed",
                assessment=f"Assessment {i} completed",
                plan=f"Treatment plan {i}",
                is_draft=False,
                finalized_at=datetime.now(UTC),
            )
            sessions.append(session)

        # Add some with "shoulder" for matching
        for i in range(10):
            sessions[i].subjective = (
                f"Session {i} patient reports shoulder pain"
            )

        db_session.add_all(sessions)
        await db_session.commit()

        # Measure search time
        start_time = time.time()
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "shoulder",
            },
        )
        elapsed_ms = (time.time() - start_time) * 1000

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 10

        # Performance target: <150ms for 100 sessions
        # Note: This may be relaxed in CI due to slower hardware
        assert elapsed_ms < 500, f"Search took {elapsed_ms:.2f}ms (expected <500ms)"

    async def test_search_performance_500_sessions(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
    ):
        """Search completes within budget for 500 sessions."""
        # Create 500 sessions
        sessions = []
        for i in range(500):
            session = Session(
                workspace_id=test_workspace.id,
                client_id=test_client.id,
                created_by_user_id=test_user.id,
                session_date=datetime.now(UTC) - timedelta(days=i),
                subjective=f"Session {i} patient reports various symptoms",
                objective=f"Examination {i} performed",
                assessment=f"Assessment {i} completed",
                plan=f"Treatment plan {i}",
                is_draft=False,
                finalized_at=datetime.now(UTC),
            )
            sessions.append(session)

        # Add some with "shoulder" for matching
        for i in range(50):
            sessions[i].subjective = (
                f"Session {i} patient reports shoulder pain"
            )

        db_session.add_all(sessions)
        await db_session.commit()

        # Measure search time
        start_time = time.time()
        response = await authenticated_client.get(
            "/api/v1/sessions",
            params={
                "client_id": str(test_client.id),
                "search": "shoulder",
            },
        )
        elapsed_ms = (time.time() - start_time) * 1000

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 50

        # Performance target: <500ms for 500 sessions (relaxed for large dataset)
        # This is acceptable as it's O(n) in-memory filtering
        assert (
            elapsed_ms < 1000
        ), f"Search took {elapsed_ms:.2f}ms (expected <1000ms)"
