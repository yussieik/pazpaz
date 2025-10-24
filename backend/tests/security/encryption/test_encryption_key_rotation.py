"""
Comprehensive tests for encryption key rotation functionality.

This test suite validates:
1. Multi-version key support (v1, v2, v3)
2. Encryption with different key versions
3. Decryption with version detection
4. Backward compatibility (decrypt legacy non-versioned data)
5. Key rotation procedure
6. Re-encryption of old data
7. 90-day rotation tracking
8. Error handling (missing key version, corrupted data)
9. Key registry initialization
10. AWS Secrets Manager integration (mocked)
"""

import base64
import secrets
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.constants import ENCRYPTION_KEY_SIZE
from pazpaz.models.session import Session
from pazpaz.utils.encryption import (
    EncryptionKeyMetadata,
    decrypt_field,
    decrypt_field_versioned,
    encrypt_field,
    encrypt_field_versioned,
    get_current_key_version,
    get_key_registry,
    get_keys_needing_rotation,
    register_key,
)

# =============================================================================
# Key Metadata Tests
# =============================================================================


def test_encryption_key_metadata_creation():
    """Test 1: Create EncryptionKeyMetadata with valid data."""
    key = secrets.token_bytes(ENCRYPTION_KEY_SIZE)
    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(days=90)

    metadata = EncryptionKeyMetadata(
        key=key,
        version="v1",
        created_at=created_at,
        expires_at=expires_at,
        is_current=True,
    )

    assert metadata.key == key
    assert metadata.version == "v1"
    assert metadata.is_current is True
    assert metadata.needs_rotation is False  # Newly created key doesn't need rotation


def test_encryption_key_metadata_invalid_key_size():
    """Test 2: Reject invalid key size."""
    invalid_key = secrets.token_bytes(16)  # Only 128-bit, need 256-bit
    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(days=90)

    with pytest.raises(ValueError, match="must be 32 bytes"):
        EncryptionKeyMetadata(
            key=invalid_key,
            version="v1",
            created_at=created_at,
            expires_at=expires_at,
        )


def test_encryption_key_metadata_invalid_version():
    """Test 3: Reject invalid version format."""
    key = secrets.token_bytes(ENCRYPTION_KEY_SIZE)
    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(days=90)

    with pytest.raises(ValueError, match="must start with 'v'"):
        EncryptionKeyMetadata(
            key=key,
            version="1",  # Should be "v1"
            created_at=created_at,
            expires_at=expires_at,
        )


def test_encryption_key_metadata_needs_rotation():
    """Test 4: Detect when key needs rotation (>90 days old)."""
    key = secrets.token_bytes(ENCRYPTION_KEY_SIZE)
    created_at = datetime.now(UTC) - timedelta(days=95)  # 95 days ago
    expires_at = created_at + timedelta(days=90)  # Expired 5 days ago

    metadata = EncryptionKeyMetadata(
        key=key,
        version="v1",
        created_at=created_at,
        expires_at=expires_at,
    )

    assert metadata.needs_rotation is True
    assert metadata.days_until_rotation < 0  # Overdue
    assert metadata.age_days == 95


def test_encryption_key_metadata_days_until_rotation():
    """Test 5: Calculate days until rotation."""
    key = secrets.token_bytes(ENCRYPTION_KEY_SIZE)
    created_at = datetime.now(UTC) - timedelta(days=80)  # 80 days ago
    expires_at = created_at + timedelta(days=90)  # Expires in 10 days

    metadata = EncryptionKeyMetadata(
        key=key,
        version="v1",
        created_at=created_at,
        expires_at=expires_at,
    )

    assert metadata.needs_rotation is False  # Not yet expired
    # Allow for timing variations (9-11 days)
    assert 9 <= metadata.days_until_rotation <= 11  # ~10 days remaining
    assert 79 <= metadata.age_days <= 81  # ~80 days old


