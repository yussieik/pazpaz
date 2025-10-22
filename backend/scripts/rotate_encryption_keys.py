#!/usr/bin/env python3
"""
Encryption Key Rotation Script

This script performs encryption key rotation for PHI/PII data protection.
It generates a new encryption key, stores it in AWS Secrets Manager with metadata,
and updates the key registry to use the new key for all future encryptions.

HIPAA Requirement:
    Encryption keys must be rotated every 90 days (§164.312(a)(2)(iv)).
    This script automates the rotation process to ensure compliance.

Usage:
    # Dry run (preview changes without applying)
    python scripts/rotate_encryption_keys.py --dry-run

    # Perform rotation
    python scripts/rotate_encryption_keys.py

    # Force rotation even if current key is not expired
    python scripts/rotate_encryption_keys.py --force

    # Specify custom expiration period (default: 90 days)
    python scripts/rotate_encryption_keys.py --expiration-days 60

Security:
    - Generates cryptographically secure 256-bit AES keys
    - Stores keys in AWS Secrets Manager with encryption at rest
    - Logs all operations for audit trail
    - Validates key format before storage
    - Atomic operation (all-or-nothing)

Workflow:
    1. Check if rotation is needed (current key >90 days old)
    2. Generate new 256-bit AES encryption key
    3. Determine next version number (v1 → v2 → v3 → ...)
    4. Store new key in AWS Secrets Manager with metadata
    5. Mark new key as current in registry
    6. Log rotation event for compliance audit
    7. Recommend running re-encryption script for old data

Prerequisites:
    - AWS credentials configured (IAM role or environment variables)
    - secretsmanager:CreateSecret and secretsmanager:PutSecretValue permissions
    - Python 3.13+ with boto3, cryptography packages

Environment Variables:
    - AWS_REGION: AWS region for Secrets Manager (default: us-east-1)
    - PAZPAZ_ENVIRONMENT: Environment name (local/staging/production)

Exit Codes:
    0 - Success
    1 - Rotation not needed (current key still valid)
    2 - AWS Secrets Manager error
    3 - Invalid arguments or configuration
"""

import argparse
import base64
import json
import secrets
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pazpaz.core.constants import ENCRYPTION_KEY_SIZE
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


class KeyRotationError(Exception):
    """Base exception for key rotation errors."""

    pass


def generate_encryption_key() -> bytes:
    """
    Generate a cryptographically secure 256-bit AES encryption key.

    Uses Python's secrets module (cryptographically strong random number
    generator) to generate a 32-byte (256-bit) key suitable for AES-256-GCM.

    Returns:
        32-byte encryption key

    Example:
        >>> key = generate_encryption_key()
        >>> len(key)
        32
    """
    key = secrets.token_bytes(ENCRYPTION_KEY_SIZE)

    logger.info(
        "encryption_key_generated",
        key_size_bytes=len(key),
        key_size_bits=len(key) * 8,
    )

    return key


