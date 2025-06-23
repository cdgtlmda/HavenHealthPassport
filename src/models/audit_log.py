"""
Audit Log Model for HIPAA Compliance.

This model tracks all system actions for security and compliance auditing.
Critical for healthcare system compliance.
All FHIR Resource access and modifications are logged for audit.
Includes validation tracking for FHIR compliance checks.
"""

from enum import Enum
from typing import Any, Dict

from sqlalchemy import Boolean, Column, Index, Integer, String, Text

from src.models.base import BaseModel
from src.models.db_types import JSONB, UUID


class AuditAction(Enum):
    """Types of audit actions in the system."""

    # User actions
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"

    # Patient actions
    PATIENT_CREATED = "patient_created"
    PATIENT_UPDATED = "patient_updated"
    PATIENT_DELETED = "patient_deleted"
    PATIENT_ACCESSED = "patient_accessed"
    PATIENT_SEARCH = "patient_search"

    # Record actions
    RECORD_CREATED = "record_created"
    RECORD_UPDATED = "record_updated"
    RECORD_DELETED = "record_deleted"
    RECORD_ACCESSED = "record_accessed"
    RECORD_SHARED = "record_shared"

    # Document actions
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_ACCESSED = "document_accessed"
    DOCUMENT_DOWNLOADED = "document_downloaded"
    DOCUMENT_DELETED = "document_deleted"
    DOCUMENT_ENHANCED = "document_enhanced"
    DOCUMENT_CLASSIFIED = "document_classified"

    # File actions
    FILE_UPLOADED = "file_uploaded"
    FILE_DOWNLOADED = "file_downloaded"
    FILE_DELETED = "file_deleted"

    # Translation actions
    TRANSLATION_PERFORMED = "translation_performed"
    VOICE_PROCESSED = "voice_processed"

    # Permission actions
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    PERMISSION_CHANGED = "permission_changed"

    # Emergency actions
    EMERGENCY_ACCESS = "emergency_access"
    EMERGENCY_OVERRIDE = "emergency_override"

    # Security actions
    SECURITY_EVENT = "security_event"
    ACCESS_DENIED = "access_denied"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"

    # Data actions
    DATA_EXPORTED = "data_exported"
    DATA_IMPORTED = "data_imported"
    DATA_DELETED = "data_deleted"
    DATA_ANONYMIZED = "data_anonymized"
    DATA_ACCESSED = "data_accessed"
    DATA_SHARED = "data_shared"
    DATA_ARCHIVED = "data_archived"
    DATA_RESTORED = "data_restored"

    # PHI Encryption actions
    PHI_ENCRYPTION = "phi_encryption"
    PHI_DECRYPTION = "phi_decryption"
    KEY_ROTATION = "key_rotation"

    # Consent actions
    CONSENT_REQUESTED = "consent_requested"
    CONSENT_GRANTED = "consent_granted"
    CONSENT_WITHDRAWN = "consent_withdrawn"

    # Privacy actions
    PRIVACY_SETTINGS_UPDATED = "privacy_settings_updated"

    # Retention actions
    RETENTION_POLICY_APPLIED = "retention_policy_applied"
    DELETION_SCHEDULED = "deletion_scheduled"

    # Configuration actions
    CONFIG_CHANGED = "config_changed"

    # API actions
    API_CALLED = "api_called"

    # Error actions
    ERROR_OCCURRED = "error_occurred"


class AuditLog(BaseModel):
    """
    Comprehensive audit log for HIPAA compliance.

    Tracks all system actions with full context for security auditing.
    Retention: 7 years (2555 days) for HIPAA compliance.
    """

    __tablename__ = "audit_logs"

    # Core audit fields
    action = Column(String(100), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), index=True)  # type: ignore[var-annotated]
    patient_id = Column(UUID(as_uuid=True), index=True)  # type: ignore[var-annotated]

    # Resource identification
    resource_type = Column(String(100), index=True)
    resource_id = Column(UUID(as_uuid=True), index=True)  # type: ignore[var-annotated]

    # Request context
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(Text)
    session_id = Column(String(255))

    # Action details
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text)
    details = Column(JSONB, default=dict)

    # HIPAA required fields
    access_type = Column(String(50))  # read, write, delete, execute
    data_accessed = Column(JSONB)  # What PHI was accessed
    reason = Column(Text)  # Reason for access

    # Emergency access tracking
    emergency_access = Column(Boolean, default=False)
    emergency_reason = Column(Text)

    # Additional security context
    risk_score = Column(Integer)  # 0-100 risk assessment
    flagged = Column(Boolean, default=False)

    # Create indexes for performance
    __table_args__ = (
        Index("idx_audit_timestamp_action", "created_at", "action"),
        Index("idx_audit_user_timestamp", "user_id", "created_at"),
        Index("idx_audit_patient_timestamp", "patient_id", "created_at"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
    )

    def __repr__(self) -> str:
        """Return string representation of AuditLog."""
        return f"<AuditLog(action={self.action}, user={self.user_id}, success={self.success})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "action": self.action,
            "user_id": str(self.user_id) if self.user_id else None,
            "patient_id": str(self.patient_id) if self.patient_id else None,
            "resource_type": self.resource_type,
            "resource_id": str(self.resource_id) if self.resource_id else None,
            "ip_address": self.ip_address,
            "success": self.success,
            "error_message": self.error_message,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "emergency_access": self.emergency_access,
            "risk_score": self.risk_score,
            "flagged": self.flagged,
        }

    def validate(self) -> bool:
        """Validate audit log entry for FHIR Resource compliance."""
        # Validate required fields
        if not self.action or not self.ip_address:
            return False

        # Validate FHIR resource tracking if applicable
        if self.resource_type and "FHIR" in self.resource_type:
            if not self.resource_id:
                return False

        return True
