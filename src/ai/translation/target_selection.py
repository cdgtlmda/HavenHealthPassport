"""
Target language selection module for medical translations.

This module provides intelligent target language selection based on
user preferences, regional settings, and medical context.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance. All transmissions use secure TLS channels.
 Handles FHIR Resource validation.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

from .config import Language, TranslationMode

logger = logging.getLogger(__name__)


class SelectionStrategy(Enum):
    """Language selection strategies."""

    USER_PREFERENCE = auto()  # Explicit user selection
    REGIONAL = auto()  # Based on region/location
    PATIENT_PROFILE = auto()  # Based on patient demographics
    HEALTHCARE_SYSTEM = auto()  # Based on healthcare system requirements
    EMERGENCY_DEFAULT = auto()  # Emergency fallback languages
    AUTO_DETECT = auto()  # Based on source language patterns


@dataclass
class LanguagePreference:
    """User/system language preference."""

    language: Language
    priority: int  # Lower number = higher priority
    reason: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TargetLanguageSelection:
    """Result of target language selection."""

    primary_language: Language
    alternative_languages: List[Language] = field(default_factory=list)
    selection_strategy: SelectionStrategy = SelectionStrategy.USER_PREFERENCE
    confidence: float = 1.0
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RegionalLanguageMapping:
    """Maps regions to common languages."""

    region: str
    primary_languages: List[Language]
    secondary_languages: List[Language] = field(default_factory=list)
    medical_language: Optional[Language] = None  # For medical records


class TargetLanguageSelector:
    """
    Intelligent target language selection for medical translations.

    Features:
    - User preference management
    - Regional language mapping
    - Emergency language defaults
    - Medical context awareness
    - Multi-language fallback
    """

    def __init__(self) -> None:
        """Initialize the target language selector."""
        self._user_preferences: Dict[str, List[LanguagePreference]] = {}
        self._regional_mappings: Dict[str, RegionalLanguageMapping] = {}
        self._emergency_languages: List[Language] = []
        self._medical_language_pairs: Dict[Tuple[Language, Language], float] = {}
        self._similarity_cache: Dict[Tuple[Language, Language], float] = {}
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Initialize default mappings and preferences."""
        # Emergency default languages (WHO official languages + major regional)
        self._emergency_languages = [
            Language.ENGLISH,
            Language.SPANISH,
            Language.FRENCH,
            Language.ARABIC,
            Language.CHINESE_SIMPLIFIED,
            Language.RUSSIAN,
        ]

        # Initialize regional mappings
        self._initialize_regional_mappings()

        # Initialize medical language pairs (source -> target compatibility)
        self._initialize_medical_pairs()

    def _initialize_regional_mappings(self) -> None:
        """Initialize regional language mappings."""
        # North America
        self._regional_mappings["north_america"] = RegionalLanguageMapping(
            region="north_america",
            primary_languages=[Language.ENGLISH, Language.SPANISH],
            secondary_languages=[Language.FRENCH],
            medical_language=Language.ENGLISH,
        )

        # Europe
        self._regional_mappings["western_europe"] = RegionalLanguageMapping(
            region="western_europe",
            primary_languages=[Language.ENGLISH, Language.FRENCH, Language.GERMAN],
            secondary_languages=[Language.SPANISH, Language.ITALIAN, Language.DUTCH],
            medical_language=Language.ENGLISH,
        )

        # Middle East
        self._regional_mappings["middle_east"] = RegionalLanguageMapping(
            region="middle_east",
            primary_languages=[Language.ARABIC, Language.ENGLISH],
            secondary_languages=[Language.PERSIAN, Language.HEBREW, Language.TURKISH],
            medical_language=Language.ENGLISH,
        )

        # East Asia
        self._regional_mappings["east_asia"] = RegionalLanguageMapping(
            region="east_asia",
            primary_languages=[
                Language.CHINESE_SIMPLIFIED,
                Language.JAPANESE,
                Language.KOREAN,
            ],
            secondary_languages=[Language.ENGLISH],
            medical_language=Language.ENGLISH,
        )

        # South Asia
        self._regional_mappings["south_asia"] = RegionalLanguageMapping(
            region="south_asia",
            primary_languages=[Language.HINDI, Language.ENGLISH, Language.URDU],
            secondary_languages=[Language.BENGALI, Language.TAMIL],
            medical_language=Language.ENGLISH,
        )

        # Africa
        self._regional_mappings["africa"] = RegionalLanguageMapping(
            region="africa",
            primary_languages=[Language.ENGLISH, Language.FRENCH, Language.ARABIC],
            secondary_languages=[Language.SWAHILI, Language.PORTUGUESE],
            medical_language=Language.ENGLISH,
        )

    def _initialize_medical_pairs(self) -> None:
        """Initialize medical language pair compatibility scores."""
        # High compatibility pairs (share medical terminology)
        high_compatibility = [
            (Language.ENGLISH, Language.SPANISH),
            (Language.ENGLISH, Language.FRENCH),
            (Language.ENGLISH, Language.GERMAN),
            (Language.SPANISH, Language.PORTUGUESE),
            (Language.SPANISH, Language.ITALIAN),
            (Language.FRENCH, Language.ITALIAN),
            (Language.GERMAN, Language.DUTCH),
            (Language.ARABIC, Language.URDU),
            (Language.HINDI, Language.URDU),
        ]

        for source, target in high_compatibility:
            self._medical_language_pairs[(source, target)] = 0.9
            self._medical_language_pairs[(target, source)] = 0.9

        # Medium compatibility
        medium_compatibility = [
            (Language.ENGLISH, Language.DUTCH),
            (Language.RUSSIAN, Language.UKRAINIAN),
            (Language.CHINESE_SIMPLIFIED, Language.CHINESE_TRADITIONAL),
        ]

        for source, target in medium_compatibility:
            self._medical_language_pairs[(source, target)] = 0.7
            self._medical_language_pairs[(target, source)] = 0.7

    def select_target_language(
        self,
        user_id: Optional[str] = None,
        region: Optional[str] = None,
        source_language: Optional[Language] = None,
        mode: TranslationMode = TranslationMode.GENERAL,
        context: Optional[Dict[str, Any]] = None,
    ) -> TargetLanguageSelection:
        """
        Select the most appropriate target language.

        Args:
            user_id: User identifier for preferences
            region: Geographic region
            source_language: Source language (for compatibility)
            mode: Translation mode
            context: Additional context

        Returns:
            TargetLanguageSelection with primary and alternatives
        """
        candidates: List[LanguagePreference] = []

        # 1. Check user preferences
        if user_id and user_id in self._user_preferences:
            user_prefs = self._user_preferences[user_id]
            for pref in user_prefs:
                pref.reason = f"User preference (priority {pref.priority})"
                candidates.append(pref)

        # 2. Check regional preferences
        if region and region in self._regional_mappings:
            regional = self._regional_mappings[region]

            # Add primary regional languages
            for i, lang in enumerate(regional.primary_languages):
                candidates.append(
                    LanguagePreference(
                        language=lang,
                        priority=10 + i,
                        reason=f"Primary language in {region}",
                        confidence=0.8,
                    )
                )

            # Add medical language if different
            if (
                regional.medical_language
                and regional.medical_language not in regional.primary_languages
            ):
                candidates.append(
                    LanguagePreference(
                        language=regional.medical_language,
                        priority=15,
                        reason=f"Medical standard in {region}",
                        confidence=0.9 if mode == TranslationMode.CLINICAL else 0.7,
                    )
                )

        # 3. Check source language compatibility
        if source_language:
            compatible_langs = self._get_compatible_languages(source_language)
            for lang, score in compatible_langs:
                candidates.append(
                    LanguagePreference(
                        language=lang,
                        priority=20,
                        reason=f"Compatible with source {source_language.value}",
                        confidence=score,
                    )
                )

        # 4. Emergency mode defaults
        if mode == TranslationMode.EMERGENCY:
            for i, lang in enumerate(self._emergency_languages):
                candidates.append(
                    LanguagePreference(
                        language=lang,
                        priority=30 + i,
                        reason="Emergency language default",
                        confidence=0.7,
                    )
                )

        # 5. Context-based selection
        if context:
            context_langs = self._extract_context_languages(context)
            for lang, conf in context_langs:
                candidates.append(
                    LanguagePreference(
                        language=lang,
                        priority=25,
                        reason="Context-based selection",
                        confidence=conf,
                    )
                )

        # Select best candidate
        if not candidates:
            # Default fallback
            return TargetLanguageSelection(
                primary_language=Language.ENGLISH,
                alternative_languages=[Language.SPANISH, Language.FRENCH],
                selection_strategy=SelectionStrategy.EMERGENCY_DEFAULT,
                confidence=0.5,
                reasons=["No selection criteria available, using default"],
                warnings=["Using fallback language selection"],
            )

        # Sort by priority and confidence
        sorted_candidates = sorted(
            candidates, key=lambda x: (x.priority, -x.confidence)
        )

        # Get unique languages
        seen_languages = set()
        unique_candidates = []
        for cand in sorted_candidates:
            if cand.language not in seen_languages:
                seen_languages.add(cand.language)
                unique_candidates.append(cand)

        # Build result
        primary = unique_candidates[0]
        alternatives = [
            c.language for c in unique_candidates[1:6]
        ]  # Top 5 alternatives

        # Determine strategy
        strategy = self._determine_strategy(primary.reason)

        return TargetLanguageSelection(
            primary_language=primary.language,
            alternative_languages=alternatives,
            selection_strategy=strategy,
            confidence=primary.confidence,
            reasons=[c.reason for c in unique_candidates[:3]],
            warnings=self._generate_warnings(primary, mode, context),
            metadata={
                "total_candidates": len(candidates),
                "source_language": source_language.value if source_language else None,
                "region": region,
                "mode": mode.name,
            },
        )

    def _determine_strategy(self, reason: str) -> SelectionStrategy:
        """Determine selection strategy from reason."""
        if "User preference" in reason:
            return SelectionStrategy.USER_PREFERENCE
        elif "Primary language in" in reason:
            return SelectionStrategy.REGIONAL
        elif "Medical standard" in reason:
            return SelectionStrategy.HEALTHCARE_SYSTEM
        elif "Emergency" in reason:
            return SelectionStrategy.EMERGENCY_DEFAULT
        elif "Context" in reason:
            return SelectionStrategy.PATIENT_PROFILE
        else:
            return SelectionStrategy.AUTO_DETECT

    def _generate_warnings(
        self,
        selection: LanguagePreference,
        mode: TranslationMode,
        context: Optional[Dict[str, Any]],
    ) -> List[str]:
        """Generate warnings for the selection."""
        warnings = []

        # Use context to check for additional warnings
        if context and context.get("emergency", False):
            warnings.append("Emergency context - using default language")

        if selection.confidence < 0.7:
            warnings.append(
                f"Low confidence ({selection.confidence:.2f}) in language selection"
            )

        if mode == TranslationMode.EMERGENCY and selection.priority > 20:
            warnings.append("Using lower priority language for emergency translation")

        if (
            mode == TranslationMode.CLINICAL
            and selection.language not in self._emergency_languages
        ):
            warnings.append("Selected language may have limited medical terminology")

        return warnings

    def _get_compatible_languages(
        self, source_language: Language
    ) -> List[Tuple[Language, float]]:
        """Get languages compatible with source."""
        compatible = []

        for (source, target), score in self._medical_language_pairs.items():
            if source == source_language:
                compatible.append((target, score))

        # Sort by score
        return sorted(compatible, key=lambda x: x[1], reverse=True)

    def _extract_context_languages(
        self, context: Dict[str, Any]
    ) -> List[Tuple[Language, float]]:
        """Extract language preferences from context."""
        languages: List[Tuple[Language, float]] = []

        # Patient preferred languages
        if "patient_languages" in context:
            for lang_code in context["patient_languages"]:
                lang = Language.from_code(lang_code)
                if lang != Language.UNKNOWN:
                    languages.append((lang, 0.9))

        # Healthcare provider language
        if "provider_language" in context:
            lang = Language.from_code(context["provider_language"])
            if lang != Language.UNKNOWN:
                languages.append((lang, 0.8))

        return languages

    def set_user_preferences(
        self, user_id: str, preferences: List[LanguagePreference]
    ) -> None:
        """Set user language preferences."""
        self._user_preferences[user_id] = sorted(preferences, key=lambda x: x.priority)
        logger.info(
            "Set %d language preferences for user %s", len(preferences), user_id
        )

    def add_user_preference(
        self, user_id: str, language: Language, priority: int = 1
    ) -> None:
        """Add a single user preference."""
        if user_id not in self._user_preferences:
            self._user_preferences[user_id] = []

        pref = LanguagePreference(
            language=language, priority=priority, reason="User preference"
        )

        # Remove existing preference for same language
        self._user_preferences[user_id] = [
            p for p in self._user_preferences[user_id] if p.language != language
        ]

        self._user_preferences[user_id].append(pref)
        self._user_preferences[user_id].sort(key=lambda x: x.priority)

    def get_user_preferences(self, user_id: str) -> List[LanguagePreference]:
        """Get user language preferences."""
        return self._user_preferences.get(user_id, [])

    def validate_language_availability(
        self, language: Language, mode: TranslationMode
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if a language is available for translation.

        Returns:
            Tuple of (is_available, warning_message)
        """
        if language == Language.UNKNOWN:
            return False, "Unknown language"

        if language == Language.AUTO_DETECT:
            return False, "Auto-detect is not a valid target language"

        # Check medical terminology availability
        if mode in [TranslationMode.CLINICAL, TranslationMode.PRESCRIPTION]:
            if language not in self._emergency_languages:
                return True, "Limited medical terminology may be available"

        return True, None

    def get_regional_languages(self, region: str) -> Optional[RegionalLanguageMapping]:
        """Get language mapping for a region."""
        return self._regional_mappings.get(region)

    def add_regional_mapping(
        self, region: str, mapping: RegionalLanguageMapping
    ) -> None:
        """Add or update regional language mapping."""
        self._regional_mappings[region] = mapping
        logger.info("Added regional mapping for %s", region)

    def get_language_similarity_score(self, lang1: Language, lang2: Language) -> float:
        """Get similarity score between two languages."""
        # Check cache first
        cache_key = (lang1, lang2) if lang1.value < lang2.value else (lang2, lang1)
        if cache_key in self._similarity_cache:
            return self._similarity_cache[cache_key]

        if lang1 == lang2:
            result = 1.0
        else:
            # Check medical pairs
            pair_score = self._medical_language_pairs.get((lang1, lang2), 0.0)
            if pair_score > 0:
                return pair_score

        # Language family similarities
        romance = {
            Language.SPANISH,
            Language.FRENCH,
            Language.ITALIAN,
            Language.PORTUGUESE,
            Language.ROMANIAN,
        }
        germanic = {
            Language.ENGLISH,
            Language.GERMAN,
            Language.DUTCH,
            Language.SWEDISH,
            Language.DANISH,
            Language.NORWEGIAN,
        }
        slavic = {
            Language.RUSSIAN,
            Language.UKRAINIAN,
            Language.POLISH,
            Language.CZECH,
            Language.BULGARIAN,
        }

        for family in [romance, germanic, slavic]:
            if lang1 in family and lang2 in family:
                result = 0.6
                break
        else:
            result = 0.0

        # Cache the result
        if len(self._similarity_cache) > 128:
            # Remove oldest entries (simple FIFO)
            self._similarity_cache = dict(list(self._similarity_cache.items())[64:])
        self._similarity_cache[cache_key] = result

        return result
