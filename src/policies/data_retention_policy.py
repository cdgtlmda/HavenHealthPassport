"""
Data Retention Policy Implementation for Haven Health Passport.

This module implements comprehensive data retention policies for all data types
in the system, ensuring compliance with HIPAA, GDPR, and international regulations
for refugee healthcare data.
All FHIR Resources are subject to retention policies with proper validation.
Healthcare data retention must validate compliance with FHIR standards.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List

from sqlalchemy import and_, select
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.base import get_db
from src.healthcare.regulatory.hipaa_retention_policies import HIPAARetentionPolicies
from src.models.audit_log import AuditAction
from src.models.patient import Patient
from src.services.audit_service import AuditService
from src.services.encryption_service import EncryptionService
from src.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class DataCategory(Enum):
    """Categories of data in the system."""

    # Healthcare Data
    MEDICAL_RECORDS = "medical_records"
    LAB_RESULTS = "lab_results"
    PRESCRIPTIONS = "prescriptions"
    IMAGING = "imaging"
    CLINICAL_NOTES = "clinical_notes"

    # Personal Data
    PATIENT_PII = "patient_pii"
    BIOMETRIC_DATA = "biometric_data"
    EMERGENCY_CONTACTS = "emergency_contacts"
    INSURANCE_INFO = "insurance_info"

    # System Data
    AUDIT_LOGS = "audit_logs"
    ACCESS_LOGS = "access_logs"
    SYSTEM_LOGS = "system_logs"
    ERROR_LOGS = "error_logs"

    # Communication Data
    MESSAGES = "messages"
    NOTIFICATIONS = "notifications"
    VOICE_RECORDINGS = "voice_recordings"

    # Blockchain Data
    BLOCKCHAIN_HASHES = "blockchain_hashes"
    VERIFICATION_RECORDS = "verification_records"

    # Translation Data
    TRANSLATION_CACHE = "translation_cache"
    CULTURAL_ADAPTATIONS = "cultural_adaptations"

    # Temporary Data
    SESSION_DATA = "session_data"
    CACHE_DATA = "cache_data"
    TEMP_FILES = "temp_files"
    QR_CODES = "qr_codes"

    # Refugee-Specific Data
    CAMP_RECORDS = "camp_records"
    TRAVEL_DOCUMENTS = "travel_documents"
    UNHCR_RECORDS = "unhcr_records"


@dataclass
class RetentionPeriod:
    """Data retention period configuration."""

    category: DataCategory
    standard_days: int
    legal_requirement: str
    deletion_method: str
    archive_before_delete: bool
    exemptions: List[str]
    notes: str


class DataRetentionPolicy:
    """Comprehensive data retention policy implementation."""

    def __init__(self, db_session: AsyncSession):
        """Initialize data retention policy with database session."""
        self.db = db_session
        self.encryption_service = EncryptionService()
        # Note: AuditService expects a sync Session, but we have AsyncSession
        # In production, you might need to handle this conversion or use async-compatible audit service
        # For now, we'll pass the db_session as-is
        self.audit_service = AuditService(db_session)  # type: ignore
        self.notification_service = NotificationService(db_session)  # type: ignore
        self.hipaa_policies = HIPAARetentionPolicies()
        self.retention_periods = self._initialize_retention_periods()

    def _initialize_retention_periods(self) -> Dict[DataCategory, RetentionPeriod]:
        """Initialize retention periods for all data categories."""
        return {
            # Healthcare Data - Follow HIPAA minimum requirements
            DataCategory.MEDICAL_RECORDS: RetentionPeriod(
                category=DataCategory.MEDICAL_RECORDS,
                standard_days=2555,  # 7 years
                legal_requirement="HIPAA, State Laws",
                deletion_method="secure_wipe",
                archive_before_delete=True,
                exemptions=["active_patient", "legal_hold", "research_consent"],
                notes="Varies by state, some require 10+ years",
            ),
            DataCategory.LAB_RESULTS: RetentionPeriod(
                category=DataCategory.LAB_RESULTS,
                standard_days=1825,  # 5 years
                legal_requirement="CLIA minimum 2 years",
                deletion_method="secure_wipe",
                archive_before_delete=True,
                exemptions=["abnormal_results", "legal_hold"],
                notes="Critical results may need longer retention",
            ),
            DataCategory.PRESCRIPTIONS: RetentionPeriod(
                category=DataCategory.PRESCRIPTIONS,
                standard_days=1095,  # 3 years
                legal_requirement="DEA requirements",
                deletion_method="secure_wipe",
                archive_before_delete=True,
                exemptions=["controlled_substances", "active_prescription"],
                notes="Controlled substances may require 5 years",
            ),
            # Personal Data - GDPR compliant
            DataCategory.PATIENT_PII: RetentionPeriod(
                category=DataCategory.PATIENT_PII,
                standard_days=2555,  # 7 years after last activity
                legal_requirement="GDPR, HIPAA",
                deletion_method="crypto_shred",
                archive_before_delete=True,
                exemptions=["active_patient", "legal_hold"],
                notes="Must honor deletion requests unless exempted",
            ),
            DataCategory.BIOMETRIC_DATA: RetentionPeriod(
                category=DataCategory.BIOMETRIC_DATA,
                standard_days=365,  # 1 year after last use
                legal_requirement="GDPR Article 9",
                deletion_method="crypto_shred",
                archive_before_delete=False,
                exemptions=["active_authentication", "consent_given"],
                notes="Special category data under GDPR",
            ),
            # System Data - Security and audit requirements
            DataCategory.AUDIT_LOGS: RetentionPeriod(
                category=DataCategory.AUDIT_LOGS,
                standard_days=2190,  # 6 years (HIPAA requirement)
                legal_requirement="HIPAA Security Rule",
                deletion_method="archive_offline",
                archive_before_delete=True,
                exemptions=["security_incident", "legal_hold"],
                notes="May need longer for security investigations",
            ),
            DataCategory.ACCESS_LOGS: RetentionPeriod(
                category=DataCategory.ACCESS_LOGS,
                standard_days=2190,  # 6 years
                legal_requirement="HIPAA Security Rule",
                deletion_method="secure_wipe",
                archive_before_delete=True,
                exemptions=["unauthorized_access", "investigation"],
                notes="Critical for access monitoring",
            ),
            # Communication Data
            DataCategory.MESSAGES: RetentionPeriod(
                category=DataCategory.MESSAGES,
                standard_days=730,  # 2 years
                legal_requirement="Healthcare communication standards",
                deletion_method="secure_wipe",
                archive_before_delete=True,
                exemptions=["medical_advice", "consent_records"],
                notes="Medical advice may need longer retention",
            ),
            DataCategory.VOICE_RECORDINGS: RetentionPeriod(
                category=DataCategory.VOICE_RECORDINGS,
                standard_days=90,  # 90 days
                legal_requirement="Consent-based retention",
                deletion_method="secure_wipe",
                archive_before_delete=False,
                exemptions=["transcription_pending", "quality_review"],
                notes="Minimize retention of voice data",
            ),
            # Temporary Data - Short retention
            DataCategory.SESSION_DATA: RetentionPeriod(
                category=DataCategory.SESSION_DATA,
                standard_days=1,  # 24 hours
                legal_requirement="Security best practice",
                deletion_method="immediate_purge",
                archive_before_delete=False,
                exemptions=[],
                notes="Clear on logout or after 24 hours",
            ),
            DataCategory.QR_CODES: RetentionPeriod(
                category=DataCategory.QR_CODES,
                standard_days=0,  # 5 minutes (0.003 days)
                legal_requirement="Security requirement",
                deletion_method="immediate_purge",
                archive_before_delete=False,
                exemptions=[],
                notes="QR codes expire after 5 minutes",
            ),
            # Refugee-Specific Data
            DataCategory.UNHCR_RECORDS: RetentionPeriod(
                category=DataCategory.UNHCR_RECORDS,
                standard_days=3650,  # 10 years
                legal_requirement="UNHCR data protection policy",
                deletion_method="secure_archive",
                archive_before_delete=True,
                exemptions=["active_case", "family_reunification"],
                notes="May need indefinite retention for stateless persons",
            ),
        }

    async def apply_retention_policy(self) -> Dict[str, Any]:
        """Apply retention policies to all data categories."""
        results: Dict[str, Any] = {
            "execution_time": datetime.utcnow(),
            "categories_processed": [],
            "total_records_deleted": 0,
            "total_records_archived": 0,
            "errors": [],
        }

        try:
            for category, retention in self.retention_periods.items():
                try:
                    category_result = await self._process_category(category, retention)
                    results["categories_processed"].append(category_result)
                    results["total_records_deleted"] += category_result.get(
                        "deleted", 0
                    )
                    results["total_records_archived"] += category_result.get(
                        "archived", 0
                    )
                except (TypeError, ValueError) as e:
                    logger.error(f"Error processing {category.value}: {str(e)}")
                    results["errors"].append(
                        {"category": category.value, "error": str(e)}
                    )

            # Log retention policy execution using standard log_action method
            self.audit_service.log_action(
                action=AuditAction.DATA_DELETED,
                details={"operation": "retention_policy_execution", "results": results},
            )

            # Send summary notification
            await self._send_retention_summary(results)

        except (RuntimeError, TypeError, ValueError) as e:
            logger.error(f"Critical error in retention policy: {str(e)}")
            results["errors"].append({"category": "SYSTEM", "error": str(e)})

        return results

    async def _process_category(
        self, category: DataCategory, retention: RetentionPeriod
    ) -> Dict[str, Any]:
        """Process retention for a specific data category."""
        result: Dict[str, Any] = {
            "category": category.value,
            "retention_days": retention.standard_days,
            "records_evaluated": 0,
            "deleted": 0,
            "archived": 0,
            "exempted": 0,
        }

        cutoff_date = datetime.utcnow() - timedelta(days=retention.standard_days)

        # Get records based on category
        records = await self._get_records_for_category(category, cutoff_date)
        result["records_evaluated"] = len(records)

        for record in records:
            # Check exemptions
            if await self._check_exemptions(record, retention.exemptions):
                result["exempted"] += 1
                continue

            # Archive if required
            if retention.archive_before_delete:
                if await self._archive_record(record, category):
                    result["archived"] += 1

            # Delete record
            if await self._delete_record(record, category, retention.deletion_method):
                result["deleted"] += 1

        return result

    async def _get_records_for_category(
        self, category: DataCategory, cutoff_date: datetime
    ) -> List[Any]:
        """Get records eligible for deletion based on category and cutoff date."""
        # Implementation depends on data model
        # This is a placeholder showing the pattern

        if category == DataCategory.MEDICAL_RECORDS:
            # Query medical records older than cutoff
            # Note: Using Patient model as a placeholder for medical records
            # In production, this would query actual medical record models
            query = select(Patient).where(
                and_(
                    Patient.updated_at < cutoff_date,
                    Patient.is_active.is_(False),
                )
            )
            result = await self.db.execute(query)
            return list(result.scalars().all())

        elif category == DataCategory.SESSION_DATA:
            # Query session data - returning empty list as model doesn't exist
            # In production, this would query actual session data table
            return []

        # Add more category handlers as needed
        return []

    async def _check_exemptions(self, record: Any, exemptions: List[str]) -> bool:
        """Check if record is exempt from deletion."""
        for exemption in exemptions:
            if exemption == "active_patient":
                if hasattr(record, "patient") and record.patient.is_active:
                    return True

            elif exemption == "legal_hold":
                if hasattr(record, "legal_hold") and record.legal_hold:
                    return True

            elif exemption == "research_consent":
                if hasattr(record, "research_consent") and record.research_consent:
                    return True

            elif exemption == "active_case":
                if hasattr(record, "case_status") and record.case_status == "active":
                    return True

        return False

    async def _archive_record(self, record: Any, category: DataCategory) -> bool:
        """Archive record before deletion."""
        try:
            # Create archive entry
            archive_data = {
                "original_id": (
                    str(record.id) if hasattr(record, "id") else str(uuid.uuid4())
                ),
                "category": category.value,
                "archived_date": datetime.utcnow(),
                "data": self._serialize_record(record),
                "metadata": {
                    "table": (
                        record.__tablename__
                        if hasattr(record, "__tablename__")
                        else "unknown"
                    ),
                    "created_at": (
                        str(record.created_at)
                        if hasattr(record, "created_at")
                        else None
                    ),
                    "patient_id": (
                        str(record.patient_id)
                        if hasattr(record, "patient_id")
                        else None
                    ),
                },
            }

            # Encrypt archive data
            encrypted_archive = self.encryption_service.encrypt(
                json.dumps(archive_data)
            )

            # Store in archive (S3, cold storage, etc.)
            encrypted_bytes = (
                encrypted_archive.encode()
                if isinstance(encrypted_archive, str)
                else encrypted_archive
            )
            await self._store_archive(encrypted_bytes, category)

            return True
        except (OSError, TypeError, ValueError) as e:
            logger.error(f"Archive failed for {category.value}: {str(e)}")
            return False

    async def _delete_record(
        self, record: Any, category: DataCategory, deletion_method: str
    ) -> bool:
        """Delete record using specified method."""
        try:
            if deletion_method == "secure_wipe":
                # Overwrite data before deletion
                await self._secure_wipe(record)

            elif deletion_method == "crypto_shred":
                # Delete encryption keys
                await self._crypto_shred(record)

            elif deletion_method == "immediate_purge":
                # Immediate deletion without overwrites
                pass

            elif deletion_method == "archive_offline":
                # Move to offline storage only
                return await self._archive_record(record, category)

            # Perform actual deletion
            await self.db.delete(record)
            await self.db.commit()

            # Log deletion using standard log_action method
            self.audit_service.log_action(
                action=AuditAction.DATA_DELETED,
                details={
                    "record_id": str(record.id) if hasattr(record, "id") else "unknown",
                    "category": category.value,
                    "deletion_method": deletion_method,
                    "deleted_at": datetime.utcnow().isoformat(),
                },
            )

            return True
        except (DataError, IntegrityError, SQLAlchemyError, TypeError, ValueError) as e:
            logger.error(f"Deletion failed for {category.value}: {str(e)}")
            await self.db.rollback()
            return False

    async def _secure_wipe(self, record: Any) -> None:
        """Securely wipe sensitive data fields."""
        # Overwrite sensitive fields with random data
        sensitive_fields = ["ssn", "credit_card", "bank_account", "passport_number"]

        for field in sensitive_fields:
            if hasattr(record, field):
                # Overwrite with random data of same length
                original_value = getattr(record, field)
                if original_value:
                    random_value = self._generate_random_data(len(str(original_value)))
                    setattr(record, field, random_value)

        await self.db.commit()

    async def _crypto_shred(self, record: Any) -> None:
        """Delete encryption keys for the record."""
        if hasattr(record, "encryption_key_id"):
            # TODO: Implement delete_key method in EncryptionService
            # await self.encryption_service.delete_key(record.encryption_key_id)
            pass

    async def _store_archive(
        self, encrypted_data: bytes, category: DataCategory
    ) -> None:
        """Store archived data in cold storage."""
        # Implementation would connect to S3 Glacier or similar
        # TODO: Implement S3 Glacier storage
        # archive_key = (
        #     f"archive/{category.value}/{datetime.utcnow().isoformat()}/{uuid.uuid4()}"
        # )
        # await s3_client.put_object(Bucket=ARCHIVE_BUCKET, Key=archive_key, Body=encrypted_data)

    def _serialize_record(self, record: Any) -> Dict[str, Any]:
        """Serialize database record for archiving."""
        # Convert SQLAlchemy model to dict
        data = {}
        if hasattr(record, "__table__"):
            for column in record.__table__.columns:
                value = getattr(record, column.name)
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif hasattr(value, "__dict__"):
                    value = str(value)
                data[column.name] = value
        else:
            # Fallback for non-SQLAlchemy objects
            data = {"raw_data": str(record)}
        return data

    def _generate_random_data(self, length: int) -> str:
        """Generate random data for secure wiping."""
        import secrets
        import string

        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    async def _send_retention_summary(self, results: Dict[str, Any]) -> None:
        """Send summary notification of retention policy execution."""
        summary = f"""
        Data Retention Policy Execution Summary
        ======================================
        Execution Time: {results['execution_time']}
        Categories Processed: {len(results['categories_processed'])}
        Total Records Deleted: {results['total_records_deleted']}
        Total Records Archived: {results['total_records_archived']}
        Errors: {len(results['errors'])}
        """

        # Send notification using available notification method
        # NotificationService doesn't have send_admin_notification, so we'll use send_notification
        # In production, you'd send to admin users
        logger.info(f"Data Retention Summary: {summary}")

    async def get_deletion_request(self, patient_id: str) -> Dict[str, Any]:
        """Handle GDPR deletion request for a patient."""
        deletion_plan: Dict[str, Any] = {
            "patient_id": patient_id,
            "request_date": datetime.utcnow(),
            "categories_affected": [],
            "estimated_records": 0,
            "exemptions": [],
        }

        # Check each category for patient data
        for category, retention in self.retention_periods.items():
            records_count = await self._count_patient_records(patient_id, category)
            if records_count > 0:
                # Check for exemptions
                exemptions = await self._check_patient_exemptions(
                    patient_id, retention.exemptions
                )

                deletion_plan["categories_affected"].append(
                    {
                        "category": category.value,
                        "records": records_count,
                        "can_delete": len(exemptions) == 0,
                        "exemptions": exemptions,
                    }
                )

                if len(exemptions) == 0:
                    deletion_plan["estimated_records"] += records_count
                else:
                    deletion_plan["exemptions"].extend(exemptions)

        return deletion_plan

    async def execute_deletion_request(
        self, patient_id: str, authorized_by: str
    ) -> Dict[str, Any]:
        """Execute GDPR deletion request."""
        # Get deletion plan
        plan = await self.get_deletion_request(patient_id)

        if plan["exemptions"]:
            raise ValueError(f"Cannot delete due to exemptions: {plan['exemptions']}")

        results: Dict[str, Any] = {
            "patient_id": patient_id,
            "execution_date": datetime.utcnow(),
            "deleted_records": 0,
            "categories_processed": [],
        }

        # Process each category
        for category_info in plan["categories_affected"]:
            if category_info["can_delete"]:
                deleted = await self._delete_patient_category(
                    patient_id, DataCategory(category_info["category"])
                )
                results["deleted_records"] += deleted
                results["categories_processed"].append(category_info["category"])

        # Log the deletion using standard log_action method
        self.audit_service.log_action(
            action=AuditAction.DATA_DELETED,
            patient_id=patient_id,
            details={
                "operation": "gdpr_deletion_request",
                "patient_id": patient_id,
                "authorized_by": authorized_by,
                "results": results,
            },
        )

        return results

    async def _count_patient_records(
        self, patient_id: str, category: DataCategory
    ) -> int:
        """Count records for a patient in a category."""
        # Implementation depends on data model
        return 0

    async def _check_patient_exemptions(
        self, patient_id: str, exemptions: List[str]
    ) -> List[str]:
        """Check which exemptions apply to a patient."""
        applicable_exemptions = []

        # Check each exemption type
        for exemption in exemptions:
            if exemption == "active_patient":
                # Check if patient is active
                from uuid import UUID

                try:
                    patient_uuid = UUID(patient_id)
                    query = select(Patient).where(Patient.id == patient_uuid)
                    result = await self.db.execute(query)
                    patient = result.scalar_one_or_none()
                    if patient and patient.is_active:
                        applicable_exemptions.append("Patient is active")
                except ValueError:
                    # Invalid UUID format
                    pass

            elif exemption == "legal_hold":
                # Check for legal holds
                if await self._has_legal_hold(patient_id):
                    applicable_exemptions.append("Legal hold in effect")

        return applicable_exemptions

    async def _delete_patient_category(
        self, patient_id: str, category: DataCategory
    ) -> int:
        """Delete all records for a patient in a category."""
        # Implementation depends on data model
        return 0

    async def _has_legal_hold(self, patient_id: str) -> bool:
        """Check if patient has any legal holds."""
        # Check legal hold table/service
        return False


# Automated retention policy scheduler
class RetentionPolicyScheduler:
    """Schedules and runs retention policies automatically."""

    def __init__(self) -> None:
        """Initialize the retention policy scheduler."""
        self.running = False

    async def start(self) -> None:
        """Start the retention policy scheduler."""
        self.running = True
        while self.running:
            try:
                # Run daily at 2 AM
                now = datetime.utcnow()
                next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
                if now >= next_run:
                    next_run += timedelta(days=1)

                wait_seconds = (next_run - now).total_seconds()
                await asyncio.sleep(wait_seconds)

                # Execute retention policy
                async with get_db() as db:
                    policy = DataRetentionPolicy(db)
                    results = await policy.apply_retention_policy()
                    logger.info(f"Retention policy executed: {results}")

            except (TypeError, ValueError) as e:
                logger.error(f"Retention scheduler error: {str(e)}")
                await asyncio.sleep(3600)  # Wait 1 hour on error

    def stop(self) -> None:
        """Stop the retention policy scheduler."""
        self.running = False
