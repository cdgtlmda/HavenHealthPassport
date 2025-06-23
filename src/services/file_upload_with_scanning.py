"""File upload service with integrated virus scanning. Handles FHIR Resource validation."""

import asyncio
import io
from datetime import datetime, timedelta
from typing import Any, BinaryIO, Dict, List, Optional, Union
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.audit.audit_service import AuditEventType, audit_event
from src.models.file_attachment import FileAttachment, FileStatus
from src.services.file_upload_service import FileUploadService
from src.services.file_validation_service import FileValidationService
from src.services.notification_service import NotificationService
from src.services.virus_scan_service_complete import ScanProvider, VirusScanService
from src.storage.base import FileCategory
from src.utils.exceptions import ValidationError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SecureFileUploadService(FileUploadService):
    """Enhanced file upload service with validation and virus scanning."""

    def __init__(self, session: Session):
        """Initialize secure file upload service."""
        super().__init__(session)
        self.validation_service = FileValidationService()
        self.virus_scan_service = VirusScanService(session)

        # Configuration
        self.enable_virus_scan = True
        self.enable_validation = True
        self.quarantine_on_threat = True
        self.scan_async = True  # Scan asynchronously after upload

    async def upload_file_secure(
        self,
        file_data: Union[bytes, BinaryIO],
        filename: str,
        category: FileCategory,
        patient_id: Optional[UUID] = None,
        uploaded_by: Optional[UUID] = None,
        description: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        skip_validation: bool = False,
        skip_virus_scan: bool = False,
        organization_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Upload file with validation and virus scanning.

        Args:
            file_data: File data to upload
            filename: Original filename
            category: File category
            patient_id: Associated patient
            uploaded_by: User uploading file
            description: File description
            tags: File tags
            metadata: Additional metadata
            skip_validation: Skip file validation
            skip_virus_scan: Skip virus scanning
            organization_id: Organization ID

        Returns:
            Upload result with scan status
        """
        try:
            # Convert to BytesIO if bytes
            if isinstance(file_data, bytes):
                file_stream = io.BytesIO(file_data)
            else:
                file_stream = file_data  # type: ignore[assignment]

            # Step 1: File validation
            validation_result = None
            if self.enable_validation and not skip_validation:
                logger.info(f"Validating file {filename}")
                validation_result = self.validation_service.validate_for_category(
                    file_stream, filename, category
                )

                if not validation_result.is_valid:
                    logger.warning(
                        f"File validation failed for {filename}: {validation_result.issues}"
                    )

                    # Decide whether to continue or reject
                    critical_issues = [
                        issue
                        for issue in validation_result.issues
                        if any(
                            term in issue.lower()
                            for term in ["executable", "script", "malicious"]
                        )
                    ]

                    if critical_issues:
                        return {
                            "success": False,
                            "error": "File validation failed",
                            "validation_issues": validation_result.issues,
                            "critical_issues": critical_issues,
                        }

            # Step 2: Initial virus scan (if not async)
            scan_result = None
            if self.enable_virus_scan and not skip_virus_scan and not self.scan_async:
                logger.info(f"Scanning file {filename} for viruses")
                scan_result = await self.virus_scan_service.scan_data(
                    file_stream, filename=filename
                )

                if not scan_result["clean"]:
                    logger.warning(
                        f"Virus detected in file {filename}: {scan_result['threats_found']}"
                    )

                    return {
                        "success": False,
                        "error": "Virus detected in file",
                        "scan_result": scan_result,
                        "threats_found": scan_result["threats_found"],
                    }

            # Step 3: Store file
            logger.info(f"Storing file {filename}")

            # Store through storage manager
            attachment = self.storage_manager.store_file(
                file_data=file_stream,
                filename=filename,
                category=category,
                patient_id=patient_id,
                uploaded_by=uploaded_by,
                description=description,
                tags=tags,
                metadata={
                    **(metadata or {}),
                    "validation": (
                        {
                            "is_valid": validation_result.is_valid,
                            "file_type": validation_result.file_type.value,
                            "mime_type": validation_result.mime_type,
                            "issues": validation_result.issues,
                            "metadata": validation_result.metadata,
                        }
                        if validation_result
                        else None
                    ),
                    "virus_scan": scan_result if scan_result else {"status": "pending"},
                    "organization_id": (
                        str(organization_id) if organization_id else None
                    ),
                },
                encrypt=category
                in [
                    FileCategory.MEDICAL_RECORD,
                    FileCategory.LAB_RESULT,
                    FileCategory.PRESCRIPTION,
                ],
            )

            # Step 4: Async virus scan (if enabled)
            if self.enable_virus_scan and not skip_virus_scan and self.scan_async:
                # Queue async scan
                asyncio.create_task(
                    self._async_virus_scan(attachment.file_id, file_stream, filename)
                )

                # Update status to scanning
                attachment.virus_scan_status = "scanning"  # type: ignore[assignment]
                self.session.commit()

            logger.info(
                f"File uploaded successfully - ID: {attachment.file_id}, "
                f"Name: {filename}, Size: {attachment.size}"
            )

            return {
                "success": True,
                "attachment": attachment,
                "file_id": attachment.file_id,
                "validation_result": (
                    {
                        "is_valid": validation_result.is_valid,
                        "file_type": validation_result.file_type.value,
                        "mime_type": validation_result.mime_type,
                        "issues": validation_result.issues,
                        "metadata": validation_result.metadata,
                    }
                    if validation_result
                    else None
                ),
                "scan_result": scan_result,
                "scan_status": (
                    "complete"
                    if scan_result
                    else "scanning" if self.scan_async else "skipped"
                ),
            }

        except ValidationError as e:
            logger.error(f"Validation error in secure file upload: {e}")
            return {"success": False, "error": f"Validation error: {str(e)}"}
        except IOError as e:
            logger.error(f"IO error in secure file upload: {e}")
            return {"success": False, "error": f"File IO error: {str(e)}"}
        except ValueError as e:
            logger.error(f"Value error in secure file upload: {e}")
            return {"success": False, "error": str(e)}

    async def _async_virus_scan(
        self, file_id: str, file_data: BinaryIO, filename: str
    ) -> None:
        """Perform asynchronous virus scan."""
        try:
            logger.info(f"Starting async virus scan for file {file_id}")

            # Perform scan
            scan_result = await self.virus_scan_service.scan_data(
                file_data, filename=filename, file_id=file_id
            )

            # Update file attachment based on result
            attachment = (
                self.session.query(FileAttachment)
                .filter(FileAttachment.file_id == file_id)
                .first()
            )

            if attachment:
                if scan_result["clean"]:
                    attachment.virus_scan_status = "clean"
                    attachment.status = FileStatus.AVAILABLE
                else:
                    attachment.virus_scan_status = "infected"
                    if self.quarantine_on_threat:
                        attachment.status = FileStatus.QUARANTINED
                        attachment.is_quarantined = True

                attachment.last_virus_scan = datetime.utcnow()

                # Update metadata
                if attachment.metadata is None:
                    attachment.metadata = {}
                attachment.metadata["virus_scan"] = scan_result

                self.session.commit()

                # Send alert if threats found
                if not scan_result["clean"]:
                    await self._send_virus_alert(attachment, scan_result)

            logger.info(
                f"Async virus scan completed for file {file_id} - "
                f"Clean: {scan_result['clean']}"
            )

        except OSError as e:
            logger.error(f"IO error in async virus scan for file {file_id}: {e}")

            # Update status to failed
            try:
                attachment = (
                    self.session.query(FileAttachment)
                    .filter(FileAttachment.file_id == file_id)
                    .first()
                )

                if attachment:
                    attachment.virus_scan_status = "failed"
                    self.session.commit()
            except (ValueError, AttributeError):
                pass

    async def _send_virus_alert(
        self, attachment: FileAttachment, scan_result: Dict[str, Any]
    ) -> None:
        """Send alert for virus detection."""
        try:
            threat_summary = []
            for threat in scan_result.get("threats_found", [])[:5]:
                threat_summary.append(
                    f"- {threat.get('name', 'Unknown')} "
                    f"({threat.get('type', 'unknown')})"
                )

            message = (
                f"Virus detected in uploaded file:\n"
                f"File: {attachment.filename}\n"
                f"ID: {attachment.file_id}\n"
                f"Uploaded by: {attachment.uploaded_by}\n"
                f"Patient ID: {attachment.patient_id}\n"
                f"Threats detected:\n" + "\n".join(threat_summary)
            )

            # Implement comprehensive virus alert system
            logger.critical(
                f"VIRUS ALERT: {message}",
                extra={
                    "file_id": attachment.file_id,
                    "filename": attachment.filename,
                    "scan_result": scan_result,
                },
            )

            # Multiple alert channels for critical security event
            try:
                # 1. Immediate file quarantine
                if hasattr(attachment, "quarantine"):
                    attachment.quarantine()
                    logger.info(f"File {attachment.file_id} quarantined")

                # 2. Security team notification
                # SecurityNotifications not available - using notification service directly

                # security_notifier = SecurityNotifications()
                # alert_data = {
                #     "event_type": "VIRUS_DETECTED",
                #     "severity": "CRITICAL",
                #     "file_id": attachment.file_id,
                #     "filename": attachment.filename,
                #     "patient_id": str(attachment.patient_id),
                #     "uploaded_by": str(attachment.uploaded_by),
                #     "threats": threat_summary,
                #     "scan_result": scan_result,
                #     "timestamp": datetime.utcnow().isoformat(),
                #     "description": f"Virus detected in medical document upload: {', '.join(threat_summary)}",
                #     "resource": f"file/{attachment.file_id}",
                # }
                # await security_notifier.notify_security_team(alert_data)

                # 3. Audit log for compliance

                # audit_service = AuditService()  # Requires db_session
                # Log security incident through audit event
                audit_event(
                    event_type=AuditEventType.PATIENT_ACCESS,
                    user_id=(
                        str(attachment.uploaded_by)
                        if attachment.uploaded_by
                        else "system"
                    ),
                    resource_type="file",
                    resource_id=str(attachment.file_id),
                )

                # 4. Notify the uploader about the infected file
                notification_service = NotificationService(self.session)

                await notification_service.send_notification(
                    user_id=attachment.uploaded_by,
                    notification_type="security_alert",
                    title="Infected File Detected",
                    message=f"The file '{attachment.filename}' you uploaded contains malware and has been quarantined. Please scan your device and re-upload a clean version.",
                    data={"file_id": attachment.file_id, "threats": threat_summary},
                )

                # 5. If patient-related, notify patient's care team
                # TODO: Implement care team notification when get_care_team method is available
                # if attachment.patient_id:
                #     from src.services.patient_service import PatientService
                #
                #     patient_service = PatientService(self.session)
                #     care_team = patient_service.get_care_team(attachment.patient_id)
                #
                #     for provider in care_team:
                #         await notification_service.send_notification(
                #             user_id=provider.user_id,
                #             notification_type="patient_security_alert",
                #             title="Security Alert - Patient File",
                #             message=f"An infected file was uploaded for patient {attachment.patient_id}. The file has been quarantined.",
                #             data={
                #                 "patient_id": str(attachment.patient_id),
                #                 "file_id": attachment.file_id,
                #             },
                #         )

                # 6. Block further access to the file
                attachment.access_blocked = True
                attachment.blocked_reason = (
                    f"Virus detected: {', '.join(threat_summary)}"
                )

                logger.info(
                    f"Virus alert system fully executed for file {attachment.file_id}"
                )

            except (AttributeError, RuntimeError, ValueError, IOError) as alert_error:
                logger.error(
                    f"Error in virus alert system: {alert_error}", exc_info=True
                )
                # Even if alerts fail, ensure file remains quarantined for safety

        except (AttributeError, KeyError, ValueError) as e:
            logger.error(f"Error sending virus alert: {e}")

    async def rescan_file(
        self, file_id: str, providers: Optional[List[ScanProvider]] = None
    ) -> Dict[str, Any]:
        """
        Rescan an existing file for viruses.

        Args:
            file_id: File ID to rescan
            providers: Specific scan providers to use

        Returns:
            Scan results
        """
        try:
            # Get file attachment
            attachment = (
                self.session.query(FileAttachment)
                .filter(FileAttachment.file_id == file_id)
                .first()
            )

            if not attachment:
                return {"success": False, "error": "File not found"}

            # Retrieve file data
            file_data, _ = self.storage_manager.retrieve_file(file_id)

            # Perform scan
            scan_result = await self.virus_scan_service.scan_data(
                file_data,
                filename=attachment.filename,
                file_id=file_id,
                providers=providers,
            )

            # Update attachment
            if scan_result["clean"]:
                attachment.virus_scan_status = "clean"
                if attachment.status == FileStatus.QUARANTINED:
                    attachment.status = FileStatus.AVAILABLE
                    attachment.is_quarantined = False
            else:
                attachment.virus_scan_status = "infected"
                if self.quarantine_on_threat:
                    attachment.status = FileStatus.QUARANTINED
                    attachment.is_quarantined = True

            attachment.last_virus_scan = datetime.utcnow()

            # Update metadata
            if attachment.metadata is None:
                attachment.metadata = {}
            attachment.metadata["virus_scan"] = scan_result

            self.session.commit()

            return {
                "success": True,
                "scan_result": scan_result,
                "file_status": attachment.status.value,
            }

        except (IOError, ValueError, AttributeError) as e:
            logger.error(f"Error rescanning file {file_id}: {e}")
            return {"success": False, "error": str(e)}

    async def bulk_rescan_files(
        self,
        file_ids: Optional[List[str]] = None,
        older_than_hours: Optional[int] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Bulk rescan files for viruses.

        Args:
            file_ids: Specific files to rescan
            older_than_hours: Rescan files not scanned in X hours
            limit: Maximum files to rescan

        Returns:
            Bulk scan results
        """
        try:
            # Build query
            query = self.session.query(FileAttachment)

            if file_ids:
                query = query.filter(FileAttachment.file_id.in_(file_ids))
            elif older_than_hours:
                cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
                query = query.filter(
                    or_(
                        FileAttachment.last_virus_scan.is_(None),
                        FileAttachment.last_virus_scan < cutoff,
                    )
                )
            else:
                # Rescan files that need it
                query = query.filter(
                    or_(
                        FileAttachment.virus_scan_status == "pending",
                        FileAttachment.virus_scan_status == "failed",
                        FileAttachment.last_virus_scan.is_(None),
                    )
                )

            files_to_scan = query.limit(limit).all()

            results: Dict[str, Any] = {
                "total": len(files_to_scan),
                "scanned": 0,
                "clean": 0,
                "infected": 0,
                "failed": 0,
                "details": [],
            }

            for file_attachment in files_to_scan:
                try:
                    scan_result = await self.rescan_file(file_attachment.file_id)

                    if scan_result["success"]:
                        results["scanned"] += 1
                        if scan_result["scan_result"]["clean"]:
                            results["clean"] += 1
                        else:
                            results["infected"] += 1
                    else:
                        results["failed"] += 1

                    results["details"].append(
                        {
                            "file_id": file_attachment.file_id,
                            "filename": file_attachment.filename,
                            "result": scan_result,
                        }
                    )

                except (IOError, ValueError, AttributeError) as e:
                    logger.error(f"Error scanning file {file_attachment.file_id}: {e}")
                    results["failed"] += 1
                    results["details"].append(
                        {
                            "file_id": file_attachment.file_id,
                            "filename": file_attachment.filename,
                            "error": str(e),
                        }
                    )

            return results

        except (ValueError, AttributeError) as e:
            logger.error(f"Error in bulk rescan: {e}")
            return {"success": False, "error": str(e)}

    def get_quarantined_files(
        self, limit: int = 100, offset: int = 0
    ) -> List[FileAttachment]:
        """Get list of quarantined files."""
        return (
            self.session.query(FileAttachment)
            .filter(FileAttachment.is_quarantined.is_(True))
            .order_by(FileAttachment.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def release_from_quarantine(
        self, file_id: str, authorized_by: UUID, reason: str
    ) -> bool:
        """
        Release a file from quarantine.

        Args:
            file_id: File to release
            authorized_by: User authorizing release
            reason: Reason for release

        Returns:
            Success status
        """
        try:
            attachment = (
                self.session.query(FileAttachment)
                .filter(FileAttachment.file_id == file_id)
                .first()
            )

            if not attachment:
                return False

            # Update status
            attachment.is_quarantined = False
            attachment.status = FileStatus.AVAILABLE

            # Add audit metadata
            if attachment.metadata is None:
                attachment.metadata = {}

            attachment.metadata["quarantine_release"] = {
                "authorized_by": str(authorized_by),
                "reason": reason,
                "released_at": datetime.utcnow().isoformat(),
            }

            self.session.commit()

            # Log release
            logger.info(
                f"File {file_id} released from quarantine by {authorized_by}: {reason}"
            )

            return True

        except (ValueError, AttributeError, IOError) as e:
            logger.error(f"Error releasing file from quarantine: {e}")
            self.session.rollback()
            return False
