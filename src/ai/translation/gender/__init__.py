"""
Gender-aware translation module for Haven Health Passport.

This module provides comprehensive gender detection, handling, and adaptation
capabilities for medical translations, ensuring accurate and respectful
communication across different languages and cultures.
"""

from .core import (
    Gender,
    GenderAdaptationResult,
    GenderAdapter,
    GenderContext,
    GenderDetectionResult,
    GenderDetector,
    GenderNeutralizer,
    GenderProfile,
)
from .inclusive import (
    InclusiveLanguageAdapter,
    InclusiveOptions,
    PronounSet,
    create_pronoun_set,
    get_inclusive_alternatives,
)
from .medical import (
    BiologicalSex,
    GenderIdentity,
    MedicalGenderAdapter,
    MedicalGenderContext,
    get_medical_gender_terms,
)
from .rules import (
    GenderRule,
    GenderRuleEngine,
    GrammaticalGender,
    get_language_gender_rules,
    register_gender_rule,
)

__all__ = [
    # Core
    "Gender",
    "GenderContext",
    "GenderDetector",
    "GenderAdapter",
    "GenderProfile",
    "GenderDetectionResult",
    "GenderAdaptationResult",
    "GenderNeutralizer",
    # Rules
    "GenderRuleEngine",
    "GenderRule",
    "GrammaticalGender",
    "get_language_gender_rules",
    "register_gender_rule",
    # Medical
    "MedicalGenderAdapter",
    "BiologicalSex",
    "GenderIdentity",
    "MedicalGenderContext",
    "get_medical_gender_terms",
    # Inclusive
    "InclusiveLanguageAdapter",
    "PronounSet",
    "InclusiveOptions",
    "get_inclusive_alternatives",
    "create_pronoun_set",
]
