"""GDPR Compliance Implementation.

This module implements GDPR (General Data Protection Regulation) compliance
controls for protecting personal health data of EU citizens and refugees
in European healthcare settings.
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Set, Tuple, TypedDict
from uuid import UUID as PyUUID

from src.healthcare.fhir_validator import FHIRValidator

# FHIR resource type for this module
__fhir_resource__ = "Consent"

logger = logging.getLogger(__name__)


class FHIRConsent(TypedDict, total=False):
    """FHIR Consent resource type definition for GDPR compliance."""

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


class GDPRLawfulBasis(Enum):
    """GDPR lawful basis for processing."""

    CONSENT = "consent"  # Article 6(1)(a)
    CONTRACT = "contract"  # Article 6(1)(b)
    LEGAL_OBLIGATION = "legal_obligation"  # Article 6(1)(c)
    VITAL_INTERESTS = "vital_interests"  # Article 6(1)(d)
    PUBLIC_TASK = "public_task"  # Article 6(1)(e)
    LEGITIMATE_INTERESTS = "legitimate_interests"  # Article 6(1)(f)

    # Special categories (Article 9)
    EXPLICIT_CONSENT = "explicit_consent"  # Article 9(2)(a)
    EMPLOYMENT = "employment"  # Article 9(2)(b)
    VITAL_INTERESTS_INCAPABLE = "vital_interests_incapable"  # Article 9(2)(c)
    HEALTHCARE = "healthcare"  # Article 9(2)(h)
    PUBLIC_HEALTH = "public_health"  # Article 9(2)(i)


class GDPRRight(Enum):
    """GDPR data subject rights."""

    ACCESS = "access"  # Article 15
    RECTIFICATION = "rectification"  # Article 16
    ERASURE = "erasure"  # Article 17 (Right to be forgotten)
    RESTRICTION = "restriction"  # Article 18
    PORTABILITY = "portability"  # Article 20
    OBJECT = "object"  # Article 21
    AUTOMATED_DECISION = "automated_decision"  # Article 22


class ProcessingPurpose(Enum):
    """Purpose of data processing."""

    HEALTHCARE_PROVISION = "healthcare_provision"
    MEDICAL_DIAGNOSIS = "medical_diagnosis"
    HEALTH_MANAGEMENT = "health_management"
    MEDICAL_RESEARCH = "medical_research"
    PUBLIC_HEALTH = "public_health"
    HUMANITARIAN_AID = "humanitarian_aid"
    EMERGENCY_CARE = "emergency_care"
    BILLING = "billing"
    QUALITY_IMPROVEMENT = "quality_improvement"


class GDPRConsentManager:
    """Manages GDPR consent for data processing."""

    def __init__(self) -> None:
        """Initialize consent manager."""
        self.consents: Dict[str, List[Dict[str, Any]]] = {}
        self.consent_templates: Dict[str, Dict[str, Any]] = self._initialize_templates()

    def _initialize_templates(self) -> Dict[str, Dict[str, Any]]:
        """Initialize consent templates."""
        return {
            "healthcare": {
                "purpose": ProcessingPurpose.HEALTHCARE_PROVISION,
                "lawful_basis": GDPRLawfulBasis.HEALTHCARE,
                "data_categories": [
                    "identification_data",
                    "health_data",
                    "medical_history",
                    "treatment_data",
                ],
                "retention_period": 365 * 10,  # 10 years
                "third_parties": ["healthcare_providers", "laboratories"],
                "international_transfer": False,
            },
            "research": {
                "purpose": ProcessingPurpose.MEDICAL_RESEARCH,
                "lawful_basis": GDPRLawfulBasis.EXPLICIT_CONSENT,
                "data_categories": [
                    "health_data",
                    "genetic_data",
                    "treatment_outcomes",
                ],
                "retention_period": 365 * 20,  # 20 years
                "third_parties": ["research_institutions"],
                "international_transfer": True,
                "requires_explicit_consent": True,
            },
            "humanitarian": {
                "purpose": ProcessingPurpose.HUMANITARIAN_AID,
                "lawful_basis": GDPRLawfulBasis.VITAL_INTERESTS,
                "data_categories": [
                    "identification_data",
                    "health_data",
                    "location_data",
                ],
                "retention_period": 365 * 5,  # 5 years
                "third_parties": ["humanitarian_organizations", "unhcr"],
                "international_transfer": True,
            },
        }

    def record_consent(
        self,
        data_subject_id: str,
        purpose: ProcessingPurpose,
        consent_given: bool,
        parent_guardian_id: Optional[str] = None,
        language: str = "en",
        method: str = "electronic",
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record consent from data subject.

        Args:
            data_subject_id: ID of person giving consent
            purpose: Purpose of processing
            consent_given: Whether consent was given
            parent_guardian_id: ID of parent/guardian if subject is minor
            language: Language consent was given in
            method: Method of consent (electronic, written, verbal)
            details: Additional details

        Returns:
            Consent record ID
        """
        consent_id = self._generate_consent_id()

        consent_record = {
            "consent_id": consent_id,
            "data_subject_id": data_subject_id,
            "timestamp": datetime.now(),
            "purpose": purpose.value,
            "consent_given": consent_given,
            "parent_guardian_id": parent_guardian_id,
            "language": language,
            "method": method,
            "ip_address": details.get("ip_address") if details else None,
            "user_agent": details.get("user_agent") if details else None,
            "consent_text_version": (
                details.get("consent_text_version", "1.0") if details else "1.0"
            ),
            "withdrawn": False,
            "withdrawal_date": None,
        }

        if data_subject_id not in self.consents:
            self.consents[data_subject_id] = []

        self.consents[data_subject_id].append(consent_record)

        # Log consent
        logger.info(
            "Consent recorded: %s for %s - Purpose: %s, Given: %s",
            consent_id,
            data_subject_id,
            purpose.value,
            consent_given,
        )

        return consent_id

    def withdraw_consent(
        self, data_subject_id: str, consent_id: str, reason: Optional[str] = None
    ) -> bool:
        """Withdraw previously given consent.

        Args:
            data_subject_id: ID of data subject
            consent_id: ID of consent to withdraw
            reason: Reason for withdrawal

        Returns:
            Success status
        """
        if data_subject_id not in self.consents:
            return False

        for consent in self.consents[data_subject_id]:
            if consent["consent_id"] == consent_id:
                consent["withdrawn"] = True
                consent["withdrawal_date"] = datetime.now()
                consent["withdrawal_reason"] = reason

                logger.info("Consent withdrawn: %s for %s", consent_id, data_subject_id)
                return True

        return False

    def check_consent(
        self, data_subject_id: str, purpose: ProcessingPurpose
    ) -> Tuple[bool, Optional[str]]:
        """Check if valid consent exists for purpose.

        Args:
            data_subject_id: ID of data subject
            purpose: Purpose to check

        Returns:
            Tuple of (has_consent, consent_id)
        """
        if data_subject_id not in self.consents:
            return False, None

        # Find most recent consent for purpose
        relevant_consents = [
            c
            for c in self.consents[data_subject_id]
            if c["purpose"] == purpose.value and not c["withdrawn"]
        ]

        if not relevant_consents:
            return False, None

        # Sort by timestamp, most recent first
        relevant_consents.sort(key=lambda x: x["timestamp"], reverse=True)
        latest = relevant_consents[0]

        return latest["consent_given"], latest["consent_id"]

    def get_consent_history(self, data_subject_id: str) -> List[Dict[str, Any]]:
        """Get consent history for data subject.

        Args:
            data_subject_id: ID of data subject

        Returns:
            List of consent records
        """
        return self.consents.get(data_subject_id, [])

    def _generate_consent_id(self) -> str:
        """Generate unique consent ID."""
        return f"CONSENT-{uuid.uuid4()}"


