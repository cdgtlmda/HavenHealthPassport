"""Database optimization utilities for API performance.

This module provides database optimization features including connection
pooling, query optimization, and performance monitoring.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, event, pool, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from src.config import get_settings
from src.healthcare.fhir_validator import FHIRValidator
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.services.encryption_service import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DatabaseOptimizer:
    """Database optimization manager."""

    def __init__(self) -> None:
        """Initialize database optimizer."""
        self.settings = get_settings()
        self.engine: Optional[Engine] = None
        self.async_engine: Optional[AsyncEngine] = None
        self._indexes_created = False
        self.fhir_validator = FHIRValidator()
        self.encryption_service = EncryptionService()

    async def initialize(self) -> None:
        """Initialize database with optimizations."""
        # Create async engine with connection pooling
        self.async_engine = create_async_engine(
            self.settings.database_url,
            pool_size=self.settings.database_pool_size,
            max_overflow=self.settings.database_max_overflow,
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600,  # Recycle connections after 1 hour
            echo=False,  # Set to True for query logging
            future=True,
        )

        # Create sync engine for certain operations
        sync_url = self.settings.database_url.replace("+asyncpg", "")
        self.engine = create_engine(
            sync_url,
            pool_size=self.settings.database_pool_size,
            max_overflow=self.settings.database_max_overflow,
        )

        # Set up event listeners
        self._setup_event_listeners()

        # Create indexes if not exists
        await self.create_indexes()

    def _setup_event_listeners(self) -> None:
        """Set up SQLAlchemy event listeners for monitoring."""

        @event.listens_for(pool.Pool, "connect")
        def set_sqlite_pragma(
            dbapi_conn: Any, connection_record: Any  # pylint: disable=unused-argument
        ) -> None:
            """Set connection pragmas for better performance."""
            # For PostgreSQL
            if self.settings.database_url.startswith("postgresql"):
                cursor = dbapi_conn.cursor()
                # Set statement timeout
                cursor.execute("SET statement_timeout = '30s'")
                # Set lock timeout
                cursor.execute("SET lock_timeout = '10s'")
                cursor.close()

        @event.listens_for(pool.Pool, "checkout")
        def receive_checkout(
            dbapi_conn: Any,  # pylint: disable=unused-argument
            connection_record: Any,  # pylint: disable=unused-argument
            connection_proxy: Any,  # pylint: disable=unused-argument
        ) -> None:
            """Log connection checkout."""
            logger.debug("Connection checked out from pool")

    async def create_indexes(self) -> None:
        """Create database indexes for performance."""
        if self._indexes_created:
            return

        indexes = [
            # Patient indexes
            "CREATE INDEX IF NOT EXISTS idx_patient_identifiers ON patients USING gin(identifiers)",
            "CREATE INDEX IF NOT EXISTS idx_patient_name ON patients USING gin(to_tsvector('english', name))",
            "CREATE INDEX IF NOT EXISTS idx_patient_refugee_status ON patients(refugee_status)",
            "CREATE INDEX IF NOT EXISTS idx_patient_created ON patients(created_at)",
            # Health record indexes
            "CREATE INDEX IF NOT EXISTS idx_health_record_patient ON health_records(patient_id)",
            "CREATE INDEX IF NOT EXISTS idx_health_record_type ON health_records(type)",
            "CREATE INDEX IF NOT EXISTS idx_health_record_verification ON health_records(verification_status)",
            "CREATE INDEX IF NOT EXISTS idx_health_record_created ON health_records(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_health_record_tags ON health_records USING gin(tags)",
            # Access log indexes
            "CREATE INDEX IF NOT EXISTS idx_access_log_user ON access_logs(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_access_log_record ON access_logs(record_id)",
            "CREATE INDEX IF NOT EXISTS idx_access_log_timestamp ON access_logs(timestamp)",
            # Verification indexes
            "CREATE INDEX IF NOT EXISTS idx_verification_record ON verifications(record_id)",
            "CREATE INDEX IF NOT EXISTS idx_verification_status ON verifications(status)",
            "CREATE INDEX IF NOT EXISTS idx_verification_blockchain ON verifications(blockchain_tx_id)",
        ]

        if self.async_engine is None:
            raise RuntimeError("Database optimizer not initialized")

        async with self.async_engine.begin() as conn:
            for index_sql in indexes:
                try:
                    await conn.execute(text(index_sql))
                    logger.info(f"Created index: {index_sql.split(' ')[5]}")
                except SQLAlchemyError as e:
                    logger.error(f"Error creating index: {e}")

        self._indexes_created = True

    async def analyze_tables(self) -> None:
        """Run ANALYZE on tables for query optimization."""
        tables = [
            "patients",
            "health_records",
            "verifications",
            "access_logs",
            "users",
        ]

        if self.async_engine is None:
            raise RuntimeError(
                "DatabaseOptimizer not initialized. Call initialize() first."
            )

        async with self.async_engine.begin() as conn:
            for table in tables:
                try:
                    await conn.execute(text(f"ANALYZE {table}"))
                    logger.info(f"Analyzed table: {table}")
                except SQLAlchemyError as e:
                    logger.error(f"Error analyzing table {table}: {e}")

    async def get_query_stats(self) -> List[Dict[str, Any]]:
        """Get query performance statistics."""
        if not self.settings.database_url.startswith("postgresql"):
            return []

        query = """
        SELECT
            query,
            calls,
            total_exec_time,
            mean_exec_time,
            stddev_exec_time,
            rows
        FROM pg_stat_statements
        WHERE query NOT LIKE '%pg_stat_statements%'
        ORDER BY total_exec_time DESC
        LIMIT 20
        """

        if self.async_engine is None:
            raise RuntimeError("Database optimizer not initialized")

        async with self.async_engine.connect() as conn:
            try:
                result = await conn.execute(text(query))
                return [dict(row) for row in result]
            except SQLAlchemyError as e:
                logger.error(f"Error getting query stats: {e}")
                return []

    async def get_table_stats(self) -> List[Dict[str, Any]]:
        """Get table size and statistics."""
        query = """
        SELECT
            schemaname,
            tablename,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
            n_tup_ins as inserts,
            n_tup_upd as updates,
            n_tup_del as deletes,
            n_live_tup as live_tuples,
            n_dead_tup as dead_tuples
        FROM pg_stat_user_tables
        ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
        """

        if self.async_engine is None:
            raise RuntimeError(
                "DatabaseOptimizer not initialized. Call initialize() first."
            )

        async with self.async_engine.connect() as conn:
            try:
                result = await conn.execute(text(query))
                return [dict(row) for row in result]
            except SQLAlchemyError as e:
                logger.error(f"Error getting table stats: {e}")
                return []

    async def vacuum_tables(self, full: bool = False) -> None:
        """Run VACUUM on tables to reclaim space."""
        if not self.settings.database_url.startswith("postgresql"):
            return

        tables = [
            "patients",
            "health_records",
            "verifications",
            "access_logs",
        ]

        vacuum_cmd = "VACUUM FULL" if full else "VACUUM"

        # Use sync connection for VACUUM
        if self.engine is None:
            raise RuntimeError(
                "DatabaseOptimizer not initialized. Call initialize() first."
            )

        with self.engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT")
            for table in tables:
                try:
                    conn.execute(text(f"{vacuum_cmd} {table}"))
                    logger.info(f"Vacuumed table: {table}")
                except SQLAlchemyError as e:
                    logger.error(f"Error vacuuming table {table}: {e}")


# Connection pool manager
class ConnectionPoolManager:
    """Manage database connection pools."""

    def __init__(self) -> None:
        """Initialize connection pool manager."""
        self.settings = get_settings()
        self._pools: Dict[str, Any] = {}
        self.fhir_validator = FHIRValidator()
        self.encryption_service = EncryptionService()

    def validate_fhir_resource(self, resource: dict) -> bool:
        """Validate FHIR resource structure and requirements."""
        # Determine resource type and call appropriate validator
        resource_type = resource.get("resourceType", "")

        # Use the generic validate_resource method
        if resource_type:
            result = self.fhir_validator.validate_resource(resource_type, resource)
        else:
            # For unknown resource types, do basic validation
            result = {
                "valid": bool(resource.get("resourceType") and resource.get("id"))
            }

        return bool(result.get("valid", False))

    @audit_phi_access("process_phi_data")
    @require_permission(AccessPermission.READ_PHI)
    def process_with_phi_protection(self, data: dict) -> dict:
        """Process data with PHI protection and audit logging."""
        # Encrypt sensitive fields
        sensitive_fields = ["name", "birthDate", "ssn", "address"]
        encrypted_data = data.copy()

        for field in sensitive_fields:
            if field in encrypted_data:
                encrypted_data[field] = self.encryption_service.encrypt(
                    str(encrypted_data[field])
                )

        return encrypted_data

    def get_pool(self, name: str = "default") -> Any:
        """Get or create a connection pool."""
        if name not in self._pools:
            self._pools[name] = create_async_engine(
                self.settings.database_url,
                pool_size=self.settings.database_pool_size,
                max_overflow=self.settings.database_max_overflow,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
        return self._pools[name]

    async def close_all(self) -> None:
        """Close all connection pools."""
        for name, conn_pool in self._pools.items():
            await conn_pool.dispose()
            logger.info(f"Closed connection pool: {name}")
        self._pools.clear()


# Query optimization helpers
class QueryOptimizer:
    """Query optimization utilities."""

    @staticmethod
    def add_pagination(query: Any, page: int = 1, page_size: int = 20) -> Any:
        """Add pagination to query."""
        offset = (page - 1) * page_size
        return query.limit(page_size).offset(offset)

    @staticmethod
    def add_batch_loading(query: Any, batch_size: int = 100) -> Any:
        """Add batch loading to query."""
        return query.execution_options(yield_per=batch_size)

    @staticmethod
    async def explain_query(session: AsyncSession, query: Any) -> Dict[str, Any]:
        """Get query execution plan."""
        # Convert SQLAlchemy query to SQL
        compiled = query.statement.compile(compile_kwargs={"literal_binds": True})
        sql = str(compiled)

        # Run EXPLAIN ANALYZE
        explain_sql = f"EXPLAIN (ANALYZE, BUFFERS) {sql}"
        result = await session.execute(text(explain_sql))

        return {
            "query": sql,
            "plan": [row[0] for row in result],
        }


# Global instances
db_optimizer = DatabaseOptimizer()
pool_manager = ConnectionPoolManager()
query_optimizer = QueryOptimizer()


# Export utilities
__all__ = [
    "DatabaseOptimizer",
    "ConnectionPoolManager",
    "QueryOptimizer",
    "db_optimizer",
    "pool_manager",
    "query_optimizer",
]
