"""upgrade_embeddings_to_1536_dimensions_for_embed_v4

Upgrades vector embeddings from 1024 to 1536 dimensions for Cohere embed-v4.0.

This migration:
1. Drops existing HNSW index (incompatible with dimension change)
2. Converts embedding column from vector(1024) to vector(1536)
3. Recreates HNSW index with same parameters

IMPORTANT: This migration will DELETE all existing embeddings because
pgvector cannot resize vectors in place. All sessions will need to be
re-embedded after this migration.

Revision ID: 5407ac8bbc2b
Revises: 154da4b93b1d
Create Date: 2025-11-06 19:19:50.090658
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5407ac8bbc2b"
down_revision: str | Sequence[str] | None = "154da4b93b1d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Upgrade embeddings from 1024 to 1536 dimensions for embed-v4.0.

    WARNING: This will delete all existing session_vectors rows because
    pgvector cannot resize vector dimensions in place.
    """
    # Step 1: Drop HNSW index (must be dropped before column type change)
    op.execute("DROP INDEX IF EXISTS idx_session_vectors_embedding")

    # Step 2: Delete all existing vectors (dimension mismatch)
    # This is necessary because pgvector cannot convert vector(1024) to vector(1536)
    op.execute("DELETE FROM session_vectors")

    # Step 3: Convert embedding column from vector(1024) to vector(1536)
    op.execute("ALTER TABLE session_vectors ALTER COLUMN embedding TYPE vector(1536)")

    # Step 4: Recreate HNSW index with same parameters
    # m=16 (connections per vector), ef_construction=64 (candidate pool size)
    op.execute(
        """
        CREATE INDEX idx_session_vectors_embedding
        ON session_vectors
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    """
    Downgrade embeddings from 1536 back to 1024 dimensions.

    WARNING: This will delete all existing session_vectors rows.
    """
    # Step 1: Drop HNSW index
    op.execute("DROP INDEX IF EXISTS idx_session_vectors_embedding")

    # Step 2: Delete all existing vectors (dimension mismatch)
    op.execute("DELETE FROM session_vectors")

    # Step 3: Convert embedding column from vector(1536) back to vector(1024)
    op.execute("ALTER TABLE session_vectors ALTER COLUMN embedding TYPE vector(1024)")

    # Step 4: Recreate HNSW index
    op.execute(
        """
        CREATE INDEX idx_session_vectors_embedding
        ON session_vectors
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )
