"""
ClientVector model for AI agent vector embeddings of client data.

This model stores vector embeddings of client medical history and notes for semantic
search and RAG (Retrieval-Augmented Generation) capabilities.

Architecture:
- Each client field (medical_history, notes) gets its own embedding
- Embeddings generated via Cohere embed-v4.0 (1536 dimensions)
- HNSW index for fast similarity search (cosine distance)
- Workspace-scoped for multi-tenant isolation

Security:
- Embeddings contain semantic meaning (lossy transformation of PHI)
- Workspace_id enforced via foreign key and application-level filtering
- Automatic deletion when client or workspace deleted (CASCADE)
"""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.client import Client
    from pazpaz.models.workspace import Workspace


class ClientVector(Base):
    """
    Vector embeddings for client medical history and notes.

    Each row represents one field embedding from a client profile.
    A client with both medical_history and notes will have 2 rows.

    Attributes:
        id: Primary key (UUID)
        workspace_id: Foreign key to workspaces (multi-tenant isolation)
        client_id: Foreign key to clients (cascade delete)
        field_name: Client field name ('medical_history', 'notes')
        embedding: Vector embedding (1536 dimensions, Cohere embed-v4.0)
        created_at: Timestamp when embedding was generated

    Relationships:
        client: Back-reference to Client model
        workspace: Back-reference to Workspace model

    Indexes:
        - idx_client_vectors_workspace: Workspace isolation (MANDATORY for all queries)
        - idx_client_vectors_client: Client lookup (for deletion cascades and updates)
        - idx_client_vectors_embedding: HNSW index for similarity search (cosine distance)
        - uq_client_vectors_client_field: Unique constraint (one embedding per client field)

    Security Notes:
        - All queries MUST filter by workspace_id (multi-tenant isolation)
        - Embeddings are NOT encrypted (lossy transformation, semantic search requires plaintext)
        - Raw client data remains encrypted in clients table
        - Workspace deletion cascades to vectors (GDPR right to be forgotten)
    """

    __tablename__ = "client_vectors"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # Foreign keys
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Client field identifier
    field_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # Vector embedding (1536 dimensions for Cohere embed-v4.0)
    embedding: Mapped[Vector] = mapped_column(
        Vector(1536),
        nullable=False,
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    # Relationships
    client: Mapped["Client"] = relationship(
        "Client",
        back_populates="vectors",
        lazy="selectin",
    )

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="client_vectors",
        lazy="selectin",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "field_name IN ('medical_history', 'notes')",
            name="ck_client_vectors_field_name",
        ),
        UniqueConstraint(
            "client_id",
            "field_name",
            name="uq_client_vectors_client_field",
        ),
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<ClientVector(id={self.id}, "
            f"client_id={self.client_id}, "
            f"field_name={self.field_name})>"
        )
