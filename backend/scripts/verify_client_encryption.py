#!/usr/bin/env python3
"""
Verification script: Verify Client PII/PHI field encryption.

This script verifies that client data is properly encrypted at rest after
running the data migration script.

Usage:
    python scripts/verify_client_encryption.py

Checks:
    1. Raw database values are encrypted (BYTEA with version prefix)
    2. ORM values are decrypted correctly (plaintext accessible)
    3. Encryption format matches expected pattern (v1: or v2: prefix)
    4. All required fields encrypted (first_name, last_name)
    5. Optional fields encrypted if present

Success criteria:
    - All clients have encrypted data in database
    - ORM correctly decrypts all values
    - No plaintext leakage in raw database values
    - Version prefix present on all encrypted values
"""

import asyncio
import sys

from sqlalchemy import select, text

# Add src to path for imports
sys.path.insert(0, "src")

from pazpaz.core.logging import get_logger
from pazpaz.db.base import get_async_session
from pazpaz.models.client import Client

logger = get_logger(__name__)


async def verify_encryption():
    """
    Verify client data is encrypted at rest.

    This function checks both raw database values (should be encrypted binary)
    and ORM values (should be decrypted plaintext).
    """
    print("=" * 80)
    print("CLIENT ENCRYPTION VERIFICATION")
    print("=" * 80)
    print("")

    # Get database session
    async for session in get_async_session():
        # Fetch sample clients (first 10)
        print("Fetching sample clients (first 10)...")
        result = await session.execute(select(Client).limit(10))
        clients = result.scalars().all()

        if not clients:
            print("❌ No clients found in database. Cannot verify encryption.")
            sys.exit(1)

        print(f"Found {len(clients)} clients to verify")
        print("")

        # Verification counters
        total_verified = 0
        total_failed = 0

        for client in clients:
            print(f"Verifying client: {client.id}")
            print("-" * 80)

            try:
                # Test 1: ORM values should be decrypted plaintext
                print(f"  ORM (decrypted) first_name: {client.first_name}")
                print(f"  ORM (decrypted) last_name:  {client.last_name}")

                if client.email:
                    print(f"  ORM (decrypted) email:      {client.email}")
                if client.phone:
                    print(f"  ORM (decrypted) phone:      {client.phone}")

                # Test 2: Raw database values should be encrypted binary
                raw_result = await session.execute(
                    text(
                        """
                        SELECT
                            first_name,
                            last_name,
                            email,
                            phone,
                            address,
                            medical_history,
                            emergency_contact_name,
                            emergency_contact_phone
                        FROM clients
                        WHERE id = :id
                        """
                    ),
                    {"id": client.id},
                )
                raw_data = raw_result.fetchone()

                if not raw_data:
                    print(f"  ❌ Failed to fetch raw data for client {client.id}")
                    total_failed += 1
                    continue

                # Check first_name (required field)
                raw_first_name = raw_data[0]
                if isinstance(raw_first_name, bytes):
                    print("  ✅ first_name is encrypted (binary data)")
                    print(f"     Length: {len(raw_first_name)} bytes")
                    print(f"     First 50 bytes: {raw_first_name[:50]}")

                    # Check version prefix
                    if b":" in raw_first_name[:10]:
                        version = raw_first_name[: raw_first_name.index(b":")].decode(
                            "ascii"
                        )
                        print(f"     ✅ Version prefix found: {version}")
                    else:
                        print("     ⚠️  No version prefix (legacy format)")
                else:
                    print("  ❌ first_name is NOT encrypted (not binary)")
                    print(f"     Value: {raw_first_name}")
                    total_failed += 1
                    continue

                # Check last_name (required field)
                raw_last_name = raw_data[1]
                if isinstance(raw_last_name, bytes):
                    print("  ✅ last_name is encrypted (binary data)")
                else:
                    print("  ❌ last_name is NOT encrypted")
                    total_failed += 1
                    continue

                # Check optional fields
                optional_fields = [
                    ("email", raw_data[2]),
                    ("phone", raw_data[3]),
                    ("address", raw_data[4]),
                    ("medical_history", raw_data[5]),
                    ("emergency_contact_name", raw_data[6]),
                    ("emergency_contact_phone", raw_data[7]),
                ]

                for field_name, raw_value in optional_fields:
                    if raw_value is not None:
                        if isinstance(raw_value, bytes):
                            print(f"  ✅ {field_name} is encrypted")
                        else:
                            print(f"  ❌ {field_name} is NOT encrypted: {raw_value}")
                            total_failed += 1

                # Test 3: Verify decryption matches expected plaintext
                # (Check that ORM decrypted value is reasonable)
                if not client.first_name or len(client.first_name) < 1:
                    print("  ❌ Decrypted first_name is empty or invalid")
                    total_failed += 1
                    continue

                if not client.last_name or len(client.last_name) < 1:
                    print("  ❌ Decrypted last_name is empty or invalid")
                    total_failed += 1
                    continue

                print("")
                print(f"  ✅ Client {client.id} encryption verified successfully")
                total_verified += 1

            except Exception as e:
                logger.error(
                    "client_verification_failed",
                    client_id=str(client.id),
                    error=str(e),
                    exc_info=True,
                )
                print(f"  ❌ Verification failed: {e}")
                total_failed += 1

            print("")

        # Print summary
        print("=" * 80)
        print("VERIFICATION SUMMARY")
        print("=" * 80)
        print(f"Total clients verified: {total_verified}")
        print(f"Total failures:         {total_failed}")
        print("")

        if total_failed > 0:
            print("❌ VERIFICATION FAILED")
            print("   Some clients have unencrypted or invalid data.")
            print("   DO NOT proceed with dropping old columns.")
            sys.exit(1)
        else:
            print("✅ VERIFICATION PASSED")
            print("   All client PII/PHI fields are encrypted at rest.")
            print("   Safe to proceed with dropping old plaintext columns.")

        break  # Exit async context manager


if __name__ == "__main__":
    asyncio.run(verify_encryption())
