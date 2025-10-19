#!/usr/bin/env python3
"""
Data migration script: Encrypt Client date_of_birth field.

This script migrates existing client date_of_birth data from plaintext DATE
columns to encrypted BYTEA columns after the database migration adds the
encrypted column.

Usage:
    python scripts/migrate_encrypt_client_dob.py

Prerequisites:
    - Database migration 92df859932f2_encrypt_client_date_of_birth.py applied
    - Encrypted column created (date_of_birth_encrypted)
    - Plaintext column still exists (not dropped yet)

Process:
    1. Fetch all clients with non-null date_of_birth in batches of 100
    2. For each client:
       a. Read DATE value from old column
       b. Convert to ISO format string (YYYY-MM-DD)
       c. Encrypt string using current encryption key
       d. Write encrypted value to new column
    3. Verify all clients migrated successfully
    4. Print migration summary

Safety:
    - Reads from old column, writes to new column
    - Original data preserved until manual verification
    - Batch processing prevents memory exhaustion
    - Progress logged to stdout

After completion:
    - Verify encryption: python scripts/verify_client_dob_encryption.py
    - If verification passes, proceed with dropping old column
"""

import asyncio
import sys
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

# Add src to path for imports
sys.path.insert(0, "src")

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger
from pazpaz.db.base import get_async_session
from pazpaz.models.client import Client
from pazpaz.utils.encryption import encrypt_field, get_current_key_version, get_key_for_version

logger = get_logger(__name__)


async def migrate_client_dob():
    """
    Migrate client date_of_birth from DATE to encrypted string.

    This function reads DATE values from old column and writes encrypted
    ISO format strings to new column. It processes clients in batches to
    prevent memory issues.
    """
    print("=" * 80)
    print("CLIENT DATE_OF_BIRTH ENCRYPTION MIGRATION")
    print("=" * 80)
    print(f"Started at: {datetime.now().isoformat()}")
    print("")

    # Get current encryption key
    try:
        key_version = get_current_key_version()
        encryption_key = get_key_for_version(key_version)
        print(f"✅ Using encryption key version: {key_version}")
    except Exception as e:
        print(f"❌ Failed to get encryption key: {e}")
        print("   Falling back to settings.encryption_key (v1)")
        encryption_key = settings.encryption_key
        key_version = "v1"

    print("")

    # Statistics
    total_clients = 0
    migrated_clients = 0
    failed_clients = 0
    skipped_clients = 0
    batch_size = 100
    offset = 0

    # Get database session
    async for session in get_async_session():
        # Count total clients with non-null date_of_birth
        print("Counting clients with date_of_birth...")
        count_result = await session.execute(
            text("SELECT COUNT(*) FROM clients WHERE date_of_birth IS NOT NULL")
        )
        total_clients = count_result.scalar()
        print(f"Total clients with date_of_birth to migrate: {total_clients}")
        print("")

        if total_clients == 0:
            print("✅ No clients with date_of_birth to migrate.")
            return

        # Process in batches
        while True:
            print(f"Processing batch: offset={offset}, limit={batch_size}")

            # Fetch batch of clients (raw SQL to read from plaintext DATE column)
            result = await session.execute(
                text(
                    """
                    SELECT
                        id,
                        date_of_birth
                    FROM clients
                    WHERE date_of_birth IS NOT NULL
                    ORDER BY id
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {"limit": batch_size, "offset": offset},
            )

            clients = result.fetchall()

            if not clients:
                break  # No more clients to process

            # Encrypt and update each client
            for client in clients:
                try:
                    # Extract plaintext values
                    client_id = client[0]
                    date_of_birth = client[1]  # Python date object

                    # Convert DATE to ISO format string (YYYY-MM-DD)
                    dob_string = date_of_birth.isoformat()  # "YYYY-MM-DD"

                    # Encrypt the string
                    dob_encrypted = encrypt_field(dob_string, encryption_key)

                    # Prepend version prefix
                    version_prefix = f"{key_version}:".encode()
                    dob_encrypted = version_prefix + dob_encrypted

                    # Update client with encrypted value
                    await session.execute(
                        text(
                            """
                            UPDATE clients
                            SET date_of_birth_encrypted = :dob_encrypted
                            WHERE id = :id
                            """
                        ),
                        {
                            "id": client_id,
                            "dob_encrypted": dob_encrypted,
                        },
                    )

                    migrated_clients += 1

                    # Log progress every 10 clients
                    if migrated_clients % 10 == 0:
                        print(f"  Migrated: {migrated_clients}/{total_clients} clients")

                except Exception as e:
                    logger.error(
                        "client_dob_migration_failed",
                        client_id=str(client_id),
                        error=str(e),
                        exc_info=True,
                    )
                    failed_clients += 1
                    print(f"  ❌ Failed to migrate client {client_id}: {e}")

            # Commit batch
            await session.commit()
            print(f"  ✅ Batch committed: {len(clients)} clients")
            print("")

            # Move to next batch
            offset += batch_size

        # Print summary
        print("=" * 80)
        print("MIGRATION SUMMARY")
        print("=" * 80)
        print(f"Total clients:    {total_clients}")
        print(f"Migrated:         {migrated_clients}")
        print(f"Failed:           {failed_clients}")
        print(f"Skipped:          {skipped_clients}")
        print(f"Success rate:     {(migrated_clients / total_clients * 100):.2f}%" if total_clients > 0 else "N/A")
        print("")
        print(f"Completed at: {datetime.now().isoformat()}")
        print("")

        if failed_clients > 0:
            print("⚠️  WARNING: Some clients failed to migrate.")
            print("   Review logs and retry migration before proceeding.")
            sys.exit(1)
        else:
            print("✅ SUCCESS: All client date_of_birth values migrated successfully!")
            print("")
            print("Next steps:")
            print("  1. Verify encryption: python scripts/verify_client_dob_encryption.py")
            print("  2. If verification passes, proceed with dropping old column")
            print("     (this happens automatically in migration Step 3)")

        break  # Exit async context manager


if __name__ == "__main__":
    asyncio.run(migrate_client_dob())