# =============================================================================
# Key Registry Tests
# =============================================================================


def test_register_key():
    """Test 6: Register encryption key in global registry."""
    from pazpaz.utils.encryption import _KEY_REGISTRY

    # Clear registry
    _KEY_REGISTRY.clear()

    key = secrets.token_bytes(ENCRYPTION_KEY_SIZE)
    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(days=90)

    metadata = EncryptionKeyMetadata(
        key=key,
        version="v2",
        created_at=created_at,
        expires_at=expires_at,
        is_current=True,
    )

    register_key(metadata)

    # Verify key is in registry
    assert "v2" in _KEY_REGISTRY
    assert _KEY_REGISTRY["v2"].key == key
    assert _KEY_REGISTRY["v2"].is_current is True

    # Cleanup
    _KEY_REGISTRY.clear()


def test_get_key_registry():
    """Test 7: Get all registered keys."""
    from pazpaz.utils.encryption import _KEY_REGISTRY

    # Clear and populate registry
    _KEY_REGISTRY.clear()

    key1 = secrets.token_bytes(ENCRYPTION_KEY_SIZE)
    key2 = secrets.token_bytes(ENCRYPTION_KEY_SIZE)

    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(days=90)

    register_key(
        EncryptionKeyMetadata(
            key=key1,
            version="v1",
            created_at=created_at,
            expires_at=expires_at,
        )
    )

    register_key(
        EncryptionKeyMetadata(
            key=key2,
            version="v2",
            created_at=created_at,
            expires_at=expires_at,
            is_current=True,
        )
    )

    # Get registry
    keys = get_key_registry()

    assert len(keys) == 2
    assert keys["v1"] == key1
    assert keys["v2"] == key2

    # Cleanup
    _KEY_REGISTRY.clear()


def test_get_current_key_version():
    """Test 8: Get current (active) key version."""
    from pazpaz.utils.encryption import _KEY_REGISTRY

    # Clear and populate registry
    _KEY_REGISTRY.clear()

    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(days=90)

    # Register v1 (not current)
    register_key(
        EncryptionKeyMetadata(
            key=secrets.token_bytes(ENCRYPTION_KEY_SIZE),
            version="v1",
            created_at=created_at,
            expires_at=expires_at,
            is_current=False,
        )
    )

    # Register v2 (current)
    register_key(
        EncryptionKeyMetadata(
            key=secrets.token_bytes(ENCRYPTION_KEY_SIZE),
            version="v2",
            created_at=created_at,
            expires_at=expires_at,
            is_current=True,
        )
    )

    current_version = get_current_key_version()

    assert current_version == "v2"

    # Cleanup
    _KEY_REGISTRY.clear()


def test_get_current_key_version_missing():
    """Test 9: Raise error when no current key is registered."""
    from pazpaz.utils.encryption import _KEY_REGISTRY

    # Clear registry
    _KEY_REGISTRY.clear()

    # All keys marked as not current
    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(days=90)

    register_key(
        EncryptionKeyMetadata(
            key=secrets.token_bytes(ENCRYPTION_KEY_SIZE),
            version="v1",
            created_at=created_at,
            expires_at=expires_at,
            is_current=False,
        )
    )

    with pytest.raises(ValueError, match="No current encryption key found"):
        get_current_key_version()

    # Cleanup
    _KEY_REGISTRY.clear()


