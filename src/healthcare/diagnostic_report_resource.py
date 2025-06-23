"""DiagnosticReport FHIR Resource Implementation.

This module implements the DiagnosticReport FHIR resource for Haven Health Passport,
handling laboratory results, imaging reports, and other diagnostic findings with
considerations for limited diagnostic capabilities in refugee settings.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from fhirclient.models.attachment import Attachment
from fhirclient.models.codeableconcept import CodeableConcept
from fhirclient.models.coding import Coding
from fhirclient.models.diagnosticreport import DiagnosticReport, DiagnosticReportMedia
from fhirclient.models.fhirreference import FHIRReference
from fhirclient.models.identifier import Identifier

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)

from .fhir_base import BaseFHIRResource
from .fhir_profiles import REFUGEE_DIAGNOSTIC_REPORT_PROFILE

logger = logging.getLogger(__name__)

# FHIR resource type for this module
__fhir_resource__ = "DiagnosticReport"


class DiagnosticReportStatus(Enum):
    """DiagnosticReport status codes."""

    REGISTERED = "registered"  # Order received, not yet started
    PARTIAL = "partial"  # Partial results available
    PRELIMINARY = "preliminary"  # Preliminary results available
    FINAL = "final"  # Final results; report complete
    AMENDED = "amended"  # Report has been modified
    CORRECTED = "corrected"  # Report has been corrected
    APPENDED = "appended"  # Report has addendum
    CANCELLED = "cancelled"  # Report cancelled
    ENTERED_IN_ERROR = "entered-in-error"  # Entered in error
    UNKNOWN = "unknown"  # Unknown status


class DiagnosticServiceCategory(Enum):
    """Diagnostic service categories."""

    # Standard categories
    HEMATOLOGY = "HM"  # Hematology
    CHEMISTRY = "CH"  # Chemistry
    MICROBIOLOGY = "MB"  # Microbiology
    PATHOLOGY = "PA"  # Pathology
    RADIOLOGY = "RAD"  # Radiology
    CARDIOLOGY = "CAR"  # Cardiology

    # Extended categories
    PARASITOLOGY = "PAR"  # Parasitology
    VIROLOGY = "VIR"  # Virology
    IMMUNOLOGY = "IMM"  # Immunology
    GENETICS = "GEN"  # Genetics

    # Field/rapid diagnostics
    RAPID_TEST = "RDT"  # Rapid diagnostic test
    POINT_OF_CARE = "POC"  # Point of care testing
    FIELD_LAB = "FIELD"  # Field laboratory

    # Other
    OTHER = "OTH"  # Other
    UNKNOWN = "UNK"  # Unknown


class CommonDiagnosticTests:
    """Common diagnostic tests in refugee healthcare."""

    TESTS = {
        # Rapid diagnostic tests
        "malaria_rdt": {
            "code": "414544004",
            "display": "Malaria rapid diagnostic test",
            "category": DiagnosticServiceCategory.RAPID_TEST,
            "typical_tat": 15,  # Turn-around time in minutes
            "specimen": "blood",
        },
        "hiv_rdt": {
            "code": "31676001",
            "display": "HIV rapid test",
            "category": DiagnosticServiceCategory.RAPID_TEST,
            "typical_tat": 20,
            "specimen": "blood",
        },
        "pregnancy_test": {
            "code": "45339005",
            "display": "Pregnancy test",
            "category": DiagnosticServiceCategory.RAPID_TEST,
            "typical_tat": 5,
            "specimen": "urine",
        },
        # Basic laboratory
        "complete_blood_count": {
            "code": "58410-2",
            "display": "Complete blood count",
            "category": DiagnosticServiceCategory.HEMATOLOGY,
            "typical_tat": 60,
            "specimen": "blood",
        },
        "hemoglobin": {
            "code": "718-7",
            "display": "Hemoglobin",
            "category": DiagnosticServiceCategory.HEMATOLOGY,
            "typical_tat": 30,
            "specimen": "blood",
        },
        "blood_glucose": {
            "code": "2339-0",
            "display": "Blood glucose",
            "category": DiagnosticServiceCategory.CHEMISTRY,
            "typical_tat": 15,
            "specimen": "blood",
        },
        "urinalysis": {
            "code": "24357-6",
            "display": "Urinalysis",
            "category": DiagnosticServiceCategory.CHEMISTRY,
            "typical_tat": 30,
            "specimen": "urine",
        },
        # Microbiology
        "blood_culture": {
            "code": "600-7",
            "display": "Blood culture",
            "category": DiagnosticServiceCategory.MICROBIOLOGY,
            "typical_tat": 2880,  # 48 hours
            "specimen": "blood",
        },
        "stool_microscopy": {
            "code": "618-9",
            "display": "Stool microscopy",
            "category": DiagnosticServiceCategory.PARASITOLOGY,
            "typical_tat": 60,
            "specimen": "stool",
        },
        "sputum_afb": {
            "code": "11545-1",
            "display": "Sputum AFB microscopy",
            "category": DiagnosticServiceCategory.MICROBIOLOGY,
            "typical_tat": 60,
            "specimen": "sputum",
        },
        # Imaging (if available)
        "chest_xray": {
            "code": "399208008",
            "display": "Chest X-ray",
            "category": DiagnosticServiceCategory.RADIOLOGY,
            "typical_tat": 30,
            "specimen": None,
        },
        "ultrasound_abdomen": {
            "code": "45036003",
            "display": "Abdominal ultrasound",
            "category": DiagnosticServiceCategory.RADIOLOGY,
            "typical_tat": 30,
            "specimen": None,
        },
    }

    @classmethod
    def get_test_info(cls, test_name: str) -> Optional[Dict]:
        """Get information about a diagnostic test."""
        return cls.TESTS.get(test_name.lower().replace(" ", "_"))


class DiagnosticReportResource(BaseFHIRResource):
    """DiagnosticReport FHIR resource implementation."""

    def __init__(self) -> None:
        """Initialize DiagnosticReport resource handler."""
        super().__init__(DiagnosticReport)
        self._encrypted_fields = []  # Reports typically not encrypted

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_diagnostic_report")
    def create_resource(self, data: Dict[str, Any]) -> DiagnosticReport:
        """Create a new DiagnosticReport resource.

        Args:
            data: Dictionary containing report data with fields:
                - status: Report status (required)
                - category: Report category
                - code: What was tested (required)
                - subject: Reference to patient (required)
                - encounter: Reference to encounter
                - effective: Clinically relevant time
                - issued: DateTime report made available
                - performer: Who performed the test
                - result: Observations that are part of report
                - conclusion: Clinical conclusion
                - conclusionCode: Coded conclusion

        Returns:
            Created DiagnosticReport resource
        """
        report = DiagnosticReport()

        # Set required fields
        report.status = data.get("status", DiagnosticReportStatus.FINAL.value)
        report.code = self._create_test_code(data["code"])
        report.subject = FHIRReference({"reference": data["subject"]})

        # Set ID if provided
        if "id" in data:
            report.id = data["id"]

        # Set identifiers
        if "identifier" in data:
            report.identifier = [
                self._create_identifier(ident) for ident in data["identifier"]
            ]

        # Set based on
        if "basedOn" in data:
            report.basedOn = [
                FHIRReference({"reference": ref}) for ref in data["basedOn"]
            ]

        # Set category
        if "category" in data:
            report.category = [self._create_category(cat) for cat in data["category"]]

        # Set encounter
        if "encounter" in data:
            report.encounter = FHIRReference({"reference": data["encounter"]})

        # Set effective time
        if "effective" in data:
            report.effectiveDateTime = self._create_fhir_datetime(data["effective"])

        # Set issued time
        if "issued" in data:
            report.issued = self._create_fhir_instant(data["issued"])

        # Set performer
        if "performer" in data:
            report.performer = [
                FHIRReference({"reference": ref}) for ref in data["performer"]
            ]

        # Set results references
        if "result" in data:
            report.result = [
                FHIRReference({"reference": ref}) for ref in data["result"]
            ]

        # Set imaging study references
        if "imagingStudy" in data:
            report.imagingStudy = [
                FHIRReference({"reference": ref}) for ref in data["imagingStudy"]
            ]

        # Set media
        if "media" in data:
            report.media = [self._create_media(media) for media in data["media"]]

        # Set conclusion
        if "conclusion" in data:
            report.conclusion = data["conclusion"]

        # Set conclusion codes
        if "conclusionCode" in data:
            report.conclusionCode = [
                self._create_codeable_concept(code) for code in data["conclusionCode"]
            ]

        # Set presented form (PDF, images, etc.)
        if "presentedForm" in data:
            report.presentedForm = [
                self._create_attachment(form) for form in data["presentedForm"]
            ]

        # Add refugee-specific extensions
        if "refugee_context" in data:
            self._add_refugee_context(report, data["refugee_context"])

        # Add profile and validate
        self.add_meta_profile(report, REFUGEE_DIAGNOSTIC_REPORT_PROFILE)

        # Store and validate
        self._resource = report
        self.validate()

        # Add audit entry
        self.add_audit_entry("create", data.get("created_by", "system"))

        return report

    def get_encrypted_fields(self) -> List[str]:
        """Return list of fields that should be encrypted."""
        return self._encrypted_fields

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_rapid_test_report")
    def create_rapid_test_report(
        self,
        test_type: str,
        patient_id: str,
        result: str,
        performed_by: Optional[str] = None,
        **kwargs: Any,
    ) -> DiagnosticReport:
        """Create a rapid diagnostic test report.

        Args:
            test_type: Type of rapid test
            patient_id: Patient reference
            result: Test result (positive/negative/invalid)
            performed_by: Performer reference
            **kwargs: Additional report fields

        Returns:
            Created diagnostic report
        """
        test_info = CommonDiagnosticTests.get_test_info(test_type)
        if not test_info:
            # Create generic rapid test
            test_code = {
                "text": test_type,
                "coding": [
                    {
                        "system": "http://havenhealthpassport.org/fhir/CodeSystem/rapid-tests",
                        "code": f'RDT-{test_type.upper().replace(" ", "-")}',
                        "display": test_type,
                    }
                ],
            }
            category = DiagnosticServiceCategory.RAPID_TEST
        else:
            test_code = {
                "coding": [
                    {
                        "system": (
                            "http://loinc.org"
                            if not test_info["code"].startswith("RDT")
                            else "http://havenhealthpassport.org/fhir/CodeSystem/rapid-tests"
                        ),
                        "code": test_info["code"],
                        "display": test_info["display"],
                    }
                ]
            }
            category = test_info["category"]

        # Create simple conclusion based on result
        conclusion = f"{test_type}: {result}"
        conclusion_code = []

        if result.lower() == "positive":
            conclusion_code.append(
                {
                    "coding": [
                        {
                            "system": "http://snomed.info/sct",
                            "code": "10828004",
                            "display": "Positive",
                        }
                    ]
                }
            )
        elif result.lower() == "negative":
            conclusion_code.append(
                {
                    "coding": [
                        {
                            "system": "http://snomed.info/sct",
                            "code": "260385009",
                            "display": "Negative",
                        }
                    ]
                }
            )

        data = {
            "status": DiagnosticReportStatus.FINAL.value,
            "category": [category.value],
            "code": test_code,
            "subject": f"Patient/{patient_id}",
            "effective": kwargs.get("effective", datetime.now()),
            "issued": kwargs.get("issued", datetime.now()),
            "conclusion": conclusion,
            "conclusionCode": conclusion_code,
        }

        if performed_by:
            data["performer"] = [performed_by]

        # Add rapid test context
        data["refugee_context"] = {
            "test_type": "rapid",
            "field_conditions": kwargs.get("field_conditions", True),
        }

        # Add any additional fields
        data.update(kwargs)

        return self.create_resource(data)

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("create_lab_report")
    def create_lab_report(
        self,
        test_codes: List[str],
        patient_id: str,
        observations: List[str],
        conclusion: Optional[str] = None,
        **kwargs: Any,
    ) -> DiagnosticReport:
        """Create a laboratory report with multiple results.

        Args:
            test_codes: List of test codes performed
            patient_id: Patient reference
            observations: List of observation references
            conclusion: Overall conclusion
            **kwargs: Additional report fields

        Returns:
            Created diagnostic report
        """
        # Create composite code for panel
        codings = []
        for test_code in test_codes:
            test_info = CommonDiagnosticTests.get_test_info(test_code)
            if test_info:
                codings.append(
                    {
                        "system": "http://loinc.org",
                        "code": test_info["code"],
                        "display": test_info["display"],
                    }
                )

        data = {
            "status": kwargs.get("status", DiagnosticReportStatus.FINAL.value),
            "category": [DiagnosticServiceCategory.CHEMISTRY.value],
            "code": {"coding": codings, "text": "Laboratory panel"},
            "subject": f"Patient/{patient_id}",
            "effective": kwargs.get("effective", datetime.now()),
            "issued": kwargs.get("issued", datetime.now()),
            "result": [f"Observation/{obs}" for obs in observations],
        }

        if conclusion:
            data["conclusion"] = conclusion

        # Add any additional fields
        data.update(kwargs)

        return self.create_resource(data)

    def _create_test_code(self, code_data: Union[str, Dict]) -> CodeableConcept:
        """Create diagnostic test code."""
        if isinstance(code_data, str):
            # Try to look up in common tests
            test_info = CommonDiagnosticTests.get_test_info(code_data)
            if test_info:
                system = "http://loinc.org"
                if test_info["code"].startswith(("RDT", "FIELD", "POC")):
                    system = "http://havenhealthpassport.org/fhir/CodeSystem/field-diagnostics"

                return CodeableConcept(
                    {
                        "coding": [
                            {
                                "system": system,
                                "code": test_info["code"],
                                "display": test_info["display"],
                            }
                        ],
                        "text": test_info["display"],
                    }
                )
            else:
                # Create as text-only
                return CodeableConcept({"text": code_data})
        else:
            return self._create_codeable_concept(code_data)

    def _create_category(self, category: Union[str, Dict]) -> CodeableConcept:
        """Create diagnostic service category."""
        if isinstance(category, str):
            # Try to match to enum
            try:
                cat_enum = DiagnosticServiceCategory(category)
                return CodeableConcept(
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                                "code": cat_enum.value,
                                "display": cat_enum.name.replace("_", " ").title(),
                            }
                        ]
                    }
                )
            except ValueError:
                return CodeableConcept({"text": category})
        else:
            return self._create_codeable_concept(category)

    def _create_media(self, media_data: Dict) -> DiagnosticReportMedia:
        """Create media reference."""
        media = DiagnosticReportMedia()

        if "comment" in media_data:
            media.comment = media_data["comment"]

        if "link" in media_data:
            media.link = FHIRReference({"reference": media_data["link"]})

        return media

    def _create_attachment(self, attachment_data: Dict) -> Attachment:
        """Create attachment for presented form."""
        attachment = Attachment()

        if "contentType" in attachment_data:
            attachment.contentType = attachment_data["contentType"]

        if "data" in attachment_data:
            attachment.data = attachment_data["data"]

        if "url" in attachment_data:
            attachment.url = attachment_data["url"]

        if "title" in attachment_data:
            attachment.title = attachment_data["title"]

        if "creation" in attachment_data:
            attachment.creation = self._create_fhir_datetime(
                attachment_data["creation"]
            )

        return attachment

    def _create_identifier(self, identifier_data: Dict) -> Identifier:
        """Create report identifier."""
        identifier = Identifier()

        if "system" in identifier_data:
            identifier.system = identifier_data["system"]

        if "value" in identifier_data:
            identifier.value = identifier_data["value"]

        if "use" in identifier_data:
            identifier.use = identifier_data["use"]

        return identifier

    def _create_codeable_concept(self, data: Union[str, Dict]) -> CodeableConcept:
        """Create CodeableConcept from data."""
        concept = CodeableConcept()

        if isinstance(data, str):
            concept.text = data
        else:
            if "coding" in data:
                concept.coding = []
                for coding_data in data["coding"]:
                    coding = Coding()
                    if "system" in coding_data:
                        coding.system = coding_data["system"]
                    if "code" in coding_data:
                        coding.code = coding_data["code"]
                    if "display" in coding_data:
                        coding.display = coding_data["display"]
                    concept.coding.append(coding)

            if "text" in data:
                concept.text = data["text"]

        return concept

    def _create_fhir_datetime(self, datetime_value: Union[str, datetime]) -> str:
        """Create FHIR datetime string."""
        if isinstance(datetime_value, str):
            return datetime_value
        elif isinstance(datetime_value, datetime):
            return datetime_value.isoformat()
        else:
            raise ValueError(f"Invalid datetime format: {type(datetime_value)}")

    def _create_fhir_instant(self, instant_value: Union[str, datetime]) -> str:
        """Create FHIR instant string."""
        if isinstance(instant_value, str):
            return instant_value
        elif isinstance(instant_value, datetime):
            # Instant requires timezone
            return instant_value.isoformat()
        else:
            raise ValueError(f"Invalid instant format: {type(instant_value)}")

    def _add_refugee_context(
        self, report: DiagnosticReport, context_data: Dict[str, Any]
    ) -> None:
        """Add refugee-specific context extensions."""
        if not report.extension:
            report.extension = []

        # Add test location type
        if "test_location" in context_data:
            ext = {
                "url": "http://havenhealthpassport.org/fhir/extension/test-location-type",
                "valueString": context_data[
                    "test_location"
                ],  # e.g., "field", "camp_clinic"
            }
            report.extension.append(ext)

        # Add equipment limitations
        if "equipment_limitations" in context_data:
            ext = {
                "url": "http://havenhealthpassport.org/fhir/extension/equipment-limitations",
                "valueString": context_data["equipment_limitations"],
            }
            report.extension.append(ext)

        # Add test type (rapid, field, etc.)
        if "test_type" in context_data:
            ext = {
                "url": "http://havenhealthpassport.org/fhir/extension/test-type",
                "valueCode": context_data["test_type"],
            }
            report.extension.append(ext)

        # Add quality indicators
        if "quality_indicators" in context_data:
            for indicator, value in context_data["quality_indicators"].items():
                ext = {
                    "url": f"http://havenhealthpassport.org/fhir/extension/quality-{indicator}",
                    "valueString": str(value),
                }
                report.extension.append(ext)