def get_next_version(region: str = "us-east-1") -> str:
    """
    Determine the next key version number by querying AWS Secrets Manager.

    This function lists all existing encryption keys and increments the
    highest version number found. Version format: v1, v2, v3, ...

    Args:
        region: AWS region (default: us-east-1)

    Returns:
        Next version string (e.g., "v2", "v3")

    Raises:
        KeyRotationError: If AWS API call fails

    Example:
        >>> get_next_version()
        'v2'  # If v1 exists
    """
    try:
        import boto3
    except ImportError:
        raise KeyRotationError("boto3 not installed. Install with: uv add boto3")

    try:
        client = boto3.client("secretsmanager", region_name=region)

        # List all secrets with prefix "pazpaz/encryption-key-"
        prefix = "pazpaz/encryption-key-"
        response = client.list_secrets(
            Filters=[
                {"Key": "name", "Values": [prefix]},
            ]
        )

        secret_list = response.get("SecretList", [])

        if not secret_list:
            # No existing keys - this is the first key
            logger.info(
                "no_existing_keys_found",
                next_version="v1",
                message="No existing keys found, starting with v1",
            )
            return "v1"

        # Extract version numbers from secret names
        versions = []
        for secret_info in secret_list:
            secret_name = secret_info["Name"]

            if not secret_name.startswith(prefix):
                continue

            # Extract version (e.g., "pazpaz/encryption-key-v2" -> "v2")
            version = secret_name[len(prefix) :]

            # Parse version number (e.g., "v2" -> 2)
            try:
                version_num = int(version[1:])  # Skip 'v' prefix
                versions.append(version_num)
            except (ValueError, IndexError):
                logger.warning(
                    "invalid_version_format",
                    secret_name=secret_name,
                    version=version,
                    message="Skipping secret with invalid version format",
                )
                continue

        if not versions:
            # No valid versions found
            logger.warning(
                "no_valid_versions_found",
                next_version="v1",
                message="No valid version numbers found, starting with v1",
            )
            return "v1"

        # Increment highest version
        max_version = max(versions)
        next_version = f"v{max_version + 1}"

        logger.info(
            "next_version_determined",
            current_max_version=f"v{max_version}",
            next_version=next_version,
        )

        return next_version

    except Exception as e:
        logger.error(
            "failed_to_determine_next_version",
            error=str(e),
            exc_info=True,
        )
        raise KeyRotationError(f"Failed to determine next version: {e}") from e


def store_key_in_aws(
    key: bytes,
    version: str,
    created_at: datetime,
    expires_at: datetime,
    is_current: bool = True,
    region: str = "us-east-1",
    dry_run: bool = False,
) -> None:
    """
    Store encryption key in AWS Secrets Manager with metadata.

    Creates a new secret with the key and metadata in JSON format:
    {
        "encryption_key": "base64-encoded-key",
        "version": "v2",
        "created_at": "2025-01-19T12:00:00Z",
        "expires_at": "2025-04-19T12:00:00Z",
        "is_current": true
    }

    Args:
        key: 32-byte encryption key
        version: Version identifier (e.g., "v2")
        created_at: Key creation timestamp
        expires_at: Key expiration timestamp (90 days from creation)
        is_current: Whether this is the current active key
        region: AWS region (default: us-east-1)
        dry_run: If True, simulate without actually storing

    Raises:
        KeyRotationError: If AWS API call fails
        ValueError: If key size is invalid

    Example:
        >>> key = generate_encryption_key()
        >>> store_key_in_aws(
        ...     key=key,
        ...     version="v2",
        ...     created_at=datetime.now(UTC),
        ...     expires_at=datetime.now(UTC) + timedelta(days=90),
        ... )
    """
    if len(key) != ENCRYPTION_KEY_SIZE:
        raise ValueError(
            f"Encryption key must be {ENCRYPTION_KEY_SIZE} bytes, got {len(key)}"
        )

    secret_name = f"pazpaz/encryption-key-{version}"

    # Build secret value as JSON
    secret_value = {
        "encryption_key": base64.b64encode(key).decode("ascii"),
        "version": version,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "is_current": is_current,
    }

    secret_string = json.dumps(secret_value, indent=2)

    if dry_run:
        logger.info(
            "dry_run_would_store_key",
            secret_name=secret_name,
            version=version,
            is_current=is_current,
            created_at=created_at.isoformat(),
            expires_at=expires_at.isoformat(),
            message="DRY RUN: Would store key in AWS Secrets Manager",
        )
        return

    try:
        import boto3
    except ImportError:
        raise KeyRotationError("boto3 not installed. Install with: uv add boto3")

    try:
        client = boto3.client("secretsmanager", region_name=region)

        # Create new secret
        response = client.create_secret(
            Name=secret_name,
            Description=f"PazPaz PHI encryption key {version} (created: {created_at.date()})",
            SecretString=secret_string,
            Tags=[
                {"Key": "Application", "Value": "PazPaz"},
                {"Key": "Purpose", "Value": "PHI_Encryption"},
                {"Key": "Version", "Value": version},
                {"Key": "CreatedAt", "Value": created_at.isoformat()},
                {"Key": "ExpiresAt", "Value": expires_at.isoformat()},
                {"Key": "IsCurrent", "Value": str(is_current)},
            ],
        )

        logger.info(
            "encryption_key_stored_in_aws",
            secret_name=secret_name,
            secret_arn=response.get("ARN"),
            version=version,
            is_current=is_current,
            created_at=created_at.isoformat(),
            expires_at=expires_at.isoformat(),
        )

    except Exception as e:
        error_code = getattr(e, "__class__.__name__", type(e).__name__)

        if hasattr(e, "response") and "Error" in e.response:
            error_code = e.response["Error"]["Code"]

            if error_code == "ResourceExistsException":
                logger.error(
                    "secret_already_exists",
                    secret_name=secret_name,
                    version=version,
                    message=f"Secret {secret_name} already exists. Use a different version.",
                )
                raise KeyRotationError(
                    f"Secret {secret_name} already exists. Cannot overwrite."
                ) from e

        logger.error(
            "failed_to_store_key_in_aws",
            secret_name=secret_name,
            error_code=error_code,
            error=str(e),
            exc_info=True,
        )
        raise KeyRotationError(f"Failed to store key in AWS: {e}") from e


