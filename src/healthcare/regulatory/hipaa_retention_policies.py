"""HIPAA Retention Policies Implementation.

This module implements HIPAA-compliant retention policies for PHI,
including retention schedules, disposal procedures, and legal holds.
"""

import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RecordType(Enum):
    """Types of healthcare records."""

    MEDICAL_RECORD = "medical_record"
    BILLING_RECORD = "billing_record"
    INSURANCE_RECORD = "insurance_record"
    LAB_RESULT = "lab_result"
    IMAGING_STUDY = "imaging_study"
    PRESCRIPTION = "prescription"
    CLINICAL_NOTE = "clinical_note"
    AUDIT_LOG = "audit_log"
    AUTHORIZATION = "authorization"
    CONSENT = "consent"
    CORRESPONDENCE = "correspondence"
    INCIDENT_REPORT = "incident_report"


class RetentionBasis(Enum):
    """Legal basis for retention period."""

    HIPAA_REQUIRED = "hipaa_required"  # HIPAA minimum
    STATE_LAW = "state_law"  # State-specific requirement
    MEDICARE = "medicare"  # Medicare conditions
    CLINICAL_TRIAL = "clinical_trial"  # Research requirements
    LEGAL_HOLD = "legal_hold"  # Litigation hold
    BUSINESS_NEED = "business_need"  # Operational need
    PATIENT_CARE = "patient_care"  # Continuity of care


class DisposalMethod(Enum):
    """Methods for secure disposal."""

    SHREDDING = "shredding"  # Physical records
    DEGAUSSING = "degaussing"  # Magnetic media
    OVERWRITING = "overwriting"  # Digital storage
    INCINERATION = "incineration"  # Physical records
    CRYPTOGRAPHIC_ERASURE = "cryptographic_erasure"  # Encrypted data


