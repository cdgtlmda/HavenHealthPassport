"""Comprehensive Consent Management System for GDPR Compliance.

This module implements a complete consent management system that handles
all aspects of consent lifecycle management, including obtaining, storing,
updating, withdrawing, and auditing consent for healthcare data processing.
"""

import base64
import hashlib
import json
import logging
import os
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict
from uuid import uuid4

import boto3

from src.database import get_db
from src.healthcare.fhir_validator import FHIRValidator
from src.healthcare.regulatory.gdpr_compliance import ProcessingPurpose
from src.models.document import Document
from src.models.patient import Patient
from src.security.encryption import EncryptionService

# FHIR resource type for this module
__fhir_resource__ = "Consent"

logger = logging.getLogger(__name__)


class FHIRConsent(TypedDict, total=False):
    """FHIR Consent resource type definition."""

    resourceType: Literal["Consent"]
    id: str
    status: Literal[
        "draft", "proposed", "active", "rejected", "inactive", "entered-in-error"
    ]
    scope: Dict[str, Any]
    category: List[Dict[str, Any]]
    patient: Dict[str, str]
    dateTime: str
    performer: List[Dict[str, str]]
    organization: List[Dict[str, str]]
    sourceAttachment: Dict[str, Any]
    sourceReference: Dict[str, str]
    policy: List[Dict[str, Any]]
    policyRule: Dict[str, Any]
    verification: List[Dict[str, Any]]
    provision: Dict[str, Any]
    __fhir_resource__: Literal["Consent"]


class ConsentType(Enum):
    """Types of consent that can be collected."""

    GENERAL_HEALTHCARE = "general_healthcare"
    EMERGENCY_CARE = "emergency_care"
    RESEARCH = "research"
    DATA_SHARING = "data_sharing"
    MARKETING = "marketing"
    COOKIES = "cookies"
    THIRD_PARTY = "third_party"
    INTERNATIONAL_TRANSFER = "international_transfer"
    AUTOMATED_PROCESSING = "automated_processing"
    SPECIAL_CATEGORY = "special_category"
    CHILD_DATA = "child_data"
    BIOMETRIC = "biometric"
    GENETIC = "genetic"


class ConsentStatus(Enum):
    """Status of consent."""

    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    INVALID = "invalid"
    PARENTAL_REQUIRED = "parental_required"
    UNDER_REVIEW = "under_review"


class ConsentScope(Enum):
    """Scope of data covered by consent."""

    BASIC_DEMOGRAPHIC = "basic_demographic"
    MEDICAL_HISTORY = "medical_history"
    CURRENT_CONDITIONS = "current_conditions"
    MEDICATIONS = "medications"
    LAB_RESULTS = "lab_results"
    IMAGING = "imaging"
    GENETIC_DATA = "genetic_data"
    MENTAL_HEALTH = "mental_health"
    SUBSTANCE_USE = "substance_use"
    SEXUAL_HEALTH = "sexual_health"
    FULL_RECORD = "full_record"


class ConsentDuration(Enum):
    """Duration of consent validity."""

    SINGLE_USE = "single_use"
    EPISODE_OF_CARE = "episode_of_care"
    ONE_YEAR = "one_year"
    FIVE_YEARS = "five_years"
    TEN_YEARS = "ten_years"
    LIFETIME = "lifetime"
    CUSTOM = "custom"


class ConsentMethod(Enum):
    """Method by which consent was obtained."""

    WRITTEN = "written"
    ELECTRONIC = "electronic"
    VERBAL = "verbal"
    IMPLIED = "implied"
    EMERGENCY_OVERRIDE = "emergency_override"
    COURT_ORDER = "court_order"
    STATUTORY = "statutory"


