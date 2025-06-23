"""Image validation module for medical images."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of image validation."""

    is_valid: bool
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]


class ImageValidator:
    """Validate medical images for clinical use."""

    def validate(
        self, image: np.ndarray, modality: str = "general"
    ) -> ValidationResult:
        """Validate medical image."""
        errors = []
        warnings = []

        # Check image dimensions
        if image.ndim < 2 or image.ndim > 3:
            errors.append("Invalid image dimensions")

        # Check image size
        if image.shape[0] < 64 or image.shape[1] < 64:
            errors.append("Image too small for diagnostic use")

        # Check data type
        if image.dtype not in [np.uint8, np.uint16, np.float32, np.float64]:
            warnings.append(f"Unusual data type: {image.dtype}")

        # Check for empty image
        if np.all(image == 0):
            errors.append("Image appears to be empty")

        # Modality-specific validation
        if modality == "xray" and len(image.shape) == 3:
            warnings.append("X-ray images should be grayscale")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={"shape": image.shape, "dtype": str(image.dtype)},
        )
