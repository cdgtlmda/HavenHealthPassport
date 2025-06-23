"""Noise Reduction Module for Medical Voice Processing.

This module provides advanced noise reduction capabilities
specifically designed for medical audio recordings.
"""

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.services.encryption_service import EncryptionService

from .noise_detector import NoiseDetectionResult, NoiseDetector, SpectralAnalysis
from .noise_profile import NoiseLevel, NoiseProfile, NoiseType
from .noise_reduction_processor import (
    NoiseReductionConfig,
    NoiseReductionMethod,
    NoiseReductionProcessor,
    NoiseReductionResult,
)

__all__ = [
    # Detector
    "NoiseDetector",
    "NoiseDetectionResult",
    "SpectralAnalysis",
    # Profile
    "NoiseType",
    "NoiseLevel",
    "NoiseProfile",
    # Processor
    "NoiseReductionProcessor",
    "NoiseReductionConfig",
    "NoiseReductionResult",
    "NoiseReductionMethod",
]

__version__ = "1.0.0"
