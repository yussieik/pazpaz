"""
Application-level encryption utilities for PHI/PII data.

This module provides AES-256-GCM authenticated encryption for sensitive data fields.
It supports both simple encryption and versioned encryption for key rotation.

Security properties:
- AES-256-GCM authenticated encryption (AEAD)
- Random 12-byte nonce per encryption (never reused)
- 16-byte authentication tag
- Constant-time operations via cryptography library
- Key versioning for zero-downtime key rotation
- 90-day key rotation policy (HIPAA requirement)

Performance targets:
- Encryption: <5ms per field
- Decryption: <10ms per field
- Bulk operations: <100ms for 100 fields

Key Rotation Architecture:
- Multiple key versions stored in AWS Secrets Manager (v1, v2, v3, ...)
- Each ciphertext includes version prefix for key selection
- Old data decrypts with old keys (backward compatible)
- New data encrypts with current key version
- Background job re-encrypts old data to latest version
- Keys expire after 90 days (HIPAA requirement)

Usage:
    from pazpaz.core.config import settings
    from pazpaz.utils.encryption import encrypt_field, decrypt_field

    # Simple encryption/decryption (legacy, non-versioned)
    ciphertext = encrypt_field("sensitive data", settings.encryption_key)
    plaintext = decrypt_field(ciphertext, settings.encryption_key)

    # Versioned encryption (for key rotation)
    encrypted_data = encrypt_field_versioned("sensitive data", key_version="v2")
    plaintext = decrypt_field_versioned(encrypted_data)

    # Multi-version decryption (automatic key selection)
    from pazpaz.utils.encryption import get_key_registry
    keys = get_key_registry()  # {"v1": key1, "v2": key2, "v3": key3}
    plaintext = decrypt_field_versioned(encrypted_data, keys)
"""

import base64
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from pazpaz.core.constants import ENCRYPTION_KEY_SIZE, NONCE_SIZE, TAG_SIZE
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


class EncryptionError(Exception):
    """Base exception for encryption operations."""

    pass


class DecryptionError(Exception):
    """Exception raised when decryption or authentication fails."""

    pass


# ============================================================================
# KEY VERSIONING & ROTATION
# ============================================================================


@dataclass
class EncryptionKeyMetadata:
    """
    Metadata for an encryption key version.

    This dataclass tracks metadata for each encryption key version to support
    zero-downtime key rotation and 90-day rotation policy (HIPAA requirement).

    Attributes:
        key: 32-byte AES-256 encryption key
        version: Version identifier (e.g., "v1", "v2", "v3")
        created_at: When the key was created/activated
        expires_at: When the key should be rotated (created_at + 90 days)
        is_current: Whether this is the active key for new encryptions
        rotated_at: When the key was rotated to new version (None if still current)

    HIPAA Requirement:
        Keys must be rotated every 90 days. The needs_rotation property
        returns True when datetime.now() > created_at + 90 days.

    Example:
        >>> key = secrets.token_bytes(32)
        >>> metadata = EncryptionKeyMetadata(
        ...     key=key,
        ...     version="v2",
        ...     created_at=datetime.now(UTC),
        ...     expires_at=datetime.now(UTC) + timedelta(days=90),
        ...     is_current=True,
        ...     rotated_at=None
        ... )
        >>> metadata.needs_rotation
        False
        >>> metadata.days_until_rotation
        90
    """

    key: bytes
    version: str
    created_at: datetime
    expires_at: datetime
    is_current: bool = False
    rotated_at: datetime | None = None

    def __post_init__(self):
        """Validate key metadata after initialization."""
        if len(self.key) != ENCRYPTION_KEY_SIZE:
            raise ValueError(
                f"Encryption key must be {ENCRYPTION_KEY_SIZE} bytes, "
                f"got {len(self.key)} bytes"
            )

        if not self.version.startswith("v"):
            raise ValueError(
                f"Key version must start with 'v' (e.g., 'v1', 'v2'), "
                f"got '{self.version}'"
            )

        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")

    @property
    def needs_rotation(self) -> bool:
        """
        Check if key needs rotation (90-day policy).

        HIPAA requires encryption keys to be rotated every 90 days.
        This property returns True if the current time exceeds the
        creation time plus 90 days.

        Returns:
            True if key needs rotation, False otherwise

        Example:
            >>> metadata.needs_rotation
            False  # If created < 90 days ago
        """
        return datetime.now(UTC) > self.expires_at

    @property
    def days_until_rotation(self) -> int:
        """
        Calculate days remaining until key rotation required.

        Returns:
            Number of days until rotation (negative if overdue)

        Example:
            >>> metadata.days_until_rotation
            85  # If created 5 days ago
        """
        delta = self.expires_at - datetime.now(UTC)
        return delta.days

    @property
    def age_days(self) -> int:
        """
        Calculate key age in days.

        Returns:
            Number of days since key was created

        Example:
            >>> metadata.age_days
            5  # If created 5 days ago
        """
        delta = datetime.now(UTC) - self.created_at
        return delta.days


