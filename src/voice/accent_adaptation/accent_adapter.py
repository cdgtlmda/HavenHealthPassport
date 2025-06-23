"""
Accent Adaptation Module.

This module provides functionality for adapting transcription models
and processes based on detected accents.

Note: Voice data analyzed for accent detection may contain PHI. Ensure all
audio data is encrypted both in transit and at rest. Implement proper access
control to restrict accent adaptation operations to authorized personnel.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from src.security import requires_phi_access

from .accent_detector import AccentDetectionResult
from .accent_profile import (
    AccentDatabase,
    AccentProfile,
    AccentStrength,
    PronunciationVariant,
)

logger = logging.getLogger(__name__)


class AdaptationStrategy(Enum):
    """Strategies for accent adaptation."""

    ACOUSTIC_MODEL = "acoustic_model"  # Adapt acoustic model parameters
    PRONUNCIATION = "pronunciation"  # Add pronunciation variants
    CONFIDENCE = "confidence"  # Adjust confidence thresholds
    VOCABULARY = "vocabulary"  # Add accent-specific vocabulary
    COMBINED = "combined"  # Use all strategies


class AcousticModelAdapter:
    """
    Adapts acoustic model parameters based on accent characteristics.

    This class modifies transcription model parameters to better
    match the acoustic properties of specific accents.
    """

    def __init__(self) -> None:
        """Initialize acoustic model adapter."""
        self.adaptations: Dict[str, Any] = {}

    def adapt_for_accent(
        self, accent_profile: AccentProfile, base_model_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Adapt model parameters for specific accent."""
        adapted_params = base_model_params.copy()

        # Adjust speaking rate expectations
        if "expected_speaking_rate" in adapted_params:
            adapted_params[
                "expected_speaking_rate"
            ] *= accent_profile.speaking_rate_adjustment

        # Adjust pitch range
        if "pitch_range" in adapted_params:
            adapted_params["pitch_range"] = accent_profile.pitch_range

        # Apply formant adjustments
        if accent_profile.formant_adjustments:
            if "formant_weights" not in adapted_params:
                adapted_params["formant_weights"] = {}
            adapted_params["formant_weights"].update(accent_profile.formant_adjustments)

        # Adjust confidence threshold based on accent strength
        if "confidence_threshold" in adapted_params:
            adapted_params[
                "confidence_threshold"
            ] += accent_profile.base_confidence_adjustment

        logger.info("Adapted acoustic model for %s", accent_profile.accent_region.value)
        return adapted_params


class PronunciationAdapter:
    """
    Adapts pronunciation dictionaries based on accent variations.

    This class adds accent-specific pronunciation variants to improve
    recognition accuracy.
    """

    def __init__(self) -> None:
        """Initialize pronunciation adapter."""
        self.variant_cache: Dict[str, List[PronunciationVariant]] = {}

    def generate_pronunciation_variants(
        self, word: str, accent_profile: AccentProfile
    ) -> List[PronunciationVariant]:
        """Generate pronunciation variants for a word based on accent."""
        variants = []

        # Check if word has predefined variants
        existing_variants = accent_profile.get_variants_for_word(word)
        if existing_variants:
            return existing_variants

        # Apply phonetic rules based on accent
        word_lower = word.lower()

        # R-dropping (e.g., British accents)
        if accent_profile.r_dropping and "r" in word_lower:
            # Drop 'r' after vowels at end of syllables
            variant = self._apply_r_dropping(word_lower)
            if variant != word_lower:
                variants.append(
                    PronunciationVariant(
                        standard_form=word,
                        variant_form=variant,
                        accent_regions=[accent_profile.accent_region],
                        frequency=0.8,
                    )
                )

        # H-dropping
        if accent_profile.h_dropping and word_lower.startswith("h"):
            variant = word_lower[1:]  # Remove initial 'h'
            variants.append(
                PronunciationVariant(
                    standard_form=word,
                    variant_form=variant,
                    accent_regions=[accent_profile.accent_region],
                    frequency=0.6,
                )
            )

        # TH-substitution
        if accent_profile.th_substitution and "th" in word_lower:
            variant = word_lower.replace("th", accent_profile.th_substitution)
            variants.append(
                PronunciationVariant(
                    standard_form=word,
                    variant_form=variant,
                    accent_regions=[accent_profile.accent_region],
                    frequency=0.7,
                )
            )

        # Apply vowel shifts
        for original, replacement in accent_profile.vowel_shifts.items():
            if original in word_lower:
                variant = word_lower.replace(original, replacement)
                if variant != word_lower:
                    variants.append(
                        PronunciationVariant(
                            standard_form=word,
                            variant_form=variant,
                            accent_regions=[accent_profile.accent_region],
                            frequency=0.7,
                        )
                    )

        return variants

    def _apply_r_dropping(self, word: str) -> str:
        """Apply r-dropping rules."""
        # Simple rule: drop 'r' after vowels except before vowels
        vowels = "aeiou"
        result = []

        for i, char in enumerate(word):
            if char == "r":
                # Check if preceded by vowel and not followed by vowel
                if (
                    i > 0
                    and word[i - 1] in vowels
                    and (i == len(word) - 1 or word[i + 1] not in vowels)
                ):
                    continue  # Skip the 'r'
            result.append(char)

        return "".join(result)

    @requires_phi_access("read")
    def adapt_medical_terms(
        self,
        terms: List[str],
        accent_profile: AccentProfile,
        user_id: str = "system",  # pylint: disable=unused-argument
    ) -> Dict[str, List[str]]:
        """Adapt medical terminology for specific accent."""
        adapted_terms = {}

        for term in terms:
            # Check for predefined medical term variants
            if term.lower() in accent_profile.medical_term_variants:
                adapted_terms[term] = accent_profile.medical_term_variants[term.lower()]
            else:
                # Generate variants using general rules
                variants = self.generate_pronunciation_variants(term, accent_profile)
                if variants:
                    adapted_terms[term] = [v.variant_form for v in variants]

        return adapted_terms


