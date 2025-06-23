"""Database sharding implementation for horizontal scaling.

This module provides database sharding capabilities to distribute data
across multiple database instances for improved scalability.

Access control note: This module manages database connections that may contain PHI.
All database operations involving patient data require appropriate access levels
and are subject to audit logging for HIPAA compliance.
"""

import hashlib
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

# Access control for PHI database operations

logger = get_logger(__name__)


class ShardingStrategy(str, Enum):
    """Strategies for data sharding."""

    HASH = "hash"  # Hash-based sharding
    RANGE = "range"  # Range-based sharding
    LIST = "list"  # List-based sharding
    GEOGRAPHIC = "geographic"  # Geography-based sharding
    COMPOSITE = "composite"  # Composite key sharding


class ShardConfig(BaseModel):
    """Configuration for a database shard."""

    shard_id: str = Field(..., description="Unique shard identifier")
    connection_url: str = Field(..., description="Database connection URL")

    # Shard key ranges (for range-based sharding)
    min_key: Optional[Union[int, str]] = Field(None, description="Minimum key value")
    max_key: Optional[Union[int, str]] = Field(None, description="Maximum key value")

    # Geographic sharding
    regions: List[str] = Field(
        default_factory=list, description="Regions served by this shard"
    )

    # List sharding
    key_values: List[Union[int, str]] = Field(
        default_factory=list, description="Specific key values"
    )

    # Capacity and state
    weight: int = Field(default=1, description="Shard weight for load distribution")
    is_active: bool = Field(default=True, description="Whether shard is active")
    read_only: bool = Field(default=False, description="Whether shard is read-only")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_migrated: Optional[datetime] = Field(
        None, description="Last migration timestamp"
    )


class ShardKey:
    """Shard key definition."""

    def __init__(
        self,
        column_name: str,
        strategy: ShardingStrategy = ShardingStrategy.HASH,
        shard_count: int = 4,
    ):
        """Initialize shard key.

        Args:
            column_name: Column to use for sharding
            strategy: Sharding strategy
            shard_count: Number of shards (for hash strategy)
        """
        self.column_name = column_name
        self.strategy = strategy
        self.shard_count = shard_count

    def get_shard_id(self, key_value: Any) -> str:
        """Get shard ID for a key value.

        Args:
            key_value: Value of the shard key

        Returns:
            Shard ID
        """
        if self.strategy == ShardingStrategy.HASH:
            # Hash the key value
            if isinstance(key_value, str):
                # MD5 is used here only for hashing distribution, not for security
                hash_value = int(
                    hashlib.md5(key_value.encode(), usedforsecurity=False).hexdigest(),
                    16,
                )
            else:
                hash_value = hash(str(key_value))

            # Determine shard
            shard_index = hash_value % self.shard_count
            return f"shard_{shard_index}"

        elif self.strategy == ShardingStrategy.RANGE:
            # Range-based sharding
            # Requires shard configuration with min/max keys
            # This is typically configured in the shard manager
            # For now, return a placeholder that the shard manager will resolve
            return f"range_shard_for_{key_value}"

        elif self.strategy == ShardingStrategy.LIST:
            # List-based sharding
            # The shard is determined by exact key value match
            # This is typically configured in the shard manager
            return f"list_shard_for_{key_value}"

        elif self.strategy == ShardingStrategy.GEOGRAPHIC:
            # Geographic sharding based on region codes
            # Expects key_value to be a region code or location identifier
            if isinstance(key_value, str):
                # Extract region prefix (e.g., "US-EAST", "EU-WEST")
                region_prefix = (
                    key_value.split("-")[0] if "-" in key_value else key_value
                )
                return f"geo_shard_{region_prefix.lower()}"
            else:
                # Fallback to hash if not a string
                return self._fallback_to_hash(key_value)

        elif self.strategy == ShardingStrategy.COMPOSITE:
            # Composite key sharding
            # Expects key_value to be a tuple or dict
            if isinstance(key_value, (tuple, list)):
                # Combine multiple key components
                composite_str = "_".join(str(k) for k in key_value)
                hash_value = int(
                    hashlib.md5(
                        composite_str.encode(), usedforsecurity=False
                    ).hexdigest(),
                    16,
                )
                shard_index = hash_value % self.shard_count
                return f"composite_shard_{shard_index}"
            elif isinstance(key_value, dict):
                # Sort dict keys for consistent hashing
                sorted_items = sorted(key_value.items())
                composite_str = "_".join(f"{k}:{v}" for k, v in sorted_items)
                hash_value = int(
                    hashlib.md5(
                        composite_str.encode(), usedforsecurity=False
                    ).hexdigest(),
                    16,
                )
                shard_index = hash_value % self.shard_count
                return f"composite_shard_{shard_index}"
            else:
                # Fallback to hash if not composite
                return self._fallback_to_hash(key_value)

        else:
            # Unknown strategy
            raise ValueError(f"Unknown sharding strategy: {self.strategy}")

    def _fallback_to_hash(self, key_value: Any) -> str:
        """Fallback to hash-based sharding for non-standard key types."""
        hash_value = hash(str(key_value))
        shard_index = abs(hash_value) % self.shard_count
        return f"shard_{shard_index}"


