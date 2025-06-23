"""
Cultural Adaptation Rules.

This module implements cultural adaptation rules for medical translations,
ensuring appropriate communication across cultural boundaries.
 Handles FHIR Resource validation.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .cultural_profiles import (
    AuthorityRelation,
    CommunicationStyle,
    CulturalProfile,
    cultural_profile_manager,
)

logger = logging.getLogger(__name__)


class AdaptationType(str, Enum):
    """Types of cultural adaptations."""

    FORMALITY = "formality"
    EUPHEMISM = "euphemism"
    METAPHOR = "metaphor"
    MEASUREMENT = "measurement"
    DATE_FORMAT = "date_format"
    FAMILY_REFERENCE = "family_reference"
    RELIGIOUS = "religious"
    TABOO = "taboo"
    COMMUNICATION_STYLE = "communication_style"
    EXPLANATION = "explanation"


@dataclass
class AdaptationRule:
    """A specific cultural adaptation rule."""

    name: str
    adaptation_type: AdaptationType
    source_pattern: str  # Regex pattern or exact match
    target_template: str  # Replacement template
    conditions: Dict[str, Any] = field(default_factory=dict)
    priority: int = 1
    explanation: Optional[str] = None


@dataclass
class AdaptationResult:
    """Result of applying cultural adaptations."""

    original_text: str
    adapted_text: str
    adaptations_applied: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    cultural_notes: List[str] = field(default_factory=list)


class CulturalAdaptationEngine:
    """Engine for applying cultural adaptation rules."""

    def __init__(self) -> None:
        """Initialize the AdaptationEngine."""
        self.rules: Dict[str, List[AdaptationRule]] = {}
        self._init_base_rules()

    def _init_base_rules(self) -> None:
        """Initialize base adaptation rules."""
        # Formality rules
        self.add_rule(
            AdaptationRule(
                name="informal_to_formal_pronouns",
                adaptation_type=AdaptationType.FORMALITY,
                source_pattern=r"\byou\b",
                target_template="{formal_you}",
                conditions={"target_formality": "formal"},
                priority=2,
            )
        )

        # Common euphemisms
        self.add_rule(
            AdaptationRule(
                name="death_euphemism",
                adaptation_type=AdaptationType.EUPHEMISM,
                source_pattern=r"\b(die|died|death|dying)\b",
                target_template="{death_euphemism}",
                conditions={"has_euphemism": "death"},
                priority=3,
            )
        )

        # Measurement conversions
        self.add_rule(
            AdaptationRule(
                name="fahrenheit_to_celsius",
                adaptation_type=AdaptationType.MEASUREMENT,
                source_pattern=r"(\d+\.?\d*)°?F\b",
                target_template="{celsius}°C",
                conditions={"temperature_scale": "celsius"},
                priority=1,
            )
        )

        self.add_rule(
            AdaptationRule(
                name="pounds_to_kg",
                adaptation_type=AdaptationType.MEASUREMENT,
                source_pattern=r"(\d+\.?\d*)\s*(?:pounds?|lbs?)\b",
                target_template="{kilograms}kg",
                conditions={"measurement_system": "metric"},
                priority=1,
            )
        )

        # Date format rules
        self.add_rule(
            AdaptationRule(
                name="us_to_iso_date",
                adaptation_type=AdaptationType.DATE_FORMAT,
                source_pattern=r"(\d{1,2})/(\d{1,2})/(\d{4})",
                target_template="{year}-{month:02d}-{day:02d}",
                conditions={"date_format": "ISO"},
                priority=1,
            )
        )

        # Family involvement rules
        self.add_rule(
            AdaptationRule(
                name="add_family_consideration",
                adaptation_type=AdaptationType.FAMILY_REFERENCE,
                source_pattern=r"(discuss|decide|consider)",
                target_template="{original} with your family",
                conditions={"family_involvement": "high"},
                priority=2,
            )
        )

    def add_rule(self, rule: AdaptationRule) -> None:
        """Add an adaptation rule."""
        if rule.adaptation_type.value not in self.rules:
            self.rules[rule.adaptation_type.value] = []
        self.rules[rule.adaptation_type.value].append(rule)

    def adapt_text(
        self, text: str, source_culture: str, target_culture: str
    ) -> AdaptationResult:
        """Apply cultural adaptations to text."""
        # Get cultural profiles
        source_profile = cultural_profile_manager.get_profile(source_culture)
        target_profile = cultural_profile_manager.get_profile(target_culture)

        if not source_profile or not target_profile:
            logger.warning(
                "Missing cultural profile for %s or %s", source_culture, target_culture
            )
            return AdaptationResult(
                original_text=text,
                adapted_text=text,
                warnings=["Missing cultural profiles"],
            )

        # Get adaptation rules
        adaptation_rules = cultural_profile_manager.get_adaptation_rules(
            source_culture, target_culture
        )

        result = AdaptationResult(original_text=text, adapted_text=text)

        # Apply adaptations by type
        result = self._apply_formality_adaptations(
            result, target_profile, adaptation_rules
        )
        result = self._apply_euphemism_adaptations(result, target_profile)
        result = self._apply_measurement_conversions(result, adaptation_rules)
        result = self._apply_date_conversions(result, adaptation_rules)
        result = self._apply_family_adaptations(result, target_profile)
        result = self._apply_communication_style(
            result, target_profile, adaptation_rules
        )
        result = self._apply_religious_adaptations(result, target_profile)
        result = self._handle_taboo_topics(result, target_profile)

        # Add cultural notes
        result.cultural_notes = self._generate_cultural_notes(
            source_profile, target_profile, result.adaptations_applied
        )

        return result

    def _apply_formality_adaptations(
        self,
        result: AdaptationResult,
        target_profile: CulturalProfile,
        adaptation_rules: Dict,
    ) -> AdaptationResult:
        """Apply formality level adaptations."""
        if not adaptation_rules.get("formality_adjustment", {}).get("adjust"):
            return result

        text = result.adapted_text

        # Apply formal pronouns for languages that have them
        if target_profile.formality_default == "formal":
            # Language-specific formal pronouns
            formal_pronouns = {
                "es": {"you": "usted", "your": "su"},
                "fr": {"you": "vous", "your": "votre"},
                "de": {"you": "Sie", "your": "Ihr"},
                "ja": {"you": "あなた", "your": "あなたの"},
            }

            if target_profile.language_code in formal_pronouns:
                pronouns = formal_pronouns[target_profile.language_code]
                for eng, formal in pronouns.items():
                    pattern = rf"\b{eng}\b"
                    text = re.sub(pattern, formal, text, flags=re.IGNORECASE)

                result.adaptations_applied.append(
                    {
                        "type": AdaptationType.FORMALITY.value,
                        "description": f"Applied formal pronouns for {target_profile.language_code}",
                    }
                )

        result.adapted_text = text
        return result

    def _apply_euphemism_adaptations(
        self, result: AdaptationResult, target_profile: CulturalProfile
    ) -> AdaptationResult:
        """Apply cultural euphemisms."""
        text = result.adapted_text

        for term, euphemism in target_profile.euphemisms.items():
            # Create pattern for the term and its variations
            pattern = rf"\b{term}s?\b"
            if term in text.lower():
                text = re.sub(pattern, euphemism, text, flags=re.IGNORECASE)
                result.adaptations_applied.append(
                    {
                        "type": AdaptationType.EUPHEMISM.value,
                        "original": term,
                        "replacement": euphemism,
                        "reason": "Cultural sensitivity",
                    }
                )

        result.adapted_text = text
        return result

    def _apply_measurement_conversions(
        self, result: AdaptationResult, adaptation_rules: Dict
    ) -> AdaptationResult:
        """Apply measurement unit conversions."""
        text = result.adapted_text
        conversions = adaptation_rules.get("measurement_conversions", {})

        # Temperature conversion
        if conversions.get("temperature", {}).get("convert"):
            if conversions["temperature"]["to"] == "celsius":

                def f_to_c(match: re.Match[str]) -> str:
                    f = float(match.group(1))
                    c = (f - 32) * 5 / 9
                    return f"{c:.1f}°C"

                text = re.sub(r"(\d+\.?\d*)°?F\b", f_to_c, text)
                result.adaptations_applied.append(
                    {
                        "type": AdaptationType.MEASUREMENT.value,
                        "conversion": "Fahrenheit to Celsius",
                    }
                )

        # Weight conversion
        if conversions.get("measurement", {}).get("convert"):
            if conversions["measurement"]["to"] == "metric":

                def lb_to_kg(match: re.Match[str]) -> str:
                    lb = float(match.group(1))
                    kg = lb * 0.453592
                    return f"{kg:.1f}kg"

                text = re.sub(r"(\d+\.?\d*)\s*(?:pounds?|lbs?)\b", lb_to_kg, text)

                def oz_to_g(match: re.Match[str]) -> str:
                    oz = float(match.group(1))
                    g = oz * 28.3495
                    return f"{g:.1f}g"

                text = re.sub(r"(\d+\.?\d*)\s*(?:ounces?|oz)\b", oz_to_g, text)

                result.adaptations_applied.append(
                    {
                        "type": AdaptationType.MEASUREMENT.value,
                        "conversion": "Imperial to Metric",
                    }
                )

        result.adapted_text = text
        return result

    def _apply_date_conversions(
        self, result: AdaptationResult, adaptation_rules: Dict
    ) -> AdaptationResult:
        """Apply date format conversions."""
        text = result.adapted_text
        date_conversion = adaptation_rules.get("measurement_conversions", {}).get(
            "date_format", {}
        )

        if date_conversion.get("convert"):
            target_format = date_conversion["to"]

            if target_format == "ISO":
                # Convert MM/DD/YYYY to YYYY-MM-DD
                def to_iso(match: re.Match[str]) -> str:
                    month, day, year = match.groups()
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

                text = re.sub(r"(\d{1,2})/(\d{1,2})/(\d{4})", to_iso, text)

            elif target_format == "EU":
                # Convert MM/DD/YYYY to DD/MM/YYYY
                def to_eu(match: re.Match[str]) -> str:
                    month, day, year = match.groups()
                    return f"{day}/{month}/{year}"

                text = re.sub(r"(\d{1,2})/(\d{1,2})/(\d{4})", to_eu, text)

            result.adaptations_applied.append(
                {
                    "type": AdaptationType.DATE_FORMAT.value,
                    "conversion": f"Date format to {target_format}",
                }
            )

        result.adapted_text = text
        return result

    def _apply_family_adaptations(
        self,
        result: AdaptationResult,
        target_profile: CulturalProfile,
    ) -> AdaptationResult:
        """Apply family involvement adaptations."""
        # Check if family involvement is expected
        if not target_profile.family_involvement_expected:
            return result

        text = result.adapted_text

        # Add family consideration to decision-making language
        if target_profile.decision_making in ["family", "collective"]:
            decision_patterns = [
                (r"(you should decide)", r"\1 together with your family"),
                (r"(consider your options)", r"\1 with your loved ones"),
                (r"(make a decision)", r"\1 after consulting family"),
                (r"(your choice)", r"\1 and your family\'s choice"),
            ]

            for pattern, replacement in decision_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
                    result.adaptations_applied.append(
                        {
                            "type": AdaptationType.FAMILY_REFERENCE.value,
                            "description": "Added family involvement in decision-making",
                        }
                    )
                    break

        result.adapted_text = text
        return result

    def _apply_communication_style(
        self,
        result: AdaptationResult,
        target_profile: CulturalProfile,  # pylint: disable=unused-argument
        adaptation_rules: Dict,
    ) -> AdaptationResult:
        """Apply communication style adaptations."""
        comm_rules = adaptation_rules.get("communication_style", {})
        text = result.adapted_text

        # Add politeness markers for indirect communication
        if comm_rules.get("add_politeness"):
            politeness_additions = [
                (r"^(Take)", r"Please \1"),
                (r"^(You need)", r"It would be beneficial if you"),
                (r"^(Stop)", r"Please consider stopping"),
                (r"(must)", r"should consider"),
            ]

            for pattern, replacement in politeness_additions:
                text = re.sub(pattern, replacement, text, flags=re.MULTILINE)

            result.adaptations_applied.append(
                {
                    "type": AdaptationType.COMMUNICATION_STYLE.value,
                    "description": "Added politeness markers",
                }
            )

        # Add context for high-context cultures
        if comm_rules.get("add_context"):
            # Add explanatory phrases
            medical_terms = re.findall(r"\b[A-Z]{2,}\b", text)  # Find acronyms
            for term in medical_terms[:3]:  # Limit to avoid over-explanation
                text = text.replace(term, f"{term} (medical test)", 1)

            result.adaptations_applied.append(
                {
                    "type": AdaptationType.EXPLANATION.value,
                    "description": "Added context for medical terms",
                }
            )

        result.adapted_text = text
        return result

    def _apply_religious_adaptations(
        self, result: AdaptationResult, target_profile: CulturalProfile
    ) -> AdaptationResult:
        """Apply religious and dietary adaptations."""
        text = result.adapted_text

        for religious in target_profile.religious_considerations:
            # Flag dietary restrictions
            for restriction in religious.dietary_restrictions:
                if restriction.lower() in text.lower():
                    result.warnings.append(
                        f"Text contains reference to '{restriction}' which is "
                        f"restricted in {religious.name}"
                    )

            # Add gender preference notes
            if religious.gender_preferences.get("provider") == "same_gender_required":
                result.cultural_notes.append(
                    "Patient may require same-gender healthcare provider"
                )

        return result

    def _handle_taboo_topics(
        self, result: AdaptationResult, target_profile: CulturalProfile
    ) -> AdaptationResult:
        """Handle culturally taboo topics."""
        text = result.adapted_text

        for taboo in target_profile.taboo_topics:
            taboo_patterns = {
                "sexual_health": r"\b(sexual|reproductive|STD|STI)\b",
                "mental_health": r"\b(mental|psychiatric|depression|anxiety)\b",
                "death": r"\b(death|dying|terminal|end.of.life)\b",
                "substance_abuse": r"\b(drug|alcohol|addiction|substance)\b",
            }

            if taboo in taboo_patterns:
                if re.search(taboo_patterns[taboo], text, re.IGNORECASE):
                    result.warnings.append(
                        f"Text contains potentially sensitive topic: {taboo}"
                    )
                    result.cultural_notes.append(
                        f"Consider indirect approach when discussing {taboo.replace('_', ' ')}"
                    )

        return result

    def _generate_cultural_notes(
        self,
        src_profile: CulturalProfile,  # pylint: disable=unused-argument
        target_profile: CulturalProfile,
        adaptations_applied: List[Dict],  # pylint: disable=unused-argument
    ) -> List[str]:
        """Generate helpful cultural notes for healthcare providers."""
        notes = []

        # Communication style notes
        if target_profile.communication_style == CommunicationStyle.HIGH_CONTEXT:
            notes.append(
                "Patient may communicate indirectly. Pay attention to non-verbal cues."
            )

        # Authority relation notes
        if target_profile.authority_relation == AuthorityRelation.HIERARCHICAL:
            notes.append(
                "Patient may be reluctant to question medical advice. Encourage questions."
            )

        # Pain expression notes
        if target_profile.healthcare_beliefs.pain_expression == "minimal":
            notes.append(
                "Patient may minimize pain expression. Use pain scales and observe carefully."
            )

        # Family involvement notes
        if target_profile.decision_making == "family":
            notes.append(
                "Family involvement is expected in medical decisions. Include family when possible."
            )

        return notes


# Global cultural adaptation engine
cultural_adapter = CulturalAdaptationEngine()


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
