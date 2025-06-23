"""Metadata extraction module for medical images."""

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


class MetadataExtractor:
    """Extract metadata from medical images."""

    def extract_metadata(
        self, file_path: str, image_array: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """Extract all available metadata from medical image file."""
        metadata = {
            "file_info": self._extract_file_info(file_path),
            "image_properties": {},
            "exif_data": {},
            "dicom_data": {},
            "technical_data": {},
        }

        # Try DICOM extraction first
        if file_path.lower().endswith(".dcm"):
            try:
                metadata["dicom_data"] = self._extract_dicom_metadata(file_path)
            except (ImportError, AttributeError, ValueError, OSError) as e:
                logger.warning("Failed to extract DICOM metadata: %s", e)

        # Extract EXIF data
        try:
            metadata["exif_data"] = self._extract_exif_data(file_path)
        except (ImportError, AttributeError, ValueError, OSError) as e:
            logger.warning("Failed to extract EXIF data: %s", e)

        # Extract image properties
        if image_array is not None:
            metadata["image_properties"] = self._extract_image_properties(image_array)

        return metadata

    def _extract_file_info(self, file_path: str) -> Dict[str, Any]:
        """Extract basic file information."""
        stat = os.stat(file_path)
        return {
            "filename": os.path.basename(file_path),
            "size_bytes": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }

    def _extract_dicom_metadata(self, dicom_file_path: str) -> Dict[str, Any]:
        """Extract DICOM metadata.

        Args:
            dicom_file_path: Path to DICOM file (placeholder implementation)
        """
        # Placeholder - requires pydicom which may not be installed
        logger.debug("Would extract DICOM metadata from: %s", dicom_file_path)
        return {}

    def _extract_exif_data(self, image_file_path: str) -> Dict[str, Any]:
        """Extract EXIF data from image.

        Args:
            image_file_path: Path to image file (placeholder implementation)
        """
        # Placeholder - requires exifread which may not be installed
        logger.debug("Would extract EXIF data from: %s", image_file_path)
        return {}

    def _extract_image_properties(self, image_array: np.ndarray) -> Dict[str, Any]:
        """Extract properties from image array."""
        return {
            "shape": image_array.shape,
            "dtype": str(image_array.dtype),
            "min_value": float(np.min(image_array)),
            "max_value": float(np.max(image_array)),
            "mean_value": float(np.mean(image_array)),
            "std_value": float(np.std(image_array)),
        }
