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

Performance targets:
- Encryption: <5ms per field
- Decryption: <10ms per field
- Bulk operations: <100ms for 100 fields

Usage:
    from pazpaz.core.config import settings
    from pazpaz.utils.encryption import encrypt_field, decrypt_field

    # Simple encryption/decryption
    ciphertext = encrypt_field("sensitive data", settings.encryption_key)
    plaintext = decrypt_field(ciphertext, settings.encryption_key)

    # Versioned encryption (for key rotation)
    encrypted_data = encrypt_field_versioned("sensitive data", key_version="v1")
    plaintext = decrypt_field_versioned(encrypted_data, {"v1": key_v1, "v2": key_v2})
"""

import base64
import secrets
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
    plaintext: str | None, key_version: str = "v1"
) -> dict[str, Any] | None:
    """
    Encrypt field with version metadata for key rotation support.

    This function wraps encrypt_field() and adds metadata to support
    zero-downtime key rotation. The encrypted data includes:
    - version: Key version identifier (e.g., "v1", "v2")
    - ciphertext: Base64-encoded encrypted bytes
    - algorithm: Encryption algorithm identifier

    During key rotation:
    1. Deploy new code with both old and new keys
    2. Start encrypting with new key version
    3. Background job re-encrypts old data
    4. Remove old key after all data migrated

    Args:
        plaintext: The plain text to encrypt (or None)
        key_version: Key version identifier (default: "v1")

    Returns:
        Dictionary with version metadata and base64-encoded ciphertext:
        {
            "version": "v1",
            "ciphertext": "base64-encoded-bytes",
            "algorithm": "AES-256-GCM"
        }
        Or None if plaintext is None

    Raises:
        ValueError: If key not found in key registry
        EncryptionError: If encryption fails

    Example:
        >>> from pazpaz.core.config import settings
        >>> encrypted = encrypt_field_versioned("sensitive data", key_version="v1")
        >>> encrypted
        {'version': 'v1', 'ciphertext': 'SGVsbG8...', 'algorithm': 'AES-256-GCM'}
    """
    if plaintext is None:
        return None

    # Import here to avoid circular dependency
    from pazpaz.core.config import settings

    # Get key for this version
    # For now, we only have one key. In production with key rotation,
    # you would maintain a registry: {"v1": key1, "v2": key2, ...}
    key = settings.encryption_key

    # Encrypt the field
    ciphertext = encrypt_field(plaintext, key)

    if ciphertext is None:
        return None

    # Return versioned structure
    return {
        "version": key_version,
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "algorithm": "AES-256-GCM",
    }


def decrypt_field_versioned(
    encrypted_data: dict[str, Any] | None, keys: dict[str, bytes] | None = None
) -> str | None:
    """
    Decrypt field using version metadata to select correct key.

    This function enables zero-downtime key rotation by selecting the
    appropriate decryption key based on the version metadata stored
    with the encrypted data.

    Args:
        encrypted_data: Dictionary from encrypt_field_versioned() with keys:
                       - version: Key version identifier
                       - ciphertext: Base64-encoded encrypted bytes
                       - algorithm: Encryption algorithm (must be "AES-256-GCM")
        keys: Dictionary mapping version -> key bytes
              If None, uses current encryption key from settings

    Returns:
        Decrypted plaintext string (or None if encrypted_data is None)

    Raises:
        ValueError: If version not found in keys, invalid format, or wrong algorithm
        DecryptionError: If decryption/authentication fails

    Example:
        >>> keys = {"v1": old_key, "v2": new_key}
        >>> plaintext = decrypt_field_versioned(encrypted_data, keys)
        >>> plaintext
        'sensitive data'
    """
    if encrypted_data is None:
        return None

    # Validate structure
    if not isinstance(encrypted_data, dict):
        raise ValueError(
            f"encrypted_data must be a dict, got {type(encrypted_data).__name__}"
        )

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

    # Get key for this version
    version = encrypted_data["version"]

    if keys is None:
        # Use current key from settings (single-key mode)
        from pazpaz.core.config import settings

        key = settings.encryption_key
    else:
        # Multi-key mode (key rotation)
        if version not in keys:
            raise ValueError(
                f"Key version '{version}' not found in key registry. "
                f"Available versions: {list(keys.keys())}"
            )
        key = keys[version]

    # Decode base64 ciphertext
    try:
        ciphertext = base64.b64decode(encrypted_data["ciphertext"])
    except Exception as e:
        raise ValueError(f"Invalid base64 ciphertext: {e}") from e

    # Decrypt
    return decrypt_field(ciphertext, key)
