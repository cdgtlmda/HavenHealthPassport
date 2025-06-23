"""ISO 27001 Risk Assessment Framework for Healthcare.

This module implements a comprehensive risk assessment framework aligned with
ISO 27001:2022 requirements, specifically tailored for healthcare organizations
handling sensitive patient data and requiring HIPAA/GDPR compliance.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, cast
from uuid import uuid4

from src.healthcare.regulatory.iso27001_controls import (
    RiskLevel,
)

logger = logging.getLogger(__name__)


class ThreatCategory(Enum):
    """Categories of security threats."""

    # Technical threats
    MALWARE = "malware_and_ransomware"
    HACKING = "hacking_and_unauthorized_access"
    DDOS = "denial_of_service"
    DATA_BREACH = "data_breach"
    SYSTEM_FAILURE = "system_failure"

    # Human threats
    INSIDER_THREAT = "insider_threat"
    SOCIAL_ENGINEERING = "social_engineering"
    HUMAN_ERROR = "human_error"
    THEFT = "theft_of_equipment"

    # Physical/Environmental threats
    NATURAL_DISASTER = "natural_disaster"
    POWER_FAILURE = "power_failure"
    EQUIPMENT_FAILURE = "equipment_failure"
    ENVIRONMENTAL = "environmental_conditions"

    # Compliance threats
    REGULATORY = "regulatory_non_compliance"
    LEGAL = "legal_liability"
    CONTRACTUAL = "contractual_breach"

    # Healthcare-specific threats
    MEDICAL_IDENTITY_THEFT = "medical_identity_theft"
    PRESCRIPTION_FRAUD = "prescription_fraud"
    PATIENT_SAFETY = "patient_safety_compromise"
    CLINICAL_DISRUPTION = "clinical_service_disruption"


class VulnerabilityType(Enum):
    """Types of vulnerabilities."""

    # Technical vulnerabilities
    SOFTWARE = "unpatched_software"
    MISCONFIGURATION = "system_misconfiguration"
    WEAK_AUTHENTICATION = "weak_authentication"
    ENCRYPTION = "inadequate_encryption"
    NETWORK = "network_vulnerabilities"

    # Process vulnerabilities
    POLICY = "missing_or_inadequate_policies"
    PROCEDURES = "inadequate_procedures"
    TRAINING = "insufficient_training"
    MONITORING = "inadequate_monitoring"

    # Physical vulnerabilities
    PHYSICAL_ACCESS = "weak_physical_access_controls"
    ENVIRONMENTAL = "environmental_controls"

    # Organizational vulnerabilities
    GOVERNANCE = "weak_governance"
    THIRD_PARTY = "third_party_dependencies"
    RESOURCES = "insufficient_resources"

    # Healthcare-specific vulnerabilities
    MEDICAL_DEVICES = "unsecured_medical_devices"
    LEGACY_SYSTEMS = "legacy_healthcare_systems"
    INTEROPERABILITY = "insecure_data_exchange"
    EMERGENCY_ACCESS = "emergency_access_procedures"


class LikelihoodLevel(Enum):
    """Likelihood levels for risk assessment."""

    VERY_HIGH = (5, "very_high", "Almost certain to occur")
    HIGH = (4, "high", "Likely to occur")
    MEDIUM = (3, "medium", "Possible to occur")
    LOW = (2, "low", "Unlikely to occur")
    VERY_LOW = (1, "very_low", "Rare to occur")

    def __init__(self, score: int, level_name: str, description: str):
        """Initialize likelihood level with score and description."""
        self.score = score
        self.level_name = level_name
        self.description = description


class ImpactLevel(Enum):
    """Impact levels for risk assessment."""

    CATASTROPHIC = (5, "catastrophic", "Complete business failure, patient harm")
    MAJOR = (4, "major", "Significant disruption, regulatory penalties")
    MODERATE = (3, "moderate", "Noticeable impact, recoverable")
    MINOR = (2, "minor", "Limited impact, quickly resolved")
    NEGLIGIBLE = (1, "negligible", "Minimal to no impact")

    def __init__(self, score: int, level_name: str, description: str):
        """Initialize likelihood level with score and description."""
        self.score = score
        self.level_name = level_name
        self.description = description


class RiskTreatment(Enum):
    """Risk treatment options."""

    MITIGATE = "mitigate"  # Reduce risk through controls
    ACCEPT = "accept"  # Accept risk as-is
    TRANSFER = "transfer"  # Transfer risk (insurance, outsourcing)
    AVOID = "avoid"  # Eliminate risk source


class RiskAssessment:
    """Represents a single risk assessment."""

    def __init__(
        self,
        assessment_id: str,
        asset_id: str,
        asset_name: str,
        threat: ThreatCategory,
        vulnerability: VulnerabilityType,
        likelihood: LikelihoodLevel,
        impact: ImpactLevel,
        assessor: str,
        assessment_date: datetime,
    ):
        """Initialize risk assessment.

        Args:
            assessment_id: Unique assessment ID
            asset_id: ID of asset being assessed
            asset_name: Name of asset
            threat: Threat category
            vulnerability: Vulnerability type
            likelihood: Likelihood level
            impact: Impact level
            assessor: Person performing assessment
            assessment_date: Date of assessment
        """
        self.assessment_id = assessment_id
        self.asset_id = asset_id
        self.asset_name = asset_name
        self.threat = threat
        self.vulnerability = vulnerability
        self.likelihood = likelihood
        self.impact = impact
        self.assessor = assessor
        self.assessment_date = assessment_date

        # Calculate risk score
        self.risk_score = self.likelihood.score * self.impact.score
        self.risk_level = self._calculate_risk_level()

        # Risk treatment
        self.treatment_option: Optional[RiskTreatment] = None
        self.treatment_plan: Optional[Dict[str, Any]] = None
        self.residual_risk_score: Optional[int] = None
        self.treatment_status: str = "pending"

        # Healthcare-specific factors
        self.patient_impact: bool = False
        self.phi_exposure: bool = False
        self.clinical_impact: bool = False
        self.regulatory_impact: bool = False

        # Related controls
        self.mitigating_controls: List[str] = []
        self.recommended_controls: List[str] = []

    def _calculate_risk_level(self) -> RiskLevel:
        """Calculate risk level based on score.

        Returns:
            Risk level
        """
        if self.risk_score >= 20:
            return RiskLevel.CRITICAL
        elif self.risk_score >= 15:
            return RiskLevel.HIGH
        elif self.risk_score >= 10:
            return RiskLevel.MEDIUM
        elif self.risk_score >= 5:
            return RiskLevel.LOW
        else:
            return RiskLevel.NEGLIGIBLE

    def apply_treatment(
        self, treatment: RiskTreatment, plan: Dict[str, Any], expected_reduction: float
    ) -> None:
        """Apply risk treatment.

        Args:
            treatment: Treatment option
            plan: Treatment implementation plan
            expected_reduction: Expected risk reduction (0-1)
        """
        self.treatment_option = treatment
        self.treatment_plan = plan

        # Calculate residual risk
        if treatment == RiskTreatment.MITIGATE:
            self.residual_risk_score = int(self.risk_score * (1 - expected_reduction))
        elif treatment == RiskTreatment.TRANSFER:
            self.residual_risk_score = int(self.risk_score * 0.3)
        elif treatment == RiskTreatment.AVOID:
            self.residual_risk_score = 0
        else:  # ACCEPT
            self.residual_risk_score = self.risk_score

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "assessment_id": self.assessment_id,
            "asset_id": self.asset_id,
            "asset_name": self.asset_name,
            "threat": self.threat.value,
            "vulnerability": self.vulnerability.value,
            "likelihood": {
                "level": self.likelihood.level_name,
                "score": self.likelihood.score,
                "description": self.likelihood.description,
            },
            "impact": {
                "level": self.impact.level_name,
                "score": self.impact.score,
                "description": self.impact.description,
            },
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value,
            "assessor": self.assessor,
            "assessment_date": self.assessment_date.isoformat(),
            "treatment": {
                "option": (
                    self.treatment_option.value if self.treatment_option else None
                ),
                "plan": self.treatment_plan,
                "residual_risk": self.residual_risk_score,
                "status": self.treatment_status,
            },
            "healthcare_factors": {
                "patient_impact": self.patient_impact,
                "phi_exposure": self.phi_exposure,
                "clinical_impact": self.clinical_impact,
                "regulatory_impact": self.regulatory_impact,
            },
            "controls": {
                "mitigating": self.mitigating_controls,
                "recommended": self.recommended_controls,
            },
        }


class RiskAssessmentFramework:
    """ISO 27001 Risk Assessment Framework for Healthcare."""

    def __init__(self) -> None:
        """Initialize risk assessment framework."""
        self.assessments: Dict[str, RiskAssessment] = {}
        self.assets: Dict[str, Dict[str, Any]] = {}
        self.risk_register: List[Dict[str, Any]] = []
        self.risk_criteria: Dict[str, Any] = self._initialize_risk_criteria()
        self.treatment_plans: Dict[str, Dict[str, Any]] = {}
        self.risk_metrics: Dict[str, Any] = {}

    def _initialize_risk_criteria(self) -> Dict[str, Any]:
        """Initialize risk acceptance criteria.

        Returns:
            Risk criteria configuration
        """
        return {
            "risk_appetite": {
                "patient_safety": RiskLevel.LOW,
                "data_breach": RiskLevel.LOW,
                "regulatory": RiskLevel.MEDIUM,
                "operational": RiskLevel.MEDIUM,
                "financial": RiskLevel.HIGH,
            },
            "acceptance_thresholds": {
                RiskLevel.CRITICAL: False,  # Never accept
                RiskLevel.HIGH: False,  # Requires CISO approval
                RiskLevel.MEDIUM: True,  # Department head approval
                RiskLevel.LOW: True,  # Team lead approval
                RiskLevel.NEGLIGIBLE: True,  # Auto-accept
            },
            "review_frequency": {
                RiskLevel.CRITICAL: 30,  # Days
                RiskLevel.HIGH: 90,
                RiskLevel.MEDIUM: 180,
                RiskLevel.LOW: 365,
                RiskLevel.NEGLIGIBLE: 365,
            },
        }

    def register_asset(
        self,
        asset_id: str,
        asset_name: str,
        asset_type: str,
        owner: str,
        classification: str,
        healthcare_data: bool,
        critical_asset: bool,
    ) -> bool:
        """Register asset for risk assessment.

        Args:
            asset_id: Unique asset ID
            asset_name: Asset name
            asset_type: Type of asset
            owner: Asset owner
            classification: Data classification
            healthcare_data: Contains healthcare data
            critical_asset: Critical to operations

        Returns:
            Success status
        """
        self.assets[asset_id] = {
            "asset_id": asset_id,
            "name": asset_name,
            "type": asset_type,
            "owner": owner,
            "classification": classification,
            "healthcare_data": healthcare_data,
            "critical_asset": critical_asset,
            "registered_date": datetime.now(),
            "risk_assessments": [],
            "current_risk_level": None,
        }

        logger.info("Registered asset: %s - %s", asset_id, asset_name)
        return True

    def conduct_risk_assessment(
        self,
        asset_id: str,
        threat: ThreatCategory,
        vulnerability: VulnerabilityType,
        likelihood: LikelihoodLevel,
        impact: ImpactLevel,
        assessor: str,
        additional_factors: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Conduct risk assessment for an asset.

        Args:
            asset_id: Asset ID
            threat: Threat category
            vulnerability: Vulnerability type
            likelihood: Likelihood level
            impact: Impact level
            assessor: Person conducting assessment
            additional_factors: Additional assessment factors

        Returns:
            Assessment ID
        """
        if asset_id not in self.assets:
            raise ValueError(f"Asset {asset_id} not registered")

        asset = self.assets[asset_id]
        assessment_id = f"RA-{uuid4().hex[:8]}"

        # Create assessment
        assessment = RiskAssessment(
            assessment_id=assessment_id,
            asset_id=asset_id,
            asset_name=asset["name"],
            threat=threat,
            vulnerability=vulnerability,
            likelihood=likelihood,
            impact=impact,
            assessor=assessor,
            assessment_date=datetime.now(),
        )

        # Apply healthcare-specific factors
        if additional_factors:
            assessment.patient_impact = additional_factors.get("patient_impact", False)
            assessment.phi_exposure = additional_factors.get("phi_exposure", False)
            assessment.clinical_impact = additional_factors.get(
                "clinical_impact", False
            )
            assessment.regulatory_impact = additional_factors.get(
                "regulatory_impact", False
            )

        # Adjust risk based on healthcare factors
        if asset["healthcare_data"]:
            if assessment.phi_exposure:
                # Increase impact for PHI exposure
                assessment.risk_score = int(assessment.risk_score * 1.5)
            if assessment.patient_impact:
                # Critical priority for patient safety
                assessment.risk_score = max(assessment.risk_score, 20)

        # Identify relevant controls
        assessment.recommended_controls = self._identify_controls(threat, vulnerability)

        # Store assessment
        self.assessments[assessment_id] = assessment
        asset["risk_assessments"].append(assessment_id)

        # Update risk register
        self._update_risk_register(assessment)

        # Update asset risk level
        self._update_asset_risk_level(asset_id)

        logger.info(
            "Conducted risk assessment %s for asset %s: Risk Level = %s",
            assessment_id,
            asset_id,
            assessment.risk_level.value,
        )

        return assessment_id

    def perform_bulk_assessment(
        self, asset_type: str, scenarios: List[Dict[str, Any]], assessor: str
    ) -> List[str]:
        """Perform bulk risk assessment for similar assets.

        Args:
            asset_type: Type of assets to assess
            scenarios: Risk scenarios to evaluate
            assessor: Person conducting assessment

        Returns:
            List of assessment IDs
        """
        assessment_ids = []

        # Find assets of specified type
        target_assets = [
            asset for asset in self.assets.values() if asset["type"] == asset_type
        ]

        for asset in target_assets:
            for scenario in scenarios:
                try:
                    assessment_id = self.conduct_risk_assessment(
                        asset_id=asset["asset_id"],
                        threat=ThreatCategory(scenario["threat"]),
                        vulnerability=VulnerabilityType(scenario["vulnerability"]),
                        likelihood=LikelihoodLevel[scenario["likelihood"]],
                        impact=ImpactLevel[scenario["impact"]],
                        assessor=assessor,
                        additional_factors=scenario.get("factors", {}),
                    )
                    assessment_ids.append(assessment_id)
                except (ValueError, KeyError, AttributeError) as e:
                    logger.error(
                        "Failed to assess %s for scenario %s: %s",
                        asset["asset_id"],
                        scenario,
                        e,
                    )

        return assessment_ids

    def develop_treatment_plan(
        self,
        assessment_id: str,
        treatment_option: RiskTreatment,
        controls: List[str],
        timeline_days: int,
        responsible_party: str,
        budget: Optional[float] = None,
    ) -> str:
        """Develop risk treatment plan.

        Args:
            assessment_id: Risk assessment ID
            treatment_option: Selected treatment option
            controls: Controls to implement
            timeline_days: Implementation timeline
            responsible_party: Responsible for implementation
            budget: Budget allocation

        Returns:
            Treatment plan ID
        """
        if assessment_id not in self.assessments:
            raise ValueError(f"Assessment {assessment_id} not found")

        assessment = self.assessments[assessment_id]
        plan_id = f"RTP-{uuid4().hex[:8]}"

        # Create treatment plan
        plan = {
            "plan_id": plan_id,
            "assessment_id": assessment_id,
            "treatment_option": treatment_option,
            "controls": controls,
            "timeline": {
                "start_date": datetime.now(),
                "end_date": datetime.now() + timedelta(days=timeline_days),
                "duration_days": timeline_days,
            },
            "responsible_party": responsible_party,
            "budget": budget,
            "status": "planned",
            "milestones": self._create_treatment_milestones(controls, timeline_days),
            "expected_risk_reduction": self._estimate_risk_reduction(
                assessment, controls
            ),
        }

        # Apply treatment to assessment
        assessment.apply_treatment(
            treatment_option, plan, cast(float, plan["expected_risk_reduction"])
        )

        # Store plan
        self.treatment_plans[plan_id] = plan

        logger.info(
            "Created treatment plan %s for assessment %s", plan_id, assessment_id
        )

        return plan_id

    def execute_treatment_plan(
        self, plan_id: str, implementation_evidence: List[Dict[str, Any]]
    ) -> bool:
        """Execute risk treatment plan.

        Args:
            plan_id: Treatment plan ID
            implementation_evidence: Evidence of implementation

        Returns:
            Success status
        """
        if plan_id not in self.treatment_plans:
            return False

        plan = self.treatment_plans[plan_id]
        assessment = self.assessments.get(plan["assessment_id"])

        if not assessment:
            return False

        # Update plan status
        plan["status"] = "implemented"
        plan["implementation_date"] = datetime.now()
        plan["evidence"] = implementation_evidence

        # Update assessment status
        assessment.treatment_status = "implemented"

        # Update risk register
        self._update_risk_register(assessment)

        logger.info("Executed treatment plan %s", plan_id)

        return True

    def generate_risk_report(
        self, report_type: str = "executive", asset_filter: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate risk assessment report.

        Args:
            report_type: Type of report (executive, detailed, technical)
            asset_filter: Filter by specific assets

        Returns:
            Risk report
        """
        report = {
            "report_id": f"RISK-RPT-{uuid4().hex[:8]}",
            "generated_date": datetime.now(),
            "report_type": report_type,
            "summary": self._generate_risk_summary(),
            "risk_distribution": self._calculate_risk_distribution(),
            "top_risks": self._identify_top_risks(10),
            "treatment_status": self._summarize_treatment_status(),
            "healthcare_specific": self._analyze_healthcare_risks(),
            "recommendations": self._generate_recommendations(),
        }

        if report_type == "detailed":
            report["assessments"] = [
                assessment.to_dict()
                for assessment in self.assessments.values()
                if not asset_filter or assessment.asset_id in asset_filter
            ]

        elif report_type == "technical":
            report["vulnerability_analysis"] = self._analyze_vulnerabilities()
            report["threat_landscape"] = self._analyze_threats()
            report["control_effectiveness"] = self._analyze_control_effectiveness()

        return report

    def calculate_risk_metrics(self) -> Dict[str, Any]:
        """Calculate risk metrics for dashboard.

        Returns:
            Risk metrics
        """
        total_assessments = len(self.assessments)

        if total_assessments == 0:
            return {
                "total_risks": 0,
                "average_risk_score": 0,
                "critical_risks": 0,
                "treated_risks": 0,
                "risk_trend": "stable",
            }

        metrics = {
            "total_risks": total_assessments,
            "average_risk_score": sum(a.risk_score for a in self.assessments.values())
            / total_assessments,
            "critical_risks": len(
                [
                    a
                    for a in self.assessments.values()
                    if a.risk_level == RiskLevel.CRITICAL
                ]
            ),
            "high_risks": len(
                [a for a in self.assessments.values() if a.risk_level == RiskLevel.HIGH]
            ),
            "treated_risks": len(
                [
                    a
                    for a in self.assessments.values()
                    if a.treatment_status == "implemented"
                ]
            ),
            "untreated_risks": len(
                [
                    a
                    for a in self.assessments.values()
                    if a.treatment_status == "pending"
                ]
            ),
            "healthcare_risks": len(
                [
                    a
                    for a in self.assessments.values()
                    if a.patient_impact or a.phi_exposure
                ]
            ),
            "compliance_risks": len(
                [a for a in self.assessments.values() if a.regulatory_impact]
            ),
            "risk_trend": self._calculate_risk_trend(),
        }

        self.risk_metrics = metrics
        return metrics

    def _identify_controls(
        self, threat: ThreatCategory, vulnerability: VulnerabilityType
    ) -> List[str]:
        """Identify relevant controls for threat/vulnerability.

        Args:
            threat: Threat category
            vulnerability: Vulnerability type

        Returns:
            List of control IDs
        """
        control_mapping = {
            # Threat-based controls
            ThreatCategory.MALWARE: ["A.8.7", "A.8.8", "A.12.2"],
            ThreatCategory.HACKING: ["A.8.2", "A.8.3", "A.8.5"],
            ThreatCategory.DATA_BREACH: ["A.8.10", "A.8.11", "A.8.12"],
            ThreatCategory.INSIDER_THREAT: ["A.6.1", "A.8.2", "A.8.4"],
            ThreatCategory.SOCIAL_ENGINEERING: ["A.6.3", "A.8.23"],
            # Vulnerability-based controls
            VulnerabilityType.WEAK_AUTHENTICATION: ["A.8.5", "A.8.6"],
            VulnerabilityType.ENCRYPTION: ["A.8.24", "A.8.25"],
            VulnerabilityType.TRAINING: ["A.6.3", "A.6.6"],
            VulnerabilityType.MONITORING: ["A.8.15", "A.8.16"],
            VulnerabilityType.MEDICAL_DEVICES: ["A.8.32", "A.8.33", "A.8.34"],
        }

        controls = []

        # Add threat-specific controls
        if threat in control_mapping:
            controls.extend(control_mapping[threat])

        # Add vulnerability-specific controls
        if vulnerability in control_mapping:
            controls.extend(control_mapping[vulnerability])

        # Remove duplicates
        return list(set(controls))

    def _update_risk_register(self, assessment: RiskAssessment) -> None:
        """Update risk register with assessment.

        Args:
            assessment: Risk assessment
        """
        # Check if risk already in register
        existing_index = None
        for i, risk in enumerate(self.risk_register):
            if risk["assessment_id"] == assessment.assessment_id:
                existing_index = i
                break

        risk_entry = {
            "assessment_id": assessment.assessment_id,
            "asset_id": assessment.asset_id,
            "asset_name": assessment.asset_name,
            "risk_description": f"{assessment.threat.value} exploiting {assessment.vulnerability.value}",
            "risk_level": assessment.risk_level.value,
            "risk_score": assessment.risk_score,
            "treatment_status": assessment.treatment_status,
            "residual_risk": assessment.residual_risk_score,
            "last_updated": datetime.now(),
            "next_review": datetime.now()
            + timedelta(
                days=self.risk_criteria["review_frequency"][assessment.risk_level]
            ),
        }

        if existing_index is not None:
            self.risk_register[existing_index] = risk_entry
        else:
            self.risk_register.append(risk_entry)

    def _update_asset_risk_level(self, asset_id: str) -> None:
        """Update overall risk level for asset.

        Args:
            asset_id: Asset ID
        """
        asset = self.assets.get(asset_id)
        if not asset:
            return

        # Get all assessments for asset
        asset_assessments = [
            self.assessments[aid]
            for aid in asset["risk_assessments"]
            if aid in self.assessments
        ]

        if not asset_assessments:
            asset["current_risk_level"] = None
            return

        # Use highest risk level
        risk_levels = [a.risk_level for a in asset_assessments]
        priority_order = [
            RiskLevel.CRITICAL,
            RiskLevel.HIGH,
            RiskLevel.MEDIUM,
            RiskLevel.LOW,
            RiskLevel.NEGLIGIBLE,
        ]

        for level in priority_order:
            if level in risk_levels:
                asset["current_risk_level"] = level.value
                break

    def _create_treatment_milestones(
        self, controls: List[str], timeline_days: int
    ) -> List[Dict[str, Any]]:
        """Create treatment implementation milestones.

        Args:
            controls: Controls to implement
            timeline_days: Total timeline

        Returns:
            List of milestones
        """
        milestones = []

        # Planning phase (10% of timeline)
        milestones.append(
            {
                "milestone": "Treatment planning complete",
                "target_days": int(timeline_days * 0.1),
                "deliverables": ["Implementation plan", "Resource allocation"],
            }
        )

        # Implementation phase (60% of timeline)
        controls_per_milestone = max(1, len(controls) // 3)
        for i in range(0, len(controls), controls_per_milestone):
            milestone_controls = controls[i : i + controls_per_milestone]
            milestones.append(
                {
                    "milestone": f"Implement controls {', '.join(milestone_controls)}",
                    "target_days": int(
                        timeline_days * (0.3 + 0.2 * (i // controls_per_milestone))
                    ),
                    "deliverables": [
                        f"Control {c} operational" for c in milestone_controls
                    ],
                }
            )

        # Testing phase (20% of timeline)
        milestones.append(
            {
                "milestone": "Testing and validation complete",
                "target_days": int(timeline_days * 0.8),
                "deliverables": ["Test results", "Effectiveness measurements"],
            }
        )

        # Closure phase (10% of timeline)
        milestones.append(
            {
                "milestone": "Treatment implementation complete",
                "target_days": timeline_days,
                "deliverables": ["Final report", "Residual risk acceptance"],
            }
        )

        return milestones

    def _estimate_risk_reduction(
        self, assessment: RiskAssessment, controls: List[str]
    ) -> float:
        """Estimate risk reduction from controls.

        Args:
            assessment: Risk assessment
            controls: Controls to implement

        Returns:
            Expected risk reduction (0-1)
        """
        # Base reduction per control
        base_reduction = 0.15

        # Adjust based on control relevance
        relevant_controls = assessment.recommended_controls
        relevance_factor = (
            len(set(controls).intersection(set(relevant_controls))) / len(controls)
            if controls
            else 0
        )

        # Calculate total reduction (with diminishing returns)
        total_reduction = 0.0
        for i, control in enumerate(controls):
            control_reduction = base_reduction * (0.8**i)  # Diminishing returns
            if control in relevant_controls:
                control_reduction *= 1 + relevance_factor
            total_reduction += control_reduction

        # Cap at 90% reduction
        return min(0.9, total_reduction)

    def _generate_risk_summary(self) -> Dict[str, Any]:
        """Generate executive risk summary.

        Returns:
            Risk summary
        """
        total_risks = len(self.assessments)

        if total_risks == 0:
            return {"message": "No risks assessed"}

        return {
            "total_risks_identified": total_risks,
            "critical_risks": len(
                [
                    a
                    for a in self.assessments.values()
                    if a.risk_level == RiskLevel.CRITICAL
                ]
            ),
            "high_risks": len(
                [a for a in self.assessments.values() if a.risk_level == RiskLevel.HIGH]
            ),
            "risks_with_treatment": len(
                [a for a in self.assessments.values() if a.treatment_option is not None]
            ),
            "average_risk_score": sum(a.risk_score for a in self.assessments.values())
            / total_risks,
            "healthcare_specific_risks": len(
                [
                    a
                    for a in self.assessments.values()
                    if a.patient_impact or a.phi_exposure
                ]
            ),
        }

    def _calculate_risk_distribution(self) -> Dict[str, Dict[str, int]]:
        """Calculate risk distribution by category.

        Returns:
            Risk distribution
        """
        distribution: Dict[str, Dict[str, int]] = {
            "by_level": {},
            "by_threat": {},
            "by_vulnerability": {},
            "by_treatment": {},
        }

        for assessment in self.assessments.values():
            # By risk level
            level = assessment.risk_level.value
            distribution["by_level"][level] = distribution["by_level"].get(level, 0) + 1

            # By threat
            threat = assessment.threat.value
            distribution["by_threat"][threat] = (
                distribution["by_threat"].get(threat, 0) + 1
            )

            # By vulnerability
            vuln = assessment.vulnerability.value
            distribution["by_vulnerability"][vuln] = (
                distribution["by_vulnerability"].get(vuln, 0) + 1
            )

            # By treatment
            treatment = (
                assessment.treatment_option.value
                if assessment.treatment_option
                else "none"
            )
            distribution["by_treatment"][treatment] = (
                distribution["by_treatment"].get(treatment, 0) + 1
            )

        return distribution

    def _identify_top_risks(self, count: int = 10) -> List[Dict[str, Any]]:
        """Identify top risks by score.

        Args:
            count: Number of top risks

        Returns:
            Top risks
        """
        sorted_assessments = sorted(
            self.assessments.values(), key=lambda a: a.risk_score, reverse=True
        )

        top_risks = []
        for assessment in sorted_assessments[:count]:
            top_risks.append(
                {
                    "assessment_id": assessment.assessment_id,
                    "asset_name": assessment.asset_name,
                    "risk_description": f"{assessment.threat.value} - {assessment.vulnerability.value}",
                    "risk_score": assessment.risk_score,
                    "risk_level": assessment.risk_level.value,
                    "treatment_status": assessment.treatment_status,
                    "healthcare_impact": assessment.patient_impact
                    or assessment.phi_exposure,
                }
            )

        return top_risks

    def _summarize_treatment_status(self) -> Dict[str, Any]:
        """Summarize risk treatment status.

        Returns:
            Treatment status summary
        """
        return {
            "total_treatment_plans": len(self.treatment_plans),
            "plans_by_status": {
                "planned": len(
                    [
                        p
                        for p in self.treatment_plans.values()
                        if p["status"] == "planned"
                    ]
                ),
                "in_progress": len(
                    [
                        p
                        for p in self.treatment_plans.values()
                        if p["status"] == "in_progress"
                    ]
                ),
                "implemented": len(
                    [
                        p
                        for p in self.treatment_plans.values()
                        if p["status"] == "implemented"
                    ]
                ),
            },
            "average_reduction": (
                sum(p["expected_risk_reduction"] for p in self.treatment_plans.values())
                / len(self.treatment_plans)
                if self.treatment_plans
                else 0
            ),
            "total_budget": sum(
                p.get("budget", 0) for p in self.treatment_plans.values()
            ),
        }

    def _analyze_healthcare_risks(self) -> Dict[str, Any]:
        """Analyze healthcare-specific risks.

        Returns:
            Healthcare risk analysis
        """
        healthcare_assessments = [
            a
            for a in self.assessments.values()
            if a.patient_impact or a.phi_exposure or a.clinical_impact
        ]

        return {
            "total_healthcare_risks": len(healthcare_assessments),
            "patient_safety_risks": len(
                [a for a in healthcare_assessments if a.patient_impact]
            ),
            "phi_exposure_risks": len(
                [a for a in healthcare_assessments if a.phi_exposure]
            ),
            "clinical_disruption_risks": len(
                [a for a in healthcare_assessments if a.clinical_impact]
            ),
            "regulatory_compliance_risks": len(
                [a for a in healthcare_assessments if a.regulatory_impact]
            ),
            "priority_areas": self._identify_healthcare_priorities(
                healthcare_assessments
            ),
        }

    def _identify_healthcare_priorities(
        self, assessments: List[RiskAssessment]
    ) -> List[str]:
        """Identify healthcare priority areas.

        Args:
            assessments: Healthcare risk assessments

        Returns:
            Priority areas
        """
        priorities = []

        # Check for critical patient safety risks
        patient_risks = [
            a
            for a in assessments
            if a.patient_impact and a.risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]
        ]
        if patient_risks:
            priorities.append("Immediate attention required for patient safety risks")

        # Check for PHI exposure risks
        phi_risks = [
            a for a in assessments if a.phi_exposure and a.treatment_status == "pending"
        ]
        if phi_risks:
            priorities.append("PHI protection controls need implementation")

        # Check for clinical disruption risks
        clinical_risks = [a for a in assessments if a.clinical_impact]
        if clinical_risks:
            priorities.append("Clinical continuity planning required")

        return priorities

    def _generate_recommendations(self) -> List[Dict[str, Any]]:
        """Generate risk treatment recommendations.

        Returns:
            Recommendations
        """
        recommendations = []

        # Critical risks without treatment
        critical_untreated = [
            a
            for a in self.assessments.values()
            if a.risk_level == RiskLevel.CRITICAL and a.treatment_status == "pending"
        ]

        if critical_untreated:
            recommendations.append(
                {
                    "priority": "urgent",
                    "recommendation": "Develop treatment plans for critical risks",
                    "affected_assets": [a.asset_name for a in critical_untreated[:5]],
                    "expected_impact": "Significant risk reduction",
                }
            )

        # Healthcare-specific recommendations
        healthcare_gaps = [
            a
            for a in self.assessments.values()
            if (a.patient_impact or a.phi_exposure) and not a.mitigating_controls
        ]

        if healthcare_gaps:
            recommendations.append(
                {
                    "priority": "high",
                    "recommendation": "Implement healthcare-specific security controls",
                    "focus_areas": ["Encryption", "Access control", "Audit logging"],
                    "compliance_impact": "HIPAA and GDPR requirements",
                }
            )

        # Control effectiveness
        ineffective_treatments = [
            p
            for p in self.treatment_plans.values()
            if p["expected_risk_reduction"] < 0.3
        ]

        if ineffective_treatments:
            recommendations.append(
                {
                    "priority": "medium",
                    "recommendation": "Review and enhance risk treatment effectiveness",
                    "treatment_plans": [
                        p["plan_id"] for p in ineffective_treatments[:3]
                    ],
                    "suggested_action": "Consider additional or alternative controls",
                }
            )

        return recommendations

    def _analyze_vulnerabilities(self) -> Dict[str, Any]:
        """Analyze vulnerability patterns.

        Returns:
            Vulnerability analysis
        """
        vuln_count: Dict[str, int] = {}
        vuln_risk: Dict[str, List[float]] = {}

        for assessment in self.assessments.values():
            vuln = assessment.vulnerability.value
            vuln_count[vuln] = vuln_count.get(vuln, 0) + 1

            if vuln not in vuln_risk:
                vuln_risk[vuln] = []
            vuln_risk[vuln].append(assessment.risk_score)

        # Calculate average risk per vulnerability
        vuln_avg_risk = {
            vuln: sum(scores) / len(scores) for vuln, scores in vuln_risk.items()
        }

        # Sort by frequency and risk
        most_common = sorted(vuln_count.items(), key=lambda x: x[1], reverse=True)[:5]
        highest_risk = sorted(vuln_avg_risk.items(), key=lambda x: x[1], reverse=True)[
            :5
        ]

        return {
            "most_common_vulnerabilities": most_common,
            "highest_risk_vulnerabilities": highest_risk,
            "vulnerability_trends": self._calculate_vulnerability_trends(),
        }

    def _analyze_threats(self) -> Dict[str, Any]:
        """Analyze threat landscape.

        Returns:
            Threat analysis
        """
        threat_count: Dict[str, int] = {}
        threat_impact: Dict[str, List[int]] = {}

        for assessment in self.assessments.values():
            threat = assessment.threat.value
            threat_count[threat] = threat_count.get(threat, 0) + 1

            if threat not in threat_impact:
                threat_impact[threat] = []
            threat_impact[threat].append(assessment.impact.score)

        # Calculate average impact per threat
        threat_avg_impact = {
            threat: sum(impacts) / len(impacts)
            for threat, impacts in threat_impact.items()
        }

        return {
            "active_threats": len(threat_count),
            "most_frequent_threats": sorted(
                threat_count.items(), key=lambda x: x[1], reverse=True
            )[:5],
            "highest_impact_threats": sorted(
                threat_avg_impact.items(), key=lambda x: x[1], reverse=True
            )[:5],
            "emerging_threats": self._identify_emerging_threats(),
        }

    def _analyze_control_effectiveness(self) -> Dict[str, Any]:
        """Analyze control effectiveness.

        Returns:
            Control effectiveness analysis
        """
        control_usage: Dict[str, int] = {}
        control_reduction: Dict[str, List[float]] = {}

        for plan in self.treatment_plans.values():
            for control in plan["controls"]:
                control_usage[control] = control_usage.get(control, 0) + 1

                if control not in control_reduction:
                    control_reduction[control] = []
                control_reduction[control].append(plan["expected_risk_reduction"])

        # Calculate average effectiveness
        control_effectiveness = {
            control: sum(reductions) / len(reductions)
            for control, reductions in control_reduction.items()
        }

        return {
            "controls_in_use": len(control_usage),
            "most_used_controls": sorted(
                control_usage.items(), key=lambda x: x[1], reverse=True
            )[:10],
            "most_effective_controls": sorted(
                control_effectiveness.items(), key=lambda x: x[1], reverse=True
            )[:10],
            "control_coverage": self._calculate_control_coverage(),
        }

    def _calculate_risk_trend(self) -> str:
        """Calculate overall risk trend.

        Returns:
            Risk trend (increasing, stable, decreasing)
        """
        # Simple implementation - would be more sophisticated in practice
        if not self.risk_register:
            return "stable"

        recent_risks = [
            r
            for r in self.risk_register
            if r["last_updated"] > datetime.now() - timedelta(days=30)
        ]

        if not recent_risks:
            return "stable"

        # Compare average risk scores
        recent_avg = sum(r["risk_score"] for r in recent_risks) / len(recent_risks)
        overall_avg = sum(r["risk_score"] for r in self.risk_register) / len(
            self.risk_register
        )

        if recent_avg > overall_avg * 1.1:
            return "increasing"
        elif recent_avg < overall_avg * 0.9:
            return "decreasing"
        else:
            return "stable"

    def _calculate_vulnerability_trends(self) -> List[str]:
        """Calculate vulnerability trends.

        Returns:
            Vulnerability trends
        """
        # Placeholder - would analyze historical data
        return [
            "Increase in cloud infrastructure vulnerabilities",
            "Decrease in patching delays",
            "Emerging IoT medical device vulnerabilities",
        ]

    def _identify_emerging_threats(self) -> List[str]:
        """Identify emerging threats.

        Returns:
            Emerging threats
        """
        # Placeholder - would use threat intelligence
        return [
            "Ransomware targeting healthcare providers",
            "Supply chain attacks on medical device vendors",
            "AI-powered social engineering attempts",
        ]

    def _calculate_control_coverage(self) -> float:
        """Calculate control coverage percentage.

        Returns:
            Control coverage (0-100)
        """
        # Get all recommended controls
        all_recommended = set()
        for assessment in self.assessments.values():
            all_recommended.update(assessment.recommended_controls)

        # Get implemented controls
        implemented = set()
        for plan in self.treatment_plans.values():
            if plan["status"] == "implemented":
                implemented.update(plan["controls"])

        if not all_recommended:
            return 100.0

        return (len(implemented) / len(all_recommended)) * 100


# Export public API
__all__ = [
    "RiskAssessmentFramework",
    "RiskAssessment",
    "ThreatCategory",
    "VulnerabilityType",
    "LikelihoodLevel",
    "ImpactLevel",
    "RiskTreatment",
]
