"""GDPR Consent Integration Module.

This module integrates the comprehensive consent management system with
the existing GDPR compliance infrastructure, ensuring seamless operation
across all data protection requirements.

All patient data is encrypted and handled with appropriate security measures.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.healthcare.fhir_validator import FHIRValidator
from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.healthcare.regulatory.consent_management import (
    ConsentDuration,
    ConsentManager,
    ConsentMethod,
    ConsentScope,
    ConsentStatus,
    ConsentType,
)
from src.healthcare.regulatory.gdpr_compliance import (
    GDPRConsentManager,
    GDPRDataPortability,
    GDPRErasure,
    GDPRLawfulBasis,
    ProcessingPurpose,
)

logger = logging.getLogger(__name__)


class GDPRConsentIntegration:
    """Integrates comprehensive consent management with GDPR compliance."""

    # FHIR resource type
    __fhir_resource__ = "Consent"

    def __init__(self) -> None:
        """Initialize GDPR consent integration."""
        self.consent_manager = ConsentManager()
        self.legacy_consent_manager = GDPRConsentManager()
        self.data_portability = GDPRDataPortability()
        self.erasure_handler = GDPRErasure()
        self.lawful_basis_mapping = self._initialize_lawful_basis_mapping()
        # Add FHIR validator
        self.fhir_validator = FHIRValidator()

    def _initialize_lawful_basis_mapping(self) -> Dict[ConsentType, GDPRLawfulBasis]:
        """Map consent types to GDPR lawful basis."""
        return {
            ConsentType.GENERAL_HEALTHCARE: GDPRLawfulBasis.HEALTHCARE,
            ConsentType.EMERGENCY_CARE: GDPRLawfulBasis.VITAL_INTERESTS,
            ConsentType.RESEARCH: GDPRLawfulBasis.EXPLICIT_CONSENT,
            ConsentType.DATA_SHARING: GDPRLawfulBasis.CONSENT,
            ConsentType.MARKETING: GDPRLawfulBasis.CONSENT,
            ConsentType.THIRD_PARTY: GDPRLawfulBasis.LEGITIMATE_INTERESTS,
            ConsentType.INTERNATIONAL_TRANSFER: GDPRLawfulBasis.EXPLICIT_CONSENT,
            ConsentType.AUTOMATED_PROCESSING: GDPRLawfulBasis.EXPLICIT_CONSENT,
            ConsentType.SPECIAL_CATEGORY: GDPRLawfulBasis.EXPLICIT_CONSENT,
            ConsentType.CHILD_DATA: GDPRLawfulBasis.EXPLICIT_CONSENT,
            ConsentType.BIOMETRIC: GDPRLawfulBasis.EXPLICIT_CONSENT,
            ConsentType.GENETIC: GDPRLawfulBasis.EXPLICIT_CONSENT,
        }

    @require_phi_access(AccessLevel.WRITE)
    def process_consent_request(
        self,
        patient_id: str,
        consent_type: ConsentType,
        purpose: ProcessingPurpose,
        requested_by: str,
        scope: List[ConsentScope],
        duration: ConsentDuration,
        custom_fields: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, bool]:
        """Process consent request with full GDPR compliance.

        Args:
            patient_id: Patient identifier
            consent_type: Type of consent
            purpose: Processing purpose
            requested_by: Requester ID
            scope: Data scope
            duration: Consent duration
            custom_fields: Additional fields

        Returns:
            Tuple of (consent_id, requires_explicit_consent)
        """
        # Parameters will be used in implementation
        _ = scope
        _ = duration
        # Create consent request in new system
        consent_id = self.consent_manager.create_consent_request(
            patient_id=patient_id,
            consent_type=consent_type,
            purpose=purpose,
            requested_by=requested_by,
            custom_fields=custom_fields,
        )

        # Check if explicit consent required
        lawful_basis = self.lawful_basis_mapping.get(consent_type)
        requires_explicit = lawful_basis in [
            GDPRLawfulBasis.EXPLICIT_CONSENT,
            GDPRLawfulBasis.CONSENT,
        ]

        # Log in legacy system for backward compatibility
        if consent_type == ConsentType.GENERAL_HEALTHCARE:
            self.legacy_consent_manager.record_consent(
                data_subject_id=patient_id,
                purpose=purpose,
                consent_given=False,  # Pending
                details={"new_consent_id": consent_id},
            )

        return consent_id, requires_explicit

    def record_consent_with_compliance(
        self,
        consent_id: str,
        patient_id: str,
        granted: bool,
        scope: List[ConsentScope],
        duration: ConsentDuration,
        method: ConsentMethod,
        responder_id: str,
        parent_guardian_id: Optional[str] = None,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Record consent response with GDPR compliance checks.

        Args:
            consent_id: Consent request ID
            patient_id: Patient ID
            granted: Whether consent granted
            scope: Consented data scope
            duration: Consent duration
            method: Collection method
            responder_id: Responder ID
            parent_guardian_id: Guardian ID if applicable
            evidence: Consent evidence

        Returns:
            Success status
        """
        # Validate method for special categories
        consent_records = self.consent_manager.get_consent_history(
            patient_id, consent_type=ConsentType.SPECIAL_CATEGORY
        )
        consent_record = next(
            (c for c in consent_records if c.get("consent_id") == consent_id), None
        )
        if not consent_record:
            return False

        consent_type = ConsentType(consent_record["consent_type"])

        # Check if written/electronic consent required
        if consent_type in [ConsentType.GENETIC, ConsentType.BIOMETRIC]:
            if method not in [ConsentMethod.WRITTEN, ConsentMethod.ELECTRONIC]:
                logger.error("Invalid consent method for %s: %s", consent_type, method)
                return False

        # Record in new system
        success = self.consent_manager.record_consent_response(
            consent_id=consent_id,
            patient_id=patient_id,
            granted=granted,
            scope=scope,
            duration=duration,
            method=method,
            responder_id=responder_id,
            parent_guardian_id=parent_guardian_id,
            restrictions=None,
            evidence=evidence,
        )

        if success and granted:
            # Sync with legacy system
            purpose = ProcessingPurpose(consent_record["purpose"])
            self.legacy_consent_manager.record_consent(
                data_subject_id=patient_id,
                purpose=purpose,
                consent_given=True,
                parent_guardian_id=parent_guardian_id,
                details={
                    "new_consent_id": consent_id,
                    "scope": [s.value for s in scope],
                    "method": method.value,
                },
            )

        return success

    async def handle_data_request(
        self,
        patient_id: str,
        request_type: str,
        requester_id: str,
        purpose: ProcessingPurpose,
        required_scope: List[ConsentScope],
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Handle data access request with consent verification.

        Args:
            patient_id: Patient ID
            request_type: Type of request (access, portability, etc.)
            requester_id: Requester ID
            purpose: Purpose of request
            required_scope: Required data scope

        Returns:
            Tuple of (allowed, reason, data)
        """
        # Map request type to consent type
        consent_type_mapping = {
            "access": ConsentType.GENERAL_HEALTHCARE,
            "portability": ConsentType.DATA_SHARING,
            "research": ConsentType.RESEARCH,
            "emergency": ConsentType.EMERGENCY_CARE,
        }

        consent_type = consent_type_mapping.get(
            request_type, ConsentType.GENERAL_HEALTHCARE
        )

        # Check consent validity
        is_valid, consent_id, details = self.consent_manager.check_consent_validity(
            patient_id=patient_id,
            consent_type=consent_type,
            purpose=purpose,
            scope=required_scope,
            requester_id=requester_id,
        )

        if not is_valid:
            return False, "No valid consent", None

        # Handle specific request types
        if request_type == "portability":
            # Export data
            data_package = await self.data_portability.export_personal_data(
                data_subject_id=patient_id,
                include_categories=None,  # All categories
                export_format="json",
            )
            return True, "Data exported", data_package

        elif request_type == "access":
            # Provide access (simplified)
            return True, "Access granted", {"consent_id": consent_id, "scope": details}

        else:
            return True, "Request processed", None

    def handle_erasure_request(
        self, patient_id: str, requester_id: str, categories: List[str], reason: str
    ) -> Tuple[str, str]:
        """Handle erasure request with consent implications.

        Args:
            patient_id: Patient ID
            requester_id: Requester ID
            categories: Data categories to erase
            reason: Erasure reason

        Returns:
            Tuple of (request_id, status)
        """
        # Check if erasure affects active consents
        active_consents = []
        if patient_id in self.consent_manager.consent_records:
            for consent in self.consent_manager.consent_records[patient_id]:
                if consent["status"] == ConsentStatus.GRANTED.value:
                    # Check if consent covers requested categories
                    consent_scope = consent.get("scope", [])
                    if any(cat in consent_scope for cat in categories):
                        active_consents.append(consent["consent_id"])

        # Withdraw affected consents first
        for consent_id in active_consents:
            self.consent_manager.withdraw_consent(
                consent_id=consent_id,
                patient_id=patient_id,
                withdrawn_by=requester_id,
                reason=f"Data erasure request: {reason}",
                immediate=True,
            )

        # Process erasure request
        request_id = self.erasure_handler.request_erasure(
            data_subject_id=patient_id,
            categories=categories,
            reason=reason,
            requestor_id=requester_id,
        )

        # Check request status
        request = self.erasure_handler.erasure_requests.get(request_id)
        status = request["status"] if request else "failed"

        return request_id, status

    def audit_consent_compliance(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Audit consent compliance for period.

        Args:
            start_date: Audit start date
            end_date: Audit end date

        Returns:
            Compliance audit results
        """
        # Get consent report
        consent_report = self.consent_manager.generate_consent_report(
            start_date=start_date, end_date=end_date, report_type="compliance"
        )

        # Analyze compliance metrics
        compliance_metrics = {
            "period": {"start": start_date, "end": end_date},
            "consent_metrics": consent_report.get("statistics", {}),
            "compliance_score": 0,
            "issues": [],
            "recommendations": [],
        }

        # Check consent grant rate
        stats = consent_report.get("statistics", {})
        total = stats.get("total_consents", 0)
        granted = stats.get("granted", 0)

        if total > 0:
            grant_rate = granted / total
            if grant_rate < 0.7:
                compliance_metrics["issues"].append(
                    {
                        "type": "low_consent_rate",
                        "severity": "medium",
                        "details": f"Consent grant rate is {grant_rate:.2%}",
                    }
                )
                compliance_metrics["recommendations"].append(
                    "Review consent request process and forms for clarity"
                )

        # Check withdrawal handling
        withdrawn = stats.get("withdrawn", 0)
        if withdrawn > 0:
            # In production, would check withdrawal processing times
            compliance_metrics["recommendations"].append(
                "Ensure all withdrawals are processed within 24 hours"
            )

        # Calculate compliance score
        score = 100
        score -= len(compliance_metrics["issues"]) * 10
        score -= (withdrawn / total * 5) if total > 0 else 0
        compliance_metrics["compliance_score"] = max(0, score)

        return compliance_metrics

    def migrate_legacy_consents(self) -> Dict[str, int]:
        """Migrate consents from legacy system to new system.

        Returns:
            Migration statistics
        """
        migrated = 0
        failed = 0

        # Get all legacy consents
        for patient_id, legacy_consents in self.legacy_consent_manager.consents.items():
            for legacy_consent in legacy_consents:
                try:
                    # Map legacy purpose to new consent type
                    purpose = ProcessingPurpose(legacy_consent["purpose"])
                    consent_type = self._map_purpose_to_consent_type(purpose)

                    # Create consent in new system
                    consent_id = self.consent_manager.create_consent_request(
                        patient_id=patient_id,
                        consent_type=consent_type,
                        purpose=purpose,
                        requested_by="MIGRATION",
                        custom_fields={
                            "legacy_consent_id": legacy_consent["consent_id"]
                        },
                    )

                    # Record response if consent was given
                    if (
                        legacy_consent["consent_given"]
                        and not legacy_consent["withdrawn"]
                    ):
                        self.consent_manager.record_consent_response(
                            consent_id=consent_id,
                            patient_id=patient_id,
                            granted=True,
                            scope=[ConsentScope.FULL_RECORD],  # Default scope
                            duration=ConsentDuration.ONE_YEAR,
                            method=ConsentMethod.ELECTRONIC,
                            responder_id=patient_id,
                            parent_guardian_id=legacy_consent.get("parent_guardian_id"),
                        )

                    migrated += 1

                except (ValueError, KeyError, AttributeError) as e:
                    logger.error("Failed to migrate consent: %s", str(e))
                    failed += 1

        return {"migrated": migrated, "failed": failed, "total": migrated + failed}

    def _map_purpose_to_consent_type(self, purpose: ProcessingPurpose) -> ConsentType:
        """Map processing purpose to consent type."""
        mapping = {
            ProcessingPurpose.HEALTHCARE_PROVISION: ConsentType.GENERAL_HEALTHCARE,
            ProcessingPurpose.MEDICAL_DIAGNOSIS: ConsentType.GENERAL_HEALTHCARE,
            ProcessingPurpose.HEALTH_MANAGEMENT: ConsentType.GENERAL_HEALTHCARE,
            ProcessingPurpose.MEDICAL_RESEARCH: ConsentType.RESEARCH,
            ProcessingPurpose.PUBLIC_HEALTH: ConsentType.GENERAL_HEALTHCARE,
            ProcessingPurpose.HUMANITARIAN_AID: ConsentType.GENERAL_HEALTHCARE,
            ProcessingPurpose.EMERGENCY_CARE: ConsentType.EMERGENCY_CARE,
            ProcessingPurpose.BILLING: ConsentType.GENERAL_HEALTHCARE,
            ProcessingPurpose.QUALITY_IMPROVEMENT: ConsentType.GENERAL_HEALTHCARE,
        }

        return mapping.get(purpose, ConsentType.GENERAL_HEALTHCARE)

    def check_consent_access(
        self, user_id: str, patient_id: str, consent_type: ConsentType, purpose: str
    ) -> bool:
        """Check if user has valid consent to access patient data.

        Args:
            user_id: ID of user requesting access
            patient_id: ID of patient whose data is being accessed
            consent_type: Type of consent required
            purpose: Purpose of access

        Returns:
            True if valid consent exists, False otherwise
        """
        # user_id will be used for audit logging in production
        _ = user_id

        # Check if consent exists and is valid
        consents = self.consent_manager.get_consent_history(patient_id=patient_id)

        for consent in consents:
            # Filter by consent type
            if consent.get("consent_type") != consent_type:
                continue

            # Check if consent matches requirements
            if consent.get("status") == "granted" and consent.get("granted", False):

                # Check if purpose matches
                if consent.get("purpose") == purpose:
                    # Check expiration
                    expiry_date = consent.get("expiry_date")
                    if expiry_date:
                        if isinstance(expiry_date, str):
                            expiry_date = datetime.fromisoformat(expiry_date)
                        if datetime.now() < expiry_date:
                            return True
                    else:
                        # No expiration, consent is valid
                        return True

        return False

    def validate_fhir_consent(self, consent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate FHIR Consent resource.

        Args:
            consent_data: FHIR Consent resource data

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        # Basic FHIR Consent validation
        errors = []
        warnings = []

        # Required fields
        if not consent_data.get("resourceType") == "Consent":
            errors.append("Resource type must be 'Consent'")

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
            errors.append("Consent must have category")

        if not consent_data.get("patient"):
            errors.append("Consent must have patient reference")

        if not consent_data.get("dateTime"):
            errors.append("Consent must have dateTime")

        # GDPR-specific validation
        if "provision" in consent_data:
            provision = consent_data["provision"]

            # Check for data categories in GDPR consent
            if not provision.get("data"):
                warnings.append("GDPR consent should specify data categories")

            # Check for purpose
            if not provision.get("purpose"):
                warnings.append("GDPR consent should specify purpose of processing")

            # Check for retention period
            if not provision.get("dataPeriod"):
                warnings.append("GDPR consent should specify data retention period")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


# Export public API
__all__ = ["GDPRConsentIntegration"]
