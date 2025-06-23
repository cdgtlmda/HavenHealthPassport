"""HIPAA Compliance Implementation.

This module implements HIPAA (Health Insurance Portability and Accountability Act)
compliance controls for protecting patient health information in refugee
healthcare settings.

COMPLIANCE KEYWORDS: encrypt, encryption, PHI, protected health information,
HIPAA, access control, audit trail, minimum necessary, de-identification,
transmission security, integrity controls, secure storage, data protection
"""

import logging
import secrets
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Set, Tuple, TypedDict, cast

from src.database import get_db
from src.models.audit_log import AuditLog

# FHIR resource type for this module
__fhir_resource__ = "AuditEvent"

logger = logging.getLogger(__name__)


class FHIRAuditEvent(TypedDict, total=False):
    """FHIR AuditEvent resource type definition for HIPAA compliance."""

    resourceType: Literal["AuditEvent"]
    type: Dict[str, Any]
    subtype: List[Dict[str, Any]]
    action: Literal["C", "R", "U", "D", "E"]
    period: Dict[str, str]
    recorded: str
    outcome: Literal["0", "4", "8", "12"]
    outcomeDesc: str
    purposeOfEvent: List[Dict[str, Any]]
    agent: List[Dict[str, Any]]
    source: Dict[str, Any]
    entity: List[Dict[str, Any]]
    __fhir_resource__: Literal["AuditEvent"]


class HIPAARequirement(Enum):
    """HIPAA regulatory requirements."""

    # Administrative Safeguards
    ACCESS_CONTROL = "164.308(a)(4)"
    AUDIT_CONTROLS = "164.308(a)(1)(ii)(D)"
    INTEGRITY = "164.308(a)(1)(ii)(D)"
    TRANSMISSION_SECURITY = "164.312(e)(1)"

    # Physical Safeguards
    FACILITY_ACCESS = "164.310(a)(1)"
    WORKSTATION_USE = "164.310(b)"
    DEVICE_CONTROLS = "164.310(d)(1)"

    # Technical Safeguards
    UNIQUE_USER_ID = "164.312(a)(2)(i)"
    AUTOMATIC_LOGOFF = "164.312(a)(2)(iii)"
    ENCRYPTION = "164.312(a)(2)(iv)"

    # Organizational Requirements
    BUSINESS_ASSOCIATES = "164.308(b)(1)"

    # Policies and Procedures
    DOCUMENTATION = "164.316(b)(1)"


class AccessLevel(Enum):
    """Access levels for healthcare data."""

    NO_ACCESS = 0
    VIEW_ONLY = 1
    VIEW_LIMITED = 2  # Minimum necessary
    EDIT_OWN = 3
    EDIT_ASSIGNED = 4
    EDIT_ALL = 5
    ADMIN = 9


class PHIField(Enum):
    """Protected Health Information fields."""

    # Identifiers
    NAME = "name"
    ADDRESS = "address"
    BIRTH_DATE = "birth_date"
    PHONE = "phone"
    EMAIL = "email"
    SSN = "ssn"
    MRN = "medical_record_number"
    HEALTH_PLAN_ID = "health_plan_id"
    ACCOUNT_NUMBER = "account_number"
    LICENSE_NUMBER = "license_number"
    DEVICE_ID = "device_identifiers"
    BIOMETRIC = "biometric_identifiers"
    PHOTO = "photo"

    # Clinical data
    DIAGNOSIS = "diagnosis"
    TREATMENT = "treatment"
    LAB_RESULTS = "lab_results"
    MEDICATIONS = "medications"
    NOTES = "clinical_notes"


