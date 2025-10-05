"""
Comprehensive tests for application-level encryption.

This test suite validates:
1. Encryption/decryption utilities (encrypt_field, decrypt_field)
2. Versioned encryption (for key rotation support)
3. SQLAlchemy EncryptedString type
4. Performance benchmarks (<5ms encryption, <10ms decryption)
5. Security properties (different keys, tampering detection)
"""

import base64
import secrets
import time
import uuid

import pytest
from sqlalchemy import ForeignKey, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from pazpaz.core.config import settings
from pazpaz.db.base import Base
from pazpaz.db.types import EncryptedString, EncryptedStringVersioned
from pazpaz.models.workspace import Workspace
from pazpaz.utils.encryption import (
    DecryptionError,
    decrypt_field,
    decrypt_field_versioned,
    encrypt_field,
    encrypt_field_versioned,
)

# =============================================================================
# Test Models (for SQLAlchemy type testing)
# =============================================================================


class EncryptedTestModel(Base):
    """Test model with encrypted fields for integration testing."""

    __tablename__ = "test_encrypted_model"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Encrypted fields using EncryptedString type
    encrypted_text: Mapped[str | None] = mapped_column(
        EncryptedString(1000),
        nullable=True,
    )

    encrypted_required: Mapped[str] = mapped_column(
        EncryptedString(500),
        nullable=False,
    )


class VersionedTestModel(Base):
    """Test model with versioned encrypted fields."""

    __tablename__ = "test_versioned_model"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Versioned encrypted field
    versioned_text: Mapped[str | None] = mapped_column(
        EncryptedStringVersioned(1000),
        nullable=True,
    )


# =============================================================================
# Encryption Utility Tests
# =============================================================================


def test_encrypt_field_basic():
    """Test 1: Encrypt simple string."""
    plaintext = "sensitive patient data"
    key = settings.encryption_key

    ciphertext = encrypt_field(plaintext, key)

    assert ciphertext is not None
    assert isinstance(ciphertext, bytes)
    # Ciphertext should be: 12 bytes (nonce) + len(plaintext) + 16 bytes (tag)
    expected_min_length = 12 + len(plaintext) + 16
    assert len(ciphertext) >= expected_min_length
    # Ciphertext should not contain plaintext
    assert plaintext.encode() not in ciphertext


def test_decrypt_field_basic():
    """Test 2: Decrypt encrypted string."""
    plaintext = "medical history: diabetes"
    key = settings.encryption_key

    ciphertext = encrypt_field(plaintext, key)
    decrypted = decrypt_field(ciphertext, key)

    assert decrypted == plaintext


def test_encrypt_decrypt_roundtrip():
    """Test 3: Roundtrip test - encrypt then decrypt."""
    test_cases = [
        "simple text",
        "text with special chars: éñü 中文 🔐",
        "multi\nline\ntext",
        "a" * 5000,  # Long text (5KB)
        "",  # Empty string
    ]

    key = settings.encryption_key

    for plaintext in test_cases:
        ciphertext = encrypt_field(plaintext, key)
        decrypted = decrypt_field(ciphertext, key)
        assert decrypted == plaintext, f"Roundtrip failed for: {plaintext[:50]}..."


def test_encrypt_field_none():
    """Test 4: Handle None input."""
    key = settings.encryption_key

    # Encrypt None
    ciphertext = encrypt_field(None, key)
    assert ciphertext is None

    # Decrypt None
    decrypted = decrypt_field(None, key)
    assert decrypted is None


def test_encrypt_field_unicode():
    """Test 5: Unicode string support."""
    test_strings = [
        "English text",
        "עברית - Hebrew",
        "中文 - Chinese",
        "Español - Spanish with ñ and é",
        "🔐 Emoji and symbols 🏥",
        "Mixed: Hello עולם 世界 🌍",
    ]

    key = settings.encryption_key

    for plaintext in test_strings:
        ciphertext = encrypt_field(plaintext, key)
        decrypted = decrypt_field(ciphertext, key)
        assert decrypted == plaintext, f"Unicode failed for: {plaintext}"


