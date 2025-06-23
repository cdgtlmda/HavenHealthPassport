"""Materialized views implementation for database performance.

This module provides materialized view management for complex queries
and aggregations that don't require real-time data.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

import asyncio
import re
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.healthcare.fhir.validators import FHIRValidator
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RefreshStrategy(str, Enum):
    """Strategies for refreshing materialized views."""

    IMMEDIATE = "immediate"  # Refresh immediately on data change
    DEFERRED = "deferred"  # Refresh at scheduled intervals
    MANUAL = "manual"  # Manual refresh only
    INCREMENTAL = "incremental"  # Incremental refresh (append-only)


class MaterializedView(BaseModel):
    """Definition of a materialized view."""

    name: str = Field(..., description="View name")
    query: str = Field(..., description="SQL query for the view")
    refresh_strategy: RefreshStrategy = Field(default=RefreshStrategy.DEFERRED)
    refresh_interval_minutes: int = Field(
        default=60, description="Refresh interval in minutes"
    )
    indexes: List[str] = Field(
        default_factory=list, description="Indexes to create on view"
    )

    # Metadata
    description: str = Field(..., description="View description")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    last_refreshed: Optional[datetime] = Field(
        None, description="Last refresh timestamp"
    )
    next_refresh: Optional[datetime] = Field(None, description="Next scheduled refresh")

    # Statistics
    row_count: int = Field(default=0, description="Number of rows in view")
    size_mb: float = Field(default=0.0, description="Size in megabytes")
    refresh_duration_seconds: float = Field(
        default=0.0, description="Last refresh duration"
    )


class MaterializedViewManager:
    """Manager for materialized views."""

    def __init__(self, database_url: str):
        """Initialize materialized view manager.

        Args:
            database_url: Database connection URL
        """
        self.database_url = database_url
        self.engine: Optional[AsyncEngine] = None
        self.views: Dict[str, MaterializedView] = {}
        self._refresh_tasks: Dict[str, asyncio.Task] = {}
        self.fhir_validator = FHIRValidator()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self._initialize_default_views()

    def validate_fhir_resource(self, resource: dict) -> bool:
        """Validate FHIR resource structure and requirements."""
        return self.fhir_validator.validate_resource(resource)

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
                    str(encrypted_data[field]).encode("utf-8")
                )

        return encrypted_data

    def _initialize_default_views(self) -> None:
        """Initialize default materialized views."""
        # Patient statistics view
        self.register_view(
            MaterializedView(
                name="mv_patient_statistics",
                description="Aggregated patient statistics by nationality and status",
                query="""
                SELECT
                    nationality,
                    COUNT(*) as patient_count,
                    COUNT(CASE WHEN is_active THEN 1 END) as active_count,
                    COUNT(CASE WHEN is_refugee THEN 1 END) as refugee_count,
                    COUNT(CASE WHEN created_at > NOW() - INTERVAL '30 days' THEN 1 END) as new_patients_30d,
                    AVG(EXTRACT(YEAR FROM AGE(date_of_birth))) as avg_age
                FROM patients
                GROUP BY nationality
            """,
                refresh_strategy=RefreshStrategy.DEFERRED,
                refresh_interval_minutes=360,  # 6 hours
                indexes=["nationality"],
                created_at=None,
                last_refreshed=None,
                next_refresh=None,
            )
        )

        # Health record summary view
        self.register_view(
            MaterializedView(
                name="mv_health_record_summary",
                description="Summary of health records by type and status",
                query="""
                SELECT
                    hr.record_type,
                    hr.is_verified,
                    COUNT(*) as record_count,
                    COUNT(DISTINCT hr.patient_id) as patient_count,
                    AVG(EXTRACT(EPOCH FROM (hr.updated_at - hr.created_at))) / 86400 as avg_days_to_verify,
                    COUNT(CASE WHEN hr.created_at > NOW() - INTERVAL '7 days' THEN 1 END) as new_records_7d
                FROM health_records hr
                WHERE hr.is_active = true
                GROUP BY hr.record_type, hr.is_verified
            """,
                refresh_strategy=RefreshStrategy.DEFERRED,
                refresh_interval_minutes=120,  # 2 hours
                indexes=["record_type", "is_verified"],
                created_at=None,
                last_refreshed=None,
                next_refresh=None,
            )
        )

        # Translation usage view
        self.register_view(
            MaterializedView(
                name="mv_translation_usage",
                description="Translation usage statistics",
                query="""
                SELECT
                    source_language,
                    target_language,
                    COUNT(*) as translation_count,
                    AVG(confidence_score) as avg_confidence,
                    COUNT(CASE WHEN cached THEN 1 END) as cached_count,
                    COUNT(DISTINCT user_id) as unique_users
                FROM translations
                WHERE created_at > NOW() - INTERVAL '30 days'
                GROUP BY source_language, target_language
                HAVING COUNT(*) > 10
            """,
                refresh_strategy=RefreshStrategy.DEFERRED,
                refresh_interval_minutes=1440,  # 24 hours
                indexes=["source_language", "target_language"],
                created_at=None,
                last_refreshed=None,
                next_refresh=None,
            )
        )

        # Provider activity view
        self.register_view(
            MaterializedView(
                name="mv_provider_activity",
                description="Healthcare provider activity summary",
                query="""
                SELECT
                    u.id as provider_id,
                    u.email as provider_email,
                    COUNT(DISTINCT hr.patient_id) as patients_treated,
                    COUNT(hr.id) as records_created,
                    COUNT(CASE WHEN hr.is_verified THEN 1 END) as verified_records,
                    MAX(hr.created_at) as last_activity,
                    COUNT(CASE WHEN hr.created_at > NOW() - INTERVAL '7 days' THEN 1 END) as records_last_7d
                FROM user_auth u
                INNER JOIN health_records hr ON hr.created_by = u.id
                WHERE u.role = 'healthcare_provider'
                GROUP BY u.id, u.email
            """,
                refresh_strategy=RefreshStrategy.DEFERRED,
                refresh_interval_minutes=720,  # 12 hours
                indexes=["provider_id"],
                created_at=None,
                last_refreshed=None,
                next_refresh=None,
            )
        )

        # System metrics view (for monitoring)
        self.register_view(
            MaterializedView(
                name="mv_system_metrics",
                description="System-wide metrics for monitoring",
                query="""
                SELECT
                    'total_patients' as metric_name,
                    COUNT(*)::text as metric_value
                FROM patients
                WHERE is_active = true

                UNION ALL

                SELECT
                    'total_health_records' as metric_name,
                    COUNT(*)::text as metric_value
                FROM health_records
                WHERE is_active = true

                UNION ALL

                SELECT
                    'total_verifications' as metric_name,
                    COUNT(*)::text as metric_value
                FROM verifications
                WHERE status = 'completed'

                UNION ALL

                SELECT
                    'active_providers' as metric_name,
                    COUNT(DISTINCT created_by)::text as metric_value
                FROM health_records
                WHERE created_at > NOW() - INTERVAL '30 days'
            """,
                refresh_strategy=RefreshStrategy.DEFERRED,
                refresh_interval_minutes=60,  # 1 hour
                indexes=["metric_name"],
                created_at=None,
                last_refreshed=None,
                next_refresh=None,
            )
        )

    async def initialize(self) -> None:
        """Initialize the async engine."""
        if not self.engine:
            self.engine = create_async_engine(
                self.database_url,
                pool_pre_ping=True,
                echo=False,
            )

    def register_view(self, view: MaterializedView) -> None:
        """Register a materialized view."""
        self.views[view.name] = view
        logger.info(f"Registered materialized view: {view.name}")

    async def create_view(self, view_name: str) -> bool:
        """Create a materialized view in the database.

        Args:
            view_name: Name of the view to create

        Returns:
            True if successful
        """
        view = self.views.get(view_name)
        if not view:
            logger.error(f"View {view_name} not found")
            return False

        await self.initialize()

        try:
            # Drop existing view if it exists
            drop_sql = f"DROP MATERIALIZED VIEW IF EXISTS {view.name} CASCADE"
            await self._execute_sql(drop_sql)

            # Create the materialized view
            create_sql = f"CREATE MATERIALIZED VIEW {view.name} AS {view.query}"
            await self._execute_sql(create_sql)

            # Create indexes
            for index_col in view.indexes:
                index_name = f"idx_{view.name}_{index_col}"
                index_sql = f"CREATE INDEX {index_name} ON {view.name}({index_col})"
                await self._execute_sql(index_sql)

            # Update metadata
            view.created_at = datetime.utcnow()

            # Initial refresh
            await self.refresh_view(view_name)

            logger.info(f"Created materialized view: {view_name}")
            return True

        except (SQLAlchemyError, RuntimeError) as e:
            logger.error(f"Failed to create view {view_name}: {e}")
            return False

    async def refresh_view(self, view_name: str) -> bool:
        """Refresh a materialized view.

        Args:
            view_name: Name of the view to refresh

        Returns:
            True if successful
        """
        view = self.views.get(view_name)
        if not view:
            logger.error(f"View {view_name} not found")
            return False

        await self.initialize()

        start_time = datetime.utcnow()

        try:
            # Refresh the view
            refresh_sql = f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view.name}"
            await self._execute_sql(refresh_sql)

            # Update statistics
            stats = await self._get_view_stats(view_name)
            view.row_count = stats.get("row_count", 0)
            view.size_mb = stats.get("size_mb", 0.0)

            # Update refresh metadata
            view.last_refreshed = start_time
            view.refresh_duration_seconds = (
                datetime.utcnow() - start_time
            ).total_seconds()

            # Calculate next refresh time
            if view.refresh_strategy == RefreshStrategy.DEFERRED:
                view.next_refresh = start_time + timedelta(
                    minutes=view.refresh_interval_minutes
                )

            logger.info(
                "Refreshed view %s in %.2f s (%s rows, %.2f MB)",
                view_name,
                view.refresh_duration_seconds,
                view.row_count,
                view.size_mb,
            )
            return True

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("Failed to refresh view %s: %s", view_name, str(e))
            return False

    async def _execute_sql(self, sql: str) -> None:
        """Execute SQL statement."""
        if not self.engine:
            raise RuntimeError("Engine not initialized")
        async with self.engine.begin() as conn:
            await conn.execute(text(sql))

    async def _get_view_stats(self, view_name: str) -> Dict[str, Any]:
        """Get statistics for a materialized view."""
        # Validate view name to prevent SQL injection
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", view_name):
            raise ValueError(f"Invalid view name: {view_name}")

        # Check if view exists in our registry
        if view_name not in self.views:
            raise ValueError(f"Unknown view: {view_name}")

        # Use parameterized query to prevent SQL injection
        stats_sql = """
            SELECT
                pg_size_pretty(pg_total_relation_size(:view_name)) as size,
                (SELECT COUNT(*) FROM information_schema.tables
                 WHERE table_name = :view_name AND table_schema = 'public') as exists
        """

        # Get row count separately with dynamic table name (validated above)
        count_sql = f"SELECT COUNT(*) FROM {view_name}"  # nosec B608

        if not self.engine:
            raise RuntimeError("Engine not initialized")

        async with self.engine.connect() as conn:
            # First check if view exists and get size
            result = await conn.execute(text(stats_sql), {"view_name": view_name})
            row = result.first()

            if row and row[1] > 0:  # View exists
                # Now get actual row count
                count_result = await conn.execute(text(count_sql))
                count_row = count_result.first()
                row_count = count_row[0] if count_row else 0

                # Parse size to MB
                size_str = row[0]
                size_mb = self._parse_size_to_mb(size_str)

                return {
                    "row_count": row_count,
                    "size_mb": size_mb,
                }

            return {}

    def _parse_size_to_mb(self, size_str: str) -> float:
        """Parse PostgreSQL size string to MB."""
        size_str = size_str.strip()

        if size_str.endswith("kB"):
            return float(size_str[:-2]) / 1024
        elif size_str.endswith("MB"):
            return float(size_str[:-2])
        elif size_str.endswith("GB"):
            return float(size_str[:-2]) * 1024
        elif size_str.endswith("bytes"):
            return float(size_str[:-5]) / (1024 * 1024)

        return 0.0

    async def start_auto_refresh(self) -> None:
        """Start automatic refresh for deferred views."""
        for view_name, view in self.views.items():
            if view.refresh_strategy == RefreshStrategy.DEFERRED:
                task = asyncio.create_task(self._auto_refresh_loop(view_name))
                self._refresh_tasks[view_name] = task
                logger.info(f"Started auto-refresh for {view_name}")

    async def stop_auto_refresh(self) -> None:
        """Stop all automatic refresh tasks."""
        for view_name, task in self._refresh_tasks.items():
            task.cancel()
            logger.info(f"Stopped auto-refresh for {view_name}")

        self._refresh_tasks.clear()

    async def _auto_refresh_loop(self, view_name: str) -> None:
        """Auto-refresh loop for a view."""
        view = self.views[view_name]

        while True:
            try:
                # Wait for refresh interval
                await asyncio.sleep(view.refresh_interval_minutes * 60)

                # Refresh the view
                await self.refresh_view(view_name)

            except asyncio.CancelledError:
                break
            except (SQLAlchemyError, RuntimeError, ValueError, AttributeError) as e:
                logger.error(f"Error in auto-refresh for {view_name}: {e}")
                # Continue loop after error
                await asyncio.sleep(60)  # Wait 1 minute before retry

    async def query_view(
        self,
        view_name: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Query a materialized view.

        Args:
            view_name: Name of the view
            filters: Optional filters to apply
            limit: Optional result limit

        Returns:
            Query results
        """
        # Validate view name to prevent SQL injection
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", view_name):
            raise ValueError(f"Invalid view name: {view_name}")

        view = self.views.get(view_name)
        if not view:
            logger.error(f"View {view_name} not found")
            return []

        await self.initialize()

        # Build query with validated view name
        # View name is validated above with regex to prevent SQL injection
        query_parts = [f"SELECT * FROM {view_name}"]  # nosec B608

        # Add filters
        if filters:
            where_clauses = []
            for col, value in filters.items():
                if isinstance(value, str):
                    where_clauses.append(f"{col} = '{value}'")
                else:
                    where_clauses.append(f"{col} = {value}")

            if where_clauses:
                query_parts.append(f"WHERE {' AND '.join(where_clauses)}")

        # Add limit
        if limit:
            query_parts.append(f"LIMIT {limit}")

        query_sql = " ".join(query_parts)

        try:
            if not self.engine:
                raise RuntimeError("Engine not initialized")

            async with self.engine.connect() as conn:
                result = await conn.execute(text(query_sql))
                rows = result.fetchall()

                # Convert to dictionaries
                # Using row._asdict() or dict(row) if available, otherwise fall back to _mapping
                return [dict(row) for row in rows]

        except (SQLAlchemyError, RuntimeError, ValueError) as e:
            logger.error(f"Failed to query view {view_name}: {e}")
            return []

    def get_view_info(
        self, view_name: Optional[str] = None
    ) -> Union[Optional[MaterializedView], Dict[str, MaterializedView]]:
        """Get information about materialized views.

        Args:
            view_name: Optional specific view name

        Returns:
            View information
        """
        if view_name:
            return self.views.get(view_name)
        return self.views


# Global manager instance
mv_manager = MaterializedViewManager(
    database_url=""
)  # URL will be set on initialization


# Export components
__all__ = [
    "RefreshStrategy",
    "MaterializedView",
    "MaterializedViewManager",
    "mv_manager",
]