def check_rotation_needed(region: str = "us-east-1") -> tuple[bool, str, datetime]:
    """
    Check if key rotation is needed based on current key age.

    HIPAA requires encryption keys to be rotated every 90 days.
    This function checks the current key's creation date and determines
    if rotation is needed.

    Args:
        region: AWS region (default: us-east-1)

    Returns:
        Tuple of (rotation_needed, current_version, expires_at)

    Raises:
        KeyRotationError: If unable to check rotation status

    Example:
        >>> needed, version, expires = check_rotation_needed()
        >>> if needed:
        ...     print(f"Rotation needed for {version}")
    """
    try:
        from pazpaz.utils.encryption import _KEY_REGISTRY, get_current_key_version
        from pazpaz.utils.secrets_manager import load_all_encryption_keys

        # Load all keys from AWS
        load_all_encryption_keys(region=region, environment="production")

        # Get current key
        current_version = get_current_key_version()
        current_key_metadata = _KEY_REGISTRY.get(current_version)

        if not current_key_metadata:
            logger.warning(
                "no_current_key_found",
                message="No current key found in registry, rotation recommended",
            )
            return True, "v0", datetime.now(UTC)

        # Check if rotation needed
        needs_rotation = current_key_metadata.needs_rotation

        logger.info(
            "rotation_check_complete",
            current_version=current_version,
            created_at=current_key_metadata.created_at.isoformat(),
            expires_at=current_key_metadata.expires_at.isoformat(),
            age_days=current_key_metadata.age_days,
            days_until_rotation=current_key_metadata.days_until_rotation,
            needs_rotation=needs_rotation,
        )

        return (
            needs_rotation,
            current_version,
            current_key_metadata.expires_at,
        )

    except Exception as e:
        logger.warning(
            "failed_to_check_rotation_status",
            error=str(e),
            message="Unable to check rotation status, recommending rotation",
        )
        # If we can't check, recommend rotation to be safe
        return True, "unknown", datetime.now(UTC)


