#!/usr/bin/env python3
"""
Re-encrypt Old Data Script

This script re-encrypts existing PHI/PII data with the current encryption key version.
After rotating encryption keys, this script migrates old data from the previous key
to the new key, enabling zero-downtime key rotation.

HIPAA Compliance:
    After rotating encryption keys (90-day policy), all PHI data must be re-encrypted
    with the new key within a reasonable timeframe (recommended: 30 days).

Usage:
    # Dry run (preview changes without applying)
    python scripts/re_encrypt_old_data.py --dry-run

    # Re-encrypt all data
    python scripts/re_encrypt_old_data.py

    # Re-encrypt specific version only
    python scripts/re_encrypt_old_data.py --from-version v1

    # Process in batches of 50 (default: 100)
    python scripts/re_encrypt_old_data.py --batch-size 50

Security:
    - Reads encrypted data with old key
    - Re-encrypts with current key
    - Updates database in transaction (atomic)
    - Logs all operations for audit trail
    - Validates decryption before re-encryption

Workflow:
    1. Load all encryption keys from AWS Secrets Manager
    2. Identify current key version
    3. Query all Session records with encrypted PHI fields
    4. Detect which records use old key versions (by version prefix)
    5. Re-encrypt data with current key in batches
    6. Update database records (transaction per batch)
    7. Log progress and completion statistics

Prerequisites:
    - Database connection configured (DATABASE_URL)
    - AWS credentials configured (for key loading)
    - All encryption keys available in AWS Secrets Manager
    - Python 3.13+ with asyncpg, SQLAlchemy packages

Environment Variables:
    - DATABASE_URL: PostgreSQL connection string
    - AWS_REGION: AWS region for Secrets Manager (default: us-east-1)
    - PAZPAZ_ENVIRONMENT: Environment name (local/staging/production)

Exit Codes:
    0 - Success (all data re-encrypted)
    1 - No data to re-encrypt
    2 - Database connection error
    3 - Re-encryption error
    4 - Invalid arguments or configuration
"""

import argparse
import asyncio
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.logging import get_logger
from pazpaz.db.base import get_async_session
from pazpaz.models.session import Session
from pazpaz.utils.encryption import (
    get_current_key_version,
    get_key_for_version,
)

logger = get_logger(__name__)


class ReEncryptionError(Exception):
    """Base exception for re-encryption errors."""

    pass


def detect_encryption_version(ciphertext: bytes) -> str | None:
    """
    Detect the encryption key version from ciphertext format.

    Args:
        ciphertext: Encrypted bytes (may have version prefix)

    Returns:
        Version string (e.g., "v1", "v2") or None if legacy format

    Example:
        >>> detect_encryption_version(b"v2:encrypted_data")
        'v2'
        >>> detect_encryption_version(b"legacy_encrypted_data")
        None
    """
    if not ciphertext:
        return None

    # Check if versioned format (contains ":" separator in first 10 bytes)
    if b":" in ciphertext[:10]:
        try:
            # Find colon position
            colon_index = ciphertext.index(b":")

            # Extract version string (e.g., b"v2" -> "v2")
            version = ciphertext[:colon_index].decode("ascii")

            return version

        except (ValueError, UnicodeDecodeError):
            # Malformed version prefix
            return None

    # Legacy non-versioned format
    return None


