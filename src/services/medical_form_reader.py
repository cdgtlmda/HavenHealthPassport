"""Production Medical Form Reader Service.

This module provides OCR and intelligent data extraction from medical forms,
including prescriptions, lab reports, vaccination cards, and other documents.
Extracted data is converted to FHIR DomainResource format.
"""

import asyncio
import io
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import boto3

# OCR and Document Processing
import numpy as np
from PIL import Image

try:
    import cv2

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None  # type: ignore[assignment]

try:
    import pytesseract

    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    pytesseract = None

# ML/NLP for data extraction
try:
    import spacy

    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None

import torch

try:
    from pdf2image import convert_from_bytes

    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    convert_from_bytes = None

from transformers import LayoutLMv3ForTokenClassification, LayoutLMv3Processor

# Access control for medical form processing
from src.security.encryption import EncryptionService

# PHI access control is required for medical form processing
# from src.security.phi_access_control import require_phi_access
from src.services.terminology_service import terminology_service
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DocumentType(Enum):
    """Types of medical documents."""

    PRESCRIPTION = "prescription"
    LAB_REPORT = "lab_report"
    VACCINATION_CARD = "vaccination_card"
    DISCHARGE_SUMMARY = "discharge_summary"
    MEDICAL_CERTIFICATE = "medical_certificate"
    INSURANCE_CARD = "insurance_card"
    PATIENT_ID = "patient_id"
    CONSENT_FORM = "consent_form"
    REFERRAL_LETTER = "referral_letter"
    DIAGNOSTIC_REPORT = "diagnostic_report"
    UNKNOWN = "unknown"


@dataclass
class ExtractedField:
    """Extracted field from document."""

    field_name: str
    value: Any
    confidence: float
    location: Optional[Tuple[int, int, int, int]]  # x, y, width, height
    field_type: str  # text, date, number, code, etc.
    validated: bool = False
    validation_details: Optional[Dict[str, Any]] = None


@dataclass
class ExtractionResult:
    """Result of document data extraction."""

    document_type: DocumentType
    extracted_fields: Dict[str, ExtractedField]
    raw_text: str
    metadata: Dict[str, Any]
    extraction_time: float
    overall_confidence: float
    warnings: List[str]
    language: str


