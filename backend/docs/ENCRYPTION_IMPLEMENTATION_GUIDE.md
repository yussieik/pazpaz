# PHI Encryption Implementation Guide
**Version:** 1.0
**Date:** 2025-10-03
**For:** Backend Developers (Day 4 Implementation)
**Prerequisites:** Read [ENCRYPTION_ARCHITECTURE.md](ENCRYPTION_ARCHITECTURE.md) first

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Setting Up Encryption](#2-setting-up-encryption)
3. [Adding Encrypted Fields to Models](#3-adding-encrypted-fields-to-models)
4. [Writing Migrations](#4-writing-migrations)
5. [Testing Encrypted Fields](#5-testing-encrypted-fields)
6. [Common Patterns](#6-common-patterns)
7. [Troubleshooting](#7-troubleshooting)
8. [Code Examples](#8-code-examples)

---

## 1. Quick Start

### 1.1 TL;DR - 5 Minute Setup

**Step 1:** Generate encryption key
```bash
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
# Output: Ky8vL2JhY2t1cC9lbmNyeXB0aW9uLWtleQ==
```

**Step 2:** Add to environment
```bash
# .env
ENCRYPTION_MASTER_KEY=Ky8vL2JhY2t1cC9lbmNyeXB0aW9uLWtleQ==
```

**Step 3:** Update model
```python
from pazpaz.db.encrypted_types import EncryptedString
from pazpaz.core.config import settings

class Client(Base):
    medical_history: Mapped[str | None] = mapped_column(
        EncryptedString(2000, key=settings.encryption_key),
        nullable=True,
    )
```

**Step 4:** Run migration
```bash
uv run alembic revision --autogenerate -m "add_encrypted_medical_history"
uv run alembic upgrade head
```

Done! Your field is now encrypted at rest.

---

## 2. Setting Up Encryption

### 2.1 Install Dependencies

**Already included in pyproject.toml:**
```toml
[project]
dependencies = [
    "cryptography>=42.0.0",  # For AES-256-GCM
    "sqlalchemy[asyncio]>=2.0.0",
]
```

**Verify installation:**
```bash
uv run python -c "from cryptography.hazmat.primitives.ciphers.aead import AESGCM; print('OK')"
```

### 2.2 Configure Encryption Key

**Development (.env file):**
```bash
# Generate key
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"

# Add to .env (NOT committed to git)
ENCRYPTION_MASTER_KEY=your-base64-encoded-key-here
```

**Production (Environment Variable):**
```bash
# Docker Compose
environment:
  - ENCRYPTION_MASTER_KEY=${ENCRYPTION_MASTER_KEY}

# Kubernetes Secret
apiVersion: v1
kind: Secret
metadata:
  name: pazpaz-secrets
data:
  ENCRYPTION_MASTER_KEY: <base64-encoded-key>
```

**Production (AWS Secrets Manager - Recommended):**
```python
# src/pazpaz/core/config.py

import boto3
import base64
from functools import lru_cache

class Settings(BaseSettings):
    # ... other settings

    @property
    @lru_cache
    def encryption_key(self) -> bytes:
        """Fetch encryption key from AWS Secrets Manager."""
        if self.environment == "local":
            # Use environment variable for local dev
            return base64.b64decode(self.encryption_master_key)

        # Production: fetch from AWS Secrets Manager
        client = boto3.client('secretsmanager', region_name='us-east-1')
        response = client.get_secret_value(SecretId='pazpaz/encryption-key')
        key_b64 = response['SecretString']
        return base64.b64decode(key_b64)
```

### 2.3 Verify Configuration

```bash
# Test encryption key is loaded
uv run python -c "from pazpaz.core.config import settings; print(f'Key length: {len(settings.encryption_key)} bytes')"
# Expected output: Key length: 32 bytes
```

---

## 3. Adding Encrypted Fields to Models

### 3.1 Import Encrypted Types

```python
from pazpaz.db.encrypted_types import EncryptedString, EncryptedText
from pazpaz.core.config import settings
```

### 3.2 Choose Appropriate Type

**EncryptedString:** For shorter text fields (up to ~10,000 characters plaintext)
- Names, emails, phone numbers, addresses
- Stored as VARCHAR in database

**EncryptedText:** For longer content (up to ~100,000 characters plaintext)
- Medical history, SOAP notes, treatment plans
- Stored as TEXT in database

### 3.3 Update Model Definition

**Example: Client model**

```python
# src/pazpaz/models/client.py

from pazpaz.db.encrypted_types import EncryptedString, EncryptedText
from pazpaz.core.config import settings

class Client(Base):
    __tablename__ = "clients"

    # Encrypted PII fields (short text)
    first_name: Mapped[str] = mapped_column(
        EncryptedString(255, key=settings.encryption_key),
        nullable=False,
        comment="Encrypted PII - first name"
    )

    last_name: Mapped[str] = mapped_column(
        EncryptedString(255, key=settings.encryption_key),
        nullable=False,
        comment="Encrypted PII - last name"
    )

    email: Mapped[str | None] = mapped_column(
        EncryptedString(255, key=settings.encryption_key),
        nullable=True,
        comment="Encrypted PII - email address"
    )

    phone: Mapped[str | None] = mapped_column(
        EncryptedString(50, key=settings.encryption_key),
        nullable=True,
        comment="Encrypted PII - phone number"
    )

    # Encrypted PHI fields (long text)
    medical_history: Mapped[str | None] = mapped_column(
        EncryptedText(key=settings.encryption_key),
        nullable=True,
        comment="Encrypted PHI - medical history and conditions"
    )

    address: Mapped[str | None] = mapped_column(
        EncryptedText(key=settings.encryption_key),
        nullable=True,
        comment="Encrypted PII - physical address"
    )

    # Non-encrypted fields (no PII/PHI)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    consent_status: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
```

### 3.4 Calculate Encrypted Length

**Formula:**
```
encrypted_length = ceil((plaintext_length + 28) * 4/3) + 30
```

**Explanation:**
- `+28`: GCM tag (16 bytes) + nonce (12 bytes)
- `*4/3`: Base64 encoding overhead
- `+30`: Version prefix + separators (`v1:nonce:ciphertext`)

**Examples:**
```python
# first_name (max 255 chars)
plaintext_length = 255
encrypted_length = int((255 + 28) * 4 / 3) + 30  # ~407 chars

# medical_history (max 10,000 chars)
plaintext_length = 10000
encrypted_length = int((10000 + 28) * 4 / 3) + 30  # ~13,367 chars
```

**Helper Function:**
```python
def calculate_encrypted_length(plaintext_max: int) -> int:
    """Calculate required VARCHAR length for encrypted field."""
    return int((plaintext_max + 28) * 4 / 3) + 30
```

### 3.5 Type Annotations

**Always use `Mapped[str]` or `Mapped[str | None]`**

```python
# ✅ CORRECT
medical_history: Mapped[str | None] = mapped_column(EncryptedText(...))

# ❌ WRONG - EncryptedText is not a valid type annotation
medical_history: EncryptedText = mapped_column(EncryptedText(...))
```

---

## 4. Writing Migrations

### 4.1 Create Migration

```bash
# Auto-generate migration from model changes
uv run alembic revision --autogenerate -m "add_encrypted_client_fields"
```

### 4.2 Review Generated Migration

**Generated file:** `alembic/versions/XXXX_add_encrypted_client_fields.py`

```python
"""add_encrypted_client_fields

Revision ID: 1234567890ab
Revises: f6092aa0856d
Create Date: 2025-10-03 14:30:00.000000

Add encrypted fields to clients table for HIPAA compliance.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '1234567890ab'
down_revision = 'f6092aa0856d'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add encrypted columns
    op.add_column('clients', sa.Column(
        'first_name_encrypted',
        sa.String(length=400),  # Encrypted length for 255 char plaintext
        nullable=True,  # Start as nullable for backfill
        comment='Encrypted PII - first name'
    ))

    op.add_column('clients', sa.Column(
        'last_name_encrypted',
        sa.String(length=400),
        nullable=True,
        comment='Encrypted PII - last name'
    ))

    op.add_column('clients', sa.Column(
        'email_encrypted',
        sa.String(length=400),
        nullable=True,
        comment='Encrypted PII - email address'
    ))

    op.add_column('clients', sa.Column(
        'medical_history_encrypted',
        sa.Text(),  # TEXT for long content
        nullable=True,
        comment='Encrypted PHI - medical history'
    ))

def downgrade() -> None:
    # Remove encrypted columns (rollback)
    op.drop_column('clients', 'medical_history_encrypted')
    op.drop_column('clients', 'email_encrypted')
    op.drop_column('clients', 'last_name_encrypted')
    op.drop_column('clients', 'first_name_encrypted')
```

### 4.3 Migration Best Practices

**DO:**
- ✅ Add encrypted columns as nullable initially (allows backfill)
- ✅ Use descriptive migration messages
- ✅ Test migration on staging database first
- ✅ Keep plaintext columns during dual-write phase

**DON'T:**
- ❌ Drop plaintext columns immediately (lose rollback ability)
- ❌ Add NOT NULL constraint before backfilling data
- ❌ Rename columns in same migration as adding them

### 4.4 Dual-Write Migration Pattern

**Phase 1: Add encrypted columns (keep plaintext)**

```python
def upgrade() -> None:
    # Add encrypted columns (nullable)
    op.add_column('clients', sa.Column('first_name_encrypted', sa.String(400), nullable=True))
    # Keep first_name column (plaintext) for now
```

**Phase 2: Backfill encrypted data (background job)**

```python
# Separate script: src/pazpaz/scripts/backfill_encrypted_clients.py

async def backfill_clients():
    """Encrypt existing plaintext client data."""
    batch_size = 100

    while True:
        # Find clients with unencrypted data
        result = await db.execute(
            select(Client)
            .where(Client.first_name_encrypted.is_(None))
            .limit(batch_size)
        )
        clients = result.scalars().all()

        if not clients:
            break  # Done

        # Encrypt fields
        for client in clients:
            # ORM automatically encrypts via EncryptedString
            client.first_name_encrypted = client._first_name_plaintext

        await db.commit()
        print(f"Encrypted {len(clients)} clients")

        await asyncio.sleep(0.1)  # Rate limiting
```

**Phase 3: Switch to encrypted columns**

```python
# Update model to read from encrypted column
class Client(Base):
    first_name: Mapped[str] = mapped_column(
        "first_name_encrypted",  # Column name in DB
        EncryptedString(255),
        nullable=False
    )

    # Keep plaintext for rollback (deprecated)
    _first_name_plaintext: Mapped[str] = mapped_column(
        "first_name",
        String(255),
        nullable=True,
        deprecated=True
    )
```

**Phase 4: Drop plaintext columns (after verification)**

```python
def upgrade() -> None:
    # Verify encrypted columns have data
    # Then drop plaintext
    op.drop_column('clients', 'first_name')

    # Rename encrypted column
    op.alter_column('clients', 'first_name_encrypted', new_column_name='first_name')
```

---

## 5. Testing Encrypted Fields

### 5.1 Unit Tests for Encryption

```python
# tests/test_encryption.py

import pytest
from pazpaz.db.encrypted_types import EncryptedString, EncryptedText
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64
import secrets

@pytest.fixture
def encryption_key() -> bytes:
    """Generate test encryption key."""
    return secrets.token_bytes(32)  # 256 bits

@pytest.fixture
def encrypted_type(encryption_key):
    """Create EncryptedString instance."""
    return EncryptedString(255, key=encryption_key, key_version="v1")

def test_encrypt_decrypt_roundtrip(encrypted_type):
    """Test that encryption and decryption are symmetric."""
    plaintext = "John Doe"

    # Encrypt
    ciphertext = encrypted_type.process_bind_param(plaintext, None)

    # Verify format: v1:nonce:ciphertext
    assert ciphertext.startswith("v1:")
    parts = ciphertext.split(":")
    assert len(parts) == 3

    # Decrypt
    decrypted = encrypted_type.process_result_value(ciphertext, None)

    # Verify
    assert decrypted == plaintext

def test_encrypt_different_nonce_each_time(encrypted_type):
    """Ensure each encryption uses unique nonce (prevent replay attacks)."""
    plaintext = "John Doe"

    ciphertext1 = encrypted_type.process_bind_param(plaintext, None)
    ciphertext2 = encrypted_type.process_bind_param(plaintext, None)

    # Same plaintext, different ciphertext (different nonce)
    assert ciphertext1 != ciphertext2

    # Both decrypt correctly
    assert encrypted_type.process_result_value(ciphertext1, None) == plaintext
    assert encrypted_type.process_result_value(ciphertext2, None) == plaintext

def test_decrypt_with_wrong_key_fails(encryption_key):
    """Decryption with wrong key should fail."""
    plaintext = "John Doe"

    # Encrypt with one key
    enc1 = EncryptedString(255, key=encryption_key, key_version="v1")
    ciphertext = enc1.process_bind_param(plaintext, None)

    # Try to decrypt with different key
    wrong_key = secrets.token_bytes(32)
    enc2 = EncryptedString(255, key=wrong_key, key_version="v1")

    with pytest.raises(ValueError, match="Failed to decrypt field"):
        enc2.process_result_value(ciphertext, None)

def test_null_values_remain_null(encrypted_type):
    """NULL values should not be encrypted."""
    assert encrypted_type.process_bind_param(None, None) is None
    assert encrypted_type.process_result_value(None, None) is None

def test_empty_string_encrypted(encrypted_type):
    """Empty strings should be encrypted (not treated as NULL)."""
    ciphertext = encrypted_type.process_bind_param("", None)
    assert ciphertext is not None
    assert ciphertext.startswith("v1:")

    decrypted = encrypted_type.process_result_value(ciphertext, None)
    assert decrypted == ""

def test_unicode_text_encryption(encrypted_type):
    """Unicode characters should encrypt correctly."""
    plaintext = "José García: 日本語 🎉"

    ciphertext = encrypted_type.process_bind_param(plaintext, None)
    decrypted = encrypted_type.process_result_value(ciphertext, None)

    assert decrypted == plaintext

def test_long_text_encryption():
    """Test encryption of long text (medical history)."""
    key = secrets.token_bytes(32)
    enc = EncryptedText(key=key, key_version="v1")

    plaintext = "A" * 10000  # 10KB medical history

    ciphertext = enc.process_bind_param(plaintext, None)
    decrypted = enc.process_result_value(ciphertext, None)

    assert decrypted == plaintext
    assert len(ciphertext) < len(plaintext) * 1.5  # Verify overhead is reasonable
```

### 5.2 Integration Tests with Database

```python
# tests/test_client_encryption.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from pazpaz.models.client import Client

@pytest.mark.asyncio
async def test_client_encrypted_fields_persist(db: AsyncSession):
    """Test encrypted fields are stored and retrieved correctly."""
    # Create client with encrypted fields
    client = Client(
        workspace_id=workspace_id,
        first_name="John",
        last_name="Doe",
        medical_history="Diabetes Type 2, hypertension"
    )
    db.add(client)
    await db.commit()

    # Clear session (force reload from database)
    await db.refresh(client)

    # Verify decrypted values
    assert client.first_name == "John"
    assert client.last_name == "Doe"
    assert client.medical_history == "Diabetes Type 2, hypertension"

@pytest.mark.asyncio
async def test_encrypted_data_in_database_is_not_plaintext(db: AsyncSession):
    """Verify data in database is actually encrypted."""
    # Create client
    client = Client(
        workspace_id=workspace_id,
        first_name="John",
        medical_history="Secret diagnosis"
    )
    db.add(client)
    await db.commit()

    # Query raw database (bypass ORM)
    result = await db.execute(
        text("SELECT first_name, medical_history FROM clients WHERE id = :id"),
        {"id": client.id}
    )
    row = result.fetchone()

    # Verify encrypted (starts with version prefix)
    assert row[0].startswith("v1:")
    assert row[1].startswith("v1:")

    # Verify NOT plaintext
    assert "John" not in row[0]
    assert "Secret diagnosis" not in row[1]
```

### 5.3 Performance Tests

```python
# tests/test_encryption_performance.py

import pytest
import time
from pazpaz.models.client import Client

@pytest.mark.performance
@pytest.mark.asyncio
async def test_encryption_overhead_single_field(db: AsyncSession):
    """Measure encryption overhead for single field."""
    times = []

    for _ in range(100):
        start = time.perf_counter()

        client = Client(
            workspace_id=workspace_id,
            first_name="John",
            last_name="Doe",
            medical_history="A" * 1000  # 1KB text
        )
        db.add(client)
        await db.commit()

        elapsed = time.perf_counter() - start
        times.append(elapsed)

    p95 = sorted(times)[94]  # 95th percentile
    print(f"Encryption p95: {p95 * 1000:.2f}ms")

    assert p95 < 0.020, f"Encryption too slow: {p95 * 1000:.2f}ms > 20ms"

@pytest.mark.performance
@pytest.mark.asyncio
async def test_decryption_overhead_bulk(db: AsyncSession):
    """Measure decryption overhead for bulk reads."""
    # Create 100 clients
    for i in range(100):
        client = Client(
            workspace_id=workspace_id,
            first_name=f"Client{i}",
            medical_history=f"Medical history {i}"
        )
        db.add(client)
    await db.commit()

    # Measure bulk read
    start = time.perf_counter()
    result = await db.execute(
        select(Client).where(Client.workspace_id == workspace_id)
    )
    clients = result.scalars().all()
    elapsed = time.perf_counter() - start

    print(f"Decryption (100 clients): {elapsed * 1000:.2f}ms")

    assert len(clients) == 100
    assert elapsed < 0.200, f"Decryption too slow: {elapsed * 1000:.2f}ms > 200ms"
```

---

## 6. Common Patterns

### 6.1 Optional Encrypted Fields

```python
# Nullable encrypted field
email: Mapped[str | None] = mapped_column(
    EncryptedString(255, key=settings.encryption_key),
    nullable=True,  # NULL allowed
)

# Usage
client.email = None  # OK
client.email = "john@example.com"  # Encrypted
```

### 6.2 Default Values

```python
# ❌ WRONG - Default values are encrypted ONCE at model definition
notes: Mapped[str] = mapped_column(
    EncryptedString(1000, key=settings.encryption_key),
    default="No notes",  # This gets encrypted once and reused (BAD)
)

# ✅ CORRECT - Use server_default or set in __init__
notes: Mapped[str] = mapped_column(
    EncryptedString(1000, key=settings.encryption_key),
    nullable=True,
)

def __init__(self, **kwargs):
    super().__init__(**kwargs)
    if self.notes is None:
        self.notes = "No notes"  # Encrypted per instance
```

### 6.3 Querying Encrypted Fields

**Cannot use WHERE clauses on encrypted fields:**

```python
# ❌ WRONG - Cannot search encrypted fields
clients = await db.execute(
    select(Client).where(Client.first_name == "John")  # Won't work
)

# ✅ CORRECT - Filter after decryption (in Python)
result = await db.execute(
    select(Client).where(Client.workspace_id == workspace_id)
)
clients = result.scalars().all()
john_clients = [c for c in clients if c.first_name == "John"]
```

**Alternative: Search tokens (unencrypted, for search only)**

```python
class Client(Base):
    first_name: Mapped[str] = mapped_column(EncryptedString(255))

    # Separate unencrypted search field
    first_name_search: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Lowercase searchable name (not encrypted)"
    )

    def __init__(self, first_name: str, **kwargs):
        super().__init__(**kwargs)
        self.first_name = first_name
        self.first_name_search = first_name.lower()  # Searchable token

# Query
clients = await db.execute(
    select(Client)
    .where(Client.workspace_id == workspace_id)
    .where(Client.first_name_search.like("%john%"))
)
```

### 6.4 Bulk Updates

```python
# ❌ WRONG - Bulk updates bypass ORM encryption
await db.execute(
    update(Client)
    .where(Client.workspace_id == workspace_id)
    .values(first_name="John")  # NOT encrypted
)

# ✅ CORRECT - Load instances and update
result = await db.execute(
    select(Client).where(Client.workspace_id == workspace_id)
)
clients = result.scalars().all()

for client in clients:
    client.first_name = "John"  # Encrypted via ORM

await db.commit()
```

---

## 7. Troubleshooting

### 7.1 Common Errors

**Error: "Failed to decrypt field"**

**Cause:** Wrong encryption key, corrupted data, or key version mismatch

**Solution:**
```python
# Check encryption key is loaded
from pazpaz.core.config import settings
print(f"Key length: {len(settings.encryption_key)} bytes")  # Should be 32

# Check encrypted data format
print(client._first_name_encrypted)  # Raw value from DB
# Should be: "v1:nonce_b64:ciphertext_b64"

# Verify key version matches
assert client._first_name_encrypted.startswith("v1:")
```

**Error: "ValueError: Invalid encrypted format"**

**Cause:** Data in database is not in expected format (plaintext or corrupted)

**Solution:**
```python
# Check if field is actually encrypted
result = await db.execute(
    text("SELECT first_name FROM clients WHERE id = :id"),
    {"id": client_id}
)
row = result.fetchone()
print(row[0])  # Should start with "v1:"

# If plaintext, re-encrypt
if not row[0].startswith("v1:"):
    print("Data is not encrypted, run migration")
```

**Error: "Key version mismatch: v2 != v1"**

**Cause:** Data encrypted with newer key version than application supports

**Solution:**
```python
# Support multiple key versions during rotation
class EncryptedType(TypeDecorator):
    def __init__(self, key: bytes, key_v2: bytes | None = None, ...):
        self.key = key
        self.key_v2 = key_v2

    def process_result_value(self, value, dialect):
        parts = value.split(":")
        key_version = parts[0]

        if key_version == "v1":
            cipher = AESGCM(self.key)
        elif key_version == "v2" and self.key_v2:
            cipher = AESGCM(self.key_v2)
        else:
            raise ValueError(f"Unsupported key version: {key_version}")

        # ... decrypt with correct key
```

### 7.2 Performance Issues

**Symptom:** Slow API responses after adding encryption

**Diagnosis:**
```python
import time

# Measure encryption time
start = time.perf_counter()
client = Client(first_name="John", medical_history="A" * 10000)
db.add(client)
await db.commit()
elapsed = time.perf_counter() - start
print(f"Encryption: {elapsed * 1000:.2f}ms")

# Measure decryption time
start = time.perf_counter()
result = await db.execute(select(Client).where(Client.id == client_id))
client = result.scalar_one()
elapsed = time.perf_counter() - start
print(f"Decryption: {elapsed * 1000:.2f}ms")
```

**Solutions:**
- Cache decrypted values in Redis (short TTL)
- Load only necessary fields (deferred loading)
- Optimize number of clients loaded per request

### 7.3 Migration Failures

**Error: "Column already exists"**

**Cause:** Migration already partially applied

**Solution:**
```bash
# Rollback migration
uv run alembic downgrade -1

# Fix migration file
# Re-run upgrade
uv run alembic upgrade head
```

**Error: "NOT NULL constraint violation"**

**Cause:** Adding encrypted column as NOT NULL before backfilling data

**Solution:**
```python
# Phase 1: Add as nullable
op.add_column('clients', sa.Column('first_name_encrypted', sa.String(400), nullable=True))

# Phase 2: Backfill data (separate script)
# ... encrypt existing data

# Phase 3: Add NOT NULL constraint
op.alter_column('clients', 'first_name_encrypted', nullable=False)
```

---

## 8. Code Examples

### 8.1 Complete Client Model with Encryption

```python
# src/pazpaz/models/client.py

from __future__ import annotations

import uuid
from datetime import date, datetime, UTC
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base
from pazpaz.db.encrypted_types import EncryptedString, EncryptedText
from pazpaz.core.config import settings

if TYPE_CHECKING:
    from pazpaz.models.appointment import Appointment
    from pazpaz.models.workspace import Workspace


class Client(Base):
    """Client represents an individual receiving treatment."""

    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Encrypted PII fields
    first_name: Mapped[str] = mapped_column(
        EncryptedString(255, key=settings.encryption_key),
        nullable=False,
        comment="Encrypted PII - first name"
    )

    last_name: Mapped[str] = mapped_column(
        EncryptedString(255, key=settings.encryption_key),
        nullable=False,
        comment="Encrypted PII - last name"
    )

    email: Mapped[str | None] = mapped_column(
        EncryptedString(255, key=settings.encryption_key),
        nullable=True,
        comment="Encrypted PII - email address"
    )

    phone: Mapped[str | None] = mapped_column(
        EncryptedString(50, key=settings.encryption_key),
        nullable=True,
        comment="Encrypted PII - phone number"
    )

    date_of_birth: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="PHI - date of birth (not encrypted in V1)"
    )

    address: Mapped[str | None] = mapped_column(
        EncryptedText(key=settings.encryption_key),
        nullable=True,
        comment="Encrypted PII - physical address"
    )

    # Encrypted PHI fields
    medical_history: Mapped[str | None] = mapped_column(
        EncryptedText(key=settings.encryption_key),
        nullable=True,
        comment="Encrypted PHI - medical history and conditions"
    )

    emergency_contact_name: Mapped[str | None] = mapped_column(
        EncryptedString(255, key=settings.encryption_key),
        nullable=True,
        comment="Encrypted PII - emergency contact name"
    )

    emergency_contact_phone: Mapped[str | None] = mapped_column(
        EncryptedString(50, key=settings.encryption_key),
        nullable=True,
        comment="Encrypted PII - emergency contact phone"
    )

    # Non-encrypted fields
    consent_status: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Client consent to store and process data"
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Active status (soft delete flag)"
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="General notes (may contain PHI, consider encrypting)"
    )

    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)),
        nullable=True,
        comment="Tags for categorization"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        back_populates="clients",
    )

    appointments: Mapped[list[Appointment]] = relationship(
        "Appointment",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        # Workspace scoping (most queries)
        Index(
            "ix_clients_workspace_updated",
            "workspace_id",
            "updated_at",
        ),
        # Active clients (partial index)
        Index(
            "ix_clients_workspace_active",
            "workspace_id",
            "is_active",
            postgresql_where=sa.text("is_active = true"),
        ),
        {"comment": "Clients with encrypted PII/PHI for HIPAA compliance"},
    )

    @property
    def full_name(self) -> str:
        """Return full name (decrypted)."""
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Client(id={self.id}, workspace_id={self.workspace_id})>"
```

### 8.2 Backfill Script for Existing Data

```python
# src/pazpaz/scripts/backfill_encrypted_clients.py

import asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.db.session import async_session
from pazpaz.models.client import Client


async def backfill_encrypted_clients():
    """
    Encrypt existing plaintext client data.

    This script reads from plaintext columns and writes to encrypted columns
    during the dual-write migration phase.
    """
    print("Starting client encryption backfill...")

    batch_size = 100
    total_encrypted = 0

    async with async_session() as db:
        while True:
            # Find clients with unencrypted fields
            result = await db.execute(
                select(Client)
                .where(Client.first_name_encrypted.is_(None))
                .limit(batch_size)
            )
            clients = result.scalars().all()

            if not clients:
                print("All clients encrypted!")
                break

            # Encrypt fields
            for client in clients:
                # Copy plaintext to encrypted columns
                # (ORM automatically encrypts via EncryptedString)
                client.first_name_encrypted = client._first_name_plaintext
                client.last_name_encrypted = client._last_name_plaintext
                client.email_encrypted = client._email_plaintext
                client.phone_encrypted = client._phone_plaintext
                client.address_encrypted = client._address_plaintext
                client.medical_history_encrypted = client._medical_history_plaintext
                client.emergency_contact_name_encrypted = client._emergency_contact_name_plaintext
                client.emergency_contact_phone_encrypted = client._emergency_contact_phone_plaintext

            await db.commit()
            total_encrypted += len(clients)

            print(f"Encrypted {total_encrypted} clients...")

            # Rate limiting (don't overload database)
            await asyncio.sleep(0.1)

    print(f"Backfill complete! Total encrypted: {total_encrypted}")


if __name__ == "__main__":
    asyncio.run(backfill_encrypted_clients())
```

### 8.3 Pydantic Schema (No Changes Needed)

```python
# src/pazpaz/schemas/client.py

from pydantic import BaseModel, EmailStr, Field
from datetime import date, datetime
import uuid

class ClientResponse(BaseModel):
    """Client response schema - sees decrypted data."""

    id: uuid.UUID
    workspace_id: uuid.UUID

    # Encrypted fields (automatically decrypted by ORM)
    first_name: str
    last_name: str
    email: EmailStr | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    address: str | None = None
    medical_history: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    # Non-encrypted fields
    consent_status: bool
    is_active: bool
    notes: str | None = None
    tags: list[str] | None = None

    created_at: datetime
    updated_at: datetime

    # Computed property
    full_name: str

    class Config:
        from_attributes = True


class ClientCreate(BaseModel):
    """Client creation schema."""

    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    date_of_birth: date | None = None
    address: str | None = None
    medical_history: str | None = None
    emergency_contact_name: str | None = Field(None, max_length=255)
    emergency_contact_phone: str | None = Field(None, max_length=50)
    consent_status: bool = False
    notes: str | None = None
    tags: list[str] | None = None
```

---

## Next Steps

1. Read [KEY_ROTATION_PROCEDURE.md](KEY_ROTATION_PROCEDURE.md) for key management procedures
2. Implement `EncryptedType` SQLAlchemy custom type
3. Write unit tests for encryption/decryption
4. Create migration for encrypted columns
5. Run backfill script on staging data
6. Benchmark performance and validate <150ms p95 target
7. Deploy to production with monitoring

---

**Questions?** Contact security-auditor or database-architect for guidance.
