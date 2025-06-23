"""Access log database model for audit trails.

This model tracks access to patient health records and other FHIR Resources
for compliance and security auditing. Handles FHIR AuditEvent Resource validation.
"""

import enum
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Session, relationship

from src.models.db_types import INET, JSONB, UUID

from .base import BaseModel

if TYPE_CHECKING:
    from src.healthcare.fhir_validator import FHIRValidator  # noqa: F401

# FHIR resource type for this model
__fhir_resource__ = "AuditEvent"


class AccessType(enum.Enum):
    """Type of access to the system."""

    VIEW = "view"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    EXPORT = "export"
    PRINT = "print"
    SHARE = "share"
    EMERGENCY = "emergency"
    AUDIT = "audit"
    SYNC = "sync"


class AccessResult(enum.Enum):
    """Result of the access attempt."""

    SUCCESS = "success"
    DENIED = "denied"
    ERROR = "error"
    PARTIAL = "partial"
    TIMEOUT = "timeout"


class AccessContext(enum.Enum):
    """Context in which access occurred."""

    WEB_PORTAL = "web_portal"
    MOBILE_APP = "mobile_app"
    API = "api"
    EMERGENCY_SYSTEM = "emergency_system"
    SYNC_SERVICE = "sync_service"
    ADMIN_CONSOLE = "admin_console"
    INTEGRATION = "integration"


