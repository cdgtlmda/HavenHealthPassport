"""Image preprocessing module for medical images."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

import numpy as np

from ..document_processing.cv2_wrapper import (
    HAS_CV2,
    CV2Constants,
    CV2Extra,
)
from ..document_processing.cv2_wrapper import CV2Operations as cv2

logger = logging.getLogger(__name__)


class PreprocessingMode(Enum):
    """Preprocessing modes for different image types."""

    XRAY = "xray"
    CT_SCAN = "ct_scan"
    MRI = "mri"
    ULTRASOUND = "ultrasound"
    MAMMOGRAPHY = "mammography"
    GENERAL = "general"


@dataclass
class PreprocessingConfig:
    """Configuration for image preprocessing."""

    mode: PreprocessingMode = PreprocessingMode.GENERAL
    target_size: Optional[Tuple[int, int]] = None
    normalize: bool = True
    denoise: bool = True
    enhance_contrast: bool = True
    remove_artifacts: bool = True
    preserve_aspect_ratio: bool = True
    histogram_equalization: bool = False
    clahe_clip_limit: float = 2.0
    clahe_grid_size: Tuple[int, int] = (8, 8)


class ImagePreprocessor:
    """Preprocess medical images for analysis."""

    def __init__(self, config: Optional[PreprocessingConfig] = None):
        """Initialize preprocessor with configuration."""
        self.config = config or PreprocessingConfig()

    def preprocess(
        self, image: np.ndarray, image_metadata: Optional[Dict[str, Any]] = None
    ) -> np.ndarray:
        """Preprocess medical image according to configuration.

        Args:
            image: Input image
            image_metadata: Optional metadata (currently unused)
        """
        _ = image_metadata  # Mark as used
        logger.info("Preprocessing image with mode: %s", self.config.mode.value)

        # Copy image to avoid modifying original
        processed = image.copy()

        # Apply mode-specific preprocessing
        if self.config.mode == PreprocessingMode.XRAY:
            processed = self._preprocess_xray(processed)
        elif self.config.mode == PreprocessingMode.CT_SCAN:
            processed = self._preprocess_ct(processed)
        elif self.config.mode == PreprocessingMode.MRI:
            processed = self._preprocess_mri(processed)
        elif self.config.mode == PreprocessingMode.ULTRASOUND:
            processed = self._preprocess_ultrasound(processed)
        elif self.config.mode == PreprocessingMode.MAMMOGRAPHY:
            processed = self._preprocess_mammography(processed)

        # Apply general preprocessing steps
        if self.config.denoise:
            processed = self._denoise(processed)

        if self.config.enhance_contrast:
            processed = self._enhance_contrast(processed)

        if self.config.remove_artifacts:
            processed = self._remove_artifacts(processed)

        if self.config.normalize:
            processed = self._normalize(processed)

        if self.config.target_size:
            processed = self._resize(processed)

        return processed

    def _preprocess_xray(self, image: np.ndarray) -> np.ndarray:
        """Specific preprocessing for X-ray images."""
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            if not HAS_CV2:
                image = np.dot(image[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
            else:
                image = cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)

        # Apply CLAHE for better visibility
        if HAS_CV2:
            clahe = CV2Extra.createCLAHE(
                clipLimit=self.config.clahe_clip_limit,
                tileGridSize=self.config.clahe_grid_size,
            )
            image = clahe.apply(image)

        # Remove border artifacts common in X-rays
        image = self._remove_xray_borders(image)

        return image

    def _preprocess_ct(self, image: np.ndarray) -> np.ndarray:
        """Specific preprocessing for CT scan images."""
        # Apply windowing if HU values are provided
        # This is a simplified version - real CT preprocessing would use DICOM metadata
        if image.dtype == np.int16:
            # Apply soft tissue window
            window_center = 40
            window_width = 400
            image = self._apply_windowing(image, window_center, window_width)

        return image

    def _preprocess_mri(self, image: np.ndarray) -> np.ndarray:
        """Specific preprocessing for MRI images."""
        # MRI-specific noise reduction
        if len(image.shape) == 2:
            image = CV2Extra.bilateralFilter(image, 9, 75, 75)

        # Intensity normalization
        image = self._normalize_intensity(image)

        return image

    def _preprocess_ultrasound(self, image: np.ndarray) -> np.ndarray:
        """Specific preprocessing for ultrasound images."""
        # Remove ultrasound-specific artifacts
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)

        # Apply speckle noise reduction
        image = CV2Extra.fastNlMeansDenoising(
            image, h=10, templateWindowSize=7, searchWindowSize=21
        )

        return image

    def _preprocess_mammography(self, image: np.ndarray) -> np.ndarray:
        """Specific preprocessing for mammography images."""
        # Enhance micro-calcifications
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)

        # Apply specialized enhancement
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        image = CV2Extra.filter2D(image, -1, kernel)

        return image

    def _denoise(self, image: np.ndarray) -> np.ndarray:
        """Apply denoising to image."""
        if not HAS_CV2:
            return image

        if len(image.shape) == 2:
            return np.array(
                CV2Extra.fastNlMeansDenoising(
                    image, h=10, templateWindowSize=7, searchWindowSize=21
                )
            )
        else:
            return np.array(
                CV2Extra.fastNlMeansDenoisingColored(
                    image, h=10, hColor=10, templateWindowSize=7, searchWindowSize=21
                )
            )

    def _enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """Enhance image contrast."""
        if len(image.shape) == 2:
            # Apply CLAHE
            clahe = CV2Extra.createCLAHE(
                clipLimit=self.config.clahe_clip_limit,
                tileGridSize=self.config.clahe_grid_size,
            )
            enhanced = clahe.apply(image)
            return np.array(enhanced)
        else:
            # Apply to each channel
            channels = CV2Extra.split(image)
            clahe = CV2Extra.createCLAHE(
                clipLimit=self.config.clahe_clip_limit,
                tileGridSize=self.config.clahe_grid_size,
            )
            channels = [clahe.apply(ch) for ch in channels]
            merged = CV2Extra.merge(channels)
            return np.array(merged)

    def _remove_artifacts(self, image: np.ndarray) -> np.ndarray:
        """Remove common artifacts from medical images."""
        # Simple artifact removal - can be extended
        if len(image.shape) == 2:
            # Morphological operations to remove small artifacts
            kernel = np.ones((3, 3), np.uint8)
            image = cv2.morphologyEx(image, CV2Constants.MORPH_OPEN, kernel)

        return image

    def _normalize(self, image: np.ndarray) -> np.ndarray:
        """Normalize image values."""
        return np.array(
            CV2Extra.normalize(
                image, None, 0, 255, CV2Constants.NORM_MINMAX, dtype=CV2Constants.CV_8U
            )
        )

    def _resize(self, image: np.ndarray) -> np.ndarray:
        """Resize image to target size."""
        if not self.config.target_size:
            return image

        if self.config.preserve_aspect_ratio:
            return self._resize_with_padding(image, self.config.target_size)
        else:
            return np.array(
                CV2Extra.resize(
                    image,
                    self.config.target_size,
                    interpolation=CV2Constants.INTER_LINEAR,
                )
            )

    def _resize_with_padding(
        self, image: np.ndarray, target_size: Tuple[int, int]
    ) -> np.ndarray:
        """Resize image while preserving aspect ratio with padding."""
        h, w = image.shape[:2]
        target_w, target_h = target_size

        # Calculate scaling factor
        scale = min(target_w / w, target_h / h)

        # Calculate new dimensions
        new_w = int(w * scale)
        new_h = int(h * scale)

        # Resize image
        resized = CV2Extra.resize(
            image, (new_w, new_h), interpolation=CV2Constants.INTER_LINEAR
        )

        # Create padded image
        if len(image.shape) == 2:
            padded = np.zeros((target_h, target_w), dtype=image.dtype)
        else:
            padded = np.zeros((target_h, target_w, image.shape[2]), dtype=image.dtype)

        # Calculate padding
        pad_top = (target_h - new_h) // 2
        pad_left = (target_w - new_w) // 2

        # Place resized image in center
        padded[pad_top : pad_top + new_h, pad_left : pad_left + new_w] = resized

        return padded

    def _remove_xray_borders(self, image: np.ndarray) -> np.ndarray:
        """Remove black borders from X-ray images."""
        # Find non-black pixels
        _, thresh = cv2.threshold(image, 10, 255, CV2Constants.THRESH_BINARY)

        # Find contours
        contours, _ = cv2.findContours(
            thresh, CV2Constants.RETR_EXTERNAL, CV2Constants.CHAIN_APPROX_SIMPLE
        )

        if contours:
            # Get bounding box of largest contour
            largest_contour = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest_contour)

            # Crop image
            return image[y : y + h, x : x + w]

        return image

    def _apply_windowing(
        self, image: np.ndarray, center: int, width: int
    ) -> np.ndarray:
        """Apply windowing to CT scan images."""
        min_val = center - width // 2
        max_val = center + width // 2

        windowed = image.copy()
        windowed[windowed < min_val] = min_val
        windowed[windowed > max_val] = max_val

        # Normalize to 0-255
        windowed = ((windowed - min_val) / (max_val - min_val) * 255).astype(np.uint8)

        return windowed

    def _normalize_intensity(self, image: np.ndarray) -> np.ndarray:
        """Normalize intensity distribution."""
        # Percentile-based normalization
        p2, p98 = np.percentile(image, (2, 98))
        image_scaled = np.clip(image, p2, p98)
        image_scaled = ((image_scaled - p2) / (p98 - p2) * 255).astype(np.uint8)

        return np.array(image_scaled)
