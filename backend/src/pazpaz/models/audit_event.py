"""AuditEvent model - HIPAA-compliant audit logging."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.user import User
    from pazpaz.models.workspace import Workspace


class AuditAction(str, enum.Enum):
    """Audit action types."""

    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    EXPORT = "EXPORT"
    PRINT = "PRINT"
    SHARE = "SHARE"


class ResourceType(str, enum.Enum):
    """Resource types that can be audited."""

    USER = "User"
    CLIENT = "Client"
    APPOINTMENT = "Appointment"
    SESSION = "Session"
    SESSION_ATTACHMENT = "SessionAttachment"
    PLAN_OF_CARE = "PlanOfCare"
    SERVICE = "Service"
    LOCATION = "Location"
    WORKSPACE = "Workspace"


class AuditEvent(Base):
    """
    AuditEvent represents an immutable audit log entry for HIPAA compliance.

    This table maintains a comprehensive audit trail of all data access and
    modifications, with a focus on Protected Health Information (PHI).

    Key Features:
    - Immutable: Cannot be updated or deleted (enforced by database triggers)
    - Workspace-scoped: Most events belong to a workspace (NULL for system-level events)
    - Flexible metadata: JSONB column for additional context (NO PII/PHI)
    - Optimized indexes: Fast queries for compliance reporting

    System-Level Events (workspace_id=NULL):
    - Blacklisted email login attempts
    - Failed authentication before workspace lookup
    - Platform admin actions not tied to specific workspace

    IMPORTANT: This table is append-only. Updates and deletes are prevented
    at the database level to ensure audit trail integrity.
    """

    __tablename__ = "audit_events"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Unique identifier for the audit event",
    )

    # Foreign keys
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Workspace context (NULL for system-level events)",
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who performed the action (NULL for system events)",
    )

    # Event identification
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Event type (e.g., user.login, client.view, session.create)",
    )

    resource_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Type of resource accessed (User, Client, Session, Appointment)",
    )

    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID of the resource being accessed or modified",
    )

    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, native_enum=False, length=20),
        nullable=False,
        index=True,
        comment="Action performed (CREATE, READ, UPDATE, DELETE, etc.)",
    )

    # Request context
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of the user (IPv4 or IPv6)",
    )

    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="User agent string from the request",
    )

    # Flexible metadata storage (NO PII/PHI)
    # Note: Using "event_metadata" to avoid SQLAlchemy reserved "metadata" attribute
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",  # Database column name is still "metadata"
        JSONB,
        nullable=True,
        comment="Additional context (changed_fields, query_params, etc. - NO PII/PHI)",
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
        index=True,
        comment="When the event occurred (immutable)",
    )

    # Relationships
    workspace: Mapped[Workspace | None] = relationship(
        "Workspace",
        back_populates="audit_events",
    )

    user: Mapped[User | None] = relationship(
        "User",
        back_populates="audit_events",
    )

    # Table configuration
    __table_args__ = (
        # Composite index for workspace timeline queries (most common)
        Index(
            "ix_audit_events_workspace_created",
            "workspace_id",
            text("created_at DESC"),
        ),
        # Index for user-specific queries
        Index(
            "ix_audit_events_workspace_user",
            "workspace_id",
            "user_id",
            text("created_at DESC"),
        ),
        # Index for event type filtering
        Index(
            "ix_audit_events_workspace_event_type",
            "workspace_id",
            "event_type",
            text("created_at DESC"),
        ),
        # Index for resource-specific audit trail
        Index(
            "ix_audit_events_resource",
            "resource_type",
            "resource_id",
            text("created_at DESC"),
        ),
        # Partial index for PHI access tracking (HIPAA requirement)
        Index(
            "ix_audit_events_phi_access",
            "workspace_id",
            "resource_type",
            text("created_at DESC"),
            postgresql_where=text(
                "action = 'READ' AND "
                "resource_type IN ('Client', 'Session', 'PlanOfCare')"
            ),
        ),
        {
            "comment": (
                "Immutable audit trail for HIPAA compliance and security monitoring"
            )
        },
    )

    def __repr__(self) -> str:
        """Return string representation of audit event."""
        return (
            f"<AuditEvent(id={self.id}, "
            f"event_type={self.event_type}, "
            f"action={self.action.value}, "
            f"resource={self.resource_type}:{self.resource_id})>"
        )

    @property
    def is_phi_access(self) -> bool:
        """Check if this event represents PHI access."""
        phi_resources = {
            ResourceType.CLIENT.value,
            ResourceType.SESSION.value,
            ResourceType.PLAN_OF_CARE.value,
        }
        return self.action == AuditAction.READ and self.resource_type in phi_resources
