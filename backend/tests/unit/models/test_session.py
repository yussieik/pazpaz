"""
Tests for Session model.

This test suite validates:
1. Encryption roundtrip for SOAP fields
2. Workspace isolation
3. NULL encrypted field handling
4. Relationship integrity
5. Draft/finalization workflow
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.client import Client
from pazpaz.models.session import Session
from pazpaz.models.user import User
from pazpaz.models.workspace import Workspace


@pytest.mark.asyncio
async def test_session_encryption_roundtrip(
    db_session: AsyncSession,
    workspace_1: Workspace,
    sample_client_ws1: Client,
    test_user_ws1: User,
):
    """Test that SOAP fields are encrypted in DB and decrypted on retrieval."""
    # Create session with complete SOAP notes
    session = Session(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        created_by_user_id=test_user_ws1.id,
        session_date=datetime.now(UTC) - timedelta(hours=1),
        subjective="Patient reports lower back pain radiating to left leg",
        objective="Reduced ROM in lumbar flexion, positive straight leg raise",
        assessment="Acute lumbar radiculopathy, likely L5-S1 disc herniation",
        plan="PT 2x/week for 6 weeks, reassess if no improvement",
        duration_minutes=60,
    )
    db_session.add(session)
    await db_session.commit()
    session_id = session.id

    # Verify encrypted in database (raw SQL check)
    result = await db_session.execute(
        text(
            "SELECT subjective, objective, assessment, plan FROM sessions WHERE id = :id"
        ),
        {"id": session_id},
    )
    raw_row = result.fetchone()

    # Raw values should be bytes (encrypted), not plaintext strings
    assert isinstance(raw_row[0], bytes), "Subjective should be encrypted (bytes)"
    assert isinstance(raw_row[1], bytes), "Objective should be encrypted (bytes)"
    assert isinstance(raw_row[2], bytes), "Assessment should be encrypted (bytes)"
    assert isinstance(raw_row[3], bytes), "Plan should be encrypted (bytes)"

    # Verify plaintext is not visible in raw bytes
    # Use latin1 encoding to decode bytes without errors for checking
    subjective_raw = raw_row[0].decode("latin1", errors="ignore")
    assert "back pain" not in subjective_raw, (
        "Plaintext should not be visible in encrypted data"
    )

    # Verify decrypted on retrieval via ORM
    retrieved = await db_session.get(Session, session_id)
    assert retrieved is not None
    assert (
        retrieved.subjective == "Patient reports lower back pain radiating to left leg"
    )
    assert (
        retrieved.objective
        == "Reduced ROM in lumbar flexion, positive straight leg raise"
    )
    assert (
        retrieved.assessment
        == "Acute lumbar radiculopathy, likely L5-S1 disc herniation"
    )
    assert retrieved.plan == "PT 2x/week for 6 weeks, reassess if no improvement"


@pytest.mark.asyncio
async def test_session_workspace_isolation(
    db_session: AsyncSession,
    workspace_1: Workspace,
    workspace_2: Workspace,
    sample_client_ws1: Client,
    sample_client_ws2: Client,
    test_user_ws1: User,
    test_user_ws2: User,
):
    """Test that sessions are isolated per workspace."""
    # Create session in workspace 1
    session_1 = Session(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        created_by_user_id=test_user_ws1.id,
        session_date=datetime.now(UTC),
        subjective="Workspace 1 session",
    )

    # Create session in workspace 2
    session_2 = Session(
        workspace_id=workspace_2.id,
        client_id=sample_client_ws2.id,
        created_by_user_id=test_user_ws2.id,
        session_date=datetime.now(UTC),
        subjective="Workspace 2 session",
    )

    db_session.add_all([session_1, session_2])
    await db_session.commit()

    # Query sessions for workspace 1
    result = await db_session.execute(
        select(Session).where(Session.workspace_id == workspace_1.id)
    )
    workspace_1_sessions = result.scalars().all()

    assert len(workspace_1_sessions) == 1
    assert workspace_1_sessions[0].subjective == "Workspace 1 session"
    assert workspace_1_sessions[0].client_id == sample_client_ws1.id

    # Query sessions for workspace 2
    result = await db_session.execute(
        select(Session).where(Session.workspace_id == workspace_2.id)
    )
    workspace_2_sessions = result.scalars().all()

    assert len(workspace_2_sessions) == 1
    assert workspace_2_sessions[0].subjective == "Workspace 2 session"
    assert workspace_2_sessions[0].client_id == sample_client_ws2.id


@pytest.mark.asyncio
async def test_session_null_encrypted_fields(
    db_session: AsyncSession,
    workspace_1: Workspace,
    sample_client_ws1: Client,
    test_user_ws1: User,
):
    """Test that NULL encrypted fields work correctly."""
    # Create session with only subjective filled
    session = Session(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        created_by_user_id=test_user_ws1.id,
        session_date=datetime.now(UTC),
        subjective="Only subjective filled",
        objective=None,
        assessment=None,
        plan=None,
    )
    db_session.add(session)
    await db_session.commit()
    session_id = session.id

    # Retrieve and verify NULL fields
    retrieved = await db_session.get(Session, session_id)
    assert retrieved is not None
    assert retrieved.subjective == "Only subjective filled"
    assert retrieved.objective is None
    assert retrieved.assessment is None
    assert retrieved.plan is None


@pytest.mark.asyncio
async def test_session_relationships(
    db_session: AsyncSession,
    workspace_1: Workspace,
    sample_client_ws1: Client,
    test_user_ws1: User,
    sample_appointment_ws1,
):
    """Test that Session relationships work correctly."""
    # Create session linked to appointment
    session = Session(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        appointment_id=sample_appointment_ws1.id,
        created_by_user_id=test_user_ws1.id,
        session_date=datetime.now(UTC),
        subjective="Test session",
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    # Test workspace relationship
    assert session.workspace.id == workspace_1.id
    assert session.workspace.name == "Test Workspace 1"

    # Test client relationship
    assert session.client.id == sample_client_ws1.id
    assert session.client.first_name == "John"

    # Test created_by relationship
    assert session.created_by.id == test_user_ws1.id
    assert session.created_by.email == "test-user-ws1@example.com"

    # Test appointment relationship
    assert session.appointment is not None
    assert session.appointment.id == sample_appointment_ws1.id


@pytest.mark.asyncio
async def test_session_draft_workflow(
    db_session: AsyncSession,
    workspace_1: Workspace,
    sample_client_ws1: Client,
    test_user_ws1: User,
):
    """Test draft session creation and finalization."""
    # Create draft session
    session = Session(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        created_by_user_id=test_user_ws1.id,
        session_date=datetime.now(UTC),
        subjective="Draft notes",
        is_draft=True,
    )
    db_session.add(session)
    await db_session.commit()
    session_id = session.id

    # Verify draft status
    assert session.is_draft is True
    assert session.finalized_at is None

    # Update draft
    session.objective = "Updated objective"
    session.draft_last_saved_at = datetime.now(UTC)
    await db_session.commit()

    # Finalize session
    session.is_draft = False
    session.finalized_at = datetime.now(UTC)
    await db_session.commit()

    # Verify finalized
    retrieved = await db_session.get(Session, session_id)
    assert retrieved is not None
    assert retrieved.is_draft is False
    assert retrieved.finalized_at is not None
    assert retrieved.objective == "Updated objective"


@pytest.mark.asyncio
async def test_session_cascade_delete_with_client(
    db_session: AsyncSession,
    workspace_1: Workspace,
    sample_client_ws1: Client,
    test_user_ws1: User,
):
    """Test that sessions are cascade deleted when client is deleted."""
    # Create session
    session = Session(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        created_by_user_id=test_user_ws1.id,
        session_date=datetime.now(UTC),
        subjective="Test session",
    )
    db_session.add(session)
    await db_session.commit()
    session_id = session.id

    # Delete client
    await db_session.delete(sample_client_ws1)
    await db_session.commit()

    # Verify session was cascade deleted
    result = await db_session.get(Session, session_id)
    assert result is None


@pytest.mark.asyncio
async def test_session_unicode_encrypted_fields(
    db_session: AsyncSession,
    workspace_1: Workspace,
    sample_client_ws1: Client,
    test_user_ws1: User,
):
    """Test that encrypted fields handle unicode correctly."""
    # Create session with unicode content
    session = Session(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        created_by_user_id=test_user_ws1.id,
        session_date=datetime.now(UTC),
        subjective="Patient reports: עברית - Hebrew, 中文 - Chinese, Español 🔐",
        objective="Unicode test with emojis 🏥 and symbols ñ é",
    )
    db_session.add(session)
    await db_session.commit()
    session_id = session.id

    # Retrieve and verify unicode preserved
    retrieved = await db_session.get(Session, session_id)
    assert retrieved is not None
    assert (
        retrieved.subjective
        == "Patient reports: עברית - Hebrew, 中文 - Chinese, Español 🔐"
    )
    assert retrieved.objective == "Unicode test with emojis 🏥 and symbols ñ é"


@pytest.mark.asyncio
async def test_session_large_encrypted_fields(
    db_session: AsyncSession,
    workspace_1: Workspace,
    sample_client_ws1: Client,
    test_user_ws1: User,
):
    """Test that large SOAP notes (up to 5KB) work correctly."""
    # Generate 4KB SOAP note (realistic size)
    large_subjective = "Patient presents with multiple complaints. " * 100  # ~4KB

    session = Session(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        created_by_user_id=test_user_ws1.id,
        session_date=datetime.now(UTC),
        subjective=large_subjective,
    )
    db_session.add(session)
    await db_session.commit()
    session_id = session.id

    # Verify large field encrypts and decrypts correctly
    retrieved = await db_session.get(Session, session_id)
    assert retrieved is not None
    assert retrieved.subjective == large_subjective
    assert len(retrieved.subjective) >= 4000


@pytest.mark.asyncio
async def test_session_client_relationship_back_populates(
    db_session: AsyncSession,
    workspace_1: Workspace,
    sample_client_ws1: Client,
    test_user_ws1: User,
):
    """Test that client.sessions relationship works (back_populates)."""
    from sqlalchemy.orm import selectinload

    # Create multiple sessions for same client
    session_1 = Session(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        created_by_user_id=test_user_ws1.id,
        session_date=datetime.now(UTC) - timedelta(days=7),
        subjective="Session 1 week ago",
    )
    session_2 = Session(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        created_by_user_id=test_user_ws1.id,
        session_date=datetime.now(UTC) - timedelta(days=1),
        subjective="Session yesterday",
    )
    db_session.add_all([session_1, session_2])
    await db_session.commit()

    # Query client with sessions eagerly loaded
    result = await db_session.execute(
        select(Client)
        .where(Client.id == sample_client_ws1.id)
        .options(selectinload(Client.sessions))
    )
    client = result.scalar_one()

    # Verify client has both sessions
    assert len(client.sessions) == 2
    session_subjects = [s.subjective for s in client.sessions]
    assert "Session 1 week ago" in session_subjects
    assert "Session yesterday" in session_subjects
