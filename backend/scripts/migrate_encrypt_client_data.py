#!/usr/bin/env python3
"""
Data migration script: Encrypt Client PII/PHI fields.

This script migrates existing client data from plaintext columns to encrypted
columns after the database migration adds the encrypted columns.

Usage:
    python scripts/migrate_encrypt_client_data.py

Prerequisites:
    - Database migration a2341bb8aa45_encrypt_client_pii_fields.py applied
    - Encrypted columns created (_encrypted suffix)
    - Plaintext columns still exist (not dropped yet)

Process:
    1. Fetch all clients in batches of 100
    2. For each client:
       a. Read plaintext values from old columns
       b. Encrypt each field using current encryption key
       c. Write encrypted values to new columns
    3. Verify all clients migrated successfully
    4. Print migration summary

Safety:
    - Reads from old columns, writes to new columns
    - Original data preserved until manual verification
    - Batch processing prevents memory exhaustion
    - Progress logged to stdout

After completion:
    - Verify encryption: python scripts/verify_client_encryption.py
    - If verification passes, proceed with dropping old columns
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


async def migrate_client_data():
    """
    Migrate client data from plaintext to encrypted columns.

    This function reads plaintext data from old columns and writes encrypted
    data to new columns. It processes clients in batches to prevent memory issues.
    """
    print("=" * 80)
    print("CLIENT DATA ENCRYPTION MIGRATION")
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
    batch_size = 100
    offset = 0

    # Get database session
    async for session in get_async_session():
        # Count total clients
        print("Counting total clients...")
        count_result = await session.execute(text("SELECT COUNT(*) FROM clients"))
        total_clients = count_result.scalar()
        print(f"Total clients to migrate: {total_clients}")
        print("")

        if total_clients == 0:
            print("✅ No clients to migrate. Database is empty.")
            return

        # Process in batches
        while True:
            print(f"Processing batch: offset={offset}, limit={batch_size}")

            # Fetch batch of clients (raw SQL to read from plaintext columns)
            result = await session.execute(
                text(
                    """
                    SELECT
                        id,
                        first_name,
                        last_name,
                        email,
                        phone,
                        address,
                        medical_history,
                        emergency_contact_name,
                        emergency_contact_phone
                    FROM clients
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
                    first_name = client[1]
                    last_name = client[2]
                    email = client[3]
                    phone = client[4]
                    address = client[5]
                    medical_history = client[6]
                    emergency_contact_name = client[7]
                    emergency_contact_phone = client[8]

                    # Encrypt each field (handle None values)
                    first_name_encrypted = encrypt_field(first_name, encryption_key) if first_name else None
                    last_name_encrypted = encrypt_field(last_name, encryption_key) if last_name else None
                    email_encrypted = encrypt_field(email, encryption_key) if email else None
                    phone_encrypted = encrypt_field(phone, encryption_key) if phone else None
                    address_encrypted = encrypt_field(address, encryption_key) if address else None
                    medical_history_encrypted = encrypt_field(medical_history, encryption_key) if medical_history else None
                    emergency_contact_name_encrypted = encrypt_field(emergency_contact_name, encryption_key) if emergency_contact_name else None
                    emergency_contact_phone_encrypted = encrypt_field(emergency_contact_phone, encryption_key) if emergency_contact_phone else None

                    # Prepend version prefix to each encrypted field
                    version_prefix = f"{key_version}:".encode()

                    if first_name_encrypted:
                        first_name_encrypted = version_prefix + first_name_encrypted
                    if last_name_encrypted:
                        last_name_encrypted = version_prefix + last_name_encrypted
                    if email_encrypted:
                        email_encrypted = version_prefix + email_encrypted
                    if phone_encrypted:
                        phone_encrypted = version_prefix + phone_encrypted
                    if address_encrypted:
                        address_encrypted = version_prefix + address_encrypted
                    if medical_history_encrypted:
                        medical_history_encrypted = version_prefix + medical_history_encrypted
                    if emergency_contact_name_encrypted:
                        emergency_contact_name_encrypted = version_prefix + emergency_contact_name_encrypted
                    if emergency_contact_phone_encrypted:
                        emergency_contact_phone_encrypted = version_prefix + emergency_contact_phone_encrypted

                    # Update client with encrypted values
                    await session.execute(
                        text(
                            """
                            UPDATE clients
                            SET first_name_encrypted = :first_name_encrypted,
                                last_name_encrypted = :last_name_encrypted,
                                email_encrypted = :email_encrypted,
                                phone_encrypted = :phone_encrypted,
                                address_encrypted = :address_encrypted,
                                medical_history_encrypted = :medical_history_encrypted,
                                emergency_contact_name_encrypted = :emergency_contact_name_encrypted,
                                emergency_contact_phone_encrypted = :emergency_contact_phone_encrypted
                            WHERE id = :id
                            """
                        ),
                        {
                            "id": client_id,
                            "first_name_encrypted": first_name_encrypted,
                            "last_name_encrypted": last_name_encrypted,
                            "email_encrypted": email_encrypted,
                            "phone_encrypted": phone_encrypted,
                            "address_encrypted": address_encrypted,
                            "medical_history_encrypted": medical_history_encrypted,
                            "emergency_contact_name_encrypted": emergency_contact_name_encrypted,
                            "emergency_contact_phone_encrypted": emergency_contact_phone_encrypted,
                        },
                    )

                    migrated_clients += 1

                    # Log progress every 10 clients
                    if migrated_clients % 10 == 0:
                        print(f"  Migrated: {migrated_clients}/{total_clients} clients")

                except Exception as e:
                    logger.error(
                        "client_migration_failed",
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
        print(f"Success rate:     {(migrated_clients / total_clients * 100):.2f}%" if total_clients > 0 else "N/A")
        print("")
        print(f"Completed at: {datetime.now().isoformat()}")
        print("")

        if failed_clients > 0:
            print("⚠️  WARNING: Some clients failed to migrate.")
            print("   Review logs and retry migration before proceeding.")
            sys.exit(1)
        else:
            print("✅ SUCCESS: All clients migrated successfully!")
            print("")
            print("Next steps:")
            print("  1. Verify encryption: python scripts/verify_client_encryption.py")
            print("  2. If verification passes, proceed with dropping old columns")
            print("     (this happens automatically in migration Step 3)")

        break  # Exit async context manager


if __name__ == "__main__":
    asyncio.run(migrate_client_data())
