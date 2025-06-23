"""Duplicate detection module for medical images."""

import hashlib
import logging
from typing import Dict, List, Tuple

import numpy as np

from ..document_processing.cv2_wrapper import (
    HAS_CV2,
    CV2Constants,
    CV2Extra,
)
from ..document_processing.cv2_wrapper import CV2Operations as cv2

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Detect duplicate medical images."""

    def __init__(self) -> None:
        """Initialize duplicate detector."""
        self.hash_cache: Dict[str, str] = {}

    def find_duplicates(self, images: List[Tuple[str, np.ndarray]]) -> List[List[str]]:
        """Find duplicate images in a collection."""
        duplicates: Dict[str, List[str]] = {}

        for image_id, image in images:
            # Calculate image hash
            img_hash = self._calculate_hash(image)

            if img_hash in duplicates:
                duplicates[img_hash].append(image_id)
            else:
                duplicates[img_hash] = [image_id]

        # Return groups of duplicates
        return [group for group in duplicates.values() if len(group) > 1]

    def _calculate_hash(self, image: np.ndarray) -> str:
        """Calculate perceptual hash of image."""
        # Check if cv2 is available
        if not HAS_CV2:
            # Simple hash without cv2
            # Downsample by taking every nth pixel
            step = max(image.shape[0] // 64, image.shape[1] // 64, 1)
            downsampled = image[::step, ::step]
            return hashlib.md5(downsampled.tobytes(), usedforsecurity=False).hexdigest()

        # Resize to standard size
        resized = CV2Extra.resize(image, (64, 64))

        # Convert to grayscale if needed
        if len(resized.shape) == 3:
            resized = cv2.cvtColor(resized, CV2Constants.COLOR_BGR2GRAY)

        # Calculate average
        avg = np.mean(resized)

        # Create binary hash
        binary = (resized > avg).astype(np.uint8)

        # Convert to hex string
        return hashlib.md5(binary.tobytes(), usedforsecurity=False).hexdigest()
