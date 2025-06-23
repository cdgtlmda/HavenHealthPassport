"""
Dialect detection module for Haven Health Passport.

This module provides comprehensive dialect detection capabilities for medical texts,
supporting regional variations in language usage, medical terminology, and cultural
communication patterns.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.services.encryption_service import EncryptionService

from .core import (
    DialectConfidence,
    DialectDetectionResult,
    DialectDetector,
    DialectFeatures,
    DialectProfile,
)
from .features import (
    DialectFeatureExtractor,
    LexicalFeatures,
    OrthographicFeatures,
    PhoneticFeatures,
    SyntacticFeatures,
)
from .medical import (
    MedicalDialectDetector,
    MedicalDialectVariation,
    get_medical_dialect_terms,
)
from .profiles import (
    get_dialect_profile,
    list_supported_dialects,
    register_dialect_profile,
)

__all__ = [
    # Core
    "DialectDetector",
    "DialectDetectionResult",
    "DialectFeatures",
    "DialectProfile",
    "DialectConfidence",
    # Profiles
    "get_dialect_profile",
    "list_supported_dialects",
    "register_dialect_profile",
    # Medical
    "MedicalDialectDetector",
    "MedicalDialectVariation",
    "get_medical_dialect_terms",
    # Features
    "DialectFeatureExtractor",
    "LexicalFeatures",
    "PhoneticFeatures",
    "SyntacticFeatures",
    "OrthographicFeatures",
]