class GDPRDataPortability:
    """Handles GDPR data portability requirements."""

    def __init__(self) -> None:
        """Initialize data portability handler."""
        self.export_formats = ["json", "xml", "csv"]

    async def export_personal_data(
        self,
        data_subject_id: str,
        include_categories: Optional[List[str]] = None,
        export_format: str = "json",
    ) -> Dict[str, Any]:
        """Export personal data in portable format.

        Args:
            data_subject_id: ID of data subject
            include_categories: Categories to include (None = all)
            format: Export format

        Returns:
            Exported data package
        """
        from src.database import get_db  # pylint: disable=import-outside-toplevel
        from src.models.access_log import (  # pylint: disable=import-outside-toplevel
            AccessLog,
        )
        from src.models.audit_log import (  # pylint: disable=import-outside-toplevel
            AuditLog,
        )
        from src.models.auth import UserAuth  # pylint: disable=import-outside-toplevel
        from src.models.document import (  # pylint: disable=import-outside-toplevel
            Document,
        )
        from src.models.health_record import (  # pylint: disable=import-outside-toplevel
            HealthRecord,
        )
        from src.models.patient import (  # pylint: disable=import-outside-toplevel
            Patient,
        )
        from src.models.translation import (  # pylint: disable=import-outside-toplevel
            Translation,
        )
        from src.models.user import User  # pylint: disable=import-outside-toplevel

        export_package: Dict[str, Any] = {
            "export_id": self._generate_export_id(),
            "data_subject_id": data_subject_id,
            "export_date": datetime.now(),
            "format": export_format,
            "data_categories": {},
            "metadata": {
                "gdpr_compliant": True,
                "machine_readable": True,
                "commonly_used_format": export_format in self.export_formats,
            },
        }

        # Get database session
        db = next(get_db())

        try:
            # Personal identification data
            patient = (
                db.query(Patient).filter(Patient.id == PyUUID(data_subject_id)).first()
            )
            user_auth = (
                db.query(UserAuth)
                .filter(UserAuth.user_id == PyUUID(data_subject_id))
                .first()
            )
            user = (
                db.query(User).filter(User.id == PyUUID(data_subject_id)).first()  # type: ignore[arg-type]
                if not patient
                else None
            )

            if patient or user_auth:
                export_package["data_categories"]["personal_data"] = {
                    "patient_id": str(patient.id) if patient else None,
                    "user_id": str(user_auth.id) if user_auth else None,
                    "name": {
                        "first_name": (
                            patient.given_name
                            if patient
                            else user.name if user else None
                        ),
                        "last_name": (patient.family_name if patient else None),
                        "middle_name": patient.middle_name if patient else None,
                    },
                    "date_of_birth": (
                        patient.date_of_birth.isoformat()
                        if patient and patient.date_of_birth
                        else None
                    ),
                    "gender": (
                        patient.gender.value if patient and patient.gender else None
                    ),
                    "contact_info": {
                        "email": (
                            patient.email if patient else user.email if user else None
                        ),
                        "phone": (
                            patient.phone_number
                            if patient
                            else user_auth.phone_number if user_auth else None
                        ),
                        "emergency_contact": (
                            patient.emergency_contact if patient else None
                        ),
                    },
                    "address": patient.address if patient else None,
                    "languages": patient.preferred_language if patient else [],
                    "nationality": patient.nationality if patient else None,
                    "refugee_status": patient.refugee_status if patient else None,
                    "un_number": patient.un_number if patient else None,
                    "verification_status": (
                        patient.verification_status.value
                        if patient and patient.verification_status
                        else None
                    ),
                    "created_at": (
                        patient.created_at.isoformat()
                        if patient
                        else user_auth.created_at.isoformat() if user_auth else None
                    ),
                }

            # Health data (if included)
            if not include_categories or "health_data" in include_categories:
                health_records = (
                    db.query(HealthRecord)
                    .filter(HealthRecord.patient_id == PyUUID(data_subject_id))  # type: ignore[arg-type]
                    .all()
                )

                export_package["data_categories"]["health_data"] = {
                    "medical_records": [
                        {
                            "id": str(record.id),
                            "record_type": record.record_type.value,
                            "title": record.title,
                            "date": (
                                record.record_date.isoformat()
                                if record.record_date
                                else None
                            ),
                            "provider": record.provider_name,
                            "facility": record.facility_name,
                            "status": record.status.value if record.status else None,
                            "priority": (
                                record.priority.value if record.priority else None
                            ),
                            "content": record.content,  # This should be decrypted if encrypted
                            "attachments": (
                                record.attachments if record.attachments else []
                            ),
                        }
                        for record in health_records
                    ],
                    "conditions": [
                        {
                            "code": cond.get("code"),
                            "display": cond.get("display"),
                            "onset_date": cond.get("onset_date"),
                            "status": cond.get("status"),
                        }
                        for cond in (
                            patient.medical_conditions
                            if patient and patient.medical_conditions
                            else []
                        )
                    ],
                    "medications": patient.current_medications if patient else [],
                    "allergies": patient.allergies if patient else [],
                    "immunizations": patient.immunizations if patient else [],
                }

            # Documents (if included)
            if not include_categories or "documents" in include_categories:
                documents = (
                    db.query(Document)
                    .filter(Document.owner_id == data_subject_id)
                    .all()
                )

                export_package["data_categories"]["documents"] = [
                    {
                        "id": str(doc.id),
                        "filename": doc.filename,
                        "document_type": doc.document_type,
                        "uploaded_at": doc.created_at.isoformat(),
                        "metadata": doc.metadata,
                    }
                    for doc in documents
                ]

            # Processing history
            if not include_categories or "processing_history" in include_categories:
                # Consent records from this class
                # Get consent history
                consent_history: List[Any] = (
                    []
                )  # TODO: Implement consent history retrieval

                # Access logs
                access_logs = (
                    db.query(AccessLog)
                    .filter(AccessLog.patient_id == data_subject_id)
                    .order_by(AccessLog.created_at.desc())
                    .limit(1000)
                    .all()
                )

                # Audit logs
                audit_logs = (
                    db.query(AuditLog)
                    .filter(AuditLog.entity_id == data_subject_id)
                    .order_by(AuditLog.created_at.desc())
                    .limit(1000)
                    .all()
                )

                # Translation logs
                translation_logs = (
                    db.query(Translation)
                    .filter(Translation.user_id == data_subject_id)
                    .order_by(Translation.created_at.desc())
                    .limit(100)
                    .all()
                )

                export_package["data_categories"]["processing_history"] = {
                    "consent_records": [
                        {
                            "consent_id": consent["consent_id"],
                            "purpose": consent["purpose"],
                            "consent_given": consent["consent_given"],
                            "timestamp": consent["timestamp"].isoformat(),
                            "withdrawn": consent["withdrawn"],
                            "withdrawal_date": (
                                consent["withdrawal_date"].isoformat()
                                if consent["withdrawal_date"]
                                else None
                            ),
                        }
                        for consent in consent_history
                    ],
                    "access_logs": [
                        {
                            "id": str(log.id),
                            "accessed_at": log.created_at.isoformat(),
                            "accessor_id": str(log.accessor_id),
                            "action": log.action,
                            "resource_type": log.resource_type,
                            "ip_address": log.ip_address,
                        }
                        for log in access_logs
                    ],
                    "audit_logs": [
                        {
                            "id": str(log.id),
                            "timestamp": log.created_at.isoformat(),
                            "action": log.action,
                            "entity_type": log.entity_type,
                            "changes": log.changes,
                            "user_id": str(log.user_id) if log.user_id else None,
                        }
                        for log in audit_logs
                    ],
                    "translations": [
                        {
                            "id": str(log.id),
                            "timestamp": log.created_at.isoformat(),
                            "source_language": log.source_language,
                            "target_language": log.target_language,
                            "translation_mode": log.translation_mode,
                            "medical_terms_count": log.medical_terms_count,
                        }
                        for log in translation_logs
                    ],
                }

            # Account security data (if included)
            if not include_categories or "security_data" in include_categories:
                if user_auth:
                    # TODO: Implement MFA method retrieval when model is available
                    mfa_methods: List[Any] = []

                    export_package["data_categories"]["security_data"] = {
                        "account_status": user_auth.is_active,
                        "email_verified": user_auth.email_verified,
                        "phone_verified": user_auth.phone_verified,
                        "mfa_enabled": user_auth.mfa_enabled,
                        "mfa_methods": [
                            {
                                "method": method.method,
                                "is_primary": method.is_primary,
                                "created_at": method.created_at.isoformat(),
                            }
                            for method in mfa_methods
                        ],
                        "last_login": (
                            user_auth.last_login.isoformat()
                            if user_auth.last_login
                            else None
                        ),
                        "password_changed_at": (
                            user_auth.password_changed_at.isoformat()
                            if user_auth.password_changed_at
                            else None
                        ),
                    }

        except (ValueError, KeyError, TypeError) as e:
            logger.error("Error exporting personal data for %s: %s", data_subject_id, e)
            # Add error to export but continue
            export_package["metadata"]["export_errors"] = str(e)
        finally:
            db.close()

        return export_package

    def transfer_to_controller(
        self, data_subject_id: str, target_controller: str, data_package: Dict[str, Any]
    ) -> str:
        """Transfer data to another controller.

        Args:
            data_subject_id: ID of data subject
            target_controller: Target controller ID
            data_package: Data to transfer

        Returns:
            Transfer ID
        """
        _ = data_package  # Mark as intentionally unused
        transfer_id = self._generate_transfer_id()

        # In production, would implement secure transfer mechanism
        logger.info(
            "Data transfer initiated: %s from %s to %s",
            transfer_id,
            data_subject_id,
            target_controller,
        )

        # Store data package for transfer (in production would be encrypted)
        # data_package would be processed here

        return transfer_id

    def _generate_export_id(self) -> str:
        """Generate unique export ID."""
        return f"EXPORT-{uuid.uuid4()}"

    def _generate_transfer_id(self) -> str:
        """Generate unique transfer ID."""
        return f"TRANSFER-{uuid.uuid4()}"


