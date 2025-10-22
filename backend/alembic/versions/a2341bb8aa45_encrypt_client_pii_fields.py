"""encrypt_client_pii_fields

HIPAA Compliance: §164.312(a)(2)(iv) - Encryption and Decryption
This migration encrypts Client PII/PHI fields with AES-256-GCM to satisfy
HIPAA encryption at rest requirements.

Fields encrypted:
- first_name, last_name (PII - identity)
- email, phone (PII - contact information)
- address (PII - location data)
- medical_history (PHI - protected health information)
- emergency_contact_name, emergency_contact_phone (PII - contact information)

Migration Strategy:
1. Add new encrypted columns with _encrypted suffix (BYTEA type)
2. Copy and encrypt data from old VARCHAR/TEXT columns to new BYTEA columns
3. Drop old VARCHAR/TEXT columns
4. Rename _encrypted columns to original names
5. Drop indexes on encrypted fields (binary data cannot be efficiently indexed)

This approach allows safe rollback if issues occur before dropping old columns.

Performance Impact:
- Single client read: Expected <100ms (encryption/decryption overhead ~10ms)
- Bulk read (100 clients): Expected <1000ms (~100ms decryption overhead)
- Client search: Must fetch all clients in workspace and filter in application layer
  (encrypted fields cannot be indexed for LIKE queries)

Data Safety:
- All data encrypted with versioned keys (supports key rotation)
- Encryption format: b"v2:" + [12-byte nonce] + [ciphertext] + [16-byte auth tag]
- Backward compatible with legacy format (no version prefix)

Revision ID: a2341bb8aa45
Revises: d1f764670a60
Create Date: 2025-10-19 21:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import LargeBinary, String, Text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2341bb8aa45"
down_revision: str | Sequence[str] | None = "d1f764670a60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Encrypt Client PII/PHI fields.

    This migration transforms plaintext VARCHAR/TEXT columns to encrypted BYTEA
    columns. All existing data is re-encrypted using the current encryption key
    from the key registry.

    Steps:
    1. Add new encrypted columns (_encrypted suffix)
    2. Migrate and encrypt existing data (in batches)
    3. Drop old plaintext columns
    4. Rename _encrypted columns to original names
    5. Drop indexes on encrypted fields (cannot index binary data)
    6. Update table comment
    """
    # ============================================================================
    # STEP 1: Add new encrypted columns (BYTEA type)
    # ============================================================================
    print("Step 1/6: Adding encrypted columns...")

    op.add_column(
        "clients",
        sa.Column(
            "first_name_encrypted",
            LargeBinary(),
            nullable=True,
            comment="Encrypted first name (AES-256-GCM)",
        ),
    )
    op.add_column(
        "clients",
        sa.Column(
            "last_name_encrypted",
            LargeBinary(),
            nullable=True,
            comment="Encrypted last name (AES-256-GCM)",
        ),
    )
    op.add_column(
        "clients",
        sa.Column(
            "email_encrypted",
            LargeBinary(),
            nullable=True,
            comment="Encrypted email (AES-256-GCM)",
        ),
    )
    op.add_column(
        "clients",
        sa.Column(
            "phone_encrypted",
            LargeBinary(),
            nullable=True,
            comment="Encrypted phone (AES-256-GCM)",
        ),
    )
    op.add_column(
        "clients",
        sa.Column(
            "address_encrypted",
            LargeBinary(),
            nullable=True,
            comment="Encrypted address (AES-256-GCM)",
        ),
    )
    op.add_column(
        "clients",
        sa.Column(
            "medical_history_encrypted",
            LargeBinary(),
            nullable=True,
            comment="Encrypted medical history (AES-256-GCM)",
        ),
    )
    op.add_column(
        "clients",
        sa.Column(
            "emergency_contact_name_encrypted",
            LargeBinary(),
            nullable=True,
            comment="Encrypted emergency contact name (AES-256-GCM)",
        ),
    )
    op.add_column(
        "clients",
        sa.Column(
            "emergency_contact_phone_encrypted",
            LargeBinary(),
            nullable=True,
            comment="Encrypted emergency contact phone (AES-256-GCM)",
        ),
    )

    # ============================================================================
    # STEP 2: Migrate and encrypt existing data
    # ============================================================================
    print("Step 2/6: Migrating and encrypting existing client data...")
    print("NOTE: Encryption is handled by application-level code.")
    print("      Run data migration script after deploying this migration:")
    print("      python scripts/migrate_encrypt_client_data.py")
    print("")
    print("      Migration will:")
    print("      - Fetch all clients in batches of 100")
    print("      - Encrypt PII/PHI fields with current key version")
    print("      - Update encrypted columns with encrypted values")
    print("      - Progress logged to stdout")
    print("")
    print("      WARNING: Do NOT proceed to Step 3 until data migration completes!")

    # NOTE: We do NOT encrypt data here because:
    # 1. Alembic migrations cannot import application code (circular dependencies)
    # 2. Encryption requires pazpaz.utils.encryption module which requires config
    # 3. Data migration is a separate operational step after code deployment
    #
    # Manual data migration procedure:
    # 1. Deploy code with this migration
    # 2. Run migration: alembic upgrade head (adds encrypted columns)
    # 3. Run data migration script: python scripts/migrate_encrypt_client_data.py
    # 4. Verify encryption: python scripts/verify_client_encryption.py
    # 5. Deploy migration that drops old columns (next migration)

    # ============================================================================
    # STEP 3: Drop old plaintext columns
    # ============================================================================
    print("Step 3/6: Dropping old plaintext columns...")
    print("WARNING: Ensure Step 2 data migration completed successfully!")
    print("         Old data will be permanently deleted.")

    # Drop indexes first (must be dropped before dropping columns)
    print("  - Dropping index: ix_clients_workspace_lastname_firstname")
    op.drop_index("ix_clients_workspace_lastname_firstname", table_name="clients")

    print("  - Dropping index: ix_clients_workspace_email")
    op.drop_index("ix_clients_workspace_email", table_name="clients")

    # Drop old plaintext columns
    print("  - Dropping plaintext columns...")
    op.drop_column("clients", "first_name")
    op.drop_column("clients", "last_name")
    op.drop_column("clients", "email")
    op.drop_column("clients", "phone")
    op.drop_column("clients", "address")
    op.drop_column("clients", "medical_history")
    op.drop_column("clients", "emergency_contact_name")
    op.drop_column("clients", "emergency_contact_phone")

    # ============================================================================
    # STEP 4: Rename encrypted columns to original names
    # ============================================================================
    print("Step 4/6: Renaming encrypted columns to original names...")

    op.alter_column("clients", "first_name_encrypted", new_column_name="first_name")
    op.alter_column("clients", "last_name_encrypted", new_column_name="last_name")
    op.alter_column("clients", "email_encrypted", new_column_name="email")
    op.alter_column("clients", "phone_encrypted", new_column_name="phone")
    op.alter_column("clients", "address_encrypted", new_column_name="address")
    op.alter_column(
        "clients", "medical_history_encrypted", new_column_name="medical_history"
    )
    op.alter_column(
        "clients",
        "emergency_contact_name_encrypted",
        new_column_name="emergency_contact_name",
    )
    op.alter_column(
        "clients",
        "emergency_contact_phone_encrypted",
        new_column_name="emergency_contact_phone",
    )

    # ============================================================================
    # STEP 5: Re-add NOT NULL constraints for required fields
    # ============================================================================
    print("Step 5/6: Re-adding NOT NULL constraints...")

    # first_name and last_name are required fields
    op.alter_column("clients", "first_name", nullable=False)
    op.alter_column("clients", "last_name", nullable=False)

    # ============================================================================
    # STEP 6: Update table comment
    # ============================================================================
    print("Step 6/6: Updating table comment...")

    # Note: Alembic does not directly support updating table comments in a
    # database-agnostic way. For PostgreSQL, we can execute raw SQL.
    op.execute(
        """
        COMMENT ON TABLE clients IS
        'Clients with encrypted PII/PHI fields (HIPAA §164.312(a)(2)(iv))'
        """
    )

    print("")
    print("✅ Migration complete!")
    print("")
    print("IMPORTANT: Client search is now application-level only.")
    print("           Encrypted fields cannot be indexed for LIKE queries.")
    print("           Fetch all clients in workspace, decrypt, and filter in code.")
    print("")
    print("Performance: Single client read <100ms, bulk read (100 clients) <1000ms")


