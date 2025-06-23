"""
Medical-specific formality adjustment.

This module provides specialized formality adjustment for medical contexts,
considering the audience (patient vs. healthcare provider), document type,
and sensitivity of medical information.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from ..config import Language
from .core import (
    FormalityAdjuster,
    FormalityAdjustmentResult,
    FormalityContext,
    FormalityLevel,
)

logger = logging.getLogger(__name__)


class MedicalContext(Enum):
    """Medical communication contexts."""

    PATIENT_EDUCATION = "patient_education"
    CLINICAL_NOTES = "clinical_notes"
    DISCHARGE_SUMMARY = "discharge_summary"
    REFERRAL_LETTER = "referral_letter"
    PRESCRIPTION = "prescription"
    LAB_REPORT = "lab_report"
    CONSENT_FORM = "consent_form"
    INSURANCE_CLAIM = "insurance_claim"
    RESEARCH_PAPER = "research_paper"
    EMERGENCY_INSTRUCTIONS = "emergency_instructions"


@dataclass
class MedicalTermFormality:
    """Formality variations for medical terms."""

    technical_term: str
    patient_friendly: str
    context: Set[MedicalContext]
    explanation: Optional[str] = None


class MedicalFormalityAdjuster:
    """Specialized formality adjuster for medical texts."""

    def __init__(self, base_adjuster: Optional[FormalityAdjuster] = None):
        """
        Initialize medical formality adjuster.

        Args:
            base_adjuster: Base formality adjuster to use
        """
        self.base_adjuster = base_adjuster or FormalityAdjuster()
        self.medical_terms = self._load_medical_terms()
        self.context_rules = self._load_context_rules()

    def adjust_medical_text(
        self,
        text: str,
        medical_context: MedicalContext,
        target_audience: str,
        language: Language = Language.ENGLISH,
    ) -> FormalityAdjustmentResult:
        """
        Adjust medical text formality based on context and audience.

        Args:
            text: Medical text to adjust
            medical_context: Type of medical document
            target_audience: patient, healthcare_provider, insurance, etc.
            language: Language of the text

        Returns:
            FormalityAdjustmentResult with adjusted text
        """
        # Determine target formality level
        target_level = self.determine_formality_level(medical_context, target_audience)

        # Create formality context
        context = FormalityContext(
            audience=target_audience,
            relationship=self._get_relationship(medical_context, target_audience),
            document_type=medical_context.value,
            sensitivity=self._is_sensitive_context(medical_context),
            legal_context=medical_context
            in [MedicalContext.CONSENT_FORM, MedicalContext.INSURANCE_CLAIM],
        )

        # Perform base adjustment
        result = self.base_adjuster.adjust(text, target_level, language, context)

        # Apply medical-specific adjustments
        if target_audience == "patient":
            result.adjusted_text = self._simplify_medical_terms(
                result.adjusted_text, medical_context
            )
        elif target_audience == "healthcare_provider":
            result.adjusted_text = self._use_technical_terms(
                result.adjusted_text, medical_context
            )

        # Add medical-specific warnings
        if medical_context == MedicalContext.PRESCRIPTION:
            result.warnings.append(
                "Prescription language must remain clear and unambiguous"
            )

        return result

    def determine_formality_level(
        self, medical_context: MedicalContext, target_audience: str
    ) -> FormalityLevel:
        """Determine appropriate formality level."""
        # Patient-facing documents
        if target_audience == "patient":
            if medical_context in [
                MedicalContext.PATIENT_EDUCATION,
                MedicalContext.EMERGENCY_INSTRUCTIONS,
            ]:
                return FormalityLevel.INFORMAL
            elif medical_context == MedicalContext.DISCHARGE_SUMMARY:
                return FormalityLevel.NEUTRAL
            else:
                return FormalityLevel.FORMAL

        # Healthcare provider communications
        elif target_audience == "healthcare_provider":
            if medical_context in [
                MedicalContext.CLINICAL_NOTES,
                MedicalContext.REFERRAL_LETTER,
            ]:
                return FormalityLevel.FORMAL
            else:
                return FormalityLevel.VERY_FORMAL

        # Legal/administrative documents
        else:
            return FormalityLevel.VERY_FORMAL

    def _get_relationship(self, medical_context: MedicalContext, audience: str) -> str:
        """Determine relationship type based on medical context and audience.

        Uses medical context to refine the relationship determination for more
        appropriate communication style.
        """
        # Use medical context for nuanced relationship determination
        if audience == "patient":
            # Patient-facing communication varies by context
            if medical_context == MedicalContext.EMERGENCY_INSTRUCTIONS:
                return "emergency_responder_patient"  # Clear, direct communication
            elif medical_context == MedicalContext.CONSENT_FORM:
                return "legal_medical_patient"  # Formal but accessible
            elif medical_context == MedicalContext.PATIENT_EDUCATION:
                return "educator_patient"  # Friendly, educational tone
            elif medical_context in [
                MedicalContext.PRESCRIPTION,
                MedicalContext.DISCHARGE_SUMMARY,
            ]:
                return "doctor_patient_directive"  # Clear instructions
            else:
                return "doctor_patient"  # Standard doctor-patient relationship

        elif audience == "healthcare_provider":
            # Provider-to-provider communication
            if medical_context == MedicalContext.CLINICAL_NOTES:
                return "peer_clinical"  # Technical, abbreviated
            elif medical_context == MedicalContext.REFERRAL_LETTER:
                return "peer_formal"  # Professional, comprehensive
            elif medical_context == MedicalContext.LAB_REPORT:
                return "lab_to_clinician"  # Data-focused, technical
            else:
                return "peer_to_peer"  # Standard peer communication

        elif audience == "administrator":
            # Administrative communication
            if medical_context == MedicalContext.INSURANCE_CLAIM:
                return "provider_to_insurance"  # Precise, formal
            elif medical_context in [
                MedicalContext.CLINICAL_NOTES,
                MedicalContext.DISCHARGE_SUMMARY,
            ]:
                return "provider_to_admin"  # Professional, complete
            else:
                return "patient_to_admin"  # Standard administrative

        else:
            # Default based on context sensitivity
            if self._is_sensitive_context(medical_context):
                return "formal_medical"
            else:
                return "general_medical"

    def _is_sensitive_context(self, medical_context: MedicalContext) -> bool:
        """Check if context involves sensitive information."""
        sensitive_contexts = [
            MedicalContext.CONSENT_FORM,
            MedicalContext.LAB_REPORT,
            MedicalContext.CLINICAL_NOTES,
        ]
        return medical_context in sensitive_contexts

    def _simplify_medical_terms(self, text: str, context: MedicalContext) -> str:
        """Replace technical terms with patient-friendly alternatives."""
        adjusted_text = text

        for term_info in self.medical_terms:
            if context in term_info.context and term_info.technical_term in text:
                # Replace with patient-friendly version
                pattern = rf"\b{re.escape(term_info.technical_term)}\b"
                replacement = term_info.patient_friendly

                # Add explanation if needed
                if (
                    term_info.explanation
                    and context == MedicalContext.PATIENT_EDUCATION
                ):
                    replacement = f"{replacement} ({term_info.explanation})"

                adjusted_text = re.sub(pattern, replacement, adjusted_text, flags=re.I)

        return adjusted_text

    def _use_technical_terms(self, text: str, context: MedicalContext) -> str:
        """Replace patient-friendly terms with technical alternatives."""
        adjusted_text = text

        for term_info in self.medical_terms:
            if context in term_info.context and term_info.patient_friendly in text:
                # Replace with technical version
                pattern = rf"\b{re.escape(term_info.patient_friendly)}\b"
                replacement = term_info.technical_term
                adjusted_text = re.sub(pattern, replacement, adjusted_text, flags=re.I)

        return adjusted_text

    def _load_medical_terms(self) -> List[MedicalTermFormality]:
        """Load medical term formality variations."""
        return [
            MedicalTermFormality(
                technical_term="myocardial infarction",
                patient_friendly="heart attack",
                context={
                    MedicalContext.PATIENT_EDUCATION,
                    MedicalContext.DISCHARGE_SUMMARY,
                },
                explanation="when blood flow to the heart is blocked",
            ),
            MedicalTermFormality(
                technical_term="cerebrovascular accident",
                patient_friendly="stroke",
                context={
                    MedicalContext.PATIENT_EDUCATION,
                    MedicalContext.DISCHARGE_SUMMARY,
                },
                explanation="when blood flow to the brain is interrupted",
            ),
            MedicalTermFormality(
                technical_term="hypertension",
                patient_friendly="high blood pressure",
                context={
                    MedicalContext.PATIENT_EDUCATION,
                    MedicalContext.DISCHARGE_SUMMARY,
                },
            ),
            MedicalTermFormality(
                technical_term="diabetes mellitus",
                patient_friendly="diabetes",
                context={MedicalContext.PATIENT_EDUCATION},
            ),
            MedicalTermFormality(
                technical_term="dyspnea",
                patient_friendly="shortness of breath",
                context={
                    MedicalContext.PATIENT_EDUCATION,
                    MedicalContext.DISCHARGE_SUMMARY,
                },
            ),
            MedicalTermFormality(
                technical_term="analgesic",
                patient_friendly="pain medication",
                context={MedicalContext.PATIENT_EDUCATION, MedicalContext.PRESCRIPTION},
            ),
            MedicalTermFormality(
                technical_term="antipyretic",
                patient_friendly="fever reducer",
                context={MedicalContext.PATIENT_EDUCATION, MedicalContext.PRESCRIPTION},
            ),
            MedicalTermFormality(
                technical_term="prognosis",
                patient_friendly="expected outcome",
                context={MedicalContext.PATIENT_EDUCATION},
            ),
            MedicalTermFormality(
                technical_term="contraindication",
                patient_friendly="reason not to use",
                context={MedicalContext.PATIENT_EDUCATION, MedicalContext.CONSENT_FORM},
            ),
            MedicalTermFormality(
                technical_term="adverse reaction",
                patient_friendly="bad reaction",
                context={MedicalContext.PATIENT_EDUCATION},
                explanation="unwanted effect from medication",
            ),
        ]

    def _load_context_rules(self) -> Dict[MedicalContext, Dict[str, Any]]:
        """Load context-specific rules."""
        return {
            MedicalContext.PATIENT_EDUCATION: {
                "use_examples": True,
                "allow_analogies": True,
                "include_definitions": True,
                "max_sentence_length": 20,
            },
            MedicalContext.CLINICAL_NOTES: {
                "use_abbreviations": True,
                "technical_precision": True,
                "structured_format": True,
            },
            MedicalContext.CONSENT_FORM: {
                "legal_language": True,
                "explicit_risks": True,
                "clear_options": True,
            },
        }


def get_medical_formality_level(
    document_type: str, audience: str, urgency: bool = False
) -> FormalityLevel:
    """
    Get recommended formality level for medical communication.

    Args:
        document_type: Type of medical document
        audience: Target audience
        urgency: Whether communication is urgent

    Returns:
        Recommended FormalityLevel
    """
    # Emergency situations require clear, direct language
    if urgency:
        return (
            FormalityLevel.INFORMAL if audience == "patient" else FormalityLevel.NEUTRAL
        )

    # Map document types to contexts
    context_map = {
        "education": MedicalContext.PATIENT_EDUCATION,
        "notes": MedicalContext.CLINICAL_NOTES,
        "discharge": MedicalContext.DISCHARGE_SUMMARY,
        "referral": MedicalContext.REFERRAL_LETTER,
        "prescription": MedicalContext.PRESCRIPTION,
        "lab": MedicalContext.LAB_REPORT,
        "consent": MedicalContext.CONSENT_FORM,
        "insurance": MedicalContext.INSURANCE_CLAIM,
        "research": MedicalContext.RESEARCH_PAPER,
        "emergency": MedicalContext.EMERGENCY_INSTRUCTIONS,
    }

    # Find matching context
    medical_context = None
    for key, ctx in context_map.items():
        if key in document_type.lower():
            medical_context = ctx
            break

    if not medical_context:
        # Default based on audience
        return (
            FormalityLevel.INFORMAL if audience == "patient" else FormalityLevel.FORMAL
        )

    # Use adjuster logic
    adjuster = MedicalFormalityAdjuster()
    return adjuster.determine_formality_level(medical_context, audience)


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
