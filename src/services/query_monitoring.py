"""Query monitoring service for database performance tracking.

This module provides comprehensive query monitoring, slow query detection,
and performance analysis for the Haven Health Passport database.
"""

import re
import time
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from src.utils.logging import get_logger

logger = get_logger(__name__)


class QueryType(str, Enum):
    """Types of database queries."""

    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    ALTER = "ALTER"
    DROP = "DROP"
    OTHER = "OTHER"


class QueryMetrics(BaseModel):
    """Metrics for a database query."""

    query: str = Field(..., description="SQL query")
    query_type: QueryType = Field(..., description="Type of query")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")
    rows_affected: int = Field(default=0, description="Number of rows affected")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Optional metadata
    user_id: Optional[str] = Field(None, description="User who executed the query")
    endpoint: Optional[str] = Field(
        None, description="API endpoint that triggered the query"
    )
    parameters: Optional[Dict[str, Any]] = Field(None, description="Query parameters")

    # Performance flags
    is_slow: bool = Field(default=False, description="Whether query is considered slow")
    used_index: bool = Field(default=True, description="Whether query used an index")


class QueryPattern(BaseModel):
    """Pattern for query analysis."""

    pattern: str = Field(..., description="Query pattern (normalized)")
    count: int = Field(default=0, description="Number of executions")
    total_time_ms: float = Field(default=0.0, description="Total execution time")
    avg_time_ms: float = Field(default=0.0, description="Average execution time")
    max_time_ms: float = Field(default=0.0, description="Maximum execution time")
    min_time_ms: float = Field(
        default=float("inf"), description="Minimum execution time"
    )

    @property
    def avg_time_ms_calculated(self) -> float:
        """Calculate average time."""
        return self.total_time_ms / self.count if self.count > 0 else 0.0


