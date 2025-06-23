"""
Cultural Translation Integration.

This module integrates cultural adaptation with the medical translation pipeline.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..context import ContextAwareTranslationRequest, ContextAwareTranslator
from .adaptation_rules import AdaptationResult, cultural_adapter
from .cultural_profiles import cultural_profile_manager
from .healthcare_systems import healthcare_adapter

logger = logging.getLogger(__name__)


@dataclass
class CulturallyAdaptedTranslationRequest:
    """Request for culturally adapted translation."""

    text: str
    source_lang: str
    target_lang: str
    source_country: Optional[str] = None
    target_country: Optional[str] = None
    adapt_formality: bool = True
    adapt_healthcare_system: bool = True
    preserve_cultural_context: bool = True
    include_cultural_notes: bool = True


@dataclass
class CulturallyAdaptedTranslationResult:
    """Result of culturally adapted translation."""

    original_text: str
    translated_text: str
    cultural_adaptations: AdaptationResult
    healthcare_adaptations: Dict[str, Any]
    cultural_notes: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]


class CulturalTranslationPipeline:
    """Pipeline for culturally aware medical translation."""

    def __init__(self) -> None:
        """Initialize the CulturalTranslationPipeline."""
        self.context_translator = ContextAwareTranslator()

    async def translate_with_cultural_adaptation(
        self, request: CulturallyAdaptedTranslationRequest, translation_func: Any
    ) -> CulturallyAdaptedTranslationResult:
        """Perform translation with cultural adaptation."""
        start_time = datetime.utcnow()

        # Step 1: Apply source culture preprocessing
        preprocessed_text = self._preprocess_for_culture(
            request.text, request.source_lang, request.source_country
        )

        # Step 2: Context-aware translation
        context_request = ContextAwareTranslationRequest(
            text=preprocessed_text,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            medical_domain=self._detect_medical_domain(request.text),
        )

        context_result = await self.context_translator.translate_with_context(
            context_request, translation_func
        )

        # Step 3: Apply cultural adaptations
        cultural_result = cultural_adapter.adapt_text(
            context_result.translated_text, request.source_lang, request.target_lang
        )

        # Step 4: Apply healthcare system adaptations
        healthcare_result = {}
        if (
            request.adapt_healthcare_system
            and request.source_country
            and request.target_country
        ):
            healthcare_result = healthcare_adapter.adapt_for_system(
                cultural_result.adapted_text,
                request.source_country,
                request.target_country,
            )
            if healthcare_result.get("adapted_text"):
                cultural_result.adapted_text = healthcare_result["adapted_text"]

        # Step 5: Post-process for target culture
        final_text = self._postprocess_for_culture(
            cultural_result.adapted_text, request.target_lang, request.target_country
        )

        # Compile cultural notes
        all_cultural_notes = []
        all_cultural_notes.extend(cultural_result.cultural_notes)
        if healthcare_result.get("notes"):
            all_cultural_notes.extend(healthcare_result["notes"])

        # Add provider guidance notes
        if request.include_cultural_notes:
            provider_notes = self._generate_provider_notes(
                request.source_lang, request.target_lang
            )
            all_cultural_notes.extend(provider_notes)

        # Compile warnings
        all_warnings = []
        all_warnings.extend(context_result.warnings)
        all_warnings.extend(cultural_result.warnings)

        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        return CulturallyAdaptedTranslationResult(
            original_text=request.text,
            translated_text=final_text,
            cultural_adaptations=cultural_result,
            healthcare_adaptations=healthcare_result,
            cultural_notes=all_cultural_notes,
            warnings=all_warnings,
            metadata={
                "processing_time": processing_time,
                "source_culture": f"{request.source_lang}-{request.source_country or 'XX'}",
                "target_culture": f"{request.target_lang}-{request.target_country or 'XX'}",
                "adaptations_applied": len(cultural_result.adaptations_applied),
                "medical_domain": context_request.medical_domain,
            },
        )

    def _preprocess_for_culture(
        self,
        text: str,
        language: str,
        country: Optional[str],
    ) -> str:
        """Preprocess text based on source culture."""
        _ = language  # Mark as intentionally unused
        _ = country  # Mark as intentionally unused
        # Handle culture-specific preprocessing
        # e.g., normalize date formats, measurements
        return text

    def _postprocess_for_culture(
        self, text: str, language: str, country: Optional[str]
    ) -> str:
        """Postprocess text for target culture."""
        # Apply final culture-specific formatting
        # e.g., honorifics, closing phrases
        profile = cultural_profile_manager.get_profile(language, country)

        if profile and profile.formality_default == "formal":
            # Add appropriate closing for formal communication
            formal_closings = {
                "ja": "よろしくお願いいたします。",  # Yoroshiku onegaishimasu
                "ko": "감사합니다.",  # Gamsahamnida
                "ar": "مع أطيب التمنيات",  # With best wishes
            }

            if language in formal_closings and not any(
                closing in text for closing in formal_closings.values()
            ):
                text += f"\n\n{formal_closings[language]}"

        return text

    def _detect_medical_domain(self, text: str) -> Optional[str]:
        """Detect medical domain from text."""
        text_lower = text.lower()

        # Simple keyword-based detection
        if any(
            word in text_lower for word in ["emergency", "urgent", "stat", "critical"]
        ):
            return "emergency"
        elif any(
            word in text_lower for word in ["child", "pediatric", "infant", "baby"]
        ):
            return "pediatrics"
        elif any(word in text_lower for word in ["heart", "cardiac", "coronary"]):
            return "cardiology"
        elif any(word in text_lower for word in ["cancer", "tumor", "oncology"]):
            return "oncology"

        return None

    def _generate_provider_notes(self, source_lang: str, target_lang: str) -> List[str]:
        """Generate notes for healthcare providers."""
        notes: List[str] = []

        source_profile = cultural_profile_manager.get_profile(source_lang)
        target_profile = cultural_profile_manager.get_profile(target_lang)

        if not source_profile or not target_profile:
            return notes

        # Communication differences
        if source_profile.communication_style != target_profile.communication_style:
            notes.append(
                f"Communication style difference: {source_profile.communication_style.value} "
                f"(source) vs {target_profile.communication_style.value} (target)"
            )

        # Family involvement differences
        if (
            source_profile.family_involvement_expected
            != target_profile.family_involvement_expected
        ):
            if target_profile.family_involvement_expected:
                notes.append(
                    "Target culture expects family involvement in medical decisions"
                )
            else:
                notes.append("Target culture emphasizes individual medical decisions")

        # Privacy differences
        if source_profile.privacy_level != target_profile.privacy_level:
            notes.append(
                f"Privacy expectations: {target_profile.privacy_level.value} "
                f"in target culture"
            )

        return notes

    def validate_cultural_appropriateness(
        self, text: str, target_culture: str
    ) -> Dict[str, Any]:
        """Validate text for cultural appropriateness."""
        profile = cultural_profile_manager.get_profile(target_culture)

        if not profile:
            return {"valid": True, "issues": []}

        issues = []

        # Check for taboo topics
        text_lower = text.lower()
        for taboo in profile.taboo_topics:
            if taboo.replace("_", " ") in text_lower:
                issues.append(f"Contains potentially taboo topic: {taboo}")

        # Check for direct language in indirect culture
        if profile.communication_style in ["indirect", "high_context"]:
            direct_phrases = ["you must", "you have to", "required", "mandatory"]
            for phrase in direct_phrases:
                if phrase in text_lower:
                    issues.append(f"Direct language '{phrase}' may be too strong")

        # Check religious considerations
        for religious in profile.religious_considerations:
            for restriction in religious.dietary_restrictions:
                if restriction in text_lower:
                    issues.append(
                        f"Contains reference to restricted item: {restriction}"
                    )

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "recommendations": self._get_recommendations(issues, profile),
        }

    def _get_recommendations(self, issues: List[str], prof: Any) -> List[str]:
        """Get recommendations based on validation issues."""
        _ = prof  # Mark as intentionally unused
        recommendations = []

        for issue in issues:
            if "taboo topic" in issue:
                recommendations.append(
                    "Consider using euphemisms or indirect language for sensitive topics"
                )
            elif "Direct language" in issue:
                recommendations.append(
                    "Soften language with conditional phrases or suggestions"
                )
            elif "restricted item" in issue:
                recommendations.append("Add cultural/religious accommodation notes")

        return list(set(recommendations))  # Remove duplicates


# Global cultural translation pipeline
cultural_translation_pipeline = CulturalTranslationPipeline()
