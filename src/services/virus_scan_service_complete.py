"""Complete virus scanning service implementation with multiple providers."""

import asyncio
import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, BinaryIO, Dict, List, Optional, Union

import aiohttp
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.config.settings import Settings
from src.models.base import BaseModel
from src.utils.logging import get_logger

logger = get_logger(__name__)
settings = Settings()


class AlertType(str, Enum):
    """Alert types for the system."""

    VIRUS_DETECTED = "virus_detected"
    SECURITY_THREAT = "security_threat"
    HIGH_RISK_FILE = "high_risk_file"
    CRITICAL = "critical"


async def send_alert(alert_type: AlertType, data: Dict[str, Any]) -> None:
    """Send alert notification."""
    logger.warning(f"Alert [{alert_type}]: {data}")
    # Placeholder for actual alert implementation


class ScanProvider(str, Enum):
    """Available virus scan providers."""

    CLAMAV = "clamav"
    AWS_MACIE = "aws_macie"
    VIRUSTOTAL = "virustotal"
    METADEFENDER = "metadefender"
    WINDOWS_DEFENDER = "windows_defender"
    HYBRID_ANALYSIS = "hybrid_analysis"


class ScanStatus(str, Enum):
    """Scan status states."""

    PENDING = "pending"
    SCANNING = "scanning"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class ThreatLevel(str, Enum):
    """Threat level classification."""

    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"
    UNKNOWN = "unknown"


@dataclass
class ScanResult:
    """Result of a virus scan."""

    scan_id: str
    status: ScanStatus
    threat_level: ThreatLevel
    is_clean: bool
    provider: ScanProvider
    scan_time: float
    threats_found: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "scan_id": self.scan_id,
            "status": self.status.value,
            "threat_level": self.threat_level.value,
            "is_clean": self.is_clean,
            "provider": self.provider.value,
            "scan_time": self.scan_time,
            "threats_found": self.threats_found,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


class VirusScanRecord(BaseModel):
    """Database model for virus scan records."""

    __tablename__ = "virus_scan_records"

    file_id: str
    file_hash: str
    filename: str
    file_size: int
    scan_provider: str
    scan_status: str
    threat_level: str
    is_clean: bool
    threats_found: List[Dict[str, Any]]
    scan_duration: float
    error_message: Optional[str]
    metadata: Dict[str, Any]
    scanned_at: datetime


