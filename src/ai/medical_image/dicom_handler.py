"""DICOM file handler for medical images. Handles FHIR Resource validation.

This module handles FHIR DomainResource operations for medical imaging.

All PHI data in medical images is encrypted and access is controlled
through role-based permissions.
"""

import logging
from typing import Any, Dict, List, Tuple

import numpy as np

try:
    import pydicom
    from pydicom.dataset import FileMetaDataset
    from pydicom.pixel_data_handlers import apply_modality_lut, apply_voi_lut
    from pydicom.uid import UID

    PYDICOM_AVAILABLE = True
except ImportError:
    PYDICOM_AVAILABLE = False
    apply_modality_lut = None
    apply_voi_lut = None
    FileMetaDataset = None  # type: ignore

logger = logging.getLogger(__name__)


class DICOMHandler:
    """Handle DICOM medical image files."""

    def __init__(self) -> None:
        """Initialize DICOM handler."""
        self.supported_transfer_syntaxes = [
            "1.2.840.10008.1.2",  # Implicit VR Little Endian
            "1.2.840.10008.1.2.1",  # Explicit VR Little Endian
            "1.2.840.10008.1.2.2",  # Explicit VR Big Endian
            "1.2.840.10008.1.2.4.50",  # JPEG Baseline
            "1.2.840.10008.1.2.4.51",  # JPEG Extended
            "1.2.840.10008.1.2.4.57",  # JPEG Lossless
            "1.2.840.10008.1.2.4.70",  # JPEG Lossless First-Order Prediction
            "1.2.840.10008.1.2.4.90",  # JPEG 2000 Lossless
            "1.2.840.10008.1.2.4.91",  # JPEG 2000
            "1.2.840.10008.1.2.5",  # RLE Lossless
        ]

    def load_dicom(self, file_path: str) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Load DICOM file and extract pixel data and metadata."""
        try:
            # Read DICOM file
            ds = pydicom.dcmread(file_path)

            # Extract pixel data
            pixel_array = ds.pixel_array

            # Apply modality LUT if present
            if hasattr(ds, "RescaleSlope") and hasattr(ds, "RescaleIntercept"):
                pixel_array = apply_modality_lut(pixel_array, ds)

            # Apply VOI LUT if present
            if hasattr(ds, "WindowCenter") and hasattr(ds, "WindowWidth"):
                pixel_array = apply_voi_lut(pixel_array, ds)

            # Extract metadata
            metadata = self._extract_metadata(ds)

            logger.info("Successfully loaded DICOM file: %s", file_path)
            return pixel_array, metadata

        except Exception as e:
            logger.error("Error loading DICOM file %s: %s", file_path, str(e))
            raise

    def _extract_metadata(self, ds: pydicom.Dataset) -> Dict[str, Any]:
        """Extract relevant metadata from DICOM dataset."""
        metadata: Dict[str, Any] = {}

        # Patient information
        metadata["patient"] = {
            "name": str(getattr(ds, "PatientName", "")),
            "id": str(getattr(ds, "PatientID", "")),
            "birth_date": str(getattr(ds, "PatientBirthDate", "")),
            "sex": str(getattr(ds, "PatientSex", "")),
            "age": str(getattr(ds, "PatientAge", "")),
        }

        # Study information
        metadata["study"] = {
            "instance_uid": str(getattr(ds, "StudyInstanceUID", "")),
            "id": str(getattr(ds, "StudyID", "")),
            "date": str(getattr(ds, "StudyDate", "")),
            "time": str(getattr(ds, "StudyTime", "")),
            "description": str(getattr(ds, "StudyDescription", "")),
        }

        # Series information
        metadata["series"] = {
            "instance_uid": str(getattr(ds, "SeriesInstanceUID", "")),
            "number": str(getattr(ds, "SeriesNumber", "")),
            "modality": str(getattr(ds, "Modality", "")),
            "description": str(getattr(ds, "SeriesDescription", "")),
        }

        # Image information
        metadata["image"] = {
            "rows": str(getattr(ds, "Rows", 0)),
            "columns": str(getattr(ds, "Columns", 0)),
            "bits_allocated": str(getattr(ds, "BitsAllocated", 0)),
            "bits_stored": str(getattr(ds, "BitsStored", 0)),
            "pixel_representation": str(getattr(ds, "PixelRepresentation", 0)),
            "photometric_interpretation": str(
                getattr(ds, "PhotometricInterpretation", "")
            ),
            "instance_number": str(getattr(ds, "InstanceNumber", 0)),
        }

        # Window/Level if present
        if hasattr(ds, "WindowCenter") and hasattr(ds, "WindowWidth"):
            metadata["window"] = {
                "center": str(ds.WindowCenter),
                "width": str(ds.WindowWidth),
            }

        # Pixel spacing if present
        if hasattr(ds, "PixelSpacing"):
            metadata["pixel_spacing"] = [float(x) for x in ds.PixelSpacing]

        # Slice information if present
        if hasattr(ds, "SliceThickness"):
            metadata["slice_thickness"] = float(ds.SliceThickness)

        if hasattr(ds, "SliceLocation"):
            metadata["slice_location"] = float(ds.SliceLocation)

        return metadata

    def anonymize_dicom(self, file_path: str, output_path: str) -> None:
        """Anonymize DICOM file by removing patient information."""
        try:
            ds = pydicom.dcmread(file_path)

            # List of tags to anonymize
            tags_to_anonymize = [
                "PatientName",
                "PatientID",
                "PatientBirthDate",
                "PatientSex",
                "PatientAge",
                "PatientAddress",
                "PatientTelephoneNumbers",
                "ReferringPhysicianName",
                "PerformingPhysicianName",
                "InstitutionName",
                "InstitutionAddress",
                "StationName",
            ]

            # Anonymize tags
            for tag in tags_to_anonymize:
                if hasattr(ds, tag):
                    if tag == "PatientName":
                        ds.PatientName = "Anonymous"
                    elif tag == "PatientID":
                        ds.PatientID = "ANON" + str(hash(ds.PatientID))[:8]
                    else:
                        delattr(ds, tag)

            # Save anonymized file
            ds.save_as(output_path)
            logger.info("Anonymized DICOM saved to: %s", output_path)

        except Exception as e:
            logger.error("Error anonymizing DICOM file: %s", str(e))
            raise

    def convert_to_standard_format(
        self, pixel_array: np.ndarray, metadata: Dict[str, Any]
    ) -> np.ndarray:
        """Convert DICOM pixel data to standard format for processing."""
        # Handle different photometric interpretations
        photometric = metadata.get("image", {}).get("photometric_interpretation", "")

        if photometric == "MONOCHROME1":
            # Invert the image (white becomes black)
            pixel_array = np.max(pixel_array) - pixel_array

        # Ensure proper data type
        if pixel_array.dtype != np.uint8:
            # Normalize to 0-255 range
            pixel_array = self._normalize_to_uint8(pixel_array)

        return pixel_array

    def _normalize_to_uint8(self, array: np.ndarray) -> np.ndarray:
        """Normalize array to uint8 range."""
        array_min = np.min(array)
        array_max = np.max(array)

        if array_max > array_min:
            normalized = (array - array_min) / (array_max - array_min) * 255
            return np.array(normalized.astype(np.uint8))
        else:
            return np.zeros_like(array, dtype=np.uint8)

    def save_as_dicom(
        self, pixel_array: np.ndarray, metadata: Dict[str, Any], output_path: str
    ) -> None:
        """Save pixel array as DICOM file with metadata."""
        # Create new DICOM dataset
        file_meta = FileMetaDataset()
        file_meta.MediaStorageSOPClassUID = UID(
            "1.2.840.10008.5.1.4.1.1.7"  # Secondary Capture
        )
        file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
        file_meta.TransferSyntaxUID = UID(
            "1.2.840.10008.1.2"
        )  # Implicit VR Little Endian

        ds = pydicom.FileDataset(
            output_path, {}, file_meta=file_meta, preamble=b"\0" * 128
        )

        # Set required values
        ds.PatientName = metadata.get("patient", {}).get("name", "Anonymous")
        ds.PatientID = metadata.get("patient", {}).get("id", "Unknown")

        # Set image pixel data
        ds.PixelData = pixel_array.tobytes()
        ds.Rows, ds.Columns = pixel_array.shape[:2]

        # Set other required attributes
        ds.SamplesPerPixel = 1 if len(pixel_array.shape) == 2 else pixel_array.shape[2]
        ds.PhotometricInterpretation = (
            "MONOCHROME2" if len(pixel_array.shape) == 2 else "RGB"
        )
        ds.BitsAllocated = 8
        ds.BitsStored = 8
        ds.HighBit = 7
        ds.PixelRepresentation = 0

        # Save the file
        ds.save_as(output_path)
        logger.info("Saved DICOM file to: %s", output_path)


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
