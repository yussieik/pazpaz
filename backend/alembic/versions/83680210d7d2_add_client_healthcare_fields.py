"""add_client_healthcare_fields

Revision ID: 83680210d7d2
Revises: f6092aa0856d
Create Date: 2025-10-02 17:33:07.310293

This migration adds missing fields to the clients table that are required
by the frontend and essential for healthcare practice management:

- address: Client's physical address (PII - requires encryption at rest)
- medical_history: Relevant medical background (PHI - requires encryption at rest)
- emergency_contact_name: Emergency contact person's name
- emergency_contact_phone: Emergency contact phone number
- is_active: Soft delete flag to preserve audit trail

These fields align with standard healthcare intake forms and enable proper
client management without data loss when clients are archived.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "83680210d7d2"
down_revision: str | Sequence[str] | None = "f6092aa0856d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add healthcare-related fields to clients table."""
    # Add address field (PII - should be encrypted at rest in production)
    op.add_column(
        "clients",
        sa.Column(
            "address",
            sa.Text(),
            nullable=True,
            comment="Client's physical address (PII - encrypt at rest)",
        ),
    )

    # Add medical_history field (PHI - MUST be encrypted at rest)
    op.add_column(
        "clients",
        sa.Column(
            "medical_history",
            sa.Text(),
            nullable=True,
            comment="Relevant medical history and conditions (PHI - encrypt at rest)",
        ),
    )

    # Add emergency contact fields
    op.add_column(
        "clients",
        sa.Column(
            "emergency_contact_name",
            sa.String(length=255),
            nullable=True,
            comment="Name of emergency contact person",
        ),
    )
    op.add_column(
        "clients",
        sa.Column(
            "emergency_contact_phone",
            sa.String(length=50),
            nullable=True,
            comment="Phone number of emergency contact",
        ),
    )

    # Add is_active field for soft deletes
    # Default to TRUE for existing clients (they are active by definition)
    op.add_column(
        "clients",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="Active status (soft delete flag)",
        ),
    )

    # Add partial index for active clients (most common query pattern)
    # This improves performance when filtering active clients in list views
    op.create_index(
        "ix_clients_workspace_active",
        "clients",
        ["workspace_id", "is_active"],
        unique=False,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    """Remove healthcare-related fields from clients table."""
    # Drop index first (depends on is_active column)
    op.drop_index("ix_clients_workspace_active", table_name="clients")

    # Drop columns in reverse order
    op.drop_column("clients", "is_active")
    op.drop_column("clients", "emergency_contact_phone")
    op.drop_column("clients", "emergency_contact_name")
    op.drop_column("clients", "medical_history")
    op.drop_column("clients", "address")
