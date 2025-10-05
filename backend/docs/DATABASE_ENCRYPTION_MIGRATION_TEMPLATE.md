# Database Encryption Migration Template
**Version:** 1.0
**Date:** 2025-10-05
**Status:** Implementation Guide (Day 4 - Security First Implementation Plan)
**Author:** database-architect

---

## Executive Summary

This document provides step-by-step templates for adding encrypted columns to existing tables using PazPaz's application-level encryption strategy (AES-256-GCM). These templates ensure zero-downtime migrations and safe rollback procedures.

**Key Principles:**
- Application-level encryption (Python `cryptography` library)
- Zero-downtime migrations using dual-write pattern
- Safe rollback with data preservation
- HIPAA-compliant encryption for all PHI/PII fields

**Use Cases:**
- Adding encryption to existing plaintext columns (migration)
- Adding new encrypted columns to existing tables
- Rotating encryption keys (zero-downtime)

---

## Table of Contents

1. [Migration Pattern Overview](#1-migration-pattern-overview)
2. [Template 1: Add New Encrypted Column](#2-template-1-add-new-encrypted-column)
3. [Template 2: Migrate Plaintext to Encrypted](#3-template-2-migrate-plaintext-to-encrypted)
4. [Template 3: Key Rotation Migration](#4-template-3-key-rotation-migration)
5. [Rollback Procedures](#5-rollback-procedures)
6. [Testing Checklist](#6-testing-checklist)
7. [Production Deployment Guide](#7-production-deployment-guide)

---

## 1. Migration Pattern Overview

### 1.1 Zero-Downtime Migration Strategy

For migrating existing plaintext data to encrypted format:

```
Phase 1: Add encrypted column (NULL)
Phase 2: Dual-write (application writes to BOTH columns)
Phase 3: Backfill (background job encrypts existing data)
Phase 4: Verify (confirm all data encrypted)
Phase 5: Cut over (application reads from encrypted column only)
Phase 6: Drop old column (after verification period)
```

**Timeline:** 1-2 weeks depending on data volume and verification requirements.

### 1.2 Column Naming Conventions

```python
# OLD: Plaintext column
medical_history: str  # VARCHAR(5000)

# NEW: Encrypted column
medical_history_encrypted: str  # VARCHAR(7000)  # Base64 overhead ~33%

# FINAL: After migration (rename)
medical_history: str  # VARCHAR(7000)  # Encrypted
```

**Storage Overhead:**
- Base64 encoding: +33% size
- Nonce (12 bytes) + version prefix (3 bytes): +15 bytes per field
- Example: 1KB plaintext → ~1.4KB encrypted (Base64 + nonce + version)

---

## 2. Template 1: Add New Encrypted Column

Use this template when adding a NEW encrypted field to an existing table.

### 2.1 Alembic Migration

```python
"""add_client_encrypted_field

Revision ID: <generated>
Revises: <previous>
Create Date: YYYY-MM-DD

Adds encrypted `insurance_info` field to clients table.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = '<generated>'
down_revision: str | Sequence[str] | None = '<previous>'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add new encrypted column to clients table."""
    # Add new encrypted column (nullable initially)
    op.add_column(
        'clients',
        sa.Column(
            'insurance_info_encrypted',
            sa.String(2000),  # Adjust size for Base64 overhead
            nullable=True,
            comment='ENCRYPTED: Insurance information (PHI) - AES-256-GCM'
        )
    )

    # Add index if needed for querying (encrypted data cannot be searched by content)
    # Only add index for non-encrypted metadata fields
    # op.create_index('ix_clients_insurance_provider', 'clients', ['insurance_provider'])

def downgrade() -> None:
    """Remove encrypted column."""
    # op.drop_index('ix_clients_insurance_provider', table_name='clients')
    op.drop_column('clients', 'insurance_info_encrypted')
```

### 2.2 SQLAlchemy Model Update

```python
# pazpaz/models/client.py

from sqlalchemy.orm import Mapped, mapped_column
from pazpaz.db.types import EncryptedString  # Custom type from Week 1 Day 4

class Client(Base):
    __tablename__ = "clients"

    # ... existing fields ...

    # NEW: Encrypted insurance information
    insurance_info: Mapped[str | None] = mapped_column(
        EncryptedString(2000),  # Encrypted type handles enc/dec automatically
        nullable=True,
        comment="ENCRYPTED: Insurance information (PHI)"
    )
```

### 2.3 Pydantic Schema Update

```python
# pazpaz/schemas/client.py

from pydantic import BaseModel, Field

class ClientCreate(BaseModel):
    """Client creation schema."""
    # ... existing fields ...

    insurance_info: str | None = Field(
        None,
        max_length=1500,  # Plaintext limit (Base64 overhead in DB)
        description="Insurance information (encrypted at rest)"
    )

class ClientResponse(BaseModel):
    """Client response schema (decrypted automatically by ORM)."""
    # ... existing fields ...

    insurance_info: str | None = Field(
        None,
        description="Insurance information (decrypted for authorized users)"
    )
```

**Key Points:**
- `EncryptedString` custom type handles encryption/decryption transparently
- Pydantic schemas work with plaintext (encryption is transparent)
- Set `max_length` in Pydantic to plaintext limit (ORM handles overhead)

---

## 3. Template 2: Migrate Plaintext to Encrypted

Use this template when migrating EXISTING plaintext data to encrypted format.

### 3.1 Phase 1: Add Encrypted Column (Migration)

```python
"""migrate_medical_history_to_encrypted

Revision ID: <generated>
Revises: <previous>
Create Date: YYYY-MM-DD

Phase 1: Add encrypted column for medical_history migration.
This is Part 1 of zero-downtime migration.

Timeline:
- Phase 1: Add column (this migration) - 0 downtime
- Phase 2: Deploy dual-write code - 0 downtime
- Phase 3: Backfill existing data - background job
- Phase 4: Deploy read-from-encrypted code - 0 downtime
- Phase 5: Drop old column (future migration) - 0 downtime
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = '<generated>'
down_revision: str | Sequence[str] | None = '<previous>'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add encrypted medical_history column (Phase 1)."""
    op.add_column(
        'clients',
        sa.Column(
            'medical_history_encrypted',
            sa.String(7000),  # 5000 * 1.4 (Base64 overhead)
            nullable=True,  # Will be populated during Phase 3
            comment='ENCRYPTED: Medical history (PHI) - AES-256-GCM. Migration in progress.'
        )
    )

    # Create index for future queries (after migration complete)
    # NOTE: Cannot index encrypted data by content
    # Only add index if you need to check NULL/NOT NULL
    op.create_index(
        'ix_clients_medical_history_encrypted_notnull',
        'clients',
        ['medical_history_encrypted'],
        postgresql_where=sa.text('medical_history_encrypted IS NOT NULL')
    )


def downgrade() -> None:
    """Remove encrypted column (rollback Phase 1)."""
    op.drop_index('ix_clients_medical_history_encrypted_notnull', table_name='clients')
    op.drop_column('clients', 'medical_history_encrypted')
```

### 3.2 Phase 2: Dual-Write Application Code

Deploy this code AFTER Phase 1 migration completes.

```python
# pazpaz/models/client.py

class Client(Base):
    __tablename__ = "clients"

    # OLD: Plaintext column (will be removed in Phase 6)
    medical_history_plaintext: Mapped[str | None] = mapped_column(
        "medical_history",  # Keep original column name for now
        String(5000),
        nullable=True,
        comment="DEPRECATED: Use medical_history_encrypted. Migration in progress."
    )

    # NEW: Encrypted column (dual-write during migration)
    medical_history_encrypted: Mapped[str | None] = mapped_column(
        EncryptedString(7000),
        nullable=True,
        comment="ENCRYPTED: Medical history (PHI) - AES-256-GCM"
    )

    @hybrid_property
    def medical_history(self) -> str | None:
        """
        Read from encrypted column if available, fallback to plaintext.

        During migration, this ensures backwards compatibility.
        """
        if self.medical_history_encrypted is not None:
            return self.medical_history_encrypted
        return self.medical_history_plaintext

    @medical_history.setter
    def medical_history(self, value: str | None):
        """
        DUAL-WRITE: Write to BOTH columns during migration.

        This ensures:
        1. New data is encrypted immediately
        2. Old code can still read from plaintext column
        3. Zero downtime migration
        """
        self.medical_history_encrypted = value  # Write encrypted
        self.medical_history_plaintext = value  # Write plaintext (temporary)
```

**Deployment Steps:**
1. Run Phase 1 migration in production
2. Deploy dual-write code (NO downtime)
3. Monitor logs for errors
4. Verify new records have BOTH columns populated

### 3.3 Phase 3: Backfill Existing Data

Create background job to encrypt existing plaintext data.

```python
# scripts/backfill_encrypted_medical_history.py

"""
Backfill script to encrypt existing medical_history data.

Run after Phase 2 dual-write code is deployed.

Usage:
    uv run python scripts/backfill_encrypted_medical_history.py --batch-size 100 --delay 0.1
"""
import asyncio
import argparse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from pazpaz.core.config import settings
from pazpaz.models.client import Client
from pazpaz.db.types import EncryptedString
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


async def backfill_medical_history(
    batch_size: int = 100,
    delay: float = 0.1,
    dry_run: bool = False
):
    """
    Backfill medical_history_encrypted from medical_history_plaintext.

    Args:
        batch_size: Number of records to process per batch
        delay: Delay between batches (seconds) to reduce database load
        dry_run: If True, only count records without updating
    """
    engine = create_async_engine(settings.database_url)
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_maker() as session:
        # Count total records needing backfill
        count_query = select(Client).where(
            Client.medical_history_plaintext.isnot(None),  # Has plaintext data
            Client.medical_history_encrypted.is_(None)  # Missing encrypted data
        )
        result = await session.execute(count_query)
        total = len(result.scalars().all())

        logger.info("backfill_start", total_records=total, batch_size=batch_size, dry_run=dry_run)

        if dry_run:
            logger.info("dry_run_complete", total_records_to_backfill=total)
            return

        # Process in batches
        processed = 0
        while processed < total:
            # Fetch batch
            batch_query = (
                select(Client)
                .where(
                    Client.medical_history_plaintext.isnot(None),
                    Client.medical_history_encrypted.is_(None)
                )
                .limit(batch_size)
            )
            result = await session.execute(batch_query)
            clients = result.scalars().all()

            if not clients:
                break  # No more records

            # Encrypt and update
            for client in clients:
                # The EncryptedString type will automatically encrypt when assigned
                client.medical_history_encrypted = client.medical_history_plaintext

            await session.commit()

            processed += len(clients)
            logger.info(
                "backfill_batch_complete",
                processed=processed,
                total=total,
                progress_percent=round((processed / total) * 100, 2)
            )

            # Delay to reduce database load
            await asyncio.sleep(delay)

        logger.info("backfill_complete", total_processed=processed)

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill encrypted medical_history")
    parser.add_argument("--batch-size", type=int, default=100, help="Records per batch")
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between batches (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Count records without updating")
    args = parser.parse_args()

    asyncio.run(backfill_medical_history(
        batch_size=args.batch_size,
        delay=args.delay,
        dry_run=args.dry_run
    ))
```

**Execution:**
```bash
# 1. Dry run to count records
uv run python scripts/backfill_encrypted_medical_history.py --dry-run

# 2. Run backfill (conservative settings for production)
uv run python scripts/backfill_encrypted_medical_history.py --batch-size 50 --delay 0.5

# 3. Monitor progress in logs
tail -f logs/app.log | grep backfill
```

### 3.4 Phase 4: Verify Migration Complete

```sql
-- Check backfill progress
SELECT
    COUNT(*) AS total_clients,
    COUNT(medical_history_plaintext) AS has_plaintext,
    COUNT(medical_history_encrypted) AS has_encrypted,
    COUNT(CASE WHEN medical_history_plaintext IS NOT NULL
               AND medical_history_encrypted IS NULL THEN 1 END) AS missing_encrypted
FROM clients;

-- Expected after backfill:
-- missing_encrypted = 0
```

### 3.5 Phase 5: Cut Over to Encrypted Only

Deploy this code AFTER backfill completes and verification passes.

```python
# pazpaz/models/client.py

class Client(Base):
    __tablename__ = "clients"

    # OLD: Deprecated plaintext column (will be dropped in Phase 6)
    _medical_history_plaintext_deprecated: Mapped[str | None] = mapped_column(
        "medical_history",
        String(5000),
        nullable=True,
        comment="DEPRECATED: Column will be dropped. Use medical_history_encrypted."
    )

    # NEW: Primary encrypted column
    medical_history: Mapped[str | None] = mapped_column(
        "medical_history_encrypted",
        EncryptedString(7000),
        nullable=True,
        comment="ENCRYPTED: Medical history (PHI) - AES-256-GCM"
    )
```

**Deployment:**
1. Deploy cut-over code
2. Monitor for errors (check logs, error rates)
3. Verify all reads/writes use encrypted column
4. Wait 1-2 weeks before Phase 6 (safety period)

### 3.6 Phase 6: Drop Old Plaintext Column

Final migration to remove deprecated plaintext column.

```python
"""drop_medical_history_plaintext

Revision ID: <generated>
Revises: <previous>
Create Date: YYYY-MM-DD

Phase 6: Drop old plaintext medical_history column.
This is the final step of zero-downtime migration.

PREREQUISITES:
- Phase 5 deployed to production (reading from encrypted column)
- At least 1-2 weeks monitoring period
- No errors in logs related to medical_history
- Backup verified
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = '<generated>'
down_revision: str | Sequence[str] | None = '<previous>'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Drop old plaintext column and rename encrypted column.

    IMPORTANT: Backup database before running this migration!
    """
    # Rename encrypted column to original name
    op.alter_column(
        'clients',
        'medical_history_encrypted',
        new_column_name='medical_history'
    )

    # Update column comment
    op.execute(
        """
        COMMENT ON COLUMN clients.medical_history IS
        'ENCRYPTED: Medical history (PHI) - AES-256-GCM. Migrated from plaintext on YYYY-MM-DD.';
        """
    )


def downgrade() -> None:
    """
    Rename column back (data remains encrypted).

    NOTE: Downgrade does NOT restore plaintext data.
    Encrypted data will remain encrypted.
    """
    op.alter_column(
        'clients',
        'medical_history',
        new_column_name='medical_history_encrypted'
    )
```

**Pre-Deployment Checklist:**
- [ ] Backup production database
- [ ] Verify Phase 5 code running for 1-2 weeks
- [ ] No errors in logs related to medical_history
- [ ] Test rollback procedure on staging
- [ ] Notify team of deployment window

---

## 4. Template 3: Key Rotation Migration

Use this template when rotating encryption keys (e.g., annual rotation, security incident).

### 4.1 Key Rotation Strategy

PazPaz uses version-prefixed ciphertext format:
```
Format: v1:nonce_b64:ciphertext_b64
Example: v1:abc123...:def456...
```

**Rotation Steps:**
1. Add new key version (v2) to AWS Secrets Manager
2. Deploy dual-read code (reads v1 or v2, writes v2)
3. Background job re-encrypts v1 → v2
4. Verify all data using v2
5. Remove v1 key from rotation

### 4.2 Dual-Read Application Code

```python
# pazpaz/utils/encryption.py

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64
import secrets

def get_encryption_key(version: str = "v1") -> bytes:
    """
    Fetch encryption key by version from AWS Secrets Manager.

    Supports key rotation by maintaining multiple key versions.
    """
    from pazpaz.core.config import settings

    if version == "v1":
        return settings.encryption_key  # Current key
    elif version == "v2":
        return settings.encryption_key_v2  # New rotated key
    else:
        raise ValueError(f"Unknown key version: {version}")


def encrypt(plaintext: str, key_version: str = "v2") -> str:
    """
    Encrypt plaintext with specified key version (default: v2 after rotation).
    """
    key = get_encryption_key(key_version)
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)
    ciphertext_bytes = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    nonce_b64 = base64.b64encode(nonce).decode("ascii")
    ciphertext_b64 = base64.b64encode(ciphertext_bytes).decode("ascii")

    return f"{key_version}:{nonce_b64}:{ciphertext_b64}"


def decrypt(ciphertext: str) -> str:
    """
    Decrypt ciphertext (auto-detects key version from prefix).
    """
    parts = ciphertext.split(":")
    if len(parts) != 3:
        raise ValueError("Invalid encrypted format")

    key_version, nonce_b64, ciphertext_b64 = parts

    key = get_encryption_key(key_version)  # Use version-specific key
    aesgcm = AESGCM(key)

    nonce = base64.b64decode(nonce_b64)
    ciphertext_bytes = base64.b64decode(ciphertext_b64)

    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_bytes, None)
    return plaintext_bytes.decode("utf-8")
```

### 4.3 Key Rotation Backfill Script

```python
# scripts/rotate_encryption_keys.py

"""
Re-encrypt all PHI fields with new encryption key version.

Run after deploying dual-read code.

Usage:
    uv run python scripts/rotate_encryption_keys.py --target-version v2 --batch-size 100
"""
import asyncio
import argparse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from pazpaz.core.config import settings
from pazpaz.models.client import Client
from pazpaz.utils.encryption import decrypt, encrypt
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


async def rotate_keys(
    target_version: str = "v2",
    batch_size: int = 100,
    delay: float = 0.1
):
    """
    Re-encrypt all PHI fields with new key version.

    This performs:
    1. Decrypt with old key (auto-detected from version prefix)
    2. Re-encrypt with new key version
    3. Update database

    Args:
        target_version: New key version (e.g., "v2")
        batch_size: Records per batch
        delay: Delay between batches (seconds)
    """
    engine = create_async_engine(settings.database_url)
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_maker() as session:
        # Find all clients with encrypted data not using target version
        query = select(Client).where(
            Client.medical_history.isnot(None)  # Has encrypted data
        )
        result = await session.execute(query)
        all_clients = result.scalars().all()

        # Filter clients needing rotation
        clients_to_rotate = [
            c for c in all_clients
            if c.medical_history and not c.medical_history.startswith(f"{target_version}:")
        ]

        total = len(clients_to_rotate)
        logger.info("key_rotation_start", total_records=total, target_version=target_version)

        # Process in batches
        for i in range(0, total, batch_size):
            batch = clients_to_rotate[i:i+batch_size]

            for client in batch:
                # Decrypt with old key (auto-detected)
                plaintext = decrypt(client.medical_history)

                # Re-encrypt with new key
                client.medical_history = encrypt(plaintext, key_version=target_version)

            await session.commit()

            processed = min(i + batch_size, total)
            logger.info(
                "key_rotation_batch_complete",
                processed=processed,
                total=total,
                progress_percent=round((processed / total) * 100, 2)
            )

            await asyncio.sleep(delay)

        logger.info("key_rotation_complete", total_processed=total)

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rotate encryption keys")
    parser.add_argument("--target-version", default="v2", help="New key version")
    parser.add_argument("--batch-size", type=int, default=100, help="Records per batch")
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between batches")
    args = parser.parse_args()

    asyncio.run(rotate_keys(
        target_version=args.target_version,
        batch_size=args.batch_size,
        delay=args.delay
    ))
```

**Execution:**
```bash
# 1. Add v2 key to AWS Secrets Manager
aws secretsmanager create-secret \
    --name pazpaz/encryption-key-v2 \
    --secret-string $(openssl rand -base64 32)

# 2. Deploy dual-read code (reads v1 or v2, writes v2)

# 3. Run key rotation
uv run python scripts/rotate_encryption_keys.py --target-version v2

# 4. Verify all data uses v2
SELECT
    COUNT(*) AS total,
    COUNT(CASE WHEN medical_history LIKE 'v1:%' THEN 1 END) AS v1_count,
    COUNT(CASE WHEN medical_history LIKE 'v2:%' THEN 1 END) AS v2_count
FROM clients
WHERE medical_history IS NOT NULL;

# 5. Remove v1 key from AWS after verification period (30+ days)
```

---

## 5. Rollback Procedures

### 5.1 Rollback Phase 1 (Add Column)

```bash
# Downgrade migration
uv run alembic downgrade -1

# Verify column removed
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "\d clients"
```

### 5.2 Rollback Phase 2 (Dual-Write)

```bash
# Revert code deployment
git revert <commit-hash>

# Redeploy previous version
./deploy.sh previous-version

# Verify plaintext column still being written
SELECT COUNT(*) FROM clients WHERE medical_history IS NOT NULL;
```

### 5.3 Rollback Phase 5 (Cut Over)

If errors occur after cutting over to encrypted-only reads:

```bash
# 1. Revert code deployment immediately
git revert <commit-hash>

# 2. Verify plaintext column still exists
docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "\d clients"

# 3. Check for data loss
SELECT
    COUNT(*) AS total_clients,
    COUNT(medical_history) AS has_plaintext,
    COUNT(medical_history_encrypted) AS has_encrypted
FROM clients;

# 4. If plaintext column missing, restore from backup
pg_restore --clean --if-exists -d pazpaz backup.dump
```

### 5.4 Emergency Rollback (Data Corruption)

If encrypted data is corrupted or keys are lost:

```bash
# 1. STOP ALL APPLICATION INSTANCES IMMEDIATELY
kubectl scale deployment pazpaz-api --replicas=0

# 2. Restore from most recent backup
pg_restore --clean --if-exists -d pazpaz_production backup_YYYY-MM-DD.dump

# 3. Verify data integrity
SELECT COUNT(*) FROM clients WHERE medical_history IS NOT NULL;

# 4. Investigate root cause before restarting application
# 5. Notify security team of potential breach
```

---

## 6. Testing Checklist

### 6.1 Pre-Migration Testing (Staging)

- [ ] Run migration on staging database (same data volume as production)
- [ ] Verify schema changes applied correctly
- [ ] Test dual-write code with sample data
- [ ] Run backfill script on staging
- [ ] Verify encryption/decryption round-trip
- [ ] Test rollback procedure
- [ ] Performance test: Query latency <150ms p95
- [ ] Performance test: Bulk decryption (100 fields) <100ms

### 6.2 Migration Day Checklist

- [ ] Backup production database (verified restorable)
- [ ] Run Phase 1 migration during low-traffic window
- [ ] Deploy Phase 2 dual-write code
- [ ] Monitor error logs for 1 hour
- [ ] Verify new records have both columns populated
- [ ] Schedule backfill during off-peak hours

### 6.3 Post-Migration Verification

- [ ] All records have encrypted column populated
- [ ] No errors in application logs (24 hours)
- [ ] API response times within target (<150ms p95)
- [ ] Audit logs show PHI access still tracked
- [ ] Manual spot-check: Decrypt sample records, verify accuracy
- [ ] Security scan: Confirm no plaintext PHI in database dumps

---

## 7. Production Deployment Guide

### 7.1 Pre-Deployment

**1 Week Before:**
- [ ] Test migration on production-sized staging database
- [ ] Review rollback procedures with team
- [ ] Schedule deployment window (low-traffic period)
- [ ] Notify stakeholders of planned maintenance

**1 Day Before:**
- [ ] Create full database backup
- [ ] Verify backup is restorable
- [ ] Prepare rollback scripts
- [ ] Set up monitoring alerts (error rates, latency)

### 7.2 Deployment Day

**Phase 1: Schema Change (5 minutes)**
```bash
# 1. Backup database
pg_dump -U pazpaz -d pazpaz_production > backup_$(date +%Y%m%d_%H%M%S).dump

# 2. Run migration
uv run alembic upgrade head

# 3. Verify schema change
docker exec pazpaz-db psql -U pazpaz -d pazpaz_production -c "\d clients"
```

**Phase 2: Deploy Dual-Write Code (10 minutes)**
```bash
# 1. Deploy new version
kubectl set image deployment/pazpaz-api pazpaz-api=pazpaz:dual-write-v1.2.0

# 2. Wait for rollout
kubectl rollout status deployment/pazpaz-api

# 3. Monitor logs
kubectl logs -f deployment/pazpaz-api | grep "medical_history"

# 4. Verify dual-write (create test record via API)
curl -X POST https://api.pazpaz.com/api/v1/clients \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"first_name": "Test", "medical_history": "Test data"}'

# 5. Check database (should have BOTH columns populated)
docker exec pazpaz-db psql -U pazpaz -d pazpaz_production -c \
    "SELECT medical_history, medical_history_encrypted FROM clients WHERE first_name = 'Test';"
```

**Phase 3: Backfill (30 minutes - 2 hours)**
```bash
# 1. Run backfill during off-peak hours
uv run python scripts/backfill_encrypted_medical_history.py \
    --batch-size 50 \
    --delay 0.5

# 2. Monitor progress
tail -f logs/backfill.log

# 3. Verify completion
docker exec pazpaz-db psql -U pazpaz -d pazpaz_production -c \
    "SELECT COUNT(*) AS missing FROM clients
     WHERE medical_history IS NOT NULL
     AND medical_history_encrypted IS NULL;"
# Expected: missing = 0
```

**Phase 4: Verification (24 hours)**
- [ ] Monitor error logs
- [ ] Check API response times (should be <150ms p95)
- [ ] Verify no regressions in existing features
- [ ] Audit trail still logging PHI access

**Phase 5: Cut Over (1-2 weeks later)**
- [ ] Deploy read-from-encrypted code
- [ ] Monitor for 1-2 weeks
- [ ] If stable, proceed to Phase 6

**Phase 6: Drop Old Column (Final)**
- [ ] Run final migration (drop plaintext column)
- [ ] Verify application still functional
- [ ] Archive backup for 90 days (compliance requirement)

### 7.3 Post-Deployment

**Immediate (24 hours):**
- [ ] Monitor error rates (should be <1%)
- [ ] Verify API latency (<150ms p95)
- [ ] Check audit logs (all PHI access logged)

**Short-term (1 week):**
- [ ] Review security logs for anomalies
- [ ] Performance testing on production
- [ ] User acceptance testing

**Long-term (30 days):**
- [ ] Archive old backups (pre-encryption)
- [ ] Update documentation
- [ ] Remove v1 encryption key from rotation (if key rotation occurred)

---

## Summary

This template provides production-ready migration patterns for encrypting sensitive data in PazPaz. Key takeaways:

1. **Zero-Downtime:** Dual-write pattern ensures no service interruption
2. **Safety First:** Multiple verification steps before irreversible changes
3. **Rollback-Ready:** Clear rollback procedures for each phase
4. **HIPAA-Compliant:** Encrypted at rest, audit trail preserved

**Next Steps:**
- Review [ENCRYPTION_ARCHITECTURE.md](ENCRYPTION_ARCHITECTURE.md) for encryption design
- Review [KEY_ROTATION_PROCEDURE.md](KEY_ROTATION_PROCEDURE.md) for key rotation details
- Implement `EncryptedString` SQLAlchemy type (Week 1 Day 4, fullstack-backend-specialist)

**Questions?** Consult database-architect or security-auditor agents.
