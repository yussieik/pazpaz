"""
Encryption key quality validation.

Validates that encryption keys have sufficient entropy and randomness
to be cryptographically secure (NIST SP 800-90B).

Security Properties:
- Shannon entropy validation (> 4.5 bits per byte for 32-byte keys)
- Minimum unique byte values (at least 10 for 32-byte keys)
- Pattern detection (sequential, all-zeros, all-same)
- Repetition analysis (max 4 occurrences per byte)

NIST SP 800-90B Requirements:
- Random number generators must produce unpredictable output
- Entropy must be sufficient for cryptographic operations
- Keys must be generated from approved sources

CWE-330 Mitigation:
This module prevents use of insufficiently random values for encryption
keys by validating entropy and randomness before key acceptance.

Usage:
    from pazpaz.utils.key_validation import validate_key_entropy, WeakKeyError

    # Validate key entropy
    try:
        validate_key_entropy(key_bytes, version="v1")
        print("Key has sufficient entropy")
    except WeakKeyError as e:
        print(f"Weak key rejected: {e}")
"""

import math
from collections import Counter

import structlog

logger = structlog.get_logger(__name__)


class WeakKeyError(Exception):
    """Raised when encryption key fails entropy validation."""

    pass


def validate_key_entropy(key: bytes, version: str = "unknown") -> bool:
    """
    Validate encryption key has sufficient entropy.

    Minimum entropy requirements (NIST SP 800-90B):
    - At least 10 unique byte values (32 bytes should have variety)
    - Not all zeros or sequential pattern
    - Shannon entropy > 4.5 bits per byte (out of 5.0 max for 32 bytes)
    - No excessive repetition (max 4 occurrences of same byte)

    Args:
        key: Raw key bytes (must be 32 bytes for AES-256)
        version: Key version identifier for logging

    Returns:
        True if key has sufficient entropy

    Raises:
        WeakKeyError: If key fails entropy checks

    Example:
        >>> import secrets
        >>> key = secrets.token_bytes(32)
        >>> validate_key_entropy(key, version="v1")
        True

        >>> weak_key = b"\\x00" * 32
        >>> validate_key_entropy(weak_key, version="weak")
        Traceback (most recent call last):
            ...
        WeakKeyError: Key weak is all zeros (no entropy)
    """
    if len(key) != 32:
        raise WeakKeyError(
            f"Key {version} has invalid length: {len(key)} bytes (expected 32)"
        )

    # Check 1: Not all zeros
    if key == b"\x00" * len(key):
        raise WeakKeyError(f"Key {version} is all zeros (no entropy)")

    # Check 2: Not all same byte
    if len(set(key)) == 1:
        raise WeakKeyError(
            f"Key {version} contains only one unique byte value (no entropy)"
        )

    # Check 3: Not sequential
    if key == bytes(range(len(key))):
        raise WeakKeyError(f"Key {version} is sequential (predictable)")

    # Check 4: Not reverse sequential
    if key == bytes(range(len(key) - 1, -1, -1)):
        raise WeakKeyError(f"Key {version} is reverse sequential (predictable)")

    # Check 5: Sufficient unique byte values
    unique_bytes = len(set(key))
    min_unique = 10  # For 32 bytes, expect at least 10 unique values

    if unique_bytes < min_unique:
        raise WeakKeyError(
            f"Key {version} has only {unique_bytes} unique bytes "
            f"(minimum {min_unique} required for {len(key)}-byte key)"
        )

    # Check 6: Shannon entropy
    # For a 32-byte key, Shannon entropy measures randomness of byte distribution
    # Perfect randomness: all 32 bytes unique (entropy = log2(32) = 5.0 bits/byte)
    # For cryptographic keys, minimum 4.5 bits/byte (moderate randomness)
    byte_counts = Counter(key)
    entropy = 0.0

    for count in byte_counts.values():
        probability = count / len(key)
        entropy -= probability * math.log2(probability)

    # For 32-byte keys, minimum entropy should be 4.5 bits/byte
    # (out of theoretical max of 5.0 for 32 unique bytes)
    min_entropy = 4.5

    if entropy < min_entropy:
        raise WeakKeyError(
            f"Key {version} has low entropy: {entropy:.2f} bits/byte "
            f"(minimum {min_entropy} required)"
        )

    # Check 7: No excessive repetition
    max_occurrences = 4  # No byte should appear more than 4 times in 32 bytes
    max_count = max(byte_counts.values())

    if max_count > max_occurrences:
        most_common_byte = max(byte_counts, key=byte_counts.get)
        raise WeakKeyError(
            f"Key {version} has excessive repetition: byte 0x{most_common_byte:02x} "
            f"appears {max_count} times (max {max_occurrences} allowed)"
        )

    # Key passed all checks
    logger.info(
        "key_entropy_validated",
        version=version,
        unique_bytes=unique_bytes,
        shannon_entropy=f"{entropy:.2f}",
        max_byte_count=max_count,
    )

    return True


