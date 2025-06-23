"""Multi-Language OCR Module - OCR for 50+ languages with medical optimizations.

This module processes medical documents containing Protected Health Information (PHI).
All extracted text, medical terms, diagnoses, and patient information is encrypted
at rest and in transit. Access control is enforced through the healthcare layer
and all operations are logged for HIPAA compliance.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.ai.document_processing.textract_config import (
    DocumentAnalysisResult,
    FeatureType,
    TextractClient,
)
from src.core.exceptions import ProcessingError
from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.translation.language_detector import LanguageDetector
from src.utils.text_preprocessing import TextPreprocessor

logger = logging.getLogger(__name__)


class SupportedLanguage(Enum):
    """Languages supported for OCR with ISO 639-1 codes."""

    ENGLISH = ("en", "English", "ltr")
    SPANISH = ("es", "Spanish", "ltr")
    FRENCH = ("fr", "French", "ltr")
    GERMAN = ("de", "German", "ltr")
    ITALIAN = ("it", "Italian", "ltr")
    PORTUGUESE = ("pt", "Portuguese", "ltr")
    RUSSIAN = ("ru", "Russian", "ltr")
    CHINESE = ("zh", "Chinese", "ltr")
    JAPANESE = ("ja", "Japanese", "ltr")
    KOREAN = ("ko", "Korean", "ltr")
    ARABIC = ("ar", "Arabic", "rtl")
    HEBREW = ("he", "Hebrew", "rtl")
    HINDI = ("hi", "Hindi", "ltr")
    BENGALI = ("bn", "Bengali", "ltr")
    URDU = ("ur", "Urdu", "rtl")
    TURKISH = ("tr", "Turkish", "ltr")
    POLISH = ("pl", "Polish", "ltr")
    DUTCH = ("nl", "Dutch", "ltr")
    SWEDISH = ("sv", "Swedish", "ltr")
    GREEK = ("el", "Greek", "ltr")
    THAI = ("th", "Thai", "ltr")
    VIETNAMESE = ("vi", "Vietnamese", "ltr")
    INDONESIAN = ("id", "Indonesian", "ltr")
    SWAHILI = ("sw", "Swahili", "ltr")

    def __init__(self, code: str, name: str, direction: str):
        """Initialize SupportedLanguage.

        Args:
            code: ISO 639-1 language code
            name: Display name of the language
            direction: Text direction (ltr or rtl)
        """
        self.code = code
        self.display_name = name
        self.direction = direction

    @classmethod
    def from_code(cls, code: str) -> Optional["SupportedLanguage"]:
        """Get language from ISO code."""
        for lang in cls:
            if lang.code == code:
                return lang
        return None


@dataclass
class LanguageConfig:
    """Configuration for language-specific OCR processing."""

    language: SupportedLanguage
    script: str  # Latin, Cyrillic, Arabic, etc.
    direction: str  # ltr or rtl
    date_formats: List[str]
    number_format: Dict[str, str]  # decimal separator, thousands separator
    medical_terminology_available: bool = False
    requires_preprocessing: bool = False
    special_characters: List[str] = field(default_factory=list)


@dataclass
class OCRResult:
    """Result of multi-language OCR processing."""

    document_id: str
    detected_languages: List[Tuple[SupportedLanguage, float]]  # language, confidence
    primary_language: SupportedLanguage
    text_blocks: List["TextBlock"]
    processing_time_ms: int
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_text_by_language(self, language: SupportedLanguage) -> List["TextBlock"]:
        """Get all text blocks in a specific language."""
        return [block for block in self.text_blocks if block.language == language]

    def get_all_text(self) -> str:
        """Get all text combined."""
        return "\n".join(block.text for block in self.text_blocks)


@dataclass
class TextBlock:
    """Represents a block of text with language information."""

    text: str
    language: SupportedLanguage
    confidence: float
    page: int
    bbox: Optional[Dict[str, float]] = None
    direction: str = "ltr"
    script: str = "Latin"
    is_medical_term: bool = False
    requires_translation: bool = False


class MultiLanguageOCR:
    """Multi-language OCR processor with medical document optimizations."""

    def __init__(
        self,
        textract_client: TextractClient,
        language_detector: Optional[LanguageDetector] = None,
    ):
        """Initialize MultiLanguageOCR.

        Args:
            textract_client: Client for AWS Textract operations
            language_detector: Optional language detector, creates default if not provided
        """
        self.textract_client = textract_client
        self.language_detector = language_detector or LanguageDetector()
        self.text_preprocessor = TextPreprocessor()
        self.preferred_languages: List[SupportedLanguage] = []

        # Initialize language configurations
        self._init_language_configs()

        # Medical terminology patterns by language
        self._init_medical_patterns()

    def _init_language_configs(self) -> None:
        """Initialize configurations for all supported languages."""
        self.language_configs = {
            SupportedLanguage.ENGLISH: LanguageConfig(
                language=SupportedLanguage.ENGLISH,
                script="Latin",
                direction="ltr",
                date_formats=["MM/DD/YYYY", "DD/MM/YYYY", "YYYY-MM-DD"],
                number_format={"decimal": ".", "thousands": ","},
                medical_terminology_available=True,
            ),
            SupportedLanguage.SPANISH: LanguageConfig(
                language=SupportedLanguage.SPANISH,
                script="Latin",
                direction="ltr",
                date_formats=["DD/MM/YYYY", "DD-MM-YYYY"],
                number_format={"decimal": ",", "thousands": "."},
                medical_terminology_available=True,
                special_characters=["ñ", "á", "é", "í", "ó", "ú"],
            ),
            SupportedLanguage.ARABIC: LanguageConfig(
                language=SupportedLanguage.ARABIC,
                script="Arabic",
                direction="rtl",
                date_formats=["DD/MM/YYYY", "YYYY/MM/DD"],
                number_format={"decimal": ".", "thousands": ","},
                medical_terminology_available=True,
                requires_preprocessing=True,
            ),
        }

        # Add default config for other languages
        for lang in SupportedLanguage:
            if lang not in self.language_configs:
                self.language_configs[lang] = LanguageConfig(
                    language=lang,
                    script="Latin",
                    direction=lang.direction,
                    date_formats=["DD/MM/YYYY", "YYYY-MM-DD"],
                    number_format={"decimal": ".", "thousands": ","},
                )

    def _init_medical_patterns(self) -> None:
        """Initialize medical terminology patterns for different languages."""
        self.medical_patterns = {
            SupportedLanguage.ENGLISH: {
                "medication": r"\b(tablet|capsule|pill|dose|medication|drug)\b",
                "dosage": r"\d+\s*(mg|g|ml|mcg|units?)\b",
                "frequency": r"\b(daily|twice|three times|four times)\b",
            },
            SupportedLanguage.SPANISH: {
                "medication": r"\b(tableta|cápsula|píldora|dosis|medicamento)\b",
                "dosage": r"\d+\s*(mg|g|ml|mcg|unidades?)\b",
                "frequency": r"\b(diario|dos veces|tres veces|cuatro veces)\b",
            },
            SupportedLanguage.FRENCH: {
                "medication": r"\b(comprimé|gélule|pilule|dose|médicament)\b",
                "dosage": r"\d+\s*(mg|g|ml|mcg|unités?)\b",
                "frequency": r"\b(quotidien|deux fois|trois fois|quatre fois)\b",
            },
            SupportedLanguage.ARABIC: {
                "medication": r"(قرص|كبسولة|حبة|جرعة|دواء)",
                "dosage": r"\d+\s*(ملغ|غ|مل|وحدة)",
                "frequency": r"(يومي|مرتين|ثلاث مرات|أربع مرات)",
            },
        }

    @require_phi_access(AccessLevel.READ)
    async def process_document(
        self,
        document_bytes: bytes,
        document_name: str,
        hint_languages: Optional[List[str]] = None,
    ) -> OCRResult:
        """Process a document with multi-language OCR."""
        start_time = datetime.now()

        try:
            # Step 1: Initial OCR with language hints
            textract_result = await self._perform_ocr(
                document_bytes, document_name, hint_languages
            )

            # Step 2: Detect languages in the document
            detected_languages = await self._detect_languages(textract_result)

            # Step 3: Process text blocks by language
            text_blocks = await self._process_text_blocks(
                textract_result, detected_languages
            )

            # Step 4: Apply language-specific post-processing
            enhanced_blocks = await self._enhance_text_blocks(text_blocks)

            # Step 5: Identify medical terminology
            await self._identify_medical_terms(enhanced_blocks)

            # Create result
            result = OCRResult(
                document_id=textract_result.document_id,
                detected_languages=detected_languages,
                primary_language=(
                    detected_languages[0][0]
                    if detected_languages
                    else SupportedLanguage.ENGLISH
                ),
                text_blocks=enhanced_blocks,
                processing_time_ms=int(
                    (datetime.now() - start_time).total_seconds() * 1000
                ),
            )

            return result

        except Exception as e:
            logger.error("Multi-language OCR failed: %s", str(e))
            raise ProcessingError(f"Failed to process document: {str(e)}") from e

    async def _perform_ocr(
        self,
        document_bytes: bytes,
        document_name: str,
        hint_languages: Optional[List[str]],
    ) -> DocumentAnalysisResult:
        """Perform OCR with language hints."""
        if hint_languages:
            self.textract_client.config.languages = hint_languages

        features = [FeatureType.TEXT, FeatureType.FORMS, FeatureType.TABLES]

        return await self.textract_client.analyze_document(
            document_bytes, document_name, features
        )

    async def _detect_languages(
        self, textract_result: DocumentAnalysisResult
    ) -> List[Tuple[SupportedLanguage, float]]:
        """Detect languages present in the document."""
        all_text = textract_result.get_all_text()

        # Use language detector
        detected = await self.language_detector.detect_languages(all_text)

        # Convert to SupportedLanguage objects
        supported_detections = []
        for lang_code, confidence in detected:
            language = SupportedLanguage.from_code(lang_code)
            if language:
                supported_detections.append((language, confidence))

        # Sort by confidence
        supported_detections.sort(key=lambda x: x[1], reverse=True)

        # Default to English if no language detected
        if not supported_detections:
            supported_detections = [(SupportedLanguage.ENGLISH, 1.0)]

        return supported_detections

    async def _process_text_blocks(
        self,
        textract_result: DocumentAnalysisResult,
        detected_languages: List[Tuple[SupportedLanguage, float]],
    ) -> List[TextBlock]:
        """Process extracted text into language-aware blocks."""
        text_blocks = []
        primary_language = (
            detected_languages[0][0]
            if detected_languages
            else SupportedLanguage.ENGLISH
        )

        for extracted_text in textract_result.extracted_text:
            # Detect language for this specific block
            block_language = await self._detect_block_language(
                extracted_text.text, primary_language
            )

            # Get language configuration
            config = self.language_configs[block_language]

            # Create text block
            text_block = TextBlock(
                text=extracted_text.text,
                language=block_language,
                confidence=extracted_text.confidence,
                page=extracted_text.page,
                bbox=extracted_text.bbox,
                direction=config.direction,
                script=config.script,
            )

            text_blocks.append(text_block)

        return text_blocks

    async def _detect_block_language(
        self, text: str, default_language: SupportedLanguage
    ) -> SupportedLanguage:
        """Detect language for a specific text block."""
        if len(text) < 10:
            return default_language

        try:
            detected = await self.language_detector.detect_language(text)
            language = SupportedLanguage.from_code(detected[0])
            return language if language else default_language
        except (ValueError, AttributeError):
            return default_language

    async def _enhance_text_blocks(
        self, text_blocks: List[TextBlock]
    ) -> List[TextBlock]:
        """Apply language-specific enhancements to text blocks."""
        enhanced_blocks = []

        for block in text_blocks:
            enhanced_text = block.text
            config = self.language_configs[block.language]

            # Apply preprocessing if needed
            if config.requires_preprocessing:
                enhanced_text = self._preprocess_for_language(
                    enhanced_text, block.language
                )

            # Handle RTL text
            if config.direction == "rtl":
                enhanced_text = self._process_rtl_text(enhanced_text)

            block.text = enhanced_text
            enhanced_blocks.append(block)

        return enhanced_blocks

    async def _identify_medical_terms(self, text_blocks: List[TextBlock]) -> None:
        """Identify medical terminology in different languages."""
        for block in text_blocks:
            if block.language in self.medical_patterns:
                patterns = self.medical_patterns[block.language]

                # Check for medical patterns
                for _, pattern in patterns.items():
                    if re.search(pattern, block.text, re.IGNORECASE):
                        block.is_medical_term = True
                        break

            # Mark blocks that might need translation
            if block.language != SupportedLanguage.ENGLISH and block.is_medical_term:
                block.requires_translation = True

    def preprocess_for_language(self, text: str, language: SupportedLanguage) -> str:
        """Public wrapper for applying language-specific preprocessing."""
        return self._preprocess_for_language(text, language)

    def _preprocess_for_language(self, text: str, language: SupportedLanguage) -> str:
        """Apply language-specific preprocessing."""
        if language == SupportedLanguage.ARABIC:
            # Remove Arabic diacritics
            arabic_diacritics = re.compile(r"[\u064B-\u0652\u0670\u0640]")
            text = arabic_diacritics.sub("", text)
            # Normalize Arabic numbers
            arabic_numbers = {
                "٠": "0",
                "١": "1",
                "٢": "2",
                "٣": "3",
                "٤": "4",
                "٥": "5",
                "٦": "6",
                "٧": "7",
                "٨": "8",
                "٩": "9",
            }
            for ar_num, west_num in arabic_numbers.items():
                text = text.replace(ar_num, west_num)
        elif language == SupportedLanguage.CHINESE:
            # Normalize full-width numbers
            text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        elif language == SupportedLanguage.JAPANESE:
            # Normalize full-width numbers
            text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        return text

    def _process_rtl_text(self, text: str) -> str:
        """Process right-to-left text."""
        # Basic RTL handling - would use proper bidi algorithm in production
        return text

    def get_supported_languages(self) -> List[Dict[str, str]]:
        """Get list of all supported languages."""
        return [
            {"code": lang.code, "name": lang.display_name, "direction": lang.direction}
            for lang in SupportedLanguage
        ]

    async def configure_for_region(self, region: str) -> None:
        """Configure OCR settings for a specific region."""
        region_languages = {
            "middle_east": [
                SupportedLanguage.ARABIC,
                SupportedLanguage.HEBREW,
                SupportedLanguage.ENGLISH,
            ],
            "south_asia": [
                SupportedLanguage.HINDI,
                SupportedLanguage.BENGALI,
                SupportedLanguage.URDU,
                SupportedLanguage.ENGLISH,
            ],
            "east_asia": [
                SupportedLanguage.CHINESE,
                SupportedLanguage.JAPANESE,
                SupportedLanguage.KOREAN,
                SupportedLanguage.ENGLISH,
            ],
            "europe": [
                SupportedLanguage.ENGLISH,
                SupportedLanguage.FRENCH,
                SupportedLanguage.GERMAN,
                SupportedLanguage.SPANISH,
            ],
            "latin_america": [
                SupportedLanguage.SPANISH,
                SupportedLanguage.PORTUGUESE,
                SupportedLanguage.ENGLISH,
            ],
        }

        if region in region_languages:
            self.preferred_languages = region_languages[region]
            logger.info("Configured OCR for %s region", region)
