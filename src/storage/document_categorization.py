"""Document categorization service for automatic file classification.

This service categorizes medical documents and maps them to appropriate
FHIR DocumentReference Resource types.
"""

from typing import Any, Dict, Optional, Tuple

from src.healthcare.fhir_validator import FHIRValidator
from src.storage.base import FileCategory
from src.utils.logging import get_logger

# FHIR resource type for this module
__fhir_resource__ = "DocumentReference"

logger = get_logger(__name__)

# Initialize validator
validator = FHIRValidator()


class DocumentCategorizationService:
    """Service for automatically categorizing uploaded documents."""

    # Keywords for categorization
    CATEGORY_KEYWORDS = {
        FileCategory.MEDICAL_RECORD: [
            "medical record",
            "patient record",
            "clinical record",
            "health record",
            "medical history",
            "patient history",
            "discharge summary",
            "admission record",
        ],
        FileCategory.LAB_RESULT: [
            "lab result",
            "laboratory",
            "blood test",
            "urine test",
            "test result",
            "pathology",
            "microbiology",
            "biochemistry",
            "hematology",
            "serology",
            "culture result",
        ],
        FileCategory.IMAGING: [
            "x-ray",
            "xray",
            "radiograph",
            "ct scan",
            "mri",
            "ultrasound",
            "sonogram",
            "mammogram",
            "pet scan",
            "imaging",
            "radiology",
        ],
        FileCategory.PRESCRIPTION: [
            "prescription",
            "rx",
            "medication order",
            "drug order",
            "pharmacy",
            "dosage",
            "medication list",
        ],
        FileCategory.VACCINATION: [
            "vaccination",
            "immunization",
            "vaccine",
            "vaccination record",
            "immunization record",
            "covid",
            "yellow fever",
            "hepatitis",
        ],
        FileCategory.INSURANCE: [
            "insurance",
            "policy",
            "coverage",
            "claim",
            "benefit",
            "insurance card",
            "member id",
            "group number",
        ],
        FileCategory.IDENTIFICATION: [
            "passport",
            "id card",
            "driver license",
            "birth certificate",
            "national id",
            "refugee card",
            "unhcr",
            "identity document",
        ],
        FileCategory.CONSENT_FORM: [
            "consent",
            "authorization",
            "release form",
            "hipaa",
            "permission",
            "agreement",
            "consent form",
        ],
        FileCategory.CLINICAL_NOTE: [
            "clinical note",
            "progress note",
            "nursing note",
            "physician note",
            "consultation",
            "assessment",
        ],
    }

    # File extension mappings
    EXTENSION_HINTS = {
        ".dcm": FileCategory.IMAGING,  # DICOM files
        ".dicom": FileCategory.IMAGING,
        ".mp3": FileCategory.VOICE_RECORDING,
        ".wav": FileCategory.VOICE_RECORDING,
        ".m4a": FileCategory.VOICE_RECORDING,
        ".ogg": FileCategory.VOICE_RECORDING,
    }

    # MIME type mappings
    MIME_TYPE_HINTS = {
        "application/dicom": FileCategory.IMAGING,
        "image/dicom": FileCategory.IMAGING,
        "audio/mpeg": FileCategory.VOICE_RECORDING,
        "audio/wav": FileCategory.VOICE_RECORDING,
        "audio/ogg": FileCategory.VOICE_RECORDING,
        "audio/mp4": FileCategory.VOICE_RECORDING,
    }

    def __init__(self) -> None:
        """Initialize document categorization service."""
        self.confidence_threshold = 0.7  # Minimum confidence for auto-categorization

    def categorize_document(
        self,
        filename: str,
        content_type: Optional[str] = None,
        content_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[FileCategory, float, Dict[str, Any]]:
        """Categorize a document based on various signals.

        Args:
            filename: Original filename
            content_type: MIME type
            content_text: Extracted text content (for searchable PDFs)
            metadata: Additional metadata

        Returns:
            Tuple of (category, confidence, analysis_details)
        """
        scores: Dict[FileCategory, float] = {}
        analysis: Dict[str, Any] = {
            "filename": filename,
            "content_type": content_type,
            "signals_used": [],
        }

        # Check file extension
        extension = self._get_file_extension(filename)
        if extension and extension.lower() in self.EXTENSION_HINTS:
            category = self.EXTENSION_HINTS[extension.lower()]
            scores[category] = scores.get(category, 0) + 0.8
            analysis["signals_used"].append(f"extension:{extension}")

        # Check MIME type
        if content_type and content_type in self.MIME_TYPE_HINTS:
            category = self.MIME_TYPE_HINTS[content_type]
            scores[category] = scores.get(category, 0) + 0.7
            analysis["signals_used"].append(f"mime_type:{content_type}")

        # Analyze filename
        filename_lower = filename.lower()
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in filename_lower:
                    scores[category] = scores.get(category, 0) + 0.6
                    analysis["signals_used"].append(f"filename_keyword:{keyword}")

        # Analyze content text if available
        if content_text:
            content_lower = content_text.lower()
            for category, keywords in self.CATEGORY_KEYWORDS.items():
                keyword_count = 0
                for keyword in keywords:
                    if keyword in content_lower:
                        keyword_count += content_lower.count(keyword)

                if keyword_count > 0:
                    # Normalize score based on content length
                    content_score = min(keyword_count * 0.1, 0.9)
                    scores[category] = scores.get(category, 0) + content_score
                    analysis["signals_used"].append(
                        f"content_keywords:{category.value}:{keyword_count}"
                    )

        # Analyze metadata
        if metadata:
            category_hint = metadata.get("category_hint")
            if category_hint:
                try:
                    hint_category = FileCategory(category_hint)
                    scores[hint_category] = scores.get(hint_category, 0) + 0.5
                    analysis["signals_used"].append(f"metadata_hint:{category_hint}")
                except ValueError:
                    pass

        # Determine best category
        if scores:
            best_category = max(scores, key=lambda k: scores.get(k, 0.0))
            confidence = min(scores[best_category], 1.0)
        else:
            best_category = FileCategory.OTHER
            confidence = 0.1

        analysis["all_scores"] = {k.value: v for k, v in scores.items()}
        analysis["selected_category"] = best_category.value
        analysis["confidence"] = confidence

        return best_category, confidence, analysis

    def _get_file_extension(self, filename: str) -> Optional[str]:
        """Extract file extension from filename.

        Args:
            filename: Filename

        Returns:
            File extension including dot, or None
        """
        if "." in filename:
            return "." + filename.rsplit(".", 1)[1]
        return None

    def categorize_by_dicom_metadata(
        self, dicom_metadata: Dict[str, Any]
    ) -> Tuple[FileCategory, float]:
        """Categorize DICOM files based on metadata.

        Args:
            dicom_metadata: DICOM metadata tags

        Returns:
            Tuple of (category, confidence)
        """
        # Mark parameter as intentionally unused - kept for API compatibility
        _ = dicom_metadata
        # DICOM files are always imaging
        return FileCategory.IMAGING, 1.0

    def categorize_by_hl7_message(
        self, hl7_message_type: str
    ) -> Tuple[FileCategory, float]:
        """Categorize based on HL7 message type.

        Args:
            hl7_message_type: HL7 message type (e.g., "ORU", "ADT")

        Returns:
            Tuple of (category, confidence)
        """
        hl7_mappings = {
            "ORU": FileCategory.LAB_RESULT,  # Observation Result
            "MDM": FileCategory.MEDICAL_RECORD,  # Medical Document Management
            "RXO": FileCategory.PRESCRIPTION,  # Pharmacy Order
            "RXE": FileCategory.PRESCRIPTION,  # Pharmacy Encoded Order
            "VXU": FileCategory.VACCINATION,  # Vaccination Update
            "ADT": FileCategory.MEDICAL_RECORD,  # Admit/Discharge/Transfer
        }

        if hl7_message_type in hl7_mappings:
            return hl7_mappings[hl7_message_type], 0.9
        else:
            return FileCategory.MEDICAL_RECORD, 0.5

    def suggest_subcategory(
        self, category: FileCategory, filename: str, content_text: Optional[str] = None
    ) -> Optional[str]:
        """Suggest a subcategory for more specific classification.

        Args:
            category: Main category
            filename: Filename
            content_text: Document content

        Returns:
            Suggested subcategory or None
        """
        subcategories = {
            FileCategory.LAB_RESULT: {
                "blood": ["cbc", "blood count", "hemoglobin", "hematology"],
                "chemistry": [
                    "glucose",
                    "cholesterol",
                    "liver",
                    "kidney",
                    "electrolyte",
                ],
                "microbiology": ["culture", "sensitivity", "bacteria", "antibiotic"],
                "immunology": ["antibody", "antigen", "immunoglobulin"],
                "urine": ["urinalysis", "urine", "protein", "microscopy"],
            },
            FileCategory.IMAGING: {
                "xray": ["x-ray", "xray", "radiograph", "chest", "bone"],
                "ct": ["ct scan", "computed tomography", "cat scan"],
                "mri": ["mri", "magnetic resonance"],
                "ultrasound": ["ultrasound", "sonogram", "echo"],
                "mammogram": ["mammogram", "mammography", "breast"],
            },
            FileCategory.VACCINATION: {
                "covid19": ["covid", "coronavirus", "sars-cov-2", "pfizer", "moderna"],
                "routine": ["mmr", "dtap", "polio", "hepatitis", "varicella"],
                "travel": [
                    "yellow fever",
                    "typhoid",
                    "malaria",
                    "japanese encephalitis",
                ],
            },
        }

        if category not in subcategories:
            return None

        # Check against subcategory keywords
        text_to_check = filename.lower()
        if content_text:
            text_to_check += " " + content_text.lower()

        for subcat, keywords in subcategories[category].items():
            for keyword in keywords:
                if keyword in text_to_check:
                    return subcat

        return None

    def get_category_requirements(self, category: FileCategory) -> Dict[str, Any]:
        """Get requirements and best practices for a category.

        Args:
            category: File category

        Returns:
            Dictionary with requirements and recommendations
        """
        requirements = {
            FileCategory.MEDICAL_RECORD: {
                "required_fields": ["patient_id", "date", "provider"],
                "recommended_format": "PDF",
                "max_size_mb": 50,
                "retention_years": 7,
                "encryption_required": True,
            },
            FileCategory.LAB_RESULT: {
                "required_fields": ["patient_id", "date", "test_type"],
                "recommended_format": "PDF or HL7",
                "max_size_mb": 25,
                "retention_years": 7,
                "encryption_required": True,
            },
            FileCategory.IMAGING: {
                "required_fields": ["patient_id", "date", "modality"],
                "recommended_format": "DICOM or JPEG",
                "max_size_mb": 100,
                "retention_years": 7,
                "encryption_required": True,
            },
            FileCategory.PRESCRIPTION: {
                "required_fields": ["patient_id", "date", "prescriber", "medication"],
                "recommended_format": "PDF",
                "max_size_mb": 10,
                "retention_years": 7,
                "encryption_required": True,
            },
            FileCategory.VACCINATION: {
                "required_fields": ["patient_id", "date", "vaccine", "lot_number"],
                "recommended_format": "PDF",
                "max_size_mb": 10,
                "retention_years": "permanent",
                "encryption_required": True,
            },
        }

        return requirements.get(
            category,
            {
                "required_fields": ["patient_id", "date"],
                "recommended_format": "PDF",
                "max_size_mb": 25,
                "retention_years": 3,
                "encryption_required": True,
            },
        )
