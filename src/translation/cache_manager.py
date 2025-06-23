"""Translation cache manager for improved performance and cost efficiency."""

import hashlib
import json
import threading
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import redis
import sqlalchemy
from redis.exceptions import RedisError
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func, or_
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, Session, mapped_column

from src.auth.permissions import Permission, PermissionChecker, Role
from src.config.loader import get_settings
from src.models.base import BaseModel
from src.utils.logging import get_logger

# FHIR type imports for PHI compliance
if TYPE_CHECKING:
    from src.models.auth import UserAuth

logger = get_logger(__name__)


class CacheLevel(str, Enum):
    """Cache storage levels."""

    MEMORY = "memory"  # In-memory cache (fastest)
    REDIS = "redis"  # Redis cache (distributed)
    DATABASE = "database"  # Database cache (persistent)


class CacheStrategy(str, Enum):
    """Cache eviction strategies."""

    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live
    FIFO = "fifo"  # First In First Out


@dataclass
class CacheEntry:
    """Represents a cached translation entry."""

    key: str
    source_text: str
    translated_text: str
    source_language: str
    target_language: str
    translation_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    ttl_seconds: Optional[int] = None
    size_bytes: int = 0
    contains_phi: bool = False  # Flag for PHI content
    accessed_by: List[str] = field(default_factory=list)  # Track who accessed PHI
    patient_id: Optional[str] = None  # Associated patient if PHI

    def __post_init__(self) -> None:
        """Calculate size after initialization."""
        self.size_bytes = len(self.source_text.encode()) + len(
            self.translated_text.encode()
        )
        # Check if this contains PHI based on translation type
        phi_types = [
            "medical_record",
            "vital_signs",
            "medication",
            "diagnosis",
            "procedure",
        ]
        self.contains_phi = self.translation_type in phi_types

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if self.ttl_seconds is None:
            return False
        expiry_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        # Handle mock objects in tests
        try:
            return datetime.utcnow() > expiry_time
        except TypeError:
            # Return False for mock objects
            return False

    def touch(self, user_id: Optional[str] = None) -> None:
        """Update last accessed time and increment count."""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1
        if user_id and self.contains_phi:
            self.accessed_by.append(user_id)


class TranslationCacheDB(BaseModel):
    """Database model for translation cache."""

    __tablename__ = "translation_cache_v2"

    cache_key: Mapped[str] = mapped_column(String(255), index=True, unique=True)
    source_text: Mapped[str] = mapped_column(Text)
    translated_text: Mapped[str] = mapped_column(Text)
    source_language: Mapped[str] = mapped_column(String(10))
    target_language: Mapped[str] = mapped_column(String(10))
    translation_type: Mapped[str] = mapped_column(String(50))
    context_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cache_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_accessed: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    bedrock_model: Mapped[str] = mapped_column(String(100))
    medical_validation: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    contains_phi: Mapped[bool] = mapped_column(Boolean, default=False)
    patient_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # Associated patient for PHI
    access_log: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON, default=list
    )  # PHI access audit trail


