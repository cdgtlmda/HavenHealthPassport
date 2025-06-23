"""AI/ML Pipeline Configuration.

This module configures and initializes all AI/ML components for the Haven Health Passport system,
including the medical form recognition system.

This module handles FHIR Resource validation and processing for medical documents.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.ai.bedrock.bedrock_client import BedrockClient
from src.ai.document_processing import (
    HandwritingRecognizer,
    MedicalFormRecognizer,
    MultiLanguageOCR,
    TextractClient,
    TextractConfig,
)
from src.ai.langchain.chain_manager import ChainManager
from src.ai.llamaindex.index_manager import IndexManager
from src.ai.medical_nlp.nlp_processor import NLPProcessor
from src.ai.translation.translation_pipeline import TranslationPipeline
from src.healthcare.fhir_converter import FHIRConverter
from src.healthcare.hl7_mapper import HL7Mapper
from src.healthcare.medical_terminology import MedicalTerminologyValidator
from src.translation.medical_terms import MedicalTermTranslator

logger = logging.getLogger(__name__)


@dataclass
class AIMLConfig:
    """Configuration for AI/ML components."""

    aws_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-v2"
    textract_confidence_threshold: float = 0.7
    translation_confidence_threshold: float = 0.85
    enable_medical_form_recognition: bool = True
    enable_voice_processing: bool = True
    enable_predictive_analytics: bool = True
    s3_bucket_name: Optional[str] = None
    sns_topic_arn: Optional[str] = None

    @classmethod
    def from_env(cls) -> "AIMLConfig":
        """Create configuration from environment variables."""
        return cls(
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            bedrock_model_id=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-v2"),
            textract_confidence_threshold=float(
                os.getenv("TEXTRACT_CONFIDENCE_THRESHOLD", "0.7")
            ),
            translation_confidence_threshold=float(
                os.getenv("TRANSLATION_CONFIDENCE_THRESHOLD", "0.85")
            ),
            enable_medical_form_recognition=os.getenv(
                "ENABLE_MEDICAL_FORM_RECOGNITION", "true"
            ).lower()
            == "true",
            enable_voice_processing=os.getenv("ENABLE_VOICE_PROCESSING", "true").lower()
            == "true",
            enable_predictive_analytics=os.getenv(
                "ENABLE_PREDICTIVE_ANALYTICS", "true"
            ).lower()
            == "true",
            s3_bucket_name=os.getenv("AI_ML_S3_BUCKET"),
            sns_topic_arn=os.getenv("AI_ML_SNS_TOPIC_ARN"),
        )


class AIMLPipeline:
    """Main AI/ML pipeline orchestrator."""

    def __init__(self, config: AIMLConfig):
        """Initialize the AI/ML pipeline with the provided configuration."""
        self.config = config
        self._initialized = False

        # Component instances
        self.textract_client: Optional[TextractClient] = None
        self.medical_form_recognizer: Optional[MedicalFormRecognizer] = None
        self.handwriting_recognizer: Optional[HandwritingRecognizer] = None
        self.multilanguage_ocr: Optional[MultiLanguageOCR] = None
        self.bedrock_client: Optional[BedrockClient] = None
        self.chain_manager: Optional[ChainManager] = None
        self.index_manager: Optional[IndexManager] = None
        self.nlp_processor: Optional[NLPProcessor] = None
        self.translation_pipeline: Optional[TranslationPipeline] = None

    async def initialize(self) -> None:
        """Initialize all AI/ML components."""
        if self._initialized:
            return

        logger.info("Initializing AI/ML pipeline...")

        try:
            # Initialize Textract
            if self.config.enable_medical_form_recognition:
                textract_config = TextractConfig(
                    region=self.config.aws_region,
                    confidence_threshold=self.config.textract_confidence_threshold,
                    s3_bucket=self.config.s3_bucket_name,
                    sns_topic_arn=self.config.sns_topic_arn,
                )
                self.textract_client = TextractClient(textract_config)

                # Initialize medical form recognizer
                terminology_validator = MedicalTerminologyValidator()
                fhir_converter = FHIRConverter()
                hl7_mapper = HL7Mapper()
                translator = MedicalTermTranslator()

                self.medical_form_recognizer = MedicalFormRecognizer(
                    textract_client=self.textract_client,
                    terminology_validator=terminology_validator,
                    fhir_converter=fhir_converter,
                    hl7_mapper=hl7_mapper,
                    translator=translator,
                )

                # Initialize handwriting recognizer
                self.handwriting_recognizer = HandwritingRecognizer(
                    textract_client=self.textract_client,
                    terminology_validator=terminology_validator,
                )

                # Initialize multi-language OCR
                from src.translation.language_detector import (  # pylint: disable=import-outside-toplevel
                    LanguageDetector,
                )

                language_detector = LanguageDetector()
                self.multilanguage_ocr = MultiLanguageOCR(
                    textract_client=self.textract_client,
                    language_detector=language_detector,
                )

                logger.info(
                    "Medical form recognition, handwriting recognition, and multi-language OCR initialized"
                )

            # Initialize other components
            # These would be initialized similarly when implemented

            self._initialized = True
            logger.info("AI/ML pipeline initialization complete")

        except Exception as e:
            logger.error("Failed to initialize AI/ML pipeline: %s", str(e))
            raise

    async def process_medical_document(
        self, document_bytes: bytes, document_name: str, language: str = "en"
    ) -> Dict[str, Any]:
        """Process a medical document through the pipeline."""
        if not self._initialized:
            await self.initialize()

        results: Dict[str, Any] = {
            "document_name": document_name,
            "language": language,
            "processing_steps": [],
        }

        # Step 1: Medical form recognition
        if self.config.enable_medical_form_recognition and self.medical_form_recognizer:
            try:
                form_data = await self.medical_form_recognizer.recognize_medical_form(
                    document_bytes, document_name, language
                )

                results["form_recognition"] = {
                    "status": "success",
                    "form_type": form_data.form_type.value,
                    "confidence": form_data.confidence_score,
                    "fields_extracted": len(form_data.fields),
                    "validation_status": form_data.validation_status,
                    "data": form_data.to_dict(),
                }
                results["processing_steps"].append("form_recognition")

            except (ValueError, TypeError, AttributeError) as e:
                logger.error("Form recognition failed: %s", str(e))
                results["form_recognition"] = {"status": "error", "error": str(e)}

        # Additional processing steps would be added here

        # Step 2: Handwriting recognition
        if self.handwriting_recognizer:
            try:
                handwriting_result = (
                    await self.handwriting_recognizer.analyze_handwriting(
                        document_bytes, document_name
                    )
                )

                results["handwriting_recognition"] = {
                    "status": "success",
                    "handwriting_type": handwriting_result.handwriting_type.value,
                    "overall_quality": handwriting_result.overall_quality.value,
                    "texts_extracted": len(handwriting_result.handwritten_texts),
                    "mixed_content": handwriting_result.mixed_content,
                    "confidence_distribution": handwriting_result.confidence_distribution,
                    "high_confidence_texts": [
                        {"text": t.text, "confidence": t.confidence, "page": t.page}
                        for t in handwriting_result.get_high_confidence_texts()
                    ],
                }
                results["processing_steps"].append("handwriting_recognition")

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Handwriting recognition failed: %s", str(e))
                results["handwriting_recognition"] = {
                    "status": "error",
                    "error": str(e),
                }

        # Step 3: Multi-language OCR
        if self.multilanguage_ocr:
            try:
                # Detect languages from previous results if available
                hint_languages = None
                if language != "en":
                    # Map language code to list for hints
                    hint_languages = [language]

                ocr_result = await self.multilanguage_ocr.process_document(
                    document_bytes, document_name, hint_languages
                )

                results["multilanguage_ocr"] = {
                    "status": "success",
                    "detected_languages": [
                        {
                            "code": lang.code,
                            "name": lang.display_name,
                            "confidence": conf,
                        }
                        for lang, conf in ocr_result.detected_languages
                    ],
                    "primary_language": ocr_result.primary_language.code,
                    "text_blocks": len(ocr_result.text_blocks),
                    "medical_terms_found": sum(
                        1 for block in ocr_result.text_blocks if block.is_medical_term
                    ),
                    "rtl_content": any(
                        block.direction == "rtl" for block in ocr_result.text_blocks
                    ),
                }
                results["processing_steps"].append("multilanguage_ocr")

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Multi-language OCR failed: %s", str(e))
                results["multilanguage_ocr"] = {"status": "error", "error": str(e)}

        return results

    async def shutdown(self) -> None:
        """Shutdown AI/ML pipeline and cleanup resources."""
        logger.info("Shutting down AI/ML pipeline...")

        # Cleanup component resources
        self._initialized = False

        logger.info("AI/ML pipeline shutdown complete")


# Pipeline instance storage
class _PipelineStore:
    """Internal class to store pipeline instance without using global."""

    _instance: Optional[AIMLPipeline] = None


async def get_aiml_pipeline() -> AIMLPipeline:
    """Get or create the global AI/ML pipeline instance."""
    if _PipelineStore._instance is None:  # pylint: disable=protected-access
        config = AIMLConfig.from_env()
        _PipelineStore._instance = AIMLPipeline(
            config
        )  # pylint: disable=protected-access
        await _PipelineStore._instance.initialize()  # pylint: disable=protected-access

    return _PipelineStore._instance  # pylint: disable=protected-access
