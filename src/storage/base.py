"""Base storage abstraction layer.

Note: This module handles PHI-related file storage abstractions.
- Access Control: Implement role-based access control (RBAC) for storage backend operations
"""

import hashlib
import mimetypes
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

from src.utils.logging import get_logger

logger = get_logger(__name__)


class StorageType(str, Enum):
    """Types of storage backends."""

    S3 = "s3"
    LOCAL = "local"
    AZURE_BLOB = "azure_blob"
    GCS = "gcs"  # Google Cloud Storage


class FileCategory(str, Enum):
    """Categories for file classification."""

    MEDICAL_RECORD = "medical_record"
    LAB_RESULT = "lab_result"
    IMAGING = "imaging"
    PRESCRIPTION = "prescription"
    VACCINATION = "vaccination"
    INSURANCE = "insurance"
    IDENTIFICATION = "identification"
    CONSENT_FORM = "consent_form"
    CLINICAL_NOTE = "clinical_note"
    VOICE_RECORDING = "voice_recording"
    OTHER = "other"


class FileMetadata:
    """Metadata for stored files."""

    def __init__(
        self,
        file_id: str,
        filename: str,
        content_type: str,
        size: int,
        checksum: str,
        category: FileCategory,
        created_at: datetime,
        modified_at: datetime,
        version: int = 1,
        tags: Optional[Dict[str, str]] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize file metadata."""
        self.file_id = file_id
        self.filename = filename
        self.content_type = content_type
        self.size = size
        self.checksum = checksum
        self.category = category
        self.created_at = created_at
        self.modified_at = modified_at
        self.version = version
        self.tags = tags or {}
        self.custom_metadata = custom_metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "content_type": self.content_type,
            "size": self.size,
            "checksum": self.checksum,
            "category": self.category.value,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "version": self.version,
            "tags": self.tags,
            "custom_metadata": self.custom_metadata,
        }


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize storage backend.

        Args:
            config: Backend-specific configuration
        """
        self.config = config
        self._validate_config()

    @abstractmethod
    def _validate_config(self) -> None:
        """Validate backend configuration."""

    @abstractmethod
    def put(
        self,
        file_id: str,
        file_data: BinaryIO,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
        encryption_key: Optional[str] = None,
    ) -> FileMetadata:
        """
        Store a file in the backend.

        Args:
            file_id: Unique identifier for the file
            file_data: Binary file data
            content_type: MIME type of the file
            metadata: Additional metadata to store
            tags: Key-value tags for the file
            encryption_key: Encryption key for client-side encryption

        Returns:
            FileMetadata object
        """

    @abstractmethod
    def get(
        self,
        file_id: str,
        version: Optional[int] = None,
        decryption_key: Optional[str] = None,
    ) -> Tuple[BinaryIO, FileMetadata]:
        """
        Retrieve a file from the backend.

        Args:
            file_id: Unique identifier for the file
            version: Specific version to retrieve (latest if None)
            decryption_key: Decryption key for client-side encryption

        Returns:
            Tuple of (file data, metadata)
        """

    @abstractmethod
    def exists(self, file_id: str) -> bool:
        """
        Check if a file exists.

        Args:
            file_id: Unique identifier for the file

        Returns:
            True if file exists
        """

    @abstractmethod
    def delete(
        self, file_id: str, version: Optional[int] = None, permanent: bool = False
    ) -> bool:
        """
        Delete a file from the backend.

        Args:
            file_id: Unique identifier for the file
            version: Specific version to delete (all if None)
            permanent: If True, permanently delete; if False, soft delete

        Returns:
            True if successfully deleted
        """

    @abstractmethod
    def list(
        self,
        prefix: Optional[str] = None,
        category: Optional[FileCategory] = None,
        tags: Optional[Dict[str, str]] = None,
        limit: int = 1000,
        continuation_token: Optional[str] = None,
    ) -> Tuple[List[FileMetadata], Optional[str]]:
        """
        List files in the backend.

        Args:
            prefix: Filter by file ID prefix
            category: Filter by file category
            tags: Filter by tags
            limit: Maximum number of results
            continuation_token: Token for pagination

        Returns:
            Tuple of (list of metadata, next continuation token)
        """

    @abstractmethod
    def get_metadata(self, file_id: str) -> FileMetadata:
        """
        Get metadata for a file without downloading it.

        Args:
            file_id: Unique identifier for the file

        Returns:
            FileMetadata object
        """

    @abstractmethod
    def update_metadata(
        self,
        file_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> FileMetadata:
        """
        Update metadata for a file.

        Args:
            file_id: Unique identifier for the file
            metadata: Metadata to update
            tags: Tags to update

        Returns:
            Updated FileMetadata object
        """

    @abstractmethod
    def generate_presigned_url(
        self,
        file_id: str,
        operation: str = "get",
        expiration: Optional[timedelta] = None,
        content_type: Optional[str] = None,
        content_disposition: Optional[str] = None,
    ) -> str:
        """
        Generate a pre-signed URL for direct access.

        Args:
            file_id: Unique identifier for the file
            operation: Operation type ("get" or "put")
            expiration: URL expiration time
            content_type: Content type for uploads
            content_disposition: Content disposition header

        Returns:
            Pre-signed URL
        """

    @abstractmethod
    def copy(
        self,
        source_file_id: str,
        destination_file_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FileMetadata:
        """
        Copy a file within the backend.

        Args:
            source_file_id: Source file ID
            destination_file_id: Destination file ID
            metadata: Metadata for the copy

        Returns:
            FileMetadata for the copied file
        """

    @abstractmethod
    def create_multipart_upload(
        self,
        file_id: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Initiate a multipart upload.

        Args:
            file_id: Unique identifier for the file
            content_type: MIME type of the file
            metadata: Additional metadata

        Returns:
            Upload ID
        """

    @abstractmethod
    def upload_part(
        self, file_id: str, upload_id: str, part_number: int, data: BinaryIO
    ) -> str:
        """
        Upload a part in a multipart upload.

        Args:
            file_id: Unique identifier for the file
            upload_id: Multipart upload ID
            part_number: Part number (1-based)
            data: Part data

        Returns:
            Part ETag
        """

    @abstractmethod
    def complete_multipart_upload(
        self, file_id: str, upload_id: str, parts: List[Dict[str, Any]]
    ) -> FileMetadata:
        """
        Complete a multipart upload.

        Args:
            file_id: Unique identifier for the file
            upload_id: Multipart upload ID
            parts: List of completed parts with ETags

        Returns:
            FileMetadata for the uploaded file
        """

    @abstractmethod
    def abort_multipart_upload(self, file_id: str, upload_id: str) -> bool:
        """
        Abort a multipart upload.

        Args:
            file_id: Unique identifier for the file
            upload_id: Multipart upload ID

        Returns:
            True if successfully aborted
        """

    def calculate_checksum(self, data: BinaryIO) -> str:
        """
        Calculate SHA-256 checksum of data.

        Args:
            data: Binary data

        Returns:
            Hex-encoded checksum
        """
        sha256_hash = hashlib.sha256()

        # Reset to beginning
        data.seek(0)

        # Read in chunks for memory efficiency
        for chunk in iter(lambda: data.read(8192), b""):
            sha256_hash.update(chunk)

        # Reset to beginning for further use
        data.seek(0)

        return sha256_hash.hexdigest()

    def guess_content_type(self, filename: str) -> str:
        """
        Guess content type from filename.

        Args:
            filename: File name

        Returns:
            MIME type
        """
        content_type, _ = mimetypes.guess_type(filename)
        return content_type or "application/octet-stream"

    def categorize_file(self, filename: str, content_type: str) -> FileCategory:
        """
        Categorize file based on name and content type.

        Args:
            filename: File name
            content_type: MIME type

        Returns:
            File category
        """
        filename_lower = filename.lower()

        # Check by file extension patterns
        if any(ext in filename_lower for ext in [".pdf", ".doc", ".docx"]):
            if any(term in filename_lower for term in ["lab", "result", "test"]):
                return FileCategory.LAB_RESULT
            elif any(
                term in filename_lower for term in ["prescription", "rx", "medication"]
            ):
                return FileCategory.PRESCRIPTION
            elif any(
                term in filename_lower
                for term in ["vaccine", "vaccination", "immunization"]
            ):
                return FileCategory.VACCINATION
            elif any(term in filename_lower for term in ["insurance", "coverage"]):
                return FileCategory.INSURANCE
            elif any(term in filename_lower for term in ["consent", "authorization"]):
                return FileCategory.CONSENT_FORM
            else:
                return FileCategory.MEDICAL_RECORD

        # Check imaging files
        elif any(
            ext in filename_lower for ext in [".jpg", ".jpeg", ".png", ".dicom", ".dcm"]
        ):
            if any(
                term in filename_lower
                for term in ["xray", "x-ray", "scan", "mri", "ct", "ultrasound"]
            ):
                return FileCategory.IMAGING
            elif any(term in filename_lower for term in ["id", "passport", "license"]):
                return FileCategory.IDENTIFICATION
            else:
                return FileCategory.IMAGING

        # Check audio files
        elif any(ext in filename_lower for ext in [".mp3", ".wav", ".m4a", ".ogg"]):
            return FileCategory.VOICE_RECORDING

        # Check by content type
        elif content_type.startswith("image/"):
            return FileCategory.IMAGING
        elif content_type.startswith("audio/"):
            return FileCategory.VOICE_RECORDING

        # Default
        return FileCategory.OTHER


class StorageException(Exception):
    """Base exception for storage operations."""


class StorageFileNotFoundError(StorageException):
    """File not found in storage."""


class StorageQuotaExceededError(StorageException):
    """Storage quota exceeded."""


class InvalidFileTypeError(StorageException):
    """Invalid file type for operation."""
