"""File upload service for handling various upload strategies.

Security Note: This module processes PHI data. All uploaded files must be:
- Subject to role-based access control (RBAC) for PHI protection
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from io import BytesIO
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.file_attachment import FileAttachment, FileStatus
from src.services.base import BaseService
from src.storage.base import FileCategory
from src.storage.manager import StorageManager
from src.utils.logging import get_logger

logger = get_logger(__name__)


class UploadStrategy(str, Enum):
    """Upload strategies for different file sizes and types."""

    DIRECT = "direct"  # Small files < 5MB
    CHUNKED = "chunked"  # Medium files 5MB - 100MB
    MULTIPART = "multipart"  # Large files > 100MB
    RESUMABLE = "resumable"  # For unreliable connections


@dataclass
class ChunkInfo:
    """Information about a file chunk."""

    chunk_number: int
    total_chunks: int
    size: int
    checksum: str
    offset: int


@dataclass
class UploadSession:
    """Upload session for tracking multi-part uploads."""

    session_id: str
    file_id: str
    filename: str
    category: FileCategory
    total_size: int
    chunk_size: int
    total_chunks: int
    uploaded_chunks: List[int]
    upload_strategy: UploadStrategy
    created_at: datetime
    expires_at: datetime
    metadata: Dict[str, Any]
    checksum_algorithm: str = "sha256"

    @property
    def is_complete(self) -> bool:
        """Check if all chunks have been uploaded."""
        return len(self.uploaded_chunks) == self.total_chunks

    @property
    def progress_percent(self) -> float:
        """Calculate upload progress percentage."""
        if self.total_chunks == 0:
            return 0.0
        return (len(self.uploaded_chunks) / self.total_chunks) * 100

    @property
    def remaining_chunks(self) -> List[int]:
        """Get list of remaining chunk numbers."""
        all_chunks = set(range(self.total_chunks))
        uploaded = set(self.uploaded_chunks)
        return sorted(list(all_chunks - uploaded))


class FileUploadService(BaseService[FileAttachment]):
    """Service for handling file uploads with various strategies."""

    model_class = FileAttachment

    # Upload size thresholds
    DIRECT_UPLOAD_THRESHOLD = 5 * 1024 * 1024  # 5MB
    CHUNKED_UPLOAD_THRESHOLD = 100 * 1024 * 1024  # 100MB
    DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024  # 5MB chunks

    # Upload session settings
    SESSION_EXPIRY_HOURS = 24
    MAX_CONCURRENT_UPLOADS = 5

    def __init__(self, session: Session):
        """Initialize file upload service."""
        super().__init__(session)
        self.storage_manager = StorageManager(session)
        self._upload_sessions: Dict[str, UploadSession] = {}
        self._chunk_buffers: Dict[str, Dict[int, bytes]] = {}

    def determine_upload_strategy(
        self, file_size: int, connection_reliability: Optional[str] = "good"
    ) -> UploadStrategy:
        """
        Determine the best upload strategy based on file size and connection.

        Args:
            file_size: Size of file in bytes
            connection_reliability: Connection quality (good, fair, poor)

        Returns:
            Recommended upload strategy
        """
        if connection_reliability == "poor":
            return UploadStrategy.RESUMABLE
        elif file_size <= self.DIRECT_UPLOAD_THRESHOLD:
            return UploadStrategy.DIRECT
        elif file_size <= self.CHUNKED_UPLOAD_THRESHOLD:
            return UploadStrategy.CHUNKED
        else:
            return UploadStrategy.MULTIPART

    def create_upload_session(
        self,
        filename: str,
        file_size: int,
        category: FileCategory,
        patient_id: Optional[UUID] = None,
        uploaded_by: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
        upload_strategy: Optional[UploadStrategy] = None,
    ) -> UploadSession:
        """
        Create a new upload session for chunked/multipart uploads.

        Args:
            filename: Original filename
            file_size: Total file size
            category: File category
            patient_id: Associated patient
            uploaded_by: User initiating upload
            metadata: Additional metadata
            upload_strategy: Override strategy selection

        Returns:
            Upload session object
        """
        # Determine strategy if not provided
        if not upload_strategy:
            upload_strategy = self.determine_upload_strategy(file_size)

        # Calculate chunks
        chunk_size = self.DEFAULT_CHUNK_SIZE
        total_chunks = (file_size + chunk_size - 1) // chunk_size

        # Generate session ID and file ID
        session_id = f"upload_{UUID()}"
        file_id = f"{patient_id or 'shared'}_{category.value}_{UUID()}"

        # Create session
        session = UploadSession(
            session_id=session_id,
            file_id=file_id,
            filename=filename,
            category=category,
            total_size=file_size,
            chunk_size=chunk_size,
            total_chunks=total_chunks,
            uploaded_chunks=[],
            upload_strategy=upload_strategy,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=self.SESSION_EXPIRY_HOURS),
            metadata=metadata or {},
        )

        # Store session
        self._upload_sessions[session_id] = session

        # Initialize chunk buffer
        self._chunk_buffers[session_id] = {}

        # Create pending file record
        if uploaded_by:
            attachment = FileAttachment(
                file_id=file_id,
                filename=filename,
                content_type="application/octet-stream",  # Will be updated
                size=file_size,
                checksum="",  # Will be calculated
                storage_backend=self.storage_manager.default_backend,
                storage_path=file_id,
                category=category,
                status=FileStatus.PENDING,
                patient_id=patient_id,
                uploaded_by=uploaded_by,
                metadata={
                    "upload_session": {
                        "session_id": session_id,
                        "strategy": upload_strategy.value,
                        "total_chunks": total_chunks,
                    }
                },
            )

            self.session.add(attachment)
            self.session.commit()

        logger.info(
            f"Created upload session {session_id} - "
            f"Strategy: {upload_strategy}, Chunks: {total_chunks}"
        )

        return session

    async def upload_chunk(
        self,
        session_id: str,
        chunk_number: int,
        chunk_data: bytes,
        chunk_checksum: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload a chunk of a file.

        Args:
            session_id: Upload session ID
            chunk_number: Chunk number (0-based)
            chunk_data: Chunk data
            chunk_checksum: Optional checksum for verification

        Returns:
            Upload progress information
        """
        # Get session
        session = self._upload_sessions.get(session_id)
        if not session:
            raise ValueError(f"Upload session {session_id} not found")

        # Check if session expired
        if datetime.utcnow() > session.expires_at:
            raise ValueError(f"Upload session {session_id} has expired")

        # Validate chunk number
        if chunk_number >= session.total_chunks or chunk_number < 0:
            raise ValueError(f"Invalid chunk number {chunk_number}")

        # Check if chunk already uploaded
        if chunk_number in session.uploaded_chunks:
            logger.warning(
                f"Chunk {chunk_number} already uploaded for session {session_id}"
            )
            return self._get_upload_progress(session)

        # Verify chunk size
        expected_size = session.chunk_size
        if chunk_number == session.total_chunks - 1:
            # Last chunk might be smaller
            expected_size = session.total_size - (chunk_number * session.chunk_size)

        if len(chunk_data) != expected_size:
            raise ValueError(
                f"Invalid chunk size. Expected {expected_size}, got {len(chunk_data)}"
            )

        # Verify checksum if provided
        if chunk_checksum:
            calculated_checksum = hashlib.sha256(chunk_data).hexdigest()
            if calculated_checksum != chunk_checksum:
                raise ValueError("Chunk checksum mismatch")

        # Store chunk in buffer
        self._chunk_buffers[session_id][chunk_number] = chunk_data
        session.uploaded_chunks.append(chunk_number)

        # Check if upload is complete
        if session.is_complete:
            # Assemble and store file
            await self._complete_chunked_upload(session)

        return self._get_upload_progress(session)

    async def _complete_chunked_upload(self, session: UploadSession) -> FileAttachment:
        """Complete a chunked upload by assembling and storing the file."""
        try:
            # Get chunks in order
            chunks = []
            for i in range(session.total_chunks):
                chunk_data = self._chunk_buffers[session.session_id].get(i)
                if not chunk_data:
                    raise ValueError(f"Missing chunk {i}")
                chunks.append(chunk_data)

            # Assemble file
            file_data = b"".join(chunks)

            # Calculate final checksum
            checksum = hashlib.sha256(file_data).hexdigest()

            # Store file
            attachment = self.storage_manager.store_file(
                file_data=BytesIO(file_data),
                filename=session.filename,
                category=session.category,
                patient_id=session.metadata.get("patient_id"),
                uploaded_by=(
                    session.metadata.get("uploaded_by")
                    if isinstance(session.metadata.get("uploaded_by"), UUID)
                    else None
                ),
                metadata={
                    **session.metadata,
                    "upload_completed_at": datetime.utcnow().isoformat(),
                    "upload_strategy": session.upload_strategy.value,
                },
            )

            # Update file record
            file_record = (
                self.session.query(FileAttachment)
                .filter(FileAttachment.file_id == session.file_id)
                .first()
            )

            if file_record:
                file_record.status = FileStatus.AVAILABLE
                file_record.checksum = checksum
                file_record.confirmed_at = datetime.utcnow()
                self.session.commit()

            # Clean up
            del self._chunk_buffers[session.session_id]
            del self._upload_sessions[session.session_id]

            logger.info(f"Completed chunked upload for session {session.session_id}")

            return attachment

        except Exception as e:
            logger.error(f"Error completing chunked upload: {e}")
            raise

    def _get_upload_progress(self, session: UploadSession) -> Dict[str, Any]:
        """Get current upload progress for a session."""
        return {
            "session_id": session.session_id,
            "file_id": session.file_id,
            "progress_percent": session.progress_percent,
            "uploaded_chunks": len(session.uploaded_chunks),
            "total_chunks": session.total_chunks,
            "remaining_chunks": session.remaining_chunks,
            "is_complete": session.is_complete,
            "expires_at": session.expires_at.isoformat(),
        }

    async def upload_file_stream(
        self,
        file_stream: AsyncGenerator[bytes, None],
        filename: str,
        category: FileCategory,
        estimated_size: Optional[int] = None,
        patient_id: Optional[UUID] = None,
        uploaded_by: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FileAttachment:
        """
        Upload a file from an async stream.

        Args:
            file_stream: Async generator yielding file chunks
            filename: Original filename
            category: File category
            estimated_size: Estimated file size (for progress tracking)
            patient_id: Associated patient
            uploaded_by: User uploading file
            metadata: Additional metadata

        Returns:
            Created file attachment
        """
        _ = estimated_size  # Mark as intentionally unused
        chunks = []
        total_size = 0
        hasher = hashlib.sha256()

        try:
            # Read chunks from stream
            async for chunk in file_stream:
                chunks.append(chunk)
                total_size += len(chunk)
                hasher.update(chunk)

                # Check size limit
                max_size = self.storage_manager.size_limits.get(
                    category, 25 * 1024 * 1024
                )
                if total_size > max_size:
                    raise ValueError(
                        f"File size {total_size} exceeds limit {max_size} "
                        f"for category {category}"
                    )

            # Assemble file
            file_data = b"".join(chunks)
            _ = hasher.hexdigest()

            # Store file
            attachment = self.storage_manager.store_file(
                file_data=BytesIO(file_data),
                filename=filename,
                category=category,
                patient_id=patient_id,
                uploaded_by=uploaded_by,
                metadata=metadata,
            )

            logger.info(
                f"Uploaded file from stream - "
                f"ID: {attachment.file_id}, Size: {total_size}"
            )

            return attachment

        except Exception as e:
            logger.error(f"Error uploading file stream: {e}")
            raise

    def resume_upload(
        self, session_id: str, from_chunk: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Resume an interrupted upload.

        Args:
            session_id: Upload session ID
            from_chunk: Resume from specific chunk (auto-detect if None)

        Returns:
            Resume information
        """
        session = self._upload_sessions.get(session_id)
        if not session:
            raise ValueError(f"Upload session {session_id} not found")

        # Check if session expired
        if datetime.utcnow() > session.expires_at:
            raise ValueError(f"Upload session {session_id} has expired")

        # Determine resume point
        if from_chunk is None:
            # Resume from next missing chunk
            remaining = session.remaining_chunks
            from_chunk = remaining[0] if remaining else session.total_chunks

        return {
            "session_id": session_id,
            "file_id": session.file_id,
            "resume_from_chunk": from_chunk,
            "uploaded_chunks": session.uploaded_chunks,
            "remaining_chunks": session.remaining_chunks,
            "chunk_size": session.chunk_size,
            "progress_percent": session.progress_percent,
            "expires_at": session.expires_at.isoformat(),
        }

    def cancel_upload(self, session_id: str) -> bool:
        """
        Cancel an upload session.

        Args:
            session_id: Upload session ID

        Returns:
            True if cancelled successfully
        """
        session = self._upload_sessions.get(session_id)
        if not session:
            return False

        # Clean up buffers
        if session_id in self._chunk_buffers:
            del self._chunk_buffers[session_id]

        # Remove session
        del self._upload_sessions[session_id]

        # Update file record if exists
        file_record = (
            self.session.query(FileAttachment)
            .filter(
                FileAttachment.file_id == session.file_id,
                FileAttachment.status == FileStatus.PENDING,
            )
            .first()
        )

        if file_record:
            self.session.delete(file_record)
            self.session.commit()

        logger.info(f"Cancelled upload session {session_id}")

        return True

    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired upload sessions.

        Returns:
            Number of sessions cleaned up
        """
        now = datetime.utcnow()
        expired_sessions = []

        for session_id, session in self._upload_sessions.items():
            if now > session.expires_at:
                expired_sessions.append(session_id)

        # Clean up expired sessions
        for session_id in expired_sessions:
            self.cancel_upload(session_id)

        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired upload sessions")

        return len(expired_sessions)

    def get_upload_statistics(
        self, user_id: Optional[UUID] = None, since: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get upload statistics.

        Args:
            user_id: Filter by user
            since: Filter uploads since this date

        Returns:
            Upload statistics
        """
        query = self.session.query(
            FileAttachment.category,
            func.count(FileAttachment.id).label("count"),
            func.sum(FileAttachment.size).label("total_size"),
            func.avg(FileAttachment.size).label("avg_size"),
        ).filter(FileAttachment.status == FileStatus.AVAILABLE)

        if user_id:
            query = query.filter(FileAttachment.uploaded_by == user_id)

        if since:
            query = query.filter(FileAttachment.created_at >= since)

        stats_by_category = query.group_by(FileAttachment.category).all()

        # Calculate totals
        total_files = sum(stat.count for stat in stats_by_category)
        total_size = sum(stat.total_size or 0 for stat in stats_by_category)

        # Get active sessions
        active_sessions = len(
            [
                s
                for s in self._upload_sessions.values()
                if datetime.utcnow() <= s.expires_at
            ]
        )

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2) if total_size else 0,
            "active_upload_sessions": active_sessions,
            "by_category": {
                stat.category.value: {
                    "count": stat.count,
                    "total_size": stat.total_size or 0,
                    "avg_size": round(stat.avg_size or 0),
                }
                for stat in stats_by_category
            },
        }
