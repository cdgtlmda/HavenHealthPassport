"""File validation service for verifying file types and content.

Security Note: This module processes PHI data. All validated files must be:
- Subject to role-based access control (RBAC) for PHI protection
"""

import hashlib
import mimetypes
import wave
import zipfile
from dataclasses import dataclass
from enum import Enum
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

try:
    import magic

    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False

try:
    import PyPDF2
    from PIL import Image

    HAS_ADVANCED_LIBS = True
except ImportError:
    HAS_ADVANCED_LIBS = False

from src.storage.base import FileCategory
from src.utils.logging import get_logger

logger = get_logger(__name__)


class FileType(str, Enum):
    """Supported file types for validation."""

    # Documents
    PDF = "pdf"
    DOC = "doc"
    DOCX = "docx"
    TXT = "txt"
    RTF = "rtf"

    # Images
    JPEG = "jpeg"
    PNG = "png"
    GIF = "gif"
    BMP = "bmp"
    TIFF = "tiff"
    WEBP = "webp"
    DICOM = "dicom"

    # Audio
    MP3 = "mp3"
    WAV = "wav"
    OGG = "ogg"
    M4A = "m4a"
    FLAC = "flac"

    # Other
    UNKNOWN = "unknown"


@dataclass
class ValidationResult:
    """Result of file validation."""

    is_valid: bool
    file_type: FileType
    mime_type: str
    actual_extension: str
    issues: List[str]
    metadata: Dict[str, Any]

    @property
    def has_issues(self) -> bool:
        """Check if validation found any issues."""
        return len(self.issues) > 0


