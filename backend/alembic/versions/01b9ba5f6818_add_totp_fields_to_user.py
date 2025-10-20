"""add_totp_fields_to_user

Revision ID: 01b9ba5f6818
Revises: 92df859932f2
Create Date: 2025-10-20 12:40:21.189813

Add TOTP/2FA fields to users table for optional 2FA authentication.

Security enhancement for HIPAA compliance - enables optional multi-factor
authentication for users accessing PHI data.

"""
from collections.abc import Sequence

import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "01b9ba5f6818"
down_revision: str | Sequence[str] | None = "92df859932f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Add TOTP/2FA fields to users table.

    Adds four new columns:
    - totp_secret: Encrypted TOTP secret key (base32-encoded)
    - totp_enabled: Boolean flag indicating if 2FA is enabled
    - totp_backup_codes: Encrypted JSON array of hashed backup codes
    - totp_enrolled_at: Timestamp when 2FA was enabled
    """
    from alembic import op

    # Add TOTP fields to users table
    op.add_column(
        "users",
        sa.Column(
            "totp_secret",
            sa.LargeBinary(),  # EncryptedString uses LargeBinary
            nullable=True,
            comment="TOTP secret key (encrypted, base32-encoded)",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "totp_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="Whether 2FA is enabled for this user",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "totp_backup_codes",
            sa.LargeBinary(),  # EncryptedString uses LargeBinary
            nullable=True,
            comment="JSON array of hashed backup codes (encrypted)",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "totp_enrolled_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when 2FA was enabled",
        ),
    )

    # Create index on totp_enabled for efficient querying of 2FA-enabled users
    op.create_index(
        "ix_users_totp_enabled",
        "users",
        ["totp_enabled"],
    )


def downgrade() -> None:
    """
    Remove TOTP/2FA fields from users table.

    WARNING: This will permanently delete all TOTP enrollment data.
    Users will need to re-enroll in 2FA after upgrade.
    """
    from alembic import op

    # Drop index
    op.drop_index("ix_users_totp_enabled", table_name="users")

    # Drop columns
    op.drop_column("users", "totp_enrolled_at")
    op.drop_column("users", "totp_backup_codes")
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_secret")
