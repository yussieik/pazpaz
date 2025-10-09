"""create_sessions_tables

Revision ID: 430584776d5b
Revises: 8283b279aeac
Create Date: 2025-10-08 15:46:05.980122

This migration creates the sessions and session_attachments tables for Week 2
of the SECURITY_FIRST_IMPLEMENTATION_PLAN.md (SOAP Notes Core feature).

The sessions table stores SOAP notes with encrypted PHI columns:
1. All PHI fields (subjective, objective, assessment, plan) stored as BYTEA using
   application-level AES-256-GCM encryption via EncryptedString SQLAlchemy type
2. Workspace isolation enforced via foreign key CASCADE
3. Soft delete only (deleted_at timestamp) for HIPAA compliance
4. Optimistic locking via version field for autosave conflict resolution
5. Draft mode support for autosave feature (Week 2 Day 8)

The session_attachments table prepares for Week 3 file upload feature:
1. References to S3/MinIO object keys (encrypted file paths)
2. Workspace scoping for multi-tenant file isolation
3. Soft delete for audit trail preservation

Performance Targets:
- Client timeline query (100 sessions): <150ms p95
- Draft list query: <100ms p95
- Single session fetch: <50ms p95

Security Requirements:
- 100% workspace isolation (foreign key enforced)
- 100% PHI encryption (BYTEA columns with EncryptedString)
- Soft delete only (audit trail preserved)
- Column comments identify all encrypted fields

Key Design Decisions:
- BYTEA column type for encrypted fields (not TEXT)
- No indexes on encrypted columns (not searchable by content)
- Composite indexes starting with workspace_id for multi-tenant performance
- Partial indexes for active sessions (deleted_at IS NULL)
- Optional appointment linkage (SET NULL on appointment deletion)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "430584776d5b"
down_revision: str | Sequence[str] | None = "8283b279aeac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create sessions and session_attachments tables with encrypted PHI columns."""
    # ========================================================================
    # SESSIONS TABLE
    # ========================================================================
    op.create_table(
        "sessions",
        # Primary key
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Unique identifier for the session",
        ),
        # Foreign keys (workspace scoping and relationships)
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            comment="Workspace this session belongs to (workspace scoping)",
        ),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"),
            nullable=False,
            comment="Client this session is for (CASCADE delete with client)",
        ),
        sa.Column(
            "appointment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appointments.id", ondelete="SET NULL"),
            nullable=True,
            comment="Optional link to appointment (SET NULL if appointment deleted)",
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="User who created this session (SET NULL to preserve record)",
        ),
        # SOAP Notes PHI Columns (ENCRYPTED as BYTEA)
        # These columns will be handled by EncryptedString SQLAlchemy type in the model
        sa.Column(
            "subjective",
            postgresql.BYTEA(),
            nullable=True,
            comment="ENCRYPTED: Subjective findings (patient-reported symptoms) - AES-256-GCM",
        ),
        sa.Column(
            "objective",
            postgresql.BYTEA(),
            nullable=True,
            comment="ENCRYPTED: Objective findings (therapist observations) - AES-256-GCM",
        ),
        sa.Column(
            "assessment",
            postgresql.BYTEA(),
            nullable=True,
            comment="ENCRYPTED: Assessment (diagnosis/evaluation) - AES-256-GCM",
        ),
        sa.Column(
            "plan",
            postgresql.BYTEA(),
            nullable=True,
            comment="ENCRYPTED: Plan (treatment plan and next steps) - AES-256-GCM",
        ),
        # Session metadata (non-encrypted)
        sa.Column(
            "session_date",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Date and time when the session occurred (timezone-aware UTC)",
        ),
        sa.Column(
            "duration_minutes",
            sa.Integer(),
            nullable=True,
            comment="Duration of the session in minutes",
        ),
        sa.Column(
            "is_draft",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Draft status (true = autosave draft, false = finalized)",
        ),
        sa.Column(
            "draft_last_saved_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp of last autosave (NULL if not a draft)",
        ),
        sa.Column(
            "finalized_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when session was marked complete (NULL if draft)",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Version number for optimistic locking (conflict resolution)",
        ),
        # Audit columns
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="When this session was created (immutable)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="When this session was last updated",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Soft delete timestamp (NULL = active, NOT NULL = deleted)",
        ),
        # Table comment
        comment="SOAP notes sessions with encrypted PHI (subjective, objective, assessment, plan)",
    )

    # ========================================================================
    # SESSION_ATTACHMENTS TABLE (for Week 3 file upload feature)
    # ========================================================================
    op.create_table(
        "session_attachments",
        # Primary key
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Unique identifier for the attachment",
        ),
        # Foreign keys
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
            comment="Session this attachment belongs to (CASCADE delete with session)",
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            comment="Workspace scoping (for multi-tenant S3 isolation)",
        ),
        sa.Column(
            "uploaded_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="User who uploaded this file (SET NULL to preserve record)",
        ),
        # File metadata
        sa.Column(
            "file_name",
            sa.String(255),
            nullable=False,
            comment="Original filename (sanitized for security)",
        ),
        sa.Column(
            "file_type",
            sa.String(100),
            nullable=False,
            comment="MIME type (validated: image/jpeg, image/png, image/webp, application/pdf)",
        ),
        sa.Column(
            "file_size_bytes",
            sa.Integer(),
            nullable=False,
            comment="File size in bytes (max 10 MB enforced by application)",
        ),
        sa.Column(
            "s3_key",
            sa.Text(),
            nullable=False,
            comment="S3/MinIO object key (workspace-scoped path with encryption)",
        ),
        # Audit columns
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="When this file was uploaded",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Soft delete timestamp (NULL = active, NOT NULL = deleted)",
        ),
        # Table comment
        comment="File attachments for SOAP notes sessions (S3/MinIO references)",
    )

    # ========================================================================
    # PERFORMANCE INDEXES FOR SESSIONS TABLE
    # ========================================================================

    # Index 1: Client timeline query (most common query pattern)
    # Query: "Get all sessions for client X, ordered by date"
    # Expected p95: <150ms for 100 sessions
    op.create_index(
        "ix_sessions_workspace_client_date",
        "sessions",
        ["workspace_id", "client_id", sa.text("session_date DESC")],
        unique=False,
    )

    # Index 2: Draft list query (for autosave UI)
    # Query: "Get all draft sessions in workspace X, ordered by last saved"
    # Expected p95: <100ms
    op.create_index(
        "ix_sessions_workspace_draft",
        "sessions",
        ["workspace_id", "is_draft", sa.text("draft_last_saved_at DESC")],
        unique=False,
        postgresql_where=sa.text("is_draft = true"),
    )

    # Index 3: Appointment linkage lookup
    # Query: "Get session linked to appointment Y"
    # Expected p95: <50ms
    op.create_index(
        "ix_sessions_appointment",
        "sessions",
        ["appointment_id"],
        unique=False,
        postgresql_where=sa.text("appointment_id IS NOT NULL"),
    )

    # Index 4: Active sessions (soft delete filter)
    # Query: "Get all active (non-deleted) sessions in workspace X"
    # Partial index for performance (most queries filter deleted_at IS NULL)
    op.create_index(
        "ix_sessions_workspace_active",
        "sessions",
        ["workspace_id", sa.text("session_date DESC")],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ========================================================================
    # PERFORMANCE INDEXES FOR SESSION_ATTACHMENTS TABLE
    # ========================================================================

    # Index 1: Attachment list for session
    # Query: "Get all attachments for session X"
    op.create_index(
        "ix_session_attachments_session",
        "session_attachments",
        ["session_id", sa.text("created_at DESC")],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Index 2: Workspace scoping (for multi-tenant queries)
    op.create_index(
        "ix_session_attachments_workspace",
        "session_attachments",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop sessions and session_attachments tables."""
    # Drop indexes explicitly (for clarity)
    # session_attachments indexes
    op.drop_index("ix_session_attachments_workspace", table_name="session_attachments")
    op.drop_index("ix_session_attachments_session", table_name="session_attachments")

    # sessions indexes
    op.drop_index("ix_sessions_workspace_active", table_name="sessions")
    op.drop_index("ix_sessions_appointment", table_name="sessions")
    op.drop_index("ix_sessions_workspace_draft", table_name="sessions")
    op.drop_index("ix_sessions_workspace_client_date", table_name="sessions")

    # Drop tables (attachments first due to foreign key dependency)
    op.drop_table("session_attachments")
    op.drop_table("sessions")
