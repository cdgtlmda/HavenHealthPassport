"""Image enhancement module for medical images."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np

from ..document_processing.cv2_wrapper import (
    HAS_CV2,
    CV2Constants,
    CV2Extra,
)
from ..document_processing.cv2_wrapper import CV2Operations as cv2

logger = logging.getLogger(__name__)


class EnhancementType(Enum):
    """Types of image enhancement."""

    CONTRAST = "contrast"
    BRIGHTNESS = "brightness"
    SHARPNESS = "sharpness"
    EDGE = "edge"
    DENOISE = "denoise"
    HISTOGRAM = "histogram"
    ADAPTIVE = "adaptive"


@dataclass
class EnhancementConfig:
    """Configuration for image enhancement."""

    enhancement_types: Optional[List[EnhancementType]] = None
    contrast_factor: float = 1.5
    brightness_offset: int = 0
    sharpness_amount: float = 1.0
    denoise_strength: int = 10
    adaptive_clip_limit: float = 2.0
    adaptive_grid_size: Tuple[int, int] = (8, 8)

    def __post_init__(self) -> None:
        """Initialize default enhancement types if not provided."""
        if self.enhancement_types is None:
            self.enhancement_types = [EnhancementType.CONTRAST, EnhancementType.DENOISE]


class ImageEnhancer:
    """Enhance medical images for better visibility and analysis."""

    def __init__(self, config: Optional[EnhancementConfig] = None):
        """Initialize image enhancer."""
        self.config = config or EnhancementConfig()

    def enhance(self, image: np.ndarray, auto_detect: bool = True) -> np.ndarray:
        """Apply enhancement pipeline to image."""
        enhanced = image.copy()

        if auto_detect:
            # Auto-detect needed enhancements
            needed_enhancements = self._detect_needed_enhancements(image)
            logger.info(
                "Auto-detected enhancements: %s", [e.value for e in needed_enhancements]
            )
        else:
            needed_enhancements = self.config.enhancement_types or []

        # Apply each enhancement
        for enhancement in needed_enhancements:
            if enhancement == EnhancementType.CONTRAST:
                enhanced = self._enhance_contrast(enhanced)
            elif enhancement == EnhancementType.BRIGHTNESS:
                enhanced = self._adjust_brightness(enhanced)
            elif enhancement == EnhancementType.SHARPNESS:
                enhanced = self._enhance_sharpness(enhanced)
            elif enhancement == EnhancementType.EDGE:
                enhanced = self._enhance_edges(enhanced)
            elif enhancement == EnhancementType.DENOISE:
                enhanced = self._denoise(enhanced)
            elif enhancement == EnhancementType.HISTOGRAM:
                enhanced = self._equalize_histogram(enhanced)
            elif enhancement == EnhancementType.ADAPTIVE:
                enhanced = self._adaptive_enhancement(enhanced)

        return enhanced

    def _detect_needed_enhancements(self, image: np.ndarray) -> list:
        """Auto-detect which enhancements are needed."""
        needed = []

        # Convert to grayscale for analysis
        if HAS_CV2:
            gray = (
                cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)
                if len(image.shape) == 3
                else image
            )
        else:
            # Fallback for grayscale conversion without cv2
            if len(image.shape) == 3:
                gray = np.dot(image[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
            else:
                gray = image

        # Check contrast
        if self._is_low_contrast(gray):
            needed.append(EnhancementType.CONTRAST)

        # Check brightness
        mean_brightness = np.mean(gray)
        if mean_brightness < 50 or mean_brightness > 200:
            needed.append(EnhancementType.BRIGHTNESS)

        # Check noise level
        if self._is_noisy(gray):
            needed.append(EnhancementType.DENOISE)

        # Check sharpness
        if self._is_blurry(gray):
            needed.append(EnhancementType.SHARPNESS)

        return needed

    def _is_low_contrast(self, gray: np.ndarray) -> bool:
        """Check if image has low contrast."""
        if not HAS_CV2:
            # Simple contrast check without cv2
            std_dev = np.std(gray)
            return bool(std_dev < 30)

        hist = CV2Extra.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten() / hist.sum()

        # Calculate histogram spread
        cumsum = np.cumsum(hist)
        lower_percentile = np.argmax(cumsum >= 0.05)
        upper_percentile = np.argmax(cumsum >= 0.95)

        spread = upper_percentile - lower_percentile
        return bool(spread < 100)  # Low contrast if spread is small

    def _is_noisy(self, gray: np.ndarray) -> bool:
        """Check if image is noisy."""
        if not HAS_CV2:
            return False  # Skip noise detection without cv2

        # Calculate noise using Laplacian variance
        laplacian = CV2Extra.Laplacian(gray, CV2Constants.CV_64F)
        variance = laplacian.var()

        return bool(variance > 500)  # Threshold for noise detection

    def _is_blurry(self, gray: np.ndarray) -> bool:
        """Check if image is blurry."""
        if not HAS_CV2:
            return False  # Skip blur detection without cv2

        # Calculate blur using Laplacian variance
        laplacian = CV2Extra.Laplacian(gray, CV2Constants.CV_64F)
        variance = laplacian.var()

        return bool(variance < 100)  # Threshold for blur detection

    def _enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """Enhance image contrast."""
        if not HAS_CV2:
            # Simple contrast enhancement without cv2
            mean = np.mean(image)
            enhanced = (image - mean) * 1.5 + mean
            return np.array(np.clip(enhanced, 0, 255).astype(np.uint8))

        if len(image.shape) == 2:
            # Apply CLAHE for grayscale
            clahe = CV2Extra.createCLAHE(
                clipLimit=self.config.adaptive_clip_limit,
                tileGridSize=self.config.adaptive_grid_size,
            )
            return np.array(clahe.apply(image))
        else:
            # Apply to each channel
            lab = cv2.cvtColor(image, CV2Constants.COLOR_BGR2LAB)
            lightness, a, b = CV2Extra.split(lab)

            clahe = CV2Extra.createCLAHE(
                clipLimit=self.config.adaptive_clip_limit,
                tileGridSize=self.config.adaptive_grid_size,
            )
            lightness = clahe.apply(lightness)

            enhanced = CV2Extra.merge([lightness, a, b])
            return np.array(cv2.cvtColor(enhanced, CV2Constants.COLOR_LAB2BGR))

    def _adjust_brightness(self, image: np.ndarray) -> np.ndarray:
        """Adjust image brightness."""
        # Calculate target brightness adjustment
        gray = (
            cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)
            if len(image.shape) == 3
            else image
        )
        mean_brightness = np.mean(gray)

        # Target brightness is 128 (middle of range)
        brightness_adjustment = 128 - mean_brightness
        brightness_adjustment = np.clip(brightness_adjustment, -50, 50)

        # Apply brightness adjustment
        adjusted = cv2.convertScaleAbs(image, alpha=1.0, beta=brightness_adjustment)
        return np.array(adjusted)

    def _enhance_sharpness(self, image: np.ndarray) -> np.ndarray:
        """Enhance image sharpness."""
        # Create sharpening kernel
        kernel = (
            np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
            * self.config.sharpness_amount
        )

        # Apply kernel
        sharpened = CV2Extra.filter2D(image, -1, kernel)

        # Blend with original
        alpha = 0.7
        enhanced = CV2Extra.addWeighted(image, 1 - alpha, sharpened, alpha, 0)

        return np.array(enhanced)

    def _enhance_edges(self, image: np.ndarray) -> np.ndarray:
        """Enhance edges in the image."""
        # Convert to grayscale if needed
        gray = (
            cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)
            if len(image.shape) == 3
            else image
        )

        # Apply Sobel edge detection
        sobelx = cv2.Sobel(gray, CV2Constants.CV_64F, 1, 0)  # pylint: disable=no-member
        sobely = cv2.Sobel(gray, CV2Constants.CV_64F, 0, 1)  # pylint: disable=no-member

        # Combine gradients
        magnitude = np.sqrt(sobelx**2 + sobely**2)
        magnitude = np.clip(magnitude, 0, 255).astype(np.uint8)

        # Add edges back to original
        if len(image.shape) == 3:
            magnitude = cv2.cvtColor(magnitude, CV2Constants.COLOR_GRAY2BGR)

        enhanced = CV2Extra.addWeighted(image, 0.8, magnitude, 0.2, 0)
        return np.array(enhanced)

    def _denoise(self, image: np.ndarray) -> np.ndarray:
        """Remove noise from image."""
        if len(image.shape) == 2:
            return np.array(
                CV2Extra.fastNlMeansDenoising(
                    image,
                    h=self.config.denoise_strength,
                    templateWindowSize=7,
                    searchWindowSize=21,
                )
            )
        else:
            return np.array(
                CV2Extra.fastNlMeansDenoisingColored(
                    image,
                    h=self.config.denoise_strength,
                    hColor=self.config.denoise_strength,
                    templateWindowSize=7,
                    searchWindowSize=21,
                )
            )

    def _equalize_histogram(self, image: np.ndarray) -> np.ndarray:
        """Apply histogram equalization."""
        if len(image.shape) == 2:
            return np.array(CV2Extra.equalizeHist(image))
        else:
            # Convert to YUV and equalize Y channel
            yuv = cv2.cvtColor(image, CV2Constants.COLOR_BGR2YUV)
            yuv[:, :, 0] = CV2Extra.equalizeHist(yuv[:, :, 0])
            return np.array(cv2.cvtColor(yuv, CV2Constants.COLOR_YUV2BGR))

    def _adaptive_enhancement(self, image: np.ndarray) -> np.ndarray:
        """Apply adaptive enhancement based on local statistics."""
        return self._enhance_contrast(image)
