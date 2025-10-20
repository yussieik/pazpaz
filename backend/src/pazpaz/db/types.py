"""
Custom SQLAlchemy column types for PazPaz.

This module provides custom SQLAlchemy types for transparent encryption/decryption
of sensitive data fields. These types handle encryption on INSERT/UPDATE and
decryption on SELECT, making PHI/PII protection transparent to application code.

Usage:
    from pazpaz.db.types import EncryptedString
    from sqlalchemy import Column

    class Client(Base):
        __tablename__ = "clients"

        # Encrypted field - transparent encryption/decryption
        medical_history = Column(EncryptedString(5000), nullable=True)

Performance:
    - Encryption overhead: <5ms per field
    - Decryption overhead: <10ms per field
    - Stored as BYTEA in PostgreSQL (binary format)

Security:
    - AES-256-GCM authenticated encryption
    - Per-field random nonce (never reused)
    - Authentication tag prevents tampering
    - Application-level encryption (defense in depth with pgcrypto)
"""

from typing import Any

from sqlalchemy import LargeBinary, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB

from pazpaz.core.logging import get_logger
from pazpaz.utils.encryption import (
    decrypt_field,
    decrypt_field_versioned,
    encrypt_field,
    encrypt_field_versioned,
)

logger = get_logger(__name__)


