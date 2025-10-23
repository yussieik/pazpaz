"""
AWS Secrets Manager integration for secure key management.

This module provides secure encryption key management using AWS Secrets Manager
with graceful fallback to environment variables for local development.

Key Features:
- AWS Secrets Manager integration for production key storage
- Multi-version key support for 90-day rotation (HIPAA requirement)
- Automatic fallback to environment variables if AWS is unavailable
- @lru_cache for performance (avoid repeated AWS API calls)
- Comprehensive error handling and logging
- Support for IAM role-based authentication

Key Versioning Architecture:
- Multiple key versions stored in AWS Secrets Manager (v1, v2, v3, ...)
- Each key has metadata: version, created_at, expires_at (90 days)
- Keys fetched dynamically based on version
- Old keys retained for decryption of historical data
- HIPAA compliance: 90-day key rotation policy

Security Model:
--------------
PRODUCTION/STAGING:
    - MUST use AWS Secrets Manager (fail-closed)
    - Environment variable fallback is DISABLED
    - Ensures HIPAA §164.312(b) compliance (audit trail via CloudTrail)
    - Centralized key management with IAM access controls

LOCAL/DEVELOPMENT:
    - Can use environment variable (ENCRYPTION_MASTER_KEY in .env)
    - Can use AWS Secrets Manager (for testing AWS integration)
    - Falls back to temporary key generation with warning
    - Fail-open for developer experience

HIPAA Compliance:
----------------
§164.312(a)(2)(iv) - Encryption and Decryption
    - Production keys stored in AWS Secrets Manager
    - Access logged via CloudTrail
    - IAM policies control key access

§164.312(b) - Audit Controls
    - All key access logged to CloudTrail
    - Audit trail includes: who, when, from where

Security Considerations:
- Uses IAM roles for authentication (no hardcoded credentials)
- Logs all key access events for audit trail (CloudTrail)
- Production enforces AWS Secrets Manager (fail-closed)
- Key fetching is cached to minimize AWS API calls (performance)

Usage:
    from pazpaz.utils.secrets_manager import get_encryption_key, load_all_encryption_keys

    # Get current encryption key (single key, backward compatible)
    key = get_encryption_key()  # Returns 32-byte AES-256 key

    # Load all key versions for multi-version decryption (key rotation)
    load_all_encryption_keys()  # Loads v1, v2, v3, ... into key registry

    # Get specific key version
    key_v2 = get_encryption_key_version("v2")

Performance:
- First call: 50-200ms (AWS Secrets Manager API call)
- Subsequent calls: <1ms (cached via @lru_cache)

For production deployment, see:
- docs/backend/database/AWS_SECRETS_MANAGER_DB_CREDENTIALS.md
- docs/security/encryption/KEY_ROTATION_PROCEDURE.md (to be created)
"""

import base64
import json
import os
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from pazpaz.core.constants import ENCRYPTION_KEY_SIZE
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


class SecretsManagerError(Exception):
    """Base exception for AWS Secrets Manager operations."""

    pass


class KeyNotFoundError(SecretsManagerError):
    """Raised when encryption key is not found in any source."""

    pass


@lru_cache(maxsize=1)
def _get_boto3_client(region: str):
    """
    Get AWS Secrets Manager client (cached).

    This function is cached to reuse the boto3 client across multiple calls,
    avoiding the overhead of creating new clients.

    Args:
        region: AWS region (e.g., "us-east-1")

    Returns:
        boto3 Secrets Manager client

    Raises:
        ImportError: If boto3 is not installed
    """
    try:
        import boto3
    except ImportError:
        raise ImportError("boto3 not installed. Install with: uv add boto3") from None

    # In production, IAM role credentials are used automatically
    # In development, you can set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
    return boto3.client("secretsmanager", region_name=region)


