"""
Image Utilities Module.

Provides utility functions for image validation, format detection, and basic
image operations used throughout the Haven Health Passport system.
"""

import io
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np
from PIL import Image


class ImageFormat(Enum):
    """Supported image formats."""

    JPEG = "jpeg"
    PNG = "png"
    GIF = "gif"
    BMP = "bmp"
    TIFF = "tiff"
    WEBP = "webp"
    PDF = "pdf"
    UNKNOWN = "unknown"


class ImageValidator:
    """Validates and processes image data."""

    SUPPORTED_FORMATS = {
        ImageFormat.JPEG: ["jpg", "jpeg"],
        ImageFormat.PNG: ["png"],
        ImageFormat.GIF: ["gif"],
        ImageFormat.BMP: ["bmp"],
        ImageFormat.TIFF: ["tiff", "tif"],
        ImageFormat.WEBP: ["webp"],
    }

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    MIN_DIMENSION = 50  # Minimum width/height
    MAX_DIMENSION = 10000  # Maximum width/height

    def validate_image(
        self, image_data: Union[bytes, str, Path]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate image data.

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            if isinstance(image_data, (str, Path)):
                # File path
                path = Path(image_data)
                if not path.exists():
                    return False, "File does not exist"

                if path.stat().st_size > self.MAX_FILE_SIZE:
                    return (
                        False,
                        f"File size exceeds {self.MAX_FILE_SIZE / 1024 / 1024}MB limit",
                    )

                with open(path, "rb") as f:
                    image_bytes = f.read()
            else:
                # Bytes
                image_bytes = image_data
                if len(image_bytes) > self.MAX_FILE_SIZE:
                    return (
                        False,
                        f"Image size exceeds {self.MAX_FILE_SIZE / 1024 / 1024}MB limit",
                    )

            # Check format
            image_format = self.detect_format(image_bytes)
            if image_format == ImageFormat.UNKNOWN:
                return False, "Unsupported image format"

            # Validate dimensions
            try:
                img = Image.open(io.BytesIO(image_bytes))
                width, height = img.size

                if width < self.MIN_DIMENSION or height < self.MIN_DIMENSION:
                    return (
                        False,
                        f"Image dimensions too small (minimum {self.MIN_DIMENSION}px)",
                    )

                if width > self.MAX_DIMENSION or height > self.MAX_DIMENSION:
                    return (
                        False,
                        f"Image dimensions too large (maximum {self.MAX_DIMENSION}px)",
                    )

            except OSError as e:
                return False, f"Failed to read image: {str(e)}"

            return True, None

        except (OSError, ValueError) as e:
            return False, f"Validation error: {str(e)}"

    def detect_format(self, image_data: bytes) -> ImageFormat:
        """Detect image format from bytes."""
        # Check file signatures
        if image_data[:2] == b"\xff\xd8":
            return ImageFormat.JPEG
        elif image_data[:8] == b"\x89PNG\r\n\x1a\n":
            return ImageFormat.PNG
        elif image_data[:6] in (b"GIF87a", b"GIF89a"):
            return ImageFormat.GIF
        elif image_data[:2] == b"BM":
            return ImageFormat.BMP
        elif image_data[:4] in (b"II*\x00", b"MM\x00*"):
            return ImageFormat.TIFF
        elif image_data.startswith(b"RIFF") and b"WEBP" in image_data[:12]:
            return ImageFormat.WEBP

        return ImageFormat.UNKNOWN

    def get_image_info(self, image_data: Union[bytes, np.ndarray, Image.Image]) -> dict:
        """Get basic information about an image."""
        img: Image.Image
        if isinstance(image_data, bytes):
            img = Image.open(io.BytesIO(image_data))
        elif isinstance(image_data, np.ndarray):
            img = Image.fromarray(image_data)
        else:
            img = image_data

        return {
            "width": img.width,
            "height": img.height,
            "mode": img.mode,
            "format": img.format,
            "has_transparency": img.mode in ("RGBA", "LA")
            or (img.mode == "P" and "transparency" in img.info),
        }


__all__ = ["ImageValidator", "ImageFormat"]
