"""ISO 27001 Controls Implementation for Healthcare.

This module implements the ISO 27001:2022 information security controls
specifically tailored for healthcare data protection and HIPAA/GDPR compliance.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ControlFamily(Enum):
    """ISO 27001 Annex A control families."""

    # A.5 - Organizational controls
    POLICIES = "policies_for_information_security"
    ROLES = "information_security_roles_and_responsibilities"
    SEGREGATION = "segregation_of_duties"
    MANAGEMENT_RESPONSIBILITIES = "management_responsibilities"

    # A.6 - People controls
    SCREENING = "screening"
    TERMS_CONDITIONS = "terms_and_conditions_of_employment"
    AWARENESS = "information_security_awareness_education_training"
    DISCIPLINARY = "disciplinary_process"

    # A.7 - Physical controls
    PHYSICAL_PERIMETERS = "physical_security_perimeters"
    PHYSICAL_ACCESS = "physical_entry_controls"
    OFFICES = "securing_offices_rooms_facilities"
    MONITORING = "physical_security_monitoring"

    # A.8 - Technological controls
    ACCESS_CONTROL = "access_control"
    IDENTITY_MANAGEMENT = "identity_management"
    AUTHENTICATION = "authentication_information"
    ACCESS_RIGHTS = "access_rights"
    PRIVILEGED_ACCESS = "privileged_access_management"
    ENCRYPTION = "data_encryption"
    DATA_MASKING = "data_masking"
    DATA_LEAKAGE = "data_leakage_prevention"
    BACKUP = "information_backup"
    REDUNDANCY = "redundancy_of_facilities"
    LOGGING = "logging_and_monitoring"
    NETWORK_SECURITY = "network_security"
    APPLICATION_SECURITY = "application_security"
    SECURE_CODING = "secure_coding"
    SECURITY_TESTING = "security_testing"
    VULNERABILITY_MANAGEMENT = "vulnerability_management"


class ControlStatus(Enum):
    """Implementation status of controls."""

    NOT_IMPLEMENTED = "not_implemented"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    MONITORED = "monitored"
    OPTIMIZED = "optimized"


class ControlPriority(Enum):
    """Priority levels for control implementation."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskLevel(Enum):
    """Risk levels for security assessment."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class ISO27001Control:
    """Represents a single ISO 27001 control."""

    def __init__(
        self,
        control_id: str,
        name: str,
        family: ControlFamily,
        description: str,
        objective: str,
        priority: ControlPriority,
        healthcare_specific: bool = False,
        hipaa_mapping: Optional[List[str]] = None,
        gdpr_mapping: Optional[List[str]] = None,
    ):
        """Initialize ISO 27001 control.

        Args:
            control_id: Unique control identifier (e.g., A.5.1)
            name: Control name
            family: Control family
            description: Control description
            objective: Control objective
            priority: Implementation priority
            healthcare_specific: Whether healthcare-specific
            hipaa_mapping: Related HIPAA requirements
            gdpr_mapping: Related GDPR articles
        """
        self.control_id = control_id
        self.name = name
        self.family = family
        self.description = description
        self.objective = objective
        self.priority = priority
        self.healthcare_specific = healthcare_specific
        self.hipaa_mapping = hipaa_mapping or []
        self.gdpr_mapping = gdpr_mapping or []
        self.status = ControlStatus.NOT_IMPLEMENTED
        self.implementation_date: Optional[datetime] = None
        self.last_review_date: Optional[datetime] = None
        self.next_review_date: Optional[datetime] = None
        self.evidence: List[Dict[str, Any]] = []
        self.gaps: List[Dict[str, Any]] = []
        self.metrics: Dict[str, Any] = {}


class ISO27001Framework:
    """ISO 27001 Information Security Management System framework."""

    def __init__(self) -> None:
        """Initialize ISO 27001 framework."""
        self.controls: Dict[str, ISO27001Control] = {}
        self.risk_register: List[Dict[str, Any]] = []
        self.security_policies: Dict[str, Dict[str, Any]] = {}
        self.audit_logs: List[Dict[str, Any]] = []
        self.incidents: List[Dict[str, Any]] = []
        self.metrics: Dict[str, Any] = {}
        self._initialize_healthcare_controls()

    def _initialize_healthcare_controls(self) -> None:
        """Initialize healthcare-specific ISO 27001 controls."""
        # A.5 - Organizational controls
        self.add_control(
            ISO27001Control(
                control_id="A.5.1",
                name="Policies for information security",
                family=ControlFamily.POLICIES,
                description="Define and approve information security policies for healthcare data",
                objective="Provide management direction and support for information security",
                priority=ControlPriority.CRITICAL,
                healthcare_specific=True,
                hipaa_mapping=["164.316(a)(1)", "164.316(b)(1)"],
                gdpr_mapping=["Article 24", "Article 32"],
            )
        )

        self.add_control(
            ISO27001Control(
                control_id="A.5.2",
                name="Information security roles and responsibilities",
                family=ControlFamily.ROLES,
                description="Define roles for protecting patient data and healthcare systems",
                objective="Ensure clear accountability for information security",
                priority=ControlPriority.HIGH,
                healthcare_specific=True,
                hipaa_mapping=["164.308(a)(2)"],
                gdpr_mapping=["Article 24", "Article 37"],
            )
        )

        self.add_control(
            ISO27001Control(
                control_id="A.5.3",
                name="Information security in risk management",
                family=ControlFamily.MANAGEMENT_RESPONSIBILITIES,
                description="Integration of information security in organizational risk management",
                objective="Ensure information security risks are identified and treated",
                priority=ControlPriority.CRITICAL,
                healthcare_specific=True,
                hipaa_mapping=["164.308(a)(1)(ii)(B)"],
                gdpr_mapping=["Article 32", "Article 35"],
            )
        )

        # A.6 - People controls
        self.add_control(
            ISO27001Control(
                control_id="A.6.1",
                name="Screening",
                family=ControlFamily.SCREENING,
                description="Background verification of personnel handling patient data",
                objective="Ensure trustworthiness of personnel",
                priority=ControlPriority.HIGH,
                healthcare_specific=True,
                hipaa_mapping=["164.308(a)(3)(ii)(B)"],
                gdpr_mapping=["Article 32"],
            )
        )

        self.add_control(
            ISO27001Control(
                control_id="A.6.3",
                name="Information security awareness, education and training",
                family=ControlFamily.AWARENESS,
                description="HIPAA and healthcare security training for all staff",
                objective="Ensure personnel understand security responsibilities",
                priority=ControlPriority.CRITICAL,
                healthcare_specific=True,
                hipaa_mapping=["164.308(a)(5)"],
                gdpr_mapping=["Article 39"],
            )
        )

        # A.7 - Physical controls
        self.add_control(
            ISO27001Control(
                control_id="A.7.1",
                name="Physical security perimeters",
                family=ControlFamily.PHYSICAL_PERIMETERS,
                description="Secure boundaries for healthcare facilities and data centers",
                objective="Prevent unauthorized physical access",
                priority=ControlPriority.HIGH,
                healthcare_specific=True,
                hipaa_mapping=["164.310(a)(1)"],
                gdpr_mapping=["Article 32"],
            )
        )

        self.add_control(
            ISO27001Control(
                control_id="A.7.2",
                name="Physical entry controls",
                family=ControlFamily.PHYSICAL_ACCESS,
                description="Access controls for areas containing patient records",
                objective="Ensure only authorized physical access",
                priority=ControlPriority.HIGH,
                healthcare_specific=True,
                hipaa_mapping=["164.310(a)(2)(ii)"],
                gdpr_mapping=["Article 32"],
            )
        )

        # A.8 - Technological controls
        self.add_control(
            ISO27001Control(
                control_id="A.8.1",
                name="Access control policy",
                family=ControlFamily.ACCESS_CONTROL,
                description="Role-based access control for healthcare systems",
                objective="Limit access based on business and patient care needs",
                priority=ControlPriority.CRITICAL,
                healthcare_specific=True,
                hipaa_mapping=["164.308(a)(4)", "164.312(a)(1)"],
                gdpr_mapping=["Article 32", "Article 25"],
            )
        )

        self.add_control(
            ISO27001Control(
                control_id="A.8.2",
                name="Identity management",
                family=ControlFamily.IDENTITY_MANAGEMENT,
                description="Unique identification for healthcare system users",
                objective="Ensure accountability and traceability",
                priority=ControlPriority.CRITICAL,
                healthcare_specific=True,
                hipaa_mapping=["164.312(a)(2)(i)"],
                gdpr_mapping=["Article 32"],
            )
        )

        self.add_control(
            ISO27001Control(
                control_id="A.8.5",
                name="Secure authentication",
                family=ControlFamily.AUTHENTICATION,
                description="Multi-factor authentication for accessing patient data",
                objective="Verify user identity before granting access",
                priority=ControlPriority.CRITICAL,
                healthcare_specific=True,
                hipaa_mapping=["164.312(d)"],
                gdpr_mapping=["Article 32"],
            )
        )

        self.add_control(
            ISO27001Control(
                control_id="A.8.10",
                name="Information deletion and disposal",
                family=ControlFamily.DATA_MASKING,
                description="Secure disposal of patient data and medical records",
                objective="Prevent unauthorized disclosure from disposed media",
                priority=ControlPriority.HIGH,
                healthcare_specific=True,
                hipaa_mapping=["164.310(d)(2)"],
                gdpr_mapping=["Article 17"],
            )
        )

        self.add_control(
            ISO27001Control(
                control_id="A.8.12",
                name="Data leakage prevention",
                family=ControlFamily.DATA_LEAKAGE,
                description="Prevent unauthorized transmission of patient data",
                objective="Protect against data breaches",
                priority=ControlPriority.CRITICAL,
                healthcare_specific=True,
                hipaa_mapping=["164.312(e)"],
                gdpr_mapping=["Article 32", "Article 33"],
            )
        )

        self.add_control(
            ISO27001Control(
                control_id="A.8.13",
                name="Information backup",
                family=ControlFamily.BACKUP,
                description="Regular backups of patient records and critical systems",
                objective="Ensure data availability and recovery",
                priority=ControlPriority.HIGH,
                healthcare_specific=True,
                hipaa_mapping=["164.308(a)(7)(ii)(A)"],
                gdpr_mapping=["Article 32"],
            )
        )

        self.add_control(
            ISO27001Control(
                control_id="A.8.16",
                name="Monitoring activities",
                family=ControlFamily.LOGGING,
                description="Audit logging of access to patient records",
                objective="Detect and investigate security incidents",
                priority=ControlPriority.CRITICAL,
                healthcare_specific=True,
                hipaa_mapping=["164.308(a)(1)(ii)(D)", "164.312(b)"],
                gdpr_mapping=["Article 32", "Article 33"],
            )
        )

        self.add_control(
            ISO27001Control(
                control_id="A.8.24",
                name="Use of cryptography",
                family=ControlFamily.ENCRYPTION,
                description="Encryption of patient data at rest and in transit",
                objective="Protect confidentiality and integrity of data",
                priority=ControlPriority.CRITICAL,
                healthcare_specific=True,
                hipaa_mapping=["164.312(a)(2)(iv)", "164.312(e)(2)(ii)"],
                gdpr_mapping=["Article 32", "Article 34"],
            )
        )

    def add_control(self, control: ISO27001Control) -> None:
        """Add a control to the framework.

        Args:
            control: ISO 27001 control
        """
        self.controls[control.control_id] = control
        logger.info(
            "Added ISO 27001 control: %s - %s", control.control_id, control.name
        )

    def implement_control(
        self,
        control_id: str,
        implementation_details: Dict[str, Any],
        evidence: List[Dict[str, Any]],
    ) -> bool:
        """Mark a control as implemented with evidence.

        Args:
            control_id: Control identifier
            implementation_details: Details of implementation
            evidence: Evidence of implementation

        Returns:
            Success status
        """
        control = self.controls.get(control_id)
        if not control:
            logger.error("Control %s not found", control_id)
            return False

        control.status = ControlStatus.IMPLEMENTED
        control.implementation_date = datetime.now()
        control.next_review_date = datetime.now() + timedelta(days=365)
        control.evidence.extend(evidence)

        # Log implementation
        self.audit_logs.append(
            {
                "timestamp": datetime.now(),
                "event": "control_implemented",
                "control_id": control_id,
                "details": implementation_details,
            }
        )

        logger.info("Implemented control %s", control_id)
        return True

    def assess_control(self, control_id: str, assessor: str) -> Dict[str, Any]:
        """Assess the effectiveness of a control.

        Args:
            control_id: Control identifier
            assessor: Person performing assessment

        Returns:
            Assessment results
        """
        control = self.controls.get(control_id)
        if not control:
            return {"error": "Control not found"}

        assessment: Dict[str, Any] = {
            "assessment_id": f"ASSESS-{uuid4()}",
            "control_id": control_id,
            "assessor": assessor,
            "date": datetime.now(),
            "status": control.status.value,
            "effectiveness": self._calculate_effectiveness(control),
            "gaps": [],
            "recommendations": [],
        }

        # Check implementation status
        if control.status == ControlStatus.NOT_IMPLEMENTED:
            assessment["gaps"].append(
                {
                    "type": "not_implemented",
                    "description": "Control has not been implemented",
                    "risk_level": control.priority.value,
                }
            )
            assessment["recommendations"].append(
                f"Implement {control.name} as priority {control.priority.value}"
            )

        # Check evidence
        if not control.evidence:
            assessment["gaps"].append(
                {
                    "type": "no_evidence",
                    "description": "No evidence of control implementation",
                    "risk_level": "high",
                }
            )
            assessment["recommendations"].append(
                "Collect and document evidence of control implementation"
            )

        # Check review status
        if control.last_review_date:
            days_since_review = (datetime.now() - control.last_review_date).days
            if days_since_review > 365:
                assessment["gaps"].append(
                    {
                        "type": "overdue_review",
                        "description": f"Control not reviewed for {days_since_review} days",
                        "risk_level": "medium",
                    }
                )
                assessment["recommendations"].append(
                    "Schedule immediate review of control effectiveness"
                )

        control.last_review_date = datetime.now()
        control.gaps = assessment["gaps"]

        return assessment

    def perform_risk_assessment(self, scope: str, assessor: str) -> Dict[str, Any]:
        """Perform information security risk assessment.

        Args:
            scope: Scope of assessment
            assessor: Person performing assessment

        Returns:
            Risk assessment results
        """
        assessment_id = f"RISK-{uuid4()}"

        risks = []

        # Assess risks based on control gaps
        for control_id, control in self.controls.items():
            if control.status != ControlStatus.IMPLEMENTED:
                risk = {
                    "risk_id": f"RISK-{control_id}",
                    "description": f"Lack of {control.name}",
                    "category": control.family.value,
                    "likelihood": self._assess_likelihood(control),
                    "impact": self._assess_impact(control),
                    "risk_level": self._calculate_risk_level(control),
                    "control_id": control_id,
                    "treatment": "implement_control",
                }
                risks.append(risk)

        # Healthcare-specific risks
        healthcare_risks = [
            {
                "risk_id": "RISK-HC-001",
                "description": "Unauthorized access to patient records",
                "category": "access_control",
                "likelihood": "medium",
                "impact": "high",
                "risk_level": RiskLevel.HIGH.value,
                "treatment": "implement_access_controls",
            },
            {
                "risk_id": "RISK-HC-002",
                "description": "Data breach of genetic information",
                "category": "data_protection",
                "likelihood": "low",
                "impact": "critical",
                "risk_level": RiskLevel.HIGH.value,
                "treatment": "encryption_and_access_control",
            },
            {
                "risk_id": "RISK-HC-003",
                "description": "Ransomware attack on healthcare systems",
                "category": "malware",
                "likelihood": "medium",
                "impact": "critical",
                "risk_level": RiskLevel.CRITICAL.value,
                "treatment": "backup_and_incident_response",
            },
        ]

        risks.extend(healthcare_risks)

        # Create risk register entry
        risk_assessment = {
            "assessment_id": assessment_id,
            "scope": scope,
            "assessor": assessor,
            "date": datetime.now(),
            "risks": risks,
            "total_risks": len(risks),
            "critical_risks": len(
                [r for r in risks if r.get("risk_level") == "critical"]
            ),
            "high_risks": len([r for r in risks if r.get("risk_level") == "high"]),
            "recommendations": self._generate_risk_recommendations(risks),
        }

        self.risk_register.append(risk_assessment)

        return risk_assessment

    def create_security_policy(
        self, policy_name: str, policy_type: str, content: Dict[str, Any], approver: str
    ) -> str:
        """Create an information security policy.

        Args:
            policy_name: Name of policy
            policy_type: Type of policy
            content: Policy content
            approver: Policy approver

        Returns:
            Policy ID
        """
        policy_id = f"POL-{uuid4()}"

        policy = {
            "policy_id": policy_id,
            "name": policy_name,
            "type": policy_type,
            "version": "1.0",
            "effective_date": datetime.now(),
            "next_review_date": datetime.now() + timedelta(days=365),
            "approver": approver,
            "content": content,
            "related_controls": [],
            "status": "active",
        }

        # Link to relevant controls
        if policy_type == "access_control":
            policy["related_controls"] = ["A.8.1", "A.8.2", "A.8.5"]
        elif policy_type == "data_protection":
            policy["related_controls"] = ["A.8.10", "A.8.12", "A.8.24"]
        elif policy_type == "incident_response":
            policy["related_controls"] = ["A.5.1", "A.8.16"]

        self.security_policies[policy_id] = policy

        logger.info("Created security policy: %s", policy_name)

        return policy_id

    def record_security_incident(
        self,
        incident_type: str,
        description: str,
        severity: str,
        affected_systems: List[str],
        reporter: str,
    ) -> str:
        """Record a security incident.

        Args:
            incident_type: Type of incident
            description: Incident description
            severity: Incident severity
            affected_systems: Affected systems
            reporter: Person reporting

        Returns:
            Incident ID
        """
        incident_id = f"INC-{uuid4()}"

        incident = {
            "incident_id": incident_id,
            "type": incident_type,
            "description": description,
            "severity": severity,
            "affected_systems": affected_systems,
            "reporter": reporter,
            "reported_date": datetime.now(),
            "status": "open",
            "response_actions": [],
            "lessons_learned": [],
            "related_controls": self._identify_related_controls(incident_type),
        }

        self.incidents.append(incident)

        # Update metrics
        if "incident_count" not in self.metrics:
            self.metrics["incident_count"] = {}
        self.metrics["incident_count"][incident_type] = (
            self.metrics["incident_count"].get(incident_type, 0) + 1
        )

        logger.warning(
            "Security incident recorded: %s - %s", incident_id, incident_type
        )

        return incident_id

    def generate_compliance_report(self, report_type: str = "full") -> Dict[str, Any]:
        """Generate ISO 27001 compliance report.

        Args:
            report_type: Type of report (full, summary, gaps)

        Returns:
            Compliance report
        """
        report: Dict[str, Any] = {
            "report_id": f"RPT-{uuid4()}",
            "type": report_type,
            "generated_date": datetime.now(),
            "framework_version": "ISO 27001:2022",
            "statistics": {
                "total_controls": len(self.controls),
                "implemented": 0,
                "in_progress": 0,
                "not_implemented": 0,
            },
            "compliance_score": 0,
            "gaps": [],
            "strengths": [],
            "recommendations": [],
        }

        # Calculate statistics
        for control in self.controls.values():
            if control.status == ControlStatus.IMPLEMENTED:
                report["statistics"]["implemented"] += 1
            elif control.status == ControlStatus.IN_PROGRESS:
                report["statistics"]["in_progress"] += 1
            else:
                report["statistics"]["not_implemented"] += 1

        # Calculate compliance score
        if report["statistics"]["total_controls"] > 0:
            report["compliance_score"] = (
                report["statistics"]["implemented"]
                / report["statistics"]["total_controls"]
                * 100
            )

        # Identify gaps and strengths
        for control in self.controls.values():
            if control.status == ControlStatus.NOT_IMPLEMENTED:
                report["gaps"].append(
                    {
                        "control_id": control.control_id,
                        "name": control.name,
                        "priority": control.priority.value,
                        "healthcare_specific": control.healthcare_specific,
                    }
                )
            elif control.status == ControlStatus.IMPLEMENTED and control.evidence:
                report["strengths"].append(
                    {
                        "control_id": control.control_id,
                        "name": control.name,
                        "evidence_count": len(control.evidence),
                    }
                )

        # Generate recommendations
        critical_gaps = [
            g for g in report["gaps"] if g["priority"] == ControlPriority.CRITICAL.value
        ]

        if critical_gaps:
            report["recommendations"].append(
                {
                    "priority": "urgent",
                    "action": "Implement critical controls immediately",
                    "controls": [g["control_id"] for g in critical_gaps],
                }
            )

        # Healthcare-specific recommendations
        healthcare_gaps = [g for g in report["gaps"] if g["healthcare_specific"]]

        if healthcare_gaps:
            report["recommendations"].append(
                {
                    "priority": "high",
                    "action": "Address healthcare-specific security requirements",
                    "controls": [g["control_id"] for g in healthcare_gaps],
                }
            )

        return report

    def generate_metrics_dashboard(self) -> Dict[str, Any]:
        """Generate security metrics dashboard.

        Returns:
            Metrics dashboard data
        """
        dashboard = {
            "generated_date": datetime.now(),
            "control_implementation": {
                "implemented": 0,
                "in_progress": 0,
                "not_implemented": 0,
            },
            "risk_profile": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "incident_trends": self.metrics.get("incident_count", {}),
            "compliance_score": 0,
            "upcoming_reviews": [],
            "overdue_actions": [],
        }

        # Control implementation status
        for control in self.controls.values():
            if control.status == ControlStatus.IMPLEMENTED:
                dashboard["control_implementation"]["implemented"] += 1
            elif control.status == ControlStatus.IN_PROGRESS:
                dashboard["control_implementation"]["in_progress"] += 1
            else:
                dashboard["control_implementation"]["not_implemented"] += 1

        # Risk profile from latest assessment
        if self.risk_register:
            latest_assessment = self.risk_register[-1]
            dashboard["risk_profile"]["critical"] = latest_assessment.get(
                "critical_risks", 0
            )
            dashboard["risk_profile"]["high"] = latest_assessment.get("high_risks", 0)

        # Calculate compliance score
        total_controls = len(self.controls)
        if total_controls > 0:
            dashboard["compliance_score"] = (
                dashboard["control_implementation"]["implemented"]
                / total_controls
                * 100
            )

        # Upcoming reviews
        for control in self.controls.values():
            if control.next_review_date:
                days_until_review = (control.next_review_date - datetime.now()).days
                if 0 < days_until_review <= 30:
                    dashboard["upcoming_reviews"].append(
                        {
                            "control_id": control.control_id,
                            "name": control.name,
                            "review_date": control.next_review_date,
                            "days_remaining": days_until_review,
                        }
                    )
                elif days_until_review < 0:
                    dashboard["overdue_actions"].append(
                        {
                            "type": "review",
                            "control_id": control.control_id,
                            "name": control.name,
                            "days_overdue": abs(days_until_review),
                        }
                    )

        return dashboard

    def _calculate_effectiveness(self, control: ISO27001Control) -> float:
        """Calculate control effectiveness score.

        Args:
            control: ISO 27001 control

        Returns:
            Effectiveness score (0-100)
        """
        score = 0.0

        # Implementation status (40%)
        if control.status == ControlStatus.IMPLEMENTED:
            score += 40
        elif control.status == ControlStatus.IN_PROGRESS:
            score += 20

        # Evidence (30%)
        if control.evidence:
            evidence_score = min(30, len(control.evidence) * 10)
            score += evidence_score

        # No gaps (20%)
        if not control.gaps:
            score += 20

        # Recent review (10%)
        if control.last_review_date:
            days_since_review = (datetime.now() - control.last_review_date).days
            if days_since_review <= 90:
                score += 10
            elif days_since_review <= 180:
                score += 5

        return score

    def _assess_likelihood(self, control: ISO27001Control) -> str:
        """Assess likelihood of risk based on control status.

        Args:
            control: ISO 27001 control

        Returns:
            Likelihood level
        """
        if control.status == ControlStatus.NOT_IMPLEMENTED:
            if control.priority == ControlPriority.CRITICAL:
                return "high"
            elif control.priority == ControlPriority.HIGH:
                return "medium"
            else:
                return "low"
        return "low"

    def _assess_impact(self, control: ISO27001Control) -> str:
        """Assess impact of risk based on control.

        Args:
            control: ISO 27001 control

        Returns:
            Impact level
        """
        if control.healthcare_specific:
            if control.priority == ControlPriority.CRITICAL:
                return "critical"
            else:
                return "high"
        else:
            if control.priority == ControlPriority.CRITICAL:
                return "high"
            elif control.priority == ControlPriority.HIGH:
                return "medium"
            else:
                return "low"

    def _calculate_risk_level(self, control: ISO27001Control) -> str:
        """Calculate overall risk level.

        Args:
            control: ISO 27001 control

        Returns:
            Risk level
        """
        likelihood = self._assess_likelihood(control)
        impact = self._assess_impact(control)

        # Risk matrix
        if impact == "critical":
            if likelihood in ["high", "medium"]:
                return RiskLevel.CRITICAL.value
            else:
                return RiskLevel.HIGH.value
        elif impact == "high":
            if likelihood == "high":
                return RiskLevel.HIGH.value
            else:
                return RiskLevel.MEDIUM.value
        else:
            return RiskLevel.LOW.value

    def _generate_risk_recommendations(self, risks: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on risks.

        Args:
            risks: List of identified risks

        Returns:
            List of recommendations
        """
        recommendations = []

        critical_risks = [r for r in risks if r.get("risk_level") == "critical"]
        if critical_risks:
            recommendations.append(
                f"Address {len(critical_risks)} critical risks immediately"
            )

        # Check for common risk categories
        risk_categories: Dict[str, int] = {}
        for risk in risks:
            category = risk.get("category", "unknown")
            risk_categories[category] = risk_categories.get(category, 0) + 1

        for category, count in risk_categories.items():
            if count >= 3:
                recommendations.append(
                    f"Implement comprehensive {category} controls ({count} risks identified)"
                )

        return recommendations

    def _identify_related_controls(self, incident_type: str) -> List[str]:
        """Identify controls related to incident type.

        Args:
            incident_type: Type of incident

        Returns:
            List of related control IDs
        """
        incident_control_mapping = {
            "unauthorized_access": ["A.8.1", "A.8.2", "A.8.5"],
            "data_breach": ["A.8.12", "A.8.24", "A.8.16"],
            "malware": ["A.8.7", "A.8.13", "A.8.16"],
            "physical_breach": ["A.7.1", "A.7.2"],
            "insider_threat": ["A.6.1", "A.6.3", "A.8.16"],
        }

        return incident_control_mapping.get(incident_type, [])


# Export public API
__all__ = [
    "ControlFamily",
    "ControlStatus",
    "ControlPriority",
    "RiskLevel",
    "ISO27001Control",
    "ISO27001Framework",
]
