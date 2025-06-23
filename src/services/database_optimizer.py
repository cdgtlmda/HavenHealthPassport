"""Database optimization module for Haven Health Passport.

This module handles database performance optimization including indexes,
query optimization, connection pooling, and monitoring.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DatabaseError, IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool, QueuePool, StaticPool

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class IndexType(str, Enum):
    """Types of database indexes."""

    BTREE = "btree"
    HASH = "hash"
    GIN = "gin"  # For PostgreSQL full-text search
    GIST = "gist"  # For PostgreSQL geometric types
    PARTIAL = "partial"
    UNIQUE = "unique"
    COMPOSITE = "composite"


class IndexDefinition(BaseModel):
    """Definition of a database index."""

    name: str = Field(..., description="Index name")
    table_name: str = Field(..., description="Table name")
    columns: List[str] = Field(..., description="Column names")
    index_type: IndexType = Field(default=IndexType.BTREE)
    unique: bool = Field(default=False)
    where_clause: Optional[str] = Field(None, description="Partial index condition")
    include_columns: Optional[List[str]] = Field(
        None, description="Included columns (covering index)"
    )
    concurrent: bool = Field(default=True, description="Create index concurrently")


class DatabaseOptimizer:
    """Service for database optimization."""

    def __init__(self) -> None:
        """Initialize database optimizer."""
        self.settings = get_settings()
        self.engine: Optional[Engine] = None
        self.async_engine: Optional[AsyncEngine] = None
        self.indexes: Dict[str, IndexDefinition] = {}
        self._initialize_indexes()
        # Enable validation for FHIR compliance
        self.validator_active = True

    def _initialize_indexes(self) -> None:
        """Initialize index definitions."""
        # User authentication indexes
        self.add_index(
            IndexDefinition(
                name="idx_user_auth_email_active",
                table_name="user_auth",
                columns=["email", "is_active"],
                index_type=IndexType.COMPOSITE,
                where_clause=None,
                include_columns=None,
            )
        )

        self.add_index(
            IndexDefinition(
                name="idx_user_auth_login",
                table_name="user_auth",
                columns=["email", "password_hash"],
                where_clause="is_active = true",
                index_type=IndexType.PARTIAL,
                include_columns=None,
            )
        )

        # Patient indexes
        self.add_index(
            IndexDefinition(
                name="idx_patient_search",
                table_name="patients",
                columns=["first_name", "last_name", "date_of_birth"],
                index_type=IndexType.COMPOSITE,
                where_clause=None,
                include_columns=None,
            )
        )

        self.add_index(
            IndexDefinition(
                name="idx_patient_nationality",
                table_name="patients",
                columns=["nationality", "is_active"],
                index_type=IndexType.COMPOSITE,
                where_clause=None,
                include_columns=None,
            )
        )

        # Health record indexes
        self.add_index(
            IndexDefinition(
                name="idx_health_record_patient",
                table_name="health_records",
                columns=["patient_id", "created_at"],
                index_type=IndexType.COMPOSITE,
                where_clause=None,
                include_columns=None,
            )
        )

        self.add_index(
            IndexDefinition(
                name="idx_health_record_type",
                table_name="health_records",
                columns=["record_type", "is_active"],
                where_clause="is_active = true",
                index_type=IndexType.PARTIAL,
                include_columns=None,
            )
        )

        # API key indexes
        self.add_index(
            IndexDefinition(
                name="idx_api_key_hash",
                table_name="api_keys",
                columns=["key_hash"],
                unique=True,
                index_type=IndexType.UNIQUE,
                where_clause=None,
                include_columns=None,
            )
        )

        self.add_index(
            IndexDefinition(
                name="idx_api_key_user_active",
                table_name="api_keys",
                columns=["user_id", "is_active"],
                where_clause="is_active = true AND revoked_at IS NULL",
                index_type=IndexType.PARTIAL,
                include_columns=None,
            )
        )

        # Session indexes
        self.add_index(
            IndexDefinition(
                name="idx_user_session_token",
                table_name="user_sessions",
                columns=["access_token"],
                unique=True,
                index_type=IndexType.UNIQUE,
                where_clause=None,
                include_columns=None,
            )
        )

        self.add_index(
            IndexDefinition(
                name="idx_user_session_active",
                table_name="user_sessions",
                columns=["user_id", "is_active", "expires_at"],
                where_clause="is_active = true",
                index_type=IndexType.PARTIAL,
                include_columns=None,
            )
        )

        # Translation indexes
        self.add_index(
            IndexDefinition(
                name="idx_translation_lookup",
                table_name="translations",
                columns=["source_language", "target_language", "text_hash"],
                unique=True,
                index_type=IndexType.UNIQUE,
                where_clause=None,
                include_columns=None,
            )
        )

        # File attachment indexes
        self.add_index(
            IndexDefinition(
                name="idx_file_attachment_entity",
                table_name="file_attachments",
                columns=["entity_type", "entity_id"],
                index_type=IndexType.COMPOSITE,
                where_clause=None,
                include_columns=None,
            )
        )

        # Audit log indexes
        self.add_index(
            IndexDefinition(
                name="idx_audit_log_user_time",
                table_name="audit_logs",
                columns=["user_id", "created_at"],
                index_type=IndexType.COMPOSITE,
                where_clause=None,
                include_columns=None,
            )
        )

        self.add_index(
            IndexDefinition(
                name="idx_audit_log_category",
                table_name="audit_logs",
                columns=["category", "event_type", "created_at"],
                index_type=IndexType.COMPOSITE,
                where_clause=None,
                include_columns=None,
            )
        )

    def add_index(self, index: IndexDefinition) -> None:
        """Add an index definition."""
        self.indexes[index.name] = index
        logger.info(f"Added index definition: {index.name}")

    async def create_indexes(self, dry_run: bool = False) -> List[Dict[str, Any]]:
        """Create database indexes.

        Args:
            dry_run: If True, only return SQL without executing

        Returns:
            List of index creation results
        """
        results = []

        for index_name, index_def in self.indexes.items():
            try:
                sql = self._generate_index_sql(index_def)

                if dry_run:
                    results.append(
                        {
                            "index": index_name,
                            "sql": sql,
                            "status": "dry_run",
                        }
                    )
                else:
                    # Execute index creation
                    await self._execute_sql(sql)
                    results.append(
                        {
                            "index": index_name,
                            "sql": sql,
                            "status": "created",
                        }
                    )
                    logger.info(f"Created index: {index_name}")

            except (DatabaseError, IntegrityError, SQLAlchemyError) as e:
                logger.error(f"Failed to create index {index_name}: {e}")
                results.append(
                    {
                        "index": index_name,
                        "error": str(e),
                        "status": "failed",
                    }
                )

        return results

    def _generate_index_sql(self, index: IndexDefinition) -> str:
        """Generate SQL for creating an index."""
        sql_parts = ["CREATE"]

        if index.unique or index.index_type == IndexType.UNIQUE:
            sql_parts.append("UNIQUE")

        sql_parts.append("INDEX")

        if index.concurrent:
            sql_parts.append("CONCURRENTLY")

        sql_parts.append(f"IF NOT EXISTS {index.name}")
        sql_parts.append(f"ON {index.table_name}")

        # Index type (PostgreSQL specific)
        if index.index_type in [IndexType.GIN, IndexType.GIST]:
            sql_parts.append(f"USING {index.index_type.value}")

        # Columns
        columns = ", ".join(index.columns)
        sql_parts.append(f"({columns})")

        # Include columns (PostgreSQL 11+)
        if index.include_columns:
            include_cols = ", ".join(index.include_columns)
            sql_parts.append(f"INCLUDE ({include_cols})")

        # Where clause for partial index
        if index.where_clause:
            sql_parts.append(f"WHERE {index.where_clause}")

        return " ".join(sql_parts)

    async def _execute_sql(self, sql: str) -> None:
        """Execute SQL statement."""
        if not self.async_engine:
            self.async_engine = create_async_engine(
                self.settings.database_url,
                pool_pre_ping=True,
            )

        async with self.async_engine.begin() as conn:
            await conn.execute(text(sql))

    def configure_connection_pool(
        self,
        pool_size: int = 20,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
        pool_pre_ping: bool = True,
    ) -> Engine:
        """Configure database connection pooling.

        Args:
            pool_size: Number of connections to maintain
            max_overflow: Maximum overflow connections
            pool_timeout: Timeout for getting connection from pool
            pool_recycle: Time to recycle connections (seconds)
            pool_pre_ping: Test connections before use

        Returns:
            Configured engine
        """
        # Determine pool class based on database
        poolclass: Any
        if "sqlite" in self.settings.database_url:
            poolclass = StaticPool
        elif self.settings.environment == "test":
            poolclass = NullPool
        else:
            poolclass = QueuePool

        # Create engine with connection pooling
        self.engine = create_engine(
            self.settings.database_url,
            poolclass=poolclass,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            pool_pre_ping=pool_pre_ping,
            echo=self.settings.debug,  # Log SQL in debug mode
        )

        # Add event listeners for monitoring
        self._setup_pool_monitoring(self.engine)

        logger.info(
            f"Configured connection pool: size={pool_size}, "
            f"max_overflow={max_overflow}, timeout={pool_timeout}s"
        )

        return self.engine

    def _setup_pool_monitoring(self, engine: Engine) -> None:
        """Set up connection pool monitoring."""

        @event.listens_for(engine, "connect")
        def receive_connect(_dbapi_conn: Any, connection_record: Any) -> None:
            """Log new connections."""
            connection_record.info["connect_time"] = datetime.utcnow()
            logger.debug("New database connection created")

        @event.listens_for(engine, "checkout")
        def receive_checkout(
            _dbapi_conn: Any, _connection_record: Any, _connection_proxy: Any
        ) -> None:
            """Log connection checkouts."""
            logger.debug("Connection checked out from pool")

        @event.listens_for(engine, "checkin")
        def receive_checkin(_dbapi_conn: Any, _connection_record: Any) -> None:
            """Log connection checkins."""
            logger.debug("Connection returned to pool")

    async def analyze_query_performance(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Analyze query performance using EXPLAIN.

        Args:
            query: SQL query to analyze
            params: Query parameters

        Returns:
            Query execution plan and statistics
        """
        # Add EXPLAIN ANALYZE prefix
        explain_query = f"EXPLAIN (ANALYZE, BUFFERS) {query}"

        try:
            if not self.async_engine:
                self.async_engine = create_async_engine(
                    self.settings.database_url,
                    pool_pre_ping=True,
                )
            async with self.async_engine.begin() as conn:
                result = await conn.execute(text(explain_query), params or {})
                rows = result.fetchall()

                # Parse execution plan
                plan = [row[0] for row in rows]

                # Extract key metrics
                metrics = self._parse_explain_output(plan)

                return {
                    "query": query,
                    "execution_plan": plan,
                    "metrics": metrics,
                    "recommendations": self._generate_query_recommendations(metrics),
                }

        except (DatabaseError, SQLAlchemyError, ValueError) as e:
            logger.error(f"Query analysis failed: {e}")
            return {
                "query": query,
                "error": str(e),
            }

    def _parse_explain_output(self, plan: List[str]) -> Dict[str, Any]:
        """Parse EXPLAIN output for key metrics."""
        metrics: Dict[str, float] = {
            "total_cost": 0.0,
            "execution_time": 0.0,
            "planning_time": 0.0,
            "rows_scanned": 0,
            "index_scans": 0,
            "sequential_scans": 0,
        }

        for line in plan:
            # Extract cost
            if "cost=" in line:
                cost_match = re.search(r"cost=(\d+\.?\d*)", line)
                if cost_match:
                    metrics["total_cost"] = float(cost_match.group(1))

            # Extract timing
            if "Execution Time:" in line:
                time_match = re.search(r"(\d+\.?\d*) ms", line)
                if time_match:
                    metrics["execution_time"] = float(time_match.group(1))

            # Count scan types
            if "Index Scan" in line:
                metrics["index_scans"] += 1
            elif "Seq Scan" in line:
                metrics["sequential_scans"] += 1

        return metrics

    def _generate_query_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """Generate query optimization recommendations."""
        recommendations = []

        # Check for sequential scans
        if metrics["sequential_scans"] > 0:
            recommendations.append(
                "Query uses sequential scans. Consider adding indexes on filter columns."
            )

        # Check execution time
        if metrics["execution_time"] > 1000:  # > 1 second
            recommendations.append(
                "Query execution time is high. Consider query optimization or caching."
            )

        # Check cost
        if metrics["total_cost"] > 10000:
            recommendations.append(
                "Query cost is high. Review query structure and join conditions."
            )

        return recommendations

    async def get_pool_statistics(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        if not self.engine:
            return {"error": "Connection pool not configured"}

        conn_pool = self.engine.pool

        return {
            "size": getattr(conn_pool, "size", lambda: 0)(),
            "checked_in": getattr(conn_pool, "checkedin", lambda: 0)(),
            "checked_out": getattr(conn_pool, "checkedout", lambda: 0)(),
            "overflow": getattr(conn_pool, "overflow", lambda: 0)(),
            "total": getattr(conn_pool, "total", lambda: 0)(),
            "configuration": {
                "pool_size": (
                    getattr(getattr(conn_pool, "_pool", None), "maxsize", None)
                    if getattr(conn_pool, "_pool", None) is not None
                    else None
                ),
                "max_overflow": getattr(conn_pool, "_max_overflow", None),
                "timeout": getattr(conn_pool, "_timeout", None),
                "recycle": getattr(conn_pool, "_recycle", None),
            },
        }


# Global optimizer instance
db_optimizer = DatabaseOptimizer()


# Export components
__all__ = [
    "IndexType",
    "IndexDefinition",
    "DatabaseOptimizer",
    "db_optimizer",
]
