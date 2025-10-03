"""add_audit_events_table

Revision ID: de72ee2cfb00
Revises: 83680210d7d2
Create Date: 2025-10-03 13:59:05.268207

This migration creates the audit_events table for HIPAA-compliant audit logging.

The audit_events table is designed to:
1. Track all access and modifications to Protected Health Information (PHI)
2. Maintain an immutable, append-only audit trail
3. Support workspace isolation with efficient indexing
4. Enable fast queries for compliance reporting and security monitoring

Key Design Decisions:
- UUID primary key for distributed systems compatibility
- JSONB metadata for flexible context storage
- Composite indexes optimized for common query patterns
- Foreign keys with CASCADE for workspace deletion
- SET NULL for user deletion (preserve audit trail)
- Partitioning by created_at recommended for production (future enhancement)

Performance Targets:
- Timeline queries (workspace_id + created_at): <50ms p95
- PHI access queries (resource_type + action): <100ms p95
- High-volume logging: 10,000+ events/day per workspace
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "de72ee2cfb00"
down_revision: str | Sequence[str] | None = "83680210d7d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create audit_events table with indexes and constraints."""
    # Create audit_events table
    op.create_table(
        "audit_events",
        # Primary key
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Unique identifier for the audit event",
        ),
        # Foreign keys
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            comment="Workspace this event belongs to (workspace scoping)",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="User who performed the action (NULL for system events)",
        ),
        # Event identification
        sa.Column(
            "event_type",
            sa.String(100),
            nullable=False,
            comment="Event type (e.g., user.login, client.view, session.create)",
        ),
        sa.Column(
            "resource_type",
            sa.String(50),
            nullable=True,
            comment="Type of resource accessed (User, Client, Session, Appointment)",
        ),
        sa.Column(
            "resource_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="ID of the resource being accessed or modified",
        ),
        sa.Column(
            "action",
            sa.String(20),
            nullable=False,
            comment="Action performed (CREATE, READ, UPDATE, DELETE, LOGIN, LOGOUT, etc.)",
        ),
        # Request context
        sa.Column(
            "ip_address",
            sa.String(45),
            nullable=True,
            comment="IP address of the user (IPv4 or IPv6)",
        ),
        sa.Column(
            "user_agent",
            sa.Text(),
            nullable=True,
            comment="User agent string from the request",
        ),
        # Flexible metadata storage (NO PII/PHI)
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=True,
            comment="Additional event context (changed_fields, query_params, etc. - NO PII/PHI)",
        ),
        # Timestamp
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="When the event occurred (immutable)",
        ),
        # Table comment
        comment="Immutable audit trail for HIPAA compliance and security monitoring",
    )

    # Primary composite index for workspace timeline queries
    # Most common query: "Get all events for workspace X in date range Y"
    op.create_index(
        "ix_audit_events_workspace_created",
        "audit_events",
        ["workspace_id", sa.text("created_at DESC")],
        unique=False,
    )

    # Index for user-specific audit queries
    # Query: "What did user X do in workspace Y?"
    op.create_index(
        "ix_audit_events_workspace_user",
        "audit_events",
        ["workspace_id", "user_id", sa.text("created_at DESC")],
        unique=False,
    )

    # Index for event type filtering
    # Query: "All login events for workspace X"
    op.create_index(
        "ix_audit_events_workspace_event_type",
        "audit_events",
        ["workspace_id", "event_type", sa.text("created_at DESC")],
        unique=False,
    )

    # Index for resource-specific audit trail
    # Query: "Who accessed client Y? What was changed in session Z?"
    op.create_index(
        "ix_audit_events_resource",
        "audit_events",
        ["resource_type", "resource_id", sa.text("created_at DESC")],
        unique=False,
    )

    # Partial index for PHI access tracking (HIPAA requirement)
    # Query: "All PHI READ operations in workspace X"
    op.create_index(
        "ix_audit_events_phi_access",
        "audit_events",
        ["workspace_id", "resource_type", sa.text("created_at DESC")],
        unique=False,
        postgresql_where=sa.text(
            "action = 'READ' AND resource_type IN ('Client', 'Session', 'PlanOfCare')"
        ),
    )

    # Create trigger to prevent UPDATE and DELETE operations (immutability)
    # This ensures the audit trail cannot be tampered with
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_event_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'Audit events are immutable and cannot be updated';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Audit events are immutable and cannot be deleted';
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER prevent_audit_event_update
        BEFORE UPDATE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_event_modification();
        """
    )

    op.execute(
        """
        CREATE TRIGGER prevent_audit_event_delete
        BEFORE DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_event_modification();
        """
    )


def downgrade() -> None:
    """Remove audit_events table, triggers, and function."""
    # Drop triggers first
    op.execute("DROP TRIGGER IF EXISTS prevent_audit_event_delete ON audit_events;")
    op.execute("DROP TRIGGER IF EXISTS prevent_audit_event_update ON audit_events;")

    # Drop function
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_event_modification();")

    # Drop indexes explicitly (for clarity)
    op.drop_index("ix_audit_events_phi_access", table_name="audit_events")
    op.drop_index("ix_audit_events_resource", table_name="audit_events")
    op.drop_index("ix_audit_events_workspace_event_type", table_name="audit_events")
    op.drop_index("ix_audit_events_workspace_user", table_name="audit_events")
    op.drop_index("ix_audit_events_workspace_created", table_name="audit_events")

    # Drop table
    op.drop_table("audit_events")