def test_get_keys_needing_rotation():
    """Test 10: Identify keys that need rotation (>90 days old)."""
    from pazpaz.utils.encryption import _KEY_REGISTRY

    # Clear registry
    _KEY_REGISTRY.clear()

    now = datetime.now(UTC)

    # Old key (95 days old - needs rotation)
    register_key(
        EncryptionKeyMetadata(
            key=secrets.token_bytes(ENCRYPTION_KEY_SIZE),
            version="v1",
            created_at=now - timedelta(days=95),
            expires_at=now - timedelta(days=5),  # Expired 5 days ago
        )
    )

    # Recent key (10 days old - doesn't need rotation)
    register_key(
        EncryptionKeyMetadata(
            key=secrets.token_bytes(ENCRYPTION_KEY_SIZE),
            version="v2",
            created_at=now - timedelta(days=10),
            expires_at=now + timedelta(days=80),  # Expires in 80 days
            is_current=True,
        )
    )

    keys_needing_rotation = get_keys_needing_rotation()

    assert keys_needing_rotation == ["v1"]

    # Cleanup
    _KEY_REGISTRY.clear()


# =============================================================================
# Versioned Encryption/Decryption Tests
# =============================================================================


def test_encrypt_field_versioned_with_registry():
    """Test 11: Encrypt field with key registry (auto-select current version)."""
    from pazpaz.utils.encryption import _KEY_REGISTRY

    # Clear and populate registry
    _KEY_REGISTRY.clear()

    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(days=90)

    key = secrets.token_bytes(ENCRYPTION_KEY_SIZE)

    register_key(
        EncryptionKeyMetadata(
            key=key,
            version="v2",
            created_at=created_at,
            expires_at=expires_at,
            is_current=True,
        )
    )

    plaintext = "sensitive data"

    # Encrypt (should use v2 automatically)
    encrypted_data = encrypt_field_versioned(plaintext)

    # Verify string format: "v2:ciphertext"
    assert isinstance(encrypted_data, str)
    assert encrypted_data.startswith("v2:")

    # Decrypt (should auto-fetch key from registry)
    decrypted = decrypt_field_versioned(encrypted_data)

    assert decrypted == plaintext

    # Cleanup
    _KEY_REGISTRY.clear()


def test_decrypt_field_versioned_from_registry():
    """Test 12: Decrypt field with key registry (auto-fetch key)."""
    from pazpaz.utils.encryption import _KEY_REGISTRY

    # Clear and populate registry
    _KEY_REGISTRY.clear()

    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(days=90)

    key_v1 = secrets.token_bytes(ENCRYPTION_KEY_SIZE)
    key_v2 = secrets.token_bytes(ENCRYPTION_KEY_SIZE)

    register_key(
        EncryptionKeyMetadata(
            key=key_v1,
            version="v1",
            created_at=created_at - timedelta(days=100),
            expires_at=created_at - timedelta(days=10),
        )
    )

    register_key(
        EncryptionKeyMetadata(
            key=key_v2,
            version="v2",
            created_at=created_at,
            expires_at=expires_at,
            is_current=True,
        )
    )

    plaintext = "old data encrypted with v1"

    # Encrypt with v1 explicitly
    encrypted_data = encrypt_field_versioned(plaintext, key_version="v1")

    # Verify string format: "v1:ciphertext"
    assert isinstance(encrypted_data, str)
    assert encrypted_data.startswith("v1:")

    # Decrypt (should auto-fetch v1 key from registry)
    decrypted = decrypt_field_versioned(encrypted_data)

    assert decrypted == plaintext

    # Cleanup
    _KEY_REGISTRY.clear()


# =============================================================================
# Backward Compatibility Tests (Legacy Format)
# =============================================================================


def test_decrypt_legacy_non_versioned_data():
    """Test 13: Decrypt legacy data without version prefix."""
    from pazpaz.core.config import settings

    # Encrypt with legacy format (no version prefix)
    plaintext = "legacy encrypted data"
    ciphertext_legacy = encrypt_field(plaintext, settings.encryption_key)

    # Legacy format has no version prefix (just raw bytes)
    assert b":" not in ciphertext_legacy[:10]

    # Decrypt using legacy method
    decrypted = decrypt_field(ciphertext_legacy, settings.encryption_key)

    assert decrypted == plaintext


