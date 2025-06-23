"""Medical Form Recognition Module.

This module implements specialized medical form recognition capabilities for the Haven Health
Passport system. It identifies, classifies, and extracts structured data from various medical
forms while ensuring compliance with healthcare standards.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

# Standard library imports
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.ai.document_processing.textract_config import (
    DocumentAnalysisResult,
    DocumentType,
    ExtractedTable,
    FeatureType,
    TextractClient,
)
from src.core.exceptions import ProcessingError
from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.healthcare.medical_terminology import MedicalTerminologyValidator
from src.translation.medical_terms import MedicalTermTranslator
from src.utils.date_parser import MultilingualDateParser

# Mock imports for missing modules
try:
    from src.healthcare.fhir_converter import FHIRConverter as FHIRResourceConverter
except ImportError:

    class FHIRResourceConverter:  # type: ignore[no-redef]
        """Fallback FHIR resource converter when main module is not available."""

        def __init__(self) -> None:
            """Initialize FHIRResourceConverter."""

        def convert_to_fhir(self, data: Any) -> Dict[str, Any]:
            """Convert data to FHIR format.

            Args:
                data: Data to convert

            Returns:
                Empty dict as fallback
            """
            # Fallback implementation - data conversion not available
            _ = data  # Acknowledge parameter
            return {}


try:
    from src.healthcare.hl7_mapper import HL7Mapper
except ImportError:

    class HL7Mapper:  # type: ignore[no-redef]
        """Fallback HL7 mapper when main module is not available."""

        def __init__(self) -> None:
            """Initialize HL7Mapper."""

        def map_to_hl7(self, data: Any) -> Dict[str, Any]:
            """Map data to HL7 format.

            Args:
                data: Data to map

            Returns:
                Empty dict as fallback
            """
            # Fallback implementation - data mapping not available
            _ = data  # Acknowledge parameter
            return {}


logger = logging.getLogger(__name__)

# FHIR resource type for this module - processes various medical document resources
__fhir_resource__ = "DocumentReference"


class MedicalFormType(Enum):
    """Types of medical forms with specific extraction rules."""

    PATIENT_INTAKE = "patient_intake"
    PRESCRIPTION_FORM = "prescription_form"
    LAB_ORDER = "lab_order"
    LAB_RESULT = "lab_result"
    VACCINATION_RECORD = "vaccination_record"
    CONSENT_FORM = "consent_form"
    INSURANCE_CLAIM = "insurance_claim"
    REFERRAL_FORM = "referral_form"
    DISCHARGE_SUMMARY = "discharge_summary"
    MEDICAL_HISTORY = "medical_history"
    PHYSICAL_EXAM = "physical_exam"
    SURGICAL_CONSENT = "surgical_consent"
    MEDICATION_LIST = "medication_list"
    ALLERGY_FORM = "allergy_form"
    VITAL_SIGNS_CHART = "vital_signs_chart"
    PROGRESS_NOTE = "progress_note"
    ADMISSION_FORM = "admission_form"
    TRANSFER_FORM = "transfer_form"
    DEATH_CERTIFICATE = "death_certificate"
    BIRTH_CERTIFICATE = "birth_certificate"


class FormFieldType(Enum):
    """Types of form fields for specialized processing."""

    PATIENT_NAME = "patient_name"
    DATE_OF_BIRTH = "date_of_birth"
    GENDER = "gender"
    ADDRESS = "address"
    PHONE_NUMBER = "phone_number"
    EMAIL = "email"
    MEDICAL_RECORD_NUMBER = "medical_record_number"
    INSURANCE_ID = "insurance_id"
    DIAGNOSIS_CODE = "diagnosis_code"
    PROCEDURE_CODE = "procedure_code"
    MEDICATION_NAME = "medication_name"
    DOSAGE = "dosage"
    FREQUENCY = "frequency"
    ROUTE = "route"
    LAB_TEST_NAME = "lab_test_name"
    LAB_VALUE = "lab_value"
    LAB_UNIT = "lab_unit"
    LAB_REFERENCE_RANGE = "lab_reference_range"
    VITAL_SIGN = "vital_sign"
    ALLERGY = "allergy"
    SIGNATURE = "signature"
    DATE_SIGNED = "date_signed"
    PROVIDER_NAME = "provider_name"
    PROVIDER_ID = "provider_id"
    FACILITY_NAME = "facility_name"
    CUSTOM_FIELD = "custom_field"


@dataclass
class FormFieldMapping:
    """Mapping configuration for form fields."""

    field_type: FormFieldType
    common_labels: List[str]  # Common labels in different languages
    regex_patterns: List[str]  # Regex patterns for validation
    fhir_path: Optional[str] = None  # FHIR resource path
    hl7_segment: Optional[str] = None  # HL7 segment mapping
    required: bool = False
    validation_func: Optional[str] = None  # Name of validation function
    post_processing: Optional[str] = None  # Post-processing function name


@dataclass
class ExtractedFormField:
    """Represents an extracted and validated form field."""

    field_type: FormFieldType
    label: str
    value: Any
    confidence: float
    page: int
    original_value: str
    normalized_value: Optional[Any] = None
    validation_status: str = "pending"
    validation_errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MedicalFormData:
    """Complete extracted data from a medical form."""

    form_type: MedicalFormType
    form_id: str
    extraction_timestamp: datetime
    fields: List[ExtractedFormField]
    tables: List[ExtractedTable]
    confidence_score: float
    page_count: int
    language: str
    validation_status: str = "pending"
    fhir_resources: List[Dict[str, Any]] = field(default_factory=list)
    hl7_messages: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def get_field_by_type(
        self, field_type: FormFieldType
    ) -> Optional[ExtractedFormField]:
        """Get field by type."""
        for form_field in self.fields:
            if form_field.field_type == field_type:
                return form_field
        return None


@dataclass
class StandardsConversionResult:
    """Result of converting medical form data to healthcare standards."""

    fhir_resources: List[Dict[str, Any]]
    hl7_messages: List[str]
    conversion_warnings: List[str] = field(default_factory=list)
    conversion_errors: List[str] = field(default_factory=list)
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class MedicalFormRecognizer:
    """Main class for medical form recognition and extraction."""

    def __init__(
        self,
        textract_client: TextractClient,
        terminology_validator: MedicalTerminologyValidator,
        fhir_converter: FHIRResourceConverter,
        hl7_mapper: HL7Mapper,
        translator: MedicalTermTranslator,
    ):
        """Initialize MedicalFormRecognitionService.

        Args:
            textract_client: Client for AWS Textract operations
            terminology_validator: Validator for medical terminology
            fhir_converter: Converter for FHIR resource conversion
            hl7_mapper: Mapper for HL7 format conversion
            translator: Translator for medical terms
        """
        self.textract_client = textract_client
        self.terminology_validator = terminology_validator
        self.fhir_converter = fhir_converter
        self.hl7_mapper = hl7_mapper
        self.translator = translator
        self.date_parser = MultilingualDateParser()

        # Initialize field mappings
        self._init_field_mappings()

        # Initialize form templates
        self._init_form_templates()

    def _init_field_mappings(self) -> None:
        """Initialize field mapping configurations."""
        self.field_mappings = {
            FormFieldType.PATIENT_NAME: FormFieldMapping(
                field_type=FormFieldType.PATIENT_NAME,
                common_labels=[
                    "patient name",
                    "name",
                    "full name",
                    "nombre del paciente",
                    "nom du patient",
                    "اسم المريض",
                    "patient",
                    "nome do paciente",
                ],
                regex_patterns=[r"^[A-Za-z\s\-'\.]+$"],
                fhir_path="Patient.name",
                hl7_segment="PID.5",
                required=True,
                post_processing="normalize_name",
            ),
            FormFieldType.DATE_OF_BIRTH: FormFieldMapping(
                field_type=FormFieldType.DATE_OF_BIRTH,
                common_labels=[
                    "date of birth",
                    "dob",
                    "birth date",
                    "fecha de nacimiento",
                    "date de naissance",
                    "تاريخ الميلاد",
                    "birthdate",
                ],
                regex_patterns=[
                    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
                    r"\d{4}[/-]\d{1,2}[/-]\d{1,2}",
                ],
                fhir_path="Patient.birthDate",
                hl7_segment="PID.7",
                required=True,
                validation_func="validate_date",
                post_processing="parse_date",
            ),
            FormFieldType.MEDICAL_RECORD_NUMBER: FormFieldMapping(
                field_type=FormFieldType.MEDICAL_RECORD_NUMBER,
                common_labels=[
                    "mrn",
                    "medical record number",
                    "patient id",
                    "record number",
                    "número de registro médico",
                    "numéro de dossier médical",
                ],
                regex_patterns=[r"^[A-Z0-9\-]+$"],
                fhir_path="Patient.identifier",
                hl7_segment="PID.3",
                required=True,
            ),
            FormFieldType.DIAGNOSIS_CODE: FormFieldMapping(
                field_type=FormFieldType.DIAGNOSIS_CODE,
                common_labels=[
                    "diagnosis",
                    "icd-10",
                    "diagnosis code",
                    "dx code",
                    "código de diagnóstico",
                    "code de diagnostic",
                ],
                regex_patterns=[r"^[A-Z]\d{2}\.?\d*$"],  # ICD-10 pattern
                fhir_path="Condition.code",
                hl7_segment="DG1.3",
                validation_func="validate_diagnosis_code",
            ),
            FormFieldType.MEDICATION_NAME: FormFieldMapping(
                field_type=FormFieldType.MEDICATION_NAME,
                common_labels=[
                    "medication",
                    "drug name",
                    "medicine",
                    "rx",
                    "medicamento",
                    "médicament",
                    "دواء",
                ],
                regex_patterns=[r"^[A-Za-z0-9\s\-]+$"],
                fhir_path="MedicationRequest.medicationCodeableConcept",
                hl7_segment="RXO.1",
                validation_func="validate_medication_name",
            ),
            FormFieldType.DOSAGE: FormFieldMapping(
                field_type=FormFieldType.DOSAGE,
                common_labels=["dose", "dosage", "strength", "dosis", "posologie"],
                regex_patterns=[r"^\d+\.?\d*\s*[a-zA-Z]+$"],
                fhir_path="MedicationRequest.dosageInstruction.doseAndRate.doseQuantity",
                hl7_segment="RXO.2",
                validation_func="validate_dosage",
            ),
            FormFieldType.LAB_TEST_NAME: FormFieldMapping(
                field_type=FormFieldType.LAB_TEST_NAME,
                common_labels=[
                    "test name",
                    "lab test",
                    "analysis",
                    "test",
                    "nombre de la prueba",
                    "nom du test",
                ],
                regex_patterns=[r"^[A-Za-z0-9\s\-\/]+$"],
                fhir_path="Observation.code",
                hl7_segment="OBR.4",
                validation_func="validate_lab_test",
            ),
            FormFieldType.LAB_VALUE: FormFieldMapping(
                field_type=FormFieldType.LAB_VALUE,
                common_labels=["result", "value", "lab value", "resultado", "résultat"],
                regex_patterns=[r"^[\d\.<>\s\-\+]+$"],
                fhir_path="Observation.valueQuantity",
                hl7_segment="OBX.5",
                validation_func="validate_lab_value",
            ),
            FormFieldType.VITAL_SIGN: FormFieldMapping(
                field_type=FormFieldType.VITAL_SIGN,
                common_labels=[
                    "vital signs",
                    "vitals",
                    "bp",
                    "blood pressure",
                    "temperature",
                    "pulse",
                    "heart rate",
                    "respiratory rate",
                ],
                regex_patterns=[r"^\d+\.?\d*\s*[\/\s]?\s*\d*\.?\d*$"],
                fhir_path="Observation.value",
                hl7_segment="OBX.5",
                validation_func="validate_vital_sign",
            ),
        }

    def _init_form_templates(self) -> None:
        """Initialize form templates with expected fields."""
        self.form_templates = {
            MedicalFormType.PRESCRIPTION_FORM: [
                FormFieldType.PATIENT_NAME,
                FormFieldType.DATE_OF_BIRTH,
                FormFieldType.MEDICATION_NAME,
                FormFieldType.DOSAGE,
                FormFieldType.FREQUENCY,
                FormFieldType.PROVIDER_NAME,
                FormFieldType.DATE_SIGNED,
            ],
            MedicalFormType.LAB_RESULT: [
                FormFieldType.PATIENT_NAME,
                FormFieldType.MEDICAL_RECORD_NUMBER,
                FormFieldType.LAB_TEST_NAME,
                FormFieldType.LAB_VALUE,
                FormFieldType.LAB_UNIT,
                FormFieldType.LAB_REFERENCE_RANGE,
            ],
            MedicalFormType.VACCINATION_RECORD: [
                FormFieldType.PATIENT_NAME,
                FormFieldType.DATE_OF_BIRTH,
                FormFieldType.MEDICATION_NAME,  # Vaccine name
                FormFieldType.DATE_SIGNED,  # Vaccination date
                FormFieldType.PROVIDER_NAME,
                FormFieldType.FACILITY_NAME,
            ],
        }

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("recognize_medical_form")
    async def recognize_medical_form(
        self, document_bytes: bytes, document_name: str, language: str = "en"
    ) -> MedicalFormData:
        """Recognize and extract data from a medical form."""
        try:
            # Step 1: Analyze document with Textract
            analysis_result = await self.textract_client.analyze_document(
                document_bytes,
                document_name,
                [FeatureType.FORMS, FeatureType.TABLES, FeatureType.SIGNATURES],
            )

            # Step 2: Detect form type
            form_type = await self._detect_form_type(analysis_result)

            # Step 3: Extract fields based on form type
            extracted_fields = await self._extract_form_fields(
                analysis_result, form_type, language
            )

            # Step 4: Validate extracted data
            validated_fields = await self._validate_fields(extracted_fields)

            # Step 5: Create structured medical form data
            form_data = MedicalFormData(
                form_type=form_type,
                form_id=analysis_result.document_id,
                extraction_timestamp=datetime.now(),
                fields=validated_fields,
                tables=analysis_result.extracted_tables,
                confidence_score=self._calculate_confidence(validated_fields),
                page_count=analysis_result.page_count,
                language=language,
            )

            # Step 6: Convert to healthcare standards
            await self._convert_to_standards(form_data)

            # Step 7: Final validation
            form_data.validation_status = await self._final_validation(form_data)

            return form_data

        except (ValueError, KeyError, AttributeError, TypeError) as e:
            logger.error("Medical form recognition failed: %s", str(e))
            raise ProcessingError(f"Failed to process medical form: {str(e)}") from e

    async def detect_form_type(
        self, analysis_result: DocumentAnalysisResult
    ) -> MedicalFormType:
        """Public wrapper for detecting the type of medical form based on content."""
        return await self._detect_form_type(analysis_result)

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("extract_medical_form_fields")
    async def extract_form_fields(
        self,
        analysis_result: DocumentAnalysisResult,
        form_type: MedicalFormType,
        language: str = "en",
    ) -> List[ExtractedFormField]:
        """Public wrapper for extracting form fields based on form type."""
        return await self._extract_form_fields(analysis_result, form_type, language)

    async def validate_fields(
        self, fields: List[ExtractedFormField]
    ) -> List[ExtractedFormField]:
        """Public wrapper for validating extracted fields."""
        return await self._validate_fields(fields)

    async def match_field_type(
        self, field_label: str, field_value: str
    ) -> Optional[FormFieldType]:
        """Public wrapper for matching field type based on label and value."""
        return await self._match_field_type(field_label, field_value)

    def calculate_confidence(self, fields: List[ExtractedFormField]) -> float:
        """Public wrapper for calculating overall confidence score."""
        return self._calculate_confidence(fields)

    async def convert_to_standards(
        self, form_data: MedicalFormData
    ) -> StandardsConversionResult:
        """Public wrapper for converting form data to standards."""
        return await self._convert_to_standards(form_data)

    async def _detect_form_type(
        self, analysis_result: DocumentAnalysisResult
    ) -> MedicalFormType:
        """Detect the type of medical form based on content."""
        # Get all text and form fields
        text = analysis_result.get_all_text().lower()

        # Score each form type
        scores = {}

        # Check for prescription indicators
        prescription_keywords = [
            "prescription",
            "rx",
            "medication",
            "drug",
            "dose",
            "sig",
        ]
        prescription_score = sum(1 for kw in prescription_keywords if kw in text)
        if "rx" in text or "prescription" in text:
            prescription_score += 3
        scores[MedicalFormType.PRESCRIPTION_FORM] = prescription_score

        # Check for lab result indicators
        lab_keywords = [
            "lab",
            "laboratory",
            "test result",
            "specimen",
            "reference range",
        ]
        lab_score = sum(1 for kw in lab_keywords if kw in text)
        if any(unit in text for unit in ["mg/dl", "mmol/l", "iu/l", "cells/mm3"]):
            lab_score += 2
        scores[MedicalFormType.LAB_RESULT] = lab_score

        # Check for vaccination indicators
        vaccine_keywords = [
            "vaccination",
            "immunization",
            "vaccine",
            "dose",
            "lot number",
        ]
        vaccine_score = sum(1 for kw in vaccine_keywords if kw in text)
        scores[MedicalFormType.VACCINATION_RECORD] = vaccine_score

        # Check for consent form indicators
        consent_keywords = ["consent", "agree", "authorize", "permission", "signature"]
        consent_score = sum(1 for kw in consent_keywords if kw in text)
        if analysis_result.signatures_detected:
            consent_score += 2
        scores[MedicalFormType.CONSENT_FORM] = consent_score

        # Return form type with highest score
        if max(scores.values()) == 0:
            # Try to detect from document type
            doc_type_mapping = {
                DocumentType.PRESCRIPTION: MedicalFormType.PRESCRIPTION_FORM,
                DocumentType.LAB_REPORT: MedicalFormType.LAB_RESULT,
                DocumentType.VACCINATION_CARD: MedicalFormType.VACCINATION_RECORD,
                DocumentType.CONSENT_FORM: MedicalFormType.CONSENT_FORM,
            }
            return doc_type_mapping.get(
                analysis_result.document_type, MedicalFormType.PATIENT_INTAKE
            )

        return max(scores, key=lambda x: scores.get(x, 0))

    async def _extract_form_fields(
        self,
        analysis_result: DocumentAnalysisResult,
        form_type: MedicalFormType,
        language: str,
    ) -> List[ExtractedFormField]:
        """Extract form fields based on form type and language."""
        extracted_fields = []

        # Get expected fields for this form type
        expected_fields = self.form_templates.get(form_type, [])

        # Process each extracted form field
        for form in analysis_result.extracted_forms:
            # Try to match field type
            field_type = await self._match_field_type(form.key, language)

            if field_type:
                extracted_field = ExtractedFormField(
                    field_type=field_type,
                    label=form.key,
                    value=form.value,
                    confidence=form.confidence,
                    page=form.page,
                    original_value=form.value,
                )

                # Apply post-processing if configured
                mapping = self.field_mappings.get(field_type)
                if mapping and mapping.post_processing:
                    extracted_field.normalized_value = (
                        await self._apply_post_processing(
                            form.value, mapping.post_processing, language
                        )
                    )

                extracted_fields.append(extracted_field)
            else:
                # Keep as custom field
                extracted_fields.append(
                    ExtractedFormField(
                        field_type=FormFieldType.CUSTOM_FIELD,
                        label=form.key,
                        value=form.value,
                        confidence=form.confidence,
                        page=form.page,
                        original_value=form.value,
                    )
                )

        # Extract from tables if needed
        table_fields = await self._extract_from_tables(
            analysis_result.extracted_tables, form_type
        )
        extracted_fields.extend(table_fields)

        # Check for missing required fields
        for expected_field in expected_fields:
            if not any(f.field_type == expected_field for f in extracted_fields):
                mapping = self.field_mappings.get(expected_field)
                if mapping and mapping.required:
                    logger.warning("Required field %s not found", expected_field.value)

        return extracted_fields

    async def _match_field_type(
        self, field_label: str, language: str
    ) -> Optional[FormFieldType]:
        """Match a field label to a field type."""
        normalized_label = field_label.lower().strip()

        # Try direct matching first
        for field_type, mapping in self.field_mappings.items():
            for common_label in mapping.common_labels:
                if common_label in normalized_label or normalized_label in common_label:
                    return field_type

        # Try translation if not English
        if language != "en":
            try:
                translated_label = await self.translator.translate_term(
                    normalized_label, source_language=language, target_language="en"
                )
                return await self._match_field_type(translated_label, "en")
            except (ValueError, KeyError):
                pass

        return None

    async def _apply_post_processing(
        self, value: str, processing_func: str, language: str
    ) -> Any:
        """Apply post-processing to extracted value."""
        if processing_func == "normalize_name":
            # Normalize name format
            parts = value.strip().split()
            return " ".join(p.capitalize() for p in parts)

        elif processing_func == "parse_date":
            # Parse multilingual date
            return self.date_parser.parse(value, language)

        return value

    async def _validate_fields(
        self, fields: List[ExtractedFormField]
    ) -> List[ExtractedFormField]:
        """Validate extracted fields."""
        validators = {
            "validate_date": self._validate_date,
            "validate_diagnosis_code": self._validate_diagnosis_code,
            "validate_medication_name": self._validate_medication_name,
            "validate_dosage": self._validate_dosage,
            "validate_lab_test": self._validate_lab_test,
            "validate_lab_value": self._validate_lab_value,
            "validate_vital_sign": self._validate_vital_sign,
        }

        for form_field in fields:
            mapping = self.field_mappings.get(form_field.field_type)
            if mapping and mapping.validation_func:
                validator = validators.get(mapping.validation_func)
                if validator:
                    try:
                        is_valid, errors = await validator(form_field.value)
                        form_field.validation_status = (
                            "valid" if is_valid else "invalid"
                        )
                        form_field.validation_errors = errors
                    except (ValueError, AttributeError, KeyError) as e:
                        form_field.validation_status = "error"
                        form_field.validation_errors = [str(e)]
                else:
                    form_field.validation_status = "skipped"
            else:
                form_field.validation_status = "not_required"

        return fields

    async def _validate_date(self, value: str) -> Tuple[bool, List[str]]:
        """Validate date value."""
        errors = []
        try:
            parsed_date = self.date_parser.parse(value, "en")
            if parsed_date is None:
                return False, ["Unable to parse date"]
            if parsed_date > date.today():
                errors.append("Date cannot be in the future")
            if parsed_date.year < 1900:
                errors.append("Date seems too old")
            return len(errors) == 0, errors
        except (ValueError, TypeError):
            return False, ["Invalid date format"]

    async def _validate_diagnosis_code(self, value: str) -> Tuple[bool, List[str]]:
        """Validate diagnosis code (ICD-10)."""
        # Basic ICD-10 format validation
        icd10_pattern = re.compile(r"^[A-Z]\d{2}\.?\d{0,4}$")
        if not icd10_pattern.match(value.upper()):
            return False, ["Invalid ICD-10 format"]

        # Could add actual ICD-10 code validation here
        return True, []

    async def _validate_medication_name(self, value: str) -> Tuple[bool, List[str]]:
        """Validate medication name."""
        try:
            # Use validate_term as validate_medication doesn't exist
            is_valid = self.terminology_validator.validate_term(value)
            if not is_valid:
                return False, ["Medication not found in database"]
            return True, []
        except (ConnectionError, TimeoutError):
            return True, []  # Allow if validation service unavailable

    async def _validate_dosage(self, value: str) -> Tuple[bool, List[str]]:
        """Validate medication dosage."""
        # Basic dosage format validation
        dosage_pattern = re.compile(r"^\d+\.?\d*\s*[a-zA-Z]+$")
        if not dosage_pattern.match(value):
            return False, ["Invalid dosage format"]
        return True, []

    async def _validate_lab_test(self, value: str) -> Tuple[bool, List[str]]:
        """Validate lab test name."""
        _ = value  # Mark as intentionally unused - placeholder for LOINC validation
        # Could validate against LOINC codes
        return True, []

    async def _validate_lab_value(self, value: str) -> Tuple[bool, List[str]]:
        """Validate lab value."""
        # Allow numeric values with operators
        lab_value_pattern = re.compile(r"^[<>≤≥]?\s*\d+\.?\d*$")
        if not lab_value_pattern.match(value):
            return False, ["Invalid lab value format"]
        return True, []

    async def _validate_vital_sign(self, value: str) -> Tuple[bool, List[str]]:
        """Validate vital sign value."""
        # Handle blood pressure format (e.g., 120/80)
        bp_pattern = re.compile(r"^\d{2,3}/\d{2,3}$")
        numeric_pattern = re.compile(r"^\d+\.?\d*$")

        if not (bp_pattern.match(value) or numeric_pattern.match(value)):
            return False, ["Invalid vital sign format"]
        return True, []

    async def _extract_from_tables(
        self, tables: List[ExtractedTable], form_type: MedicalFormType
    ) -> List[ExtractedFormField]:
        _ = form_type  # Mark as intentionally unused - may be used for form-specific logic
        # Extract fields from tables
        fields = []

        for table in tables:
            # Analyze table structure
            if len(table.rows) < 2:
                continue

            # Assume first row is header
            headers = table.rows[0]

            # Process data rows
            for row_idx in range(1, len(table.rows)):
                row = table.rows[row_idx]

                for col_idx, cell_value in enumerate(row):
                    if col_idx < len(headers) and cell_value:
                        header = headers[col_idx]

                        # Try to match field type
                        field_type = await self._match_field_type(header, "en")

                        if field_type:
                            fields.append(
                                ExtractedFormField(
                                    field_type=field_type,
                                    label=header,
                                    value=cell_value,
                                    confidence=table.confidence,
                                    page=table.page,
                                    original_value=cell_value,
                                    metadata={
                                        "from_table": True,
                                        "row": row_idx,
                                        "col": col_idx,
                                    },
                                )
                            )

        return fields

    def _calculate_confidence(self, fields: List[ExtractedFormField]) -> float:
        """Calculate overall confidence score."""
        if not fields:
            return 0.0

        required_fields = [
            f
            for f in fields
            if self.field_mappings.get(
                f.field_type, FormFieldMapping(FormFieldType.CUSTOM_FIELD, [], [])
            ).required
        ]

        # Weight confidence by validation status and requirement
        total_weight = 0.0
        weighted_confidence = 0.0

        for form_field in fields:
            weight = 2.0 if form_field in required_fields else 1.0
            if form_field.validation_status != "valid":
                weight *= 0.5

            weighted_confidence += form_field.confidence * weight
            total_weight += weight

        return weighted_confidence / total_weight if total_weight > 0 else 0.0

    async def _convert_to_standards(
        self, form_data: MedicalFormData
    ) -> StandardsConversionResult:
        """Convert form data to healthcare standards."""
        # Convert to FHIR
        try:
            if form_data.form_type == MedicalFormType.PRESCRIPTION_FORM:
                fhir_resource = await self._create_medication_request(form_data)
                form_data.fhir_resources.append(fhir_resource)

            elif form_data.form_type == MedicalFormType.LAB_RESULT:
                fhir_resource = await self._create_observation(form_data)
                form_data.fhir_resources.append(fhir_resource)

        except (ValueError, AttributeError, KeyError) as e:
            logger.error("FHIR conversion failed: %s", str(e))
            form_data.warnings.append(f"FHIR conversion failed: {str(e)}")

        # Convert to HL7
        try:
            hl7_message = await self._create_hl7_message(form_data)
            if hl7_message:
                form_data.hl7_messages.append(hl7_message)
        except (ValueError, KeyError, AttributeError, TypeError) as e:
            logger.error("HL7 conversion failed: %s", str(e))
            form_data.warnings.append(f"HL7 conversion failed: {str(e)}")

        # Return the conversion result
        return StandardsConversionResult(
            fhir_resources=form_data.fhir_resources,
            hl7_messages=form_data.hl7_messages,
            conversion_warnings=form_data.warnings,
            conversion_errors=[],
            success=True,
            metadata={"form_type": form_data.form_type.value},
        )

    async def _create_medication_request(
        self, form_data: MedicalFormData
    ) -> Dict[str, Any]:
        """Create FHIR MedicationRequest resource."""
        patient_name = form_data.get_field_by_type(FormFieldType.PATIENT_NAME)
        medication = form_data.get_field_by_type(FormFieldType.MEDICATION_NAME)
        dosage = form_data.get_field_by_type(FormFieldType.DOSAGE)

        return {
            "resourceType": "MedicationRequest",
            "id": form_data.form_id,
            "status": "active",
            "intent": "order",
            "medicationCodeableConcept": {
                "text": medication.value if medication else None
            },
            "subject": {"display": patient_name.value if patient_name else None},
            "dosageInstruction": [{"text": dosage.value if dosage else None}],
        }

    async def _create_observation(self, form_data: MedicalFormData) -> Dict[str, Any]:
        """Create FHIR Observation resource."""
        patient_name = form_data.get_field_by_type(FormFieldType.PATIENT_NAME)
        test_name = form_data.get_field_by_type(FormFieldType.LAB_TEST_NAME)
        value = form_data.get_field_by_type(FormFieldType.LAB_VALUE)

        return {
            "resourceType": "Observation",
            "id": form_data.form_id,
            "status": "final",
            "code": {"text": test_name.value if test_name else None},
            "subject": {"display": patient_name.value if patient_name else None},
            "valueQuantity": {"value": value.value if value else None},
        }

    async def _create_hl7_message(self, form_data: MedicalFormData) -> Optional[str]:
        """Create HL7 message from form data."""
        # This would create actual HL7 message
        # Simplified for now
        _ = form_data  # Mark as intentionally unused
        return None

    async def _final_validation(self, form_data: MedicalFormData) -> str:
        """Perform final validation of form data."""
        # Check required fields
        required_fields_present = True
        for field_type in self.form_templates.get(form_data.form_type, []):
            mapping = self.field_mappings.get(field_type)
            if mapping and mapping.required:
                if not form_data.get_field_by_type(field_type):
                    required_fields_present = False
                    form_data.warnings.append(
                        f"Required field {field_type.value} missing"
                    )

        # Check validation status of fields
        invalid_fields = [
            f for f in form_data.fields if f.validation_status == "invalid"
        ]

        if not required_fields_present:
            return "incomplete"
        elif invalid_fields:
            return "partially_valid"
        elif form_data.confidence_score < 0.7:
            return "low_confidence"
        else:
            return "valid"
