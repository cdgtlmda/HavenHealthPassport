"""Feature flags configuration for Haven Health Passport.

This module provides a dynamic feature flags system that can be configured
via environment variables, configuration files, or runtime updates.
"""

import os
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class FeatureFlagStatus(str, Enum):
    """Status of a feature flag."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    BETA = "beta"
    CANARY = "canary"
    PERCENTAGE_BASED = "percentage_based"


class FeatureFlag(BaseModel):
    """Model for a feature flag."""

    name: str = Field(..., description="Feature flag name")
    status: FeatureFlagStatus = Field(
        FeatureFlagStatus.DISABLED, description="Current status of the feature"
    )
    description: str = Field("", description="Description of the feature")
    enabled_for_users: list[str] = Field(
        default_factory=list,
        description="List of user IDs for which this feature is enabled",
    )
    enabled_for_roles: list[str] = Field(
        default_factory=list,
        description="List of roles for which this feature is enabled",
    )
    percentage: float = Field(
        0.0,
        ge=0.0,
        le=100.0,
        description="Percentage of users to enable (for percentage-based rollout)",
    )
    start_date: Optional[datetime] = Field(
        None, description="Date when the feature becomes active"
    )
    end_date: Optional[datetime] = Field(
        None, description="Date when the feature becomes inactive"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for the feature"
    )

    def is_enabled_for_user(
        self,
        user_id: Optional[str] = None,
        user_roles: Optional[list[str]] = None,
        user_hash: Optional[int] = None,
    ) -> bool:
        """Check if feature is enabled for a specific user."""
        # Check if feature is globally disabled
        if self.status == FeatureFlagStatus.DISABLED:
            return False

        # Check date constraints
        now = datetime.utcnow()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False

        # Check if feature is globally enabled
        if self.status == FeatureFlagStatus.ENABLED:
            return True

        # Check user-specific enablement
        if user_id and user_id in self.enabled_for_users:
            return True

        # Check role-based enablement
        if user_roles and any(role in self.enabled_for_roles for role in user_roles):
            return True

        # Check percentage-based rollout
        if self.status == FeatureFlagStatus.PERCENTAGE_BASED and user_hash is not None:
            return (user_hash % 100) < self.percentage

        # Beta features are disabled by default unless explicitly enabled
        return False


class FeatureFlagsManager:
    """Manager for feature flags."""

    def __init__(self) -> None:
        """Initialize feature flags manager."""
        self.settings = get_settings()
        self._flags: Dict[str, FeatureFlag] = {}
        self._initialize_default_flags()

    def _initialize_default_flags(self) -> None:
        """Initialize default feature flags."""
        # Core features
        self.register_flag(
            FeatureFlag(
                name="biometric_authentication",
                status=FeatureFlagStatus.ENABLED,
                description="Enable biometric authentication for mobile app",
                percentage=0.0,
                start_date=None,
                end_date=None,
            )
        )

        self.register_flag(
            FeatureFlag(
                name="multi_factor_authentication",
                status=FeatureFlagStatus.ENABLED,
                description="Enable MFA for enhanced security",
                percentage=0.0,
                start_date=None,
                end_date=None,
            )
        )

        self.register_flag(
            FeatureFlag(
                name="blockchain_verification",
                status=FeatureFlagStatus.ENABLED,
                description="Enable blockchain-based health record verification",
                percentage=0.0,
                start_date=None,
                end_date=None,
            )
        )

        self.register_flag(
            FeatureFlag(
                name="ai_translation",
                status=FeatureFlagStatus.ENABLED,
                description="Enable AI-powered medical translation",
                percentage=0.0,
                start_date=None,
                end_date=None,
            )
        )

        self.register_flag(
            FeatureFlag(
                name="voice_processing",
                status=FeatureFlagStatus.ENABLED,
                description="Enable voice-based data entry and processing",
                percentage=0.0,
                start_date=None,
                end_date=None,
            )
        )

        self.register_flag(
            FeatureFlag(
                name="offline_mode",
                status=FeatureFlagStatus.ENABLED,
                description="Enable offline functionality for mobile app",
                percentage=0.0,
                start_date=None,
                end_date=None,
            )
        )

        self.register_flag(
            FeatureFlag(
                name="real_time_sync",
                status=FeatureFlagStatus.ENABLED,
                description="Enable real-time data synchronization",
                percentage=0.0,
                start_date=None,
                end_date=None,
            )
        )

        # Beta features
        self.register_flag(
            FeatureFlag(
                name="advanced_analytics",
                status=FeatureFlagStatus.BETA,
                description="Advanced analytics dashboard for organizations",
                percentage=0.0,
                start_date=None,
                end_date=None,
            )
        )

        self.register_flag(
            FeatureFlag(
                name="third_party_integrations",
                status=FeatureFlagStatus.DISABLED,
                description="Enable third-party healthcare system integrations",
                percentage=0.0,
                start_date=None,
                end_date=None,
            )
        )

        # Canary features
        self.register_flag(
            FeatureFlag(
                name="predictive_health_insights",
                status=FeatureFlagStatus.CANARY,
                description="AI-powered predictive health insights",
                percentage=5.0,
                start_date=None,
                end_date=None,
            )
        )

        self.register_flag(
            FeatureFlag(
                name="automated_appointment_scheduling",
                status=FeatureFlagStatus.PERCENTAGE_BASED,
                description="Automated appointment scheduling system",
                percentage=20.0,
                start_date=None,
                end_date=None,
            )
        )

        # Security features
        self.register_flag(
            FeatureFlag(
                name="enhanced_encryption",
                status=FeatureFlagStatus.ENABLED,
                description="Enhanced encryption for sensitive data",
                percentage=0.0,
                start_date=None,
                end_date=None,
            )
        )

        self.register_flag(
            FeatureFlag(
                name="zero_trust_security",
                status=FeatureFlagStatus.BETA,
                description="Zero trust security model implementation",
                percentage=0.0,
                start_date=None,
                end_date=None,
            )
        )

        # Load environment-based overrides
        self._load_environment_overrides()

    def _load_environment_overrides(self) -> None:
        """Load feature flag overrides from environment variables."""
        for flag_name, flag in self._flags.items():
            env_var = f"FEATURE_FLAG_{flag_name.upper()}"
            env_value = os.getenv(env_var)

            if env_value:
                try:
                    if env_value.lower() in ["true", "enabled", "1"]:
                        flag.status = FeatureFlagStatus.ENABLED
                    elif env_value.lower() in ["false", "disabled", "0"]:
                        flag.status = FeatureFlagStatus.DISABLED
                    else:
                        flag.status = FeatureFlagStatus(env_value.lower())

                    logger.info(
                        "Feature flag override from environment",
                        flag=flag_name,
                        status=flag.status,
                    )
                except ValueError:
                    logger.warning(
                        "Invalid feature flag value in environment",
                        flag=flag_name,
                        value=env_value,
                    )

    def register_flag(self, flag: FeatureFlag) -> None:
        """Register a new feature flag."""
        self._flags[flag.name] = flag
        logger.info("Feature flag registered", flag=flag.name, status=flag.status)

    def get_flag(self, name: str) -> Optional[FeatureFlag]:
        """Get a feature flag by name."""
        return self._flags.get(name)

    def is_enabled(
        self,
        flag_name: str,
        user_id: Optional[str] = None,
        user_roles: Optional[list[str]] = None,
    ) -> bool:
        """Check if a feature flag is enabled."""
        flag = self.get_flag(flag_name)

        if not flag:
            logger.warning("Unknown feature flag requested", flag=flag_name)
            return False

        # Generate user hash for percentage-based rollout
        user_hash = None
        if user_id:
            user_hash = hash(user_id) % 100

        return flag.is_enabled_for_user(user_id, user_roles, user_hash)

    def update_flag(
        self,
        flag_name: str,
        status: Optional[FeatureFlagStatus] = None,
        percentage: Optional[float] = None,
        enabled_for_users: Optional[list[str]] = None,
        enabled_for_roles: Optional[list[str]] = None,
    ) -> Optional[FeatureFlag]:
        """Update a feature flag configuration."""
        flag = self.get_flag(flag_name)

        if not flag:
            logger.error("Attempted to update non-existent flag", flag=flag_name)
            return None

        if status is not None:
            flag.status = status

        if percentage is not None:
            flag.percentage = percentage

        if enabled_for_users is not None:
            flag.enabled_for_users = enabled_for_users

        if enabled_for_roles is not None:
            flag.enabled_for_roles = enabled_for_roles

        logger.info(
            "Feature flag updated",
            flag=flag_name,
            status=flag.status,
            percentage=flag.percentage,
        )

        return flag

    def get_all_flags(self) -> Dict[str, FeatureFlag]:
        """Get all registered feature flags."""
        return self._flags.copy()

    def get_enabled_features(
        self, user_id: Optional[str] = None, user_roles: Optional[list[str]] = None
    ) -> list[str]:
        """Get list of enabled features for a user."""
        enabled = []

        for flag_name, _ in self._flags.items():
            if self.is_enabled(flag_name, user_id, user_roles):
                enabled.append(flag_name)

        return enabled


# Global feature flags manager instance
_feature_flags_manager: Optional[FeatureFlagsManager] = None


def get_feature_flags_manager() -> FeatureFlagsManager:
    """Get the global feature flags manager instance."""
    global _feature_flags_manager  # pylint: disable=global-statement

    if _feature_flags_manager is None:
        _feature_flags_manager = FeatureFlagsManager()

    return _feature_flags_manager


# Convenience functions
def is_feature_enabled(
    flag_name: str,
    user_id: Optional[str] = None,
    user_roles: Optional[list[str]] = None,
) -> bool:
    """Check if a feature is enabled."""
    manager = get_feature_flags_manager()
    return manager.is_enabled(flag_name, user_id, user_roles)


def register_feature_flag(flag: FeatureFlag) -> None:
    """Register a new feature flag."""
    manager = get_feature_flags_manager()
    manager.register_flag(flag)


def update_feature_flag(flag_name: str, **kwargs: Any) -> Optional[FeatureFlag]:
    """Update a feature flag."""
    manager = get_feature_flags_manager()
    return manager.update_flag(flag_name, **kwargs)


__all__ = [
    "FeatureFlagStatus",
    "FeatureFlag",
    "FeatureFlagsManager",
    "get_feature_flags_manager",
    "is_feature_enabled",
    "register_feature_flag",
    "update_feature_flag",
]
