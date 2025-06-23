"""
Medical Term Translation Verification Service.

CRITICAL: Accurate medical terminology translation is essential for patient safety.
This service verifies that critical medical terms are properly translated.

HIPAA Compliance: Medical term verification requires:
- Access control for medical terminology verification operations
- Audit logging of all medical term access and verification
- Role-based permissions for accessing medical terminology
- Track access patterns to sensitive medical terms
"""

import re
from typing import Dict, List, Optional

from src.config import settings
from src.services.cache_service import CacheService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MedicalTermVerifier:
    """Verifies medical terms are properly translated across languages."""

    def __init__(self) -> None:
        """Initialize medical term verifier with cache and dictionaries."""
        self.cache = CacheService()

        # Load medical dictionaries
        self.medical_dictionaries = self._load_medical_dictionaries()

        # Critical terms that must be accurately translated
        self.critical_medical_terms = {
            "allergy",
            "allergic",
            "anaphylaxis",
            "anaphylactic",
            "diabetes",
            "diabetic",
            "insulin",
            "hypertension",
            "blood pressure",
            "hypotension",
            "pregnant",
            "pregnancy",
            "prenatal",
            "emergency",
            "urgent",
            "critical",
            "medication",
            "medicine",
            "drug",
            "dose",
            "dosage",
            "pain",
            "severe",
            "acute",
            "chronic",
            "breathing",
            "respiratory",
            "asthma",
            "heart",
            "cardiac",
            "chest pain",
            "stroke",
            "seizure",
            "unconscious",
            "infection",
            "fever",
            "sepsis",
            "bleeding",
            "hemorrhage",
            "blood",
            "surgery",
            "operation",
            "anesthesia",
        }

    def _load_medical_dictionaries(self) -> Dict[str, Dict[str, List[str]]]:
        """Load medical term dictionaries for different languages."""
        # In production, this would load from medical terminology databases
        # For now, include essential translations
        return {
            "en-es": {
                "allergy": ["alergia"],
                "allergic": ["alérgico", "alérgica"],
                "diabetes": ["diabetes"],
                "pregnant": ["embarazada", "embarazo"],
                "emergency": ["emergencia", "urgencia"],
                "medication": ["medicamento", "medicación", "medicina"],
                "pain": ["dolor"],
                "breathing": ["respiración", "respirar"],
                "heart": ["corazón", "cardíaco"],
                "blood": ["sangre"],
                "fever": ["fiebre"],
            },
            "en-ar": {
                "allergy": ["حساسية"],
                "diabetes": ["السكري", "مرض السكر"],
                "pregnant": ["حامل", "الحمل"],
                "emergency": ["طوارئ", "عاجل"],
                "medication": ["دواء", "علاج"],
                "pain": ["ألم", "وجع"],
                "heart": ["قلب", "قلبي"],
                "blood": ["دم"],
                "fever": ["حمى", "حرارة"],
            },
            "en-fr": {
                "allergy": ["allergie"],
                "allergic": ["allergique"],
                "diabetes": ["diabète"],
                "pregnant": ["enceinte", "grossesse"],
                "emergency": ["urgence", "urgences"],
                "medication": ["médicament", "médication"],
                "pain": ["douleur"],
                "breathing": ["respiration", "respirer"],
                "heart": ["cœur", "cardiaque"],
                "blood": ["sang"],
                "fever": ["fièvre"],
            },
            # Add more language pairs as needed
        }

    async def verify_term_translation(
        self,
        term: str,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
    ) -> bool:
        """
        Verify if a medical term is properly translated.

        Args:
            term: The medical term to verify
            source_text: Full source text
            translated_text: Full translated text
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            True if term is properly translated, False otherwise
        """
        # Check cache first
        cache_key = f"{term}:{source_lang}:{target_lang}:{hash(translated_text)}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return bool(cached)

        # Check if term exists in source text first
        if term.lower() not in source_text.lower():
            logger.warning(f"Term '{term}' not found in source text")
            return True  # Don't fail if term wasn't in source

        # Get position of term in source for context checking
        # source_position = source_text.lower().find(term.lower())
        # Context extraction would be used here for advanced context-aware verification
        # Currently using position-based matching

        # Get expected translations
        expected_translations = await self.get_medical_translations(
            term, source_lang, target_lang
        )

        if not expected_translations:
            # If no dictionary entry, use fuzzy matching
            result = await self._fuzzy_verify_translation(
                term, translated_text, target_lang
            )
        else:
            # Check if any expected translation appears in the text
            translated_lower = translated_text.lower()
            result = any(
                expected.lower() in translated_lower
                for expected in expected_translations
            )

            # If not found, check for morphological variations
            if not result:
                result = await self._check_morphological_variations(
                    expected_translations, translated_text, target_lang
                )

        # Cache result
        await self.cache.set(cache_key, result, ttl=3600)

        return result

    async def get_medical_translations(
        self, term: str, source_lang: str, target_lang: str
    ) -> List[str]:
        """Get expected medical translations for a term."""
        lang_pair = f"{source_lang}-{target_lang}"

        # Check medical dictionaries
        if lang_pair in self.medical_dictionaries:
            translations = self.medical_dictionaries[lang_pair].get(term.lower(), [])
            if translations:
                return translations

        # Try medical terminology service if available
        if hasattr(settings, "UMLS_API_KEY") and settings.UMLS_API_KEY:
            try:
                # Would integrate with UMLS or similar service
                pass
            except (TypeError, ValueError) as e:
                logger.error(f"Failed to query medical terminology service: {e}")

        # Return empty list if no translations found
        return []

    async def _fuzzy_verify_translation(
        self, term: str, translated_text: str, _target_lang: str
    ) -> bool:
        """Use fuzzy matching for terms without dictionary entries."""
        # For medical terms, often they're similar across languages
        # (e.g., "diabetes" is similar in many languages)

        # Check if the term appears nearly unchanged (common for medical terms)
        if term.lower() in translated_text.lower():
            return True

        # Check for common medical term patterns
        # Many medical terms are Latin/Greek derived and similar across languages
        medical_roots = [
            "diabet",
            "insulin",
            "cardiac",
            "hepat",
            "renal",
            "pulmon",
            "gastro",
            "neuro",
            "dermato",
            "ophtalm",
        ]

        for root in medical_roots:
            if root in term.lower() and root in translated_text.lower():
                return True

        return False

    async def _check_morphological_variations(
        self, expected_translations: List[str], translated_text: str, _target_lang: str
    ) -> bool:
        """Check for morphological variations of expected translations."""
        translated_lower = translated_text.lower()

        for expected in expected_translations:
            # Check for word stem
            stem = expected[: max(3, len(expected) - 3)].lower()
            if len(stem) >= 3 and stem in translated_lower:
                # Verify it's actually a word boundary
                if re.search(rf"\b{re.escape(stem)}\w*\b", translated_lower):
                    return True

        return False

    def _extract_context(
        self, text: str, position: int, term_length: int, window: int = 50
    ) -> str:
        """Extract context around a term for better verification."""
        start = max(0, position - window)
        end = min(len(text), position + term_length + window)
        return text[start:end]

    def is_critical_term(self, term: str) -> bool:
        """Check if a term is critical for medical safety."""
        return term.lower() in self.critical_medical_terms


# Singleton instance
class _MedicalTermVerifierSingleton:
    """Singleton holder for MedicalTermVerifier."""

    _instance: Optional[MedicalTermVerifier] = None

    @classmethod
    def get_instance(cls) -> Optional[MedicalTermVerifier]:
        """Get the singleton instance."""
        return cls._instance

    @classmethod
    def set_instance(cls, instance: MedicalTermVerifier) -> None:
        """Set the singleton instance."""
        cls._instance = instance


def get_medical_term_verifier() -> MedicalTermVerifier:
    """Get singleton medical term verifier instance."""
    if _MedicalTermVerifierSingleton.get_instance() is None:
        _MedicalTermVerifierSingleton.set_instance(MedicalTermVerifier())

    instance = _MedicalTermVerifierSingleton.get_instance()
    if instance is None:
        raise RuntimeError("Failed to create MedicalTermVerifier instance")

    return instance
