"""add_pgvector_extension_and_session_vectors_table

Revision ID: 154da4b93b1d
Revises: 2941a42b2723
Create Date: 2025-11-06 17:43:04.192878

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "154da4b93b1d"
down_revision: str | Sequence[str] | None = "2941a42b2723"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Install pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create session_vectors table
    op.create_table(
        "session_vectors",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column(
            "field_name",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name="fk_session_vectors_session_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_session_vectors_workspace_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "field_name IN ('subjective', 'objective', 'assessment', 'plan')",
            name="ck_session_vectors_field_name",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_session_vectors"),
    )

    # Add embedding column as ARRAY FLOAT (will convert to vector type next)
    op.add_column(
        "session_vectors", sa.Column("embedding", sa.ARRAY(sa.Float()), nullable=False)
    )

    # Convert embedding column to vector(1024) type using pgvector
    # This must be done via raw SQL after column exists
    op.execute(
        "ALTER TABLE session_vectors ALTER COLUMN embedding TYPE vector(1024) USING embedding::vector(1024)"
    )

    # Create indexes
    # 1. Workspace isolation index (MANDATORY for all queries)
    op.create_index(
        "idx_session_vectors_workspace",
        "session_vectors",
        ["workspace_id"],
    )

    # 2. Session lookup index (for deletion cascades)
    op.create_index(
        "idx_session_vectors_session",
        "session_vectors",
        ["session_id"],
    )

    # 3. HNSW index for vector similarity search (cosine distance)
    # Parameters: m=16 (connections per vector), ef_construction=64 (candidate pool size)
    # These params provide good balance between recall and build time for <100k vectors
    op.execute(
        """
        CREATE INDEX idx_session_vectors_embedding
        ON session_vectors
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop table (cascade will drop indexes automatically)
    op.drop_table("session_vectors")

    # Drop pgvector extension (only if no other tables use it)
    op.execute("DROP EXTENSION IF EXISTS vector CASCADE")