def _fetch_secret_from_aws(
    secret_name: str, region: str, environment: str
) -> dict | None:
    """
    Fetch a secret from AWS Secrets Manager.

    Args:
        secret_name: Name/ARN of the secret in AWS Secrets Manager
        region: AWS region
        environment: Current environment (for logging)

    Returns:
        Secret value as dictionary (parsed JSON) or None if fallback needed

    Raises:
        SecretsManagerError: If AWS error occurs and no fallback available
    """
    try:
        client = _get_boto3_client(region)
        response = client.get_secret_value(SecretId=secret_name)

        # Log successful key access for audit trail
        logger.info(
            "encryption_key_fetched_from_aws",
            secret_id=secret_name,
            version_id=response.get("VersionId"),
            environment=environment,
        )

        # Parse secret JSON
        if "SecretString" in response:
            secret_value = response["SecretString"]

            # Handle both plain base64 string and JSON format
            try:
                # Try parsing as JSON first (versioned format)
                return json.loads(secret_value)
            except json.JSONDecodeError:
                # Plain base64 string (legacy format)
                return {"encryption_key": secret_value}
        else:
            # Binary secrets not supported for encryption keys
            logger.error(
                "secret_is_binary_not_supported",
                secret_id=secret_name,
            )
            raise SecretsManagerError(
                f"Secret {secret_name} is binary (expected JSON string)"
            )

    except Exception as e:
        error_code = getattr(e, "__class__.__name__", type(e).__name__)

        # Handle specific AWS errors
        if hasattr(e, "response") and "Error" in e.response:
            error_code = e.response["Error"]["Code"]

            if error_code == "ResourceNotFoundException":
                logger.warning(
                    "secret_not_found_in_aws",
                    secret_id=secret_name,
                    message=(
                        "Secret not found, will attempt fallback "
                        "to environment variable"
                    ),
                )
            elif error_code == "AccessDeniedException":
                logger.warning(
                    "secret_access_denied",
                    secret_id=secret_name,
                    message=(
                        "Access denied to secret, will attempt fallback "
                        "to environment variable"
                    ),
                )
            elif error_code == "InvalidRequestException":
                logger.warning(
                    "invalid_secret_request",
                    secret_id=secret_name,
                    error=str(e),
                )
            else:
                logger.warning(
                    "aws_secrets_manager_error",
                    secret_id=secret_name,
                    error_code=error_code,
                    error=str(e),
                )
        else:
            # Non-AWS error (e.g., network, boto3 not installed)
            logger.warning(
                "failed_to_fetch_secret",
                secret_id=secret_name,
                error_type=error_code,
                error=str(e),
            )

        # Return None to trigger fallback
        return None


def _get_key_from_env() -> bytes | None:
    """
    Get encryption key from environment variable (fallback).

    Returns:
        32-byte encryption key or None if not found

    Raises:
        ValueError: If key format is invalid
    """
    # Try to load from environment first
    key_b64 = os.getenv("ENCRYPTION_MASTER_KEY")

    # If not in environment, try loading from .env file
    if not key_b64:
        try:
            from dotenv import load_dotenv

            load_dotenv()
            key_b64 = os.getenv("ENCRYPTION_MASTER_KEY")
        except ImportError:
            # python-dotenv not installed, skip
            pass

    if not key_b64:
        return None

    try:
        key = base64.b64decode(key_b64)

        if len(key) != ENCRYPTION_KEY_SIZE:
            raise ValueError(
                f"Encryption key from environment must be {ENCRYPTION_KEY_SIZE} bytes, "
                f"got {len(key)} bytes"
            )

        logger.info(
            "encryption_key_loaded_from_env",
            message="Using ENCRYPTION_MASTER_KEY environment variable",
        )

        return key

    except Exception as e:
        logger.error(
            "invalid_encryption_key_in_env",
            error=str(e),
            message="ENCRYPTION_MASTER_KEY environment variable is not valid base64",
        )
        raise ValueError(f"Invalid ENCRYPTION_MASTER_KEY format: {e}") from e