# Global key registry (populated from AWS Secrets Manager)
# Format: {"v1": EncryptionKeyMetadata(...), "v2": EncryptionKeyMetadata(...), ...}
_KEY_REGISTRY: dict[str, EncryptionKeyMetadata] = {}


def register_key(metadata: EncryptionKeyMetadata) -> None:
    """
    Register an encryption key version in the global registry.

    This function adds a key version to the in-memory registry for use
    in encryption/decryption operations. Keys are typically loaded from
    AWS Secrets Manager at application startup.

    Args:
        metadata: Encryption key metadata

    Raises:
        ValueError: If key version already registered

    Example:
        >>> key = secrets.token_bytes(32)
        >>> metadata = EncryptionKeyMetadata(
        ...     key=key,
        ...     version="v2",
        ...     created_at=datetime.now(UTC),
        ...     expires_at=datetime.now(UTC) + timedelta(days=90),
        ...     is_current=True
        ... )
        >>> register_key(metadata)
    """
    if metadata.version in _KEY_REGISTRY:
        logger.warning(
            "key_already_registered",
            version=metadata.version,
            message="Key version already in registry, replacing",
        )

    _KEY_REGISTRY[metadata.version] = metadata

    logger.info(
        "key_registered",
        version=metadata.version,
        is_current=metadata.is_current,
        age_days=metadata.age_days,
        days_until_rotation=metadata.days_until_rotation,
    )


def get_key_registry() -> dict[str, bytes]:
    """
    Get all registered encryption keys for multi-version decryption.

    This function returns a dictionary mapping version identifiers to
    encryption keys. It's used by decrypt_field_versioned() to support
    decryption of data encrypted with any registered key version.

    Returns:
        Dictionary mapping version -> key bytes
        Example: {"v1": key1_bytes, "v2": key2_bytes, "v3": key3_bytes}

    Example:
        >>> keys = get_key_registry()
        >>> len(keys)
        3
        >>> "v1" in keys
        True
    """
    return {version: metadata.key for version, metadata in _KEY_REGISTRY.items()}


def get_current_key_version() -> str:
    """
    Get the current (active) key version for new encryptions.

    This function returns the version identifier of the key marked as
    is_current=True. All new encryptions should use this key version.

    Returns:
        Current key version (e.g., "v2")

    Raises:
        ValueError: If no current key is registered

    Example:
        >>> get_current_key_version()
        'v2'
    """
    for version, metadata in _KEY_REGISTRY.items():
        if metadata.is_current:
            return version

    # No current key found - this should not happen in production
    raise ValueError(
        "No current encryption key found in registry. "
        "Ensure at least one key is marked as is_current=True."
    )