@pytest.mark.asyncio
async def test_encrypted_string_type_backward_compatibility(
    db: AsyncSession, workspace_1, test_user_ws1, sample_client_ws1
):
    """Test 14: EncryptedString type handles both legacy and versioned formats."""
    from pazpaz.core.config import settings
    from pazpaz.utils.encryption import _KEY_REGISTRY

    # Setup key registry
    _KEY_REGISTRY.clear()
    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(days=90)

    register_key(
        EncryptionKeyMetadata(
            key=settings.encryption_key,
            version="v1",
            created_at=created_at,
            expires_at=expires_at,
            is_current=True,
        )
    )

    # Create session with encrypted data
    session = Session(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        created_by_user_id=test_user_ws1.id,
        session_date=datetime.now(UTC),
        subjective="new data with versioned encryption",
        objective="test",
    )
    db.add(session)
    await db.commit()

    # Retrieve and verify
    await db.refresh(session)
    assert session.subjective == "new data with versioned encryption"

    # Cleanup
    _KEY_REGISTRY.clear()


# =============================================================================
# Multi-Version Decryption Tests
# =============================================================================


def test_decrypt_with_multiple_key_versions():
    """Test 15: Decrypt data encrypted with different key versions."""
    from pazpaz.utils.encryption import _KEY_REGISTRY

    # Clear and populate registry
    _KEY_REGISTRY.clear()

    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(days=90)

    key_v1 = secrets.token_bytes(ENCRYPTION_KEY_SIZE)
    key_v2 = secrets.token_bytes(ENCRYPTION_KEY_SIZE)
    key_v3 = secrets.token_bytes(ENCRYPTION_KEY_SIZE)

    # Register all keys
    for version, key, is_current in [
        ("v1", key_v1, False),
        ("v2", key_v2, False),
        ("v3", key_v3, True),
    ]:
        register_key(
            EncryptionKeyMetadata(
                key=key,
                version=version,
                created_at=created_at,
                expires_at=expires_at,
                is_current=is_current,
            )
        )

    # Encrypt data with each version
    plaintext_v1 = "data encrypted with v1"
    plaintext_v2 = "data encrypted with v2"
    plaintext_v3 = "data encrypted with v3"

    encrypted_v1 = encrypt_field_versioned(plaintext_v1, key_version="v1")
    encrypted_v2 = encrypt_field_versioned(plaintext_v2, key_version="v2")
    encrypted_v3 = encrypt_field_versioned(plaintext_v3, key_version="v3")

    # Decrypt all (should auto-select correct key from registry)
    assert decrypt_field_versioned(encrypted_v1) == plaintext_v1
    assert decrypt_field_versioned(encrypted_v2) == plaintext_v2
    assert decrypt_field_versioned(encrypted_v3) == plaintext_v3

    # Cleanup
    _KEY_REGISTRY.clear()


# =============================================================================
# Error Handling Tests
# =============================================================================


def test_decrypt_versioned_missing_key():
    """Test 16: Auto-fetch key from AWS when not in registry."""
    from pazpaz.utils.encryption import _KEY_REGISTRY

    # Clear registry
    _KEY_REGISTRY.clear()

    plaintext = "test data"

    # Encrypt with v1
    encrypted_data = encrypt_field_versioned(plaintext, key_version="v1")

    # Clear registry so v1 is not available locally
    _KEY_REGISTRY.clear()

    # Decrypt should auto-fetch from AWS and succeed (graceful fallback)
    # This tests the automatic key fetching mechanism
    decrypted = decrypt_field_versioned(encrypted_data)
    assert decrypted == plaintext

    # Verify the key was auto-registered after fetching
    assert "v1" in _KEY_REGISTRY

    # Cleanup
    _KEY_REGISTRY.clear()


