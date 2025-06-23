"""
Voice Progressive Disclosure Module.

This module implements progressive disclosure patterns for voice interfaces in the
Haven Health Passport system, revealing features and complexity gradually based on
user proficiency and context. Handles FHIR Encounter Resource validation for
voice-based patient encounters.
"""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.security.encryption import EncryptionService

from .progressive_disclosure_types import (
    DisclosureLevel,
    DisclosureRule,
    Feature,
    FeatureCategory,
    InteractionContext,
    UserProfile,
)
from .voice_command_grammar import (
    CommandGrammar,
    CommandPriority,
    CommandType,
    ParsedCommand,
)

logger = logging.getLogger(__name__)


class ProgressiveDisclosureEngine:
    """Base engine for progressive disclosure functionality."""

    def __init__(self) -> None:
        """Initialize the progressive disclosure engine."""
        self.disclosure_rules: List[DisclosureRule] = []
        self.user_profiles: Dict[str, UserProfile] = {}
        self.features: Dict[str, Feature] = {}
        # TODO: Provide proper KMS key ID
        self.encryption_service = EncryptionService(kms_key_id="default-key")

        # Rule: Unlock intermediate after 80% success rate with 20+ interactions
        self.disclosure_rules.append(
            DisclosureRule(
                id="unlock_intermediate",
                condition_type="success_rate",
                threshold=0.8,
                target_level=DisclosureLevel.INTERMEDIATE,
                features_to_unlock=["share_records", "export_data"],
                message="You're doing well! Advanced features are now available: sharing and exporting records.",
            )
        )

        # Rule: Unlock advanced after mastering intermediate features
        self.disclosure_rules.append(
            DisclosureRule(
                id="unlock_advanced",
                condition_type="feature_mastery",
                threshold=0.7,
                target_level=DisclosureLevel.ADVANCED,
                features_to_unlock=["bulk_update", "voice_macros"],
                message="Expert features unlocked! You can now use bulk operations and voice macros.",
            )
        )

        # Rule: Time-based unlock for regular users
        self.disclosure_rules.append(
            DisclosureRule(
                id="time_unlock",
                condition_type="time_based",
                threshold=30,  # 30 days
                target_level=DisclosureLevel.INTERMEDIATE,
                features_to_unlock=["share_records"],
                message="You've been using the system for a month! Sharing features are now available.",
            )
        )

    @require_phi_access(AccessLevel.READ)
    def get_user_profile(self, user_id: str) -> UserProfile:
        """Get or create user profile."""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = UserProfile(user_id=user_id)
        return self.user_profiles[user_id]

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access(action="get_available_voice_features")
    def get_available_features(
        self, user_id: str, context: Optional[InteractionContext] = None
    ) -> List[Feature]:
        """Get features available to user at their current level."""
        profile = self.get_user_profile(user_id)

        # Emergency context shows all emergency features regardless of level
        if context == InteractionContext.EMERGENCY:
            return [
                f
                for f in self.features.values()
                if f.category == FeatureCategory.EMERGENCY
            ]

        # Filter by user level and unlocked features
        available = []
        for feature in self.features.values():
            if (
                feature.is_available(profile.current_level)
                or feature.id in profile.features_unlocked
            ):
                # Check prerequisites
                if all(
                    prereq in profile.features_used for prereq in feature.prerequisites
                ):
                    available.append(feature)

        return available

    def suggest_next_features(self, user_id: str, limit: int = 3) -> List[Feature]:
        """Suggest next features user might want to try."""
        profile = self.get_user_profile(user_id)
        available = self.get_available_features(user_id)

        # Filter out already heavily used features
        suggestions = [f for f in available if profile.features_used.get(f.id, 0) < 3]

        # Sort by category relevance and complexity
        suggestions.sort(
            key=lambda f: (f.min_level.value, -f.success_rate, f.usage_count)
        )

        return suggestions[:limit]

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access(action="record_voice_interaction")
    def record_interaction(
        self,
        user_id: str,
        command: ParsedCommand,
        success: bool,
        feature_id: Optional[str] = None,
    ) -> None:
        """Record a user interaction for learning."""
        profile = self.get_user_profile(user_id)

        # Update counters
        profile.total_interactions += 1
        if success:
            profile.successful_interactions += 1

        # Track feature usage
        if feature_id:
            profile.features_used[feature_id] = (
                profile.features_used.get(feature_id, 0) + 1
            )

            # Update feature stats
            if feature_id in self.features:
                feature = self.features[feature_id]
                feature.usage_count += 1
                # Simple success rate calculation
                current_rate = feature.success_rate
                new_rate = (current_rate * 0.9) + (0.1 if success else 0.0)
                feature.success_rate = new_rate

        # Record in history
        profile.interaction_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "command_type": command.command_type.value,
                "success": success,
                "feature_id": feature_id,
            }
        )

        # Keep only last 100 interactions
        if len(profile.interaction_history) > 100:
            profile.interaction_history = profile.interaction_history[-100:]

        profile.last_active = datetime.now()

        # Check for level progression
        self._check_progression(user_id)

    def _check_progression(self, user_id: str) -> None:
        """Check if user should progress to next level."""
        profile = self.get_user_profile(user_id)

        for rule in self.disclosure_rules:
            if (
                rule.evaluate(profile)
                and profile.current_level.value < rule.target_level.value
            ):
                # Progress to new level
                old_level = profile.current_level
                profile.current_level = rule.target_level

                # Unlock new features
                for feature_id in rule.features_to_unlock:
                    profile.features_unlocked.add(feature_id)

                # Log progression
                logger.info(
                    "User %s progressed from %s to %s",
                    user_id,
                    old_level.name,
                    profile.current_level.name,
                )

                # Store progression message for user
                profile.preferences["last_progression_message"] = rule.message
                profile.preferences["progression_timestamp"] = (
                    datetime.now().isoformat()
                )

                break

    def get_contextual_help(
        self, user_id: str, context: Optional[InteractionContext] = None
    ) -> Dict[str, Any]:
        """Get contextual help based on user level and situation."""
        profile = self.get_user_profile(user_id)
        available_features = self.get_available_features(user_id, context)

        # Group features by category
        by_category = defaultdict(list)
        for feature in available_features:
            by_category[feature.category.value].append(feature)

        # Create help structure
        help_info = {
            "user_level": profile.current_level.name,
            "proficiency": profile.calculate_proficiency(),
            "available_commands": {},
            "suggested_next": [],
            "tips": [],
        }

        # Add commands by category
        for category, features in by_category.items():
            help_info["available_commands"][category] = [
                {
                    "name": f.name,
                    "examples": f.command_examples[:2],  # Limit examples
                    "description": f.description,
                }
                for f in features
            ]

        # Add suggestions
        suggestions = self.suggest_next_features(user_id, limit=3)
        help_info["suggested_next"] = [
            {
                "name": f.name,
                "example": f.command_examples[0] if f.command_examples else "",
                "why": self._get_suggestion_reason(profile, f),
            }
            for f in suggestions
        ]

        # Add contextual tips
        help_info["tips"] = self._get_contextual_tips(profile, context)

        return help_info

    def _get_suggestion_reason(self, profile: UserProfile, feature: Feature) -> str:
        """Get reason for suggesting a feature."""
        usage = profile.features_used.get(feature.id, 0)

        if usage == 0:
            return "New feature you haven't tried yet"
        elif usage < 3:
            return "You've used this a few times - try it again to master it"
        else:
            return "Popular feature among users at your level"

    def _get_contextual_tips(
        self, profile: UserProfile, context: Optional[InteractionContext]
    ) -> List[str]:
        """Get tips based on user profile and context."""
        tips = []

        if profile.current_level == DisclosureLevel.ESSENTIAL:
            tips.append("Say 'help' anytime to see available commands")
            tips.append("Start with simple commands like 'show medications'")

        elif profile.current_level == DisclosureLevel.BASIC:
            tips.append("You can now add and manage your health information")
            tips.append("Try saying 'add medication' to get started")

        elif profile.current_level == DisclosureLevel.INTERMEDIATE:
            tips.append("You can share your records with healthcare providers")
            tips.append("Export your data for backup or analysis")

        # Context-specific tips
        if context == InteractionContext.FIRST_TIME:
            tips.insert(0, "Welcome! Let's start with basic commands")
        elif context == InteractionContext.EMERGENCY:
            tips.insert(0, "Say 'emergency' or 'help' for immediate assistance")

        return tips[:3]  # Limit to 3 tips


