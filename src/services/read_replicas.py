"""Read replica configuration for database scalability.

This module provides read replica management for distributing read queries
across multiple database instances to improve performance and availability.
"""

import random
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ReplicaState(str, Enum):
    """State of a read replica."""

    ACTIVE = "active"  # Replica is active and healthy
    LAGGING = "lagging"  # Replica is lagging behind master
    OFFLINE = "offline"  # Replica is offline
    SYNCING = "syncing"  # Replica is catching up
    MAINTENANCE = "maintenance"  # Replica is in maintenance


class LoadBalancingStrategy(str, Enum):
    """Load balancing strategies for read replicas."""

    ROUND_ROBIN = "round_robin"  # Distribute evenly
    RANDOM = "random"  # Random selection
    LEAST_CONNECTIONS = "least_connections"  # Fewest active connections
    LATENCY_BASED = "latency_based"  # Lowest latency
    WEIGHTED = "weighted"  # Weighted distribution


class ReadReplica(BaseModel):
    """Configuration for a read replica."""

    name: str = Field(..., description="Replica name")
    connection_url: str = Field(..., description="Database connection URL")
    region: Optional[str] = Field(None, description="AWS region or datacenter")
    weight: int = Field(default=1, description="Weight for load balancing")
    max_lag_seconds: int = Field(default=10, description="Maximum acceptable lag")

    # State
    state: ReplicaState = Field(default=ReplicaState.ACTIVE)
    last_check: Optional[datetime] = Field(None)
    lag_seconds: int = Field(default=0)
    active_connections: int = Field(default=0)

    # Performance metrics
    avg_latency_ms: float = Field(default=0.0)
    error_count: int = Field(default=0)
    success_count: int = Field(default=0)

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True