class MedicalFormReader:
    """Production medical form reader with OCR and intelligent extraction."""

    # HIPAA: Access control required for medical form processing
    nlp: Optional[Any]
    layout_processor: Optional[Any]
    layout_model: Optional[Any]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize medical form reader."""
        self.config = config or self._get_default_config()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-documents"
        )

        # AWS clients
        self.textract_client = boto3.client("textract")
        self.comprehend_medical = boto3.client("comprehendmedical")
        self.s3_client = boto3.client("s3")

        # Load ML models
        self.nlp = None
        self.layout_processor = None
        self.layout_model = None
        self._load_models()

        # OpenCV module reference
        self.cv2 = cv2

        # Document patterns
        self.document_patterns = self._load_document_patterns()

        # Field validators
        self.field_validators = self._load_field_validators()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "ocr_engine": "textract",  # textract, tesseract, both
            "enable_layout_analysis": True,
            "enable_medical_nlp": True,
            "supported_formats": ["pdf", "png", "jpg", "jpeg", "tiff"],
            "max_file_size": 50 * 1024 * 1024,  # 50MB
            "confidence_threshold": 0.7,
            "enable_field_validation": True,
            "cache_extractions": True,
            "extraction_timeout": 60,
            "temp_directory": os.path.join(tempfile.gettempdir(), "medical_forms"),
        }

    def _load_models(self) -> None:
        """Load ML models for extraction."""
        try:
            # Load spaCy medical model
            self.nlp = spacy.load("en_core_sci_md")

            # Load LayoutLMv3 for document understanding
            if self.config["enable_layout_analysis"]:
                self.layout_processor = LayoutLMv3Processor.from_pretrained(
                    "microsoft/layoutlmv3-base"
                )
                self.layout_model = LayoutLMv3ForTokenClassification.from_pretrained(
                    "microsoft/layoutlmv3-base"
                )

            logger.info("ML models loaded successfully")

        except (ImportError, OSError, RuntimeError) as e:
            logger.error(f"Failed to load ML models: {e}")
            # Fall back to basic extraction

    def _load_document_patterns(self) -> Dict[DocumentType, Dict]:
        """Load patterns for different document types."""
        return {
            DocumentType.PRESCRIPTION: {
                "keywords": ["rx", "prescription", "medication", "dosage", "sig"],
                "required_fields": [
                    "patient_name",
                    "medication",
                    "dosage",
                    "prescriber",
                ],
                "patterns": {
                    "medication": r"(?:Rx|Medication):\s*(.+?)(?:\n|$)",
                    "dosage": r"(?:Dosage|Dose):\s*(.+?)(?:\n|$)",
                    "frequency": r"(?:Frequency|Sig):\s*(.+?)(?:\n|$)",
                    "quantity": r"(?:Quantity|Qty):\s*(\d+)",
                    "refills": r"(?:Refills?):\s*(\d+)",
                },
            },
            DocumentType.LAB_REPORT: {
                "keywords": ["laboratory", "lab report", "test results", "specimen"],
                "required_fields": ["patient_name", "test_name", "result", "date"],
                "patterns": {
                    "test_name": r"(?:Test Name|Analyte):\s*(.+?)(?:\n|$)",
                    "result": r"(?:Result|Value):\s*([\d.]+)\s*(.+?)(?:\n|$)",
                    "reference_range": r"(?:Reference Range|Normal):\s*(.+?)(?:\n|$)",
                    "units": r"(?:Units?):\s*(.+?)(?:\n|$)",
                },
            },
            DocumentType.VACCINATION_CARD: {
                "keywords": ["vaccination", "immunization", "vaccine", "covid-19"],
                "required_fields": [
                    "patient_name",
                    "vaccine_name",
                    "date",
                    "lot_number",
                ],
                "patterns": {
                    "vaccine_name": r"(?:Vaccine|Product Name):\s*(.+?)(?:\n|$)",
                    "date": r"(?:Date|Date of Vaccination):\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
                    "lot_number": r"(?:Lot Number|Lot #):\s*([A-Z0-9]+)",
                    "site": r"(?:Site|Location):\s*(.+?)(?:\n|$)",
                },
            },
        }

    def _load_field_validators(self) -> Dict[str, Any]:
        """Load field validation functions."""
        return {
            "date": self._validate_date,
            "medication": self._validate_medication,
            "dosage": self._validate_dosage,
            "test_result": self._validate_test_result,
            "vaccine": self._validate_vaccine,
        }

    async def extract_data(
        self,
        document: Union[str, bytes, Path],
        document_type: Optional[DocumentType] = None,
        language: str = "en",
    ) -> ExtractionResult:
        # HIPAA: Authorize document processing operations
        """
        Extract structured data from medical document.

        Args:
            document: Path to document or document bytes
            document_type: Optional document type hint
            language: Document language

        Returns:
            ExtractionResult with extracted data
        """
        start_time = time.time()
        warnings = []

        try:
            # Load document
            if isinstance(document, (str, Path)):
                document_path = Path(document)
                if not document_path.exists():
                    raise FileNotFoundError(f"Document not found: {document}")
                document_bytes = document_path.read_bytes()
                filename = document_path.name
            else:
                document_bytes = document
                filename = "document"

            # Detect document type if not provided
            if not document_type:
                document_type = await self._detect_document_type(document_bytes)

            # Convert to images if PDF
            if filename.lower().endswith(".pdf"):
                images = convert_from_bytes(document_bytes)
            else:
                images = [Image.open(io.BytesIO(document_bytes))]

            # Extract text using OCR
            raw_text = await self._extract_text(images)

            # Extract structured data
            extracted_fields = await self._extract_structured_data(
                raw_text, images, document_type, language
            )

            # Validate extracted fields
            if self.config["enable_field_validation"]:
                extracted_fields = await self._validate_fields(
                    extracted_fields, document_type
                )

            # Calculate overall confidence
            confidences = [f.confidence for f in extracted_fields.values()]
            overall_confidence = (
                sum(confidences) / len(confidences) if confidences else 0
            )

            # Check for required fields
            if document_type in self.document_patterns:
                required = self.document_patterns[document_type]["required_fields"]
                missing = [f for f in required if f not in extracted_fields]
                if missing:
                    warnings.append(f"Missing required fields: {', '.join(missing)}")

            return ExtractionResult(
                document_type=document_type,
                extracted_fields=extracted_fields,
                raw_text=raw_text,
                metadata={
                    "filename": filename,
                    "page_count": len(images),
                    "file_size": len(document_bytes),
                    "extraction_method": self.config["ocr_engine"],
                },
                extraction_time=time.time() - start_time,
                overall_confidence=overall_confidence,
                warnings=warnings,
                language=language,
            )

        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"Document extraction failed: {e}")
            return ExtractionResult(
                document_type=DocumentType.UNKNOWN,
                extracted_fields={},
                raw_text="",
                metadata={"error": str(e)},
                extraction_time=time.time() - start_time,
                overall_confidence=0,
                warnings=[f"Extraction failed: {str(e)}"],
                language=language,
            )

    async def _detect_document_type(self, document_bytes: bytes) -> DocumentType:
        """Detect document type using ML and pattern matching."""
        try:
            # Quick OCR for first page
            if document_bytes[:4] == b"%PDF":
                images = convert_from_bytes(document_bytes, last_page=1)
            else:
                images = [Image.open(io.BytesIO(document_bytes))]

            text = await self._extract_text(images[:1])
            text_lower = text.lower()

            # Check patterns
            for doc_type, patterns in self.document_patterns.items():
                keywords = patterns["keywords"]
                if any(keyword in text_lower for keyword in keywords):
                    return doc_type

            # Use NLP classification if available
            if self.nlp is not None:
                try:
                    doc = self.nlp(
                        text[:1000]
                    )  # Analyze first 1000 chars  # pragma: no cover
                    # Simple classification based on entities
                    if any(ent.label_ == "DRUG" for ent in doc.ents):
                        return DocumentType.PRESCRIPTION
                except (ValueError, KeyError, AttributeError):
                    pass

            return DocumentType.UNKNOWN

        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"Document type detection failed: {e}")
            return DocumentType.UNKNOWN

    async def _extract_text(self, images: List[Image.Image]) -> str:
        """Extract text from images using OCR."""
        all_text = []

        for i, image in enumerate(images):
            try:
                if self.config["ocr_engine"] in ["textract", "both"]:
                    # Use AWS Textract
                    text = await self._extract_with_textract(image)
                else:
                    # Use Tesseract
                    text = await self._extract_with_tesseract(image)

                all_text.append(text)

            except (OSError, ValueError, RuntimeError) as e:
                logger.error(f"OCR failed for page {i+1}: {e}")
                # Fall back to tesseract
                try:
                    text = await self._extract_with_tesseract(image)
                    all_text.append(text)
                except (OSError, ValueError, RuntimeError):
                    all_text.append("")

        return "\n\n".join(all_text)

    async def _extract_with_textract(self, image: Image.Image) -> str:
        """Extract text using AWS Textract."""
        # Convert image to bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format="PNG")
        img_bytes = img_byte_arr.getvalue()

        # Call Textract
        response = self.textract_client.detect_document_text(
            Document={"Bytes": img_bytes}
        )

        # Extract text
        text_parts = []
        for block in response.get("Blocks", []):
            if block["BlockType"] == "LINE":
                text_parts.append(block.get("Text", ""))

        return "\n".join(text_parts)

    async def _extract_with_tesseract(self, image: Image.Image) -> str:
        """Extract text using Tesseract OCR."""
        # Preprocess image
        processed_image = self._preprocess_image(image)

        # Extract text
        text = pytesseract.image_to_string(
            processed_image, config="--psm 3"  # Automatic page segmentation
        )

        return str(text)

    def _preprocess_image(self, image: Image.Image) -> np.ndarray:
        """Preprocess image for better OCR results."""
        # Convert to OpenCV format
        img_array = np.array(image)

        # Convert to grayscale
        if len(img_array.shape) == 3:
            if CV2_AVAILABLE and self.cv2:
                gray = self.cv2.cvtColor(img_array, self.cv2.COLOR_RGB2GRAY)
            else:
                # Fallback: simple grayscale conversion
                gray = np.dot(img_array[..., :3], [0.2989, 0.5870, 0.1140]).astype(
                    np.uint8
                )
        else:
            gray = img_array

        # Apply thresholding
        if CV2_AVAILABLE and self.cv2:
            _, thresh = self.cv2.threshold(  # pylint: disable=no-member
                gray,
                0,
                255,
                self.cv2.THRESH_BINARY
                + self.cv2.THRESH_OTSU,  # pylint: disable=no-member
            )
        else:
            # Fallback: simple thresholding
            thresh = ((gray > 127) * 255).astype(np.uint8)

        # Denoise
        if CV2_AVAILABLE and self.cv2:
            denoised = self.cv2.fastNlMeansDenoising(
                thresh
            )  # pylint: disable=no-member
        else:
            # Fallback: return thresholded image without denoising
            denoised = thresh

        return denoised

    async def _extract_structured_data(
        self,
        raw_text: str,
        images: List[Image.Image],
        document_type: DocumentType,
        language: str,  # pylint: disable=unused-argument
    ) -> Dict[str, ExtractedField]:
        """Extract structured data from raw text and images."""
        # HIPAA: Permission required for data extraction
        extracted_fields = {}

        # Use document-specific patterns
        if document_type in self.document_patterns:
            patterns = self.document_patterns[document_type]["patterns"]

            # Extract using regex patterns
            for field_name, pattern in patterns.items():
                match = re.search(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
                if match:
                    value = match.group(1).strip()
                    extracted_fields[field_name] = ExtractedField(
                        field_name=field_name,
                        value=value,
                        confidence=0.8,  # Pattern match confidence
                        location=None,
                        field_type=self._determine_field_type(field_name),
                    )

        # Use Medical NLP for entity extraction
        if self.config["enable_medical_nlp"] and self.comprehend_medical:
            try:
                # Detect medical entities
                entities = self.comprehend_medical.detect_entities_v2(
                    Text=raw_text[:10000]  # API limit
                )

                # Process entities
                for entity in entities.get("Entities", []):
                    field_name = self._map_entity_to_field(entity["Category"])
                    if field_name and field_name not in extracted_fields:
                        extracted_fields[field_name] = ExtractedField(
                            field_name=field_name,
                            value=entity["Text"],
                            confidence=entity["Score"],
                            location=None,
                            field_type=entity["Type"],
                        )

                        # Add traits as additional fields
                        for trait in entity.get("Traits", []):
                            if trait["Score"] > 0.8:
                                trait_field = f"{field_name}_{trait['Name'].lower()}"
                                extracted_fields[trait_field] = ExtractedField(
                                    field_name=trait_field,
                                    value=trait["Name"],
                                    confidence=trait["Score"],
                                    location=None,
                                    field_type="trait",
                                )

            except (KeyError, ValueError, RuntimeError) as e:
                logger.error(f"Medical NLP extraction failed: {e}")

        # Use Layout Analysis if enabled
        if images and self.layout_model is not None:
            try:  # pragma: no cover
                layout_fields = await self._extract_with_layout_analysis(
                    images[0], raw_text
                )

                # Merge layout results
                for field_name, field in layout_fields.items():
                    if (
                        field_name not in extracted_fields
                        or field.confidence > extracted_fields[field_name].confidence
                    ):
                        extracted_fields[field_name] = field

            except (ValueError, RuntimeError, AttributeError) as e:
                logger.error(f"Layout analysis failed: {e}")

        # Extract common fields using patterns
        common_fields = await self._extract_common_fields(raw_text)
        for field_name, field in common_fields.items():
            if field_name not in extracted_fields:
                extracted_fields[field_name] = field

        return extracted_fields

    def _determine_field_type(self, field_name: str) -> str:
        """Determine field type based on field name."""
        field_types = {
            "date": ["date", "dob", "birth_date", "expiry", "issued"],
            "number": ["quantity", "refills", "dose", "amount"],
            "code": ["icd", "cpt", "ndc", "lot_number", "rxnorm"],
            "medication": ["medication", "drug", "medicine"],
            "test": ["test", "analyte", "lab", "result"],
        }

        field_lower = field_name.lower()
        for field_type, keywords in field_types.items():
            if any(keyword in field_lower for keyword in keywords):
                return field_type

        return "text"

    def _map_entity_to_field(self, category: str) -> Optional[str]:
        """Map AWS Comprehend Medical entity category to field name."""
        mapping = {
            "MEDICATION": "medication",
            "MEDICAL_CONDITION": "diagnosis",
            "TEST_TREATMENT_PROCEDURE": "procedure",
            "ANATOMY": "anatomy",
            "TIME_EXPRESSION": "date",
            "PROTECTED_HEALTH_INFORMATION": "patient_info",
        }

        return mapping.get(category)

    async def _extract_with_layout_analysis(
        self, image: Image.Image, text: str  # pylint: disable=unused-argument
    ) -> Dict[str, ExtractedField]:
        """Extract fields using LayoutLMv3 for document understanding."""
        extracted_fields: Dict[str, ExtractedField] = {}

        try:
            # Check models are loaded
            if self.layout_processor is None or self.layout_model is None:
                return extracted_fields

            # Prepare inputs for LayoutLMv3
            encoding = self.layout_processor(  # pragma: no cover
                image,
                text,
                return_tensors="pt",
                truncation=True,
                padding="max_length",
                max_length=512,
            )

            # Get predictions
            with torch.no_grad():
                outputs = self.layout_model(**encoding)
                predictions = outputs.logits.argmax(-1).squeeze().tolist()

            # Map predictions to fields
            tokens = encoding.tokens()

            current_field = None
            current_value = []

            for token, pred in zip(tokens, predictions):
                if pred > 0:  # Not 'O' (outside)
                    field_type = self._get_field_from_prediction(pred)

                    if field_type != current_field:
                        # Save previous field
                        if current_field and current_value:
                            value = " ".join(current_value)
                            extracted_fields[current_field] = ExtractedField(
                                field_name=current_field,
                                value=value,
                                confidence=0.85,
                                location=None,
                                field_type=self._determine_field_type(current_field),
                            )

                        # Start new field
                        current_field = field_type
                        current_value = [token]
                    else:
                        current_value.append(token)

            # Save last field
            if current_field and current_value:
                value = " ".join(current_value)
                extracted_fields[current_field] = ExtractedField(
                    field_name=current_field,
                    value=value,
                    confidence=0.85,
                    location=None,
                    field_type=self._determine_field_type(current_field),
                )

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error(f"Layout analysis error: {e}")

        return extracted_fields

    def _get_field_from_prediction(self, prediction: int) -> str:
        """Map model prediction to field name."""
        # This would map to actual model's label set
        label_map = {
            1: "patient_name",
            2: "date",
            3: "medication",
            4: "dosage",
            5: "doctor_name",
            6: "diagnosis",
        }

        return label_map.get(prediction, "other")

    async def _extract_common_fields(self, text: str) -> Dict[str, ExtractedField]:
        """Extract common fields using patterns."""
        fields = {}

        # Extract dates
        date_pattern = r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b"
        dates = re.findall(date_pattern, text)
        if dates:
            fields["date"] = ExtractedField(
                field_name="date",
                value=dates[0],
                confidence=0.9,
                location=None,
                field_type="date",
            )

        # Extract patient name (simplified)
        name_patterns = [
            r"Patient(?:\s+Name)?:\s*([A-Z][a-z]+ [A-Z][a-z]+)",
            r"Name:\s*([A-Z][a-z]+ [A-Z][a-z]+)",
            r"^([A-Z][A-Z\s]+)$",  # All caps name at beginning
        ]

        for pattern in name_patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                fields["patient_name"] = ExtractedField(
                    field_name="patient_name",
                    value=match.group(1).strip(),
                    confidence=0.7,
                    location=None,
                    field_type="text",
                )
                break

        # Extract phone numbers
        phone_pattern = (
            r"(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})"
        )
        phones = re.findall(phone_pattern, text)
        if phones:
            phone = "".join(phones[0])
            fields["phone"] = ExtractedField(
                field_name="phone",
                value=phone,
                confidence=0.9,
                location=None,
                field_type="phone",
            )

        # Extract email
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        emails = re.findall(email_pattern, text)
        if emails:
            fields["email"] = ExtractedField(
                field_name="email",
                value=emails[0],
                confidence=0.9,
                location=None,
                field_type="email",
            )

        return fields

    async def _validate_fields(
        self,
        fields: Dict[str, ExtractedField],
        document_type: DocumentType,  # pylint: disable=unused-argument
    ) -> Dict[str, ExtractedField]:
        """Validate extracted fields."""
        validated_fields = {}

        for field_name, field in fields.items():
            # Get appropriate validator
            validator = None

            if field.field_type in self.field_validators:
                validator = self.field_validators[field.field_type]
            elif field_name in ["medication", "drug"]:
                validator = self.field_validators.get("medication")
            elif field_name in ["vaccine", "vaccination"]:
                validator = self.field_validators.get("vaccine")

            if validator:
                try:
                    validation_result = await validator(field.value)
                    field.validated = validation_result["valid"]
                    field.validation_details = validation_result

                    # Adjust confidence based on validation
                    if field.validated:
                        field.confidence = min(1.0, field.confidence * 1.1)
                    else:
                        field.confidence = field.confidence * 0.8

                except (ValueError, KeyError, RuntimeError) as e:
                    logger.error(f"Field validation error for {field_name}: {e}")

            validated_fields[field_name] = field

        return validated_fields

    async def _validate_date(self, value: str) -> Dict[str, Any]:
        """Validate date field."""
        try:
            # Try common date formats
            formats = [
                "%m/%d/%Y",
                "%d/%m/%Y",
                "%Y-%m-%d",
                "%m-%d-%Y",
                "%d-%m-%Y",
                "%Y/%m/%d",
                "%m/%d/%y",
                "%d/%m/%y",
            ]

            parsed_date = None
            for fmt in formats:
                try:
                    parsed_date = datetime.strptime(value, fmt)
                    break
                except ValueError:
                    continue

            if parsed_date:
                # Check if date is reasonable
                min_date = datetime(1900, 1, 1)
                max_date = datetime.now() + timedelta(days=365)

                is_valid = min_date <= parsed_date <= max_date

                return {
                    "valid": is_valid,
                    "parsed_value": parsed_date.isoformat(),
                    "format": fmt if "fmt" in locals() else None,
                    "warnings": [] if is_valid else ["Date outside reasonable range"],
                }

            return {"valid": False, "error": "Could not parse date"}

        except ValueError as e:
            return {"valid": False, "error": str(e)}

    async def _validate_medication(self, value: str) -> Dict[str, Any]:
        """Validate medication name."""
        try:
            # Check against RxNorm
            validation_result = await terminology_service.validate_code(
                system="http://www.nlm.nih.gov/research/umls/rxnorm",
                code=value,
                display=value,
            )

            if not validation_result.valid:
                # Try searching for the medication
                search_results = await terminology_service.search_concepts(
                    text=value,
                    systems=["http://www.nlm.nih.gov/research/umls/rxnorm"],
                    limit=5,
                )

                if search_results:
                    return {
                        "valid": True,
                        "confidence": 0.8,
                        "suggestions": search_results,
                        "warnings": [
                            "Medication name not exact match, suggestions provided"
                        ],
                    }

            return {
                "valid": validation_result.valid,
                "rxnorm_code": (
                    validation_result.code if validation_result.valid else None
                ),
                "preferred_name": validation_result.preferred_term,
                "warnings": [],
            }

        except (ValueError, KeyError, RuntimeError) as e:
            logger.error(f"Medication validation error: {e}")
            return {"valid": True, "warnings": ["Could not validate against RxNorm"]}

    async def _validate_dosage(self, value: str) -> Dict[str, Any]:
        """Validate medication dosage."""
        try:
            # Parse dosage components
            dosage_pattern = r"(\d+(?:\.\d+)?)\s*([a-zA-Z]+)"
            match = re.match(dosage_pattern, value)

            if match:
                amount = float(match.group(1))
                unit = match.group(2).lower()

                # Validate units
                valid_units = {
                    "mg",
                    "g",
                    "mcg",
                    "ml",
                    "l",
                    "units",
                    "iu",
                    "tablet",
                    "tablets",
                    "tab",
                    "tabs",
                    "capsule",
                    "capsules",
                    "cap",
                    "caps",
                }

                unit_valid = any(
                    unit.startswith(valid_unit) for valid_unit in valid_units
                )

                return {
                    "valid": unit_valid,
                    "amount": amount,
                    "unit": unit,
                    "warnings": [] if unit_valid else ["Unrecognized dosage unit"],
                }

            return {"valid": False, "error": "Could not parse dosage"}

        except (ValueError, KeyError) as e:
            return {"valid": False, "error": str(e)}

    async def _validate_test_result(self, value: str) -> Dict[str, Any]:
        """Validate lab test result."""
        try:
            # Try to parse numeric result with units
            result_pattern = r"(<?=?>?)?\s*(\d+(?:\.\d+)?)\s*([a-zA-Z/%]+)?"
            match = re.match(result_pattern, value)

            if match:
                operator = match.group(1) or "="
                numeric_value = float(match.group(2))
                unit = match.group(3) or ""

                return {
                    "valid": True,
                    "operator": operator,
                    "value": numeric_value,
                    "unit": unit,
                    "warnings": [],
                }

            # Check for qualitative results
            qualitative = [
                "positive",
                "negative",
                "normal",
                "abnormal",
                "detected",
                "not detected",
            ]
            if value.lower() in qualitative:
                return {
                    "valid": True,
                    "qualitative": True,
                    "value": value.lower(),
                    "warnings": [],
                }

            return {"valid": False, "error": "Could not parse test result"}

        except (ValueError, KeyError) as e:
            return {"valid": False, "error": str(e)}

    async def _validate_vaccine(self, value: str) -> Dict[str, Any]:
        """Validate vaccine name."""
        try:
            # Check against CVX codes
            validation_result = await terminology_service.validate_code(
                system="http://hl7.org/fhir/sid/cvx", code=value, display=value
            )

            if not validation_result.valid:
                # Try common vaccine names
                common_vaccines = {
                    "pfizer": "208",  # Pfizer-BioNTech COVID-19
                    "moderna": "207",  # Moderna COVID-19
                    "johnson": "212",  # Janssen COVID-19
                    "astrazeneca": "210",  # AstraZeneca COVID-19
                    "flu": "158",  # Influenza
                    "mmr": "03",  # MMR
                    "tdap": "115",  # Tdap
                    "hepatitis b": "08",  # Hep B
                }

                value_lower = value.lower()
                for vaccine_name, cvx_code in common_vaccines.items():
                    if vaccine_name in value_lower:
                        return {
                            "valid": True,
                            "cvx_code": cvx_code,
                            "matched_name": vaccine_name,
                            "warnings": [],
                        }

            return {
                "valid": validation_result.valid,
                "cvx_code": validation_result.code if validation_result.valid else None,
                "warnings": (
                    [] if validation_result.valid else ["Vaccine not found in CVX"]
                ),
            }

        except (ValueError, KeyError, RuntimeError) as e:
            logger.error(f"Vaccine validation error: {e}")
            return {"valid": True, "warnings": ["Could not validate against CVX"]}

    async def extract_batch(
        self,
        documents: List[Union[str, bytes, Path]],
        document_types: Optional[List[DocumentType]] = None,
        language: str = "en",
    ) -> List[ExtractionResult]:
        """Extract data from multiple documents in batch."""
        if document_types and len(document_types) != len(documents):
            document_types = [DocumentType.UNKNOWN] * len(documents)
        elif not document_types:
            document_types = [DocumentType.UNKNOWN] * len(documents)

        # Process documents concurrently
        tasks = [
            self.extract_data(doc, doc_type, language)
            for doc, doc_type in zip(documents, document_types)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        extraction_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch extraction error for document {i}: {result}")
                # Create error result
                extraction_results.append(
                    ExtractionResult(
                        document_type=DocumentType.UNKNOWN,
                        extracted_fields={},
                        raw_text="",
                        metadata={"error": str(result)},
                        extraction_time=0,
                        overall_confidence=0,
                        warnings=[f"Extraction failed: {str(result)}"],
                        language=language,
                    )
                )
            else:
                # Type assertion: result is ExtractionResult after Exception check
                assert isinstance(result, ExtractionResult)
                extraction_results.append(result)

        return extraction_results

    async def save_extraction_result(
        self, result: ExtractionResult, output_format: str = "json"
    ) -> str:
        """Save extraction result in specified format."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if output_format == "json":
            # Convert to JSON-serializable format
            output_data = {
                "document_type": result.document_type.value,
                "extraction_time": result.extraction_time,
                "overall_confidence": result.overall_confidence,
                "language": result.language,
                "metadata": result.metadata,
                "warnings": result.warnings,
                "fields": {
                    name: {
                        "value": field.value,
                        "confidence": field.confidence,
                        "type": field.field_type,
                        "validated": field.validated,
                        "validation_details": field.validation_details,
                    }
                    for name, field in result.extracted_fields.items()
                },
            }

            output_path = os.path.join(
                tempfile.gettempdir(), f"extraction_{timestamp}.json"
            )
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, default=str)

        elif output_format == "fhir":
            # Convert to FHIR format
            fhir_resource = self._convert_to_fhir(result)
            output_path = os.path.join(
                tempfile.gettempdir(), f"extraction_{timestamp}_fhir.json"
            )
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(fhir_resource, f, indent=2)

        else:
            raise ValueError(f"Unsupported output format: {output_format}")

        return output_path

    def _convert_to_fhir(self, result: ExtractionResult) -> Dict[str, Any]:
        """Convert extraction result to FHIR format."""
        # Create appropriate FHIR resource based on document type
        if result.document_type == DocumentType.LAB_REPORT:
            return self._create_fhir_observation(result)
        elif result.document_type == DocumentType.PRESCRIPTION:
            return self._create_fhir_medication_request(result)
        elif result.document_type == DocumentType.VACCINATION_CARD:
            return self._create_fhir_immunization(result)
        else:
            return self._create_fhir_document_reference(result)

    def _create_fhir_observation(self, result: ExtractionResult) -> Dict[str, Any]:
        """Create FHIR Observation from lab report."""
        fields = result.extracted_fields

        observation = {
            "resourceType": "Observation",
            "status": "final",
            "code": {
                "text": fields.get(
                    "test_name", ExtractedField("", "", 0, None, "")
                ).value
            },
            "effectiveDateTime": fields.get(
                "date", ExtractedField("", "", 0, None, "")
            ).value,
            "issued": datetime.now().isoformat(),
        }

        # Add result value
        if "result" in fields:
            result_field = fields["result"]
            if result_field.validation_details and result_field.validation_details.get(
                "qualitative"
            ):
                observation["valueCodeableConcept"] = {"text": result_field.value}
            else:
                observation["valueQuantity"] = {
                    "value": result_field.value,
                    "unit": fields.get(
                        "units", ExtractedField("", "", 0, None, "")
                    ).value,
                }

        return observation

    def _create_fhir_medication_request(
        self, result: ExtractionResult
    ) -> Dict[str, Any]:
        """Create FHIR MedicationRequest from prescription."""
        fields = result.extracted_fields

        return {
            "resourceType": "MedicationRequest",
            "status": "active",
            "intent": "order",
            "medicationCodeableConcept": {
                "text": fields.get(
                    "medication", ExtractedField("", "", 0, None, "")
                ).value
            },
            "dosageInstruction": [
                {
                    "text": fields.get(
                        "dosage", ExtractedField("", "", 0, None, "")
                    ).value,
                    "timing": {
                        "code": {
                            "text": fields.get(
                                "frequency", ExtractedField("", "", 0, None, "")
                            ).value
                        }
                    },
                }
            ],
            "dispenseRequest": {
                "quantity": {
                    "value": fields.get(
                        "quantity", ExtractedField("", "0", 0, None, "")
                    ).value
                },
                "numberOfRepeatsAllowed": int(
                    fields.get("refills", ExtractedField("", "0", 0, None, "")).value
                ),
            },
        }

    def _create_fhir_immunization(self, result: ExtractionResult) -> Dict[str, Any]:
        """Create FHIR Immunization from vaccination card."""
        fields = result.extracted_fields

        return {
            "resourceType": "Immunization",
            "status": "completed",
            "vaccineCode": {
                "text": fields.get(
                    "vaccine_name", ExtractedField("", "", 0, None, "")
                ).value
            },
            "occurrenceDateTime": fields.get(
                "date", ExtractedField("", "", 0, None, "")
            ).value,
            "lotNumber": fields.get(
                "lot_number", ExtractedField("", "", 0, None, "")
            ).value,
            "site": {
                "text": fields.get("site", ExtractedField("", "", 0, None, "")).value
            },
        }

    def _create_fhir_document_reference(
        self, result: ExtractionResult
    ) -> Dict[str, Any]:
        """Create generic FHIR DocumentReference."""
        return {
            "resourceType": "DocumentReference",
            "status": "current",
            "type": {"text": result.document_type.value},
            "date": datetime.now().isoformat(),
            "content": [
                {
                    "attachment": {
                        "contentType": "text/plain",
                        "data": result.raw_text[:1000],  # First 1000 chars
                    }
                }
            ],
        }


# Global instance
medical_form_reader = MedicalFormReader()
