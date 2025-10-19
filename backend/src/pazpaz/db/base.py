"""SQLAlchemy base configuration."""

import os
import ssl
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


def _create_ssl_context() -> ssl.SSLContext | None:
    """
    Create SSL context for PostgreSQL connections.

    Returns:
        SSL context with certificate verification, or None if SSL disabled

    Raises:
        FileNotFoundError: If CA certificate file not found
        ssl.SSLError: If SSL configuration is invalid
    """
    if not settings.db_ssl_enabled:
        logger.warning(
            "database_ssl_disabled",
            message="Database SSL/TLS is disabled - HIPAA violation in production",
            environment=settings.environment,
        )
        return None

    # Create SSL context with secure defaults
    ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

    # Verify CA certificate exists
    if not os.path.exists(settings.db_ssl_ca_cert_path):
        raise FileNotFoundError(
            f"Database CA certificate not found: {settings.db_ssl_ca_cert_path}. "
            "Generate certificates with: ./backend/scripts/generate_ssl_certs.sh"
        )

    # Load CA certificate for verification
    ssl_context.load_verify_locations(cafile=settings.db_ssl_ca_cert_path)

    # Configure SSL verification based on mode
    if settings.db_ssl_mode == "verify-full":
        # Full verification: certificate AND hostname
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
    elif settings.db_ssl_mode == "verify-ca":
        # Verify certificate only (recommended for development with self-signed certs)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_REQUIRED
    elif settings.db_ssl_mode == "require":
        # Require encryption but don't verify certificate
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    else:
        # For development with self-signed certs, allow less strict modes
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_OPTIONAL

    # Load client certificate for mutual TLS (optional)
    if settings.db_ssl_client_cert_path and settings.db_ssl_client_key_path:
        if os.path.exists(settings.db_ssl_client_cert_path) and os.path.exists(
            settings.db_ssl_client_key_path
        ):
            ssl_context.load_cert_chain(
                certfile=settings.db_ssl_client_cert_path,
                keyfile=settings.db_ssl_client_key_path,
            )
            logger.info("database_ssl_mutual_tls_enabled")

    # Enforce TLS 1.2+ (HIPAA requirement)
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

    logger.info(
        "database_ssl_context_created",
        ssl_mode=settings.db_ssl_mode,
        ca_cert=settings.db_ssl_ca_cert_path,
        verify_mode=ssl_context.verify_mode.name,
        check_hostname=ssl_context.check_hostname,
        min_tls_version="TLSv1.2",
    )

    return ssl_context


def _get_engine_connect_args() -> dict[str, Any]:
    """
    Get connection arguments for SQLAlchemy engine.

    Returns:
        Connection arguments including SSL context and server settings
    """
    connect_args: dict[str, Any] = {
        "server_settings": {
            "application_name": "pazpaz_api",
        },
    }

    # Add SSL context if enabled
    ssl_context = _create_ssl_context()
    if ssl_context:
        connect_args["ssl"] = ssl_context

    return connect_args


# Create async engine with SSL enforcement
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    connect_args=_get_engine_connect_args(),
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def verify_ssl_connection() -> bool:
    """
    Verify that database connection uses SSL/TLS.

    This function checks if the current database connection is encrypted
    with SSL/TLS. HIPAA requires all PHI data in transit to be encrypted.

    Returns:
        True if SSL is active, False otherwise

    Raises:
        RuntimeError: If SSL verification is required but not active (production)
    """
    try:
        async with engine.connect() as conn:
            # Query PostgreSQL to check SSL status
            # pg_stat_ssl view shows SSL status for current connection
            result = await conn.execute(
                text(
                    "SELECT COALESCE(ssl, false) as ssl_used, version() as pg_version "
                    "FROM pg_stat_ssl WHERE pid = pg_backend_pid()"
                )
            )
            row = result.fetchone()

            if row is None:
                raise RuntimeError("Failed to query database SSL status")

            ssl_used = bool(row[0])
            pg_version = row[1]

            logger.info(
                "database_ssl_verification",
                ssl_enabled=ssl_used,
                postgresql_version=pg_version,
                environment=settings.environment,
            )

            # In production/staging, SSL MUST be enabled
            if settings.environment in ("production", "staging") and not ssl_used:
                raise RuntimeError(
                    "Database SSL/TLS is not enabled - HIPAA violation. "
                    "PHI data in transit must be encrypted. "
                    "Enable SSL in PostgreSQL configuration and connection string."
                )

            # In development, warn if SSL is disabled
            if settings.environment == "local" and not ssl_used:
                logger.warning(
                    "database_ssl_disabled_development",
                    message="SSL is disabled in development. Enable for HIPAA compliance testing.",
                )

            return ssl_used

    except Exception as e:
        logger.error("database_ssl_verification_failed", error=str(e))
        # In production, fail closed - reject startup if SSL verification fails
        if settings.environment in ("production", "staging"):
            raise
        # In development, allow startup but log warning
        logger.warning("database_ssl_verification_skipped_development")
        return False


async def get_db() -> AsyncSession:
    """Dependency for database sessions."""
    async with AsyncSessionLocal() as session:
        yield session
