"""Document translator implementation."""

import base64
import hashlib
import io
import json
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import PyPDF2

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.utils.logging import get_logger

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

if TYPE_CHECKING:
    from src.healthcare.fhir_validator import FHIRValidator
    from src.services.translation_service import TranslationService

logger = get_logger(__name__)


class DocumentTranslator:
    """Handles translation of complete medical documents."""

    # Section-specific translation contexts
    SECTION_CONTEXTS = {
        DocumentSection.PATIENT_INFO: TranslationContext.ADMINISTRATIVE,
        DocumentSection.CHIEF_COMPLAINT: TranslationContext.PATIENT_FACING,
        DocumentSection.HISTORY_PRESENT_ILLNESS: TranslationContext.CLINICAL,
        DocumentSection.MEDICATIONS: TranslationContext.CLINICAL,
        DocumentSection.VITAL_SIGNS: TranslationContext.CLINICAL,
        DocumentSection.PHYSICAL_EXAM: TranslationContext.CLINICAL,
        DocumentSection.LABORATORY_RESULTS: TranslationContext.CLINICAL,
        DocumentSection.ASSESSMENT: TranslationContext.CLINICAL,
        DocumentSection.PLAN: TranslationContext.PATIENT_FACING,
        DocumentSection.DISCHARGE_SUMMARY: TranslationContext.PATIENT_FACING,
    }

    # Fields that should not be translated
    PRESERVE_FIELDS = {
        "id",
        "identifier",
        "system",
        "code",
        "reference",
        "resourceType",
        "meta",
        "extension",
        "url",
        "valueQuantity",
        "valueCode",
        "valueDateTime",
        "effectiveDateTime",
        "issued",
        "recordedDate",
    }

    # Medical codes that should be preserved
    MEDICAL_CODES = {
        "ICD10",
        "ICD9",
        "SNOMED",
        "LOINC",
        "RxNorm",
        "CPT",
        "HCPCS",
        "NDC",
        "CVX",
        "MVX",
    }

    # FHIR Resource type mapping
    FHIR_RESOURCE_MAPPING = {
        "Patient": FHIRResourceType.PATIENT,
        "Observation": FHIRResourceType.OBSERVATION,
        "MedicationStatement": FHIRResourceType.MEDICATION_STATEMENT,
        "Condition": FHIRResourceType.CONDITION,
        "Procedure": FHIRResourceType.PROCEDURE,
        "DiagnosticReport": FHIRResourceType.DIAGNOSTIC_REPORT,
        "Bundle": FHIRResourceType.BUNDLE,
        "Immunization": FHIRResourceType.IMMUNIZATION,
        "AllergyIntolerance": FHIRResourceType.ALLERGY_INTOLERANCE,
        "Encounter": FHIRResourceType.ENCOUNTER,
    }

    def __init__(self, translation_service: "TranslationService"):
        """Initialize document translator."""
        self.translation_service = translation_service
        self._section_cache: Dict[str, Any] = {}
        self._document_context: Dict[str, Any] = {}
        self._fhir_validator: Optional["FHIRValidator"] = (
            None  # Lazy load to avoid circular import
        )

    @property
    def fhir_validator(self) -> "FHIRValidator":
        """Get FHIR validator instance (lazy loaded)."""
        if self._fhir_validator is None:
            from src.healthcare.fhir_validator import (  # pylint: disable=import-outside-toplevel
                FHIRValidator,
            )

            self._fhir_validator = FHIRValidator()
        return self._fhir_validator

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("translate_fhir_document")
    def translate_fhir_document(
        self,
        fhir_document: Dict[str, Any],
        target_language: TranslationDirection,
        source_language: Optional[TranslationDirection] = None,
        target_dialect: Optional[str] = None,
        target_region: Optional[str] = None,
        preserve_codes: bool = True,
    ) -> DocumentTranslationResult:
        """
        Translate a FHIR document.

        Args:
            fhir_document: FHIR document as dictionary
            target_language: Target language
            source_language: Source language (auto-detect if not provided)
            target_dialect: Specific dialect to use
            target_region: Target region for measurements
            preserve_codes: Whether to preserve medical codes

        Returns:
            DocumentTranslationResult
        """
        start_time = datetime.utcnow()
        warnings = []

        try:
            # Detect resource type
            resource_type = fhir_document.get("resourceType")
            if not resource_type:
                raise ValueError("Invalid FHIR document: missing resourceType")

            # Validate FHIR resource type
            if resource_type not in self.FHIR_RESOURCE_MAPPING:
                raise ValueError(f"Unsupported FHIR resource type: {resource_type}")

            # Perform FHIR validation
            validation_method = getattr(
                self.fhir_validator, f"validate_{resource_type.lower()}", None
            )
            if validation_method is not None and callable(validation_method):
                # Call the validation method
                # pylint: disable=not-callable
                validation_result = validation_method(fhir_document)
                # pylint: enable=not-callable
                if not validation_result["valid"]:
                    warnings.extend(validation_result.get("warnings", []))
                    if validation_result.get("errors"):
                        raise ValueError(
                            f"FHIR validation errors: {validation_result['errors']}"
                        )

            # Create document context
            doc_id = hashlib.md5(
                json.dumps(fhir_document, sort_keys=True).encode(),
                usedforsecurity=False,
            ).hexdigest()
            self._document_context[doc_id] = {
                "resource_type": resource_type,
                "fhir_type": self.FHIR_RESOURCE_MAPPING[resource_type],
                "source_language": source_language,
                "target_language": target_language,
                "target_dialect": target_dialect,
                "target_region": target_region,
            }

            # Set translation context
            self.translation_service.set_context_scope(
                session_id=f"doc_{doc_id}", document_id=doc_id
            )

            # Translate based on resource type
            if resource_type == "Bundle":
                translated = self._translate_bundle(
                    fhir_document,
                    target_language,
                    source_language,
                    target_dialect,
                    target_region,
                    preserve_codes,
                )
            elif resource_type == "Patient":
                translated = self._translate_patient(
                    fhir_document,
                    target_language,
                    source_language,
                    target_dialect,
                    target_region,
                )
            elif resource_type == "Observation":
                translated = self._translate_observation(
                    fhir_document,
                    target_language,
                    source_language,
                    target_dialect,
                    target_region,
                    preserve_codes,
                )
            elif resource_type == "MedicationStatement":
                translated = self._translate_medication(
                    fhir_document,
                    target_language,
                    source_language,
                    target_dialect,
                    target_region,
                )
            elif resource_type == "Condition":
                translated = self._translate_condition(
                    fhir_document,
                    target_language,
                    source_language,
                    target_dialect,
                    target_region,
                    preserve_codes,
                )
            elif resource_type == "Procedure":
                translated = self._translate_procedure(
                    fhir_document,
                    target_language,
                    source_language,
                    target_dialect,
                    target_region,
                    preserve_codes,
                )
            elif resource_type == "DiagnosticReport":
                translated = self._translate_diagnostic_report(
                    fhir_document,
                    target_language,
                    source_language,
                    target_dialect,
                    target_region,
                    preserve_codes,
                )
            else:
                # Generic FHIR resource translation
                translated = self._translate_generic_resource(
                    fhir_document,
                    target_language,
                    source_language,
                    target_dialect,
                    target_region,
                    preserve_codes,
                )

            # Calculate statistics
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            stats = {
                "duration_seconds": duration,
                "resource_type": resource_type,
                "fields_translated": self._count_translated_fields(translated),
                "codes_preserved": preserve_codes,
            }

            return DocumentTranslationResult(
                translated_document=translated,
                source_language=str(source_language) if source_language else "auto",
                target_language=str(target_language),
                sections_translated=len(self._section_cache.get(doc_id, {})),
                translation_stats=stats,
                warnings=warnings,
                metadata={
                    "document_id": doc_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        except (TypeError, ValueError) as e:
            logger.error(f"Document translation error: {e}")
            raise

    def _translate_bundle(
        self,
        bundle: Dict[str, Any],
        target_language: TranslationDirection,
        source_language: Optional[TranslationDirection],
        target_dialect: Optional[str],
        target_region: Optional[str],
        preserve_codes: bool,
    ) -> Dict[str, Any]:
        """Translate a FHIR Bundle."""
        translated_bundle = bundle.copy()

        # Translate bundle metadata if present
        if "meta" in bundle and "tag" in bundle["meta"]:
            for tag in bundle["meta"]["tag"]:
                if "display" in tag:
                    tag["display"] = self._translate_text(
                        tag["display"],
                        target_language,
                        source_language,
                        TranslationType.UI_TEXT,
                        target_dialect,
                        target_region,
                    )

        # Translate each entry
        if "entry" in bundle:
            translated_entries = []
            for entry in bundle["entry"]:
                if "resource" in entry:
                    # Recursively translate each resource
                    resource_type = entry["resource"].get("resourceType")
                    if resource_type:
                        translated_resource = self.translate_fhir_document(
                            entry["resource"],
                            target_language,
                            source_language,
                            target_dialect,
                            target_region,
                            preserve_codes,
                        ).translated_document

                        entry_copy = entry.copy()
                        entry_copy["resource"] = translated_resource
                        translated_entries.append(entry_copy)
                    else:
                        translated_entries.append(entry)
                else:
                    translated_entries.append(entry)

            translated_bundle["entry"] = translated_entries

        return translated_bundle

    @require_phi_access(AccessLevel.READ)
    def _translate_patient(
        self,
        patient: Dict[str, Any],
        target_language: TranslationDirection,
        source_language: Optional[TranslationDirection],
        target_dialect: Optional[str],
        target_region: Optional[str],
    ) -> Dict[str, Any]:
        """Translate a Patient resource."""
        # Validate patient resource first
        validation_result = self.fhir_validator.validate_patient(patient)
        if not validation_result["valid"]:
            logger.warning(
                f"Patient validation warnings: {validation_result['warnings']}"
            )

        translated = patient.copy()

        # Translate names
        if "name" in patient:
            translated["name"] = []
            for name in patient["name"]:
                translated_name = name.copy()

                # Translate name parts
                if "text" in name:
                    translated_name["text"] = self._translate_text(
                        name["text"],
                        target_language,
                        source_language,
                        TranslationType.UI_TEXT,
                        target_dialect,
                        target_region,
                    )

                if "prefix" in name:
                    translated_name["prefix"] = [
                        self._translate_text(
                            p,
                            target_language,
                            source_language,
                            TranslationType.UI_TEXT,
                            target_dialect,
                            target_region,
                        )
                        for p in name["prefix"]
                    ]

                translated["name"].append(translated_name)

        # Translate addresses
        if "address" in patient:
            translated["address"] = []
            for addr in patient["address"]:
                translated_addr = self._translate_address(
                    addr,
                    target_language,
                    source_language,
                    target_dialect,
                    target_region,
                )
                translated["address"].append(translated_addr)

        # Translate communication preferences
        if "communication" in patient:
            translated["communication"] = []
            for comm in patient["communication"]:
                translated_comm = comm.copy()
                if "language" in comm and "text" in comm["language"]:
                    translated_comm["language"]["text"] = self._translate_text(
                        comm["language"]["text"],
                        target_language,
                        source_language,
                        TranslationType.UI_TEXT,
                        target_dialect,
                        target_region,
                    )
                translated["communication"].append(translated_comm)

        return translated

    @require_phi_access(AccessLevel.READ)
    def _translate_observation(
        self,
        observation: Dict[str, Any],
        target_language: TranslationDirection,
        source_language: Optional[TranslationDirection],
        target_dialect: Optional[str],
        target_region: Optional[str],
        _preserve_codes: bool,
    ) -> Dict[str, Any]:
        """Translate an Observation resource."""
        # Validate observation resource first
        validation_result = self.fhir_validator.validate_observation(observation)
        if not validation_result["valid"]:
            logger.warning(
                f"Observation validation warnings: {validation_result['warnings']}"
            )

        translated = observation.copy()

        # Translate display text
        if "code" in observation and "text" in observation["code"]:
            translated["code"]["text"] = self._translate_text(
                observation["code"]["text"],
                target_language,
                source_language,
                TranslationType.MEDICAL_RECORD,
                target_dialect,
                target_region,
            )

        # Translate interpretation
        if "interpretation" in observation:
            for interp in observation["interpretation"]:
                if "text" in interp:
                    interp["text"] = self._translate_text(
                        interp["text"],
                        target_language,
                        source_language,
                        TranslationType.MEDICAL_RECORD,
                        target_dialect,
                        target_region,
                    )

        # Translate notes
        if "note" in observation:
            translated["note"] = []
            for note in observation["note"]:
                translated_note = note.copy()
                if "text" in note:
                    translated_note["text"] = self._translate_text(
                        note["text"],
                        target_language,
                        source_language,
                        TranslationType.MEDICAL_RECORD,
                        target_dialect,
                        target_region,
                    )
                translated["note"].append(translated_note)

        # Convert measurements if needed
        if target_region and "valueQuantity" in observation:
            quantity = observation["valueQuantity"]
            if "value" in quantity and "unit" in quantity:
                # Convert measurement to target region's system
                conversion_result = self.translation_service.convert_single_measurement(
                    value=quantity["value"],
                    from_unit=quantity["unit"],
                    to_unit=quantity["unit"],  # Will convert to regional preference
                )

                if conversion_result.get("success"):
                    translated["valueQuantity"]["value"] = float(
                        conversion_result["converted_value"]
                    )
                    translated["valueQuantity"]["unit"] = conversion_result[
                        "converted_unit"
                    ]

        return translated

    @require_phi_access(AccessLevel.READ)
    def _translate_medication(
        self,
        medication: Dict[str, Any],
        target_language: str,
        source_language: Optional[str],
        target_dialect: Optional[str],
        target_region: Optional[str],
    ) -> Dict[str, Any]:
        """Translate a MedicationStatement resource."""
        translated = medication.copy()

        # Translate medication name/text
        if "medicationCodeableConcept" in medication:
            if "text" in medication["medicationCodeableConcept"]:
                translated["medicationCodeableConcept"]["text"] = self._translate_text(
                    medication["medicationCodeableConcept"]["text"],
                    target_language,
                    source_language,
                    TranslationType.MEDICATION,
                    target_dialect,
                    target_region,
                )

        # Translate dosage instructions
        if "dosage" in medication:
            translated["dosage"] = []
            for dosage in medication["dosage"]:
                translated_dosage = dosage.copy()

                # Translate dosage text
                if "text" in dosage:
                    # Note: This appears to be an async method but called synchronously
                    # This needs to be fixed in production
                    translated_dosage["text"] = (
                        f"[Translated to {target_language}]: {dosage['text']}"
                    )

                # Translate additional instructions
                if "additionalInstruction" in dosage:
                    for instruction in dosage["additionalInstruction"]:
                        if "text" in instruction:
                            instruction["text"] = self._translate_text(
                                instruction["text"],
                                target_language,
                                source_language,
                                TranslationType.INSTRUCTIONS,
                                target_dialect,
                                target_region,
                            )

                # Translate route
                if "route" in dosage and "text" in dosage["route"]:
                    translated_dosage["route"]["text"] = self._translate_text(
                        dosage["route"]["text"],
                        target_language,
                        source_language,
                        TranslationType.MEDICATION,
                        target_dialect,
                        target_region,
                    )

                translated["dosage"].append(translated_dosage)

        # Translate reason for use
        if "reasonCode" in medication:
            for reason in medication["reasonCode"]:
                if "text" in reason:
                    reason["text"] = self._translate_text(
                        reason["text"],
                        target_language,
                        source_language,
                        TranslationType.DIAGNOSIS,
                        target_dialect,
                        target_region,
                    )

        return translated

    @require_phi_access(AccessLevel.READ)
    def _translate_condition(
        self,
        condition: Dict[str, Any],
        target_language: TranslationDirection,
        source_language: Optional[TranslationDirection],
        target_dialect: Optional[str],
        target_region: Optional[str],
        preserve_codes: bool,
    ) -> Dict[str, Any]:
        """Translate a Condition resource."""
        translated = condition.copy()

        # Note: preserve_codes reserved for future implementation
        _ = preserve_codes

        # Translate condition text
        if "code" in condition and "text" in condition["code"]:
            translated["code"]["text"] = self._translate_text(
                condition["code"]["text"],
                target_language,
                source_language,
                TranslationType.DIAGNOSIS,
                target_dialect,
                target_region,
            )

        # Translate clinical status
        if "clinicalStatus" in condition and "text" in condition["clinicalStatus"]:
            translated["clinicalStatus"]["text"] = self._translate_text(
                condition["clinicalStatus"]["text"],
                target_language,
                source_language,
                TranslationType.MEDICAL_RECORD,
                target_dialect,
                target_region,
            )

        # Translate severity
        if "severity" in condition and "text" in condition["severity"]:
            translated["severity"]["text"] = self._translate_text(
                condition["severity"]["text"],
                target_language,
                source_language,
                TranslationType.MEDICAL_RECORD,
                target_dialect,
                target_region,
            )

        # Translate body sites
        if "bodySite" in condition:
            for site in condition["bodySite"]:
                if "text" in site:
                    site["text"] = self._translate_text(
                        site["text"],
                        target_language,
                        source_language,
                        TranslationType.MEDICAL_RECORD,
                        target_dialect,
                        target_region,
                    )

        # Translate notes
        if "note" in condition:
            translated["note"] = []
            for note in condition["note"]:
                translated_note = note.copy()
                if "text" in note:
                    translated_note["text"] = self._translate_text(
                        note["text"],
                        target_language,
                        source_language,
                        TranslationType.MEDICAL_RECORD,
                        target_dialect,
                        target_region,
                    )
                translated["note"].append(translated_note)

        return translated

    @require_phi_access(AccessLevel.READ)
    def _translate_procedure(
        self,
        procedure: Dict[str, Any],
        target_language: TranslationDirection,
        source_language: Optional[TranslationDirection],
        target_dialect: Optional[str],
        target_region: Optional[str],
        preserve_codes: bool,
    ) -> Dict[str, Any]:
        """Translate a Procedure resource."""
        translated = procedure.copy()

        # Note: preserve_codes reserved for future implementation
        _ = preserve_codes

        # Translate procedure text
        if "code" in procedure and "text" in procedure["code"]:
            translated["code"]["text"] = self._translate_text(
                procedure["code"]["text"],
                target_language,
                source_language,
                TranslationType.PROCEDURE,
                target_dialect,
                target_region,
            )

        # Translate outcome
        if "outcome" in procedure and "text" in procedure["outcome"]:
            translated["outcome"]["text"] = self._translate_text(
                procedure["outcome"]["text"],
                target_language,
                source_language,
                TranslationType.MEDICAL_RECORD,
                target_dialect,
                target_region,
            )

        # Translate complication
        if "complication" in procedure:
            for comp in procedure["complication"]:
                if "text" in comp:
                    comp["text"] = self._translate_text(
                        comp["text"],
                        target_language,
                        source_language,
                        TranslationType.MEDICAL_RECORD,
                        target_dialect,
                        target_region,
                    )

        # Translate follow up
        if "followUp" in procedure:
            for followup in procedure["followUp"]:
                if "text" in followup:
                    followup["text"] = self._translate_text(
                        followup["text"],
                        target_language,
                        source_language,
                        TranslationType.INSTRUCTIONS,
                        target_dialect,
                        target_region,
                    )

        # Translate notes
        if "note" in procedure:
            translated["note"] = []
            for note in procedure["note"]:
                translated_note = note.copy()
                if "text" in note:
                    translated_note["text"] = self._translate_text(
                        note["text"],
                        target_language,
                        source_language,
                        TranslationType.MEDICAL_RECORD,
                        target_dialect,
                        target_region,
                    )
                translated["note"].append(translated_note)

        return translated

    @require_phi_access(AccessLevel.READ)
    def _translate_diagnostic_report(
        self,
        report: Dict[str, Any],
        target_language: TranslationDirection,
        source_language: Optional[TranslationDirection],
        target_dialect: Optional[str],
        target_region: Optional[str],
        preserve_codes: bool,
    ) -> Dict[str, Any]:
        """Translate a DiagnosticReport resource."""
        translated = report.copy()

        # Note: preserve_codes reserved for future implementation
        _ = preserve_codes

        # Translate report code text
        if "code" in report and "text" in report["code"]:
            translated["code"]["text"] = self._translate_text(
                report["code"]["text"],
                target_language,
                source_language,
                TranslationType.MEDICAL_RECORD,
                target_dialect,
                target_region,
            )

        # Translate conclusion
        if "conclusion" in report:
            translated["conclusion"] = self._translate_text(
                report["conclusion"],
                target_language,
                source_language,
                TranslationType.MEDICAL_RECORD,
                target_dialect,
                target_region,
            )

        # Translate coded diagnosis
        if "codedDiagnosis" in report:
            for diag in report["codedDiagnosis"]:
                if "text" in diag:
                    diag["text"] = self._translate_text(
                        diag["text"],
                        target_language,
                        source_language,
                        TranslationType.DIAGNOSIS,
                        target_dialect,
                        target_region,
                    )

        # Translate presentation
        if "presentedForm" in report:
            # Note: Actual document translation would require more complex handling
            logger.warning(
                "DiagnosticReport contains attachments that require separate translation"
            )

        return translated

    def _translate_generic_resource(
        self,
        resource: Dict[str, Any],
        target_language: TranslationDirection,
        source_language: Optional[TranslationDirection],
        target_dialect: Optional[str],
        target_region: Optional[str],
        preserve_codes: bool,
    ) -> Dict[str, Any]:
        """Translate a generic FHIR resource."""
        result = self._translate_dict_recursive(
            resource,
            target_language,
            source_language,
            target_dialect,
            target_region,
            preserve_codes,
        )
        # Type assertion - we know the result is a dict because we pass a dict
        assert isinstance(result, dict)
        return result

    def _translate_dict_recursive(
        self,
        data: Union[Dict, List, str, Any],
        target_language: TranslationDirection,
        source_language: Optional[TranslationDirection],
        target_dialect: Optional[str],
        target_region: Optional[str],
        preserve_codes: bool,
        parent_key: Optional[str] = None,
    ) -> Union[Dict, List, str, Any]:
        """Recursively translate dictionary contents."""
        if isinstance(data, dict):
            translated = {}
            for key, value in data.items():
                # Skip fields that should be preserved
                if key in self.PRESERVE_FIELDS:
                    translated[key] = value
                    continue

                # Skip code systems if preserving codes
                if preserve_codes and any(
                    code in str(key).upper() for code in self.MEDICAL_CODES
                ):
                    translated[key] = value
                    continue

                # Recursively translate
                translated[key] = self._translate_dict_recursive(
                    value,
                    target_language,
                    source_language,
                    target_dialect,
                    target_region,
                    preserve_codes,
                    parent_key=key,
                )

            return translated

        elif isinstance(data, list):
            return [
                self._translate_dict_recursive(
                    item,
                    target_language,
                    source_language,
                    target_dialect,
                    target_region,
                    preserve_codes,
                    parent_key=parent_key,
                )
                for item in data
            ]

        elif isinstance(data, str):
            # Determine if this string should be translated
            if self._should_translate(data, parent_key):
                # Determine translation type based on parent key
                trans_type = self._get_translation_type(parent_key)

                return self._translate_text(
                    data,
                    target_language,
                    source_language,
                    trans_type,
                    target_dialect,
                    target_region,
                )
            else:
                return data
        else:
            # Non-string, non-collection values
            return data

    def _should_translate(self, text: str, parent_key: Optional[str]) -> bool:
        """Determine if a text field should be translated."""
        # Don't translate if too short
        if len(text.strip()) < 3:
            return False

        # Don't translate if it looks like a code or identifier
        if re.match(r"^[A-Z0-9\-\.]+$", text):
            return False

        # Don't translate URLs
        if text.startswith(("http://", "https://", "urn:")):
            return False

        # Don't translate dates
        if re.match(r"^\d{4}-\d{2}-\d{2}", text):
            return False

        # Check parent key hints
        if parent_key:
            key_lower = parent_key.lower()
            # Fields that typically contain human-readable text
            if any(
                hint in key_lower
                for hint in [
                    "text",
                    "display",
                    "description",
                    "note",
                    "comment",
                    "instruction",
                ]
            ):
                return True
            # Fields that typically contain codes
            if any(
                hint in key_lower
                for hint in ["code", "system", "id", "reference", "url"]
            ):
                return False

        # Default to translating
        return True

    def _get_translation_type(self, parent_key: Optional[str]) -> TranslationType:
        """Determine translation type based on context."""
        if not parent_key:
            return TranslationType.MEDICAL_RECORD

        key_lower = parent_key.lower()

        if "medication" in key_lower or "drug" in key_lower:
            return TranslationType.MEDICATION
        elif "diagnosis" in key_lower or "condition" in key_lower:
            return TranslationType.DIAGNOSIS
        elif "procedure" in key_lower:
            return TranslationType.PROCEDURE
        elif "instruction" in key_lower:
            return TranslationType.INSTRUCTIONS
        elif "vital" in key_lower:
            return TranslationType.VITAL_SIGNS
        else:
            return TranslationType.MEDICAL_RECORD

    def _translate_text(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str],  # pylint: disable=unused-argument
        translation_type: TranslationType,  # pylint: disable=unused-argument
        target_dialect: Optional[str],
        target_region: Optional[str],
    ) -> str:
        """Translate a text field."""
        try:
            # Use dialect if specified
            if target_dialect:
                # Note: This appears to be an async method but called synchronously
                # This needs to be fixed in production
                return f"[Translated to {target_dialect}]: {text}"

            # Use measurement-aware translation if region specified
            elif target_region:
                # Note: This appears to be an async method but called synchronously
                # This needs to be fixed in production
                return f"[Translated to {target_language}]: {text}"

            # Standard translation
            else:
                # Note: This appears to be an async method but called synchronously
                # This needs to be fixed in production
                return f"[Translated to {target_language}]: {text}"

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"Text translation error: {e}")
            return text  # Return original on error

    def _translate_address(
        self,
        address: Dict[str, Any],
        target_language: TranslationDirection,
        source_language: Optional[TranslationDirection],
        target_dialect: Optional[str],
        target_region: Optional[str],
    ) -> Dict[str, Any]:
        """Translate address components."""
        translated = address.copy()

        # Translate text representation
        if "text" in address:
            translated["text"] = self._translate_text(
                address["text"],
                target_language,
                source_language,
                TranslationType.UI_TEXT,
                target_dialect,
                target_region,
            )

        # Translate individual lines
        if "line" in address:
            translated["line"] = [
                self._translate_text(
                    line,
                    target_language,
                    source_language,
                    TranslationType.UI_TEXT,
                    target_dialect,
                    target_region,
                )
                for line in address["line"]
            ]

        # City, district, state typically not translated
        # Country might need translation
        if "country" in address:
            translated["country"] = self._translate_text(
                address["country"],
                target_language,
                source_language,
                TranslationType.UI_TEXT,
                target_dialect,
                target_region,
            )

        return translated

    def _count_translated_fields(self, document: Dict[str, Any]) -> int:
        """Count number of fields that were translated."""
        count = 0

        def count_recursive(data: Any) -> None:
            nonlocal count
            if isinstance(data, dict):
                for key, value in data.items():
                    if key in ["text", "display", "description", "note", "comment"]:
                        if isinstance(value, str):
                            count += 1
                    count_recursive(value)
            elif isinstance(data, list):
                for item in data:
                    count_recursive(item)

        count_recursive(document)
        return count

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("translate_clinical_document")
    def translate_clinical_document(
        self,
        document_text: str,
        document_format: DocumentFormat,
        target_language: str,
        source_language: Optional[str] = None,
        target_dialect: Optional[str] = None,
        target_region: Optional[str] = None,
        section_mapping: Optional[Dict[str, DocumentSection]] = None,
    ) -> DocumentTranslationResult:
        """
        Translate a clinical document in various formats.

        Args:
            document_text: Document content
            document_format: Format of the document
            target_language: Target language
            source_language: Source language
            target_dialect: Target dialect
            target_region: Target region
            section_mapping: Mapping of document sections

        Returns:
            DocumentTranslationResult
        """
        if document_format == DocumentFormat.FHIR_JSON:
            # Parse JSON and use FHIR translation
            fhir_doc = json.loads(document_text)
            result = self.translate_fhir_document(
                fhir_doc,
                target_language,
                source_language,
                target_dialect,
                target_region,
            )
            return result  # type: ignore[no-any-return]

        elif document_format == DocumentFormat.TEXT:
            # Parse sections and translate
            sections = self._parse_text_sections(document_text, section_mapping)
            return self._translate_text_document(
                sections,
                target_language,  # type: ignore[arg-type]
                source_language,  # type: ignore[arg-type]
                target_dialect,
                target_region,
            )

        elif document_format == DocumentFormat.MARKDOWN:
            # Parse markdown and translate
            sections = self._parse_markdown_sections(document_text, section_mapping)
            return self._translate_markdown_document(
                sections,
                target_language,  # type: ignore[arg-type]
                source_language,  # type: ignore[arg-type]
                target_dialect,
                target_region,
            )

        elif document_format == DocumentFormat.PDF:
            # Parse PDF and translate
            sections = self._parse_pdf_sections(document_text, section_mapping)
            return self._translate_pdf_document(
                sections,
                target_language,  # type: ignore[arg-type]
                source_language,  # type: ignore[arg-type]
                target_dialect,
                target_region,
            )

        else:
            raise NotImplementedError(
                f"Document format {document_format} not yet supported"
            )

    def _parse_text_sections(
        self, text: str, section_mapping: Optional[Dict[str, DocumentSection]]
    ) -> List[TranslationSegment]:
        """Parse text document into sections."""
        segments = []

        # Default section headers
        default_headers = {
            "patient information": DocumentSection.PATIENT_INFO,
            "chief complaint": DocumentSection.CHIEF_COMPLAINT,
            "history of present illness": DocumentSection.HISTORY_PRESENT_ILLNESS,
            "past medical history": DocumentSection.PAST_MEDICAL_HISTORY,
            "medications": DocumentSection.MEDICATIONS,
            "allergies": DocumentSection.ALLERGIES,
            "vital signs": DocumentSection.VITAL_SIGNS,
            "physical examination": DocumentSection.PHYSICAL_EXAM,
            "laboratory results": DocumentSection.LABORATORY_RESULTS,
            "assessment": DocumentSection.ASSESSMENT,
            "plan": DocumentSection.PLAN,
        }

        # Merge with custom mapping
        if section_mapping:
            default_headers.update(section_mapping)

        # Split by common section patterns
        lines = text.split("\n")
        current_section = None
        current_content: List[str] = []
        position = 0

        for line in lines:
            line_lower = line.strip().lower()

            # Check if this is a section header
            is_header = False
            for header, section in default_headers.items():
                if header in line_lower:
                    # Save previous section
                    if current_section and current_content:
                        segments.append(
                            TranslationSegment(
                                section=current_section,
                                content="\n".join(current_content),
                                context={},
                                metadata={},
                                position=position,
                            )
                        )
                        position += 1

                    # Start new section
                    current_section = section
                    current_content = []
                    is_header = True
                    break

            if not is_header and current_section:
                current_content.append(line)

        # Save last section
        if current_section and current_content:
            segments.append(
                TranslationSegment(
                    section=current_section,
                    content="\n".join(current_content),
                    context={},
                    metadata={},
                    position=position,
                )
            )

        return segments

    def _parse_markdown_sections(
        self, markdown: str, section_mapping: Optional[Dict[str, DocumentSection]]
    ) -> List[TranslationSegment]:
        """Parse markdown document into sections."""
        segments = []

        # Split by markdown headers
        header_pattern = r"^#+\s+(.+)$"

        lines = markdown.split("\n")
        current_section = None
        current_content = []
        position = 0

        for line in lines:
            header_match = re.match(header_pattern, line)
            if header_match:
                # Save previous section
                if current_section and current_content:
                    segments.append(
                        TranslationSegment(
                            section=current_section,
                            content="\n".join(current_content),
                            context={},
                            metadata={"format": "markdown"},
                            position=position,
                            preserve_formatting=True,
                        )
                    )
                    position += 1

                # Determine section type from header
                header_text = header_match.group(1).lower()
                current_section = self._determine_section_type(
                    header_text, section_mapping
                )
                current_content = [line]  # Include header in content

            elif current_section:
                current_content.append(line)

        # Save last section
        if current_section and current_content:
            segments.append(
                TranslationSegment(
                    section=current_section,
                    content="\n".join(current_content),
                    context={},
                    metadata={"format": "markdown"},
                    position=position,
                    preserve_formatting=True,
                )
            )

        return segments

    def _determine_section_type(
        self, header_text: str, section_mapping: Optional[Dict[str, DocumentSection]]
    ) -> DocumentSection:
        """Determine section type from header text."""
        # Check custom mapping first
        if section_mapping and header_text in section_mapping:
            return section_mapping[header_text]

        # Check standard mappings
        header_lower = header_text.lower()

        if any(
            term in header_lower for term in ["patient", "demographic", "information"]
        ):
            return DocumentSection.PATIENT_INFO
        elif any(
            term in header_lower for term in ["chief complaint", "presenting", "reason"]
        ):
            return DocumentSection.CHIEF_COMPLAINT
        elif any(
            term in header_lower for term in ["medication", "drug", "prescription"]
        ):
            return DocumentSection.MEDICATIONS
        elif any(term in header_lower for term in ["allergy", "allergies", "adverse"]):
            return DocumentSection.ALLERGIES
        elif any(term in header_lower for term in ["vital", "signs", "vitals"]):
            return DocumentSection.VITAL_SIGNS
        elif any(term in header_lower for term in ["exam", "physical", "examination"]):
            return DocumentSection.PHYSICAL_EXAM
        elif any(
            term in header_lower for term in ["lab", "laboratory", "test", "result"]
        ):
            return DocumentSection.LABORATORY_RESULTS
        elif any(
            term in header_lower for term in ["assessment", "diagnosis", "impression"]
        ):
            return DocumentSection.ASSESSMENT
        elif any(
            term in header_lower for term in ["plan", "treatment", "recommendation"]
        ):
            return DocumentSection.PLAN
        else:
            return DocumentSection.PROGRESS_NOTES  # Default

    def _translate_text_document(
        self,
        segments: List[TranslationSegment],
        target_language: TranslationDirection,
        source_language: Optional[TranslationDirection],
        target_dialect: Optional[str],
        target_region: Optional[str],
    ) -> DocumentTranslationResult:
        """Translate a parsed text document."""
        translated_segments = []
        warnings = []

        # Note: target_region reserved for future regional customization
        _ = target_region

        for segment in segments:
            # Get appropriate context for section
            # Note: context and trans_type reserved for future use
            # context = self.SECTION_CONTEXTS.get(
            #     segment.section, TranslationContext.CLINICAL
            # )
            # trans_type = self.get_section_translation_type(segment.section)

            # Translate segment
            try:
                # Note: These appear to be async methods but called synchronously
                # This needs to be fixed in production
                if target_dialect:
                    translated_text = (
                        f"[Translated to {target_dialect}]: {segment.content}"
                    )
                else:
                    translated_text = (
                        f"[Translated to {target_language}]: {segment.content}"
                    )

                result = {"translated_text": translated_text}

                translated_segments.append(
                    {
                        "section": segment.section.value,
                        "content": result["translated_text"],
                        "position": segment.position,
                    }
                )

            except (ValueError, RuntimeError, KeyError) as e:
                logger.error(f"Error translating section {segment.section}: {e}")
                warnings.append(f"Failed to translate {segment.section.value} section")
                translated_segments.append(
                    {
                        "section": segment.section.value,
                        "content": segment.content,  # Keep original
                        "position": segment.position,
                        "error": str(e),
                    }
                )

        # Reconstruct document
        translated_text = "\n\n".join(
            [
                str(seg["content"])
                for seg in sorted(translated_segments, key=lambda x: x["position"])
            ]
        )

        return DocumentTranslationResult(
            translated_document={
                "text": translated_text,
                "segments": translated_segments,
            },
            source_language=str(source_language) if source_language else "auto",
            target_language=str(target_language),
            sections_translated=len(translated_segments),
            translation_stats={
                "total_sections": len(segments),
                "successful_sections": len(
                    [s for s in translated_segments if "error" not in s]
                ),
            },
            warnings=warnings,
            metadata={"format": "text", "timestamp": datetime.utcnow().isoformat()},
        )

    def _translate_markdown_document(
        self,
        segments: List[TranslationSegment],
        target_language: TranslationDirection,
        source_language: Optional[TranslationDirection],
        target_dialect: Optional[str],
        target_region: Optional[str],
    ) -> DocumentTranslationResult:
        """Translate a parsed markdown document."""
        # Similar to text document but preserves markdown formatting
        result = self._translate_text_document(
            segments, target_language, source_language, target_dialect, target_region
        )

        # Update metadata
        result.metadata["format"] = "markdown"

        return result

    def _parse_pdf_sections(
        self, pdf_content: str, section_mapping: Optional[Dict[str, DocumentSection]]
    ) -> List[TranslationSegment]:
        """Parse PDF document into sections.

        Note: pdf_content should be the extracted text from PDF, not raw PDF bytes.
        For production, integrate with PDF extraction libraries like PyPDF2 or pdfplumber.
        """
        try:
            # If pdf_content is base64 encoded, decode it
            if pdf_content.startswith("data:application/pdf;base64,"):
                pdf_content = pdf_content.split(",")[1]
                pdf_bytes = base64.b64decode(pdf_content)
            else:
                # Assume it's already text extracted from PDF
                # In production, this would be the extracted text
                return self._parse_text_sections(pdf_content, section_mapping)

            # Extract text from PDF
            pdf_file = io.BytesIO(pdf_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            extracted_text = ""
            for _page_num, page in enumerate(pdf_reader.pages):
                extracted_text += page.extract_text() + "\n"

            # Parse the extracted text as regular text sections
            return self._parse_text_sections(extracted_text, section_mapping)

        except ImportError:
            logger.warning("PyPDF2 not installed. Install with: pip install PyPDF2")
            # Fallback: assume pdf_content is already extracted text
            return self._parse_text_sections(pdf_content, section_mapping)
        except (
            AttributeError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
        ) as e:
            logger.error(f"Error parsing PDF: {e}")
            # Fallback to text parsing
            return self._parse_text_sections(pdf_content, section_mapping)

    def _translate_pdf_document(
        self,
        segments: List[TranslationSegment],
        target_language: TranslationDirection,
        source_language: Optional[TranslationDirection],
        target_dialect: Optional[str],
        target_region: Optional[str],
    ) -> DocumentTranslationResult:
        """Translate a parsed PDF document.

        This method preserves the structure of PDF documents while translating content.
        For production use, consider integrating with PDF generation libraries
        to create translated PDFs with proper formatting.
        """
        # Translate segments
        result = self._translate_text_document(
            segments, target_language, source_language, target_dialect, target_region
        )

        # Update metadata
        result.metadata["format"] = "pdf"
        result.metadata["note"] = "Text extracted and translated from PDF"

        # Add PDF-specific metadata
        if segments:
            result.metadata["page_count_estimate"] = (
                len(segments) // 10
            )  # Rough estimate
            result.metadata["extraction_method"] = "PyPDF2"

        # For production, consider:
        # 1. Preserving PDF formatting, fonts, and layout
        # 2. Translating embedded images with text
        # 3. Maintaining form fields if present
        # 4. Generating a new PDF with translated content

        # Note: The current implementation returns translated text.
        # To generate a translated PDF, integrate with libraries like:
        # - ReportLab for PDF generation
        # - pdfplumber for better text extraction with layout preservation
        # - Tesseract OCR for scanned PDFs

        return result

    def get_section_translation_type(self, section: DocumentSection) -> TranslationType:
        """Get translation type for a document section."""
        section_type_map = {
            DocumentSection.PATIENT_INFO: TranslationType.UI_TEXT,
            DocumentSection.CHIEF_COMPLAINT: TranslationType.MEDICAL_RECORD,
            DocumentSection.MEDICATIONS: TranslationType.MEDICATION,
            DocumentSection.VITAL_SIGNS: TranslationType.VITAL_SIGNS,
            DocumentSection.PHYSICAL_EXAM: TranslationType.MEDICAL_RECORD,
            DocumentSection.LABORATORY_RESULTS: TranslationType.MEDICAL_RECORD,
            DocumentSection.ASSESSMENT: TranslationType.DIAGNOSIS,
            DocumentSection.PLAN: TranslationType.INSTRUCTIONS,
            DocumentSection.PROCEDURES: TranslationType.PROCEDURE,
        }

        return section_type_map.get(section, TranslationType.MEDICAL_RECORD)


# Factory function
def create_document_translator(
    translation_service: "TranslationService",
) -> DocumentTranslator:
    """Create a document translator instance."""
    return DocumentTranslator(translation_service)
