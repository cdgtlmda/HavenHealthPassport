"""Image indexing module for medical images."""

import logging
from dataclasses import dataclass
from typing import Any, Dict

import numpy as np

from ..document_processing.cv2_wrapper import (
    HAS_CV2,
    CV2Extra,
)

logger = logging.getLogger(__name__)


@dataclass
class ImageIndex:
    """Index entry for a medical image."""

    image_id: str
    modality: str
    body_part: str
    features: np.ndarray
    metadata: Dict[str, Any]


class ImageIndexer:
    """Index medical images for efficient search and retrieval."""

    def __init__(self) -> None:
        """Initialize image indexer."""
        self.index: Dict[str, Any] = {}
        self.feature_extractor = None

    def add_image(
        self, image_id: str, image: np.ndarray, metadata: Dict[str, Any]
    ) -> None:
        """Add image to index."""
        # Extract features
        features = self._extract_features(image)

        # Create index entry
        entry = ImageIndex(
            image_id=image_id,
            modality=metadata.get("modality", "unknown"),
            body_part=metadata.get("body_part", "unknown"),
            features=features,
            metadata=metadata,
        )

        self.index[image_id] = entry
        logger.info("Added image %s to index", image_id)

    def _extract_features(self, image: np.ndarray) -> np.ndarray:
        """Extract features for indexing."""
        # Simple feature extraction - histogram
        if not HAS_CV2:
            # Manual histogram calculation
            hist, _ = np.histogram(image.flatten(), bins=256, range=(0, 256))
            return hist.astype(np.float32)
        else:
            hist = CV2Extra.calcHist([image], [0], None, [256], [0, 256])
            return np.array(hist.flatten())
