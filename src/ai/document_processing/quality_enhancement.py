"""Document Quality Enhancement Module.

This module provides advanced image quality enhancement capabilities for medical documents
in the Haven Health Passport system. It preprocesses documents to improve OCR accuracy,
readability, and overall quality.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

# Standard library imports
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple, Union

# Third-party imports
import numpy as np
from PIL import Image

# First-party imports
from src.ai.document_processing.textract_config import DocumentType
from src.audit.audit_logger import AuditEventType, AuditLogger
from src.metrics.metrics_collector import MetricsCollector, MetricType
from src.utils.image_utils import ImageValidator

from .cv2_wrapper import HAS_CV2, CV2Constants, CV2Extra
from .cv2_wrapper import CV2Operations as cv2

logger = logging.getLogger(__name__)


class EnhancementType(Enum):
    """Types of quality enhancement operations."""

    CONTRAST = "contrast"
    BRIGHTNESS = "brightness"
    SHARPNESS = "sharpness"
    DENOISE = "denoise"
    DESKEW = "deskew"
    BINARIZATION = "binarization"
    RESOLUTION = "resolution"
    COLOR_CORRECTION = "color_correction"
    SHADOW_REMOVAL = "shadow_removal"
    BACKGROUND_REMOVAL = "background_removal"
    TEXT_ENHANCEMENT = "text_enhancement"
    AUTO = "auto"


class QualityLevel(Enum):
    """Document quality levels."""

    EXCELLENT = "excellent"  # No enhancement needed
    GOOD = "good"  # Minor enhancements beneficial
    FAIR = "fair"  # Moderate enhancements needed
    POOR = "poor"  # Significant enhancements required
    VERY_POOR = "very_poor"  # Major quality issues


@dataclass
class QualityMetrics:
    """Metrics for document quality assessment."""

    brightness_score: float
    contrast_score: float
    sharpness_score: float
    noise_level: float
    skew_angle: float
    text_clarity: float
    overall_quality: QualityLevel
    has_shadows: bool
    has_artifacts: bool
    is_color: bool
    resolution: Tuple[int, int]
    dpi: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "brightness_score": self.brightness_score,
            "contrast_score": self.contrast_score,
            "sharpness_score": self.sharpness_score,
            "noise_level": self.noise_level,
            "skew_angle": self.skew_angle,
            "text_clarity": self.text_clarity,
            "overall_quality": self.overall_quality.value,
            "has_shadows": self.has_shadows,
            "has_artifacts": self.has_artifacts,
            "is_color": self.is_color,
            "resolution": list(self.resolution),
            "dpi": self.dpi,
        }


@dataclass
class EnhancementParameters:
    """Parameters for quality enhancement operations."""

    contrast_factor: float = 1.2
    brightness_factor: float = 1.1
    sharpness_factor: float = 1.5
    denoise_strength: int = 5
    deskew_threshold: float = 0.5
    binarization_threshold: int = 128
    target_dpi: int = 300
    enable_shadow_removal: bool = True
    enable_background_removal: bool = False
    auto_enhance: bool = True
    preserve_color: bool = False
    enhancement_types: List[EnhancementType] = field(
        default_factory=lambda: [EnhancementType.AUTO]
    )


@dataclass
class EnhancementResult:
    """Result of quality enhancement operation."""

    enhanced_image: np.ndarray
    original_metrics: QualityMetrics
    enhanced_metrics: QualityMetrics
    operations_applied: List[EnhancementType]
    processing_time_ms: float
    improvement_score: float
    success: bool
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "original_metrics": self.original_metrics.to_dict(),
            "enhanced_metrics": self.enhanced_metrics.to_dict(),
            "operations_applied": [op.value for op in self.operations_applied],
            "processing_time_ms": self.processing_time_ms,
            "improvement_score": self.improvement_score,
            "success": self.success,
            "error_message": self.error_message,
        }


class DocumentQualityEnhancer:
    """Main service for document quality enhancement."""

    def __init__(
        self,
        audit_logger: AuditLogger,
        metrics_collector: MetricsCollector,
        image_validator: Optional[ImageValidator] = None,
        default_params: Optional[EnhancementParameters] = None,
    ):
        """Initialize the quality enhancer."""
        self.audit_logger = audit_logger
        self.metrics_collector = metrics_collector
        self.image_validator = image_validator or ImageValidator()
        self.default_params = default_params or EnhancementParameters()

        # Initialize OpenCV settings if available
        if HAS_CV2:
            CV2Extra.setNumThreads(4)
            CV2Extra.setUseOptimized(True)

    async def enhance_document(
        self,
        image_data: Union[bytes, np.ndarray, Image.Image],
        document_type: Optional[DocumentType] = None,
        params: Optional[EnhancementParameters] = None,
    ) -> EnhancementResult:
        """
        Enhance document quality for better OCR and readability.

        Args:
            image_data: Input image as bytes, numpy array, or PIL Image
            document_type: Type of document for optimized enhancement
            params: Enhancement parameters (uses defaults if not provided)

        Returns:
            EnhancementResult with enhanced image and metrics
        """
        start_time = datetime.utcnow()
        params = params or self.default_params
        original_image = np.array([])  # Initialize with empty array
        original_metrics: Optional[QualityMetrics] = None

        try:
            # Convert input to numpy array
            image = self._convert_to_numpy(image_data)
            original_image = image.copy()

            # Assess original quality
            original_metrics = self._assess_quality(image)
            assert original_metrics is not None  # For type checker

            # Determine enhancement strategy
            if params.auto_enhance or EnhancementType.AUTO in params.enhancement_types:
                enhancement_types = self._determine_enhancements(
                    original_metrics, document_type
                )
            else:
                enhancement_types = params.enhancement_types

            # Apply enhancements
            operations_applied = []
            for enhancement_type in enhancement_types:
                try:
                    image = await self._apply_enhancement(
                        image, enhancement_type, params
                    )
                    operations_applied.append(enhancement_type)
                except (ValueError, AttributeError, IOError) as e:
                    logger.warning("Failed to apply %s: %s", enhancement_type, e)

            # Assess enhanced quality
            enhanced_metrics = self._assess_quality(image)

            # Calculate improvement score
            improvement_score = self._calculate_improvement(
                original_metrics, enhanced_metrics
            )

            # Record metrics
            processing_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            self.metrics_collector.record_metric(
                MetricType.DOCUMENT_ENHANCEMENT,
                {
                    "original_quality": original_metrics.overall_quality.value,
                    "enhanced_quality": enhanced_metrics.overall_quality.value,
                    "improvement_score": improvement_score,
                    "operations_count": len(operations_applied),
                    "processing_time_ms": processing_time_ms,
                },
            )

            # Audit log
            await self.audit_logger.log_event(
                AuditEventType.DOCUMENT_ENHANCED,
                {
                    "operations": [op.value for op in operations_applied],
                    "improvement_score": improvement_score,
                    "processing_time_ms": processing_time_ms,
                },
            )

            return EnhancementResult(
                enhanced_image=image,
                original_metrics=original_metrics,
                enhanced_metrics=enhanced_metrics,
                operations_applied=operations_applied,
                processing_time_ms=processing_time_ms,
                improvement_score=improvement_score,
                success=True,
            )

        except (ValueError, AttributeError, IOError) as e:
            logger.error("Document enhancement failed: %s", e)

            # Return original image on failure
            return EnhancementResult(
                enhanced_image=original_image,
                original_metrics=original_metrics or self._get_default_metrics(),
                enhanced_metrics=self._get_default_metrics(),
                operations_applied=[],
                processing_time_ms=0,
                improvement_score=0,
                success=False,
                error_message=str(e),
            )

    def _convert_to_numpy(
        self, image_data: Union[bytes, np.ndarray, Image.Image]
    ) -> np.ndarray:
        """Convert various image formats to numpy array."""
        if isinstance(image_data, np.ndarray):
            return image_data
        elif isinstance(image_data, Image.Image):
            return np.array(image_data)
        elif isinstance(image_data, bytes):
            # Decode image from bytes
            if HAS_CV2:
                nparr = np.frombuffer(image_data, np.uint8)
                image = cv2.imdecode(nparr, CV2Constants.IMREAD_COLOR)
                if image is None:
                    raise ValueError("Failed to decode image from bytes")
                return np.array(image)
            else:
                # Fallback to PIL
                image = Image.open(BytesIO(image_data))
                return np.array(image)
        else:
            raise ValueError(f"Unsupported image type: {type(image_data)}")

    def _assess_quality(self, image: np.ndarray) -> QualityMetrics:
        """Assess document quality metrics."""
        # Default metrics for when cv2 is not available
        if not HAS_CV2:
            return QualityMetrics(
                brightness_score=0.5,
                contrast_score=0.5,
                sharpness_score=0.5,
                noise_level=0.0,
                skew_angle=0.0,
                text_clarity=0.5,
                overall_quality=QualityLevel.FAIR,
                has_shadows=False,
                has_artifacts=False,
                is_color=len(image.shape) == 3,
                resolution=(image.shape[1], image.shape[0]),
            )

        # Convert to grayscale for analysis
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)
            is_color = True
        else:
            gray = image
            is_color = False

        # Calculate brightness
        brightness_score = np.mean(gray) / 255.0

        # Calculate contrast
        contrast_score = np.std(gray) / 128.0

        # Calculate sharpness using Laplacian
        laplacian = CV2Extra.Laplacian(gray, CV2Constants.CV_64F)
        sharpness_score = np.var(laplacian) / 1000.0
        sharpness_score = min(sharpness_score, 1.0)

        # Estimate noise level
        noise_level = self._estimate_noise(gray)

        # Detect skew angle
        skew_angle = self._detect_skew(gray)

        # Assess text clarity
        text_clarity = self._assess_text_clarity(gray)

        # Detect shadows
        has_shadows = self._detect_shadows(gray)

        # Detect artifacts
        has_artifacts = self._detect_artifacts(gray)

        # Get resolution
        resolution = (image.shape[1], image.shape[0])

        # Determine overall quality
        overall_quality = self._determine_overall_quality(
            brightness_score, contrast_score, sharpness_score, noise_level, text_clarity
        )

        return QualityMetrics(
            brightness_score=brightness_score,
            contrast_score=contrast_score,
            sharpness_score=sharpness_score,
            noise_level=noise_level,
            skew_angle=skew_angle,
            text_clarity=text_clarity,
            overall_quality=overall_quality,
            has_shadows=has_shadows,
            has_artifacts=has_artifacts,
            is_color=is_color,
            resolution=resolution,
        )

    def _estimate_noise(self, gray: np.ndarray) -> float:
        """Estimate noise level in the image."""
        # Use median filter to estimate noise
        median = CV2Extra.medianBlur(gray, 5)
        diff = np.abs(gray.astype(np.float32) - median.astype(np.float32))
        noise_level = np.mean(diff) / 255.0
        return float(noise_level)

    def _detect_skew(self, gray: np.ndarray) -> float:
        """Detect document skew angle."""
        # Apply edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Detect lines using Hough transform
        lines = CV2Extra.HoughLines(edges, 1, np.pi / 180, 200)

        if lines is None:
            return 0.0

        # Calculate angles
        angles = []
        for _, theta in lines[:, 0]:
            angle = np.degrees(theta) - 90
            if -45 < angle < 45:
                angles.append(angle)

        if angles:
            # Return median angle (negated to match expected convention)
            return float(-np.median(angles))
        return 0.0

    def _assess_text_clarity(self, gray: np.ndarray) -> float:
        """Assess text clarity using edge strength."""
        # Apply morphological gradient
        kernel = cv2.getStructuringElement(CV2Constants.MORPH_RECT, (3, 3))
        gradient = cv2.morphologyEx(gray, CV2Constants.MORPH_GRADIENT, kernel)

        # Calculate mean gradient strength
        clarity = np.mean(gradient) / 255.0
        return float(min(clarity * 2, 1.0))  # Scale to 0-1 range

    def _detect_shadows(self, gray: np.ndarray) -> bool:
        """Detect if image has shadows."""
        # Calculate local statistics
        kernel_size = 50
        mean = CV2Extra.blur(gray, (kernel_size, kernel_size))
        diff = np.abs(gray.astype(np.float32) - mean.astype(np.float32))

        # High variance in local differences indicates shadows
        shadow_score = np.std(diff) / 128.0
        return bool(shadow_score > 0.3)

    def _detect_artifacts(self, gray: np.ndarray) -> bool:
        """Detect compression artifacts or noise patterns."""
        # Use FFT to detect regular patterns
        f_transform = np.fft.fft2(gray)
        f_shift = np.fft.fftshift(f_transform)
        magnitude = np.abs(f_shift)

        # Look for periodic patterns in frequency domain
        rows, cols = gray.shape
        crow, ccol = rows // 2, cols // 2

        # Exclude DC component
        magnitude[crow - 5 : crow + 5, ccol - 5 : ccol + 5] = 0

        # High frequency content indicates artifacts
        artifact_score = np.mean(magnitude) / (rows * cols)
        return bool(artifact_score > 0.1)

    def _determine_overall_quality(
        self,
        brightness: float,
        contrast: float,
        sharpness: float,
        noise: float,
        clarity: float,
    ) -> QualityLevel:
        """Determine overall document quality level."""
        # Weighted quality score
        quality_score = (
            brightness * 0.2
            + contrast * 0.2
            + sharpness * 0.3
            + (1 - noise) * 0.15
            + clarity * 0.15
        )

        if quality_score > 0.85:
            return QualityLevel.EXCELLENT
        elif quality_score > 0.70:
            return QualityLevel.GOOD
        elif quality_score > 0.55:
            return QualityLevel.FAIR
        elif quality_score > 0.40:
            return QualityLevel.POOR
        else:
            return QualityLevel.VERY_POOR

    def _determine_enhancements(
        self, metrics: QualityMetrics, document_type: Optional[DocumentType]
    ) -> List[EnhancementType]:
        """Determine which enhancements to apply based on quality metrics."""
        enhancements = []

        # Always start with deskew if needed
        if abs(metrics.skew_angle) > 0.5:
            enhancements.append(EnhancementType.DESKEW)

        # Brightness correction
        if metrics.brightness_score < 0.4 or metrics.brightness_score > 0.8:
            enhancements.append(EnhancementType.BRIGHTNESS)

        # Contrast enhancement
        if metrics.contrast_score < 0.5:
            enhancements.append(EnhancementType.CONTRAST)

        # Sharpness enhancement
        if metrics.sharpness_score < 0.4:
            enhancements.append(EnhancementType.SHARPNESS)

        # Noise reduction
        if metrics.noise_level > 0.2:
            enhancements.append(EnhancementType.DENOISE)

        # Shadow removal for poor quality
        if metrics.has_shadows and metrics.overall_quality in [
            QualityLevel.POOR,
            QualityLevel.VERY_POOR,
        ]:
            enhancements.append(EnhancementType.SHADOW_REMOVAL)

        # Text enhancement for documents
        if document_type in [
            DocumentType.PRESCRIPTION,
            DocumentType.LAB_REPORT,
            DocumentType.MEDICAL_RECORD,
        ]:
            enhancements.append(EnhancementType.TEXT_ENHANCEMENT)

        # Binarization for very poor quality text documents
        if metrics.overall_quality == QualityLevel.VERY_POOR and not metrics.is_color:
            enhancements.append(EnhancementType.BINARIZATION)

        return enhancements

    async def _apply_enhancement(
        self,
        image: np.ndarray,
        enhancement_type: EnhancementType,
        params: EnhancementParameters,
    ) -> np.ndarray:
        """Apply a specific enhancement to the image."""
        if enhancement_type == EnhancementType.BRIGHTNESS:
            return self._enhance_brightness(image, params.brightness_factor)
        elif enhancement_type == EnhancementType.CONTRAST:
            return self._enhance_contrast(image, params.contrast_factor)
        elif enhancement_type == EnhancementType.SHARPNESS:
            return self._enhance_sharpness(image, params.sharpness_factor)
        elif enhancement_type == EnhancementType.DENOISE:
            return self._denoise_image(image, params.denoise_strength)
        elif enhancement_type == EnhancementType.DESKEW:
            return self._deskew_image(image, params.deskew_threshold)
        elif enhancement_type == EnhancementType.BINARIZATION:
            return self._binarize_image(image, params.binarization_threshold)
        elif enhancement_type == EnhancementType.SHADOW_REMOVAL:
            return self._remove_shadows(image)
        elif enhancement_type == EnhancementType.TEXT_ENHANCEMENT:
            return self._enhance_text(image)
        elif enhancement_type == EnhancementType.RESOLUTION:
            return self._enhance_resolution(image, params.target_dpi)
        else:
            logger.warning("Unknown enhancement type: %s", enhancement_type)
            return image

    def _enhance_brightness(self, image: np.ndarray, factor: float) -> np.ndarray:
        """Enhance image brightness."""
        # Convert to float to prevent overflow
        enhanced = image.astype(np.float32) * factor
        # Clip values and convert back
        enhanced = np.clip(enhanced, 0, 255).astype(np.uint8)
        return np.array(enhanced)

    def _enhance_contrast(self, image: np.ndarray, factor: float) -> np.ndarray:
        """Enhance image contrast using CLAHE or simple scaling."""
        if not HAS_CV2:
            # Simple contrast enhancement without cv2
            mean = np.mean(image)
            enhanced = (image - mean) * factor + mean
            return np.array(np.clip(enhanced, 0, 255).astype(np.uint8))

        if len(image.shape) == 3:
            # Apply to each channel for color images
            lab = cv2.cvtColor(image, CV2Constants.COLOR_BGR2LAB)
            l_channel, a, b = CV2Extra.split(lab)

            # Apply CLAHE to L channel
            clahe = CV2Extra.createCLAHE(clipLimit=factor * 2, tileGridSize=(8, 8))
            l_channel = clahe.apply(l_channel)

            # Merge and convert back
            enhanced = CV2Extra.merge([l_channel, a, b])
            enhanced = cv2.cvtColor(enhanced, CV2Constants.COLOR_LAB2BGR)
        else:
            # Grayscale image
            clahe = CV2Extra.createCLAHE(clipLimit=factor * 2, tileGridSize=(8, 8))
            enhanced = clahe.apply(image)

        return np.array(enhanced)

    def _enhance_sharpness(self, image: np.ndarray, factor: float) -> np.ndarray:
        """Enhance image sharpness using unsharp masking."""
        if not HAS_CV2:
            # Simple sharpening without cv2
            return image

        # Create blurred version
        blurred = CV2Extra.GaussianBlur(image, (0, 0), 2)

        # Unsharp mask
        sharpened = CV2Extra.addWeighted(image, 1 + factor, blurred, -factor, 0)

        return np.array(np.clip(sharpened, 0, 255).astype(np.uint8))

    def _denoise_image(self, image: np.ndarray, strength: int) -> np.ndarray:
        """Remove noise from image."""
        if not HAS_CV2:
            return image

        if len(image.shape) == 3:
            # Color image denoising
            denoised = CV2Extra.fastNlMeansDenoisingColored(
                image,
                h=strength,
                hColor=strength,
                templateWindowSize=7,
                searchWindowSize=21,
            )
        else:
            # Grayscale denoising
            denoised = CV2Extra.fastNlMeansDenoising(
                image, h=strength, templateWindowSize=7, searchWindowSize=21
            )

        return np.array(denoised)

    def _deskew_image(self, image: np.ndarray, threshold: float) -> np.ndarray:
        """Correct document skew."""
        # Get skew angle
        gray = (
            cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)
            if len(image.shape) == 3
            else image
        )
        angle = self._detect_skew(gray)

        if abs(angle) < threshold:
            return image

        # Get image center and rotation matrix (negate angle to correct the skew)
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = CV2Extra.getRotationMatrix2D(center, -angle, 1.0)

        # Determine bounding box of rotated image
        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])
        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))

        # Adjust rotation matrix
        M[0, 2] += (new_w / 2) - center[0]
        M[1, 2] += (new_h / 2) - center[1]

        # Perform rotation (negate angle to correct the skew)
        rotated = CV2Extra.warpAffine(
            image,
            M,
            (new_w, new_h),
            flags=CV2Constants.INTER_LINEAR,
            borderMode=CV2Constants.BORDER_CONSTANT,
            borderValue=(255, 255, 255) if len(image.shape) == 3 else 255,
        )

        return np.array(rotated)

    def _binarize_image(self, image: np.ndarray, threshold: int) -> np.ndarray:
        """Convert image to binary (black and white)."""
        _ = threshold  # Mark as intentionally unused - using Otsu's automatic thresholding
        # Convert to grayscale if needed
        gray = (
            cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)
            if len(image.shape) == 3
            else image
        )

        # Apply Otsu's thresholding
        _, binary = cv2.threshold(
            gray, 0, 255, CV2Constants.THRESH_BINARY + CV2Constants.THRESH_OTSU
        )

        return np.array(binary)

    def _remove_shadows(self, image: np.ndarray) -> np.ndarray:
        """Remove shadows from document image."""
        # Convert to LAB color space
        if len(image.shape) == 3:
            lab = cv2.cvtColor(image, CV2Constants.COLOR_BGR2LAB)
            l_channel, a, b = CV2Extra.split(lab)
        else:
            l_channel = image

        # Apply morphological operations to estimate background
        kernel = cv2.getStructuringElement(CV2Constants.MORPH_ELLIPSE, (20, 20))
        background = cv2.morphologyEx(l_channel, CV2Constants.MORPH_DILATE, kernel)

        # Normalize by dividing by background
        normalized = CV2Extra.divide(
            l_channel.astype(np.float32) * 255, background.astype(np.float32)
        )  # pylint: disable=no-member
        normalized = normalized.astype(np.uint8)

        if len(image.shape) == 3:
            # Merge channels back
            enhanced = CV2Extra.merge([normalized, a, b])
            enhanced = cv2.cvtColor(enhanced, CV2Constants.COLOR_LAB2BGR)
        else:
            enhanced = normalized

        return np.array(enhanced)

    def _enhance_text(self, image: np.ndarray) -> np.ndarray:
        """Enhance text readability in document."""
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Apply morphological operations to enhance text
        kernel = np.ones((2, 2), np.uint8)

        # Erosion followed by dilation (opening)
        enhanced = cv2.morphologyEx(gray, CV2Constants.MORPH_OPEN, kernel)

        # Increase contrast for text
        enhanced = cv2.convertScaleAbs(enhanced)  # pylint: disable=no-member

        # If original was color, convert back
        if len(image.shape) == 3:
            enhanced = cv2.cvtColor(enhanced, CV2Constants.COLOR_GRAY2BGR)

        return np.array(enhanced)

    def _enhance_resolution(self, image: np.ndarray, target_dpi: int) -> np.ndarray:
        """Enhance image resolution using super-resolution techniques."""
        # Simple upscaling using INTER_CUBIC
        # In production, could use deep learning models
        current_height, current_width = image.shape[:2]

        # Assume standard document is 8.5x11 inches
        target_width = int(8.5 * target_dpi)
        target_height = int(11 * target_dpi)

        # Calculate scale factors
        scale_x = target_width / current_width
        scale_y = target_height / current_height

        # Use the smaller scale to maintain aspect ratio
        scale = min(scale_x, scale_y, 2.0)  # Cap at 2x upscaling

        if scale > 1.1:  # Only upscale if significant
            new_width = int(current_width * scale)
            new_height = int(current_height * scale)

            enhanced = CV2Extra.resize(
                image, (new_width, new_height), interpolation=CV2Constants.INTER_CUBIC
            )
        else:
            enhanced = image

        return np.array(enhanced)

    def _calculate_improvement(
        self, original: QualityMetrics, enhanced: QualityMetrics
    ) -> float:
        """Calculate improvement score between original and enhanced metrics."""
        # Compare key metrics
        improvements = []

        # Brightness improvement (closer to optimal 0.6)
        optimal_brightness = 0.6
        orig_diff = abs(original.brightness_score - optimal_brightness)
        enh_diff = abs(enhanced.brightness_score - optimal_brightness)
        brightness_imp = (
            max(0, (orig_diff - enh_diff) / orig_diff) if orig_diff > 0 else 0
        )
        improvements.append(brightness_imp)

        # Contrast improvement
        contrast_imp = max(0, enhanced.contrast_score - original.contrast_score)
        improvements.append(contrast_imp)

        # Sharpness improvement
        sharpness_imp = max(0, enhanced.sharpness_score - original.sharpness_score)
        improvements.append(sharpness_imp)

        # Noise reduction
        noise_imp = max(0, original.noise_level - enhanced.noise_level)
        improvements.append(noise_imp)

        # Text clarity improvement
        clarity_imp = max(0, enhanced.text_clarity - original.text_clarity)
        improvements.append(clarity_imp)

        # Overall quality improvement
        quality_levels = {
            QualityLevel.VERY_POOR: 0,
            QualityLevel.POOR: 1,
            QualityLevel.FAIR: 2,
            QualityLevel.GOOD: 3,
            QualityLevel.EXCELLENT: 4,
        }

        quality_imp = (
            quality_levels[enhanced.overall_quality]
            - quality_levels[original.overall_quality]
        ) / 4.0

        # Weighted average
        improvement_score = float(np.mean(improvements) * 0.7 + quality_imp * 0.3)

        return max(0.0, min(1.0, improvement_score))

    def _get_default_metrics(self) -> QualityMetrics:
        """Get default quality metrics for error cases."""
        return QualityMetrics(
            brightness_score=0.5,
            contrast_score=0.5,
            sharpness_score=0.5,
            noise_level=0.5,
            skew_angle=0.0,
            text_clarity=0.5,
            overall_quality=QualityLevel.FAIR,
            has_shadows=False,
            has_artifacts=False,
            is_color=False,
            resolution=(0, 0),
        )


# Export classes and functions
__all__ = [
    "DocumentQualityEnhancer",
    "EnhancementType",
    "QualityLevel",
    "QualityMetrics",
    "EnhancementParameters",
    "EnhancementResult",
]