@lru_cache(maxsize=1)
def get_encryption_key(
    secret_name: str = "pazpaz/encryption-key-v1",
    region: str = "us-east-1",
    environment: str = "local",
) -> bytes:
    """
    Get encryption key from AWS Secrets Manager or environment variable.

    Security Model:
    - Production/Staging: MUST use AWS Secrets Manager (fail-closed)
    - Local/Development: Can use environment variable (fail-open for dev speed)

    The result is cached via @lru_cache to avoid repeated AWS API calls.

    Args:
        secret_name: AWS Secrets Manager secret name (default: pazpaz/encryption-key-v1)
        region: AWS region (default: us-east-1)
        environment: Current environment (local/development/staging/production)

    Returns:
        32-byte encryption key for AES-256-GCM

    Raises:
        KeyNotFoundError: If key not found in required source
        ValueError: If key format is invalid

    Example:
        >>> from pazpaz.utils.secrets_manager import get_encryption_key
        >>> key = get_encryption_key()
        >>> len(key)
        32
    """
    # PRODUCTION/STAGING: Enforce AWS Secrets Manager (fail-closed)
    if environment in ("production", "staging"):
        logger.info(
            "enforcing_aws_secrets_manager",
            environment=environment,
            secret_name=secret_name,
            fallback_disabled=True,
        )

        secret = _fetch_secret_from_aws(secret_name, region, environment)

        if not secret or "encryption_key" not in secret:
            # FAIL CLOSED: No fallback in production
            raise KeyNotFoundError(
                f"Encryption key not found in AWS Secrets Manager: {secret_name}. "
                f"Environment variable fallback is DISABLED in {environment} for HIPAA compliance. "
                f"Ensure AWS Secrets Manager secret exists and IAM permissions are configured correctly."
            )

        key_b64 = secret["encryption_key"]
        key = base64.b64decode(key_b64)

        if len(key) != ENCRYPTION_KEY_SIZE:
            raise ValueError(
                f"Encryption key from AWS must be {ENCRYPTION_KEY_SIZE} bytes, "
                f"got {len(key)} bytes. Check secret format in AWS Secrets Manager."
            )

        logger.info(
            "encryption_key_loaded_from_aws",
            secret_id=secret_name,
            environment=environment,
            key_length=len(key),
            fallback_disabled=True,
        )

        return key

    # LOCAL/DEVELOPMENT: Try environment variable first (faster development)
    logger.info("attempting_local_key_load", environment=environment)

    env_key = _get_key_from_env()
    if env_key:
        logger.info("encryption_key_loaded_from_env", environment=environment)
        return env_key

    # Local dev can also use AWS for testing AWS integration
    logger.info("no_env_key_trying_aws", environment=environment)
    secret = _fetch_secret_from_aws(secret_name, region, environment)

    if secret and "encryption_key" in secret:
        key_b64 = secret["encryption_key"]
        key = base64.b64decode(key_b64)

        if len(key) != ENCRYPTION_KEY_SIZE:
            raise ValueError(f"Encryption key must be {ENCRYPTION_KEY_SIZE} bytes")

        logger.info("encryption_key_loaded_from_aws_in_dev", environment=environment)
        return key

    # LOCAL ONLY: Final fallback - generate temporary key with warning
    if environment == "local":
        logger.warning(
            "generating_temporary_encryption_key",
            message="No encryption key found. Generating temporary key for development. "
            "THIS KEY WILL NOT PERSIST. Set ENCRYPTION_MASTER_KEY in .env or use AWS.",
        )
        import secrets

        temp_key = secrets.token_bytes(ENCRYPTION_KEY_SIZE)
        return temp_key

    # If we get here in non-local, fail
    raise KeyNotFoundError(
        f"No encryption key found in environment={environment}. "
        f"Configure ENCRYPTION_MASTER_KEY or AWS Secrets Manager."
    )


def get_encryption_key_from_settings() -> bytes:
    """
    Get encryption key using settings from config.

    This is a convenience wrapper that reads configuration from
    pazpaz.core.config.Settings and calls get_encryption_key().

    Returns:
        32-byte encryption key

    Raises:
        KeyNotFoundError: If key not found
        ValueError: If key format is invalid
    """
    from pazpaz.core.config import settings

    return get_encryption_key(
        secret_name=settings.secrets_manager_key_name,
        region=settings.aws_region,
        environment=settings.environment,
    )