class ReadReplicaManager:
    """Manager for read replica connections."""

    def __init__(
        self,
        master_url: str,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
    ):
        """Initialize read replica manager.

        Args:
            master_url: Master database connection URL
            strategy: Load balancing strategy
        """
        self.master_url = master_url
        self.strategy = strategy
        self.replicas: Dict[str, ReadReplica] = {}
        self.engines: Dict[str, Engine] = {}
        self.session_factories: Dict[str, sessionmaker] = {}

        # Round-robin state
        self._round_robin_index = 0

        # Initialize master connection
        self._initialize_master()

    def _initialize_master(self) -> None:
        """Initialize master database connection."""
        self.master_engine = create_engine(
            self.master_url,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self.master_session_factory = sessionmaker(bind=self.master_engine)
        logger.info("Initialized master database connection")

    def add_replica(self, replica: ReadReplica) -> None:
        """Add a read replica.

        Args:
            replica: Read replica configuration
        """
        try:
            # Create engine for replica
            engine = create_engine(
                replica.connection_url,
                pool_size=10,
                max_overflow=5,
                pool_pre_ping=True,
                pool_recycle=3600,
                connect_args={"connect_timeout": 5},
            )

            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            # Store engine and session factory
            self.engines[replica.name] = engine
            self.session_factories[replica.name] = sessionmaker(bind=engine)
            self.replicas[replica.name] = replica

            # Set up monitoring
            self._setup_replica_monitoring(replica.name, engine)

            logger.info(f"Added read replica: {replica.name}")

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error(f"Failed to add replica {replica.name}: {e}")
            replica.state = ReplicaState.OFFLINE
            self.replicas[replica.name] = replica

    def _setup_replica_monitoring(self, replica_name: str, engine: Engine) -> None:
        """Set up monitoring for a replica."""

        @event.listens_for(engine, "connect")
        def receive_connect(dbapi_conn: Any, connection_record: Any) -> None:
            """Track new connections."""
            _ = dbapi_conn  # Will be used for connection-specific settings
            _ = connection_record  # Will be used for connection tracking
            replica = self.replicas.get(replica_name)
            if replica:
                replica.active_connections += 1

        @event.listens_for(engine, "close")
        def receive_close(dbapi_conn: Any, connection_record: Any) -> None:
            """Track closed connections."""
            _ = dbapi_conn  # Will be used for connection cleanup
            _ = connection_record  # Will be used for connection tracking
            replica = self.replicas.get(replica_name)
            if replica:
                replica.active_connections = max(0, replica.active_connections - 1)

    def get_read_session(
        self,
        prefer_region: Optional[str] = None,
        max_lag_seconds: Optional[int] = None,
    ) -> Session:
        """Get a session for read queries.

        Args:
            prefer_region: Preferred region for geo-based routing
            max_lag_seconds: Maximum acceptable lag

        Returns:
            Database session for reads
        """
        # Get available replicas
        available_replicas = self._get_available_replicas(
            prefer_region=prefer_region,
            max_lag_seconds=max_lag_seconds,
        )

        if not available_replicas:
            logger.warning("No available read replicas, using master")
            return self.master_session_factory()

        # Select replica based on strategy
        replica = self._select_replica(available_replicas)

        # Create session
        session_factory = self.session_factories.get(replica.name)
        if session_factory:
            session: Session = session_factory()
            # Mark session as read-only
            session.info["read_only"] = True
            session.info["replica_name"] = replica.name
            return session
        else:
            logger.error(f"No session factory for replica {replica.name}")
            return self.master_session_factory()

    def get_write_session(self) -> Session:
        """Get a session for write queries (always uses master).

        Returns:
            Database session for writes
        """
        session = self.master_session_factory()
        session.info["read_only"] = False
        session.info["replica_name"] = "master"
        return session

    def _get_available_replicas(
        self,
        prefer_region: Optional[str] = None,
        max_lag_seconds: Optional[int] = None,
    ) -> List[ReadReplica]:
        """Get list of available replicas."""
        available = []

        for replica in self.replicas.values():
            # Check state
            if replica.state not in [ReplicaState.ACTIVE, ReplicaState.LAGGING]:
                continue

            # Check lag
            if max_lag_seconds and replica.lag_seconds > max_lag_seconds:
                continue

            # Check region preference
            if prefer_region and replica.region != prefer_region:
                # Still include but with lower priority
                pass

            available.append(replica)

        # Sort by region preference if specified
        if prefer_region:
            available.sort(key=lambda r: 0 if r.region == prefer_region else 1)

        return available

    def _select_replica(self, replicas: List[ReadReplica]) -> ReadReplica:
        """Select a replica based on load balancing strategy."""
        if not replicas:
            raise ValueError("No replicas available")

        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            replica = replicas[self._round_robin_index % len(replicas)]
            self._round_robin_index += 1
            return replica

        elif self.strategy == LoadBalancingStrategy.RANDOM:
            return random.choice(replicas)

        elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return min(replicas, key=lambda r: r.active_connections)

        elif self.strategy == LoadBalancingStrategy.LATENCY_BASED:
            return min(replicas, key=lambda r: r.avg_latency_ms)

        else:  # LoadBalancingStrategy.WEIGHTED
            # Weighted random selection
            weights = [r.weight for r in replicas]
            return random.choices(replicas, weights=weights)[0]

    async def check_replica_health(self, replica_name: str) -> bool:
        """Check health of a specific replica.

        Args:
            replica_name: Name of the replica

        Returns:
            True if healthy
        """
        replica = self.replicas.get(replica_name)
        if not replica:
            return False

        engine = self.engines.get(replica_name)
        if not engine:
            replica.state = ReplicaState.OFFLINE
            return False

        try:
            # Check connection
            with engine.connect() as conn:
                # Check basic connectivity
                conn.execute(text("SELECT 1"))

                # Check replication lag (PostgreSQL specific)
                if "postgresql" in replica.connection_url:
                    result = conn.execute(
                        text(
                            "SELECT EXTRACT(EPOCH FROM (NOW() - pg_last_xact_replay_timestamp())) AS lag"
                        )
                    )
                    lag = result.scalar()
                    if lag is not None:
                        replica.lag_seconds = int(lag)

            # Update state based on lag
            if replica.lag_seconds > replica.max_lag_seconds * 2:
                replica.state = ReplicaState.LAGGING
            else:
                replica.state = ReplicaState.ACTIVE

            replica.last_check = datetime.utcnow()
            replica.success_count += 1

            return True

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error(f"Health check failed for replica {replica_name}: {e}")
            replica.state = ReplicaState.OFFLINE
            replica.error_count += 1
            replica.last_check = datetime.utcnow()
            return False

    async def check_all_replicas(self) -> None:
        """Check health of all replicas."""
        for replica_name in list(self.replicas.keys()):
            await self.check_replica_health(replica_name)

    def failover_replica(self, replica_name: str) -> None:
        """Mark a replica as failed and remove from rotation.

        Args:
            replica_name: Name of the replica
        """
        replica = self.replicas.get(replica_name)
        if replica:
            replica.state = ReplicaState.OFFLINE
            logger.warning(f"Failed over replica: {replica_name}")

            # Close connections
            engine = self.engines.get(replica_name)
            if engine:
                engine.dispose()

    def get_replica_stats(self) -> Dict[str, Any]:
        """Get statistics for all replicas."""
        stats: Dict[str, Any] = {
            "total_replicas": len(self.replicas),
            "active_replicas": sum(
                1 for r in self.replicas.values() if r.state == ReplicaState.ACTIVE
            ),
            "replicas": {},
        }

        for name, replica in self.replicas.items():
            replicas_dict = stats["replicas"]
            if isinstance(replicas_dict, dict):
                replicas_dict[name] = {
                    "state": replica.state.value,
                    "region": replica.region,
                    "lag_seconds": replica.lag_seconds,
                    "active_connections": replica.active_connections,
                    "avg_latency_ms": replica.avg_latency_ms,
                    "error_rate": (
                        replica.error_count
                        / (replica.error_count + replica.success_count)
                        if (replica.error_count + replica.success_count) > 0
                        else 0
                    ),
                    "last_check": (
                        replica.last_check.isoformat() if replica.last_check else None
                    ),
                }

        return stats


# Global replica manager instance
_replica_manager_instance = None


def initialize_replicas(
    master_url: str, replica_configs: List[Dict[str, Any]]
) -> ReadReplicaManager:
    """Initialize the global replica manager.

    Args:
        master_url: Master database URL
        replica_configs: List of replica configurations
    """
    global _replica_manager_instance
    settings = get_settings()
    strategy = getattr(settings, "replica_strategy", LoadBalancingStrategy.ROUND_ROBIN)

    manager = ReadReplicaManager(master_url, strategy)

    for config in replica_configs:
        replica = ReadReplica(**config)
        manager.add_replica(replica)

    # Store as module-level instance
    _replica_manager_instance = manager
    return manager


@contextmanager
def read_db_session() -> Any:
    """Context manager for read database sessions."""
    if not _replica_manager_instance:
        raise RuntimeError("Replica manager not initialized")

    session = _replica_manager_instance.get_read_session()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def write_db_session() -> Any:
    """Context manager for write database sessions."""
    if not _replica_manager_instance:
        raise RuntimeError("Replica manager not initialized")

    session = _replica_manager_instance.get_write_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Export components
__all__ = [
    "ReplicaState",
    "LoadBalancingStrategy",
    "ReadReplica",
    "ReadReplicaManager",
    "initialize_replicas",
    "read_db_session",
    "write_db_session",
]