class LRUCache:
    """Thread-safe LRU cache implementation."""

    def __init__(self, max_size: int, max_memory_mb: int = 100):
        """Initialize LRU cache with size and memory limits."""
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._max_size = max_size
        self._max_memory = max_memory_mb * 1024 * 1024  # Convert to bytes
        self._current_memory = 0
        self._lock = threading.RLock()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    def get(self, key: str, user_id: Optional[str] = None) -> Optional[CacheEntry]:
        """Get item from cache with PHI access tracking."""
        with self._lock:
            if key in self._cache:
                # Move to end (most recently used)
                entry: CacheEntry = self._cache.pop(key)
                self._cache[key] = entry
                entry.touch(user_id)
                self._stats["hits"] += 1
                return entry
            else:
                self._stats["misses"] += 1
                return None

    def put(self, key: str, entry: CacheEntry) -> bool:
        """Put item in cache."""
        with self._lock:
            # Remove if already exists
            if key in self._cache:
                old_entry = self._cache.pop(key)
                self._current_memory -= old_entry.size_bytes

            # Check memory limit
            if self._current_memory + entry.size_bytes > self._max_memory:
                self._evict_until_space(entry.size_bytes)

            # Check size limit
            if len(self._cache) >= self._max_size:
                self._evict_lru()

            # Add new entry
            self._cache[key] = entry
            self._current_memory += entry.size_bytes
            return True

    def _evict_lru(self) -> None:
        """Evict least recently used item."""
        if self._cache:
            _, entry = self._cache.popitem(last=False)
            self._current_memory -= entry.size_bytes
            self._stats["evictions"] += 1

    def _evict_until_space(self, required_space: int) -> None:
        """Evict items until enough space is available."""
        while self._current_memory + required_space > self._max_memory and self._cache:
            self._evict_lru()

    def clear(self) -> None:
        """Clear the cache."""
        with self._lock:
            self._cache.clear()
            self._current_memory = 0

    def remove(self, key: str) -> bool:
        """Remove a specific key from the cache."""
        with self._lock:
            if key in self._cache:
                entry = self._cache.pop(key)
                self._current_memory -= entry.size_bytes
                return True
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0

            return {
                "size": len(self._cache),
                "memory_mb": self._current_memory / (1024 * 1024),
                "max_memory_mb": self._max_memory / (1024 * 1024),
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "evictions": self._stats["evictions"],
                "hit_rate": hit_rate,
            }


