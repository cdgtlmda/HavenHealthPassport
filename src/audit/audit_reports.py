"""
Audit Report Generator for Compliance Reporting.

Generates HIPAA-compliant audit reports for certification.
All PHI data is encrypted and access is controlled through role-based permissions.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from src.audit.audit_service import AuditEventType, AuditLog


class AuditReportGenerator:
    """Generate compliance audit reports."""

    def __init__(self, session: Session):
        """Initialize report generator with database session."""
        self.session = session

    def generate_access_report(
        self, start_date: datetime, end_date: datetime, patient_id: Optional[str] = None
    ) -> pd.DataFrame:
        """Generate patient access report for HIPAA compliance."""
        query = self.session.query(AuditLog).filter(
            and_(
                AuditLog.timestamp >= start_date,
                AuditLog.timestamp <= end_date,
                AuditLog.event_type.in_(
                    [
                        AuditEventType.PATIENT_ACCESS.value,
                        AuditEventType.OBSERVATION_ACCESS.value,
                        AuditEventType.MEDICATION_ACCESS.value,
                    ]
                ),
            )
        )

        if patient_id:
            query = query.filter(AuditLog.patient_id == patient_id)

        results = query.all()

        # Convert to DataFrame
        data = []
        for log in results:
            data.append(
                {
                    "timestamp": log.timestamp,
                    "user_id": log.user_id,
                    "patient_id": log.patient_id,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "ip_address": log.ip_address,
                    "outcome": "Success" if log.outcome else "Failed",
                }
            )

        return pd.DataFrame(data)

    def generate_user_activity_report(
        self, start_date: datetime, end_date: datetime, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate user activity summary report."""
        query = (
            self.session.query(
                AuditLog.user_id,
                AuditLog.event_type,
                func.count(AuditLog.id).label("count"),  # pylint: disable=not-callable
                func.count(
                    func.distinct(AuditLog.patient_id)
                ).label(  # pylint: disable=not-callable
                    "unique_patients"
                ),
            )
            .filter(
                and_(AuditLog.timestamp >= start_date, AuditLog.timestamp <= end_date)
            )
            .group_by(AuditLog.user_id, AuditLog.event_type)
        )

        if user_id:
            query = query.filter(AuditLog.user_id == user_id)

        results = query.all()

        # Organize by user
        report: Dict[str, Dict[str, Any]] = {}
        for row in results:
            if row.user_id not in report:
                report[row.user_id] = {
                    "total_actions": 0,
                    "unique_patients_accessed": 0,
                    "actions_by_type": {},
                }

            report[row.user_id]["total_actions"] += row.count
            report[row.user_id]["unique_patients_accessed"] = max(
                report[row.user_id]["unique_patients_accessed"], row.unique_patients
            )
            report[row.user_id]["actions_by_type"][row.event_type] = row.count

        return report

    def generate_failed_access_report(
        self, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Generate report of failed access attempts."""
        failed_attempts = (
            self.session.query(AuditLog)
            .filter(
                and_(
                    AuditLog.timestamp >= start_date,
                    AuditLog.timestamp <= end_date,
                    AuditLog.outcome.is_(False),
                )
            )
            .order_by(AuditLog.timestamp.desc())
            .all()
        )

        return [
            {
                "timestamp": log.timestamp.isoformat(),
                "user_id": log.user_id,
                "event_type": log.event_type,
                "resource_attempted": f"{log.resource_type}/{log.resource_id}",
                "ip_address": log.ip_address,
                "error_message": log.error_message,
            }
            for log in failed_attempts
        ]