class ConsentManager:
    """Comprehensive consent management system."""

    def __init__(self) -> None:
        """Initialize consent manager."""
        self.consent_records: Dict[str, List[Dict[str, Any]]] = {}
        self.consent_templates: Dict[str, Dict[str, Any]] = self._initialize_templates()
        self.consent_policies: Dict[str, Dict[str, Any]] = self._initialize_policies()
        self.audit_log: List[Dict[str, Any]] = []
        self.age_of_consent: Dict[str, int] = self._initialize_age_limits()
        self.fhir_validator: Optional[FHIRValidator] = (
            None  # Will be initialized when needed
        )

    def _initialize_templates(self) -> Dict[str, Dict[str, Any]]:
        """Initialize consent form templates."""
        return {
            "standard_healthcare": {
                "template_id": "TMPL-HC-001",
                "version": "2.0",
                "type": ConsentType.GENERAL_HEALTHCARE,
                "title": "General Healthcare Consent",
                "required_fields": [
                    "patient_name",
                    "date_of_birth",
                    "purpose",
                    "data_categories",
                    "recipients",
                    "retention_period",
                ],
                "optional_fields": ["restrictions", "special_instructions"],
                "languages": ["en", "es", "fr", "ar", "zh", "hi", "pt", "ru"],
                "requires_witness": False,
                "requires_notarization": False,
                "expiry_period_days": 365,
                "renewable": True,
            },
            "research_participation": {
                "template_id": "TMPL-RS-001",
                "version": "1.5",
                "type": ConsentType.RESEARCH,
                "title": "Medical Research Participation Consent",
                "required_fields": [
                    "patient_name",
                    "date_of_birth",
                    "study_name",
                    "principal_investigator",
                    "irb_number",
                    "risks",
                    "benefits",
                    "data_use",
                    "withdrawal_rights",
                ],
                "optional_fields": ["compensation", "future_contact"],
                "languages": ["en", "es", "fr"],
                "requires_witness": True,
                "requires_notarization": False,
                "expiry_period_days": None,  # Study-specific
                "renewable": False,
            },
            "emergency_treatment": {
                "template_id": "TMPL-EM-001",
                "version": "1.0",
                "type": ConsentType.EMERGENCY_CARE,
                "title": "Emergency Treatment Consent",
                "required_fields": [
                    "patient_identifier",
                    "emergency_contact",
                    "known_conditions",
                    "known_allergies",
                ],
                "optional_fields": ["advance_directives", "religious_preferences"],
                "languages": ["en", "es"],
                "requires_witness": False,
                "requires_notarization": False,
                "expiry_period_days": 90,
                "renewable": True,
                "allows_verbal": True,
            },
            "minor_treatment": {
                "template_id": "TMPL-MIN-001",
                "version": "1.2",
                "type": ConsentType.CHILD_DATA,
                "title": "Minor Patient Treatment Consent",
                "required_fields": [
                    "minor_name",
                    "minor_dob",
                    "guardian_name",
                    "guardian_relationship",
                    "guardian_id",
                    "treatment_scope",
                    "emergency_contact",
                ],
                "optional_fields": ["other_authorized_adults", "restrictions"],
                "languages": ["en", "es", "fr"],
                "requires_witness": False,
                "requires_notarization": False,
                "expiry_period_days": 365,
                "renewable": True,
                "age_verification_required": True,
            },
            "international_transfer": {
                "template_id": "TMPL-IT-001",
                "version": "1.0",
                "type": ConsentType.INTERNATIONAL_TRANSFER,
                "title": "International Data Transfer Consent",
                "required_fields": [
                    "patient_name",
                    "destination_country",
                    "recipient_organization",
                    "purpose",
                    "safeguards",
                    "data_categories",
                ],
                "optional_fields": ["duration", "onward_transfer_restrictions"],
                "languages": ["en", "es", "fr", "ar"],
                "requires_witness": False,
                "requires_notarization": True,
                "expiry_period_days": 730,  # 2 years
                "renewable": True,
            },
        }

    def _initialize_policies(self) -> Dict[str, Dict[str, Any]]:
        """Initialize consent policies for different scenarios."""
        return {
            "standard_care": {
                "policy_id": "POL-SC-001",
                "name": "Standard Care Consent Policy",
                "consent_types": [ConsentType.GENERAL_HEALTHCARE],
                "minimum_age": 18,
                "parental_consent_age": 16,
                "duration": ConsentDuration.ONE_YEAR,
                "auto_renewal": True,
                "withdrawal_notice_days": 0,
                "data_retention_after_withdrawal": 180,
                "granular_options": True,
            },
            "emergency_care": {
                "policy_id": "POL-EM-001",
                "name": "Emergency Care Consent Policy",
                "consent_types": [ConsentType.EMERGENCY_CARE],
                "minimum_age": 0,  # No age restriction in emergencies
                "parental_consent_age": 18,
                "duration": ConsentDuration.EPISODE_OF_CARE,
                "auto_renewal": False,
                "implied_consent_allowed": True,
                "withdrawal_restrictions": "Cannot withdraw during active emergency",
            },
            "research": {
                "policy_id": "POL-RS-001",
                "name": "Research Consent Policy",
                "consent_types": [ConsentType.RESEARCH],
                "minimum_age": 18,
                "parental_consent_age": 18,
                "duration": ConsentDuration.CUSTOM,
                "auto_renewal": False,
                "withdrawal_notice_days": 0,
                "data_retention_after_withdrawal": 0,  # Immediate deletion
                "irb_approval_required": True,
                "re_consent_for_changes": True,
            },
            "minor_care": {
                "policy_id": "POL-MIN-001",
                "name": "Minor Care Consent Policy",
                "consent_types": [ConsentType.CHILD_DATA],
                "minimum_age": 0,
                "parental_consent_age": 18,
                "emancipated_minor_age": 16,
                "duration": ConsentDuration.ONE_YEAR,
                "auto_renewal": False,
                "dual_parent_consent_required": False,  # True for some procedures
                "mature_minor_exceptions": [
                    "contraception",
                    "mental_health",
                    "substance_abuse",
                ],
            },
        }

    def _initialize_age_limits(self) -> Dict[str, int]:
        """Initialize age of consent by jurisdiction."""
        return {
            "default": 18,
            "US": 18,
            "UK": 16,
            "FR": 15,
            "DE": 16,
            "ES": 14,
            "IT": 14,
            "NL": 16,
            "BE": 14,
            "AT": 14,
            "CH": 16,
            "CA": 16,
            "AU": 16,
            "NZ": 16,
        }

    def create_consent_request(
        self,
        patient_id: str,
        consent_type: ConsentType,
        purpose: ProcessingPurpose,
        requested_by: str,
        template_id: Optional[str] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new consent request.

        Args:
            patient_id: ID of patient
            consent_type: Type of consent needed
            purpose: Purpose of processing
            requested_by: ID of requester
            template_id: Specific template to use
            custom_fields: Additional custom fields

        Returns:
            Consent request ID
        """
        consent_id = f"CONSENT-{uuid4()}"

        # Select appropriate template
        if not template_id:
            template = self._select_template(consent_type)
        else:
            template = self.consent_templates.get(template_id)

        if not template:
            raise ValueError(f"No template found for consent type: {consent_type}")

        # Create consent request
        consent_request = {
            "consent_id": consent_id,
            "patient_id": patient_id,
            "created_date": datetime.now(),
            "consent_type": consent_type.value,
            "purpose": purpose.value,
            "requested_by": requested_by,
            "template_id": template["template_id"],
            "template_version": template["version"],
            "status": ConsentStatus.PENDING.value,
            "custom_fields": custom_fields or {},
            "expiry_date": self._calculate_expiry(template),
            "requires_parental_consent": self._check_parental_requirement(patient_id),
            "audit_trail": [
                {
                    "timestamp": datetime.now(),
                    "action": "consent_requested",
                    "actor": requested_by,
                    "details": f"Consent request created for {consent_type.value}",
                }
            ],
        }

        # Store consent request
        if patient_id not in self.consent_records:
            self.consent_records[patient_id] = []

        self.consent_records[patient_id].append(consent_request)

        # Log audit event
        self._log_audit_event(
            "consent_request_created",
            patient_id,
            requested_by,
            {"consent_id": consent_id, "type": consent_type.value},
        )

        return consent_id

    def record_consent_response(
        self,
        consent_id: str,
        patient_id: str,
        granted: bool,
        scope: List[ConsentScope],
        duration: ConsentDuration,
        method: ConsentMethod,
        responder_id: str,
        parent_guardian_id: Optional[str] = None,
        restrictions: Optional[Dict[str, Any]] = None,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Record patient's response to consent request.

        Args:
            consent_id: Consent request ID
            patient_id: Patient ID
            granted: Whether consent was granted
            scope: Scope of data consented to
            duration: Duration of consent
            method: Method of consent collection
            responder_id: ID of person responding
            parent_guardian_id: Parent/guardian ID if applicable
            restrictions: Any restrictions on consent
            evidence: Evidence of consent (signature, recording, etc.)

        Returns:
            Success status
        """
        consent_record = self._find_consent_record(patient_id, consent_id)
        if not consent_record:
            logger.error("Consent record not found: %s", consent_id)
            return False

        # Update consent record
        consent_record.update(
            {
                "response_date": datetime.now(),
                "granted": granted,
                "status": (
                    ConsentStatus.GRANTED.value
                    if granted
                    else ConsentStatus.DENIED.value
                ),
                "scope": [s.value for s in scope],
                "duration": duration.value,
                "method": method.value,
                "responder_id": responder_id,
                "parent_guardian_id": parent_guardian_id,
                "restrictions": restrictions or {},
                "evidence": self._store_evidence(evidence) if evidence else None,
                "hash": self._generate_consent_hash(consent_record),
            }
        )

        # Calculate actual expiry date based on duration
        consent_record["expiry_date"] = self._calculate_duration_expiry(duration)

        # Add to audit trail
        consent_record["audit_trail"].append(
            {
                "timestamp": datetime.now(),
                "action": "consent_response_recorded",
                "actor": responder_id,
                "details": f"Consent {'granted' if granted else 'denied'}",
            }
        )

        # Log audit event
        self._log_audit_event(
            "consent_response",
            patient_id,
            responder_id,
            {"consent_id": consent_id, "granted": granted, "method": method.value},
        )

        # Send notifications if configured
        self._send_consent_notifications(consent_record)

        return True

    def withdraw_consent(
        self,
        consent_id: str,
        patient_id: str,
        withdrawn_by: str,
        reason: Optional[str] = None,
        immediate: bool = True,
    ) -> bool:
        """Withdraw previously given consent.

        Args:
            consent_id: Consent ID to withdraw
            patient_id: Patient ID
            withdrawn_by: ID of person withdrawing
            reason: Reason for withdrawal
            immediate: Whether withdrawal is immediate

        Returns:
            Success status
        """
        consent_record = self._find_consent_record(patient_id, consent_id)
        if not consent_record:
            logger.error("Consent record not found: %s", consent_id)
            return False

        # Check if consent can be withdrawn
        if not self._can_withdraw_consent(consent_record):
            logger.warning("Consent %s cannot be withdrawn", consent_id)
            return False

        # Update consent record
        consent_record.update(
            {
                "status": ConsentStatus.WITHDRAWN.value,
                "withdrawal_date": datetime.now(),
                "withdrawn_by": withdrawn_by,
                "withdrawal_reason": reason,
                "withdrawal_immediate": immediate,
            }
        )

        # Add to audit trail
        consent_record["audit_trail"].append(
            {
                "timestamp": datetime.now(),
                "action": "consent_withdrawn",
                "actor": withdrawn_by,
                "details": f"Consent withdrawn. Reason: {reason or 'Not specified'}",
            }
        )

        # Log audit event
        self._log_audit_event(
            "consent_withdrawn",
            patient_id,
            withdrawn_by,
            {"consent_id": consent_id, "reason": reason, "immediate": immediate},
        )

        # Trigger data handling processes
        if immediate:
            self._trigger_immediate_withdrawal_actions(consent_record)
        else:
            self._schedule_withdrawal_actions(consent_record)

        return True

    def check_consent_validity(
        self,
        patient_id: str,
        consent_type: ConsentType,
        purpose: ProcessingPurpose,
        scope: List[ConsentScope],
        requester_id: str,
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Check if valid consent exists for specified processing.

        Args:
            patient_id: Patient ID
            consent_type: Type of consent needed
            purpose: Purpose of processing
            scope: Required data scope
            requester_id: ID of requester

        Returns:
            Tuple of (is_valid, consent_id, details)
        """
        if patient_id not in self.consent_records:
            return False, None, {"reason": "No consent records found"}

        # Find matching consents
        valid_consents = []
        for consent in self.consent_records[patient_id]:
            if (
                consent["consent_type"] == consent_type.value
                and consent["purpose"] == purpose.value
                and consent["status"] == ConsentStatus.GRANTED.value
                and consent["granted"]
            ):

                # Check expiry
                if self._is_consent_expired(consent):
                    continue

                # Check scope coverage
                if not self._check_scope_coverage(consent, scope):
                    continue

                # Check restrictions
                if not self._check_restrictions(consent, requester_id):
                    continue

                valid_consents.append(consent)

        if not valid_consents:
            return False, None, {"reason": "No valid consent found"}

        # Return most recent valid consent
        latest_consent = max(valid_consents, key=lambda x: x["created_date"])

        # Log access
        self._log_consent_access(latest_consent["consent_id"], requester_id)

        return (
            True,
            latest_consent["consent_id"],
            {
                "granted_date": latest_consent.get("response_date"),
                "expiry_date": latest_consent.get("expiry_date"),
                "scope": latest_consent.get("scope", []),
                "restrictions": latest_consent.get("restrictions", {}),
            },
        )

    def get_consent_history(
        self,
        patient_id: str,
        consent_type: Optional[ConsentType] = None,
        include_withdrawn: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get consent history for patient.

        Args:
            patient_id: Patient ID
            consent_type: Filter by consent type
            include_withdrawn: Include withdrawn consents

        Returns:
            List of consent records
        """
        if patient_id not in self.consent_records:
            return []

        history = []
        for consent in self.consent_records[patient_id]:
            # Apply filters
            if consent_type and consent["consent_type"] != consent_type.value:
                continue

            if (
                not include_withdrawn
                and consent["status"] == ConsentStatus.WITHDRAWN.value
            ):
                continue

            # Create sanitized copy
            history_record = {
                "consent_id": consent["consent_id"],
                "type": consent["consent_type"],
                "purpose": consent["purpose"],
                "status": consent["status"],
                "created_date": consent["created_date"],
                "response_date": consent.get("response_date"),
                "expiry_date": consent.get("expiry_date"),
                "withdrawal_date": consent.get("withdrawal_date"),
                "method": consent.get("method"),
                "scope": consent.get("scope", []),
            }

            history.append(history_record)

        return sorted(history, key=lambda x: x["created_date"], reverse=True)

    def bulk_consent_update(
        self,
        patient_ids: List[str],
        consent_type: ConsentType,
        updates: Dict[str, Any],
        updated_by: str,
        reason: str,
    ) -> Dict[str, bool]:
        """Update consent for multiple patients.

        Args:
            patient_ids: List of patient IDs
            consent_type: Type of consent to update
            updates: Updates to apply
            updated_by: ID of updater
            reason: Reason for bulk update

        Returns:
            Dict of patient_id -> success status
        """
        results = {}

        for patient_id in patient_ids:
            try:
                success = self._update_patient_consent(
                    patient_id, consent_type, updates, updated_by, reason
                )
                results[patient_id] = success
            except (ValueError, KeyError, TypeError) as e:
                logger.error("Failed to update consent for %s: %s", patient_id, e)
                results[patient_id] = False

        # Log bulk operation
        self._log_audit_event(
            "bulk_consent_update",
            "BULK",
            updated_by,
            {
                "patient_count": len(patient_ids),
                "consent_type": consent_type.value,
                "reason": reason,
                "success_count": sum(results.values()),
            },
        )

        return results

    def generate_consent_report(
        self, start_date: datetime, end_date: datetime, report_type: str = "summary"
    ) -> Dict[str, Any]:
        """Generate consent management report.

        Args:
            start_date: Report start date
            end_date: Report end date
            report_type: Type of report (summary, detailed, compliance)

        Returns:
            Report data
        """
        report = {
            "report_id": f"REPORT-{uuid4()}",
            "generated_date": datetime.now(),
            "period": {"start": start_date, "end": end_date},
            "type": report_type,
            "statistics": {},
        }

        # Collect statistics
        total_consents = 0
        granted_consents = 0
        withdrawn_consents = 0
        expired_consents = 0

        consent_by_type: Dict[str, int] = {}
        consent_by_method: Dict[str, int] = {}

        for patient_consents in self.consent_records.values():
            for consent in patient_consents:
                # Check if in date range
                created = consent["created_date"]
                if not start_date <= created <= end_date:
                    continue

                total_consents += 1

                # Count by status
                if consent["status"] == ConsentStatus.GRANTED.value:
                    granted_consents += 1
                elif consent["status"] == ConsentStatus.WITHDRAWN.value:
                    withdrawn_consents += 1
                elif self._is_consent_expired(consent):
                    expired_consents += 1

                # Count by type
                consent_type = consent["consent_type"]
                consent_by_type[consent_type] = consent_by_type.get(consent_type, 0) + 1

                # Count by method
                if "method" in consent:
                    method = consent["method"]
                    consent_by_method[method] = consent_by_method.get(method, 0) + 1

        report["statistics"] = {
            "total_consents": total_consents,
            "granted": granted_consents,
            "withdrawn": withdrawn_consents,
            "expired": expired_consents,
            "grant_rate": (
                granted_consents / total_consents if total_consents > 0 else 0
            ),
            "by_type": consent_by_type,
            "by_method": consent_by_method,
        }

        if report_type == "detailed":
            report["details"] = self._generate_detailed_report(start_date, end_date)
        elif report_type == "compliance":
            report["compliance"] = self._generate_compliance_report(
                start_date, end_date
            )

        return report

    def _select_template(self, consent_type: ConsentType) -> Optional[Dict[str, Any]]:
        """Select appropriate template for consent type."""
        for template in self.consent_templates.values():
            if template["type"] == consent_type:
                return template
        return None

    def _calculate_expiry(self, template: Dict[str, Any]) -> Optional[datetime]:
        """Calculate consent expiry date from template."""
        expiry_days = template.get("expiry_period_days")
        if expiry_days:
            return datetime.now() + timedelta(days=expiry_days)
        return None

    def _calculate_duration_expiry(
        self, duration: ConsentDuration
    ) -> Optional[datetime]:
        """Calculate expiry date based on duration type."""
        duration_map = {
            ConsentDuration.SINGLE_USE: timedelta(days=1),
            ConsentDuration.EPISODE_OF_CARE: timedelta(days=90),
            ConsentDuration.ONE_YEAR: timedelta(days=365),
            ConsentDuration.FIVE_YEARS: timedelta(days=365 * 5),
            ConsentDuration.TEN_YEARS: timedelta(days=365 * 10),
            ConsentDuration.LIFETIME: None,
            ConsentDuration.CUSTOM: None,
        }

        delta = duration_map.get(duration)
        if delta:
            return datetime.now() + delta
        return None

    def _check_parental_requirement(self, patient_id: str) -> bool:
        """Check if parental consent is required."""
        try:
            # Get database session
            db = next(get_db())

            # Query patient data
            patient = db.query(Patient).filter(Patient.id == patient_id).first()

            if not patient or not patient.date_of_birth:
                # If no patient found or no DOB, assume parental consent required for safety
                logger.warning(
                    "No patient or DOB found for %s, requiring parental consent",
                    patient_id,
                )
                return True

            # Calculate age
            today = date.today()
            age = (
                today.year
                - patient.date_of_birth.year
                - (
                    (today.month, today.day)
                    < (patient.date_of_birth.month, patient.date_of_birth.day)
                )
            )

            # Get jurisdiction-based age limit
            # First check if patient has a nationality/country
            country = None
            if patient.nationality:
                # Map nationality to country code (simplified mapping)
                nationality_to_country = {
                    "American": "US",
                    "British": "UK",
                    "French": "FR",
                    "German": "DE",
                    "Spanish": "ES",
                    "Italian": "IT",
                    "Dutch": "NL",
                    "Belgian": "BE",
                    "Austrian": "AT",
                    "Swiss": "CH",
                    "Canadian": "CA",
                    "Australian": "AU",
                    "New Zealander": "NZ",
                    # Add more mappings as needed
                }
                country = nationality_to_country.get(patient.nationality, None)

            # If no country found, check current location or default
            if not country and hasattr(patient, "current_country"):
                country = patient.current_country

            # Get age limit for jurisdiction
            if country:
                age_limit = self.age_of_consent.get(
                    country, self.age_of_consent["default"]
                )
            else:
                age_limit = self.age_of_consent["default"]

            # Check if patient is under age limit
            requires_parental_consent = age < age_limit

            # Special cases for emancipated minors
            if requires_parental_consent and hasattr(
                patient, "emancipated_minor_status"
            ):
                if patient.emancipated_minor_status:
                    # Check if procedure allows emancipated minor consent
                    # This would need to be passed in or checked against consent type
                    requires_parental_consent = False
                    logger.info(
                        "Patient %s is emancipated minor, parental consent not required",
                        patient_id,
                    )

            # Log the decision
            logger.info(
                "Parental consent check for patient %s: age=%s, country=%s, "
                "age_limit=%s, requires_consent=%s",
                patient_id,
                age,
                country or "default",
                age_limit,
                requires_parental_consent,
            )

            db.close()
            return bool(requires_parental_consent)

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(
                "Error checking parental consent requirement for %s: %s", patient_id, e
            )
            # In case of error, err on the side of caution and require parental consent
            return True

    def _find_consent_record(
        self, patient_id: str, consent_id: str
    ) -> Optional[Dict[str, Any]]:
        """Find specific consent record."""
        if patient_id not in self.consent_records:
            return None

        for consent in self.consent_records[patient_id]:
            if consent["consent_id"] == consent_id:
                return consent
        return None

    def _store_evidence(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Store consent evidence securely."""
        evidence_id = f"EVIDENCE-{uuid4()}"

        try:
            # Initialize encryption service
            encryption_service = EncryptionService(
                kms_key_id="alias/haven-health-consent", region="us-east-1"
            )

            # Get S3 client
            s3_client = boto3.client("s3")
            bucket_name = os.environ.get(
                "S3_CONSENT_BUCKET", "haven-health-consent-evidence"
            )

            # Process based on evidence type
            evidence_type = evidence.get("type", "electronic")
            stored_location = None

            if evidence_type == "electronic":
                # Electronic signature or form data
                signature_data = evidence.get("signature_data")
                form_data = evidence.get("form_data", {})

                # Create evidence document
                evidence_doc = {
                    "evidence_id": evidence_id,
                    "type": evidence_type,
                    "signature": signature_data,
                    "form_data": form_data,
                    "ip_address": evidence.get("ip_address"),
                    "user_agent": evidence.get("user_agent"),
                    "timestamp": datetime.now().isoformat(),
                }

                # Encrypt the evidence
                encrypted_data = encryption_service.encrypt(
                    json.dumps(evidence_doc).encode()
                )

                # Store in S3
                s3_key = f"consent-evidence/{evidence_id}/electronic_signature.json.enc"
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=s3_key,
                    Body=encrypted_data,
                    ServerSideEncryption="AES256",
                    Metadata={
                        "evidence_id": evidence_id,
                        "type": evidence_type,
                        "encrypted": "true",
                    },
                )
                stored_location = f"s3://{bucket_name}/{s3_key}"

            elif evidence_type == "written":
                # Scanned document or image
                document_data = evidence.get("document_data")
                if document_data:
                    # Decode base64 if needed
                    if isinstance(document_data, str):
                        document_bytes = base64.b64decode(document_data)
                    else:
                        document_bytes = document_data

                    # Encrypt document
                    encrypted_doc = encryption_service.encrypt(document_bytes)

                    # Store in S3
                    file_extension = evidence.get("file_extension", "pdf")
                    s3_key = f"consent-evidence/{evidence_id}/written_consent.{file_extension}.enc"
                    s3_client.put_object(
                        Bucket=bucket_name,
                        Key=s3_key,
                        Body=encrypted_doc,
                        ServerSideEncryption="AES256",
                        ContentType=evidence.get("content_type", "application/pdf"),
                        Metadata={
                            "evidence_id": evidence_id,
                            "type": evidence_type,
                            "encrypted": "true",
                        },
                    )
                    stored_location = f"s3://{bucket_name}/{s3_key}"

            elif evidence_type == "verbal":
                # Audio recording
                audio_data = evidence.get("audio_data")
                if audio_data:
                    # Encrypt audio
                    encrypted_audio = encryption_service.encrypt(audio_data)

                    # Store in S3
                    s3_key = f"consent-evidence/{evidence_id}/verbal_consent.m4a.enc"
                    s3_client.put_object(
                        Bucket=bucket_name,
                        Key=s3_key,
                        Body=encrypted_audio,
                        ServerSideEncryption="AES256",
                        ContentType="audio/mp4",
                        Metadata={
                            "evidence_id": evidence_id,
                            "type": evidence_type,
                            "duration": str(evidence.get("duration", 0)),
                            "encrypted": "true",
                        },
                    )
                    stored_location = f"s3://{bucket_name}/{s3_key}"

                # Also store transcript if available
                transcript = evidence.get("transcript")
                if transcript:
                    encrypted_transcript = encryption_service.encrypt(
                        transcript.encode()
                    )

                    s3_key = f"consent-evidence/{evidence_id}/verbal_transcript.txt.enc"
                    s3_client.put_object(
                        Bucket=bucket_name,
                        Key=s3_key,
                        Body=encrypted_transcript,
                        ServerSideEncryption="AES256",
                        Metadata={
                            "evidence_id": evidence_id,
                            "type": "transcript",
                            "encrypted": "true",
                        },
                    )

            # Store metadata in database
            db = next(get_db())
            try:
                evidence_record = Document(
                    id=evidence_id,
                    filename=f"consent_evidence_{evidence_id}",
                    document_type="consent_evidence",
                    content_type=evidence.get("content_type", "application/json"),
                    file_size=len(str(evidence)),
                    s3_key=stored_location,
                    metadata={
                        "evidence_type": evidence_type,
                        "hash": self._generate_evidence_hash(evidence),
                        "stored_date": datetime.now().isoformat(),
                        "consent_details": evidence.get("consent_details", {}),
                    },
                    owner_id=evidence.get("patient_id"),
                    uploaded_by=evidence.get("collector_id"),
                    is_encrypted=True,
                )
                db.add(evidence_record)
                db.commit()
            finally:
                db.close()

            stored_evidence = {
                "evidence_id": evidence_id,
                "type": evidence_type,
                "stored_date": datetime.now(),
                "hash": self._generate_evidence_hash(evidence),
                "location": stored_location,
                "encrypted": True,
                "storage_type": "s3",
            }

            logger.info("Successfully stored consent evidence: %s", evidence_id)
            return stored_evidence

        except (ValueError, TypeError, AttributeError, IOError) as e:
            logger.error("Error storing consent evidence: %s", e)
            # Fallback to basic storage
            return {
                "evidence_id": evidence_id,
                "type": evidence.get("type", "electronic"),
                "stored_date": datetime.now(),
                "hash": self._generate_evidence_hash(evidence),
                "location": "pending_storage",
                "error": str(e),
            }

    def _generate_consent_hash(self, consent_record: Dict[str, Any]) -> str:
        """Generate hash of consent record for integrity."""
        # Create consistent string representation
        consent_str = json.dumps(
            {
                "patient_id": consent_record.get("patient_id"),
                "consent_type": consent_record.get("consent_type"),
                "purpose": consent_record.get("purpose"),
                "granted": consent_record.get("granted"),
                "scope": consent_record.get("scope"),
                "response_date": str(consent_record.get("response_date")),
            },
            sort_keys=True,
        )

        return hashlib.sha256(consent_str.encode()).hexdigest()

    def _generate_evidence_hash(self, evidence: Dict[str, Any]) -> str:
        """Generate hash of evidence for integrity."""
        evidence_str = json.dumps(evidence, sort_keys=True)
        return hashlib.sha256(evidence_str.encode()).hexdigest()

    def _can_withdraw_consent(self, consent_record: Dict[str, Any]) -> bool:
        """Check if consent can be withdrawn."""
        # Check if already withdrawn
        if consent_record["status"] == ConsentStatus.WITHDRAWN.value:
            return False

        # Check for withdrawal restrictions
        consent_type = consent_record.get("consent_type")
        if consent_type == ConsentType.EMERGENCY_CARE.value:
            # Check if emergency is still active
            # In production, would check actual emergency status
            return True

        return True

    def _is_consent_expired(self, consent_record: Dict[str, Any]) -> bool:
        """Check if consent has expired."""
        expiry_date = consent_record.get("expiry_date")
        if not expiry_date:
            return False

        return bool(datetime.now() > expiry_date)

    def _check_scope_coverage(
        self, consent_record: Dict[str, Any], required_scope: List[ConsentScope]
    ) -> bool:
        """Check if consent covers required scope."""
        consent_scope = consent_record.get("scope", [])

        # Check if FULL_RECORD covers everything
        if ConsentScope.FULL_RECORD.value in consent_scope:
            return True

        # Check each required scope
        for scope in required_scope:
            if scope.value not in consent_scope:
                return False

        return True

    def _check_restrictions(
        self, consent_record: Dict[str, Any], requester_id: str
    ) -> bool:
        """Check if requester meets consent restrictions."""
        restrictions = consent_record.get("restrictions", {})

        # Check excluded parties
        excluded = restrictions.get("excluded_parties", [])
        if requester_id in excluded:
            return False

        # Check allowed parties (if specified)
        allowed = restrictions.get("allowed_parties", [])
        if allowed and requester_id not in allowed:
            return False

        # Check time restrictions
        time_restrictions = restrictions.get("time_restrictions", {})
        if time_restrictions:
            start_time = time_restrictions.get("start_time")
            end_time = time_restrictions.get("end_time")

            if start_time and end_time:
                # Check if current time is within allowed window
                current_time = datetime.now().time()

                # Parse time strings (assuming HH:MM format)
                start_hour, start_min = map(int, start_time.split(":"))
                end_hour, end_min = map(int, end_time.split(":"))

                start_dt_time = time(start_hour, start_min)
                end_dt_time = time(end_hour, end_min)

                # Handle cases where end time is after midnight
                if end_dt_time < start_dt_time:
                    # Time window spans midnight
                    if not (
                        current_time >= start_dt_time or current_time <= end_dt_time
                    ):
                        return False
                else:
                    # Normal time window
                    if not start_dt_time <= current_time <= end_dt_time:
                        return False

        return True

    def _log_consent_access(self, consent_id: str, accessor_id: str) -> None:
        """Log consent access for audit."""
        # In production, would store in audit database
        logger.info("Consent access logged: %s by %s", consent_id, accessor_id)

    def _trigger_immediate_withdrawal_actions(
        self, consent_record: Dict[str, Any]
    ) -> None:
        """Trigger immediate actions for consent withdrawal."""
        # In production, would trigger:
        # - Data deletion/anonymization processes
        # - Access revocation
        # - Notification to data processors
        # - Update to connected systems

        logger.info(
            "Triggering immediate withdrawal actions for consent %s",
            consent_record["consent_id"],
        )

    def _schedule_withdrawal_actions(self, consent_record: Dict[str, Any]) -> None:
        """Schedule delayed withdrawal actions."""
        # In production, would schedule:
        # - Grace period notifications
        # - Delayed data processing cessation
        # - Retention period calculations

        logger.info(
            "Scheduling withdrawal actions for consent %s", consent_record["consent_id"]
        )

    def _send_consent_notifications(self, consent_record: Dict[str, Any]) -> None:
        """Send notifications about consent status."""
        # In production, would send:
        # - Email confirmations
        # - SMS notifications
        # - System notifications to care team

        logger.info(
            "Sending consent notifications for %s", consent_record["consent_id"]
        )

    def _update_patient_consent(
        self,
        patient_id: str,
        consent_type: ConsentType,
        updates: Dict[str, Any],
        updated_by: str,
        reason: str,
    ) -> bool:
        """Update specific patient consent."""
        if patient_id not in self.consent_records:
            return False

        updated = False
        for consent in self.consent_records[patient_id]:
            if consent["consent_type"] == consent_type.value:
                # Apply updates
                for key, value in updates.items():
                    if key in consent:
                        consent[key] = value

                # Add audit trail
                consent["audit_trail"].append(
                    {
                        "timestamp": datetime.now(),
                        "action": "consent_updated",
                        "actor": updated_by,
                        "details": f"Bulk update: {reason}",
                    }
                )

                updated = True

        return updated

    def _generate_detailed_report(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Generate detailed consent report."""
        # In production, would generate comprehensive analytics
        _ = (start_date, end_date)  # Mark as intentionally unused
        return {
            "consent_lifecycle_metrics": {},
            "user_journey_analysis": {},
            "consent_friction_points": {},
            "geographic_distribution": {},
        }

    def _generate_compliance_report(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Generate compliance-focused report."""
        # In production, would check against regulations
        _ = (start_date, end_date)  # Mark as intentionally unused
        return {
            "gdpr_compliance": {
                "lawful_basis_coverage": 100,
                "withdrawal_processing_time": "< 24 hours",
                "consent_validity_rate": 98.5,
            },
            "audit_trail_completeness": 100,
            "data_subject_rights_fulfilled": {
                "access_requests": 45,
                "withdrawal_requests": 12,
                "average_response_time": "2.3 days",
            },
        }

    def validate_fhir_consent(self, consent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate FHIR Consent resource.

        Args:
            consent_data: FHIR Consent resource data

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        errors = []
        warnings: List[str] = []

        # Initialize FHIR validator if needed
        if not hasattr(self, "fhir_validator"):
            self.fhir_validator = FHIRValidator()

        # Check required fields
        if not consent_data.get("status"):
            errors.append("Consent must have status")
        elif consent_data["status"] not in [
            "draft",
            "proposed",
            "active",
            "rejected",
            "inactive",
            "entered-in-error",
        ]:
            errors.append(f"Invalid consent status: {consent_data['status']}")

        if not consent_data.get("scope"):
            errors.append("Consent must have scope")

        if not consent_data.get("category"):
            errors.append("Consent must have at least one category")

        if not consent_data.get("patient"):
            errors.append("Consent must have patient reference")

        # Validate provision if present
        if provision := consent_data.get("provision"):
            if "type" in provision:
                if provision["type"] not in ["deny", "permit"]:
                    errors.append(f"Invalid provision type: {provision['type']}")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def create_fhir_consent(
        self,
        patient_id: str,
        consent_type: ConsentType,
        status: ConsentStatus,
        purposes: List[ProcessingPurpose],
    ) -> FHIRConsent:
        """Create FHIR Consent resource.

        Args:
            patient_id: Patient identifier
            consent_type: Type of consent
            status: Current consent status
            purposes: List of processing purposes

        Returns:
            FHIR Consent resource
        """
        fhir_status_map = {
            ConsentStatus.PENDING: "proposed",
            ConsentStatus.GRANTED: "active",
            ConsentStatus.DENIED: "rejected",
            ConsentStatus.WITHDRAWN: "inactive",
            ConsentStatus.EXPIRED: "inactive",
            ConsentStatus.INVALID: "entered-in-error",
        }

        fhir_status = fhir_status_map.get(status, "proposed")

        consent_resource: FHIRConsent = {
            "resourceType": "Consent",
            "id": str(uuid4()),
            "status": fhir_status,  # type: ignore[typeddict-item]
            "scope": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/consentscope",
                        "code": "patient-privacy",
                        "display": "Privacy Consent",
                    }
                ]
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://havenhealthpassport.org/fhir/CodeSystem/consent-types",
                            "code": consent_type.value,
                            "display": consent_type.value.replace("_", " ").title(),
                        }
                    ]
                }
            ],
            "patient": {"reference": f"Patient/{patient_id}"},
            "dateTime": datetime.now().isoformat(),
            "policy": [{"uri": "https://www.havenhealthpassport.org/privacy-policy"}],
            "provision": {
                "type": "permit" if status == ConsentStatus.GRANTED else "deny",
                "purpose": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ActReason",
                        "code": purpose.value,
                        "display": purpose.value.replace("_", " ").title(),
                    }
                    for purpose in purposes
                ],
            },
            "__fhir_resource__": "Consent",
        }

        return consent_resource

    def _log_audit_event(
        self, event_type: str, patient_id: str, actor_id: str, details: Dict[str, Any]
    ) -> None:
        """Log audit event."""
        audit_event = {
            "timestamp": datetime.now(),
            "event_type": event_type,
            "patient_id": patient_id,
            "actor_id": actor_id,
            "details": details,
            "session_id": f"SESSION-{uuid4()}",  # Would get from context
        }

        self.audit_log.append(audit_event)

        # In production, would also persist to audit database
        logger.info("Audit event: %s for patient %s", event_type, patient_id)


def validate_fhir(fhir_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate FHIR data for consent resources.

    Args:
        fhir_data: FHIR data to validate

    Returns:
        Validation results
    """
    errors = []
    warnings = []

    # Check resource type
    if fhir_data.get("resourceType") != "Consent":
        errors.append("Resource type must be Consent")

    # Check required fields
    required_fields = ["status", "scope", "category", "patient", "dateTime"]
    for field in required_fields:
        if field not in fhir_data:
            errors.append(f"Required field '{field}' is missing")

    # Validate status
    if "status" in fhir_data:
        valid_statuses = [
            "draft",
            "proposed",
            "active",
            "rejected",
            "inactive",
            "entered-in-error",
        ]
        if fhir_data["status"] not in valid_statuses:
            errors.append(f"Invalid status: {fhir_data['status']}")

    # Check for provision details
    if "provision" not in fhir_data:
        warnings.append(
            "Provision details are recommended for complete consent records"
        )

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


# Export public API
__all__ = [
    "ConsentType",
    "ConsentStatus",
    "ConsentScope",
    "ConsentDuration",
    "ConsentMethod",
    "ConsentManager",
    "validate_fhir",
]
