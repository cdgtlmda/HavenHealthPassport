"""Database connection pool implementation for PostgreSQL."""

import os
import random
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import psycopg2.pool
from psycopg2.extras import RealDictCursor

from src.config.loader import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DatabaseConnectionPool:
    """PostgreSQL connection pool manager."""

    def __init__(self) -> None:
        """Initialize connection pool."""
        self.pool = None
        self.master_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
        self.replica_pools: List[Any] = []
        self._initialize_pools()

    def _initialize_pools(self) -> None:
        """Initialize database connection pools."""
        try:
            settings = get_settings()
            # Master database pool (for writes)
            self.master_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=5,
                maxconn=100,
                host=os.getenv(
                    "DB_HOST", getattr(settings, "database_host", "localhost")
                ),
                port=int(os.getenv("DB_PORT", "5432")),
                database=os.getenv(
                    "DB_NAME", getattr(settings, "database_name", "haven_health")
                ),
                user=os.getenv(
                    "DB_USER", getattr(settings, "database_user", "postgres")
                ),
                password=os.getenv(
                    "DB_PASSWORD", getattr(settings, "database_password", "")
                ),
                sslmode="require",
                sslrootcert="/opt/rds-ca-2019-root.pem",
                connect_timeout=10,
                options="-c statement_timeout=30000",  # 30 seconds
            )

            # Read replica pools (for reads)
            replica_hosts = os.getenv("DB_REPLICA_HOSTS", "").split(",")
            for replica_host in replica_hosts:
                if replica_host:
                    replica_pool = psycopg2.pool.ThreadedConnectionPool(
                        minconn=2,
                        maxconn=50,
                        host=replica_host,
                        port=int(os.getenv("DB_PORT", "5432")),
                        database=os.getenv(
                            "DB_NAME",
                            getattr(settings, "database_name", "haven_health"),
                        ),
                        user=os.getenv(
                            "DB_USER", getattr(settings, "database_user", "postgres")
                        ),
                        password=os.getenv(
                            "DB_PASSWORD", getattr(settings, "database_password", "")
                        ),
                        sslmode="require",
                        sslrootcert="/opt/rds-ca-2019-root.pem",
                        connect_timeout=10,
                    )
                    self.replica_pools.append(replica_pool)

            logger.info("Database connection pools initialized successfully")

        except (OSError, TypeError, ValueError) as e:
            logger.error(f"Failed to initialize database pools: {e}")
            raise

    @contextmanager
    def get_connection(self, read_only: bool = False) -> Any:
        """Get a database connection from the pool.

        Args:
            read_only: If True, use read replica; if False, use master

        Yields:
            Database connection
        """
        connection = None
        pool_to_use = None

        try:
            if read_only and self.replica_pools:
                # Round-robin between read replicas
                pool_to_use = random.choice(self.replica_pools)
            else:
                pool_to_use = self.master_pool

            if pool_to_use is None:
                raise ValueError("No connection pool available")
            connection = pool_to_use.getconn()
            yield connection

        except OSError as e:
            logger.error(f"Error getting connection from pool: {e}")
            if connection:
                connection.rollback()
            raise

        finally:
            if connection and pool_to_use:
                pool_to_use.putconn(connection)

    @contextmanager
    def get_cursor(self, read_only: bool = False, dict_cursor: bool = True) -> Any:
        """Get a database cursor from the pool.

        Args:
            read_only: If True, use read replica
            dict_cursor: If True, return results as dictionaries

        Yields:
            Database cursor
        """
        with self.get_connection(read_only=read_only) as conn:
            cursor_factory = RealDictCursor if dict_cursor else None
            cursor = conn.cursor(cursor_factory=cursor_factory)

            try:
                yield cursor
                conn.commit()
            except OSError:
                conn.rollback()
                raise
            finally:
                cursor.close()

    def execute_query(
        self,
        query: str,
        params: Optional[tuple] = None,
        read_only: bool = True,
        fetch_one: bool = False,
    ) -> Any:
        """Execute a query and return results.

        Args:
            query: SQL query to execute
            params: Query parameters
            read_only: Whether this is a read-only query
            fetch_one: Whether to fetch one result or all

        Returns:
            Query results
        """
        with self.get_cursor(read_only=read_only) as cursor:
            cursor.execute(query, params)

            if fetch_one:
                return cursor.fetchone()
            else:
                return cursor.fetchall()

    def close_all_pools(self) -> None:
        """Close all connection pools."""
        try:
            # Check and close master pool
            if self.master_pool is not None:
                self.master_pool.closeall()

            for replica_pool in self.replica_pools:
                if replica_pool is not None:
                    replica_pool.closeall()

            logger.info("All database connection pools closed")

        except (psycopg2.Error, AttributeError) as e:
            logger.error(f"Error closing connection pools: {e}")

    def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        stats: Dict[str, Any] = {
            "master": {
                "min_connections": (
                    getattr(self.master_pool, "minconn", 0) if self.master_pool else 0
                ),
                "max_connections": (
                    getattr(self.master_pool, "maxconn", 0) if self.master_pool else 0
                ),
            }
        }

        if self.replica_pools:
            stats["replicas"] = []
            for i, replica_pool in enumerate(self.replica_pools):
                stats["replicas"].append(
                    {
                        "replica_index": i,
                        "min_connections": getattr(replica_pool, "minconn", 0),
                        "max_connections": getattr(replica_pool, "maxconn", 0),
                    }
                )

        return stats


# Global connection pool instance
db_pool = DatabaseConnectionPool()