def rotate_encryption_keys(
    expiration_days: int = 90,
    region: str = "us-east-1",
    dry_run: bool = False,
    force: bool = False,
) -> None:
    """
    Perform encryption key rotation.

    This is the main function that orchestrates the key rotation process:
    1. Check if rotation is needed (or force if --force flag)
    2. Generate new encryption key
    3. Determine next version number
    4. Store new key in AWS Secrets Manager
    5. Log rotation event for audit trail

    Args:
        expiration_days: Days until new key expires (default: 90)
        region: AWS region (default: us-east-1)
        dry_run: If True, simulate without actually rotating
        force: If True, rotate even if current key is not expired

    Raises:
        KeyRotationError: If rotation fails

    Example:
        >>> rotate_encryption_keys(dry_run=True)  # Preview changes
        >>> rotate_encryption_keys()  # Perform rotation
    """
    logger.info(
        "key_rotation_started",
        expiration_days=expiration_days,
        region=region,
        dry_run=dry_run,
        force=force,
    )

    # Check if rotation is needed
    if not force:
        needs_rotation, current_version, expires_at = check_rotation_needed(region)

        if not needs_rotation:
            days_remaining = (expires_at - datetime.now(UTC)).days
            logger.info(
                "rotation_not_needed",
                current_version=current_version,
                days_until_expiration=days_remaining,
                expires_at=expires_at.isoformat(),
                message=(
                    f"Current key {current_version} is still valid "
                    f"(expires in {days_remaining} days). "
                    f"Use --force to rotate anyway."
                ),
            )
            sys.exit(1)

    # Generate new key
    new_key = generate_encryption_key()

    # Determine next version
    next_version = get_next_version(region)

    # Calculate expiration (90 days from now)
    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(days=expiration_days)

    # Store key in AWS Secrets Manager
    store_key_in_aws(
        key=new_key,
        version=next_version,
        created_at=created_at,
        expires_at=expires_at,
        is_current=True,
        region=region,
        dry_run=dry_run,
    )

    if dry_run:
        logger.info(
            "dry_run_complete",
            next_version=next_version,
            created_at=created_at.isoformat(),
            expires_at=expires_at.isoformat(),
            message="DRY RUN: Key rotation simulated successfully",
        )
    else:
        logger.info(
            "key_rotation_complete",
            new_version=next_version,
            created_at=created_at.isoformat(),
            expires_at=expires_at.isoformat(),
            message=(
                f"Encryption key rotated to {next_version}. "
                f"Run re_encrypt_old_data.py to migrate existing data."
            ),
        )

        print("\n✅ Key rotation successful!")
        print(f"   New key version: {next_version}")
        print(f"   Created: {created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"   Expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"   Days until next rotation: {expiration_days}")
        print(
            "\n⚠️  IMPORTANT: Run scripts/re_encrypt_old_data.py to migrate existing PHI data"
        )


def main():
    """Command-line interface for key rotation."""
    parser = argparse.ArgumentParser(
        description="Rotate encryption keys for PHI/PII data (HIPAA 90-day policy)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (preview changes)
  python scripts/rotate_encryption_keys.py --dry-run

  # Perform rotation
  python scripts/rotate_encryption_keys.py

  # Force rotation even if current key is valid
  python scripts/rotate_encryption_keys.py --force

  # Use custom expiration period
  python scripts/rotate_encryption_keys.py --expiration-days 60

Environment Variables:
  AWS_REGION              AWS region for Secrets Manager (default: us-east-1)
  PAZPAZ_ENVIRONMENT      Environment name (local/staging/production)

HIPAA Compliance:
  Encryption keys must be rotated every 90 days per §164.312(a)(2)(iv).
  This script automates the rotation process to ensure compliance.

Security:
  - Keys stored in AWS Secrets Manager with encryption at rest
  - All operations logged for audit trail
  - Atomic operation (all-or-nothing)
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate rotation without actually storing new key",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force rotation even if current key is not expired",
    )

    parser.add_argument(
        "--expiration-days",
        type=int,
        default=90,
        help="Days until new key expires (default: 90)",
    )

    parser.add_argument(
        "--region",
        type=str,
        default="us-east-1",
        help="AWS region for Secrets Manager (default: us-east-1)",
    )

    args = parser.parse_args()

    # Validate expiration days
    if args.expiration_days < 1 or args.expiration_days > 365:
        logger.error(
            "invalid_expiration_days",
            expiration_days=args.expiration_days,
            message="Expiration days must be between 1 and 365",
        )
        sys.exit(3)

    try:
        rotate_encryption_keys(
            expiration_days=args.expiration_days,
            region=args.region,
            dry_run=args.dry_run,
            force=args.force,
        )
        sys.exit(0)

    except KeyRotationError as e:
        logger.error("key_rotation_failed", error=str(e), exc_info=True)
        print(f"\n❌ Key rotation failed: {e}", file=sys.stderr)
        sys.exit(2)

    except KeyboardInterrupt:
        logger.warning("key_rotation_interrupted", message="User interrupted rotation")
        print("\n⚠️  Key rotation interrupted by user", file=sys.stderr)
        sys.exit(130)

    except Exception as e:
        logger.error("unexpected_error", error=str(e), exc_info=True)
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