def get_key_for_version(version: str) -> bytes:
    """
    Get encryption key for a specific version.

    This function retrieves the encryption key for a given version identifier.
    If the key is not in the registry, it attempts to fetch it from AWS
    Secrets Manager and register it.

    Args:
        version: Key version identifier (e.g., "v1", "v2")

    Returns:
        32-byte encryption key

    Raises:
        ValueError: If key version not found in registry or AWS

    Example:
        >>> key = get_key_for_version("v2")
        >>> len(key)
        32
    """
    if version in _KEY_REGISTRY:
        return _KEY_REGISTRY[version].key

    # Key not in registry - try to fetch from AWS Secrets Manager
    logger.info(
        "key_not_in_registry_fetching",
        version=version,
        message="Key version not in registry, attempting to fetch from AWS",
    )

    try:
        from pazpaz.utils.secrets_manager import get_encryption_key_version

        key = get_encryption_key_version(version)

        # Register fetched key
        metadata = EncryptionKeyMetadata(
            key=key,
            version=version,
            created_at=datetime.now(UTC),  # Approximate (actual created_at in AWS)
            expires_at=datetime.now(UTC)
            + timedelta(days=90),  # Approximate expiration
            is_current=False,  # Fetched keys are not current
        )
        register_key(metadata)

        return key

    except Exception as e:
        logger.error(
            "failed_to_fetch_key_version",
            version=version,
            error=str(e),
        )
        raise ValueError(
            f"Encryption key version '{version}' not found in registry or AWS Secrets Manager. "
            f"Available versions: {list(_KEY_REGISTRY.keys())}"
        ) from e


def get_keys_needing_rotation() -> list[str]:
    """
    Get list of key versions that need rotation (>90 days old).

    This function checks all registered keys and returns versions that
    have exceeded the 90-day rotation policy.

    Returns:
        List of key versions needing rotation (e.g., ["v1", "v2"])

    Example:
        >>> get_keys_needing_rotation()
        ['v1']  # If v1 is >90 days old
    """
    return [
        version
        for version, metadata in _KEY_REGISTRY.items()
        if metadata.needs_rotation
    ]


def encrypt_field(plaintext: str | None, key: bytes) -> bytes | None:
    """
    Encrypt a field using AES-256-GCM.

    AES-GCM provides both confidentiality and authenticity (AEAD - Authenticated
    Encryption with Associated Data). The output format is:
    [12-byte nonce][ciphertext][16-byte authentication tag]

    Args:
        plaintext: The plain text to encrypt (or None)
        key: 32-byte encryption key from AWS Secrets Manager or config

    Returns:
        Encrypted bytes in format: nonce || ciphertext || tag
        Or None if plaintext is None

    Raises:
        ValueError: If key is not 32 bytes
        EncryptionError: If encryption fails

    Example:
        >>> from pazpaz.core.config import settings
        >>> ciphertext = encrypt_field("patient has diabetes", settings.encryption_key)
        >>> len(ciphertext)  # 12 (nonce) + len(plaintext) + 16 (tag)
        49
    """
    if plaintext is None:
        return None

    # Validate key size
    if len(key) != ENCRYPTION_KEY_SIZE:
        raise ValueError(
            f"Encryption key must be {ENCRYPTION_KEY_SIZE} bytes, got {len(key)}"
        )

    try:
        # Convert string to bytes
        plaintext_bytes = plaintext.encode("utf-8")

        # Generate random nonce (NEVER reuse with the same key)
        nonce = secrets.token_bytes(NONCE_SIZE)

        # Initialize AESGCM cipher
        aesgcm = AESGCM(key)

        # Encrypt and authenticate
        # Output format: ciphertext || tag (tag is appended automatically)
        ciphertext_with_tag = aesgcm.encrypt(
            nonce, plaintext_bytes, associated_data=None
        )

        # Return: nonce || ciphertext || tag
        return nonce + ciphertext_with_tag

    except Exception as e:
        logger.error(
            "encryption_failed",
            error=str(e),
            plaintext_length=len(plaintext),
            exc_info=True,
        )
        raise EncryptionError(f"Failed to encrypt field: {e}") from e


