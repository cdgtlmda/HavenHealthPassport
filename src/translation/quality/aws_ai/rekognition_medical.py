"""
AWS Rekognition Integration for Medical Image Annotation Translation.

This module provides integration with AWS Rekognition for translating
medical image annotations and ensuring visual medical content is
properly localized.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple, Union

import boto3
from botocore.exceptions import ClientError
from PIL import Image, ImageDraw, ImageFont

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.services.encryption_service import EncryptionService
from src.translation.medical_terminology import MedicalTerminologyHandler
from src.ui.fonts.font_manager import FontCategory, WritingSystem, font_manager
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ImageType(str, Enum):
    """Types of medical images."""

    XRAY = "xray"
    CT_SCAN = "ct_scan"
    MRI = "mri"
    ULTRASOUND = "ultrasound"
    PATHOLOGY = "pathology"
    DIAGRAM = "diagram"
    CHART = "chart"
    OTHER = "other"


class AnnotationType(str, Enum):
    """Types of medical annotations."""

    ANATOMICAL_LABEL = "anatomical_label"
    MEASUREMENT = "measurement"
    DIAGNOSIS = "diagnosis"
    PROCEDURE = "procedure"
    MEDICATION = "medication"
    INSTRUCTION = "instruction"
    OTHER = "other"


@dataclass
class MedicalImageAnnotation:
    """Medical annotation on an image."""

    text: str
    language: str
    bbox: Tuple[float, float, float, float]  # x, y, width, height
    confidence: float
    medical_category: Optional[str] = None
    translated_text: Optional[str] = None
    translation_confidence: Optional[float] = None


@dataclass
class AnnotatedMedicalImage:
    """Medical image with annotations."""

    image_id: str
    image_data: bytes
    source_language: str
    target_language: str
    annotations: List[MedicalImageAnnotation]
    medical_context: Optional[str] = None
    processed_at: datetime = field(default_factory=datetime.utcnow)


class RekognitionMedicalTranslator:
    """
    Translates medical image annotations using AWS Rekognition.

    Features:
    - Extract text from medical images
    - Identify medical diagrams and labels
    - Translate anatomical labels
    - Preserve visual medical context
    - Generate localized medical images
    """

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize Rekognition medical translator.

        Args:
            region: AWS region
        """
        self.rekognition = boto3.client("rekognition", region_name=region)
        self.translate = boto3.client("translate", region_name=region)
        self.s3 = boto3.client("s3", region_name=region)

        self.terminology_manager = MedicalTerminologyHandler()
        self.encryption_service = EncryptionService()
        self._annotation_cache: Dict[str, Any] = {}

    @require_phi_access(AccessLevel.READ)
    async def translate_medical_image_annotations(
        self,
        image_data: bytes,
        source_language: str,
        target_language: str,
        medical_context: Optional[str] = None,
    ) -> AnnotatedMedicalImage:
        """
        Extract and translate annotations from medical images.

        Args:
            image_data: Image bytes
            source_language: Source language code
            target_language: Target language code
            medical_context: Medical context (e.g., "anatomy", "radiology")

        Returns:
            AnnotatedMedicalImage with translated annotations
        """
        try:
            # Detect text in image
            response = self.rekognition.detect_text(Image={"Bytes": image_data})

            # Extract medical annotations
            annotations = []
            for text_detection in response.get("TextDetections", []):
                if (
                    text_detection["Type"] == "LINE"
                    and text_detection["Confidence"] > 80
                ):
                    # Create annotation
                    annotation = MedicalImageAnnotation(
                        text=text_detection["DetectedText"],
                        language=source_language,
                        bbox=self._convert_bbox(
                            text_detection["Geometry"]["BoundingBox"]
                        ),
                        confidence=text_detection["Confidence"] / 100,
                    )

                    # Identify medical category
                    annotation.medical_category = await self._identify_medical_category(
                        annotation.text, medical_context
                    )

                    # Translate annotation
                    translated = await self._translate_medical_annotation(
                        annotation, target_language
                    )
                    annotation.translated_text = translated["text"]
                    annotation.translation_confidence = translated["confidence"]

                    annotations.append(annotation)

            # Create annotated image object
            image_id = f"medical_img_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

            return AnnotatedMedicalImage(
                image_id=image_id,
                image_data=image_data,
                source_language=source_language,
                target_language=target_language,
                annotations=annotations,
                medical_context=medical_context,
            )

        except ClientError as e:
            logger.error("Error processing medical image: %s", e)
            raise

    async def generate_translated_image(
        self,
        annotated_image: AnnotatedMedicalImage,
        output_format: str = "PNG",
    ) -> bytes:
        """Generate new image with translated annotations."""
        # Load image
        image = Image.open(BytesIO(annotated_image.image_data))
        draw = ImageDraw.Draw(image)

        # Use proper font management for multi-language support
        # Detect writing system for target language
        language_writing_systems = {
            "ar": WritingSystem.ARABIC,
            "hi": WritingSystem.DEVANAGARI,
            "bn": WritingSystem.BENGALI,
            "zh": WritingSystem.CHINESE,
            "ja": WritingSystem.JAPANESE,
            "ko": WritingSystem.KOREAN,
            "ru": WritingSystem.CYRILLIC,
            "he": WritingSystem.HEBREW,
            "th": WritingSystem.THAI,
            "am": WritingSystem.ETHIOPIC,
        }

        # Get appropriate writing system
        writing_system = WritingSystem.LATIN  # Default
        for lang_code, ws in language_writing_systems.items():
            if annotated_image.target_language.lower().startswith(lang_code):
                writing_system = ws
                break

        # Get font stack for medical terminology
        font_stack = font_manager.get_font_stack(
            FontCategory.MEDICAL, writing_system, annotated_image.target_language
        )

        # Try to load fonts in order of preference
        font: Optional[Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]] = None
        font_size = 16

        # Font paths for different systems (common locations)
        font_paths = {
            "Inter": ["/usr/share/fonts/truetype/inter/Inter-Regular.ttf"],
            "IBM Plex Sans Arabic": [
                "/usr/share/fonts/truetype/ibm-plex/IBMPlexSansArabic-Regular.ttf"
            ],
            "Noto Sans Devanagari": [
                "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"
            ],
            "Noto Sans Bengali": [
                "/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf"
            ],
            "Noto Sans CJK": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"],
            "default": [
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/System/Library/Fonts/Helvetica.ttc",  # macOS
                "C:\\Windows\\Fonts\\arial.ttf",  # Windows
            ],
        }

        # Try primary font first
        primary_font = font_stack.primary_font
        if primary_font in font_paths:
            for path in font_paths[primary_font]:
                try:
                    font = ImageFont.truetype(path, font_size)
                    logger.info(f"Loaded primary font: {primary_font} from {path}")
                    break
                except (OSError, ValueError):
                    continue

        # Try fallback fonts
        if not font:
            for fallback in font_stack.fallback_fonts:
                if fallback in font_paths:
                    for path in font_paths[fallback]:
                        try:
                            font = ImageFont.truetype(path, font_size)
                            logger.info(f"Loaded fallback font: {fallback} from {path}")
                            break
                        except (OSError, ValueError):
                            continue
                if font:
                    break

        # Try default fonts as last resort
        if not font:
            for path in font_paths["default"]:
                try:
                    font = ImageFont.truetype(path, font_size)
                    logger.info(f"Loaded default font from {path}")
                    break
                except (OSError, ValueError):
                    continue

        # Ultimate fallback
        if not font:
            logger.warning("No suitable font found, using system default")
            font = ImageFont.load_default()

        # Replace annotations with translations
        for annotation in annotated_image.annotations:
            if annotation.translated_text:
                # Convert relative bbox to absolute coordinates
                x = annotation.bbox[0] * image.width
                y = annotation.bbox[1] * image.height

                # Draw white background
                text_bbox = draw.textbbox((x, y), annotation.translated_text, font=font)
                draw.rectangle(text_bbox, fill="white")

                # Draw translated text
                draw.text((x, y), annotation.translated_text, fill="black", font=font)

        # Save to bytes
        output = BytesIO()
        image.save(output, format=output_format)
        return output.getvalue()

    def _convert_bbox(
        self, rekognition_bbox: Dict[str, float]
    ) -> Tuple[float, float, float, float]:
        """Convert Rekognition bbox format to standard format."""
        return (
            rekognition_bbox["Left"],
            rekognition_bbox["Top"],
            rekognition_bbox["Width"],
            rekognition_bbox["Height"],
        )

    async def _identify_medical_category(
        self, text: str, context: Optional[str]
    ) -> Optional[str]:
        """Identify medical category of annotation text."""
        text_lower = text.lower()

        # Medical category patterns
        categories = {
            "anatomy": ["bone", "muscle", "organ", "artery", "vein", "nerve"],
            "measurement": ["mm", "cm", "ml", "mg", "measurement", "scale"],
            "pathology": ["tumor", "lesion", "fracture", "inflammation"],
            "direction": [
                "anterior",
                "posterior",
                "lateral",
                "medial",
                "superior",
                "inferior",
            ],
            "procedure": ["incision", "injection", "examination", "surgery"],
        }

        # Check context first
        if context and context in categories:
            return context

        # Check text patterns
        for category, keywords in categories.items():
            if any(keyword in text_lower for keyword in keywords):
                return category

        return None

    async def _translate_medical_annotation(
        self, annotation: MedicalImageAnnotation, target_language: str
    ) -> Dict[str, Any]:
        """Translate medical annotation with terminology awareness."""
        try:
            # Check if it's a medical term
            is_medical_term = await self.terminology_manager.is_medical_term(
                annotation.text, annotation.language
            )

            if is_medical_term:
                # Use medical terminology translation
                translated_term = await self.terminology_manager.translate_term(
                    annotation.text,
                    annotation.language,
                    target_language,
                    category=annotation.medical_category,
                )

                return {
                    "text": translated_term if translated_term else annotation.text,
                    "confidence": 0.9 if translated_term else 0.5,
                }
            else:
                # Use standard translation
                response = self.translate.translate_text(
                    Text=annotation.text,
                    SourceLanguageCode=annotation.language,
                    TargetLanguageCode=target_language,
                )

                return {
                    "text": response["TranslatedText"],
                    "confidence": 0.85,
                }

        except (ClientError, KeyError, ValueError) as e:
            logger.error("Error translating annotation: %s", e)
            return {"text": annotation.text, "confidence": 0.0}


