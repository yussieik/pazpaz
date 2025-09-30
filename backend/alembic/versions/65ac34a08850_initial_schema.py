"""initial schema

Revision ID: 65ac34a08850
Revises:
Create Date: 2025-09-30 18:36:34.040176

This migration creates the foundational schema for PazPaz:
- Workspace: Multi-tenant context for therapist accounts
- User: Therapists and assistants within workspaces
- Client: Individuals receiving treatment (contains PII/PHI)
- Appointment: Scheduled sessions with conflict detection indexes

All tables except Workspace include workspace_id for data isolation.
Indexes are optimized for <150ms p95 query performance on schedule operations.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "65ac34a08850"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create initial schema with all core tables and indexes."""
    # Create workspaces table
    op.create_table(
        "workspaces",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        comment="Therapist account context for multi-tenant data isolation",
    )
    op.create_index(op.f("ix_workspaces_id"), "workspaces", ["id"], unique=False)

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "owner", "assistant", name="userrole", native_enum=False, length=50
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "email", name="uq_users_workspace_email"),
        comment="Users within workspaces with role-based access",
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(
        op.f("ix_users_workspace_id"),
        "users",
        ["workspace_id"],
        unique=False,
    )

    # Create clients table
    op.create_table(
        "clients",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column(
            "consent_status",
            sa.Boolean(),
            nullable=False,
            comment="Client consent to store and process data",
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment="General notes about the client",
        ),
        sa.Column(
            "tags",
            sa.ARRAY(sa.String(length=100)),
            nullable=True,
            comment="Tags for categorization and filtering",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Clients with PII/PHI - encryption at rest required",
    )
    op.create_index(op.f("ix_clients_id"), "clients", ["id"], unique=False)
    op.create_index(
        op.f("ix_clients_workspace_id"),
        "clients",
        ["workspace_id"],
        unique=False,
    )
    # Performance indexes for client queries
    op.create_index(
        "ix_clients_workspace_lastname_firstname",
        "clients",
        ["workspace_id", "last_name", "first_name"],
        unique=False,
    )
    op.create_index(
        "ix_clients_workspace_email",
        "clients",
        ["workspace_id", "email"],
        unique=False,
    )
    op.create_index(
        "ix_clients_workspace_updated",
        "clients",
        ["workspace_id", "updated_at"],
        unique=False,
    )

    # Create appointments table
    op.create_table(
        "appointments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column(
            "scheduled_start",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Start time of the appointment (timezone-aware UTC)",
        ),
        sa.Column(
            "scheduled_end",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="End time of the appointment (timezone-aware UTC)",
        ),
        sa.Column(
            "location_type",
            sa.Enum(
                "clinic",
                "home",
                "online",
                name="locationtype",
                native_enum=False,
                length=50,
            ),
            nullable=False,
        ),
        sa.Column(
            "location_details",
            sa.Text(),
            nullable=True,
            comment="Additional location details (address, room number, video link)",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "scheduled",
                "completed",
                "cancelled",
                "no_show",
                name="appointmentstatus",
                native_enum=False,
                length=50,
            ),
            nullable=False,
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment="Therapist notes for the appointment",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment=(
            "Appointments with time-range indexes optimized for "
            "conflict detection (<150ms p95 target)"
        ),
    )
    op.create_index(op.f("ix_appointments_id"), "appointments", ["id"], unique=False)
    op.create_index(
        op.f("ix_appointments_client_id"),
        "appointments",
        ["client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_appointments_workspace_id"),
        "appointments",
        ["workspace_id"],
        unique=False,
    )
    # Critical performance indexes for appointment queries
    # Index for conflict detection and calendar view (time-range queries)
    op.create_index(
        "ix_appointments_workspace_time_range",
        "appointments",
        ["workspace_id", "scheduled_start", "scheduled_end"],
        unique=False,
    )
    # Index for client timeline view (ordered by appointment time)
    op.create_index(
        "ix_appointments_workspace_client_time",
        "appointments",
        ["workspace_id", "client_id", "scheduled_start"],
        unique=False,
    )
    # Index for filtering by status within workspace
    op.create_index(
        "ix_appointments_workspace_status",
        "appointments",
        ["workspace_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    """Drop all tables and indexes in reverse order."""
    # Drop appointments table and its indexes
    op.drop_index("ix_appointments_workspace_status", table_name="appointments")
    op.drop_index("ix_appointments_workspace_client_time", table_name="appointments")
    op.drop_index("ix_appointments_workspace_time_range", table_name="appointments")
    op.drop_index(op.f("ix_appointments_workspace_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_client_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_id"), table_name="appointments")
    op.drop_table("appointments")

    # Drop clients table and its indexes
    op.drop_index("ix_clients_workspace_updated", table_name="clients")
    op.drop_index("ix_clients_workspace_email", table_name="clients")
    op.drop_index("ix_clients_workspace_lastname_firstname", table_name="clients")
    op.drop_index(op.f("ix_clients_workspace_id"), table_name="clients")
    op.drop_index(op.f("ix_clients_id"), table_name="clients")
    op.drop_table("clients")

    # Drop users table and its indexes
    op.drop_index(op.f("ix_users_workspace_id"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_table("users")

    # Drop workspaces table and its indexes
    op.drop_index(op.f("ix_workspaces_id"), table_name="workspaces")
    op.drop_table("workspaces")

    # Drop enums (in reverse order of dependencies)
    op.execute("DROP TYPE IF EXISTS appointmentstatus")
    op.execute("DROP TYPE IF EXISTS locationtype")
    op.execute("DROP TYPE IF EXISTS userrole")