def decrypt_field(ciphertext: bytes | None, key: bytes) -> str | None:
    """
    Decrypt a field using AES-256-GCM.

    This function verifies the authentication tag before returning plaintext,
    ensuring data integrity and authenticity. If the tag verification fails,
    a DecryptionError is raised (indicating tampering or wrong key).

    Args:
        ciphertext: Encrypted bytes from encrypt_field() in format:
                   [12-byte nonce][ciphertext][16-byte tag]
        key: 32-byte encryption key (same as used for encryption)

    Returns:
        Decrypted plaintext string (or None if ciphertext is None)

    Raises:
        ValueError: If key is not 32 bytes or ciphertext format is invalid
        DecryptionError: If decryption/authentication fails (wrong key or tampering)

    Example:
        >>> from pazpaz.core.config import settings
        >>> plaintext = decrypt_field(ciphertext, settings.encryption_key)
        >>> plaintext
        'patient has diabetes'
    """
    if ciphertext is None:
        return None

    # Validate key size
    if len(key) != ENCRYPTION_KEY_SIZE:
        raise ValueError(
            f"Encryption key must be {ENCRYPTION_KEY_SIZE} bytes, got {len(key)}"
        )

    # Validate ciphertext format
    min_size = NONCE_SIZE + TAG_SIZE
    if len(ciphertext) < min_size:
        raise ValueError(
            f"Ciphertext too short: expected at least {min_size} bytes, "
            f"got {len(ciphertext)}"
        )

    try:
        # Extract nonce and ciphertext_with_tag
        nonce = ciphertext[:NONCE_SIZE]
        ciphertext_with_tag = ciphertext[NONCE_SIZE:]

        # Initialize AESGCM cipher
        aesgcm = AESGCM(key)

        # Decrypt and verify authentication tag
        # This will raise an exception if tag verification fails
        plaintext_bytes = aesgcm.decrypt(
            nonce, ciphertext_with_tag, associated_data=None
        )

        # Convert bytes to string
        return plaintext_bytes.decode("utf-8")

    except Exception as e:
        # Log decryption failure (but don't log ciphertext - could leak data)
        logger.warning(
            "decryption_failed",
            error_type=type(e).__name__,
            ciphertext_length=len(ciphertext),
        )
        raise DecryptionError(
            f"Failed to decrypt field: {type(e).__name__}. "
            "This may indicate wrong key, tampering, or corrupted data."
        ) from e


def encrypt_field_versioned(
    plaintext: str | None, key_version: str | None = None
) -> str | None:
    """
    Encrypt field with version prefix for key rotation support.

    This function wraps encrypt_field() and adds a version prefix to support
    zero-downtime key rotation. The encrypted data format is:
    "version:base64_ciphertext"

    During key rotation:
    1. Deploy new code with both old and new keys
    2. Start encrypting with new key version
    3. Background job re-encrypts old data
    4. Remove old key after all data migrated

    Args:
        plaintext: The plain text to encrypt (or None)
        key_version: Key version identifier (e.g., "v2")
                    If None, uses current key version from registry

    Returns:
        String with version prefix and base64-encoded ciphertext:
        "v2:SGVsbG8..."
        Or None if plaintext is None

    Raises:
        ValueError: If key version not found in key registry
        EncryptionError: If encryption fails

    Example:
        >>> # Encrypt with current key (automatic version selection)
        >>> encrypted = encrypt_field_versioned("sensitive data")
        >>> encrypted
        'v2:SGVsbG8...'

        >>> # Encrypt with specific key version
        >>> encrypted = encrypt_field_versioned("sensitive data", key_version="v1")
        >>> encrypted
        'v1:SGVsbG8...'
    """
    if plaintext is None:
        return None

    # Auto-select current key version if not specified
    if key_version is None:
        try:
            key_version = get_current_key_version()
        except ValueError:
            # Fallback to settings if registry not initialized
            # Auto-register the fallback key as current
            logger.warning(
                "key_registry_not_initialized_using_settings",
                message="Key registry not initialized, falling back to settings.encryption_key as v1",
            )
            from pazpaz.core.config import settings

            key = settings.encryption_key
            key_version = "v1"

            # Auto-register fallback key as current
            metadata = EncryptionKeyMetadata(
                key=key,
                version=key_version,
                created_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(days=90),
                is_current=True,
            )
            register_key(metadata)
        else:
            # Get key from registry
            key = get_key_for_version(key_version)
    else:
        # Get key for specified version
        key = get_key_for_version(key_version)

    # Encrypt the field
    ciphertext = encrypt_field(plaintext, key)

    if ciphertext is None:
        return None

    logger.debug(
        "field_encrypted_versioned",
        key_version=key_version,
        plaintext_length=len(plaintext),
    )

    # Return versioned string format: "version:ciphertext"
    return f"{key_version}:{base64.b64encode(ciphertext).decode('ascii')}"