class GDPRErasure:
    """Handles GDPR right to erasure (right to be forgotten)."""

    def __init__(self) -> None:
        """Initialize erasure handler."""
        self.erasure_requests: Dict[str, Dict[str, Any]] = {}
        self.retention_rules: Dict[str, int] = {
            "healthcare_records": 365 * 10,  # 10 years
            "billing_records": 365 * 7,  # 7 years
            "consent_records": 365 * 3,  # 3 years after withdrawal
            "access_logs": 365 * 6,  # 6 years
        }

    def request_erasure(
        self,
        data_subject_id: str,
        categories: List[str],
        reason: str,
        requestor_id: Optional[str] = None,
    ) -> str:
        """Request erasure of personal data.

        Args:
            data_subject_id: ID of data subject
            categories: Categories to erase
            reason: Reason for erasure
            requestor_id: ID of person making request

        Returns:
            Request ID
        """
        request_id = self._generate_request_id()

        erasure_request = {
            "request_id": request_id,
            "data_subject_id": data_subject_id,
            "requestor_id": requestor_id or data_subject_id,
            "timestamp": datetime.now(),
            "categories": categories,
            "reason": reason,
            "status": "pending",
            "legal_review_required": self._requires_legal_review(categories),
            "completion_date": None,
            "denial_reason": None,
        }

        self.erasure_requests[request_id] = erasure_request

        # Process request
        self._process_erasure_request(request_id)

        return request_id

    def _process_erasure_request(self, request_id: str) -> None:
        """Process erasure request.

        Args:
            request_id: Request ID
        """
        request = self.erasure_requests[request_id]

        # Check legal obligations
        can_erase, denial_reason = self._check_legal_obligations(request)

        if not can_erase:
            request["status"] = "denied"
            request["denial_reason"] = denial_reason
            logger.info("Erasure request %s denied: %s", request_id, denial_reason)
            return

        # Perform erasure
        erased_items = []
        for category in request["categories"]:
            if self._can_erase_category(category, request["data_subject_id"]):
                # In production, would actually delete/anonymize data
                erased_items.append(category)
                logger.info("Erasing %s for %s", category, request["data_subject_id"])

        request["status"] = "completed"
        request["completion_date"] = datetime.now()
        request["erased_items"] = erased_items

    def _requires_legal_review(self, categories: List[str]) -> bool:
        """Check if erasure requires legal review.

        Args:
            categories: Categories to erase

        Returns:
            Whether legal review is required
        """
        protected_categories = [
            "healthcare_records",
            "billing_records",
            "legal_documents",
        ]

        return any(cat in protected_categories for cat in categories)

    def _check_legal_obligations(
        self, request: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Check if erasure conflicts with legal obligations.

        Args:
            request: Erasure request

        Returns:
            Tuple of (can_erase, denial_reason)
        """
        # Check retention requirements
        for category in request["categories"]:
            if category in self.retention_rules:
                # Check if minimum retention period has passed
                # In production, would check actual data age
                return False, f"Legal retention period for {category} not met"

        # Check ongoing legal proceedings
        # In production, would check legal hold database

        return True, None

    def _can_erase_category(self, category: str, data_subject_id: str) -> bool:
        """Check if specific category can be erased.

        Args:
            category: Data category
            data_subject_id: Data subject ID

        Returns:
            Whether category can be erased
        """
        # In production, would check specific business rules
        # using both category and data_subject_id to determine eligibility
        _ = (category, data_subject_id)  # Mark as used
        return True

    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        return f"ERASURE-{uuid.uuid4()}"


class GDPRDataProtectionOfficer:
    """Data Protection Officer (DPO) functions."""

    def __init__(self) -> None:
        """Initialize DPO functions."""
        self.privacy_impact_assessments: Dict[str, Dict[str, Any]] = {}
        self.breach_register: List[Dict[str, Any]] = []

    def conduct_dpia(
        self,
        project_name: str,
        processing_description: str,
        data_categories: List[str],
        purposes: List[ProcessingPurpose],
        risks: List[Dict[str, Any]],
    ) -> str:
        """Conduct Data Protection Impact Assessment.

        Args:
            project_name: Name of project/processing
            processing_description: Description of processing
            data_categories: Categories of data
            purposes: Processing purposes
            risks: Identified risks

        Returns:
            DPIA ID
        """
        dpia_id = self._generate_dpia_id()

        dpia = {
            "dpia_id": dpia_id,
            "project_name": project_name,
            "assessment_date": datetime.now(),
            "processing_description": processing_description,
            "data_categories": data_categories,
            "purposes": [p.value for p in purposes],
            "necessity_assessment": self._assess_necessity(purposes),
            "proportionality_assessment": self._assess_proportionality(
                data_categories, purposes
            ),
            "risks": risks,
            "risk_score": self._calculate_risk_score(risks),
            "mitigation_measures": self._suggest_mitigation(risks),
            "approval_status": "pending",
            "approver": None,
            "approval_date": None,
        }

        self.privacy_impact_assessments[dpia_id] = dpia

        return dpia_id

    def report_breach(
        self,
        breach_type: str,
        affected_records: int,
        data_categories: List[str],
        discovery_date: datetime,
        description: str,
        likely_consequences: str,
        measures_taken: str,
    ) -> str:
        """Report a data breach.

        Args:
            breach_type: Type of breach
            affected_records: Number of affected records
            data_categories: Categories of data breached
            discovery_date: When breach was discovered
            description: Description of breach
            likely_consequences: Likely consequences
            measures_taken: Measures taken

        Returns:
            Breach ID
        """
        breach_id = self._generate_breach_id()

        breach_record = {
            "breach_id": breach_id,
            "report_date": datetime.now(),
            "discovery_date": discovery_date,
            "breach_type": breach_type,
            "affected_records": affected_records,
            "data_categories": data_categories,
            "description": description,
            "likely_consequences": likely_consequences,
            "measures_taken": measures_taken,
            "risk_to_rights": self._assess_risk_to_rights(
                data_categories, affected_records
            ),
            "supervisory_authority_notified": False,
            "data_subjects_notified": False,
            "notification_dates": {},
        }

        self.breach_register.append(breach_record)

        # Check if notification required
        if self._requires_authority_notification(breach_record):
            self._notify_supervisory_authority(breach_id)

        if self._requires_subject_notification(breach_record):
            self._notify_data_subjects(breach_id)

        return breach_id

    def _assess_necessity(self, purposes: List[ProcessingPurpose]) -> str:
        """Assess necessity of processing.

        Args:
            purposes: Processing purposes

        Returns:
            Necessity assessment
        """
        essential_purposes = [
            ProcessingPurpose.HEALTHCARE_PROVISION,
            ProcessingPurpose.EMERGENCY_CARE,
            ProcessingPurpose.PUBLIC_HEALTH,
        ]

        if any(p in essential_purposes for p in purposes):
            return "Processing necessary for essential healthcare services"

        return "Processing requires further justification"

    def _assess_proportionality(
        self, data_categories: List[str], purposes: List[ProcessingPurpose]
    ) -> str:
        """Assess proportionality of processing.

        Args:
            data_categories: Data categories
            purposes: Processing purposes

        Returns:
            Proportionality assessment
        """
        sensitive_categories = ["genetic_data", "biometric_data", "health_data"]
        sensitive_count = sum(
            1 for cat in data_categories if cat in sensitive_categories
        )

        if sensitive_count > len(purposes):
            return "Processing may not be proportionate - too many sensitive categories"

        return "Processing appears proportionate to purposes"

    def _calculate_risk_score(self, risks: List[Dict[str, Any]]) -> int:
        """Calculate overall risk score.

        Args:
            risks: List of risks

        Returns:
            Risk score (1-10)
        """
        if not risks:
            return 1

        total_score = 0
        for risk in risks:
            likelihood = risk.get("likelihood", 1)
            impact = risk.get("impact", 1)
            total_score += likelihood * impact

        return min(10, total_score // len(risks))

    def _suggest_mitigation(self, risks: List[Dict[str, Any]]) -> List[str]:
        """Suggest mitigation measures for risks.

        Args:
            risks: List of risks

        Returns:
            List of mitigation measures
        """
        measures = []

        for risk in risks:
            risk_type = risk.get("type", "")

            if "access" in risk_type.lower():
                measures.append("Implement strong access controls and authentication")
            if "breach" in risk_type.lower():
                measures.append("Enhance encryption and security monitoring")
            if "retention" in risk_type.lower():
                measures.append("Implement automated retention policies")

        return list(set(measures))  # Remove duplicates

    def _assess_risk_to_rights(
        self, data_categories: List[str], affected_records: int
    ) -> str:
        """Assess risk to data subject rights.

        Args:
            data_categories: Breached data categories
            affected_records: Number of affected records

        Returns:
            Risk assessment
        """
        high_risk_categories = [
            "health_data",
            "genetic_data",
            "biometric_data",
            "financial_data",
        ]

        if any(cat in high_risk_categories for cat in data_categories):
            return "high"
        elif affected_records > 1000:
            return "high"
        elif affected_records > 100:
            return "medium"
        else:
            return "low"

    def _requires_authority_notification(self, breach: Dict[str, Any]) -> bool:
        """Check if supervisory authority notification required.

        Args:
            breach: Breach record

        Returns:
            Whether notification required
        """
        # Must notify unless unlikely to result in risk
        return bool(breach["risk_to_rights"] != "low")

    def _requires_subject_notification(self, breach: Dict[str, Any]) -> bool:
        """Check if data subject notification required.

        Args:
            breach: Breach record

        Returns:
            Whether notification required
        """
        # Must notify if high risk to rights
        return bool(breach["risk_to_rights"] == "high")

    def _notify_supervisory_authority(self, breach_id: str) -> None:
        """Notify supervisory authority of breach.

        Args:
            breach_id: Breach ID
        """
        # In production, would send actual notification
        logger.warning("Notifying supervisory authority of breach %s", breach_id)

        for breach in self.breach_register:
            if breach["breach_id"] == breach_id:
                breach["supervisory_authority_notified"] = True
                breach["notification_dates"]["authority"] = datetime.now()
                break

    def _notify_data_subjects(self, breach_id: str) -> None:
        """Notify data subjects of breach.

        Args:
            breach_id: Breach ID
        """
        # In production, would send actual notifications
        logger.warning("Notifying data subjects of breach %s", breach_id)

        for breach in self.breach_register:
            if breach["breach_id"] == breach_id:
                breach["data_subjects_notified"] = True
                breach["notification_dates"]["subjects"] = datetime.now()
                break

    def _generate_dpia_id(self) -> str:
        """Generate unique DPIA ID."""
        return f"DPIA-{uuid.uuid4()}"

    def _generate_breach_id(self) -> str:
        """Generate unique breach ID."""
        return f"BREACH-{uuid.uuid4()}"


class HIPAAMinimumNecessary:
    """Implements HIPAA Minimum Necessary standard for PHI access control."""

    def __init__(self) -> None:
        """Initialize minimum necessary handler."""
        self.role_definitions: Dict[str, Dict[str, Any]] = self._initialize_roles()
        self.purpose_definitions: Dict[str, Dict[str, Any]] = (
            self._initialize_purposes()
        )
        self.access_policies: Dict[str, Dict[str, Any]] = {}
        self.access_audit_log: List[Dict[str, Any]] = []

    def _initialize_roles(self) -> Dict[str, Dict[str, Any]]:
        """Initialize role-based access definitions."""
        return {
            "primary_care_physician": {
                "role_id": "PCP",
                "description": "Primary care physician providing direct care",
                "default_access_level": "comprehensive",
                "data_categories": [
                    "demographics",
                    "medical_history",
                    "current_conditions",
                    "medications",
                    "allergies",
                    "lab_results",
                    "imaging",
                    "care_plans",
                    "clinical_notes",
                ],
                "time_restriction": None,
                "requires_relationship": True,
            },
            "specialist_physician": {
                "role_id": "SPEC",
                "description": "Specialist physician providing consultation",
                "default_access_level": "focused",
                "data_categories": [
                    "demographics",
                    "relevant_medical_history",
                    "current_conditions",
                    "medications",
                    "allergies",
                    "relevant_lab_results",
                    "relevant_imaging",
                    "referral_info",
                ],
                "time_restriction": 180,  # days
                "requires_relationship": True,
            },
            "emergency_physician": {
                "role_id": "EMRG",
                "description": "Emergency department physician",
                "default_access_level": "emergency",
                "data_categories": [
                    "demographics",
                    "allergies",
                    "current_medications",
                    "critical_conditions",
                    "emergency_contacts",
                    "advance_directives",
                    "recent_vitals",
                ],
                "time_restriction": 72,  # hours
                "requires_relationship": False,  # Emergency override
            },
            "nurse": {
                "role_id": "RN",
                "description": "Registered nurse providing care",
                "default_access_level": "care_delivery",
                "data_categories": [
                    "demographics",
                    "current_conditions",
                    "medications",
                    "allergies",
                    "care_plans",
                    "vitals",
                    "nursing_notes",
                ],
                "time_restriction": None,
                "requires_relationship": True,
            },
            "pharmacist": {
                "role_id": "PHARM",
                "description": "Pharmacist reviewing medications",
                "default_access_level": "medication_focused",
                "data_categories": [
                    "demographics",
                    "medications",
                    "allergies",
                    "relevant_conditions",
                    "insurance_info",
                ],
                "time_restriction": 30,  # days
                "requires_relationship": True,
            },
            "lab_technician": {
                "role_id": "LAB",
                "description": "Laboratory technician",
                "default_access_level": "test_ordering",
                "data_categories": [
                    "demographics",
                    "test_orders",
                    "relevant_conditions",
                    "relevant_medications",
                ],
                "time_restriction": 7,  # days
                "requires_relationship": True,
            },
            "billing_specialist": {
                "role_id": "BILL",
                "description": "Billing and coding specialist",
                "default_access_level": "billing_only",
                "data_categories": [
                    "demographics",
                    "insurance_info",
                    "procedure_codes",
                    "diagnosis_codes",
                    "billing_history",
                ],
                "time_restriction": 365,  # days
                "requires_relationship": False,
            },
            "case_manager": {
                "role_id": "CM",
                "description": "Case manager coordinating care",
                "default_access_level": "care_coordination",
                "data_categories": [
                    "demographics",
                    "current_conditions",
                    "care_plans",
                    "provider_list",
                    "appointments",
                    "insurance_info",
                ],
                "time_restriction": None,
                "requires_relationship": True,
            },
            "researcher": {
                "role_id": "RSRCH",
                "description": "Medical researcher with IRB approval",
                "default_access_level": "de_identified",
                "data_categories": [
                    "de_identified_demographics",
                    "conditions",
                    "treatments",
                    "outcomes",
                ],
                "time_restriction": None,
                "requires_relationship": False,
                "requires_special_approval": True,
            },
            "health_information_manager": {
                "role_id": "HIM",
                "description": "Health information management professional",
                "default_access_level": "administrative",
                "data_categories": [
                    "demographics",
                    "record_metadata",
                    "access_logs",
                    "consent_records",
                ],
                "time_restriction": None,
                "requires_relationship": False,
            },
        }

    def _initialize_purposes(self) -> Dict[str, Dict[str, Any]]:
        """Initialize purpose-based access definitions."""
        return {
            "treatment": {
                "purpose_id": "TREAT",
                "description": "Direct patient treatment",
                "allowed_roles": [
                    "primary_care_physician",
                    "specialist_physician",
                    "emergency_physician",
                    "nurse",
                ],
                "required_data": "full_medical_record",
                "documentation_required": False,
            },
            "payment": {
                "purpose_id": "PAY",
                "description": "Healthcare payment activities",
                "allowed_roles": ["billing_specialist"],
                "required_data": "billing_subset",
                "documentation_required": False,
            },
            "operations": {
                "purpose_id": "OPS",
                "description": "Healthcare operations",
                "allowed_roles": ["health_information_manager", "case_manager"],
                "required_data": "operational_subset",
                "documentation_required": True,
            },
            "emergency": {
                "purpose_id": "EMRG",
                "description": "Emergency treatment",
                "allowed_roles": ["emergency_physician", "nurse"],
                "required_data": "emergency_subset",
                "documentation_required": False,
                "override_restrictions": True,
            },
            "public_health": {
                "purpose_id": "PH",
                "description": "Public health activities",
                "allowed_roles": ["public_health_official"],
                "required_data": "public_health_subset",
                "documentation_required": True,
                "requires_authorization": True,
            },
            "research": {
                "purpose_id": "RSRCH",
                "description": "Medical research with IRB approval",
                "allowed_roles": ["researcher"],
                "required_data": "de_identified_subset",
                "documentation_required": True,
                "requires_authorization": True,
            },
            "legal": {
                "purpose_id": "LEGAL",
                "description": "Legal proceedings or requirements",
                "allowed_roles": ["legal_representative"],
                "required_data": "court_ordered_subset",
                "documentation_required": True,
                "requires_authorization": True,
            },
            "quality_improvement": {
                "purpose_id": "QI",
                "description": "Healthcare quality improvement",
                "allowed_roles": ["quality_analyst"],
                "required_data": "quality_metrics_subset",
                "documentation_required": True,
            },
        }

    def determine_minimum_necessary(
        self,
        requester_role: str,
        purpose: str,
        patient_id: str,
        requested_data: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[str], Dict[str, Any]]:
        """Determine minimum necessary data for request.

        Args:
            requester_role: Role of person requesting data
            purpose: Purpose of data request
            patient_id: Patient ID
            requested_data: Data categories requested
            context: Additional context (e.g., emergency, specific condition)

        Returns:
            Tuple of (allowed_data_categories, access_details)
        """
        # Validate role and purpose
        if requester_role not in self.role_definitions:
            return [], {"denied": True, "reason": "Invalid role"}

        if purpose not in self.purpose_definitions:
            return [], {"denied": True, "reason": "Invalid purpose"}

        role_def = self.role_definitions[requester_role]
        purpose_def = self.purpose_definitions[purpose]

        # Check if role is allowed for purpose
        if requester_role not in purpose_def["allowed_roles"]:
            return [], {
                "denied": True,
                "reason": f"Role {requester_role} not authorized for purpose {purpose}",
            }

        # Check special approvals
        if role_def.get("requires_special_approval"):
            if not self._check_special_approval(requester_role, patient_id, context):
                return [], {"denied": True, "reason": "Special approval required"}

        # Determine allowed data based on minimum necessary
        allowed_data = self._calculate_minimum_data(
            role_def, purpose_def, requested_data, context
        )

        # Apply time restrictions
        if role_def.get("time_restriction"):
            allowed_data = self._apply_time_restriction(
                allowed_data, role_def["time_restriction"], context
            )

        # Create access details
        access_details = {
            "granted": True,
            "role": requester_role,
            "purpose": purpose,
            "patient_id": patient_id,
            "allowed_categories": allowed_data,
            "denied_categories": list(set(requested_data) - set(allowed_data)),
            "timestamp": datetime.now(),
            "restrictions": self._get_applicable_restrictions(role_def, purpose_def),
            "audit_required": purpose_def.get("documentation_required", False),
        }

        # Log access
        self._log_access_decision(access_details)

        return allowed_data, access_details

    def _calculate_minimum_data(
        self,
        role_def: Dict[str, Any],
        purpose_def: Dict[str, Any],
        requested_data: List[str],
        context: Optional[Dict[str, Any]],
    ) -> List[str]:
        """Calculate minimum necessary data categories.

        Args:
            role_def: Role definition
            purpose_def: Purpose definition
            requested_data: Requested data categories
            context: Request context

        Returns:
            List of allowed data categories
        """
        # Start with role's allowed categories
        role_allowed = set(role_def["data_categories"])

        # Apply purpose-specific restrictions
        if purpose_def["required_data"] == "full_medical_record":
            allowed = role_allowed
        elif purpose_def["required_data"] == "billing_subset":
            allowed = role_allowed & {
                "demographics",
                "insurance_info",
                "procedure_codes",
                "diagnosis_codes",
                "billing_history",
            }
        elif purpose_def["required_data"] == "emergency_subset":
            allowed = {
                "demographics",
                "allergies",
                "current_medications",
                "critical_conditions",
                "emergency_contacts",
                "blood_type",
            }
        elif purpose_def["required_data"] == "de_identified_subset":
            allowed = {
                "de_identified_demographics",
                "conditions",
                "treatments",
                "outcomes",
            }
        else:
            allowed = role_allowed

        # Apply context-specific adjustments
        if context:
            allowed = self._apply_contextual_adjustments(allowed, context)

        # Return intersection with requested data
        return list(allowed & set(requested_data))

    def _apply_contextual_adjustments(
        self, allowed_data: Set[str], context: Dict[str, Any]
    ) -> Set[str]:
        """Apply contextual adjustments to allowed data.

        Args:
            allowed_data: Initially allowed data
            context: Request context

        Returns:
            Adjusted allowed data
        """
        adjusted = allowed_data.copy()

        # Emergency context
        if context.get("is_emergency"):
            # Add critical data for emergencies
            adjusted.update(
                {
                    "blood_type",
                    "emergency_contacts",
                    "advance_directives",
                    "critical_allergies",
                }
            )

        # Specific condition context
        if context.get("specific_condition"):
            condition = context["specific_condition"]
            # Add condition-specific data
            if "diabetes" in condition.lower():
                adjusted.update({"glucose_readings", "a1c_history", "insulin_regimen"})
            elif "cardiac" in condition.lower():
                adjusted.update({"ekg_results", "cardiac_markers", "echo_results"})

        # Referral context
        if context.get("is_referral"):
            adjusted.update({"referral_info", "relevant_imaging", "relevant_labs"})

        return adjusted

    def _apply_time_restriction(
        self,
        allowed_data: List[str],
        time_limit_days: int,
        context: Optional[Dict[str, Any]],
    ) -> List[str]:
        """Apply time-based restrictions to data access.

        Args:
            allowed_data: Initially allowed data
            time_limit_days: Time limit in days
            context: Request context

        Returns:
            Time-restricted data categories
        """
        # In production, would filter based on data age
        # For now, return all allowed data with time window applied
        _ = (time_limit_days, context)  # Mark as used
        return allowed_data

    def _check_special_approval(
        self, role: str, patient_id: str, context: Optional[Dict[str, Any]]
    ) -> bool:
        """Check if special approval exists for access.

        Args:
            role: Requester role
            patient_id: Patient ID
            context: Request context

        Returns:
            Whether special approval exists
        """
        # In production, would check approval database
        _ = (role, patient_id)  # Mark as used
        if context and context.get("irb_approval_number"):
            return True
        if context and context.get("court_order_number"):
            return True
        return False

    def _get_applicable_restrictions(
        self, role_def: Dict[str, Any], purpose_def: Dict[str, Any]
    ) -> List[str]:
        """Get applicable restrictions for access.

        Args:
            role_def: Role definition
            purpose_def: Purpose definition

        Returns:
            List of restrictions
        """
        restrictions = []

        if role_def.get("time_restriction"):
            restrictions.append(
                f"Access limited to data from last {role_def['time_restriction']} days"
            )

        if role_def.get("requires_relationship"):
            restrictions.append("Must have established care relationship")

        if purpose_def.get("documentation_required"):
            restrictions.append("Access must be documented with reason")

        if purpose_def.get("requires_authorization"):
            restrictions.append("Requires prior authorization")

        return restrictions

    def _log_access_decision(self, access_details: Dict[str, Any]) -> None:
        """Log access control decision.

        Args:
            access_details: Details of access decision
        """
        log_entry = {
            "timestamp": access_details["timestamp"],
            "decision_id": self._generate_decision_id(),
            "granted": access_details["granted"],
            "role": access_details.get("role"),
            "purpose": access_details.get("purpose"),
            "patient_id": access_details.get("patient_id"),
            "allowed_count": len(access_details.get("allowed_categories", [])),
            "denied_count": len(access_details.get("denied_categories", [])),
        }

        self.access_audit_log.append(log_entry)

        if access_details["granted"]:
            logger.info(
                "Access granted: %s - Role: %s, Purpose: %s",
                log_entry["decision_id"],
                log_entry["role"],
                log_entry["purpose"],
            )
        else:
            logger.warning(
                "Access denied: %s - Reason: %s",
                log_entry["decision_id"],
                access_details.get("reason"),
            )

    def create_access_policy(
        self,
        policy_name: str,
        description: str,
        roles: List[str],
        purposes: List[str],
        data_categories: List[str],
        conditions: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create custom access policy.

        Args:
            policy_name: Name of policy
            description: Policy description
            roles: Allowed roles
            purposes: Allowed purposes
            data_categories: Allowed data categories
            conditions: Additional conditions

        Returns:
            Policy ID
        """
        policy_id = self._generate_policy_id()

        policy = {
            "policy_id": policy_id,
            "policy_name": policy_name,
            "description": description,
            "created_date": datetime.now(),
            "active": True,
            "roles": roles,
            "purposes": purposes,
            "data_categories": data_categories,
            "conditions": conditions or {},
            "usage_count": 0,
            "last_used": None,
        }

        self.access_policies[policy_id] = policy

        logger.info("Access policy created: %s - %s", policy_id, policy_name)

        return policy_id

    def audit_minimum_necessary_compliance(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Audit minimum necessary compliance.

        Args:
            start_date: Audit start date
            end_date: Audit end date

        Returns:
            Audit results
        """
        # Filter audit log for date range
        relevant_logs = [
            log
            for log in self.access_audit_log
            if start_date <= log["timestamp"] <= end_date
        ]

        # Calculate metrics
        total_requests = len(relevant_logs)
        granted_requests = sum(1 for log in relevant_logs if log["granted"])
        denied_requests = total_requests - granted_requests

        # Analyze by role
        role_stats = {}
        for log in relevant_logs:
            role = log.get("role", "unknown")
            if role not in role_stats:
                role_stats[role] = {"granted": 0, "denied": 0}
            if log["granted"]:
                role_stats[role]["granted"] += 1
            else:
                role_stats[role]["denied"] += 1

        # Analyze by purpose
        purpose_stats = {}
        for log in relevant_logs:
            purpose = log.get("purpose", "unknown")
            if purpose not in purpose_stats:
                purpose_stats[purpose] = {"requests": 0, "data_items": 0}
            purpose_stats[purpose]["requests"] += 1
            purpose_stats[purpose]["data_items"] += log.get("allowed_count", 0)

        audit_report = {
            "audit_period": {"start": start_date, "end": end_date},
            "summary": {
                "total_requests": total_requests,
                "granted_requests": granted_requests,
                "denied_requests": denied_requests,
                "grant_rate": (
                    granted_requests / total_requests if total_requests > 0 else 0
                ),
            },
            "role_analysis": role_stats,
            "purpose_analysis": purpose_stats,
            "compliance_score": self._calculate_compliance_score(relevant_logs),
            "recommendations": self._generate_compliance_recommendations(
                role_stats, purpose_stats
            ),
        }

        return audit_report

    def _calculate_compliance_score(self, logs: List[Dict[str, Any]]) -> float:
        """Calculate minimum necessary compliance score.

        Args:
            logs: Access logs

        Returns:
            Compliance score (0-100)
        """
        if not logs:
            return 100.0

        # Factors for compliance score
        appropriate_denials = sum(
            1 for log in logs if not log["granted"] and log.get("denied_count", 0) > 0
        )

        minimal_access = sum(
            1 for log in logs if log["granted"] and log.get("allowed_count", 0) <= 5
        )

        total_appropriate = appropriate_denials + minimal_access
        score = (total_appropriate / len(logs)) * 100

        return round(score, 2)

    def _generate_compliance_recommendations(
        self,
        role_stats: Dict[str, Dict[str, int]],
        purpose_stats: Dict[str, Dict[str, int]],
    ) -> List[str]:
        """Generate compliance recommendations.

        Args:
            role_stats: Statistics by role
            purpose_stats: Statistics by purpose

        Returns:
            List of recommendations
        """
        recommendations = []

        # Check for high-access roles
        for role, stats in role_stats.items():
            if stats["granted"] > 100:
                recommendations.append(
                    f"Review access patterns for role '{role}' - high volume detected"
                )

        # Check for unusual purpose patterns
        for purpose, stats in purpose_stats.items():
            avg_data_items = (
                stats["data_items"] / stats["requests"] if stats["requests"] > 0 else 0
            )
            if avg_data_items > 10:
                recommendations.append(
                    f"Purpose '{purpose}' accessing large data sets - verify necessity"
                )

        if not recommendations:
            recommendations.append("Minimum necessary compliance appears appropriate")

        return recommendations

    def _generate_decision_id(self) -> str:
        """Generate unique decision ID."""
        return f"DEC-{uuid.uuid4()}"

    def _generate_policy_id(self) -> str:
        """Generate unique policy ID."""
        return f"POL-{uuid.uuid4()}"


class HIPAAAuditControls:
    """Implements HIPAA audit controls for monitoring PHI access and modifications."""

    def __init__(self) -> None:
        """Initialize audit controls system."""
        self.audit_log: List[Dict[str, Any]] = []
        self.audit_policies: Dict[str, Dict[str, Any]] = (
            self._initialize_audit_policies()
        )
        self.alert_rules: Dict[str, Dict[str, Any]] = self._initialize_alert_rules()
        self.audit_reports: Dict[str, Dict[str, Any]] = {}
        self.fhir_validator: Optional[FHIRValidator] = (
            None  # Initialize to None, lazy load later
        )

    def _initialize_audit_policies(self) -> Dict[str, Dict[str, Any]]:
        """Initialize audit policy definitions."""
        return {
            "phi_access": {
                "policy_id": "AUD-PHI-001",
                "description": "Audit all PHI access events",
                "enabled": True,
                "retention_days": 2555,  # 7 years as per HIPAA
                "log_level": "detailed",
                "includes": [
                    "user_authentication",
                    "phi_access",
                    "phi_modification",
                    "phi_deletion",
                    "report_generation",
                    "data_export",
                ],
            },
            "system_activity": {
                "policy_id": "AUD-SYS-001",
                "description": "Audit system-level activities",
                "enabled": True,
                "retention_days": 1095,  # 3 years
                "log_level": "standard",
                "includes": [
                    "system_startup",
                    "system_shutdown",
                    "configuration_changes",
                    "security_events",
                    "backup_operations",
                ],
            },
            "user_activity": {
                "policy_id": "AUD-USR-001",
                "description": "Audit user activities",
                "enabled": True,
                "retention_days": 2555,  # 7 years
                "log_level": "detailed",
                "includes": [
                    "login_attempts",
                    "logout_events",
                    "password_changes",
                    "permission_changes",
                    "failed_access_attempts",
                ],
            },
            "emergency_access": {
                "policy_id": "AUD-EMR-001",
                "description": "Audit emergency access overrides",
                "enabled": True,
                "retention_days": 2555,  # 7 years
                "log_level": "verbose",
                "includes": [
                    "break_glass_access",
                    "emergency_overrides",
                    "vip_patient_access",
                ],
                "immediate_alert": True,
            },
        }

    def _initialize_alert_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize alert rules for suspicious activities."""
        return {
            "excessive_access": {
                "rule_id": "ALERT-001",
                "description": "Alert on excessive PHI access",
                "threshold": 100,  # accesses per hour
                "window_minutes": 60,
                "severity": "high",
                "actions": ["email_security", "log_alert", "temporary_suspend"],
            },
            "after_hours_access": {
                "rule_id": "ALERT-002",
                "description": "Alert on after-hours access",
                "time_ranges": ["22:00-06:00", "weekends"],
                "severity": "medium",
                "actions": ["log_alert", "supervisor_notification"],
            },
            "unauthorized_export": {
                "rule_id": "ALERT-003",
                "description": "Alert on unauthorized data export",
                "patterns": ["bulk_export", "full_database_access"],
                "severity": "critical",
                "actions": ["immediate_suspend", "security_notification", "log_alert"],
            },
            "failed_login_attempts": {
                "rule_id": "ALERT-004",
                "description": "Alert on multiple failed login attempts",
                "threshold": 5,
                "window_minutes": 15,
                "severity": "high",
                "actions": ["account_lockout", "security_notification"],
            },
            "vip_access": {
                "rule_id": "ALERT-005",
                "description": "Alert on VIP or employee patient record access",
                "severity": "high",
                "immediate_notification": True,
                "actions": ["immediate_notification", "detailed_logging"],
            },
        }

    def log_event(
        self,
        event_type: str,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None,
        outcome: str = "success",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """Log an audit event.

        Args:
            event_type: Type of event (e.g., 'phi_access', 'login')
            user_id: ID of user performing action
            action: Action performed (e.g., 'read', 'write', 'delete')
            resource_type: Type of resource (e.g., 'patient_record', 'report')
            resource_id: ID of resource accessed
            details: Additional event details
            outcome: Event outcome ('success', 'failure', 'error')
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Audit log entry ID
        """
        audit_id = self._generate_audit_id()

        audit_entry = {
            "audit_id": audit_id,
            "timestamp": datetime.now(),
            "event_type": event_type,
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "outcome": outcome,
            "details": details or {},
            "network_info": {"ip_address": ip_address, "user_agent": user_agent},
            "session_info": self._get_session_info(user_id),
            "integrity_hash": None,  # Will be set after hashing
        }

        # Calculate integrity hash
        audit_entry["integrity_hash"] = self._calculate_integrity_hash(audit_entry)

        # Add to audit log
        self.audit_log.append(audit_entry)

        # Check alert rules
        self._check_alert_rules(audit_entry)

        # Log based on policy
        self._apply_audit_policy(audit_entry)

        return audit_id

    def log_phi_access(
        self,
        user_id: str,
        patient_id: str,
        data_accessed: List[str],
        purpose: str,
        access_granted: bool,
        denial_reason: Optional[str] = None,
    ) -> str:
        """Log PHI access event with specific details.

        Args:
            user_id: User accessing PHI
            patient_id: Patient whose PHI was accessed
            data_accessed: Categories of data accessed
            purpose: Purpose of access
            access_granted: Whether access was granted
            denial_reason: Reason if access denied

        Returns:
            Audit log entry ID
        """
        details = {
            "data_categories": data_accessed,
            "purpose": purpose,
            "access_granted": access_granted,
            "data_elements_count": len(data_accessed),
        }

        if denial_reason:
            details["denial_reason"] = denial_reason

        # Check for VIP or employee patient
        if self._is_vip_or_employee(patient_id):
            details["vip_access"] = True
            details["requires_review"] = True

        return self.log_event(
            event_type="phi_access",
            user_id=user_id,
            action="read" if access_granted else "denied",
            resource_type="patient_record",
            resource_id=patient_id,
            details=details,
            outcome="success" if access_granted else "denied",
        )

    def log_data_modification(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        changes: Dict[str, Any],
        modification_type: str = "update",
    ) -> str:
        """Log data modification event.

        Args:
            user_id: User making modification
            resource_type: Type of resource modified
            resource_id: ID of resource modified
            changes: Dictionary of changes made
            modification_type: Type of modification ('create', 'update', 'delete')

        Returns:
            Audit log entry ID
        """
        details: Dict[str, Any] = {
            "modification_type": modification_type,
            "fields_modified": (
                list(changes.keys()) if modification_type == "update" else None
            ),
            "record_count": 1,
        }

        # For updates, track before/after values (without actual PHI)
        if modification_type == "update":
            details["change_summary"] = {
                field: {"changed": True, "data_type": type(value).__name__}
                for field, value in changes.items()
            }

        return self.log_event(
            event_type="phi_modification",
            user_id=user_id,
            action=modification_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            outcome="success",
        )

    def log_security_event(
        self,
        event_subtype: str,
        user_id: Optional[str],
        details: Dict[str, Any],
        severity: str = "medium",
    ) -> str:
        """Log security-related event.

        Args:
            event_subtype: Subtype of security event
            user_id: User involved (if applicable)
            details: Event details
            severity: Event severity ('low', 'medium', 'high', 'critical')

        Returns:
            Audit log entry ID
        """
        security_details = {
            "event_subtype": event_subtype,
            "severity": severity,
            **details,
        }

        return self.log_event(
            event_type="security_event",
            user_id=user_id or "SYSTEM",
            action=event_subtype,
            resource_type="system",
            resource_id="security_subsystem",
            details=security_details,
            outcome="logged",
        )

    def log_emergency_access(
        self,
        user_id: str,
        patient_id: str,
        reason: str,
        authorizing_physician: Optional[str] = None,
    ) -> str:
        """Log emergency/break-glass access.

        Args:
            user_id: User accessing under emergency
            patient_id: Patient being accessed
            reason: Emergency reason
            authorizing_physician: Physician authorizing (if applicable)

        Returns:
            Audit log entry ID
        """
        details = {
            "access_type": "emergency_override",
            "reason": reason,
            "authorizing_physician": authorizing_physician,
            "requires_post_review": True,
            "notification_sent": True,
        }

        audit_id = self.log_event(
            event_type="emergency_access",
            user_id=user_id,
            action="break_glass_access",
            resource_type="patient_record",
            resource_id=patient_id,
            details=details,
            outcome="success",
        )

        # Send immediate notifications
        self._send_emergency_notifications(audit_id, user_id, patient_id, reason)

        return audit_id

    def query_audit_log(
        self,
        filters: Dict[str, Any],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Query audit log with filters.

        Args:
            filters: Filter criteria
            start_date: Start date for query
            end_date: End date for query
            limit: Maximum results to return

        Returns:
            List of matching audit entries
        """
        results = []

        for entry in self.audit_log:
            # Apply date filters
            if start_date and entry["timestamp"] < start_date:
                continue
            if end_date and entry["timestamp"] > end_date:
                continue

            # Apply other filters
            match = True
            for key, value in filters.items():
                if key in entry:
                    if isinstance(value, list):
                        if entry[key] not in value:
                            match = False
                            break
                    elif entry[key] != value:
                        match = False
                        break
                elif key in entry.get("details", {}):
                    if entry["details"][key] != value:
                        match = False
                        break

            if match:
                results.append(entry)
                if len(results) >= limit:
                    break

        return results

    def generate_audit_report(
        self,
        report_type: str,
        start_date: datetime,
        end_date: datetime,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate audit report.

        Args:
            report_type: Type of report to generate
            start_date: Report start date
            end_date: Report end date
            parameters: Additional report parameters

        Returns:
            Generated report
        """
        report_id = self._generate_report_id()

        # Filter logs for date range
        period_logs = [
            log for log in self.audit_log if start_date <= log["timestamp"] <= end_date
        ]

        report = {
            "report_id": report_id,
            "report_type": report_type,
            "generated_date": datetime.now(),
            "period": {"start": start_date, "end": end_date},
            "total_events": len(period_logs),
            "parameters": parameters or {},
        }

        if report_type == "user_activity":
            report["data"] = self._generate_user_activity_report(
                period_logs, parameters
            )
        elif report_type == "phi_access":
            report["data"] = self._generate_phi_access_report(period_logs, parameters)
        elif report_type == "security_summary":
            report["data"] = self._generate_security_summary_report(
                period_logs, parameters
            )
        elif report_type == "compliance":
            report["data"] = self._generate_compliance_report(period_logs, parameters)
        else:
            report["data"] = {"error": "Unknown report type"}

        self.audit_reports[report_id] = report

        # Log report generation
        self.log_event(
            event_type="report_generation",
            user_id=(
                parameters.get("requested_by", "SYSTEM") if parameters else "SYSTEM"
            ),
            action="generate_report",
            resource_type="audit_report",
            resource_id=report_id,
            details={"report_type": report_type},
        )

        return report

    def verify_audit_integrity(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Verify integrity of audit logs.

        Args:
            start_date: Start date for verification
            end_date: End date for verification

        Returns:
            Integrity verification results
        """
        results: Dict[str, Any] = {
            "verification_date": datetime.now(),
            "total_entries_checked": 0,
            "valid_entries": 0,
            "invalid_entries": 0,
            "tampering_detected": False,
            "invalid_entry_ids": [],
        }

        for entry in self.audit_log:
            # Apply date filters
            if start_date and entry["timestamp"] < start_date:
                continue
            if end_date and entry["timestamp"] > end_date:
                continue

            results["total_entries_checked"] += 1

            # Verify integrity hash
            stored_hash = entry.get("integrity_hash")
            calculated_hash = self._calculate_integrity_hash(entry, exclude_hash=True)

            if stored_hash == calculated_hash:
                results["valid_entries"] += 1
            else:
                results["invalid_entries"] += 1
                results["invalid_entry_ids"].append(entry["audit_id"])
                results["tampering_detected"] = True

        return results

    def _calculate_integrity_hash(
        self, entry: Dict[str, Any], exclude_hash: bool = False
    ) -> str:
        """Calculate integrity hash for audit entry.

        Args:
            entry: Audit entry
            exclude_hash: Whether to exclude hash field

        Returns:
            Calculated hash
        """
        # Create copy without hash field if needed
        if exclude_hash:
            entry_copy = entry.copy()
            entry_copy.pop("integrity_hash", None)
        else:
            entry_copy = entry

        # Sort keys for consistent hashing
        entry_string = json.dumps(entry_copy, sort_keys=True, default=str)

        return hashlib.sha256(entry_string.encode()).hexdigest()

    def _check_alert_rules(self, audit_entry: Dict[str, Any]) -> None:
        """Check if audit entry triggers any alert rules.

        Args:
            audit_entry: Audit entry to check
        """
        user_id = audit_entry["user_id"]

        # Check excessive access rule
        if audit_entry["event_type"] == "phi_access":
            recent_accesses = self._count_recent_events(user_id, "phi_access", 60)
            if recent_accesses > self.alert_rules["excessive_access"]["threshold"]:
                self._trigger_alert("excessive_access", audit_entry)

        # Check after-hours access
        if self._is_after_hours(audit_entry["timestamp"]):
            self._trigger_alert("after_hours_access", audit_entry)

        # Check failed login attempts
        if (
            audit_entry["event_type"] == "user_activity"
            and audit_entry["action"] == "login"
            and audit_entry["outcome"] == "failure"
        ):
            recent_failures = self._count_recent_events(user_id, "login_failure", 15)
            if (
                recent_failures
                >= self.alert_rules["failed_login_attempts"]["threshold"]
            ):
                self._trigger_alert("failed_login_attempts", audit_entry)

        # Check VIP access
        if audit_entry.get("details", {}).get("vip_access"):
            self._trigger_alert("vip_access", audit_entry)

    def _trigger_alert(self, rule_id: str, audit_entry: Dict[str, Any]) -> None:
        """Trigger alert based on rule.

        Args:
            rule_id: Alert rule ID
            audit_entry: Triggering audit entry
        """
        rule = self.alert_rules.get(rule_id)
        if not rule:
            return

        alert_details = {
            "alert_id": self._generate_alert_id(),
            "rule_id": rule_id,
            "severity": rule["severity"],
            "timestamp": datetime.now(),
            "triggering_event": audit_entry["audit_id"],
            "user_id": audit_entry["user_id"],
        }

        # Log security event
        self.log_security_event(
            event_subtype="alert_triggered",
            user_id=audit_entry["user_id"],
            details=alert_details,
            severity=rule["severity"],
        )

        # Execute alert actions
        for action in rule.get("actions", []):
            self._execute_alert_action(action, alert_details, audit_entry)

    def _execute_alert_action(
        self, action: str, alert_details: Dict[str, Any], audit_entry: Dict[str, Any]
    ) -> None:
        """Execute alert action.

        Args:
            action: Action to execute
            alert_details: Alert details
            audit_entry: Triggering audit entry
        """
        if action == "email_security":
            logger.warning("Security alert email: %s", alert_details)
        elif action == "temporary_suspend":
            logger.critical(
                "Temporary suspension triggered for user %s", audit_entry["user_id"]
            )
        elif action == "immediate_suspend":
            logger.critical(
                "Immediate suspension triggered for user %s", audit_entry["user_id"]
            )
        elif action == "account_lockout":
            logger.warning(
                "Account lockout triggered for user %s", audit_entry["user_id"]
            )
        elif action == "log_alert":
            logger.warning("Alert logged: %s", alert_details)

    def _apply_audit_policy(self, audit_entry: Dict[str, Any]) -> None:
        """Apply audit policy to entry.

        Args:
            audit_entry: Audit entry
        """
        event_type = audit_entry["event_type"]

        # Find applicable policy
        for policy in self.audit_policies.values():
            if event_type in policy.get("includes", []):
                # Apply retention policy
                audit_entry["retention_until"] = audit_entry["timestamp"] + timedelta(
                    days=policy["retention_days"]
                )

                # Apply log level
                audit_entry["log_level"] = policy["log_level"]

                break

    def _get_session_info(self, user_id: str) -> Dict[str, Any]:
        """Get current session information for user.

        Args:
            user_id: User ID

        Returns:
            Session information
        """
        # In production, would retrieve from session store
        return {
            "session_id": f"SESSION-{user_id}-{datetime.now().timestamp()}",
            "session_start": datetime.now(),
        }

    def _is_vip_or_employee(self, patient_id: str) -> bool:
        """Check if patient is VIP or employee.

        Args:
            patient_id: Patient ID

        Returns:
            Whether patient is VIP/employee
        """
        # In production, would check VIP/employee database
        _ = patient_id  # Mark as used
        return False

    def _send_emergency_notifications(
        self, audit_id: str, user_id: str, patient_id: str, reason: str
    ) -> None:
        """Send emergency access notifications.

        Args:
            audit_id: Audit entry ID
            user_id: User who accessed
            patient_id: Patient accessed
            reason: Emergency reason
        """
        logger.critical(
            "EMERGENCY ACCESS: Audit %s - User %s accessed patient %s under emergency. Reason: %s",
            audit_id,
            user_id,
            patient_id,
            reason,
        )

    def _count_recent_events(
        self, user_id: str, event_type: str, window_minutes: int
    ) -> int:
        """Count recent events for user.

        Args:
            user_id: User ID
            event_type: Event type to count
            window_minutes: Time window in minutes

        Returns:
            Count of events
        """
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)

        count = 0
        for entry in self.audit_log:
            if (
                entry["user_id"] == user_id
                and entry["event_type"] == event_type
                and entry["timestamp"] >= cutoff_time
            ):
                count += 1

        return count

    def _is_after_hours(self, timestamp: datetime) -> bool:
        """Check if timestamp is after hours.

        Args:
            timestamp: Timestamp to check

        Returns:
            Whether timestamp is after hours
        """
        hour = timestamp.hour
        weekday = timestamp.weekday()

        # After hours: 10 PM - 6 AM or weekends
        if hour >= 22 or hour < 6:
            return True
        if weekday >= 5:  # Saturday = 5, Sunday = 6
            return True

        return False

    def _generate_user_activity_report(
        self, logs: List[Dict[str, Any]], parameters: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate user activity report.

        Args:
            logs: Activity logs
            parameters: Report parameters

        Returns:
            Activity report
        """
        # Parameters will be used for filtering/formatting in production
        _ = parameters
        user_stats = {}

        for log in logs:
            user_id = log["user_id"]
            if user_id not in user_stats:
                user_stats[user_id] = {
                    "total_actions": 0,
                    "phi_accesses": 0,
                    "modifications": 0,
                    "failed_attempts": 0,
                    "emergency_accesses": 0,
                }

            user_stats[user_id]["total_actions"] += 1

            if log["event_type"] == "phi_access":
                user_stats[user_id]["phi_accesses"] += 1
            elif log["event_type"] == "phi_modification":
                user_stats[user_id]["modifications"] += 1
            elif log["event_type"] == "emergency_access":
                user_stats[user_id]["emergency_accesses"] += 1
            elif log["outcome"] == "failure":
                user_stats[user_id]["failed_attempts"] += 1

        return {
            "user_statistics": user_stats,
            "total_users": len(user_stats),
            "most_active_users": sorted(
                user_stats.items(), key=lambda x: x[1]["total_actions"], reverse=True
            )[:10],
        }

    def _generate_phi_access_report(
        self, logs: List[Dict[str, Any]], parameters: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate PHI access report.

        Args:
            logs: Audit logs to analyze
            parameters: Report parameters

        Returns:
            PHI access report
        """
        # Parameters will be used for filtering/formatting in production
        _ = parameters

        phi_logs = [log for log in logs if log["event_type"] == "phi_access"]

        patient_access_count: Dict[str, int] = {}
        purpose_breakdown: Dict[str, int] = {}
        denied_accesses = []

        for log in phi_logs:
            patient_id = log["resource_id"]
            patient_access_count[patient_id] = (
                patient_access_count.get(patient_id, 0) + 1
            )

            purpose = log.get("details", {}).get("purpose", "unknown")
            purpose_breakdown[purpose] = purpose_breakdown.get(purpose, 0) + 1

            if not log.get("details", {}).get("access_granted", True):
                denied_accesses.append(
                    {
                        "timestamp": log["timestamp"],
                        "user_id": log["user_id"],
                        "patient_id": patient_id,
                        "reason": log.get("details", {}).get("denial_reason"),
                    }
                )

        return {
            "total_phi_accesses": len(phi_logs),
            "unique_patients_accessed": len(patient_access_count),
            "access_by_purpose": purpose_breakdown,
            "most_accessed_patients": sorted(
                patient_access_count.items(), key=lambda x: x[1], reverse=True
            )[:10],
            "denied_access_count": len(denied_accesses),
            "denied_access_samples": denied_accesses[:10],
        }

    def _generate_security_summary_report(
        self, logs: List[Dict[str, Any]], parameters: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate security summary report.

        Args:
            logs: Audit logs to analyze
            parameters: Report parameters

        Returns:
            Security summary report
        """
        # Parameters will be used for filtering/formatting in production
        _ = parameters

        security_logs = [log for log in logs if log["event_type"] == "security_event"]

        severity_breakdown: Dict[str, int] = {}
        event_type_breakdown: Dict[str, int] = {}
        critical_events = []

        for log in security_logs:
            severity = log.get("details", {}).get("severity", "unknown")
            severity_breakdown[severity] = severity_breakdown.get(severity, 0) + 1

            subtype = log.get("details", {}).get("event_subtype", "unknown")
            event_type_breakdown[subtype] = event_type_breakdown.get(subtype, 0) + 1

            if severity == "critical":
                critical_events.append(
                    {
                        "timestamp": log["timestamp"],
                        "event": subtype,
                        "user_id": log["user_id"],
                        "details": log.get("details", {}),
                    }
                )

        return {
            "total_security_events": len(security_logs),
            "severity_breakdown": severity_breakdown,
            "event_type_breakdown": event_type_breakdown,
            "critical_event_count": len(critical_events),
            "critical_events": critical_events[:20],
        }

    def _generate_compliance_report(
        self, logs: List[Dict[str, Any]], parameters: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate compliance report.

        Args:
            logs: Audit logs to analyze
            parameters: Report parameters

        Returns:
            Compliance report
        """
        # Parameters will be used for filtering/formatting in production
        _ = parameters

        # Verify audit integrity
        integrity_check = self.verify_audit_integrity()

        # Calculate compliance metrics
        total_events = len(logs)
        emergency_accesses = len(
            [log for log in logs if log["event_type"] == "emergency_access"]
        )
        failed_accesses = len([log for log in logs if log["outcome"] == "failure"])

        return {
            "audit_integrity": integrity_check,
            "total_audited_events": total_events,
            "emergency_access_percentage": (
                (emergency_accesses / total_events * 100) if total_events > 0 else 0
            ),
            "failed_access_percentage": (
                (failed_accesses / total_events * 100) if total_events > 0 else 0
            ),
            "retention_compliance": self._check_retention_compliance(),
            "audit_coverage": self._calculate_audit_coverage(logs),
            "recommendations": self._generate_compliance_recommendations(logs),
        }

    def _check_retention_compliance(self) -> Dict[str, Any]:
        """Check audit log retention compliance.

        Returns:
            Retention compliance status
        """
        if not self.audit_log:
            return {"compliant": True, "message": "No audit logs to check"}

        oldest_entry = min(
            self.audit_log, key=lambda x: x.get("timestamp", datetime.now())
        )

        timestamp = oldest_entry.get("timestamp")
        if not timestamp:
            return {"compliant": True, "message": "Invalid audit log entry"}

        age_days = (datetime.now() - timestamp).days

        return {
            "compliant": age_days <= 2555,  # 7 years
            "oldest_entry_age_days": age_days,
            "required_retention_days": 2555,
            "message": (
                "Compliant"
                if age_days <= 2555
                else "Non-compliant: logs older than required retention period"
            ),
        }

    def _calculate_audit_coverage(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate audit coverage metrics.

        Args:
            logs: Audit logs to analyze

        Returns:
            Coverage metrics
        """
        event_types = set(log["event_type"] for log in logs)
        expected_types = {
            "phi_access",
            "phi_modification",
            "user_activity",
            "security_event",
        }

        return {
            "event_type_coverage": len(event_types) / len(expected_types) * 100,
            "covered_event_types": list(event_types),
            "missing_event_types": list(expected_types - event_types),
        }

    def _generate_compliance_recommendations(
        self, logs: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate compliance recommendations.

        Args:
            logs: Audit logs to analyze

        Returns:
            List of recommendations
        """
        recommendations = []

        # Check for patterns
        emergency_rate = (
            len([log for log in logs if log["event_type"] == "emergency_access"])
            / len(logs)
            if logs
            else 0
        )
        if emergency_rate > 0.05:  # More than 5% emergency access
            recommendations.append(
                "High emergency access rate detected - review emergency access policies"
            )

        failed_rate = (
            len([log for log in logs if log["outcome"] == "failure"]) / len(logs)
            if logs
            else 0
        )
        if failed_rate > 0.1:  # More than 10% failures
            recommendations.append(
                "High failure rate detected - review access controls and user training"
            )

        if not recommendations:
            recommendations.append(
                "Audit patterns appear normal - maintain current monitoring"
            )

        return recommendations

    def _generate_audit_id(self) -> str:
        """Generate unique audit ID."""
        return f"AUD-{uuid.uuid4()}"

    def _generate_report_id(self) -> str:
        """Generate unique report ID."""
        return f"RPT-{uuid.uuid4()}"

    def _generate_alert_id(self) -> str:
        """Generate unique alert ID."""
        return f"ALRT-{uuid.uuid4()}"

    def validate_fhir_consent(self, consent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate GDPR consent data as FHIR Consent resource.

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
            # Lazy load the validator
            self.fhir_validator = FHIRValidator()
        return self.fhir_validator.validate_resource("Consent", consent_data)

    def create_fhir_consent(
        self,
        patient_id: str,
        purpose: ProcessingPurpose,
        lawful_basis: GDPRLawfulBasis,
        status: Literal[
            "draft", "proposed", "active", "rejected", "inactive", "entered-in-error"
        ] = "active",
    ) -> FHIRConsent:
        """Create FHIR Consent resource for GDPR compliance.

        Args:
            patient_id: Patient identifier
            purpose: Processing purpose
            lawful_basis: GDPR lawful basis
            status: Consent status

        Returns:
            FHIR Consent resource
        """
        consent: FHIRConsent = {
            "resourceType": "Consent",
            "id": str(uuid.uuid4()),
            "status": status,
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
                            "system": "http://loinc.org",
                            "code": "59284-0",
                            "display": "Consent Document",
                        }
                    ]
                },
                {
                    "coding": [
                        {
                            "system": "http://havenhealthpassport.org/fhir/CodeSystem/gdpr",
                            "code": "gdpr-consent",
                            "display": "GDPR Consent",
                        }
                    ]
                },
            ],
            "patient": {"reference": f"Patient/{patient_id}"},
            "dateTime": datetime.now().isoformat(),
            "policy": [
                {
                    "authority": "https://gdpr.eu",
                    "uri": f"https://gdpr.eu/article-{self._get_gdpr_article(lawful_basis)}/",
                }
            ],
            "provision": {
                "type": "permit",
                "purpose": [
                    {
                        "system": "http://havenhealthpassport.org/fhir/CodeSystem/processing-purposes",
                        "code": purpose.value,
                        "display": purpose.value.replace("_", " ").title(),
                    }
                ],
                "dataPeriod": {
                    "start": datetime.now().isoformat(),
                    "end": (datetime.now() + timedelta(days=365)).isoformat(),
                },
            },
            "__fhir_resource__": "Consent",
        }

        return consent

    def _get_gdpr_article(self, lawful_basis: GDPRLawfulBasis) -> str:
        """Get GDPR article number for lawful basis."""
        article_map = {
            GDPRLawfulBasis.CONSENT: "6-1-a",
            GDPRLawfulBasis.CONTRACT: "6-1-b",
            GDPRLawfulBasis.LEGAL_OBLIGATION: "6-1-c",
            GDPRLawfulBasis.VITAL_INTERESTS: "6-1-d",
            GDPRLawfulBasis.PUBLIC_TASK: "6-1-e",
            GDPRLawfulBasis.LEGITIMATE_INTERESTS: "6-1-f",
            GDPRLawfulBasis.EXPLICIT_CONSENT: "9-2-a",
            GDPRLawfulBasis.HEALTHCARE: "9-2-h",
            GDPRLawfulBasis.PUBLIC_HEALTH: "9-2-i",
        }
        return article_map.get(lawful_basis, "6-1-a")


def validate_fhir(fhir_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate FHIR data for GDPR consent resources.

    Args:
        fhir_data: FHIR data to validate

    Returns:
        Validation results
    """
    errors = []
    warnings = []

    # Check resource type
    if fhir_data.get("resourceType") != "Consent":
        errors.append("Resource type must be Consent for GDPR compliance")

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

    # Check for GDPR-specific policy
    if "policy" in fhir_data and isinstance(fhir_data["policy"], list):
        has_gdpr_policy = any(
            p.get("uri", "").startswith("http://gdpr.europa.eu/")
            for p in fhir_data["policy"]
        )
        if not has_gdpr_policy:
            warnings.append("GDPR policy reference is recommended")

    # Validate provision has necessary elements
    if "provision" in fhir_data:
        provision = fhir_data["provision"]
        if "type" not in provision:
            errors.append("Provision must have 'type' (permit/deny)")
        if "dataPeriod" not in provision:
            warnings.append("Data retention period is recommended in provision")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