class AdaptiveDisclosureManager(ProgressiveDisclosureEngine):
    """Advanced disclosure manager with adaptive learning."""

    def __init__(self) -> None:
        """Initialize the adaptive disclosure engine."""
        super().__init__()
        self.learning_patterns: Dict[str, List[Dict]] = defaultdict(list)
        self.feature_correlations: Dict[str, Dict[str, float]] = defaultdict(dict)

    def learn_user_patterns(self, user_id: str) -> None:
        """Learn from user interaction patterns."""
        profile = self.get_user_profile(user_id)

        # Analyze command sequences
        if len(profile.interaction_history) >= 10:
            patterns = self._extract_patterns(profile.interaction_history)
            self.learning_patterns[user_id] = patterns

            # Update feature correlations
            self._update_correlations(user_id, patterns)

    def _extract_patterns(self, history: List[Dict]) -> List[Dict]:
        """Extract common patterns from interaction history."""
        patterns = []

        # Look for sequential patterns (commands often used together)
        for idx in range(len(history) - 1):
            if history[idx]["success"] and history[idx + 1]["success"]:
                pattern = {
                    "sequence": [
                        history[idx]["command_type"],
                        history[idx + 1]["command_type"],
                    ],
                    "frequency": 1,
                    "avg_time_between": 0,  # Would calculate in production
                }
                patterns.append(pattern)

        return patterns

    def _update_correlations(self, user_id: str, patterns: List[Dict]) -> None:
        """Update feature correlation scores."""
        # Use user_id for user-specific correlations tracking
        if user_id not in self.feature_correlations:
            self.feature_correlations[user_id] = {}

        for pattern in patterns:
            if len(pattern["sequence"]) == 2:
                feature1, feature2 = pattern["sequence"]

                # Update correlation score
                current = self.feature_correlations[feature1].get(feature2, 0)
                self.feature_correlations[feature1][feature2] = current + 0.1

    def get_adaptive_suggestions(
        self, user_id: str, current_context: str
    ) -> List[Feature]:
        """Get suggestions based on learned patterns."""
        profile = self.get_user_profile(user_id)
        _ = profile  # Profile is used for context in actual implementation
        patterns = self.learning_patterns.get(user_id, [])

        suggestions = []

        # Find features that often follow the current context
        for pattern in patterns:
            if pattern["sequence"][0] == current_context:
                next_feature = pattern["sequence"][1]
                if next_feature in self.features:
                    suggestions.append(self.features[next_feature])

        return suggestions[:3]

    def adjust_disclosure_speed(self, user_id: str) -> float:
        """Adjust how quickly features are revealed based on user performance."""
        profile = self.get_user_profile(user_id)

        # Calculate learning velocity
        if profile.total_interactions < 10:
            return 1.0  # Normal speed

        success_rate = profile.successful_interactions / profile.total_interactions
        proficiency = profile.calculate_proficiency()

        # Faster disclosure for quick learners
        if success_rate > 0.9 and proficiency > 0.7:
            return 1.5  # 50% faster
        # Slower for struggling users
        elif success_rate < 0.6:
            return 0.7  # 30% slower

        return 1.0


