"""fix_pgcrypto_functions

Revision ID: 8283b279aeac
Revises: 6be7adba063b
Create Date: 2025-10-05 15:59:22.398302

Fix pgcrypto encryption functions to properly handle bytea conversion.

The previous version had incorrect bytea casting for the encryption key.
This migration replaces the functions with corrected versions.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8283b279aeac'
down_revision: str | Sequence[str] | None = '6be7adba063b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Replace pgcrypto functions with corrected versions."""

    # Drop existing functions
    op.execute("DROP FUNCTION IF EXISTS verify_encryption_pgcrypto(TEXT, TEXT);")
    op.execute("DROP FUNCTION IF EXISTS decrypt_phi_pgcrypto(TEXT, TEXT);")
    op.execute("DROP FUNCTION IF EXISTS encrypt_phi_pgcrypto(TEXT, TEXT, TEXT);")

    # Recreate with proper bytea handling
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

            -- Encrypt using AES-256 with pgcrypto
            -- Note: pgcrypto uses AES in CBC mode by default
            encrypted_bytes := encrypt(
                convert_to(plaintext, 'UTF8'),
                convert_to(encryption_key, 'UTF8'),
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
                convert_to(encryption_key, 'UTF8'),
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

    # Restore comments
    op.execute(
        """
        COMMENT ON FUNCTION encrypt_phi_pgcrypto(TEXT, TEXT, TEXT) IS
        'OPTIONAL: Database-level PHI encryption using pgcrypto (AES-256-CBC). '
        'Primary encryption is application-level (AES-256-GCM). Use only for backup/verification. '
        'Returns version-prefixed ciphertext (format: v1:base64data).';
        """
    )

    op.execute(
        """
        COMMENT ON FUNCTION decrypt_phi_pgcrypto(TEXT, TEXT) IS
        'OPTIONAL: Database-level PHI decryption using pgcrypto (AES-256-CBC). '
        'Primary decryption is application-level (AES-256-GCM). Use only for backup/verification. '
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
    """Revert to previous version (broken functions)."""
    # Not necessary - if downgrading, the previous migration will handle it
    pass
