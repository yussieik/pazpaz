"""add_check_constraint_finalized_sessions_not_draft

Revision ID: 11a114ee018b
Revises: 2de77d93d190
Create Date: 2025-10-16 12:51:22.046076

Add CHECK constraint to prevent finalized sessions from being marked as draft.
This prevents a bug where the autosave endpoint would set is_draft = true
unconditionally, reverting finalized sessions back to draft status.

CONSTRAINT LOGIC:
- If finalized_at IS NULL → is_draft can be anything (allows drafts)
- If finalized_at IS NOT NULL → is_draft MUST be false (enforces finalized)

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "11a114ee018b"
down_revision: str | Sequence[str] | None = "2de77d93d190"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add CHECK constraint: finalized sessions cannot be drafts
    # (finalized_at IS NULL) OR (is_draft = false)
    op.create_check_constraint(
        "ck_sessions_finalized_not_draft",
        "sessions",
        "(finalized_at IS NULL) OR (is_draft = false)",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_sessions_finalized_not_draft", "sessions", type_="check")
