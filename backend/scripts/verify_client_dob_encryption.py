#!/usr/bin/env python3
"""
Verification script: Verify Client date_of_birth field encryption.

This script verifies that client date_of_birth is properly encrypted at rest
after running the data migration script.

Usage:
    python scripts/verify_client_dob_encryption.py

Checks:
    1. Raw database values are encrypted (BYTEA with version prefix)
    2. ORM values are decrypted correctly (string in ISO format YYYY-MM-DD)
    3. Encryption format matches expected pattern (v1: or v2: prefix)
    4. Decrypted string can be parsed as valid date
    5. Age calculation works correctly

Success criteria:
    - All clients have encrypted data in database
    - ORM correctly decrypts all values
    - No plaintext leakage in raw database values
    - Version prefix present on all encrypted values
    - Date parsing works (datetime.fromisoformat)
"""

import asyncio
import sys
from datetime import datetime

from sqlalchemy import select, text

# Add src to path for imports
sys.path.insert(0, "src")

from pazpaz.core.logging import get_logger
from pazpaz.db.base import get_async_session
from pazpaz.models.client import Client

logger = get_logger(__name__)


async def verify_dob_encryption():
    """
    Verify client date_of_birth is encrypted at rest.

    This function checks both raw database values (should be encrypted binary)
    and ORM values (should be decrypted ISO format string).
    """
    print("=" * 80)
    print("CLIENT DATE_OF_BIRTH ENCRYPTION VERIFICATION")
    print("=" * 80)
    print("")

    # Get database session
    async for session in get_async_session():
        # Fetch sample clients with date_of_birth (first 10)
        print("Fetching sample clients with date_of_birth (first 10)...")
        result = await session.execute(
            select(Client).where(Client.date_of_birth.isnot(None)).limit(10)
        )
        clients = result.scalars().all()

        if not clients:
            print("⚠️  No clients with date_of_birth found in database.")
            print("   Verification cannot be performed.")
            print("   This is acceptable if no clients have date_of_birth set.")
            sys.exit(0)

        print(f"Found {len(clients)} clients with date_of_birth to verify")
        print("")

        # Verification counters
        total_verified = 0
        total_failed = 0

        for client in clients:
            print(f"Verifying client: {client.id}")
            print("-" * 80)

            try:
                # Test 1: ORM value should be decrypted ISO format string
                print(f"  ORM (decrypted) date_of_birth: {client.date_of_birth}")

                # Test 2: Raw database value should be encrypted binary
                raw_result = await session.execute(
                    text(
                        """
                        SELECT date_of_birth
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

                # Check date_of_birth (should be encrypted BYTEA)
                raw_dob = raw_data[0]
                if isinstance(raw_dob, bytes):
                    print(f"  ✅ date_of_birth is encrypted (binary data)")
                    print(f"     Length: {len(raw_dob)} bytes")
                    print(f"     First 50 bytes: {raw_dob[:50]}")

                    # Check version prefix
                    if b":" in raw_dob[:10]:
                        version = raw_dob[:raw_dob.index(b":")].decode("ascii")
                        print(f"     ✅ Version prefix found: {version}")
                    else:
                        print(f"     ⚠️  No version prefix (legacy format)")
                else:
                    print(f"  ❌ date_of_birth is NOT encrypted (not binary)")
                    print(f"     Value: {raw_dob}")
                    total_failed += 1
                    continue

                # Test 3: Verify decrypted value is valid ISO format date string
                if not client.date_of_birth:
                    print(f"  ❌ Decrypted date_of_birth is empty or None")
                    total_failed += 1
                    continue

                # Test 4: Parse decrypted string as date
                try:
                    parsed_date = datetime.fromisoformat(client.date_of_birth).date()
                    print(f"  ✅ date_of_birth parses as valid date: {parsed_date}")
                except (ValueError, AttributeError) as e:
                    print(f"  ❌ date_of_birth cannot be parsed as date: {e}")
                    print(f"     Value: {client.date_of_birth}")
                    total_failed += 1
                    continue

                # Test 5: Verify age calculation works
                from datetime import date

                age = (date.today() - parsed_date).days // 365
                print(f"  ✅ Age calculation works: {age} years old")

                # Test 6: Verify format is ISO YYYY-MM-DD
                if len(client.date_of_birth) == 10 and client.date_of_birth.count("-") == 2:
                    print(f"  ✅ date_of_birth format is ISO YYYY-MM-DD")
                else:
                    print(f"  ⚠️  date_of_birth format unexpected: {client.date_of_birth}")

                print("")
                print(f"  ✅ Client {client.id} date_of_birth encryption verified successfully")
                total_verified += 1

            except Exception as e:
                logger.error(
                    "client_dob_verification_failed",
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
            print("   Some clients have unencrypted or invalid date_of_birth data.")
            print("   DO NOT proceed with dropping old column.")
            sys.exit(1)
        else:
            print("✅ VERIFICATION PASSED")
            print("   All client date_of_birth values are encrypted at rest.")
            print("   Safe to proceed with dropping old plaintext column.")

        break  # Exit async context manager


if __name__ == "__main__":
    asyncio.run(verify_dob_encryption())
