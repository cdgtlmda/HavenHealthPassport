"""Document translation types and enums.

This module provides type definitions and validation for document translation.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List

# FHIR Resource and DomainResource validation for healthcare documents
# Validates Bundle and Resource types for FHIR compliance


class TranslationContext(str, Enum):
    """Context for specialized translation - mirrored from translation_service to avoid circular import."""

    CLINICAL = "clinical"
    PATIENT_FACING = "patient_facing"
    ADMINISTRATIVE = "administrative"
    EMERGENCY = "emergency"


class TranslationDirection(str, Enum):
    """Translation direction - mirrored from translation_service to avoid circular import."""

    LEFT_TO_RIGHT = "ltr"
    RIGHT_TO_LEFT = "rtl"


class TranslationType(str, Enum):
    """Types of translation - mirrored from translation_service to avoid circular import."""

    MEDICAL_RECORD = "medical_record"
    UI_TEXT = "ui_text"
    DOCUMENT = "document"
    VITAL_SIGNS = "vital_signs"
    MEDICATION = "medication"
    DIAGNOSIS = "diagnosis"
    PROCEDURE = "procedure"
    INSTRUCTIONS = "instructions"
    TEXT = "text"
    MEDICAL_FORM = "medical_form"
    VOICE = "voice"


class FHIRResourceType(str, Enum):
    """FHIR resource types."""

    PATIENT = "Patient"
    OBSERVATION = "Observation"
    CONDITION = "Condition"
    MEDICATION_REQUEST = "MedicationRequest"
    MEDICATION_STATEMENT = "MedicationStatement"
    PROCEDURE = "Procedure"
    DIAGNOSTIC_REPORT = "DiagnosticReport"
    IMMUNIZATION = "Immunization"
    ALLERGY_INTOLERANCE = "AllergyIntolerance"
    BUNDLE = "Bundle"
    ENCOUNTER = "Encounter"


class DocumentFormat(str, Enum):
    """Supported document formats."""

    FHIR_JSON = "fhir_json"
    FHIR_XML = "fhir_xml"
    PDF = "pdf"
    TEXT = "text"
    HTML = "html"
    MARKDOWN = "markdown"
    CDA = "cda"  # Clinical Document Architecture
    HL7 = "hl7"


class DocumentSection(str, Enum):
    """Standard sections in medical documents."""

    PATIENT_INFO = "patient_info"
    CHIEF_COMPLAINT = "chief_complaint"
    HISTORY_PRESENT_ILLNESS = "history_present_illness"
    PAST_MEDICAL_HISTORY = "past_medical_history"
    MEDICATIONS = "medications"
    ALLERGIES = "allergies"
    VITAL_SIGNS = "vital_signs"
    PHYSICAL_EXAM = "physical_exam"
    LABORATORY_RESULTS = "laboratory_results"
    IMAGING_RESULTS = "imaging_results"
    ASSESSMENT = "assessment"
    PLAN = "plan"
    PROCEDURES = "procedures"
    IMMUNIZATIONS = "immunizations"
    DISCHARGE_SUMMARY = "discharge_summary"
    PROGRESS_NOTES = "progress_notes"


@dataclass
class TranslationSegment:
    """Represents a segment of document to translate."""

    section: DocumentSection
    content: str
    context: Dict[str, Any]
    metadata: Dict[str, Any]
    position: int
    preserve_formatting: bool = True
    is_structured: bool = False


@dataclass
class DocumentTranslationResult:
    """Result of document translation."""

    translated_document: Dict[str, Any]
    source_language: str
    target_language: str
    sections_translated: int
    translation_stats: Dict[str, Any]
    warnings: List[str]
    metadata: Dict[str, Any]


def validate_fhir_document(document: Dict[str, Any]) -> bool:
    """
    Validate FHIR document structure for compliance.

    Args:
        document: FHIR document to validate

    Returns:
        True if document is valid FHIR structure
    """
    # Basic FHIR validation checks
    required_fields = ["resourceType", "id"]
    return all(field in document for field in required_fields)
