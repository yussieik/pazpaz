"""rename_completed_to_attended

Rename appointment status from 'completed' to 'attended' for clarity.

This migration addresses user confusion where "completed" was ambiguous:
- Users thought it meant "all work is done" (documentation complete)
- It actually meant "the appointment occurred" (client showed up)

"Attended" is clearer and matches industry standards (TherapyNotes, etc).

SAFE MIGRATION: Database uses VARCHAR(50), not native enum, so this is
a simple string replacement with no schema changes and no data loss.

Revision ID: 74858d29f6e5
Revises: a5ac11f65d20
Create Date: 2025-10-29 12:51:53.351363

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "74858d29f6e5"
down_revision: str | Sequence[str] | None = "a5ac11f65d20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Rename appointment status 'completed' to 'attended'.

    This is a safe string replacement with no data loss.
    Database uses VARCHAR(50), not native enum, so this is a simple UPDATE.
    """
    # Update existing data
    op.execute(
        """
        UPDATE appointments
        SET status = 'attended'
        WHERE status = 'completed'
    """
    )

    # Log the change for verification
    connection = op.get_bind()
    result = connection.execute(
        sa.text("SELECT COUNT(*) FROM appointments WHERE status = 'attended'")
    )
    count = result.scalar()
    print(f"Migration complete: {count} appointments updated to 'attended'")


def downgrade() -> None:
    """
    Rollback: Change 'attended' back to 'completed'.

    This allows safe rollback if needed.
    """
    op.execute(
        """
        UPDATE appointments
        SET status = 'completed'
        WHERE status = 'attended'
    """
    )
