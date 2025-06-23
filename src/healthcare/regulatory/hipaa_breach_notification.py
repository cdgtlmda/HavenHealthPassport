"""HIPAA Breach Notification Implementation.

This module implements HIPAA breach notification requirements, including
breach assessment, notification timelines, and reporting procedures.
"""

import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TypedDict, cast

from src.healthcare.fhir_validator import FHIRValidator

# FHIR resource type for this module
__fhir_resource__ = "AuditEvent"

logger = logging.getLogger(__name__)


class FHIRAuditEvent(TypedDict, total=False):
    """FHIR AuditEvent resource type definition for breach notifications."""

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


class BreachType(Enum):
    """Types of PHI breaches."""

    THEFT = "theft"
    LOSS = "loss"
    IMPROPER_DISPOSAL = "improper_disposal"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    UNAUTHORIZED_DISCLOSURE = "unauthorized_disclosure"
    HACKING_IT_INCIDENT = "hacking_it_incident"
    EMPLOYEE_ERROR = "employee_error"
    BUSINESS_ASSOCIATE = "business_associate"
    OTHER = "other"


class BreachSeverity(Enum):
    """Breach severity levels."""

    LOW = "low"  # < 500 individuals
    MEDIUM = "medium"  # 500-999 individuals
    HIGH = "high"  # 1000+ individuals
    CRITICAL = "critical"  # Involves media or HHS Secretary notification


class NotificationStatus(Enum):
    """Status of breach notifications."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_REQUIRED = "not_required"


class HIPAABreachNotification:
    """Implements HIPAA breach notification requirements."""

    def __init__(self) -> None:
        """Initialize breach notification system."""
        self.breach_registry: Dict[str, Dict[str, Any]] = {}
        self.risk_assessments: Dict[str, Dict[str, Any]] = {}
        self.notifications: Dict[str, Dict[str, Any]] = {}
        self.notification_templates = self._initialize_templates()
        self.timeline_requirements = self._initialize_timelines()
        self._annual_submissions: List[Dict[str, Any]] = []
        self.fhir_validator: Optional[FHIRValidator] = (
            None  # Will be initialized when needed
        )

    def _initialize_templates(self) -> Dict[str, str]:
        """Initialize notification templates."""
        return {
            "individual_notice": """
Dear {individual_name},

We are writing to notify you of a breach of your protected health information.

What Happened: {breach_description}
When It Happened: {breach_date}
When We Discovered It: {discovery_date}

What Information Was Involved: {information_types}

What We Are Doing: {mitigation_steps}

What You Should Do: {individual_steps}

For More Information: {contact_info}

Sincerely,
{organization_name}
""",
            "media_notice": """
{organization_name} Reports Breach of Protected Health Information

{city}, {state} - {organization_name} is notifying {affected_count} individuals
of a breach of protected health information that occurred on {breach_date}.

The breach involved {breach_description}. The types of information involved
included {information_types}.

{organization_name} is {mitigation_steps}. Affected individuals are being
notified by {notification_method} and are being offered {services_offered}.

For more information, contact {contact_info}.
""",
            "hhs_notice": """
Breach Notification to HHS Secretary

