"""Application configuration."""

import base64
import os
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _fetch_encryption_key_from_aws(
    aws_region: str,
    secrets_manager_key_name: str,
    environment: str,
) -> bytes:
    """
    Fetch and cache encryption key from AWS Secrets Manager.

    This function is cached to avoid repeated AWS API calls. The key is fetched
    once per application instance and reused for all encryption operations.

    Args:
        aws_region: AWS region for Secrets Manager
        secrets_manager_key_name: Name of the secret in Secrets Manager
        environment: Current environment (for logging)

    Returns:
        32-byte encryption key for AES-256-GCM

    Raises:
        ImportError: If boto3 not installed
        RuntimeError: If key not found or AWS error
        ValueError: If key is not 32 bytes
    """
    try:
        import boto3
    except ImportError:
        raise RuntimeError("boto3 not installed. Install with: uv add boto3") from None

    try:
        client = boto3.client("secretsmanager", region_name=aws_region)
        response = client.get_secret_value(SecretId=secrets_manager_key_name)

        # Audit key access
        logger.info(
            "encryption_key_accessed",
            secret_id=secrets_manager_key_name,
            version_id=response.get("VersionId"),
            environment=environment,
        )

        key_b64 = response["SecretString"]
        key = base64.b64decode(key_b64)

        if len(key) != 32:
            raise ValueError(
                f"Encryption key from Secrets Manager must be 32 bytes, got {len(key)}"
            )

        return key

    except Exception as e:
        # Check for specific AWS errors
        error_name = type(e).__name__
        if error_name == "ResourceNotFoundException":
            raise RuntimeError(
                f"Encryption key not found in AWS Secrets Manager: "
                f"{secrets_manager_key_name}. "
                "Create with: aws secretsmanager create-secret "
                "--name pazpaz/encryption-key-v1 "
                "--secret-string $(openssl rand -base64 32)"
            ) from e

        logger.error(
            "failed_to_fetch_encryption_key",
            error=str(e),
            error_type=error_name,
            secret_id=secrets_manager_key_name,
            exc_info=True,
        )
        raise RuntimeError(
            f"Critical: Encryption key unavailable from AWS Secrets Manager: {e}"
        ) from e


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    # App
    app_name: str = "PazPaz"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Environment detection
    environment: str = Field(
        default="local", description="Deployment environment (local/staging/production)"
    )

    # Database
    database_url: str = "postgresql+asyncpg://pazpaz:pazpaz@localhost:5432/pazpaz"

    # Redis
    redis_password: str = "change-me-in-production"
    redis_url: str = "redis://:change-me-in-production@localhost:6379/0"

    # Security
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # CSRF Protection
    csrf_token_expire_minutes: int = 60 * 24 * 7  # 7 days (match JWT expiry)

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """
        Validate SECRET_KEY meets security requirements.

        Requirements:
        - Minimum 32 characters (256 bits if random)
        - Not the default value in production
        - Contains variety of characters (not all same character)

        Args:
            v: SECRET_KEY value

        Returns:
            Validated secret key

        Raises:
            ValueError: If key doesn't meet requirements
        """
        # Check minimum length (32 chars = 256 bits if random)
        if len(v) < 32:
            raise ValueError(
                f"SECRET_KEY must be at least 32 characters, got {len(v)}. "
                "Generate a secure key with: openssl rand -hex 32"
            )

        # Check not default value (only in production/staging)
        environment = os.getenv("ENVIRONMENT", "local")
        if environment in ("production", "staging"):
            if "change-me" in v.lower():
                raise ValueError(
                    "SECRET_KEY cannot be default value in production. "
                    "Set a secure random key in environment variables. "
                    "Generate with: openssl rand -hex 32"
                )

        # Check for weak patterns (all same character)
        if len(set(v)) < 10:
            raise ValueError(
                "SECRET_KEY appears to be weak (insufficient entropy). "
                "Use a cryptographically random key. "
                "Generate with: openssl rand -hex 32"
            )

        return v

    # Encryption (local/development only - use AWS Secrets Manager in production)
    encryption_master_key: str | None = Field(
        default=None,
        description="Base64-encoded 32-byte AES-256 key (local/dev only)",
    )

    # AWS Secrets Manager configuration (production)
    aws_region: str = Field(default="us-east-1", description="AWS region")
    secrets_manager_key_name: str = Field(
        default="pazpaz/encryption-key-v1",
        description="AWS Secrets Manager secret name for encryption key",
    )

    # Frontend
    frontend_url: str = "http://localhost:5173"

    # Email
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    emails_from_email: str = "noreply@pazpaz.local"

    @property
    def encryption_key(self) -> bytes:
        """
        Fetch encryption key from secure storage (cached).

        - Local/Development: Environment variable (ENCRYPTION_MASTER_KEY)
        - Staging/Production: AWS Secrets Manager (cached via @lru_cache)

        The AWS Secrets Manager key is cached after first access to avoid
        repeated API calls (50-200ms latency). The cache persists for the
        lifetime of the application instance.

        Returns:
            32-byte encryption key for AES-256-GCM

        Raises:
            ValueError: If key not found or invalid format
            RuntimeError: If AWS Secrets Manager unavailable (production)
        """
        if self.environment == "local":
            # Development mode: Use environment variable (not cached - cheap operation)
            if not self.encryption_master_key:
                raise ValueError(
                    "ENCRYPTION_MASTER_KEY not set in .env file. "
                    "Generate with: python -c 'import secrets,base64; "
                    "print(base64.b64encode(secrets.token_bytes(32)).decode())'"
                )

            try:
                key = base64.b64decode(self.encryption_master_key)
                if len(key) != 32:
                    raise ValueError(f"Encryption key must be 32 bytes, got {len(key)}")
                logger.debug("encryption_key_loaded_from_env")
                return key
            except Exception as e:
                raise ValueError(f"Invalid ENCRYPTION_MASTER_KEY format: {e}") from e

        # Production/Staging: Fetch from AWS Secrets Manager (cached)
        return _fetch_encryption_key_from_aws(
            aws_region=self.aws_region,
            secrets_manager_key_name=self.secrets_manager_key_name,
            environment=self.environment,
        )


settings = Settings()
