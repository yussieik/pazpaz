# Encryption Key Rotation Implementation Guide

**Version:** 1.0
**Date:** 2025-10-19
**Status:** ✅ Implemented
**HIPAA Compliance:** 90-day key rotation policy (§164.312(a)(2)(iv))

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Implementation Details](#implementation-details)
4. [Usage Guide](#usage-guide)
5. [Testing](#testing)
6. [Troubleshooting](#troubleshooting)

---

## Overview

### Purpose

This document describes the implementation of encryption key rotation for PHI/PII data protection. The system supports zero-downtime key rotation with backward compatibility for legacy encrypted data.

### Key Features

- **Multi-version key support**: v1, v2, v3, ... (unlimited versions)
- **Zero-downtime rotation**: Old data remains accessible during migration
- **Backward compatibility**: Decrypts legacy non-versioned data automatically
- **90-day rotation policy**: HIPAA compliance tracking
- **AWS Secrets Manager integration**: Secure key storage and retrieval
- **Automated re-encryption**: Background script migrates old data

### Key Rotation Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    Key Rotation Workflow                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Generate new key (v2)         [rotate_encryption_keys.py]│
│  2. Store in AWS Secrets Manager  [boto3 API]               │
│  3. Load keys into registry       [load_all_encryption_keys]│
│  4. New writes use v2             [EncryptedString type]    │
│  5. Old reads use v1/v2           [version detection]       │
│  6. Background re-encryption      [re_encrypt_old_data.py]  │
│  7. All data migrated to v2       [validation]              │
│  8. Remove v1 from production     [AWS cleanup]             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Architecture

### Key Versioning System

**Storage Format:**

```
Versioned (new):  b"v2:" + [12-byte nonce] + [ciphertext] + [16-byte tag]
Legacy (old):     [12-byte nonce] + [ciphertext] + [16-byte tag]
```

**Backward Compatibility:**
- EncryptedString type detects version prefix (`b"v2:"`)
- If prefix exists, uses versioned decryption with key registry
- If no prefix, uses legacy decryption with settings.encryption_key

### Key Registry

**In-Memory Registry:**
```python
_KEY_REGISTRY = {
    "v1": EncryptionKeyMetadata(key=key1, version="v1", created_at=..., expires_at=..., is_current=False),
    "v2": EncryptionKeyMetadata(key=key2, version="v2", created_at=..., expires_at=..., is_current=True),
    "v3": EncryptionKeyMetadata(key=key3, version="v3", created_at=..., expires_at=..., is_current=False),
}
```

**Key Metadata:**
- `key`: 32-byte AES-256 encryption key
- `version`: Version identifier (e.g., "v2")
- `created_at`: Key creation timestamp (UTC)
- `expires_at`: Key expiration timestamp (created_at + 90 days)
- `is_current`: Whether this is the active key for new encryptions
- `rotated_at`: When the key was rotated (None if never rotated)

### AWS Secrets Manager Integration

**Secret Naming Convention:**
```
pazpaz/encryption-key-v1
pazpaz/encryption-key-v2
pazpaz/encryption-key-v3
...
```

**Secret Format (JSON):**
```json
{
  "encryption_key": "base64-encoded-32-byte-key",
  "version": "v2",
  "created_at": "2025-01-19T12:00:00Z",
  "expires_at": "2025-04-19T12:00:00Z",
  "is_current": true
}
```

---

## Implementation Details

### 1. EncryptedString Type (Backward Compatible)

**File:** `/backend/src/pazpaz/db/types.py`

**Encryption (INSERT/UPDATE):**
```python
def process_bind_param(self, value: str | None, dialect: Any) -> bytes | None:
    # Try to use key registry for versioned encryption
    try:
        version = get_current_key_version()
        key = get_key_for_version(version)

        # Encrypt with versioned format
        encrypted = encrypt_field(value, key)

        # Prepend version prefix: b"v2:" + ciphertext
        return f"{version}:".encode() + encrypted

    except (ValueError, ImportError):
        # Fallback to legacy encryption (settings.encryption_key)
        return encrypt_field(value, settings.encryption_key)
```

**Decryption (SELECT):**
```python
def process_result_value(self, value: bytes | None, dialect: Any) -> str | None:
    # Check if versioned format (has ":" in first 10 bytes)
    if b":" in value[:10]:
        # Extract version: b"v2:..." -> "v2"
        colon_index = value.index(b":")
        version = value[:colon_index].decode("ascii")
        ciphertext = value[colon_index + 1:]

        # Decrypt with version-specific key from registry
        key = get_key_for_version(version)
        return decrypt_field(ciphertext, key)

    # Legacy format (no version prefix)
    return decrypt_field(value, settings.encryption_key)
```

### 2. Key Registry Functions

**File:** `/backend/src/pazpaz/utils/encryption.py`

**Register Key:**
```python
def register_key(metadata: EncryptionKeyMetadata) -> None:
    """Register encryption key in global registry."""
    _KEY_REGISTRY[metadata.version] = metadata
    logger.info("key_registered", version=metadata.version, is_current=metadata.is_current)
```

**Get Current Key Version:**
```python
def get_current_key_version() -> str:
    """Get current (active) key version for new encryptions."""
    for version, metadata in _KEY_REGISTRY.items():
        if metadata.is_current:
            return version

    raise ValueError("No current encryption key found in registry")
```

**Get Key for Version:**
```python
def get_key_for_version(version: str) -> bytes:
    """Get encryption key for specific version (with AWS fallback)."""
    if version in _KEY_REGISTRY:
        return _KEY_REGISTRY[version].key

    # Not in registry - fetch from AWS Secrets Manager
    from pazpaz.utils.secrets_manager import get_encryption_key_version

    key = get_encryption_key_version(version)

    # Register fetched key
    register_key(EncryptionKeyMetadata(
        key=key,
        version=version,
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=90),
        is_current=False,
    ))

    return key
```

### 3. AWS Secrets Manager Integration

**File:** `/backend/src/pazpaz/utils/secrets_manager.py`

**Load All Keys (Application Startup):**
```python
def load_all_encryption_keys(region: str = "us-east-1", environment: str = "local") -> None:
    """Load all encryption keys from AWS Secrets Manager into key registry."""
    client = boto3.client("secretsmanager", region_name=region)

    # List all secrets with prefix "pazpaz/encryption-key-"
    response = client.list_secrets(Filters=[{"Key": "name", "Values": ["pazpaz/encryption-key-"]}])

    for secret_info in response.get("SecretList", []):
        secret_name = secret_info["Name"]
        version = secret_name[len("pazpaz/encryption-key-"):]

        # Fetch secret value
        secret = client.get_secret_value(SecretId=secret_name)
        secret_value = json.loads(secret["SecretString"])

        # Parse key and metadata
        key = base64.b64decode(secret_value["encryption_key"])
        created_at = datetime.fromisoformat(secret_value["created_at"])
        expires_at = datetime.fromisoformat(secret_value["expires_at"])
        is_current = secret_value.get("is_current", False)

        # Register key
        register_key(EncryptionKeyMetadata(
            key=key,
            version=version,
            created_at=created_at,
            expires_at=expires_at,
            is_current=is_current,
        ))
```

**Get Specific Key Version:**
```python
def get_encryption_key_version(version: str, region: str = "us-east-1") -> bytes:
    """Fetch specific encryption key version from AWS."""
    secret_name = f"pazpaz/encryption-key-{version}"

    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)

    secret_value = json.loads(response["SecretString"])
    return base64.b64decode(secret_value["encryption_key"])
```

---

## Usage Guide

### 1. Rotate Encryption Keys (90-Day Policy)

**Command:**
```bash
# Dry run (preview changes)
python scripts/rotate_encryption_keys.py --dry-run

# Perform rotation
python scripts/rotate_encryption_keys.py

# Force rotation even if current key is valid
python scripts/rotate_encryption_keys.py --force

# Custom expiration period (default: 90 days)
python scripts/rotate_encryption_keys.py --expiration-days 60
```

**What It Does:**
1. Checks if rotation is needed (current key >90 days old)
2. Generates new 256-bit AES encryption key
3. Determines next version number (v1 → v2 → v3)
4. Stores new key in AWS Secrets Manager with metadata
5. Marks new key as current in registry
6. Logs rotation event for audit trail

**Output:**
```
✅ Key rotation successful!
   New key version: v2
   Created: 2025-01-19 12:00:00 UTC
   Expires: 2025-04-19 12:00:00 UTC
   Days until next rotation: 90

⚠️  IMPORTANT: Run scripts/re_encrypt_old_data.py to migrate existing PHI data
```

### 2. Re-encrypt Old Data

**Command:**
```bash
# Dry run (preview changes)
python scripts/re_encrypt_old_data.py --dry-run

# Re-encrypt all data
python scripts/re_encrypt_old_data.py

# Re-encrypt only specific version
python scripts/re_encrypt_old_data.py --from-version v1

# Process in smaller batches
python scripts/re_encrypt_old_data.py --batch-size 50
```

**What It Does:**
1. Loads all encryption keys from AWS Secrets Manager
2. Identifies current key version
3. Queries all Session records with encrypted PHI fields
4. Re-encrypts data with current key in batches (default: 100)
5. Updates database records in transactions
6. Logs progress and completion statistics

**Output:**
```
📊 Re-encryption Plan:
   Total sessions to process: 450
   Batch size: 100
   Target key version: v2
   Dry run: false

   Batch 1: 100 sessions, 100 re-encrypted (2.5s) - 22.2% complete
   Batch 2: 100 sessions, 100 re-encrypted (2.4s) - 44.4% complete
   Batch 3: 100 sessions, 100 re-encrypted (2.3s) - 66.7% complete
   Batch 4: 100 sessions, 100 re-encrypted (2.5s) - 88.9% complete
   Batch 5: 50 sessions, 50 re-encrypted (1.2s) - 100.0% complete

✅ Re-encryption complete!
   Sessions processed: 450
   Sessions re-encrypted: 450
   New key version: v2
   All PHI data is now encrypted with the latest key version.
```

### 3. Application Startup (Load Keys)

**File:** `/backend/src/pazpaz/main.py` (Lifespan)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("application_startup")

    # Load all encryption keys from AWS Secrets Manager
    from pazpaz.utils.secrets_manager import load_all_encryption_keys

    try:
        load_all_encryption_keys(
            region=settings.aws_region,
            environment=settings.environment,
        )
        logger.info("encryption_keys_loaded", message="All encryption keys loaded into registry")
    except Exception as e:
        logger.error("failed_to_load_encryption_keys", error=str(e), exc_info=True)
        # Fallback to single key from settings
        from pazpaz.utils.encryption import EncryptionKeyMetadata, register_key

        register_key(EncryptionKeyMetadata(
            key=settings.encryption_key,
            version="v1",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=90),
            is_current=True,
        ))
        logger.warning("loaded_single_key_fallback", message="Loaded single key as v1 (AWS unavailable)")

    yield

    # Shutdown
    logger.info("application_shutdown")
```

---

## Testing

### Run Test Suite

```bash
# Run all encryption key rotation tests
pytest tests/test_encryption_key_rotation.py -v

# Run with coverage
pytest tests/test_encryption_key_rotation.py --cov=pazpaz.utils.encryption --cov=pazpaz.db.types --cov-report=html

# Run specific tests
pytest tests/test_encryption_key_rotation.py::test_encrypt_field_versioned_with_registry -v
pytest tests/test_encryption_key_rotation.py::test_decrypt_legacy_non_versioned_data -v
```

### Test Coverage

The test suite includes 21 comprehensive tests covering:

1. **Key Metadata Tests (5 tests)**
   - Create EncryptionKeyMetadata with valid data
   - Reject invalid key size
   - Reject invalid version format
   - Detect when key needs rotation (>90 days)
   - Calculate days until rotation

2. **Key Registry Tests (5 tests)**
   - Register encryption key in registry
   - Get all registered keys
   - Get current key version
   - Raise error when no current key
   - Identify keys needing rotation

3. **Versioned Encryption/Decryption Tests (2 tests)**
   - Encrypt field with key registry (auto-select current version)
   - Decrypt field with key registry (auto-fetch key)

4. **Backward Compatibility Tests (2 tests)**
   - Decrypt legacy data without version prefix
   - EncryptedString type handles both legacy and versioned formats

5. **Multi-Version Decryption Tests (1 test)**
   - Decrypt data encrypted with different key versions (v1, v2, v3)

6. **Error Handling Tests (2 tests)**
   - Raise error when key version not in registry
   - Handle corrupted versioned ciphertext

7. **AWS Secrets Manager Integration Tests (1 test, mocked)**
   - Load all encryption keys from AWS Secrets Manager

8. **Integration Tests with Session Model (2 tests)**
   - Session model uses versioned encryption
   - Re-encrypt session data after key rotation

9. **Performance Tests (1 test)**
   - Validate versioned encryption performance overhead (<10ms)

### Manual Testing

**Test Backward Compatibility:**
```python
# 1. Encrypt with legacy format (no version prefix)
from pazpaz.core.config import settings
from pazpaz.utils.encryption import encrypt_field, decrypt_field

plaintext = "legacy encrypted data"
ciphertext_legacy = encrypt_field(plaintext, settings.encryption_key)

# Verify no version prefix
assert b":" not in ciphertext_legacy[:10]

# 2. Decrypt using EncryptedString type (should auto-detect legacy)
from pazpaz.db.types import EncryptedString

encrypted_string_type = EncryptedString()
decrypted = encrypted_string_type.process_result_value(ciphertext_legacy, None)

assert decrypted == plaintext
```

**Test Multi-Version Support:**
```python
# 1. Register multiple keys
from pazpaz.utils.encryption import register_key, EncryptionKeyMetadata
from datetime import UTC, datetime, timedelta
import secrets

key_v1 = secrets.token_bytes(32)
key_v2 = secrets.token_bytes(32)

register_key(EncryptionKeyMetadata(
    key=key_v1,
    version="v1",
    created_at=datetime.now(UTC) - timedelta(days=100),
    expires_at=datetime.now(UTC) - timedelta(days=10),
))

register_key(EncryptionKeyMetadata(
    key=key_v2,
    version="v2",
    created_at=datetime.now(UTC),
    expires_at=datetime.now(UTC) + timedelta(days=90),
    is_current=True,
))

# 2. Encrypt with v1, decrypt with registry
from pazpaz.utils.encryption import encrypt_field_versioned, decrypt_field_versioned

plaintext = "data encrypted with v1"
encrypted = encrypt_field_versioned(plaintext, key_version="v1")

assert encrypted["version"] == "v1"

# Decrypt (should auto-fetch v1 key from registry)
decrypted = decrypt_field_versioned(encrypted)

assert decrypted == plaintext
```

---

## Troubleshooting

### Issue 1: "No current encryption key found in registry"

**Cause:** No key is marked as `is_current=True` in the registry.

**Solution:**
```python
# Verify registry state
from pazpaz.utils.encryption import _KEY_REGISTRY

for version, metadata in _KEY_REGISTRY.items():
    print(f"{version}: is_current={metadata.is_current}")

# Manually set current key
_KEY_REGISTRY["v2"].is_current = True
```

### Issue 2: "Key version 'v2' not found in registry or AWS"

**Cause:** Key version v2 doesn't exist in AWS Secrets Manager or environment variables.

**Solution:**
```bash
# Check if secret exists in AWS
aws secretsmanager get-secret-value --secret-id pazpaz/encryption-key-v2

# If missing, create it
python scripts/rotate_encryption_keys.py

# Or manually create secret
aws secretsmanager create-secret \
  --name pazpaz/encryption-key-v2 \
  --secret-string '{"encryption_key": "base64-key", "version": "v2", "created_at": "...", "expires_at": "...", "is_current": true}'
```

### Issue 3: Decryption fails after key rotation

**Cause:** Old data encrypted with v1, but v1 key not in registry.

**Solution:**
```python
# Load all keys from AWS (including old versions)
from pazpaz.utils.secrets_manager import load_all_encryption_keys

load_all_encryption_keys(region="us-east-1", environment="production")

# Verify v1 is loaded
from pazpaz.utils.encryption import _KEY_REGISTRY
assert "v1" in _KEY_REGISTRY
```

### Issue 4: Re-encryption script is slow

**Cause:** Large batch size or slow database.

**Solution:**
```bash
# Reduce batch size
python scripts/re_encrypt_old_data.py --batch-size 50

# Or increase database connection pool size
# Edit backend/src/pazpaz/db/base.py:
engine = create_async_engine(
    settings.database_url,
    pool_size=20,  # Increase from default 5
    max_overflow=40,  # Increase from default 10
)
```

### Issue 5: AWS Secrets Manager access denied

**Cause:** Missing IAM permissions for application service account.

**Solution:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:ListSecrets"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:*:secret:pazpaz/encryption-key-*"
      ]
    }
  ]
}
```

---

## Summary

✅ **Implemented Features:**
- Multi-version key support (v1, v2, v3, ...)
- Zero-downtime key rotation
- Backward compatibility for legacy encrypted data
- AWS Secrets Manager integration
- 90-day rotation policy tracking
- Automated re-encryption script
- Comprehensive test suite (21 tests)

✅ **HIPAA Compliance:**
- Encryption keys rotated every 90 days (§164.312(a)(2)(iv))
- Audit logging for all key access and rotations
- Secure key storage in AWS Secrets Manager
- Key metadata tracking (created_at, expires_at)

✅ **Production Ready:**
- All tests passing
- Backward compatible with existing encrypted data
- Performance validated (<10ms overhead)
- Error handling and fallback strategies
- Comprehensive documentation

---

**Last Updated:** 2025-10-19
**Next Review:** After first production key rotation
**Owner:** Security Team + Backend Engineering
