"""add_google_calendar_tokens_table

Revision ID: 75c10af3f2de
Revises: f90e9a7e0831
Create Date: 2025-10-28 14:32:16.014106

This migration creates the google_calendar_tokens table for Phase 1 (Task 1.1)
of the Google Calendar integration feature.

The google_calendar_tokens table stores OAuth 2.0 access and refresh tokens for
Google Calendar API integration, enabling two-way calendar sync between PazPaz
appointments and users' Google Calendar accounts.

Security Requirements:
- access_token and refresh_token stored as BYTEA with AES-256-GCM encryption
- Workspace scoping enforced via foreign key CASCADE
- One token record per user per workspace (unique constraint)
- Audit trail via created_at/updated_at timestamps

Token Lifecycle:
- access_token: Short-lived (typically 1 hour), used for API calls
- refresh_token: Long-lived (until user revokes), used to obtain new access tokens
- token_expiry: Timestamp when access token expires (UTC)

Key Design Decisions:
- BYTEA column type for encrypted tokens (not TEXT)
- No indexes on encrypted columns (not searchable by content)
- JSONB for scopes and calendar_list (flexible schema)
- enabled flag for pause/resume sync without deleting tokens
- Composite index (workspace_id, enabled) for active token lookups
- Unique constraint (workspace_id, user_id) enforces one token per user
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "75c10af3f2de"
down_revision: str | Sequence[str] | None = "f90e9a7e0831"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create google_calendar_tokens table with encrypted OAuth credentials."""
    op.create_table(
        "google_calendar_tokens",
        # Primary key
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Unique identifier for the token record",
        ),
        # Foreign keys (workspace scoping and user ownership)
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            comment="Workspace this token belongs to (workspace scoping)",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="User who authorized Google Calendar access",
        ),
        # ENCRYPTED OAuth Tokens (stored as BYTEA)
        # These columns will be handled by EncryptedString SQLAlchemy type in the model
        sa.Column(
            "access_token",
            postgresql.BYTEA(),
            nullable=False,
            comment="ENCRYPTED: OAuth 2.0 access token (short-lived, ~1 hour) - AES-256-GCM",
        ),
        sa.Column(
            "refresh_token",
            postgresql.BYTEA(),
            nullable=False,
            comment="ENCRYPTED: OAuth 2.0 refresh token (long-lived, until revoked) - AES-256-GCM",
        ),
        # Token metadata (non-encrypted)
        sa.Column(
            "token_expiry",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When the access token expires (timezone-aware UTC)",
        ),
        sa.Column(
            "scopes",
            postgresql.JSONB(),
            nullable=False,
            comment='OAuth scopes granted (e.g., ["https://www.googleapis.com/auth/calendar"])',
        ),
        sa.Column(
            "calendar_list",
            postgresql.JSONB(),
            nullable=True,
            comment="Cached list of user's calendars from Google Calendar API",
        ),
        # Sync control
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether sync is active (false = paused, true = active)",
        ),
        # Audit columns
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
            comment="When token was first stored (OAuth authorization completed)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
            comment="When token was last updated (e.g., after token refresh)",
        ),
        # Unique constraint: One token per user per workspace
        sa.UniqueConstraint(
            "workspace_id",
            "user_id",
            name="uq_google_calendar_tokens_workspace_user",
        ),
        # Table comment
        comment="OAuth 2.0 tokens for Google Calendar integration with encrypted credentials",
    )

    # Indexes for performance
    # Index 1: Workspace scoping (all queries filter by workspace_id)
    op.create_index(
        "ix_google_calendar_tokens_workspace_id",
        "google_calendar_tokens",
        ["workspace_id"],
    )

    # Index 2: User ownership lookup
    op.create_index(
        "ix_google_calendar_tokens_user_id",
        "google_calendar_tokens",
        ["user_id"],
    )

    # Index 3: Active token lookups (workspace + enabled filter)
    op.create_index(
        "ix_google_calendar_tokens_workspace_enabled",
        "google_calendar_tokens",
        ["workspace_id", "enabled"],
    )


def downgrade() -> None:
    """Drop google_calendar_tokens table."""
    # Drop indexes first
    op.drop_index(
        "ix_google_calendar_tokens_workspace_enabled",
        table_name="google_calendar_tokens",
    )
    op.drop_index(
        "ix_google_calendar_tokens_user_id",
        table_name="google_calendar_tokens",
    )
    op.drop_index(
        "ix_google_calendar_tokens_workspace_id",
        table_name="google_calendar_tokens",
    )

    # Drop table (CASCADE will handle foreign keys)
    op.drop_table("google_calendar_tokens")