@lru_cache(maxsize=1)
def get_database_credentials(
    secret_name: str = "pazpaz/database-credentials",
    region: str = "us-east-1",
    environment: str = "local",
) -> str:
    """
    Get database connection URL from AWS Secrets Manager or environment variable.

    This function implements a fallback strategy:
    1. Try AWS Secrets Manager (production/staging)
    2. Fall back to DATABASE_URL environment variable
    3. Raise KeyNotFoundError if both fail

    The result is cached via @lru_cache to avoid repeated AWS API calls.

    Args:
        secret_name: AWS Secrets Manager secret name
            (default: pazpaz/database-credentials)
        region: AWS region (default: us-east-1)
        environment: Current environment (local/staging/production)

    Returns:
        PostgreSQL connection URL with SSL parameters

    Raises:
        KeyNotFoundError: If credentials not found in AWS or environment
        ValueError: If credentials format is invalid

    Example:
        >>> from pazpaz.utils.secrets_manager import get_database_credentials
        >>> db_url = get_database_credentials()
        >>> "postgresql+asyncpg://" in db_url
        True

    AWS Secret Format (JSON):
        {
            "username": "pazpaz",
            "password": "GENERATED_STRONG_PASSWORD",
            "host": "prod-db.internal",
            "port": 5432,
            "database": "pazpaz",
            "ssl_cert_path": "/etc/ssl/certs/rds-ca-2019-root.pem"
        }
    """
    # Local development: Try environment variable first (faster)
    if environment == "local":
        env_url = os.getenv("DATABASE_URL")

        # If not in environment, try loading from .env file
        if not env_url:
            try:
                from dotenv import load_dotenv

                load_dotenv()
                env_url = os.getenv("DATABASE_URL")
            except ImportError:
                # python-dotenv not installed, skip
                pass

        if env_url:
            logger.info(
                "database_url_loaded_from_env",
                message="Using DATABASE_URL environment variable",
            )
            return env_url

        # Local dev can also use AWS for testing
        logger.info(
            "no_env_db_url_trying_aws",
            message="DATABASE_URL not set, trying AWS Secrets Manager",
        )

    # Production/Staging: Try AWS Secrets Manager first
    secret = _fetch_secret_from_aws(secret_name, region, environment)

    if secret and all(
        key in secret for key in ("username", "password", "host", "port", "database")
    ):
        # Build connection URL from secret
        try:
            username = secret["username"]
            password = secret["password"]
            host = secret["host"]
            port = secret["port"]
            database = secret["database"]
            # Note: ssl_cert_path is in the secret but SSL config
            # is handled in db/base.py via connect_args

            # Build PostgreSQL URL without SSL params
            db_url = (
                f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{database}"
            )

            # Note: SSL parameters are handled in db/base.py via connect_args
            # We don't add query parameters here to avoid conflicts

            logger.info(
                "database_credentials_fetched_from_aws",
                secret_id=secret_name,
                host=host,
                database=database,
                environment=environment,
            )

            return db_url

        except (KeyError, TypeError) as e:
            logger.error(
                "invalid_db_credentials_format_in_aws",
                secret_id=secret_name,
                error=str(e),
                message="Secret missing required fields or invalid format",
            )
            # Fall through to environment variable fallback

    # Fallback to environment variable
    logger.warning(
        "aws_unavailable_using_env_fallback_db",
        secret_id=secret_name,
        message=(
            "AWS Secrets Manager unavailable, falling back to "
            "DATABASE_URL environment variable"
        ),
    )

    env_url = os.getenv("DATABASE_URL")

    # If not in environment, try loading from .env file
    if not env_url:
        try:
            from dotenv import load_dotenv

            load_dotenv()
            env_url = os.getenv("DATABASE_URL")
        except ImportError:
            # python-dotenv not installed, skip
            pass

    if env_url:
        logger.info(
            "database_url_loaded_from_env_fallback",
            message="Using DATABASE_URL environment variable as fallback",
        )
        return env_url

    # Both AWS and environment variable failed
    raise KeyNotFoundError(
        f"Database credentials not found in AWS Secrets Manager ({secret_name}) "
        f"or DATABASE_URL environment variable. "
        f"Set DATABASE_URL in .env file for local development."
    )


