"""Test authentication audit logging for HIPAA compliance.

All authentication events must be logged with IP address for security monitoring.

Security Requirements:
- HIPAA audit trail requirements
- Log all auth events (success and failure)
- Include IP address for investigation

Reference: Week 2, Task 2.5 - Authentication Audit Logging
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from pazpaz.models.audit_event import AuditAction, AuditEvent, ResourceType
from pazpaz.models.user import User
from pazpaz.models.workspace import Workspace

pytestmark = pytest.mark.asyncio


class TestMagicLinkRequestAuditLogging:
    """Test audit logging for magic link requests."""

    async def test_magic_link_request_creates_audit_event_success(
        self,
        client: AsyncClient,
        db_session,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        unauthenticated_workspace,
    ):
        """Verify successful magic link requests create audit events."""
        await db_session.execute(delete(AuditEvent))
        await db_session.commit()

        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": test_user_ws1.email},
        )
        assert response.status_code == 200

        query = (
            select(AuditEvent)
            .where(AuditEvent.user_id == test_user_ws1.id)
            .where(AuditEvent.workspace_id == workspace_1.id)
        )
        result = await db_session.execute(query)
        audit_event = result.scalar_one_or_none()

        assert audit_event is not None
        assert audit_event.action == AuditAction.READ
        assert audit_event.resource_type == ResourceType.USER.value
        assert audit_event.resource_id == test_user_ws1.id
        assert audit_event.event_metadata["action"] == "magic_link_generated"
        assert audit_event.ip_address is not None


class TestAuthAuditEventsIncludeIPAddress:
    """Test that all auth audit events include IP address."""

    async def test_auth_audit_events_include_ip_address(
        self,
        client: AsyncClient,
        db_session,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        unauthenticated_workspace,
    ):
        """Verify audit events include client IP address."""
        await db_session.execute(delete(AuditEvent))
        await db_session.commit()

        response = await client.post(
            "/api/v1/auth/magic-link",
            json={"email": test_user_ws1.email},
        )
        assert response.status_code == 200

        query = (
            select(AuditEvent)
            .where(AuditEvent.user_id == test_user_ws1.id)
            .where(AuditEvent.workspace_id == workspace_1.id)
        )
        result = await db_session.execute(query)
        audit_event = result.scalar_one_or_none()

        assert audit_event is not None
        assert audit_event.ip_address is not None
        assert audit_event.ip_address in ["127.0.0.1", "testclient"]
