"""
Formality adjustment module for Haven Health Passport.

This module provides comprehensive formality detection and adjustment capabilities
for medical translations, ensuring appropriate tone and register for different
contexts and audiences.
"""

from .core import (
    FormalityAdjuster,
    FormalityAdjustmentResult,
    FormalityContext,
    FormalityDetectionResult,
    FormalityDetector,
    FormalityLevel,
    FormalityProfile,
)
from .cultural import (
    CulturalContext,
    CulturalFormalityAdapter,
    get_cultural_formality_norms,
)
from .medical import (
    MedicalContext,
    MedicalFormalityAdjuster,
    get_medical_formality_level,
)
from .rules import (
    FormalityRule,
    FormalityRuleEngine,
    get_language_formality_rules,
    register_formality_rule,
)

__all__ = [
    # Core
    "FormalityLevel",
    "FormalityDetector",
    "FormalityAdjuster",
    "FormalityProfile",
    "FormalityContext",
    "FormalityDetectionResult",
    "FormalityAdjustmentResult",
    # Rules
    "FormalityRuleEngine",
    "FormalityRule",
    "get_language_formality_rules",
    "register_formality_rule",
    # Medical
    "MedicalFormalityAdjuster",
    "MedicalContext",
    "get_medical_formality_level",
    # Cultural
    "CulturalFormalityAdapter",
    "CulturalContext",
    "get_cultural_formality_norms",
]
