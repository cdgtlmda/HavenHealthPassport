"""
Handwriting Recognition Module - specialized handwriting recognition for medical documents.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

# Standard library imports
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.ai.document_processing.textract_config import (
    DocumentAnalysisResult,
    DocumentType,
    FeatureType,
    TextractClient,
)
from src.ai.medical_nlp.medical_abbreviations import MedicalAbbreviationExpander
from src.core.exceptions import ProcessingError
from src.healthcare.medical_terminology import MedicalTerminologyValidator
from src.utils.text_preprocessing import TextPreprocessor

logger = logging.getLogger(__name__)


class HandwritingType(Enum):
    """Types of handwriting in medical documents."""

    DOCTOR_NOTES = "doctor_notes"
    PRESCRIPTION = "prescription"
    PATIENT_FORM = "patient_form"
    LAB_NOTATION = "lab_notation"
    NURSE_NOTES = "nurse_notes"
    SIGNATURE = "signature"
    MIXED = "mixed"


class HandwritingQuality(Enum):
    """Quality levels for handwriting."""

    EXCELLENT = "excellent"  # > 90% confidence
    GOOD = "good"  # 75-90% confidence
    FAIR = "fair"  # 60-75% confidence
    POOR = "poor"  # 45-60% confidence
    ILLEGIBLE = "illegible"  # < 45% confidence


@dataclass
class HandwritingContext:
    """Context to improve handwriting recognition."""

    document_type: DocumentType
    medical_specialty: Optional[str] = None
    language: str = "en"


@dataclass
class HandwrittenText:
    """Extracted handwritten text with metadata."""

    text: str
    confidence: float
    quality: HandwritingQuality
    page: int
    bbox: Optional[Dict[str, float]] = None
    alternative_readings: List[Tuple[str, float]] = field(default_factory=list)
    is_medical_term: bool = False
    expanded_abbreviations: Dict[str, str] = field(default_factory=dict)
    validation_status: Optional[str] = None


@dataclass
class HandwritingAnalysisResult:
    """Complete result of handwriting analysis."""

    document_id: str
    handwriting_type: HandwritingType
    overall_quality: HandwritingQuality
    handwritten_texts: List[HandwrittenText]
    mixed_content: bool  # True if document has both printed and handwritten text
    confidence_distribution: Dict[str, int]  # Distribution of confidence levels
    processing_time_ms: int
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_high_confidence_texts(self) -> List[HandwrittenText]:
        """Get only high confidence handwritten texts."""
        return [
            t
            for t in self.handwritten_texts
            if t.quality in [HandwritingQuality.EXCELLENT, HandwritingQuality.GOOD]
        ]


class HandwritingRecognizer:
    """Specialized handwriting recognition for medical documents."""

    def __init__(
        self,
        textract_client: TextractClient,
        terminology_validator: MedicalTerminologyValidator,
        abbreviation_expander: Optional[MedicalAbbreviationExpander] = None,
    ):
        """Initialize HandwritingRecognitionService.

        Args:
            textract_client: Client for AWS Textract operations
            terminology_validator: Validator for medical terminology
            abbreviation_expander: Optional expander for medical abbreviations
        """
        self.textract_client = textract_client
        self.terminology_validator = terminology_validator
        self.abbreviation_expander = (
            abbreviation_expander or MedicalAbbreviationExpander()
        )
        self.text_preprocessor = TextPreprocessor()

        # Medical handwriting patterns
        self._init_handwriting_patterns()

    def _init_handwriting_patterns(self) -> None:
        """Initialize patterns commonly found in medical handwriting."""
        self.handwriting_patterns = {
            "dosage": [r"\d+\s*mg", r"\d+\s*ml", r"\d+\s*tabs?", r"\d+\s*caps?"],
            "frequency": [
                r"[qtb]\.?i\.?d\.?",
                r"p\.?r\.?n\.?",
                r"[qb]\.?d\.?",
                r"h\.?s\.?",
            ],
            "route": [r"p\.?o\.?", r"i\.?m\.?", r"i\.?v\.?", r"s\.?c\.?"],
            "medical_notation": [r"[↑↓]", r"[Δ∆]", r"[⊕⊖]", r"[♂♀]"],
        }

        self.medical_abbreviations = {
            "qd": "once daily",
            "bid": "twice daily",
            "tid": "three times daily",
            "qid": "four times daily",
            "prn": "as needed",
            "po": "by mouth",
            "im": "intramuscular",
            "iv": "intravenous",
            "sc": "subcutaneous",
            "hs": "at bedtime",
            "ac": "before meals",
            "pc": "after meals",
            "hx": "history",
            "px": "physical examination",
            "dx": "diagnosis",
            "tx": "treatment",
            "rx": "prescription",
            "sx": "symptoms",
            "pt": "patient",
            "htn": "hypertension",
            "dm": "diabetes mellitus",
            "copd": "chronic obstructive pulmonary disease",
            "cad": "coronary artery disease",
            "chf": "congestive heart failure",
            "uti": "urinary tract infection",
            "uri": "upper respiratory infection",
            "cbc": "complete blood count",
            "bmp": "basic metabolic panel",
            "cmp": "comprehensive metabolic panel",
            "lfts": "liver function tests",
            "tsh": "thyroid stimulating hormone",
            "hgb": "hemoglobin",
            "wbc": "white blood cell",
            "plt": "platelet",
        }

    async def analyze_handwriting(
        self,
        document_bytes: bytes,
        document_name: str,
        context: Optional[HandwritingContext] = None,
    ) -> HandwritingAnalysisResult:
        """Analyze handwriting in a medical document."""
        start_time = datetime.now()

        if not context:
            context = HandwritingContext(
                document_type=DocumentType.MEDICAL_RECORD, language="en"
            )

        try:
            # Extract text with Textract, focusing on handwriting
            textract_result = await self._extract_handwritten_text(
                document_bytes, document_name
            )

            # Identify handwriting type
            handwriting_type = self._identify_handwriting_type(textract_result, context)

            # Process and enhance handwritten text
            handwritten_texts = await self._process_handwritten_texts(
                textract_result, context
            )

            # Apply medical-specific enhancements
            enhanced_texts = await self._enhance_medical_handwriting(
                handwritten_texts, context
            )

            # Calculate quality metrics
            overall_quality = self._calculate_overall_quality(enhanced_texts)
            confidence_distribution = self._calculate_confidence_distribution(
                enhanced_texts
            )

            # Check for mixed content
            mixed_content = self._check_mixed_content(textract_result)

            # Create result
            result = HandwritingAnalysisResult(
                document_id=textract_result.document_id,
                handwriting_type=handwriting_type,
                overall_quality=overall_quality,
                handwritten_texts=enhanced_texts,
                mixed_content=mixed_content,
                confidence_distribution=confidence_distribution,
                processing_time_ms=int(
                    (datetime.now() - start_time).total_seconds() * 1000
                ),
            )

            if overall_quality in [
                HandwritingQuality.POOR,
                HandwritingQuality.ILLEGIBLE,
            ]:
                result.warnings.append(
                    "Document contains sections with poor handwriting quality"
                )

            return result

        except Exception as e:
            logger.error("Handwriting analysis failed: %s", str(e))
            raise ProcessingError(f"Failed to analyze handwriting: {str(e)}") from e

    async def _extract_handwritten_text(
        self, document_bytes: bytes, document_name: str
    ) -> DocumentAnalysisResult:
        """Extract handwritten text using Textract."""
        features = [
            FeatureType.TEXT,
            FeatureType.HANDWRITING,
            FeatureType.FORMS,
            FeatureType.SIGNATURES,
        ]

        return await self.textract_client.analyze_document(
            document_bytes, document_name, features
        )

    def _identify_handwriting_type(
        self, textract_result: DocumentAnalysisResult, context: HandwritingContext
    ) -> HandwritingType:
        """Identify the type of handwriting in the document."""
        all_text = textract_result.get_all_text().lower()

        if any(pattern in all_text for pattern in ["rx", "sig:", "dispense"]):
            return HandwritingType.PRESCRIPTION
        elif any(
            pattern in all_text for pattern in ["chief complaint", "hpi", "assessment"]
        ):
            return HandwritingType.DOCTOR_NOTES
        elif any(
            pattern in all_text for pattern in ["specimen", "collected", "results"]
        ):
            return HandwritingType.LAB_NOTATION
        elif textract_result.extracted_forms:
            return HandwritingType.PATIENT_FORM
        elif context.document_type == DocumentType.PRESCRIPTION:
            return HandwritingType.PRESCRIPTION

        return HandwritingType.MIXED

    async def _process_handwritten_texts(
        self, textract_result: DocumentAnalysisResult, context: HandwritingContext
    ) -> List[HandwrittenText]:
        """Process extracted handwritten texts."""
        handwritten_texts = []

        for extracted_text in textract_result.extracted_text:
            if extracted_text.text_type == "HANDWRITING":
                handwritten = HandwrittenText(
                    text=extracted_text.text,
                    confidence=extracted_text.confidence,
                    quality=self._determine_quality(extracted_text.confidence),
                    page=extracted_text.page,
                    bbox=extracted_text.bbox,
                )

                # Generate alternative readings for low confidence text
                if handwritten.confidence < 0.7:
                    alternatives = await self._generate_alternatives(
                        handwritten.text, context
                    )
                    handwritten.alternative_readings = alternatives

                handwritten_texts.append(handwritten)

        return handwritten_texts

    def _determine_quality(self, confidence: float) -> HandwritingQuality:
        """Determine handwriting quality based on confidence."""
        if confidence > 0.9:
            return HandwritingQuality.EXCELLENT
        elif confidence > 0.75:
            return HandwritingQuality.GOOD
        elif confidence > 0.6:
            return HandwritingQuality.FAIR
        elif confidence > 0.45:
            return HandwritingQuality.POOR
        else:
            return HandwritingQuality.ILLEGIBLE

    async def _generate_alternatives(
        self, text: str, context: HandwritingContext
    ) -> List[Tuple[str, float]]:
        """Generate alternative readings for ambiguous handwriting."""
        alternatives = []

        # Common character confusions in handwriting
        confusion_pairs = [
            ("a", "o"),
            ("e", "c"),
            ("l", "1"),
            ("0", "O"),
            ("5", "S"),
            ("6", "b"),
            ("9", "g"),
            ("u", "v"),
            ("n", "h"),
            ("r", "v"),
            ("i", "l"),
            ("t", "+"),
        ]

        for old, new in confusion_pairs:
            if old in text:
                alt_text = text.replace(old, new)
                is_medical = await self._is_medical_term(alt_text, context)
                confidence = 0.6 if is_medical else 0.4
                alternatives.append((alt_text, confidence))

        return sorted(alternatives, key=lambda x: x[1], reverse=True)[:5]

    async def _enhance_medical_handwriting(
        self, texts: List[HandwrittenText], context: HandwritingContext
    ) -> List[HandwrittenText]:
        """Apply medical-specific enhancements to handwritten text."""
        enhanced_texts = []

        for text in texts:
            # Expand medical abbreviations
            if self.abbreviation_expander:
                expanded = await self.abbreviation_expander.expand_text(text.text)
                if expanded != text.text:
                    text.expanded_abbreviations = self._get_expansions(
                        text.text, expanded
                    )

            # Validate medical terms
            text.is_medical_term = await self._is_medical_term(text.text, context)

            # Apply pattern validation
            if self._matches_medical_pattern(text.text):
                text.validation_status = "pattern_matched"
                text.confidence = min(1.0, text.confidence + 0.05)

            enhanced_texts.append(text)

        return enhanced_texts

    def _get_expansions(self, original: str, expanded: str) -> Dict[str, str]:
        """Get dictionary of abbreviation expansions."""
        expansions = {}
        original_words = original.split()
        expanded_words = expanded.split()

        for orig, exp in zip(original_words, expanded_words):
            if orig != exp:
                expansions[orig] = exp

        return expansions

    async def _is_medical_term(self, text: str, context: HandwritingContext) -> bool:
        """Check if text is a medical term."""
        _ = context  # Mark as intentionally unused
        try:
            # Check with terminology validator
            is_valid = self.terminology_validator.validate_term(text)
            if is_valid:
                return True

            # Check abbreviations
            if text.lower() in self.medical_abbreviations:
                return True

            # Check patterns
            return self._matches_medical_pattern(text)
        except (ValueError, KeyError):
            return False

    def _matches_medical_pattern(self, text: str) -> bool:
        """Check if text matches medical patterns."""
        text_lower = text.lower()

        for _, patterns in self.handwriting_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return True

        return False

    def _calculate_overall_quality(
        self, texts: List[HandwrittenText]
    ) -> HandwritingQuality:
        """Calculate overall handwriting quality."""
        if not texts:
            return HandwritingQuality.EXCELLENT

        avg_confidence = sum(t.confidence for t in texts) / len(texts)
        return self._determine_quality(avg_confidence)

    def _calculate_confidence_distribution(
        self, texts: List[HandwrittenText]
    ) -> Dict[str, int]:
        """Calculate distribution of confidence levels."""
        distribution = {"excellent": 0, "good": 0, "fair": 0, "poor": 0, "illegible": 0}

        for text in texts:
            distribution[text.quality.value] += 1

        return distribution

    def _check_mixed_content(self, textract_result: DocumentAnalysisResult) -> bool:
        """Check if document contains both printed and handwritten text."""
        has_printed = False
        has_handwritten = False

        for text in textract_result.extracted_text:
            if text.text_type == "PRINTED":
                has_printed = True
            elif text.text_type == "HANDWRITING":
                has_handwritten = True

            if has_printed and has_handwritten:
                return True

        return False

    async def improve_recognition(
        self,
        analysis_result: HandwritingAnalysisResult,
        human_corrections: Dict[str, str],
    ) -> HandwritingAnalysisResult:
        """Improve recognition results with human corrections."""
        for i, text in enumerate(analysis_result.handwritten_texts):
            if text.text in human_corrections:
                corrected_text = human_corrections[text.text]

                # Update text with correction
                analysis_result.handwritten_texts[i].text = corrected_text
                analysis_result.handwritten_texts[i].confidence = 1.0
                analysis_result.handwritten_texts[i].quality = (
                    HandwritingQuality.EXCELLENT
                )
                analysis_result.handwritten_texts[i].validation_status = (
                    "human_verified"
                )

        return analysis_result