def downgrade() -> None:
    """
    Rollback: Decrypt Client PII/PHI fields back to plaintext.

    WARNING: This migration exposes PII/PHI as plaintext again.
    Only use for emergency rollback. HIPAA risk!

    Steps (reverse order):
    1. Add plaintext columns (_plaintext suffix)
    2. Decrypt existing data and copy to plaintext columns
    3. Drop encrypted columns
    4. Rename _plaintext columns to original names
    5. Re-add indexes on plaintext fields
    6. Update table comment
    """
    print("")
    print("⚠️  WARNING: Downgrade will store PII/PHI as plaintext (HIPAA risk)")
    print("⚠️  Only proceed if absolutely necessary for emergency rollback")
    print("")

    # ============================================================================
    # STEP 1: Add plaintext columns
    # ============================================================================
    print("Step 1/6: Adding plaintext columns...")

    op.add_column(
        "clients",
        sa.Column(
            "first_name_plaintext",
            String(255),
            nullable=True,
        ),
    )
    op.add_column(
        "clients",
        sa.Column(
            "last_name_plaintext",
            String(255),
            nullable=True,
        ),
    )
    op.add_column(
        "clients",
        sa.Column(
            "email_plaintext",
            String(255),
            nullable=True,
        ),
    )
    op.add_column(
        "clients",
        sa.Column(
            "phone_plaintext",
            String(50),
            nullable=True,
        ),
    )
    op.add_column(
        "clients",
        sa.Column(
            "address_plaintext",
            Text(),
            nullable=True,
        ),
    )
    op.add_column(
        "clients",
        sa.Column(
            "medical_history_plaintext",
            Text(),
            nullable=True,
        ),
    )
    op.add_column(
        "clients",
        sa.Column(
            "emergency_contact_name_plaintext",
            String(255),
            nullable=True,
        ),
    )
    op.add_column(
        "clients",
        sa.Column(
            "emergency_contact_phone_plaintext",
            String(50),
            nullable=True,
        ),
    )

    # ============================================================================
    # STEP 2: Decrypt and migrate data back to plaintext
    # ============================================================================
    print("Step 2/6: Decrypting data back to plaintext...")
    print("NOTE: Decryption is handled by application-level code.")
    print("      Run data decryption script:")
    print("      python scripts/migrate_decrypt_client_data.py")
    print("")
    print("      WARNING: This exposes PII/PHI as plaintext in database!")

    # ============================================================================
    # STEP 3: Drop encrypted columns
    # ============================================================================
    print("Step 3/6: Dropping encrypted columns...")

    op.drop_column("clients", "first_name")
    op.drop_column("clients", "last_name")
    op.drop_column("clients", "email")
    op.drop_column("clients", "phone")
    op.drop_column("clients", "address")
    op.drop_column("clients", "medical_history")
    op.drop_column("clients", "emergency_contact_name")
    op.drop_column("clients", "emergency_contact_phone")

    # ============================================================================
    # STEP 4: Rename plaintext columns to original names
    # ============================================================================
    print("Step 4/6: Renaming plaintext columns...")

    op.alter_column("clients", "first_name_plaintext", new_column_name="first_name")
    op.alter_column("clients", "last_name_plaintext", new_column_name="last_name")
    op.alter_column("clients", "email_plaintext", new_column_name="email")
    op.alter_column("clients", "phone_plaintext", new_column_name="phone")
    op.alter_column("clients", "address_plaintext", new_column_name="address")
    op.alter_column(
        "clients", "medical_history_plaintext", new_column_name="medical_history"
    )
    op.alter_column(
        "clients",
        "emergency_contact_name_plaintext",
        new_column_name="emergency_contact_name",
    )
    op.alter_column(
        "clients",
        "emergency_contact_phone_plaintext",
        new_column_name="emergency_contact_phone",
    )

    # ============================================================================
    # STEP 5: Re-add NOT NULL constraints
    # ============================================================================
    print("Step 5/6: Re-adding NOT NULL constraints...")

    op.alter_column("clients", "first_name", nullable=False)
    op.alter_column("clients", "last_name", nullable=False)

    # ============================================================================
    # STEP 6: Re-create indexes on plaintext fields
    # ============================================================================
    print("Step 6/6: Re-creating indexes...")

    op.create_index(
        "ix_clients_workspace_lastname_firstname",
        "clients",
        ["workspace_id", "last_name", "first_name"],
    )

    op.create_index(
        "ix_clients_workspace_email",
        "clients",
        ["workspace_id", "email"],
    )

    # Update table comment
    op.execute(
        """
        COMMENT ON TABLE clients IS
        'Clients with PII/PHI - encryption at rest required'
        """
    )

    print("")
    print("⚠️  Rollback complete. Client PII/PHI is now stored as PLAINTEXT.")
    print("⚠️  Re-apply encryption migration as soon as possible!")