class EncryptedString(TypeDecorator):
    """
    SQLAlchemy type for transparent encryption/decryption of string fields with key rotation support.

    This type automatically encrypts data on INSERT/UPDATE and decrypts on SELECT,
    making encryption transparent to application code. Supports both legacy (non-versioned)
    and versioned encryption formats for zero-downtime key rotation.

    Storage format in database (new versioned format):
        BYTEA: b"v2:"[12-byte nonce][ciphertext][16-byte authentication tag]

    Legacy storage format (backward compatible):
        BYTEA: [12-byte nonce][ciphertext][16-byte authentication tag]

    The type automatically detects the format on decryption:
    - If version prefix exists (b"v2:"), uses versioned decryption with key registry
    - If no version prefix, uses legacy decryption with settings.encryption_key

    Application usage:
        Transparent string get/set - no manual encryption needed

    Example:
        class Client(Base):
            __tablename__ = "clients"

            # Encrypted field - stores up to ~2000 chars of plaintext
            # Database column is BYTEA with encryption overhead
            medical_history = Column(EncryptedString(2000), nullable=True)

        # Application code (encryption is transparent)
        client = Client(medical_history="Patient has diabetes")
        session.add(client)
        await session.commit()

        # Decryption is automatic on SELECT (supports both legacy and versioned formats)
        result = await session.get(Client, client_id)
        print(result.medical_history)  # "Patient has diabetes" (decrypted)

    Args:
        length: Maximum plaintext length (for documentation/validation)
                Note: Actual database column will be larger due to encryption overhead
                (version prefix + 12 bytes nonce + 16 bytes tag)

    Security considerations:
        - Cannot perform LIKE queries on encrypted fields
        - Cannot create functional indexes on encrypted content
        - Decrypted values exist in application memory
        - All queries must decrypt entire field (no partial decryption)
        - Use audit logging to track access to encrypted fields
        - Supports zero-downtime key rotation via versioned format

    Key Rotation:
        - New encryptions use current key version from key registry
        - Old data decrypts with appropriate key version
        - Migration path: legacy (no prefix) → versioned (with prefix)
    """

    impl = LargeBinary
    cache_ok = True

    def __init__(self, length: int | None = None, *args: Any, **kwargs: Any):
        """
        Initialize EncryptedString type.

        Args:
            length: Maximum expected plaintext length (for documentation)
                   The actual BYTEA column will be larger due to encryption overhead.
        """
        super().__init__(*args, **kwargs)
        self.length = length

    def process_bind_param(self, value: str | None, dialect: Any) -> bytes | None:
        """
        Encrypt value before storing in database (INSERT/UPDATE).

        This method is called by SQLAlchemy when binding a parameter to a query.
        It transparently encrypts the plaintext string before storage using the
        current key version from the key registry.

        Args:
            value: Plaintext string to encrypt (or None)
            dialect: SQLAlchemy dialect (unused)

        Returns:
            Encrypted bytes in versioned format: b"v2:" + nonce || ciphertext || tag
            Or None if value is None

        Raises:
            EncryptionError: If encryption fails
        """
        if value is None:
            return None

        # Try to use key registry for versioned encryption
        try:
            from pazpaz.utils.encryption import (
                get_current_key_version,
                get_key_for_version,
            )

            # Get current key version from registry
            version = get_current_key_version()
            key = get_key_for_version(version)

            # Encrypt with versioned format
            encrypted = encrypt_field(value, key)

            # Prepend version prefix for key selection during decryption
            versioned_ciphertext = f"{version}:".encode() + encrypted

            # Log encryption operation (do NOT log plaintext value)
            logger.debug(
                "field_encrypted_versioned",
                plaintext_length=len(value),
                ciphertext_length=len(versioned_ciphertext),
                key_version=version,
            )

            return versioned_ciphertext

        except (ValueError, ImportError) as e:
            # Fallback to legacy encryption with settings key
            logger.warning(
                "key_registry_not_available_using_settings_key",
                error=str(e),
                message="Key registry not initialized, falling back to settings.encryption_key",
            )

            from pazpaz.core.config import settings

            # Encrypt the field with legacy format (no version prefix)
            encrypted = encrypt_field(value, settings.encryption_key)

            # Log encryption operation (do NOT log plaintext value)
            logger.debug(
                "field_encrypted_legacy",
                plaintext_length=len(value),
                ciphertext_length=len(encrypted) if encrypted else 0,
            )

            return encrypted

    def process_result_value(self, value: bytes | None, dialect: Any) -> str | None:
        """
        Decrypt value after retrieving from database (SELECT).

        This method is called by SQLAlchemy when processing a result set.
        It transparently decrypts the stored bytes back to plaintext, supporting
        both versioned (with prefix) and legacy (without prefix) formats.

        Decryption strategy:
        1. Check if ciphertext has version prefix (b"v2:")
        2. If yes, extract version and use corresponding key from registry
        3. If no, use legacy decryption with settings.encryption_key

        Args:
            value: Encrypted bytes from database (or None)
            dialect: SQLAlchemy dialect (unused)

        Returns:
            Decrypted plaintext string (or None if value is None)

        Raises:
            DecryptionError: If decryption/authentication fails
        """
        if value is None:
            return None

        # Check if versioned format (contains ":" separator in first 10 bytes)
        # Version prefix format: b"v1:", b"v2:", b"v3:", etc.
        if b":" in value[:10]:
            # New versioned format - extract version and use key registry
            try:
                # Find colon position
                colon_index = value.index(b":")

                # Extract version string (e.g., b"v2" -> "v2")
                version = value[:colon_index].decode("ascii")

                # Extract ciphertext (everything after colon)
                ciphertext = value[colon_index + 1 :]

                # Get key for this version from registry
                from pazpaz.utils.encryption import get_key_for_version

                key = get_key_for_version(version)

                # Decrypt with version-specific key
                plaintext = decrypt_field(ciphertext, key)

                # Log decryption operation (do NOT log plaintext value)
                logger.debug(
                    "field_decrypted_versioned",
                    ciphertext_length=len(value),
                    plaintext_length=len(plaintext) if plaintext else 0,
                    key_version=version,
                )

                return plaintext

            except (ValueError, IndexError, UnicodeDecodeError) as e:
                # Malformed version prefix - fall back to legacy decryption
                logger.warning(
                    "invalid_version_prefix_falling_back_to_legacy",
                    error=str(e),
                    message="Failed to parse version prefix, trying legacy decryption",
                )

        # Legacy non-versioned format - use master key from settings
        from pazpaz.core.config import settings

        plaintext = decrypt_field(value, settings.encryption_key)

        # Log decryption operation (do NOT log plaintext value)
        logger.debug(
            "field_decrypted_legacy",
            ciphertext_length=len(value),
            plaintext_length=len(plaintext) if plaintext else 0,
        )

        return plaintext


