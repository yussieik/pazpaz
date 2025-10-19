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
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields like DATABASE_URL (handled by property)
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
    # NOTE: In production/staging, database_url is fetched from AWS Secrets Manager
    # In local development, it's read from DATABASE_URL environment variable
    # See @property database_url below for dynamic credential fetching

    # Database SSL/TLS Configuration (HIPAA requirement)
    db_ssl_enabled: bool = Field(
        default=True,
        description="Enable SSL/TLS for database connections (required for production)",
    )
    db_ssl_mode: str = Field(
        default="verify-ca",
        description="SSL mode: disable, allow, prefer, require, verify-ca, verify-full",
    )
    db_ssl_ca_cert_path: str = Field(
        default="/Users/yussieik/Desktop/projects/pazpaz/backend/certs/ca-cert.pem",
        description="Path to PostgreSQL CA certificate for SSL verification",
    )
    db_ssl_client_cert_path: str | None = Field(
        default=None, description="Path to client certificate for mutual TLS (optional)"
    )
    db_ssl_client_key_path: str | None = Field(
        default=None, description="Path to client private key for mutual TLS (optional)"
    )

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
    def validate_secret_key(cls, v: str, info) -> str:
        """
        Validate SECRET_KEY meets security requirements.

        Requirements:
        - Production: Minimum 64 characters (256 bits hex-encoded)
        - Development: Minimum 32 characters (with warning)
        - Not the default value in production/staging
        - Contains variety of characters (sufficient entropy)

        Args:
            v: SECRET_KEY value
            info: Validation context

        Returns:
            Validated secret key

        Raises:
            ValueError: If key doesn't meet requirements
        """
        environment = info.data.get("environment", "local")

        # Production/Staging: Enforce 64+ characters (32 bytes hex = 64 chars)
        if environment in ("production", "staging"):
            if len(v) < 64:
                raise ValueError(
                    f"SECRET_KEY must be at least 64 characters in {environment}, "
                    f"got {len(v)}. Generate with: openssl rand -hex 32"
                )

            # Check not default value
            if "change-me" in v.lower():
                raise ValueError(
                    "SECRET_KEY cannot be default value in production. "
                    "Generate with: openssl rand -hex 32"
                )

        # Development: Minimum 32 characters (with warning)
        elif len(v) < 32:
            logger.warning(
                "secret_key_weak_in_development",
                length=len(v),
                message="SECRET_KEY should be at least 32 characters. "
                "Generate with: openssl rand -hex 32",
            )

        # Check for weak patterns (insufficient entropy)
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

    # AWS Secrets Manager configuration for database credentials
    db_secrets_manager_key_name: str = Field(
        default="pazpaz/database-credentials",
        description="AWS Secrets Manager secret name for database credentials",
    )

    @field_validator("s3_access_key")
    @classmethod
    def validate_s3_access_key(cls, v: str, info) -> str:
        """
        Validate S3_ACCESS_KEY is not default in production.

        Requirements:
        - Production: Cannot be 'minioadmin', minimum 12 characters
        - Development: Warns if default credentials used

        Args:
            v: S3_ACCESS_KEY value
            info: Validation context

        Returns:
            Validated access key

        Raises:
            ValueError: If key is weak in production
        """
        environment = info.data.get("environment", "local")

        if environment in ("production", "staging"):
            # Reject default MinIO credentials
            if v in ("minioadmin", "CHANGE_ME_16_CHARS"):
                raise ValueError(
                    f"S3_ACCESS_KEY cannot be default MinIO credential in {environment}. "
                    "Generate with: openssl rand -base64 16 | tr -d '/+=' | cut -c1-16"
                )

            # Enforce minimum length (12 chars, recommend 16+)
            if len(v) < 12:
                raise ValueError(
                    f"S3_ACCESS_KEY must be at least 12 characters in {environment}, "
                    f"got {len(v)}. Generate with: openssl rand -base64 16"
                )

        elif v == "minioadmin":
            logger.warning(
                "s3_access_key_default_in_development",
                message="S3_ACCESS_KEY is using default 'minioadmin'. "
                "This is acceptable for local development only.",
            )

        return v

    @field_validator("s3_secret_key")
    @classmethod
    def validate_s3_secret_key(cls, v: str, info) -> str:
        """
        Validate S3_SECRET_KEY is not default in production.

        Requirements:
        - Production: Cannot be 'minioadmin123', minimum 20 characters
        - Development: Warns if default credentials used

        Args:
            v: S3_SECRET_KEY value
            info: Validation context

        Returns:
            Validated secret key

        Raises:
            ValueError: If key is weak in production
        """
        environment = info.data.get("environment", "local")

        if environment in ("production", "staging"):
            # Reject default MinIO credentials
            if v in ("minioadmin123", "CHANGE_ME_GENERATE_RANDOM_32_CHARS"):
                raise ValueError(
                    f"S3_SECRET_KEY cannot be default MinIO credential in {environment}. "
                    "Generate with: openssl rand -base64 32 | tr -d '/+='"
                )

            # Enforce minimum length (20 chars, recommend 32+)
            if len(v) < 20:
                raise ValueError(
                    f"S3_SECRET_KEY must be at least 20 characters in {environment}, "
                    f"got {len(v)}. Generate with: openssl rand -base64 32"
                )

        elif v == "minioadmin123":
            logger.warning(
                "s3_secret_key_default_in_development",
                message="S3_SECRET_KEY is using default 'minioadmin123'. "
                "This is acceptable for local development only.",
            )

        return v

    @field_validator("db_ssl_mode")
    @classmethod
    def validate_db_ssl_mode(cls, v: str, info) -> str:
        """
        Validate DB_SSL_MODE is secure in production.

        Requirements:
        - Production/Staging: Must use 'verify-ca' or 'verify-full'
        - Development: Warns if using 'require' (doesn't verify cert)

        Args:
            v: DB_SSL_MODE value
            info: Validation context

        Returns:
            Validated SSL mode

        Raises:
            ValueError: If SSL mode is insecure in production
        """
        environment = info.data.get("environment", "local")

        # Production MUST use verify-ca or verify-full
        if environment in ("production", "staging"):
            if v not in ("verify-ca", "verify-full"):
                raise ValueError(
                    f"DB_SSL_MODE must be 'verify-ca' or 'verify-full' in {environment}, "
                    f"got '{v}'. Current mode does not verify certificate authenticity, "
                    f"exposing PHI to MITM attacks (HIPAA §164.312(e)(1) violation)."
                )

        # Development: allow require mode but warn
        elif v == "require":
            logger.warning(
                "db_ssl_mode_weak_in_development",
                mode=v,
                message="DB_SSL_MODE=require does not verify certificates. "
                "Use 'verify-ca' for production-like security testing.",
            )

        return v

    @field_validator("redis_password")
    @classmethod
    def validate_redis_password(cls, v: str, info) -> str:
        """
        Validate REDIS_PASSWORD is strong.

        Requirements:
        - Production: Minimum 32 characters
        - Development: Warns if less than 32 characters

        Args:
            v: REDIS_PASSWORD value
            info: Validation context

        Returns:
            Validated password

        Raises:
            ValueError: If password is weak in production
        """
        environment = info.data.get("environment", "local")

        if environment in ("production", "staging"):
            # Reject default/weak passwords
            if v in ("change-me-in-production", "CHANGE_ME_GENERATE_RANDOM_32_CHARS"):
                raise ValueError(
                    f"REDIS_PASSWORD cannot be default value in {environment}. "
                    "Generate with: openssl rand -base64 32 | tr -d '/+='"
                )

            # Enforce minimum length
            if len(v) < 32:
                raise ValueError(
                    f"REDIS_PASSWORD must be at least 32 characters in {environment}, "
                    f"got {len(v)}. Generate with: openssl rand -base64 32"
                )

        elif len(v) < 32:
            logger.warning(
                "redis_password_weak_in_development",
                length=len(v),
                message="REDIS_PASSWORD should be at least 32 characters. "
                "Generate with: openssl rand -base64 32",
            )

        return v

    # S3/MinIO Storage Configuration
    s3_endpoint_url: str = Field(
        default="http://localhost:9000",
        description="S3/MinIO endpoint URL (use https:// in production)",
    )
    s3_access_key: str = Field(
        default="minioadmin",
        description="S3/MinIO access key (root user)",
    )
    s3_secret_key: str = Field(
        default="minioadmin123",
        description="S3/MinIO secret key (root password)",
    )
    s3_bucket_name: str = Field(
        default="pazpaz-attachments",
        description="S3 bucket name for session attachments",
    )
    s3_region: str = Field(
        default="us-east-1",
        description="S3 region (MinIO uses us-east-1 by default)",
    )

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

    @property
    def database_url(self) -> str:
        """
        Get database URL from AWS Secrets Manager (prod/staging) or env var (dev).

        This property implements a secure credential management strategy:
        - Production/Staging: Fetch from AWS Secrets Manager
        - Local Development: Read from DATABASE_URL environment variable

        The database credentials are cached via @lru_cache to avoid repeated
        AWS API calls (50-200ms latency). The cache persists for the lifetime
        of the application instance.

        Graceful fallback strategy:
        1. Production/Staging: Try AWS Secrets Manager first, fall back to env var
        2. Local: Try env var first, fall back to AWS (for testing)
        3. Raise error if both fail

        Returns:
            PostgreSQL connection URL (postgresql+asyncpg://...)

        Raises:
            KeyNotFoundError: If credentials not found in AWS or environment

        Security Notes:
            - Credentials are NEVER logged (only host/database name)
            - Production MUST use AWS Secrets Manager for HIPAA compliance
            - Local .env file is acceptable for development only
            - SSL/TLS parameters are configured separately in db/base.py
        """
        from pazpaz.utils.secrets_manager import get_database_credentials

        return get_database_credentials(
            secret_name=self.db_secrets_manager_key_name,
            region=self.aws_region,
            environment=self.environment,
        )


settings = Settings()
