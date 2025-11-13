"""Database connection pool metrics for Prometheus.

This module provides real-time metrics about SQLAlchemy's connection pool
usage, enabling monitoring of database connection health and resource utilization.
"""

from prometheus_client import Gauge
from prometheus_client.registry import Collector

from pazpaz.core.logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# Connection Pool Metrics (Gauges)
# =============================================================================

db_pool_size = Gauge(
    "db_pool_size",
    "Current number of connections in the pool (size + overflow)",
)

db_pool_checked_in = Gauge(
    "db_pool_checked_in",
    "Number of connections currently checked into the pool (available)",
)

db_pool_checked_out = Gauge(
    "db_pool_checked_out",
    "Number of connections currently checked out from the pool (in use)",
)

db_pool_overflow = Gauge(
    "db_pool_overflow",
    "Number of overflow connections created beyond pool_size",
)

db_pool_max_overflow = Gauge(
    "db_pool_max_overflow",
    "Maximum number of overflow connections allowed",
)


class ConnectionPoolCollector(Collector):
    """
    Custom Prometheus collector for SQLAlchemy connection pool statistics.

    This collector reads real-time pool stats from the async engine and
    updates Prometheus gauges on each scrape.

    Usage:
        from prometheus_client import REGISTRY
        from pazpaz.db.base import engine
        from pazpaz.db.metrics import ConnectionPoolCollector

        # Register collector at app startup
        REGISTRY.register(ConnectionPoolCollector(engine))
    """

    def __init__(self, engine):
        """
        Initialize the collector with a SQLAlchemy engine.

        Args:
            engine: SQLAlchemy async engine with connection pool
        """
        self.engine = engine

    def collect(self):
        """
        Collect pool statistics and update metrics.

        This method is called by Prometheus on each scrape. It reads the
        current pool state and updates all gauge metrics.

        Yields:
            Metric families for all connection pool gauges
        """
        try:
            # Get connection pool from engine
            pool = self.engine.pool

            # Read pool statistics (thread-safe)
            # size() returns current total connections (checked in + checked out)
            # checkedin() returns available connections
            # checkedout() returns connections in use
            # overflow() returns connections beyond pool_size

            size = pool.size()
            checked_in = pool.checkedin()
            checked_out = pool.checkedout()
            overflow = pool.overflow()

            # Update gauges
            db_pool_size.set(size)
            db_pool_checked_in.set(checked_in)
            db_pool_checked_out.set(checked_out)
            db_pool_overflow.set(overflow)

            # max_overflow is configured at pool creation, not a runtime stat
            # We'll set it from the pool config if available
            if hasattr(pool, "_max_overflow"):
                db_pool_max_overflow.set(pool._max_overflow)

            logger.debug(
                "connection_pool_metrics_collected",
                size=size,
                checked_in=checked_in,
                checked_out=checked_out,
                overflow=overflow,
            )

        except Exception as e:
            logger.error("connection_pool_metrics_collection_failed", error=str(e))
            # Don't raise - metrics collection should not break the application

        # Return empty list - metrics are already updated via set()
        # prometheus_client will collect them via the REGISTRY
        return []


__all__ = [
    "db_pool_size",
    "db_pool_checked_in",
    "db_pool_checked_out",
    "db_pool_overflow",
    "db_pool_max_overflow",
    "ConnectionPoolCollector",
]
