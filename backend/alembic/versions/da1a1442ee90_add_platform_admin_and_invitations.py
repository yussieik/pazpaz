"""add_platform_admin_and_invitations

Revision ID: da1a1442ee90
Revises: 01a5a73e9841
Create Date: 2025-10-21 18:20:19.809414

Adds platform admin functionality and invitation tracking to User model:
- is_platform_admin: Boolean flag for platform-level access
- invitation_token_hash: SHA256 hash of invitation token (indexed)
- invited_by_platform_admin: Audit trail for invitation source
- invited_at: Timestamp for invitation expiration checks

This enables the platform admin system where platform admins can:
- Access /platform-admin endpoints
- Invite therapists to onboard to the platform
- Track invitation sources for audit purposes
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "da1a1442ee90"
down_revision: str | Sequence[str] | None = "01a5a73e9841"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Add platform admin and invitation fields to users table.

    Adds four new columns:
    - is_platform_admin: Boolean flag (default=False, NOT NULL)
    - invitation_token_hash: SHA256 hash for invitation tokens (indexed)
    - invited_by_platform_admin: Audit trail for invitation source
    - invited_at: Timestamp for invitation expiration checks

    Creates two indexes:
    - idx_users_platform_admin: For fast platform admin queries
    - ix_users_invitation_token_hash: For invitation token lookup
    """
    # Add platform admin flag
    op.add_column(
        "users",
        sa.Column(
            "is_platform_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="True if user can access platform admin panel",
        ),
    )

    # Add invitation token hash (SHA256, 64 hex chars)
    op.add_column(
        "users",
        sa.Column(
            "invitation_token_hash",
            sa.String(length=64),
            nullable=True,
            comment="SHA256 hash of invitation token",
        ),
    )

    # Add invitation source tracking
    op.add_column(
        "users",
        sa.Column(
            "invited_by_platform_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="True if invited by platform admin (not by another user)",
        ),
    )

    # Add invitation timestamp
    op.add_column(
        "users",
        sa.Column(
            "invited_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When invitation was sent",
        ),
    )

    # Create index for platform admin queries
    # NOTE: This is a non-unique index on a boolean column.
    # In production, very few users will be platform admins,
    # making this index efficient for filtering.
    # CONCURRENTLY option removed because it requires running outside
    # a transaction, which complicates testing. For production deployments
    # with large user tables, consider creating this index manually with
    # CONCURRENTLY to avoid table locks.
    op.create_index(
        "idx_users_platform_admin",
        "users",
        ["is_platform_admin"],
        unique=False,
    )

    # Create index for invitation token lookup
    op.create_index(
        op.f("ix_users_invitation_token_hash"),
        "users",
        ["invitation_token_hash"],
        unique=False,
    )


def downgrade() -> None:
    """
    Remove platform admin and invitation fields from users table.

    WARNING: This will permanently delete:
    - Platform admin designations
    - Invitation tokens and tracking data
    Users will need to be re-invited after upgrade.
    """
    # Drop indexes first (before dropping columns they reference)
    op.drop_index(
        op.f("ix_users_invitation_token_hash"),
        table_name="users",
    )
    op.drop_index(
        "idx_users_platform_admin",
        table_name="users",
    )

    # Drop columns in reverse order of creation
    op.drop_column("users", "invited_at")
    op.drop_column("users", "invited_by_platform_admin")
    op.drop_column("users", "invitation_token_hash")
    op.drop_column("users", "is_platform_admin")
