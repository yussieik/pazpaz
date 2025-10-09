"""Workspace model - therapist account context."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.appointment import Appointment
    from pazpaz.models.audit_event import AuditEvent
    from pazpaz.models.client import Client
    from pazpaz.models.location import Location
    from pazpaz.models.service import Service
    from pazpaz.models.session import Session
    from pazpaz.models.user import User


class Workspace(Base):
    """
    Workspace represents a therapist's account context.

    All data in the system is scoped to a workspace to ensure privacy
    and data isolation between different therapists/practices.
    """

    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    users: Mapped[list[User]] = relationship(
        "User",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    clients: Mapped[list[Client]] = relationship(
        "Client",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    appointments: Mapped[list[Appointment]] = relationship(
        "Appointment",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    services: Mapped[list[Service]] = relationship(
        "Service",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    locations: Mapped[list[Location]] = relationship(
        "Location",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(
        "AuditEvent",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list[Session]] = relationship(
        "Session",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Workspace(id={self.id}, name={self.name})>"