class ScanProviderInterface(ABC):
    """Abstract interface for virus scan providers."""

    @abstractmethod
    async def scan(
        self, file_data: Union[bytes, BinaryIO], file_hash: str, filename: str
    ) -> ScanResult:
        """Scan file for viruses."""

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider is available."""

    @abstractmethod
    def get_provider_name(self) -> ScanProvider:
        """Get provider name."""


class ClamAVProvider(ScanProviderInterface):
    """ClamAV local virus scanner provider."""

    def __init__(self) -> None:
        """Initialize ClamAV provider."""
        self.clamav: Any = None
        self._initialize_clamav()

    def _initialize_clamav(self) -> None:
        """Initialize ClamAV connection."""
        try:
            import pyclamd  # pylint: disable=import-outside-toplevel

            # Try Unix socket first (faster)
            try:
                self.clamav = pyclamd.ClamdUnixSocket()
                if self.clamav.ping():
                    logger.info("Connected to ClamAV via Unix socket")
                    return
            except OSError:
                pass

            # Try network socket
            try:
                self.clamav = pyclamd.ClamdNetworkSocket(host="localhost", port=3310)
                if self.clamav.ping():
                    logger.info("Connected to ClamAV via network socket")
                    return
            except OSError:
                pass

            self.clamav = None
            logger.warning("ClamAV not available")

        except ImportError:
            logger.warning("pyclamd not installed, ClamAV scanning disabled")
            self.clamav = None

    async def scan(
        self, file_data: Union[bytes, BinaryIO], file_hash: str, filename: str
    ) -> ScanResult:
        """Scan file with ClamAV."""
        start_time = time.time()
        scan_id = f"clamav_{file_hash[:16]}_{int(time.time())}"

        try:
            if not self.clamav:
                raise RuntimeError("ClamAV not available")

            # Convert to bytes if needed
            if isinstance(file_data, BinaryIO):
                file_data.seek(0)
                data = file_data.read()
            else:
                data = file_data

            # Scan with ClamAV
            scan_result = await asyncio.to_thread(self.clamav.scan_stream, data)

            scan_time = time.time() - start_time

            if scan_result is None:
                # Clean file
                return ScanResult(
                    scan_id=scan_id,
                    status=ScanStatus.COMPLETED,
                    threat_level=ThreatLevel.CLEAN,
                    is_clean=True,
                    provider=ScanProvider.CLAMAV,
                    scan_time=scan_time,
                    threats_found=[],
                    metadata={
                        "engine_version": self.clamav.version(),
                        "filename": filename,
                    },
                    timestamp=datetime.utcnow(),
                )
            else:
                # Threat found
                threats = []
                threat_level = ThreatLevel.MALICIOUS

                for _, (status, threat_name) in scan_result.items():
                    if status == "FOUND":
                        threats.append(
                            {"name": threat_name, "type": "virus", "severity": "high"}
                        )

                return ScanResult(
                    scan_id=scan_id,
                    status=ScanStatus.COMPLETED,
                    threat_level=threat_level,
                    is_clean=False,
                    provider=ScanProvider.CLAMAV,
                    scan_time=scan_time,
                    threats_found=threats,
                    metadata={
                        "engine_version": self.clamav.version(),
                        "filename": filename,
                        "raw_result": scan_result,
                    },
                    timestamp=datetime.utcnow(),
                )

        except (IOError, ValueError, RuntimeError) as e:
            logger.error(f"ClamAV scan error: {e}")
            return ScanResult(
                scan_id=scan_id,
                status=ScanStatus.FAILED,
                threat_level=ThreatLevel.UNKNOWN,
                is_clean=False,
                provider=ScanProvider.CLAMAV,
                scan_time=time.time() - start_time,
                threats_found=[],
                metadata={"error": str(e), "filename": filename},
                timestamp=datetime.utcnow(),
            )

    async def is_available(self) -> bool:
        """Check if ClamAV is available."""
        try:
            return self.clamav is not None and self.clamav.ping()
        except OSError:
            return False

    def get_provider_name(self) -> ScanProvider:
        """Get provider name."""
        return ScanProvider.CLAMAV


class VirusTotalProvider(ScanProviderInterface):
    """VirusTotal API provider."""

    def __init__(self, api_key: str):
        """Initialize VirusTotal provider."""
        self.api_key = api_key
        self.base_url = "https://www.virustotal.com/api/v3"
        self.upload_url = f"{self.base_url}/files"
        self.report_url = f"{self.base_url}/files"

    async def scan(
        self, file_data: Union[bytes, BinaryIO], file_hash: str, filename: str
    ) -> ScanResult:
        """Scan file with VirusTotal."""
        start_time = time.time()
        scan_id = f"vt_{file_hash[:16]}_{int(time.time())}"

        try:
            # Convert to bytes if needed
            if isinstance(file_data, BinaryIO):
                file_data.seek(0)
                data = file_data.read()
            else:
                data = file_data

            # Check if file already scanned by hash
            existing_result = await self._check_existing_scan(file_hash)
            if existing_result:
                return existing_result

            # Upload file
            upload_result = await self._upload_file(data, filename)
            if not upload_result:
                raise RuntimeError("Failed to upload file to VirusTotal")

            file_id = upload_result["data"]["id"]

            # Wait for scan completion
            scan_result = await self._wait_for_scan(file_id)

            scan_time = time.time() - start_time

            # Parse results
            return self._parse_scan_result(scan_result, scan_id, scan_time, filename)

        except (IOError, ValueError, RuntimeError) as e:
            logger.error(f"VirusTotal scan error: {e}")
            return ScanResult(
                scan_id=scan_id,
                status=ScanStatus.FAILED,
                threat_level=ThreatLevel.UNKNOWN,
                is_clean=False,
                provider=ScanProvider.VIRUSTOTAL,
                scan_time=time.time() - start_time,
                threats_found=[],
                metadata={"error": str(e), "filename": filename},
                timestamp=datetime.utcnow(),
            )

    async def _check_existing_scan(self, file_hash: str) -> Optional[ScanResult]:
        """Check if file was already scanned."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"x-apikey": self.api_key}
                url = f"{self.report_url}/{file_hash}"

                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        # File already scanned, parse results
                        scan_id = f"vt_existing_{file_hash[:16]}"
                        return self._parse_scan_result(
                            data, scan_id, 0.0, "cached_result"
                        )
                    else:
                        return None

        except (IOError, ValueError, RuntimeError) as e:
            logger.debug(f"No existing scan found: {e}")
            return None

    async def _upload_file(
        self, file_data: bytes, filename: str
    ) -> Optional[Dict[str, Any]]:
        """Upload file to VirusTotal."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"x-apikey": self.api_key}

                # Create multipart form
                data = aiohttp.FormData()
                data.add_field(
                    "file",
                    file_data,
                    filename=filename,
                    content_type="application/octet-stream",
                )

                async with session.post(
                    self.upload_url, headers=headers, data=data
                ) as response:
                    if response.status == 200:
                        response_data: Dict[str, Any] = await response.json()
                        return response_data
                    else:
                        error_text = await response.text()
                        logger.error(f"VirusTotal upload failed: {error_text}")
                        return None

        except (IOError, ValueError, RuntimeError) as e:
            logger.error(f"Error uploading to VirusTotal: {e}")
            return None

    async def _wait_for_scan(self, file_id: str, max_wait: int = 300) -> Dict[str, Any]:
        """Wait for scan to complete."""
        start_time = time.time()

        async with aiohttp.ClientSession() as session:
            headers = {"x-apikey": self.api_key}
            url = f"{self.report_url}/{file_id}"

            while time.time() - start_time < max_wait:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Check if analysis complete
                        if data["data"]["attributes"].get("last_analysis_stats"):
                            result: Dict[str, Any] = data
                            return result

                # Wait before next check
                await asyncio.sleep(5)

            raise TimeoutError("Scan timeout waiting for VirusTotal results")

    def _parse_scan_result(
        self, vt_data: Dict[str, Any], scan_id: str, scan_time: float, filename: str
    ) -> ScanResult:
        """Parse VirusTotal scan result."""
        attributes = vt_data["data"]["attributes"]
        stats = attributes.get("last_analysis_stats", {})
        results = attributes.get("last_analysis_results", {})

        # Calculate threat level
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)

        threats_found = []

        # Extract detected threats
        for engine, result in results.items():
            if result["category"] in ["malicious", "suspicious"]:
                threats_found.append(
                    {
                        "engine": engine,
                        "name": result.get("result", "Unknown"),
                        "type": result["category"],
                        "severity": (
                            "high" if result["category"] == "malicious" else "medium"
                        ),
                    }
                )

        # Determine threat level
        if malicious > 0:
            threat_level = ThreatLevel.MALICIOUS
            is_clean = False
        elif suspicious > 0:
            threat_level = ThreatLevel.SUSPICIOUS
            is_clean = False
        else:
            threat_level = ThreatLevel.CLEAN
            is_clean = True

        return ScanResult(
            scan_id=scan_id,
            status=ScanStatus.COMPLETED,
            threat_level=threat_level,
            is_clean=is_clean,
            provider=ScanProvider.VIRUSTOTAL,
            scan_time=scan_time,
            threats_found=threats_found,
            metadata={
                "filename": filename,
                "stats": stats,
                "total_engines": len(results),
                "file_hash": attributes.get("sha256", ""),
                "file_type": attributes.get("type_description", ""),
                "scan_date": attributes.get("last_analysis_date", ""),
            },
            timestamp=datetime.utcnow(),
        )

    async def is_available(self) -> bool:
        """Check if VirusTotal is available."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"x-apikey": self.api_key}
                url = f"{self.base_url}/files/test"

                async with session.get(url, headers=headers) as response:
                    return response.status in [200, 404]  # 404 is ok, means API works

        except (aiohttp.ClientError, OSError):
            return False

    def get_provider_name(self) -> ScanProvider:
        """Get provider name."""
        return ScanProvider.VIRUSTOTAL


