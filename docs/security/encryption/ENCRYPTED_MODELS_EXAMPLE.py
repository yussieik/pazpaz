"""
Example: Client model with encrypted fields.

DO NOT APPLY YET - This is a reference example for Week 2 implementation.

This file shows how Client and other models will be updated to use encrypted
fields in Week 2 when implementing SOAP Notes feature. The encryption layer
is being built in Week 1 Day 4 and will be applied to models in Week 2.

Migration Strategy:
    1. Week 1 Day 4: Build encryption utilities and SQLAlchemy types (current)
    2. Week 2 Day 1: Create Alembic migration to change column types
    3. Week 2 Day 2: Apply migration and validate encryption works
    4. Week 2 Day 3: Implement SOAP Notes with encrypted fields from start

Migration Example (Week 2):
    # Alembic migration (versions/XXXX_encrypt_client_pii.py)

    def upgrade():
        # Add new encrypted columns
        op.add_column('clients',
            sa.Column('first_name_encrypted', LargeBinary(), nullable=True))
        op.add_column('clients',
            sa.Column('last_name_encrypted', LargeBinary(), nullable=True))
        op.add_column('clients',
            sa.Column('email_encrypted', LargeBinary(), nullable=True))

        # Migrate data (encrypt existing plaintext)
        # This requires a data migration script run after schema change

        # Drop old columns and rename encrypted columns
        op.drop_column('clients', 'first_name')
        op.drop_column('clients', 'last_name')
        op.drop_column('clients', 'email')

        op.alter_column('clients', 'first_name_encrypted',
            new_column_name='first_name')
        # ... repeat for other fields

Fields to Encrypt by Priority:

HIGH PRIORITY (PHI - Protected Health Information):
    - medical_history: Text field with sensitive medical data
    - notes: General notes may contain PHI
    - address: Physical address is PII

MEDIUM PRIORITY (PII - Personally Identifiable Information):
    - first_name: Required for client identification
    - last_name: Required for client identification
    - email: Contact information
    - phone: Contact information
    - emergency_contact_name: Emergency contact details
    - emergency_contact_phone: Emergency contact details

LOW PRIORITY (Non-sensitive):
    - date_of_birth: Useful for age calculation, less sensitive alone
    - consent_status: Boolean, not PII
    - is_active: Boolean, not PII
    - tags: Categories, typically not sensitive
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base
from pazpaz.db.types import EncryptedString  # New import for encrypted fields

if TYPE_CHECKING:
    from pazpaz.models.appointment import Appointment
    from pazpaz.models.workspace import Workspace


class ClientEncrypted(Base):
    """
    EXAMPLE: Client model with encrypted PHI/PII fields.

    DO NOT APPLY YET - This is a reference for Week 2 implementation.

    This shows the future state of the Client model after applying encryption
    to sensitive fields. Compare with current Client model to see changes:
    - String columns → EncryptedString columns for PII/PHI
    - Database storage changes from VARCHAR/TEXT → BYTEA
    - Application code remains unchanged (transparent encryption)
    """

    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ==========================================
    # ENCRYPTED FIELDS (Changed from String/Text to EncryptedString)
    # ==========================================

    # BEFORE (Week 1):
    #   first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # AFTER (Week 2):
    first_name: Mapped[str] = mapped_column(
        EncryptedString(255),  # Encrypted at rest
        nullable=False,
        comment="Client first name (PII - encrypted at rest)",
    )

    # BEFORE (Week 1):
    #   last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # AFTER (Week 2):
    last_name: Mapped[str] = mapped_column(
        EncryptedString(255),  # Encrypted at rest
        nullable=False,
        comment="Client last name (PII - encrypted at rest)",
    )

    # BEFORE (Week 1):
    #   email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # AFTER (Week 2):
    email: Mapped[str | None] = mapped_column(
        EncryptedString(255),  # Encrypted at rest
        nullable=True,
        comment="Client email (PII - encrypted at rest)",
    )

    # BEFORE (Week 1):
    #   phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # AFTER (Week 2):
    phone: Mapped[str | None] = mapped_column(
        EncryptedString(50),  # Encrypted at rest
        nullable=True,
        comment="Client phone (PII - encrypted at rest)",
    )

    # BEFORE (Week 1):
    #   address: Mapped[str | None] = mapped_column(Text, nullable=True)
    # AFTER (Week 2):
    address: Mapped[str | None] = mapped_column(
        EncryptedString(500),  # Encrypted at rest
        nullable=True,
        comment="Client's physical address (PII - encrypted at rest)",
    )

    # BEFORE (Week 1):
    #   medical_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    # AFTER (Week 2):
    medical_history: Mapped[str | None] = mapped_column(
        EncryptedString(5000),  # Encrypted at rest, supports long medical notes
        nullable=True,
        comment="Relevant medical history and conditions (PHI - encrypted at rest)",
    )

    # BEFORE (Week 1):
    #   emergency_contact_name: Mapped[str | None] = mapped_column(String(255), ...)
    # AFTER (Week 2):
    emergency_contact_name: Mapped[str | None] = mapped_column(
        EncryptedString(255),  # Encrypted at rest
        nullable=True,
        comment="Name of emergency contact person (PII - encrypted at rest)",
    )

    # BEFORE (Week 1):
    #   emergency_contact_phone: Mapped[str | None] = mapped_column(String(50), ...)
    # AFTER (Week 2):
    emergency_contact_phone: Mapped[str | None] = mapped_column(
        EncryptedString(50),  # Encrypted at rest
        nullable=True,
        comment="Phone number of emergency contact (PII - encrypted at rest)",
    )

    # BEFORE (Week 1):
    #   notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # AFTER (Week 2):
    notes: Mapped[str | None] = mapped_column(
        EncryptedString(5000),  # Encrypted at rest
        nullable=True,
        comment="General notes about the client (may contain PHI - encrypted at rest)",
    )

    # ==========================================
    # NON-ENCRYPTED FIELDS (Remain unchanged)
    # ==========================================

    # date_of_birth: Consider encryption based on threat model
    # For now, keep as plaintext for age calculations and filtering
    date_of_birth: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    # Boolean flags don't need encryption
    consent_status: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Client consent to store and process data",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Active status (soft delete flag)",
    )

    # Tags array - typically not sensitive, keep plaintext for querying
    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)),
        nullable=True,
        comment="Tags for categorization and filtering",
    )

    # Timestamps - metadata, not PII
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

    # Relationships (unchanged)
    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        back_populates="clients",
    )
    appointments: Mapped[list[Appointment]] = relationship(
        "Appointment",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    # ==========================================
    # IMPORTANT: Index Strategy Changes
    # ==========================================
    #
    # LIMITATION: Cannot create indexes on encrypted fields!
    # Encrypted data is random bytes - indexes would be useless.
    #
    # BEFORE (Week 1):
    #   Index("ix_clients_workspace_lastname_firstname", "workspace_id",
    #         "last_name", "first_name")
    #   Index("ix_clients_workspace_email", "workspace_id", "email")
    #
    # AFTER (Week 2):
    #   - REMOVE indexes on encrypted fields (last_name, first_name, email)
    #   - Client search MUST use full table scan within workspace
    #   - Consider searchable encryption or tokenization if performance issues
    #   - For MVP: workspace scoping limits table size, scans are acceptable
    #
    # Alternative strategies for search (if needed in future):
    #   1. Separate search_tokens table with hashed/tokenized names
    #   2. Full-text search on application-side after decryption
    #   3. Searchable encryption schemes (more complex, research needed)

    __table_args__ = (
        # Keep workspace + updated_at index (both plaintext)
        Index(
            "ix_clients_workspace_updated",
            "workspace_id",
            "updated_at",
        ),
        # Keep partial index for active clients
        Index(
            "ix_clients_workspace_active",
            "workspace_id",
            "is_active",
            postgresql_where=sa.text("is_active = true"),
        ),
        {"comment": "Clients with encrypted PII/PHI fields"},
    )

    @property
    def full_name(self) -> str:
        """
        Return full name of the client.

        This property works transparently with encrypted fields.
        first_name and last_name are decrypted automatically by SQLAlchemy
        when accessed, so this method doesn't need to change.
        """
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Client(id={self.id}, name={self.full_name})>"


# ==========================================
# FUTURE: Session (SOAP Notes) Model with Encryption
# ==========================================
#
# This model doesn't exist yet, will be created in Week 2.
# Example of how encrypted fields would be used from the start:


class SessionExample(Base):
    """
    EXAMPLE: Session model with encrypted SOAP notes.

    This model will be created in Week 2 with encrypted fields from the start
    (no migration needed - new table).
    """

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False
    )

    # SOAP fields - ALL ENCRYPTED (PHI)
    subjective: Mapped[str | None] = mapped_column(
        EncryptedString(5000),  # Client-reported symptoms
        nullable=True,
        comment="Subjective (client-reported symptoms) - PHI encrypted at rest",
    )

    objective: Mapped[str | None] = mapped_column(
        EncryptedString(5000),  # Therapist findings
        nullable=True,
        comment="Objective (therapist findings) - PHI encrypted at rest",
    )

    assessment: Mapped[str | None] = mapped_column(
        EncryptedString(5000),  # Clinical assessment
        nullable=True,
        comment="Assessment (clinical evaluation) - PHI encrypted at rest",
    )

    plan: Mapped[str | None] = mapped_column(
        EncryptedString(5000),  # Treatment plan
        nullable=True,
        comment="Plan (treatment plan) - PHI encrypted at rest",
    )

    # Timestamps (metadata, not encrypted)
    session_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        # Index on workspace and session_date (both plaintext) for chronological queries
        Index("ix_sessions_workspace_date", "workspace_id", "session_date"),
        {"comment": "SOAP session notes with encrypted PHI"},
    )


# ==========================================
# Application Code Examples (Transparent Usage)
# ==========================================

"""
# Example 1: Create a client with encrypted fields
# The encryption happens automatically - no manual encrypt() calls needed