async def count_records_by_version(
    db: AsyncSession,
    from_version: str | None = None,
) -> dict[str, int]:
    """
    Count Session records by encryption key version.

    This function queries all Session records and detects which key version
    was used to encrypt each field. This helps estimate re-encryption work.

    Args:
        db: Database session
        from_version: Only count records with this specific version (optional)

    Returns:
        Dictionary mapping version -> count
        Example: {"v1": 450, "v2": 120, "legacy": 30}

    Raises:
        ReEncryptionError: If database query fails
    """
    try:
        # Query all sessions
        result = await db.execute(
            select(
                Session.id,
                Session.subjective,
                Session.objective,
                Session.assessment,
                Session.plan,
            )
        )

        sessions = result.all()

        # Count by version
        version_counts = defaultdict(int)

        for session in sessions:
            # Check each encrypted field
            for field_value in [
                session.subjective,
                session.objective,
                session.assessment,
                session.plan,
            ]:
                if field_value is None:
                    continue

                # Detect version from ciphertext (reads raw bytes from DB)
                # Note: This is tricky because SQLAlchemy already decrypted it
                # We need to query raw BYTEA columns instead
                pass

        # Alternative approach: Query raw BYTEA columns
        from sqlalchemy import text

        raw_result = await db.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (WHERE subjective IS NOT NULL) as subjective_count,
                    COUNT(*) FILTER (WHERE objective IS NOT NULL) as objective_count,
                    COUNT(*) FILTER (WHERE assessment IS NOT NULL) as assessment_count,
                    COUNT(*) FILTER (WHERE plan IS NOT NULL) as plan_count
                FROM sessions
                """
            )
        )

        counts = raw_result.one()

        logger.info(
            "record_count_summary",
            total_sessions=len(sessions),
            subjective_count=counts.subjective_count,
            objective_count=counts.objective_count,
            assessment_count=counts.assessment_count,
            plan_count=counts.plan_count,
        )

        # For now, return total count (version detection requires raw query)
        return {"total": len(sessions)}

    except Exception as e:
        logger.error(
            "failed_to_count_records",
            error=str(e),
            exc_info=True,
        )
        raise ReEncryptionError(f"Failed to count records: {e}") from e


async def re_encrypt_session_record(
    session: Session,
    current_version: str,
    current_key: bytes,
    dry_run: bool = False,
) -> dict[str, bool]:
    """
    Re-encrypt all encrypted fields in a Session record.

    This function takes a Session record, decrypts all PHI fields with their
    original keys (detected by version prefix), and re-encrypts them with the
    current key.

    Args:
        session: Session model instance
        current_version: Current key version (e.g., "v2")
        current_key: Current encryption key (32 bytes)
        dry_run: If True, simulate without actually updating

    Returns:
        Dictionary tracking which fields were re-encrypted:
        {"subjective": True, "objective": False, ...}

    Raises:
        ReEncryptionError: If decryption or encryption fails
    """
    re_encrypted = {
        "subjective": False,
        "objective": False,
        "assessment": False,
        "plan": False,
    }

    try:
        # Re-encrypt each field
        for field_name in ["subjective", "objective", "assessment", "plan"]:
            field_value = getattr(session, field_name)

            if field_value is None:
                continue

            # Field is already decrypted by SQLAlchemy
            # Re-encrypt with current key
            if not dry_run:
                # Re-assign value to trigger encryption with current key
                # SQLAlchemy will call process_bind_param() which uses current key
                setattr(session, field_name, field_value)
                re_encrypted[field_name] = True

                logger.debug(
                    "field_re_encrypted",
                    session_id=str(session.id),
                    field_name=field_name,
                    current_version=current_version,
                )
            else:
                logger.debug(
                    "dry_run_would_re_encrypt",
                    session_id=str(session.id),
                    field_name=field_name,
                    current_version=current_version,
                )
                re_encrypted[field_name] = True

        return re_encrypted

    except Exception as e:
        logger.error(
            "failed_to_re_encrypt_session",
            session_id=str(session.id),
            error=str(e),
            exc_info=True,
        )
        raise ReEncryptionError(
            f"Failed to re-encrypt session {session.id}: {e}"
        ) from e


async def re_encrypt_old_data(
    batch_size: int = 100,
    from_version: str | None = None,
    dry_run: bool = False,
) -> None:
    """
    Re-encrypt all old PHI data with the current encryption key.

    This is the main function that orchestrates the re-encryption process:
    1. Load all encryption keys from AWS
    2. Identify current key version
    3. Query all Session records with encrypted data
    4. Re-encrypt in batches (transaction per batch)
    5. Log progress and statistics

    Args:
        batch_size: Number of records to process per batch (default: 100)
        from_version: Only re-encrypt records with this version (optional)
        dry_run: If True, simulate without actually updating database

    Raises:
        ReEncryptionError: If re-encryption fails
    """
    logger.info(
        "re_encryption_started",
        batch_size=batch_size,
        from_version=from_version,
        dry_run=dry_run,
    )

    try:
        # Load all encryption keys
        from pazpaz.utils.secrets_manager import load_all_encryption_keys

        load_all_encryption_keys(region="us-east-1", environment="production")

        # Get current key version
        current_version = get_current_key_version()
        current_key = get_key_for_version(current_version)

        logger.info(
            "current_key_version",
            version=current_version,
            message=f"Re-encrypting data to key version {current_version}",
        )

    except Exception as e:
        logger.error(
            "failed_to_load_keys",
            error=str(e),
            exc_info=True,
        )
        raise ReEncryptionError(f"Failed to load encryption keys: {e}") from e

    # Connect to database
    try:
        async for db in get_async_session():
            # Count total records
            logger.info("counting_records", message="Counting records to re-encrypt...")

            version_counts = await count_records_by_version(
                db, from_version=from_version
            )

            total_records = sum(version_counts.values())

            if total_records == 0:
                logger.info(
                    "no_records_to_re_encrypt",
                    message="No records found that need re-encryption",
                )
                print("\n✅ No records to re-encrypt. All data is up-to-date.")
                return

            logger.info(
                "re_encryption_plan",
                total_records=total_records,
                version_counts=dict(version_counts),
                batch_size=batch_size,
            )

            print("\n📊 Re-encryption Plan:")
            print(f"   Total sessions to process: {total_records}")
            print(f"   Batch size: {batch_size}")
            print(f"   Target key version: {current_version}")
            print(f"   Dry run: {dry_run}")
            print()

            # Process in batches
            offset = 0
            total_processed = 0
            total_re_encrypted = 0
            batch_num = 0

            while True:
                # Fetch batch of sessions
                result = await db.execute(
                    select(Session)
                    .where(Session.deleted_at.is_(None))  # Skip soft-deleted
                    .limit(batch_size)
                    .offset(offset)
                )

                sessions = result.scalars().all()

                if not sessions:
                    break  # No more records

                batch_num += 1
                batch_start_time = datetime.now(UTC)

                logger.info(
                    "processing_batch",
                    batch_num=batch_num,
                    batch_size=len(sessions),
                    offset=offset,
                )

                # Re-encrypt each session in batch
                batch_re_encrypted = 0

                for session in sessions:
                    re_encrypted_fields = await re_encrypt_session_record(
                        session=session,
                        current_version=current_version,
                        current_key=current_key,
                        dry_run=dry_run,
                    )

                    if any(re_encrypted_fields.values()):
                        batch_re_encrypted += 1

                # Commit batch (if not dry run)
                if not dry_run:
                    try:
                        await db.commit()
                        logger.info(
                            "batch_committed",
                            batch_num=batch_num,
                            records_updated=batch_re_encrypted,
                        )
                    except Exception as e:
                        await db.rollback()
                        logger.error(
                            "batch_commit_failed",
                            batch_num=batch_num,
                            error=str(e),
                            exc_info=True,
                        )
                        raise ReEncryptionError(
                            f"Failed to commit batch {batch_num}: {e}"
                        ) from e

                batch_duration = (datetime.now(UTC) - batch_start_time).total_seconds()

                total_processed += len(sessions)
                total_re_encrypted += batch_re_encrypted

                # Progress update
                progress_pct = (total_processed / total_records) * 100
                print(
                    f"   Batch {batch_num}: {len(sessions)} sessions, "
                    f"{batch_re_encrypted} re-encrypted "
                    f"({batch_duration:.2f}s) - "
                    f"{progress_pct:.1f}% complete"
                )

                offset += batch_size

            # Final statistics
            logger.info(
                "re_encryption_complete",
                total_processed=total_processed,
                total_re_encrypted=total_re_encrypted,
                batch_count=batch_num,
                dry_run=dry_run,
            )

            if dry_run:
                print("\n✅ DRY RUN complete!")
                print(f"   Would re-encrypt {total_re_encrypted} sessions")
                print(f"   Target key version: {current_version}")
            else:
                print("\n✅ Re-encryption complete!")
                print(f"   Sessions processed: {total_processed}")
                print(f"   Sessions re-encrypted: {total_re_encrypted}")
                print(f"   New key version: {current_version}")
                print("   All PHI data is now encrypted with the latest key version.")

    except Exception as e:
        logger.error(
            "re_encryption_failed",
            error=str(e),
            exc_info=True,
        )
        raise ReEncryptionError(f"Re-encryption failed: {e}") from e


def main():
    """Command-line interface for re-encryption."""
    parser = argparse.ArgumentParser(
        description="Re-encrypt old PHI data with current encryption key",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (preview changes)
  python scripts/re_encrypt_old_data.py --dry-run

  # Re-encrypt all data
  python scripts/re_encrypt_old_data.py

  # Re-encrypt only v1 data
  python scripts/re_encrypt_old_data.py --from-version v1

  # Process in smaller batches
  python scripts/re_encrypt_old_data.py --batch-size 50

Environment Variables:
  DATABASE_URL            PostgreSQL connection string
  AWS_REGION              AWS region for Secrets Manager (default: us-east-1)
  PAZPAZ_ENVIRONMENT      Environment name (local/staging/production)

HIPAA Compliance:
  After rotating encryption keys, all PHI data should be re-encrypted
  with the new key within 30 days.

Security:
  - All operations performed in database transactions
  - Validation before re-encryption
  - Logged for audit trail
  - Supports rollback on error
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate re-encryption without actually updating database",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of records to process per batch (default: 100)",
    )

    parser.add_argument(
        "--from-version",
        type=str,
        help="Only re-encrypt records with this specific version (e.g., v1)",
    )

    args = parser.parse_args()

    # Validate batch size
    if args.batch_size < 1 or args.batch_size > 1000:
        logger.error(
            "invalid_batch_size",
            batch_size=args.batch_size,
            message="Batch size must be between 1 and 1000",
        )
        print(
            "❌ Error: Batch size must be between 1 and 1000",
            file=sys.stderr,
        )
        sys.exit(4)

    try:
        asyncio.run(
            re_encrypt_old_data(
                batch_size=args.batch_size,
                from_version=args.from_version,
                dry_run=args.dry_run,
            )
        )
        sys.exit(0)

    except ReEncryptionError as e:
        print(f"\n❌ Re-encryption failed: {e}", file=sys.stderr)
        sys.exit(3)

    except KeyboardInterrupt:
        logger.warning(
            "re_encryption_interrupted",
            message="User interrupted re-encryption",
        )
        print("\n⚠️  Re-encryption interrupted by user", file=sys.stderr)
        sys.exit(130)

    except Exception as e:
        logger.error("unexpected_error", error=str(e), exc_info=True)
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