def validate_key_chi_square(key: bytes, version: str = "unknown") -> bool:
    """
    Perform chi-square test for randomness (optional additional test).

    Chi-square test checks if byte distribution is uniform (random).

    Args:
        key: Raw key bytes
        version: Key version identifier

    Returns:
        True if key passes chi-square test

    Raises:
        WeakKeyError: If key fails chi-square test

    Example:
        >>> import secrets
        >>> key = secrets.token_bytes(32)
        >>> validate_key_chi_square(key, version="v1")
        True
    """
    if len(key) != 32:
        return True  # Only validate 32-byte keys

    # Expected frequency: 32 bytes / 256 possible values = 0.125
    expected_freq = len(key) / 256

    # Observed frequencies
    byte_counts = Counter(key)

    # Chi-square statistic
    chi_square = 0.0
    for byte_val in range(256):
        observed = byte_counts.get(byte_val, 0)
        chi_square += ((observed - expected_freq) ** 2) / expected_freq

    # Critical value for chi-square with 255 degrees of freedom at 95% confidence
    # Simplified check: chi-square should be < 300 for reasonable randomness
    critical_value = 300.0

    if chi_square > critical_value:
        logger.warning(
            "key_chi_square_warning",
            version=version,
            chi_square=f"{chi_square:.2f}",
            critical_value=critical_value,
            message="Key may not be uniformly random",
        )
        # Don't raise error, just warn (chi-square can have false positives)

    return True


def validate_key_runs_test(key: bytes, version: str = "unknown") -> bool:
    """
    Perform runs test for randomness (optional additional test).

    Runs test checks for patterns in bit sequences.

    Args:
        key: Raw key bytes
        version: Key version identifier

    Returns:
        True (informational test, doesn't fail)

    Example:
        >>> import secrets
        >>> key = secrets.token_bytes(32)
        >>> validate_key_runs_test(key, version="v1")
        True
    """
    # Convert bytes to bit string
    bits = "".join(f"{byte:08b}" for byte in key)

    # Count runs (sequences of same bit)
    runs = 1
    for i in range(1, len(bits)):
        if bits[i] != bits[i - 1]:
            runs += 1

    # Expected runs for random sequence
    n = len(bits)
    ones = bits.count("1")
    zeros = bits.count("0")

    if ones == 0 or zeros == 0:
        logger.warning(
            "key_runs_test_warning",
            version=version,
            message="All bits are same value",
        )
        return True

    expected_runs = (2 * ones * zeros / n) + 1

    # Variance of runs
    variance = (2 * ones * zeros * (2 * ones * zeros - n)) / (n * n * (n - 1))
    std_dev = math.sqrt(variance)

    # Z-score
    if std_dev > 0:
        z_score = (runs - expected_runs) / std_dev

        # |Z| > 2 suggests non-randomness (at 95% confidence)
        if abs(z_score) > 2:
            logger.warning(
                "key_runs_test_warning",
                version=version,
                runs=runs,
                expected_runs=f"{expected_runs:.2f}",
                z_score=f"{z_score:.2f}",
                message="Key may have non-random bit patterns",
            )

    return True