class AccentAdapter:
    """
    Main accent adaptation system.

    This class coordinates different adaptation strategies to improve
    transcription accuracy for accented speech.
    """

    def __init__(self, accent_database: Optional[AccentDatabase] = None):
        """Initialize accent adapter."""
        self.accent_database = accent_database
        self.acoustic_adapter = AcousticModelAdapter()
        self.pronunciation_adapter = PronunciationAdapter()
        self._adaptation_cache: Dict[str, Any] = {}

        logger.info("Accent adapter initialized")

    def adapt_for_speaker(
        self,
        accent_detection_result: AccentDetectionResult,
        strategy: AdaptationStrategy = AdaptationStrategy.COMBINED,
    ) -> Dict[str, Any]:
        """
        Generate adaptations for a specific speaker's accent.

        Args:
            accent_detection_result: Result from accent detection
            strategy: Adaptation strategy to use

        Returns:
            Dictionary of adaptations to apply
        """
        # Get accent profile
        accent_profile = None
        if self.accent_database:
            accent_profile = self.accent_database.get_profile(
                accent_detection_result.primary_accent
            )

        if not accent_profile:
            logger.warning(
                "No profile found for %s", accent_detection_result.primary_accent.value
            )
            return {}

        adaptations: Dict[str, Any] = {
            "accent_region": accent_detection_result.primary_accent.value,
            "accent_strength": accent_detection_result.accent_strength.value,
            "confidence": accent_detection_result.confidence,
            "adaptations": {},
        }

        # Apply adaptations based on strategy
        if strategy in [AdaptationStrategy.ACOUSTIC_MODEL, AdaptationStrategy.COMBINED]:
            # Adapt acoustic model parameters
            base_params = {"confidence_threshold": 0.5, "expected_speaking_rate": 1.0}
            adapted_params = self.acoustic_adapter.adapt_for_accent(
                accent_profile, base_params
            )
            adaptations["adaptations"]["acoustic_model"] = adapted_params

        if strategy in [AdaptationStrategy.PRONUNCIATION, AdaptationStrategy.COMBINED]:
            # Generate pronunciation variants for common words
            common_medical_terms = [
                "patient",
                "doctor",
                "hospital",
                "medicine",
                "prescription",
                "diagnosis",
                "treatment",
                "surgery",
                "emergency",
                "symptoms",
            ]
            pronunciation_variants = {}
            for term in common_medical_terms:
                variants = self.pronunciation_adapter.generate_pronunciation_variants(
                    term, accent_profile
                )
                if variants:
                    pronunciation_variants[term] = [v.variant_form for v in variants]

            adaptations["adaptations"][
                "pronunciation_variants"
            ] = pronunciation_variants

        if strategy in [AdaptationStrategy.CONFIDENCE, AdaptationStrategy.COMBINED]:
            # Adjust confidence thresholds
            confidence_adjustments = {
                "base_adjustment": accent_profile.base_confidence_adjustment,
                "strength_factor": self._get_strength_factor(
                    accent_detection_result.accent_strength
                ),
                "recommended_threshold": 0.5
                + accent_profile.base_confidence_adjustment,
            }
            adaptations["adaptations"]["confidence"] = confidence_adjustments

        if strategy in [AdaptationStrategy.VOCABULARY, AdaptationStrategy.COMBINED]:
            # Add accent-specific vocabulary
            vocabulary_additions = {
                "medical_variants": accent_profile.medical_term_variants,
                "common_variants": self._get_common_variants(accent_profile),
            }
            adaptations["adaptations"]["vocabulary"] = vocabulary_additions

        return adaptations

    def _get_strength_factor(self, accent_strength: "AccentStrength") -> float:
        """Get adjustment factor based on accent strength."""
        strength_factors = {
            AccentStrength.NATIVE: 1.0,
            AccentStrength.MILD: 0.95,
            AccentStrength.MODERATE: 0.9,
            AccentStrength.STRONG: 0.85,
            AccentStrength.VERY_STRONG: 0.8,
        }
        return strength_factors.get(accent_strength, 0.9)

    def _get_common_variants(
        self, accent_profile: AccentProfile
    ) -> Dict[str, List[str]]:
        """Get common word variants for accent."""
        common_variants = {}

        # Add variants based on accent characteristics
        if accent_profile.r_dropping:
            common_variants.update(
                {
                    "doctor": ["doctah", "docta"],
                    "after": ["aftah", "afta"],
                    "never": ["nevah", "neva"],
                }
            )

        if accent_profile.g_dropping:
            common_variants.update(
                {"going": ["goin"], "feeling": ["feelin"], "taking": ["takin"]}
            )

        return common_variants

    def get_adaptation_summary(self, adaptations: Dict[str, Any]) -> str:
        """Generate human-readable summary of adaptations."""
        summary_parts = []

        summary_parts.append(
            f"Accent: {adaptations['accent_region']} "
            f"({adaptations['accent_strength']} strength)"
        )
        summary_parts.append(f"Confidence: {adaptations['confidence']:.2%}")

        if "adaptations" in adaptations:
            for strategy, details in adaptations["adaptations"].items():
                if strategy == "pronunciation_variants":
                    summary_parts.append(f"Added {len(details)} pronunciation variants")
                elif strategy == "confidence":
                    summary_parts.append(
                        f"Confidence adjustment: {details['base_adjustment']:+.2f}"
                    )

        return " | ".join(summary_parts)
