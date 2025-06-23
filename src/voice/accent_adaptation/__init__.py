"""
Accent Adaptation Module for Medical Voice Transcription.

This module provides accent detection, classification, and adaptation
capabilities to improve transcription accuracy across diverse speaker
populations in healthcare settings.
"""

from .accent_adapter import (
    AccentAdapter,
    AcousticModelAdapter,
    AdaptationStrategy,
    PronunciationAdapter,
)
from .accent_detector import (
    AccentConfidence,
    AccentDetectionResult,
    AccentDetector,
    AcousticFeatures,
)
from .accent_profile import (
    AccentDatabase,
    AccentProfile,
    AccentRegion,
    AccentStrength,
    PronunciationVariant,
)
from .medical_pronunciations import (
    MedicalPronunciationDatabase,
    MedicalTermVariant,
    get_medical_term_variants,
)

__all__ = [
    "AccentProfile",
    "AccentRegion",
    "AccentStrength",
    "PronunciationVariant",
    "AccentDatabase",
    "AccentDetector",
    "AccentDetectionResult",
    "AcousticFeatures",
    "AccentConfidence",
    "AccentAdapter",
    "AdaptationStrategy",
    "AcousticModelAdapter",
    "PronunciationAdapter",
    "MedicalPronunciationDatabase",
    "MedicalTermVariant",
    "get_medical_term_variants",
]
