"""Cache TTL configuration for the Haven Health Passport API.

This module provides comprehensive cache TTL (Time To Live) configuration
for different types of data with support for environment-specific overrides,
dynamic configuration, and cache warming strategies.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

import random
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, Union

from pydantic import BaseModel, Field, validator

from src.config import get_settings
from src.healthcare.fhir.validators import FHIRValidator
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class CacheCategory(str, Enum):
    """Categories of cached data with different TTL requirements."""

    # User and authentication
    USER_PROFILE = "user_profile"
    USER_SESSION = "user_session"
    USER_PERMISSIONS = "user_permissions"
    API_KEY = "api_key"

    # Patient data
    PATIENT_BASIC = "patient_basic"
    PATIENT_DEMOGRAPHICS = "patient_demographics"
    PATIENT_CONTACTS = "patient_contacts"

    # Health records
    HEALTH_RECORD = "health_record"
    HEALTH_RECORD_LIST = "health_record_list"
    MEDICAL_HISTORY = "medical_history"
    VACCINATION_RECORD = "vaccination_record"

    # Translations
    TRANSLATION = "translation"
    TRANSLATION_MEDICAL = "translation_medical"
    TRANSLATION_GLOSSARY = "translation_glossary"
    LANGUAGE_DETECTION = "language_detection"

    # Verifications
    VERIFICATION_STATUS = "verification_status"
    BLOCKCHAIN_HASH = "blockchain_hash"
    DOCUMENT_VERIFICATION = "document_verification"

    # Search and queries
    SEARCH_RESULTS = "search_results"
    QUERY_RESULTS = "query_results"
    AGGREGATION_RESULTS = "aggregation_results"

    # File and media
    FILE_METADATA = "file_metadata"
    FILE_CONTENT = "file_content"
    THUMBNAIL = "thumbnail"

    # System and config
    SYSTEM_CONFIG = "system_config"
    FEATURE_FLAGS = "feature_flags"
    RATE_LIMIT_COUNTER = "rate_limit_counter"


class CacheTTLConfig(BaseModel):
    """Configuration for cache TTL values."""

    # User and authentication (shorter TTL for security)
    user_profile: int = Field(
        default=600, description="User profile TTL in seconds (10 min)"
    )
    user_session: int = Field(
        default=1800, description="User session TTL in seconds (30 min)"
    )
    user_permissions: int = Field(
        default=300, description="User permissions TTL in seconds (5 min)"
    )
    api_key: int = Field(
        default=300, description="API key validation TTL in seconds (5 min)"
    )

    # Patient data (medium TTL)
    patient_basic: int = Field(
        default=3600, description="Basic patient info TTL in seconds (1 hour)"
    )
    patient_demographics: int = Field(
        default=3600, description="Demographics TTL in seconds (1 hour)"
    )
    patient_contacts: int = Field(
        default=1800, description="Contact info TTL in seconds (30 min)"
    )

    # Health records (longer TTL as they change less frequently)
    health_record: int = Field(
        default=3600, description="Health record TTL in seconds (1 hour)"
    )
    health_record_list: int = Field(
        default=900, description="Record list TTL in seconds (15 min)"
    )
    medical_history: int = Field(
        default=7200, description="Medical history TTL in seconds (2 hours)"
    )
    vaccination_record: int = Field(
        default=86400, description="Vaccination TTL in seconds (24 hours)"
    )

    # Translations (very long TTL as they rarely change)
    translation: int = Field(
        default=86400, description="Translation TTL in seconds (24 hours)"
    )
    translation_medical: int = Field(
        default=604800, description="Medical translation TTL in seconds (7 days)"
    )
    translation_glossary: int = Field(
        default=2592000, description="Glossary TTL in seconds (30 days)"
    )
    language_detection: int = Field(
        default=3600, description="Language detection TTL in seconds (1 hour)"
    )

    # Verifications (medium to long TTL)
    verification_status: int = Field(
        default=3600, description="Verification status TTL in seconds (1 hour)"
    )
    blockchain_hash: int = Field(
        default=2592000, description="Blockchain hash TTL in seconds (30 days)"
    )
    document_verification: int = Field(
        default=86400, description="Document verification TTL in seconds (24 hours)"
    )

    # Search and queries (short TTL for freshness)
    search_results: int = Field(
        default=300, description="Search results TTL in seconds (5 min)"
    )
    query_results: int = Field(
        default=600, description="Query results TTL in seconds (10 min)"
    )
    aggregation_results: int = Field(
        default=900, description="Aggregation results TTL in seconds (15 min)"
    )

    # File and media (long TTL)
    file_metadata: int = Field(
        default=3600, description="File metadata TTL in seconds (1 hour)"
    )
    file_content: int = Field(
        default=86400, description="File content TTL in seconds (24 hours)"
    )
    thumbnail: int = Field(
        default=604800, description="Thumbnail TTL in seconds (7 days)"
    )

    # System and config (variable TTL)
    system_config: int = Field(
        default=300, description="System config TTL in seconds (5 min)"
    )
    feature_flags: int = Field(
        default=60, description="Feature flags TTL in seconds (1 min)"
    )
    rate_limit_counter: int = Field(
        default=60, description="Rate limit counter TTL in seconds (1 min)"
    )

    @validator("*")
    @classmethod
    def validate_positive(cls, v: int) -> int:
        """Ensure all TTL values are positive."""
        if v < 0:
            raise ValueError("TTL values must be positive")
        return v


class CacheTTLManager:
    """Manager for cache TTL configuration with environment-specific overrides."""

    def __init__(self) -> None:
        """Initialize the TTL manager."""
        self.settings = get_settings()
        self.config = CacheTTLConfig()
        self._load_environment_overrides()
        self._custom_ttls: Dict[str, int] = {}
        self.fhir_validator = FHIRValidator()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )

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

    def _load_environment_overrides(self) -> None:
        """Load environment-specific TTL overrides."""
        # In production, we might want longer TTLs for stability
        if self.settings.environment == "production":
            self.config.user_session = 3600  # 1 hour
            self.config.health_record = 7200  # 2 hours
            self.config.translation_medical = 2592000  # 30 days

        # In development, shorter TTLs for testing
        elif self.settings.environment == "development":
            self.config.user_session = 300  # 5 minutes
            self.config.health_record = 600  # 10 minutes
            self.config.translation_medical = 3600  # 1 hour

        # Load from environment variables if available
        for category in CacheCategory:
            env_key = f"CACHE_TTL_{category.value.upper()}"
            env_value = getattr(self.settings, env_key, None)
            if env_value:
                try:
                    setattr(self.config, category.value, int(env_value))
                except (ValueError, AttributeError):
                    logger.warning(f"Invalid TTL value for {env_key}: {env_value}")

    def get_ttl(self, category: Union[CacheCategory, str]) -> int:
        """Get TTL for a specific category.

        Args:
            category: The cache category

        Returns:
            TTL in seconds
        """
        # Check custom TTLs first
        if isinstance(category, str) and category in self._custom_ttls:
            return self._custom_ttls[category]

        # Convert to enum if string
        if isinstance(category, str):
            try:
                category = CacheCategory(category)
            except ValueError:
                logger.warning(f"Unknown cache category: {category}, using default TTL")
                return 300  # Default 5 minutes

        # Get configured TTL
        return getattr(self.config, category.value, 300)

    def set_custom_ttl(self, key: str, ttl: int) -> None:
        """Set a custom TTL for a specific cache key pattern.

        Args:
            key: The cache key pattern
            ttl: TTL in seconds
        """
        if ttl < 0:
            raise ValueError("TTL must be positive")
        self._custom_ttls[key] = ttl
        logger.info(f"Set custom TTL for {key}: {ttl} seconds")

    def get_ttl_with_jitter(
        self, category: Union[CacheCategory, str], jitter_percent: int = 10
    ) -> int:
        """Get TTL with random jitter to prevent cache stampede.

        Args:
            category: The cache category
            jitter_percent: Percentage of jitter to add (0-50)

        Returns:
            TTL with jitter in seconds
        """
        base_ttl = self.get_ttl(category)
        jitter_percent = min(50, max(0, jitter_percent))  # Clamp to 0-50%

        jitter = int(base_ttl * jitter_percent / 100)
        return base_ttl + random.randint(-jitter, jitter)

    def get_cache_headers(self, category: Union[CacheCategory, str]) -> Dict[str, str]:
        """Get HTTP cache headers for a category.

        Args:
            category: The cache category

        Returns:
            Dictionary of cache headers
        """
        ttl = self.get_ttl(category)

        # Public caching for non-sensitive data
        public_categories = [
            CacheCategory.TRANSLATION,
            CacheCategory.TRANSLATION_MEDICAL,
            CacheCategory.TRANSLATION_GLOSSARY,
            CacheCategory.LANGUAGE_DETECTION,
            CacheCategory.THUMBNAIL,
        ]

        cache_control = "public" if category in public_categories else "private"

        return {
            "Cache-Control": f"{cache_control}, max-age={ttl}",
            "Expires": self._get_expires_header(ttl),
            "Vary": "Accept-Encoding, Accept-Language",
        }

    def _get_expires_header(self, ttl: int) -> str:
        """Generate Expires header value."""
        expires = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        return expires.strftime("%a, %d %b %Y %H:%M:%S GMT")

    def should_cache(self, category: Union[CacheCategory, str]) -> bool:
        """Determine if a category should be cached based on environment and settings.

        Args:
            category: The cache category

        Returns:
            True if caching is enabled for this category
        """
        # Check if caching is globally disabled
        if hasattr(self.settings, "cache_enabled") and not self.settings.cache_enabled:
            return False

        # Check category-specific settings
        if isinstance(category, str):
            try:
                category = CacheCategory(category)
            except ValueError:
                return True  # Cache unknown categories by default

        # Don't cache sensitive data in development
        if self.settings.environment == "development":
            sensitive_categories = [
                CacheCategory.USER_SESSION,
                CacheCategory.USER_PERMISSIONS,
                CacheCategory.API_KEY,
            ]
            if category in sensitive_categories:
                return False

        return True

    def get_cache_stats_ttl(self) -> int:
        """Get TTL for cache statistics."""
        return 60  # 1 minute for real-time stats

    def get_all_ttls(self) -> Dict[str, int]:
        """Get all configured TTLs.

        Returns:
            Dictionary of category to TTL mappings
        """
        ttls = {}
        for category in CacheCategory:
            ttls[category.value] = self.get_ttl(category)

        # Add custom TTLs
        ttls.update(self._custom_ttls)

        return ttls


# Global TTL manager instance
ttl_manager = CacheTTLManager()


# Helper functions for common use cases
def get_user_cache_ttl() -> int:
    """Get TTL for user-related caching."""
    return ttl_manager.get_ttl(CacheCategory.USER_PROFILE)


def get_health_record_cache_ttl() -> int:
    """Get TTL for health record caching."""
    return ttl_manager.get_ttl(CacheCategory.HEALTH_RECORD)


def get_translation_cache_ttl(is_medical: bool = False) -> int:
    """Get TTL for translation caching."""
    category = (
        CacheCategory.TRANSLATION_MEDICAL if is_medical else CacheCategory.TRANSLATION
    )
    return ttl_manager.get_ttl(category)


def get_search_cache_ttl() -> int:
    """Get TTL for search result caching."""
    return ttl_manager.get_ttl(CacheCategory.SEARCH_RESULTS)


def get_file_cache_ttl(is_content: bool = False) -> int:
    """Get TTL for file caching."""
    category = CacheCategory.FILE_CONTENT if is_content else CacheCategory.FILE_METADATA
    return ttl_manager.get_ttl(category)


# Export all components
__all__ = [
    "CacheCategory",
    "CacheTTLConfig",
    "CacheTTLManager",
    "ttl_manager",
    "get_user_cache_ttl",
    "get_health_record_cache_ttl",
    "get_translation_cache_ttl",
    "get_search_cache_ttl",
    "get_file_cache_ttl",
]
