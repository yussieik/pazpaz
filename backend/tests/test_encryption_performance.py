"""Performance benchmarks for PHI encryption (Day 4 - Database Encryption Implementation).

This test suite validates that encryption overhead meets the <10ms per field target
required for HIPAA-compliant PHI storage in PazPaz.

Test Scenarios:
1. Application-level encryption (Python cryptography - AES-256-GCM) - PRIMARY
2. Database-level encryption (pgcrypto - AES-256-CBC) - BACKUP/OPTIONAL
3. Bulk operations (100 fields) to simulate calendar view queries
4. Various field sizes (typical SOAP note sizes)

Performance Targets:
- Single field encryption: <5ms per field
- Single field decryption: <10ms per field
- Bulk decryption (100 fields): <100ms total (<1ms per field)
- Overall API latency with encryption: <150ms p95 (existing target)

Context:
- Day 3: Encryption architecture designed (application-level AES-256-GCM primary)
- Day 4: Performance validation before Week 2 SOAP Notes implementation
- Week 2: Application-level encryption will be used in production

Usage:
    pytest tests/test_encryption_performance.py -v --benchmark-only
    pytest tests/test_encryption_performance.py::test_application_encryption_1kb -v
"""

import base64
import secrets
import time

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


# Test data fixtures (typical PHI field sizes)
SMALL_FIELD = "Patient reports mild pain in lower back."  # ~50 bytes
MEDIUM_FIELD = """Subjective: Patient reports chronic lower back pain (8/10), worsening over past 2 weeks.
Pain radiates to right leg. Sleep disturbed. No numbness/tingling.
Objective: Reduced ROM in lumbar spine. Tenderness L4-L5. Straight leg raise negative.
Assessment: Acute exacerbation of chronic lumbar strain.
Plan: Continue PT 2x/week, NSAIDs as needed, reassess in 1 week."""  # ~350 bytes (typical SOAP note)
LARGE_FIELD = MEDIUM_FIELD * 3  # ~1KB (large clinical note)
EXTRA_LARGE_FIELD = MEDIUM_FIELD * 15  # ~5KB (comprehensive treatment plan)