class AccessLog(BaseModel):
    """Access log model for tracking all data access."""

    __tablename__ = "access_logs"

    # Initialize FHIR validator lazily to avoid circular imports
    _validator = None

    @classmethod
    def get_validator(cls) -> "FHIRValidator":
        """Get FHIR validator instance (lazy initialization)."""
        if cls._validator is None:
            from src.healthcare.fhir_validator import (  # pylint: disable=import-outside-toplevel # noqa: F811
                FHIRValidator,
            )

            cls._validator = FHIRValidator()
        return cls._validator

    # Access Subject (who is accessing)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # type: ignore[var-annotated]
    user_name = Column(String(200))
    user_role = Column(String(50))
    organization_id = Column(UUID(as_uuid=True))  # type: ignore[var-annotated]
    organization_name = Column(String(200))

    # Access Object (what is being accessed)
    patient_id = Column(  # type: ignore[var-annotated]
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), index=True
    )
    resource_type = Column(
        String(50), nullable=False
    )  # patient, health_record, verification, etc.
    resource_id = Column(UUID(as_uuid=True), index=True)  # type: ignore[var-annotated]
    resource_details = Column(
        JSONB, default=dict
    )  # Additional details about the resource

    # Access Details
    access_type = Column(Enum(AccessType), nullable=False)  # type: ignore[var-annotated]
    access_context = Column(Enum(AccessContext), nullable=False)  # type: ignore[var-annotated]
    access_result = Column(  # type: ignore[var-annotated]
        Enum(AccessResult), nullable=False, default=AccessResult.SUCCESS
    )
    access_timestamp = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )

    # Purpose and Justification
    purpose_of_access = Column(String(255), nullable=False)
    access_justification = Column(Text)
    emergency_override = Column(Boolean, default=False)
    consent_reference = Column(String(255))  # Reference to consent document

    # Request Details
    request_id = Column(  # type: ignore[var-annotated]
        UUID(as_uuid=True), default=uuid.uuid4
    )  # Unique request identifier
    request_method = Column(String(10))  # GET, POST, etc.
    request_path = Column(String(500))  # API endpoint or resource path
    query_parameters = Column(JSONB, default=dict)
    request_headers = Column(JSONB, default=dict)  # Sanitized headers

    # Response Details
    response_status_code = Column(Integer)
    response_size_bytes = Column(Integer)
    response_time_ms = Column(Integer)
    data_returned = Column(
        JSONB, default=dict
    )  # Summary of data returned (not actual data)
    fields_accessed = Column(JSONB, default=list)  # Which fields were accessed

    # Security Context
    ip_address = Column(INET)  # PostgreSQL INET type for IP addresses
    user_agent = Column(String(500))
    device_id = Column(String(255))
    device_type = Column(String(50))  # mobile, desktop, tablet, etc.
    location_country = Column(String(2))  # ISO country code
    location_region = Column(String(100))

    # Authentication Details
    auth_method = Column(String(50))  # password, oauth, mfa, biometric, etc.
    mfa_used = Column(Boolean, default=False)
    session_id = Column(String(255))
    api_key_id = Column(String(255))

    # Data Sharing and Export
    shared_with_organization = Column(String(200))
    export_format = Column(String(20))  # json, pdf, csv, etc.
    export_destination = Column(String(255))  # email, system, etc.

    # Compliance and Audit
    compliance_check_passed = Column(Boolean, default=True)
    compliance_failures = Column(JSONB, default=list)
    requires_review = Column(Boolean, default=False)
    reviewed_by = Column(UUID(as_uuid=True))  # type: ignore[var-annotated]
    reviewed_at = Column(DateTime(timezone=True))
    review_notes = Column(Text)

    # Performance Metrics
    database_queries = Column(Integer, default=0)
    cache_hits = Column(Integer, default=0)
    cache_misses = Column(Integer, default=0)

    # Error Handling
    error_code = Column(String(50))
    error_message = Column(Text)
    stack_trace = Column(Text)  # Only stored in development

    # Retention Policy
    retention_days = Column(Integer, default=2555)  # 7 years default
    can_be_purged = Column(Boolean, default=True)

    # Relationships
    patient = relationship("Patient", back_populates="access_logs")

    # Indexes for performance
    __table_args__ = (
        Index("idx_access_log_user_time", "user_id", "access_timestamp"),
        Index("idx_access_log_patient_time", "patient_id", "access_timestamp"),
        Index("idx_access_log_resource", "resource_type", "resource_id"),
        Index("idx_access_log_result", "access_result"),
        Index("idx_access_log_emergency", "emergency_override"),
        Index("idx_access_log_review", "requires_review", "reviewed_by"),
    )

    @property
    def is_emergency_access(self) -> bool:
        """Check if this was emergency access."""
        return bool(
            self.emergency_override
            or self.access_context == AccessContext.EMERGENCY_SYSTEM
        )

    @property
    def is_suspicious(self) -> bool:
        """Check if this access appears suspicious."""
        suspicious_indicators = []

        # Multiple failed attempts
        if self.access_result in [AccessResult.DENIED, AccessResult.ERROR]:
            suspicious_indicators.append("failed_access")

        # Unusual time (e.g., outside business hours)
        hour = self.access_timestamp.hour
        if hour < 6 or hour > 22:
            suspicious_indicators.append("unusual_time")

        # High volume of data accessed
        if self.fields_accessed and len(self.fields_accessed) > 20:
            suspicious_indicators.append("high_volume")

        # Export of sensitive data
        if self.access_type == AccessType.EXPORT:
            suspicious_indicators.append("data_export")

        return len(suspicious_indicators) > 0

    def calculate_risk_score(self) -> int:
        """Calculate risk score for this access."""
        risk_score = 0

        # Access result risks
        if self.access_result == AccessResult.DENIED:
            risk_score += 20
        elif self.access_result == AccessResult.ERROR:
            risk_score += 10

        # Access type risks
        risk_by_type = {
            AccessType.DELETE: 30,
            AccessType.EXPORT: 25,
            AccessType.UPDATE: 15,
            AccessType.SHARE: 20,
            AccessType.EMERGENCY: 10,
            AccessType.VIEW: 5,
        }
        if isinstance(self.access_type, AccessType):
            risk_score += risk_by_type.get(self.access_type, 0)

        # Context risks
        if self.access_context == AccessContext.API:
            risk_score += 10

        # Time-based risks
        hour = self.access_timestamp.hour
        if hour < 6 or hour > 22:
            risk_score += 15

        # Weekend access
        if self.access_timestamp.weekday() in [5, 6]:
            risk_score += 10

        # Emergency override
        if self.emergency_override:
            risk_score += 20

        # No MFA
        if not self.mfa_used and self.access_type in [
            AccessType.UPDATE,
            AccessType.DELETE,
        ]:
            risk_score += 15

        return int(min(risk_score, 100))

    def flag_for_review(self, reason: str) -> None:
        """Flag this access log for manual review."""
        self.requires_review = True  # type: ignore[assignment]
        current_notes = self.review_notes or ""
        timestamp = datetime.utcnow().isoformat()
        if current_notes:
            self.review_notes = f"{current_notes}\n[FLAGGED] {timestamp}: {reason}"  # type: ignore[assignment]
        else:
            self.review_notes = f"[FLAGGED] {timestamp}: {reason}"  # type: ignore[assignment]

    @classmethod
    def log_access(
        cls,
        session: Session,
        user_id: uuid.UUID,
        resource_type: str,
        resource_id: uuid.UUID,
        access_type: AccessType,
        access_context: AccessContext,
        purpose: str,
        **kwargs: Any,
    ) -> "AccessLog":
        """Create a new access log entry."""
        log_entry = cls(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            access_type=access_type,
            access_context=access_context,
            purpose_of_access=purpose,
            **kwargs,
        )

        # Calculate risk score
        risk_score = log_entry.calculate_risk_score()
        if risk_score > 50:
            log_entry.flag_for_review(f"High risk score: {risk_score}")

        # Check if suspicious
        if log_entry.is_suspicious:
            log_entry.flag_for_review("Suspicious activity detected")

        session.add(log_entry)
        return log_entry

    @classmethod
    def get_user_activity(
        cls,
        session: Session,
        user_id: uuid.UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List["AccessLog"]:
        """Get activity logs for a specific user."""
        query = session.query(cls).filter(cls.user_id == user_id)

        if start_date:
            query = query.filter(cls.access_timestamp >= start_date)

        if end_date:
            query = query.filter(cls.access_timestamp <= end_date)

        return query.order_by(cls.access_timestamp.desc()).limit(limit).all()

    @classmethod
    def get_patient_access_history(
        cls,
        session: Session,
        patient_id: uuid.UUID,
        days_back: int = 30,
        access_types: Optional[List[AccessType]] = None,
    ) -> List["AccessLog"]:
        """Get access history for a specific patient."""
        start_date = datetime.utcnow() - timedelta(days=days_back)

        query = session.query(cls).filter(
            cls.patient_id == patient_id, cls.access_timestamp >= start_date
        )

        if access_types:
            query = query.filter(cls.access_type.in_(access_types))

        return query.order_by(cls.access_timestamp.desc()).all()

    @classmethod
    def get_emergency_access_logs(
        cls,
        session: Session,
        start_date: Optional[datetime] = None,
        unreviewed_only: bool = True,
    ) -> List["AccessLog"]:
        """Get emergency access logs for review."""
        query = session.query(cls).filter(cls.emergency_override.is_(True))

        if start_date:
            query = query.filter(cls.access_timestamp >= start_date)

        if unreviewed_only:
            query = query.filter(cls.reviewed_by.is_(None))

        return query.order_by(cls.access_timestamp.desc()).all()

    @classmethod
    def get_failed_access_attempts(
        cls, session: Session, user_id: Optional[uuid.UUID] = None, hours_back: int = 24
    ) -> List["AccessLog"]:
        """Get failed access attempts."""
        start_time = datetime.utcnow() - timedelta(hours=hours_back)

        query = session.query(cls).filter(
            cls.access_result.in_([AccessResult.DENIED, AccessResult.ERROR]),
            cls.access_timestamp >= start_time,
        )

        if user_id:
            query = query.filter(cls.user_id == user_id)

        return query.order_by(cls.access_timestamp.desc()).all()

    @classmethod
    def generate_compliance_report(
        cls,
        session: Session,
        start_date: datetime,
        end_date: datetime,
        organization_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Generate compliance report for access logs."""
        query = session.query(cls).filter(
            cls.access_timestamp >= start_date, cls.access_timestamp <= end_date
        )

        if organization_id:
            query = query.filter(cls.organization_id == organization_id)

        logs = query.all()

        access_by_type: Dict[str, int] = {}
        access_by_result: Dict[str, int] = {}
        unique_users: Set[str] = set()
        unique_patients: Set[str] = set()

        report: Dict[str, Any] = {
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "total_accesses": len(logs),
            "access_by_type": access_by_type,
            "access_by_result": access_by_result,
            "emergency_accesses": 0,
            "failed_accesses": 0,
            "exports": 0,
            "requires_review": 0,
            "average_response_time_ms": 0,
            "unique_users": unique_users,
            "unique_patients": unique_patients,
        }

        total_response_time: int = 0
        response_count: int = 0

        for log in logs:
            # Count by type
            access_type_value: str = log.access_type.value
            access_by_type[access_type_value] = (
                access_by_type.get(access_type_value, 0) + 1
            )

            # Count by result
            result: str = log.access_result.value
            access_by_result[result] = access_by_result.get(result, 0) + 1

            # Count special cases
            if bool(log.emergency_override):
                report["emergency_accesses"] += 1

            if log.access_result in [AccessResult.DENIED, AccessResult.ERROR]:
                report["failed_accesses"] += 1

            if log.access_type == AccessType.EXPORT:
                report["exports"] += 1

            if bool(log.requires_review):
                report["requires_review"] += 1

            # Response time
            if log.response_time_ms is not None:
                total_response_time += int(log.response_time_ms)
                response_count += 1

            # Unique counts
            unique_users.add(str(log.user_id))
            if log.patient_id:
                unique_patients.add(str(log.patient_id))

        # Calculate averages
        if response_count > 0:
            report["average_response_time_ms"] = total_response_time / response_count

        # Convert sets to counts
        report["unique_users"] = len(unique_users)
        report["unique_patients"] = len(unique_patients)

        return report

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<AccessLog(id={self.id}, user={self.user_id}, "
            f"type='{self.access_type.value}', result='{self.access_result.value}')>"
        )
