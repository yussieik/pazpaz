"""Application configuration."""

import os

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


# Note: AWS Secrets Manager key fetching is now handled by
# pazpaz.utils.secrets_manager module with improved error handling
# and graceful fallback to environment variables.


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
        if environment in ("production", "staging") and "change-me" in v.lower():
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
        - Staging/Production: AWS Secrets Manager with env var fallback
          (cached via @lru_cache)

        The AWS Secrets Manager key is cached after first access to avoid
        repeated API calls (50-200ms latency). The cache persists for the
        lifetime of the application instance.

        Graceful fallback strategy:
        1. Try AWS Secrets Manager (if not local environment)
        2. Fall back to ENCRYPTION_MASTER_KEY environment variable
        3. Raise error if both fail

        Returns:
            32-byte encryption key for AES-256-GCM

        Raises:
            KeyNotFoundError: If key not found in AWS or environment
            ValueError: If key format is invalid
        """
        from pazpaz.utils.secrets_manager import get_encryption_key

        return get_encryption_key(
            secret_name=self.secrets_manager_key_name,
            region=self.aws_region,
            environment=self.environment,
        )


settings = Settings()