class TestApplicationLevelEncryption:
    """Test Python cryptography library (AES-256-GCM) - PRIMARY encryption approach."""

    def setup_method(self):
        """Initialize encryption key and cipher."""
        # Generate 32-byte key (256 bits for AES-256)
        self.encryption_key = secrets.token_bytes(32)
        self.aesgcm = AESGCM(self.encryption_key)

    def encrypt(self, plaintext: str, key_version: str = "v1") -> str:
        """
        Encrypt plaintext using AES-256-GCM (authenticated encryption).

        Format: version:nonce_b64:ciphertext_b64
        Example: v1:abc123...:def456...

        This matches the production encryption implementation.
        """
        # Generate unique 96-bit nonce (NIST recommended for AES-GCM)
        nonce = secrets.token_bytes(12)

        # Encrypt with authenticated encryption (prevents tampering)
        ciphertext_bytes = self.aesgcm.encrypt(
            nonce, plaintext.encode("utf-8"), associated_data=None
        )

        # Encode nonce and ciphertext as Base64
        nonce_b64 = base64.b64encode(nonce).decode("ascii")
        ciphertext_b64 = base64.b64encode(ciphertext_bytes).decode("ascii")

        # Return version-prefixed format (supports key rotation)
        return f"{key_version}:{nonce_b64}:{ciphertext_b64}"

    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt ciphertext using AES-256-GCM.

        Parses version-prefixed format and verifies authenticity.
        """
        # Parse version, nonce, and ciphertext
        parts = encrypted.split(":")
        if len(parts) != 3:
            raise ValueError(
                f"Invalid encrypted format (expected 3 parts, got {len(parts)})"
            )

        key_version, nonce_b64, ciphertext_b64 = parts

        # Decode from Base64
        nonce = base64.b64decode(nonce_b64)
        ciphertext_bytes = base64.b64decode(ciphertext_b64)

        # Decrypt and verify authenticity
        plaintext_bytes = self.aesgcm.decrypt(
            nonce, ciphertext_bytes, associated_data=None
        )

        return plaintext_bytes.decode("utf-8")

    def test_application_encryption_50b(self):
        """Benchmark: Encrypt 50-byte field (small PHI field)."""
        iterations = 1000
        plaintexts = [SMALL_FIELD for _ in range(iterations)]

        start = time.perf_counter()
        for plaintext in plaintexts:
            _ = self.encrypt(plaintext)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        logger.info(
            "encryption_benchmark",
            test="app_encrypt_50b",
            iterations=iterations,
            total_seconds=elapsed,
            avg_ms_per_field=avg_ms,
            target_ms=5,
            passed=avg_ms < 5,
        )

        assert avg_ms < 5, f"Encryption too slow: {avg_ms:.2f}ms (target: <5ms)"

    def test_application_encryption_1kb(self):
        """Benchmark: Encrypt 1KB field (typical SOAP note)."""
        iterations = 1000
        plaintexts = [LARGE_FIELD for _ in range(iterations)]

        start = time.perf_counter()
        for plaintext in plaintexts:
            _ = self.encrypt(plaintext)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        logger.info(
            "encryption_benchmark",
            test="app_encrypt_1kb",
            iterations=iterations,
            total_seconds=elapsed,
            avg_ms_per_field=avg_ms,
            target_ms=5,
            passed=avg_ms < 5,
        )

        assert avg_ms < 5, f"Encryption too slow: {avg_ms:.2f}ms (target: <5ms)"

    def test_application_encryption_5kb(self):
        """Benchmark: Encrypt 5KB field (large clinical note)."""
        iterations = 1000
        plaintexts = [EXTRA_LARGE_FIELD for _ in range(iterations)]

        start = time.perf_counter()
        for plaintext in plaintexts:
            _ = self.encrypt(plaintext)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        logger.info(
            "encryption_benchmark",
            test="app_encrypt_5kb",
            iterations=iterations,
            total_seconds=elapsed,
            avg_ms_per_field=avg_ms,
            target_ms=10,
            passed=avg_ms < 10,
        )

        # Relax target for large fields (5KB is uncommon)
        assert avg_ms < 10, (
            f"Encryption too slow: {avg_ms:.2f}ms (target: <10ms for 5KB)"
        )

    def test_application_decryption_50b(self):
        """Benchmark: Decrypt 50-byte field (small PHI field)."""
        iterations = 1000
        encrypted_fields = [self.encrypt(SMALL_FIELD) for _ in range(iterations)]

        start = time.perf_counter()
        for encrypted in encrypted_fields:
            _ = self.decrypt(encrypted)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        logger.info(
            "decryption_benchmark",
            test="app_decrypt_50b",
            iterations=iterations,
            total_seconds=elapsed,
            avg_ms_per_field=avg_ms,
            target_ms=10,
            passed=avg_ms < 10,
        )

        assert avg_ms < 10, f"Decryption too slow: {avg_ms:.2f}ms (target: <10ms)"

    def test_application_decryption_1kb(self):
        """Benchmark: Decrypt 1KB field (typical SOAP note)."""
        iterations = 1000
        encrypted_fields = [self.encrypt(LARGE_FIELD) for _ in range(iterations)]

        start = time.perf_counter()
        for encrypted in encrypted_fields:
            _ = self.decrypt(encrypted)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        logger.info(
            "decryption_benchmark",
            test="app_decrypt_1kb",
            iterations=iterations,
            total_seconds=elapsed,
            avg_ms_per_field=avg_ms,
            target_ms=10,
            passed=avg_ms < 10,
        )

        assert avg_ms < 10, f"Decryption too slow: {avg_ms:.2f}ms (target: <10ms)"

    def test_application_bulk_decryption_100_fields(self):
        """Benchmark: Decrypt 100 fields (calendar view scenario)."""
        num_fields = 100
        encrypted_fields = [self.encrypt(MEDIUM_FIELD) for _ in range(num_fields)]

        start = time.perf_counter()
        for encrypted in encrypted_fields:
            _ = self.decrypt(encrypted)
        elapsed = time.perf_counter() - start

        total_ms = elapsed * 1000
        avg_ms = total_ms / num_fields

        logger.info(
            "bulk_decryption_benchmark",
            test="app_bulk_decrypt_100_fields",
            num_fields=num_fields,
            total_ms=total_ms,
            avg_ms_per_field=avg_ms,
            target_total_ms=100,
            passed=total_ms < 100,
        )

        assert total_ms < 100, (
            f"Bulk decryption too slow: {total_ms:.2f}ms (target: <100ms)"
        )

    def test_encryption_correctness(self):
        """Verify encryption round-trip preserves data."""
        test_cases = [
            SMALL_FIELD,
            MEDIUM_FIELD,
            LARGE_FIELD,
            "Unicode: 你好世界 🔒",  # Test Unicode handling
            "",  # Empty string edge case
        ]

        for plaintext in test_cases:
            encrypted = self.encrypt(plaintext)
            decrypted = self.decrypt(encrypted)
            assert decrypted == plaintext, f"Round-trip failed for: {plaintext[:50]}..."

            # Verify format
            assert encrypted.startswith("v1:"), "Missing version prefix"
            parts = encrypted.split(":")
            assert len(parts) == 3, (
                f"Invalid format (expected 3 parts, got {len(parts)})"
            )


class TestDatabaseLevelEncryption:
    """Test pgcrypto (AES-256-CBC) - BACKUP/OPTIONAL encryption approach."""

    @pytest.mark.asyncio
    async def test_pgcrypto_encryption_50b(self, db_session: AsyncSession):
        """Benchmark: pgcrypto encrypt 50-byte field."""
        iterations = 100  # Fewer iterations (database round-trip overhead)
        encryption_key = "my-test-encryption-key-32bytes!"

        # Warm-up query
        await db_session.execute(
            text("SELECT encrypt_phi_pgcrypto(:plaintext, :key, 'v1')"),
            {"plaintext": SMALL_FIELD, "key": encryption_key},
        )

        start = time.perf_counter()
        for _ in range(iterations):
            result = await db_session.execute(
                text("SELECT encrypt_phi_pgcrypto(:plaintext, :key, 'v1')"),
                {"plaintext": SMALL_FIELD, "key": encryption_key},
            )
            _ = result.scalar()
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        logger.info(
            "encryption_benchmark",
            test="pgcrypto_encrypt_50b",
            iterations=iterations,
            total_seconds=elapsed,
            avg_ms_per_field=avg_ms,
            note="Database round-trip overhead included",
        )

        # pgcrypto will be slower due to database round-trip (acceptable for backup use)
        assert avg_ms < 50, f"pgcrypto encryption too slow: {avg_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_pgcrypto_encryption_1kb(self, db_session: AsyncSession):
        """Benchmark: pgcrypto encrypt 1KB field."""
        iterations = 100
        encryption_key = "my-test-encryption-key-32bytes!"

        start = time.perf_counter()
        for _ in range(iterations):
            result = await db_session.execute(
                text("SELECT encrypt_phi_pgcrypto(:plaintext, :key, 'v1')"),
                {"plaintext": LARGE_FIELD, "key": encryption_key},
            )
            _ = result.scalar()
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        logger.info(
            "encryption_benchmark",
            test="pgcrypto_encrypt_1kb",
            iterations=iterations,
            total_seconds=elapsed,
            avg_ms_per_field=avg_ms,
            note="Database round-trip overhead included",
        )

        assert avg_ms < 50, f"pgcrypto encryption too slow: {avg_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_pgcrypto_decryption_1kb(self, db_session: AsyncSession):
        """Benchmark: pgcrypto decrypt 1KB field."""
        iterations = 100
        encryption_key = "my-test-encryption-key-32bytes!"

        # Pre-encrypt data
        result = await db_session.execute(
            text("SELECT encrypt_phi_pgcrypto(:plaintext, :key, 'v1')"),
            {"plaintext": LARGE_FIELD, "key": encryption_key},
        )
        encrypted_data = result.scalar()

        start = time.perf_counter()
        for _ in range(iterations):
            result = await db_session.execute(
                text("SELECT decrypt_phi_pgcrypto(:ciphertext, :key)"),
                {"ciphertext": encrypted_data, "key": encryption_key},
            )
            _ = result.scalar()
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        logger.info(
            "decryption_benchmark",
            test="pgcrypto_decrypt_1kb",
            iterations=iterations,
            total_seconds=elapsed,
            avg_ms_per_field=avg_ms,
            note="Database round-trip overhead included",
        )

        assert avg_ms < 50, f"pgcrypto decryption too slow: {avg_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_pgcrypto_correctness(self, db_session: AsyncSession):
        """Verify pgcrypto encryption round-trip preserves data."""
        encryption_key = "my-test-encryption-key-32bytes!"
        test_cases = [
            SMALL_FIELD,
            MEDIUM_FIELD,
            LARGE_FIELD,
        ]

        for plaintext in test_cases:
            # Encrypt
            result = await db_session.execute(
                text("SELECT encrypt_phi_pgcrypto(:plaintext, :key, 'v1')"),
                {"plaintext": plaintext, "key": encryption_key},
            )
            encrypted = result.scalar()

            # Decrypt
            result = await db_session.execute(
                text("SELECT decrypt_phi_pgcrypto(:ciphertext, :key)"),
                {"ciphertext": encrypted, "key": encryption_key},
            )
            decrypted = result.scalar()

            assert decrypted == plaintext, (
                f"pgcrypto round-trip failed for: {plaintext[:50]}..."
            )

            # Verify format
            assert encrypted.startswith("v1:"), "Missing version prefix"


class TestEncryptionComparison:
    """Compare application-level vs database-level encryption performance."""

    def setup_method(self):
        """Initialize both encryption approaches."""
        self.encryption_key = secrets.token_bytes(32)
        self.aesgcm = AESGCM(self.encryption_key)

    def encrypt_app(self, plaintext: str) -> str:
        """Application-level encryption (AES-256-GCM)."""
        nonce = secrets.token_bytes(12)
        ciphertext_bytes = self.aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        nonce_b64 = base64.b64encode(nonce).decode("ascii")
        ciphertext_b64 = base64.b64encode(ciphertext_bytes).decode("ascii")
        return f"v1:{nonce_b64}:{ciphertext_b64}"

    def test_comparison_summary(self):
        """Generate comparison summary for documentation."""
        iterations = 1000

        # Application-level encryption (1KB)
        start = time.perf_counter()
        for _ in range(iterations):
            _ = self.encrypt_app(LARGE_FIELD)
        app_encrypt_ms = (time.perf_counter() - start) / iterations * 1000

        # Log summary
        summary = {
            "application_level": {
                "algorithm": "AES-256-GCM",
                "library": "Python cryptography",
                "encrypt_1kb_avg_ms": round(app_encrypt_ms, 2),
                "recommendation": "PRIMARY - Use for production",
                "pros": [
                    "Fastest (<5ms per field)",
                    "External key management (AWS Secrets Manager)",
                    "Authenticated encryption (tamper detection)",
                    "Easy key rotation (version prefix)",
                ],
            },
            "database_level": {
                "algorithm": "AES-256-CBC",
                "library": "PostgreSQL pgcrypto",
                "encrypt_1kb_avg_ms": "~20-30ms (includes DB round-trip)",
                "recommendation": "BACKUP/OPTIONAL - For verification scenarios",
                "pros": [
                    "Defense in depth",
                    "Database-level verification",
                    "Backup option for hybrid scenarios",
                ],
            },
            "performance_targets": {
                "single_field_encrypt": "<5ms",
                "single_field_decrypt": "<10ms",
                "bulk_100_fields": "<100ms total",
                "api_latency_p95": "<150ms (with encryption overhead)",
            },
        }

        logger.info("encryption_comparison_summary", summary=summary)

        # Verify application-level meets target
        assert app_encrypt_ms < 5, (
            f"Application encryption too slow: {app_encrypt_ms:.2f}ms"
        )


# Test execution summary
if __name__ == "__main__":
    print("Performance Benchmark Suite - Day 4 Database Encryption Implementation")
    print("=" * 80)
    print("\nTest Coverage:")
    print("1. Application-level encryption (Python cryptography - AES-256-GCM)")
    print("2. Database-level encryption (pgcrypto - AES-256-CBC)")
    print("3. Bulk operations (100 fields)")
    print("4. Field sizes: 50B, 1KB, 5KB")
    print("\nRun with: pytest tests/test_encryption_performance.py -v")
    print("=" * 80)
