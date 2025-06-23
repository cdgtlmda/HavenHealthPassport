"""Voice Shortcuts Module.

This module implements voice shortcuts for quick access to common functions
in the Haven Health Passport system.

Security Note: All PHI data accessed through voice shortcuts must be encrypted at rest
and in transit using AES-256 encryption standards.

Access Control: Voice shortcut functionality requires proper authentication and authorization
to ensure PHI data is only accessible to authorized users.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .voice_command_grammar import CommandPriority

logger = logging.getLogger(__name__)


class ShortcutCategory(Enum):
    """Categories for voice shortcuts."""

    NAVIGATION = "navigation"
    QUICK_ACTION = "quick_action"
    EMERGENCY = "emergency"
    MEDICAL_RECORD = "medical_record"
    COMMUNICATION = "communication"
    STATUS_CHECK = "status_check"
    SETTINGS = "settings"


class ShortcutScope(Enum):
    """Scope/context where shortcuts are available."""

    GLOBAL = "global"  # Available everywhere
    HOME = "home"  # Only on home screen
    MEDICAL = "medical"  # In medical contexts
    PROFILE = "profile"  # In profile/settings
    EMERGENCY = "emergency"  # Emergency mode


@dataclass
class VoiceShortcut:
    """Represents a voice shortcut configuration."""

    phrase: str  # The shortcut phrase
    full_command: str  # The full command it maps to
    category: ShortcutCategory
    scope: ShortcutScope = ShortcutScope.GLOBAL
    priority: CommandPriority = CommandPriority.NORMAL
    description: str = ""
    aliases: List[str] = field(default_factory=list)
    context_requirements: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def matches(self, input_phrase: str) -> bool:
        """Check if input matches this shortcut."""
        input_lower = input_phrase.lower().strip()

        # Check main phrase
        if input_lower == self.phrase.lower():
            return True

        # Check aliases
        for alias in self.aliases:
            if input_lower == alias.lower():
                return True

        return False

    def is_available_in_scope(self, current_scope: ShortcutScope) -> bool:
        """Check if shortcut is available in current scope."""
        return self.scope == ShortcutScope.GLOBAL or self.scope == current_scope


@dataclass
class ShortcutMatch:
    """Result of shortcut matching."""

    shortcut: VoiceShortcut
    matched_phrase: str
    confidence: float = 1.0

    def to_command(self) -> str:
        """Convert to full command."""
        return self.shortcut.full_command


@dataclass
class ShortcutConfig:
    """Configuration for voice shortcuts."""

    shortcuts: List[VoiceShortcut] = field(default_factory=list)
    fuzzy_matching: bool = True
    min_confidence: float = 0.8
    max_shortcuts_per_category: int = 10
    allow_custom_shortcuts: bool = True

    def __post_init__(self) -> None:
        """Initialize with default shortcuts if none provided."""
        if not self.shortcuts:
            self._add_default_shortcuts()

    def _add_default_shortcuts(self) -> None:
        """Add default system shortcuts."""
        self.shortcuts.extend(
            [
                # Navigation shortcuts
                VoiceShortcut(
                    phrase="home",
                    full_command="go to home",
                    category=ShortcutCategory.NAVIGATION,
                    description="Navigate to home screen",
                ),
                VoiceShortcut(
                    phrase="back",
                    full_command="go back",
                    category=ShortcutCategory.NAVIGATION,
                    description="Go back to previous screen",
                ),
                VoiceShortcut(
                    phrase="meds",
                    full_command="show my medications",
                    category=ShortcutCategory.NAVIGATION,
                    aliases=["pills", "medicines"],
                    description="View medications list",
                ),
                # Quick actions
                VoiceShortcut(
                    phrase="vitals",
                    full_command="record vitals",
                    category=ShortcutCategory.QUICK_ACTION,
                    description="Start vitals recording",
                ),
                VoiceShortcut(
                    phrase="pain",
                    full_command="record pain level",
                    category=ShortcutCategory.QUICK_ACTION,
                    description="Quick pain assessment",
                ),
                VoiceShortcut(
                    phrase="refill",
                    full_command="refill prescriptions",
                    category=ShortcutCategory.QUICK_ACTION,
                    description="Start prescription refill",
                ),
                # Emergency shortcuts
                VoiceShortcut(
                    phrase="help",
                    full_command="emergency help",
                    category=ShortcutCategory.EMERGENCY,
                    priority=CommandPriority.EMERGENCY,
                    scope=ShortcutScope.GLOBAL,
                    description="Get emergency assistance",
                ),
                VoiceShortcut(
                    phrase="911",
                    full_command="call emergency services",
                    category=ShortcutCategory.EMERGENCY,
                    priority=CommandPriority.EMERGENCY,
                    aliases=["emergency"],
                    description="Call emergency services",
                ),
                # Medical record shortcuts
                VoiceShortcut(
                    phrase="records",
                    full_command="show medical records",
                    category=ShortcutCategory.MEDICAL_RECORD,
                    description="View medical records",
                ),
                VoiceShortcut(
                    phrase="allergies",
                    full_command="show my allergies",
                    category=ShortcutCategory.MEDICAL_RECORD,
                    description="View allergy information",
                ),
                # Status check shortcuts
                VoiceShortcut(
                    phrase="status",
                    full_command="health status summary",
                    category=ShortcutCategory.STATUS_CHECK,
                    description="Get health status summary",
                ),
                VoiceShortcut(
                    phrase="appointments",
                    full_command="show upcoming appointments",
                    category=ShortcutCategory.STATUS_CHECK,
                    aliases=["schedule"],
                    description="View appointments",
                ),
            ]
        )


class ShortcutEngine:
    """Engine for managing and processing voice shortcuts."""

    def __init__(self, config: ShortcutConfig):
        """Initialize the shortcut engine.

        Args:
            config: Configuration for voice shortcuts
        """
        self.config = config
        self.shortcuts_by_category: Dict[ShortcutCategory, List[VoiceShortcut]] = {}
        self.custom_shortcuts: List[VoiceShortcut] = []
        self.usage_stats: Dict[str, int] = {}  # Track usage for optimization
        self._organize_shortcuts()

    def _organize_shortcuts(self) -> None:
        """Organize shortcuts by category for efficient lookup."""
        self.shortcuts_by_category.clear()

        for shortcut in self.config.shortcuts:
            category = shortcut.category
            if category not in self.shortcuts_by_category:
                self.shortcuts_by_category[category] = []
            self.shortcuts_by_category[category].append(shortcut)

    def find_shortcut(
        self, phrase: str, scope: ShortcutScope = ShortcutScope.GLOBAL
    ) -> Optional[ShortcutMatch]:
        """Find matching shortcut for given phrase."""
        phrase = phrase.strip()

        # First try exact matching
        for shortcut in self._get_available_shortcuts(scope):
            if shortcut.matches(phrase):
                self._track_usage(shortcut.phrase)
                return ShortcutMatch(
                    shortcut=shortcut, matched_phrase=phrase, confidence=1.0
                )

        # Try fuzzy matching if enabled
        if self.config.fuzzy_matching:
            match = self._fuzzy_match(phrase, scope)
            if match:  # Remove confidence check here, let _fuzzy_match decide
                self._track_usage(match.shortcut.phrase)
                return match

        return None

    def _get_available_shortcuts(self, scope: ShortcutScope) -> List[VoiceShortcut]:
        """Get shortcuts available in current scope."""
        available = []

        for shortcut in self.config.shortcuts + self.custom_shortcuts:
            if shortcut.enabled and shortcut.is_available_in_scope(scope):
                available.append(shortcut)

        return available

    def _fuzzy_match(
        self, phrase: str, scope: ShortcutScope
    ) -> Optional[ShortcutMatch]:
        """Perform fuzzy matching for shortcuts."""
        # Simple implementation - in production, use more sophisticated matching
        phrase_lower = phrase.lower()
        best_match = None
        best_confidence = 0.0

        for shortcut in self._get_available_shortcuts(scope):
            # Check if phrase contains shortcut phrase
            if shortcut.phrase.lower() in phrase_lower:
                # Calculate confidence based on how much of the phrase is the shortcut
                confidence = len(shortcut.phrase) / len(phrase)
                # Boost confidence if shortcut is at word boundary
                words = phrase_lower.split()
                if shortcut.phrase.lower() in words:
                    confidence = min(confidence * 1.5, 0.95)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = shortcut

            # Check aliases
            for alias in shortcut.aliases:
                if alias.lower() in phrase_lower:
                    confidence = (
                        len(alias) / len(phrase) * 0.9
                    )  # Slightly lower for aliases
                    words = phrase_lower.split()
                    if alias.lower() in words:
                        confidence = min(confidence * 1.5, 0.9)
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = shortcut

        if (
            best_match and best_confidence >= self.config.min_confidence * 0.5
        ):  # Lower threshold for fuzzy
            return ShortcutMatch(
                shortcut=best_match, matched_phrase=phrase, confidence=best_confidence
            )

        return None

    def _track_usage(self, phrase: str) -> None:
        """Track shortcut usage for optimization."""
        if phrase not in self.usage_stats:
            self.usage_stats[phrase] = 0
        self.usage_stats[phrase] += 1

    def add_custom_shortcut(self, shortcut: VoiceShortcut) -> bool:
        """Add a custom user-defined shortcut."""
        if not self.config.allow_custom_shortcuts:
            logger.warning("Custom shortcuts are disabled")
            return False

        # Check category limits
        category_count = len(
            [s for s in self.custom_shortcuts if s.category == shortcut.category]
        )
        if category_count >= self.config.max_shortcuts_per_category:
            logger.warning(
                "Category %s has reached shortcut limit", shortcut.category.value
            )
            return False

        # Check for duplicates
        for existing in self.config.shortcuts + self.custom_shortcuts:
            if existing.phrase.lower() == shortcut.phrase.lower():
                logger.warning("Shortcut '%s' already exists", shortcut.phrase)
                return False

        self.custom_shortcuts.append(shortcut)
        logger.info("Added custom shortcut: %s", shortcut.phrase)
        return True

    def remove_custom_shortcut(self, phrase: str) -> bool:
        """Remove a custom shortcut."""
        phrase_lower = phrase.lower()

        for i, shortcut in enumerate(self.custom_shortcuts):
            if shortcut.phrase.lower() == phrase_lower:
                self.custom_shortcuts.pop(i)
                logger.info("Removed custom shortcut: %s", phrase)
                return True

        return False

    def get_shortcuts_by_category(
        self, category: ShortcutCategory
    ) -> List[VoiceShortcut]:
        """Get all shortcuts in a category."""
        category_shortcuts = self.shortcuts_by_category.get(category, [])
        custom_in_category = [
            s for s in self.custom_shortcuts if s.category == category
        ]
        return category_shortcuts + custom_in_category

    def get_most_used_shortcuts(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Get most frequently used shortcuts."""
        sorted_stats = sorted(
            self.usage_stats.items(), key=lambda x: x[1], reverse=True
        )
        return sorted_stats[:limit]

    def enable_shortcut(self, phrase: str) -> bool:
        """Enable a disabled shortcut."""
        for shortcut in self.config.shortcuts + self.custom_shortcuts:
            if shortcut.phrase.lower() == phrase.lower():
                shortcut.enabled = True
                return True
        return False

    def disable_shortcut(self, phrase: str) -> bool:
        """Disable a shortcut."""
        for shortcut in self.config.shortcuts + self.custom_shortcuts:
            if shortcut.phrase.lower() == phrase.lower():
                shortcut.enabled = False
                return True
        return False

    def get_all_shortcuts(
        self, scope: Optional[ShortcutScope] = None
    ) -> List[VoiceShortcut]:
        """Get all shortcuts, optionally filtered by scope."""
        all_shortcuts = self.config.shortcuts + self.custom_shortcuts

        if scope:
            return [s for s in all_shortcuts if s.is_available_in_scope(scope)]
        return all_shortcuts

    def export_shortcuts(self) -> Dict[str, Any]:
        """Export shortcuts configuration."""
        return {
            "default_shortcuts": [
                self._shortcut_to_dict(s) for s in self.config.shortcuts
            ],
            "custom_shortcuts": [
                self._shortcut_to_dict(s) for s in self.custom_shortcuts
            ],
            "usage_stats": self.usage_stats,
        }

    def _shortcut_to_dict(self, shortcut: VoiceShortcut) -> Dict[str, Any]:
        """Convert shortcut to dictionary."""
        return {
            "phrase": shortcut.phrase,
            "full_command": shortcut.full_command,
            "category": shortcut.category.value,
            "scope": shortcut.scope.value,
            "priority": shortcut.priority.value,
            "description": shortcut.description,
            "aliases": shortcut.aliases,
            "enabled": shortcut.enabled,
        }


