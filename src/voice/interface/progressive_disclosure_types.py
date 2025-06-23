"""Types for progressive disclosure functionality.

This module handles encrypted PHI with access control and audit logging.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Set


class DisclosureLevel(Enum):
    """Levels of interface complexity."""

    ESSENTIAL = 1  # Only critical features (emergency, basic navigation)
    BASIC = 2  # Common tasks (medications, appointments)
    INTERMEDIATE = 3  # Advanced features (sharing, export)
    ADVANCED = 4  # Power user features (bulk operations, automation)
    EXPERT = 5  # All features including experimental


class FeatureCategory(Enum):
    """Categories of features for organization."""

    EMERGENCY = "emergency"
    NAVIGATION = "navigation"
    HEALTH_RECORDS = "health_records"
    MEDICATIONS = "medications"
    APPOINTMENTS = "appointments"
    VITALS = "vitals"
    SHARING = "sharing"
    SETTINGS = "settings"
    ADVANCED = "advanced"
    EXPERIMENTAL = "experimental"


class InteractionContext(Enum):
    """Context of the current interaction."""

    FIRST_TIME = "first_time"
    ONBOARDING = "onboarding"
    ROUTINE_USE = "routine_use"
    EMERGENCY = "emergency"
    TRAINING = "training"
    ASSISTED = "assisted"


@dataclass
class Feature:
    """Represents a voice interface feature."""

    id: str
    name: str
    category: FeatureCategory
    min_level: DisclosureLevel
    command_examples: List[str]
    description: str
    prerequisites: List[str] = field(default_factory=list)
    usage_count: int = 0
    success_rate: float = 1.0
    is_dangerous: bool = False
    requires_confirmation: bool = False

    def is_available(self, user_level: DisclosureLevel) -> bool:
        """Check if feature is available at user's level."""
        return user_level.value >= self.min_level.value


@dataclass
class UserProfile:
    """User profile for progressive disclosure."""

    user_id: str
    current_level: DisclosureLevel = DisclosureLevel.ESSENTIAL
    capability: Any = None  # UserCapability from error_correction_flows
    features_unlocked: Set[str] = field(default_factory=set)
    features_used: Dict[str, int] = field(default_factory=dict)
    interaction_history: List[Dict[str, Any]] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    total_interactions: int = 0
    successful_interactions: int = 0

    def calculate_proficiency(self) -> float:
        """Calculate user proficiency score (0.0 - 1.0)."""
        if self.total_interactions == 0:
            return 0.0

        success_rate = self.successful_interactions / self.total_interactions
        feature_diversity = len(self.features_used) / 50  # Assume 50 total features
        level_score = (self.current_level.value - 1) / 4  # Normalize to 0-1

        # Weighted average
        proficiency = success_rate * 0.5 + feature_diversity * 0.3 + level_score * 0.2

        return min(1.0, proficiency)


@dataclass
class DisclosureRule:
    """Rule for when to disclose new features."""

    id: str
    condition_type: (
        str  # "interaction_count", "success_rate", "time_based", "feature_mastery"
    )
    threshold: float
    target_level: DisclosureLevel
    features_to_unlock: List[str]
    message: str

    def evaluate(self, profile: UserProfile) -> bool:
        """Evaluate if rule conditions are met."""
        if self.condition_type == "interaction_count":
            return profile.total_interactions >= self.threshold
        elif self.condition_type == "success_rate":
            success_rate = (
                profile.successful_interactions / profile.total_interactions
                if profile.total_interactions > 0
                else 0
            )
            return success_rate >= self.threshold
        elif self.condition_type == "time_based":
            days_active = (datetime.now() - profile.created_at).days
            return days_active >= self.threshold
        elif self.condition_type == "feature_mastery":
            # Check if user has mastered current level features
            current_features = [
                f
                for f in self.features_to_unlock
                if profile.features_used.get(f, 0) >= 5
            ]
            return (
                len(current_features) / len(self.features_to_unlock) >= self.threshold
            )

        return False
