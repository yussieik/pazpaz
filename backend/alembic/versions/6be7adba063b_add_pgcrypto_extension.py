"""add_pgcrypto_extension

Revision ID: 6be7adba063b
Revises: de72ee2cfb00
Create Date: 2025-10-05 15:58:06.013546

This migration installs the pgcrypto extension for PostgreSQL encryption capabilities.

Context:
- Primary encryption approach: Application-level (Python cryptography library)
- pgcrypto role: Backup/optional database-level encryption capability
- Use case: Future hybrid scenarios or database-side operations

Design Decisions:
1. Install pgcrypto extension for optional database-level encryption
2. Provide backup SQL functions for hybrid encryption scenarios
3. Primary encryption remains application-level (Week 1 Day 4 implementation)

IMPORTANT: This migration provides OPTIONAL backup capabilities. The primary
encryption strategy uses Python `cryptography` library at the application layer
for better key management and rotation flexibility.

Performance Implications:
- pgcrypto installation: <10ms (one-time operation)
- No query performance impact (only installs extension)
- Functions not used unless explicitly called

HIPAA Compliance:
- Supports defense-in-depth encryption strategy
- Enables database-level verification of encryption
- Provides backup option for key rotation scenarios
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6be7adba063b"
down_revision: str | Sequence[str] | None = "de72ee2cfb00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Install pgcrypto extension and create optional backup encryption functions.

    This migration:
    1. Installs pgcrypto extension (PostgreSQL cryptographic functions)
    2. Creates optional SQL functions for database-level encryption
    3. Provides backup capability for hybrid encryption scenarios

    Note: Primary encryption is application-level (Python cryptography).
    These functions are OPTIONAL and only used in specific scenarios.
    """
    # Install pgcrypto extension
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # Create optional database-level encryption helper functions
    # These are NOT used by default - application-level encryption is primary
    # Keeping them as backup/optional capability for future use cases

    # Optional Function 1: Encrypt PHI with key version tracking
    op.execute(
        """
        CREATE OR REPLACE FUNCTION encrypt_phi_pgcrypto(
            plaintext TEXT,
            encryption_key TEXT,
            key_version TEXT DEFAULT 'v1'
        )
        RETURNS TEXT AS $$
        DECLARE
            encrypted_bytes BYTEA;
            encoded_result TEXT;
        BEGIN
            -- Validate inputs
            IF plaintext IS NULL THEN
                RETURN NULL;
            END IF;

            IF encryption_key IS NULL OR OCTET_LENGTH(encryption_key) < 32 THEN
                RAISE EXCEPTION 'Encryption key must be at least 32 bytes';
            END IF;

            -- Encrypt using AES-256 (pgcrypto uses AES in CBC mode by default)
            -- For production, use AES-GCM (not directly supported by pgcrypto)
            encrypted_bytes := encrypt(
                plaintext::bytea,
                encryption_key::bytea,
                'aes'
            );

            -- Encode as Base64 and prefix with key version
            encoded_result := encode(encrypted_bytes, 'base64');

            -- Return version-prefixed ciphertext (format: "v1:base64data")
            RETURN key_version || ':' || encoded_result;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE STRICT;
        """
    )

    # Optional Function 2: Decrypt PHI with automatic key version detection
    op.execute(
        """
        CREATE OR REPLACE FUNCTION decrypt_phi_pgcrypto(
            ciphertext TEXT,
            encryption_key TEXT
        )
        RETURNS TEXT AS $$
        DECLARE
            key_version TEXT;
            encoded_data TEXT;
            encrypted_bytes BYTEA;
            decrypted_bytes BYTEA;
        BEGIN
            -- Validate inputs
            IF ciphertext IS NULL THEN
                RETURN NULL;
            END IF;

            IF encryption_key IS NULL OR OCTET_LENGTH(encryption_key) < 32 THEN
                RAISE EXCEPTION 'Encryption key must be at least 32 bytes';
            END IF;

            -- Extract key version and encrypted data
            -- Format: "v1:base64data"
            IF position(':' IN ciphertext) > 0 THEN
                key_version := split_part(ciphertext, ':', 1);
                encoded_data := split_part(ciphertext, ':', 2);
            ELSE
                -- Legacy format without version (assume v1)
                key_version := 'v1';
                encoded_data := ciphertext;
            END IF;

            -- Decode Base64
            encrypted_bytes := decode(encoded_data, 'base64');

            -- Decrypt using AES-256
            decrypted_bytes := decrypt(
                encrypted_bytes,
                encryption_key::bytea,
                'aes'
            );

            -- Convert bytea to text
            RETURN convert_from(decrypted_bytes, 'UTF8');
        EXCEPTION
            WHEN OTHERS THEN
                -- Log error but don't expose key material
                RAISE EXCEPTION 'Decryption failed (invalid key or corrupted data)';
        END;
        $$ LANGUAGE plpgsql IMMUTABLE STRICT;
        """
    )

    # Optional Function 3: Verify encryption (test encrypt/decrypt round-trip)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION verify_encryption_pgcrypto(
            test_plaintext TEXT,
            encryption_key TEXT
        )
        RETURNS BOOLEAN AS $$
        DECLARE
            encrypted TEXT;
            decrypted TEXT;
        BEGIN
            -- Encrypt
            encrypted := encrypt_phi_pgcrypto(test_plaintext, encryption_key, 'v1');

            -- Decrypt
            decrypted := decrypt_phi_pgcrypto(encrypted, encryption_key);

            -- Verify round-trip
            RETURN decrypted = test_plaintext;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE STRICT;
        """
    )

    # Add comments for documentation
    op.execute(
        """
        COMMENT ON FUNCTION encrypt_phi_pgcrypto(TEXT, TEXT, TEXT) IS
        'OPTIONAL: Database-level PHI encryption using pgcrypto (AES-256). '
        'Primary encryption is application-level. Use only for backup/verification scenarios. '
        'Returns version-prefixed ciphertext (format: v1:base64data).';
        """
    )

    op.execute(
        """
        COMMENT ON FUNCTION decrypt_phi_pgcrypto(TEXT, TEXT) IS
        'OPTIONAL: Database-level PHI decryption using pgcrypto (AES-256). '
        'Primary decryption is application-level. Use only for backup/verification scenarios. '
        'Automatically detects key version from ciphertext prefix.';
        """
    )

    op.execute(
        """
        COMMENT ON FUNCTION verify_encryption_pgcrypto(TEXT, TEXT) IS
        'Test function to verify encryption/decryption round-trip. '
        'Returns TRUE if encrypt -> decrypt returns original plaintext. '
        'Used for testing pgcrypto encryption setup.';
        """
    )


def downgrade() -> None:
    """
    Remove pgcrypto extension and encryption functions.

    WARNING: This will remove backup encryption capability.
    Ensure no data relies on pgcrypto functions before downgrading.
    """
    # Drop functions (in reverse order of dependencies)
    op.execute("DROP FUNCTION IF EXISTS verify_encryption_pgcrypto(TEXT, TEXT);")
    op.execute("DROP FUNCTION IF EXISTS decrypt_phi_pgcrypto(TEXT, TEXT);")
    op.execute("DROP FUNCTION IF EXISTS encrypt_phi_pgcrypto(TEXT, TEXT, TEXT);")

    # Drop extension (only if no other functions depend on it)
    op.execute("DROP EXTENSION IF EXISTS pgcrypto;")
