"""Virus scanning service for file safety validation.

This service provides integration with virus scanning solutions like
ClamAV, AWS Macie, or third-party APIs for malware detection.
"""

import asyncio
import math
import mimetypes
from datetime import datetime
from typing import Any, Dict, Optional

import aiohttp

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class VirusScanService:
    """Service for scanning files for viruses and malware."""

    def __init__(self) -> None:
        """Initialize virus scan service."""
        self.scan_endpoint = settings.virus_scan_endpoint
        self.scan_api_key = settings.virus_scan_api_key
        self.scan_timeout = 300  # 5 minutes timeout
        self.max_file_size = 100 * 1024 * 1024  # 100MB max for scanning

        # Initialize local ClamAV if available
        self.clamav_available = self._check_clamav()

    def _check_clamav(self) -> bool:
        """Check if ClamAV is available locally."""
        try:
            import pyclamd  # pylint: disable=import-outside-toplevel

            self.clamav = pyclamd.ClamdUnixSocket()
            result: bool = self.clamav.ping()
            return result
        except (ImportError, AttributeError, ConnectionError) as e:
            logger.info(f"ClamAV not available: {e}, using cloud scanning")
            return False

    async def scan_file(
        self, file_content: bytes, file_hash: str, filename: str
    ) -> Dict[str, Any]:
        """Scan file for viruses and malware."""
        try:
            # Check file size
            if len(file_content) > self.max_file_size:
                return {
                    "scanned": False,
                    "infected": False,
                    "error": "File too large for scanning",
                    "timestamp": datetime.utcnow().isoformat(),
                }

            # Try local ClamAV first if available
            if self.clamav_available:
                result = await self._scan_with_clamav(file_content, filename)
                if result:
                    return result

            # Use cloud scanning service
            if self.scan_endpoint:
                return await self._scan_with_cloud(file_content, file_hash, filename)

            # If no scanning available, perform basic checks
            return await self._basic_scan(file_content, filename)

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error scanning file {filename}: {e}")
            return {
                "scanned": False,
                "infected": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _scan_with_clamav(
        self, file_content: bytes, filename: str
    ) -> Optional[Dict[str, Any]]:
        """Scan file using local ClamAV."""
        try:
            # Use filename for logging
            logger.debug(f"Scanning file with ClamAV: {filename}")

            # Run scan in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self.clamav.scan_stream, file_content
            )

            if result is None:
                # File is clean
                return {
                    "scanned": True,
                    "infected": False,
                    "scanner": "ClamAV",
                    "threats": [],
                    "timestamp": datetime.utcnow().isoformat(),
                }
            else:
                # Threat detected
                threats = []
                for _file_path, (status, threat) in result.items():
                    if status == "FOUND":
                        threats.append(threat)

                return {
                    "scanned": True,
                    "infected": True,
                    "scanner": "ClamAV",
                    "threats": threats,
                    "timestamp": datetime.utcnow().isoformat(),
                }

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"ClamAV scan error: {e}")
            return None

    async def _scan_with_cloud(
        self, file_content: bytes, file_hash: str, filename: str
    ) -> Dict[str, Any]:
        """Scan file using cloud scanning service."""
        try:
            async with aiohttp.ClientSession() as session:
                # Prepare multipart form data
                data = aiohttp.FormData()
                data.add_field(
                    "file",
                    file_content,
                    filename=filename,
                    content_type="application/octet-stream",
                )
                data.add_field("hash", file_hash)

                headers = {"Authorization": f"Bearer {self.scan_api_key}"}

                if not self.scan_endpoint:
                    return {
                        "scanned": False,
                        "infected": False,
                        "error": "No scan endpoint configured",
                        "timestamp": datetime.utcnow().isoformat(),
                    }

                async with session.post(
                    self.scan_endpoint,
                    data=data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.scan_timeout),
                ) as response:
                    if response.status == 200:
                        result = await response.json()

                        return {
                            "scanned": True,
                            "infected": result.get("infected", False),
                            "scanner": result.get("scanner", "Cloud Scanner"),
                            "threats": result.get("threats", []),
                            "confidence": result.get("confidence", 1.0),
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Cloud scan error: {response.status} - {error_text}"
                        )
                        return {
                            "scanned": False,
                            "infected": False,
                            "error": f"Scan service error: {response.status}",
                            "timestamp": datetime.utcnow().isoformat(),
                        }

        except asyncio.TimeoutError:
            logger.error("Cloud scan timeout")
            return {
                "scanned": False,
                "infected": False,
                "error": "Scan timeout",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Cloud scan error: {e}")
            return {
                "scanned": False,
                "infected": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _basic_scan(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Perform basic file safety checks."""
        threats = []

        # Check for known malware signatures (simplified)
        malware_signatures = [
            b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE",  # EICAR test string
            b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR",  # EICAR signature
            # Add more known signatures
        ]

        for signature in malware_signatures:
            if signature in file_content:
                threats.append(
                    f"Known malware signature: {signature.decode('utf-8', errors='ignore')[:20]}..."
                )

        # Check for suspicious patterns
        suspicious_patterns = [
            b"<script",  # JavaScript in non-HTML files
            b"eval(",  # Eval functions
            b"exec(",  # Exec functions
            b"system(",  # System calls
            b"<?php",  # PHP code in unexpected files
        ]

        # Only check patterns for certain file types
        if not filename.lower().endswith((".html", ".htm", ".js", ".php")):
            for pattern in suspicious_patterns:
                if pattern in file_content.lower():
                    threats.append(
                        f"Suspicious pattern detected: {pattern.decode('utf-8')}"
                    )

        # Check for executable headers
        executable_headers = [
            b"MZ",  # DOS/Windows executable
            b"\x7fELF",  # Linux ELF
            b"\xfe\xed\xfa\xce",  # Mach-O (macOS)
            b"\xce\xfa\xed\xfe",  # Mach-O (macOS)
        ]

        for header in executable_headers:
            if file_content.startswith(header):
                if not filename.lower().endswith((".exe", ".dll", ".so", ".dylib")):
                    threats.append("Executable file with misleading extension")

        return {
            "scanned": True,
            "infected": len(threats) > 0,
            "scanner": "Basic Scanner",
            "threats": threats,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def scan_url(self, url: str) -> Dict[str, Any]:
        """Scan a URL for malicious content."""
        try:
            # Use URL scanning service (e.g., Google Safe Browsing, VirusTotal)
            if hasattr(settings, "url_scan_endpoint") and settings.url_scan_endpoint:
                async with aiohttp.ClientSession() as session:
                    headers = {"Authorization": f"Bearer {self.scan_api_key}"}

                    payload = {"url": url}

                    async with session.post(
                        settings.url_scan_endpoint,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            return {
                                "scanned": True,
                                "malicious": result.get("malicious", False),
                                "threats": result.get("threats", []),
                                "categories": result.get("categories", []),
                                "timestamp": datetime.utcnow().isoformat(),
                            }

            # Basic URL validation
            threats = []

            # Check for suspicious patterns
            suspicious_patterns = [
                "bit.ly",
                "tinyurl.com",
                "goo.gl",  # URL shorteners
                "javascript:",
                "data:",
                "vbscript:",  # Script protocols
            ]

            for pattern in suspicious_patterns:
                if pattern in url.lower():
                    threats.append(f"Suspicious URL pattern: {pattern}")

            return {
                "scanned": True,
                "malicious": len(threats) > 0,
                "threats": threats,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error scanning URL {url}: {e}")
            return {
                "scanned": False,
                "malicious": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def get_file_risk_score(
        self, file_content: bytes, filename: str, content_type: str
    ) -> float:
        """Calculate risk score for a file (0.0 - 1.0)."""
        risk_score = 0.0

        # File extension vs content type mismatch
        expected_type = mimetypes.guess_type(filename)[0]
        if expected_type and expected_type != content_type:
            risk_score += 0.2

        # Executable files
        executable_extensions = [
            ".exe",
            ".dll",
            ".bat",
            ".cmd",
            ".com",
            ".scr",
            ".vbs",
            ".js",
        ]
        if any(filename.lower().endswith(ext) for ext in executable_extensions):
            risk_score += 0.3

        # Archive files (can hide malware)
        archive_extensions = [".zip", ".rar", ".7z", ".tar", ".gz"]
        if any(filename.lower().endswith(ext) for ext in archive_extensions):
            risk_score += 0.1

        # Office documents with macros
        if filename.lower().endswith((".docm", ".xlsm", ".pptm")):
            risk_score += 0.2

        # File size anomalies
        file_size = len(file_content)
        if file_size < 100:  # Suspiciously small
            risk_score += 0.1
        elif file_size > 50 * 1024 * 1024:  # Very large
            risk_score += 0.1

        # Entropy check (high entropy might indicate encryption/packing)
        entropy = self._calculate_entropy(file_content[:1024])  # Check first 1KB
        if entropy > 7.5:  # High entropy
            risk_score += 0.2

        return min(risk_score, 1.0)

    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of data."""
        if not data:
            return 0.0

        # Count byte frequencies
        frequencies: Dict[int, int] = {}
        for byte in data:
            frequencies[byte] = frequencies.get(byte, 0) + 1

        # Calculate entropy
        entropy = 0.0
        data_len = len(data)

        for count in frequencies.values():
            if count > 0:
                probability = count / data_len
                entropy -= probability * math.log2(probability)

        return entropy
