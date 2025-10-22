"""create_session_versions_table

Creates session_versions table to track version history of session note amendments.

This table stores historical snapshots of SOAP notes when finalized or amended,
enabling:
1. Complete amendment audit trail (legal requirement)
2. Version comparison for clinical review
3. Recovery capability if needed

All PHI fields are encrypted with AES-256-GCM using EncryptedString type.

Revision ID: 9262695391b3
Revises: 03742492d865
Create Date: 2025-10-10 13:03:36.629226

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9262695391b3"
down_revision: str | Sequence[str] | None = "03742492d865"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create session_versions table for version history."""
    op.create_table(
        "session_versions",
        # Primary key
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Unique identifier for the version",
        ),
        # Foreign keys
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
            comment="Session this version belongs to",
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=False,
            comment="User who created this version (who finalized or amended)",
        ),
        # Version metadata
        sa.Column(
            "version_number",
            sa.Integer(),
            nullable=False,
            comment="Version number (1 = original, 2+ = amendments)",
        ),
        # SOAP Notes PHI Columns (ENCRYPTED as BYTEA)
        # These match the sessions table structure
        sa.Column(
            "subjective",
            postgresql.BYTEA(),
            nullable=True,
            comment="ENCRYPTED: Subjective snapshot (patient-reported symptoms) - AES-256-GCM",
        ),
        sa.Column(
            "objective",
            postgresql.BYTEA(),
            nullable=True,
            comment="ENCRYPTED: Objective snapshot (therapist observations) - AES-256-GCM",
        ),
        sa.Column(
            "assessment",
            postgresql.BYTEA(),
            nullable=True,
            comment="ENCRYPTED: Assessment snapshot (diagnosis/evaluation) - AES-256-GCM",
        ),
        sa.Column(
            "plan",
            postgresql.BYTEA(),
            nullable=True,
            comment="ENCRYPTED: Plan snapshot (treatment plan) - AES-256-GCM",
        ),
        # Timestamp
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="When this version was created (finalized or amended)",
        ),
        # Constraints
        sa.UniqueConstraint(
            "session_id",
            "version_number",
            name="uq_session_version_number",
        ),
        comment="Version history for session notes - tracks amendments with encrypted PHI snapshots",
    )

    # Create index for fetching version history
    op.create_index(
        "ix_session_versions_session_version",
        "session_versions",
        ["session_id", "version_number"],
    )


def downgrade() -> None:
    """Drop session_versions table."""
    op.drop_index("ix_session_versions_session_version", table_name="session_versions")
    op.drop_table("session_versions")