# ============================================================================
# KEY VERSIONING & ROTATION SUPPORT
# ============================================================================


def generate_encryption_key() -> bytes:
    """
    Generate a new AES-256 encryption key (32 bytes).

    Uses secrets.token_bytes() for cryptographically secure random generation.
    Validates entropy before returning to ensure key quality (CWE-330 mitigation).

    Returns:
        bytes: 32-byte encryption key

    Raises:
        WeakKeyError: If generated key fails entropy validation (extremely rare)

    Example:
        >>> from pazpaz.utils.secrets_manager import generate_encryption_key
        >>> key = generate_encryption_key()
        >>> len(key)
        32

    Security Note:
        This function retries up to 3 times if generated keys fail entropy
        validation. With secrets.token_bytes(), failures should be extremely
        rare (practically impossible), but this provides defense in depth.
    """
    import secrets

    from pazpaz.utils.key_validation import WeakKeyError, validate_key_entropy

    max_attempts = 3

    for attempt in range(max_attempts):
        # Generate 32 bytes (256 bits) of cryptographically secure random data
        key = secrets.token_bytes(ENCRYPTION_KEY_SIZE)

        try:
            # Validate entropy (should always pass with secrets.token_bytes)
            validate_key_entropy(key, version="newly-generated")

            logger.info(
                "encryption_key_generated",
                key_length=len(key),
                attempt=attempt + 1,
            )

            return key

        except WeakKeyError as e:
            # This should be extremely rare with secrets.token_bytes
            logger.warning(
                "generated_key_failed_entropy_check",
                attempt=attempt + 1,
                reason=str(e),
            )

            if attempt == max_attempts - 1:
                # Final attempt failed
                raise WeakKeyError(
                    f"Failed to generate key with sufficient entropy "
                    f"after {max_attempts} attempts"
                ) from e

            # Try again
            continue

    # Should never reach here
    raise WeakKeyError("Key generation failed unexpectedly")


@lru_cache(maxsize=10)
def get_encryption_key_version(
    version: str,
    region: str = "us-east-1",
    environment: str = "local",
) -> bytes:
    """
    Get a specific encryption key version from AWS Secrets Manager.

    This function fetches a specific key version for multi-version decryption
    during key rotation. Each key version is stored as a separate secret in
    AWS Secrets Manager with naming convention: pazpaz/encryption-key-{version}

    The result is cached via @lru_cache to avoid repeated AWS API calls
    (maxsize=10 allows caching up to 10 key versions).

    Args:
        version: Key version identifier (e.g., "v1", "v2", "v3")
        region: AWS region (default: us-east-1)
        environment: Current environment (local/staging/production)

    Returns:
        32-byte encryption key for AES-256-GCM

    Raises:
        KeyNotFoundError: If key version not found in AWS or environment
        ValueError: If key format is invalid

    Example:
        >>> from pazpaz.utils.secrets_manager import get_encryption_key_version
        >>> key_v2 = get_encryption_key_version("v2")
        >>> len(key_v2)
        32

    AWS Secret Naming Convention:
        - pazpaz/encryption-key-v1
        - pazpaz/encryption-key-v2
        - pazpaz/encryption-key-v3
        - ...

    AWS Secret Format (JSON):
        {
            "encryption_key": "base64-encoded-32-byte-key",
            "version": "v2",
            "created_at": "2025-01-19T00:00:00Z",
            "expires_at": "2025-04-19T00:00:00Z",
            "is_current": false
        }
    """
    secret_name = f"pazpaz/encryption-key-{version}"

    # Local development: Try environment variable first
    if environment == "local":
        # Check for version-specific env var first
        env_var_name = f"ENCRYPTION_KEY_{version.upper()}"
        key_b64 = os.getenv(env_var_name)

        if key_b64:
            try:
                key = base64.b64decode(key_b64)

                if len(key) != ENCRYPTION_KEY_SIZE:
                    raise ValueError(
                        f"Encryption key from {env_var_name} must be "
                        f"{ENCRYPTION_KEY_SIZE} bytes, got {len(key)} bytes"
                    )

                logger.info(
                    "encryption_key_version_loaded_from_env",
                    version=version,
                    env_var=env_var_name,
                )

                return key

            except Exception as e:
                logger.error(
                    "invalid_encryption_key_version_in_env",
                    version=version,
                    env_var=env_var_name,
                    error=str(e),
                )
                # Fall through to AWS

        # Fall back to default ENCRYPTION_MASTER_KEY for v1
        if version == "v1":
            env_key = _get_key_from_env()
            if env_key:
                return env_key

    # Production/Staging: Fetch from AWS Secrets Manager
    secret = _fetch_secret_from_aws(secret_name, region, environment)

    if secret and "encryption_key" in secret:
        try:
            key_b64 = secret["encryption_key"]
            key = base64.b64decode(key_b64)

            if len(key) != ENCRYPTION_KEY_SIZE:
                raise ValueError(
                    f"Encryption key {version} from AWS must be "
                    f"{ENCRYPTION_KEY_SIZE} bytes, got {len(key)} bytes"
                )

            logger.info(
                "encryption_key_version_fetched_from_aws",
                version=version,
                secret_id=secret_name,
                is_current=secret.get("is_current", False),
            )

            return key

        except Exception as e:
            logger.error(
                "invalid_key_version_format_in_aws",
                version=version,
                secret_id=secret_name,
                error=str(e),
            )

    # Both AWS and environment variable failed
    raise KeyNotFoundError(
        f"Encryption key version '{version}' not found in AWS Secrets Manager "
        f"({secret_name}) or environment variable (ENCRYPTION_KEY_{version.upper()}). "
        f"Generate a key with: python -c 'import secrets,base64; "
        f"print(base64.b64encode(secrets.token_bytes(32)).decode())'"
    )