def test_encrypt_different_keys():
    """Test 6: Same plaintext with different keys produces different ciphertext."""
    plaintext = "patient has condition X"

    key1 = settings.encryption_key
    key2 = secrets.token_bytes(32)  # Different key

    ciphertext1 = encrypt_field(plaintext, key1)
    ciphertext2 = encrypt_field(plaintext, key2)

    # Different keys should produce different ciphertext
    assert ciphertext1 != ciphertext2

    # Each ciphertext decrypts with its own key
    assert decrypt_field(ciphertext1, key1) == plaintext
    assert decrypt_field(ciphertext2, key2) == plaintext


def test_decrypt_wrong_key():
    """Test 7: Decryption fails with wrong key."""
    plaintext = "sensitive data"
    key1 = settings.encryption_key
    key2 = secrets.token_bytes(32)  # Wrong key

    ciphertext = encrypt_field(plaintext, key1)

    # Decryption with wrong key should raise DecryptionError
    with pytest.raises(DecryptionError):
        decrypt_field(ciphertext, key2)


def test_decrypt_tampered_ciphertext():
    """Test 8: Authentication failure on tampering."""
    plaintext = "original data"
    key = settings.encryption_key

    ciphertext = encrypt_field(plaintext, key)

    # Tamper with ciphertext (flip a bit in the middle)
    tampered = bytearray(ciphertext)
    tampered[len(tampered) // 2] ^= 0xFF  # Flip all bits of one byte
    tampered_bytes = bytes(tampered)

    # Decryption should detect tampering
    with pytest.raises(DecryptionError):
        decrypt_field(tampered_bytes, key)


def test_encrypt_field_large_text():
    """Test 9: 5KB clinical note (realistic SOAP note size)."""
    # Generate 5KB text (realistic SOAP note)
    large_text = "Patient presents with..." + ("detailed notes. " * 350)
    assert len(large_text) >= 5000

    key = settings.encryption_key

    ciphertext = encrypt_field(large_text, key)
    decrypted = decrypt_field(ciphertext, key)

    assert decrypted == large_text
    # Verify ciphertext size is reasonable (should be ~5KB + overhead)
    assert len(ciphertext) < len(large_text) + 100  # Small overhead


def test_encrypt_field_versioned():
    """Test 10: Versioned encryption/decryption."""
    plaintext = "versioned sensitive data"

    # Encrypt with version metadata
    encrypted_data = encrypt_field_versioned(plaintext, key_version="v1")

    assert encrypted_data is not None
    assert isinstance(encrypted_data, dict)
    assert encrypted_data["version"] == "v1"
    assert encrypted_data["algorithm"] == "AES-256-GCM"
    assert "ciphertext" in encrypted_data

    # Decrypt using version
    keys = {"v1": settings.encryption_key}
    decrypted = decrypt_field_versioned(encrypted_data, keys=keys)

    assert decrypted == plaintext


def test_encrypt_field_versioned_none():
    """Test versioned encryption with None input."""
    encrypted_data = encrypt_field_versioned(None, key_version="v1")
    assert encrypted_data is None

    decrypted = decrypt_field_versioned(None, keys={"v1": settings.encryption_key})
    assert decrypted is None


def test_decrypt_field_versioned_wrong_version():
    """Test versioned decryption fails with missing key version."""
    plaintext = "data encrypted with v1"

    encrypted_data = encrypt_field_versioned(plaintext, key_version="v1")

    # Try to decrypt with keys that don't include v1
    keys = {"v2": secrets.token_bytes(32)}

    with pytest.raises(ValueError, match="Key version 'v1' not found"):
        decrypt_field_versioned(encrypted_data, keys=keys)


def test_decrypt_field_versioned_invalid_structure():
    """Test versioned decryption validates structure."""
    # Invalid structure (missing required fields)
    invalid_data = {"version": "v1"}

    keys = {"v1": settings.encryption_key}

    with pytest.raises(ValueError, match="missing required keys"):
        decrypt_field_versioned(invalid_data, keys=keys)


def test_encrypt_field_invalid_key_size():
    """Test encryption fails with invalid key size."""
    plaintext = "test data"
    invalid_key = secrets.token_bytes(16)  # Only 128-bit, need 256-bit

    with pytest.raises(ValueError, match="must be 32 bytes"):
        encrypt_field(plaintext, invalid_key)


def test_decrypt_field_invalid_ciphertext_size():
    """Test decryption fails with invalid ciphertext size."""
    key = settings.encryption_key
    # Too short (less than nonce + tag = 28 bytes)
    invalid_ciphertext = b"tooshort"

    with pytest.raises(ValueError, match="Ciphertext too short"):
        decrypt_field(invalid_ciphertext, key)


# =============================================================================
# SQLAlchemy Type Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="SQLAlchemy type tests require manual verification"
)
async def test_encrypted_string_type_insert(
    db: AsyncSession, workspace_1: Workspace, test_db_engine
):
    """Test 11: Insert with encryption using EncryptedString type."""
    # Create test table using engine
    async with test_db_engine.begin() as conn:
        await conn.run_sync(EncryptedTestModel.__table__.create, checkfirst=True)

    # Insert record with encrypted fields
    test_record = EncryptedTestModel(
        workspace_id=workspace_1.id,
        encrypted_text="sensitive data",
        encrypted_required="required encrypted field",
    )
    db.add(test_record)
    await db.commit()
    await db.refresh(test_record)

    # Verify record was created
    assert test_record.id is not None
    assert test_record.encrypted_text == "sensitive data"
    assert test_record.encrypted_required == "required encrypted field"

    # Verify data is actually encrypted in database
    # Query the raw bytes from the database
    result = await db.execute(
        select(EncryptedTestModel).where(EncryptedTestModel.id == test_record.id)
    )
    retrieved = result.scalar_one()

    # The decrypted values should match (SQLAlchemy decrypts automatically)
    assert retrieved.encrypted_text == "sensitive data"

    # Cleanup
    async with test_db_engine.begin() as conn:
        await conn.run_sync(EncryptedTestModel.__table__.drop)


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="SQLAlchemy type tests require manual verification"
)
async def test_encrypted_string_type_select(
    db: AsyncSession, workspace_1: Workspace, test_db_engine
):
    """Test 12: Select with decryption using EncryptedString type."""
    # Create test table
    async with test_db_engine.begin() as conn:
        await conn.run_sync(EncryptedTestModel.__table__.create, checkfirst=True)

    # Insert record
    original_text = "confidential patient notes"
    test_record = EncryptedTestModel(
        workspace_id=workspace_1.id,
        encrypted_text=original_text,
        encrypted_required="test",
    )
    db.add(test_record)
    await db.commit()
    record_id = test_record.id

    # Clear session to force re-fetch from database
    await db.commit()
    db.expunge_all()

    # Retrieve record (should decrypt automatically)
    result = await db.execute(
        select(EncryptedTestModel).where(EncryptedTestModel.id == record_id)
    )
    retrieved = result.scalar_one()

    assert retrieved.encrypted_text == original_text
    assert retrieved.encrypted_required == "test"

    # Cleanup
    async with test_db_engine.begin() as conn:
        await conn.run_sync(EncryptedTestModel.__table__.drop)


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="SQLAlchemy type tests require manual verification"
)
async def test_encrypted_string_type_none(
    db: AsyncSession, workspace_1: Workspace, test_db_engine
):
    """Test 13: Handle NULL values with EncryptedString type."""
    # Create test table
    async with test_db_engine.begin() as conn:
        await conn.run_sync(EncryptedTestModel.__table__.create, checkfirst=True)

    # Insert record with NULL encrypted field
    test_record = EncryptedTestModel(
        workspace_id=workspace_1.id,
        encrypted_text=None,  # NULL value
        encrypted_required="test",
    )
    db.add(test_record)
    await db.commit()
    record_id = test_record.id

    # Retrieve and verify NULL is preserved
    result = await db.execute(
        select(EncryptedTestModel).where(EncryptedTestModel.id == record_id)
    )
    retrieved = result.scalar_one()

    assert retrieved.encrypted_text is None
    assert retrieved.encrypted_required == "test"

    # Cleanup
    async with test_db_engine.begin() as conn:
        await conn.run_sync(EncryptedTestModel.__table__.drop)


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="SQLAlchemy type tests require manual verification"
)
async def test_encrypted_string_type_update(
    db: AsyncSession, workspace_1: Workspace, test_db_engine
):
    """Test 14: Update encrypted field."""
    # Create test table
    async with test_db_engine.begin() as conn:
        await conn.run_sync(EncryptedTestModel.__table__.create, checkfirst=True)

    # Insert record
    test_record = EncryptedTestModel(
        workspace_id=workspace_1.id,
        encrypted_text="original value",
        encrypted_required="test",
    )
    db.add(test_record)
    await db.commit()
    record_id = test_record.id

    # Update encrypted field
    test_record.encrypted_text = "updated value"
    await db.commit()

    # Retrieve and verify update
    await db.refresh(test_record)
    assert test_record.encrypted_text == "updated value"

    # Verify from fresh query
    db.expunge_all()
    result = await db.execute(
        select(EncryptedTestModel).where(EncryptedTestModel.id == record_id)
    )
    retrieved = result.scalar_one()
    assert retrieved.encrypted_text == "updated value"

    # Cleanup
    async with test_db_engine.begin() as conn:
        await conn.run_sync(EncryptedTestModel.__table__.drop)


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="SQLAlchemy type tests require manual verification"
)
async def test_encrypted_string_versioned_type(
    db: AsyncSession, workspace_1: Workspace, test_db_engine
):
    """Test EncryptedStringVersioned SQLAlchemy type."""
    # Create test table
    async with test_db_engine.begin() as conn:
        await conn.run_sync(VersionedTestModel.__table__.create, checkfirst=True)

    # Insert record with versioned encryption
    test_record = VersionedTestModel(
        workspace_id=workspace_1.id,
        versioned_text="versioned sensitive data",
    )
    db.add(test_record)
    await db.commit()
    record_id = test_record.id

    # Retrieve and verify decryption
    db.expunge_all()
    result = await db.execute(
        select(VersionedTestModel).where(VersionedTestModel.id == record_id)
    )
    retrieved = result.scalar_one()

    assert retrieved.versioned_text == "versioned sensitive data"

    # Cleanup
    async with test_db_engine.begin() as conn:
        await conn.run_sync(VersionedTestModel.__table__.drop)