class FileValidationService:
    """Service for validating file types and content."""

    # Magic numbers for file type detection
    FILE_SIGNATURES = {
        # PDF
        b"%PDF": FileType.PDF,
        # Images
        b"\xff\xd8\xff": FileType.JPEG,
        b"\x89PNG\r\n\x1a\n": FileType.PNG,
        b"GIF87a": FileType.GIF,
        b"GIF89a": FileType.GIF,
        b"BM": FileType.BMP,
        b"II*\x00": FileType.TIFF,  # Little-endian
        b"MM\x00*": FileType.TIFF,  # Big-endian
        b"DICM": FileType.DICOM,  # DICOM at offset 128
        # Audio
        b"ID3": FileType.MP3,  # MP3 with ID3 tag
        b"\xff\xfb": FileType.MP3,  # MP3 without ID3
        b"\xff\xf3": FileType.MP3,  # MP3 without ID3
        b"\xff\xf2": FileType.MP3,  # MP3 without ID3
        b"RIFF": FileType.WEBP,  # WebP and WAV both start with RIFF - handled specially
        b"OggS": FileType.OGG,
        b"fLaC": FileType.FLAC,
    }

    # MIME type mappings
    MIME_TYPE_MAP = {
        FileType.PDF: ["application/pdf"],
        FileType.DOC: ["application/msword"],
        FileType.DOCX: [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ],
        FileType.TXT: ["text/plain"],
        FileType.RTF: ["application/rtf", "text/rtf"],
        FileType.JPEG: ["image/jpeg", "image/jpg"],
        FileType.PNG: ["image/png"],
        FileType.GIF: ["image/gif"],
        FileType.BMP: ["image/bmp", "image/x-ms-bmp"],
        FileType.TIFF: ["image/tiff", "image/tif"],
        FileType.WEBP: ["image/webp"],
        FileType.DICOM: ["application/dicom"],
        FileType.MP3: ["audio/mpeg", "audio/mp3"],
        FileType.WAV: ["audio/wav", "audio/wave", "audio/x-wav"],
        FileType.OGG: ["audio/ogg", "application/ogg"],
        FileType.M4A: ["audio/mp4", "audio/x-m4a"],
        FileType.FLAC: ["audio/flac", "audio/x-flac"],
    }

    # Maximum file sizes by type (in bytes)
    MAX_FILE_SIZES = {
        FileType.PDF: 50 * 1024 * 1024,  # 50MB
        FileType.DOC: 25 * 1024 * 1024,  # 25MB
        FileType.DOCX: 25 * 1024 * 1024,  # 25MB
        FileType.TXT: 5 * 1024 * 1024,  # 5MB
        FileType.RTF: 10 * 1024 * 1024,  # 10MB
        FileType.JPEG: 20 * 1024 * 1024,  # 20MB
        FileType.PNG: 20 * 1024 * 1024,  # 20MB
        FileType.GIF: 10 * 1024 * 1024,  # 10MB
        FileType.BMP: 20 * 1024 * 1024,  # 20MB
        FileType.TIFF: 50 * 1024 * 1024,  # 50MB
        FileType.WEBP: 20 * 1024 * 1024,  # 20MB
        FileType.DICOM: 100 * 1024 * 1024,  # 100MB
        FileType.MP3: 50 * 1024 * 1024,  # 50MB
        FileType.WAV: 100 * 1024 * 1024,  # 100MB
        FileType.OGG: 50 * 1024 * 1024,  # 50MB
        FileType.M4A: 50 * 1024 * 1024,  # 50MB
        FileType.FLAC: 100 * 1024 * 1024,  # 100MB
    }

    def __init__(self) -> None:
        """Initialize file validation service."""
        self._magic = None
        if HAS_MAGIC:
            try:
                self._magic = magic.Magic(mime=True)
            except (AttributeError, OSError) as e:
                logger.warning(f"python-magic not available: {e}")

    def validate_file(
        self,
        file_data: BinaryIO,
        filename: str,
        expected_type: Optional[FileType] = None,
    ) -> ValidationResult:
        """
        Validate a file's type and content.

        Args:
            file_data: Binary file data
            filename: Original filename
            expected_type: Expected file type

        Returns:
            Validation result
        """
        issues: List[str] = []
        metadata: Dict[str, Any] = {}

        # Get file size
        file_data.seek(0, 2)
        file_size = file_data.tell()
        file_data.seek(0)
        metadata["file_size"] = file_size

        # Detect file type
        detected_type = self._detect_file_type(file_data)

        # Get MIME type
        mime_type = self._get_mime_type(file_data, filename)

        # Determine actual extension
        actual_extension = self._get_extension_for_type(detected_type)

        # Validate file type matches expectation
        if expected_type and detected_type != expected_type:
            issues.append(
                f"File type mismatch. Expected {expected_type}, got {detected_type}"
            )

        # Validate MIME type
        if not self._validate_mime_type(detected_type, mime_type):
            issues.append(
                f"MIME type '{mime_type}' doesn't match detected type {detected_type}"
            )

        # Validate file size
        max_size = self.MAX_FILE_SIZES.get(detected_type, 50 * 1024 * 1024)
        if file_size > max_size:
            issues.append(
                f"File size {file_size} exceeds maximum {max_size} for {detected_type}"
            )

        # Perform type-specific validation
        if detected_type == FileType.PDF:
            pdf_issues, pdf_metadata = self._validate_pdf(file_data)
            issues.extend(pdf_issues)
            metadata.update(pdf_metadata)

        elif detected_type in [
            FileType.JPEG,
            FileType.PNG,
            FileType.GIF,
            FileType.BMP,
            FileType.TIFF,
            FileType.WEBP,
        ]:
            image_issues, image_metadata = self._validate_image(
                file_data, detected_type
            )
            issues.extend(image_issues)
            metadata.update(image_metadata)

        elif detected_type in [
            FileType.MP3,
            FileType.WAV,
            FileType.OGG,
            FileType.M4A,
            FileType.FLAC,
        ]:
            audio_issues, audio_metadata = self._validate_audio(
                file_data, detected_type
            )
            issues.extend(audio_issues)
            metadata.update(audio_metadata)

        # Check for suspicious content
        suspicious_issues = self._check_suspicious_content(file_data, detected_type)
        issues.extend(suspicious_issues)

        return ValidationResult(
            is_valid=len(issues) == 0,
            file_type=detected_type,
            mime_type=mime_type,
            actual_extension=actual_extension,
            issues=issues,
            metadata=metadata,
        )

    def _detect_file_type(self, file_data: BinaryIO) -> FileType:
        """Detect file type from magic numbers."""
        file_data.seek(0)

        # Read first 512 bytes for detection
        header = file_data.read(512)
        file_data.seek(0)

        # Check DICOM special case (signature at offset 128)
        if len(header) > 132 and header[128:132] == b"DICM":
            return FileType.DICOM

        # Check signatures
        for signature, file_type in self.FILE_SIGNATURES.items():
            if header.startswith(signature):
                # Special handling for RIFF-based formats
                if signature == b"RIFF" and len(header) > 12:
                    if header[8:12] == b"WEBP":
                        return FileType.WEBP
                    elif header[8:12] == b"WAVE":
                        return FileType.WAV

                return file_type

        # Check for Office documents
        if header.startswith(b"PK\x03\x04"):  # ZIP archive
            # Could be DOCX or other Office format
            if self._is_docx(file_data):
                return FileType.DOCX

        # Check for text files
        if self._is_text_file(header):
            return FileType.TXT

        return FileType.UNKNOWN

    def _get_mime_type(self, file_data: BinaryIO, filename: str) -> str:
        """Get MIME type of file."""
        file_data.seek(0)

        # Try python-magic if available
        if self._magic:
            try:
                mime_type = self._magic.from_buffer(file_data.read(2048))
                file_data.seek(0)
                return str(mime_type)
            except (AttributeError, OSError) as e:
                logger.warning(f"Error getting MIME type with magic: {e}")

        # Fallback to extension-based detection
        mime_type, _ = mimetypes.guess_type(filename)
        return str(mime_type or "application/octet-stream")

    def _validate_mime_type(self, file_type: FileType, mime_type: str) -> bool:
        """Validate MIME type matches file type."""
        expected_mimes = self.MIME_TYPE_MAP.get(file_type, [])
        return mime_type in expected_mimes or not expected_mimes

    def _get_extension_for_type(self, file_type: FileType) -> str:
        """Get file extension for file type."""
        extension_map = {
            FileType.PDF: ".pdf",
            FileType.DOC: ".doc",
            FileType.DOCX: ".docx",
            FileType.TXT: ".txt",
            FileType.RTF: ".rtf",
            FileType.JPEG: ".jpg",
            FileType.PNG: ".png",
            FileType.GIF: ".gif",
            FileType.BMP: ".bmp",
            FileType.TIFF: ".tif",
            FileType.WEBP: ".webp",
            FileType.DICOM: ".dcm",
            FileType.MP3: ".mp3",
            FileType.WAV: ".wav",
            FileType.OGG: ".ogg",
            FileType.M4A: ".m4a",
            FileType.FLAC: ".flac",
        }
        return extension_map.get(file_type, "")

    def _validate_pdf(self, file_data: BinaryIO) -> Tuple[List[str], Dict[str, Any]]:
        """Validate PDF file."""
        issues: List[str] = []
        metadata: Dict[str, Any] = {}

        if not HAS_ADVANCED_LIBS:
            return issues, metadata

        try:
            file_data.seek(0)
            pdf_reader = PyPDF2.PdfReader(file_data)

            # Get page count
            page_count = len(pdf_reader.pages)
            metadata["page_count"] = page_count

            # Check if encrypted
            if pdf_reader.is_encrypted:
                issues.append("PDF is encrypted")
                metadata["encrypted"] = True

            # Check for forms
            if pdf_reader.get_form_text_fields():
                metadata["has_forms"] = True

            # Extract metadata
            if pdf_reader.metadata:
                pdf_metadata = {}
                for key, value in pdf_reader.metadata.items():
                    if key.startswith("/"):
                        key = key[1:]
                    pdf_metadata[key] = str(value) if value else None
                metadata["pdf_metadata"] = pdf_metadata

            # Check for suspicious elements
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    # Check for JavaScript
                    if "/JS" in page or "/JavaScript" in page:
                        issues.append(f"JavaScript found on page {page_num + 1}")

                    # Check for embedded files
                    if "/EmbeddedFiles" in page:
                        issues.append(f"Embedded files found on page {page_num + 1}")

                except (KeyError, AttributeError) as e:
                    logger.warning(f"Error checking PDF page {page_num}: {e}")

        except (PyPDF2.errors.PdfReadError, OSError, ValueError) as e:
            issues.append(f"PDF validation error: {str(e)}")

        finally:
            file_data.seek(0)

        return issues, metadata

    def _validate_image(
        self, file_data: BinaryIO, file_type: FileType
    ) -> Tuple[List[str], Dict[str, Any]]:
        """Validate image file."""
        _ = file_type  # Acknowledge unused parameter
        issues: List[str] = []
        metadata: Dict[str, Any] = {}

        if not HAS_ADVANCED_LIBS:
            return issues, metadata

        try:
            file_data.seek(0)
            img = Image.open(file_data)

            # Get image properties
            metadata["width"] = img.width
            metadata["height"] = img.height
            metadata["format"] = img.format
            metadata["mode"] = img.mode

            # Check image dimensions
            max_dimension = 10000  # 10k pixels
            if img.width > max_dimension or img.height > max_dimension:
                issues.append(
                    f"Image dimensions ({img.width}x{img.height}) exceed maximum "
                    f"{max_dimension}x{max_dimension}"
                )

            # Check for EXIF data
            exif = getattr(img, "_getexif", None)
            if exif and callable(exif):
                exif_data = exif()
                if exif_data:
                    metadata["has_exif"] = True
                    # Could extract GPS coordinates, camera info, etc.

            # Verify image integrity
            try:
                img.verify()
            except (OSError, ValueError) as e:
                issues.append(f"Image integrity check failed: {str(e)}")

        except (OSError, ValueError, AttributeError) as e:
            issues.append(f"Image validation error: {str(e)}")

        finally:
            file_data.seek(0)

        return issues, metadata

    def _validate_audio(
        self, file_data: BinaryIO, file_type: FileType
    ) -> Tuple[List[str], Dict[str, Any]]:
        """Validate audio file."""
        issues: List[str] = []
        metadata: Dict[str, Any] = {}

        try:
            file_data.seek(0)

            if file_type == FileType.WAV:
                # Validate WAV file
                try:
                    with wave.open(file_data, "rb") as wav:
                        metadata["channels"] = wav.getnchannels()
                        metadata["sample_width"] = wav.getsampwidth()
                        metadata["framerate"] = wav.getframerate()
                        metadata["frames"] = wav.getnframes()
                        metadata["duration_seconds"] = (
                            wav.getnframes() / wav.getframerate()
                        )

                        # Check audio parameters
                        if wav.getframerate() > 48000:
                            issues.append(
                                f"Sample rate {wav.getframerate()} exceeds 48kHz"
                            )

                        if wav.getnchannels() > 2:
                            issues.append(
                                f"More than 2 channels ({wav.getnchannels()})"
                            )

                except (wave.Error, OSError, EOFError) as e:
                    issues.append(f"WAV validation error: {str(e)}")

            elif file_type == FileType.MP3:
                # Basic MP3 validation
                file_data.seek(0)
                header = file_data.read(10)

                # Check for ID3 tag
                if header.startswith(b"ID3"):
                    metadata["has_id3"] = True
                    # Could parse ID3 tags for metadata

            # Add general audio metadata
            metadata["audio_format"] = file_type.value

        except (OSError, ValueError) as e:
            issues.append(f"Audio validation error: {str(e)}")

        finally:
            file_data.seek(0)

        return issues, metadata

    def _check_suspicious_content(
        self, file_data: BinaryIO, file_type: FileType
    ) -> List[str]:
        """Check for suspicious content in file."""
        issues = []
        file_data.seek(0)

        # Read file in chunks to check for suspicious patterns
        suspicious_patterns = [
            # Executable signatures
            (b"MZ", "Windows executable signature found"),
            (b"\x7fELF", "Linux executable signature found"),
            (b"\xfe\xed\xfa", "Mach-O executable signature found"),
            # Script patterns
            (b"<script", "Script tag found"),
            (b"eval(", "Eval function found"),
            (b"exec(", "Exec function found"),
            # Shell patterns
            (b"#!/bin/sh", "Shell script found"),
            (b"#!/bin/bash", "Bash script found"),
            (b"cmd.exe", "Command prompt reference found"),
            (b"powershell", "PowerShell reference found"),
        ]

        # Don't check text files for some patterns
        skip_for_text = [b"<script", b"eval(", b"exec("]

        content = file_data.read(1024 * 1024)  # Read first 1MB
        file_data.seek(0)

        for pattern, message in suspicious_patterns:
            if file_type == FileType.TXT and pattern in skip_for_text:
                continue

            if pattern in content:
                issues.append(message)

        return issues

    def _is_docx(self, file_data: BinaryIO) -> bool:
        """Check if file is a DOCX file."""
        try:
            file_data.seek(0)

            with zipfile.ZipFile(file_data, "r") as z:
                # Check for required DOCX structure
                required_files = ["[Content_Types].xml", "word/document.xml"]
                zip_files = z.namelist()

                return all(
                    any(f.endswith(req) for f in zip_files) for req in required_files
                )
        except (zipfile.BadZipFile, OSError):
            return False
        finally:
            file_data.seek(0)

    def _is_text_file(self, header: bytes) -> bool:
        """Check if file appears to be plain text."""
        try:
            # Try to decode as UTF-8
            header.decode("utf-8")

            # Check for binary characters
            text_chars = set(range(32, 127)) | {
                9,
                10,
                13,
            }  # Printable + tab, newline, return
            return all(b in text_chars or b >= 128 for b in header)

        except UnicodeDecodeError:
            return False

    def validate_for_category(
        self, file_data: BinaryIO, filename: str, category: FileCategory
    ) -> ValidationResult:
        """
        Validate file for specific category requirements.

        Args:
            file_data: Binary file data
            filename: Original filename
            category: Target file category

        Returns:
            Validation result
        """
        # Define allowed types by category
        category_allowed_types = {
            FileCategory.MEDICAL_RECORD: [
                FileType.PDF,
                FileType.DOC,
                FileType.DOCX,
                FileType.TXT,
            ],
            FileCategory.LAB_RESULT: [FileType.PDF, FileType.JPEG, FileType.PNG],
            FileCategory.IMAGING: [
                FileType.JPEG,
                FileType.PNG,
                FileType.DICOM,
                FileType.TIFF,
            ],
            FileCategory.PRESCRIPTION: [FileType.PDF, FileType.JPEG, FileType.PNG],
            FileCategory.VACCINATION: [FileType.PDF, FileType.JPEG, FileType.PNG],
            FileCategory.INSURANCE: [FileType.PDF, FileType.JPEG, FileType.PNG],
            FileCategory.IDENTIFICATION: [FileType.JPEG, FileType.PNG, FileType.PDF],
            FileCategory.CONSENT_FORM: [FileType.PDF],
            FileCategory.CLINICAL_NOTE: [
                FileType.TXT,
                FileType.PDF,
                FileType.DOC,
                FileType.DOCX,
            ],
            FileCategory.VOICE_RECORDING: [
                FileType.MP3,
                FileType.WAV,
                FileType.OGG,
                FileType.M4A,
            ],
        }

        # Validate file
        result = self.validate_file(file_data, filename)

        # Check if file type is allowed for category
        allowed_types = category_allowed_types.get(category, [])
        if allowed_types and result.file_type not in allowed_types:
            result.issues.append(
                f"File type {result.file_type} not allowed for category {category}. "
                f"Allowed types: {', '.join(t.value for t in allowed_types)}"
            )
            result.is_valid = False

        return result

    def calculate_file_hash(
        self, file_data: BinaryIO, algorithm: str = "sha256"
    ) -> str:
        """
        Calculate hash of file data.

        Args:
            file_data: Binary file data
            algorithm: Hash algorithm to use

        Returns:
            Hex-encoded hash
        """
        file_data.seek(0)

        if algorithm == "sha256":
            hasher = hashlib.sha256()
        elif algorithm == "sha1":
            hasher = hashlib.sha1(usedforsecurity=False)
        elif algorithm == "md5":
            hasher = hashlib.md5(usedforsecurity=False)
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")

        # Read in chunks for memory efficiency
        for chunk in iter(lambda: file_data.read(8192), b""):
            hasher.update(chunk)

        file_data.seek(0)
        return hasher.hexdigest()