def load_all_encryption_keys(
    region: str = "us-east-1",
    environment: str = "local",
) -> None:
    """
    Load all encryption key versions from AWS Secrets Manager into the key registry.

    This function discovers all encryption keys by listing secrets with the prefix
    "pazpaz/encryption-key-" and loads them into the global key registry for
    multi-version decryption support.

    This should be called at application startup to enable zero-downtime key rotation.

    Args:
        region: AWS region (default: us-east-1)
        environment: Current environment (local/staging/production)

    Raises:
        KeyNotFoundError: If no encryption keys found
        SecretsManagerError: If AWS API call fails

    Example:
        >>> from pazpaz.utils.secrets_manager import load_all_encryption_keys
        >>> load_all_encryption_keys()
        >>> # Keys now available in encryption.get_key_registry()

    Side Effects:
        - Populates encryption._KEY_REGISTRY with all key versions
        - Logs key loading events for audit trail

    Security Note:
        Keys are stored in memory for the lifetime of the application process.
        This is acceptable because:
        1. Application server memory is protected
        2. Avoids repeated AWS API calls (performance)
        3. HIPAA allows in-memory key storage with proper access controls
    """
    # Import here to avoid circular dependency
    from pazpaz.utils.encryption import EncryptionKeyMetadata, register_key

    try:
        client = _get_boto3_client(region)

        # List all secrets with prefix "pazpaz/encryption-key-"
        prefix = "pazpaz/encryption-key-"
        response = client.list_secrets(
            Filters=[
                {"Key": "name", "Values": [prefix]},
            ]
        )

        secret_list = response.get("SecretList", [])

        if not secret_list:
            # No versioned keys in AWS - try loading single key
            logger.warning(
                "no_versioned_keys_found_in_aws",
                prefix=prefix,
                message="No versioned encryption keys found, loading single key as v1",
            )

            # Load single key as v1
            try:
                key = get_encryption_key(environment=environment, region=region)
                metadata = EncryptionKeyMetadata(
                    key=key,
                    version="v1",
                    created_at=datetime.now(UTC),
                    expires_at=datetime.now(UTC) + timedelta(days=90),
                    is_current=True,
                )
                register_key(metadata)

                logger.info(
                    "loaded_single_key_as_v1",
                    message="Loaded single encryption key as v1 (legacy mode)",
                )

                return

            except KeyNotFoundError:
                raise KeyNotFoundError(
                    "No encryption keys found in AWS Secrets Manager or environment. "
                    "Set ENCRYPTION_MASTER_KEY in .env file or create secrets in AWS."
                )

        # Load each key version
        for secret_info in secret_list:
            secret_name = secret_info["Name"]

            # Extract version from secret name (e.g., "pazpaz/encryption-key-v2" -> "v2")
            if not secret_name.startswith(prefix):
                continue

            version = secret_name[len(prefix) :]

            # Fetch secret value
            secret = _fetch_secret_from_aws(secret_name, region, environment)

            if not secret or "encryption_key" not in secret:
                logger.warning(
                    "invalid_key_version_format",
                    secret_name=secret_name,
                    version=version,
                    message="Secret missing encryption_key field, skipping",
                )
                continue

            # Parse key and metadata
            try:
                key_b64 = secret["encryption_key"]
                key = base64.b64decode(key_b64)

                if len(key) != ENCRYPTION_KEY_SIZE:
                    logger.error(
                        "invalid_key_size",
                        version=version,
                        expected_size=ENCRYPTION_KEY_SIZE,
                        actual_size=len(key),
                    )
                    continue

                # NEW: Validate key entropy and quality (CWE-330 mitigation)
                from pazpaz.utils.key_validation import (
                    WeakKeyError,
                    validate_key_entropy,
                )

                try:
                    validate_key_entropy(key, version=version)
                except WeakKeyError as e:
                    logger.error(
                        "weak_key_rejected",
                        version=version,
                        reason=str(e),
                        action="skipping_key",
                    )
                    # Skip weak key - don't add to registry
                    continue

                # Parse metadata (with defaults)
                created_at_str = secret.get("created_at")
                if created_at_str:
                    created_at = datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )
                else:
                    # Default: assume created now (conservative estimate)
                    created_at = datetime.now(UTC)

                expires_at_str = secret.get("expires_at")
                if expires_at_str:
                    expires_at = datetime.fromisoformat(
                        expires_at_str.replace("Z", "+00:00")
                    )
                else:
                    # Default: 90 days from creation
                    expires_at = created_at + timedelta(days=90)

                is_current = secret.get("is_current", False)

                # Create metadata and register
                metadata = EncryptionKeyMetadata(
                    key=key,
                    version=version,
                    created_at=created_at,
                    expires_at=expires_at,
                    is_current=is_current,
                )

                register_key(metadata)

            except Exception as e:
                logger.error(
                    "failed_to_load_key_version",
                    version=version,
                    secret_name=secret_name,
                    error=str(e),
                )
                continue

        logger.info(
            "all_encryption_keys_loaded",
            key_count=len(secret_list),
            message="All encryption key versions loaded into registry",
        )

    except Exception as e:
        # In local environment, fall back to single key
        if environment == "local":
            logger.warning(
                "aws_unavailable_loading_single_key",
                error=str(e),
                message="AWS unavailable, loading single key from environment",
            )

            from pazpaz.utils.encryption import EncryptionKeyMetadata, register_key

            try:
                key = get_encryption_key(environment=environment, region=region)
                metadata = EncryptionKeyMetadata(
                    key=key,
                    version="v1",
                    created_at=datetime.now(UTC),
                    expires_at=datetime.now(UTC) + timedelta(days=90),
                    is_current=True,
                )
                register_key(metadata)

                logger.info(
                    "loaded_single_key_fallback",
                    message="Loaded single encryption key as v1 (AWS unavailable)",
                )

                return

            except KeyNotFoundError:
                raise KeyNotFoundError(
                    "No encryption keys found in AWS Secrets Manager or environment. "
                    "Set ENCRYPTION_MASTER_KEY in .env file."
                )

        # Production/staging: fail loudly
        logger.error(
            "failed_to_load_encryption_keys",
            error=str(e),
            environment=environment,
        )
        raise SecretsManagerError(
            f"Failed to load encryption keys from AWS: {e}"
        ) from e
