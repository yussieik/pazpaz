"""add_workspace_storage_quota_fields

This migration adds storage quota tracking to workspaces to prevent storage abuse
and enforce resource limits per HIPAA §164.308(a)(7)(ii)(B).

Changes:
1. Add storage_used_bytes column - tracks total bytes used by all files
2. Add storage_quota_bytes column - maximum storage allowed (default 10 GB)
3. Both columns indexed for quota enforcement queries

Revision ID: d1f764670a60
Revises: ea67a34acb9c
Create Date: 2025-10-19 17:47:46.192463

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd1f764670a60'
down_revision: str | Sequence[str] | None = 'ea67a34acb9c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Add storage quota fields to workspaces table.

    Steps:
    1. Add storage_used_bytes column (default 0)
    2. Add storage_quota_bytes column (default 10 GB)
    3. Add index for quota enforcement queries
    """
    # Step 1: Add storage_used_bytes column
    # BigInteger supports up to 9,223,372,036,854,775,807 bytes (~9 exabytes)
    op.add_column(
        'workspaces',
        sa.Column(
            'storage_used_bytes',
            sa.BigInteger(),
            nullable=False,
            server_default='0',
            comment='Total bytes used by all files in workspace'
        )
    )

    # Step 2: Add storage_quota_bytes column
    # Default: 10 GB = 10,737,418,240 bytes
    op.add_column(
        'workspaces',
        sa.Column(
            'storage_quota_bytes',
            sa.BigInteger(),
            nullable=False,
            server_default='10737418240',  # 10 GB in bytes
            comment='Maximum storage allowed for workspace in bytes'
        )
    )

    # Step 3: Add index for quota enforcement queries
    # This enables fast lookups when checking quota before uploads
    op.create_index(
        'ix_workspaces_storage_quota',
        'workspaces',
        ['storage_used_bytes', 'storage_quota_bytes']
    )


def downgrade() -> None:
    """
    Remove storage quota fields from workspaces table.

    WARNING: This will permanently delete storage tracking data.
    """
    # Step 1: Drop index
    op.drop_index('ix_workspaces_storage_quota', table_name='workspaces')

    # Step 2: Drop storage columns
    op.drop_column('workspaces', 'storage_quota_bytes')
    op.drop_column('workspaces', 'storage_used_bytes')
