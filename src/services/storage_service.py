"""Storage service for report files.

This module provides a simple interface for storing and retrieving
generated report files.
"""

from datetime import datetime, timedelta
from typing import BinaryIO, Optional

from src.storage.base import FileCategory
from src.storage.manager import StorageManager
from src.utils.logging import get_logger

logger = get_logger(__name__)


class StorageService:
    """Service for managing report file storage."""

    def __init__(self, storage_manager: Optional[StorageManager] = None):
        """Initialize storage service."""
        self.storage_manager = storage_manager

    async def upload_report(
        self, file_path: str, report_id: str, file_format: str
    ) -> str:
        """Upload a report file and return the download URL."""
        try:
            # If no storage manager provided, use local storage
            if not self.storage_manager:
                # For now, just return a local file URL
                # In production, this would upload to S3/CDN
                return f"/api/v2/reports/{report_id}/download"

            # Read file
            with open(file_path, "rb") as f:
                file_data = f.read()

            # Generate unique filename
            filename = f"report_{report_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{file_format}"

            # Upload using storage manager
            file_info = await self.storage_manager.store_file(
                file_data=file_data,
                filename=filename,
                uploaded_by=None,  # System-generated reports
                category=FileCategory.OTHER,
                description=f"Generated report {report_id}",
                metadata={
                    "report_id": report_id,
                    "format": file_format,
                    "generated_at": datetime.utcnow().isoformat(),
                },
            )

            # Return download URL
            download_url = file_info.get(
                "download_url", f"/api/v2/reports/{report_id}/download"
            )
            return str(download_url)

        except (OSError, ValueError, AttributeError) as e:
            logger.error(f"Failed to upload report {report_id}: {str(e)}")
            # Return fallback URL
            return f"/api/v2/reports/{report_id}/download"

    async def get_report_file(self, report_id: str) -> Optional[BinaryIO]:
        """Retrieve a report file."""
        try:
            if self.storage_manager:
                # TODO: StorageManager needs get_file_by_metadata method
                # For now, return None to prevent runtime errors
                logger.warning(
                    f"get_file_by_metadata not implemented for report {report_id}"
                )
                return None
            return None
        except (OSError, ValueError, AttributeError) as e:
            logger.error(f"Failed to retrieve report {report_id}: {str(e)}")
            return None

    async def delete_expired_reports(self, days: int = 30) -> int:
        """Delete reports older than specified days."""
        try:
            if self.storage_manager:
                # TODO: StorageManager needs delete_files_before_date method
                # For now, return 0 to prevent runtime errors
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                logger.warning(
                    f"delete_files_before_date not implemented for cutoff {cutoff_date}"
                )
                return 0
            return 0
        except (OSError, ValueError, AttributeError) as e:
            logger.error(f"Failed to delete expired reports: {str(e)}")
            return 0
