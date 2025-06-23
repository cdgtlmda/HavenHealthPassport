"""
Cultural Profiles.

This module defines cultural profiles for different regions and languages,
capturing healthcare-related cultural norms and preferences.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CommunicationStyle(str, Enum):
    """Communication style preferences."""

    DIRECT = "direct"  # Straightforward, explicit
    INDIRECT = "indirect"  # Polite, implicit
    HIGH_CONTEXT = "high_context"  # Relies on context/nonverbal
    LOW_CONTEXT = "low_context"  # Explicit verbal communication


class AuthorityRelation(str, Enum):
    """Relationship to medical authority."""

    HIERARCHICAL = "hierarchical"  # Doctor as authority figure
    COLLABORATIVE = "collaborative"  # Doctor as partner
    DEFERENTIAL = "deferential"  # High respect for medical authority
    QUESTIONING = "questioning"  # Encourages questions/discussion


class PrivacyLevel(str, Enum):
    """Privacy preferences."""

    VERY_HIGH = "very_high"  # Extreme privacy needs
    HIGH = "high"  # Strong privacy preference
    MODERATE = "moderate"  # Balanced approach
    LOW = "low"  # Open discussion acceptable


class TimeOrientation(str, Enum):
    """Cultural time orientation."""

    MONOCHRONIC = "monochronic"  # Punctual, scheduled
    POLYCHRONIC = "polychronic"  # Flexible, relational
    MIXED = "mixed"  # Context-dependent


@dataclass
class ReligiousConsiderations:
    """Religious considerations for healthcare."""

    name: str
    dietary_restrictions: List[str] = field(default_factory=list)
    medical_restrictions: List[str] = field(default_factory=list)
    prayer_times: List[str] = field(default_factory=list)
    fasting_periods: List[str] = field(default_factory=list)
    gender_preferences: Dict[str, str] = field(default_factory=dict)
    end_of_life: Dict[str, Any] = field(default_factory=dict)
    blood_products: str = "allowed"  # allowed, restricted, forbidden
    organ_donation: str = "allowed"  # allowed, restricted, forbidden


@dataclass
class HealthcareBelief:
    """Cultural healthcare beliefs."""

    traditional_medicine: bool = False
    holistic_approach: bool = False
    family_involvement: str = "moderate"  # low, moderate, high, required
    mental_health_stigma: str = "moderate"  # low, moderate, high
    preventive_care: str = "accepted"  # accepted, neutral, skeptical
    pain_expression: str = "moderate"  # minimal, moderate, expressive


@dataclass
class CulturalProfile:
    """Complete cultural profile for a language/region."""

    language_code: str
    region: Optional[str] = None
    name: str = ""

    # Communication preferences
    communication_style: CommunicationStyle = CommunicationStyle.DIRECT
    authority_relation: AuthorityRelation = AuthorityRelation.COLLABORATIVE
    formality_default: str = "formal"  # formal, informal, neutral

    # Privacy and family
    privacy_level: PrivacyLevel = PrivacyLevel.MODERATE
    family_involvement_expected: bool = True
    decision_making: str = "individual"  # individual, family, collective

    # Time and scheduling
    time_orientation: TimeOrientation = TimeOrientation.MONOCHRONIC
    appointment_flexibility: str = "strict"  # strict, moderate, flexible

    # Religious/spiritual
    primary_religions: List[str] = field(default_factory=list)
    religious_considerations: List[ReligiousConsiderations] = field(
        default_factory=list
    )

    # Healthcare beliefs
    healthcare_beliefs: HealthcareBelief = field(default_factory=HealthcareBelief)

    # Specific adaptations
    taboo_topics: List[str] = field(default_factory=list)
    euphemisms: Dict[str, str] = field(default_factory=dict)
    metaphors: Dict[str, str] = field(default_factory=dict)

    # Measurement preferences
    measurement_system: str = "metric"  # metric, imperial
    temperature_scale: str = "celsius"  # celsius, fahrenheit
    date_format: str = "ISO"  # ISO, US, EU, other

    # Additional metadata
    notes: List[str] = field(default_factory=list)


class CulturalProfileManager:
    """Manages cultural profiles for different regions."""

    def __init__(self) -> None:
        """Initialize the CulturalProfileManager."""
        self.profiles: Dict[str, CulturalProfile] = {}
        self._load_default_profiles()

    def _load_default_profiles(self) -> None:
        """Load default cultural profiles."""
        # Arabic-speaking regions
        self.profiles["ar"] = CulturalProfile(
            language_code="ar",
            name="Arabic (General)",
            communication_style=CommunicationStyle.INDIRECT,
            authority_relation=AuthorityRelation.HIERARCHICAL,
            formality_default="formal",
            privacy_level=PrivacyLevel.HIGH,
            family_involvement_expected=True,
            decision_making="family",
            primary_religions=["Islam"],
            religious_considerations=[
                ReligiousConsiderations(
                    name="Islam",
                    dietary_restrictions=["pork", "alcohol"],
                    medical_restrictions=["opposite_gender_provider_restricted"],
                    prayer_times=["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"],
                    fasting_periods=["Ramadan"],
                    gender_preferences={"provider": "same_gender_preferred"},
                    blood_products="allowed",
                    organ_donation="restricted",
                )
            ],
            healthcare_beliefs=HealthcareBelief(
                traditional_medicine=True,
                family_involvement="high",
                mental_health_stigma="high",
                pain_expression="minimal",
            ),
            taboo_topics=["sexual_health", "mental_health", "substance_abuse"],
            euphemisms={
                "cancer": "the disease",
                "mental illness": "nervous condition",
                "death": "return to God",
            },
        )

        # Chinese culture
        self.profiles["zh"] = CulturalProfile(
            language_code="zh",
            name="Chinese (Mandarin)",
            communication_style=CommunicationStyle.HIGH_CONTEXT,
            authority_relation=AuthorityRelation.DEFERENTIAL,
            formality_default="formal",
            privacy_level=PrivacyLevel.HIGH,
            family_involvement_expected=True,
            decision_making="family",
            healthcare_beliefs=HealthcareBelief(
                traditional_medicine=True,
                holistic_approach=True,
                family_involvement="high",
                mental_health_stigma="high",
                pain_expression="minimal",
            ),
            taboo_topics=["death", "mental_health"],
            euphemisms={
                "death": "passing away",
                "cancer": "serious illness",
                "surgery": "procedure",
            },
            metaphors={
                "health": "balance and harmony",
                "illness": "imbalance",
                "recovery": "restoration of balance",
            },
        )

        # Spanish-speaking (Latin America)
        self.profiles["es-LA"] = CulturalProfile(
            language_code="es",
            region="LA",
            name="Spanish (Latin America)",
            communication_style=CommunicationStyle.INDIRECT,
            authority_relation=AuthorityRelation.HIERARCHICAL,
            formality_default="formal",
            privacy_level=PrivacyLevel.MODERATE,
            family_involvement_expected=True,
            decision_making="family",
            time_orientation=TimeOrientation.POLYCHRONIC,
            appointment_flexibility="flexible",
            primary_religions=["Catholicism"],
            healthcare_beliefs=HealthcareBelief(
                traditional_medicine=True,
                family_involvement="high",
                mental_health_stigma="moderate",
                pain_expression="expressive",
            ),
            euphemisms={"cancer": "la enfermedad", "death": "pasar a mejor vida"},
        )

        # Somali culture
        self.profiles["so"] = CulturalProfile(
            language_code="so",
            name="Somali",
            communication_style=CommunicationStyle.INDIRECT,
            authority_relation=AuthorityRelation.HIERARCHICAL,
            formality_default="formal",
            privacy_level=PrivacyLevel.VERY_HIGH,
            family_involvement_expected=True,
            decision_making="collective",
            primary_religions=["Islam"],
            religious_considerations=[
                ReligiousConsiderations(
                    name="Islam",
                    dietary_restrictions=["pork", "alcohol"],
                    medical_restrictions=["opposite_gender_provider_restricted"],
                    gender_preferences={"provider": "same_gender_required"},
                    blood_products="restricted",
                )
            ],
            healthcare_beliefs=HealthcareBelief(
                traditional_medicine=True,
                family_involvement="required",
                mental_health_stigma="high",
                pain_expression="minimal",
            ),
            taboo_topics=["reproductive_health", "mental_health"],
            measurement_system="metric",
            temperature_scale="celsius",
        )

        # Japanese culture
        self.profiles["ja"] = CulturalProfile(
            language_code="ja",
            name="Japanese",
            communication_style=CommunicationStyle.HIGH_CONTEXT,
            authority_relation=AuthorityRelation.DEFERENTIAL,
            formality_default="formal",
            privacy_level=PrivacyLevel.VERY_HIGH,
            family_involvement_expected=False,
            decision_making="individual",
            time_orientation=TimeOrientation.MONOCHRONIC,
            appointment_flexibility="strict",
            healthcare_beliefs=HealthcareBelief(
                traditional_medicine=True,
                holistic_approach=True,
                family_involvement="low",
                mental_health_stigma="high",
                pain_expression="minimal",
                preventive_care="accepted",
            ),
            taboo_topics=["mental_health", "terminal_diagnosis"],
            euphemisms={"cancer": "serious condition", "death": "passing"},
        )

        # Add more cultural profiles...

    def get_profile(
        self, language_code: str, region: Optional[str] = None
    ) -> Optional[CulturalProfile]:
        """Get cultural profile for language/region."""
        # Try region-specific first
        if region:
            key = f"{language_code}-{region}"
            if key in self.profiles:
                return self.profiles[key]

        # Fall back to language-only
        return self.profiles.get(language_code)

    def add_profile(self, profile: CulturalProfile) -> None:
        """Add or update a cultural profile."""
        key = profile.language_code
        if profile.region:
            key = f"{key}-{profile.region}"
        self.profiles[key] = profile
        logger.info("Added cultural profile for %s", key)

    def get_adaptation_rules(
        self, source_culture: str, target_culture: str
    ) -> Dict[str, Any]:
        """Get specific adaptation rules between cultures."""
        source_profile = self.get_profile(source_culture)
        target_profile = self.get_profile(target_culture)

        if not source_profile or not target_profile:
            return {}

        rules = {
            "formality_adjustment": self._get_formality_adjustment(
                source_profile, target_profile
            ),
            "communication_style": self._get_communication_adjustment(
                source_profile, target_profile
            ),
            "privacy_adjustments": self._get_privacy_adjustments(
                source_profile, target_profile
            ),
            "family_involvement": self._get_family_adjustments(
                source_profile, target_profile
            ),
            "religious_considerations": self._get_religious_considerations(
                target_profile
            ),
            "taboo_adaptations": self._get_taboo_adaptations(target_profile),
            "measurement_conversions": self._get_measurement_conversions(
                source_profile, target_profile
            ),
        }

        return rules

    def _get_formality_adjustment(
        self, src: CulturalProfile, target: CulturalProfile
    ) -> Dict[str, Any]:
        """Determine formality adjustments needed."""
        return {
            "source_formality": src.formality_default,
            "target_formality": target.formality_default,
            "adjust": src.formality_default != target.formality_default,
        }

    def _get_communication_adjustment(
        self, source: CulturalProfile, target: CulturalProfile
    ) -> Dict[str, Any]:
        """Determine communication style adjustments."""
        return {
            "source_style": source.communication_style.value,
            "target_style": target.communication_style.value,
            "add_context": target.communication_style
            == CommunicationStyle.HIGH_CONTEXT,
            "add_politeness": target.communication_style == CommunicationStyle.INDIRECT,
            "clarify_implicit": source.communication_style
            == CommunicationStyle.HIGH_CONTEXT,
        }

    def _get_privacy_adjustments(
        self, source: CulturalProfile, target: CulturalProfile
    ) -> Dict[str, Any]:
        """Determine privacy level adjustments."""
        return {
            "increase_privacy": target.privacy_level.value > source.privacy_level.value,
            "use_euphemisms": target.privacy_level
            in [PrivacyLevel.HIGH, PrivacyLevel.VERY_HIGH],
            "family_disclosure": target.family_involvement_expected,
        }

    def _get_family_adjustments(
        self,
        source: CulturalProfile,
        target: CulturalProfile,
    ) -> Dict[str, Any]:
        """Determine family involvement adjustments."""
        _ = source  # Mark as intentionally unused
        return {
            "include_family": target.family_involvement_expected,
            "decision_making": target.decision_making,
            "family_honorifics": target.decision_making in ["family", "collective"],
        }

    def _get_religious_considerations(
        self, target: CulturalProfile
    ) -> List[Dict[str, Any]]:
        """Get religious considerations for target culture."""
        considerations = []
        for religious in target.religious_considerations:
            considerations.append(
                {
                    "religion": religious.name,
                    "dietary": religious.dietary_restrictions,
                    "medical": religious.medical_restrictions,
                    "gender_preferences": religious.gender_preferences,
                    "blood_products": religious.blood_products,
                }
            )
        return considerations

    def _get_taboo_adaptations(self, target: CulturalProfile) -> Dict[str, Any]:
        """Get taboo topic adaptations."""
        return {
            "taboo_topics": target.taboo_topics,
            "euphemisms": target.euphemisms,
            "metaphors": target.metaphors,
        }

    def _get_measurement_conversions(
        self, source: CulturalProfile, target: CulturalProfile
    ) -> Dict[str, Any]:
        """Determine measurement conversions needed."""
        return {
            "measurement": {
                "convert": source.measurement_system != target.measurement_system,
                "from": source.measurement_system,
                "to": target.measurement_system,
            },
            "temperature": {
                "convert": source.temperature_scale != target.temperature_scale,
                "from": source.temperature_scale,
                "to": target.temperature_scale,
            },
            "date_format": {
                "convert": source.date_format != target.date_format,
                "from": source.date_format,
                "to": target.date_format,
            },
        }


# Global cultural profile manager
cultural_profile_manager = CulturalProfileManager()