def decrypt_field_versioned(
    encrypted_data: str | dict[str, Any] | None, keys: dict[str, bytes] | None = None
) -> str | None:
    """
    Decrypt field using version prefix to select correct key.

    This function enables zero-downtime key rotation by selecting the
    appropriate decryption key based on the version prefix in the
    encrypted data string.

    Key Selection Strategy:
    1. If `keys` dict provided: Use specified keys (manual multi-version)
    2. If `keys` is None: Auto-fetch from key registry (recommended)
    3. Fallback: Use settings.encryption_key if registry not initialized

    Args:
        encrypted_data: String from encrypt_field_versioned() in format:
                       "version:base64_ciphertext" (e.g., "v1:SGVsbG8...")
                       OR legacy dict format (for backward compatibility)
        keys: Optional dictionary mapping version -> key bytes
              If None, uses key registry (supports all registered versions)

    Returns:
        Decrypted plaintext string (or None if encrypted_data is None)

    Raises:
        ValueError: If version not found in keys or invalid format
        DecryptionError: If decryption/authentication fails

    Example:
        >>> # Automatic key selection from registry (recommended)
        >>> plaintext = decrypt_field_versioned("v1:SGVsbG8...")
        >>> plaintext
        'sensitive data'

        >>> # Manual key specification (for testing)
        >>> keys = {"v1": old_key, "v2": new_key}
        >>> plaintext = decrypt_field_versioned("v1:SGVsbG8...", keys)
        >>> plaintext
        'sensitive data'
    """
    if encrypted_data is None:
        return None

    # Support both string format (current) and dict format (legacy)
    if isinstance(encrypted_data, dict):
        # Legacy dict format: {"version": "v1", "ciphertext": "...", "algorithm": "..."}
        required_keys = {"version", "ciphertext", "algorithm"}
        if not required_keys.issubset(encrypted_data.keys()):
            raise ValueError(
                f"encrypted_data missing required keys. "
                f"Expected: {required_keys}, got: {set(encrypted_data.keys())}"
            )

        # Validate algorithm
        algorithm = encrypted_data["algorithm"]
        if algorithm != "AES-256-GCM":
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        version = encrypted_data["version"]
        ciphertext_b64 = encrypted_data["ciphertext"]

    elif isinstance(encrypted_data, str):
        # Current string format: "version:base64_ciphertext"
        if ":" not in encrypted_data:
            raise ValueError(
                f"Invalid encrypted_data format. Expected 'version:ciphertext', got: {encrypted_data[:50]}"
            )

        parts = encrypted_data.split(":", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Invalid encrypted_data format. Expected 'version:ciphertext', got: {encrypted_data[:50]}"
            )

        version = parts[0]
        ciphertext_b64 = parts[1]

        # Validate version format
        if not version.startswith("v"):
            raise ValueError(
                f"Invalid version format. Expected 'vN', got: {version}"
            )

    else:
        raise ValueError(
            f"encrypted_data must be str or dict, got {type(encrypted_data).__name__}"
        )

    # Get key for this version
    if keys is None:
        # Auto-fetch from key registry (supports all registered versions)
        try:
            key = get_key_for_version(version)
            logger.debug(
                "field_decrypted_versioned_from_registry",
                key_version=version,
            )
        except ValueError as e:
            # Fallback to settings if registry not initialized
            logger.warning(
                "key_registry_not_initialized_using_settings_fallback",
                key_version=version,
                message="Key registry not initialized, falling back to settings.encryption_key",
            )
            from pazpaz.core.config import settings

            key = settings.encryption_key
    else:
        # Manual key specification (multi-key mode)
        if version not in keys:
            raise ValueError(
                f"Key version '{version}' not found in provided keys. "
                f"Available versions: {list(keys.keys())}"
            )
        key = keys[version]
        logger.debug(
            "field_decrypted_versioned_from_manual_keys",
            key_version=version,
        )

    # Decode base64 ciphertext
    try:
        ciphertext = base64.b64decode(ciphertext_b64)
    except Exception as e:
        raise ValueError(f"Invalid base64 ciphertext: {e}") from e

    # Decrypt
    return decrypt_field(ciphertext, key)
