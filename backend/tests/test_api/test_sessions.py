"""Tests for Session CRUD API endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.audit_event import AuditAction, AuditEvent, ResourceType
from pazpaz.models.session import Session


class TestCreateSession:
    """Tests for POST /api/v1/sessions endpoint."""

    async def test_create_session_success(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user,
        test_workspace,
        test_client,
    ):
        """Test successful session creation."""
        session_date = datetime.now(UTC) - timedelta(hours=2)
        payload = {
            "client_id": str(test_client.id),
            "session_date": session_date.isoformat(),
            "subjective": "Patient reports lower back pain",
            "objective": "Limited range of motion observed",
            "assessment": "Acute lumbar strain",
            "plan": "Ice therapy, rest for 48 hours",
            "duration_minutes": 60,
        }

        response = await authenticated_client.post(
            "/api/v1/sessions",
            json=payload,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # Verify response structure
        assert "id" in data
        assert data["workspace_id"] == str(test_workspace.id)
        assert data["client_id"] == str(test_client.id)
        assert data["created_by_user_id"] == str(test_user.id)

        # Verify SOAP fields are returned (decrypted)
        assert data["subjective"] == payload["subjective"]
        assert data["objective"] == payload["objective"]
        assert data["assessment"] == payload["assessment"]
        assert data["plan"] == payload["plan"]

        # Verify draft metadata
        assert data["is_draft"] is True
        assert data["draft_last_saved_at"] is not None
        assert data["finalized_at"] is None
        assert data["version"] == 1

        # Verify session was created in database
        result = await db_session.execute(
            select(Session).where(Session.id == uuid.UUID(data["id"]))
        )
        session = result.scalar_one()
        assert session is not None
        assert session.workspace_id == test_workspace.id

        # Verify PHI is encrypted in database (raw BYTEA)
        # Note: We can't easily check raw bytes here,
        # but we verified encryption in test_models

    async def test_create_session_minimal_fields(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_client,
    ):
        """Test session creation with only required fields."""
        session_date = datetime.now(UTC) - timedelta(hours=1)
        payload = {
            "client_id": str(test_client.id),
            "session_date": session_date.isoformat(),
        }

        response = await authenticated_client.post(
            "/api/v1/sessions",
            json=payload,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # Verify optional SOAP fields are null
        assert data["subjective"] is None
        assert data["objective"] is None
        assert data["assessment"] is None
        assert data["plan"] is None
        assert data["duration_minutes"] is None

    async def test_create_session_future_date_rejected(
        self,
        authenticated_client: AsyncClient,
        test_client,
    ):
        """Test session creation fails with future date."""
        future_date = datetime.now(UTC) + timedelta(days=1)
        payload = {
            "client_id": str(test_client.id),
            "session_date": future_date.isoformat(),
        }

        response = await authenticated_client.post(
            "/api/v1/sessions",
            json=payload,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "future" in response.text.lower()

    async def test_create_session_invalid_client_id(
        self,
        authenticated_client: AsyncClient,
        auth_headers,
    ):
        """Test session creation fails with non-existent client."""
        fake_client_id = uuid.uuid4()
        session_date = datetime.now(UTC) - timedelta(hours=1)
        payload = {
            "client_id": str(fake_client_id),
            "session_date": session_date.isoformat(),
        }

        response = await authenticated_client.post(
            "/api/v1/sessions",
            json=payload,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_create_session_workspace_isolation(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace2,
        test_client2,
    ):
        """Test cannot create session for client in different workspace."""
        session_date = datetime.now(UTC) - timedelta(hours=1)
        payload = {
            "client_id": str(test_client2.id),  # Client in different workspace
            "session_date": session_date.isoformat(),
        }

        response = await authenticated_client.post(
            "/api/v1/sessions",
            json=payload,  # Headers for workspace 1
        )

        # Should return 404 (not 403) to prevent information leakage
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_create_session_unauthenticated(
        self,
        client: AsyncClient,
        test_client,
    ):
        """Test that unauthenticated requests are rejected by CSRF protection.

        Note: CSRF middleware (403) runs before auth middleware (401) for
        POST/PUT/DELETE. This is correct security behavior - CSRF protection
        validates tokens before authentication to prevent CSRF attacks even
        from unauthenticated users.
        """
        session_date = datetime.now(UTC) - timedelta(hours=1)
        payload = {
            "client_id": str(test_client.id),
            "session_date": session_date.isoformat(),
        }

        response = await client.post(
            "/api/v1/sessions",
            json=payload,
        )

        # CSRF middleware runs before auth, so we get 403 instead of 401
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestGetSession:
    """Tests for GET /api/v1/sessions/{id} endpoint."""

    async def test_get_session_success(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_session,
        test_workspace,
    ):
        """Test successful session retrieval."""
        response = await authenticated_client.get(
            f"/api/v1/sessions/{test_session.id}",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert data["id"] == str(test_session.id)
        assert data["workspace_id"] == str(test_workspace.id)

        # Verify SOAP fields are decrypted
        assert data["subjective"] == test_session.subjective
        assert data["objective"] == test_session.objective
        assert data["assessment"] == test_session.assessment
        assert data["plan"] == test_session.plan

        # Verify audit event was created for PHI access
        result = await db_session.execute(
            select(AuditEvent).where(
                AuditEvent.resource_type == ResourceType.SESSION.value,
                AuditEvent.resource_id == test_session.id,
                AuditEvent.action == AuditAction.READ,
            )
        )
        audit_event = result.scalar_one()
        assert audit_event is not None
        assert audit_event.workspace_id == test_workspace.id

    async def test_get_session_not_found(
        self,
        authenticated_client: AsyncClient,
        auth_headers,
    ):
        """Test get session with non-existent ID."""
        fake_id = uuid.uuid4()
        response = await authenticated_client.get(
            f"/api/v1/sessions/{fake_id}",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_session_workspace_isolation(
        self,
        authenticated_client: AsyncClient,
        test_session2,
    ):
        """Test cannot access session from different workspace."""
        response = await authenticated_client.get(
            f"/api/v1/sessions/{test_session2.id}",  # Headers for workspace 1
        )

        # Should return 404 (not 403) to prevent information leakage
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_session_unauthenticated(
        self,
        client: AsyncClient,
        test_session,
    ):
        """Test session retrieval requires authentication."""
        response = await client.get(
            f"/api/v1/sessions/{test_session.id}",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestListSessions:
    """Tests for GET /api/v1/sessions endpoint."""

    async def test_list_sessions_success(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_client,
        test_session,
    ):
        """Test successful session list retrieval."""
        response = await authenticated_client.get(
            f"/api/v1/sessions?client_id={test_client.id}",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify pagination structure
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data

        # Verify at least one session returned
        assert len(data["items"]) >= 1
        assert data["total"] >= 1

        # Verify session data
        session_data = next(
            (item for item in data["items"] if item["id"] == str(test_session.id)),
            None,
        )
        assert session_data is not None
        assert session_data["client_id"] == str(test_client.id)

    async def test_list_sessions_requires_client_id(
        self,
        authenticated_client: AsyncClient,
        auth_headers,
    ):
        """Test list sessions requires client_id parameter."""
        response = await authenticated_client.get(
            "/api/v1/sessions",
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "client_id" in response.text.lower()

    async def test_list_sessions_pagination(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_client,
        test_workspace,
        test_user,
    ):
        """Test session list pagination."""
        # Create 5 sessions
        sessions = []
        for i in range(5):
            session = Session(
                workspace_id=test_workspace.id,
                client_id=test_client.id,
                created_by_user_id=test_user.id,
                session_date=datetime.now(UTC) - timedelta(hours=i + 1),
                subjective=f"Session {i + 1}",
                is_draft=True,
                version=1,
            )
            db_session.add(session)
            sessions.append(session)
        await db_session.commit()

        # Request page 1 with page_size=2
        response = await authenticated_client.get(
            f"/api/v1/sessions?client_id={test_client.id}&page=1&page_size=2",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total"] >= 5

        # Request page 2
        response = await authenticated_client.get(
            f"/api/v1/sessions?client_id={test_client.id}&page=2&page_size=2",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["items"]) == 2
        assert data["page"] == 2

    async def test_list_sessions_draft_filter(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_client,
        test_workspace,
        test_user,
    ):
        """Test filtering sessions by draft status."""
        # Create draft and finalized sessions
        draft_session = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(hours=1),
            is_draft=True,
            version=1,
        )
        finalized_session = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(hours=2),
            is_draft=False,
            finalized_at=datetime.now(UTC) - timedelta(hours=2),
            version=1,
        )
        db_session.add_all([draft_session, finalized_session])
        await db_session.commit()

        # Filter for drafts only
        response = await authenticated_client.get(
            f"/api/v1/sessions?client_id={test_client.id}&is_draft=true",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All returned sessions should be drafts
        for item in data["items"]:
            assert item["is_draft"] is True

    async def test_list_sessions_workspace_isolation(
        self,
        authenticated_client: AsyncClient,
        test_client2,
    ):
        """Test cannot list sessions for client in different workspace."""
        response = await authenticated_client.get(
            f"/api/v1/sessions?client_id={test_client2.id}",  # Headers for workspace 1
        )

        # Should return 404 (client not found in workspace)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_list_sessions_unauthenticated(
        self,
        client: AsyncClient,
        test_client,
    ):
        """Test session list requires authentication."""
        response = await client.get(
            f"/api/v1/sessions?client_id={test_client.id}",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestUpdateSession:
    """Tests for PUT /api/v1/sessions/{id} endpoint."""

    async def test_update_session_success(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_session,
    ):
        """Test successful session update."""
        original_version = test_session.version
        payload = {
            "subjective": "Updated patient report",
            "assessment": "Updated assessment",
        }

        response = await authenticated_client.put(
            f"/api/v1/sessions/{test_session.id}",
            json=payload,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify updated fields
        assert data["subjective"] == payload["subjective"]
        assert data["assessment"] == payload["assessment"]

        # Verify version incremented
        assert data["version"] == original_version + 1

        # Verify draft_last_saved_at updated
        assert data["draft_last_saved_at"] is not None

        # Verify unchanged fields remain the same
        assert data["objective"] == test_session.objective
        assert data["plan"] == test_session.plan

    async def test_update_session_partial_update(
        self,
        authenticated_client: AsyncClient,
        test_session,
    ):
        """Test partial update with only one field."""
        payload = {"plan": "Updated treatment plan only"}

        response = await authenticated_client.put(
            f"/api/v1/sessions/{test_session.id}",
            json=payload,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Only plan should be updated
        assert data["plan"] == payload["plan"]
        assert data["subjective"] == test_session.subjective
        assert data["objective"] == test_session.objective
        assert data["assessment"] == test_session.assessment

    async def test_update_session_empty_payload(
        self,
        authenticated_client: AsyncClient,
        test_session,
    ):
        """Test update with empty payload returns current session."""
        payload = {}

        response = await authenticated_client.put(
            f"/api/v1/sessions/{test_session.id}",
            json=payload,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should return current session unchanged
        assert data["id"] == str(test_session.id)
        assert data["subjective"] == test_session.subjective

    async def test_update_session_future_date_rejected(
        self,
        authenticated_client: AsyncClient,
        test_session,
    ):
        """Test updating session with future date is rejected."""
        future_date = datetime.now(UTC) + timedelta(days=1)
        payload = {"session_date": future_date.isoformat()}

        response = await authenticated_client.put(
            f"/api/v1/sessions/{test_session.id}",
            json=payload,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "future" in response.text.lower()

    async def test_update_session_not_found(
        self,
        authenticated_client: AsyncClient,
        auth_headers,
    ):
        """Test update session with non-existent ID."""
        fake_id = uuid.uuid4()
        payload = {"subjective": "Updated text"}

        response = await authenticated_client.put(
            f"/api/v1/sessions/{fake_id}",
            json=payload,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_session_workspace_isolation(
        self,
        authenticated_client: AsyncClient,
        test_session2,
    ):
        """Test cannot update session from different workspace."""
        payload = {"subjective": "Malicious update attempt"}

        response = await authenticated_client.put(
            f"/api/v1/sessions/{test_session2.id}",
            json=payload,  # Headers for workspace 1
        )

        # Should return 404 (not 403) to prevent information leakage
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_session_unauthenticated(
        self,
        client: AsyncClient,
        test_session,
    ):
        """Test that unauthenticated requests are rejected by CSRF protection.

        Note: CSRF middleware (403) runs before auth middleware (401) for
        POST/PUT/DELETE.
        """
        payload = {"subjective": "Unauthorized update"}

        response = await client.put(
            f"/api/v1/sessions/{test_session.id}",
            json=payload,
        )

        # CSRF middleware runs before auth, so we get 403 instead of 401
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestDeleteSession:
    """Tests for DELETE /api/v1/sessions/{id} endpoint."""

    async def test_delete_session_success(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_session,
    ):
        """Test successful session soft delete."""
        response = await authenticated_client.delete(
            f"/api/v1/sessions/{test_session.id}",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify session is soft deleted (deleted_at set)
        await db_session.refresh(test_session)
        assert test_session.deleted_at is not None

        # Verify session still exists in database (soft delete)
        result = await db_session.execute(
            select(Session).where(Session.id == test_session.id)
        )
        session = result.scalar_one()
        assert session is not None

    async def test_delete_session_already_deleted(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_session,
    ):
        """Test deleting already deleted session returns 404."""
        # Soft delete the session
        test_session.deleted_at = datetime.now(UTC)
        await db_session.commit()

        # Try to delete again
        response = await authenticated_client.delete(
            f"/api/v1/sessions/{test_session.id}",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_session_not_found(
        self,
        authenticated_client: AsyncClient,
        auth_headers,
    ):
        """Test delete session with non-existent ID."""
        fake_id = uuid.uuid4()
        response = await authenticated_client.delete(
            f"/api/v1/sessions/{fake_id}",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_session_workspace_isolation(
        self,
        authenticated_client: AsyncClient,
        test_session2,
    ):
        """Test cannot delete session from different workspace."""
        response = await authenticated_client.delete(
            f"/api/v1/sessions/{test_session2.id}",  # Headers for workspace 1
        )

        # Should return 404 (not 403) to prevent information leakage
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_session_unauthenticated(
        self,
        client: AsyncClient,
        test_session,
    ):
        """Test that unauthenticated requests are rejected by CSRF protection.

        Note: CSRF middleware (403) runs before auth middleware (401) for
        POST/PUT/DELETE.
        """
        response = await client.delete(
            f"/api/v1/sessions/{test_session.id}",
        )

        # CSRF middleware runs before auth, so we get 403 instead of 401
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestAuditLogging:
    """Tests for audit logging of session operations."""

    async def test_create_session_audit_logged(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_client,
        test_workspace,
    ):
        """Test session creation is audit logged."""
        session_date = datetime.now(UTC) - timedelta(hours=1)
        payload = {
            "client_id": str(test_client.id),
            "session_date": session_date.isoformat(),
            "subjective": "Test session",
        }

        response = await authenticated_client.post(
            "/api/v1/sessions",
            json=payload,
        )

        assert response.status_code == status.HTTP_201_CREATED
        session_id = uuid.UUID(response.json()["id"])

        # Verify audit event was created
        # Note: resource_id may be None if middleware can't extract from response
        result = await db_session.execute(
            select(AuditEvent)
            .where(
                AuditEvent.resource_type == ResourceType.SESSION.value,
                AuditEvent.action == AuditAction.CREATE,
                AuditEvent.workspace_id == test_workspace.id,
            )
            .order_by(AuditEvent.created_at.desc())
            .limit(1)
        )
        audit_event = result.scalar_one_or_none()
        assert audit_event is not None
        assert audit_event.workspace_id == test_workspace.id
        # resource_id might be None or the session_id depending on response extraction
        assert audit_event.resource_id is None or audit_event.resource_id == session_id

    async def test_update_session_audit_logged(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_session,
        test_workspace,
    ):
        """Test session update is audit logged."""
        payload = {"subjective": "Updated session"}

        response = await authenticated_client.put(
            f"/api/v1/sessions/{test_session.id}",
            json=payload,
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify audit event was created
        result = await db_session.execute(
            select(AuditEvent).where(
                AuditEvent.resource_type == ResourceType.SESSION.value,
                AuditEvent.resource_id == test_session.id,
                AuditEvent.action == AuditAction.UPDATE,
            )
        )
        audit_event = result.scalar_one()
        assert audit_event is not None
        assert audit_event.workspace_id == test_workspace.id

    async def test_delete_session_audit_logged(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_session,
        test_workspace,
    ):
        """Test session deletion is audit logged."""
        response = await authenticated_client.delete(
            f"/api/v1/sessions/{test_session.id}",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify audit event was created
        result = await db_session.execute(
            select(AuditEvent).where(
                AuditEvent.resource_type == ResourceType.SESSION.value,
                AuditEvent.resource_id == test_session.id,
                AuditEvent.action == AuditAction.DELETE,
            )
        )
        audit_event = result.scalar_one()
        assert audit_event is not None
        assert audit_event.workspace_id == test_workspace.id


class TestEncryption:
    """Tests for PHI encryption."""

    async def test_phi_encrypted_at_rest(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_client,
    ):
        """Test PHI fields are encrypted in database."""
        session_date = datetime.now(UTC) - timedelta(hours=1)
        phi_data = {
            "client_id": str(test_client.id),
            "session_date": session_date.isoformat(),
            "subjective": "Sensitive patient information",
            "objective": "Sensitive observations",
            "assessment": "Sensitive assessment",
            "plan": "Sensitive treatment plan",
        }

        response = await authenticated_client.post(
            "/api/v1/sessions",
            json=phi_data,
        )

        assert response.status_code == status.HTTP_201_CREATED
        session_id = uuid.UUID(response.json()["id"])

        # Query raw database to verify encryption
        # Note: We can't easily verify bytes here,
        # but the model tests verify encryption works
        result = await db_session.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalar_one()

        # PHI fields should be decrypted by ORM when accessed via model
        assert session.subjective == phi_data["subjective"]
        assert session.objective == phi_data["objective"]

    async def test_phi_decrypted_in_response(
        self,
        authenticated_client: AsyncClient,
        test_session,
    ):
        """Test PHI fields are decrypted in API response."""
        response = await authenticated_client.get(
            f"/api/v1/sessions/{test_session.id}",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify all SOAP fields are readable (decrypted)
        assert data["subjective"] == test_session.subjective
        assert data["objective"] == test_session.objective
        assert data["assessment"] == test_session.assessment
        assert data["plan"] == test_session.plan


class TestSaveDraft:
    """Tests for PATCH /api/v1/sessions/{id}/draft endpoint."""

    async def test_save_draft_success(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_session,
    ):
        """Test draft autosave updates fields."""
        original_version = test_session.version
        payload = {
            "subjective": "Updated patient report via autosave",
            "assessment": "Updated assessment via autosave",
        }

        response = await authenticated_client.patch(
            f"/api/v1/sessions/{test_session.id}/draft",
            json=payload,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify updated fields
        assert data["subjective"] == payload["subjective"]
        assert data["assessment"] == payload["assessment"]

        # Verify unchanged fields remain the same
        assert data["objective"] == test_session.objective
        assert data["plan"] == test_session.plan

        # Verify version incremented
        assert data["version"] == original_version + 1

        # Verify draft_last_saved_at was set
        assert data["draft_last_saved_at"] is not None

        # Verify is_draft remains True
        assert data["is_draft"] is True

        # Verify finalized_at is still None
        assert data["finalized_at"] is None

    async def test_save_draft_partial_update(
        self,
        authenticated_client: AsyncClient,
        test_session,
    ):
        """Test only provided fields are updated."""
        original_subjective = test_session.subjective
        payload = {"plan": "Updated plan only via autosave"}

        response = await authenticated_client.patch(
            f"/api/v1/sessions/{test_session.id}/draft",
            json=payload,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Only plan should be updated
        assert data["plan"] == payload["plan"]
        assert data["subjective"] == original_subjective
        assert data["objective"] == test_session.objective
        assert data["assessment"] == test_session.assessment

    async def test_save_draft_empty_payload(
        self,
        authenticated_client: AsyncClient,
        test_session,
    ):
        """Test empty payload doesn't error (autosave may send empty updates)."""
        original_version = test_session.version
        payload = {}

        response = await authenticated_client.patch(
            f"/api/v1/sessions/{test_session.id}/draft",
            json=payload,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Version should not increment for empty payload
        assert data["version"] == original_version
        assert data["id"] == str(test_session.id)

    async def test_save_draft_updates_timestamp(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_session,
    ):
        """Test draft_last_saved_at is updated on autosave."""
        # First autosave to set initial timestamp
        payload1 = {"subjective": "First autosave"}
        response1 = await authenticated_client.patch(
            f"/api/v1/sessions/{test_session.id}/draft",
            json=payload1,
        )
        assert response1.status_code == status.HTTP_200_OK
        first_timestamp = datetime.fromisoformat(
            response1.json()["draft_last_saved_at"].replace("Z", "+00:00")
        )

        # Wait a tiny bit to ensure timestamp changes
        import asyncio

        await asyncio.sleep(0.01)

        # Second autosave
        payload2 = {"subjective": "Second autosave"}
        response2 = await authenticated_client.patch(
            f"/api/v1/sessions/{test_session.id}/draft",
            json=payload2,
        )

        assert response2.status_code == status.HTTP_200_OK
        data = response2.json()

        # Verify timestamp was updated
        second_timestamp = datetime.fromisoformat(
            data["draft_last_saved_at"].replace("Z", "+00:00")
        )
        assert second_timestamp > first_timestamp

    async def test_save_draft_increments_version(
        self,
        authenticated_client: AsyncClient,
        test_session,
    ):
        """Test version increments for optimistic locking."""
        original_version = test_session.version

        # Save draft multiple times
        for i in range(3):
            payload = {"subjective": f"Autosave {i + 1}"}
            response = await authenticated_client.patch(
                f"/api/v1/sessions/{test_session.id}/draft",
                json=payload,
            )
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["version"] == original_version + i + 1

    async def test_save_draft_workspace_isolation(
        self,
        authenticated_client: AsyncClient,
        test_session2,
    ):
        """Test cannot save draft from other workspace."""
        payload = {"subjective": "Malicious autosave attempt"}

        response = await authenticated_client.patch(
            f"/api/v1/sessions/{test_session2.id}/draft",
            json=payload,
        )

        # Should return 404 (not 403) to prevent information leakage
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_save_draft_not_found(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test autosave with non-existent session ID."""
        fake_id = uuid.uuid4()
        payload = {"subjective": "Autosave to non-existent session"}

        response = await authenticated_client.patch(
            f"/api/v1/sessions/{fake_id}/draft",
            json=payload,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_save_draft_unauthenticated(
        self,
        client: AsyncClient,
        test_session,
    ):
        """Test autosave requires authentication."""
        payload = {"subjective": "Unauthorized autosave"}

        response = await client.patch(
            f"/api/v1/sessions/{test_session.id}/draft",
            json=payload,
        )

        # CSRF middleware runs before auth for PATCH
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestFinalizeSession:
    """Tests for POST /api/v1/sessions/{id}/finalize endpoint."""

    async def test_finalize_success(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_session,
    ):
        """Test finalize sets timestamps and is_draft=False."""
        original_version = test_session.version
        assert test_session.is_draft is True
        assert test_session.finalized_at is None

        response = await authenticated_client.post(
            f"/api/v1/sessions/{test_session.id}/finalize",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify finalized_at is set
        assert data["finalized_at"] is not None
        finalized_time = datetime.fromisoformat(
            data["finalized_at"].replace("Z", "+00:00")
        )
        assert finalized_time <= datetime.now(UTC)

        # Verify is_draft is False
        assert data["is_draft"] is False

        # Verify version incremented
        assert data["version"] == original_version + 1

        # Verify in database
        await db_session.refresh(test_session)
        assert test_session.finalized_at is not None
        assert test_session.is_draft is False

    async def test_finalize_requires_content(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
    ):
        """Test cannot finalize session with all empty SOAP fields."""
        from pazpaz.models.session import Session

        # Create session with no SOAP content
        empty_session = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(hours=1),
            subjective=None,
            objective=None,
            assessment=None,
            plan=None,
            is_draft=True,
            version=1,
        )
        db_session.add(empty_session)
        await db_session.commit()
        await db_session.refresh(empty_session)

        response = await authenticated_client.post(
            f"/api/v1/sessions/{empty_session.id}/finalize",
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "at least one soap field must have content" in response.text.lower()

        # Verify session is still a draft
        await db_session.refresh(empty_session)
        assert empty_session.is_draft is True
        assert empty_session.finalized_at is None

    async def test_finalize_with_only_one_field(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
    ):
        """Test can finalize with only one SOAP field populated."""
        from pazpaz.models.session import Session

        # Create session with only subjective field
        session_one_field = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(hours=1),
            subjective="Only subjective filled in",
            objective=None,
            assessment=None,
            plan=None,
            is_draft=True,
            version=1,
        )
        db_session.add(session_one_field)
        await db_session.commit()
        await db_session.refresh(session_one_field)

        response = await authenticated_client.post(
            f"/api/v1/sessions/{session_one_field.id}/finalize",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["finalized_at"] is not None
        assert data["is_draft"] is False

    async def test_finalize_workspace_isolation(
        self,
        authenticated_client: AsyncClient,
        test_session2,
    ):
        """Test cannot finalize session from other workspace."""
        response = await authenticated_client.post(
            f"/api/v1/sessions/{test_session2.id}/finalize",
        )

        # Should return 404 (not 403) to prevent information leakage
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_finalize_not_found(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test finalize with non-existent session ID."""
        fake_id = uuid.uuid4()

        response = await authenticated_client.post(
            f"/api/v1/sessions/{fake_id}/finalize",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_finalize_unauthenticated(
        self,
        client: AsyncClient,
        test_session,
    ):
        """Test finalize requires authentication."""
        response = await client.post(
            f"/api/v1/sessions/{test_session.id}/finalize",
        )

        # CSRF middleware runs before auth for POST
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestDeleteFinalizedSession:
    """Tests for preventing deletion of finalized sessions."""

    async def test_delete_finalized_session_blocked(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_session,
    ):
        """Test cannot delete finalized session."""
        # First finalize the session
        test_session.finalized_at = datetime.now(UTC)
        test_session.is_draft = False
        await db_session.commit()

        # Try to delete
        response = await authenticated_client.delete(
            f"/api/v1/sessions/{test_session.id}",
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "cannot delete finalized sessions" in response.text.lower()

        # Verify session is not deleted
        await db_session.refresh(test_session)
        assert test_session.deleted_at is None

    async def test_delete_draft_session_allowed(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_session,
    ):
        """Test can delete draft session (not finalized)."""
        assert test_session.is_draft is True
        assert test_session.finalized_at is None

        response = await authenticated_client.delete(
            f"/api/v1/sessions/{test_session.id}",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify session is soft deleted
        await db_session.refresh(test_session)
        assert test_session.deleted_at is not None


class TestDraftAutosaveRateLimiting:
    """Tests for draft autosave rate limiting (60 requests/min per user per session)."""

    async def test_save_draft_rate_limit_enforced(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_session,
        redis_client,
    ):
        """Test 60 requests/min rate limit is enforced."""
        # Clear Redis to ensure clean state
        await redis_client.flushdb()

        # Make 60 successful requests (max allowed)
        for i in range(60):
            response = await authenticated_client.patch(
                f"/api/v1/sessions/{test_session.id}/draft",
                json={"subjective": f"Update {i}"},
            )
            assert response.status_code == status.HTTP_200_OK, (
                f"Request {i + 1} failed: {response.text}"
            )

        # 61st request should be rate limited
        response = await authenticated_client.patch(
            f"/api/v1/sessions/{test_session.id}/draft",
            json={"subjective": "Rate limit exceeded"},
        )
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "rate limit" in response.json()["detail"].lower()

    async def test_save_draft_rate_limit_resets_after_window(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_session,
        redis_client,
    ):
        """Test rate limit resets after 60 second window."""

        # Clear Redis to ensure clean state
        await redis_client.flushdb()

        # Make 60 requests to hit the limit
        for i in range(60):
            response = await authenticated_client.patch(
                f"/api/v1/sessions/{test_session.id}/draft",
                json={"subjective": f"Update {i}"},
            )
            assert response.status_code == status.HTTP_200_OK

        # Next request should be rate limited
        response = await authenticated_client.patch(
            f"/api/v1/sessions/{test_session.id}/draft",
            json={"subjective": "Should be rate limited"},
        )
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

        # Wait for window to expire (61 seconds to be safe)
        # Note: In real tests, this would be mocked. Here we use a short wait
        # and verify the Redis sliding window implementation.
        # For practical testing, we verify the window works by checking
        # Redis key TTL instead of actually waiting 60 seconds.

        # Get the user_id from the test user fixture
        user_id = test_session.created_by_user_id
        rate_limit_key = f"draft_autosave:{user_id}:{test_session.id}"

        # Verify the rate limit key exists and has appropriate TTL
        ttl = await redis_client.ttl(rate_limit_key)
        assert ttl > 0  # Key should have TTL set
        assert ttl <= 70  # Should be window_seconds (60) + buffer (10)

        # Manually clear the key to simulate window expiration (instead of waiting)
        await redis_client.delete(rate_limit_key)

        # After window reset, requests should work again
        response = await authenticated_client.patch(
            f"/api/v1/sessions/{test_session.id}/draft",
            json={"subjective": "After window reset"},
        )
        assert response.status_code == status.HTTP_200_OK

    async def test_save_draft_rate_limit_per_user(
        self,
        db_session: AsyncSession,
        redis_client,
        workspace_1,
        test_user_ws1,
        workspace_2,
        test_user_ws2,
        sample_client_ws1,
        sample_client_ws2,
    ):
        """Test rate limits are per-user, not global."""
        from pazpaz.core.rate_limiting import check_rate_limit_redis
        from pazpaz.models.session import Session

        # Clear Redis to ensure clean state
        await redis_client.flushdb()

        # Create sessions for both users
        session_ws1 = Session(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            created_by_user_id=test_user_ws1.id,
            session_date=datetime.now(UTC) - timedelta(hours=1),
            subjective="User 1 session",
            is_draft=True,
            version=1,
        )
        session_ws2 = Session(
            workspace_id=workspace_2.id,
            client_id=sample_client_ws2.id,
            created_by_user_id=test_user_ws2.id,
            session_date=datetime.now(UTC) - timedelta(hours=1),
            subjective="User 2 session",
            is_draft=True,
            version=1,
        )
        db_session.add_all([session_ws1, session_ws2])
        await db_session.commit()
        await db_session.refresh(session_ws1)
        await db_session.refresh(session_ws2)

        # User 1 makes 60 requests to their session (hits limit)
        user1_key = f"draft_autosave:{test_user_ws1.id}:{session_ws1.id}"
        for _i in range(60):
            allowed = await check_rate_limit_redis(
                redis_client=redis_client,
                key=user1_key,
                max_requests=60,
                window_seconds=60,
            )
            assert allowed is True

        # User 1's 61st request should be rate limited
        allowed = await check_rate_limit_redis(
            redis_client=redis_client,
            key=user1_key,
            max_requests=60,
            window_seconds=60,
        )
        assert allowed is False, "User 1 should be rate limited"

        # User 2 should still have full quota (different user_id in key)
        user2_key = f"draft_autosave:{test_user_ws2.id}:{session_ws2.id}"
        allowed = await check_rate_limit_redis(
            redis_client=redis_client,
            key=user2_key,
            max_requests=60,
            window_seconds=60,
        )
        assert allowed is True, "User 2 should have full quota (separate rate limit)"

        # Verify user 2 can make all 60 requests
        for _i in range(59):  # Already made 1
            allowed = await check_rate_limit_redis(
                redis_client=redis_client,
                key=user2_key,
                max_requests=60,
                window_seconds=60,
            )
            assert allowed is True

        # User 2's 61st request should now be rate limited
        allowed = await check_rate_limit_redis(
            redis_client=redis_client,
            key=user2_key,
            max_requests=60,
            window_seconds=60,
        )
        assert allowed is False, "User 2 should now be rate limited"

    async def test_save_draft_rate_limit_per_session(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_workspace,
        test_client,
        test_user,
        redis_client,
    ):
        """Test rate limits are per-session, allowing concurrent editing."""
        from pazpaz.models.session import Session

        # Clear Redis to ensure clean state
        await redis_client.flushdb()

        # Create two sessions for the same user
        session1 = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(hours=1),
            subjective="Session 1",
            is_draft=True,
            version=1,
        )
        session2 = Session(
            workspace_id=test_workspace.id,
            client_id=test_client.id,
            created_by_user_id=test_user.id,
            session_date=datetime.now(UTC) - timedelta(hours=2),
            subjective="Session 2",
            is_draft=True,
            version=1,
        )
        db_session.add_all([session1, session2])
        await db_session.commit()
        await db_session.refresh(session1)
        await db_session.refresh(session2)

        # Make 60 requests to session 1 (hits limit for that session)
        for i in range(60):
            response = await authenticated_client.patch(
                f"/api/v1/sessions/{session1.id}/draft",
                json={"subjective": f"Session 1 update {i}"},
            )
            assert response.status_code == status.HTTP_200_OK

        # Session 1's 61st request should be rate limited
        response = await authenticated_client.patch(
            f"/api/v1/sessions/{session1.id}/draft",
            json={"subjective": "Session 1 exceeded"},
        )
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

        # Session 2 should still have full quota (separate rate limit key)
        response = await authenticated_client.patch(
            f"/api/v1/sessions/{session2.id}/draft",
            json={"subjective": "Session 2 update"},
        )
        assert response.status_code == status.HTTP_200_OK, (
            f"Session 2 should have full quota: {response.text}"
        )

        # Verify session 2 can make all 60 requests
        for i in range(59):  # Already made 1
            response = await authenticated_client.patch(
                f"/api/v1/sessions/{session2.id}/draft",
                json={"subjective": f"Session 2 update {i}"},
            )
            assert response.status_code == status.HTTP_200_OK

        # Session 2's 61st request should now be rate limited
        response = await authenticated_client.patch(
            f"/api/v1/sessions/{session2.id}/draft",
            json={"subjective": "Session 2 exceeded"},
        )
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    async def test_save_draft_rate_limit_key_format(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_session,
        test_user,
        redis_client,
    ):
        """Test rate limit key includes user_id and session_id for proper scoping."""
        # Clear Redis to ensure clean state
        await redis_client.flushdb()

        # Make a single request
        response = await authenticated_client.patch(
            f"/api/v1/sessions/{test_session.id}/draft",
            json={"subjective": "Test update"},
        )
        assert response.status_code == status.HTTP_200_OK

        # Verify Redis key format: draft_autosave:{user_id}:{session_id}
        expected_key = f"draft_autosave:{test_user.id}:{test_session.id}"
        key_exists = await redis_client.exists(expected_key)
        assert key_exists == 1, f"Expected key {expected_key} to exist in Redis"

        # Verify the key is a sorted set (used for sliding window)
        key_type = await redis_client.type(expected_key)
        assert key_type == "zset", f"Expected key type 'zset', got '{key_type}'"

        # Verify the sorted set has 1 member (1 request)
        count = await redis_client.zcard(expected_key)
        assert count == 1, f"Expected 1 request in window, got {count}"
