"""add_service_and_location_entities

Revision ID: f6092aa0856d
Revises: 65ac34a08850
Create Date: 2025-09-30 20:31:45.866717

This migration adds Service and Location entities for M1 completion:
- Service: Types of therapy offered with default durations
- Location: Saved places (clinic, home, online) for appointments
- Appointment: Add optional foreign keys to service_id and location_id

These entities normalize previously embedded data and enable reusability
across appointments. Backward compatible: existing appointments continue
using embedded location_type/location_details fields.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6092aa0856d"
down_revision: str | Sequence[str] | None = "65ac34a08850"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add Service and Location tables, update Appointments with optional FKs."""
    # Create services table
    op.create_table(
        "services",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
            comment="Service name (e.g., 'Deep Tissue Massage', 'Physiotherapy Session')",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Optional description of the service",
        ),
        sa.Column(
            "default_duration_minutes",
            sa.Integer(),
            nullable=False,
            comment="Default duration in minutes for scheduling (e.g., 60, 90)",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            comment="Active services appear in scheduling UI; inactive are archived",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Services with default durations for quick scheduling",
    )
    op.create_index(op.f("ix_services_id"), "services", ["id"], unique=False)
    op.create_index(
        op.f("ix_services_workspace_id"),
        "services",
        ["workspace_id"],
        unique=False,
    )
    # Unique constraint: one service name per workspace
    op.create_index(
        "uq_services_workspace_name",
        "services",
        ["workspace_id", "name"],
        unique=True,
    )
    # Partial index for active services (most common query pattern)
    op.create_index(
        "ix_services_workspace_active",
        "services",
        ["workspace_id", "is_active"],
        unique=False,
        postgresql_where=sa.text("is_active = true"),
    )

    # Create locations table
    op.create_table(
        "locations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
            comment="Location name (e.g., 'Main Clinic', 'Home Visits')",
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
            comment="Type: clinic, home, or online",
        ),
        sa.Column(
            "address",
            sa.Text(),
            nullable=True,
            comment="Physical address for clinic or home visits",
        ),
        sa.Column(
            "details",
            sa.Text(),
            nullable=True,
            comment="Additional details (room number, video link, parking instructions)",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            comment="Active locations appear in scheduling UI; inactive are archived",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Saved locations for appointment scheduling",
    )
    op.create_index(op.f("ix_locations_id"), "locations", ["id"], unique=False)
    op.create_index(
        op.f("ix_locations_workspace_id"),
        "locations",
        ["workspace_id"],
        unique=False,
    )
    # Unique constraint: one location name per workspace
    op.create_index(
        "uq_locations_workspace_name",
        "locations",
        ["workspace_id", "name"],
        unique=True,
    )
    # Partial index for active locations (most common query pattern)
    op.create_index(
        "ix_locations_workspace_active",
        "locations",
        ["workspace_id", "is_active"],
        unique=False,
        postgresql_where=sa.text("is_active = true"),
    )
    # Index for filtering by location type within workspace
    op.create_index(
        "ix_locations_workspace_type",
        "locations",
        ["workspace_id", "location_type"],
        unique=False,
    )

    # Add optional foreign keys to appointments table
    # These are nullable for backward compatibility with existing appointments
    # and to allow one-off appointments without predefined services/locations
    op.add_column(
        "appointments",
        sa.Column(
            "service_id",
            sa.UUID(),
            nullable=True,
            comment="Optional reference to predefined service type",
        ),
    )
    op.add_column(
        "appointments",
        sa.Column(
            "location_id",
            sa.UUID(),
            nullable=True,
            comment="Optional reference to saved location (overrides location_type/details)",
        ),
    )
    op.create_index(
        op.f("ix_appointments_service_id"),
        "appointments",
        ["service_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_appointments_location_id"),
        "appointments",
        ["location_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_appointments_service_id_services",
        "appointments",
        "services",
        ["service_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_appointments_location_id_locations",
        "appointments",
        "locations",
        ["location_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove Service and Location tables, remove optional FKs from Appointments."""
    # Drop foreign keys and columns from appointments table
    op.drop_constraint(
        "fk_appointments_location_id_locations",
        "appointments",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_appointments_service_id_services",
        "appointments",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_appointments_location_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_service_id"), table_name="appointments")
    op.drop_column("appointments", "location_id")
    op.drop_column("appointments", "service_id")

    # Drop locations table and its indexes
    op.drop_index("ix_locations_workspace_type", table_name="locations")
    op.drop_index("ix_locations_workspace_active", table_name="locations")
    op.drop_index("uq_locations_workspace_name", table_name="locations")
    op.drop_index(op.f("ix_locations_workspace_id"), table_name="locations")
    op.drop_index(op.f("ix_locations_id"), table_name="locations")
    op.drop_table("locations")

    # Drop services table and its indexes
    op.drop_index("ix_services_workspace_active", table_name="services")
    op.drop_index("uq_services_workspace_name", table_name="services")
    op.drop_index(op.f("ix_services_workspace_id"), table_name="services")
    op.drop_index(op.f("ix_services_id"), table_name="services")
    op.drop_table("services")
