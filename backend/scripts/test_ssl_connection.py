#!/usr/bin/env python3
"""Test script to verify PostgreSQL SSL/TLS connection."""

import asyncio
import sys

from pazpaz.core.config import settings
from pazpaz.core.logging import configure_logging, get_logger
from pazpaz.db.base import verify_ssl_connection


async def main():
    """Test database SSL connection."""
    configure_logging(debug=True)
    logger = get_logger(__name__)

    logger.info("=" * 60)
    logger.info("Testing PostgreSQL SSL/TLS Connection")
    logger.info("=" * 60)
    logger.info("")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Database URL: {settings.database_url}")
    logger.info(f"SSL Enabled: {settings.db_ssl_enabled}")
    logger.info(f"SSL Mode: {settings.db_ssl_mode}")
    logger.info(f"CA Certificate: {settings.db_ssl_ca_cert_path}")
    logger.info("")

    try:
        logger.info("Attempting to connect to database with SSL/TLS...")
        ssl_enabled = await verify_ssl_connection()

        logger.info("")
        logger.info("=" * 60)
        if ssl_enabled:
            logger.info("✅ SUCCESS: Database SSL/TLS connection verified!")
            logger.info("=" * 60)
            logger.info("")
            logger.info("Database connection is encrypted with SSL/TLS")
            logger.info("✅ HIPAA compliance requirement met for data in transit")
            return 0
        else:
            logger.warning("=" * 60)
            logger.warning("⚠️  WARNING: Database SSL/TLS is NOT enabled!")
            logger.warning("=" * 60)
            logger.warning("")
            logger.warning("Database connection is NOT encrypted")
            logger.warning("❌ HIPAA compliance violation - PHI data exposed in transit")
            return 1

    except Exception as e:
        logger.error("")
        logger.error("=" * 60)
        logger.error("❌ FAILED: Database SSL/TLS verification failed!")
        logger.error("=" * 60)
        logger.error("")
        logger.error(f"Error: {e}")
        logger.error("")
        logger.error("Possible causes:")
        logger.error("  1. PostgreSQL is not configured with SSL")
        logger.error("  2. SSL certificates are missing or invalid")
        logger.error("  3. Database connection string is incorrect")
        logger.error("  4. CA certificate path is incorrect")
        logger.error("")
        logger.error("To fix:")
        logger.error("  1. Run: ./backend/scripts/generate_ssl_certs.sh")
        logger.error("  2. Ensure docker-compose.yml mounts SSL certificates")
        logger.error("  3. Verify DB_SSL_CA_CERT_PATH in .env")
        logger.error("  4. Restart PostgreSQL: docker compose restart db")
        return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
