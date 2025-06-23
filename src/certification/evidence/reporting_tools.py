"""Reporting tools for certification evidence and compliance."""

import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from .evidence_package import EvidencePackage


class ReportingTool:
    """Tool for generating various certification and compliance reports."""

    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize reporting tool.

        Args:
            output_dir: Directory for report outputs
        """
        self.output_dir = output_dir or Path("certification/reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_compliance_dashboard(self, package: EvidencePackage) -> Dict[str, Any]:
        """Generate compliance dashboard data.

        Args:
            package: Evidence package to analyze

        Returns:
            Dashboard data dictionary
        """
        dashboard: Dict[str, Any] = {
            "generated_at": datetime.utcnow().isoformat(),
            "package_id": package.id,
            "package_name": package.name,
            "overall_compliance": package.calculate_completeness(),
            "standards": {},
            "evidence_metrics": self._calculate_evidence_metrics(package),
            "requirement_metrics": self._calculate_requirement_metrics(package),
            "timeline": self._generate_timeline_data(package),
            "risk_assessment": self._assess_compliance_risks(package),
        }

        # Calculate per-standard compliance
        for standard in package.certification_standards:
            requirements = package.get_requirements_by_standard(standard)
            satisfied = sum(1 for r in requirements if r.satisfied)
            total = len(requirements)

            dashboard["standards"][standard.value] = {
                "compliance_percentage": (satisfied / total * 100) if total > 0 else 0,
                "total_requirements": total,
                "satisfied_requirements": satisfied,
                "critical_gaps": sum(
                    1 for r in requirements if not r.satisfied and r.mandatory
                ),
            }

        return dashboard

    def generate_evidence_report(
        self, package: EvidencePackage, format: str = "json"
    ) -> Path:
        """Generate detailed evidence report.

        Args:
            package: Evidence package
            format: Output format (json, csv, html)

        Returns:
            Path to generated report file
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        if format == "json":
            return self._generate_json_report(package, timestamp)
        elif format == "csv":
            return self._generate_csv_report(package, timestamp)
        elif format == "html":
            return self._generate_html_report(package, timestamp)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def generate_requirement_traceability_matrix(
        self, package: EvidencePackage
    ) -> Path:
        """Generate requirement traceability matrix.

        Args:
            package: Evidence package

        Returns:
            Path to traceability matrix file
        """
        matrix_data = []

        for req in package.requirements.values():
            evidence_items = [
                package.evidence_items.get(eid)
                for eid in req.evidence_items
                if eid in package.evidence_items
            ]

            matrix_data.append(
                {
                    "Standard": req.standard.value,
                    "Requirement ID": req.requirement_id,
                    "Title": req.title,
                    "Mandatory": "Yes" if req.mandatory else "No",
                    "Status": "Satisfied" if req.satisfied else "Not Satisfied",
                    "Evidence Count": len(evidence_items),
                    "Evidence Types": ", ".join(
                        set(e.type.value for e in evidence_items if e)
                    ),
                    "Evidence IDs": ", ".join(e.id[:8] for e in evidence_items if e),
                }
            )

        # Save as CSV
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        csv_file = self.output_dir / f"traceability_matrix_{timestamp}.csv"

        with open(csv_file, "w", newline="") as f:
            if matrix_data:
                writer = csv.DictWriter(f, fieldnames=matrix_data[0].keys())
                writer.writeheader()
                writer.writerows(matrix_data)

        return csv_file

    def generate_compliance_timeline(self, package: EvidencePackage) -> Dict[str, Any]:
        """Generate compliance timeline showing evidence collection progress.

        Args:
            package: Evidence package

        Returns:
            Timeline data
        """
        timeline: Dict[str, Any] = {
            "start_date": None,
            "end_date": None,
            "duration_days": 0,
            "evidence_by_date": defaultdict(list),
            "milestones": [],
            "collection_rate": {},
        }

        if package.evidence_items:
            dates = [e.created_at for e in package.evidence_items.values()]
            timeline["start_date"] = min(dates).isoformat()
            timeline["end_date"] = max(dates).isoformat()
            timeline["duration_days"] = (max(dates) - min(dates)).days

            # Group evidence by date
            for evidence in package.evidence_items.values():
                date_key = evidence.created_at.date().isoformat()
                timeline["evidence_by_date"][date_key].append(
                    {
                        "id": evidence.id,
                        "type": evidence.type.value,
                        "title": evidence.title,
                    }
                )

            # Calculate collection rate
            total_days = timeline["duration_days"] or 1
            timeline["collection_rate"] = {
                "average_per_day": len(package.evidence_items) / total_days,
                "peak_day": (
                    max(timeline["evidence_by_date"].items(), key=lambda x: len(x[1]))[
                        0
                    ]
                    if timeline["evidence_by_date"]
                    else None
                ),
            }

        return timeline

    def generate_executive_summary(self, package: EvidencePackage) -> Path:
        """Generate executive summary report.

        Args:
            package: Evidence package

        Returns:
            Path to executive summary file
        """
        summary: Dict[str, Any] = {
            "Executive Summary": {
                "Generated": datetime.utcnow().isoformat(),
                "Package": package.name,
                "Overall Compliance": f"{package.calculate_completeness():.1f}%",
                "Status": package.status,
            },
            "Certification Standards": {},
            "Key Findings": [],
            "Recommendations": [],
            "Next Steps": [],
        }

        # Analyze each standard
        for standard in package.certification_standards:
            requirements = package.get_requirements_by_standard(standard)
            satisfied = sum(1 for r in requirements if r.satisfied)

            summary["Certification Standards"][standard.value] = {
                "Requirements": len(requirements),
                "Satisfied": satisfied,
                "Compliance": f"{(satisfied/len(requirements)*100) if requirements else 0:.1f}%",
            }

        # Key findings
        unsatisfied = package.get_unsatisfied_requirements()
        if unsatisfied:
            summary["Key Findings"].append(
                f"{len(unsatisfied)} requirements remain unsatisfied"
            )
            critical = [r for r in unsatisfied if r.mandatory]
            if critical:
                summary["Key Findings"].append(
                    f"{len(critical)} critical mandatory requirements need immediate attention"
                )

        # Recommendations
        if package.calculate_completeness() < 100:
            summary["Recommendations"].append(
                "Complete evidence collection for all mandatory requirements"
            )
            summary["Recommendations"].append(
                "Schedule compliance review with certification body"
            )

        # Save as JSON
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        summary_file = self.output_dir / f"executive_summary_{timestamp}.json"

        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        return summary_file

    # Helper methods

    def _calculate_evidence_metrics(self, package: EvidencePackage) -> Dict[str, Any]:
        """Calculate evidence-related metrics."""
        metrics: Dict[str, Any] = {
            "total_evidence": len(package.evidence_items),
            "evidence_by_type": {},
            "evidence_age": {"newest": None, "oldest": None, "average_age_days": 0},
            "evidence_sources": defaultdict(int),
        }

        if package.evidence_items:
            # Count by type
            for evidence in package.evidence_items.values():
                type_key = evidence.type.value
                metrics["evidence_by_type"][type_key] = (
                    metrics["evidence_by_type"].get(type_key, 0) + 1
                )

                # Count by source
                metrics["evidence_sources"][evidence.created_by] += 1

            # Calculate age metrics
            now = datetime.utcnow()
            ages = [(now - e.created_at).days for e in package.evidence_items.values()]
            metrics["evidence_age"]["newest"] = min(ages)
            metrics["evidence_age"]["oldest"] = max(ages)
            metrics["evidence_age"]["average_age_days"] = sum(ages) / len(ages)

        return metrics

    def _calculate_requirement_metrics(
        self, package: EvidencePackage
    ) -> Dict[str, Any]:
        """Calculate requirement-related metrics."""
        metrics: Dict[str, Any] = {
            "total_requirements": len(package.requirements),
            "mandatory_requirements": sum(
                1 for r in package.requirements.values() if r.mandatory
            ),
            "optional_requirements": sum(
                1 for r in package.requirements.values() if not r.mandatory
            ),
            "satisfaction_rate": {"overall": 0, "mandatory": 0, "optional": 0},
        }

        if package.requirements:
            satisfied = sum(1 for r in package.requirements.values() if r.satisfied)
            metrics["satisfaction_rate"]["overall"] = (
                satisfied / len(package.requirements) * 100
            )

            mandatory = [r for r in package.requirements.values() if r.mandatory]
            if mandatory:
                satisfied_mandatory = sum(1 for r in mandatory if r.satisfied)
                metrics["satisfaction_rate"]["mandatory"] = (
                    satisfied_mandatory / len(mandatory) * 100
                )

            optional = [r for r in package.requirements.values() if not r.mandatory]
            if optional:
                satisfied_optional = sum(1 for r in optional if r.satisfied)
                metrics["satisfaction_rate"]["optional"] = (
                    satisfied_optional / len(optional) * 100
                )

        return metrics

    def _generate_timeline_data(self, package: EvidencePackage) -> Dict[str, Any]:
        """Generate timeline visualization data."""
        timeline_data: Dict[str, Any] = {"events": [], "periods": [], "statistics": {}}

        # Create events for evidence creation
        for evidence in package.evidence_items.values():
            timeline_data["events"].append(
                {
                    "date": evidence.created_at.isoformat(),
                    "type": "evidence_created",
                    "title": evidence.title,
                    "evidence_type": evidence.type.value,
                }
            )

        # Calculate collection periods
        if package.evidence_items:
            dates = [e.created_at for e in package.evidence_items.values()]
            start_date = min(dates)
            end_date = max(dates)

            # Weekly aggregation
            current = start_date
            while current <= end_date:
                week_end = current + timedelta(days=7)
                week_evidence = [
                    e
                    for e in package.evidence_items.values()
                    if current <= e.created_at < week_end
                ]

                if week_evidence:
                    timeline_data["periods"].append(
                        {
                            "start": current.isoformat(),
                            "end": week_end.isoformat(),
                            "evidence_count": len(week_evidence),
                            "types": list(set(e.type.value for e in week_evidence)),
                        }
                    )

                current = week_end

        return timeline_data

    def _assess_compliance_risks(self, package: EvidencePackage) -> Dict[str, Any]:
        """Assess compliance-related risks."""
        risks: Dict[str, Any] = {
            "risk_level": "low",  # low, medium, high, critical
            "risk_factors": [],
            "mitigation_required": [],
        }

        # Check for unsatisfied mandatory requirements
        unsatisfied_mandatory = [
            r for r in package.requirements.values() if r.mandatory and not r.satisfied
        ]

        if unsatisfied_mandatory:
            risks["risk_factors"].append(
                {
                    "factor": "unsatisfied_mandatory_requirements",
                    "count": len(unsatisfied_mandatory),
                    "severity": "high",
                }
            )
            risks["mitigation_required"].append(
                "Complete evidence collection for mandatory requirements"
            )

        # Check for old evidence
        if package.evidence_items:
            now = datetime.utcnow()
            old_evidence = [
                e
                for e in package.evidence_items.values()
                if (now - e.created_at).days > 90
            ]

            if old_evidence:
                risks["risk_factors"].append(
                    {
                        "factor": "outdated_evidence",
                        "count": len(old_evidence),
                        "severity": "medium",
                    }
                )
                risks["mitigation_required"].append(
                    "Update evidence older than 90 days"
                )

        # Determine overall risk level
        severities = [rf["severity"] for rf in risks["risk_factors"]]
        if "high" in severities:
            risks["risk_level"] = "high"
        elif "medium" in severities:
            risks["risk_level"] = "medium"

        return risks

    def _generate_json_report(self, package: EvidencePackage, timestamp: str) -> Path:
        """Generate JSON format report."""
        report_file = self.output_dir / f"evidence_report_{timestamp}.json"

        report_data = {
            "report_metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "package_id": package.id,
                "package_name": package.name,
                "version": package.version,
            },
            "compliance_summary": self.generate_compliance_dashboard(package),
            "evidence_details": [e.to_dict() for e in package.evidence_items.values()],
            "requirements_details": [
                r.to_dict() for r in package.requirements.values()
            ],
        }

        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2)

        return report_file

    def _generate_csv_report(self, package: EvidencePackage, timestamp: str) -> Path:
        """Generate CSV format report."""
        csv_file = self.output_dir / f"evidence_report_{timestamp}.csv"

        rows = []
        for evidence in package.evidence_items.values():
            rows.append(
                {
                    "Evidence ID": evidence.id,
                    "Type": evidence.type.value,
                    "Title": evidence.title,
                    "Description": evidence.description,
                    "Created At": evidence.created_at.isoformat(),
                    "Created By": evidence.created_by,
                    "Tags": ", ".join(evidence.tags),
                    "Has File": "Yes" if evidence.file_path else "No",
                }
            )

        with open(csv_file, "w", newline="") as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

        return csv_file

    def _generate_html_report(self, package: EvidencePackage, timestamp: str) -> Path:
        """Generate HTML format report."""
        html_file = self.output_dir / f"evidence_report_{timestamp}.html"

        dashboard = self.generate_compliance_dashboard(package)

        html_content = f"""
        <html>
        <head>
            <title>Evidence Report - {package.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2 {{ color: #333; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .metric {{ display: inline-block; margin: 10px; padding: 10px;
                          background: #f5f5f5; border-radius: 5px; }}
                .compliant {{ color: green; }}
                .non-compliant {{ color: red; }}
            </style>
        </head>
        <body>
            <h1>Evidence Report: {package.name}</h1>
            <p>Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}</p>

            <h2>Compliance Summary</h2>
            <div class="metric">
                <strong>Overall Compliance:</strong> {dashboard['overall_compliance']:.1f}%
            </div>

            <h2>Standards Compliance</h2>
            <table>
                <tr>
                    <th>Standard</th>
                    <th>Compliance</th>
                    <th>Requirements</th>
                    <th>Satisfied</th>
                </tr>
        """

        for std, data in dashboard["standards"].items():
            compliance_class = (
                "compliant" if data["compliance_percentage"] >= 100 else "non-compliant"
            )
            html_content += f"""
                <tr>
                    <td>{std}</td>
                    <td class="{compliance_class}">{data['compliance_percentage']:.1f}%</td>
                    <td>{data['total_requirements']}</td>
                    <td>{data['satisfied_requirements']}</td>
                </tr>
            """

        html_content += """
            </table>

            <h2>Evidence Summary</h2>
            <p>Total Evidence Items: {}</p>

            <h2>Risk Assessment</h2>
            <p>Risk Level: <strong>{}</strong></p>
        </body>
        </html>
        """.format(
            dashboard["evidence_metrics"]["total_evidence"],
            dashboard["risk_assessment"]["risk_level"].upper(),
        )

        with open(html_file, "w") as f:
            f.write(html_content)

        return html_file
