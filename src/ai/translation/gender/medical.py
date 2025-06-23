"""
Medical-specific gender handling.

This module provides specialized gender handling for medical contexts,
including biological sex considerations, medical terminology, and
sensitive health topics.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Set

from ..config import Language
from .core import Gender, GenderAdaptationResult, GenderAdapter, GenderContext

logger = logging.getLogger(__name__)


class BiologicalSex(Enum):
    """Biological sex categories for medical contexts."""

    MALE = "male"
    FEMALE = "female"
    INTERSEX = "intersex"
    UNKNOWN = "unknown"


class GenderIdentity(Enum):
    """Gender identity categories."""

    MAN = "man"
    WOMAN = "woman"
    NON_BINARY = "non-binary"
    GENDERFLUID = "genderfluid"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer not to say"


@dataclass
class MedicalGenderContext:
    """Medical-specific gender context."""

    biological_sex: Optional[BiologicalSex] = None
    gender_identity: Optional[GenderIdentity] = None
    pronouns: Optional[str] = None  # e.g., "she/her", "they/them"
    medical_relevance: bool = True  # Whether biological sex is medically relevant
    sensitive_topic: bool = False
    reproductive_health: bool = False
    document_type: str = "general"


class MedicalGenderAdapter:
    """Specialized gender adapter for medical texts."""

    def __init__(self, base_adapter: Optional[GenderAdapter] = None):
        """
        Initialize medical gender adapter.

        Args:
            base_adapter: Base gender adapter to use
        """
        self.base_adapter = base_adapter or GenderAdapter()
        self.medical_terms = self._load_medical_gender_terms()
        self.sensitive_terms = self._load_sensitive_terms()

    def adapt_medical_text(
        self,
        text: str,
        medical_context: MedicalGenderContext,
        language: Language = Language.ENGLISH,
    ) -> GenderAdaptationResult:
        """
        Adapt medical text with gender considerations.

        Args:
            text: Medical text to adapt
            medical_context: Medical gender context
            language: Language of the text

        Returns:
            GenderAdaptationResult with adapted text
        """
        # Determine target gender from context
        target_gender = self._determine_target_gender(medical_context)

        # Create general gender context
        general_context = GenderContext(
            subject_gender=target_gender,
            medical_context=True,
            prefer_neutral=medical_context.gender_identity == GenderIdentity.NON_BINARY,
        )

        # Perform base adaptation
        result = self.base_adapter.adapt(text, target_gender, language, general_context)

        # Apply medical-specific adjustments
        result.adapted_text = self._apply_medical_adjustments(
            result.adapted_text, medical_context, language
        )

        # Add medical warnings if needed
        if medical_context.medical_relevance and medical_context.biological_sex:
            result.warnings.append(
                f"Biological sex ({medical_context.biological_sex.value}) "
                "maintained where medically relevant"
            )

        return result

    def _determine_target_gender(self, context: MedicalGenderContext) -> Gender:
        """Determine target gender from medical context."""
        # Map gender identity to gender for adaptation
        identity_map = {
            GenderIdentity.MAN: Gender.MASCULINE,
            GenderIdentity.WOMAN: Gender.FEMININE,
            GenderIdentity.NON_BINARY: Gender.NEUTRAL,
            GenderIdentity.GENDERFLUID: Gender.NEUTRAL,
        }

        if context.gender_identity:
            return identity_map.get(context.gender_identity, Gender.NEUTRAL)

        # Fall back to biological sex if no gender identity specified
        if context.biological_sex:
            if context.biological_sex == BiologicalSex.MALE:
                return Gender.MASCULINE
            elif context.biological_sex == BiologicalSex.FEMALE:
                return Gender.FEMININE

        return Gender.NEUTRAL

    def _apply_medical_adjustments(
        self, text: str, context: MedicalGenderContext, language: Language
    ) -> str:
        """Apply medical-specific gender adjustments."""
        adjusted_text = text

        # Handle biological sex references where medically relevant
        if context.medical_relevance and context.biological_sex:
            # Preserve biological sex terms in medical contexts
            sex_terms = {
                BiologicalSex.MALE: ["male", "XY", "testicular", "prostate"],
                BiologicalSex.FEMALE: [
                    "female",
                    "XX",
                    "ovarian",
                    "uterine",
                    "cervical",
                ],
                BiologicalSex.INTERSEX: [
                    "intersex",
                    "DSD",
                    "differences of sex development",
                ],
            }

            # Add clarification if biological sex differs from gender identity
            if context.gender_identity and self._sex_gender_mismatch(
                context.biological_sex, context.gender_identity
            ):

                # Add note about biological sex where relevant
                for term in sex_terms.get(context.biological_sex, []):
                    if term.lower() in adjusted_text.lower():
                        # Don't modify the term, but could add clarification
                        pass  # Handled by warnings

        # Handle sensitive reproductive health terms
        if context.reproductive_health:
            adjusted_text = self._handle_reproductive_terms(
                adjusted_text, context, language
            )

        # Apply inclusive language for general medical terms
        if context.gender_identity in [
            GenderIdentity.NON_BINARY,
            GenderIdentity.GENDERFLUID,
        ]:
            inclusive_terms = self.medical_terms.get("inclusive", {})
            for gendered, inclusive in inclusive_terms.items():
                if gendered in adjusted_text:
                    adjusted_text = adjusted_text.replace(gendered, inclusive)

        return adjusted_text

    def _sex_gender_mismatch(
        self,
        biological_sex: Optional[BiologicalSex],
        gender_identity: Optional[GenderIdentity],
    ) -> bool:
        """Check if biological sex and gender identity mismatch."""
        if not biological_sex or not gender_identity:
            return False

        matches = {
            (BiologicalSex.MALE, GenderIdentity.MAN): False,
            (BiologicalSex.FEMALE, GenderIdentity.WOMAN): False,
        }

        return matches.get((biological_sex, gender_identity), True)

    def _handle_reproductive_terms(
        self, text: str, context: MedicalGenderContext, language: Language
    ) -> str:
        """Handle reproductive health terms sensitively."""
        # Log language for context
        logger.debug("Handling reproductive terms in %s", language)

        # Use person-first language
        replacements = {
            "pregnant woman": "pregnant person",
            "expectant mother": "expectant parent",
            "maternal": "gestational",
            "breastfeeding": "chestfeeding or breastfeeding",
        }

        adjusted_text = text
        if context.gender_identity in [GenderIdentity.NON_BINARY, GenderIdentity.MAN]:
            for old, new in replacements.items():
                adjusted_text = adjusted_text.replace(old, new)

        return adjusted_text

    def _load_medical_gender_terms(self) -> Dict[str, Dict[str, str]]:
        """Load medical gender-specific terms."""
        return {
            "inclusive": {
                "mother": "parent",
                "father": "parent",
                "maternal": "parental",
                "paternal": "parental",
                "maternity": "parental",
                "paternity": "parental",
            },
            "biological": {
                # Terms that should preserve biological sex
                "prostate": "prostate",
                "ovarian": "ovarian",
                "testicular": "testicular",
                "cervical": "cervical",
                "uterine": "uterine",
            },
        }

    def _load_sensitive_terms(self) -> Set[str]:
        """Load sensitive medical terms requiring special handling."""
        return {
            "pregnancy",
            "pregnant",
            "menstruation",
            "menstrual",
            "erectile",
            "vaginal",
            "penile",
            "breast",
            "chest",
            "hormone",
            "testosterone",
            "estrogen",
            "transition",
        }


def get_medical_gender_terms(category: str) -> Dict[str, str]:
    """
    Get medical gender terms for a specific category.

    Args:
        category: Term category (e.g., "reproductive", "anatomical")

    Returns:
        Dictionary of gendered term mappings
    """
    terms = {
        "reproductive": {
            "sperm": "gametes",
            "egg": "gametes",
            "mother": "gestational parent",
            "father": "non-gestational parent",
            "maternal": "gestational",
            "paternal": "non-gestational",
        },
        "anatomical": {
            "penis": "external genitalia",
            "vagina": "internal genitalia",
            "breasts": "chest tissue",
            "testes": "gonads",
            "ovaries": "gonads",
        },
        "hormonal": {
            "testosterone": "masculinizing hormone",
            "estrogen": "feminizing hormone",
            "male hormones": "masculinizing hormones",
            "female hormones": "feminizing hormones",
        },
        "general": {
            "he or she": "they",
            "his or her": "their",
            "man or woman": "person",
            "male or female": "person",
        },
    }

    return terms.get(category, {})