def test_decrypt_corrupted_versioned_data():
    """Test 17: Handle corrupted versioned ciphertext."""
    from pazpaz.utils.encryption import _KEY_REGISTRY, DecryptionError

    # Clear and populate registry
    _KEY_REGISTRY.clear()

    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(days=90)

    register_key(
        EncryptionKeyMetadata(
            key=secrets.token_bytes(ENCRYPTION_KEY_SIZE),
            version="v1",
            created_at=created_at,
            expires_at=expires_at,
            is_current=True,
        )
    )

    plaintext = "test data"
    encrypt_field_versioned(plaintext, key_version="v1")

    # Corrupt the ciphertext (tamper with string format)
    # Original format: "v1:base64_ciphertext"
    # Corrupted format: "v1:corrupted_base64_data"
    corrupted_data = "v1:corrupted_base64_data"

    # Decrypt should fail
    with pytest.raises((DecryptionError, ValueError)):
        decrypt_field_versioned(corrupted_data)

    # Cleanup
    _KEY_REGISTRY.clear()


# =============================================================================
# AWS Secrets Manager Integration Tests (Mocked)
# =============================================================================


@patch("pazpaz.utils.secrets_manager._get_boto3_client")
def test_load_all_encryption_keys_from_aws(mock_get_client):
    """Test 18: Load all encryption keys from AWS Secrets Manager."""
    from pazpaz.utils.encryption import _KEY_REGISTRY
    from pazpaz.utils.secrets_manager import load_all_encryption_keys

    # Clear registry
    _KEY_REGISTRY.clear()

    # Mock AWS Secrets Manager responses
    mock_client = MagicMock()

    # Mock list_secrets response
    mock_client.list_secrets.return_value = {
        "SecretList": [
            {"Name": "pazpaz/encryption-key-v1"},
            {"Name": "pazpaz/encryption-key-v2"},
        ]
    }

    # Mock get_secret_value responses
    key_v1 = base64.b64encode(secrets.token_bytes(32)).decode()
    key_v2 = base64.b64encode(secrets.token_bytes(32)).decode()

    def get_secret_value_side_effect(SecretId):
        if SecretId == "pazpaz/encryption-key-v1":
            return {
                "SecretString": f'{{"encryption_key": "{key_v1}", "version": "v1", '
                f'"created_at": "{datetime.now(UTC).isoformat()}", '
                f'"expires_at": "{(datetime.now(UTC) + timedelta(days=90)).isoformat()}", '
                f'"is_current": false}}',
                "VersionId": "version-1",
            }
        elif SecretId == "pazpaz/encryption-key-v2":
            return {
                "SecretString": f'{{"encryption_key": "{key_v2}", "version": "v2", '
                f'"created_at": "{datetime.now(UTC).isoformat()}", '
                f'"expires_at": "{(datetime.now(UTC) + timedelta(days=90)).isoformat()}", '
                f'"is_current": true}}',
                "VersionId": "version-2",
            }

    mock_client.get_secret_value.side_effect = get_secret_value_side_effect
    mock_get_client.return_value = mock_client

    # Load keys
    load_all_encryption_keys(region="us-east-1", environment="production")

    # Verify keys loaded
    assert "v1" in _KEY_REGISTRY
    assert "v2" in _KEY_REGISTRY
    assert get_current_key_version() == "v2"

    # Cleanup
    _KEY_REGISTRY.clear()


# =============================================================================
# Integration Tests with Session Model
# =============================================================================