class QueryMonitoringService:
    """Service for monitoring database queries."""

    def __init__(
        self,
        slow_query_threshold_ms: float = 100.0,
        enable_parameter_logging: bool = False,
        max_query_length: int = 1000,
    ):
        """Initialize query monitoring service.

        Args:
            slow_query_threshold_ms: Threshold for slow queries in milliseconds
            enable_parameter_logging: Whether to log query parameters
            max_query_length: Maximum query length to store
        """
        self.slow_query_threshold_ms = slow_query_threshold_ms
        self.enable_parameter_logging = enable_parameter_logging
        self.max_query_length = max_query_length

        # Storage
        self.queries: List[QueryMetrics] = []
        self.query_patterns: Dict[str, QueryPattern] = {}
        self.slow_queries: List[QueryMetrics] = []

        # Real-time metrics
        self.active_queries: Dict[str, datetime] = {}
        self.query_count_by_type: Dict[QueryType, int] = defaultdict(int)

        # Configuration
        self.is_monitoring = False
        self.max_stored_queries = 10000
        self.max_slow_queries = 1000

    def start_monitoring(self, engine: Engine) -> None:
        """Start monitoring queries on the given engine."""
        if self.is_monitoring:
            logger.warning("Query monitoring already active")
            return

        # Set up event listeners
        event.listen(engine, "before_cursor_execute", self._before_cursor_execute)
        event.listen(engine, "after_cursor_execute", self._after_cursor_execute)

        self.is_monitoring = True
        logger.info("Started query monitoring")

    def stop_monitoring(self, engine: Engine) -> None:
        """Stop monitoring queries."""
        if not self.is_monitoring:
            return

        # Remove event listeners
        event.remove(engine, "before_cursor_execute", self._before_cursor_execute)
        event.remove(engine, "after_cursor_execute", self._after_cursor_execute)

        self.is_monitoring = False
        logger.info("Stopped query monitoring")

    def _before_cursor_execute(
        self,
        conn: Connection,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        """Handle pre-query execution tasks."""
        _ = (
            conn,
            cursor,
            statement,
            parameters,
            executemany,
        )  # Intentionally unused - event callback signature
        # Store start time in context
        # pylint: disable=protected-access
        context._query_start_time = time.time()

        # Track active query
        query_id = f"{id(context)}_{time.time()}"
        self.active_queries[query_id] = datetime.utcnow()
        # pylint: disable=protected-access
        context._query_id = query_id

    def _after_cursor_execute(
        self,
        conn: Connection,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        """Handle post-query execution tasks."""
        _ = (conn, executemany)  # Intentionally unused - event callback signature
        # Calculate execution time
        execution_time_ms = (
            time.time() - getattr(context, "_query_start_time", time.time())
        ) * 1000

        # Remove from active queries
        query_id = getattr(context, "_query_id", None)
        if query_id and query_id in self.active_queries:
            del self.active_queries[query_id]

        # Determine query type
        query_type = self._determine_query_type(statement)

        # Create metrics
        metrics = QueryMetrics(
            query=statement[: self.max_query_length],
            query_type=query_type,
            execution_time_ms=execution_time_ms,
            rows_affected=cursor.rowcount if hasattr(cursor, "rowcount") else 0,
            is_slow=execution_time_ms > self.slow_query_threshold_ms,
            user_id=None,
            endpoint=None,
            parameters=None,
        )

        # Add parameters if enabled
        if self.enable_parameter_logging and parameters:
            metrics.parameters = (
                dict(parameters)
                if isinstance(parameters, dict)
                else {"params": parameters}
            )

        # Store metrics
        self._store_metrics(metrics)

        # Update patterns
        self._update_query_pattern(statement, execution_time_ms)

        # Log slow queries
        if metrics.is_slow:
            self._log_slow_query(metrics)

    def _determine_query_type(self, statement: str) -> QueryType:
        """Determine the type of SQL query."""
        statement_upper = statement.strip().upper()

        for query_type in QueryType:
            if statement_upper.startswith(query_type.value):
                return query_type

        return QueryType.OTHER

    def _store_metrics(self, metrics: QueryMetrics) -> None:
        """Store query metrics."""
        # Add to main storage
        self.queries.append(metrics)

        # Maintain size limit
        if len(self.queries) > self.max_stored_queries:
            self.queries = self.queries[-self.max_stored_queries :]

        # Update type counter
        self.query_count_by_type[metrics.query_type] += 1

        # Store slow queries separately
        if metrics.is_slow:
            self.slow_queries.append(metrics)
            if len(self.slow_queries) > self.max_slow_queries:
                self.slow_queries = self.slow_queries[-self.max_slow_queries :]

    def _update_query_pattern(self, statement: str, execution_time_ms: float) -> None:
        """Update query pattern statistics."""
        # Normalize query for pattern matching
        pattern = self._normalize_query(statement)

        if pattern not in self.query_patterns:
            self.query_patterns[pattern] = QueryPattern(pattern=pattern)

        query_pattern = self.query_patterns[pattern]
        query_pattern.count += 1
        query_pattern.total_time_ms += execution_time_ms
        query_pattern.max_time_ms = max(query_pattern.max_time_ms, execution_time_ms)
        query_pattern.min_time_ms = min(query_pattern.min_time_ms, execution_time_ms)
        query_pattern.avg_time_ms = query_pattern.total_time_ms / query_pattern.count

    def _normalize_query(self, statement: str) -> str:
        """Normalize query for pattern matching."""
        # Remove extra whitespace
        normalized = " ".join(statement.split())

        # Replace values with placeholders
        # Replace numbers
        normalized = re.sub(r"\b\d+\b", "?", normalized)
        # Replace quoted strings
        normalized = re.sub(r"'[^']*'", "?", normalized)
        normalized = re.sub(r'"[^"]*"', "?", normalized)

        # Truncate if too long
        if len(normalized) > 200:
            normalized = normalized[:200] + "..."

        return normalized

    def _log_slow_query(self, metrics: QueryMetrics) -> None:
        """Log a slow query."""
        logger.warning(
            f"Slow query detected ({metrics.execution_time_ms:.2f}ms): "
            f"{metrics.query[:100]}..."
        )

    def get_active_queries(self) -> List[Dict[str, Any]]:
        """Get currently executing queries."""
        active = []
        current_time = datetime.utcnow()

        for query_id, start_time in self.active_queries.items():
            duration = (current_time - start_time).total_seconds()
            active.append(
                {
                    "query_id": query_id,
                    "start_time": start_time.isoformat(),
                    "duration_seconds": duration,
                }
            )

        return active

    def get_query_statistics(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Get query statistics for a time window."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)

        # Filter queries within time window
        recent_queries = [q for q in self.queries if q.timestamp >= cutoff_time]

        if not recent_queries:
            return {
                "time_window_minutes": time_window_minutes,
                "total_queries": 0,
                "message": "No queries in time window",
            }

        # Calculate statistics
        total_time = sum(q.execution_time_ms for q in recent_queries)
        slow_count = sum(1 for q in recent_queries if q.is_slow)

        # Group by type
        queries_by_type = defaultdict(list)
        for q in recent_queries:
            queries_by_type[q.query_type].append(q)

        type_stats = {}
        for query_type, queries in queries_by_type.items():
            type_total_time = sum(q.execution_time_ms for q in queries)
            type_stats[query_type.value] = {
                "count": len(queries),
                "total_time_ms": type_total_time,
                "avg_time_ms": type_total_time / len(queries),
                "percentage": (len(queries) / len(recent_queries)) * 100,
            }

        return {
            "time_window_minutes": time_window_minutes,
            "total_queries": len(recent_queries),
            "total_time_ms": total_time,
            "avg_time_ms": total_time / len(recent_queries),
            "slow_queries": slow_count,
            "slow_query_percentage": (slow_count / len(recent_queries)) * 100,
            "queries_by_type": type_stats,
            "active_queries": len(self.active_queries),
        }

    def get_slow_query_report(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get report of slowest queries."""
        # Sort by execution time
        sorted_slow = sorted(
            self.slow_queries, key=lambda q: q.execution_time_ms, reverse=True
        )[:limit]

        return [
            {
                "query": q.query,
                "execution_time_ms": q.execution_time_ms,
                "timestamp": q.timestamp.isoformat(),
                "query_type": q.query_type.value,
                "rows_affected": q.rows_affected,
            }
            for q in sorted_slow
        ]

    def get_query_patterns_report(self, min_count: int = 5) -> List[Dict[str, Any]]:
        """Get report of query patterns."""
        # Filter patterns by minimum count
        patterns = [p for p in self.query_patterns.values() if p.count >= min_count]

        # Sort by total time
        sorted_patterns = sorted(patterns, key=lambda p: p.total_time_ms, reverse=True)

        return [
            {
                "pattern": p.pattern,
                "count": p.count,
                "total_time_ms": p.total_time_ms,
                "avg_time_ms": p.avg_time_ms,
                "max_time_ms": p.max_time_ms,
                "min_time_ms": p.min_time_ms,
            }
            for p in sorted_patterns
        ]

    def clear_statistics(self) -> None:
        """Clear all collected statistics."""
        self.queries.clear()
        self.query_patterns.clear()
        self.slow_queries.clear()
        self.query_count_by_type.clear()
        logger.info("Cleared query monitoring statistics")


# Global monitoring instance
query_monitor = QueryMonitoringService()


# Context manager for query monitoring
class MonitoredSession:
    """Context manager for monitored database sessions."""

    def __init__(
        self,
        session: Session,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
    ):
        """Initialize monitored session.

        Args:
            session: SQLAlchemy session
            user_id: Optional user ID for tracking
            endpoint: Optional API endpoint for tracking
        """
        self.session = session
        self.user_id = user_id
        self.endpoint = endpoint

    def __enter__(self) -> Session:
        """Enter context."""
        # Store context in session info
        if hasattr(self.session, "info"):
            self.session.info["user_id"] = self.user_id
            self.session.info["endpoint"] = self.endpoint
        return self.session

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context."""
        # Clear context
        if hasattr(self.session, "info"):
            self.session.info.pop("user_id", None)
            self.session.info.pop("endpoint", None)


# Export components
__all__ = [
    "QueryType",
    "QueryMetrics",
    "QueryPattern",
    "QueryMonitoringService",
    "query_monitor",
    "MonitoredSession",
]
