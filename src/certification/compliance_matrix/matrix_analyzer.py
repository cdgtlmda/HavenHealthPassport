"""Compliance matrix analyzer for insights and recommendations."""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ..evidence.evidence_package import CertificationStandard
from .compliance_matrix import (
    ComplianceMatrix,
    ComplianceMatrixEntry,
    ComplianceStatus,
    RiskLevel,
)

logger = logging.getLogger(__name__)


class ComplianceMatrixAnalyzer:
    """Analyzes compliance matrix for insights, gaps, and recommendations."""

    def __init__(self, matrix: ComplianceMatrix):
        """Initialize analyzer with a compliance matrix.

        Args:
            matrix: Compliance matrix to analyze
        """
        self.matrix = matrix

    def analyze_compliance_readiness(self) -> Dict[str, Any]:
        """Analyze overall compliance readiness.

        Returns:
            Comprehensive readiness analysis
        """
        logger.info("Analyzing compliance readiness")

        # Get overall metrics
        overall_metrics = self.matrix.calculate_overall_compliance()

        # Analyze by standard
        standard_readiness = {}
        for standard in self.matrix.standards:
            standard_readiness[standard.value] = self._analyze_standard_readiness(
                standard
            )

        # Identify critical gaps
        critical_gaps = self._identify_critical_gaps()

        # Calculate time to compliance
        time_estimates = self._estimate_time_to_compliance()

        # Generate recommendations
        recommendations = self._generate_recommendations()

        # Risk assessment
        risk_assessment = self._assess_compliance_risks()

        return {
            "overall_readiness": overall_metrics["overall_percentage"],
            "certification_ready": overall_metrics["overall_percentage"] >= 95
            and overall_metrics["blocking_count"] == 0,
            "standard_readiness": standard_readiness,
            "critical_gaps": critical_gaps,
            "time_estimates": time_estimates,
            "recommendations": recommendations,
            "risk_assessment": risk_assessment,
            "analysis_timestamp": datetime.utcnow().isoformat(),
        }

    def _analyze_standard_readiness(
        self, standard: CertificationStandard
    ) -> Dict[str, Any]:
        """Analyze readiness for a specific standard."""
        entries = self.matrix.get_entries_by_standard(standard)

        if not entries:
            return {
                "ready": False,
                "percentage": 0.0,
                "blocking_items": 0,
                "estimated_days": 0,
            }

        # Calculate metrics
        total_compliance = sum(e.compliance_percentage for e in entries)
        percentage = total_compliance / len(entries)

        blocking_items = sum(1 for e in entries if e.is_blocking())

        # Estimate completion time
        incomplete_entries = [
            e
            for e in entries
            if e.status not in [ComplianceStatus.VALIDATED, ComplianceStatus.CERTIFIED]
        ]
        estimated_days = self._estimate_completion_time(incomplete_entries)

        return {
            "ready": percentage >= 95 and blocking_items == 0,
            "percentage": percentage,
            "total_requirements": len(entries),
            "completed_requirements": sum(
                1
                for e in entries
                if e.status in [ComplianceStatus.VALIDATED, ComplianceStatus.CERTIFIED]
            ),
            "blocking_items": blocking_items,
            "estimated_days": estimated_days,
            "categories": self._analyze_categories(entries),
        }

    def _analyze_categories(
        self, entries: List[ComplianceMatrixEntry]
    ) -> Dict[str, Dict[str, Any]]:
        """Analyze compliance by category."""
        categories = defaultdict(list)

        for entry in entries:
            categories[entry.requirement_category].append(entry)

        category_analysis = {}
        for category, cat_entries in categories.items():
            total_compliance = sum(e.compliance_percentage for e in cat_entries)
            category_analysis[category] = {
                "percentage": total_compliance / len(cat_entries),
                "total": len(cat_entries),
                "completed": sum(
                    1
                    for e in cat_entries
                    if e.status
                    in [ComplianceStatus.VALIDATED, ComplianceStatus.CERTIFIED]
                ),
            }

        return category_analysis

    def _identify_critical_gaps(self) -> List[Dict[str, Any]]:
        """Identify critical compliance gaps."""
        critical_gaps = []

        for entry in self.matrix.entries.values():
            if entry.is_blocking() and entry.risk_level in [
                RiskLevel.CRITICAL,
                RiskLevel.HIGH,
            ]:
                gap = {
                    "entry_id": entry.id,
                    "standard": entry.standard.value,
                    "requirement_id": entry.requirement_id,
                    "title": entry.requirement_title,
                    "risk_level": entry.risk_level.value,
                    "status": entry.status.value,
                    "compliance_percentage": entry.compliance_percentage,
                    "missing_evidence": len(entry.evidence_types_required)
                    - len(entry.evidence_ids),
                    "remediation_priority": entry.get_remediation_priority(),
                }
                critical_gaps.append(gap)

        # Sort by priority
        critical_gaps.sort(key=lambda x: x["remediation_priority"])

        return critical_gaps[:20]  # Top 20 critical gaps

    def _estimate_time_to_compliance(self) -> Dict[str, Any]:
        """Estimate time required to achieve compliance."""
        # Group incomplete entries by complexity
        incomplete_entries = [
            e
            for e in self.matrix.entries.values()
            if e.status
            not in [
                ComplianceStatus.VALIDATED,
                ComplianceStatus.CERTIFIED,
                ComplianceStatus.NOT_APPLICABLE,
            ]
        ]

        if not incomplete_entries:
            return {
                "total_days": 0,
                "by_standard": {},
                "completion_date": datetime.utcnow().isoformat(),
            }

        # Estimate based on status and complexity
        total_days = self._estimate_completion_time(incomplete_entries)

        # By standard
        by_standard = {}
        for standard in self.matrix.standards:
            standard_entries = [e for e in incomplete_entries if e.standard == standard]
            if standard_entries:
                by_standard[standard.value] = self._estimate_completion_time(
                    standard_entries
                )

        # Calculate completion date
        completion_date = datetime.utcnow() + timedelta(days=total_days)

        return {
            "total_days": total_days,
            "by_standard": by_standard,
            "completion_date": completion_date.isoformat(),
            "confidence_level": "medium",  # Could be calculated based on historical data
        }

    def _estimate_completion_time(self, entries: List[ComplianceMatrixEntry]) -> int:
        """Estimate days to complete given entries."""
        if not entries:
            return 0

        total_days = 0

        for entry in entries:
            # Base estimation on status and implementation type
            if entry.status == ComplianceStatus.NOT_STARTED:
                if entry.implementation_type.value in [
                    "technical_control",
                    "code_implementation",
                ]:
                    days = 5  # Technical implementations take longer
                elif entry.implementation_type.value in ["policy", "documentation"]:
                    days = 3  # Documentation is quicker
                else:
                    days = 4  # Default
            elif entry.status == ComplianceStatus.IN_PROGRESS:
                days = 2  # Already started, less time needed
            elif entry.status == ComplianceStatus.IMPLEMENTED:
                days = 1  # Just needs validation
            else:
                days = 3  # Default

            # Adjust for risk level
            if entry.risk_level == RiskLevel.CRITICAL:
                days = int(days * 0.8)  # Prioritize critical items

            total_days += days

        # Account for parallel work (can't do everything sequentially)
        total_days = int(total_days * 0.3)  # Assume 70% can be done in parallel

        return max(total_days, 1)

    def _generate_recommendations(self) -> List[Dict[str, Any]]:
        """Generate actionable recommendations."""
        recommendations = []

        # Check for missing evidence
        missing_evidence = self._check_missing_evidence()
        if missing_evidence:
            recommendations.append(
                {
                    "type": "evidence_collection",
                    "priority": "high",
                    "title": "Collect Missing Evidence",
                    "description": f"Collect evidence for {len(missing_evidence)} requirements",
                    "action_items": [
                        f"Gather {me['evidence_type']} for {me['requirement_title']}"
                        for me in missing_evidence[:5]
                    ],
                }
            )

        # Check for outdated reviews
        outdated_reviews = self._check_outdated_reviews()
        if outdated_reviews:
            recommendations.append(
                {
                    "type": "review_update",
                    "priority": "medium",
                    "title": "Update Outdated Reviews",
                    "description": f"Review and update {len(outdated_reviews)} requirements",
                    "action_items": [
                        f"Review {r['requirement_title']} (last reviewed {r['days_ago']} days ago)"
                        for r in outdated_reviews[:5]
                    ],
                }
            )

        # Check for dependency issues
        dependency_issues = self.matrix.validate_dependencies()
        if dependency_issues:
            recommendations.append(
                {
                    "type": "dependency_resolution",
                    "priority": "high",
                    "title": "Resolve Dependency Issues",
                    "description": f"Address {len(dependency_issues)} dependency conflicts",
                    "action_items": [
                        issue["message"] for issue in dependency_issues[:5]
                    ],
                }
            )

        # Standard-specific recommendations
        for standard in self.matrix.standards:
            standard_recs = self._generate_standard_recommendations(standard)
            recommendations.extend(standard_recs)

        # Sort by priority
        priority_order: Dict[str, int] = {
            "critical": 0,
            "high": 1,
            "medium": 2,
            "low": 3,
        }
        recommendations.sort(key=lambda x: priority_order.get(str(x["priority"]), 10))

        return recommendations

    def _check_missing_evidence(self) -> List[Dict[str, Any]]:
        """Check for requirements missing evidence."""
        missing = []

        for entry in self.matrix.entries.values():
            if entry.evidence_types_required and not entry.evidence_ids:
                for evidence_type in entry.evidence_types_required:
                    missing.append(
                        {
                            "entry_id": entry.id,
                            "requirement_title": entry.requirement_title,
                            "evidence_type": evidence_type.value,
                        }
                    )

        return missing

    def _check_outdated_reviews(self) -> List[Dict[str, Any]]:
        """Check for requirements with outdated reviews."""
        outdated = []
        review_threshold = timedelta(days=90)  # 90 days

        for entry in self.matrix.entries.values():
            if entry.last_review_date:
                days_since_review = (datetime.utcnow() - entry.last_review_date).days
                if days_since_review > review_threshold.days:
                    outdated.append(
                        {
                            "entry_id": entry.id,
                            "requirement_title": entry.requirement_title,
                            "days_ago": days_since_review,
                        }
                    )

        return outdated

    def _generate_standard_recommendations(
        self, standard: CertificationStandard
    ) -> List[Dict[str, Any]]:
        """Generate recommendations specific to a standard."""
        recommendations = []
        # entries = self.matrix.get_entries_by_standard(standard)  # Currently unused

        # Check completion percentage
        standard_metrics = self._analyze_standard_readiness(standard)
        if standard_metrics["percentage"] < 50:
            recommendations.append(
                {
                    "type": "standard_compliance",
                    "priority": "high",
                    "title": f"Accelerate {standard.value} Compliance",
                    "description": f"Only {standard_metrics['percentage']:.1f}% complete for {standard.value}",
                    "action_items": [
                        f"Focus on {standard_metrics['blocking_items']} blocking items",
                        "Allocate additional resources to this standard",
                    ],
                }
            )

        return recommendations

    def _assess_compliance_risks(self) -> Dict[str, Any]:
        """Assess risks related to compliance gaps."""
        risks: Dict[str, Any] = {
            "overall_risk_level": "low",
            "risk_factors": [],
            "mitigation_priorities": [],
        }

        # Count high-risk non-compliant items
        high_risk_count = sum(
            1
            for e in self.matrix.entries.values()
            if e.is_blocking() and e.risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]
        )

        if high_risk_count > 10:
            risks["overall_risk_level"] = "critical"
        elif high_risk_count > 5:
            risks["overall_risk_level"] = "high"
        elif high_risk_count > 2:
            risks["overall_risk_level"] = "medium"

        # Identify specific risk factors
        if high_risk_count > 0:
            risks["risk_factors"].append(
                {
                    "factor": "High-risk non-compliance",
                    "description": f"{high_risk_count} critical/high risk requirements not satisfied",
                    "impact": "Certification delay or rejection",
                }
            )

        # Check for systemic issues
        category_risks = self._identify_category_risks()
        risks["risk_factors"].extend(category_risks)

        # Mitigation priorities
        risks["mitigation_priorities"] = self._prioritize_risk_mitigation()

        return risks

    def _identify_category_risks(self) -> List[Dict[str, Any]]:
        """Identify risks by requirement category."""
        category_risks = []

        # Group by category
        categories = defaultdict(list)
        for entry in self.matrix.entries.values():
            categories[entry.requirement_category].append(entry)

        # Check each category
        for category, entries in categories.items():
            non_compliant = sum(1 for e in entries if e.is_blocking())
            if non_compliant > len(entries) * 0.3:  # More than 30% non-compliant
                category_risks.append(
                    {
                        "factor": f"Systemic gaps in {category}",
                        "description": f"{non_compliant} of {len(entries)} requirements not satisfied",
                        "impact": "Indicates process or system deficiencies",
                    }
                )

        return category_risks

    def _prioritize_risk_mitigation(self) -> List[Dict[str, str]]:
        """Prioritize risk mitigation actions."""
        priorities = []

        # Get high-priority items
        high_priority = self.matrix.get_high_priority_items(10)

        for entry in high_priority:
            priorities.append(
                {
                    "requirement": entry.requirement_title,
                    "action": f"Implement {entry.implementation_type.value}",
                    "urgency": (
                        "immediate"
                        if entry.risk_level == RiskLevel.CRITICAL
                        else "high"
                    ),
                }
            )

        return priorities[:5]  # Top 5 priorities

    def generate_executive_summary(self) -> str:
        """Generate executive summary of compliance status."""
        analysis = self.analyze_compliance_readiness()

        summary_parts = [
            "# Compliance Matrix Executive Summary",
            "",
            f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "## Overall Status",
            f"- **Compliance Readiness:** {analysis['overall_readiness']:.1f}%",
            f"- **Certification Ready:** {'Yes' if analysis['certification_ready'] else 'No'}",
            f"- **Estimated Time to Compliance:** {analysis['time_estimates']['total_days']} days",
            "",
            "## Standards Summary",
        ]

        for standard, readiness in analysis["standard_readiness"].items():
            summary_parts.extend(
                [
                    "",
                    f"### {standard.upper()}",
                    f"- Readiness: {readiness['percentage']:.1f}%",
                    f"- Requirements: {readiness['completed_requirements']}/{readiness['total_requirements']} completed",
                    f"- Blocking Items: {readiness['blocking_items']}",
                    f"- Estimated Days: {readiness['estimated_days']}",
                ]
            )

        # Add critical gaps
        if analysis["critical_gaps"]:
            summary_parts.extend(["", "## Critical Gaps (Top 5)", ""])

            for gap in analysis["critical_gaps"][:5]:
                summary_parts.append(
                    f"- **{gap['requirement_id']}**: {gap['title']} "
                    f"(Risk: {gap['risk_level']}, Status: {gap['status']})"
                )

        # Add top recommendations
        if analysis["recommendations"]:
            summary_parts.extend(["", "## Key Recommendations", ""])

            for rec in analysis["recommendations"][:3]:
                summary_parts.append(f"- **{rec['title']}**: {rec['description']}")

        # Risk assessment
        risk = analysis["risk_assessment"]
        summary_parts.extend(
            [
                "",
                "## Risk Assessment",
                f"- **Overall Risk Level:** {risk['overall_risk_level'].upper()}",
                f"- **Risk Factors:** {len(risk['risk_factors'])}",
            ]
        )

        return "\n".join(summary_parts)