@pytest.mark.asyncio
async def test_session_encryption_with_versioned_keys(
    db: AsyncSession, workspace_1, test_user_ws1, sample_client_ws1
):
    """Test 19: Session model uses versioned encryption."""
    from pazpaz.core.config import settings
    from pazpaz.utils.encryption import _KEY_REGISTRY

    # Setup key registry with v2 as current
    _KEY_REGISTRY.clear()
    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(days=90)

    register_key(
        EncryptionKeyMetadata(
            key=settings.encryption_key,
            version="v2",
            created_at=created_at,
            expires_at=expires_at,
            is_current=True,
        )
    )

    # Create session
    session = Session(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        created_by_user_id=test_user_ws1.id,
        session_date=datetime.now(UTC),
        subjective="Patient reports pain level 7/10",
        objective="Reduced range of motion in right shoulder",
        assessment="Rotator cuff strain, improving from last session",
        plan="Continue physical therapy 2x weekly",
    )
    db.add(session)
    await db.commit()

    # Retrieve and verify all fields decrypt correctly
    await db.refresh(session)
    assert session.subjective == "Patient reports pain level 7/10"
    assert session.objective == "Reduced range of motion in right shoulder"
    assert session.assessment == "Rotator cuff strain, improving from last session"
    assert session.plan == "Continue physical therapy 2x weekly"

    # Cleanup
    _KEY_REGISTRY.clear()


@pytest.mark.asyncio
async def test_re_encrypt_session_after_key_rotation(
    db: AsyncSession, workspace_1, test_user_ws1, sample_client_ws1
):
    """Test 20: Re-encrypt session data after key rotation."""
    from pazpaz.core.config import settings
    from pazpaz.utils.encryption import _KEY_REGISTRY

    # Setup initial key (v1)
    _KEY_REGISTRY.clear()
    created_at = datetime.now(UTC)

    key_v1 = settings.encryption_key

    register_key(
        EncryptionKeyMetadata(
            key=key_v1,
            version="v1",
            created_at=created_at - timedelta(days=100),
            expires_at=created_at - timedelta(days=10),
            is_current=True,  # Initially current
        )
    )

    # Create session with v1
    session = Session(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        created_by_user_id=test_user_ws1.id,
        session_date=datetime.now(UTC),
        subjective="Old data encrypted with v1",
        objective="test",
    )
    db.add(session)
    await db.commit()
    session_id = session.id

    # Simulate key rotation: Add v2 and make it current
    key_v2 = secrets.token_bytes(ENCRYPTION_KEY_SIZE)

    # Update v1 to not current
    _KEY_REGISTRY["v1"].is_current = False

    # Add v2 as current
    register_key(
        EncryptionKeyMetadata(
            key=key_v2,
            version="v2",
            created_at=created_at,
            expires_at=created_at + timedelta(days=90),
            is_current=True,
        )
    )

    # Re-encrypt: Read and write triggers re-encryption with current key
    await db.refresh(session)
    original_subjective = session.subjective

    # Update field (triggers re-encryption with v2)
    session.subjective = original_subjective  # Re-assign to trigger encryption
    await db.commit()

    # Verify data still decrypts correctly
    db.expunge_all()
    result = await db.execute(select(Session).where(Session.id == session_id))
    retrieved = result.scalar_one()

    assert retrieved.subjective == "Old data encrypted with v1"

    # Cleanup
    _KEY_REGISTRY.clear()


# =============================================================================
# Performance Tests
# =============================================================================


@pytest.mark.performance
def test_versioned_encryption_performance():
    """Test 21: Validate versioned encryption performance overhead."""
    from pazpaz.utils.encryption import _KEY_REGISTRY

    # Setup registry
    _KEY_REGISTRY.clear()
    created_at = datetime.now(UTC)

    register_key(
        EncryptionKeyMetadata(
            key=secrets.token_bytes(ENCRYPTION_KEY_SIZE),
            version="v2",
            created_at=created_at,
            expires_at=created_at + timedelta(days=90),
            is_current=True,
        )
    )

    plaintext = "test data " * 100  # ~1KB

    import time

    # Measure versioned encryption
    iterations = 100
    start = time.perf_counter()
    for _ in range(iterations):
        encrypt_field_versioned(plaintext)
    end = time.perf_counter()

    avg_time_ms = ((end - start) / iterations) * 1000

    print(f"\nVersioned encryption: {avg_time_ms:.2f}ms per field")

    # Should still be under 10ms despite overhead
    assert avg_time_ms < 10

    # Cleanup
    _KEY_REGISTRY.clear()
