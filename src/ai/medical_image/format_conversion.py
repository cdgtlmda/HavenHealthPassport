"""Format conversion module for medical images.

This module handles conversion between medical image formats for FHIR Resource compliance.
Supports conversion and validation of medical imaging data formats.
"""

import datetime
import io
import json
import logging
from enum import Enum

import numpy as np
from PIL import Image

from ..document_processing.cv2_wrapper import HAS_CV2
from ..document_processing.cv2_wrapper import CV2Operations as cv2

# Optional imports for specialized formats
try:
    import pydicom
    from pydicom import dcmwrite
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import generate_uid

    HAS_PYDICOM = True
except ImportError:
    HAS_PYDICOM = False
    pydicom = None  # type: ignore

try:
    import nibabel

    HAS_NIBABEL = True
except ImportError:
    HAS_NIBABEL = False
    nibabel = None

logger = logging.getLogger(__name__)


class ImageFormat(Enum):
    """Supported image formats."""

    DICOM = "dicom"
    PNG = "png"
    JPEG = "jpeg"
    TIFF = "tiff"
    BMP = "bmp"
    NIFTI = "nifti"
    RAW = "raw"


class FormatConverter:
    """Convert between medical image formats."""

    def __init__(self) -> None:
        """Initialize format converter."""
        self.format_extensions = {
            ImageFormat.DICOM: ".dcm",
            ImageFormat.PNG: ".png",
            ImageFormat.JPEG: ".jpg",
            ImageFormat.TIFF: ".tif",
            ImageFormat.BMP: ".bmp",
            ImageFormat.NIFTI: ".nii",
            ImageFormat.RAW: ".raw",
        }

    def convert(
        self, image: np.ndarray, source_format: ImageFormat, to_format: ImageFormat
    ) -> bytes:
        """Convert image from one format to another.

        Args:
            image: Input image array
            source_format: Source format (currently unused)
            to_format: Target format
        """
        _ = source_format  # Mark as used
        if to_format == ImageFormat.PNG:
            return self._to_png(image)
        elif to_format == ImageFormat.JPEG:
            return self._to_jpeg(image)
        elif to_format == ImageFormat.TIFF:
            return self._to_tiff(image)
        elif to_format == ImageFormat.BMP:
            return self._to_bmp(image)
        elif to_format == ImageFormat.DICOM:
            return self._to_dicom(image)
        elif to_format == ImageFormat.NIFTI:
            return self._to_nifti(image)
        elif to_format == ImageFormat.RAW:
            return self._to_raw(image)
        else:
            raise ValueError(f"Unsupported target format: {to_format.value}")

    def _to_png(self, image: np.ndarray) -> bytes:
        """Convert to PNG format."""
        if not HAS_CV2:
            # Use PIL as fallback
            img = Image.fromarray(image)
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return buffer.getvalue()
        _, encoded = cv2.imencode(".png", image)
        return bytes(encoded.tobytes())

    def _to_jpeg(self, image: np.ndarray) -> bytes:
        """Convert to JPEG format."""
        if not HAS_CV2:
            # Use PIL as fallback
            img = Image.fromarray(image)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG")
            return buffer.getvalue()
        _, encoded = cv2.imencode(".jpg", image)
        return bytes(encoded.tobytes())

    def _to_tiff(self, image: np.ndarray) -> bytes:
        """Convert to TIFF format."""
        if not HAS_CV2:
            # Use PIL as fallback
            img = Image.fromarray(image)
            buffer = io.BytesIO()
            img.save(buffer, format="TIFF")
            return buffer.getvalue()
        _, encoded = cv2.imencode(".tif", image)
        return bytes(encoded.tobytes())

    def _to_bmp(self, image: np.ndarray) -> bytes:
        """Convert to BMP format."""
        if not HAS_CV2:
            # Use PIL as fallback
            img = Image.fromarray(image)
            buffer = io.BytesIO()
            img.save(buffer, format="BMP")
            return buffer.getvalue()
        _, encoded = cv2.imencode(".bmp", image)
        return bytes(encoded.tobytes())

    def _to_dicom(self, image: np.ndarray) -> bytes:
        """Convert to DICOM format.

        DICOM conversion requires special handling for medical metadata.
        This implementation provides basic conversion for prototyping.
        Production use should integrate with pydicom for proper DICOM support.
        """
        if not HAS_PYDICOM:
            logger.warning("pydicom not available, cannot convert to DICOM format")
            return b""

        try:

            # Create a basic DICOM dataset
            file_meta = FileMetaDataset()
            file_meta.MediaStorageSOPClassUID = pydicom.uid.SecondaryCaptureImageStorage
            file_meta.MediaStorageSOPInstanceUID = generate_uid()
            file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian

            # Create the FileDataset instance
            ds = FileDataset("", {}, file_meta=file_meta, preamble=b"\0" * 128)

            # Add basic patient and study information
            ds.PatientName = "Anonymous"
            ds.PatientID = "000000"
            ds.StudyDate = datetime.date.today().strftime("%Y%m%d")
            ds.StudyTime = datetime.datetime.now().strftime("%H%M%S.%f")[:-3]
            ds.StudyInstanceUID = generate_uid()
            ds.SeriesInstanceUID = generate_uid()
            ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
            ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
            ds.SecondaryCaptureDeviceManufctur = "Haven Health Passport"

            # Set image properties
            ds.SamplesPerPixel = 1 if len(image.shape) == 2 else image.shape[2]
            ds.PhotometricInterpretation = (
                "MONOCHROME2" if ds.SamplesPerPixel == 1 else "RGB"
            )
            ds.Rows, ds.Columns = image.shape[:2]
            ds.BitsAllocated = 8 if image.dtype == np.uint8 else 16
            ds.BitsStored = ds.BitsAllocated
            ds.HighBit = ds.BitsAllocated - 1
            ds.PixelRepresentation = 0  # unsigned

            # Add pixel data
            if image.dtype != np.uint8 and image.dtype != np.uint16:
                # Convert to appropriate type
                if ds.BitsAllocated == 8:
                    image = (
                        (image * 255).astype(np.uint8)
                        if image.max() <= 1
                        else image.astype(np.uint8)
                    )
                else:
                    image = (
                        (image * 65535).astype(np.uint16)
                        if image.max() <= 1
                        else image.astype(np.uint16)
                    )

            ds.PixelData = image.tobytes()

            # Save to bytes
            buffer = io.BytesIO()
            dcmwrite(buffer, ds, write_like_original=False)
            return buffer.getvalue()

        except ImportError:
            logger.warning(
                "pydicom not installed. Using basic raw format as fallback for DICOM."
            )
            # Fallback to raw format with basic header
            header = b"DICOM_PLACEHOLDER"
            shape_info = np.array(image.shape, dtype=np.int32).tobytes()
            dtype_info = np.array([image.dtype.itemsize], dtype=np.int32).tobytes()
            return header + shape_info + dtype_info + image.tobytes()

    def _to_nifti(self, image: np.ndarray) -> bytes:
        """Convert to NIfTI format.

        NIfTI is commonly used for neuroimaging data.
        This implementation provides basic conversion.
        Production use should integrate with nibabel for proper NIfTI support.
        """
        if not HAS_NIBABEL:
            logger.warning(
                "nibabel not installed. Using basic raw format as fallback for NIfTI."
            )
            # Fallback to raw format with basic header
            header = b"NIFTI_PLACEHOLDER"
            shape_info = np.array(image.shape, dtype=np.int32).tobytes()
            dtype_info = np.array([image.dtype.itemsize], dtype=np.int32).tobytes()
            # Add basic affine transformation matrix (identity)
            affine = np.eye(4, dtype=np.float32).tobytes()
            return header + shape_info + dtype_info + affine + image.tobytes()

        try:

            # Create NIfTI image
            # Assume image is in standard radiological orientation
            nifti_img = nibabel.Nifti1Image(image, affine=np.eye(4))

            # Set basic header information
            nifti_img.header["descrip"] = b"Haven Health Passport Medical Image"

            # Save to bytes
            buffer = io.BytesIO()
            file_map = nifti_img.make_file_map({"image": buffer, "header": buffer})
            nifti_img.to_file_map(file_map)
            return buffer.getvalue()

        except ImportError:
            logger.warning(
                "nibabel not installed. Using basic raw format as fallback for NIfTI."
            )
            # Fallback to raw format with basic header
            header = b"NIFTI_PLACEHOLDER"
            shape_info = np.array(image.shape, dtype=np.int32).tobytes()
            dtype_info = np.array([image.dtype.itemsize], dtype=np.int32).tobytes()
            # Add basic affine transformation matrix (identity)
            affine = np.eye(4, dtype=np.float32).tobytes()
            return header + shape_info + dtype_info + affine + image.tobytes()

    def _to_raw(self, image: np.ndarray) -> bytes:
        """Convert to raw format.

        Raw format contains just the pixel data with minimal header information.
        This is useful for interoperability with custom medical imaging systems.
        """
        # Create a simple header with shape and dtype information
        header = {
            "magic": "HAVEN_RAW_v1",
            "shape": image.shape,
            "dtype": str(image.dtype),
            "byte_order": "little",
        }

        # Serialize header as JSON for easy parsing
        header_json = json.dumps(header).encode("utf-8")
        header_size = np.array([len(header_json)], dtype=np.uint32).tobytes()

        # Combine header size, header, and raw pixel data
        return header_size + header_json + image.tobytes()

    def validate(self, image_data: bytes, image_format: ImageFormat) -> bool:
        """Validate medical image data for FHIR Resource compliance."""
        if not image_data:
            return False

        # Basic format validation
        if image_format == ImageFormat.DICOM:
            # Check for DICOM preamble
            return len(image_data) > 132 and image_data[128:132] == b"DICM"
        elif image_format in [
            ImageFormat.PNG,
            ImageFormat.JPEG,
            ImageFormat.TIFF,
            ImageFormat.BMP,
        ]:
            # Validate using PIL
            try:
                Image.open(io.BytesIO(image_data))
                return True
            except (ValueError, ImportError, AttributeError):
                return False

        return True
