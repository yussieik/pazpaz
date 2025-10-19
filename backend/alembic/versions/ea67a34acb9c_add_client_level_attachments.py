"""add_client_level_attachments

This migration extends the session_attachments table to support client-level files
in addition to session-level files. Changes include:

1. Add client_id column (required for all attachments)
2. Make session_id nullable (NULL for client-level files)
3. Add indexes for client-level queries
4. Backfill client_id from existing session records

Revision ID: ea67a34acb9c
Revises: 11a114ee018b
Create Date: 2025-10-19 10:54:39.843004

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "ea67a34acb9c"
down_revision: str | Sequence[str] | None = "11a114ee018b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Upgrade schema to support client-level attachments.

    Steps:
    1. Add client_id column (temporarily nullable for backfill)
    2. Backfill client_id from sessions table for existing records
    3. Make client_id NOT NULL
    4. Make session_id nullable
    5. Add indexes for client queries
    6. Update comments
    """
    # Step 1: Add client_id column (temporarily nullable)
    op.add_column(
        "session_attachments",
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Client this attachment belongs to (required for all attachments)",
        ),
    )

    # Step 2: Backfill client_id from sessions table
    # This sets client_id for all existing session-level attachments
    op.execute(
        """
        UPDATE session_attachments sa
        SET client_id = s.client_id
        FROM sessions s
        WHERE sa.session_id = s.id
        """
    )

    # Step 3: Make client_id NOT NULL and add foreign key
    op.alter_column(
        "session_attachments",
        "client_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.create_foreign_key(
        "session_attachments_client_id_fkey",
        "session_attachments",
        "clients",
        ["client_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Step 4: Make session_id nullable (allows client-level files)
    op.alter_column(
        "session_attachments",
        "session_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
        comment="NULL for client-level attachments (e.g., intake forms, consent docs)",
    )

    # Step 5: Add indexes for client queries
    # Index for listing all attachments for a client
    op.create_index(
        "ix_session_attachments_client_created",
        "session_attachments",
        ["client_id", "created_at"],
    )
    # Composite index for workspace + client queries
    op.create_index(
        "ix_session_attachments_workspace_client",
        "session_attachments",
        ["workspace_id", "client_id"],
    )

    # Step 6: Add client_id index for foreign key constraint
    op.create_index(
        "ix_session_attachments_client_id",
        "session_attachments",
        ["client_id"],
    )


def downgrade() -> None:
    """
    Downgrade schema to remove client-level attachment support.

    WARNING: This will DELETE all client-level attachments (where session_id IS NULL)
    before reverting the schema changes.
    """
    # Step 1: Delete all client-level attachments (session_id IS NULL)
    # This is necessary because session_id will become NOT NULL again
    op.execute(
        """
        DELETE FROM session_attachments
        WHERE session_id IS NULL
        """
    )

    # Step 2: Drop indexes
    op.drop_index("ix_session_attachments_client_id", table_name="session_attachments")
    op.drop_index(
        "ix_session_attachments_workspace_client", table_name="session_attachments"
    )
    op.drop_index(
        "ix_session_attachments_client_created", table_name="session_attachments"
    )

    # Step 3: Make session_id NOT NULL again
    op.alter_column(
        "session_attachments",
        "session_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )

    # Step 4: Drop foreign key constraint
    op.drop_constraint(
        "session_attachments_client_id_fkey",
        "session_attachments",
        type_="foreignkey",
    )

    # Step 5: Drop client_id column
    op.drop_column("session_attachments", "client_id")
