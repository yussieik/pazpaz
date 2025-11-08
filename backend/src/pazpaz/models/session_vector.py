"""
SessionVector model for AI agent vector embeddings.

This model stores vector embeddings of session SOAP notes for semantic search
and RAG (Retrieval-Augmented Generation) capabilities.

Architecture:
- Each SOAP field (subjective, objective, assessment, plan) gets its own embedding
- Embeddings generated via Cohere embed-v4.0 (1536 dimensions)
- HNSW index for fast similarity search (cosine distance)
- Workspace-scoped for multi-tenant isolation

Security:
- Embeddings contain semantic meaning (lossy transformation of PHI)
- Workspace_id enforced via foreign key and application-level filtering
- Automatic deletion when session or workspace deleted (CASCADE)
"""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.session import Session
    from pazpaz.models.workspace import Workspace


class SessionVector(Base):
    """
    Vector embeddings for session SOAP notes.

    Each row represents one SOAP field embedding from a session.
    A single session with all 4 fields populated will have 4 rows.

    Attributes:
        id: Primary key (UUID)
        workspace_id: Foreign key to workspaces (multi-tenant isolation)
        session_id: Foreign key to sessions (cascade delete)
        field_name: SOAP field name ('subjective', 'objective', 'assessment', 'plan')
        embedding: Vector embedding (1536 dimensions, Cohere embed-v4.0)
        created_at: Timestamp when embedding was generated

    Relationships:
        session: Back-reference to Session model
        workspace: Back-reference to Workspace model

    Indexes:
        - idx_session_vectors_workspace: Workspace isolation (MANDATORY for all queries)
        - idx_session_vectors_session: Session lookup (for deletion cascades)
        - idx_session_vectors_embedding: HNSW index for similarity search (cosine distance)

    Security Notes:
        - All queries MUST filter by workspace_id (multi-tenant isolation)
        - Embeddings are NOT encrypted (lossy transformation, semantic search requires plaintext)
        - Raw SOAP text remains encrypted in sessions table
        - Workspace deletion cascades to vectors (GDPR right to be forgotten)
    """

    __tablename__ = "session_vectors"

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

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # SOAP field identifier
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
    session: Mapped["Session"] = relationship(
        "Session",
        back_populates="vectors",
        lazy="selectin",
    )

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="session_vectors",
        lazy="selectin",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "field_name IN ('subjective', 'objective', 'assessment', 'plan')",
            name="ck_session_vectors_field_name",
        ),
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<SessionVector(id={self.id}, "
            f"session_id={self.session_id}, "
            f"field_name={self.field_name})>"
        )