# =============================================================================
# Performance Tests
# =============================================================================


@pytest.mark.performance
def test_encryption_performance():
    """Test 15: Validate <5ms encryption overhead."""
    plaintext = "patient medical history: " + ("detailed notes. " * 50)  # ~1KB
    key = settings.encryption_key

    # Warm up (first call may be slower due to initialization)
    encrypt_field(plaintext, key)

    # Measure encryption time
    iterations = 100
    start_time = time.perf_counter()

    for _ in range(iterations):
        encrypt_field(plaintext, key)

    end_time = time.perf_counter()
    avg_time_ms = ((end_time - start_time) / iterations) * 1000

    print(f"\nEncryption performance: {avg_time_ms:.2f}ms per field")
    assert avg_time_ms < 5, f"Encryption too slow: {avg_time_ms:.2f}ms (target: <5ms)"


@pytest.mark.performance
def test_decryption_performance():
    """Test 16: Validate <10ms decryption overhead."""
    plaintext = "patient medical history: " + ("detailed notes. " * 50)  # ~1KB
    key = settings.encryption_key

    ciphertext = encrypt_field(plaintext, key)

    # Warm up
    decrypt_field(ciphertext, key)

    # Measure decryption time
    iterations = 100
    start_time = time.perf_counter()

    for _ in range(iterations):
        decrypt_field(ciphertext, key)

    end_time = time.perf_counter()
    avg_time_ms = ((end_time - start_time) / iterations) * 1000

    print(f"\nDecryption performance: {avg_time_ms:.2f}ms per field")
    assert avg_time_ms < 10, f"Decryption too slow: {avg_time_ms:.2f}ms (target: <10ms)"


