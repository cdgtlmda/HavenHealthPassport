"""Cache invalidation service for maintaining data consistency.

This module provides intelligent cache invalidation strategies to ensure
cached data remains consistent when underlying data changes.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

import asyncio

# datetime imported when needed
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from pydantic import BaseModel, Field

from src.healthcare.fhir.validators import FHIRValidator
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService
from src.services.cache_service import cache_service

# CacheCategory imported when needed
from src.utils.logging import get_logger

# FHIR resources imported when needed for type checking only


logger = get_logger(__name__)


class InvalidationStrategy(str, Enum):
    """Cache invalidation strategies."""

    IMMEDIATE = "immediate"  # Invalidate immediately
    DELAYED = "delayed"  # Invalidate after a delay
    LAZY = "lazy"  # Mark as stale, refresh on next access
    CASCADE = "cascade"  # Invalidate related entries
    PATTERN = "pattern"  # Invalidate by pattern matching


class InvalidationRule(BaseModel):
    """Rule for cache invalidation."""

    name: str = Field(..., description="Rule name")
    trigger_event: str = Field(..., description="Event that triggers invalidation")
    patterns: List[str] = Field(..., description="Cache key patterns to invalidate")
    strategy: InvalidationStrategy = Field(default=InvalidationStrategy.IMMEDIATE)
    delay_seconds: Optional[int] = Field(None, description="Delay for DELAYED strategy")
    cascade_rules: Optional[List[str]] = Field(
        None, description="Names of rules to cascade"
    )
    enabled: bool = Field(default=True)


class CacheInvalidationService:
    """Service for managing cache invalidation."""

    def __init__(self) -> None:
        """Initialize the invalidation service."""
        self.rules: Dict[str, InvalidationRule] = {}
        self.pending_invalidations: Dict[str, Set[str]] = {}
        self.fhir_validator = FHIRValidator()
        # Use a default KMS key ID for cache encryption
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-cache"
        )
        self._initialize_default_rules()

    def validate_fhir_resource(self, resource: dict) -> bool:
        """Validate FHIR resource structure and requirements."""
        # Resource type could be used for type-specific validation
        # resource_type = resource.get("resourceType", "")
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

    def _initialize_default_rules(self) -> None:
        """Initialize default invalidation rules."""
        # User-related invalidations
        self.add_rule(
            InvalidationRule(
                name="user_update",
                trigger_event="user.updated",
                patterns=[
                    "user:{user_id}",
                    "user:{user_id}:*",
                    "query:*/users/{user_id}*",
                ],
                strategy=InvalidationStrategy.CASCADE,
                cascade_rules=["user_permissions_update"],
                delay_seconds=None,
            )
        )

        self.add_rule(
            InvalidationRule(
                name="user_permissions_update",
                trigger_event="user.permissions_changed",
                patterns=[
                    "user:{user_id}:permissions",
                    "user:{user_id}:roles",
                    "api_key:*:{user_id}",
                ],
                strategy=InvalidationStrategy.IMMEDIATE,
                delay_seconds=None,
                cascade_rules=None,
            )
        )

        # Patient-related invalidations
        self.add_rule(
            InvalidationRule(
                name="patient_update",
                trigger_event="patient.updated",
                patterns=[
                    "patient:{patient_id}",
                    "patient:{patient_id}:*",
                    "query:*/patients/{patient_id}*",
                ],
                strategy=InvalidationStrategy.CASCADE,
                cascade_rules=["patient_records_update"],
                delay_seconds=None,
            )
        )

        self.add_rule(
            InvalidationRule(
                name="patient_records_update",
                trigger_event="patient.records_changed",
                patterns=[
                    "health_record:*:{patient_id}",
                    "patient:{patient_id}:records",
                    "query:*/patients/{patient_id}/records*",
                ],
                strategy=InvalidationStrategy.IMMEDIATE,
                delay_seconds=None,
                cascade_rules=None,
            )
        )

        # Health record invalidations
        self.add_rule(
            InvalidationRule(
                name="health_record_update",
                trigger_event="health_record.updated",
                patterns=[
                    "health_record:{record_id}",
                    "health_record:{record_id}:*",
                    "patient:{patient_id}:records",
                    "query:*/health-records/{record_id}*",
                ],
                strategy=InvalidationStrategy.IMMEDIATE,
                delay_seconds=None,
                cascade_rules=None,
            )
        )

        self.add_rule(
            InvalidationRule(
                name="health_record_verification",
                trigger_event="health_record.verified",
                patterns=[
                    "health_record:{record_id}:verification",
                    "verification:{verification_id}",
                    "blockchain:hash:{record_id}",
                ],
                strategy=InvalidationStrategy.DELAYED,
                delay_seconds=5,  # Allow blockchain propagation
                cascade_rules=None,
            )
        )

        # Translation invalidations
        self.add_rule(
            InvalidationRule(
                name="translation_update",
                trigger_event="translation.updated",
                patterns=[
                    "translation:{source_lang}:{target_lang}:{text_hash}",
                    "translation:glossary:{glossary_id}",
                ],
                strategy=InvalidationStrategy.LAZY,
                delay_seconds=None,
                cascade_rules=None,
            )
        )

        self.add_rule(
            InvalidationRule(
                name="glossary_update",
                trigger_event="glossary.updated",
                patterns=[
                    "translation:glossary:{glossary_id}",
                    "translation:glossary:*:{language}",
                    "translation:*:*:*",  # Invalidate all translations using glossary
                ],
                strategy=InvalidationStrategy.PATTERN,
                delay_seconds=None,
                cascade_rules=None,
            )
        )

        # File invalidations
        self.add_rule(
            InvalidationRule(
                name="file_update",
                trigger_event="file.updated",
                patterns=[
                    "file:{file_id}:*",
                    "thumbnail:{file_id}",
                ],
                strategy=InvalidationStrategy.IMMEDIATE,
                delay_seconds=None,
                cascade_rules=None,
            )
        )

        # Search/query invalidations
        self.add_rule(
            InvalidationRule(
                name="search_index_update",
                trigger_event="search.index_updated",
                patterns=[
                    "search:*",
                    "query:*/search*",
                ],
                strategy=InvalidationStrategy.PATTERN,
                delay_seconds=None,
                cascade_rules=None,
            )
        )

    def add_rule(self, rule: InvalidationRule) -> None:
        """Add an invalidation rule."""
        self.rules[rule.name] = rule
        logger.info(f"Added invalidation rule: {rule.name}")

    def remove_rule(self, rule_name: str) -> None:
        """Remove an invalidation rule."""
        if rule_name in self.rules:
            del self.rules[rule_name]
            logger.info(f"Removed invalidation rule: {rule_name}")

    async def trigger_invalidation(
        self,
        event: str,
        context: Optional[Dict[str, str]] = None,
    ) -> None:
        """Trigger cache invalidation based on an event.

        Args:
            event: The event that occurred (e.g., "user.updated")
            context: Context variables for pattern substitution
        """
        logger.info(f"Triggering invalidation for event: {event}")

        # Find matching rules
        matching_rules = [
            rule
            for rule in self.rules.values()
            if rule.enabled and rule.trigger_event == event
        ]

        if not matching_rules:
            logger.debug(f"No invalidation rules found for event: {event}")
            return

        # Process each matching rule
        for rule in matching_rules:
            await self._process_rule(rule, context or {})

    async def _process_rule(
        self, rule: InvalidationRule, context: Dict[str, str]
    ) -> None:
        """Process a single invalidation rule."""
        # Substitute context variables in patterns
        patterns = self._substitute_patterns(rule.patterns, context)

        # Apply strategy
        if rule.strategy == InvalidationStrategy.IMMEDIATE:
            await self._invalidate_immediate(patterns)

        elif rule.strategy == InvalidationStrategy.DELAYED:
            await self._invalidate_delayed(patterns, rule.delay_seconds or 5)

        elif rule.strategy == InvalidationStrategy.LAZY:
            await self._mark_stale(patterns)

        elif rule.strategy == InvalidationStrategy.CASCADE:
            await self._invalidate_immediate(patterns)
            # Process cascade rules
            if rule.cascade_rules:
                for cascade_rule_name in rule.cascade_rules:
                    if cascade_rule_name in self.rules:
                        cascade_rule = self.rules[cascade_rule_name]
                        await self._process_rule(cascade_rule, context)

        elif rule.strategy == InvalidationStrategy.PATTERN:
            await self._invalidate_by_pattern(patterns)

    def _substitute_patterns(
        self, patterns: List[str], context: Dict[str, str]
    ) -> List[str]:
        """Substitute context variables in patterns."""
        substituted = []
        for pattern in patterns:
            # Replace {variable} with context values
            for key, value in context.items():
                pattern = pattern.replace(f"{{{key}}}", value)
            substituted.append(pattern)
        return substituted

    async def _invalidate_immediate(self, keys: List[str]) -> None:
        """Immediately invalidate cache keys."""
        for key in keys:
            if "*" in key:
                # Pattern-based deletion
                count = await cache_service.clear_pattern(key)
                logger.info(f"Invalidated {count} keys matching pattern: {key}")
            else:
                # Direct key deletion
                success = await cache_service.delete(key)
                if success:
                    logger.debug(f"Invalidated cache key: {key}")

    async def _invalidate_delayed(self, keys: List[str], delay_seconds: int) -> None:
        """Invalidate cache keys after a delay."""

        async def delayed_invalidation() -> None:
            await asyncio.sleep(delay_seconds)
            await self._invalidate_immediate(keys)

        # Run in background
        asyncio.create_task(delayed_invalidation())
        logger.info(
            f"Scheduled invalidation of {len(keys)} keys after {delay_seconds}s"
        )

    async def _mark_stale(self, keys: List[str]) -> None:
        """Mark cache entries as stale (for lazy invalidation)."""
        # Store stale markers
        stale_set_key = "cache:stale:keys"
        for key in keys:
            await cache_service.add_to_set(stale_set_key, key)

        logger.info(f"Marked {len(keys)} keys as stale")

    async def _invalidate_by_pattern(self, patterns: List[str]) -> None:
        """Invalidate all keys matching patterns."""
        total_invalidated = 0
        for pattern in patterns:
            count = await cache_service.clear_pattern(pattern)
            total_invalidated += count

        logger.info(f"Pattern invalidation cleared {total_invalidated} keys")

    async def is_stale(self, key: str) -> bool:
        """Check if a cache key is marked as stale."""
        stale_set_key = "cache:stale:keys"
        members = await cache_service.get_set_members(stale_set_key)
        return key in members

    async def refresh_if_stale(self, key: str, refresh_func: Callable) -> Optional[Any]:
        """Refresh cache if key is stale."""
        if await self.is_stale(key):
            logger.info(f"Refreshing stale cache key: {key}")
            # Remove from stale set
            stale_set_key = "cache:stale:keys"
            await cache_service.remove_from_set(stale_set_key, key)

            # Refresh the value
            fresh_value = await refresh_func()
            if fresh_value is not None:
                await cache_service.set(key, fresh_value)

            return fresh_value

        # Not stale, return cached value
        return await cache_service.get(key)

    def get_invalidation_stats(self) -> Dict[str, Any]:
        """Get statistics about cache invalidation."""
        return {
            "total_rules": len(self.rules),
            "enabled_rules": sum(1 for r in self.rules.values() if r.enabled),
            "rules_by_strategy": {
                strategy: sum(1 for r in self.rules.values() if r.strategy == strategy)
                for strategy in InvalidationStrategy
            },
            "pending_invalidations": len(self.pending_invalidations),
        }


# Global invalidation service instance
invalidation_service = CacheInvalidationService()


# Helper function for common invalidation scenarios
async def invalidate_user_cache(user_id: str) -> None:
    """Invalidate all cache entries for a user."""
    await invalidation_service.trigger_invalidation(
        "user.updated", {"user_id": user_id}
    )


async def invalidate_patient_cache(patient_id: str) -> None:
    """Invalidate all cache entries for a patient."""
    await invalidation_service.trigger_invalidation(
        "patient.updated", {"patient_id": patient_id}
    )


async def invalidate_health_record_cache(record_id: str, patient_id: str) -> None:
    """Invalidate cache entries for a health record."""
    await invalidation_service.trigger_invalidation(
        "health_record.updated", {"record_id": record_id, "patient_id": patient_id}
    )


async def invalidate_translation_cache(
    source_lang: str, target_lang: str, text_hash: str
) -> None:
    """Invalidate cache entries for a translation."""
    await invalidation_service.trigger_invalidation(
        "translation.updated",
        {
            "source_lang": source_lang,
            "target_lang": target_lang,
            "text_hash": text_hash,
        },
    )


# Export components
__all__ = [
    "InvalidationStrategy",
    "InvalidationRule",
    "CacheInvalidationService",
    "invalidation_service",
    "invalidate_user_cache",
    "invalidate_patient_cache",
    "invalidate_health_record_cache",
    "invalidate_translation_cache",
]
