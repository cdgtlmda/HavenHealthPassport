"""Cache configuration settings."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class CacheConfig(BaseSettings):
    """Cache-specific configuration.

    Note: Cache configurations that may contain PHI require proper access control
    and encryption when storing sensitive health information.
    """

    # Memory cache settings
    translation_cache_memory_mb: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Maximum memory for translation cache in MB",
    )

    translation_cache_max_entries: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Maximum number of entries in memory cache",
    )

    # Redis cache settings
    redis_cache_enabled: bool = Field(
        default=True, description="Enable Redis caching layer"
    )

    redis_key_prefix: str = Field(
        default="haven:trans:", description="Prefix for Redis cache keys"
    )

    redis_connection_timeout: int = Field(
        default=5, description="Redis connection timeout in seconds"
    )

    redis_retry_attempts: int = Field(
        default=3, description="Number of Redis retry attempts"
    )

    # Database cache settings
    db_cache_enabled: bool = Field(
        default=True, description="Enable database caching layer"
    )

    db_cache_batch_size: int = Field(
        default=100, description="Batch size for database cache operations"
    )

    # TTL settings (in seconds)
    cache_ttl_default: int = Field(
        default=3600, description="Default cache TTL (1 hour)"
    )

    cache_ttl_medical: int = Field(
        default=7200, description="Medical translation cache TTL (2 hours)"
    )

    cache_ttl_ui: int = Field(
        default=1800, description="UI text cache TTL (30 minutes)"
    )

    cache_ttl_document: int = Field(
        default=86400, description="Document cache TTL (24 hours)"
    )

    cache_ttl_context: int = Field(
        default=14400, description="Context-specific cache TTL (4 hours)"
    )

    # Cache warmup settings
    cache_warmup_enabled: bool = Field(
        default=True, description="Enable cache warmup on startup"
    )

    cache_warmup_phrases_file: Optional[str] = Field(
        default="config/common_phrases.json",
        description="File containing common phrases for cache warmup",
    )

    # Cache eviction settings
    cache_eviction_strategy: str = Field(
        default="lru", description="Cache eviction strategy (lru, lfu, ttl)"
    )

    cache_cleanup_interval_minutes: int = Field(
        default=60, description="Interval for cache cleanup job"
    )

    # Performance settings
    cache_compression_enabled: bool = Field(
        default=False, description="Enable compression for cached data"
    )

    cache_async_writes: bool = Field(
        default=True, description="Enable asynchronous cache writes"
    )

    # PHI encryption settings
    encrypt_phi_in_cache: bool = Field(
        default=True, description="Encrypt PHI data before caching"
    )

    phi_cache_key_encryption: bool = Field(
        default=True, description="Encrypt cache keys containing PHI"
    )

    # Monitoring settings
    cache_metrics_enabled: bool = Field(
        default=True, description="Enable cache performance metrics"
    )

    cache_metrics_interval_seconds: int = Field(
        default=60, description="Interval for cache metrics collection"
    )

    # Cost optimization
    cache_cost_tracking_enabled: bool = Field(
        default=True, description="Track estimated cost savings from cache hits"
    )

    bedrock_cost_per_1k_tokens: float = Field(
        default=0.01, description="Estimated cost per 1000 tokens for Bedrock API"
    )

    class Config:
        """Pydantic config."""

        env_prefix = "CACHE_"
        case_sensitive = False


def get_cache_config() -> CacheConfig:
    """Get cache configuration."""
    return CacheConfig()


# Common phrases for cache warmup
DEFAULT_COMMON_PHRASES = {
    "greetings": [
        ("Hello", "en", "es"),
        ("Hello", "en", "fr"),
        ("Hello", "en", "ar"),
        ("Good morning", "en", "es"),
        ("Good morning", "en", "fr"),
        ("Good morning", "en", "ar"),
        ("Thank you", "en", "es"),
        ("Thank you", "en", "fr"),
        ("Thank you", "en", "ar"),
    ],
    "medical_common": [
        ("Take medication", "en", "es"),
        ("Take medication", "en", "fr"),
        ("Take medication", "en", "ar"),
        ("Blood pressure", "en", "es"),
        ("Blood pressure", "en", "fr"),
        ("Blood pressure", "en", "ar"),
        ("Temperature", "en", "es"),
        ("Temperature", "en", "fr"),
        ("Temperature", "en", "ar"),
        ("Pain level", "en", "es"),
        ("Pain level", "en", "fr"),
        ("Pain level", "en", "ar"),
    ],
    "instructions": [
        ("Once daily", "en", "es"),
        ("Once daily", "en", "fr"),
        ("Once daily", "en", "ar"),
        ("Twice daily", "en", "es"),
        ("Twice daily", "en", "fr"),
        ("Twice daily", "en", "ar"),
        ("With food", "en", "es"),
        ("With food", "en", "fr"),
        ("With food", "en", "ar"),
        ("Before meals", "en", "es"),
        ("Before meals", "en", "fr"),
        ("Before meals", "en", "ar"),
    ],
    "emergency": [
        ("Emergency", "en", "es"),
        ("Emergency", "en", "fr"),
        ("Emergency", "en", "ar"),
        ("Call doctor", "en", "es"),
        ("Call doctor", "en", "fr"),
        ("Call doctor", "en", "ar"),
        ("Go to hospital", "en", "es"),
        ("Go to hospital", "en", "fr"),
        ("Go to hospital", "en", "ar"),
    ],
}
