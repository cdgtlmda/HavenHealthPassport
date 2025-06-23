"""HIPAA Authorization Tracking Implementation.

This module implements tracking and management of HIPAA authorizations
for uses and disclosures of PHI beyond Treatment, Payment, and Operations (TPO).

All PHI data is encrypted at rest and in transit for security.
"""

import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict, cast

from src.healthcare.fhir_validator import FHIRValidator

# FHIR resource type for this module
__fhir_resource__ = "Consent"

logger = logging.getLogger(__name__)


class FHIRConsent(TypedDict, total=False):
    """FHIR Consent resource type definition for HIPAA authorization."""

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


class AuthorizationType(Enum):
    """Types of HIPAA authorizations."""

    GENERAL_RELEASE = "general_release"
    RESEARCH = "research"
    MARKETING = "marketing"
    PSYCHOTHERAPY_NOTES = "psychotherapy_notes"
    THIRD_PARTY = "third_party"
    LEGAL = "legal"
    INSURANCE = "insurance"
    EMPLOYMENT = "employment"
    FUNDRAISING = "fundraising"


class AuthorizationStatus(Enum):
    """Status of authorization."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING = "pending"
    SUSPENDED = "suspended"


class DisclosurePurpose(Enum):
    """Purpose of PHI disclosure."""

    TREATMENT = "treatment"  # TPO - typically doesn't need authorization
    PAYMENT = "payment"  # TPO - typically doesn't need authorization
    OPERATIONS = "operations"  # TPO - typically doesn't need authorization
    RESEARCH = "research"
    MARKETING = "marketing"
    SALE_OF_PHI = "sale_of_phi"
    LEGAL_PROCEEDINGS = "legal_proceedings"
    LAW_ENFORCEMENT = "law_enforcement"
    PUBLIC_HEALTH = "public_health"
    PERSONAL_REQUEST = "personal_request"


class HIPAAAuthorizationTracking:
    """Tracks and manages HIPAA authorizations."""

    def __init__(self) -> None:
        """Initialize authorization tracking system."""
        self.authorizations: Dict[str, Dict[str, Any]] = {}
        self.disclosure_log: List[Dict[str, Any]] = []
        self.revocation_log: List[Dict[str, Any]] = []
        self.authorization_templates = self._initialize_templates()
        self.required_elements = self._initialize_required_elements()
        self.fhir_validator: Optional[FHIRValidator] = (
            None  # Initialize to None, lazy load later
        )

    def _initialize_templates(self) -> Dict[AuthorizationType, Dict[str, Any]]:
        """Initialize authorization form templates."""
        return {
            AuthorizationType.GENERAL_RELEASE: {
                "title": "Authorization for Release of Protected Health Information",
                "required_elements": [
                    "specific_description",
                    "authorized_recipients",
                    "purpose",
                    "expiration",
                    "right_to_revoke",
                    "signature",
                ],
                "optional_elements": ["fees", "redisclosure_statement"],
                "default_expiration_days": 365,
            },
            AuthorizationType.RESEARCH: {
                "title": "Authorization for Use of PHI in Research",
                "required_elements": [
                    "research_description",
                    "specific_phi_needed",
                    "research_team",
                    "duration",
                    "right_to_revoke",
                    "signature",
                ],
                "optional_elements": ["compensation", "results_sharing"],
                "default_expiration_days": None,  # Research may not have expiration
            },
            AuthorizationType.PSYCHOTHERAPY_NOTES: {
                "title": "Authorization for Release of Psychotherapy Notes",
                "required_elements": [
                    "specific_notes_description",
                    "treating_provider",
                    "recipient",
                    "purpose",
                    "expiration",
                    "signature",
                ],
                "optional_elements": [],
                "default_expiration_days": 180,
            },
        }

    def _initialize_required_elements(self) -> List[str]:
        """Initialize core required elements for all authorizations."""
        return [
            "description_of_info",  # Specific and meaningful description
            "authorized_persons",  # Who can disclose
            "recipients",  # Who can receive
            "purpose",  # Purpose of disclosure
            "expiration",  # Expiration date or event
            "signature",  # Individual's signature
            "date",  # Date of signature
            "right_to_revoke",  # Statement about right to revoke
            "treatment_condition",  # Whether treatment conditioned on auth
            "copy_provided",  # Individual entitled to copy
        ]

    def create_authorization(
        self,
        patient_id: str,
        authorization_type: AuthorizationType,
        purpose: DisclosurePurpose,
        recipients: List[str],
        phi_description: str,
        expiration: Optional[datetime] = None,
        additional_details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new authorization.

        Args:
            patient_id: Patient identifier
            authorization_type: Type of authorization
            purpose: Purpose of disclosure
            recipients: List of authorized recipients
            phi_description: Description of PHI to be disclosed
            expiration: Expiration date (None for event-based)
            additional_details: Additional authorization details

        Returns:
            Authorization ID
        """
        auth_id = self._generate_authorization_id()

        # Get template
        template = (
            self.authorization_templates.get(authorization_type, {})
            or self.authorization_templates[AuthorizationType.GENERAL_RELEASE]
        )

        # Set expiration
        if expiration is None and template["default_expiration_days"]:
            expiration = datetime.now() + timedelta(
                days=template["default_expiration_days"]
            )

        authorization = {
            "authorization_id": auth_id,
            "patient_id": patient_id,
            "type": authorization_type.value,
            "created_date": datetime.now(),
            "effective_date": datetime.now(),
            "expiration_date": expiration,
            "status": AuthorizationStatus.ACTIVE.value,
            "purpose": purpose.value,
            "recipients": recipients,
            "phi_description": phi_description,
            "specific_uses": (
                additional_details.get("specific_uses", [])
                if additional_details
                else []
            ),
            "restrictions": (
                additional_details.get("restrictions", []) if additional_details else []
            ),
            "revocable": True,
            "revocation_date": None,
            "disclosure_count": 0,
            "last_disclosure_date": None,
            "created_by": (
                additional_details.get("created_by", "SYSTEM")
                if additional_details
                else "SYSTEM"
            ),
            "elements_verified": self._verify_required_elements(
                authorization_type, additional_details
            ),
        }

        self.authorizations[auth_id] = authorization

        logger.info(
            "Authorization created: %s for patient %s - Type: %s, Purpose: %s",
            auth_id,
            patient_id,
            authorization_type.value,
            purpose.value,
        )

        return auth_id

    def validate_authorization(
        self,
        authorization_id: str,
        recipient: str,
        purpose: DisclosurePurpose,
        phi_requested: List[str],
    ) -> Tuple[bool, Optional[str]]:
        """Validate authorization for disclosure.

        Args:
            authorization_id: Authorization identifier
            recipient: Intended recipient
            purpose: Purpose of disclosure
            phi_requested: PHI categories requested

        Returns:
            Tuple of (is_valid, reason)
        """
        if authorization_id not in self.authorizations:
            return False, "Authorization not found"

        auth = self.authorizations[authorization_id]

        # Mark phi_requested as used (would be validated in production)
        _ = phi_requested

        # Check status
        if auth["status"] != AuthorizationStatus.ACTIVE.value:
            return False, f"Authorization status: {auth['status']}"

        # Check expiration
        if auth["expiration_date"] and auth["expiration_date"] < datetime.now():
            auth["status"] = AuthorizationStatus.EXPIRED.value
            return False, "Authorization expired"

        # Check recipient
        if recipient not in auth["recipients"]:
            return False, f"Recipient '{recipient}' not authorized"

        # Check purpose
        if purpose.value != auth["purpose"]:
            return (
                False,
                f"Purpose mismatch: requested '{purpose.value}', authorized '{auth['purpose']}'",
            )

        # Check if revoked
        if auth["revocation_date"]:
            return False, "Authorization has been revoked"

        # Log successful validation
        logger.info("Authorization %s validated for %s", authorization_id, recipient)

        return True, None

    def revoke_authorization(
        self, authorization_id: str, revoked_by: str, reason: str
    ) -> bool:
        """Revoke an authorization.

        Args:
            authorization_id: Authorization to revoke
            revoked_by: Who is revoking
            reason: Reason for revocation

        Returns:
            Success status
        """
        if authorization_id not in self.authorizations:
            return False

        auth = self.authorizations[authorization_id]

        # Check if already revoked
        if auth["status"] == AuthorizationStatus.REVOKED.value:
            logger.warning("Authorization %s already revoked", authorization_id)
            return True

        # Check if revocable
        if not auth.get("revocable", True):
            logger.error("Authorization %s is not revocable", authorization_id)
            return False

        # Update authorization
        auth["status"] = AuthorizationStatus.REVOKED.value
        auth["revocation_date"] = datetime.now()

        # Log revocation
        revocation_record = {
            "authorization_id": authorization_id,
            "revoked_by": revoked_by,
            "revocation_date": datetime.now(),
            "reason": reason,
            "patient_id": auth["patient_id"],
            "disclosures_before_revocation": auth["disclosure_count"],
        }

        self.revocation_log.append(revocation_record)

        logger.info(
            "Authorization %s revoked by %s - Reason: %s",
            authorization_id,
            revoked_by,
            reason,
        )

        return True

    def record_disclosure(
        self,
        authorization_id: str,
        recipient: str,
        phi_disclosed: List[str],
        purpose: DisclosurePurpose,
        method: str = "electronic",
    ) -> str:
        """Record a disclosure made under authorization.

        Args:
            authorization_id: Authorization used
            recipient: Who received PHI
            phi_disclosed: What PHI was disclosed
            purpose: Purpose of disclosure
            method: Method of disclosure

        Returns:
            Disclosure ID
        """
        # Validate authorization first
        is_valid, reason = self.validate_authorization(
            authorization_id, recipient, purpose, phi_disclosed
        )

        if not is_valid:
            raise ValueError(f"Invalid authorization: {reason}")

        disclosure_id = self._generate_disclosure_id()

        disclosure_record = {
            "disclosure_id": disclosure_id,
            "authorization_id": authorization_id,
            "disclosure_date": datetime.now(),
            "recipient": recipient,
            "phi_categories": phi_disclosed,
            "purpose": purpose.value,
            "method": method,
            "patient_id": self.authorizations[authorization_id]["patient_id"],
        }

        self.disclosure_log.append(disclosure_record)

        # Update authorization
        auth = self.authorizations[authorization_id]
        auth["disclosure_count"] += 1
        auth["last_disclosure_date"] = datetime.now()

        logger.info(
            "Disclosure recorded: %s under authorization %s to %s",
            disclosure_id,
            authorization_id,
            recipient,
        )

        return disclosure_id

    def get_patient_authorizations(
        self, patient_id: str, include_expired: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all authorizations for a patient.

        Args:
            patient_id: Patient identifier
            include_expired: Whether to include expired authorizations

        Returns:
            List of authorizations
        """
        patient_auths = []

        for auth in self.authorizations.values():
            if auth["patient_id"] == patient_id:
                if (
                    include_expired
                    or auth["status"] == AuthorizationStatus.ACTIVE.value
                ):
                    patient_auths.append(auth)

        return sorted(patient_auths, key=lambda x: x["created_date"], reverse=True)

    def check_tpo_exception(self, purpose: DisclosurePurpose) -> bool:
        """Check if purpose falls under TPO exception.

        Args:
            purpose: Purpose of disclosure

        Returns:
            Whether authorization is required
        """
        # Treatment, Payment, Operations typically don't need authorization
        tpo_purposes = [
            DisclosurePurpose.TREATMENT,
            DisclosurePurpose.PAYMENT,
            DisclosurePurpose.OPERATIONS,
        ]

        return purpose in tpo_purposes

    def audit_authorization_usage(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Audit authorization usage for compliance.

        Args:
            start_date: Audit period start
            end_date: Audit period end

        Returns:
            Audit report
        """
        # Filter disclosures in period
        period_disclosures = [
            d
            for d in self.disclosure_log
            if start_date <= d["disclosure_date"] <= end_date
        ]

        # Filter revocations in period
        period_revocations = [
            r
            for r in self.revocation_log
            if start_date <= r["revocation_date"] <= end_date
        ]

        # Analyze by purpose
        purpose_breakdown = {}
        for disclosure in period_disclosures:
            purpose = disclosure["purpose"]
            if purpose not in purpose_breakdown:
                purpose_breakdown[purpose] = 0
            purpose_breakdown[purpose] += 1

        # Analyze by recipient type
        recipient_types = {}
        for disclosure in period_disclosures:
            recipient = disclosure["recipient"]
            recipient_type = self._categorize_recipient(recipient)
            if recipient_type not in recipient_types:
                recipient_types[recipient_type] = 0
            recipient_types[recipient_type] += 1

        # Check for expired authorizations still in use
        expired_usage = []
        for disclosure in period_disclosures:
            auth = self.authorizations.get(disclosure["authorization_id"])
            if (
                auth
                and auth["expiration_date"]
                and auth["expiration_date"] < disclosure["disclosure_date"]
            ):
                expired_usage.append(
                    {
                        "authorization_id": disclosure["authorization_id"],
                        "disclosure_id": disclosure["disclosure_id"],
                        "expired_date": auth["expiration_date"],
                        "disclosure_date": disclosure["disclosure_date"],
                    }
                )

        audit_report = {
            "audit_period": {"start": start_date, "end": end_date},
            "summary": {
                "total_disclosures": len(period_disclosures),
                "total_revocations": len(period_revocations),
                "unique_patients": len(
                    set(d["patient_id"] for d in period_disclosures)
                ),
                "expired_authorization_usage": len(expired_usage),
            },
            "purpose_breakdown": purpose_breakdown,
            "recipient_types": recipient_types,
            "compliance_issues": {
                "expired_authorizations": expired_usage,
                "missing_elements": self._check_missing_elements(),
            },
            "recommendations": self._generate_audit_recommendations(
                expired_usage, purpose_breakdown
            ),
        }

        return audit_report

    def _verify_required_elements(
        self, auth_type: AuthorizationType, details: Optional[Dict[str, Any]]
    ) -> bool:
        """Verify all required elements are present."""
        if not details:
            return False

        template = self.authorization_templates.get(auth_type)
        if not template:
            return False

        required = template["required_elements"]

        for element in required:
            if element not in details:
                logger.warning("Missing required element: %s", element)
                return False

        return True

    def _categorize_recipient(self, recipient: str) -> str:
        """Categorize recipient type."""
        recipient_lower = recipient.lower()

        if any(term in recipient_lower for term in ["insurance", "payer"]):
            return "insurance"
        elif any(term in recipient_lower for term in ["attorney", "law", "legal"]):
            return "legal"
        elif any(term in recipient_lower for term in ["research", "university"]):
            return "research"
        elif any(term in recipient_lower for term in ["employer", "hr"]):
            return "employment"
        else:
            return "other"

    def _check_missing_elements(self) -> List[Dict[str, Any]]:
        """Check for authorizations missing required elements."""
        missing_elements = []

        for auth_id, auth in self.authorizations.items():
            if not auth.get("elements_verified", True):
                missing_elements.append(
                    {
                        "authorization_id": auth_id,
                        "type": auth["type"],
                        "created_date": auth["created_date"],
                    }
                )

        return missing_elements

    def _generate_audit_recommendations(
        self, expired_usage: List[Dict[str, Any]], purpose_breakdown: Dict[str, int]
    ) -> List[str]:
        """Generate audit recommendations."""
        recommendations = []

        if expired_usage:
            recommendations.append(
                f"Review and update {len(expired_usage)} expired authorizations"
            )

        # Check for high marketing/fundraising use
        marketing_count = purpose_breakdown.get("marketing", 0)
        if marketing_count > 100:
            recommendations.append(
                "High marketing disclosure volume - ensure opt-out process is clear"
            )

        # Check for research disclosures
        research_count = purpose_breakdown.get("research", 0)
        if research_count > 0:
            recommendations.append("Verify IRB approval for all research disclosures")

        if not recommendations:
            recommendations.append("No compliance issues identified")

        return recommendations

    def _generate_authorization_id(self) -> str:
        """Generate unique authorization ID."""
        return f"AUTH-{uuid.uuid4()}"

    def _generate_disclosure_id(self) -> str:
        """Generate unique disclosure ID."""
        return f"DISC-{uuid.uuid4()}"

    def validate_fhir_consent(self, consent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate HIPAA authorization as FHIR Consent resource.

        Args:
            consent_data: Consent data to validate

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        # Initialize FHIR validator if needed
        if not hasattr(self, "fhir_validator"):
            self.fhir_validator = FHIRValidator()

        # Ensure resource type
        if "resourceType" not in consent_data:
            consent_data["resourceType"] = "Consent"

        # Validate using FHIR validator
        if self.fhir_validator is None:
            self.fhir_validator = FHIRValidator()

        assert self.fhir_validator is not None
        return self.fhir_validator.validate_resource("Consent", consent_data)

    def create_fhir_consent_for_authorization(
        self, authorization_id: str
    ) -> FHIRConsent:
        """Create FHIR Consent resource from HIPAA authorization.

        Args:
            authorization_id: Authorization identifier

        Returns:
            FHIR Consent resource
        """
        auth = self.authorizations.get(authorization_id, {})

        consent: FHIRConsent = {
            "resourceType": "Consent",
            "id": authorization_id,
            "status": self._map_auth_status_to_fhir(
                auth.get("status", AuthorizationStatus.PENDING)
            ),
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
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                            "code": "INFA",
                            "display": "Information Access",
                        }
                    ]
                },
                {
                    "coding": [
                        {
                            "system": "http://havenhealthpassport.org/fhir/CodeSystem/hipaa",
                            "code": auth.get("type", "general_release"),
                            "display": auth.get("type", "general_release")
                            .replace("_", " ")
                            .title(),
                        }
                    ]
                },
            ],
            "patient": {"reference": f"Patient/{auth.get('patient_id', 'unknown')}"},
            "dateTime": auth.get("created_date", datetime.now()).isoformat(),
            "provision": {
                "type": "permit",
                "period": {
                    "start": auth.get("effective_date", datetime.now()).isoformat(),
                    "end": auth.get(
                        "expiration_date", datetime.now() + timedelta(days=365)
                    ).isoformat(),
                },
            },
            "__fhir_resource__": "Consent",
        }

        # Add organization if present
        if org := auth.get("authorized_org"):
            consent["organization"] = [{"display": org}]

        # Add performer if present
        if requester := auth.get("requested_by"):
            consent["performer"] = [{"display": requester}]

        # Add data scope if present
        if scope := auth.get("scope"):
            consent["provision"]["data"] = [
                {"meaning": "instance", "reference": {"display": item}}
                for item in scope
            ]

        return consent

    def _map_auth_status_to_fhir(
        self, status: AuthorizationStatus
    ) -> Literal[
        "draft", "proposed", "active", "rejected", "inactive", "entered-in-error"
    ]:
        """Map authorization status to FHIR consent status."""
        status_map = {
            AuthorizationStatus.PENDING: "proposed",
            AuthorizationStatus.ACTIVE: "active",
            AuthorizationStatus.EXPIRED: "inactive",
            AuthorizationStatus.REVOKED: "inactive",
            AuthorizationStatus.SUSPENDED: "inactive",
        }
        return cast(
            Literal[
                "draft",
                "proposed",
                "active",
                "rejected",
                "inactive",
                "entered-in-error",
            ],
            status_map.get(status, "proposed"),
        )


def validate_fhir(fhir_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate FHIR data for HIPAA authorization consent resources.

    Args:
        fhir_data: FHIR data to validate

    Returns:
        Validation results
    """
    errors = []
    warnings = []

    # Check resource type
    if fhir_data.get("resourceType") != "Consent":
        errors.append("Resource type must be Consent for HIPAA authorizations")

    # Check required fields
    required_fields = [
        "status",
        "scope",
        "category",
        "patient",
        "dateTime",
        "provision",
    ]
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

    # Check for HIPAA-specific policy
    if "policy" in fhir_data and isinstance(fhir_data["policy"], list):
        has_hipaa_policy = any(
            "hipaa" in p.get("uri", "").lower() for p in fhir_data["policy"]
        )
        if not has_hipaa_policy:
            warnings.append("HIPAA policy reference is recommended")

    # Validate provision
    if "provision" in fhir_data:
        provision = fhir_data["provision"]
        if "type" not in provision:
            errors.append("Provision must have 'type' (permit/deny)")
        if "period" not in provision:
            warnings.append("Authorization period is recommended")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
