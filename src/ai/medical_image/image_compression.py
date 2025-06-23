"""Image compression module for medical images."""

import io
import logging
from enum import Enum

import numpy as np
from PIL import Image

from ..document_processing.cv2_wrapper import (
    HAS_CV2,
    CV2Constants,
)
from ..document_processing.cv2_wrapper import CV2Operations as cv2

logger = logging.getLogger(__name__)


class CompressionMethod(Enum):
    """Compression methods for medical images."""

    LOSSLESS = "lossless"
    LOSSY = "lossy"
    DICOM_COMPATIBLE = "dicom_compatible"
    WEB_OPTIMIZED = "web_optimized"


class ImageCompressor:
    """Compress medical images while preserving diagnostic quality."""

    def __init__(self) -> None:
        """Initialize compressor."""
        self.quality_thresholds = {
            CompressionMethod.LOSSLESS: 100,
            CompressionMethod.LOSSY: 85,
            CompressionMethod.DICOM_COMPATIBLE: 95,
            CompressionMethod.WEB_OPTIMIZED: 80,
        }

    def compress(
        self,
        image: np.ndarray,
        method: CompressionMethod = CompressionMethod.DICOM_COMPATIBLE,
    ) -> bytes:
        """Compress image using specified method."""
        quality = self.quality_thresholds[method]

        if not HAS_CV2:
            # Fallback to PIL
            img = Image.fromarray(image)
            buffer = io.BytesIO()

            if method == CompressionMethod.LOSSLESS:
                img.save(buffer, format="PNG", compress_level=9)
            else:
                img.save(buffer, format="JPEG", quality=quality)

            return buffer.getvalue()

        if method == CompressionMethod.LOSSLESS:
            # PNG compression (lossless)
            encode_param = [CV2Constants.IMWRITE_PNG_COMPRESSION, 9]
            _, encoded = cv2.imencode(".png", image, encode_param)
        else:
            # JPEG compression with quality setting
            encode_param = [CV2Constants.IMWRITE_JPEG_QUALITY, quality]
            _, encoded = cv2.imencode(".jpg", image, encode_param)

        return bytes(encoded.tobytes())

    def estimate_compression_ratio(
        self, original_size: int, compressed_size: int
    ) -> float:
        """Calculate compression ratio."""
        return original_size / compressed_size if compressed_size > 0 else 0.0