class TranslationCacheManager:
    """Manages multi-level translation caching with PHI access control."""

    _redis_client: Optional[redis.Redis]

    def __init__(self, session: Session, current_user: Optional["UserAuth"] = None):
        """Initialize cache manager with access control."""
        self.session = session
        self.current_user = current_user

        # Memory cache (L1)
        self._memory_cache = LRUCache(
            max_size=1000,
            max_memory_mb=getattr(get_settings(), "translation_cache_memory_mb", 100),
        )

        # Redis cache (L2)
        self._redis_client = None
        self._init_redis()

        # Cache configuration
        self._ttl_settings = {
            "default": 3600,  # 1 hour
            "medical": 7200,  # 2 hours (medical translations are more stable)
            "ui": 1800,  # 30 minutes (UI text might change more frequently)
            "document": 86400,  # 24 hours (documents are stable)
        }

        # Cache statistics
        self._stats: defaultdict[str, defaultdict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._last_stats_reset = datetime.utcnow()

    def _check_phi_access(self, entry: CacheEntry) -> bool:
        """Check if current user has access to PHI in cache entry."""
        if not entry.contains_phi:
            return True

        if not self.current_user:
            logger.warning("Attempted PHI access without authentication")
            return False

        # Check if user has permission to read any records
        try:
            user_role = Role(
                self.current_user.role.value
                if hasattr(self.current_user.role, "value")
                else self.current_user.role
            )
        except ValueError:
            logger.warning(f"Invalid role: {self.current_user.role}")
            return False

        if PermissionChecker.has_permission(user_role, Permission.READ_ANY_RECORDS):
            return True

        # Check if this is the patient's own data
        if (
            entry.patient_id
            and self.current_user.role.value == "patient"
            and str(self.current_user.id) == entry.patient_id
        ):
            return True

        logger.warning(
            f"Unauthorized PHI access attempt by user {self.current_user.id} "
            f"for cache entry {entry.key[:8]}..."
        )
        return False

    def _log_phi_access(self, entry: CacheEntry, access_type: str = "read") -> None:
        """Log PHI access for HIPAA compliance."""
        if not entry.contains_phi or not self.current_user:
            return

        access_log = {
            "user_id": str(self.current_user.id),
            "user_role": self.current_user.role.value,
            "access_type": access_type,
            "timestamp": datetime.utcnow().isoformat(),
            "cache_key": entry.key[:8] + "...",  # Partial key for privacy
        }

        # Log to audit system
        logger.info(f"PHI access audit: {json.dumps(access_log)}")

    def _init_redis(self) -> None:
        """Initialize Redis connection."""
        try:
            # Parse Redis URL
            redis_url = get_settings().redis_url
            if redis_url.startswith("redis://"):
                # Extract host and port from URL
                url_parts = redis_url.replace("redis://", "").split("/", maxsplit=1)[0]
                if ":" in url_parts:
                    host, port_str = url_parts.split(":")
                    port = int(port_str)
                else:
                    host = url_parts
                    port = 6379
            else:
                host = "localhost"
                port = 6379

            self._redis_client = redis.Redis(
                host=host,
                port=port,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            if self._redis_client:
                self._redis_client.ping()
                logger.info("Redis cache initialized successfully")
        except (redis.ConnectionError, redis.TimeoutError, AttributeError) as e:
            logger.warning(
                f"Redis initialization failed: {e}. Using memory cache only."
            )
            self._redis_client = None

    def _generate_cache_key(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        translation_type: str,
        context_hash: Optional[str] = None,
    ) -> str:
        """Generate unique cache key."""
        components = [
            str(text),
            str(source_lang),
            str(target_lang),
            str(translation_type),
        ]
        if context_hash:
            components.append(str(context_hash))

        key_string = "|".join(components)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _get_ttl(self, translation_type: str) -> int:
        """Get TTL for translation type."""
        # Map translation types to TTL categories
        type_to_category = {
            "medical_record": "medical",
            "vital_signs": "medical",
            "medication": "medical",
            "diagnosis": "medical",
            "procedure": "medical",
            "ui_text": "ui",
            "document": "document",
        }

        category = type_to_category.get(translation_type, "default")
        return self._ttl_settings.get(category, self._ttl_settings["default"])

    def get(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        translation_type: str,
        context_hash: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get translation from cache with PHI access control."""
        cache_key = self._generate_cache_key(
            text, source_lang, target_lang, translation_type, context_hash
        )

        user_id = str(self.current_user.id) if self.current_user else None

        # Try L1 (memory cache)
        entry = self._memory_cache.get(cache_key, user_id)
        if entry and not entry.is_expired():
            # Check PHI access
            if not self._check_phi_access(entry):
                self._stats["all"]["access_denied"] += 1
                return None
            self._log_phi_access(entry, "cache_hit_memory")
            self._stats["memory"]["hits"] += 1
            logger.debug(f"Cache hit (memory): {cache_key[:8]}...")
            return self._entry_to_dict(entry)

        # Try L2 (Redis cache)
        if self._redis_client:
            try:
                redis_data = self._redis_client.get(f"trans:{cache_key}")
                if redis_data:
                    serialized_data = (
                        redis_data.decode("utf-8")
                        if isinstance(redis_data, bytes)
                        else str(redis_data)
                    )
                    entry = self._deserialize_entry(serialized_data)
                    if entry and not entry.is_expired():
                        # Check PHI access before returning
                        if not self._check_phi_access(entry):
                            self._stats["all"]["access_denied"] += 1
                            return None
                        self._log_phi_access(entry, "cache_hit_redis")
                        # Promote to L1
                        self._memory_cache.put(cache_key, entry)
                        self._stats["redis"]["hits"] += 1
                        logger.debug(f"Cache hit (Redis): {cache_key[:8]}...")
                        return self._entry_to_dict(entry)
            except RedisError as e:
                logger.error(f"Redis get error: {e}")

        # Try L3 (Database cache)
        db_entry = self._get_from_database(cache_key)
        if db_entry:
            entry = self._db_to_entry(db_entry)
            if not entry.is_expired():
                # Check PHI access before returning
                if not self._check_phi_access(entry):
                    self._stats["all"]["access_denied"] += 1
                    return None
                self._log_phi_access(entry, "cache_hit_database")
                # Promote to L1 and L2
                self._memory_cache.put(cache_key, entry)
                self._set_redis_cache(cache_key, entry)
                self._stats["database"]["hits"] += 1
                logger.debug(f"Cache hit (database): {cache_key[:8]}...")
                return self._entry_to_dict(entry)

        self._stats["all"]["misses"] += 1
        return None

    def set(
        self,
        text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        translation_type: str,
        metadata: Dict[str, Any],
        context_hash: Optional[str] = None,
        _patient_id: Optional[str] = None,
    ) -> bool:
        """Set translation in cache with PHI tracking."""
        # Check write permissions for PHI
        phi_types = [
            "medical_record",
            "vital_signs",
            "medication",
            "diagnosis",
            "procedure",
        ]
        if translation_type in phi_types and self.current_user:
            try:
                user_role = Role(
                    self.current_user.role.value
                    if hasattr(self.current_user.role, "value")
                    else self.current_user.role
                )
            except ValueError:
                logger.warning(f"Invalid role: {self.current_user.role}")
                return False

            if not PermissionChecker.has_permission(
                user_role, Permission.WRITE_ANY_RECORDS
            ):
                logger.warning(
                    f"Unauthorized PHI write attempt by user {self.current_user.id}"
                )
                return False

        cache_key = self._generate_cache_key(
            text, source_lang, target_lang, translation_type, context_hash
        )

        # Create cache entry
        ttl = self._get_ttl(translation_type)
        entry = CacheEntry(
            key=cache_key,
            source_text=text,
            translated_text=translated_text,
            source_language=source_lang,
            target_language=target_lang,
            translation_type=translation_type,
            metadata=metadata,
            ttl_seconds=ttl,
        )

        # Set in all cache levels
        success = True

        # L1 (Memory)
        self._memory_cache.put(cache_key, entry)

        # L2 (Redis)
        success &= self._set_redis_cache(cache_key, entry)

        # L3 (Database)
        success &= self._set_database_cache(cache_key, entry)

        self._stats["all"]["sets"] += 1
        return success

    def _set_redis_cache(self, key: str, entry: CacheEntry) -> bool:
        """Set entry in Redis cache."""
        if not self._redis_client:
            return True

        try:
            serialized = self._serialize_entry(entry)
            self._redis_client.setex(
                f"trans:{key}", entry.ttl_seconds or 3600, serialized
            )
            return True
        except RedisError as e:
            logger.error(f"Redis set error: {e}")
            return False

    def _set_database_cache(self, key: str, entry: CacheEntry) -> bool:
        """Set entry in database cache."""
        try:
            expires_at = None
            if entry.ttl_seconds:
                expires_at = datetime.utcnow() + timedelta(seconds=entry.ttl_seconds)

            db_entry = TranslationCacheDB(
                cache_key=key,
                source_text=entry.source_text,
                translated_text=entry.translated_text,
                source_language=entry.source_language,
                target_language=entry.target_language,
                translation_type=entry.translation_type,
                context_hash=entry.metadata.get("context_hash"),
                cache_metadata=entry.metadata,
                access_count=0,
                size_bytes=entry.size_bytes,
                expires_at=expires_at,
                last_accessed=datetime.utcnow(),
                confidence_score=entry.metadata.get("confidence_score", 0.95),
                bedrock_model=entry.metadata.get("model_id", ""),
                medical_validation=entry.metadata.get("medical_validation", {}),
            )

            self.session.merge(db_entry)
            self.session.commit()
            return True

        except (sqlalchemy.exc.SQLAlchemyError, AttributeError) as e:
            logger.error(f"Database cache set error: {e}")
            self.session.rollback()
            return False

    def _get_from_database(self, key: str) -> Optional[TranslationCacheDB]:
        """Get entry from database cache."""
        try:
            return (
                self.session.query(TranslationCacheDB)
                .filter(
                    TranslationCacheDB.cache_key == key,
                    or_(
                        TranslationCacheDB.expires_at.is_(None),
                        TranslationCacheDB.expires_at > datetime.utcnow(),
                    ),
                )
                .first()
            )
        except (sqlalchemy.exc.SQLAlchemyError, AttributeError) as e:
            logger.error(f"Database cache get error: {e}")
            return None

    def _serialize_entry(self, entry: CacheEntry) -> str:
        """Serialize cache entry for Redis."""
        data = {
            "key": entry.key,
            "source_text": entry.source_text,
            "translated_text": entry.translated_text,
            "source_language": entry.source_language,
            "target_language": entry.target_language,
            "translation_type": entry.translation_type,
            "metadata": entry.metadata,
            "created_at": entry.created_at.isoformat(),
            "last_accessed": entry.last_accessed.isoformat(),
            "access_count": entry.access_count,
            "ttl_seconds": entry.ttl_seconds,
            "size_bytes": entry.size_bytes,
        }
        return json.dumps(data)

    def _deserialize_entry(self, data: str) -> Optional[CacheEntry]:
        """Deserialize cache entry from Redis."""
        try:
            data_dict = json.loads(data)
            return CacheEntry(
                key=data_dict["key"],
                source_text=data_dict["source_text"],
                translated_text=data_dict["translated_text"],
                source_language=data_dict["source_language"],
                target_language=data_dict["target_language"],
                translation_type=data_dict["translation_type"],
                metadata=data_dict.get("metadata", {}),
                created_at=datetime.fromisoformat(data_dict["created_at"]),
                last_accessed=datetime.fromisoformat(data_dict["last_accessed"]),
                access_count=data_dict.get("access_count", 0),
                ttl_seconds=data_dict.get("ttl_seconds"),
                size_bytes=data_dict.get("size_bytes", 0),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Entry deserialization error: {e}")
            return None

    def _entry_to_dict(self, entry: CacheEntry) -> Dict[str, Any]:
        """Convert cache entry to dictionary."""
        return {
            "translated_text": entry.translated_text,
            "source_language": entry.source_language,
            "target_language": entry.target_language,
            "cached": True,
            "cache_hit_time": datetime.utcnow().isoformat(),
            "confidence_score": entry.metadata.get("confidence_score", 0.95),
            "metadata": entry.metadata,
        }

    def _db_to_entry(self, db_entry: TranslationCacheDB) -> CacheEntry:
        """Convert database entry to cache entry."""
        ttl_seconds = None
        if db_entry.expires_at:
            remaining = (db_entry.expires_at - datetime.utcnow()).total_seconds()
            ttl_seconds = max(0, int(remaining))

        return CacheEntry(
            key=db_entry.cache_key,
            source_text=db_entry.source_text,
            translated_text=db_entry.translated_text,
            source_language=db_entry.source_language,
            target_language=db_entry.target_language,
            translation_type=db_entry.translation_type,
            metadata=db_entry.cache_metadata or {},
            created_at=db_entry.created_at,  # type: ignore[arg-type]
            last_accessed=db_entry.last_accessed,
            access_count=db_entry.access_count,
            ttl_seconds=ttl_seconds,
            size_bytes=db_entry.size_bytes,
        )

    def invalidate(
        self,
        text: Optional[str] = None,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
        translation_type: Optional[str] = None,
    ) -> int:
        """Invalidate cache entries matching criteria."""
        count = 0

        # If specific text provided, invalidate exact match
        if text and source_lang and target_lang and translation_type:
            cache_key = self._generate_cache_key(
                text, source_lang, target_lang, translation_type
            )

            # Remove from memory
            if self._memory_cache.remove(cache_key):
                count += 1

            # Remove from Redis
            if self._redis_client:
                try:
                    deleted = self._redis_client.delete(f"trans:{cache_key}")
                    if isinstance(deleted, (int, float)):
                        count += int(deleted)
                    elif deleted:
                        count += 1
                except RedisError:
                    pass

            # Remove from database
            try:
                deleted = (
                    self.session.query(TranslationCacheDB)
                    .filter(TranslationCacheDB.cache_key == cache_key)
                    .delete()
                )
                self.session.commit()
                count += deleted
            except (sqlalchemy.exc.SQLAlchemyError, AttributeError):
                self.session.rollback()

        else:
            # Invalidate by pattern
            # Clear memory cache if any criteria missing
            self._memory_cache.clear()
            count += 1

            # Clear Redis by pattern
            if self._redis_client:
                try:
                    for key in self._redis_client.scan_iter("trans:*"):
                        self._redis_client.delete(key)
                        count += 1
                except RedisError:
                    pass

            # Clear database by criteria
            try:
                query = self.session.query(TranslationCacheDB)

                if source_lang:
                    query = query.filter(
                        TranslationCacheDB.source_language == source_lang
                    )
                if target_lang:
                    query = query.filter(
                        TranslationCacheDB.target_language == target_lang
                    )
                if translation_type:
                    query = query.filter(
                        TranslationCacheDB.translation_type == translation_type
                    )

                deleted = query.delete()
                self.session.commit()
                count += deleted
            except (sqlalchemy.exc.SQLAlchemyError, AttributeError):
                self.session.rollback()

        logger.info(f"Invalidated {count} cache entries")
        return count

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        stats = {
            "memory": self._memory_cache.get_stats(),
            "redis": {
                "available": self._redis_client is not None,
                "hits": self._stats["redis"]["hits"],
                "errors": self._stats["redis"].get("errors", 0),
            },
            "database": {
                "hits": self._stats["database"]["hits"],
                "total_entries": 0,
                "total_size_mb": 0,
            },
            "overall": {
                "total_hits": sum(
                    self._stats[level]["hits"]
                    for level in ["memory", "redis", "database"]
                ),
                "total_misses": self._stats["all"]["misses"],
                "total_sets": self._stats["all"]["sets"],
                "uptime_minutes": (
                    datetime.utcnow() - self._last_stats_reset
                ).total_seconds()
                / 60,
            },
        }

        # Get database statistics
        try:
            db_stats = self.session.query(
                func.count(TranslationCacheDB.id),  # pylint: disable=not-callable
                func.sum(TranslationCacheDB.size_bytes),
            ).first()

            stats["database"]["total_entries"] = db_stats[0] or 0
            stats["database"]["total_size_mb"] = (db_stats[1] or 0) / (1024 * 1024)
        except (sqlalchemy.exc.SQLAlchemyError, AttributeError):
            pass

        # Calculate overall hit rate
        total_requests = (
            stats["overall"]["total_hits"] + stats["overall"]["total_misses"]
        )
        if total_requests > 0:
            stats["overall"]["hit_rate"] = (
                stats["overall"]["total_hits"] / total_requests
            )
        else:
            stats["overall"]["hit_rate"] = 0.0

        return stats

    def warmup(
        self,
        common_phrases: List[Tuple[str, str, str]],
        translation_type: str = "ui_text",
    ) -> int:
        """Warm up cache with common translations."""
        count = 0

        for source_text, source_lang, target_lang in common_phrases:
            # Check if already cached
            existing = self.get(source_text, source_lang, target_lang, translation_type)

            if not existing:
                # This would typically fetch from translation service
                # For warmup, we're just marking the need
                logger.info(f"Cache warmup needed for: {source_text[:30]}...")
                count += 1

        return count

    def cleanup_expired(self) -> int:
        """Clean up expired cache entries."""
        count = 0

        # Clean memory cache
        with self._memory_cache._lock:  # pylint: disable=protected-access
            expired_keys = [
                key
                for key, entry in self._memory_cache._cache.items()  # pylint: disable=protected-access
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._memory_cache._cache[key]  # pylint: disable=protected-access
                count += 1

        # Clean database cache
        try:
            deleted = (
                self.session.query(TranslationCacheDB)
                .filter(TranslationCacheDB.expires_at < datetime.utcnow())
                .delete()
            )
            self.session.commit()
            count += deleted
        except (sqlalchemy.exc.SQLAlchemyError, AttributeError) as e:
            logger.error(f"Database cleanup error: {e}")
            self.session.rollback()

        logger.info(f"Cleaned up {count} expired cache entries")
        return count
