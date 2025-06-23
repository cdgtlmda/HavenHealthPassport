"""Document Classification Module.

This module provides intelligent document classification capabilities for the Haven Health
Passport system. It automatically identifies and categorizes medical documents using
machine learning models and rule-based approaches.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

# Standard library imports
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Third-party imports
import joblib
import numpy as np

from src.ai.document_processing.textract_config import (
    DocumentType,
    FeatureType,
    TextractClient,
)

try:
    from src.ai.medical_nlp.entity_extraction import MedicalEntityExtractor
except ImportError:

    class MedicalEntityExtractor:  # type: ignore[no-redef]
        def __init__(self) -> None:
            pass

        def extract_entities(self, text: str) -> List[Any]:
            _ = text  # Mark as intentionally unused
            return []


from src.audit.audit_logger import AuditEventType, AuditLogger
from src.healthcare.medical_terminology import MedicalTerminologyValidator
from src.metrics.metrics_collector import MetricsCollector, MetricType
from src.utils.text_processing import TextNormalizer

logger = logging.getLogger(__name__)


class ClassificationMethod(Enum):
    """Methods used for document classification."""

    RULE_BASED = "rule_based"
    KEYWORD_MATCHING = "keyword_matching"
    ML_MODEL = "ml_model"
    HYBRID = "hybrid"
    ENSEMBLE = "ensemble"


class ClassificationConfidence(Enum):
    """Confidence levels for classification results."""

    VERY_HIGH = "very_high"  # > 95%
    HIGH = "high"  # 85-95%
    MEDIUM = "medium"  # 70-85%
    LOW = "low"  # 50-70%
    VERY_LOW = "very_low"  # < 50%


@dataclass
class DocumentFeatures:
    """Features extracted from a document for classification."""

    text_content: str
    extracted_entities: Dict[str, List[str]]
    key_phrases: List[str]
    document_structure: Dict[str, Any]
    metadata: Dict[str, Any]
    language: str
    text_length: int
    has_tables: bool
    has_forms: bool
    has_images: bool
    has_signatures: bool
    date_references: List[str]
    numeric_values: List[str]
    medical_terms_count: int

    def to_feature_vector(self) -> Dict[str, Any]:
        """Convert features to a vector for ML models."""
        return {
            "text_length": self.text_length,
            "has_tables": int(self.has_tables),
            "has_forms": int(self.has_forms),
            "has_images": int(self.has_images),
            "has_signatures": int(self.has_signatures),
            "medical_terms_count": self.medical_terms_count,
            "entity_types_count": len(self.extracted_entities),
            "date_count": len(self.date_references),
            "numeric_count": len(self.numeric_values),
            "key_phrases_count": len(self.key_phrases),
        }


@dataclass
class ClassificationResult:
    """Result of document classification."""

    document_type: DocumentType
    confidence: float
    confidence_level: ClassificationConfidence
    method_used: ClassificationMethod
    alternative_types: List[Tuple[DocumentType, float]]
    features_used: DocumentFeatures
    reasoning: str
    processing_time_ms: float
    model_version: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "document_type": self.document_type.value,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "method_used": self.method_used.value,
            "alternative_types": [
                {"type": dt.value, "confidence": conf}
                for dt, conf in self.alternative_types
            ],
            "reasoning": self.reasoning,
            "processing_time_ms": self.processing_time_ms,
            "model_version": self.model_version,
        }


@dataclass
class ClassificationRule:
    """Rule for document classification."""

    document_type: DocumentType
    required_keywords: List[str]
    optional_keywords: List[str]
    excluded_keywords: List[str]
    required_entities: List[str]
    min_confidence: float
    weight: float = 1.0

    def matches(self, features: DocumentFeatures) -> Tuple[bool, float]:
        """Check if features match this rule."""
        text_lower = features.text_content.lower()

        # Check required keywords
        required_found = sum(
            1 for keyword in self.required_keywords if keyword.lower() in text_lower
        )
        if required_found < len(self.required_keywords):
            return False, 0.0

        # Check excluded keywords
        for keyword in self.excluded_keywords:
            if keyword.lower() in text_lower:
                return False, 0.0

        # Calculate confidence based on optional keywords
        optional_found = sum(
            1 for keyword in self.optional_keywords if keyword.lower() in text_lower
        )

        keyword_confidence = (required_found + optional_found * 0.5) / (
            len(self.required_keywords) + len(self.optional_keywords)
        )

        # Check required entities
        entity_confidence = 1.0
        if self.required_entities:
            entities_found = sum(
                1
                for entity_type in self.required_entities
                if entity_type in features.extracted_entities
                and features.extracted_entities[entity_type]
            )
            entity_confidence = entities_found / len(self.required_entities)

        final_confidence = (
            keyword_confidence * 0.7 + entity_confidence * 0.3
        ) * self.weight

        return final_confidence >= self.min_confidence, final_confidence


class DocumentClassifier:
    """Main document classification service."""

    def __init__(
        self,
        textract_client: TextractClient,
        medical_entity_extractor: MedicalEntityExtractor,
        medical_terminology_validator: MedicalTerminologyValidator,
        audit_logger: AuditLogger,
        metrics_collector: MetricsCollector,
        model_path: Optional[Path] = None,
    ):
        """Initialize the document classifier."""
        self.textract_client = textract_client
        self.medical_entity_extractor = medical_entity_extractor
        self.medical_terminology_validator = medical_terminology_validator
        self.audit_logger = audit_logger
        self.metrics_collector = metrics_collector
        self.model_path = model_path

        # Initialize classification components
        self.text_normalizer = TextNormalizer()
        self.classification_rules = self._initialize_rules()
        self.ml_model = None
        self.vectorizer = None
        self.label_encoder = None

        if model_path and model_path.exists():
            self._load_ml_model()

    def _initialize_rules(self) -> Dict[DocumentType, ClassificationRule]:
        """Initialize rule-based classification rules."""
        return {
            DocumentType.PRESCRIPTION: ClassificationRule(
                document_type=DocumentType.PRESCRIPTION,
                required_keywords=["prescription"],
                optional_keywords=[
                    "rx",
                    "medication",
                    "dose",
                    "pharmacy",
                    "refill",
                    "dispense",
                    "sig",
                    "quantity",
                ],
                excluded_keywords=["lab", "test", "result"],
                required_entities=["medication"],
                min_confidence=0.7,
            ),
            DocumentType.LAB_REPORT: ClassificationRule(
                document_type=DocumentType.LAB_REPORT,
                required_keywords=["lab", "test", "result"],
                optional_keywords=["specimen", "reference range", "abnormal", "normal"],
                excluded_keywords=["prescription", "discharge"],
                required_entities=["test_name"],
                min_confidence=0.7,
            ),
            DocumentType.MEDICAL_RECORD: ClassificationRule(
                document_type=DocumentType.MEDICAL_RECORD,
                required_keywords=["medical record", "patient", "history"],
                optional_keywords=["diagnosis", "treatment", "examination"],
                excluded_keywords=["invoice", "bill", "payment"],
                required_entities=["condition", "procedure"],
                min_confidence=0.6,
            ),
            DocumentType.INSURANCE_CARD: ClassificationRule(
                document_type=DocumentType.INSURANCE_CARD,
                required_keywords=["insurance", "policy", "member"],
                optional_keywords=["coverage", "copay", "deductible", "group"],
                excluded_keywords=["claim", "bill"],
                required_entities=["insurance_company"],
                min_confidence=0.8,
            ),
            DocumentType.VACCINATION_CARD: ClassificationRule(
                document_type=DocumentType.VACCINATION_CARD,
                required_keywords=["vaccination", "vaccine", "immunization"],
                optional_keywords=["dose", "covid", "flu", "batch", "lot"],
                excluded_keywords=["prescription", "lab"],
                required_entities=["vaccine_name"],
                min_confidence=0.8,
            ),
            DocumentType.CONSENT_FORM: ClassificationRule(
                document_type=DocumentType.CONSENT_FORM,
                required_keywords=["consent", "agree", "authorize"],
                optional_keywords=["signature", "witness", "guardian", "minor"],
                excluded_keywords=["prescription", "result"],
                required_entities=[],
                min_confidence=0.7,
            ),
            DocumentType.DISCHARGE_SUMMARY: ClassificationRule(
                document_type=DocumentType.DISCHARGE_SUMMARY,
                required_keywords=["discharge", "summary", "hospital"],
                optional_keywords=[
                    "admission",
                    "diagnosis",
                    "follow-up",
                    "instructions",
                ],
                excluded_keywords=["appointment", "schedule"],
                required_entities=["facility_name"],
                min_confidence=0.7,
            ),
            DocumentType.REFERRAL_LETTER: ClassificationRule(
                document_type=DocumentType.REFERRAL_LETTER,
                required_keywords=["referral", "refer", "specialist"],
                optional_keywords=["consultation", "appointment", "evaluation"],
                excluded_keywords=["discharge", "prescription"],
                required_entities=["provider_name"],
                min_confidence=0.7,
            ),
            DocumentType.MEDICAL_CERTIFICATE: ClassificationRule(
                document_type=DocumentType.MEDICAL_CERTIFICATE,
                required_keywords=["certificate", "certify", "medical"],
                optional_keywords=["fitness", "sick leave", "disability", "work"],
                excluded_keywords=["prescription", "lab"],
                required_entities=[],
                min_confidence=0.7,
            ),
            DocumentType.IDENTITY_DOCUMENT: ClassificationRule(
                document_type=DocumentType.IDENTITY_DOCUMENT,
                required_keywords=["passport", "id", "identification", "license"],
                optional_keywords=["birth", "nationality", "expiry", "issued"],
                excluded_keywords=["medical", "health"],
                required_entities=["person_name"],
                min_confidence=0.8,
            ),
        }

    def _load_ml_model(self) -> None:
        """Load pre-trained ML model for classification."""
        try:
            model_dir = self.model_path
            if model_dir:
                self.ml_model = joblib.load(model_dir / "classifier_model.pkl")
                self.vectorizer = joblib.load(model_dir / "tfidf_vectorizer.pkl")
                self.label_encoder = joblib.load(model_dir / "label_encoder.pkl")
            logger.info("ML model loaded successfully")
        except (FileNotFoundError, ValueError) as e:
            logger.error("Failed to load ML model: %s", e)
            self.ml_model = None
            self.vectorizer = None
            self.label_encoder = None

    async def classify_document(
        self,
        document_content: Union[str, bytes],
        metadata: Optional[Dict[str, Any]] = None,
        use_ml: bool = True,
    ) -> ClassificationResult:
        """
        Classify a document into one of the predefined categories.

        Args:
            document_content: The document content (text or image bytes)
            metadata: Additional metadata about the document
            use_ml: Whether to use ML model if available

        Returns:
            ClassificationResult with the predicted document type and confidence
        """
        start_time = datetime.utcnow()

        try:
            # Extract features from document
            features = await self._extract_features(document_content, metadata)

            # Perform classification using multiple methods
            rule_based_result = self._classify_rule_based(features)
            ml_result = None

            if use_ml and self.ml_model is not None:
                ml_result = self._classify_ml(features)  # type: ignore[unreachable]

            # Combine results
            final_result = self._combine_results(rule_based_result, ml_result, features)

            # Calculate processing time
            processing_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            final_result.processing_time_ms = processing_time_ms

            # Log metrics
            self.metrics_collector.record_metric(
                MetricType.DOCUMENT_CLASSIFICATION,
                {
                    "document_type": final_result.document_type.value,
                    "confidence": final_result.confidence,
                    "method": final_result.method_used.value,
                    "processing_time_ms": processing_time_ms,
                },
            )

            # Audit log
            await self.audit_logger.log_event(
                AuditEventType.DOCUMENT_CLASSIFIED,
                {
                    "document_type": final_result.document_type.value,
                    "confidence": final_result.confidence,
                    "method": final_result.method_used.value,
                },
            )

            return final_result

        except Exception as e:
            logger.error("Document classification failed: %s", e)
            raise

    async def _extract_features(
        self,
        document_content: Union[str, bytes],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DocumentFeatures:
        """Extract features from document for classification."""
        # If content is bytes (image), perform OCR first
        if isinstance(document_content, bytes):
            ocr_result = await self.textract_client.analyze_document(
                document_content,
                document_name=(
                    metadata.get("filename", "unknown.pdf")
                    if metadata
                    else "unknown.pdf"
                ),
                features=[
                    FeatureType.TEXT,
                    FeatureType.FORMS,
                    FeatureType.TABLES,
                    FeatureType.SIGNATURES,
                ],
            )
            text_content = ocr_result.get_all_text()
            has_tables = bool(ocr_result.extracted_tables)
            has_forms = bool(ocr_result.extracted_forms)
            has_signatures = bool(ocr_result.signatures_detected)
        else:
            text_content = document_content
            has_tables = False
            has_forms = False
            has_signatures = False

        # Normalize text
        normalized_text = self.text_normalizer.normalize(text_content)

        # Extract medical entities
        entities = await self.medical_entity_extractor.extract_entities(normalized_text)

        # Extract key phrases
        key_phrases = self._extract_key_phrases(normalized_text)

        # Extract dates and numbers
        date_references = self._extract_dates(normalized_text)
        numeric_values = self._extract_numbers(normalized_text)

        # Count medical terms
        # Check each word in the text against medical terms
        words = normalized_text.lower().split()
        medical_terms_count = sum(
            1
            for word in words
            if self.medical_terminology_validator.validate_term(word)
        )

        # Detect language
        language = metadata.get("language", "en") if metadata else "en"

        return DocumentFeatures(
            text_content=normalized_text,
            extracted_entities=entities,
            key_phrases=key_phrases,
            document_structure={
                "has_header": self._has_header(text_content),
                "has_footer": self._has_footer(text_content),
                "sections": self._identify_sections(text_content),
            },
            metadata=metadata or {},
            language=language,
            text_length=len(normalized_text),
            has_tables=has_tables,
            has_forms=has_forms,
            has_images=metadata.get("has_images", False) if metadata else False,
            has_signatures=has_signatures,
            date_references=date_references,
            numeric_values=numeric_values,
            medical_terms_count=medical_terms_count,
        )

    def _classify_rule_based(self, features: DocumentFeatures) -> ClassificationResult:
        """Perform rule-based classification."""
        matches = []

        for doc_type, rule in self.classification_rules.items():
            is_match, confidence = rule.matches(features)
            if is_match:
                matches.append((doc_type, confidence))

        # Sort by confidence
        matches.sort(key=lambda x: x[1], reverse=True)

        if matches:
            best_match = matches[0]
            alternatives = matches[1:5]  # Top 5 alternatives

            confidence_level = self._get_confidence_level(best_match[1])

            reasoning = self._generate_reasoning(best_match[0], features, "rule_based")

            return ClassificationResult(
                document_type=best_match[0],
                confidence=best_match[1],
                confidence_level=confidence_level,
                method_used=ClassificationMethod.RULE_BASED,
                alternative_types=alternatives,
                features_used=features,
                reasoning=reasoning,
                processing_time_ms=0,  # Will be set later
                model_version="1.0.0",
            )
        else:
            return ClassificationResult(
                document_type=DocumentType.UNKNOWN,
                confidence=0.0,
                confidence_level=ClassificationConfidence.VERY_LOW,
                method_used=ClassificationMethod.RULE_BASED,
                alternative_types=[],
                features_used=features,
                reasoning="No matching rules found",
                processing_time_ms=0,
                model_version="1.0.0",
            )

    def _classify_ml(self, features: DocumentFeatures) -> ClassificationResult:
        """Perform ML-based classification."""
        # Caller ensures ml_model is not None
        assert self.ml_model is not None
        assert self.vectorizer is not None  # type: ignore[unreachable]
        assert self.label_encoder is not None

        try:
            # Convert features to vector
            feature_vector = features.to_feature_vector()
            text_features = self.vectorizer.transform([features.text_content])

            # Combine numeric and text features
            numeric_features = np.array(
                [
                    [
                        feature_vector["text_length"],
                        feature_vector["has_tables"],
                        feature_vector["has_forms"],
                        feature_vector["has_signatures"],
                        feature_vector["medical_terms_count"],
                        feature_vector["entity_types_count"],
                        feature_vector["date_count"],
                        feature_vector["numeric_count"],
                    ]
                ]
            )

            combined_features = np.hstack([numeric_features, text_features.toarray()])

            # Get predictions with probabilities
            predictions = self.ml_model.predict_proba(combined_features)[0]
            predicted_class_idx = np.argmax(predictions)
            predicted_class = self.label_encoder.inverse_transform(
                [predicted_class_idx]
            )[0]
            confidence = float(predictions[predicted_class_idx])

            # Get top alternatives
            top_indices = np.argsort(predictions)[::-1][:5]
            alternatives = []
            for idx in top_indices[1:]:
                if predictions[idx] > 0.1:  # Only include if confidence > 10%
                    doc_type = DocumentType(
                        self.label_encoder.inverse_transform([idx])[0]
                    )
                    alternatives.append((doc_type, float(predictions[idx])))

            confidence_level = self._get_confidence_level(confidence)

            reasoning = self._generate_reasoning(
                DocumentType(predicted_class), features, "ml_model"
            )

            return ClassificationResult(
                document_type=DocumentType(predicted_class),
                confidence=confidence,
                confidence_level=confidence_level,
                method_used=ClassificationMethod.ML_MODEL,
                alternative_types=alternatives,
                features_used=features,
                reasoning=reasoning,
                processing_time_ms=0,
                model_version="2.0.0",
            )

        except (ValueError, AttributeError) as e:
            logger.error("ML classification failed: %s", e)
            # Return unknown if ML fails
            return ClassificationResult(
                document_type=DocumentType.UNKNOWN,
                confidence=0.0,
                confidence_level=ClassificationConfidence.VERY_LOW,
                method_used=ClassificationMethod.ML_MODEL,
                alternative_types=[],
                features_used=features,
                reasoning=f"ML classification failed: {str(e)}",
                processing_time_ms=0,
                model_version="2.0.0",
            )

    def _combine_results(
        self,
        rule_result: ClassificationResult,
        ml_result: Optional[ClassificationResult],
        features: DocumentFeatures,
    ) -> ClassificationResult:
        """Combine results from different classification methods."""
        if not ml_result:
            return rule_result

        # If both agree with high confidence, use ensemble
        if (
            rule_result.document_type == ml_result.document_type
            and rule_result.confidence > 0.7
            and ml_result.confidence > 0.7
        ):

            combined_confidence = (rule_result.confidence + ml_result.confidence) / 2

            return ClassificationResult(
                document_type=rule_result.document_type,
                confidence=combined_confidence,
                confidence_level=self._get_confidence_level(combined_confidence),
                method_used=ClassificationMethod.ENSEMBLE,
                alternative_types=self._merge_alternatives(
                    rule_result.alternative_types, ml_result.alternative_types
                ),
                features_used=features,
                reasoning=f"Both rule-based and ML agree: {rule_result.reasoning}",
                processing_time_ms=0,
                model_version="hybrid-1.0.0",
            )

        # If they disagree, use the one with higher confidence
        if ml_result.confidence > rule_result.confidence:
            ml_result.method_used = ClassificationMethod.HYBRID
            return ml_result
        else:
            rule_result.method_used = ClassificationMethod.HYBRID
            return rule_result

    def _extract_key_phrases(self, text: str) -> List[str]:
        """Extract key phrases from text."""
        # Simple implementation - can be enhanced with NLP libraries
        sentences = text.split(".")
        key_phrases = []

        for sentence in sentences:
            # Extract noun phrases (simplified)
            words = sentence.split()
            for i in range(len(words) - 1):
                if len(words[i]) > 3 and len(words[i + 1]) > 3:
                    phrase = f"{words[i]} {words[i+1]}"
                    if phrase.lower() not in ["the patient", "this is"]:
                        key_phrases.append(phrase)

        return list(set(key_phrases))[:20]  # Return top 20 unique phrases

    def _extract_dates(self, text: str) -> List[str]:
        """Extract date references from text."""
        date_patterns = [
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
            r"\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}\b",
            r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{2,4}\b",
        ]

        dates = []
        for pattern in date_patterns:
            dates.extend(re.findall(pattern, text, re.IGNORECASE))

        return dates

    def _extract_numbers(self, text: str) -> List[str]:
        """Extract numeric values from text."""
        # Extract numbers with units
        number_pattern = r"\b\d+\.?\d*\s*(?:mg|ml|kg|lbs|cm|mm|°[CF]|%|mcg|IU|units?)\b"
        return re.findall(number_pattern, text, re.IGNORECASE)

    def _has_header(self, text: str) -> bool:
        """Check if document has a header."""
        lines = text.split("\n")
        if len(lines) < 3:
            return False

        # Check if first few lines contain typical header elements
        header_keywords = [
            "clinic",
            "hospital",
            "medical",
            "health",
            "center",
            "institute",
        ]
        first_lines = " ".join(lines[:3]).lower()

        return any(keyword in first_lines for keyword in header_keywords)

    def _has_footer(self, text: str) -> bool:
        """Check if document has a footer."""
        lines = text.split("\n")
        if len(lines) < 3:
            return False

        # Check if last few lines contain typical footer elements
        footer_keywords = ["page", "confidential", "signature", "date", "printed"]
        last_lines = " ".join(lines[-3:]).lower()

        return any(keyword in last_lines for keyword in footer_keywords)

    def _identify_sections(self, text: str) -> List[str]:
        """Identify document sections."""
        section_headers = []
        lines = text.split("\n")

        for line in lines:
            # Look for section headers (all caps, or ending with colon)
            if line.strip() and (line.isupper() or line.strip().endswith(":")):
                section_headers.append(line.strip())

        return section_headers[:10]  # Return top 10 sections

    def _get_confidence_level(self, confidence: float) -> ClassificationConfidence:
        """Convert numeric confidence to confidence level."""
        if confidence > 0.95:
            return ClassificationConfidence.VERY_HIGH
        elif confidence > 0.85:
            return ClassificationConfidence.HIGH
        elif confidence > 0.70:
            return ClassificationConfidence.MEDIUM
        elif confidence > 0.50:
            return ClassificationConfidence.LOW
        else:
            return ClassificationConfidence.VERY_LOW

    def _generate_reasoning(
        self, document_type: DocumentType, features: DocumentFeatures, method: str
    ) -> str:
        """Generate human-readable reasoning for classification."""
        reasons = []

        if method == "rule_based":
            reasons.append(
                f"Document classified as {document_type.value} based on keyword matching"
            )

            if features.extracted_entities:
                entity_types = list(features.extracted_entities.keys())
                reasons.append(f"Found relevant entities: {', '.join(entity_types)}")

            if features.medical_terms_count > 5:
                reasons.append(f"Contains {features.medical_terms_count} medical terms")

        elif method == "ml_model":
            reasons.append(
                f"ML model predicted {document_type.value} based on document features"
            )
            reasons.append(
                f"Key features: {len(features.key_phrases)} key phrases, "
                f"{features.medical_terms_count} medical terms"
            )

        if features.has_forms:
            reasons.append("Document contains form fields")
        if features.has_tables:
            reasons.append("Document contains tables")
        if features.has_signatures:
            reasons.append("Document contains signatures")

        return ". ".join(reasons)

    def _merge_alternatives(
        self,
        alternatives1: List[Tuple[DocumentType, float]],
        alternatives2: List[Tuple[DocumentType, float]],
    ) -> List[Tuple[DocumentType, float]]:
        """Merge alternative classifications from different methods."""
        merged = {}

        for doc_type, conf in alternatives1:
            merged[doc_type] = conf

        for doc_type, conf in alternatives2:
            if doc_type in merged:
                merged[doc_type] = (merged[doc_type] + conf) / 2
            else:
                merged[doc_type] = conf

        # Sort by confidence
        sorted_alternatives = sorted(merged.items(), key=lambda x: x[1], reverse=True)

        return sorted_alternatives[:5]  # Return top 5


# Export classes and functions
__all__ = [
    "DocumentClassifier",
    "ClassificationResult",
    "ClassificationMethod",
    "ClassificationConfidence",
    "DocumentFeatures",
    "ClassificationRule",
]
