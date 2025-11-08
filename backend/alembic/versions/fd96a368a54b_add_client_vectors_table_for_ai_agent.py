"""add_client_vectors_table_for_ai_agent

Adds client_vectors table for semantic search on client medical history and notes.

This enables the AI agent to answer questions about client baseline data (medical
history, therapist notes) in addition to session SOAP notes.

Revision ID: fd96a368a54b
Revises: 5407ac8bbc2b
Create Date: 2025-11-07 12:43:03.173549

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fd96a368a54b"
down_revision: str | Sequence[str] | None = "5407ac8bbc2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create client_vectors table
    op.create_table(
        "client_vectors",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
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
            ["client_id"],
            ["clients.id"],
            name="fk_client_vectors_client_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_client_vectors_workspace_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "field_name IN ('medical_history', 'notes')",
            name="ck_client_vectors_field_name",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_client_vectors"),
    )

    # Add embedding column as ARRAY FLOAT (will convert to vector type next)
    op.add_column(
        "client_vectors", sa.Column("embedding", sa.ARRAY(sa.Float()), nullable=False)
    )

    # Convert embedding column to vector(1536) type using pgvector
    # Using embed-v4.0 dimensions (same as session_vectors)
    op.execute(
        "ALTER TABLE client_vectors ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)"
    )

    # Create indexes
    # 1. Workspace isolation index (MANDATORY for all queries)
    op.create_index(
        "idx_client_vectors_workspace",
        "client_vectors",
        ["workspace_id"],
    )

    # 2. Client lookup index (for deletion cascades and updates)
    op.create_index(
        "idx_client_vectors_client",
        "client_vectors",
        ["client_id"],
    )

    # 3. Unique constraint to prevent duplicate embeddings for same client field
    op.create_unique_constraint(
        "uq_client_vectors_client_field",
        "client_vectors",
        ["client_id", "field_name"],
    )

    # 4. HNSW index for vector similarity search (cosine distance)
    # Parameters: m=16 (connections per vector), ef_construction=64 (candidate pool size)
    # Same parameters as session_vectors for consistency
    op.execute(
        """
        CREATE INDEX idx_client_vectors_embedding
        ON client_vectors
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop table (cascade will drop indexes and constraints automatically)
    op.drop_table("client_vectors")