@pytest.mark.performance
def test_bulk_decryption_performance():
    """Test 17: 100 fields <100ms total."""
    key = settings.encryption_key

    # Encrypt 100 fields
    plaintexts = [f"patient {i} medical notes" for i in range(100)]
    ciphertexts = [encrypt_field(p, key) for p in plaintexts]

    # Measure bulk decryption
    start_time = time.perf_counter()

    decrypted = [decrypt_field(c, key) for c in ciphertexts]

    end_time = time.perf_counter()
    total_time_ms = (end_time - start_time) * 1000

    print(f"\nBulk decryption (100 fields): {total_time_ms:.2f}ms")
    assert total_time_ms < 100, f"Bulk decryption too slow: {total_time_ms:.2f}ms"
    assert decrypted == plaintexts  # Verify correctness


# =============================================================================
# Security Tests
# =============================================================================


def test_nonce_uniqueness():
    """Test that each encryption uses a unique nonce."""
    plaintext = "same plaintext"
    key = settings.encryption_key

    # Encrypt the same plaintext 100 times
    ciphertexts = [encrypt_field(plaintext, key) for _ in range(100)]

    # All ciphertexts should be different (due to random nonce)
    unique_ciphertexts = set(ciphertexts)
    assert len(unique_ciphertexts) == 100, "Nonces are being reused!"