# Alias classes for backward compatibility
ImageAnnotation = MedicalImageAnnotation


@dataclass
class ImageAnalysisResult:
    """Result of medical image analysis."""

    image_id: str
    image_type: ImageType
    annotations: List[MedicalImageAnnotation]
    confidence: float
    processed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ImageTranslationResult:
    """Result of medical image translation."""

    source_image: AnnotatedMedicalImage
    translated_image: AnnotatedMedicalImage
    translation_quality: float
    issues: List[str] = field(default_factory=list)
    completed_at: datetime = field(default_factory=datetime.utcnow)


# Global instance for easy access
# Singleton instance storage
class _RekognitionTranslatorSingleton:
    """Singleton storage for RekognitionMedicalTranslator."""

    instance: Optional[RekognitionMedicalTranslator] = None
    region: Optional[str] = None


def get_rekognition_translator(
    region: str = "us-east-1",
) -> RekognitionMedicalTranslator:
    """Get or create a singleton instance of RekognitionMedicalTranslator."""
    if (
        _RekognitionTranslatorSingleton.instance is None
        or _RekognitionTranslatorSingleton.region != region
    ):
        _RekognitionTranslatorSingleton.instance = RekognitionMedicalTranslator(region)
        _RekognitionTranslatorSingleton.region = region
    return _RekognitionTranslatorSingleton.instance
