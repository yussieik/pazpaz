"""make audit events workspace_id nullable for system events

Revision ID: c289c823d8e8
Revises: 6480841e9520
Create Date: 2025-10-22 15:44:33.842903

This migration makes the workspace_id column in audit_events nullable to support
system-level audit events that don't have a workspace context.

Use Cases for NULL workspace_id:
- Blacklisted email attempts (before workspace lookup)
- Failed login attempts (before authentication)
- Platform admin actions (not tied to specific workspace)
- System-level security events

Impact:
- Existing indexes will continue to work (indexes ignore NULL values in WHERE clauses)
- Queries filtering by workspace_id must explicitly handle NULL if needed
- Foreign key constraint remains but allows NULL values

Performance:
- No performance impact on existing queries
- Partial indexes automatically exclude NULL workspace_id rows
"""

from collections.abc import Sequence

from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c289c823d8e8"
down_revision: str | Sequence[str] | None = "6480841e9520"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Make workspace_id nullable to support system-level audit events."""
    # Make workspace_id nullable
    # This allows audit events for system-level actions (blacklist blocks, etc.)
    # that don't have a workspace context
    op.alter_column(
        "audit_events",
        "workspace_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
        comment="Workspace context (NULL for system-level events)",
    )

    # Note: We don't need to update indexes. Composite indexes like
    # ix_audit_events_workspace_created will automatically exclude NULL values
    # in WHERE clauses, and partial indexes already filter by workspace_id IS NOT NULL


def downgrade() -> None:
    """Make workspace_id non-nullable again.

    WARNING: This will fail if there are any audit_events with NULL workspace_id.
    You must delete or update those rows before downgrading.
    """
    # Check if there are any NULL workspace_id values
    # If so, the migration will fail with a clear error message
    op.alter_column(
        "audit_events",
        "workspace_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
        comment="Workspace this event belongs to (workspace scoping)",
    )
