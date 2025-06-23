"""
Audit Logging Module.

This module provides audit logging functionality for the Haven Health Passport system.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events in the system."""

    DOCUMENT_ENHANCED = "document_enhanced"
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_ACCESSED = "document_accessed"
    DOCUMENT_CLASSIFIED = "document_classified"
    TRANSLATION_PERFORMED = "translation_performed"
    VOICE_PROCESSED = "voice_processed"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    PERMISSION_CHANGED = "permission_changed"
    DATA_EXPORTED = "data_exported"
    DATA_DELETED = "data_deleted"
    SECURITY_EVENT = "security_event"
    ERROR_OCCURRED = "error_occurred"
    # Voice privacy events
    CONSENT_REQUESTED = "consent_requested"
    CONSENT_GRANTED = "consent_granted"
    CONSENT_WITHDRAWN = "consent_withdrawn"
    PRIVACY_SETTINGS_UPDATED = "privacy_settings_updated"
    DATA_ANONYMIZED = "data_anonymized"
    DATA_ACCESSED = "data_accessed"
    DATA_SHARED = "data_shared"
    # Retention events
    RETENTION_POLICY_APPLIED = "retention_policy_applied"
    DATA_ARCHIVED = "data_archived"
    DELETION_SCHEDULED = "deletion_scheduled"
    DATA_RESTORED = "data_restored"
    # Access management events
    USER_CREATED = "user_created"
    ROLE_ASSIGNED = "role_assigned"
    RESOURCE_ACCESS = "resource_access"
    ACCESS_REQUESTED = "access_requested"
    ACCESS_APPROVED = "access_approved"
    ACCESS_REVIEW_COMPLETED = "access_review_completed"
    LOGIN_FAILED = "login_failed"
    BREAK_GLASS_ACCESS = "break_glass_access"


class AuditLogger:
    """Handles audit logging for security and compliance."""

    def __init__(self) -> None:
        """Initialize the audit logger."""
        self.audit_logs: List[Dict[str, Any]] = []

    async def log_event(
        self,
        event_type: AuditEventType,
        details: Dict[str, Any],
        user_id: Optional[str] = None,
        patient_id: Optional[str] = None,
    ) -> None:
        """
        Log an audit event asynchronously.

        Args:
            event_type: Type of audit event
            details: Event details as a dictionary
            user_id: Optional user ID associated with the event
            patient_id: Optional patient ID associated with the event
        """
        timestamp = datetime.utcnow()

        audit_entry = {
            "timestamp": timestamp.isoformat(),
            "event_type": event_type.value,
            "details": details,
            "user_id": user_id,
            "patient_id": patient_id,
        }

        self.audit_logs.append(audit_entry)
        logger.info("Audit event logged: %s", event_type.value)

        # In a real implementation, this would persist to a database
        # For now, we just store in memory

    def log_event_sync(
        self,
        event_type: AuditEventType,
        details: Dict[str, Any],
        user_id: Optional[str] = None,
        patient_id: Optional[str] = None,
    ) -> None:
        """
        Log an audit event synchronously.

        Args:
            event_type: Type of audit event
            details: Event details as a dictionary
            user_id: Optional user ID associated with the event
            patient_id: Optional patient ID associated with the event
        """
        timestamp = datetime.utcnow()

        audit_entry = {
            "timestamp": timestamp.isoformat(),
            "event_type": event_type.value,
            "details": details,
            "user_id": user_id,
            "patient_id": patient_id,
        }

        self.audit_logs.append(audit_entry)
        logger.info("Audit event logged: %s", event_type.value)

    def get_audit_logs(
        self,
        event_type: Optional[AuditEventType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list:
        """
        Retrieve audit logs with optional filtering.

        Args:
            event_type: Filter by event type
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            List of audit log entries
        """
        logs = self.audit_logs

        if event_type:
            logs = [log for log in logs if log["event_type"] == event_type.value]

        if start_date:
            logs = [
                log
                for log in logs
                if datetime.fromisoformat(log["timestamp"]) >= start_date
            ]

        if end_date:
            logs = [
                log
                for log in logs
                if datetime.fromisoformat(log["timestamp"]) <= end_date
            ]

        return logs