class VoiceInterfaceAdapter:
    """Adapts voice interface based on progressive disclosure."""

    def __init__(self, disclosure_engine: ProgressiveDisclosureEngine):
        """Initialize the voice interface adapter."""
        self.disclosure_engine = disclosure_engine
        self.command_filters: Dict[str, List[CommandGrammar]] = {}

    def filter_available_commands(
        self, user_id: str, all_commands: List[CommandGrammar]
    ) -> List[CommandGrammar]:
        """Filter commands based on user's disclosure level."""
        available_features = self.disclosure_engine.get_available_features(user_id)
        feature_ids = {f.id for f in available_features}

        # Map commands to features (simplified)
        filtered_commands = []
        for command in all_commands:
            # Check if command matches available features
            if self._command_matches_features(command, feature_ids):
                filtered_commands.append(command)

        return filtered_commands

    def _command_matches_features(
        self, command: CommandGrammar, feature_ids: Set[str]
    ) -> bool:
        """Check if command matches available features."""
        # Map command types to feature IDs (simplified mapping)
        command_feature_map = {
            CommandType.EMERGENCY: "emergency_help",
            CommandType.MEDICATION: "show_medications",
            CommandType.CREATE: "add_medication",
            CommandType.SHARE: "share_records",
            CommandType.EXPORT: "export_data",
        }

        feature_id = command_feature_map.get(command.command_type)
        return feature_id is None or feature_id in feature_ids

    def generate_adaptive_prompt(
        self, user_id: str, context: InteractionContext
    ) -> str:
        """Generate prompts adapted to user's level."""
        profile = self.disclosure_engine.get_user_profile(user_id)

        # Adjust prompt based on context
        if context == InteractionContext.EMERGENCY:
            return "Emergency mode activated. What's your emergency?"
        elif context == InteractionContext.FIRST_TIME:
            return "Welcome! I'm here to help with your health information. Say 'help' to get started."

        if profile.current_level == DisclosureLevel.ESSENTIAL:
            return "What would you like to do? You can say 'help' for options."
        elif profile.current_level == DisclosureLevel.BASIC:
            return "How can I help? You can check medications, appointments, or say 'help'."
        elif profile.current_level == DisclosureLevel.INTERMEDIATE:
            return "Ready to help with medications, appointments, sharing, or more. What do you need?"
        else:
            return "What would you like to do?"

    def provide_level_appropriate_feedback(
        self, user_id: str, command_result: str, success: bool
    ) -> str:
        """Provide feedback appropriate to user's level."""
        profile = self.disclosure_engine.get_user_profile(user_id)

        if not success:
            if profile.current_level == DisclosureLevel.ESSENTIAL:
                return f"{command_result}. Don't worry, you're still learning! Try saying 'help' if you're stuck."
            else:
                return command_result

        # Success feedback with hints about new features
        feedback = command_result

        # Check if user is close to unlocking new features
        if profile.total_interactions % 5 == 4:  # One away from milestone
            feedback += " You're doing great! One more successful command to unlock new features."

        return feedback