Organization: {organization_name}
Date of Breach: {breach_date}
Date of Discovery: {discovery_date}
Number of Individuals Affected: {affected_count}
Type of Breach: {breach_type}
Location of Breach: {breach_location}
Type of PHI Involved: {phi_types}
Safeguards in Place: {safeguards}
Mitigation Actions: {mitigation_actions}
""",
        }

    def _initialize_timelines(self) -> Dict[str, timedelta]:
        """Initialize notification timeline requirements."""
        return {
            "individual_notification": timedelta(days=60),  # 60 days
            "media_notification": timedelta(days=60),  # 60 days for 500+ people
            "hhs_notification_low": timedelta(days=60),  # 60 days for <500
            "hhs_notification_high": timedelta(days=60),  # 60 days for 500+
            "annual_summary": timedelta(days=60),  # 60 days after year end
            "law_enforcement_delay": timedelta(days=30),  # Initial delay period
            "substitute_notice": timedelta(days=60),  # If contact info insufficient
        }

    def report_breach(
        self,
        breach_type: BreachType,
        discovery_date: datetime,
        affected_individuals: List[Dict[str, Any]],
        phi_involved: List[str],
        breach_description: str,
        breach_location: str,
        containment_date: Optional[datetime] = None,
    ) -> str:
        """Report a PHI breach.

        Args:
            breach_type: Type of breach
            discovery_date: When breach was discovered
            affected_individuals: List of affected individuals
            phi_involved: Types of PHI involved
            breach_description: Description of breach
            breach_location: Where breach occurred
            containment_date: When breach was contained

        Returns:
            Breach ID
        """
        breach_id = self._generate_breach_id()

        breach_record = {
            "breach_id": breach_id,
            "type": breach_type.value,
            "reported_date": datetime.now(),
            "discovery_date": discovery_date,
            "containment_date": containment_date,
            "affected_count": len(affected_individuals),
            "affected_individuals": affected_individuals,
            "phi_types": phi_involved,
            "description": breach_description,
            "location": breach_location,
            "severity": self._determine_severity(len(affected_individuals)),
            "status": "reported",
            "risk_assessment_required": True,
            "notifications_required": [],
        }

        self.breach_registry[breach_id] = breach_record

        # Perform initial assessment
        self._perform_initial_assessment(breach_id)

        logger.warning(
            "Breach reported: %s - Type: %s, Affected: %d",
            breach_id,
            breach_type.value,
            len(affected_individuals),
        )

        return breach_id

    def perform_risk_assessment(self, breach_id: str) -> Dict[str, Any]:
        """Perform four-factor risk assessment.

        Args:
            breach_id: Breach identifier

        Returns:
            Risk assessment results
        """
        if breach_id not in self.breach_registry:
            raise ValueError(f"Breach {breach_id} not found")

        breach = self.breach_registry[breach_id]

        # Four-factor risk assessment per HIPAA
        assessment = {
            "breach_id": breach_id,
            "assessment_date": datetime.now(),
            "factors": {
                "nature_extent": self._assess_nature_extent(breach),
                "unauthorized_person": self._assess_unauthorized_person(breach),
                "acquired_viewed": self._assess_acquisition_viewing(breach),
                "mitigation": self._assess_mitigation(breach),
            },
            "overall_risk": "low",
            "notification_required": True,
            "reasoning": [],
        }

        # Determine overall risk
        factors = cast(Dict[str, Any], assessment["factors"])
        risk_scores = [f["risk_level"] for f in factors.values()]
        if any(risk == "high" for risk in risk_scores):
            assessment["overall_risk"] = "high"
        elif any(risk == "medium" for risk in risk_scores):
            assessment["overall_risk"] = "medium"

        # Determine if notification required
        if assessment["overall_risk"] == "low":
            # Check if exception applies
            if self._check_low_risk_exceptions(breach):
                assessment["notification_required"] = False
                reasoning = cast(List[str], assessment["reasoning"])
                reasoning.append("Low risk exception applies")

        self.risk_assessments[breach_id] = assessment

        # Update breach record
        breach["risk_assessment_completed"] = True
        breach["notification_required"] = assessment["notification_required"]

        return assessment

    def notify_individuals(
        self, breach_id: str, notification_method: str = "written"
    ) -> Dict[str, Any]:
        """Notify affected individuals of breach.

        Args:
            breach_id: Breach identifier
            notification_method: Method of notification

        Returns:
            Notification results
        """
        if breach_id not in self.breach_registry:
            raise ValueError(f"Breach {breach_id} not found")

        breach = self.breach_registry[breach_id]

        # Check if notification required
        if not breach.get("notification_required", True):
            return {
                "breach_id": breach_id,
                "status": NotificationStatus.NOT_REQUIRED.value,
                "reason": "Risk assessment determined notification not required",
            }

        # Check timeline
        deadline = (
            breach["discovery_date"]
            + self.timeline_requirements["individual_notification"]
        )
        if datetime.now() > deadline:
            logger.warning(
                "Individual notification deadline exceeded for breach %s", breach_id
            )

        # Prepare notifications
        notification_record = {
            "breach_id": breach_id,
            "notification_type": "individual",
            "method": notification_method,
            "start_date": datetime.now(),
            "total_individuals": breach["affected_count"],
            "notified_count": 0,
            "failed_count": 0,
            "status": NotificationStatus.IN_PROGRESS.value,
            "notifications": [],
        }

        # Send notifications to each individual
        for individual in breach["affected_individuals"]:
            notice = self._send_individual_notice(
                breach, individual, notification_method
            )
            notification_record["notifications"].append(notice)

            if notice["sent"]:
                notification_record["notified_count"] += 1
            else:
                notification_record["failed_count"] += 1

        # Update status
        if (
            notification_record["notified_count"]
            == notification_record["total_individuals"]
        ):
            notification_record["status"] = NotificationStatus.COMPLETED.value
        elif notification_record["failed_count"] > 0:
            notification_record["status"] = NotificationStatus.FAILED.value

        self.notifications[f"{breach_id}_individual"] = notification_record

        return notification_record

    def notify_media(self, breach_id: str) -> Dict[str, Any]:
        """Notify media for breaches affecting 500+ in a state.

        Args:
            breach_id: Breach identifier

        Returns:
            Media notification results
        """
        if breach_id not in self.breach_registry:
            raise ValueError(f"Breach {breach_id} not found")

        breach = self.breach_registry[breach_id]

        # Check if media notification required
        if breach["affected_count"] < 500:
            return {
                "breach_id": breach_id,
                "status": NotificationStatus.NOT_REQUIRED.value,
                "reason": "Fewer than 500 individuals affected",
            }

        # Group by state/jurisdiction
        individuals_by_state = self._group_by_state(breach["affected_individuals"])

        notification_record = {
            "breach_id": breach_id,
            "notification_type": "media",
            "start_date": datetime.now(),
            "states_notified": [],
            "status": NotificationStatus.IN_PROGRESS.value,
        }

        # Notify media in states with 500+ affected
        for state, individuals in individuals_by_state.items():
            if len(individuals) >= 500:
                media_notice = self._send_media_notice(breach, state, len(individuals))
                states_notified = cast(
                    List[Any], notification_record["states_notified"]
                )
                states_notified.append(
                    {
                        "state": state,
                        "affected_count": len(individuals),
                        "notice_sent": media_notice["sent"],
                        "media_outlets": media_notice.get("outlets", []),
                    }
                )

        notification_record["status"] = NotificationStatus.COMPLETED.value
        self.notifications[f"{breach_id}_media"] = notification_record

        return notification_record

    def notify_hhs(self, breach_id: str) -> Dict[str, Any]:
        """Notify HHS Secretary of breach.

        Args:
            breach_id: Breach identifier

        Returns:
            HHS notification results
        """
        if breach_id not in self.breach_registry:
            raise ValueError(f"Breach {breach_id} not found")

        breach = self.breach_registry[breach_id]

        # Determine notification timeline
        if breach["affected_count"] >= 500:
            # Must notify within 60 days
            deadline = (
                breach["discovery_date"]
                + self.timeline_requirements["hhs_notification_high"]
            )
            immediate = True
        else:
            # Can notify annually for <500
            deadline = self._get_annual_deadline()
            immediate = False

        notification_record = {
            "breach_id": breach_id,
            "notification_type": "hhs",
            "submission_date": datetime.now() if immediate else None,
            "deadline": deadline,
            "immediate_notification": immediate,
            "status": (
                NotificationStatus.PENDING.value
                if not immediate
                else NotificationStatus.IN_PROGRESS.value
            ),
            "submission_details": {},
        }

        if immediate:
            # Submit immediately
            submission = self._submit_to_hhs(breach)
            notification_record["submission_details"] = submission
            notification_record["status"] = (
                NotificationStatus.COMPLETED.value
                if submission["success"]
                else NotificationStatus.FAILED.value
            )
        else:
            # Add to annual submission queue
            self._add_to_annual_submission(breach_id)

        self.notifications[f"{breach_id}_hhs"] = notification_record

        return notification_record

    def request_law_enforcement_delay(
        self, breach_id: str, requesting_agency: str, reason: str
    ) -> Dict[str, Any]:
        """Request delay in notification for law enforcement.

        Args:
            breach_id: Breach identifier
            requesting_agency: Law enforcement agency
            reason: Reason for delay

        Returns:
            Delay approval details
        """
        if breach_id not in self.breach_registry:
            raise ValueError(f"Breach {breach_id} not found")

        delay_request = {
            "breach_id": breach_id,
            "request_date": datetime.now(),
            "agency": requesting_agency,
            "reason": reason,
            "initial_delay": self.timeline_requirements["law_enforcement_delay"],
            "approved": True,
            "delay_until": datetime.now()
            + self.timeline_requirements["law_enforcement_delay"],
        }

        # Update breach record
        breach = self.breach_registry[breach_id]
        breach["law_enforcement_delay"] = delay_request
        breach["notification_delayed"] = True

        logger.info(
            "Law enforcement delay approved for breach %s until %s",
            breach_id,
            delay_request["delay_until"],
        )

        return delay_request

    def _determine_severity(self, affected_count: int) -> str:
        """Determine breach severity based on affected individuals."""
        if affected_count >= 1000:
            return BreachSeverity.CRITICAL.value
        elif affected_count >= 500:
            return BreachSeverity.HIGH.value
        elif affected_count >= 100:
            return BreachSeverity.MEDIUM.value
        else:
            return BreachSeverity.LOW.value

    def _perform_initial_assessment(self, breach_id: str) -> None:
        """Perform initial breach assessment."""
        breach = self.breach_registry[breach_id]

        # Determine required notifications
        notifications_required = ["individual", "hhs"]

        if breach["affected_count"] >= 500:
            notifications_required.append("media")

        breach["notifications_required"] = notifications_required

    def _assess_nature_extent(self, breach: Dict[str, Any]) -> Dict[str, Any]:
        """Assess nature and extent of PHI involved."""
        phi_types = breach.get("phi_types", [])

        risk_level = "low"
        if any(
            sensitive in phi_types for sensitive in ["ssn", "financial", "diagnosis"]
        ):
            risk_level = "high"
        elif len(phi_types) > 3:
            risk_level = "medium"

        return {
            "factor": "nature_extent",
            "phi_types": phi_types,
            "risk_level": risk_level,
            "reasoning": f"Breach involved {len(phi_types)} types of PHI",
        }

    def _assess_unauthorized_person(self, breach: Dict[str, Any]) -> Dict[str, Any]:
        """Assess the unauthorized person who received PHI."""
        breach_type = breach.get("type")

        risk_level = "medium"
        reasoning = "Unknown recipient"

        if breach_type == BreachType.BUSINESS_ASSOCIATE.value:
            risk_level = "low"
            reasoning = "Business associate with existing obligations"
        elif breach_type in [
            BreachType.THEFT.value,
            BreachType.HACKING_IT_INCIDENT.value,
        ]:
            risk_level = "high"
            reasoning = "Malicious actor likely involved"
        elif breach_type == BreachType.EMPLOYEE_ERROR.value:
            risk_level = "low"
            reasoning = "Internal employee with training"

        return {
            "factor": "unauthorized_person",
            "breach_type": breach_type,
            "risk_level": risk_level,
            "reasoning": reasoning,
        }

    def _assess_acquisition_viewing(self, breach: Dict[str, Any]) -> Dict[str, Any]:
        """Assess whether PHI was actually acquired or viewed."""
        # In real implementation, would have forensic data
        containment_date = breach.get("containment_date")
        discovery_date = breach.get("discovery_date")

        if containment_date and discovery_date:
            exposure_time = containment_date - discovery_date
            if exposure_time < timedelta(hours=1):
                risk_level = "low"
                reasoning = "Short exposure window"
            elif exposure_time < timedelta(days=1):
                risk_level = "medium"
                reasoning = "Moderate exposure window"
            else:
                risk_level = "high"
                reasoning = "Extended exposure window"
        else:
            risk_level = "high"
            reasoning = "Unknown exposure duration"

        return {
            "factor": "acquisition_viewing",
            "risk_level": risk_level,
            "reasoning": reasoning,
        }

    def _assess_mitigation(self, breach: Dict[str, Any]) -> Dict[str, Any]:
        """Assess mitigation efforts."""
        # Check if mitigation steps were taken
        description = breach.get("description", "").lower()

        mitigation_indicators = [
            "encrypted",
            "destroyed",
            "returned",
            "agreement",
            "trained",
            "cannot be used",
        ]

        has_mitigation = any(
            indicator in description for indicator in mitigation_indicators
        )

        if has_mitigation:
            risk_level = "low"
            reasoning = "Mitigation measures in place"
        else:
            risk_level = "medium"
            reasoning = "No clear mitigation identified"

        return {
            "factor": "mitigation",
            "risk_level": risk_level,
            "reasoning": reasoning,
            "mitigation_present": has_mitigation,
        }

    def _check_low_risk_exceptions(self, breach: Dict[str, Any]) -> bool:
        """Check if low risk exceptions apply."""
        # Exception 1: Unintentional acquisition by workforce member
        if breach.get("type") == BreachType.EMPLOYEE_ERROR.value:
            description = breach.get("description", "").lower()
            if "unintentional" in description and "good faith" in description:
                return True

        # Exception 2: Inadvertent disclosure within facility
        if "inadvertent" in breach.get("description", "").lower():
            return True

        # Exception 3: Recipient could not retain information
        if "unable to retain" in breach.get("description", "").lower():
            return True

        return False

    def _send_individual_notice(
        self, breach: Dict[str, Any], individual: Dict[str, Any], method: str
    ) -> Dict[str, Any]:
        """Send notice to individual."""
        # Prepare notice content
        notice_content = self.notification_templates["individual_notice"].format(
            individual_name=individual.get("name", "Patient"),
            breach_description=breach["description"],
            breach_date=breach.get("breach_date", "Unknown"),
            discovery_date=breach["discovery_date"].strftime("%B %d, %Y"),
            information_types=", ".join(breach["phi_types"]),
            mitigation_steps="conducting a thorough investigation and enhancing security",
            individual_steps="monitor your accounts and medical records",
            contact_info="Privacy Officer at 1-800-XXX-XXXX",
            organization_name="Healthcare Organization",
        )

        # Simulate sending
        notice_record = {
            "individual_id": individual.get("id"),
            "method": method,
            "sent_date": datetime.now(),
            "content": notice_content,
            "sent": True,  # In production, would track actual delivery
            "delivery_confirmed": False,
        }

        if method == "written":
            if not individual.get("address"):
                notice_record["sent"] = False
                notice_record["failure_reason"] = "No address available"
        elif method == "email":
            if not individual.get("email"):
                notice_record["sent"] = False
                notice_record["failure_reason"] = "No email available"

        return notice_record

    def _send_media_notice(
        self, breach: Dict[str, Any], state: str, affected_count: int
    ) -> Dict[str, Any]:
        """Send notice to media outlets."""
        notice_content = self.notification_templates["media_notice"].format(
            organization_name="Healthcare Organization",
            city="City",
            state=state,
            affected_count=affected_count,
            breach_date=breach.get("breach_date", "Unknown"),
            breach_description=breach["description"],
            information_types=", ".join(breach["phi_types"]),
            mitigation_steps="taking steps to prevent future incidents",
            notification_method="direct mail",
            services_offered="credit monitoring services",
            contact_info="1-800-XXX-XXXX",
        )

        # In production, would send to actual media outlets
        return {
            "sent": True,
            "outlets": ["Major newspaper", "Local TV station"],
            "content": notice_content,
            "sent_date": datetime.now(),
        }

    def _submit_to_hhs(self, breach: Dict[str, Any]) -> Dict[str, Any]:
        """Submit breach notification to HHS."""
        submission = {
            "submission_date": datetime.now(),
            "breach_id": breach["breach_id"],
            "success": True,  # In production, would use HHS breach portal
            "confirmation_number": f"HHS-{breach['breach_id']}-CONF",
            "content": self.notification_templates["hhs_notice"].format(
                organization_name="Healthcare Organization",
                breach_date=breach.get("breach_date", "Unknown"),
                discovery_date=breach["discovery_date"].strftime("%Y-%m-%d"),
                affected_count=breach["affected_count"],
                breach_type=breach["type"],
                breach_location=breach["location"],
                phi_types=", ".join(breach["phi_types"]),
                safeguards="Access controls, encryption, monitoring",
                mitigation_actions="Investigation, notification, enhanced security",
            ),
        }

        return submission

    def _group_by_state(
        self, individuals: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group individuals by state."""
        by_state: Dict[str, List[Dict[str, Any]]] = {}

        for individual in individuals:
            state = individual.get("state", "Unknown")
            if state not in by_state:
                by_state[state] = []
            by_state[state].append(individual)

        return by_state

    def _get_annual_deadline(self) -> datetime:
        """Get deadline for annual HHS submission."""
        # 60 days after end of calendar year
        current_year = datetime.now().year
        year_end = datetime(current_year, 12, 31)
        return year_end + timedelta(days=60)

    def _add_to_annual_submission(self, breach_id: str) -> None:
        """Add breach to annual submission list."""
        # In production, this would persist to database
        if not hasattr(self, "_annual_submissions"):
            self._annual_submissions = []
        self._annual_submissions.append({"breach_id": str(breach_id)})

    def validate_fhir_breach_audit(self, audit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate FHIR AuditEvent for breach notification.

        Args:
            audit_data: FHIR AuditEvent resource data

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        errors = []
        warnings = []

        # Initialize FHIR validator if needed
        if not hasattr(self, "fhir_validator"):
            self.fhir_validator = FHIRValidator()

        # Ensure resource type
        if "resourceType" not in audit_data:
            audit_data["resourceType"] = "AuditEvent"

        # Check required fields
        if not audit_data.get("type"):
            errors.append("AuditEvent must have type")

        if not audit_data.get("recorded"):
            errors.append("AuditEvent must have recorded timestamp")

        if not audit_data.get("agent") or not isinstance(audit_data["agent"], list):
            errors.append("AuditEvent must have at least one agent")

        if not audit_data.get("source"):
            errors.append("AuditEvent must have source")

        # Validate action code for breach
        if action := audit_data.get("action"):
            if action != "R":  # Read action for unauthorized access
                warnings.append("Breach events typically use 'R' action code")

        # Validate outcome code for breach
        if outcome := audit_data.get("outcome"):
            if outcome == "0":  # Success
                errors.append("Breach events should not have success outcome")
            elif outcome not in ["4", "8", "12"]:
                errors.append(f"Invalid outcome code for breach: {outcome}")

        # Check for breach-specific extensions
        if "extension" in audit_data:
            has_breach_type = False
            for ext in audit_data["extension"]:
                if (
                    ext.get("url")
                    == "http://havenhealthpassport.org/fhir/StructureDefinition/breach-type"
                ):
                    has_breach_type = True
                    break

            if not has_breach_type:
                warnings.append(
                    "Breach AuditEvent should include breach type extension"
                )

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def create_fhir_breach_audit(
        self,
        breach_type: BreachType,
        affected_count: int,
        discovered_date: datetime,
        actor_id: Optional[str] = None,
    ) -> FHIRAuditEvent:
        """Create FHIR AuditEvent for breach notification.

        Args:
            breach_type: Type of breach
            affected_count: Number of affected individuals
            discovered_date: When breach was discovered
            actor_id: ID of person/system responsible (if known)

        Returns:
            FHIR AuditEvent resource
        """
        audit_event: FHIRAuditEvent = {
            "resourceType": "AuditEvent",
            "type": {
                "system": "http://terminology.hl7.org/CodeSystem/audit-event-type",
                "code": "security",
                "display": "Security Event",
            },
            "subtype": [
                {
                    "system": "http://havenhealthpassport.org/fhir/CodeSystem/breach-types",
                    "code": breach_type.value,
                    "display": breach_type.value.replace("_", " ").title(),
                }
            ],
            "action": "R",  # Unauthorized read
            "recorded": discovered_date.isoformat() + "Z",
            "outcome": "8",  # Serious failure
            "outcomeDesc": f"HIPAA breach affecting {affected_count} individuals",
            "agent": [
                {
                    "who": {"identifier": {"value": actor_id or "unknown"}},
                    "requestor": False,
                    "type": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/extra-security-role-type",
                                "code": "intruder",
                                "display": "Intruder",
                            }
                        ]
                    },
                }
            ],
            "source": {
                "observer": {"display": "Haven Health Passport Breach Detection"},
                "type": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/security-source-type",
                        "code": "4",
                        "display": "Application Server",
                    }
                ],
            },
            "entity": [
                {
                    "what": {"display": f"PHI of {affected_count} individuals"},
                    "type": {
                        "system": "http://terminology.hl7.org/CodeSystem/audit-entity-type",
                        "code": "1",
                        "display": "Person",
                    },
                    "detail": [
                        {"type": "affected-count", "valueString": str(affected_count)}
                    ],
                }
            ],
            "__fhir_resource__": "AuditEvent",
        }

        # Add extension for breach type (cast to avoid type error)
        audit_event_with_extension = dict(audit_event)
        audit_event_with_extension["extension"] = [
            {
                "url": "http://havenhealthpassport.org/fhir/StructureDefinition/breach-type",
                "valueCode": breach_type.value,
            }
        ]

        return cast(FHIRAuditEvent, audit_event_with_extension)

    def _add_to_hhs_submission_queue(self, breach_id: str) -> None:
        """Add breach to annual HHS submission queue."""
        # In production, would maintain queue for annual submission
        logger.info("Breach %s added to annual HHS submission queue", breach_id)

    def _generate_breach_id(self) -> str:
        """Generate unique breach ID."""
        return f"BREACH-{uuid.uuid4()}"


def validate_fhir(fhir_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate FHIR data for breach notification audit events.

    Args:
        fhir_data: FHIR data to validate

    Returns:
        Validation results
    """
    errors = []
    warnings = []

    # Check resource type
    if fhir_data.get("resourceType") != "AuditEvent":
        errors.append("Resource type must be AuditEvent for breach notifications")

    # Check required fields
    required_fields = ["type", "recorded", "agent", "source", "entity"]
    for field in required_fields:
        if field not in fhir_data:
            errors.append(f"Required field '{field}' is missing")

    # Validate outcome code
    if "outcome" in fhir_data:
        valid_outcomes = ["0", "4", "8", "12"]
        if fhir_data["outcome"] not in valid_outcomes:
            errors.append(f"Invalid outcome code: {fhir_data['outcome']}")

    # Check for breach-specific extensions
    if "extension" in fhir_data:
        breach_extension = next(
            (
                ext
                for ext in fhir_data["extension"]
                if ext.get("url")
                == "http://havenhealthpassport.org/fhir/StructureDefinition/breach-type"
            ),
            None,
        )
        if not breach_extension:
            warnings.append(
                "Breach type extension is recommended for breach notifications"
            )

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
