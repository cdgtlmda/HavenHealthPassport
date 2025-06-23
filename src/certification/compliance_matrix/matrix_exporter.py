"""Compliance matrix exporter for various output formats."""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path

from .compliance_matrix import ComplianceMatrix
from .matrix_analyzer import ComplianceMatrixAnalyzer

logger = logging.getLogger(__name__)


class ComplianceMatrixExporter:
    """Exports compliance matrix to various formats."""

    def __init__(self, matrix: ComplianceMatrix):
        """Initialize exporter with a compliance matrix.

        Args:
            matrix: Compliance matrix to export
        """
        self.matrix = matrix
        self.analyzer = ComplianceMatrixAnalyzer(matrix)

    def export_to_csv(self, file_path: Path) -> None:
        """Export matrix to CSV format.

        Args:
            file_path: Path to save CSV file
        """
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "ID",
                "Standard",
                "Requirement ID",
                "Title",
                "Category",
                "Status",
                "Compliance %",
                "Implementation Type",
                "Risk Level",
                "Priority",
                "Mandatory",
                "Responsible Party",
                "Evidence Count",
                "Implementation Date",
                "Validation Date",
                "Notes",
            ]

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for entry in self.matrix.entries.values():
                writer.writerow(
                    {
                        "ID": entry.id,
                        "Standard": entry.standard.value,
                        "Requirement ID": entry.requirement_id,
                        "Title": entry.requirement_title,
                        "Category": entry.requirement_category,
                        "Status": entry.status.value,
                        "Compliance %": f"{entry.compliance_percentage:.1f}",
                        "Implementation Type": entry.implementation_type.value,
                        "Risk Level": entry.risk_level.value,
                        "Priority": entry.priority,
                        "Mandatory": "Yes" if entry.mandatory else "No",
                        "Responsible Party": entry.responsible_party,
                        "Evidence Count": len(entry.evidence_ids),
                        "Implementation Date": (
                            entry.implementation_date.strftime("%Y-%m-%d")
                            if entry.implementation_date
                            else ""
                        ),
                        "Validation Date": (
                            entry.validation_date.strftime("%Y-%m-%d")
                            if entry.validation_date
                            else ""
                        ),
                        "Notes": (
                            entry.notes[:100] + "..."
                            if len(entry.notes) > 100
                            else entry.notes
                        ),
                    }
                )

        logger.info(f"Exported matrix to CSV: {file_path}")

    def export_to_excel_format(self, file_path: Path) -> None:
        """Export matrix to Excel-compatible CSV with multiple sheets.

        Args:
            file_path: Path to save files
        """
        base_path = Path(file_path).with_suffix("")

        # Export main matrix
        self.export_to_csv(Path(f"{base_path}_matrix.csv"))

        # Export summary by standard
        self._export_standard_summary(Path(f"{base_path}_summary.csv"))

        # Export gap analysis
        self._export_gap_analysis(Path(f"{base_path}_gaps.csv"))

        # Export recommendations
        self._export_recommendations(Path(f"{base_path}_recommendations.csv"))

        logger.info(f"Exported Excel-format files to: {base_path}_*.csv")

    def export_to_json(self, file_path: Path, include_analysis: bool = True) -> None:
        """Export matrix to JSON format.

        Args:
            file_path: Path to save JSON file
            include_analysis: Include analysis results
        """
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        export_data = self.matrix.to_dict()

        if include_analysis:
            export_data["analysis"] = self.analyzer.analyze_compliance_readiness()

        with open(file_path, "w") as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Exported matrix to JSON: {file_path}")

    def export_to_html(self, file_path: Path) -> None:
        """Export matrix to HTML format with interactive features.

        Args:
            file_path: Path to save HTML file
        """
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate HTML content
        html_content = self._generate_html_report()

        with open(file_path, "w") as f:
            f.write(html_content)

        logger.info(f"Exported matrix to HTML: {file_path}")

    def export_to_markdown(self, file_path: Path) -> None:
        """Export matrix to Markdown format.

        Args:
            file_path: Path to save Markdown file
        """
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate executive summary
        summary = self.analyzer.generate_executive_summary()

        # Add detailed matrix table
        matrix_table = self._generate_markdown_table()

        content = f"{summary}\n\n{matrix_table}"

        with open(file_path, "w") as f:
            f.write(content)

        logger.info(f"Exported matrix to Markdown: {file_path}")

    def _export_standard_summary(self, file_path: Path) -> None:
        """Export summary by standard to CSV."""
        analysis = self.analyzer.analyze_compliance_readiness()

        with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "Standard",
                "Ready",
                "Compliance %",
                "Total Requirements",
                "Completed",
                "Blocking Items",
                "Estimated Days",
            ]

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for standard, data in analysis["standard_readiness"].items():
                writer.writerow(
                    {
                        "Standard": standard,
                        "Ready": "Yes" if data["ready"] else "No",
                        "Compliance %": f"{data['percentage']:.1f}",
                        "Total Requirements": data["total_requirements"],
                        "Completed": data["completed_requirements"],
                        "Blocking Items": data["blocking_items"],
                        "Estimated Days": data["estimated_days"],
                    }
                )

    def _export_gap_analysis(self, file_path: Path) -> None:
        """Export gap analysis to CSV."""
        analysis = self.analyzer.analyze_compliance_readiness()

        with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "Standard",
                "Requirement ID",
                "Title",
                "Risk Level",
                "Status",
                "Compliance %",
                "Missing Evidence",
                "Priority Score",
            ]

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for gap in analysis["critical_gaps"]:
                writer.writerow(
                    {
                        "Standard": gap["standard"],
                        "Requirement ID": gap["requirement_id"],
                        "Title": gap["title"],
                        "Risk Level": gap["risk_level"],
                        "Status": gap["status"],
                        "Compliance %": f"{gap['compliance_percentage']:.1f}",
                        "Missing Evidence": gap["missing_evidence"],
                        "Priority Score": gap["remediation_priority"],
                    }
                )

    def _export_recommendations(self, file_path: Path) -> None:
        """Export recommendations to CSV."""
        analysis = self.analyzer.analyze_compliance_readiness()

        with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["Type", "Priority", "Title", "Description", "Action Items"]

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for rec in analysis["recommendations"]:
                writer.writerow(
                    {
                        "Type": rec["type"],
                        "Priority": rec["priority"],
                        "Title": rec["title"],
                        "Description": rec["description"],
                        "Action Items": "; ".join(rec.get("action_items", [])),
                    }
                )

    def _generate_html_report(self) -> str:
        """Generate HTML report content."""
        analysis = self.analyzer.analyze_compliance_readiness()

        html_parts = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="UTF-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
            "<title>Compliance Matrix Report</title>",
            "<style>",
            self._get_html_styles(),
            "</style>",
            "</head>",
            "<body>",
            '<div class="container">',
            "<h1>Compliance Matrix Report</h1>",
            f'<p class="timestamp">Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</p>',
            # Overall metrics
            '<div class="metrics-section">',
            "<h2>Overall Compliance Status</h2>",
            '<div class="metrics-grid">',
            '<div class="metric-card">',
            f'<div class="metric-value">{analysis["overall_readiness"]:.1f}%</div>',
            '<div class="metric-label">Overall Readiness</div>',
            "</div>",
            '<div class="metric-card">',
            f'<div class="metric-value">{"Ready" if analysis["certification_ready"] else "Not Ready"}</div>',
            '<div class="metric-label">Certification Status</div>',
            "</div>",
            '<div class="metric-card">',
            f'<div class="metric-value">{analysis["time_estimates"]["total_days"]}</div>',
            '<div class="metric-label">Days to Compliance</div>',
            "</div>",
            "</div>",
            "</div>",
            # Standards breakdown
            '<div class="standards-section">',
            "<h2>Standards Compliance</h2>",
            '<table class="data-table">',
            "<thead>",
            "<tr>",
            "<th>Standard</th>",
            "<th>Readiness</th>",
            "<th>Progress</th>",
            "<th>Blocking Items</th>",
            "<th>Est. Days</th>",
            "</tr>",
            "</thead>",
            "<tbody>",
        ]

        # Add standard rows
        for standard, data in analysis["standard_readiness"].items():
            html_parts.extend(
                [
                    "<tr>",
                    f"<td>{standard.upper()}</td>",
                    f'<td>{"✓" if data["ready"] else "✗"}</td>',
                    f'<td><div class="progress-bar"><div class="progress-fill" style="width: {data["percentage"]:.1f}%"></div></div></td>',
                    f'<td>{data["blocking_items"]}</td>',
                    f'<td>{data["estimated_days"]}</td>',
                    "</tr>",
                ]
            )

        html_parts.extend(
            ["</tbody>", "</table>", "</div>", "</div>", "</body>", "</html>"]
        )

        return "\n".join(html_parts)

    def _get_html_styles(self) -> str:
        """Get CSS styles for HTML report."""
        return """
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f7fa;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        h1 {
            color: #2c3e50;
            margin-bottom: 10px;
        }
        .timestamp {
            color: #7f8c8d;
            font-size: 14px;
            margin-bottom: 30px;
        }
        .metrics-section, .standards-section {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }
        .metric-card {
            text-align: center;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 6px;
        }
        .metric-value {
            font-size: 32px;
            font-weight: bold;
            color: #3498db;
        }
        .metric-label {
            font-size: 14px;
            color: #7f8c8d;
            margin-top: 5px;
        }
        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        .data-table th, .data-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }
        .data-table th {
            background-color: #f8f9fa;
            font-weight: 600;
        }
        .progress-bar {
            width: 100%;
            height: 20px;
            background-color: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background-color: #3498db;
            transition: width 0.3s ease;
        }
        """

    def _generate_markdown_table(self) -> str:
        """Generate detailed matrix table in Markdown format."""
        lines = [
            "## Detailed Compliance Matrix",
            "",
            "| Standard | Requirement | Status | Compliance | Risk | Priority |",
            "|----------|-------------|--------|------------|------|----------|",
        ]

        for entry in sorted(
            self.matrix.entries.values(),
            key=lambda x: (x.standard.value, x.requirement_id),
        ):
            status_emoji = {
                "not_started": "🔴",
                "in_progress": "🟡",
                "implemented": "🟢",
                "validated": "✅",
                "certified": "✅",
                "not_applicable": "➖",
            }.get(entry.status.value, "❓")

            lines.append(
                f"| {entry.standard.value} | "
                f"{entry.requirement_id}: {entry.requirement_title[:40]}... | "
                f"{status_emoji} {entry.status.value} | "
                f"{entry.compliance_percentage:.0f}% | "
                f"{entry.risk_level.value} | "
                f"{entry.priority} |"
            )

        return "\n".join(lines)