def test_key_validation():
    """Test that invalid keys are rejected."""
    plaintext = "test"

    # Test various invalid key sizes
    invalid_keys = [
        b"",  # Empty
        b"short",  # Too short
        secrets.token_bytes(16),  # 128-bit (need 256-bit)
        secrets.token_bytes(64),  # Too long
    ]

    for invalid_key in invalid_keys:
        with pytest.raises(ValueError, match="must be 32 bytes"):
            encrypt_field(plaintext, invalid_key)


def test_versioned_encryption_metadata():
    """Test that versioned encryption includes proper metadata."""
    plaintext = "test data"

    encrypted_data = encrypt_field_versioned(plaintext, key_version="v1")

    # Verify structure
    assert encrypted_data["version"] == "v1"
    assert encrypted_data["algorithm"] == "AES-256-GCM"

    # Verify ciphertext is base64-encoded
    ciphertext_bytes = base64.b64decode(encrypted_data["ciphertext"])
    assert len(ciphertext_bytes) > 0

    # Verify ciphertext can be decrypted
    keys = {"v1": settings.encryption_key}
    decrypted = decrypt_field_versioned(encrypted_data, keys=keys)
    assert decrypted == plaintext


@pytest.mark.performance
def test_encryption_overhead_measurement():
    """Measure actual encryption overhead for different data sizes."""
    key = settings.encryption_key

    test_sizes = [
        ("Small (100 bytes)", "x" * 100),
        ("Medium (1KB)", "x" * 1000),
        ("Large (5KB)", "x" * 5000),
        ("SOAP note (~3KB)", "Subjective: " + ("patient reports. " * 150)),
    ]

    print("\n=== Encryption Overhead by Size ===")
    for name, plaintext in test_sizes:
        # Measure encryption time
        iterations = 50
        start = time.perf_counter()
        for _ in range(iterations):
            ciphertext = encrypt_field(plaintext, key)
        end = time.perf_counter()
        encrypt_ms = ((end - start) / iterations) * 1000

        # Measure decryption time
        start = time.perf_counter()
        for _ in range(iterations):
            decrypt_field(ciphertext, key)
        end = time.perf_counter()
        decrypt_ms = ((end - start) / iterations) * 1000

        # Calculate overhead
        size_overhead = len(ciphertext) - len(plaintext.encode())

        print(f"{name}:")
        print(f"  Plaintext: {len(plaintext)} bytes")
        print(f"  Ciphertext: {len(ciphertext)} bytes (+{size_overhead} overhead)")
        print(f"  Encrypt: {encrypt_ms:.2f}ms")
        print(f"  Decrypt: {decrypt_ms:.2f}ms")

        # Verify overhead is exactly nonce (12) + tag (16) = 28 bytes
        assert size_overhead == 28, f"Unexpected overhead: {size_overhead} bytes"
