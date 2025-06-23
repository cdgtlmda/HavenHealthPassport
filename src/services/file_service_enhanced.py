"""Enhanced file service with validation support."""

import uuid
from datetime import datetime
from typing import Any, BinaryIO, Callable, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.file_attachment import FileAttachment, FileStatus
from src.services.file_service import FileService
from src.services.file_validation_service import FileType, FileValidationService
from src.storage.base import FileCategory
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EnhancedFileService(FileService):
    """Enhanced file service with integrated validation."""

    def __init__(self, db: Session):
        """Initialize enhanced file service."""
        super().__init__(db)
        self.validation_service = FileValidationService()

    def create_file_attachment_with_validation(
        self,
        file_data: BinaryIO,
        filename: str,
        content_type: str,
        storage_key: str,
        patient_id: Optional[uuid.UUID] = None,
        record_id: Optional[uuid.UUID] = None,
        category: Optional[FileCategory] = None,
        access_level: str = "private",
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        skip_validation: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a file attachment with validation.

        Args:
            file_data: Binary file data for validation
            filename: Original filename
            content_type: MIME type
            storage_key: Storage location key
            patient_id: Associated patient ID
            record_id: Associated record ID
            category: File category for validation
            access_level: Access level (private/public)
            title: File title
            description: File description
            tags: File tags
            metadata: Additional metadata
            skip_validation: Skip validation if True

        Returns:
            Dictionary with attachment and validation results
        """
        validation_result = None
        validation_passed = True

        # Perform validation unless skipped
        if not skip_validation:
            if category:
                validation_result = self.validation_service.validate_for_category(
                    file_data, filename, category
                )
            else:
                validation_result = self.validation_service.validate_file(
                    file_data, filename
                )

            validation_passed = validation_result.is_valid

            # Log validation results
            if not validation_passed:
                logger.warning(
                    f"File validation failed for {filename}: {validation_result.issues}"
                )

        # Calculate file hash
        file_hash = self.validation_service.calculate_file_hash(file_data)

        # Get file size
        file_data.seek(0, 2)
        file_size = file_data.tell()
        file_data.seek(0)

        # Add validation metadata
        if metadata is None:
            metadata = {}

        if validation_result:
            metadata["validation"] = {
                "performed": True,
                "passed": validation_passed,
                "file_type": validation_result.file_type.value,
                "mime_type": validation_result.mime_type,
                "issues": validation_result.issues,
                "metadata": validation_result.metadata,
            }
        else:
            metadata["validation"] = {"performed": False, "skipped": True}

        # Create file attachment
        try:
            attachment = self.create_file_attachment(
                filename=filename,
                content_type=(
                    validation_result.mime_type if validation_result else content_type
                ),
                size=file_size,
                storage_key=storage_key,
                file_hash=file_hash,
                patient_id=patient_id,
                record_id=record_id,
                access_level=access_level,
                title=title,
                description=description,
                tags=tags,
                metadata=metadata,
            )

            # Update status based on validation
            if validation_passed:
                attachment.status = FileStatus.AVAILABLE
            else:
                attachment.status = FileStatus.QUARANTINED

            self.db.commit()

            return {
                "attachment": attachment,
                "validation_result": validation_result,
                "validation_passed": validation_passed,
                "file_hash": file_hash,
            }

        except Exception as e:
            logger.error(f"Error creating file attachment: {e}")
            self.db.rollback()
            raise

    def validate_existing_file(
        self,
        file_id: uuid.UUID,
        file_data: BinaryIO,
        category: Optional[FileCategory] = None,
    ) -> Dict[str, Any]:
        """
        Validate an existing file attachment.

        Args:
            file_id: File attachment ID
            file_data: Binary file data
            category: File category for validation

        Returns:
            Validation results
        """
        # Get file attachment
        attachment = self.get_by_id(file_id)
        if not attachment:
            raise ValueError(f"File attachment {file_id} not found")

        # Perform validation
        if category:
            validation_result = self.validation_service.validate_for_category(
                file_data, str(attachment.filename), category
            )
        else:
            validation_result = self.validation_service.validate_file(
                file_data, str(attachment.filename)
            )

        # Update attachment metadata
        if attachment.metadata is None:
            attachment.metadata = {}

        attachment.metadata["validation"] = {
            "performed": True,
            "passed": validation_result.is_valid,
            "file_type": validation_result.file_type.value,
            "mime_type": validation_result.mime_type,
            "issues": validation_result.issues,
            "metadata": validation_result.metadata,
            "validated_at": datetime.utcnow().isoformat(),
        }

        # Update status
        if validation_result.is_valid:
            if attachment.status == FileStatus.QUARANTINED:
                attachment.status = FileStatus.AVAILABLE
        else:
            attachment.status = FileStatus.QUARANTINED

        self.db.commit()

        return {
            "attachment": attachment,
            "validation_result": validation_result,
            "validation_passed": validation_result.is_valid,
        }

    def get_files_by_validation_status(
        self,
        validation_passed: Optional[bool] = None,
        file_type: Optional[FileType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[FileAttachment]:
        """
        Get files filtered by validation status.

        Args:
            validation_passed: Filter by validation result
            file_type: Filter by detected file type
            limit: Maximum results
            offset: Skip results

        Returns:
            List of file attachments
        """
        query = self.db.query(FileAttachment)

        if validation_passed is not None:
            if validation_passed:
                query = query.filter(FileAttachment.status != FileStatus.QUARANTINED)
            else:
                query = query.filter(FileAttachment.status == FileStatus.QUARANTINED)

        if file_type:
            # Filter by file type in metadata
            query = query.filter(
                FileAttachment.metadata["validation"]["file_type"].astext
                == file_type.value
            )

        return query.limit(limit).offset(offset).all()

    def bulk_validate_files(
        self,
        file_ids: List[uuid.UUID],
        get_file_data_func: Callable[[uuid.UUID], BinaryIO],
    ) -> Dict[str, Any]:
        """
        Validate multiple files in bulk.

        Args:
            file_ids: List of file IDs to validate
            get_file_data_func: Function to retrieve file data by ID

        Returns:
            Bulk validation results
        """
        results: Dict[str, Any] = {
            "total": len(file_ids),
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "details": [],
        }

        for file_id in file_ids:
            try:
                # Get file data
                file_data = get_file_data_func(file_id)

                # Validate file
                validation_result = self.validate_existing_file(file_id, file_data)

                if validation_result["validation_passed"]:
                    results["passed"] += 1
                else:
                    results["failed"] += 1

                results["details"].append(
                    {
                        "file_id": str(file_id),
                        "passed": validation_result["validation_passed"],
                        "issues": validation_result["validation_result"].issues,
                    }
                )

            except (ValueError, AttributeError, KeyError) as e:
                logger.error(f"Error validating file {file_id}: {e}")
                results["errors"] += 1
                results["details"].append({"file_id": str(file_id), "error": str(e)})

        return results

    def get_validation_statistics(self) -> Dict[str, Any]:
        """Get file validation statistics."""
        total_files = self.db.query(func.count(FileAttachment.id)).scalar() or 0

        validated_files = (
            self.db.query(func.count(FileAttachment.id))  # pylint: disable=not-callable
            .filter(FileAttachment.metadata["validation"]["performed"].astext == "true")
            .scalar()
        )

        validation_passed = (
            self.db.query(func.count(FileAttachment.id))  # pylint: disable=not-callable
            .filter(
                FileAttachment.status != FileStatus.QUARANTINED,
                FileAttachment.metadata["validation"]["performed"].astext == "true",
            )
            .scalar()
        )

        validation_failed = (
            self.db.query(func.count(FileAttachment.id))  # pylint: disable=not-callable
            .filter(FileAttachment.status == FileStatus.QUARANTINED)
            .scalar()
        )

        # Get file type distribution
        file_types = (
            self.db.query(
                FileAttachment.metadata["validation"]["file_type"].astext,
                func.count(FileAttachment.id),  # pylint: disable=not-callable
            )
            .filter(FileAttachment.metadata["validation"]["performed"].astext == "true")
            .group_by(FileAttachment.metadata["validation"]["file_type"].astext)
            .all()
        )

        return {
            "total_files": total_files,
            "validated_files": validated_files,
            "validation_passed": validation_passed,
            "validation_failed": validation_failed,
            "validation_rate": (
                (validated_files / total_files * 100) if total_files > 0 else 0
            ),
            "pass_rate": (
                (validation_passed / validated_files * 100)
                if validated_files > 0
                else 0
            ),
            "file_type_distribution": {
                file_type: count for file_type, count in file_types
            },
        }
