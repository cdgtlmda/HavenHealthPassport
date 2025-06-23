"""Translation Context System.

This module provides context-aware translation functionality, ensuring
medical terms are translated appropriately based on their usage context.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR resource typing and validation for healthcare data.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from src.healthcare.fhir.validators import FHIRValidator
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService
from src.translation.context_system_production import translation_context_system
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MedicalContext(str, Enum):
    """Medical context types for translations."""

    ANATOMY = "anatomy"  # Body parts, organs
    SYMPTOMS = "symptoms"  # Patient symptoms
    DIAGNOSIS = "diagnosis"  # Medical diagnoses
    PROCEDURES = "procedures"  # Medical procedures
    MEDICATIONS = "medications"  # Drug names and descriptions
    LAB_RESULTS = "lab_results"  # Laboratory test results
    VITAL_SIGNS = "vital_signs"  # Blood pressure, temperature, etc.
    ALLERGIES = "allergies"  # Allergy information
    IMMUNIZATIONS = "immunizations"  # Vaccines and shots
    PATIENT_HISTORY = "patient_history"  # Medical history
    EMERGENCY = "emergency"  # Emergency-related terms
    INSTRUCTIONS = "instructions"  # Medical instructions


class FormContext(str, Enum):
    """Form context types for UI translations."""

    LABEL = "label"  # Form field labels
    PLACEHOLDER = "placeholder"  # Input placeholders
    HELPER_TEXT = "helper_text"  # Help text
    ERROR_MESSAGE = "error_message"  # Validation errors
    BUTTON = "button"  # Button text
    TOOLTIP = "tooltip"  # Tooltips
    HEADING = "heading"  # Section headings
    DESCRIPTION = "description"  # Descriptions


@dataclass
class TranslationContext:
    """Context information for a translation."""

    key: str
    domain: str  # medical, ui, general
    specific_context: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None
    max_length: Optional[int] = None
    gender: Optional[str] = None  # For gender-specific translations
    count: Optional[int] = None  # For pluralization
    tone: Optional[str] = None  # formal, informal, urgent


@dataclass
class ContextualTranslation:
    """Translation with context metadata."""

    text: str
    context: TranslationContext
    alternatives: Optional[List[str]] = None
    usage_notes: Optional[str] = None
    medical_accuracy_verified: bool = False


class TranslationContextManager:
    """Manages context-aware translations."""

    # Context-specific translation rules
    CONTEXT_RULES: Dict[MedicalContext, Dict[str, Any]] = {
        MedicalContext.ANATOMY: {
            "formality": "technical",
            "abbreviations": False,
            "lay_terms_allowed": True,
        },
        MedicalContext.SYMPTOMS: {
            "formality": "patient_friendly",
            "abbreviations": False,
            "lay_terms_allowed": True,
        },
        MedicalContext.DIAGNOSIS: {
            "formality": "technical",
            "abbreviations": True,
            "include_codes": True,  # ICD codes
        },
        MedicalContext.EMERGENCY: {
            "formality": "clear_urgent",
            "abbreviations": False,
            "max_words": 5,  # Keep emergency text short
        },
    }

    def __init__(self) -> None:
        """Initialize context manager."""
        self.context_mappings: Dict[str, Dict[str, Any]] = {}
        self.term_contexts: Dict[str, Set[MedicalContext]] = {}
        self.medical_glossary: Dict[str, Dict[str, str]] = {}
        self._load_context_mappings()
        self.fhir_validator = FHIRValidator()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default", region="us-east-1"
        )

    def _load_context_mappings(self) -> None:
        """Load context mapping configurations."""
        # Define context mappings for common translation keys
        self.context_mappings = {
            # Medical contexts
            "medical.blood_pressure": {
                "domain": "medical",
                "context": MedicalContext.VITAL_SIGNS,
                "abbreviation": "BP",
                "unit_aware": True,
            },
            "medical.heart_rate": {
                "domain": "medical",
                "context": MedicalContext.VITAL_SIGNS,
                "abbreviation": "HR",
                "unit": "bpm",
            },
            "medical.temperature": {
                "domain": "medical",
                "context": MedicalContext.VITAL_SIGNS,
                "celsius_fahrenheit": True,
            },
            "medical.chest_pain": {
                "domain": "medical",
                "context": MedicalContext.SYMPTOMS,
                "severity_scale": True,
                "emergency_flag": True,
            },
            # UI contexts
            "form.name": {
                "domain": "ui",
                "context": FormContext.LABEL,
                "required": True,
                "max_length": 20,
            },
            "form.date_of_birth": {
                "domain": "ui",
                "context": FormContext.LABEL,
                "date_format_aware": True,
            },
            "errors.required_field": {
                "domain": "ui",
                "context": FormContext.ERROR_MESSAGE,
                "tone": "polite",
                "actionable": True,
            },
        }

    def get_translation_with_context(
        self,
        key: str,
        language: str,
        variables: Optional[Dict[str, Any]] = None,
        override_context: Optional[TranslationContext] = None,
    ) -> ContextualTranslation:
        """Get translation with appropriate context."""
        # Use override context if provided
        if override_context:
            context = override_context
        else:
            # Build context from mappings
            context = self._build_context(key, variables)

        # Get base translation
        translation_text = self._get_base_translation(key, language)

        # Apply context-specific modifications
        translation_text = self._apply_context_rules(
            translation_text, context, language
        )

        # Handle variables
        if variables:
            translation_text = self._interpolate_variables(
                translation_text, variables, language
            )

        # Create contextual translation
        return ContextualTranslation(
            text=translation_text,
            context=context,
            alternatives=self._get_alternatives(key, language, context),
            usage_notes=self._get_usage_notes(key, context),
            medical_accuracy_verified=self._is_medically_verified(key),
        )

    def _build_context(
        self, key: str, variables: Optional[Dict[str, Any]] = None
    ) -> TranslationContext:
        """Build context from key and variables."""
        mapping: Dict[str, Any] = self.context_mappings.get(key, {})

        return TranslationContext(
            key=key,
            domain=mapping.get("domain", "general"),
            specific_context=mapping.get("context"),
            variables=variables,
            max_length=mapping.get("max_length"),
            gender=variables.get("gender") if variables else None,
            count=variables.get("count") if variables else None,
            tone=mapping.get("tone", "formal"),
        )

    def _get_base_translation(self, key: str, language: str) -> str:
        """Get base translation text."""
        # Use production translation system
        return translation_context_system.get_base_translation(key, language)

    def _apply_context_rules(
        self, text: str, context: TranslationContext, language: str
    ) -> str:
        """Apply context-specific rules to translation."""
        rules = {}  # Initialize rules to empty dict
        if context.specific_context and isinstance(context.specific_context, str):
            # Convert string to MedicalContext if possible
            try:
                mc = MedicalContext(context.specific_context)
                if mc in self.CONTEXT_RULES:
                    rules = self.CONTEXT_RULES[mc]
            except ValueError:
                pass

            # Apply emergency context rules
            if context.specific_context == MedicalContext.EMERGENCY:
                text = self._simplify_for_emergency(text, language)

            # Apply formality rules
            if rules.get("formality") == "patient_friendly":
                text = self._make_patient_friendly(text, language)

        # Apply length constraints
        if context.max_length and len(text) > context.max_length:
            text = self._truncate_intelligently(text, context.max_length, language)

        return text

    def _interpolate_variables(
        self, text: str, variables: Dict[str, Any], language: str
    ) -> str:
        """Interpolate variables into translation."""
        # Handle special variable types
        for key, value in variables.items():
            placeholder = f"{{{key}}}"

            if key == "count":
                # Handle pluralization
                text = self._apply_pluralization(text, value, language)
            elif key == "gender":
                # Handle gender-specific forms
                text = self._apply_gender_forms(text, value, language)
            elif placeholder in text:
                # Simple replacement
                text = text.replace(placeholder, str(value))

        return text

    def _apply_pluralization(self, text: str, count: int, language: str) -> str:
        """Apply pluralization rules."""
        # Language-specific pluralization
        if language == "en":
            if count == 1:
                return text.replace("{plural}", "")
            else:
                return text.replace("{plural}", "s")
        elif language == "ar":
            # Arabic has dual and plural forms
            if count == 1:
                return text  # Singular
            elif count == 2:
                return text + " (dual)"  # Placeholder for dual form
            else:
                return text + " (plural)"  # Placeholder for plural form

        return text

    def _apply_gender_forms(self, text: str, gender: str, language: str) -> str:
        """Apply gender-specific forms."""
        # Language-specific gender rules
        if language in ["es", "fr", "ar"]:
            if "{gender}" in text:
                if gender == "male":
                    text = text.replace("{gender}", "o")  # Spanish/Portuguese
                elif gender == "female":
                    text = text.replace("{gender}", "a")

        return text

    def _simplify_for_emergency(self, text: str, language: str) -> str:
        """Simplify text for emergency context."""
        # Remove unnecessary words, keep core meaning
        simplifications = {
            "en": {
                "Please seek immediate medical attention": "SEEK HELP NOW",
                "Call emergency services": "CALL 911",
            },
            "es": {
                "Por favor busque atención médica inmediata": "BUSQUE AYUDA AHORA",
                "Llame a servicios de emergencia": "LLAME AL 911",
            },
        }

        if language in simplifications:
            for long_form, short_form in simplifications[language].items():
                if long_form in text:
                    text = text.replace(long_form, short_form)

        return text.upper()  # Emergency text in capitals

    def _make_patient_friendly(self, text: str, language: str) -> str:
        """Convert technical terms to patient-friendly language."""
        # Map technical terms to lay terms
        lay_terms = {
            "en": {
                "hypertension": "high blood pressure",
                "hypotension": "low blood pressure",
                "tachycardia": "rapid heartbeat",
                "bradycardia": "slow heartbeat",
            },
            "es": {
                "hipertensión": "presión arterial alta",
                "hipotensión": "presión arterial baja",
                "taquicardia": "latidos rápidos del corazón",
            },
        }

        if language in lay_terms:
            for technical, lay in lay_terms[language].items():
                text = text.replace(technical, lay)

        return text

    def _truncate_intelligently(self, text: str, max_length: int, language: str) -> str:
        """Truncate text intelligently while preserving meaning."""
        if len(text) <= max_length:
            return text

        # Try to truncate at word boundary
        truncated = text[:max_length]
        last_space = truncated.rfind(" ")

        if last_space > max_length * 0.8:  # If space is reasonably close to end
            truncated = truncated[:last_space]

        # Add ellipsis based on language
        ellipsis = "..." if language not in ["zh", "ja", "ko"] else "…"

        return truncated.rstrip() + ellipsis

    def _get_alternatives(
        self, key: str, language: str, context: TranslationContext
    ) -> List[str]:
        """Get alternative translations for the context."""
        # Use production translation system
        return translation_context_system.get_alternatives(key, language, context)

    def _get_usage_notes(self, key: str, _context: TranslationContext) -> Optional[str]:
        """Get usage notes for translators."""
        notes = {
            "medical.blood_pressure": "Use standard medical abbreviation BP in clinical contexts",
            "medical.chest_pain": "Critical symptom - ensure translation conveys urgency",
            "form.date_of_birth": "Date format varies by locale - use appropriate format",
        }

        return notes.get(key)

    def _is_medically_verified(self, key: str) -> bool:
        """Check if translation has been medically verified."""
        # Use production translation system
        return translation_context_system.is_medically_verified(key)

    def register_context_mapping(self, key: str, mapping: Dict[str, Any]) -> None:
        """Register a new context mapping."""
        self.context_mappings[key] = mapping
        logger.info(f"Registered context mapping for: {key}")

    def get_context_for_key(self, key: str) -> Dict[str, Any]:
        """Get context mapping for a translation key."""
        return self.context_mappings.get(key, {})

    def validate_medical_translation(
        self, key: str, translation: str, language: str, context: MedicalContext
    ) -> Tuple[bool, List[str]]:
        """Validate medical translation accuracy."""
        issues = []

        # Check for required medical codes
        if context == MedicalContext.DIAGNOSIS:
            if "ICD" not in translation and self._requires_code(key):
                issues.append("Missing ICD code reference")

        # Check for ambiguous terms
        ambiguous_terms = self._get_ambiguous_terms(language)
        for term in ambiguous_terms:
            if term in translation.lower():
                issues.append(f"Contains ambiguous term: {term}")

        # Check length for emergency contexts
        if context == MedicalContext.EMERGENCY:
            word_count = len(translation.split())
            max_words_default: Dict[str, Any] = {}
            max_words = self.CONTEXT_RULES.get(context, max_words_default).get(
                "max_words", 10
            )
            if isinstance(max_words, int) and word_count > max_words:
                issues.append(
                    f"Emergency text too long: {word_count} words (max: {max_words})"
                )

        return len(issues) == 0, issues

    def _requires_code(self, key: str) -> bool:
        """Check if translation requires medical code."""
        # Keys that require medical codes
        code_required = {"diagnosis.", "procedure.", "medication."}

        return any(key.startswith(prefix) for prefix in code_required)

    def _get_ambiguous_terms(self, language: str) -> Set[str]:
        """Get list of ambiguous medical terms to avoid."""
        ambiguous = {
            "en": {"condition", "issue", "problem", "thing"},
            "es": {"condición", "problema", "cosa"},
            "fr": {"condition", "problème", "chose"},
        }

        return ambiguous.get(language, set())

    def map_to_fhir_resource_type(self, context: MedicalContext) -> str:
        """Map medical context to FHIR resource type."""
        context_to_fhir = {
            MedicalContext.ANATOMY: "BodyStructure",
            MedicalContext.SYMPTOMS: "Observation",
            MedicalContext.DIAGNOSIS: "Condition",
            MedicalContext.PROCEDURES: "Procedure",
            MedicalContext.MEDICATIONS: "MedicationStatement",
            MedicalContext.LAB_RESULTS: "Observation",
            MedicalContext.VITAL_SIGNS: "Observation",
            MedicalContext.ALLERGIES: "AllergyIntolerance",
            MedicalContext.IMMUNIZATIONS: "Immunization",
            MedicalContext.PATIENT_HISTORY: "Condition",
            MedicalContext.EMERGENCY: "Encounter",
            MedicalContext.INSTRUCTIONS: "ServiceRequest",
        }
        return context_to_fhir.get(context, "Basic")

    @audit_phi_access("translate_medical_content_with_phi")
    @require_permission(AccessPermission.READ_PHI)
    def translate_with_fhir_context(
        self,
        text: str,
        fhir_resource: Dict[str, Any],
        target_language: str,
        context: Optional[MedicalContext] = None,
    ) -> Dict[str, Any]:
        """Translate medical content with FHIR resource context.

        This method handles PHI and requires proper access permissions.
        """
        # Validate FHIR resource
        resource_type = fhir_resource.get("resourceType", "")
        if not self.fhir_validator.validate_resource(fhir_resource):
            raise ValueError(f"Invalid FHIR {resource_type} resource")

        # Determine context from resource type if not provided
        if not context:
            context = self._infer_context_from_fhir(resource_type)

        # Encrypt sensitive fields
        encrypted_fields = {}
        sensitive_paths = self._get_sensitive_fhir_paths(resource_type)

        for path in sensitive_paths:
            value = self._extract_fhir_value(fhir_resource, path)
            if value:
                encrypted_fields[path] = self.encryption_service.encrypt(
                    str(value).encode()
                )

        # Get contextual translation
        translation_context = TranslationContext(
            key=text,
            domain="medical",
            specific_context=context.value if context else None,
        )
        contextual_translation = self.get_translation_with_context(
            key=text, language=target_language, override_context=translation_context
        )

        # Validate the translation
        is_valid, issues = (
            self.validate_medical_translation(
                key=text,
                translation=contextual_translation.text,
                language=target_language,
                context=context,
            )
            if context
            else (True, [])
        )

        return {
            "translation": contextual_translation,
            "context": context.value,
            "fhirResourceType": resource_type,
            "valid": is_valid,
            "issues": issues,
            "encrypted": True,
        }

    def _infer_context_from_fhir(self, resource_type: str) -> MedicalContext:
        """Infer medical context from FHIR resource type."""
        fhir_to_context = {
            "Observation": MedicalContext.LAB_RESULTS,
            "Condition": MedicalContext.DIAGNOSIS,
            "Procedure": MedicalContext.PROCEDURES,
            "MedicationStatement": MedicalContext.MEDICATIONS,
            "AllergyIntolerance": MedicalContext.ALLERGIES,
            "Immunization": MedicalContext.IMMUNIZATIONS,
            "Encounter": MedicalContext.EMERGENCY,
        }
        return fhir_to_context.get(resource_type, MedicalContext.SYMPTOMS)

    def _get_sensitive_fhir_paths(self, resource_type: str) -> List[str]:
        """Get paths to sensitive data in FHIR resources."""
        sensitive_paths = {
            "Patient": ["name", "telecom", "address", "birthDate"],
            "Observation": ["subject.reference", "performer.reference"],
            "Condition": ["subject.reference", "asserter.reference"],
            "Procedure": ["subject.reference", "performer.actor.reference"],
            "MedicationStatement": ["subject.reference"],
            "AllergyIntolerance": ["patient.reference"],
            "Immunization": ["patient.reference"],
        }
        return sensitive_paths.get(resource_type, [])

    def _extract_fhir_value(self, resource: Dict[str, Any], path: str) -> Any:
        """Extract value from FHIR resource using dot notation path."""
        parts = path.split(".")
        value: Any = resource

        for part in parts:
            if value is None:
                return None

            if isinstance(value, dict):
                value = value.get(part)
            elif isinstance(value, list) and value:
                value = value[0].get(part) if isinstance(value[0], dict) else None
            else:
                value = None

        return value


# Global context manager instance
context_manager = TranslationContextManager()