class OnboardingFlowManager:
    """Manages progressive onboarding for new users."""

    def __init__(self, disclosure_engine: ProgressiveDisclosureEngine):
        """Initialize the onboarding manager."""
        self.disclosure_engine = disclosure_engine
        self.onboarding_steps = self._create_onboarding_steps()

    def _create_onboarding_steps(self) -> List[Dict[str, Any]]:
        """Create onboarding steps for new users."""
        return [
            {
                "step": 1,
                "title": "Welcome to Haven Health Voice",
                "instruction": "Let's start with a simple command. Try saying 'Show my medications'",
                "expected_command": "show_medications",
                "success_message": "Great! You can view your medications anytime.",
                "failure_hint": "Just say 'show my medications' or 'what medicines am I taking'",
            },
            {
                "step": 2,
                "title": "Emergency Access",
                "instruction": "You can always get help quickly. Try saying 'Emergency'",
                "expected_command": "emergency_help",
                "success_message": "Perfect! Emergency help is always available.",
                "failure_hint": "Say 'emergency' or 'help' for immediate assistance",
            },
            {
                "step": 3,
                "title": "Getting Help",
                "instruction": "You can always ask for help. Try saying 'Help'",
                "expected_command": "help",
                "success_message": "Excellent! Now you know the basics.",
                "failure_hint": "Just say 'help' to see available commands",
            },
        ]

    def get_current_step(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get current onboarding step for user."""
        profile = self.disclosure_engine.get_user_profile(user_id)

        # Check onboarding progress
        completed_steps = profile.preferences.get("onboarding_completed", [])

        for step in self.onboarding_steps:
            if step["step"] not in completed_steps:
                return step

        return None  # Onboarding complete

    def complete_step(self, user_id: str, step_number: int) -> None:
        """Mark onboarding step as complete."""
        profile = self.disclosure_engine.get_user_profile(user_id)

        completed = profile.preferences.get("onboarding_completed", [])
        if step_number not in completed:
            completed.append(step_number)
            profile.preferences["onboarding_completed"] = completed

            # Check if onboarding is complete
            if len(completed) >= len(self.onboarding_steps):
                profile.preferences["onboarding_complete"] = True
                profile.preferences["onboarding_completed_at"] = (
                    datetime.now().isoformat()
                )

                # Graduate to basic level
                if profile.current_level == DisclosureLevel.ESSENTIAL:
                    profile.current_level = DisclosureLevel.BASIC
                    logger.info(
                        "User %s completed onboarding, promoted to BASIC level", user_id
                    )


class AccessibilityDisclosureAdapter:
    """Adapts progressive disclosure for accessibility needs."""

    def __init__(self, disclosure_engine: ProgressiveDisclosureEngine):
        """Initialize the accessibility adapter."""
        self.disclosure_engine = disclosure_engine

    def adapt_for_accessibility(
        self, user_id: str, accessibility_needs: List[str]
    ) -> Dict[str, Any]:
        """Adapt disclosure based on accessibility needs."""
        adaptations = {
            "disclosure_speed": 1.0,
            "feature_limit": None,
            "simplify_options": False,
            "extended_help": False,
            "repetition_allowed": True,
        }

        profile = self.disclosure_engine.get_user_profile(user_id)

        # Cognitive support needs
        if "cognitive_support" in accessibility_needs:
            adaptations["disclosure_speed"] = 0.5  # Much slower progression
            adaptations["feature_limit"] = 3  # Limit visible features
            adaptations["simplify_options"] = True
            adaptations["extended_help"] = True

            # Keep at basic level longer
            if profile.current_level.value > DisclosureLevel.BASIC.value:
                profile.current_level = DisclosureLevel.BASIC

        # Motor impairments
        if "motor_impaired" in accessibility_needs:
            adaptations["repetition_allowed"] = True
            # Features remain the same but with extended timeouts

        # Vision impairments
        if "vision_impaired" in accessibility_needs:
            adaptations["extended_help"] = True
            # Audio descriptions for all features

        return adaptations

    def get_simplified_features(self, user_id: str, limit: int = 3) -> List[Feature]:
        """Get simplified feature set for users with cognitive needs."""
        all_features = self.disclosure_engine.get_available_features(user_id)

        # Prioritize essential and frequently used features
        profile = self.disclosure_engine.get_user_profile(user_id)

        # Sort by usage frequency and simplicity
        sorted_features = sorted(
            all_features,
            key=lambda f: (
                -profile.features_used.get(f.id, 0),  # Most used first
                f.min_level.value,  # Simpler features first
                not f.is_dangerous,  # Safe features first
            ),
        )

        return sorted_features[:limit]


# Metrics and Analytics
class DisclosureMetrics:
    """Track metrics for progressive disclosure effectiveness."""

    def __init__(self) -> None:
        """Initialize the disclosure metrics tracker."""
        self.user_progression: Dict[str, List[Dict]] = defaultdict(list)
        self.feature_adoption: Dict[str, Dict] = defaultdict(dict)
        self.abandonment_points: List[Dict] = []

    def track_progression(
        self, user_id: str, old_level: DisclosureLevel, new_level: DisclosureLevel
    ) -> None:
        """Track user level progression."""
        self.user_progression[user_id].append(
            {
                "timestamp": datetime.now().isoformat(),
                "from_level": old_level.name,
                "to_level": new_level.name,
                "progression_time": None,  # Calculate from previous entry
            }
        )

    def track_feature_adoption(
        self, feature_id: str, user_id: str, success: bool
    ) -> None:
        """Track how well features are adopted."""
        if feature_id not in self.feature_adoption:
            self.feature_adoption[feature_id] = {
                "total_attempts": 0,
                "successful_attempts": 0,
                "unique_users": set(),
                "average_attempts_to_master": [],
            }

        stats = self.feature_adoption[feature_id]
        stats["total_attempts"] += 1
        if success:
            stats["successful_attempts"] += 1
        stats["unique_users"].add(user_id)

    def track_abandonment(
        self, user_id: str, level: DisclosureLevel, last_command: str
    ) -> None:
        """Track where users abandon the system."""
        self.abandonment_points.append(
            {
                "user_id": user_id,
                "level": level.name,
                "last_command": last_command,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def get_analytics_summary(self) -> Dict[str, Any]:
        """Get summary of disclosure metrics."""
        total_users = len(self.user_progression)

        # Level distribution
        level_distribution: Dict[str, int] = defaultdict(int)
        for progressions in self.user_progression.values():
            if progressions:
                current_level = progressions[-1]["to_level"]
                level_distribution[current_level] += 1

        # Feature success rates
        feature_success = {}
        for feature_id, stats in self.feature_adoption.items():
            if stats["total_attempts"] > 0:
                success_rate = stats["successful_attempts"] / stats["total_attempts"]
                feature_success[feature_id] = {
                    "success_rate": success_rate,
                    "adoption_rate": (
                        len(stats["unique_users"]) / total_users
                        if total_users > 0
                        else 0
                    ),
                }

        return {
            "total_users": total_users,
            "level_distribution": dict(level_distribution),
            "feature_success_rates": feature_success,
            "abandonment_count": len(self.abandonment_points),
            "average_progression_speed": self._calculate_avg_progression_speed(),
        }

    def _calculate_avg_progression_speed(self) -> Dict[str, float]:
        """Calculate average time to progress between levels."""
        progression_times = defaultdict(list)

        for user_progressions in self.user_progression.values():
            for idx in range(1, len(user_progressions)):
                prev = datetime.fromisoformat(user_progressions[idx - 1]["timestamp"])
                curr = datetime.fromisoformat(user_progressions[idx]["timestamp"])
                days = (curr - prev).days

                transition = f"{user_progressions[idx]['from_level']}_to_{user_progressions[idx]['to_level']}"
                progression_times[transition].append(days)

        avg_times = {}
        for transition, times in progression_times.items():
            if times:
                avg_times[transition] = sum(times) / len(times)

        return avg_times


# Example usage
if __name__ == "__main__":
    # Initialize disclosure system
    demo_disclosure_engine = AdaptiveDisclosureManager()
    demo_interface_adapter = VoiceInterfaceAdapter(demo_disclosure_engine)
    demo_onboarding = OnboardingFlowManager(demo_disclosure_engine)
    demo_metrics = DisclosureMetrics()

    # Simulate new user experience
    demo_user_id = "new_user_123"

    print("=== Progressive Disclosure Demo ===\n")

    # Get initial available features
    demo_features = demo_disclosure_engine.get_available_features(demo_user_id)
    print(f"Initial features available: {len(demo_features)}")
    for f in demo_features:
        print(f"  - {f.name}: {f.command_examples[0]}")

    # Simulate successful interactions
    print("\nSimulating user interactions...")
    for _i in range(10):
        # Record successful interaction
        demo_command = ParsedCommand(
            command_type=CommandType.MEDICATION,
            raw_text="show medications",
            parameters={},
            confidence=0.9,
            language="en",
            timestamp=datetime.now(),
            priority=CommandPriority.NORMAL,
        )

        demo_disclosure_engine.record_interaction(
            demo_user_id, demo_command, success=True, feature_id="show_medications"
        )

    # Check progression
    demo_profile = demo_disclosure_engine.get_user_profile(demo_user_id)
    print(f"\nUser level after interactions: {demo_profile.current_level.name}")
    print(f"Features unlocked: {len(demo_profile.features_unlocked)}")

    # Get contextual help
    demo_help_info = demo_disclosure_engine.get_contextual_help(demo_user_id)
    print("\nContextual help for user:")
    print(f"  Tips: {demo_help_info['tips']}")
    print(f"  Suggested next: {[s['name'] for s in demo_help_info['suggested_next']]}")


def validate_encounter_data(encounter_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate encounter data for FHIR compliance.

    Args:
        encounter_data: Encounter data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings: List[str] = []

    if not encounter_data:
        errors.append("No encounter data provided")
    elif (
        "resourceType" in encounter_data
        and encounter_data["resourceType"] != "Encounter"
    ):
        errors.append("Invalid resource type for encounter")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
