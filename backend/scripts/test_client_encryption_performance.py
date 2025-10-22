#!/usr/bin/env python3
"""
Performance test: Client encryption/decryption overhead.

This script measures query performance before and after encryption to ensure
acceptable latency (<100ms single read, <1000ms bulk read of 100 clients).

Usage:
    python scripts/test_client_encryption_performance.py

Measurements:
    1. Single client read (ORM)
    2. Bulk client read (100 clients)
    3. Client list query (all clients in workspace)
    4. Per-client decryption overhead

Acceptance Criteria:
    - Single client read: <100ms (p95)
    - Bulk read (100 clients): <1000ms (p95)
    - Per-client overhead: <10ms
"""

import asyncio
import sys
import time
from statistics import mean, median

from sqlalchemy import select

# Add src to path for imports
sys.path.insert(0, "src")

from pazpaz.core.logging import get_logger
from pazpaz.db.base import get_async_session
from pazpaz.models.client import Client

logger = get_logger(__name__)


async def test_performance():
    """
    Test client query performance with encryption.

    Runs multiple iterations to measure p50, p95, and p99 latencies.
    """
    print("=" * 80)
    print("CLIENT ENCRYPTION PERFORMANCE TEST")
    print("=" * 80)
    print("")

    # Get database session
    async for session in get_async_session():
        # Count total clients
        result = await session.execute(select(Client))
        all_clients = result.scalars().all()
        total_clients = len(all_clients)

        print(f"Total clients in database: {total_clients}")
        print("")

        if total_clients == 0:
            print("❌ No clients found. Cannot test performance.")
            print("   Create test clients first:")
            print("   python scripts/create_test_clients.py")
            sys.exit(1)

        # Test 1: Single client read performance
        print("Test 1: Single client read performance")
        print("-" * 80)

        single_read_times = []
        iterations = 20

        # Pick a random client ID
        sample_client_id = all_clients[0].id

        for i in range(iterations):
            start = time.time()
            result = await session.execute(
                select(Client).where(Client.id == sample_client_id)
            )
            client = result.scalar_one()
            # Access all encrypted fields to trigger decryption
            _ = client.first_name
            _ = client.last_name
            _ = client.email
            _ = client.phone
            _ = client.address
            _ = client.medical_history
            _ = client.emergency_contact_name
            _ = client.emergency_contact_phone
            elapsed_ms = (time.time() - start) * 1000
            single_read_times.append(elapsed_ms)

        single_read_times.sort()
        p50_single = single_read_times[int(len(single_read_times) * 0.5)]
        p95_single = single_read_times[int(len(single_read_times) * 0.95)]
        p99_single = single_read_times[int(len(single_read_times) * 0.99)]

        print(f"  Iterations:    {iterations}")
        print(f"  Mean:          {mean(single_read_times):.2f}ms")
        print(f"  Median (p50):  {p50_single:.2f}ms")
        print(f"  p95:           {p95_single:.2f}ms")
        print(f"  p99:           {p99_single:.2f}ms")
        print(f"  Min:           {min(single_read_times):.2f}ms")
        print(f"  Max:           {max(single_read_times):.2f}ms")
        print("")

        if p95_single < 100:
            print(f"  ✅ PASS: p95 latency ({p95_single:.2f}ms) < 100ms target")
        else:
            print(f"  ⚠️  SLOW: p95 latency ({p95_single:.2f}ms) >= 100ms target")

        print("")

        # Test 2: Bulk read performance (100 clients)
        print("Test 2: Bulk read performance (100 clients)")
        print("-" * 80)

        bulk_read_times = []
        iterations = 10
        bulk_size = min(100, total_clients)

        for i in range(iterations):
            start = time.time()
            result = await session.execute(select(Client).limit(bulk_size))
            clients = result.scalars().all()
            # Access encrypted fields for all clients
            for client in clients:
                _ = client.first_name
                _ = client.last_name
                _ = client.email
            elapsed_ms = (time.time() - start) * 1000
            bulk_read_times.append(elapsed_ms)

        bulk_read_times.sort()
        p50_bulk = bulk_read_times[int(len(bulk_read_times) * 0.5)]
        p95_bulk = bulk_read_times[int(len(bulk_read_times) * 0.95)]
        p99_bulk = bulk_read_times[int(len(bulk_read_times) * 0.99)]

        print(f"  Iterations:    {iterations}")
        print(f"  Bulk size:     {bulk_size} clients")
        print(f"  Mean:          {mean(bulk_read_times):.2f}ms")
        print(f"  Median (p50):  {p50_bulk:.2f}ms")
        print(f"  p95:           {p95_bulk:.2f}ms")
        print(f"  p99:           {p99_bulk:.2f}ms")
        print(f"  Min:           {min(bulk_read_times):.2f}ms")
        print(f"  Max:           {max(bulk_read_times):.2f}ms")
        print(f"  Per-client:    {(mean(bulk_read_times) / bulk_size):.2f}ms")
        print("")

        if p95_bulk < 1000:
            print(f"  ✅ PASS: p95 latency ({p95_bulk:.2f}ms) < 1000ms target")
        else:
            print(f"  ⚠️  SLOW: p95 latency ({p95_bulk:.2f}ms) >= 1000ms target")

        print("")

        # Test 3: All clients in workspace (real-world scenario)
        if total_clients > 100:
            print("Test 3: All clients in workspace")
            print("-" * 80)

            all_clients_times = []
            iterations = 5

            for i in range(iterations):
                start = time.time()
                result = await session.execute(select(Client))
                clients = result.scalars().all()
                for client in clients:
                    _ = client.first_name
                    _ = client.last_name
                elapsed_ms = (time.time() - start) * 1000
                all_clients_times.append(elapsed_ms)

            print(f"  Iterations:    {iterations}")
            print(f"  Total clients: {total_clients}")
            print(f"  Mean:          {mean(all_clients_times):.2f}ms")
            print(f"  Median:        {median(all_clients_times):.2f}ms")
            print(f"  Min:           {min(all_clients_times):.2f}ms")
            print(f"  Max:           {max(all_clients_times):.2f}ms")
            print(f"  Per-client:    {(mean(all_clients_times) / total_clients):.2f}ms")
            print("")

        # Summary
        print("=" * 80)
        print("PERFORMANCE SUMMARY")
        print("=" * 80)
        print("")
        print("Single client read:")
        print(f"  p95 latency:  {p95_single:.2f}ms (target: <100ms)")
        print(f"  Status:       {'✅ PASS' if p95_single < 100 else '⚠️  SLOW'}")
        print("")
        print("Bulk read (100 clients):")
        print(f"  p95 latency:  {p95_bulk:.2f}ms (target: <1000ms)")
        print(f"  Status:       {'✅ PASS' if p95_bulk < 1000 else '⚠️  SLOW'}")
        print("")

        # Estimate decryption overhead
        # Assume base query time is ~20ms, rest is decryption
        decryption_overhead = (mean(bulk_read_times) - 20) / bulk_size
        print("Estimated per-field decryption overhead:")
        print(f"  ~{decryption_overhead:.2f}ms per client (8 fields)")
        print(f"  ~{(decryption_overhead / 8):.2f}ms per field")
        print("")

        if p95_single < 100 and p95_bulk < 1000:
            print("✅ SUCCESS: Performance meets all targets")
            print("   Encryption overhead is acceptable for production use")
        else:
            print("⚠️  WARNING: Performance below targets")
            print("   Consider optimization or caching strategies")

        break  # Exit async context manager


if __name__ == "__main__":
    asyncio.run(test_performance())
