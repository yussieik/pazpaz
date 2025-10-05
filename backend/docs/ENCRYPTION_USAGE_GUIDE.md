# Encryption Usage Guide

This guide explains how to use the PazPaz application-level encryption layer for protecting PHI/PII data.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Using Encrypted Fields](#using-encrypted-fields)
- [Key Rotation](#key-rotation)
- [Performance Considerations](#performance-considerations)
- [Security Best Practices](#security-best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

PazPaz implements **application-level encryption** using AES-256-GCM (Galois/Counter Mode) authenticated encryption for PHI/PII data. This provides:

- **Confidentiality**: Encrypted data is unreadable without the key
- **Integrity**: Authentication tag prevents tampering
- **Defense in depth**: Application-level + database-level encryption (pgcrypto)

### Architecture

```
┌─────────────────┐
│  Application    │
│  (Python)       │
│                 │
│  Plaintext ──►  │──► EncryptedString type
│  "John Doe"     │    (transparent encryption)
└────────┬────────┘
         │ AES-256-GCM
         ▼
┌─────────────────┐
│  PostgreSQL     │
│  Database       │
│                 │
│  BYTEA column   │
│  [nonce||ct||tag]
└─────────────────┘
```

### Key Components

1. **Encryption Utilities** (`src/pazpaz/utils/encryption.py`)
   - `encrypt_field()`: Encrypt plaintext string → bytes
   - `decrypt_field()`: Decrypt bytes → plaintext string
   - `encrypt_field_versioned()`: Encrypt with version metadata (for key rotation)
   - `decrypt_field_versioned()`: Decrypt using version-aware key lookup

2. **SQLAlchemy Types** (`src/pazpaz/db/types.py`)
   - `EncryptedString`: Transparent encryption/decryption type for VARCHAR/TEXT fields
   - `EncryptedStringVersioned`: Versioned encryption (JSONB storage) for key rotation

3. **Configuration** (`src/pazpaz/core/config.py`)
   - Local/dev: `ENCRYPTION_MASTER_KEY` environment variable
   - Staging/prod: AWS Secrets Manager integration (cached)

---

## Quick Start

### 1. Setting Up Encryption Key (Development)

Generate a 32-byte (256-bit) encryption key:

```bash
# Generate base64-encoded 32-byte key
python -c 'import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())'
```

Add to `.env`:

```env
ENCRYPTION_MASTER_KEY=your-base64-encoded-key-here
```

### 2. Using Encrypted Fields in Models

```python
from sqlalchemy import Column
from pazpaz.db.types import EncryptedString

class Client(Base):
    __tablename__ = "clients"

    # Encrypted field - transparent encryption/decryption
    medical_history = Column(EncryptedString(5000), nullable=True)
```

### 3. Application Code (Transparent Usage)

```python
# Create client (encryption is automatic)
client = Client(
    workspace_id=workspace_id,
    medical_history="Patient has diabetes and hypertension"
)
session.add(client)
await session.commit()

# Read client (decryption is automatic)
client = await session.get(Client, client_id)
print(client.medical_history)  # "Patient has diabetes..." (decrypted)

# Update client (re-encryption is automatic)
client.medical_history += " Also allergic to penicillin."
await session.commit()
```

---

## Using Encrypted Fields

### Supported Field Types

Use `EncryptedString` for any text field containing PII/PHI:

| Field Type | Use EncryptedString For | Example |
|------------|------------------------|---------|
| Names | `first_name`, `last_name` | "John Doe" |
| Contact Info | `email`, `phone`, `address` | "john@example.com" |
| Medical Data | `medical_history`, `notes` | "Patient has diabetes" |
| SOAP Notes | `subjective`, `objective`, `assessment`, `plan` | Clinical notes |

### Database Column Configuration

```python
from pazpaz.db.types import EncryptedString

# Basic encrypted field
medical_history = Column(
    EncryptedString(5000),  # Max plaintext length hint
    nullable=True,
    comment="Medical history (PHI - encrypted at rest)"
)

# Required encrypted field
first_name = Column(
    EncryptedString(255),
    nullable=False,  # Required field
    comment="Client first name (PII - encrypted at rest)"
)
```

**Important**: The `length` parameter is a hint for the maximum plaintext size. The actual database column will be BYTEA (binary) with size = plaintext_length + 28 bytes overhead (12-byte nonce + 16-byte tag).

### Migration Example

When adding encryption to existing models:

```python
# Alembic migration: versions/xxxx_encrypt_client_pii.py

from alembic import op
import sqlalchemy as sa
from sqlalchemy import LargeBinary

def upgrade():
    # Step 1: Add new encrypted columns (BYTEA type)
    op.add_column('clients',
        sa.Column('first_name_encrypted', LargeBinary(), nullable=True))
    op.add_column('clients',
        sa.Column('last_name_encrypted', LargeBinary(), nullable=True))

    # Step 2: Data migration (run separate Python script)
    # See docs/ENCRYPTED_MODELS_EXAMPLE.py for details

    # Step 3: Drop old plaintext columns
    op.drop_column('clients', 'first_name')
    op.drop_column('clients', 'last_name')

    # Step 4: Rename encrypted columns
    op.alter_column('clients', 'first_name_encrypted',
        new_column_name='first_name', nullable=False)
    op.alter_column('clients', 'last_name_encrypted',
        new_column_name='last_name', nullable=False)

def downgrade():
    # Downgrade not supported for encrypted fields
    # (decryption would require key access in migration)
    raise NotImplementedError("Cannot downgrade encrypted fields")
```

---

## Key Rotation

Key rotation is essential for long-term security. PazPaz supports zero-downtime key rotation using versioned encryption.

### When to Rotate Keys

Rotate encryption keys when:

- **Scheduled rotation**: Every 12-24 months (compliance requirement)
- **Suspected compromise**: Key may have been exposed
- **Personnel change**: Team member with key access leaves
- **Regulatory requirement**: Compliance mandates key rotation

### Key Rotation Procedure

#### Phase 1: Deploy New Key (Dual-Write)

1. **Generate new encryption key** (v2):

```bash
# Generate new key
python -c 'import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())'

# Store in AWS Secrets Manager
aws secretsmanager create-secret \
    --name pazpaz/encryption-key-v2 \
    --secret-string "your-new-base64-key"
```

2. **Update application configuration** to support both keys:

```python
# src/pazpaz/core/config.py

class Settings(BaseSettings):
    # ... existing config ...

    encryption_key_version: str = "v2"  # New writes use v2
    encryption_keys: dict[str, bytes] = {}  # Loaded at startup

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Load both v1 and v2 keys
        self.encryption_keys = {
            "v1": self._load_key("pazpaz/encryption-key-v1"),
            "v2": self._load_key("pazpaz/encryption-key-v2"),
        }

    @property
    def encryption_key(self) -> bytes:
        """Get current encryption key for new writes."""
        return self.encryption_keys[self.encryption_key_version]
```

3. **Update models to use versioned encryption**:

```python
from pazpaz.db.types import EncryptedStringVersioned

class Client(Base):
    # Change from EncryptedString to EncryptedStringVersioned
    medical_history = Column(
        EncryptedStringVersioned(5000, key_version="v2"),  # Use v2 for new writes
        nullable=True
    )
```

4. **Deploy application**:
   - New writes use v2
   - Reads support both v1 and v2
   - No downtime

#### Phase 2: Re-encrypt Old Data

Run background job to re-encrypt all v1 data with v2:

```python
# scripts/reencrypt_with_new_key.py

from pazpaz.core.config import settings
from pazpaz.utils.encryption import encrypt_field_versioned, decrypt_field_versioned
from pazpaz.models.client import Client

async def reencrypt_clients():
    """Re-encrypt all client data with new key version."""

    keys = settings.encryption_keys  # {"v1": key1, "v2": key2}

    async with get_session() as session:
        # Process in batches (1000 at a time)
        batch_size = 1000
        offset = 0

        while True:
            # Load batch
            query = select(Client).limit(batch_size).offset(offset)
            result = await session.execute(query)
            clients = result.scalars().all()

            if not clients:
                break

            for client in clients:
                # Re-encrypt fields still using v1
                if needs_reencryption(client.medical_history):
                    # Decrypt with v1
                    plaintext = decrypt_field_versioned(
                        client.medical_history, keys=keys
                    )

                    # Re-encrypt with v2
                    client.medical_history = encrypt_field_versioned(
                        plaintext, key_version="v2"
                    )

            await session.commit()

            print(f"Re-encrypted batch {offset // batch_size + 1}")
            offset += batch_size

def needs_reencryption(encrypted_data: dict) -> bool:
    """Check if data is still encrypted with old key version."""
    return encrypted_data and encrypted_data.get("version") == "v1"
```

Run the migration:

```bash
# Run re-encryption job
uv run python scripts/reencrypt_with_new_key.py

# Monitor progress
# Check logs: "Re-encrypted batch 1", "Re-encrypted batch 2", ...
```

#### Phase 3: Remove Old Key

After all data is re-encrypted with v2:

1. **Verify migration complete**:

```sql
-- Check for any remaining v1 encrypted data
SELECT COUNT(*)
FROM clients
WHERE medical_history::jsonb->>'version' = 'v1';
-- Should return 0
```

2. **Remove v1 key from configuration**:

```python
# src/pazpaz/core/config.py

self.encryption_keys = {
    # "v1": ... (REMOVED)
    "v2": self._load_key("pazpaz/encryption-key-v2"),
}
```

3. **Deploy updated configuration**

4. **Delete v1 key from AWS Secrets Manager**:

```bash
aws secretsmanager delete-secret \
    --secret-id pazpaz/encryption-key-v1 \
    --force-delete-without-recovery
```

### Key Rotation Timeline

```
Day 0:  Deploy v2 key (dual-write mode)
        ├─ New writes use v2
        └─ Reads support v1 and v2

Day 1:  Start background re-encryption job
        └─ Gradually convert v1 → v2

Day 7:  Verify 100% migration complete
        └─ No v1 data remaining

Day 8:  Remove v1 key from config and AWS
        └─ Single-key mode (v2 only)
```

---

## Performance Considerations

### Benchmarks

Expected performance (measured on MacBook Pro M1):

| Operation | Target | Actual (Avg) |
|-----------|--------|--------------|
| Encrypt field | <5ms | ~0.5ms |
| Decrypt field | <10ms | ~0.8ms |
| Bulk decrypt (100 fields) | <100ms | ~80ms |

### Optimization Strategies

#### 1. Minimize Decryptions

**Bad** (decrypts twice):
```python
# Query all clients
clients = await session.execute(select(Client))

# Filter in application code (decrypts all fields)
active_clients = [c for c in clients if c.is_active]
vip_clients = [c for c in active_clients if "vip" in c.tags]

# This decrypts all clients' names, even if not needed
for client in vip_clients:
    print(client.full_name)  # Decryption happens here
```

**Good** (filter before decryption):
```python
# Query only active VIP clients (no encryption involved)
query = select(Client).where(
    Client.is_active == True,
    Client.tags.contains(["vip"])
)
clients = await session.execute(query)

# Only decrypt fields when actually needed
for client in clients.scalars():
    print(client.full_name)  # Decryption happens once per needed field
```

#### 2. Batch Processing

For bulk operations, process in batches:

```python
# Good: Process 1000 records at a time
batch_size = 1000
offset = 0

while True:
    query = select(Client).limit(batch_size).offset(offset)
    clients = (await session.execute(query)).scalars().all()

    if not clients:
        break

    # Process batch
    for client in clients:
        process_client(client)

    offset += batch_size
```

#### 3. Caching Decrypted Values

**⚠️ Security Trade-off**: Caching decrypted values improves performance but increases security risk.

```python
# Cache decrypted values in application memory (if acceptable)
from functools import lru_cache

@lru_cache(maxsize=100)
def get_client_name(client_id: uuid.UUID) -> str:
    # Cached for session duration
    client = session.get(Client, client_id)
    return client.full_name

# Clear cache on sensitive operations
get_client_name.cache_clear()
```

**When caching is acceptable**:
- Short-lived caches (session duration only)
- Non-PHI fields (names, email)
- Protected environments (authenticated sessions)

**Never cache**:
- Medical history or SOAP notes
- Data displayed to multiple users
- Long-lived caches (>5 minutes)

### Index Limitations

**⚠️ Important**: You **cannot create indexes on encrypted fields** (e.g., cannot use LIKE or = on encrypted data).

**Removed indexes** (after encryption):
```sql
-- BEFORE encryption:
CREATE INDEX idx_clients_lastname ON clients(last_name);
CREATE INDEX idx_clients_email ON clients(email);

-- AFTER encryption:
-- ❌ These indexes no longer work (searching random bytes)
-- Must use alternative strategies
```

**Alternative search strategies**:

1. **Full table scan within workspace** (acceptable for MVP):
```python
# Load all clients in workspace (workspace scoping limits size)
query = select(Client).where(Client.workspace_id == workspace_id)
clients = (await session.execute(query)).scalars().all()

# Search in application code after decryption
search_term = "john"
results = [c for c in clients if search_term.lower() in c.first_name.lower()]
```

2. **Tokenization table** (future optimization):
```python
# Separate table with hashed/tokenized search tokens
class ClientSearchToken(Base):
    client_id = Column(UUID, ForeignKey("clients.id"))
    token_hash = Column(String)  # Hash of search term (e.g., SHA256("john"))

# Index on token_hash enables fast lookup
# Trade-off: Hash collisions, less security than full encryption
```

3. **Full-text search** (post-decryption):
```python
# Use PostgreSQL full-text search on decrypted application-side cache
# Requires caching (security trade-off)
```

---

## Security Best Practices

### 1. Never Log Decrypted PII/PHI

**Bad** ❌:
```python
logger.info(f"Processing client: {client.full_name}")  # Logs PII!
logger.debug(f"Medical history: {client.medical_history}")  # Logs PHI!
```

**Good** ✅:
```python
logger.info(f"Processing client", client_id=client.id)  # Only log ID
logger.debug(f"Medical history updated", client_id=client.id, length=len(client.medical_history))
```

### 2. Use Audit Logging for PHI Access

Track all access to encrypted fields:

```python
from pazpaz.services.audit_service import log_audit_event

# Log when PHI is accessed
await log_audit_event(
    db=session,
    user_id=current_user.id,
    workspace_id=workspace_id,
    action="read",
    entity_type="client",
    entity_id=client.id,
    # Do NOT log decrypted value
)

# Then access the field
medical_history = client.medical_history
```

### 3. Validate Key Strength

Always use 32-byte (256-bit) keys:

```python
# Good: Generate cryptographically secure key
import secrets
key = secrets.token_bytes(32)

# Bad: Weak key generation
key = hashlib.sha256(b"password").digest()  # ❌ Predictable
key = os.urandom(16)  # ❌ Only 128-bit
```

### 4. Protect Keys in Transit and at Rest

**Development**:
- Store in `.env` file (not committed to git)
- Base64-encoded 32-byte random key

**Production**:
- Use AWS Secrets Manager (encrypted at rest)
- Rotate keys regularly (12-24 months)
- Enable CloudTrail logging for key access

**Never**:
- Hardcode keys in source code
- Commit keys to version control
- Share keys via email/Slack
- Store keys in database

### 5. Defense in Depth

Application-level encryption is one layer. Also implement:

- **Transport encryption**: TLS/HTTPS for all connections
- **Database encryption**: pgcrypto or transparent data encryption
- **Disk encryption**: Encrypt database storage volumes
- **Access controls**: Workspace scoping, RBAC
- **Audit logging**: Track all PHI access

---

## Troubleshooting

### Error: "Encryption key must be 32 bytes"

**Cause**: Invalid key size (not 256-bit).

**Solution**:
```bash
# Generate valid key
python -c 'import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())'

# Add to .env
ENCRYPTION_MASTER_KEY=<generated-key>
```

### Error: "Decryption failed (wrong key or tampering)"

**Cause**:
- Using wrong decryption key
- Ciphertext was modified/corrupted
- Key rotation issue (v1 data, v2 key)

**Solution**:
```python
# Check if using correct key
from pazpaz.core.config import settings
key = settings.encryption_key
print(f"Key length: {len(key)} bytes")  # Should be 32

# For versioned encryption, check key registry
if hasattr(settings, 'encryption_keys'):
    print(f"Available key versions: {list(settings.encryption_keys.keys())}")
```

### Error: "Ciphertext too short"

**Cause**: Corrupted ciphertext or wrong data type.

**Solution**:
```python
# Verify ciphertext format
print(f"Ciphertext length: {len(ciphertext)} bytes")
# Should be >= 28 bytes (12 nonce + 16 tag)

# Check if it's base64-encoded (versioned encryption)
try:
    import base64
    decoded = base64.b64decode(ciphertext)
    print(f"Decoded length: {len(decoded)} bytes")
except:
    print("Not base64-encoded")
```

### Performance: Queries are slow after encryption

**Cause**: Decrypting many fields or missing optimization.

**Solution**:
1. **Profile query**: Time decryption operations
```python
import time
start = time.time()
clients = (await session.execute(select(Client))).scalars().all()
print(f"Query time: {time.time() - start}s")

start = time.time()
for c in clients:
    _ = c.full_name  # Triggers decryption
print(f"Decryption time: {time.time() - start}s")
```

2. **Optimize**: Only decrypt fields you need
```python
# Bad: Decrypt all fields
for client in clients:
    print(client.full_name, client.email, client.medical_history)

# Good: Only decrypt needed fields
for client in clients:
    print(client.full_name)  # Only decrypt name
```

3. **Batch processing**: Process in smaller batches (1000 records)

### Migration: How to encrypt existing data?

See [Migration Example](#migration-example) above and `docs/ENCRYPTED_MODELS_EXAMPLE.py`.

---

## Additional Resources

- **Code Examples**: `docs/ENCRYPTED_MODELS_EXAMPLE.py`
- **Test Suite**: `tests/test_encryption.py` (17+ comprehensive tests)
- **Encryption Utilities**: `src/pazpaz/utils/encryption.py`
- **SQLAlchemy Types**: `src/pazpaz/db/types.py`

---

## Support

For questions or issues:

1. Check this guide and code examples
2. Review test suite for usage patterns
3. Check audit logs for PHI access patterns
4. Consult security team for key rotation or compliance questions