class ShardedTable:
    """Base class for sharded tables."""

    # Override in subclasses
    __shard_key__: Optional[ShardKey] = None  # ShardKey instance
    __tablename__: Optional[str] = None  # Table name

    @classmethod
    def get_shard_key(cls) -> ShardKey:
        """Get the shard key for this table."""
        if cls.__shard_key__ is None:
            raise ValueError(f"No shard key defined for {cls.__name__}")
        return cls.__shard_key__

    @classmethod
    def get_shard_id(cls, key_value: Any) -> str:
        """Get shard ID for a key value."""
        return cls.get_shard_key().get_shard_id(key_value)


class DatabaseShardManager:
    """Manager for database sharding."""

    def __init__(self) -> None:
        """Initialize shard manager."""
        self.shards: Dict[str, ShardConfig] = {}
        self.engines: Dict[str, Engine] = {}
        self.session_factories: Dict[str, sessionmaker] = {}
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self.shard_maps: Dict[str, Dict[str, str]] = {}  # table -> key -> shard_id

    def add_shard(self, shard: ShardConfig) -> None:
        """Add a shard configuration.

        Args:
            shard: Shard configuration
        """
        try:
            # Create engine
            engine = create_engine(
                shard.connection_url,
                pool_size=10,
                max_overflow=5,
                pool_pre_ping=True,
                pool_recycle=3600,
            )

            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            # Store configuration
            self.shards[shard.shard_id] = shard
            self.engines[shard.shard_id] = engine
            self.session_factories[shard.shard_id] = sessionmaker(bind=engine)

            logger.info(f"Added shard: {shard.shard_id}")

        except Exception as e:
            logger.error(f"Failed to add shard {shard.shard_id}: {e}")
            raise

    def get_shard_for_key(
        self,
        table_class: Type[ShardedTable],
        key_value: Any,
    ) -> str:
        """Get shard ID for a specific key value.

        Args:
            table_class: Sharded table class
            key_value: Shard key value

        Returns:
            Shard ID
        """
        shard_key = table_class.get_shard_key()
        initial_shard_id = table_class.get_shard_id(key_value)

        # For hash and composite strategies, the shard ID is already resolved
        if shard_key.strategy in [ShardingStrategy.HASH, ShardingStrategy.COMPOSITE]:
            # Verify the shard exists
            if initial_shard_id in self.shards:
                return initial_shard_id
            else:
                # Fallback to first available shard
                logger.warning(f"Shard {initial_shard_id} not found, using fallback")
                for shard_id, shard in self.shards.items():
                    if shard.is_active and not shard.read_only:
                        return shard_id
                raise ValueError("No active writable shards available")

        # For range-based sharding, find the appropriate shard
        elif shard_key.strategy == ShardingStrategy.RANGE:
            for shard_id, shard in self.shards.items():
                if not shard.is_active:
                    continue

                # Check if key falls within shard's range
                if shard.min_key is not None and shard.max_key is not None:
                    # Convert to comparable types
                    if isinstance(key_value, str):
                        if str(shard.min_key) <= key_value <= str(shard.max_key):
                            return shard_id
                    elif isinstance(key_value, (int, float)):
                        try:
                            min_val = float(shard.min_key)
                            max_val = float(shard.max_key)
                            if min_val <= float(key_value) <= max_val:
                                return shard_id
                        except (ValueError, TypeError):
                            pass

            # No matching range found, use fallback
            logger.warning(f"No range shard found for key {key_value}")
            return self._get_fallback_shard()

        # For list-based sharding, find exact match
        elif shard_key.strategy == ShardingStrategy.LIST:
            for shard_id, shard in self.shards.items():
                if not shard.is_active:
                    continue

                # Check if key is in shard's list
                if key_value in shard.key_values:
                    return shard_id

            # No matching list found, use fallback
            logger.warning(f"No list shard found for key {key_value}")
            return self._get_fallback_shard()

        # For geographic sharding, match by region
        elif shard_key.strategy == ShardingStrategy.GEOGRAPHIC:
            # Extract region from initial shard ID
            if initial_shard_id.startswith("geo_shard_"):
                region = initial_shard_id.replace("geo_shard_", "").upper()

                # Find shard serving this region
                for shard_id, shard in self.shards.items():
                    if not shard.is_active:
                        continue

                    if region in [r.upper() for r in shard.regions]:
                        return shard_id

                    # Also check partial matches (e.g., "US" matches "US-EAST")
                    for shard_region in shard.regions:
                        if region.startswith(
                            shard_region.upper()
                        ) or shard_region.upper().startswith(region):
                            return shard_id

            # No matching region found, use fallback
            logger.warning(f"No geographic shard found for {initial_shard_id}")
            return self._get_fallback_shard()

        else:
            # Unknown strategy, use initial shard ID
            logger.warning(
                f"Unknown strategy {shard_key.strategy}, using {initial_shard_id}"
            )
            return initial_shard_id

    def _get_fallback_shard(self) -> str:
        """Get a fallback shard when no specific match is found."""
        # Find first active, writable shard
        for shard_id, shard in self.shards.items():
            if shard.is_active and not shard.read_only:
                return shard_id

        # If no writable shards, use any active shard
        for shard_id, shard in self.shards.items():
            if shard.is_active:
                logger.warning("Using read-only shard as fallback")
                return shard_id

        raise ValueError("No active shards available")

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("get_database_session")
    def get_session(self, shard_id: str) -> Session:
        """Get a session for a specific shard.

        Args:
            shard_id: Shard identifier

        Returns:
            Database session
        """
        if shard_id not in self.session_factories:
            raise ValueError(f"Unknown shard: {shard_id}")

        session: Session = self.session_factories[shard_id]()
        session.info["shard_id"] = shard_id
        return session

    def get_session_for_key(
        self,
        table_class: Type[ShardedTable],
        key_value: Any,
    ) -> Session:
        """Get a session for a specific key value.

        Args:
            table_class: Sharded table class
            key_value: Shard key value

        Returns:
            Database session for the appropriate shard
        """
        shard_id = self.get_shard_for_key(table_class, key_value)
        session: Session = self.get_session(shard_id)
        return session

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("query_sharded_data")
    def query_all_shards(
        self,
        table_class: Type[ShardedTable],
        filter_func: Optional[Callable] = None,
    ) -> List[Any]:
        """Query across all shards.

        Args:
            table_class: Table class to query
            filter_func: Optional filter function

        Returns:
            Combined results from all shards
        """
        results = []

        for shard_id, shard in self.shards.items():
            if not shard.is_active:
                continue

            session = self.get_session(shard_id)
            try:
                query = session.query(table_class)

                if filter_func:
                    query = filter_func(query)

                shard_results = query.all()
                results.extend(shard_results)

            finally:
                session.close()

        return results

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("migrate_patient_record")
    def migrate_record(
        self,
        record: Any,
        from_shard: str,
        to_shard: str,
        table_class: Type[ShardedTable],
    ) -> bool:
        """Migrate a record between shards.

        Args:
            record: Record to migrate
            from_shard: Source shard ID
            to_shard: Destination shard ID
            table_class: Table class

        Returns:
            True if successful
        """
        from_session = self.get_session(from_shard)
        to_session = self.get_session(to_shard)

        try:
            # Begin transactions
            from_session.begin()
            to_session.begin()

            # Copy record to new shard
            # Note: This is simplified - actual implementation would handle relationships
            new_record = table_class(**record.__dict__)
            to_session.add(new_record)

            # Delete from old shard
            from_session.delete(record)

            # Commit both transactions
            to_session.commit()
            from_session.commit()

            logger.info(f"Migrated record from {from_shard} to {to_shard}")
            return True

        except (IntegrityError, SQLAlchemyError, AttributeError, ValueError) as e:
            logger.error(f"Migration failed: {e}")
            from_session.rollback()
            to_session.rollback()
            return False

        finally:
            from_session.close()
            to_session.close()

    def rebalance_shards(
        self,
        table_class: Type[ShardedTable],
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Rebalance data across shards.

        Args:
            table_class: Table class to rebalance
            dry_run: If True, only simulate rebalancing

        Returns:
            Rebalancing plan/results
        """
        # Count records per shard
        shard_counts = {}
        for shard_id, shard in self.shards.items():
            if not shard.is_active:
                continue

            session = self.get_session(shard_id)
            try:
                count = session.query(table_class).count()
                shard_counts[shard_id] = count
            finally:
                session.close()

        # Calculate target distribution
        total_records = sum(shard_counts.values())
        active_shards = [s for s in self.shards.values() if s.is_active]

        if not active_shards:
            return {"error": "No active shards"}

        # Weight-based distribution
        total_weight = sum(s.weight for s in active_shards)
        target_counts = {}

        for shard in active_shards:
            target_counts[shard.shard_id] = int(
                (shard.weight / total_weight) * total_records
            )

        # Calculate migrations needed
        migrations = []
        for shard_id, current_count in shard_counts.items():
            target_count = target_counts.get(shard_id, 0)

            if current_count > target_count:
                # Need to migrate out
                excess = current_count - target_count
                migrations.append(
                    {
                        "from_shard": shard_id,
                        "count": excess,
                        "direction": "out",
                    }
                )
            elif current_count < target_count:
                # Need to migrate in
                deficit = target_count - current_count
                migrations.append(
                    {
                        "from_shard": shard_id,
                        "count": deficit,
                        "direction": "in",
                    }
                )

        return {
            "current_distribution": shard_counts,
            "target_distribution": target_counts,
            "migrations_needed": migrations,
            "dry_run": dry_run,
        }

    def get_shard_statistics(self) -> Dict[str, Any]:
        """Get statistics for all shards."""
        stats: Dict[str, Any] = {
            "total_shards": len(self.shards),
            "active_shards": sum(1 for s in self.shards.values() if s.is_active),
            "shards": {},
        }

        for shard_id, shard in self.shards.items():
            engine = self.engines.get(shard_id)

            shard_stats = {
                "is_active": shard.is_active,
                "read_only": shard.read_only,
                "weight": shard.weight,
                "regions": shard.regions,
            }

            # Get connection pool stats if available
            if engine and hasattr(engine.pool, "size"):
                shard_stats["pool_size"] = engine.pool.size()
                shard_stats["pool_checked_out"] = getattr(
                    engine.pool, "checkedout", lambda: 0
                )()

            shards_dict = stats["shards"]
            if isinstance(shards_dict, dict):
                shards_dict[shard_id] = shard_stats

        return stats


# Global shard manager
shard_manager = DatabaseShardManager()


# Context managers for sharded operations
@contextmanager
def sharded_session(table_class: Type[ShardedTable], key_value: Any) -> Any:
    """Context manager for sharded database session.

    Args:
        table_class: Sharded table class
        key_value: Shard key value

    Yields:
        Database session for the appropriate shard
    """
    session = shard_manager.get_session_for_key(table_class, key_value)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def all_shards_session() -> Any:
    """Context manager for operations across all shards.

    Yields:
        Dictionary of shard_id -> session
    """
    sessions = {}

    try:
        # Open sessions for all active shards
        for shard_id, shard in shard_manager.shards.items():
            if shard.is_active:
                sessions[shard_id] = shard_manager.get_session(shard_id)

        yield sessions

        # Commit all sessions
        for session in sessions.values():
            session.commit()

    except Exception:
        # Rollback all sessions on error
        for session in sessions.values():
            session.rollback()
        raise

    finally:
        # Close all sessions
        for session in sessions.values():
            session.close()


# Decorator for sharded queries
def sharded_query(shard_key_param: str = "shard_key") -> Callable:
    """Decorate functions that perform sharded queries.

    Args:
        shard_key_param: Parameter name containing the shard key value
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract shard key value
            shard_key_value = kwargs.get(shard_key_param)
            if not shard_key_value:
                raise ValueError(f"Missing required parameter: {shard_key_param}")

            # Get table class (assumes first argument is self with table_class attribute)
            if args and hasattr(args[0], "table_class"):
                table_class = args[0].table_class
            else:
                raise ValueError("Cannot determine table class for sharding")

            # Get appropriate session
            with sharded_session(table_class, shard_key_value) as session:
                # Inject session into kwargs
                kwargs["session"] = session
                return func(*args, **kwargs)

        return wrapper

    return decorator


# Export components
__all__ = [
    "ShardingStrategy",
    "ShardConfig",
    "ShardKey",
    "ShardedTable",
    "DatabaseShardManager",
    "shard_manager",
    "sharded_session",
    "all_shards_session",
    "sharded_query",
]
