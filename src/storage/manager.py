"""Storage manager for handling multiple storage backends.

Note: This module handles PHI-related file storage management.
- Access Control: Implement role-based access control (RBAC) for all storage operations
"""

# pylint: disable=too-many-lines

import base64
import io
import os
import tempfile
from datetime import datetime, timedelta
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.file_attachment import FileAttachment, FileStatus
from src.services.file_versioning_service import (
    FileVersioningService,
    VersionChangeType,
)
from src.storage.base import (
    FileCategory,
    StorageBackend,
    StorageException,
    StorageFileNotFoundError,
    StorageType,
)
from src.storage.cdn_integration import CDNIntegration
from src.storage.document_categorization import DocumentCategorizationService
from src.storage.lifecycle_manager import StorageLifecycleManager
from src.storage.local_backend import LocalStorageBackend
from src.storage.s3_backend import S3StorageBackend
from src.utils.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class StorageManager:
    """Manager for handling file storage across different backends."""

    def __init__(self, session: Session):
        """
        Initialize storage manager.

        Args:
            session: Database session
        """
        self.session = session
        self.backends: Dict[StorageType, StorageBackend] = {}
        self.default_backend = StorageType.S3
        # Pass self to FileVersioningService to break circular dependency
        self.versioning_service = FileVersioningService(session, storage_manager=self)
        self.encryption_service = EncryptionService()

        # Initialize new services
        self.lifecycle_manager = StorageLifecycleManager(session)
        self.cdn_integration = CDNIntegration()
        self.categorization_service = DocumentCategorizationService()

        # Initialize configured backends
        self._initialize_backends()

        # File size limits by category (in bytes)
        self.size_limits = {
            FileCategory.MEDICAL_RECORD: 50 * 1024 * 1024,  # 50MB
            FileCategory.LAB_RESULT: 25 * 1024 * 1024,  # 25MB
            FileCategory.IMAGING: 100 * 1024 * 1024,  # 100MB
            FileCategory.PRESCRIPTION: 10 * 1024 * 1024,  # 10MB
            FileCategory.VACCINATION: 10 * 1024 * 1024,  # 10MB
            FileCategory.INSURANCE: 25 * 1024 * 1024,  # 25MB
            FileCategory.IDENTIFICATION: 10 * 1024 * 1024,  # 10MB
            FileCategory.CONSENT_FORM: 10 * 1024 * 1024,  # 10MB
            FileCategory.CLINICAL_NOTE: 5 * 1024 * 1024,  # 5MB
            FileCategory.VOICE_RECORDING: 50 * 1024 * 1024,  # 50MB
            FileCategory.OTHER: 25 * 1024 * 1024,  # 25MB
        }

        # Allowed MIME types by category
        self.allowed_types = {
            FileCategory.MEDICAL_RECORD: [
                "application/pdf",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "text/plain",
                "application/rtf",
            ],
            FileCategory.LAB_RESULT: [
                "application/pdf",
                "image/jpeg",
                "image/png",
                "application/dicom",
                "text/plain",
            ],
            FileCategory.IMAGING: [
                "image/jpeg",
                "image/png",
                "image/tiff",
                "application/dicom",
                "image/x-ray",
            ],
            FileCategory.PRESCRIPTION: ["application/pdf", "image/jpeg", "image/png"],
            FileCategory.VACCINATION: ["application/pdf", "image/jpeg", "image/png"],
            FileCategory.INSURANCE: ["application/pdf", "image/jpeg", "image/png"],
            FileCategory.IDENTIFICATION: ["image/jpeg", "image/png", "application/pdf"],
            FileCategory.CONSENT_FORM: ["application/pdf", "image/jpeg", "image/png"],
            FileCategory.CLINICAL_NOTE: [
                "text/plain",
                "application/pdf",
                "application/rtf",
            ],
            FileCategory.VOICE_RECORDING: [
                "audio/mpeg",
                "audio/wav",
                "audio/ogg",
                "audio/mp4",
                "audio/webm",
            ],
            FileCategory.OTHER: [],  # Allow all types
        }

    def _initialize_backends(self) -> None:
        """Initialize configured storage backends."""
        settings = get_settings()

        # Initialize S3 backend if configured
        if hasattr(settings, "aws_s3_bucket"):
            self.backends[StorageType.S3] = S3StorageBackend(
                {
                    "bucket_name": settings.aws_s3_bucket,
                    "region": settings.aws_region,
                    "access_key_id": settings.aws_access_key_id,
                    "secret_access_key": settings.aws_secret_access_key,
                    "encryption": "AES256",  # Server-side encryption
                    "storage_class": "STANDARD_IA",  # Infrequent access for cost savings
                }
            )

        # Initialize local backend for development/testing
        if settings.environment == "development":
            # Implement LocalStorageBackend
            self.backends[StorageType.LOCAL] = LocalStorageBackend(
                {
                    "base_path": getattr(settings, "local_storage_path", None)
                    or os.path.join(tempfile.gettempdir(), "haven_storage"),
                    "create_dirs": True,
                }
            )

            # Use local as default in development
            if StorageType.S3 not in self.backends:
                # For now, use S3 even in development
                pass

    def store_file(
        self,
        file_data: Union[BinaryIO, bytes],
        filename: str,
        category: Optional[FileCategory] = None,
        patient_id: Optional[UUID] = None,
        health_record_id: Optional[UUID] = None,
        uploaded_by: Optional[UUID] = None,
        description: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        backend_type: Optional[StorageType] = None,
        encrypt: bool = True,
        create_version: bool = True,
        version_change_type: VersionChangeType = VersionChangeType.MINOR,
        version_description: Optional[str] = None,
        requires_approval: bool = False,
        auto_categorize: bool = True,
    ) -> FileAttachment:
        """
        Store a file and create database record with optional versioning.

        Args:
            file_data: File data (binary stream or bytes)
            filename: Original filename
            category: File category (optional if auto_categorize is True)
            patient_id: Associated patient ID
            health_record_id: Associated health record ID
            uploaded_by: User who uploaded the file
            description: File description
            tags: Key-value tags
            metadata: Additional metadata
            backend_type: Specific backend to use
            encrypt: Whether to encrypt the file
            create_version: Whether to create a version instead of overwriting
            version_change_type: Type of change for versioning
            version_description: Description of version changes
            requires_approval: Whether version needs approval
            auto_categorize: Whether to automatically categorize the file

        Returns:
            FileAttachment database record
        """
        try:
            # Convert bytes to stream if needed
            if isinstance(file_data, bytes):
                file_data = io.BytesIO(file_data)

            # Get backend
            backend = self._get_backend(backend_type)

            # Get content type
            content_type = backend.guess_content_type(filename)

            # Auto-categorize if needed
            if auto_categorize and not category:
                # Extract text content if possible (for PDFs, etc.)
                content_text = None
                if content_type == "application/pdf":
                    try:
                        # Implement PDF text extraction
                        # Save current position
                        current_pos = file_data.tell()
                        file_data.seek(0)

                        try:
                            import PyPDF2  # pylint: disable=import-outside-toplevel

                            pdf_reader = PyPDF2.PdfReader(file_data)
                            text_parts = []

                            # Extract text from each page
                            for _page_num, page in enumerate(pdf_reader.pages):
                                text = page.extract_text()
                                if text.strip():
                                    text_parts.append(text)

                            content_text = "\n\n".join(text_parts)

                            # Log extraction success
                            logger.info(
                                f"Extracted {len(content_text)} characters from PDF '{filename}'"
                            )

                        except ImportError:
                            logger.warning(
                                "PyPDF2 not installed. Cannot extract PDF text."
                            )
                            content_text = None
                        except (ValueError, OSError) as e:
                            logger.warning(
                                f"Failed to extract text from PDF '{filename}': {e}"
                            )
                            content_text = None
                        finally:
                            # Restore file position
                            file_data.seek(current_pos)
                    except (ValueError, ImportError, RuntimeError):
                        pass

                # Categorize document
                category, confidence, analysis = (
                    self.categorization_service.categorize_document(
                        filename=filename,
                        content_type=content_type,
                        content_text=content_text,
                        metadata=metadata,
                    )
                )

                # Store categorization analysis in metadata
                if not metadata:
                    metadata = {}
                metadata["categorization"] = {
                    "auto_categorized": True,
                    "confidence": confidence,
                    "analysis": analysis,
                }

                logger.info(
                    f"Auto-categorized file '{filename}' as {category.value if category else 'unknown'} "
                    f"with confidence {confidence:.2f}"
                )
            elif not category:
                # Default category if not provided and auto-categorization disabled
                category = FileCategory.OTHER

            # Ensure category is not None for type safety
            assert category is not None

            # Validate file
            self._validate_file(file_data, filename, category)

            # Check if file already exists for versioning
            existing_file = None
            if create_version and patient_id:
                existing_file = (
                    self.session.query(FileAttachment)
                    .filter(
                        FileAttachment.patient_id == patient_id,
                        FileAttachment.filename == filename,
                        FileAttachment.category == category,
                        FileAttachment.status == FileStatus.AVAILABLE,
                    )
                    .first()
                )

            # Generate file ID
            if existing_file and create_version:
                file_id = existing_file.file_id
            else:
                file_id = self._generate_file_id(patient_id, category)

            # Get content type
            content_type = backend.guess_content_type(filename)

            # Calculate checksum before encryption
            original_checksum = backend.calculate_checksum(file_data)

            # Encrypt if requested
            encryption_key = None
            if encrypt:
                encrypted_data, encryption_key = self._encrypt_file(file_data)
                file_data = encrypted_data

            # Prepare storage metadata
            storage_metadata: Dict[str, Any] = {
                "original_filename": filename,
                "category": category.value,
                "patient_id": str(patient_id) if patient_id else None,
                "health_record_id": str(health_record_id) if health_record_id else None,
                "uploaded_by": str(uploaded_by) if uploaded_by else None,
                "encrypted": encrypt,
                "original_checksum": original_checksum,
            }

            if metadata:
                storage_metadata["custom"] = metadata

            # If versioning is enabled and file exists, create version
            if existing_file and create_version:
                # Reset file data position
                file_data.seek(0)

                # Create version using versioning service
                version = self.versioning_service.create_version(
                    file_id=file_id,
                    file_data=file_data,
                    filename=filename,
                    created_by=uploaded_by
                    or UUID("00000000-0000-0000-0000-000000000000"),
                    change_type=version_change_type,
                    change_description=version_description or description,
                    metadata={
                        **(metadata or {}),
                        "health_record_id": (
                            str(health_record_id) if health_record_id else None
                        ),
                        "encrypted": encrypt,
                        "encryption_key_id": (
                            encryption_key["key_id"] if encryption_key else None
                        ),
                    },
                    tags=list(tags.values()) if tags else None,
                    requires_approval=requires_approval,
                    category=category,
                )

                # Update existing attachment with new version info
                existing_file.version = version.version_number
                # updated_at will be automatically set by SQLAlchemy onupdate
                existing_file.checksum = version.checksum
                existing_file.size = version.size

                attachment = existing_file
                self.session.commit()
            else:
                # Store in backend
                file_metadata = backend.put(
                    file_id=file_id,
                    file_data=file_data,
                    content_type=content_type,
                    metadata=storage_metadata,
                    tags=tags,
                )

                # Create database record
                attachment = FileAttachment(
                    file_id=file_id,
                    filename=filename,
                    content_type=content_type,
                    size=file_metadata.size,
                    checksum=file_metadata.checksum,
                    storage_backend=backend_type or self.default_backend,
                    storage_path=file_id,
                    category=category,
                    status=FileStatus.AVAILABLE,
                    patient_id=patient_id,
                    health_record_id=health_record_id,
                    uploaded_by=uploaded_by,
                    description=description,
                    tags=tags or {},
                    metadata=metadata or {},
                    encrypted=encrypt,
                    encryption_key_id=(
                        encryption_key["key_id"] if encryption_key else None
                    ),
                    version=1,
                )

                self.session.add(attachment)
                self.session.commit()

            logger.info(
                f"Stored file {file_id} - "
                f"Category: {category}, Size: {file_metadata.size}, "
                f"Backend: {backend_type or self.default_backend}"
            )

            return attachment

        except Exception as e:
            logger.error(f"Error storing file: {e}")
            self.session.rollback()
            raise

    def retrieve_file(
        self, file_id: str, version: Optional[int] = None, decrypt: bool = True
    ) -> Tuple[BinaryIO, FileAttachment]:
        """
        Retrieve a file from storage with version support.

        Args:
            file_id: File ID
            version: Specific version (latest if None)
            decrypt: Whether to decrypt the file

        Returns:
            Tuple of (file data, database record)
        """
        # Get database record
        attachment = (
            self.session.query(FileAttachment)
            .filter(FileAttachment.file_id == file_id)
            .first()
        )

        if not attachment:
            raise StorageFileNotFoundError(f"File {file_id} not found")

        if attachment.status == FileStatus.DELETED:
            raise StorageFileNotFoundError(f"File {file_id} has been deleted")

        # Check if we should use versioning service
        file_version = self.versioning_service.get_version(
            file_id=file_id, version_number=version
        )

        if file_version:
            # Retrieve versioned file
            backend = self._get_backend(attachment.storage_backend)
            file_data, _ = backend.get(file_version.storage_path)

            # Handle decryption if needed
            if decrypt and file_version.metadata.get("encrypted"):
                encryption_key_id = file_version.metadata.get("encryption_key_id")
                if encryption_key_id:
                    file_data = self._decrypt_file(file_data, encryption_key_id)
        else:
            # Fallback to direct backend retrieval
            backend = self._get_backend(attachment.storage_backend)
            file_data, _ = backend.get(file_id=file_id, version=version)

            # Decrypt if needed
            if attachment.encrypted and decrypt:
                decrypted_data = self._decrypt_file(
                    file_data, attachment.encryption_key_id
                )
                file_data = decrypted_data

        # Update access timestamp
        attachment.last_accessed_at = datetime.utcnow()
        attachment.access_count = (attachment.access_count or 0) + 1
        self.session.commit()

        return file_data, attachment

    def delete_file(
        self, file_id: str, permanent: bool = False, deleted_by: Optional[UUID] = None
    ) -> bool:
        """
        Delete a file from storage.

        Args:
            file_id: File ID
            permanent: If True, permanently delete; if False, soft delete
            deleted_by: User who deleted the file

        Returns:
            True if successfully deleted
        """
        # Get database record
        attachment = (
            self.session.query(FileAttachment)
            .filter(FileAttachment.file_id == file_id)
            .first()
        )

        if not attachment:
            raise StorageFileNotFoundError(f"File {file_id} not found")

        # Get backend
        backend = self._get_backend(attachment.storage_backend)

        if permanent:
            # Permanently delete from backend
            success = backend.delete(file_id=file_id, permanent=True)

            if success:
                # Remove database record
                self.session.delete(attachment)
                self.session.commit()

                logger.info(f"Permanently deleted file {file_id}")
        else:
            # Soft delete - mark as deleted in database
            attachment.status = FileStatus.DELETED
            attachment.deleted_at = datetime.utcnow()
            attachment.deleted_by = deleted_by
            self.session.commit()

            logger.info(f"Soft deleted file {file_id}")
            success = True

        return success

    def list_files(
        self,
        patient_id: Optional[UUID] = None,
        health_record_id: Optional[UUID] = None,
        category: Optional[FileCategory] = None,
        status: Optional[FileStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[FileAttachment]:
        """
        List files based on filters.

        Args:
            patient_id: Filter by patient
            health_record_id: Filter by health record
            category: Filter by category
            status: Filter by status
            limit: Maximum results
            offset: Skip results

        Returns:
            List of FileAttachment records
        """
        query = self.session.query(FileAttachment)

        if patient_id:
            query = query.filter(FileAttachment.patient_id == patient_id)

        if health_record_id:
            query = query.filter(FileAttachment.health_record_id == health_record_id)

        if category:
            query = query.filter(FileAttachment.category == category)

        if status:
            query = query.filter(FileAttachment.status == status)
        else:
            # Default to active files only
            query = query.filter(FileAttachment.status == FileStatus.AVAILABLE)

        # Order by most recent first
        query = query.order_by(FileAttachment.created_at.desc())

        # Apply pagination
        files = query.limit(limit).offset(offset).all()

        return files

    def generate_download_url(
        self,
        file_id: str,
        expiration: Optional[timedelta] = None,
        content_disposition: Optional[str] = None,
    ) -> str:
        """
        Generate a pre-signed download URL.

        Args:
            file_id: File ID
            expiration: URL expiration time
            content_disposition: Content disposition header

        Returns:
            Pre-signed URL
        """
        if expiration is None:
            expiration = timedelta(hours=1)
        # Get database record
        attachment = (
            self.session.query(FileAttachment)
            .filter(FileAttachment.file_id == file_id)
            .first()
        )

        if not attachment:
            raise StorageFileNotFoundError(f"File {file_id} not found")

        if attachment.status != FileStatus.AVAILABLE:
            raise StorageException(f"File {file_id} is not active")

        # Get backend
        backend = self._get_backend(attachment.storage_backend)

        # Generate URL
        url = backend.generate_presigned_url(
            file_id=file_id,
            operation="get",
            expiration=expiration,
            content_disposition=content_disposition
            or f'attachment; filename="{attachment.filename}"',
        )

        # Log URL generation
        logger.info(f"Generated download URL for file {file_id}")

        return url

    def generate_upload_url(
        self,
        filename: str,
        category: FileCategory,
        patient_id: Optional[UUID] = None,
        content_type: Optional[str] = None,
        expiration: Optional[timedelta] = None,
        backend_type: Optional[StorageType] = None,
    ) -> Dict[str, Any]:
        """
        Generate a pre-signed upload URL.

        Args:
            filename: Original filename
            category: File category
            patient_id: Associated patient ID
            content_type: MIME type
            expiration: URL expiration time
            backend_type: Specific backend to use

        Returns:
            Dictionary with upload URL and file ID
        """
        if expiration is None:
            expiration = timedelta(hours=1)
        # Get backend
        backend = self._get_backend(backend_type)

        # Generate file ID
        file_id = self._generate_file_id(patient_id, category)

        # Guess content type if not provided
        if not content_type:
            content_type = backend.guess_content_type(filename)

        # Validate content type for category
        if not self._is_valid_content_type(content_type, category):
            raise StorageException(
                f"Content type {content_type} not allowed for category {category}"
            )

        # Generate URL
        url = backend.generate_presigned_url(
            file_id=file_id,
            operation="put",
            expiration=expiration,
            content_type=content_type,
        )

        return {
            "upload_url": url,
            "file_id": file_id,
            "expires_at": (datetime.utcnow() + expiration).isoformat(),
        }

    def _get_backend(
        self, backend_type: Optional[StorageType] = None
    ) -> StorageBackend:
        """Get storage backend instance."""
        backend_type = backend_type or self.default_backend

        if backend_type not in self.backends:
            raise StorageException(f"Backend {backend_type} not configured")

        return self.backends[backend_type]

    def _generate_file_id(
        self, patient_id: Optional[UUID], category: FileCategory
    ) -> str:
        """Generate unique file ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        unique_id = str(uuid4())

        if patient_id:
            return f"patients/{patient_id}/{category.value}/{timestamp}/{unique_id}"
        else:
            return f"general/{category.value}/{timestamp}/{unique_id}"

    def _validate_file(
        self, file_data: BinaryIO, filename: str, category: FileCategory
    ) -> None:
        """Validate file before storage."""
        # Check file size
        file_data.seek(0, 2)  # Seek to end
        size = file_data.tell()
        file_data.seek(0)  # Reset to beginning

        max_size = self.size_limits.get(category, 25 * 1024 * 1024)
        if size > max_size:
            raise StorageException(
                f"File size {size} exceeds limit {max_size} for category {category}"
            )

        # Check content type
        backend = self._get_backend()
        content_type = backend.guess_content_type(filename)

        if not self._is_valid_content_type(content_type, category):
            raise StorageException(
                f"Content type {content_type} not allowed for category {category}"
            )

    def _is_valid_content_type(self, content_type: str, category: FileCategory) -> bool:
        """Check if content type is valid for category."""
        allowed = self.allowed_types.get(category, [])

        # If no restrictions, allow all
        if not allowed:
            return True

        # Check exact match or prefix match
        return any(
            content_type == allowed_type or content_type.startswith(allowed_type + ";")
            for allowed_type in allowed
        )

    def _encrypt_file(self, file_data: BinaryIO) -> Tuple[BinaryIO, Dict[str, str]]:
        """Encrypt file data."""
        # Read file data
        file_data.seek(0)
        data = file_data.read()

        # Convert bytes to base64 string for encryption
        data_str = base64.b64encode(data).decode("utf-8")

        # Encrypt
        encrypted_data = self.encryption_service.encrypt(data_str)

        # Return as stream
        return io.BytesIO(encrypted_data.encode("utf-8")), {"encrypted": "true"}

    def _decrypt_file(self, file_data: BinaryIO, key_id: str) -> BinaryIO:
        """Decrypt file data."""
        _ = key_id  # Mark as intentionally unused
        # Read encrypted data
        file_data.seek(0)
        encrypted_data = file_data.read()

        # Decrypt expects string, convert bytes to string
        encrypted_str = encrypted_data.decode("utf-8")
        decrypted_data = self.encryption_service.decrypt(encrypted_str)

        # Convert base64 string back to bytes
        decrypted_bytes = base64.b64decode(decrypted_data)

        # Return as stream
        return io.BytesIO(decrypted_bytes)

    def get_storage_statistics(
        self,
        patient_id: Optional[UUID] = None,
        backend_type: Optional[StorageType] = None,
    ) -> Dict[str, Any]:
        """
        Get storage usage statistics.

        Args:
            patient_id: Filter by patient
            backend_type: Filter by backend

        Returns:
            Dictionary with statistics
        """
        query = self.session.query(
            FileAttachment.category,
            func.count(FileAttachment.id).label(  # pylint: disable=not-callable
                "count"
            ),
            func.sum(FileAttachment.size).label("total_size"),
        ).filter(FileAttachment.status == FileStatus.AVAILABLE)

        if patient_id:
            query = query.filter(FileAttachment.patient_id == patient_id)

        if backend_type:
            query = query.filter(FileAttachment.storage_backend == backend_type)

        # Group by category
        category_stats = query.group_by(FileAttachment.category).all()

        # Calculate totals
        total_files = sum(stat.count for stat in category_stats)
        total_size = sum(stat.total_size or 0 for stat in category_stats)

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "by_category": {
                stat.category.value: {
                    "count": stat.count,
                    "size_bytes": stat.total_size or 0,
                    "size_mb": round((stat.total_size or 0) / (1024 * 1024), 2),
                }
                for stat in category_stats
            },
            "backend": backend_type.value if backend_type else "all",
        }

    def get_file_versions(
        self, file_id: str, include_deleted: bool = False, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get version history for a file.

        Args:
            file_id: File ID
            include_deleted: Include deleted versions
            limit: Maximum versions to return

        Returns:
            List of version information
        """
        versions = self.versioning_service.get_version_history(
            file_id=file_id, include_deleted=include_deleted, limit=limit
        )

        return [
            {
                "version_id": v.version_id,
                "version_number": v.version_number,
                "filename": v.filename,
                "size": v.size,
                "status": v.status,
                "change_type": v.change_type,
                "change_description": v.change_description,
                "created_by": v.created_by,
                "created_at": v.created_at,
                "is_current": v.is_current,
            }
            for v in versions
        ]

    def compare_file_versions(
        self, file_id: str, version_a: int, version_b: int
    ) -> Dict[str, Any]:
        """
        Compare two versions of a file.

        Args:
            file_id: File ID
            version_a: First version number
            version_b: Second version number

        Returns:
            Version comparison information
        """
        diff = self.versioning_service.compare_versions(
            file_id=file_id, version_a=version_a, version_b=version_b
        )

        return {
            "version_a": diff.version_a,
            "version_b": diff.version_b,
            "size_change": diff.size_change,
            "hash_changed": diff.hash_changed,
            "metadata_changes": diff.metadata_changes,
            "change_summary": diff.change_summary,
        }

    def rollback_file_version(
        self, file_id: str, target_version: int, rolled_back_by: UUID, reason: str
    ) -> FileAttachment:
        """
        Rollback file to a previous version.

        Args:
            file_id: File ID
            target_version: Version to rollback to
            rolled_back_by: User performing rollback
            reason: Reason for rollback

        Returns:
            Updated file attachment
        """
        # Perform rollback
        new_version = self.versioning_service.rollback_version(
            file_id=file_id,
            target_version=target_version,
            rolled_back_by=rolled_back_by,
            reason=reason,
        )

        # Update attachment with new version info
        attachment = (
            self.session.query(FileAttachment)
            .filter(FileAttachment.file_id == file_id)
            .first()
        )

        if attachment:
            attachment.version = new_version.version_number
            # updated_at will be automatically set by SQLAlchemy onupdate
            attachment.checksum = new_version.checksum
            attachment.size = new_version.size
            self.session.commit()
            return attachment
        else:
            raise StorageFileNotFoundError(
                f"File attachment not found for file_id: {file_id}"
            )

    def approve_file_version(
        self, version_id: str, approved_by: UUID, approval_notes: Optional[str] = None
    ) -> bool:
        """
        Approve a pending file version.

        Args:
            version_id: Version ID to approve
            approved_by: User approving
            approval_notes: Optional approval notes

        Returns:
            Success status
        """
        try:
            version = self.versioning_service.approve_version(
                version_id=version_id,
                approved_by=approved_by,
                approval_notes=approval_notes,
            )

            # Update attachment if this becomes current
            if version.is_current:
                attachment = (
                    self.session.query(FileAttachment)
                    .filter(FileAttachment.file_id == version.file_id)
                    .first()
                )
                if attachment:
                    attachment.version = version.version_number
                    attachment.updated_at = datetime.utcnow()  # type: ignore[assignment]
                    self.session.commit()

            return True
        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Error approving version: {e}")
            return False

    def cleanup_old_versions(
        self, file_id: Optional[str] = None, keep_versions: int = 10
    ) -> int:
        """
        Clean up old file versions.

        Args:
            file_id: Specific file to clean up (all if None)
            keep_versions: Number of versions to keep

        Returns:
            Number of versions cleaned up
        """
        if file_id:
            return self.versioning_service.cleanup_versions(
                file_id=file_id, keep_versions=keep_versions
            )
        else:
            # Clean up all files
            total_cleaned = 0
            attachments = (
                self.session.query(FileAttachment)
                .filter(FileAttachment.status == FileStatus.AVAILABLE)
                .all()
            )

            for attachment in attachments:
                cleaned = self.versioning_service.cleanup_versions(
                    file_id=attachment.file_id, keep_versions=keep_versions
                )
                total_cleaned += cleaned

            return total_cleaned

    def get_version_storage_usage(self, file_id: str) -> Dict[str, Any]:
        """
        Get storage usage for all versions of a file.

        Args:
            file_id: File ID

        Returns:
            Storage usage statistics
        """
        return self.versioning_service.get_storage_usage(file_id)

    # CDN Integration Methods

    def get_cdn_url(
        self,
        file_id: str,
        expires_in: int = 3600,
        download: bool = False,
    ) -> Optional[str]:
        """Get CDN URL for a file.

        Args:
            file_id: File ID
            expires_in: Seconds until URL expires
            download: Force download instead of inline display

        Returns:
            CDN URL or None if file not found
        """
        attachment = (
            self.session.query(FileAttachment)
            .filter(FileAttachment.file_id == file_id)
            .first()
        )

        if not attachment:
            return None

        # Update last accessed timestamp
        attachment.last_accessed_at = datetime.utcnow()
        self.session.commit()

        # Get CDN URL
        return self.cdn_integration.get_cdn_url(
            file=attachment,
            expires_in=expires_in,
            download=download,
        )

    def invalidate_cdn_cache(self, file_ids: List[str]) -> bool:
        """Invalidate CDN cache for files.

        Args:
            file_ids: List of file IDs to invalidate

        Returns:
            True if invalidation was initiated
        """
        # Get S3 keys for the files
        attachments = (
            self.session.query(FileAttachment)
            .filter(FileAttachment.file_id.in_(file_ids))
            .all()
        )

        if not attachments:
            return False

        s3_keys = [att.storage_path for att in attachments]
        invalidation_id = self.cdn_integration.invalidate_cache(s3_keys)

        return invalidation_id is not None

    # Lifecycle Management Methods

    def process_lifecycle_policies(self, batch_size: int = 100) -> Dict[str, List[str]]:
        """Process files according to lifecycle policies.

        Args:
            batch_size: Number of files to process

        Returns:
            Dictionary with processed file IDs by action
        """
        return self.lifecycle_manager.process_lifecycle_policies(batch_size)

    def archive_files(self, file_ids: List[str]) -> int:
        """Archive files to cheaper storage.

        Args:
            file_ids: List of file IDs to archive

        Returns:
            Number of files archived
        """
        count = self.lifecycle_manager.archive_files(file_ids)

        # Move files to archive storage tier in S3
        if count > 0 and StorageType.S3 in self.backends:
            s3_backend = self.backends[StorageType.S3]
            for file_id in file_ids:
                try:
                    # Change storage class to GLACIER
                    if hasattr(s3_backend, "change_storage_class"):
                        s3_backend.change_storage_class(file_id, "GLACIER")
                    else:
                        logger.warning(
                            f"S3 backend does not support change_storage_class for file {file_id}"
                        )
                except (ValueError, RuntimeError, AttributeError) as e:
                    logger.error(f"Failed to archive file {file_id} in S3: {e}")

        return count

    def restore_from_archive(self, file_id: str) -> bool:
        """Restore file from archive.

        Args:
            file_id: File ID to restore

        Returns:
            True if restored successfully
        """
        success = self.lifecycle_manager.restore_from_archive(file_id)

        if success and StorageType.S3 in self.backends:
            s3_backend = self.backends[StorageType.S3]
            try:
                # Restore from GLACIER to STANDARD
                if hasattr(s3_backend, "restore_from_glacier"):
                    s3_backend.restore_from_glacier(file_id)
            except (ValueError, RuntimeError, AttributeError) as e:
                logger.error(f"Failed to restore file {file_id} from S3 archive: {e}")

        return success

    def set_file_retention_policy(
        self,
        file_id: str,
        retention_policy: str,
        retention_date: Optional[datetime] = None,
    ) -> bool:
        """Set custom retention policy for a file.

        Args:
            file_id: File ID
            retention_policy: Retention policy name
            retention_date: Custom retention date

        Returns:
            True if policy was set
        """
        attachment = (
            self.session.query(FileAttachment)
            .filter(FileAttachment.file_id == file_id)
            .first()
        )

        if not attachment:
            return False

        # Update lifecycle metadata
        if not attachment.lifecycle_metadata:
            attachment.lifecycle_metadata = {}

        attachment.lifecycle_metadata["retention_policy"] = retention_policy
        if retention_date:
            attachment.lifecycle_metadata["retention_date"] = retention_date.isoformat()

        self.session.commit()
        return True