class VirusScanService:
    """Main virus scanning service orchestrator."""

    def __init__(self, session: Optional[Session] = None):
        """Initialize virus scan service."""
        self.session = session
        self.providers: Dict[ScanProvider, ScanProviderInterface] = {}
        self._initialize_providers()

        # Configuration
        self.max_file_size = getattr(
            settings, "virus_scan_max_file_size", 100 * 1024 * 1024
        )
        self.scan_timeout = getattr(settings, "virus_scan_timeout", 300)
        self.enable_multi_scan = getattr(settings, "virus_scan_multi_scan", False)
        self.quarantine_on_fail = getattr(
            settings, "virus_scan_quarantine_on_fail", True
        )

    def _initialize_providers(self) -> None:
        """Initialize available scan providers."""
        # Initialize ClamAV
        clamav_provider = ClamAVProvider()
        self.providers[ScanProvider.CLAMAV] = clamav_provider

        # Initialize VirusTotal if API key available
        vt_api_key = getattr(settings, "virustotal_api_key", None)
        if vt_api_key:
            vt_provider = VirusTotalProvider(vt_api_key)
            self.providers[ScanProvider.VIRUSTOTAL] = vt_provider

        # Add more providers as needed
        logger.info(f"Initialized virus scan providers: {list(self.providers.keys())}")

    async def scan_data(
        self,
        data: Union[bytes, BinaryIO],
        filename: str,
        file_id: Optional[str] = None,
        providers: Optional[List[ScanProvider]] = None,
    ) -> Dict[str, Any]:
        """
        Scan data for viruses using available providers.

        Args:
            data: File data to scan
            filename: Name of file
            file_id: Optional file ID for tracking
            providers: Specific providers to use (all if None)

        Returns:
            Scan results dictionary
        """
        # Calculate file hash
        if isinstance(data, bytes):
            file_hash = hashlib.sha256(data).hexdigest()
            file_size = len(data)
        else:
            data.seek(0)
            hasher = hashlib.sha256()
            file_size = 0
            for chunk in iter(lambda: data.read(8192), b""):
                hasher.update(chunk)
                file_size += len(chunk)
            file_hash = hasher.hexdigest()
            data.seek(0)

        # Check file size
        if file_size > self.max_file_size:
            logger.warning(f"File {filename} too large for scanning: {file_size} bytes")
            return {
                "clean": True,  # Assume clean if too large
                "scanned": False,
                "reason": "file_too_large",
                "file_size": file_size,
                "max_size": self.max_file_size,
            }

        # Determine which providers to use
        if providers:
            scan_providers = [p for p in providers if p in self.providers]
        else:
            scan_providers = list(self.providers.keys())

        # Check provider availability
        available_providers = []
        for provider_name in scan_providers:
            provider = self.providers[provider_name]
            if await provider.is_available():
                available_providers.append(provider_name)

        if not available_providers:
            logger.error("No virus scan providers available")
            return {
                "clean": self.quarantine_on_fail,
                "scanned": False,
                "reason": "no_providers_available",
            }

        # Perform scans
        scan_results = []

        if self.enable_multi_scan:
            # Run all providers in parallel
            tasks = []
            for provider_name in available_providers:
                provider = self.providers[provider_name]
                task = provider.scan(data, file_hash, filename)
                tasks.append(task)

            scan_results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            # Run first available provider
            provider = self.providers[available_providers[0]]
            result = await provider.scan(data, file_hash, filename)
            scan_results = [result]

        # Process results
        all_clean = True
        threats_found: List[Any] = []
        scan_summaries = []

        for scan_item in scan_results:
            if isinstance(scan_item, Exception):
                logger.error(f"Scan provider error: {scan_item}")
                continue

            # At this point, scan_item is guaranteed to be ScanResult
            if not isinstance(scan_item, ScanResult):
                continue
            scan_result = scan_item

            scan_summaries.append(
                {
                    "provider": scan_result.provider.value,
                    "status": scan_result.status.value,
                    "threat_level": scan_result.threat_level.value,
                    "is_clean": scan_result.is_clean,
                    "scan_time": scan_result.scan_time,
                    "threats_count": len(scan_result.threats_found),
                }
            )

            if not scan_result.is_clean:
                all_clean = False
                threats_found.extend(scan_result.threats_found)

            # Save scan record if session available
            if self.session and file_id:
                self._save_scan_record(
                    file_id=file_id,
                    file_hash=file_hash,
                    filename=filename,
                    file_size=file_size,
                    scan_result=scan_result,
                )

        # Alert on threats
        if threats_found:
            await self._send_threat_alert(filename, file_hash, threats_found)

        return {
            "clean": all_clean,
            "scanned": True,
            "file_hash": file_hash,
            "file_size": file_size,
            "threats_found": threats_found,
            "threat_count": len(threats_found),
            "scan_providers": available_providers,
            "scan_summaries": scan_summaries,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _save_scan_record(
        self,
        file_id: str,
        file_hash: str,
        filename: str,
        file_size: int,
        scan_result: ScanResult,
    ) -> None:
        """Save scan record to database."""
        try:
            record = VirusScanRecord(
                file_id=file_id,
                file_hash=file_hash,
                filename=filename,
                file_size=file_size,
                scan_provider=scan_result.provider.value,
                scan_status=scan_result.status.value,
                threat_level=scan_result.threat_level.value,
                is_clean=scan_result.is_clean,
                threats_found=scan_result.threats_found,
                scan_duration=scan_result.scan_time,
                error_message=scan_result.metadata.get("error"),
                metadata=scan_result.metadata,
                scanned_at=scan_result.timestamp,
            )

            if self.session:
                self.session.add(record)
                self.session.commit()

        except (IOError, ValueError, RuntimeError) as e:
            logger.error(f"Error saving scan record: {e}")
            if self.session:
                self.session.rollback()

    async def _send_threat_alert(
        self, filename: str, file_hash: str, threats: List[Dict[str, Any]]
    ) -> None:
        """Send alert for detected threats."""
        try:
            threat_names = [t.get("name", "Unknown") for t in threats[:5]]

            message = (
                f"Virus/malware detected in file upload:\n"
                f"File: {filename}\n"
                f"Hash: {file_hash[:16]}...\n"
                f"Threats: {', '.join(threat_names)}\n"
                f"Total threats: {len(threats)}"
            )

            await send_alert(
                alert_type=AlertType.CRITICAL,
                data={
                    "message": message,
                    "filename": filename,
                    "file_hash": file_hash,
                    "threat_count": len(threats),
                    "threats": threats,
                },
            )

        except (IOError, ValueError, RuntimeError) as e:
            logger.error(f"Error sending threat alert: {e}")

    async def get_scan_history(
        self,
        file_id: Optional[str] = None,
        file_hash: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get scan history for files."""
        if not self.session:
            return []

        query = self.session.query(VirusScanRecord)

        if file_id:
            query = query.filter(VirusScanRecord.file_id == file_id)

        if file_hash:
            query = query.filter(VirusScanRecord.file_hash == file_hash)

        records = query.order_by(VirusScanRecord.scanned_at.desc()).limit(limit).all()

        return [
            {
                "file_id": r.file_id,
                "file_hash": r.file_hash,
                "filename": r.filename,
                "scan_provider": r.scan_provider,
                "is_clean": r.is_clean,
                "threat_level": r.threat_level,
                "threats_found": r.threats_found,
                "scanned_at": r.scanned_at.isoformat(),
            }
            for r in records
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """Get virus scan statistics."""
        if not self.session:
            return {}

        total_scans = self.session.query(func.count(VirusScanRecord.id)).scalar()

        clean_scans = (
            self.session.query(func.count(VirusScanRecord.id))
            .filter(VirusScanRecord.is_clean.is_(True))
            .scalar()
        )

        threats_by_level = (
            self.session.query(
                VirusScanRecord.threat_level, func.count(VirusScanRecord.id)
            )
            .group_by(VirusScanRecord.threat_level)
            .all()
        )

        scans_by_provider = (
            self.session.query(
                VirusScanRecord.scan_provider, func.count(VirusScanRecord.id)
            )
            .group_by(VirusScanRecord.scan_provider)
            .all()
        )

        avg_scan_time = self.session.query(
            func.avg(VirusScanRecord.scan_duration)
        ).scalar()

        return {
            "total_scans": total_scans,
            "clean_scans": clean_scans,
            "infected_scans": total_scans - clean_scans,
            "clean_percentage": (
                (clean_scans / total_scans * 100) if total_scans > 0 else 0
            ),
            "threats_by_level": {
                str(level): count for level, count in threats_by_level
            },
            "scans_by_provider": {
                str(provider): count for provider, count in scans_by_provider
            },
            "average_scan_time": float(avg_scan_time) if avg_scan_time else 0,
        }


# Create singleton instance
virus_scan_service = VirusScanService()
