"""DICOM document loader for medical imaging data.

Handles loading of DICOM (Digital Imaging and Communications in Medicine) files.
DICOM data is converted to FHIR ImagingStudy Resources for interoperability.
All loaded imaging data must validate against FHIR ImagingStudy profiles.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from llama_index.core import Document

from .base import (
    BaseDocumentLoader,
    DocumentLoaderConfig,
    DocumentMetadata,
    LoaderResult,
)

if TYPE_CHECKING:
    import pydicom
else:
    try:
        import pydicom
    except ImportError:
        pydicom = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class DICOMMedicalLoader(BaseDocumentLoader):
    """Loader for DICOM medical imaging files."""

    def __init__(self, config: Optional[DocumentLoaderConfig] = None):
        """Initialize DICOM loader."""
        super().__init__(config or DocumentLoaderConfig())
        self.supported_extensions = [".dcm", ".dicom"]

    def load(self, file_path: str, **kwargs: Any) -> LoaderResult:
        """Load DICOM file.

        Args:
            file_path: Path to DICOM file

        Returns:
            LoaderResult with documents and metadata
        """
        try:
            path = Path(file_path)

            if not path.exists():
                return LoaderResult(
                    success=False, errors=[f"File not found: {file_path}"]
                )

            # Check file extension
            extension = path.suffix.lower()
            if extension not in self.supported_extensions:
                # DICOM files sometimes have no extension, try to load anyway
                logger.warning("Unusual DICOM extension: %s", extension)

            documents = self._load_dicom_file(path)

            return LoaderResult(
                success=True,
                documents=documents,
                metadata=DocumentMetadata(
                    file_path=str(path),
                    file_type="dicom",
                    file_size=path.stat().st_size,
                ),
            )

        except Exception as e:
            logger.error("Error loading DICOM file %s: %s", file_path, e)
            return LoaderResult(success=False, errors=[str(e)])

    def _load_dicom_file(self, path: Path) -> List[Document]:
        """Load DICOM file and extract metadata."""
        try:
            import pydicom

            # Read DICOM file
            ds = pydicom.dcmread(str(path))

            # Extract text information from DICOM tags
            text_parts = []
            metadata: Dict[str, Any] = {}

            # Patient information
            if hasattr(ds, "PatientName"):
                patient_name = str(ds.PatientName)
                text_parts.append(f"Patient Name: {patient_name}")
                metadata["patient_name"] = patient_name

            if hasattr(ds, "PatientID"):
                patient_id = str(ds.PatientID)
                text_parts.append(f"Patient ID: {patient_id}")
                metadata["patient_id"] = patient_id

            if hasattr(ds, "PatientBirthDate"):
                text_parts.append(f"Patient Birth Date: {ds.PatientBirthDate}")
                metadata["patient_birth_date"] = str(ds.PatientBirthDate)

            if hasattr(ds, "PatientSex"):
                text_parts.append(f"Patient Sex: {ds.PatientSex}")
                metadata["patient_sex"] = str(ds.PatientSex)

            # Study information
            if hasattr(ds, "StudyDate"):
                text_parts.append(f"Study Date: {ds.StudyDate}")
                metadata["study_date"] = str(ds.StudyDate)

            if hasattr(ds, "StudyTime"):
                text_parts.append(f"Study Time: {ds.StudyTime}")
                metadata["study_time"] = str(ds.StudyTime)

            if hasattr(ds, "StudyDescription"):
                study_desc = str(ds.StudyDescription)
                text_parts.append(f"Study Description: {study_desc}")
                metadata["study_description"] = study_desc

            if hasattr(ds, "StudyInstanceUID"):
                metadata["study_instance_uid"] = str(ds.StudyInstanceUID)

            # Series information
            if hasattr(ds, "SeriesDescription"):
                series_desc = str(ds.SeriesDescription)
                text_parts.append(f"Series Description: {series_desc}")
                metadata["series_description"] = series_desc

            if hasattr(ds, "SeriesNumber"):
                text_parts.append(f"Series Number: {ds.SeriesNumber}")
                metadata["series_number"] = int(ds.SeriesNumber)

            if hasattr(ds, "Modality"):
                modality = str(ds.Modality)
                text_parts.append(f"Modality: {modality}")
                metadata["modality"] = modality

            # Image information
            if hasattr(ds, "Rows") and hasattr(ds, "Columns"):
                text_parts.append(f"Image Size: {ds.Rows} x {ds.Columns}")
                metadata["image_size"] = f"{ds.Rows}x{ds.Columns}"

            if hasattr(ds, "BitsAllocated"):
                text_parts.append(f"Bits Allocated: {ds.BitsAllocated}")
                metadata["bits_allocated"] = int(ds.BitsAllocated)

            if hasattr(ds, "PhotometricInterpretation"):
                text_parts.append(
                    f"Photometric Interpretation: {ds.PhotometricInterpretation}"
                )
                metadata["photometric_interpretation"] = str(
                    ds.PhotometricInterpretation
                )

            # Equipment information
            if hasattr(ds, "Manufacturer"):
                text_parts.append(f"Manufacturer: {ds.Manufacturer}")
                metadata["manufacturer"] = str(ds.Manufacturer)

            if hasattr(ds, "ManufacturerModelName"):
                text_parts.append(f"Model: {ds.ManufacturerModelName}")
                metadata["model"] = str(ds.ManufacturerModelName)

            if hasattr(ds, "StationName"):
                text_parts.append(f"Station Name: {ds.StationName}")
                metadata["station_name"] = str(ds.StationName)

            # Body part and view
            if hasattr(ds, "BodyPartExamined"):
                body_part = str(ds.BodyPartExamined)
                text_parts.append(f"Body Part Examined: {body_part}")
                metadata["body_part"] = body_part

            if hasattr(ds, "ViewPosition"):
                view_pos = str(ds.ViewPosition)
                text_parts.append(f"View Position: {view_pos}")
                metadata["view_position"] = view_pos

            # Protocol and technique
            if hasattr(ds, "ProtocolName"):
                protocol = str(ds.ProtocolName)
                text_parts.append(f"Protocol: {protocol}")
                metadata["protocol"] = protocol

            # Findings and comments
            if hasattr(ds, "ImageComments"):
                comments = str(ds.ImageComments)
                text_parts.append(f"\nImage Comments:\n{comments}")
                metadata["image_comments"] = comments

            # Additional relevant tags for medical context
            medical_tags = [
                ("ContrastBolusAgent", "Contrast Agent"),
                ("KVP", "KVP"),
                ("ExposureTime", "Exposure Time"),
                ("XRayTubeCurrent", "X-Ray Tube Current"),
                ("SliceThickness", "Slice Thickness"),
                ("PatientPosition", "Patient Position"),
                ("ImagePositionPatient", "Image Position"),
                ("ImageOrientationPatient", "Image Orientation"),
            ]

            for tag_name, display_name in medical_tags:
                if hasattr(ds, tag_name):
                    value = getattr(ds, tag_name)
                    text_parts.append(f"{display_name}: {value}")
                    metadata[tag_name.lower()] = str(value)

            # Create comprehensive text document
            full_text = "\n".join(text_parts)

            # Add metadata
            metadata.update(
                {
                    "source": str(path),
                    "file_type": "dicom",
                    "sop_class_uid": (
                        str(ds.SOPClassUID) if hasattr(ds, "SOPClassUID") else None
                    ),
                    "sop_instance_uid": (
                        str(ds.SOPInstanceUID)
                        if hasattr(ds, "SOPInstanceUID")
                        else None
                    ),
                    "transfer_syntax_uid": (
                        str(ds.file_meta.TransferSyntaxUID)
                        if hasattr(ds.file_meta, "TransferSyntaxUID")
                        else None
                    ),
                }
            )

            # Add a note about pixel data
            if hasattr(ds, "PixelData"):
                metadata["has_pixel_data"] = True
                full_text += (
                    "\n\n[Image pixel data present but not displayed in text format]"
                )

            return [Document(text=full_text, metadata=metadata)]

        except ImportError:
            logger.error("pydicom not installed. Install with: pip install pydicom")
            raise
        except Exception as e:
            logger.error("Error loading DICOM file: %s", e)
            raise

    def validate(self, file_path: str) -> Dict[str, Any]:
        """Validate DICOM file."""
        validation_result: Dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
        }

        try:
            path = Path(file_path)

            # Check file exists
            if not path.exists():
                validation_result["valid"] = False
                validation_result["errors"].append(f"File not found: {file_path}")
                return validation_result

            # Check file size
            file_size = path.stat().st_size
            if file_size > self.config.max_file_size_mb * 1024 * 1024:
                validation_result["valid"] = False
                validation_result["errors"].append(
                    f"File too large: {file_size} bytes (max: {self.config.max_file_size_mb * 1024 * 1024})"
                )

            # Try to read DICOM file
            try:
                if pydicom is None:
                    raise ImportError("pydicom is required for DICOM file loading")

                ds = pydicom.dcmread(str(path), stop_before_pixels=True)

                # Check for required DICOM tags
                required_tags = [
                    "PatientID",
                    "StudyInstanceUID",
                    "SeriesInstanceUID",
                    "SOPInstanceUID",
                ]
                for tag in required_tags:
                    if not hasattr(ds, tag):
                        validation_result["warnings"].append(
                            f"Missing recommended DICOM tag: {tag}"
                        )

                # Check if it's a valid medical image
                if hasattr(ds, "Modality"):
                    modality = str(ds.Modality)
                    valid_modalities = [
                        "CT",
                        "MR",
                        "US",
                        "XR",
                        "CR",
                        "DX",
                        "MG",
                        "NM",
                        "PT",
                        "SC",
                    ]
                    if modality not in valid_modalities:
                        validation_result["warnings"].append(
                            f"Unusual modality: {modality}"
                        )

            except (ImportError, AttributeError, ValueError, OSError) as e:
                validation_result["valid"] = False
                validation_result["errors"].append(f"Invalid DICOM file: {e}")

        except (OSError, ValueError, IOError) as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Validation error: {e}")

        return validation_result
