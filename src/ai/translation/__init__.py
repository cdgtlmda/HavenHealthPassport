"""
Translation pipeline for Haven Health Passport.

This module provides medical-aware translation capabilities with:
- Multi-language support (50+ languages)
- Medical terminology preservation
- Context-aware translation
- Quality assurance and validation
"""

from .base import BaseTranslationChain
from .chains import TranslationChainFactory
from .config import TranslationConfig
from .exceptions import TranslationError
from .language_detection import LanguageDetectionResult, LanguageDetector
from .regulatory import (
    ComplianceCategory,
    ComplianceChecker,
    RegulatoryMapper,
    RegulatorySystem,
    check_regulatory_compliance,
    get_regulatory_definition,
    map_regulatory_term,
    translate_healthcare_terms,
)
from .target_selection import TargetLanguageSelection, TargetLanguageSelector
from .validation import (
    BackTranslationChecker,
    BackTranslationConfig,
    BackTranslationMethod,
    BackTranslationResult,
    SimilarityMetric,
    TranslationValidationPipeline,
    ValidationConfig,
    ValidationLevel,
    ValidationResult,
    ValidationStatus,
    check_back_translation,
    evaluate_translation_quality,
)

__all__ = [
    "BaseTranslationChain",
    "TranslationChainFactory",
    "TranslationConfig",
    "TranslationError",
    "LanguageDetector",
    "LanguageDetectionResult",
    "TargetLanguageSelector",
    "TargetLanguageSelection",
    # Regulatory
    "RegulatorySystem",
    "ComplianceCategory",
    "RegulatoryMapper",
    "ComplianceChecker",
    "map_regulatory_term",
    "translate_healthcare_terms",
    "check_regulatory_compliance",
    "get_regulatory_definition",
    # Validation
    "ValidationLevel",
    "ValidationStatus",
    "ValidationResult",
    "ValidationConfig",
    "TranslationValidationPipeline",
    "BackTranslationChecker",
    "BackTranslationConfig",
    "BackTranslationResult",
    "BackTranslationMethod",
    "SimilarityMetric",
    "check_back_translation",
    "evaluate_translation_quality",
]
