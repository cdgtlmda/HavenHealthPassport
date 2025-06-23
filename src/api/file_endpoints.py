"""File management REST API endpoints."""

import hashlib
import io
import json
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.models.auth import UserAuth
from src.services.file_service import FileService
from src.services.file_validation_service import FileValidationService
from src.services.virus_scan_service import VirusScanService
from src.storage.base import FileCategory as StorageFileCategory
from src.storage.manager import StorageManager
from src.utils.logging import get_logger

from .auth_endpoints import get_current_user

router = APIRouter(prefix="/files", tags=["files"])
logger = get_logger(__name__)

# Module-level dependency variables to avoid B008 errors
db_dependency = Depends(get_db)
current_user_dependency = Depends(get_current_user)
file_dependency = File(...)
form_category_dependency = Form(
    ..., regex="^(medical_record|lab_result|prescription|imaging|document|photo)$"
)
form_metadata_dependency = Form(None)


# Response Models
class FileUploadResponse(BaseModel):
    """File upload response."""

    file_id: uuid.UUID
    filename: str
    size: int
    content_type: str
    checksum: str
    scan_status: str
    metadata: Dict[str, Any] = {}


@router.post(
    "/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED
)
async def upload_file(
    file: UploadFile = file_dependency,
    category: str = form_category_dependency,
    metadata: Optional[str] = form_metadata_dependency,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> FileUploadResponse:
    """Upload a file with virus scanning and validation."""
    try:
        # Initialize services
        file_service = FileService(db)
        validation_service = FileValidationService()
        scan_service = VirusScanService()

        # Read file content first
        content = await file.read()

        # Create a BytesIO object for validation
        file_data = io.BytesIO(content)

        # Validate file type and size
        validation_result = validation_service.validate_file(
            file_data=file_data, filename=file.filename or "unknown"
        )

        if not validation_result.is_valid:
            error_msg = "; ".join(validation_result.issues)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg
            )

        # Check file size limit (50MB) - use validation result
        file_size = validation_result.metadata.get("file_size", 0)
        if file_size > 50 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size exceeds 50MB limit",
            )

        # Calculate file hash
        file_hash = hashlib.sha256(content).hexdigest()

        # Scan for viruses (content already read above)
        scan_result = await scan_service.scan_file(
            content, file_hash, file.filename or "unknown"
        )

        if scan_result.get("infected", False):
            logger.warning(
                f"Virus detected in file {file.filename}: {scan_result.get('threats', [])}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="File contains malware"
            )

        # Parse metadata if provided
        file_metadata = {"category": category}
        if metadata:
            try:
                additional_metadata = json.loads(metadata)
                file_metadata.update(additional_metadata)
            except (json.JSONDecodeError, ValueError):
                pass

        # Generate storage key
        storage_key = (
            f"uploads/{current_user.patient_id}/{file_hash[:8]}/{file.filename}"
        )

        # Store file metadata
        stored_file = file_service.create_file_attachment(
            filename=file.filename or "unknown",
            content_type=file.content_type or "application/octet-stream",
            size=file_size,
            storage_key=storage_key,
            file_hash=file_hash,
            patient_id=current_user.patient_id,
            access_level="private",
            metadata=file_metadata,
        )

        # Store the content to storage backend
        # Map API category to storage category
        category_map = {
            "medical_record": StorageFileCategory.MEDICAL_RECORD,
            "lab_result": StorageFileCategory.LAB_RESULT,
            "prescription": StorageFileCategory.PRESCRIPTION,
            "imaging": StorageFileCategory.IMAGING,
            "document": StorageFileCategory.OTHER,
            "photo": StorageFileCategory.OTHER,
        }

        storage_manager = StorageManager(db)

        # Extract tags
        tags_value = file_metadata.get("tags")
        tags = tags_value if isinstance(tags_value, dict) else None

        # Store the file
        storage_result = storage_manager.store_file(
            file_data=content,
            filename=file.filename or "unknown",
            category=category_map.get(category, StorageFileCategory.OTHER),
            patient_id=current_user.patient_id,
            health_record_id=None,  # Can be linked later
            uploaded_by=current_user.id,
            description=file_metadata.get("description"),
            tags=tags,
            metadata=file_metadata,
            encrypt=True,
        )

        # Update the file attachment with the actual storage information
        stored_file.storage_key = storage_result.storage_key
        stored_file.id = storage_result.id

        db.commit()

        return FileUploadResponse(
            file_id=stored_file.id,
            filename=str(stored_file.filename),
            size=int(stored_file.size),
            content_type=str(stored_file.content_type),
            checksum=str(stored_file.file_hash),
            scan_status="clean",
            metadata=stored_file.metadata or {},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload error: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File upload failed",
        ) from e


@router.get("/download/{file_id}")
async def download_file(
    file_id: uuid.UUID,
    current_user: UserAuth = current_user_dependency,
    db: Session = db_dependency,
) -> StreamingResponse:
    """Download a file with access control."""
    try:
        file_service = FileService(db)

        # Get file record
        file_record = file_service.get_by_id(file_id)

        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )

        # Check access permissions
        # Simple check: user must own the patient record or be the uploader
        has_access = (
            file_record.patient_id == current_user.patient_id
            or file_record.uploaded_by == current_user.id
            or current_user.is_superuser
        )

        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        # Retrieve from actual storage backend
        storage_manager = StorageManager(db)

        try:
            # Retrieve the file content
            content, _ = storage_manager.retrieve_file(  # metadata not used here
                file_id=str(file_record.id)
            )

            if not content:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File content not found in storage",
                )
        except Exception as e:
            logger.error(f"Failed to retrieve file {file_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve file content",
            ) from e

        # Set cache headers for CDN
        headers = {
            "Cache-Control": "private, max-age=3600",
            "Content-Disposition": f'attachment; filename="{file_record.filename}"',
            "Content-Type": str(file_record.content_type),
            "ETag": str(file_record.file_hash),
        }

        # Return file as streaming response
        return StreamingResponse(
            io.BytesIO(content),  # type: ignore[arg-type]
            media_type=(
                str(file_record.content_type)
                if file_record.content_type
                else "application/octet-stream"
            ),
            headers=headers,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File download error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File download failed",
        ) from e
