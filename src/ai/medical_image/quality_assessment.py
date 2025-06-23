"""Quality assessment module for medical images."""

import logging
from dataclasses import dataclass

import numpy as np

from ..document_processing.cv2_wrapper import (
    HAS_CV2,
    CV2Constants,
    CV2Extra,
)
from ..document_processing.cv2_wrapper import CV2Operations as cv2

logger = logging.getLogger(__name__)


@dataclass
class QualityMetrics:
    """Image quality metrics."""

    sharpness: float
    contrast: float
    brightness: float
    noise_level: float
    artifact_score: float
    overall_score: float


class QualityAssessor:
    """Assess quality of medical images."""

    def assess_quality(self, image: np.ndarray) -> QualityMetrics:
        """Assess overall image quality."""
        if not HAS_CV2:
            # Basic quality assessment without cv2
            if len(image.shape) == 3:
                gray = np.dot(image[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
            else:
                gray = image
        else:
            gray = (
                cv2.cvtColor(image, CV2Constants.COLOR_BGR2GRAY)
                if len(image.shape) == 3
                else image
            )

        sharpness = self._assess_sharpness(gray)
        contrast = self._assess_contrast(gray)
        brightness = self._assess_brightness(gray)
        noise_level = self._assess_noise(gray)
        artifact_score = self._assess_artifacts(gray)

        overall_score = np.mean(
            [sharpness, contrast, brightness, 1 - noise_level, 1 - artifact_score]
        )

        return QualityMetrics(
            sharpness=sharpness,
            contrast=contrast,
            brightness=brightness,
            noise_level=noise_level,
            artifact_score=artifact_score,
            overall_score=float(overall_score),
        )

    def _assess_contrast(self, gray: np.ndarray) -> float:
        """Assess image contrast."""
        return float(gray.std()) / 255.0

    def _assess_brightness(self, gray: np.ndarray) -> float:
        """Assess image brightness."""
        mean = float(gray.mean())
        # Optimal range is 100-150
        if 100 <= mean <= 150:
            return 1.0
        else:
            return max(0, 1 - abs(mean - 125) / 125)

    def _assess_noise(self, gray: np.ndarray) -> float:
        """Assess noise level."""
        if not HAS_CV2:
            # Simple noise estimation without cv2
            # Calculate local variance
            h, w = gray.shape
            noise_sum = 0.0
            count = 0
            for i in range(1, h - 1):
                for j in range(1, w - 1):
                    local = gray[i - 1 : i + 2, j - 1 : j + 2].astype(np.float32)
                    noise_sum += float(np.var(local))
                    count += 1
            return min(1.0, noise_sum / (count * 255))

        # Use median filter to estimate noise
        median = CV2Extra.medianBlur(gray, 5)
        noise = np.abs(gray.astype(np.float32) - median.astype(np.float32))
        return float(np.mean(noise) / 255.0)

    def _assess_artifacts(self, gray: np.ndarray) -> float:
        """Assess compression artifacts."""
        if not HAS_CV2:
            # Simple artifact detection without cv2
            # Look for blocky patterns
            h, w = gray.shape
            block_size = 8
            artifact_score = 0
            for i in range(0, h - block_size, block_size):
                for j in range(0, w - block_size, block_size):
                    block = gray[i : i + block_size, j : j + block_size]
                    # Check if block has uniform values (compression artifact)
                    if np.std(block) < 5:
                        artifact_score += 1
            return float(artifact_score / ((h // block_size) * (w // block_size)))

        # Simple artifact detection using edge analysis
        edges = cv2.Canny(gray, 50, 150)
        return float(np.sum(edges > 0) / (gray.shape[0] * gray.shape[1]))

    def _assess_sharpness(self, gray: np.ndarray) -> float:
        """Assess image sharpness using Laplacian variance."""
        if not HAS_CV2:
            # Simple sharpness estimation without cv2
            # Use gradient magnitude
            gy, gx = np.gradient(gray.astype(np.float32))
            gnorm = np.sqrt(gx**2 + gy**2)
            sharpness = np.mean(gnorm)
            return float(min(sharpness / 100, 1.0))  # Normalize to 0-1

        laplacian = CV2Extra.Laplacian(gray, CV2Constants.CV_64F)
        variance = laplacian.var()
        return float(min(variance / 1000, 1.0))  # Normalize to 0-1
