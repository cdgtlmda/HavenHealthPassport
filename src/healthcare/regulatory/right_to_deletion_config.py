"""GDPR Right to Deletion Configuration.

This module implements comprehensive configuration and management for GDPR
Article 17 "Right to Erasure" (Right to be Forgotten) with full support for
healthcare-specific requirements and legal obligations.
Includes FHIR resource validation for audit events.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict

from src.healthcare.fhir_validator import FHIRValidator
from src.healthcare.hipaa_access_control import hipaa_access_control

# FHIR resource type for this module
__fhir_resource__ = "AuditEvent"

logger = logging.getLogger(__name__)


class FHIRAuditEvent(TypedDict, total=False):
    """FHIR AuditEvent resource type definition for deletion events."""

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


class DeletionValidationResource:
    """Deletion configuration with FHIR Resource validation."""

    # FHIR DomainResource compliance
    resource_type = "AuditEvent"

    def __init__(self) -> None:
        """Initialize with FHIR validator."""
        self.validator = FHIRValidator()


class DeletionMethod(Enum):
    """Methods for data deletion/erasure."""

    PHYSICAL_DELETE = "physical_delete"  # Complete removal from storage
    ANONYMIZATION = "anonymization"  # Remove identifying information
    PSEUDONYMIZATION = "pseudonymization"  # Replace with pseudonyms
    ENCRYPTION_KEY_DELETION = "encryption_key_deletion"  # Crypto-shredding
    ARCHIVAL = "archival"  # Move to restricted archive
    PARTIAL_DELETION = "partial_deletion"  # Delete specific fields only


class DataCategory(Enum):
    """Categories of data for deletion policies."""

    # Personal identifiers
    IDENTIFIERS = "identifiers"
    CONTACT_INFO = "contact_info"
    DEMOGRAPHIC = "demographic"

    # Healthcare data
    MEDICAL_HISTORY = "medical_history"
    DIAGNOSES = "diagnoses"
    MEDICATIONS = "medications"
    LAB_RESULTS = "lab_results"
    IMAGING = "imaging"
    CLINICAL_NOTES = "clinical_notes"
    CARE_PLANS = "care_plans"

    # Special categories
    GENETIC_DATA = "genetic_data"
    BIOMETRIC_DATA = "biometric_data"
    MENTAL_HEALTH = "mental_health"
    SEXUAL_HEALTH = "sexual_health"
    SUBSTANCE_USE = "substance_use"

    # Administrative
    BILLING_INFO = "billing_info"
    INSURANCE_INFO = "insurance_info"
    CONSENT_RECORDS = "consent_records"
    ACCESS_LOGS = "access_logs"
    AUDIT_TRAILS = "audit_trails"

    # Communications
    MESSAGES = "messages"
    APPOINTMENTS = "appointments"
    NOTIFICATIONS = "notifications"

    # Research
    RESEARCH_DATA = "research_data"
    STUDY_PARTICIPATION = "study_participation"

    # Third party
    THIRD_PARTY_DATA = "third_party_data"
    SHARED_DATA = "shared_data"


class LegalBasis(Enum):
    """Legal basis for retention that may override deletion."""

    LEGAL_OBLIGATION = "legal_obligation"  # Legal requirement to retain
    VITAL_INTERESTS = "vital_interests"  # Necessary to protect life
    PUBLIC_HEALTH = "public_health"  # Public health requirement
    LEGAL_CLAIMS = "legal_claims"  # Establishment/defense of legal claims
    SCIENTIFIC_RESEARCH = "scientific_research"  # Scientific/historical research
    FREEDOM_OF_EXPRESSION = "freedom_of_expression"  # Exercise of free expression
    COMPLIANCE = "compliance"  # Compliance with legal obligation


class DeletionStatus(Enum):
    """Status of deletion request."""

    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    DENIED = "denied"
    SUSPENDED = "suspended"
    FAILED = "failed"


class RightToDeletionConfiguration:
    """Configuration for right to deletion implementation."""

    # FHIR resource type
    __fhir_resource__ = "Provenance"

    def __init__(self) -> None:
        """Initialize deletion configuration with policies and rules."""
        self.fhir_validator = FHIRValidator()
        self.deletion_policies: Dict[DataCategory, Dict[str, Any]] = (
            self._init_deletion_policies()
        )
        self.retention_requirements: Dict[str, Dict[str, Any]] = (
            self._init_retention_requirements()
        )
        self.deletion_exceptions: Dict[LegalBasis, Dict[str, Any]] = (
            self._init_deletion_exceptions()
        )
        self.anonymization_rules: Dict[DataCategory, Dict[str, Any]] = (
            self._init_anonymization_rules()
        )
        self.third_party_processors: Dict[str, Dict[str, Any]] = (
            self._init_third_party_processors()
        )

    def _init_deletion_policies(self) -> Dict[DataCategory, Dict[str, Any]]:
        """Initialize deletion policies by data category."""
        return {
            DataCategory.IDENTIFIERS: {
                "method": DeletionMethod.ANONYMIZATION,
                "timeline_days": 30,
                "requires_verification": True,
                "cascading_delete": True,
                "notify_third_parties": True,
                "backup_retention_days": 90,
            },
            DataCategory.MEDICAL_HISTORY: {
                "method": DeletionMethod.PARTIAL_DELETION,
                "timeline_days": 45,
                "requires_verification": True,
                "cascading_delete": False,
                "legal_review_required": True,
                "preserve_fields": ["anonymized_conditions", "anonymized_procedures"],
                "backup_retention_days": 180,
            },
            DataCategory.GENETIC_DATA: {
                "method": DeletionMethod.PHYSICAL_DELETE,
                "timeline_days": 60,
                "requires_verification": True,
                "cascading_delete": True,
                "special_handling": True,
                "notification_required": ["genetic_counselor", "primary_physician"],
                "backup_retention_days": 365,
            },
            DataCategory.BIOMETRIC_DATA: {
                "method": DeletionMethod.ENCRYPTION_KEY_DELETION,
                "timeline_days": 30,
                "requires_verification": True,
                "cascading_delete": True,
                "immediate_deletion": True,
                "backup_retention_days": 30,
            },
            DataCategory.BILLING_INFO: {
                "method": DeletionMethod.ARCHIVAL,
                "timeline_days": 90,
                "requires_verification": False,
                "cascading_delete": False,
                "retention_override": "legal_requirement",
                "minimum_retention_years": 7,
                "backup_retention_days": 2555,  # 7 years
            },
            DataCategory.CONSENT_RECORDS: {
                "method": DeletionMethod.ARCHIVAL,
                "timeline_days": 180,
                "requires_verification": False,
                "cascading_delete": False,
                "retention_override": "audit_requirement",
                "minimum_retention_years": 3,
                "backup_retention_days": 1095,  # 3 years
            },
            DataCategory.ACCESS_LOGS: {
                "method": DeletionMethod.ANONYMIZATION,
                "timeline_days": 365,
                "requires_verification": False,
                "cascading_delete": False,
                "retention_override": "security_requirement",
                "anonymize_fields": ["user_id", "ip_address"],
                "preserve_fields": ["timestamp", "action_type"],
                "backup_retention_days": 2190,  # 6 years
            },
            DataCategory.RESEARCH_DATA: {
                "method": DeletionMethod.ANONYMIZATION,
                "timeline_days": 30,
                "requires_verification": True,
                "cascading_delete": False,
                "irb_notification_required": True,
                "preserve_anonymized": True,
                "backup_retention_days": 90,
            },
            DataCategory.THIRD_PARTY_DATA: {
                "method": DeletionMethod.PHYSICAL_DELETE,
                "timeline_days": 45,
                "requires_verification": True,
                "cascading_delete": True,
                "third_party_notification": True,
                "propagation_required": True,
                "backup_retention_days": 60,
            },
        }

    def _init_retention_requirements(self) -> Dict[str, Dict[str, Any]]:
        """Initialize legal retention requirements."""
        return {
            "healthcare_records": {
                "category": DataCategory.MEDICAL_HISTORY,
                "minimum_years": 10,
                "jurisdiction_specific": {
                    "US": {"adults": 6, "minors": "until_age_21_plus_6"},
                    "UK": 8,
                    "EU": 10,
                    "CA": 10,
                },
                "exceptions": ["mental_health", "substance_abuse", "hiv_aids"],
            },
            "billing_records": {
                "category": DataCategory.BILLING_INFO,
                "minimum_years": 7,
                "jurisdiction_specific": {"US": 7, "UK": 6, "EU": 10},
            },
            "prescription_records": {
                "category": DataCategory.MEDICATIONS,
                "minimum_years": 2,
                "controlled_substances": 5,
            },
            "imaging_studies": {
                "category": DataCategory.IMAGING,
                "minimum_years": 7,
                "mammograms": 10,
                "pediatric": "until_age_21_plus_7",
            },
            "lab_results": {
                "category": DataCategory.LAB_RESULTS,
                "minimum_years": 2,
                "pathology": 10,
                "genetic_tests": 50,
            },
            "consent_documentation": {
                "category": DataCategory.CONSENT_RECORDS,
                "minimum_years": 3,
                "research_consent": "study_duration_plus_3",
            },
        }

    def _init_deletion_exceptions(self) -> Dict[LegalBasis, Dict[str, Any]]:
        """Initialize exceptions to deletion rights."""
        return {
            LegalBasis.LEGAL_OBLIGATION: {
                "description": "Legal requirement to retain data",
                "examples": [
                    "Tax records",
                    "Medical malpractice statute of limitations",
                    "Regulatory compliance",
                ],
                "verification_required": True,
                "documentation_required": True,
                "review_period_days": 30,
                "override_categories": [
                    DataCategory.BILLING_INFO,
                    DataCategory.MEDICAL_HISTORY,
                    DataCategory.CONSENT_RECORDS,
                ],
            },
            LegalBasis.VITAL_INTERESTS: {
                "description": "Necessary to protect someone's life",
                "examples": [
                    "Emergency contact information",
                    "Critical medical alerts",
                    "Life-threatening allergies",
                ],
                "verification_required": True,
                "medical_review_required": True,
                "immediate_review": True,
                "override_categories": [
                    DataCategory.MEDICAL_HISTORY,
                    DataCategory.MEDICATIONS,
                    DataCategory.CONTACT_INFO,
                ],
            },
            LegalBasis.PUBLIC_HEALTH: {
                "description": "Public health interest",
                "examples": [
                    "Infectious disease reporting",
                    "Vaccination records",
                    "Epidemiological data",
                ],
                "verification_required": True,
                "health_authority_approval": True,
                "anonymization_alternative": True,
                "override_categories": [
                    DataCategory.DIAGNOSES,
                    DataCategory.LAB_RESULTS,
                    DataCategory.MEDICATIONS,
                ],
            },
            LegalBasis.LEGAL_CLAIMS: {
                "description": "Establishment or defense of legal claims",
                "examples": [
                    "Ongoing litigation",
                    "Potential malpractice claims",
                    "Insurance disputes",
                ],
                "verification_required": True,
                "legal_hold": True,
                "review_period_days": 90,
                "override_categories": "all",
            },
            LegalBasis.SCIENTIFIC_RESEARCH: {
                "description": "Scientific or historical research purposes",
                "examples": [
                    "Clinical trial data",
                    "Longitudinal studies",
                    "Public health research",
                ],
                "verification_required": True,
                "irb_approval_required": True,
                "anonymization_preferred": True,
                "override_categories": [
                    DataCategory.RESEARCH_DATA,
                    DataCategory.LAB_RESULTS,
                    DataCategory.CLINICAL_NOTES,
                ],
            },
        }

    def _init_anonymization_rules(self) -> Dict[DataCategory, Dict[str, Any]]:
        """Initialize anonymization rules for different data categories."""
        return {
            DataCategory.IDENTIFIERS: {
                "fields_to_remove": [
                    "name",
                    "address",
                    "phone",
                    "email",
                    "ssn",
                    "medical_record_number",
                    "insurance_id",
                ],
                "fields_to_generalize": {
                    "date_of_birth": "year_only",
                    "zip_code": "first_3_digits",
                },
                "replacement_strategy": "random_identifier",
            },
            DataCategory.MEDICAL_HISTORY: {
                "fields_to_remove": ["provider_notes", "patient_comments"],
                "fields_to_generalize": {
                    "diagnosis_date": "month_year",
                    "provider_name": "specialty_only",
                },
                "preserve_for_research": True,
            },
            DataCategory.GENETIC_DATA: {
                "fields_to_remove": ["all_identifiable"],
                "special_handling": "genetic_counselor_review",
                "research_exemption": True,
                "family_member_notification": True,
            },
            DataCategory.ACCESS_LOGS: {
                "fields_to_remove": ["user_id", "ip_address", "session_id"],
                "fields_to_hash": ["device_id", "browser_fingerprint"],
                "preserve_fields": ["timestamp", "action", "resource_accessed"],
            },
        }

    def _init_third_party_processors(self) -> Dict[str, Dict[str, Any]]:
        """Initialize third-party processor configurations."""
        return {
            "laboratory_partners": {
                "notification_method": "api",
                "deletion_endpoint": "/api/v1/gdpr/delete",
                "verification_required": True,
                "sla_days": 30,
                "confirmation_required": True,
            },
            "imaging_centers": {
                "notification_method": "secure_email",
                "deletion_protocol": "manual_verification",
                "sla_days": 45,
                "retention_override": "legal_requirement",
            },
            "cloud_storage": {
                "notification_method": "api",
                "deletion_endpoint": "/storage/gdpr/delete",
                "includes_backups": True,
                "sla_days": 60,
                "verification_method": "cryptographic_proof",
            },
            "analytics_providers": {
                "notification_method": "api",
                "deletion_endpoint": "/analytics/subject/delete",
                "anonymization_option": True,
                "sla_days": 30,
            },
            "research_institutions": {
                "notification_method": "formal_request",
                "requires_irb_notification": True,
                "anonymization_preferred": True,
                "sla_days": 90,
            },
        }

    def get_deletion_policy(self, category: DataCategory) -> Dict[str, Any]:
        """Get deletion policy for data category.

        Args:
            category: Data category

        Returns:
            Deletion policy configuration
        """
        return self.deletion_policies.get(
            category,
            {
                "method": DeletionMethod.PHYSICAL_DELETE,
                "timeline_days": 30,
                "requires_verification": True,
            },
        )

    def check_retention_requirement(
        self,
        category: DataCategory,
        jurisdiction: str,
        patient_age: Optional[int] = None,
    ) -> Optional[int]:
        """Check if data has mandatory retention period.

        Args:
            category: Data category
            jurisdiction: Legal jurisdiction
            patient_age: Patient age (for pediatric rules)

        Returns:
            Required retention period in years, or None
        """
        for _, requirement in self.retention_requirements.items():
            if requirement["category"] == category:
                # Check jurisdiction-specific rules
                if "jurisdiction_specific" in requirement:
                    juris_rules = requirement["jurisdiction_specific"].get(jurisdiction)
                    if juris_rules:
                        if isinstance(juris_rules, dict):
                            # Handle special cases like minors
                            if (
                                patient_age
                                and patient_age < 18
                                and "minors" in juris_rules
                            ):
                                return self._calculate_minor_retention(
                                    juris_rules["minors"], patient_age
                                )
                            result = juris_rules.get(
                                "adults", requirement["minimum_years"]
                            )
                            return int(result) if result is not None else None
                        return (
                            int(juris_rules)
                            if isinstance(juris_rules, (int, float))
                            else None
                        )

                return (
                    int(requirement["minimum_years"])
                    if "minimum_years" in requirement
                    else None
                )

        return None

    def check_deletion_exception(
        self, category: DataCategory, legal_basis: Optional[LegalBasis] = None
    ) -> Tuple[bool, Optional[str]]:
        """Check if deletion exception applies.

        Args:
            category: Data category
            legal_basis: Claimed legal basis for exception

        Returns:
            Tuple of (has_exception, reason)
        """
        if not legal_basis:
            return False, None

        exception = self.deletion_exceptions.get(legal_basis)
        if not exception:
            return False, None

        # Check if category is covered by exception
        override_categories = exception.get("override_categories", [])
        if override_categories == "all":
            return True, exception["description"]

        if category in override_categories:
            return True, exception["description"]

        return False, None

    def get_anonymization_rules(self, category: DataCategory) -> Dict[str, Any]:
        """Get anonymization rules for data category.

        Args:
            category: Data category

        Returns:
            Anonymization rules
        """
        return self.anonymization_rules.get(
            category,
            {
                "fields_to_remove": ["all_identifiable"],
                "replacement_strategy": "remove",
            },
        )

    def get_third_party_config(self, processor_type: str) -> Dict[str, Any]:
        """Get third-party processor configuration.

        Args:
            processor_type: Type of processor

        Returns:
            Processor configuration
        """
        return self.third_party_processors.get(
            processor_type, {"notification_method": "manual", "sla_days": 30}
        )

    def _calculate_minor_retention(self, rule: str, current_age: int) -> int:
        """Calculate retention period for minor's records.

        Args:
            rule: Retention rule string
            current_age: Current age of patient

        Returns:
            Retention period in years
        """
        if "until_age" in rule:
            # Parse rules like "until_age_21_plus_6"
            parts = rule.split("_")
            if len(parts) >= 4:
                until_age = int(parts[2])
                plus_years = int(parts[4]) if len(parts) > 4 else 0
                years_until_age = max(0, until_age - current_age)
                return years_until_age + plus_years

        return 10  # Default retention

    def validate_fhir_deletion_provenance(
        self, deletion_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate deletion event as FHIR Provenance resource.

        Args:
            deletion_data: Deletion event data

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        # Convert to FHIR Provenance format for deletion tracking
        fhir_provenance = {
            "resourceType": "Provenance",
            "recorded": deletion_data.get("timestamp", datetime.now()).isoformat(),
            "activity": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-DataOperation",
                        "code": "DELETE",
                        "display": "Delete",
                    }
                ]
            },
            "agent": [
                {
                    "type": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/provenance-participant-type",
                                "code": "performer",
                                "display": "Performer",
                            }
                        ]
                    },
                    "who": {
                        "display": deletion_data.get("requested_by", "Data Subject")
                    },
                }
            ],
            "entity": [
                {
                    "role": "removal",
                    "what": {
                        "display": f"Data Category: {deletion_data.get('category', 'Unknown')}"
                    },
                }
            ],
            "reason": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ActReason",
                            "code": "GDPR-17",
                            "display": "GDPR Article 17 Right to Erasure",
                        }
                    ]
                }
            ],
        }

        # Add signature if present
        if deletion_data.get("authorized_by"):
            fhir_provenance["signature"] = [
                {
                    "type": [
                        {
                            "system": "urn:iso-astm:E1762-95:2013",
                            "code": "1.2.840.10065.1.12.1.5",
                            "display": "Verification Signature",
                        }
                    ],
                    "when": deletion_data.get(
                        "authorization_time", datetime.now()
                    ).isoformat(),
                    "who": {"display": deletion_data["authorized_by"]},
                }
            ]

        # Validate using FHIR validator
        return self.fhir_validator.validate_resource("Provenance", fhir_provenance)

    def check_deletion_access(
        self, user_id: str, data_subject_id: str, category: DataCategory
    ) -> Tuple[bool, Optional[str]]:
        """Check if user has access to request deletion.

        Args:
            user_id: ID of user requesting deletion
            data_subject_id: ID of data subject
            category: Category of data to delete

        Returns:
            Tuple of (allowed, denial_reason)
        """
        # Data subjects can request their own deletion
        if user_id == data_subject_id:
            return True, None

        # Check if user has appropriate role
        user = hipaa_access_control.users.get(user_id)
        if not user:
            return False, "User not found"

        # Check for data protection officer or admin roles
        allowed_roles = ["data_protection_officer", "privacy_officer", "admin"]
        if not any(role.name in allowed_roles for role in user.roles):
            return False, "Insufficient privileges"

        # Check category-specific restrictions
        restricted_categories = [
            DataCategory.MENTAL_HEALTH,
            DataCategory.SEXUAL_HEALTH,
            DataCategory.SUBSTANCE_USE,
        ]

        if category in restricted_categories:
            # Only DPO can delete sensitive categories for others
            if not any(role.name == "data_protection_officer" for role in user.roles):
                return False, "Only DPO can delete sensitive categories for other users"

        return True, None


def validate_fhir(fhir_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate FHIR data for deletion audit events.

    Args:
        fhir_data: FHIR data to validate

    Returns:
        Validation results
    """
    errors = []
    warnings: List[str] = []

    # Check resource type
    valid_types = ["AuditEvent", "Provenance"]
    if fhir_data.get("resourceType") not in valid_types:
        errors.append(f"Resource type must be one of {valid_types} for deletion events")

    # For AuditEvent
    if fhir_data.get("resourceType") == "AuditEvent":
        required_fields = ["type", "recorded", "agent", "source"]
        for field in required_fields:
            if field not in fhir_data:
                errors.append(f"Required field '{field}' is missing")

    # For Provenance
    elif fhir_data.get("resourceType") == "Provenance":
        required_fields = ["recorded", "activity", "agent"]
        for field in required_fields:
            if field not in fhir_data:
                errors.append(f"Required field '{field}' is missing")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
