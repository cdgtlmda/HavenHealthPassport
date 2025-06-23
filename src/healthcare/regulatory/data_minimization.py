"""GDPR Data Minimization Implementation.

This module implements the data minimization principle from GDPR Article 5(1)(c),
ensuring that personal data processing is adequate, relevant, and limited to
what is necessary for the specified purposes.

All PHI data is handled with appropriate encryption and access control measures.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.healthcare.regulatory.consent_management import ConsentScope
from src.healthcare.regulatory.gdpr_compliance import ProcessingPurpose

logger = logging.getLogger(__name__)


class DataMinimizationLevel(Enum):
    """Levels of data minimization applied."""

    MINIMAL = "minimal"  # Only absolutely essential data
    STANDARD = "standard"  # Standard necessary data
    COMPREHENSIVE = "comprehensive"  # Full data for specific purposes
    RESEARCH = "research"  # Anonymized/pseudonymized for research


class DataField(Enum):
    """Individual data fields that can be collected."""

    # Basic identifiers
    FULL_NAME = "full_name"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    DATE_OF_BIRTH = "date_of_birth"
    AGE = "age"
    GENDER = "gender"

    # Contact information
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    EMERGENCY_CONTACT = "emergency_contact"

    # Identifiers
    NATIONAL_ID = "national_id"
    PASSPORT_NUMBER = "passport_number"
    MEDICAL_RECORD_NUMBER = "medical_record_number"
    INSURANCE_ID = "insurance_id"

    # Medical basics
    BLOOD_TYPE = "blood_type"
    ALLERGIES = "allergies"
    CURRENT_MEDICATIONS = "current_medications"
    MEDICAL_CONDITIONS = "medical_conditions"

    # Medical history
    PAST_DIAGNOSES = "past_diagnoses"
    SURGICAL_HISTORY = "surgical_history"
    FAMILY_HISTORY = "family_history"
    IMMUNIZATION_RECORDS = "immunization_records"

    # Clinical data
    VITAL_SIGNS = "vital_signs"
    LAB_RESULTS = "lab_results"
    IMAGING_RESULTS = "imaging_results"
    CLINICAL_NOTES = "clinical_notes"

    # Special categories
    GENETIC_DATA = "genetic_data"
    BIOMETRIC_DATA = "biometric_data"
    MENTAL_HEALTH_DATA = "mental_health_data"
    SEXUAL_HEALTH_DATA = "sexual_health_data"
    SUBSTANCE_USE_DATA = "substance_use_data"

    # Administrative
    APPOINTMENT_HISTORY = "appointment_history"
    BILLING_INFORMATION = "billing_information"
    INSURANCE_DETAILS = "insurance_details"
    CONSENT_RECORDS = "consent_records"

    # Demographics
    ETHNICITY = "ethnicity"
    LANGUAGE_PREFERENCE = "language_preference"
    RELIGION = "religion"
    MARITAL_STATUS = "marital_status"
    OCCUPATION = "occupation"

    # Location
    GPS_LOCATION = "gps_location"
    IP_ADDRESS = "ip_address"
    DEVICE_ID = "device_id"


class CollectionJustification(Enum):
    """Justifications for data collection."""

    LEGAL_REQUIREMENT = "legal_requirement"
    MEDICAL_NECESSITY = "medical_necessity"
    PATIENT_SAFETY = "patient_safety"
    EMERGENCY_CARE = "emergency_care"
    BILLING_PURPOSE = "billing_purpose"
    QUALITY_IMPROVEMENT = "quality_improvement"
    RESEARCH_PURPOSE = "research_purpose"
    PATIENT_REQUEST = "patient_request"
    CONTINUITY_OF_CARE = "continuity_of_care"


class DataMinimizationPolicy:
    """Policy defining data minimization rules."""

    def __init__(
        self,
        policy_id: str,
        name: str,
        purpose: ProcessingPurpose,
        level: DataMinimizationLevel,
        required_fields: Set[DataField],
        optional_fields: Set[DataField],
        prohibited_fields: Set[DataField],
        retention_days: int,
        justifications: Dict[DataField, CollectionJustification],
    ):
        """Initialize data minimization policy.

        Args:
            policy_id: Unique policy ID
            name: Policy name
            purpose: Processing purpose
            level: Minimization level
            required_fields: Fields that must be collected
            optional_fields: Fields that may be collected if needed
            prohibited_fields: Fields that must not be collected
            retention_days: How long to retain data
            justifications: Justification for each field
        """
        self.policy_id = policy_id
        self.name = name
        self.purpose = purpose
        self.level = level
        self.required_fields = required_fields
        self.optional_fields = optional_fields
        self.prohibited_fields = prohibited_fields
        self.retention_days = retention_days
        self.justifications = justifications
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def is_field_allowed(self, field: DataField) -> bool:
        """Check if field is allowed under this policy.

        Args:
            field: Data field to check

        Returns:
            Whether field is allowed
        """
        return field not in self.prohibited_fields

    def is_field_required(self, field: DataField) -> bool:
        """Check if field is required under this policy.

        Args:
            field: Data field to check

        Returns:
            Whether field is required
        """
        return field in self.required_fields

    def get_justification(self, field: DataField) -> Optional[CollectionJustification]:
        """Get justification for collecting field.

        Args:
            field: Data field

        Returns:
            Justification or None
        """
        return self.justifications.get(field)


class DataMinimizationManager:
    """Manages data minimization policies and enforcement."""

    def __init__(self) -> None:
        """Initialize data minimization manager."""
        self.policies: Dict[str, DataMinimizationPolicy] = {}
        self.purpose_policies: Dict[ProcessingPurpose, List[str]] = {}
        self.field_usage_log: List[Dict[str, Any]] = []
        self.minimization_audits: List[Dict[str, Any]] = []
        self._initialize_default_policies()

    def _initialize_default_policies(self) -> None:
        """Initialize default minimization policies."""
        # Emergency care policy - absolute minimum
        emergency_policy = DataMinimizationPolicy(
            policy_id="POL-EMRG-001",
            name="Emergency Care Minimization",
            purpose=ProcessingPurpose.EMERGENCY_CARE,
            level=DataMinimizationLevel.MINIMAL,
            required_fields={
                DataField.FIRST_NAME,
                DataField.LAST_NAME,
                DataField.AGE,
                DataField.BLOOD_TYPE,
                DataField.ALLERGIES,
                DataField.CURRENT_MEDICATIONS,
                DataField.EMERGENCY_CONTACT,
            },
            optional_fields={DataField.MEDICAL_CONDITIONS, DataField.INSURANCE_ID},
            prohibited_fields={
                DataField.GENETIC_DATA,
                DataField.MENTAL_HEALTH_DATA,
                DataField.SEXUAL_HEALTH_DATA,
                DataField.RELIGION,
                DataField.ETHNICITY,
            },
            retention_days=90,
            justifications={
                DataField.BLOOD_TYPE: CollectionJustification.EMERGENCY_CARE,
                DataField.ALLERGIES: CollectionJustification.PATIENT_SAFETY,
                DataField.CURRENT_MEDICATIONS: CollectionJustification.PATIENT_SAFETY,
            },
        )
        self.add_policy(emergency_policy)

        # Standard healthcare policy
        healthcare_policy = DataMinimizationPolicy(
            policy_id="POL-HC-001",
            name="Standard Healthcare Minimization",
            purpose=ProcessingPurpose.HEALTHCARE_PROVISION,
            level=DataMinimizationLevel.STANDARD,
            required_fields={
                DataField.FULL_NAME,
                DataField.DATE_OF_BIRTH,
                DataField.GENDER,
                DataField.PHONE,
                DataField.ADDRESS,
                DataField.MEDICAL_RECORD_NUMBER,
                DataField.ALLERGIES,
                DataField.CURRENT_MEDICATIONS,
                DataField.MEDICAL_CONDITIONS,
            },
            optional_fields={
                DataField.EMAIL,
                DataField.INSURANCE_ID,
                DataField.PAST_DIAGNOSES,
                DataField.FAMILY_HISTORY,
                DataField.LAB_RESULTS,
                DataField.VITAL_SIGNS,
            },
            prohibited_fields={
                DataField.GENETIC_DATA,  # Unless specifically consented
                DataField.GPS_LOCATION,
                DataField.IP_ADDRESS,
                DataField.DEVICE_ID,
            },
            retention_days=3650,  # 10 years
            justifications={
                DataField.FULL_NAME: CollectionJustification.LEGAL_REQUIREMENT,
                DataField.DATE_OF_BIRTH: CollectionJustification.MEDICAL_NECESSITY,
                DataField.MEDICAL_CONDITIONS: CollectionJustification.CONTINUITY_OF_CARE,
            },
        )
        self.add_policy(healthcare_policy)

        # Research policy - anonymized data
        research_policy = DataMinimizationPolicy(
            policy_id="POL-RES-001",
            name="Research Data Minimization",
            purpose=ProcessingPurpose.MEDICAL_RESEARCH,
            level=DataMinimizationLevel.RESEARCH,
            required_fields={
                DataField.AGE,  # Not date of birth
                DataField.GENDER,
                DataField.MEDICAL_CONDITIONS,
                DataField.LAB_RESULTS,
            },
            optional_fields={
                DataField.ETHNICITY,  # If relevant to research
                DataField.FAMILY_HISTORY,
                DataField.VITAL_SIGNS,
            },
            prohibited_fields={
                DataField.FULL_NAME,
                DataField.ADDRESS,
                DataField.PHONE,
                DataField.EMAIL,
                DataField.NATIONAL_ID,
                DataField.MEDICAL_RECORD_NUMBER,
                DataField.INSURANCE_ID,
            },
            retention_days=7300,  # 20 years for research
            justifications={
                DataField.MEDICAL_CONDITIONS: CollectionJustification.RESEARCH_PURPOSE,
                DataField.LAB_RESULTS: CollectionJustification.RESEARCH_PURPOSE,
            },
        )
        self.add_policy(research_policy)

        # Billing policy - financial minimum
        billing_policy = DataMinimizationPolicy(
            policy_id="POL-BILL-001",
            name="Billing Data Minimization",
            purpose=ProcessingPurpose.BILLING,
            level=DataMinimizationLevel.MINIMAL,
            required_fields={
                DataField.FULL_NAME,
                DataField.DATE_OF_BIRTH,
                DataField.ADDRESS,
                DataField.INSURANCE_ID,
                DataField.MEDICAL_RECORD_NUMBER,
                DataField.BILLING_INFORMATION,
            },
            optional_fields={DataField.PHONE, DataField.EMAIL},
            prohibited_fields={
                DataField.GENETIC_DATA,
                DataField.MENTAL_HEALTH_DATA,
                DataField.SEXUAL_HEALTH_DATA,
                DataField.CLINICAL_NOTES,
                DataField.FAMILY_HISTORY,
            },
            retention_days=2555,  # 7 years for financial records
            justifications={
                DataField.INSURANCE_ID: CollectionJustification.BILLING_PURPOSE,
                DataField.BILLING_INFORMATION: CollectionJustification.LEGAL_REQUIREMENT,
            },
        )
        self.add_policy(billing_policy)

    def add_policy(self, policy: DataMinimizationPolicy) -> None:
        """Add a data minimization policy.

        Args:
            policy: Policy to add
        """
        self.policies[policy.policy_id] = policy

        # Index by purpose
        if policy.purpose not in self.purpose_policies:
            self.purpose_policies[policy.purpose] = []
        self.purpose_policies[policy.purpose].append(policy.policy_id)

        logger.info("Added data minimization policy: %s", policy.name)

    def get_policy_for_purpose(
        self, purpose: ProcessingPurpose, level: Optional[DataMinimizationLevel] = None
    ) -> Optional[DataMinimizationPolicy]:
        """Get appropriate policy for purpose.

        Args:
            purpose: Processing purpose
            level: Desired minimization level

        Returns:
            Matching policy or None
        """
        policy_ids = self.purpose_policies.get(purpose, [])

        for policy_id in policy_ids:
            policy = self.policies.get(policy_id)
            if policy and (level is None or policy.level == level):
                return policy

        return None

    def validate_data_collection(
        self,
        purpose: ProcessingPurpose,
        requested_fields: Set[DataField],
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, List[str], Dict[DataField, str]]:
        """Validate if data collection meets minimization requirements.

        Args:
            purpose: Purpose of collection
            requested_fields: Fields requested
            context: Additional context

        Returns:
            Tuple of (is_valid, violations, recommendations)
        """
        # Context parameter reserved for future use
        _ = context
        policy = self.get_policy_for_purpose(purpose)
        if not policy:
            return False, ["No policy found for purpose"], {}

        violations = []
        recommendations = {}

        # Check prohibited fields
        prohibited_collected = requested_fields & policy.prohibited_fields
        if prohibited_collected:
            for field in prohibited_collected:
                violations.append(
                    f"Field {field.value} is prohibited for {purpose.value}"
                )

        # Check if all required fields are included
        missing_required = policy.required_fields - requested_fields
        if missing_required:
            for field in missing_required:
                violations.append(f"Required field {field.value} is missing")

        # Check unnecessary fields
        allowed_fields = policy.required_fields | policy.optional_fields
        unnecessary_fields = (
            requested_fields - allowed_fields - policy.prohibited_fields
        )

        for field in unnecessary_fields:
            recommendations[field] = (
                f"Field {field.value} is not necessary for {purpose.value}. "
                "Consider removing to minimize data collection."
            )

        # Log validation
        self.field_usage_log.append(
            {
                "timestamp": datetime.now(),
                "purpose": purpose.value,
                "requested_fields": [f.value for f in requested_fields],
                "violations": violations,
                "recommendations": list(recommendations.keys()),
            }
        )

        is_valid = len(violations) == 0
        return is_valid, violations, recommendations

    @require_phi_access(AccessLevel.READ)
    def apply_minimization(
        self,
        data: Dict[str, Any],
        purpose: ProcessingPurpose,
        consent_scope: Optional[List[ConsentScope]] = None,
    ) -> Dict[str, Any]:
        """Apply data minimization to dataset.

        Args:
            data: Original data
            purpose: Processing purpose
            consent_scope: Consented data scope

        Returns:
            Minimized data
        """
        policy = self.get_policy_for_purpose(purpose)
        if not policy:
            logger.warning("No minimization policy for %s", purpose.value)
            return data

        minimized_data = {}
        removed_fields = []

        # Map data keys to DataField enum
        field_mapping = {field.value: field for field in DataField}

        for key, value in data.items():
            field = field_mapping.get(key)

            if not field:
                # Unknown field - remove by default
                removed_fields.append(key)
                continue

            # Check if field is allowed
            if field in policy.prohibited_fields:
                removed_fields.append(key)
                continue

            # Check if field is in allowed set
            if field in policy.required_fields or field in policy.optional_fields:
                # Check consent if applicable
                if consent_scope and not self._check_consent_coverage(
                    field, consent_scope
                ):
                    removed_fields.append(key)
                    continue

                minimized_data[key] = value
            else:
                removed_fields.append(key)

        # Log minimization
        if removed_fields:
            logger.info(
                "Data minimization removed %d fields for %s: %s",
                len(removed_fields),
                purpose.value,
                removed_fields,
            )

        return minimized_data

    def generate_field_usage_report(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Generate report on field usage patterns.

        Args:
            start_date: Report start
            end_date: Report end

        Returns:
            Usage report
        """
        report: Dict[str, Any] = {
            "period": {"start": start_date, "end": end_date},
            "field_frequency": {},
            "violation_summary": {},
            "recommendation_summary": {},
            "purpose_breakdown": {},
        }

        # Analyze usage logs
        for log_entry in self.field_usage_log:
            if start_date <= log_entry["timestamp"] <= end_date:
                # Count field usage
                for field in log_entry["requested_fields"]:
                    report["field_frequency"][field] = (
                        report["field_frequency"].get(field, 0) + 1
                    )

                # Count violations
                for violation in log_entry["violations"]:
                    report["violation_summary"][violation] = (
                        report["violation_summary"].get(violation, 0) + 1
                    )

                # Purpose breakdown
                purpose = log_entry["purpose"]
                if purpose not in report["purpose_breakdown"]:
                    report["purpose_breakdown"][purpose] = {
                        "request_count": 0,
                        "avg_fields": 0,
                        "total_fields": 0,
                    }

                report["purpose_breakdown"][purpose]["request_count"] += 1
                report["purpose_breakdown"][purpose]["total_fields"] += len(
                    log_entry["requested_fields"]
                )

        # Calculate averages
        for _purpose, stats in report["purpose_breakdown"].items():
            if stats["request_count"] > 0:
                stats["avg_fields"] = stats["total_fields"] / stats["request_count"]

        return report

    def audit_data_minimization(
        self, organization_id: str, auditor_id: str
    ) -> Dict[str, Any]:
        """Perform data minimization audit.

        Args:
            organization_id: Organization being audited
            auditor_id: ID of auditor

        Returns:
            Audit results
        """
        audit_id = f"AUDIT-{uuid4()}"

        findings: List[Dict[str, str]] = []
        recommendations: List[str] = []
        policy_coverage: Dict[str, bool] = {}

        audit_results: Dict[str, Any] = {
            "audit_id": audit_id,
            "organization_id": organization_id,
            "auditor_id": auditor_id,
            "timestamp": datetime.now(),
            "compliance_score": 0,
            "findings": findings,
            "recommendations": recommendations,
            "policy_coverage": policy_coverage,
        }

        # Check policy coverage for each purpose
        for purpose in ProcessingPurpose:
            policy = self.get_policy_for_purpose(purpose)
            audit_results["policy_coverage"][purpose.value] = policy is not None

            if not policy:
                audit_results["findings"].append(
                    {
                        "severity": "high",
                        "issue": f"No minimization policy for {purpose.value}",
                    }
                )

        # Analyze recent usage patterns
        recent_logs = [
            log
            for log in self.field_usage_log
            if log["timestamp"] > datetime.now() - timedelta(days=30)
        ]

        # Check for repeated violations
        violation_counts: Dict[str, int] = {}
        for log in recent_logs:
            for violation in log["violations"]:
                violation_counts[violation] = violation_counts.get(violation, 0) + 1

        for violation, count in violation_counts.items():
            if count > 5:
                audit_results["findings"].append(
                    {
                        "severity": "medium",
                        "issue": f"Repeated violation: {violation} ({count} times)",
                    }
                )

        # Calculate compliance score
        base_score = 100
        base_score -= len(audit_results["findings"]) * 10
        base_score -= sum(
            5 for f in audit_results["findings"] if f["severity"] == "high"
        )

        audit_results["compliance_score"] = max(0, base_score)

        # Add recommendations
        if audit_results["compliance_score"] < 80:
            audit_results["recommendations"].append(
                "Review and update data minimization policies"
            )
            audit_results["recommendations"].append(
                "Provide additional training on data minimization principles"
            )

        # Store audit
        self.minimization_audits.append(audit_results)

        return audit_results

    def get_retention_schedule(self) -> Dict[ProcessingPurpose, int]:
        """Get data retention schedule by purpose.

        Returns:
            Retention days by purpose
        """
        schedule = {}

        for purpose, policy_ids in self.purpose_policies.items():
            min_retention = None

            for policy_id in policy_ids:
                policy = self.policies.get(policy_id)
                if policy:
                    if min_retention is None or policy.retention_days < min_retention:
                        min_retention = policy.retention_days

            if min_retention is not None:
                schedule[purpose] = min_retention

        return schedule

    def _check_consent_coverage(
        self, field: DataField, consent_scope: List[ConsentScope]
    ) -> bool:
        """Check if field is covered by consent scope.

        Args:
            field: Data field
            consent_scope: Consented scopes

        Returns:
            Whether field is covered
        """
        # Map fields to consent scopes
        field_scope_mapping = {
            DataField.GENETIC_DATA: ConsentScope.GENETIC_DATA,
            DataField.MENTAL_HEALTH_DATA: ConsentScope.MENTAL_HEALTH,
            DataField.SEXUAL_HEALTH_DATA: ConsentScope.SEXUAL_HEALTH,
            DataField.SUBSTANCE_USE_DATA: ConsentScope.SUBSTANCE_USE,
            DataField.LAB_RESULTS: ConsentScope.LAB_RESULTS,
            DataField.IMAGING_RESULTS: ConsentScope.IMAGING,
            DataField.PAST_DIAGNOSES: ConsentScope.MEDICAL_HISTORY,
            DataField.CURRENT_MEDICATIONS: ConsentScope.MEDICATIONS,
        }

        # Check if full record consent given
        if ConsentScope.FULL_RECORD in consent_scope:
            return True

        # Check specific scope
        required_scope = field_scope_mapping.get(field)
        if required_scope:
            return required_scope in consent_scope

        # Default fields assumed covered by basic consent
        return True


# Export public API
__all__ = [
    "DataMinimizationLevel",
    "DataField",
    "CollectionJustification",
    "DataMinimizationPolicy",
    "DataMinimizationManager",
]