class HIPAARetentionPolicies:
    """Manages HIPAA-compliant retention policies."""

    def __init__(self) -> None:
        """Initialize retention policy system."""
        self.retention_schedules = self._initialize_retention_schedules()
        self.retention_registry: Dict[str, Any] = {}
        self.disposal_log: List[Dict[str, Any]] = []
        self.legal_holds: Dict[str, Any] = {}
        self.extension_requests: List[Dict[str, Any]] = []

    def _initialize_retention_schedules(self) -> Dict[RecordType, Dict[str, Any]]:
        """Initialize standard retention schedules."""
        return {
            RecordType.MEDICAL_RECORD: {
                "standard_retention_years": 7,  # Typical state requirement
                "basis": RetentionBasis.STATE_LAW,
                "from_date": "last_treatment",
                "minor_extension": 3,  # Years after age of majority
                "disposal_method": DisposalMethod.SHREDDING,
                "notes": "Varies by state, some require 10+ years",
            },
            RecordType.BILLING_RECORD: {
                "standard_retention_years": 7,
                "basis": RetentionBasis.MEDICARE,
                "from_date": "service_date",
                "minor_extension": 0,
                "disposal_method": DisposalMethod.SHREDDING,
                "notes": "Medicare requires 7 years",
            },
            RecordType.AUDIT_LOG: {
                "standard_retention_years": 6,
                "basis": RetentionBasis.HIPAA_REQUIRED,
                "from_date": "creation_date",
                "minor_extension": 0,
                "disposal_method": DisposalMethod.CRYPTOGRAPHIC_ERASURE,
                "notes": "HIPAA Security Rule requirement",
            },
            RecordType.LAB_RESULT: {
                "standard_retention_years": 5,
                "basis": RetentionBasis.STATE_LAW,
                "from_date": "result_date",
                "minor_extension": 3,
                "disposal_method": DisposalMethod.SHREDDING,
                "notes": "CLIA requires 2 years minimum",
            },
            RecordType.IMAGING_STUDY: {
                "standard_retention_years": 7,
                "basis": RetentionBasis.STATE_LAW,
                "from_date": "study_date",
                "minor_extension": 3,
                "disposal_method": DisposalMethod.OVERWRITING,
                "notes": "Mammograms may require longer retention",
            },
        }

    def create_retention_record(
        self,
        record_id: str,
        record_type: RecordType,
        creation_date: datetime,
        patient_id: str,
        last_activity_date: Optional[datetime] = None,
        is_minor: bool = False,
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a retention tracking record.

        Args:
            record_id: Unique record identifier
            record_type: Type of record
            creation_date: When record was created
            patient_id: Associated patient
            last_activity_date: Last treatment/activity date
            is_minor: Whether patient is a minor
            additional_metadata: Additional record metadata

        Returns:
            Retention record ID
        """
        retention_id = self._generate_retention_id()

        # Get retention schedule
        schedule = self.retention_schedules.get(
            record_type, self._get_default_schedule()
        )

        # Calculate retention end date
        base_date = last_activity_date or creation_date
        retention_years = schedule["standard_retention_years"]

        if is_minor:
            retention_years += schedule.get("minor_extension", 0)

        retention_end_date = base_date + timedelta(days=retention_years * 365)

        retention_record = {
            "retention_id": retention_id,
            "record_id": record_id,
            "record_type": record_type.value,
            "patient_id": patient_id,
            "creation_date": creation_date,
            "last_activity_date": last_activity_date,
            "retention_start_date": base_date,
            "retention_end_date": retention_end_date,
            "retention_years": retention_years,
            "is_minor": is_minor,
            "legal_hold": False,
            "disposal_eligible": False,
            "disposal_date": None,
            "metadata": additional_metadata or {},
        }

        self.retention_registry[retention_id] = retention_record

        logger.info(
            "Retention record created: %s for %s until %s",
            retention_id,
            record_type.value,
            retention_end_date.strftime("%Y-%m-%d"),
        )

        return retention_id

    def apply_legal_hold(
        self,
        hold_name: str,
        record_criteria: Dict[str, Any],
        reason: str,
        authorized_by: str,
    ) -> str:
        """Apply legal hold to records.

        Args:
            hold_name: Name of legal hold
            record_criteria: Criteria for records to hold
            reason: Reason for hold
            authorized_by: Person authorizing hold

        Returns:
            Legal hold ID
        """
        hold_id = self._generate_hold_id()

        legal_hold: Dict[str, Any] = {
            "hold_id": hold_id,
            "hold_name": hold_name,
            "created_date": datetime.now(),
            "criteria": record_criteria,
            "reason": reason,
            "authorized_by": authorized_by,
            "active": True,
            "affected_records": [],
            "release_date": None,
        }

        # Apply hold to matching records
        affected_count = 0
        for retention_id, record in self.retention_registry.items():
            if self._matches_criteria(record, record_criteria):
                record["legal_hold"] = True
                record["disposal_eligible"] = False
                legal_hold["affected_records"].append(retention_id)
                affected_count += 1

        legal_hold["affected_count"] = affected_count
        self.legal_holds[hold_id] = legal_hold

        logger.warning(
            "Legal hold applied: %s affecting %d records", hold_id, affected_count
        )

        return hold_id

    def release_legal_hold(self, hold_id: str, authorized_by: str, reason: str) -> bool:
        """Release a legal hold.

        Args:
            hold_id: Legal hold to release
            authorized_by: Person authorizing release
            reason: Reason for release

        Returns:
            Success status
        """
        if hold_id not in self.legal_holds:
            return False

        hold = self.legal_holds[hold_id]
        hold["active"] = False
        hold["release_date"] = datetime.now()
        hold["released_by"] = authorized_by
        hold["release_reason"] = reason

        # Remove hold from affected records
        for retention_id in hold["affected_records"]:
            if retention_id in self.retention_registry:
                record = self.retention_registry[retention_id]
                record["legal_hold"] = False
                # Check if now eligible for disposal
                if datetime.now() > record["retention_end_date"]:
                    record["disposal_eligible"] = True

        logger.info("Legal hold released: %s", hold_id)

        return True

    def identify_disposal_eligible(
        self, as_of_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Identify records eligible for disposal.

        Args:
            as_of_date: Date to check eligibility (default: now)

        Returns:
            List of eligible records
        """
        check_date = as_of_date or datetime.now()
        eligible_records = []

        for retention_id, record in self.retention_registry.items():
            # Skip if under legal hold
            if record.get("legal_hold", False):
                continue

            # Skip if already disposed
            if record.get("disposal_date"):
                continue

            # Check if retention period has expired
            if check_date >= record["retention_end_date"]:
                record["disposal_eligible"] = True
                eligible_records.append(
                    {
                        "retention_id": retention_id,
                        "record_id": record["record_id"],
                        "record_type": record["record_type"],
                        "retention_end_date": record["retention_end_date"],
                        "days_overdue": (
                            check_date - record["retention_end_date"]
                        ).days,
                    }
                )

        return sorted(eligible_records, key=lambda x: x["days_overdue"], reverse=True)

    def dispose_records(
        self,
        retention_ids: List[str],
        disposal_method: DisposalMethod,
        authorized_by: str,
        verification_details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Dispose of records per retention policy.

        Args:
            retention_ids: Records to dispose
            disposal_method: Method of disposal
            authorized_by: Person authorizing disposal
            verification_details: Disposal verification info

        Returns:
            Disposal results
        """
        disposal_batch_id = self._generate_disposal_id()
        disposal_date = datetime.now()

        results: Dict[str, Any] = {
            "batch_id": disposal_batch_id,
            "disposal_date": disposal_date,
            "method": disposal_method.value,
            "authorized_by": authorized_by,
            "total_records": len(retention_ids),
            "disposed": 0,
            "failed": 0,
            "disposal_details": [],
        }

        for retention_id in retention_ids:
            if retention_id not in self.retention_registry:
                results["failed"] += 1
                results["disposal_details"].append(
                    {
                        "retention_id": retention_id,
                        "status": "failed",
                        "reason": "Record not found",
                    }
                )
                continue

            record = self.retention_registry[retention_id]

            # Verify eligibility
            if not record.get("disposal_eligible", False):
                results["failed"] += 1
                results["disposal_details"].append(
                    {
                        "retention_id": retention_id,
                        "status": "failed",
                        "reason": "Not eligible for disposal",
                    }
                )
                continue

            if record.get("legal_hold", False):
                results["failed"] += 1
                results["disposal_details"].append(
                    {
                        "retention_id": retention_id,
                        "status": "failed",
                        "reason": "Under legal hold",
                    }
                )
                continue

            # Perform disposal
            disposal_record = {
                "retention_id": retention_id,
                "record_id": record["record_id"],
                "record_type": record["record_type"],
                "disposal_date": disposal_date,
                "disposal_method": disposal_method.value,
                "authorized_by": authorized_by,
                "batch_id": disposal_batch_id,
                "verification": verification_details or {},
            }

            self.disposal_log.append(disposal_record)

            # Update retention record
            record["disposal_date"] = disposal_date
            record["disposal_method"] = disposal_method.value

            results["disposed"] += 1
            results["disposal_details"].append(
                {
                    "retention_id": retention_id,
                    "status": "success",
                    "disposal_date": disposal_date,
                }
            )

        logger.info(
            "Disposal batch %s: %d disposed, %d failed",
            disposal_batch_id,
            results["disposed"],
            results["failed"],
        )

        return results

    def request_retention_extension(
        self, retention_id: str, extension_years: int, reason: str, requested_by: str
    ) -> str:
        """Request extension of retention period.

        Args:
            retention_id: Retention record to extend
            extension_years: Years to extend
            reason: Reason for extension
            requested_by: Person requesting

        Returns:
            Extension request ID
        """
        if retention_id not in self.retention_registry:
            raise ValueError(f"Retention record {retention_id} not found")

        request_id = self._generate_extension_id()

        extension_request = {
            "request_id": request_id,
            "retention_id": retention_id,
            "request_date": datetime.now(),
            "extension_years": extension_years,
            "reason": reason,
            "requested_by": requested_by,
            "approved": None,
            "approval_date": None,
            "approved_by": None,
        }

        self.extension_requests.append(extension_request)

        # Auto-approve if valid business reason
        if self._is_valid_extension_reason(reason):
            self.approve_extension(request_id, "SYSTEM", "Auto-approved")

        return request_id

    def approve_extension(
        self, request_id: str, approved_by: str, approval_notes: str
    ) -> bool:
        """Approve retention extension request.

        Args:
            request_id: Extension request ID
            approved_by: Person approving
            approval_notes: Approval notes

        Returns:
            Success status
        """
        # Find request
        request = None
        for req in self.extension_requests:
            if req["request_id"] == request_id:
                request = req
                break

        if not request:
            return False

        # Update request
        request["approved"] = True
        request["approval_date"] = datetime.now()
        request["approved_by"] = approved_by
        request["approval_notes"] = approval_notes

        # Update retention record
        retention_id = request["retention_id"]
        if retention_id in self.retention_registry:
            record = self.retention_registry[retention_id]
            old_date = record["retention_end_date"]
            new_date = old_date + timedelta(days=request["extension_years"] * 365)
            record["retention_end_date"] = new_date
            record["retention_years"] += request["extension_years"]
            record["disposal_eligible"] = False

            logger.info(
                "Retention extended for %s from %s to %s",
                retention_id,
                old_date.strftime("%Y-%m-%d"),
                new_date.strftime("%Y-%m-%d"),
            )

        return True

    def audit_retention_compliance(
        self, audit_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Audit retention policy compliance.

        Args:
            audit_date: Date to audit (default: now)

        Returns:
            Audit report
        """
        audit_date = audit_date or datetime.now()

        # Analyze retention records
        total_records = len(self.retention_registry)
        expired_not_disposed = 0
        under_legal_hold = 0
        disposal_overdue = []

        for retention_id, record in self.retention_registry.items():
            if record.get("legal_hold", False):
                under_legal_hold += 1

            if record["retention_end_date"] < audit_date and not record.get(
                "disposal_date"
            ):
                expired_not_disposed += 1
                days_overdue = (audit_date - record["retention_end_date"]).days

                if days_overdue > 90:  # More than 90 days overdue
                    disposal_overdue.append(
                        {
                            "retention_id": retention_id,
                            "record_type": record["record_type"],
                            "days_overdue": days_overdue,
                        }
                    )

        # Analyze disposal log
        disposal_summary = {}
        for disposal in self.disposal_log:
            method = disposal["disposal_method"]
            if method not in disposal_summary:
                disposal_summary[method] = 0
            disposal_summary[method] += 1

        audit_report = {
            "audit_date": audit_date,
            "summary": {
                "total_tracked_records": total_records,
                "expired_not_disposed": expired_not_disposed,
                "under_legal_hold": under_legal_hold,
                "disposal_overdue_count": len(disposal_overdue),
                "total_disposed": len(self.disposal_log),
            },
            "disposal_methods_used": disposal_summary,
            "overdue_disposals": disposal_overdue[:10],  # Top 10
            "active_legal_holds": sum(
                1 for h in self.legal_holds.values() if h["active"]
            ),
            "pending_extensions": sum(
                1 for e in self.extension_requests if e["approved"] is None
            ),
            "compliance_score": self._calculate_compliance_score(
                total_records, expired_not_disposed, len(disposal_overdue)
            ),
            "recommendations": self._generate_compliance_recommendations(
                expired_not_disposed, disposal_overdue
            ),
        }

        return audit_report

    def _get_default_schedule(self) -> Dict[str, Any]:
        """Get default retention schedule."""
        return {
            "standard_retention_years": 7,
            "basis": RetentionBasis.BUSINESS_NEED,
            "from_date": "creation_date",
            "minor_extension": 3,
            "disposal_method": DisposalMethod.SHREDDING,
            "notes": "Default retention period",
        }

    def _matches_criteria(
        self, record: Dict[str, Any], criteria: Dict[str, Any]
    ) -> bool:
        """Check if record matches criteria."""
        for key, value in criteria.items():
            if key in record:
                if isinstance(value, list):
                    if record[key] not in value:
                        return False
                elif record[key] != value:
                    return False
        return True

    def _is_valid_extension_reason(self, reason: str) -> bool:
        """Check if extension reason is valid."""
        valid_reasons = [
            "litigation",
            "audit",
            "investigation",
            "patient care",
            "research",
            "compliance",
        ]

        reason_lower = reason.lower()
        return any(valid in reason_lower for valid in valid_reasons)

    def _calculate_compliance_score(
        self, total_records: int, expired_not_disposed: int, overdue_count: int
    ) -> float:
        """Calculate compliance score."""
        if total_records == 0:
            return 100.0

        # Base score
        score = 100.0

        # Deduct for expired records not disposed
        if expired_not_disposed > 0:
            expired_percentage = (expired_not_disposed / total_records) * 100
            score -= min(expired_percentage * 2, 40)  # Max 40 point deduction

        # Deduct for overdue disposals
        if overdue_count > 0:
            overdue_percentage = (overdue_count / total_records) * 100
            score -= min(overdue_percentage * 3, 30)  # Max 30 point deduction

        return max(0, score)

    def _generate_compliance_recommendations(
        self, expired_count: int, overdue_list: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate compliance recommendations."""
        recommendations = []

        if expired_count > 100:
            recommendations.append(
                f"Schedule immediate disposal review for {expired_count} expired records"
            )

        if overdue_list:
            recommendations.append(
                f"Prioritize disposal of {len(overdue_list)} records overdue by 90+ days"
            )

        # Check for specific record types
        overdue_types = {}
        for record in overdue_list:
            record_type = record["record_type"]
            if record_type not in overdue_types:
                overdue_types[record_type] = 0
            overdue_types[record_type] += 1

        for record_type, count in overdue_types.items():
            if count > 10:
                recommendations.append(
                    f"Review retention process for {record_type} records ({count} overdue)"
                )

        if not recommendations:
            recommendations.append("Retention compliance is satisfactory")

        return recommendations

    def _generate_retention_id(self) -> str:
        """Generate unique retention ID."""
        return f"RET-{uuid.uuid4()}"

    def _generate_hold_id(self) -> str:
        """Generate unique hold ID."""
        return f"HOLD-{uuid.uuid4()}"

    def _generate_disposal_id(self) -> str:
        """Generate unique disposal ID."""
        return f"DISP-{uuid.uuid4()}"

    def _generate_extension_id(self) -> str:
        """Generate unique extension ID."""
        return f"EXT-{uuid.uuid4()}"