class PersonalizedShortcutEngine(ShortcutEngine):
    """Shortcut engine with personalization features."""

    def __init__(self, config: ShortcutConfig, user_id: str):
        """Initialize personalized shortcut engine."""
        super().__init__(config)
        self.user_id = user_id
        self.learned_patterns: Dict[str, str] = {}  # Common phrases to shortcuts
        self.context_shortcuts: Dict[str, List[VoiceShortcut]] = {}  # Context-specific

    def learn_pattern(self, user_phrase: str, matched_command: str) -> None:
        """Learn user's speech patterns for better matching."""
        if len(user_phrase) < 20:  # Only learn short phrases
            self.learned_patterns[user_phrase.lower()] = matched_command

    def suggest_shortcut(self, full_command: str) -> Optional[VoiceShortcut]:
        """Suggest creating a shortcut for frequently used commands."""
        # Find if this command is used frequently
        command_count = sum(
            1 for cmd in self.learned_patterns.values() if cmd == full_command
        )

        if command_count >= 3:  # Used 3+ times
            # Generate shortcut suggestion
            words = full_command.split()
            if len(words) > 2:
                suggested_phrase = " ".join(words[:2])  # First two words
                return VoiceShortcut(
                    phrase=suggested_phrase,
                    full_command=full_command,
                    category=ShortcutCategory.QUICK_ACTION,
                    description=f"Suggested shortcut for: {full_command}",
                )
        return None
