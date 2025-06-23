"""
Cultural formality adaptation module.

This module handles cultural variations in formality expectations,
ensuring appropriate tone for different cultural contexts.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

from .core import FormalityContext, FormalityLevel

logger = logging.getLogger(__name__)


@dataclass
class CulturalContext:
    """Cultural context information."""

    culture_code: str  # e.g., "ja-JP", "de-DE", "ar-SA"
    hierarchy_importance: float  # 0-1, how important hierarchy is
    directness_preference: float  # 0-1, 0=indirect, 1=very direct
    relationship_based: bool  # Whether formality depends on relationship
    age_sensitivity: float  # 0-1, how much age affects formality
    gender_considerations: bool  # Whether gender affects formality
    professional_distance: float  # 0-1, expected professional distance

    # Specific rules
    title_usage: Dict[str, str] = field(default_factory=dict)
    honorifics: List[str] = field(default_factory=list)
    taboo_topics: Set[str] = field(default_factory=set)


class CulturalFormalityAdapter:
    """Adapts formality based on cultural expectations."""

    def __init__(self) -> None:
        """Initialize cultural adapter."""
        self.cultural_profiles = self._load_cultural_profiles()

    def adapt_formality(
        self,
        base_level: FormalityLevel,
        source_culture: str,
        target_culture: str,
        context: FormalityContext,
    ) -> FormalityLevel:
        """
        Adapt formality level based on cultural expectations.

        Args:
            base_level: Base formality level
            source_culture: Source culture code
            target_culture: Target culture code
            context: Formality context

        Returns:
            Culturally adapted formality level
        """
        source_profile = self.cultural_profiles.get(source_culture)
        target_profile = self.cultural_profiles.get(target_culture)

        if not source_profile or not target_profile:
            return base_level

        # Calculate cultural adjustment
        adjustment = 0

        # Hierarchy differences
        hierarchy_diff = (
            target_profile.hierarchy_importance - source_profile.hierarchy_importance
        )
        if hierarchy_diff > 0.3:
            adjustment += 1  # More formal
        elif hierarchy_diff < -0.3:
            adjustment -= 1  # Less formal

        # Professional distance
        if context.audience in ["healthcare_provider", "government", "insurance"]:
            distance_diff = (
                target_profile.professional_distance
                - source_profile.professional_distance
            )
            if distance_diff > 0.3:
                adjustment += 1

        # Age considerations
        if (
            context.age_group in ["elderly", "child"]
            and target_profile.age_sensitivity > 0.7
        ):
            adjustment += 1  # More respectful with elderly, clearer with children

        # Relationship-based adjustments
        if (
            target_profile.relationship_based
            and context.relationship == "doctor_patient"
        ):
            # Some cultures expect more formal doctor-patient relationships
            if target_profile.hierarchy_importance > 0.7:
                adjustment += 1

        # Apply adjustment
        new_level = base_level + adjustment

        # Ensure within bounds
        return FormalityLevel(max(1, min(5, new_level)))

    def get_cultural_guidelines(self, culture_code: str) -> Dict[str, Any]:
        """Get formality guidelines for a specific culture."""
        profile = self.cultural_profiles.get(culture_code)
        if not profile:
            return {}

        return {
            "use_titles": profile.hierarchy_importance > 0.6,
            "use_honorifics": len(profile.honorifics) > 0,
            "maintain_distance": profile.professional_distance > 0.6,
            "consider_age": profile.age_sensitivity > 0.5,
            "consider_gender": profile.gender_considerations,
            "avoid_directness": profile.directness_preference < 0.4,
            "taboo_topics": list(profile.taboo_topics),
        }

    def _load_cultural_profiles(self) -> Dict[str, CulturalContext]:
        """Load cultural profiles."""
        profiles = {}

        # American English
        profiles["en-US"] = CulturalContext(
            culture_code="en-US",
            hierarchy_importance=0.4,
            directness_preference=0.7,
            relationship_based=False,
            age_sensitivity=0.3,
            gender_considerations=False,
            professional_distance=0.5,
            title_usage={"doctor": "Dr.", "professor": "Prof."},
            honorifics=["Mr.", "Ms.", "Dr."],
        )

        # British English
        profiles["en-GB"] = CulturalContext(
            culture_code="en-GB",
            hierarchy_importance=0.6,
            directness_preference=0.5,
            relationship_based=True,
            age_sensitivity=0.5,
            gender_considerations=False,
            professional_distance=0.7,
            title_usage={"doctor": "Dr", "professor": "Professor"},
            honorifics=["Mr", "Mrs", "Ms", "Dr", "Sir", "Madam"],
        )

        # Japanese
        profiles["ja-JP"] = CulturalContext(
            culture_code="ja-JP",
            hierarchy_importance=0.9,
            directness_preference=0.2,
            relationship_based=True,
            age_sensitivity=0.9,
            gender_considerations=True,
            professional_distance=0.9,
            title_usage={"doctor": "先生", "professor": "教授"},
            honorifics=["さん", "様", "先生", "殿"],
            taboo_topics={"death", "failure", "direct_criticism"},
        )

        # German
        profiles["de-DE"] = CulturalContext(
            culture_code="de-DE",
            hierarchy_importance=0.7,
            directness_preference=0.8,
            relationship_based=True,
            age_sensitivity=0.6,
            gender_considerations=False,
            professional_distance=0.8,
            title_usage={"doctor": "Dr.", "professor": "Prof. Dr."},
            honorifics=["Herr", "Frau", "Dr.", "Prof."],
        )

        # Arabic (Saudi)
        profiles["ar-SA"] = CulturalContext(
            culture_code="ar-SA",
            hierarchy_importance=0.8,
            directness_preference=0.3,
            relationship_based=True,
            age_sensitivity=0.8,
            gender_considerations=True,
            professional_distance=0.7,
            title_usage={"doctor": "د.", "professor": "أ.د."},
            honorifics=["السيد", "السيدة", "الدكتور", "الأستاذ"],
            taboo_topics={"personal_medical_history", "reproductive_health"},
        )

        return profiles


def get_cultural_formality_norms(culture_code: str) -> Dict[str, Any]:
    """
    Get cultural formality norms for a specific culture.

    Args:
        culture_code: Culture identifier (e.g., "en-US", "ja-JP")

    Returns:
        Dictionary of cultural formality norms
    """
    adapter = CulturalFormalityAdapter()
    profile = adapter.cultural_profiles.get(culture_code)

    if not profile:
        # Return default norms
        return {
            "default_formality": FormalityLevel.NEUTRAL,
            "medical_formality": FormalityLevel.FORMAL,
            "patient_communication": FormalityLevel.NEUTRAL,
            "professional_communication": FormalityLevel.FORMAL,
        }

    # Calculate recommended levels based on cultural profile
    norms = {
        "default_formality": (
            FormalityLevel.FORMAL
            if profile.hierarchy_importance > 0.6
            else FormalityLevel.NEUTRAL
        ),
        "medical_formality": (
            FormalityLevel.VERY_FORMAL
            if profile.professional_distance > 0.7
            else FormalityLevel.FORMAL
        ),
        "patient_communication": (
            FormalityLevel.NEUTRAL
            if profile.directness_preference > 0.5
            else FormalityLevel.FORMAL
        ),
        "professional_communication": (
            FormalityLevel.VERY_FORMAL
            if profile.hierarchy_importance > 0.7
            else FormalityLevel.FORMAL
        ),
        "emergency_communication": (
            FormalityLevel.INFORMAL
            if profile.directness_preference > 0.6
            else FormalityLevel.NEUTRAL
        ),
        "use_honorifics": len(profile.honorifics) > 0,
        "maintain_hierarchy": profile.hierarchy_importance > 0.5,
        "age_respectful": profile.age_sensitivity > 0.5,
        "gender_aware": profile.gender_considerations,
        "avoid_direct_commands": profile.directness_preference < 0.4,
    }

    return norms