from pazpaz.models.client import Client
from pazpaz.db.session import get_session

async def create_client_example():
    async with get_session() as session:
        client = Client(
            workspace_id=workspace_id,
            first_name="John",  # Will be encrypted automatically
            last_name="Doe",     # Will be encrypted automatically
            email="john@example.com",  # Will be encrypted automatically
            medical_history="Patient has diabetes and hypertension",  # Encrypted
        )
        session.add(client)
        await session.commit()
        return client


# Example 2: Query and access encrypted fields
# The decryption happens automatically - no manual decrypt() calls needed

async def get_client_example(client_id: uuid.UUID):
    async with get_session() as session:
        client = await session.get(Client, client_id)

        # All fields are automatically decrypted when accessed
        print(client.full_name)  # "John Doe" (decrypted)
        print(client.email)  # "john@example.com" (decrypted)
        print(client.medical_history)  # "Patient has..." (decrypted)


# Example 3: Update encrypted fields
# Updates work transparently - encryption happens on commit

async def update_client_example(client_id: uuid.UUID):
    async with get_session() as session:
        client = await session.get(Client, client_id)

        # Update fields normally - will be re-encrypted on commit
        client.email = "newemail@example.com"  # Will be encrypted on commit
        client.medical_history += " Also has allergies."  # Will be encrypted

        await session.commit()


# Example 4: LIMITATION - Cannot search encrypted fields directly
# This WILL NOT WORK after encryption:

async def search_by_name_broken(last_name: str):
    # THIS BREAKS: Cannot use LIKE on encrypted fields
    query = select(Client).where(Client.last_name.like(f"%{last_name}%"))
    # This will search encrypted bytes, not plaintext - results will be wrong!


# Example 5: WORKAROUND - Search by loading all clients in workspace

async def search_by_name_working(workspace_id: uuid.UUID, search_term: str):
    async with get_session() as session:
        # Load all clients in workspace (workspace scoping limits size)
        query = select(Client).where(Client.workspace_id == workspace_id)
        result = await session.execute(query)
        clients = result.scalars().all()

        # Filter in application code after decryption
        search_lower = search_term.lower()
        matching_clients = [
            c for c in clients
            if search_lower in c.first_name.lower()
            or search_lower in c.last_name.lower()
        ]

        return matching_clients
"""
