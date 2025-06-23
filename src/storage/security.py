"""Security utilities for storage operations.

This module provides virus scanning and security validation for uploaded files.
"""

import asyncio
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from src.utils.logging import get_logger

logger = get_logger(__name__)


class ScanResult(Enum):
    """Virus scan result status."""

    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"
    SKIPPED = "skipped"


class VirusScanService:
    """Service for scanning files for viruses and malware."""

    def __init__(
        self,
        engine: str = "clamav",
        quarantine_path: Optional[Path] = None,
        max_file_size: int = 100 * 1024 * 1024,  # 100MB
        allowed_extensions: Optional[Set[str]] = None,
        scan_timeout: int = 60,
    ):
        """Initialize virus scan service.

        Args:
            engine: Scanning engine to use ("clamav", "defender", "dummy")
            quarantine_path: Path for quarantined files
            max_file_size: Maximum file size to scan (bytes)
            allowed_extensions: Set of allowed file extensions
            scan_timeout: Timeout for scan operations (seconds)
        """
        self.engine = engine
        self.quarantine_path = quarantine_path or Path(
            os.path.join(tempfile.gettempdir(), "quarantine")
        )
        self.max_file_size = max_file_size
        self.allowed_extensions = allowed_extensions or {
            ".pdf",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".txt",
            ".csv",
            ".json",
            ".xml",
            ".dicom",
        }
        self.scan_timeout = scan_timeout

        # Create quarantine directory if it doesn't exist
        self.quarantine_path.mkdir(parents=True, exist_ok=True)

        # Verify scanning engine is available
        self._verify_engine()

    def _verify_engine(self) -> None:
        """Verify the scanning engine is available."""
        if self.engine == "clamav":
            try:
                result = subprocess.run(
                    ["clamscan", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.returncode == 0:
                    logger.info(f"ClamAV available: {result.stdout.strip()}")
                else:
                    logger.warning(
                        "ClamAV not available, falling back to dummy scanner"
                    )
                    self.engine = "dummy"
            except (subprocess.TimeoutExpired, FileNotFoundError):
                logger.warning("ClamAV not found, falling back to dummy scanner")
                self.engine = "dummy"
        elif self.engine == "defender" and not self._is_windows():
            logger.warning("Windows Defender not available on non-Windows systems")
            self.engine = "dummy"

    def _is_windows(self) -> bool:
        """Check if running on Windows."""
        return platform.system().lower() == "windows"

    async def scan_file(self, file_path: Path) -> Dict[str, Any]:
        """Scan a file for viruses.

        Args:
            file_path: Path to file to scan

        Returns:
            Dictionary with scan results
        """
        result = {
            "status": ScanResult.CLEAN,
            "file_path": str(file_path),
            "file_size": 0,
            "threats": [],
            "scan_time": 0,
            "engine": self.engine,
        }

        try:
            # Check if file exists
            if not file_path.exists():
                result["status"] = ScanResult.ERROR
                result["error"] = "File not found"
                return result

            # Get file info
            file_size = file_path.stat().st_size
            result["file_size"] = file_size

            # Check file size
            if file_size > self.max_file_size:
                result["status"] = ScanResult.SKIPPED
                result["reason"] = f"File too large ({file_size} bytes)"
                logger.warning(f"Skipping scan for large file: {file_path}")
                return result

            # Check file extension
            if (
                self.allowed_extensions
                and file_path.suffix.lower() not in self.allowed_extensions
            ):
                result["status"] = ScanResult.ERROR
                result["error"] = f"File type not allowed: {file_path.suffix}"
                return result

            # Perform scan based on engine
            if self.engine == "clamav":
                return await self._scan_with_clamav(file_path, result)
            elif self.engine == "defender":
                return await self._scan_with_defender(file_path, result)
            else:
                return await self._scan_with_dummy(file_path, result)

        except OSError as e:
            logger.error(f"Error scanning file {file_path}: {e}")
            result["status"] = ScanResult.ERROR
            result["error"] = str(e)
            return result

    async def _scan_with_clamav(
        self, file_path: Path, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Scan file using ClamAV.

        Args:
            file_path: Path to file
            result: Result dictionary to update

        Returns:
            Updated result dictionary
        """
        start_time = time.time()

        try:
            # Run clamscan
            process = await asyncio.create_subprocess_exec(
                "clamscan",
                "--no-summary",
                "--infected",
                str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait for scan with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.scan_timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                result["status"] = ScanResult.ERROR
                result["error"] = "Scan timeout"
                return result

            result["scan_time"] = time.time() - start_time

            # Parse results
            if process.returncode == 0:
                result["status"] = ScanResult.CLEAN
            elif process.returncode == 1:
                # Virus found
                result["status"] = ScanResult.INFECTED
                output = stdout.decode().strip()
                if output:
                    # Extract threat name from output
                    lines = output.split("\n")
                    for line in lines:
                        if "FOUND" in line:
                            threat_name = line.split(":")[1].strip()
                            result["threats"].append(threat_name)

                # Quarantine the file
                await self._quarantine_file(file_path)
            else:
                result["status"] = ScanResult.ERROR
                result["error"] = stderr.decode().strip()

        except (subprocess.CalledProcessError, OSError) as e:
            result["status"] = ScanResult.ERROR
            result["error"] = str(e)

        return result

    async def _scan_with_defender(
        self, file_path: Path, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Scan file using Windows Defender (placeholder).

        Args:
            file_path: Path to file
            result: Result dictionary to update

        Returns:
            Updated result dictionary
        """
        # Windows Defender integration would go here
        # For now, use dummy scan
        return await self._scan_with_dummy(file_path, result)

    async def _scan_with_dummy(
        self, file_path: Path, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform dummy scan for testing/development.

        Args:
            file_path: Path to file
            result: Result dictionary to update

        Returns:
            Updated result dictionary
        """
        start_time = time.time()

        # Read file content for basic checks
        try:
            with open(file_path, "rb") as f:
                # Read first 1KB for header checks
                header = f.read(1024)

            # Check for EICAR test signature
            if (
                b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
                in header
            ):
                result["status"] = ScanResult.INFECTED
                result["threats"].append("EICAR-Test-File")
                await self._quarantine_file(file_path)
            else:
                # Basic pattern matching
                suspicious_patterns = [
                    (b"MZ", "Potential executable"),
                    (b"\x7fELF", "Potential ELF executable"),
                    (b"<script", "Potential script injection"),
                    (b"eval(", "Potential code execution"),
                ]

                for pattern, threat_name in suspicious_patterns:
                    if pattern in header:
                        logger.warning(
                            f"Suspicious pattern found in {file_path}: {threat_name}"
                        )
                        # Don't mark as infected in dummy mode, just log

            result["scan_time"] = time.time() - start_time

        except OSError as e:
            result["status"] = ScanResult.ERROR
            result["error"] = str(e)

        return result

    async def _quarantine_file(self, file_path: Path) -> Path:
        """Move infected file to quarantine.

        Args:
            file_path: Path to infected file

        Returns:
            Path to quarantined file
        """
        # Create quarantine filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        file_hash = hashlib.sha256(str(file_path).encode()).hexdigest()[:8]
        quarantine_name = f"{timestamp}_{file_hash}_{file_path.name}"
        quarantine_path = self.quarantine_path / quarantine_name

        try:
            # Move file to quarantine
            shutil.move(str(file_path), str(quarantine_path))
            logger.warning(f"File quarantined: {file_path} -> {quarantine_path}")

            # Create metadata file
            metadata_path = quarantine_path.with_suffix(".metadata.json")
            metadata = {
                "original_path": str(file_path),
                "quarantine_time": datetime.utcnow().isoformat(),
                "file_hash": file_hash,
                "reason": "Virus detected",
            }

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            return quarantine_path

        except (OSError, TypeError, ValueError) as e:
            logger.error(f"Failed to quarantine file {file_path}: {e}")
            # If quarantine fails, delete the file for safety
            try:
                file_path.unlink()
                logger.warning(f"Infected file deleted: {file_path}")
            except (
                OSError,
                TypeError,
                ValueError,
            ) as del_err:
                logger.error(f"Failed to delete infected file: {del_err}")
            raise

    async def scan_data(self, data: bytes, filename: str = "data") -> Dict[str, Any]:
        """Scan data bytes for viruses.

        Args:
            data: Data to scan
            filename: Filename for the data

        Returns:
            Scan results
        """
        # Create temporary file
        with tempfile.NamedTemporaryFile(
            delete=False, prefix=f"scan_{filename}_"
        ) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)

        try:
            # Scan the temporary file
            result = await self.scan_file(tmp_path)
            return result
        finally:
            # Clean up temporary file if not quarantined
            if tmp_path.exists():
                tmp_path.unlink()

    async def batch_scan(
        self, directory: Path, recursive: bool = True
    ) -> List[Dict[str, Any]]:
        """Scan all files in a directory.

        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories

        Returns:
            List of scan results
        """
        results = []

        if recursive:
            pattern = "**/*"
        else:
            pattern = "*"

        # Get all files
        files = [f for f in directory.glob(pattern) if f.is_file()]

        logger.info(f"Scanning {len(files)} files in {directory}")

        # Scan files with concurrency limit
        semaphore = asyncio.Semaphore(5)  # Limit concurrent scans

        async def scan_with_limit(file_path: Path) -> Dict[str, Any]:
            async with semaphore:
                return await self.scan_file(file_path)

        # Scan all files
        results = await asyncio.gather(
            *[scan_with_limit(f) for f in files], return_exceptions=True
        )

        # Process results
        processed_results: List[Dict[str, Any]] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    {
                        "status": ScanResult.ERROR,
                        "file_path": str(files[i]),
                        "error": str(result),
                    }
                )
            else:
                if isinstance(result, dict):
                    processed_results.append(result)

        # Log summary
        infected_count = sum(
            1 for r in processed_results if r["status"] == ScanResult.INFECTED
        )
        error_count = sum(
            1 for r in processed_results if r["status"] == ScanResult.ERROR
        )

        logger.info(
            f"Batch scan complete: {len(files)} files scanned, "
            f"{infected_count} infected, {error_count} errors"
        )

        return processed_results

    def validate_file_type(self, file_path: Path) -> bool:
        """Validate file type is allowed.

        Args:
            file_path: Path to file

        Returns:
            True if file type is allowed
        """
        return file_path.suffix.lower() in self.allowed_extensions

    def get_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file.

        Args:
            file_path: Path to file

        Returns:
            Hex digest of file hash
        """
        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()