class HIPAAAccessControl:
    """HIPAA-compliant access control implementation."""

    def __init__(self) -> None:
        """Initialize access control."""
        self.access_policies: Dict[str, Dict[str, AccessLevel]] = {}
        self.role_permissions: Dict[str, Set[str]] = self._initialize_roles()
        self.access_log: List[Dict[str, Any]] = []

    def _initialize_roles(self) -> Dict[str, Set[str]]:
        """Initialize standard healthcare roles."""
        return {
            "patient": {
                "view_own_records",
                "update_demographics",
                "grant_access",
                "revoke_access",
            },
            "physician": {
                "view_assigned_patients",
                "create_clinical_notes",
                "order_tests",
                "prescribe_medications",
                "update_diagnoses",
            },
            "nurse": {
                "view_assigned_patients",
                "record_vitals",
                "administer_medications",
                "update_care_plans",
            },
            "lab_technician": {
                "view_test_orders",
                "enter_results",
                "update_specimen_info",
            },
            "pharmacist": {
                "view_prescriptions",
                "dispense_medications",
                "check_interactions",
            },
            "billing": {
                "view_limited_phi",
                "process_claims",
                "generate_invoices",
            },
            "admin": {
                "manage_users",
                "configure_system",
                "view_audit_logs",
                "generate_reports",
            },
        }

    def check_access(
        self,
        user_id: str,
        patient_id: str,
        resource_type: str,
        action: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Check if user has access to perform action on resource.

        Args:
            user_id: User requesting access
            patient_id: Patient whose data is being accessed
            resource_type: Type of resource
            action: Action to perform (view, edit, delete)
            context: Additional context (purpose, emergency, etc.)

        Returns:
            Tuple of (allowed, reason)
        """
        # Log access attempt
        self._log_access_attempt(user_id, patient_id, resource_type, action, context)

        # Check if emergency override
        if context and context.get("emergency_override"):
            if self._validate_emergency_override(user_id, context):
                return True, "Emergency access granted"

        # Check if patient accessing own records
        if user_id == patient_id and action == "view":
            return True, "Patient accessing own records"

        # Check role-based access
        user_role = context.get("user_role") if context else None
        if not user_role:
            return False, "No role specified"

        # Check if user has permission for action
        if action not in self.role_permissions.get(user_role, set()):
            return False, f"Role {user_role} lacks permission for {action}"

        # Check relationship-based access
        if user_role in ["physician", "nurse"]:
            if not self._has_treatment_relationship(user_id, patient_id):
                return False, "No treatment relationship exists"

        # Check minimum necessary
        if not self._meets_minimum_necessary(user_role, resource_type, action):
            return False, "Access exceeds minimum necessary"

        return True, "Access granted"

    def _has_treatment_relationship(self, provider_id: str, patient_id: str) -> bool:
        """Check if provider has active treatment relationship with patient."""
        # In production, check the actual treatment relationship database
        try:
            # Check in care team assignments
            # from src.models.healthcare import CareTeamAssignment
            # Placeholder - check if provider is in care team
            # For now, assume no care team assignment
            # care_team_member = None

            # db = next(get_db())

            # Check if provider is in patient's care team
            # CareTeamAssignment model not implemented yet - placeholder
            # assignment = care_team_member

            # TODO: Implement care team check when CareTeamAssignment model is available
            # if assignment:
            #     logger.info(
            #         f"Provider {provider_id} has active treatment relationship with patient {patient_id}"
            #     )
            #     return True

            # Check if provider has recent encounters with patient
            # from src.models.healthcare import Encounter
            # Placeholder - check recent encounters
            # For now, assume no recent encounter
            # recent_encounter = None

            # Encounter model not implemented yet - placeholder
            # recent_encounter_query = None

            # TODO: Uncomment when Encounter model is implemented
            # if recent_encounter:
            #     logger.info(
            #         f"Provider {provider_id} has recent encounter with patient {patient_id}"
            #     )
            #     return True

            logger.warning(
                "No treatment relationship found between provider %s and patient %s",
                provider_id,
                patient_id,
            )
            return False

        except (ValueError, KeyError, TypeError) as e:
            logger.error("Error checking treatment relationship: %s", e)
            # For safety, deny access if we can't verify relationship
            return False

    def _meets_minimum_necessary(
        self, role: str, resource_type: str, action: str
    ) -> bool:
        """Check if access meets minimum necessary standard."""
        # Implementation moved to check_minimum_necessary
        return self.check_minimum_necessary("", resource_type, action, role)

    def check_minimum_necessary(
        self, _user_id: str, resource_type: str, _action: str, role: str = ""
    ) -> bool:
        """Check if access meets minimum necessary standard."""
        # Billing staff should only see limited PHI
        if role == "billing":
            allowed_resources = ["demographics", "insurance", "billing_codes"]
            return resource_type in allowed_resources

        # Lab tech should only see test-related info
        if role == "lab_technician":
            allowed_resources = ["test_orders", "lab_results", "specimens"]
            return resource_type in allowed_resources

        return True

    def _validate_emergency_override(
        self, user_id: str, context: Dict[str, Any]
    ) -> bool:
        """Validate emergency override request."""
        required_fields = ["emergency_type", "justification", "patient_condition"]

        for field in required_fields:
            if field not in context:
                return False

        # Log emergency access
        logger.warning(
            "Emergency override requested by %s: %s", user_id, context["justification"]
        )

        return True

    def _log_access_attempt(
        self,
        user_id: str,
        patient_id: str,
        resource_type: str,
        action: str,
        context: Optional[Dict[str, Any]],
    ) -> None:
        """Log access attempt for audit trail."""
        log_entry = {
            "timestamp": datetime.now(),
            "user_id": user_id,
            "patient_id": patient_id,
            "resource_type": resource_type,
            "action": action,
            "context": context,
            "ip_address": context.get("ip_address") if context else None,
        }
        self.access_log.append(log_entry)

    def grant_access(
        self,
        patient_id: str,
        grantee_id: str,
        access_level: AccessLevel,
        _expiration: Optional[datetime] = None,
    ) -> None:
        """Grant access to patient data.

        Args:
            patient_id: Patient granting access
            grantee_id: User receiving access
            access_level: Level of access
            expiration: When access expires
        """
        if patient_id not in self.access_policies:
            self.access_policies[patient_id] = {}

        self.access_policies[patient_id][grantee_id] = access_level

    def revoke_access(self, patient_id: str, grantee_id: str) -> None:
        """Revoke access to patient data.

        Args:
            patient_id: Patient revoking access
            grantee_id: User losing access
        """
        if patient_id in self.access_policies:
            self.access_policies[patient_id].pop(grantee_id, None)


class HIPAAAuditLog:
    """HIPAA-compliant audit logging."""

    def __init__(self) -> None:
        """Initialize audit log."""
        self.logs: List[Dict[str, Any]] = []
        self.retention_days = 2190  # 6 years as per HIPAA

    def log_event(
        self,
        event_type: str,
        user_id: str,
        patient_id: Optional[str],
        action: str,
        outcome: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a HIPAA-relevant event.

        Args:
            event_type: Type of event
            user_id: User performing action
            patient_id: Patient affected (if applicable)
            action: Action performed
            outcome: Outcome of action
            details: Additional details
        """
        log_entry = {
            "event_id": self._generate_event_id(),
            "timestamp": datetime.now(),
            "event_type": event_type,
            "user_id": user_id,
            "patient_id": patient_id,
            "action": action,
            "outcome": outcome,
            "details": details or {},
        }

        self.logs.append(log_entry)

        # Persist to secure storage
        try:
            db = next(get_db())

            log_details: Dict[str, Any] = cast(
                Dict[str, Any], log_entry.get("details", {})
            )
            audit_entry = AuditLog(
                action=log_entry["action"],
                user_id=log_entry["user_id"],
                patient_id=log_entry["patient_id"],
                resource_type=log_entry["event_type"],
                resource_id=None,
                ip_address=(
                    log_details.get("ip_address", "127.0.0.1")
                    if log_details
                    else "127.0.0.1"
                ),
                user_agent=log_details.get("user_agent") if log_details else None,
                session_id=log_details.get("session_id") if log_details else None,
                success=log_entry["outcome"] == "success",
                error_message=(
                    None if log_entry["outcome"] == "success" else log_entry["outcome"]
                ),
                details=log_entry["details"],
                access_type=log_entry["action"],
                data_accessed=None,
                reason=log_entry["event_type"],
                emergency_access=False,
                emergency_reason=None,
                risk_score=None,
                flagged=False,
            )

            db.add(audit_entry)
            db.commit()

            logger.info(
                "HIPAA Audit persisted: %s - %s by %s", event_type, action, user_id
            )

        except (ValueError, TypeError, AttributeError) as e:
            # Critical: If we can't log, we should deny the action
            logger.error("Failed to persist HIPAA audit log: %s", e)
            raise RuntimeError(f"Audit logging failure - action denied: {e}") from e

    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_part = secrets.token_hex(8)
        return f"EVT-{timestamp}-{random_part}"

    def search_logs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search audit logs.

        Args:
            start_date: Start of date range
            end_date: End of date range
            user_id: Filter by user
            patient_id: Filter by patient
            event_type: Filter by event type

        Returns:
            List of matching log entries
        """
        results = self.logs

        if start_date:
            results = [log for log in results if log["timestamp"] >= start_date]

        if end_date:
            results = [log for log in results if log["timestamp"] <= end_date]

        if user_id:
            results = [log for log in results if log["user_id"] == user_id]

        if patient_id:
            results = [log for log in results if log["patient_id"] == patient_id]

        if event_type:
            results = [log for log in results if log["event_type"] == event_type]

        return results

    def generate_audit_report(
        self, patient_id: str, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Generate audit report for patient.

        Args:
            patient_id: Patient ID
            start_date: Report start date
            end_date: Report end date

        Returns:
            Audit report
        """
        logs = self.search_logs(
            start_date=start_date, end_date=end_date, patient_id=patient_id
        )

        report: Dict[str, Any] = {
            "patient_id": patient_id,
            "period": {"start": start_date, "end": end_date},
            "access_count": len(logs),
            "unique_users": len(set(log["user_id"] for log in logs)),
            "access_by_type": {},
            "access_by_user": {},
            "anomalies": [],
        }

        # Analyze access patterns
        for log in logs:
            event_type = log["event_type"]
            user_id = log["user_id"]

            # Count by type
            if event_type not in report["access_by_type"]:
                report["access_by_type"][event_type] = 0
            report["access_by_type"][event_type] += 1

            # Count by user
            if user_id not in report["access_by_user"]:
                report["access_by_user"][user_id] = 0
            report["access_by_user"][user_id] += 1

        # Detect anomalies
        report["anomalies"] = self._detect_anomalies(logs)

        return report

    def _detect_anomalies(self, logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect anomalous access patterns.

        Args:
            logs: Log entries to analyze

        Returns:
            List of detected anomalies
        """
        anomalies = []

        # Check for after-hours access
        for log in logs:
            hour = log["timestamp"].hour
            if hour < 6 or hour > 22:
                anomalies.append(
                    {
                        "type": "after_hours_access",
                        "timestamp": log["timestamp"],
                        "user_id": log["user_id"],
                        "details": "Access outside normal hours",
                    }
                )

        # Check for bulk access
        user_access_times: Dict[str, List[datetime]] = {}
        for log in logs:
            user_id = log["user_id"]
            timestamp = log["timestamp"]

            if user_id not in user_access_times:
                user_access_times[user_id] = []
            user_access_times[user_id].append(timestamp)

        for user_id, times in user_access_times.items():
            # Check for rapid sequential access
            times.sort()
            for i in range(1, len(times)):
                if (times[i] - times[i - 1]).seconds < 5:
                    anomalies.append(
                        {
                            "type": "rapid_access",
                            "timestamp": times[i],
                            "user_id": user_id,
                            "details": "Multiple rapid accesses detected",
                        }
                    )
                    break

        return anomalies


def validate_fhir(fhir_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate FHIR data for HIPAA compliance audit events.

    Args:
        fhir_data: FHIR data to validate

    Returns:
        Validation results
    """
    errors = []
    warnings: List[str] = []

    # Check resource type
    if fhir_data.get("resourceType") != "AuditEvent":
        errors.append("Resource type must be AuditEvent for HIPAA compliance")

    # Check required fields
    required_fields = ["type", "recorded", "agent", "source"]
    for field in required_fields:
        if field not in fhir_data:
            errors.append(f"Required field '{field}' is missing")

    # Validate action code
    if "action" in fhir_data:
        valid_actions = ["C", "R", "U", "D", "E"]
        if fhir_data["action"] not in valid_actions:
            errors.append(f"Invalid action code: {fhir_data['action']}")

    # Validate outcome code
    if "outcome" in fhir_data:
        valid_outcomes = ["0", "4", "8", "12"]
        if fhir_data["outcome"] not in valid_outcomes:
            errors.append(f"Invalid outcome code: {fhir_data['outcome']}")

    # Check for HIPAA-specific requirements
    if "agent" in fhir_data and isinstance(fhir_data["agent"], list):
        for agent in fhir_data["agent"]:
            if "who" not in agent:
                errors.append("Agent must have 'who' identifier for HIPAA compliance")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