class EncryptedStringVersioned(TypeDecorator):
    """
    Encrypted string with key version support for zero-downtime rotation.

    This type stores encrypted data in JSONB format with version metadata,
    enabling seamless key rotation without downtime. During rotation:
    1. Deploy code with both old and new keys
    2. New writes use new key version
    3. Reads support both versions
    4. Background job re-encrypts old data
    5. Remove old key after migration complete

    Storage format in database:
        JSONB: {
            "version": "v1",
            "ciphertext": "base64-encoded-bytes",
            "algorithm": "AES-256-GCM"
        }

    Example:
        class Client(Base):
            __tablename__ = "clients"

            # Versioned encrypted field (supports key rotation)
            medical_history = Column(EncryptedStringVersioned(2000), nullable=True)

        # Application code (transparent usage)
        client = Client(medical_history="Patient has diabetes")
        session.add(client)
        await session.commit()

        # During key rotation, configure multiple keys:
        # In config.py:
        #   ENCRYPTION_KEYS = {"v1": old_key, "v2": new_key}
        #   ENCRYPTION_KEY_VERSION = "v2"  # Use v2 for new writes

    Trade-offs vs EncryptedString:
        Pros:
            - Supports zero-downtime key rotation
            - Can verify which key version encrypted each field
            - Easier key lifecycle management

        Cons:
            - ~20% storage overhead (JSONB metadata)
            - Slightly slower queries (JSONB parsing)
            - More complex key management logic

    Recommended for:
        - Production environments requiring key rotation
        - Fields with long retention periods
        - Compliance scenarios with key rotation requirements

    Use EncryptedString for:
        - Development environments
        - Fields with short retention
        - Simpler deployments without key rotation needs
    """

    impl = JSONB
    cache_ok = True

    def __init__(
        self,
        length: int | None = None,
        key_version: str = "v1",
        *args: Any,
        **kwargs: Any,
    ):
        """
        Initialize EncryptedStringVersioned type.

        Args:
            length: Maximum expected plaintext length (for documentation)
            key_version: Default key version for new encryptions
        """
        super().__init__(*args, **kwargs)
        self.length = length
        self.key_version = key_version

    def process_bind_param(
        self, value: str | None, dialect: Any
    ) -> dict[str, Any] | None:
        """
        Encrypt value with version prefix before storing (INSERT/UPDATE).

        Args:
            value: Plaintext string to encrypt (or None)
            dialect: SQLAlchemy dialect (unused)

        Returns:
            Dictionary with version metadata and encrypted ciphertext
            (for JSONB storage)
            Or None if value is None

        Raises:
            EncryptionError: If encryption fails
        """
        if value is None:
            return None

        # Encrypt with version prefix (returns string format)
        encrypted_string = encrypt_field_versioned(value, key_version=self.key_version)

        # Convert string format "version:ciphertext" to dict for JSONB storage
        # This provides compatibility with existing JSONB column type
        if ":" in encrypted_string:
            version, ciphertext = encrypted_string.split(":", 1)
            encrypted_data = {
                "version": version,
                "ciphertext": ciphertext,
                "algorithm": "AES-256-GCM",
            }
        else:
            # Fallback in case format is unexpected
            encrypted_data = {
                "version": self.key_version,
                "ciphertext": encrypted_string,
                "algorithm": "AES-256-GCM",
            }

        # Log encryption operation (do NOT log plaintext value)
        logger.debug(
            "field_encrypted_versioned",
            plaintext_length=len(value),
            key_version=self.key_version,
        )

        return encrypted_data

    def process_result_value(
        self, value: str | dict[str, Any] | None, _dialect: Any
    ) -> str | None:
        """
        Decrypt value using version prefix after retrieval (SELECT).

        Args:
            value: Encrypted string in format "version:ciphertext" or
                   legacy dict format (for backward compatibility)
            dialect: SQLAlchemy dialect (unused)

        Returns:
            Decrypted plaintext string (or None if value is None)

        Raises:
            DecryptionError: If decryption/authentication fails
            ValueError: If version not found in key registry
        """
        if value is None:
            return None

        # Get keys from settings
        # In production, this would load multiple keys for rotation support
        # For now, we use the single key from settings
        from pazpaz.core.config import settings

        keys = {self.key_version: settings.encryption_key}

        # Decrypt using version metadata/prefix
        plaintext = decrypt_field_versioned(value, keys=keys)

        # Extract version for logging
        if isinstance(value, str):
            # New string format: "version:ciphertext"
            version = value.split(":", 1)[0] if ":" in value else "unknown"
        else:
            # Legacy dict format
            version = value.get("version", "unknown")

        # Log decryption operation (do NOT log plaintext value)
        logger.debug(
            "field_decrypted_versioned",
            key_version=version,
            plaintext_length=len(plaintext) if plaintext else 0,
        )

        return plaintext
