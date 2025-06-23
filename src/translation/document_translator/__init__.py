"""Document translation module for medical records.

This module handles translation of complete medical documents including
structured data, preserving formatting, and maintaining medical accuracy.
"""

from src.healthcare.hipaa_access_control import require_phi_access
from src.services.encryption_service import EncryptionService

from .document_translator import DocumentTranslator, create_document_translator
from .types import (
    DocumentFormat,
    DocumentSection,
    DocumentTranslationResult,
    FHIRResourceType,
    TranslationContext,
    TranslationDirection,
    TranslationSegment,
    TranslationType,
)

__all__ = [
    "DocumentFormat",
    "DocumentSection",
    "DocumentTranslationResult",
    "FHIRResourceType",
    "TranslationContext",
    "TranslationDirection",
    "TranslationSegment",
    "TranslationType",
    "DocumentTranslator",
    "create_document_translator",
]
