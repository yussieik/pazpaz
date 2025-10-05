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
    SQLAlchemy type for transparent encryption/decryption of string fields.

    This type automatically encrypts data on INSERT/UPDATE and decrypts on SELECT,
    making encryption transparent to application code. The encrypted data is stored
    as BYTEA (binary) in PostgreSQL.

    Storage format in database:
        BYTEA: [12-byte nonce][ciphertext][16-byte authentication tag]

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

        # Decryption is automatic on SELECT
        result = await session.get(Client, client_id)
        print(result.medical_history)  # "Patient has diabetes" (decrypted)

    Args:
        length: Maximum plaintext length (for documentation/validation)
                Note: Actual database column will be larger due to encryption overhead
                (12 bytes nonce + 16 bytes tag = 28 bytes extra)

    Security considerations:
        - Cannot perform LIKE queries on encrypted fields
        - Cannot create functional indexes on encrypted content
        - Decrypted values exist in application memory
        - All queries must decrypt entire field (no partial decryption)
        - Use audit logging to track access to encrypted fields
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
        It transparently encrypts the plaintext string before storage.

        Args:
            value: Plaintext string to encrypt (or None)
            dialect: SQLAlchemy dialect (unused)

        Returns:
            Encrypted bytes in format: nonce || ciphertext || tag
            Or None if value is None

        Raises:
            EncryptionError: If encryption fails
        """
        if value is None:
            return None

        # Get encryption key from settings
        from pazpaz.core.config import settings

        # Encrypt the field
        encrypted = encrypt_field(value, settings.encryption_key)

        # Log encryption operation (do NOT log plaintext value)
        logger.debug(
            "field_encrypted",
            plaintext_length=len(value),
            ciphertext_length=len(encrypted) if encrypted else 0,
        )

        return encrypted

    def process_result_value(self, value: bytes | None, dialect: Any) -> str | None:
        """
        Decrypt value after retrieving from database (SELECT).

        This method is called by SQLAlchemy when processing a result set.
        It transparently decrypts the stored bytes back to plaintext.

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

        # Get encryption key from settings
        from pazpaz.core.config import settings

        # Decrypt the field
        plaintext = decrypt_field(value, settings.encryption_key)

        # Log decryption operation (do NOT log plaintext value)
        logger.debug(
            "field_decrypted",
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
        Encrypt value with version metadata before storing (INSERT/UPDATE).

        Args:
            value: Plaintext string to encrypt (or None)
            dialect: SQLAlchemy dialect (unused)

        Returns:
            Dictionary with version metadata and encrypted ciphertext
            Or None if value is None

        Raises:
            EncryptionError: If encryption fails
        """
        if value is None:
            return None

        # Encrypt with version metadata
        encrypted_data = encrypt_field_versioned(value, key_version=self.key_version)

        # Log encryption operation (do NOT log plaintext value)
        logger.debug(
            "field_encrypted_versioned",
            plaintext_length=len(value),
            key_version=self.key_version,
        )

        return encrypted_data

    def process_result_value(
        self, value: dict[str, Any] | None, dialect: Any
    ) -> str | None:
        """
        Decrypt value using version metadata after retrieval (SELECT).

        Args:
            value: Dictionary with version metadata from database (or None)
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

        # Decrypt using version metadata
        plaintext = decrypt_field_versioned(value, keys=keys)

        # Log decryption operation (do NOT log plaintext value)
        logger.debug(
            "field_decrypted_versioned",
            key_version=value.get("version"),
            plaintext_length=len(plaintext) if plaintext else 0,
        )

        return plaintext
