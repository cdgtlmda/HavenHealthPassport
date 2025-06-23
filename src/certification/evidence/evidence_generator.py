"""Evidence generator for creating certification documentation."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .evidence_package import (
    CertificationStandard,
    EvidenceItem,
    EvidencePackage,
    EvidenceType,
)

# Remove dependencies on external libraries for now
# import markdown
# from jinja2 import Environment, FileSystemLoader, Template


class EvidenceGenerator:
    """Generates formatted evidence documentation for certification."""

    def __init__(self, template_dir: Optional[Path] = None):
        """Initialize evidence generator.

        Args:
            template_dir: Directory containing document templates
        """
        self.template_dir = template_dir or Path(__file__).parent / "templates"
        self.output_dir = Path("certification/evidence-packages/output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_summary_report(self, package: EvidencePackage) -> EvidenceItem:
        """Generate executive summary report for the evidence package.

        Args:
            package: Evidence package to summarize

        Returns:
            Evidence item containing the summary report
        """
        summary_data = {
            "package_id": package.id,
            "package_name": package.name,
            "created_at": package.created_at.isoformat(),
            "updated_at": package.updated_at.isoformat(),
            "version": package.version,
            "status": package.status,
            "completeness": package.calculate_completeness(),
            "certification_standards": [
                cs.value for cs in package.certification_standards
            ],
            "evidence_summary": self._generate_evidence_summary(package),
            "requirements_summary": self._generate_requirements_summary(package),
            "compliance_gaps": self._identify_compliance_gaps(package),
        }

        report_content = self._format_summary_report(summary_data)

        return EvidenceItem(
            type=EvidenceType.COMPLIANCE_REPORT,
            title="Evidence Package Summary Report",
            description="Executive summary of certification evidence package",
            content=summary_data,
            created_by="EvidenceGenerator",
            tags=["summary", "report", "certification"],
            metadata={"format": "markdown", "content": report_content},
        )

    def generate_compliance_matrix(
        self, package: EvidencePackage, standard: CertificationStandard
    ) -> EvidenceItem:
        """Generate compliance matrix for specific certification standard.

        Args:
            package: Evidence package
            standard: Certification standard to generate matrix for

        Returns:
            Evidence item containing the compliance matrix
        """
        requirements = package.get_requirements_by_standard(standard)

        matrix_data: Dict[str, Any] = {
            "standard": standard.value,
            "generated_at": datetime.utcnow().isoformat(),
            "total_requirements": len(requirements),
            "satisfied_requirements": sum(1 for r in requirements if r.satisfied),
            "requirements": [],
        }

        for req in requirements:
            evidence_items = [
                package.evidence_items.get(eid)
                for eid in req.evidence_items
                if eid in package.evidence_items
            ]

            matrix_data["requirements"].append(
                {
                    "requirement_id": req.requirement_id,
                    "title": req.title,
                    "description": req.description,
                    "mandatory": req.mandatory,
                    "satisfied": req.satisfied,
                    "evidence_count": len(evidence_items),
                    "evidence_types": list(
                        set(e.type.value for e in evidence_items if e)
                    ),
                    "evidence_items": [
                        {
                            "id": e.id,
                            "title": e.title,
                            "type": e.type.value,
                            "created_at": e.created_at.isoformat(),
                        }
                        for e in evidence_items
                        if e
                    ],
                }
            )

        matrix_content = self._format_compliance_matrix(matrix_data)

        return EvidenceItem(
            type=EvidenceType.COMPLIANCE_REPORT,
            title=f"Compliance Matrix - {standard.value}",
            description=f"Requirements compliance matrix for {standard.value}",
            content=matrix_data,
            created_by="EvidenceGenerator",
            tags=["compliance", "matrix", standard.value.lower()],
            metadata={"format": "markdown", "content": matrix_content},
        )

    def generate_evidence_catalog(self, package: EvidencePackage) -> EvidenceItem:
        """Generate comprehensive catalog of all evidence items.

        Args:
            package: Evidence package

        Returns:
            Evidence item containing the evidence catalog
        """
        catalog_data: Dict[str, Any] = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_evidence_items": len(package.evidence_items),
            "evidence_by_type": {},
            "evidence_items": [],
        }

        # Group evidence by type
        for evidence_type in EvidenceType:
            items = package.get_evidence_by_type(evidence_type)
            if items:
                catalog_data["evidence_by_type"][evidence_type.value] = len(items)

        # Detailed evidence list
        for evidence in package.evidence_items.values():
            catalog_data["evidence_items"].append(
                {
                    "id": evidence.id,
                    "type": evidence.type.value,
                    "title": evidence.title,
                    "description": evidence.description,
                    "created_at": evidence.created_at.isoformat(),
                    "created_by": evidence.created_by,
                    "tags": evidence.tags,
                    "file_path": (
                        str(evidence.file_path) if evidence.file_path else None
                    ),
                    "file_hash": evidence.file_hash or evidence.calculate_hash(),
                }
            )

        catalog_content = self._format_evidence_catalog(catalog_data)

        return EvidenceItem(
            type=EvidenceType.COMPLIANCE_REPORT,
            title="Evidence Catalog",
            description="Comprehensive catalog of all certification evidence",
            content=catalog_data,
            created_by="EvidenceGenerator",
            tags=["catalog", "evidence", "inventory"],
            metadata={"format": "markdown", "content": catalog_content},
        )

    def generate_gap_analysis(self, package: EvidencePackage) -> EvidenceItem:
        """Generate gap analysis report identifying missing evidence.

        Args:
            package: Evidence package

        Returns:
            Evidence item containing gap analysis
        """
        gap_data: Dict[str, Any] = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_gaps": 0,
            "gaps_by_standard": {},
            "critical_gaps": [],
            "recommendations": [],
        }

        for standard in package.certification_standards:
            requirements = package.get_requirements_by_standard(standard)
            unsatisfied = [r for r in requirements if not r.satisfied and r.mandatory]

            if unsatisfied:
                gap_data["gaps_by_standard"][standard.value] = {
                    "total_requirements": len(requirements),
                    "unsatisfied_requirements": len(unsatisfied),
                    "gaps": [],
                }

                for req in unsatisfied:
                    gap = {
                        "requirement_id": req.requirement_id,
                        "title": req.title,
                        "description": req.description,
                        "required_evidence_types": [
                            et.value for et in req.evidence_types
                        ],
                        "current_evidence": len(req.evidence_items),
                        "gap_severity": "critical" if req.mandatory else "medium",
                    }
                    gap_data["gaps_by_standard"][standard.value]["gaps"].append(gap)

                    if req.mandatory:
                        gap_data["critical_gaps"].append(gap)

                gap_data["total_gaps"] += len(unsatisfied)

        # Generate recommendations
        gap_data["recommendations"] = self._generate_gap_recommendations(gap_data)

        gap_content = self._format_gap_analysis(gap_data)

        return EvidenceItem(
            type=EvidenceType.COMPLIANCE_REPORT,
            title="Gap Analysis Report",
            description="Analysis of missing evidence and compliance gaps",
            content=gap_data,
            created_by="EvidenceGenerator",
            tags=["gap-analysis", "compliance", "assessment"],
            metadata={"format": "markdown", "content": gap_content},
        )

    def generate_certification_package(
        self, package: EvidencePackage, output_format: str = "pdf"
    ) -> Path:
        """Generate complete certification package documentation.

        Args:
            package: Evidence package
            output_format: Output format (pdf, html, docx)

        Returns:
            Path to generated package file
        """
        # Validate package requirements
        package.validate_requirements()

        # Create output directory for this package
        package_dir = self.output_dir / f"package_{package.id}"
        package_dir.mkdir(exist_ok=True)

        # Generate all reports
        reports = [
            self.generate_summary_report(package),
            self.generate_evidence_catalog(package),
            self.generate_gap_analysis(package),
        ]

        # Generate compliance matrices for each standard
        for standard in package.certification_standards:
            reports.append(self.generate_compliance_matrix(package, standard))

        # Save package data
        package_file = package_dir / "evidence_package.json"
        package.save_to_file(package_file)

        # Generate consolidated document
        if output_format == "html":
            output_file = self._generate_html_package(package, reports, package_dir)
        elif output_format == "pdf":
            output_file = self._generate_pdf_package(package, reports, package_dir)
        else:
            output_file = self._generate_markdown_package(package, reports, package_dir)

        return output_file

    # Helper methods for formatting reports

    def _generate_evidence_summary(self, package: EvidencePackage) -> Dict[str, Any]:
        """Generate summary statistics for evidence items."""
        summary: Dict[str, Any] = {
            "total_items": len(package.evidence_items),
            "by_type": {},
            "by_created_date": {},
            "file_evidence": 0,
        }

        for evidence in package.evidence_items.values():
            # Count by type
            type_key = evidence.type.value
            summary["by_type"][type_key] = summary["by_type"].get(type_key, 0) + 1

            # Count by date
            date_key = evidence.created_at.date().isoformat()
            summary["by_created_date"][date_key] = (
                summary["by_created_date"].get(date_key, 0) + 1
            )

            # Count file evidence
            if evidence.file_path:
                summary["file_evidence"] += 1

        return summary

    def _generate_requirements_summary(
        self, package: EvidencePackage
    ) -> Dict[str, Any]:
        """Generate summary statistics for requirements."""
        summary: Dict[str, Any] = {
            "total_requirements": len(package.requirements),
            "satisfied": 0,
            "unsatisfied": 0,
            "by_standard": {},
        }

        for req in package.requirements.values():
            if req.satisfied:
                summary["satisfied"] += 1
            else:
                summary["unsatisfied"] += 1

            standard_key = req.standard.value
            if standard_key not in summary["by_standard"]:
                summary["by_standard"][standard_key] = {
                    "total": 0,
                    "satisfied": 0,
                    "unsatisfied": 0,
                }

            summary["by_standard"][standard_key]["total"] += 1
            if req.satisfied:
                summary["by_standard"][standard_key]["satisfied"] += 1
            else:
                summary["by_standard"][standard_key]["unsatisfied"] += 1

        return summary

    def _identify_compliance_gaps(
        self, package: EvidencePackage
    ) -> List[Dict[str, Any]]:
        """Identify critical compliance gaps."""
        gaps = []

        for req in package.get_unsatisfied_requirements():
            gap = {
                "requirement_id": req.requirement_id,
                "standard": req.standard.value,
                "title": req.title,
                "missing_evidence_types": [et.value for et in req.evidence_types],
                "priority": "high" if req.mandatory else "medium",
            }
            gaps.append(gap)

        return sorted(gaps, key=lambda x: x["priority"], reverse=True)

    def _generate_gap_recommendations(
        self, gap_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on identified gaps."""
        recommendations = []

        # Check for critical gaps
        if gap_data["critical_gaps"]:
            recommendations.append(
                {
                    "priority": "critical",
                    "category": "mandatory_requirements",
                    "recommendation": "Address all critical mandatory requirements immediately",
                    "action_items": [
                        f"Collect evidence for: {gap['title']}"
                        for gap in gap_data["critical_gaps"][:5]  # Top 5 critical gaps
                    ],
                }
            )

        # Check for specific standard gaps
        for standard, gaps in gap_data["gaps_by_standard"].items():
            if gaps["unsatisfied_requirements"] > 0:
                recommendations.append(
                    {
                        "priority": "high",
                        "category": f"{standard}_compliance",
                        "recommendation": f"Complete {standard} compliance requirements",
                        "action_items": [
                            f"Collect {gaps['unsatisfied_requirements']} missing evidence items",
                            f"Review {standard} requirements checklist",
                            "Schedule compliance assessment",
                        ],
                    }
                )

        return recommendations

    def _format_summary_report(self, data: Dict[str, Any]) -> str:
        """Format summary report as markdown."""
        lines = [
            "# Evidence Package Summary Report",
            "",
            f"**Package ID:** {data['package_id']}",
            f"**Package Name:** {data['package_name']}",
            f"**Generated:** {datetime.utcnow().isoformat()}",
            f"**Status:** {data['status']}",
            f"**Completeness:** {data['completeness']:.1f}%",
            "",
            "## Certification Standards",
            "",
        ]

        for standard in data["certification_standards"]:
            lines.append(f"- {standard}")

        lines.extend(
            [
                "",
                "## Evidence Summary",
                "",
                f"Total Evidence Items: {data['evidence_summary']['total_items']}",
                "",
                "### Evidence by Type",
                "",
            ]
        )

        for etype, count in data["evidence_summary"]["by_type"].items():
            lines.append(f"- {etype}: {count}")

        lines.extend(
            [
                "",
                "## Requirements Summary",
                "",
                f"- Total Requirements: {data['requirements_summary']['total_requirements']}",
                f"- Satisfied: {data['requirements_summary']['satisfied']}",
                f"- Unsatisfied: {data['requirements_summary']['unsatisfied']}",
                "",
                "## Compliance Gaps",
                "",
                f"Critical gaps identified: {len(data['compliance_gaps'])}",
                "",
            ]
        )

        return "\n".join(lines)

    def _format_compliance_matrix(self, data: Dict[str, Any]) -> str:
        """Format compliance matrix as markdown."""
        lines = [
            f"# Compliance Matrix - {data['standard']}",
            "",
            f"**Generated:** {data['generated_at']}",
            f"**Total Requirements:** {data['total_requirements']}",
            f"**Satisfied Requirements:** {data['satisfied_requirements']}",
            "",
            "## Requirements Status",
            "",
            "| Requirement ID | Title | Mandatory | Status | Evidence Count |",
            "|----------------|-------|-----------|--------|----------------|",
        ]

        for req in data["requirements"]:
            status = "✓ Satisfied" if req["satisfied"] else "✗ Not Satisfied"
            mandatory = "Yes" if req["mandatory"] else "No"
            lines.append(
                f"| {req['requirement_id']} | {req['title']} | {mandatory} | {status} | {req['evidence_count']} |"
            )

        return "\n".join(lines)

    def _format_evidence_catalog(self, data: Dict[str, Any]) -> str:
        """Format evidence catalog as markdown."""
        lines = [
            "# Evidence Catalog",
            "",
            f"**Generated:** {data['generated_at']}",
            f"**Total Evidence Items:** {data['total_evidence_items']}",
            "",
            "## Evidence Distribution",
            "",
        ]

        for etype, count in data["evidence_by_type"].items():
            lines.append(f"- {etype}: {count} items")

        lines.extend(
            [
                "",
                "## Evidence Items",
                "",
                "| ID | Type | Title | Created | Tags |",
                "|----|------|-------|---------|------|",
            ]
        )

        for item in data["evidence_items"][:20]:  # Show first 20 items
            tags = ", ".join(item["tags"][:3])  # Show first 3 tags
            lines.append(
                f"| {item['id'][:8]}... | {item['type']} | {item['title']} | {item['created_at'][:10]} | {tags} |"
            )

        if len(data["evidence_items"]) > 20:
            lines.append("| ... | ... | ... | ... | ... |")
            lines.append(f"| *{len(data['evidence_items']) - 20} more items* | | | | |")

        return "\n".join(lines)

    def _format_gap_analysis(self, data: Dict[str, Any]) -> str:
        """Format gap analysis as markdown."""
        lines = [
            "# Gap Analysis Report",
            "",
            f"**Generated:** {data['generated_at']}",
            f"**Total Gaps:** {data['total_gaps']}",
            f"**Critical Gaps:** {len(data['critical_gaps'])}",
            "",
        ]

        if data["critical_gaps"]:
            lines.extend(
                [
                    "## Critical Gaps",
                    "",
                    "The following mandatory requirements must be addressed immediately:",
                    "",
                ]
            )

            for gap in data["critical_gaps"]:
                lines.append(f"- **{gap['requirement_id']}**: {gap['title']}")
                lines.append(
                    f"  - Required evidence types: {', '.join(gap['required_evidence_types'])}"
                )
                lines.append(f"  - Current evidence: {gap['current_evidence']}")
                lines.append("")

        lines.extend(
            [
                "## Recommendations",
                "",
            ]
        )

        for rec in data["recommendations"]:
            lines.append(f"### {rec['category']} ({rec['priority']} priority)")
            lines.append("")
            lines.append(f"{rec['recommendation']}")
            lines.append("")
            lines.append("Action items:")
            for item in rec.get("action_items", []):
                lines.append(f"- {item}")
            lines.append("")

        return "\n".join(lines)

    def _generate_html_package(
        self, package: EvidencePackage, reports: List[EvidenceItem], output_dir: Path
    ) -> Path:
        """Generate HTML version of certification package."""
        html_file = output_dir / f"certification_package_{package.id}.html"

        # Combine all reports into HTML
        html_content = [
            "<html>",
            "<head>",
            "<title>Haven Health Passport - Certification Evidence Package</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 40px; }",
            "h1 { color: #2c3e50; }",
            "h2 { color: #34495e; }",
            "table { border-collapse: collapse; width: 100%; margin: 20px 0; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #f2f2f2; }",
            ".satisfied { color: green; }",
            ".unsatisfied { color: red; }",
            "</style>",
            "</head>",
            "<body>",
        ]

        for report in reports:
            if "content" in report.metadata:
                # Convert markdown to HTML (simple conversion)
                content = report.metadata["content"]
                # Simple markdown to HTML conversion
                content = content.replace("# ", "<h1>").replace("\n\n", "</h1>\n")
                content = content.replace("## ", "<h2>").replace("\n\n", "</h2>\n")
                content = content.replace("- ", "<li>").replace("\n", "</li>\n")
                html_content.append(content)
                html_content.append("<hr>")

        html_content.extend(["</body>", "</html>"])

        with open(html_file, "w") as f:
            f.write("\n".join(html_content))

        return html_file

    def _generate_pdf_package(
        self, package: EvidencePackage, reports: List[EvidenceItem], output_dir: Path
    ) -> Path:
        """Generate PDF version of certification package."""
        # For now, generate HTML and note that it should be converted to PDF
        html_file = self._generate_html_package(package, reports, output_dir)
        pdf_file = output_dir / f"certification_package_{package.id}.pdf"

        # Note: In production, use a library like weasyprint or pdfkit to convert HTML to PDF
        print(f"PDF generation pending. HTML version saved at: {html_file}")

        return pdf_file

    def _generate_markdown_package(
        self, package: EvidencePackage, reports: List[EvidenceItem], output_dir: Path
    ) -> Path:
        """Generate Markdown version of certification package."""
        md_file = output_dir / f"certification_package_{package.id}.md"

        md_content = []
        for report in reports:
            if "content" in report.metadata:
                md_content.append(report.metadata["content"])
                md_content.append("\n---\n")

        with open(md_file, "w") as f:
            f.write("\n".join(md_content))

        return md_file
