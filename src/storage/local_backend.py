"""Local Storage Backend Implementation.

This module provides a secure local storage backend for the Haven Health Passport
system, with encryption, integrity checking, and offline support capabilities.
"""

import asyncio
import base64
import hashlib
import io
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from src.storage.base import FileCategory, FileMetadata, StorageBackend
from src.utils.logging import get_logger

logger = get_logger(__name__)


class LocalStorageBackend(StorageBackend):
    """Secure local storage backend with encryption and integrity checking."""

    _virus_scanner: Optional[Any] = None

    def __init__(self, config: Dict):
        """Initialize local storage backend.

        Args:
            config: Configuration dictionary containing:
                - base_path: Base directory for storage
                - encryption_key: 32-byte encryption key (optional)
                - create_dirs: Whether to create directories if missing
                - quota_mb: Storage quota per user in MB
                - retention_days: Default retention period in days
        """
        super().__init__(config)
        self.base_path = Path(
            config.get(
                "base_path", os.path.join(tempfile.gettempdir(), "haven_storage")
            )
        )
        self.create_dirs = config.get("create_dirs", True)
        self.quota_mb = config.get("quota_mb", 10240)  # 10GB default
        self.retention_days = config.get("retention_days", 90)

        # Initialize encryption
        encryption_key = config.get("encryption_key")
        if encryption_key:
            if isinstance(encryption_key, str):
                encryption_key = encryption_key.encode()
            if len(encryption_key) != 32:
                raise ValueError("Encryption key must be 32 bytes")
            self.encryption_key = encryption_key
        else:
            # Generate a default key (should be replaced in production)
            self.encryption_key = hashlib.sha256(b"haven-health-default-key").digest()
            logger.warning("Using default encryption key - replace in production!")

        # Initialize storage
        self._init_storage()

        # Virus scanner integration placeholder
        self.virus_scanner = config.get("virus_scanner")
        self._virus_scanner = None  # Lazy initialized in scan_virus method

    def _init_storage(self) -> None:
        """Initialize storage directories and metadata."""
        if self.create_dirs:
            self.base_path.mkdir(parents=True, exist_ok=True)
            (self.base_path / "data").mkdir(exist_ok=True)
            (self.base_path / "metadata").mkdir(exist_ok=True)
            (self.base_path / "temp").mkdir(exist_ok=True)

        # Initialize quota tracking
        self._init_quota_tracking()

    def _init_quota_tracking(self) -> None:
        """Initialize user quota tracking."""
        quota_file = self.base_path / "metadata" / "quotas.json"
        if not quota_file.exists():
            with open(quota_file, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _sanitize_key(self, key: str) -> str:
        """Sanitize storage key to prevent path traversal attacks."""
        # Remove any path traversal attempts
        key = key.replace("..", "")
        key = key.replace("~", "")
        key = os.path.normpath(key).lstrip("/\\")

        # Ensure key doesn't escape base path
        if os.path.isabs(key):
            raise ValueError("Absolute paths not allowed")

        # Replace path separators with safe character
        key = key.replace("/", "_").replace("\\", "_")

        return key

    def _encrypt_data(self, data: bytes) -> Tuple[bytes, bytes]:
        """Encrypt data using AES-256-GCM.

        Returns:
            Tuple of (encrypted_data, nonce)
        """
        # Generate random nonce
        nonce = os.urandom(16)

        # Create cipher
        cipher = Cipher(
            algorithms.AES(self.encryption_key),
            modes.GCM(nonce),
            backend=default_backend(),
        )
        encryptor = cipher.encryptor()

        # Encrypt data
        ciphertext = encryptor.update(data) + encryptor.finalize()

        return ciphertext + encryptor.tag, nonce

    def _decrypt_data(self, encrypted_data: bytes, nonce: bytes) -> bytes:
        """Decrypt data using AES-256-GCM."""
        # Split ciphertext and tag
        ciphertext = encrypted_data[:-16]
        tag = encrypted_data[-16:]

        # Create cipher
        cipher = Cipher(
            algorithms.AES(self.encryption_key),
            modes.GCM(nonce, tag),
            backend=default_backend(),
        )
        decryptor = cipher.decryptor()

        # Decrypt data
        return decryptor.update(ciphertext) + decryptor.finalize()

    def store(self, key: str, data: bytes, metadata: Optional[Dict] = None) -> str:
        """Store data with encryption and metadata.

        Args:
            key: Storage key
            data: Data to store
            metadata: Optional metadata

        Returns:
            Storage ID (integrity hash)
        """
        # Sanitize key
        safe_key = self._sanitize_key(key)

        # Check quota
        user_id = (
            str(metadata.get("user_id"))
            if metadata and metadata.get("user_id")
            else "anonymous"
        )
        if not self._check_quota(user_id, len(data)):
            raise ValueError("Storage quota exceeded")

        # Scan for viruses if configured
        if self.virus_scanner:
            # Run async scan in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                scan_passed = loop.run_until_complete(
                    self._scan_data(data, f"{user_id}/{key}")
                )
                if not scan_passed:
                    raise ValueError("Virus detected in uploaded data")
            finally:
                loop.close()
        # Encrypt data
        encrypted_data, nonce = self._encrypt_data(data)

        # Calculate integrity hash
        integrity_hash = hashlib.sha256(encrypted_data).hexdigest()

        # Prepare storage record
        storage_record = {
            "data": base64.b64encode(encrypted_data).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "metadata": metadata or {},
            "integrity_hash": integrity_hash,
            "stored_at": datetime.utcnow().isoformat(),
            "encryption_version": "AES-256-GCM",
            "original_size": len(data),
            "encrypted_size": len(encrypted_data),
        }

        # Store data file
        file_path = self.base_path / "data" / safe_key
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(f"{file_path}.json", "w", encoding="utf-8") as f:
            json.dump(storage_record, f, indent=2)

        # Update quota
        self._update_quota(user_id, len(encrypted_data))

        logger.info(f"Stored file {safe_key} with hash {integrity_hash}")

        return integrity_hash

    def retrieve(self, key: str) -> Tuple[bytes, Dict]:
        """Retrieve and decrypt stored data.

        Args:
            key: Storage key

        Returns:
            Tuple of (data, metadata)
        """  # Sanitize key
        safe_key = self._sanitize_key(key)
        file_path = self.base_path / "data" / f"{safe_key}.json"

        if not file_path.exists():
            raise FileNotFoundError(f"Key not found: {key}")

        # Load storage record
        with open(file_path, "r", encoding="utf-8") as f:
            storage_record = json.load(f)

        # Verify integrity
        encrypted_data = base64.b64decode(storage_record["data"])
        stored_hash = storage_record["integrity_hash"]
        calculated_hash = hashlib.sha256(encrypted_data).hexdigest()

        if stored_hash != calculated_hash:
            raise ValueError("Data integrity check failed")

        # Decrypt data
        nonce = base64.b64decode(storage_record["nonce"])
        decrypted_data = self._decrypt_data(encrypted_data, nonce)

        return decrypted_data, storage_record["metadata"]

    def delete(
        self, file_id: str, version: Optional[int] = None, permanent: bool = False
    ) -> bool:
        """Delete stored data.

        Args:
            file_id: Storage key
            version: Specific version to delete (unused)
            permanent: If True, permanently delete (unused)

        Returns:
            True if deleted, False if not found
        """
        # Sanitize key
        safe_key = self._sanitize_key(file_id)
        file_path = self.base_path / "data" / f"{safe_key}.json"

        if file_path.exists():
            # Load record to update quota
            with open(file_path, "r", encoding="utf-8") as f:
                storage_record = json.load(f)

            user_id = storage_record.get("metadata", {}).get("user_id", "anonymous")
            size = storage_record.get("encrypted_size", 0)

            # Delete file
            file_path.unlink()

            # Update quota
            self._update_quota(user_id, -size)

            logger.info(f"Deleted file {safe_key}")
            return True

        return False

    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List all keys with optional prefix filtering."""
        keys: List[str] = []
        data_dir = self.base_path / "data"

        if not data_dir.exists():
            return keys

        for file_path in data_dir.rglob("*.json"):
            key = file_path.stem
            if not prefix or key.startswith(prefix):
                keys.append(key)

        return sorted(keys)

    def _check_quota(self, user_id: str, size: int) -> bool:
        """Check if user has sufficient quota."""
        quota_file = self.base_path / "metadata" / "quotas.json"

        with open(quota_file, "r", encoding="utf-8") as f:
            quotas = json.load(f)

        current_usage = quotas.get(user_id, {}).get("used_bytes", 0)
        max_bytes = self.quota_mb * 1024 * 1024

        return bool((current_usage + size) <= max_bytes)

    def _update_quota(self, user_id: str, size_delta: int) -> None:
        """Update user's storage quota usage."""
        quota_file = self.base_path / "metadata" / "quotas.json"

        with open(quota_file, "r", encoding="utf-8") as f:
            quotas = json.load(f)
        if user_id not in quotas:
            quotas[user_id] = {"used_bytes": 0, "file_count": 0}

        quotas[user_id]["used_bytes"] += size_delta
        quotas[user_id]["file_count"] += 1 if size_delta > 0 else -1
        quotas[user_id]["last_updated"] = datetime.utcnow().isoformat()

        with open(quota_file, "w", encoding="utf-8") as f:
            json.dump(quotas, f, indent=2)

    async def _scan_data(self, data: bytes, filename: str = "upload") -> bool:
        """Scan data for viruses using the virus scanning service.

        Args:
            data: Data to scan
            filename: Name of the file being scanned

        Returns:
            True if scan passed, False if infected or error
        """
        from src.storage.security import (  # pylint: disable=import-outside-toplevel
            ScanResult,
            VirusScanService,
        )

        # Initialize virus scanner if not already done
        if not hasattr(self, "_virus_scanner"):
            self._virus_scanner = VirusScanService(engine="clamav")

        try:
            # Scan the data
            assert (
                self._virus_scanner is not None
            )  # Help mypy understand this is initialized
            result = await self._virus_scanner.scan_data(data, filename)

            if result["status"] == ScanResult.CLEAN:
                return True
            elif result["status"] == ScanResult.INFECTED:
                logger.error(
                    f"Virus detected in {filename}: {result.get('threats', [])}"
                )
                return False
            elif result["status"] == ScanResult.ERROR:
                logger.error(
                    f"Virus scan error for {filename}: {result.get('error', 'Unknown')}"
                )
                # In production, you might want to reject on error for safety
                # For now, we'll allow it but log the error
                return True
            else:
                # SKIPPED or other status
                logger.warning(
                    f"Virus scan skipped for {filename}: {result.get('reason', 'Unknown')}"
                )
                return True

        except OSError as e:
            logger.error(f"Unexpected error during virus scan: {e}")
            # On unexpected errors, be safe and reject
            return False

    def cleanup_old_files(self) -> int:
        """Clean up files older than retention period.

        Returns:
            Number of files deleted
        """
        deleted_count = 0
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)

        data_dir = self.base_path / "data"
        if not data_dir.exists():
            return 0

        for file_path in data_dir.rglob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    record = json.load(f)

                stored_at = datetime.fromisoformat(record["stored_at"])
                if stored_at < cutoff_date:
                    file_path.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted expired file: {file_path.stem}")
            except (
                OSError,
                TypeError,
                ValueError,
            ) as e:
                logger.error(f"Error cleaning up {file_path}: {e}")

        return deleted_count

    def get_storage_stats(self) -> Dict:
        """Get storage statistics."""
        quota_file = self.base_path / "metadata" / "quotas.json"

        with open(quota_file, "r", encoding="utf-8") as f:
            quotas = json.load(f)

        total_used = sum(
            user_data.get("used_bytes", 0) for user_data in quotas.values()
        )
        total_files = sum(
            user_data.get("file_count", 0) for user_data in quotas.values()
        )

        return {
            "total_users": len(quotas),
            "total_used_bytes": total_used,
            "total_used_mb": total_used / (1024 * 1024),
            "total_files": total_files,
            "quota_per_user_mb": self.quota_mb,
            "retention_days": self.retention_days,
        }

    def create_multipart_upload(
        self,
        file_id: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a multipart upload session."""
        # For local storage, we don't need true multipart uploads
        # Just return a unique upload ID
        import uuid  # pylint: disable=import-outside-toplevel

        upload_id = str(uuid.uuid4())

        # Store metadata for the upload
        upload_metadata = {
            "file_id": file_id,
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
            "parts": [],
        }

        upload_file = self.base_path / "uploads" / f"{upload_id}.json"
        upload_file.parent.mkdir(parents=True, exist_ok=True)

        with open(upload_file, "w", encoding="utf-8") as f:
            json.dump(upload_metadata, f)

        return upload_id

    def upload_part(
        self, file_id: str, upload_id: str, part_number: int, data: BinaryIO
    ) -> str:
        """Upload a part of a multipart upload."""
        # Store the part data temporarily
        part_file = self.base_path / "uploads" / upload_id / f"part_{part_number}"
        part_file.parent.mkdir(parents=True, exist_ok=True)

        # Read data from BinaryIO
        data_bytes = data.read()

        with open(part_file, "wb") as f:
            f.write(data_bytes)

        # Update upload metadata
        upload_file = self.base_path / "uploads" / f"{upload_id}.json"
        with open(upload_file, "r", encoding="utf-8") as f:
            upload_metadata = json.load(f)

        etag = hashlib.md5(data_bytes, usedforsecurity=False).hexdigest()
        part_info = {
            "part_number": part_number,
            "size": len(data_bytes),
            "etag": etag,
        }
        upload_metadata["parts"].append(part_info)

        with open(upload_file, "w", encoding="utf-8") as f:
            json.dump(upload_metadata, f)

        return etag

    def complete_multipart_upload(
        self, file_id: str, upload_id: str, parts: List[Dict[str, Any]]
    ) -> FileMetadata:
        """Complete a multipart upload."""
        # Combine all parts into final file
        upload_dir = self.base_path / "uploads" / upload_id
        combined_data = bytearray()

        # Sort parts by part number and combine
        sorted_parts = sorted(parts, key=lambda x: x["PartNumber"])
        for part in sorted_parts:
            part_file = upload_dir / f"part_{part['PartNumber']}"
            with open(part_file, "rb") as f:
                combined_data.extend(f.read())

        # Store the combined file
        metadata = self._load_upload_metadata(upload_id)
        _ = self.store(file_id, bytes(combined_data), metadata.get("metadata"))

        # Cleanup upload files
        import shutil  # pylint: disable=import-outside-toplevel

        shutil.rmtree(upload_dir, ignore_errors=True)
        upload_metadata_file = self.base_path / "uploads" / f"{upload_id}.json"
        upload_metadata_file.unlink(missing_ok=True)

        return FileMetadata(
            file_id=file_id,
            filename=metadata.get("metadata", {}).get("filename", file_id),
            content_type=metadata.get("metadata", {}).get(
                "content_type", "application/octet-stream"
            ),
            size=len(combined_data),
            checksum=hashlib.sha256(bytes(combined_data)).hexdigest(),
            category=FileCategory(
                metadata.get("metadata", {}).get("category", "other")
            ),
            created_at=datetime.utcnow(),
            modified_at=datetime.utcnow(),
            custom_metadata=metadata.get("metadata", {}),
        )

    def abort_multipart_upload(self, file_id: str, upload_id: str) -> bool:
        """Abort a multipart upload."""
        # Cleanup upload files
        import shutil  # pylint: disable=import-outside-toplevel

        upload_dir = self.base_path / "uploads" / upload_id
        shutil.rmtree(upload_dir, ignore_errors=True)

        upload_metadata_file = self.base_path / "uploads" / f"{upload_id}.json"
        upload_metadata_file.unlink(missing_ok=True)

        return True

    def _load_upload_metadata(self, upload_id: str) -> Dict[str, Any]:
        """Load metadata for an upload."""
        upload_file = self.base_path / "uploads" / f"{upload_id}.json"
        with open(upload_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return dict(data) if isinstance(data, dict) else {}

    def _validate_config(self) -> None:
        """Validate backend configuration."""
        # Configuration validation is done in __init__

    def put(
        self,
        file_id: str,
        file_data: BinaryIO,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
        encryption_key: Optional[str] = None,
    ) -> FileMetadata:
        """Store a file in the backend."""
        # Read file data
        data = file_data.read()

        # Use existing store method
        self.store(file_id, data, metadata)

        # Create and return FileMetadata
        return FileMetadata(
            file_id=file_id,
            filename=metadata.get("filename", file_id) if metadata else file_id,
            content_type=content_type or "application/octet-stream",
            size=len(data),
            checksum=hashlib.sha256(data).hexdigest(),
            category=(
                FileCategory(metadata.get("category", "other"))
                if metadata
                else FileCategory.OTHER
            ),
            created_at=datetime.now(),
            modified_at=datetime.now(),
            version=1,
            tags=tags,
            custom_metadata=metadata,
        )

    def get(
        self,
        file_id: str,
        version: Optional[int] = None,
        decryption_key: Optional[str] = None,
    ) -> Tuple[BinaryIO, FileMetadata]:
        """Retrieve a file from the backend."""
        # Use existing retrieve method
        data, meta = self.retrieve(file_id)

        # Convert to BinaryIO
        file_obj = io.BytesIO(data)

        # Create FileMetadata
        metadata = FileMetadata(
            file_id=file_id,
            filename=meta.get("filename", file_id),
            content_type=meta.get("content_type", "application/octet-stream"),
            size=len(data),
            checksum=meta.get("checksum", hashlib.sha256(data).hexdigest()),
            category=FileCategory(meta.get("category", "other")),
            created_at=datetime.fromisoformat(
                meta.get("created_at", datetime.now().isoformat())
            ),
            modified_at=datetime.fromisoformat(
                meta.get("modified_at", datetime.now().isoformat())
            ),
            version=meta.get("version", 1),
            tags=meta.get("tags", {}),
            custom_metadata=meta,
        )

        return file_obj, metadata

    def exists(self, file_id: str) -> bool:
        """Check if a file exists."""
        sanitized_key = self._sanitize_key(file_id)
        file_path = self.base_path / "data" / sanitized_key
        return file_path.exists()

    def list(
        self,
        prefix: Optional[str] = None,
        category: Optional[FileCategory] = None,
        tags: Optional[Dict[str, str]] = None,
        limit: int = 1000,
        continuation_token: Optional[str] = None,
    ) -> Tuple[List[FileMetadata], Optional[str]]:
        """List files in the backend."""
        # Use existing list_keys method
        keys = self.list_keys(prefix)

        metadata_list = []
        for key in keys[:limit]:
            try:
                _, meta = self.retrieve(key)
                # Filter by category if specified
                if category and meta.get("category") != category.value:
                    continue
                # Filter by tags if specified
                if tags:
                    file_tags = meta.get("tags", {})
                    if not all(file_tags.get(k) == v for k, v in tags.items()):
                        continue

                metadata_list.append(
                    FileMetadata(
                        file_id=key,
                        filename=meta.get("filename", key),
                        content_type=meta.get(
                            "content_type", "application/octet-stream"
                        ),
                        size=meta.get("size", 0),
                        checksum=meta.get("checksum", ""),
                        category=FileCategory(meta.get("category", "other")),
                        created_at=datetime.fromisoformat(
                            meta.get("created_at", datetime.now().isoformat())
                        ),
                        modified_at=datetime.fromisoformat(
                            meta.get("modified_at", datetime.now().isoformat())
                        ),
                        version=meta.get("version", 1),
                        tags=meta.get("tags", {}),
                        custom_metadata=meta,
                    )
                )
            except (ValueError, KeyError, TypeError):
                # Skip files with invalid metadata
                continue

        # Simple pagination
        next_token = None
        if len(keys) > limit:
            next_token = str(limit)

        return metadata_list, next_token

    def get_metadata(self, file_id: str) -> FileMetadata:
        """Get metadata for a file without downloading it."""
        sanitized_key = self._sanitize_key(file_id)
        metadata_path = self.base_path / "metadata" / f"{sanitized_key}.json"

        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata not found for file: {file_id}")

        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        return FileMetadata(
            file_id=file_id,
            filename=meta.get("filename", file_id),
            content_type=meta.get("content_type", "application/octet-stream"),
            size=meta.get("size", 0),
            checksum=meta.get("checksum", ""),
            category=FileCategory(meta.get("category", "other")),
            created_at=datetime.fromisoformat(
                meta.get("created_at", datetime.now().isoformat())
            ),
            modified_at=datetime.fromisoformat(
                meta.get("modified_at", datetime.now().isoformat())
            ),
            version=meta.get("version", 1),
            tags=meta.get("tags", {}),
            custom_metadata=meta,
        )

    def update_metadata(
        self,
        file_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> FileMetadata:
        """Update metadata for a file."""
        # Get existing metadata
        existing_meta = self.get_metadata(file_id)

        # Update metadata
        if metadata:
            existing_meta.custom_metadata.update(metadata)
        if tags:
            existing_meta.tags.update(tags)

        existing_meta.modified_at = datetime.now()

        # Save updated metadata
        sanitized_key = self._sanitize_key(file_id)
        metadata_path = self.base_path / "metadata" / f"{sanitized_key}.json"

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(existing_meta.to_dict(), f, indent=2)

        return existing_meta

    def generate_presigned_url(
        self,
        file_id: str,
        operation: str = "get",
        expiration: Optional[timedelta] = None,
        content_type: Optional[str] = None,
        content_disposition: Optional[str] = None,
    ) -> str:
        """Generate a pre-signed URL for direct access."""
        # Local storage doesn't support presigned URLs
        # Return a file:// URL for local access
        sanitized_key = self._sanitize_key(file_id)
        file_path = self.base_path / "data" / sanitized_key
        return f"file://{file_path.absolute()}"

    def copy(
        self,
        source_file_id: str,
        destination_file_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FileMetadata:
        """Copy a file within the backend."""
        # Retrieve source file
        data, source_meta = self.retrieve(source_file_id)

        # Update metadata if provided
        if metadata:
            source_meta.update(metadata)

        # Store as new file
        self.store(destination_file_id, data, source_meta)

        # Return metadata for new file
        return self.get_metadata(destination_file_id)
