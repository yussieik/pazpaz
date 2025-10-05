"""Tests for audit logging functionality."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.audit_event import AuditAction, ResourceType
from pazpaz.services.audit_service import (
    create_audit_event,
    sanitize_metadata,
)


class TestAuditService:
    """Test audit service helper functions."""

    async def test_create_audit_event(
        self,
        db_session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ):
        """Test creating an audit event."""
        # Create audit event
        audit_event = await create_audit_event(
            db=db_session,
            user_id=user_id,
            workspace_id=workspace_id,
            action=AuditAction.READ,
            resource_type=ResourceType.CLIENT,
            resource_id=uuid.uuid4(),
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            metadata={"query_params": {"include_inactive": True}},
        )

        await db_session.commit()

        # Verify audit event was created
        assert audit_event.id is not None
        assert audit_event.workspace_id == workspace_id
        assert audit_event.user_id == user_id
        assert audit_event.action == AuditAction.READ
        assert audit_event.resource_type == ResourceType.CLIENT.value
        assert audit_event.event_type == "client.read"
        assert audit_event.ip_address == "192.168.1.1"
        assert audit_event.user_agent == "Mozilla/5.0"
        assert audit_event.event_metadata == {
            "query_params": {"include_inactive": True}
        }

    async def test_create_audit_event_system_event(
        self,
        db_session: AsyncSession,
        workspace_id: uuid.UUID,
    ):
        """Test creating a system audit event (no user_id)."""
        # Create system event
        audit_event = await create_audit_event(
            db=db_session,
            user_id=None,  # System event
            workspace_id=workspace_id,
            action=AuditAction.DELETE,
            resource_type=ResourceType.CLIENT,
            resource_id=uuid.uuid4(),
        )

        await db_session.commit()

        # Verify system event
        assert audit_event.id is not None
        assert audit_event.user_id is None
        assert audit_event.workspace_id == workspace_id

    async def test_create_audit_event_with_string_resource_type(
        self,
        db_session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ):
        """Test creating audit event with string resource type."""
        # Create with string resource type
        audit_event = await create_audit_event(
            db=db_session,
            user_id=user_id,
            workspace_id=workspace_id,
            action=AuditAction.CREATE,
            resource_type="Client",  # String instead of enum
            resource_id=uuid.uuid4(),
        )

        await db_session.commit()

        # Verify resource type was normalized
        assert audit_event.resource_type == ResourceType.CLIENT.value

    async def test_create_audit_event_invalid_resource_type(
        self,
        db_session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ):
        """Test creating audit event with invalid resource type raises error."""
        with pytest.raises(ValueError, match="Invalid resource_type"):
            await create_audit_event(
                db=db_session,
                user_id=user_id,
                workspace_id=workspace_id,
                action=AuditAction.CREATE,
                resource_type="InvalidType",
                resource_id=uuid.uuid4(),
            )

    def test_sanitize_metadata_removes_pii(self):
        """Test metadata sanitization removes PII/PHI fields."""
        metadata = {
            "first_name": "John",  # Should be removed
            "last_name": "Doe",  # Should be removed
            "email": "john@example.com",  # Should be removed
            "phone": "555-1234",  # Should be removed
            "status": "active",  # Should be kept
            "updated_fields": ["first_name", "email"],  # Should be kept
            "count": 5,  # Should be kept
        }

        sanitized = sanitize_metadata(metadata)

        # Verify PII removed but non-sensitive data kept
        assert "first_name" not in sanitized
        assert "last_name" not in sanitized
        assert "email" not in sanitized
        assert "phone" not in sanitized
        assert sanitized["status"] == "active"
        assert sanitized["updated_fields"] == ["first_name", "email"]
        assert sanitized["count"] == 5

    def test_sanitize_metadata_nested_dict(self):
        """Test sanitization works on nested dictionaries."""
        metadata = {
            "user": {
                "name": "John",  # Should be removed
                "role": "admin",  # Should be kept
            },
            "changes": {
                "email": "old@example.com",  # Should be removed
                "status": "updated",  # Should be kept
            },
        }

        sanitized = sanitize_metadata(metadata)

        # Verify nested PII removed
        assert "name" not in sanitized["user"]
        assert sanitized["user"]["role"] == "admin"
        assert "email" not in sanitized["changes"]
        assert sanitized["changes"]["status"] == "updated"

    def test_sanitize_metadata_empty(self):
        """Test sanitization of empty metadata."""
        assert sanitize_metadata(None) is None
        assert sanitize_metadata({}) is None

    # NOTE: Immutability is enforced by database triggers (Day 2 implementation)
    # This test would require the triggers to be in place, which are handled
    # separately in the database migration system


# NOTE: Middleware and API integration tests are skipped here
# The middleware functionality will be tested through actual API endpoint usage
# in the existing integration tests for clients, appointments, etc.
# The audit service tests above verify the core functionality
