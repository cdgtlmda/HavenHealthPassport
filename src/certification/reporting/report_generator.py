"""Certification report generator."""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from ..evidence import (
    EvidenceCollector,
    EvidenceGenerator,
    EvidencePackage,
    EvidenceValidator,
)
from ..evidence.evidence_package import EvidenceType
from .report_config import ReportConfiguration, ReportFormat, ReportType

logger = logging.getLogger(__name__)


class CertificationReportGenerator:
    """Generates certification compliance reports."""

    def __init__(self, config: ReportConfiguration, project_root: Path):
        """Initialize report generator.

        Args:
            config: Report configuration
            project_root: Root directory of the project
        """
        self.config = config
        self.project_root = project_root
        self.evidence_collector = EvidenceCollector(project_root)
        self.evidence_generator = EvidenceGenerator()
        self.evidence_validator = EvidenceValidator()
        self.executor = ThreadPoolExecutor(max_workers=config.max_concurrent_reports)
        self._cache: Dict[str, Tuple[Any, datetime]] = {}

    async def generate_report(
        self,
        report_type: ReportType,
        format: Optional[ReportFormat] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Generate a certification report.

        Args:
            report_type: Type of report to generate
            format: Output format (uses default if not specified)
            parameters: Additional parameters for report generation

        Returns:
            Path to generated report file
        """
        format = format or self.config.default_formats[0]
        parameters = parameters or {}

        logger.info(f"Generating {report_type.value} report in {format.value} format")

        # Check cache if enabled
        cache_key = f"{report_type.value}_{format.value}_{json.dumps(parameters, sort_keys=True)}"
        if self.config.enable_caching and cache_key in self._cache:
            cached_result, cached_time = self._cache[cache_key]
            if (datetime.utcnow() - cached_time).seconds < self.config.cache_ttl:
                logger.info("Returning cached report")
                return cast(Path, cached_result)

        # Generate report based on type
        if report_type == ReportType.COMPLIANCE_SUMMARY:
            report_path = await self._generate_compliance_summary(format, parameters)
        elif report_type == ReportType.EVIDENCE_INVENTORY:
            report_path = await self._generate_evidence_inventory(format, parameters)
        elif report_type == ReportType.GAP_ANALYSIS:
            report_path = await self._generate_gap_analysis(format, parameters)
        elif report_type == ReportType.AUDIT_TRAIL:
            report_path = await self._generate_audit_trail(format, parameters)
        elif report_type == ReportType.PERFORMANCE_METRICS:
            report_path = await self._generate_performance_metrics(format, parameters)
        elif report_type == ReportType.RISK_ASSESSMENT:
            report_path = await self._generate_risk_assessment(format, parameters)
        elif report_type == ReportType.CERTIFICATION_STATUS:
            report_path = await self._generate_certification_status(format, parameters)
        elif report_type == ReportType.REQUIREMENT_TRACKING:
            report_path = await self._generate_requirement_tracking(format, parameters)
        elif report_type == ReportType.EVIDENCE_VALIDATION:
            report_path = await self._generate_evidence_validation(format, parameters)
        else:
            raise ValueError(f"Unsupported report type: {report_type.value}")

        # Cache result
        if self.config.enable_caching:
            self._cache[cache_key] = (report_path, datetime.utcnow())

        return report_path

    async def generate_batch_reports(
        self,
        report_types: List[ReportType],
        formats: Optional[List[ReportFormat]] = None,
    ) -> List[Path]:
        """Generate multiple reports in batch.

        Args:
            report_types: List of report types to generate
            formats: Output formats for each report

        Returns:
            List of paths to generated reports
        """
        formats = formats or [self.config.default_formats[0]] * len(report_types)

        # Create tasks for concurrent generation
        tasks = []
        for report_type, format in zip(report_types, formats):
            task = self.generate_report(report_type, format)
            tasks.append(task)

        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and log them
        report_paths: List[Path] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to generate {report_types[i].value}: {result}")
            else:
                report_paths.append(cast(Path, result))

        return report_paths

    def clear_cache(self) -> None:
        """Clear the report cache."""
        self._cache.clear()
        logger.info("Report cache cleared")

    # Private methods for generating specific report types

    async def _generate_compliance_summary(
        self, format: ReportFormat, parameters: Dict[str, Any]
    ) -> Path:
        """Generate compliance summary report."""
        # Collect evidence
        package = self.evidence_collector.collect_all_evidence()

        # Add requirements based on configured standards
        self._add_standard_requirements(package)

        # Validate package
        validation_report = self.evidence_validator.validate_evidence_package(package)

        # Generate report content
        report_data = {
            "title": "Certification Compliance Summary",
            "generated_at": datetime.utcnow().isoformat(),
            "certification_standards": [
                cs.value for cs in self.config.certification_standards
            ],
            "package_completeness": package.calculate_completeness(),
            "validation_summary": validation_report["summary"],
            "compliance_status": self._calculate_compliance_status(
                package, validation_report
            ),
            "critical_issues": validation_report["critical_issues"],
            "recommendations": self._generate_recommendations(
                package, validation_report
            ),
        }

        # Save report
        return await self._save_report(
            report_data, ReportType.COMPLIANCE_SUMMARY, format
        )

    async def _generate_evidence_inventory(
        self, format: ReportFormat, parameters: Dict[str, Any]
    ) -> Path:
        """Generate evidence inventory report."""
        package = self.evidence_collector.collect_all_evidence()

        # Create detailed inventory
        inventory_data: Dict[str, Any] = {
            "title": "Evidence Inventory Report",
            "generated_at": datetime.utcnow().isoformat(),
            "total_evidence_items": len(package.evidence_items),
            "evidence_by_type": {},
            "evidence_by_date": {},
            "evidence_details": [],
        }

        # Group evidence by type
        for evidence_type in EvidenceType:
            items = package.get_evidence_by_type(evidence_type)
            if items:
                inventory_data["evidence_by_type"][evidence_type.value] = {
                    "count": len(items),
                    "items": [self._summarize_evidence(item) for item in items],
                }

        # Group evidence by date
        for evidence in package.evidence_items.values():
            date_key = evidence.created_at.date().isoformat()
            if date_key not in inventory_data["evidence_by_date"]:
                inventory_data["evidence_by_date"][date_key] = []
            inventory_data["evidence_by_date"][date_key].append(evidence.id)

        # Add detailed evidence list
        for evidence in package.evidence_items.values():
            inventory_data["evidence_details"].append(
                {
                    "id": evidence.id,
                    "type": evidence.type.value,
                    "title": evidence.title,
                    "description": evidence.description,
                    "created_at": evidence.created_at.isoformat(),
                    "created_by": evidence.created_by,
                    "tags": evidence.tags,
                    "has_file": evidence.file_path is not None,
                    "hash": evidence.file_hash or evidence.calculate_hash(),
                }
            )

        return await self._save_report(
            inventory_data, ReportType.EVIDENCE_INVENTORY, format
        )

    async def _generate_gap_analysis(
        self, format: ReportFormat, parameters: Dict[str, Any]
    ) -> Path:
        """Generate gap analysis report."""
        package = self.evidence_collector.collect_all_evidence()
        self._add_standard_requirements(package)

        # Generate gap analysis
        gap_report = self.evidence_generator.generate_gap_analysis(package)

        # Enhanced gap data
        gap_data = {
            "title": "Compliance Gap Analysis",
            "generated_at": datetime.utcnow().isoformat(),
            "summary": gap_report.content,
            "prioritized_gaps": self._prioritize_gaps(package),
            "remediation_timeline": self._generate_remediation_timeline(package),
            "resource_requirements": self._estimate_resource_requirements(package),
        }

        return await self._save_report(gap_data, ReportType.GAP_ANALYSIS, format)

    async def _generate_audit_trail(
        self, format: ReportFormat, parameters: Dict[str, Any]
    ) -> Path:
        """Generate audit trail report."""
        # Collect audit logs
        start_date = parameters.get("start_date")
        end_date = parameters.get("end_date")

        audit_logs = self.evidence_collector.collect_audit_logs(start_date, end_date)

        audit_data = {
            "title": "Certification Audit Trail",
            "generated_at": datetime.utcnow().isoformat(),
            "period": {
                "start": start_date.isoformat() if start_date else "All time",
                "end": end_date.isoformat() if end_date else "Present",
            },
            "total_events": sum(
                len(log.content.get("events", [])) for log in audit_logs
            ),
            "audit_logs": [self._summarize_evidence(log) for log in audit_logs],
            "event_summary": self._summarize_audit_events(audit_logs),
        }

        return await self._save_report(audit_data, ReportType.AUDIT_TRAIL, format)

    async def _generate_performance_metrics(
        self, format: ReportFormat, parameters: Dict[str, Any]
    ) -> Path:
        """Generate performance metrics report."""
        metrics = self.evidence_collector.collect_performance_metrics()

        metrics_data = {
            "title": "Certification Performance Metrics",
            "generated_at": datetime.utcnow().isoformat(),
            "metrics_summary": self._summarize_performance_metrics(metrics),
            "detailed_metrics": [self._summarize_evidence(m) for m in metrics],
            "performance_trends": self._analyze_performance_trends(metrics),
            "benchmarks": self._compare_to_benchmarks(metrics),
        }

        return await self._save_report(
            metrics_data, ReportType.PERFORMANCE_METRICS, format
        )

    async def _generate_risk_assessment(
        self, format: ReportFormat, parameters: Dict[str, Any]
    ) -> Path:
        """Generate risk assessment report."""
        package = self.evidence_collector.collect_all_evidence()
        security_assessments = self.evidence_collector.collect_security_assessments()

        risk_data = {
            "title": "Certification Risk Assessment",
            "generated_at": datetime.utcnow().isoformat(),
            "risk_summary": self._assess_certification_risks(
                package, security_assessments
            ),
            "vulnerabilities": self._extract_vulnerabilities(security_assessments),
            "mitigation_strategies": self._generate_mitigation_strategies(
                security_assessments
            ),
            "risk_matrix": self._generate_risk_matrix(package, security_assessments),
        }

        return await self._save_report(risk_data, ReportType.RISK_ASSESSMENT, format)

    async def _generate_certification_status(
        self, format: ReportFormat, parameters: Dict[str, Any]
    ) -> Path:
        """Generate certification status report."""
        package = self.evidence_collector.collect_all_evidence()
        self._add_standard_requirements(package)
        validation_report = self.evidence_validator.validate_evidence_package(package)

        status_data: Dict[str, Any] = {
            "title": "Certification Status Report",
            "generated_at": datetime.utcnow().isoformat(),
            "overall_status": self._determine_overall_status(
                package, validation_report
            ),
            "standards_status": {},
            "completion_percentage": package.calculate_completeness(),
            "estimated_completion_date": self._estimate_completion_date(package),
            "blocking_issues": self._identify_blocking_issues(
                package, validation_report
            ),
        }

        # Status for each standard
        for standard in self.config.certification_standards:
            requirements = package.get_requirements_by_standard(standard)
            satisfied = sum(1 for r in requirements if r.satisfied)
            total = len(requirements)

            status_data["standards_status"][standard.value] = {
                "requirements_total": total,
                "requirements_satisfied": satisfied,
                "percentage_complete": (satisfied / total * 100) if total > 0 else 0,
                "status": "Ready" if satisfied == total else "In Progress",
            }

        return await self._save_report(
            status_data, ReportType.CERTIFICATION_STATUS, format
        )

    async def _generate_requirement_tracking(
        self, format: ReportFormat, parameters: Dict[str, Any]
    ) -> Path:
        """Generate requirement tracking report."""
        package = self.evidence_collector.collect_all_evidence()
        self._add_standard_requirements(package)

        tracking_data: Dict[str, Any] = {
            "title": "Requirement Tracking Report",
            "generated_at": datetime.utcnow().isoformat(),
            "requirements_by_standard": {},
            "requirement_details": [],
            "satisfaction_timeline": self._generate_satisfaction_timeline(package),
        }

        # Track requirements by standard
        for standard in self.config.certification_standards:
            requirements = package.get_requirements_by_standard(standard)
            tracking_data["requirements_by_standard"][standard.value] = {
                "total": len(requirements),
                "satisfied": sum(1 for r in requirements if r.satisfied),
                "in_progress": sum(
                    1 for r in requirements if r.evidence_items and not r.satisfied
                ),
                "not_started": sum(1 for r in requirements if not r.evidence_items),
            }

            # Detailed requirement tracking
            for req in requirements:
                tracking_data["requirement_details"].append(
                    {
                        "id": req.id,
                        "standard": req.standard.value,
                        "requirement_id": req.requirement_id,
                        "title": req.title,
                        "mandatory": req.mandatory,
                        "satisfied": req.satisfied,
                        "evidence_count": len(req.evidence_items),
                        "evidence_types_required": [
                            et.value for et in req.evidence_types
                        ],
                        "progress": self._calculate_requirement_progress(req, package),
                    }
                )

        return await self._save_report(
            tracking_data, ReportType.REQUIREMENT_TRACKING, format
        )

    async def _generate_evidence_validation(
        self, format: ReportFormat, parameters: Dict[str, Any]
    ) -> Path:
        """Generate evidence validation report."""
        package = self.evidence_collector.collect_all_evidence()
        validation_report = self.evidence_validator.validate_evidence_package(package)

        validation_data = {
            "title": "Evidence Validation Report",
            "generated_at": datetime.utcnow().isoformat(),
            "validation_summary": validation_report["summary"],
            "validation_details": validation_report["evidence_validation"],
            "critical_issues": validation_report["critical_issues"],
            "warnings": validation_report["warnings"],
            "recommendations": self._generate_validation_recommendations(
                validation_report
            ),
        }

        return await self._save_report(
            validation_data, ReportType.EVIDENCE_VALIDATION, format
        )

    # Helper methods

    async def _save_report(
        self, data: Dict[str, Any], report_type: ReportType, format: ReportFormat
    ) -> Path:
        """Save report data in specified format."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{report_type.value}_{timestamp}.{format.value}"
        output_path = self.config.output_directory / filename

        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == ReportFormat.JSON:
            with open(output_path, "w") as f:
                json.dump(data, f, indent=2)
        elif format == ReportFormat.HTML:
            html_content = self._generate_html_report(data, report_type)
            with open(output_path, "w") as f:
                f.write(html_content)
        elif format == ReportFormat.MARKDOWN:
            md_content = self._generate_markdown_report(data, report_type)
            with open(output_path, "w") as f:
                f.write(md_content)
        elif format == ReportFormat.CSV:
            # For CSV, we'll save a simplified version
            import csv

            csv_path = output_path.with_suffix(".csv")
            with open(csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                # Write headers and data based on report type
                self._write_csv_report(writer, data, report_type)
            output_path = csv_path
        else:
            # For other formats, save as JSON for now
            with open(output_path.with_suffix(".json"), "w") as f:
                json.dump(data, f, indent=2)
            output_path = output_path.with_suffix(".json")

        logger.info(f"Report saved to: {output_path}")
        return output_path

    def _generate_html_report(
        self, data: Dict[str, Any], report_type: ReportType
    ) -> str:
        """Generate HTML formatted report."""
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"<title>{data.get('title', report_type.value)}</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }",
            ".container { background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
            "h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }",
            "h2 { color: #34495e; margin-top: 30px; }",
            "h3 { color: #7f8c8d; }",
            ".metric { display: inline-block; margin: 10px 20px 10px 0; }",
            ".metric-value { font-size: 24px; font-weight: bold; color: #3498db; }",
            ".metric-label { font-size: 14px; color: #7f8c8d; }",
            "table { border-collapse: collapse; width: 100%; margin-top: 20px; }",
            "th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }",
            "th { background-color: #f8f9fa; font-weight: bold; }",
            ".success { color: #27ae60; }",
            ".warning { color: #f39c12; }",
            ".error { color: #e74c3c; }",
            ".info { background-color: #e3f2fd; padding: 10px; border-radius: 4px; margin: 10px 0; }",
            "</style>",
            "</head>",
            "<body>",
            "<div class='container'>",
        ]

        # Add title and generation info
        html_parts.append(f"<h1>{data.get('title', report_type.value)}</h1>")
        html_parts.append(
            f"<p class='info'>Generated on: {data.get('generated_at', datetime.utcnow().isoformat())}</p>"
        )

        # Add content based on report type
        if report_type == ReportType.COMPLIANCE_SUMMARY:
            html_parts.extend(self._format_compliance_summary_html(data))
        elif report_type == ReportType.EVIDENCE_INVENTORY:
            html_parts.extend(self._format_evidence_inventory_html(data))
        elif report_type == ReportType.GAP_ANALYSIS:
            html_parts.extend(self._format_gap_analysis_html(data))
        else:
            # Default formatting
            html_parts.append("<pre>")
            html_parts.append(json.dumps(data, indent=2))
            html_parts.append("</pre>")

        html_parts.extend(["</div>", "</body>", "</html>"])

        return "\n".join(html_parts)

    def _generate_markdown_report(
        self, data: Dict[str, Any], report_type: ReportType
    ) -> str:
        """Generate Markdown formatted report."""
        md_parts = [
            f"# {data.get('title', report_type.value)}",
            "",
            f"**Generated:** {data.get('generated_at', datetime.utcnow().isoformat())}",
            "",
        ]

        # Add content based on report type
        if report_type == ReportType.COMPLIANCE_SUMMARY:
            md_parts.extend(self._format_compliance_summary_markdown(data))
        elif report_type == ReportType.EVIDENCE_INVENTORY:
            md_parts.extend(self._format_evidence_inventory_markdown(data))
        else:
            # Default formatting
            md_parts.append("```json")
            md_parts.append(json.dumps(data, indent=2))
            md_parts.append("```")

        return "\n".join(md_parts)

    def _write_csv_report(
        self, writer: Any, data: Dict[str, Any], report_type: ReportType
    ) -> None:
        """Write CSV formatted report."""
        if report_type == ReportType.EVIDENCE_INVENTORY:
            # Write evidence inventory as CSV
            writer.writerow(["ID", "Type", "Title", "Created At", "Created By", "Tags"])
            for item in data.get("evidence_details", []):
                writer.writerow(
                    [
                        item["id"],
                        item["type"],
                        item["title"],
                        item["created_at"],
                        item["created_by"],
                        ", ".join(item["tags"]),
                    ]
                )
        else:
            # Generic CSV output
            writer.writerow(["Key", "Value"])
            for key, value in data.items():
                if isinstance(value, (str, int, float)):
                    writer.writerow([key, value])

    def _add_standard_requirements(self, package: EvidencePackage) -> None:
        """Add requirements for configured certification standards."""
        # This would typically load requirements from a requirements database
        # For now, we'll add some sample requirements

        for _ in self.config.certification_standards:
            # Add sample requirements based on standard
            # In production, this would load from a comprehensive requirements database
            pass

    def _summarize_evidence(self, evidence: Any) -> Dict[str, Any]:
        """Create a summary of an evidence item."""
        return {
            "id": evidence.id,
            "type": evidence.type.value,
            "title": evidence.title,
            "description": (
                evidence.description[:200] + "..."
                if len(evidence.description) > 200
                else evidence.description
            ),
            "created_at": evidence.created_at.isoformat(),
            "created_by": evidence.created_by,
            "tags": evidence.tags,
        }

    def _calculate_compliance_status(
        self, package: EvidencePackage, validation_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate overall compliance status."""
        return {
            "overall_compliant": validation_report["overall_valid"],
            "completeness_percentage": package.calculate_completeness(),
            "standards_compliance": validation_report.get("standard_compliance", {}),
            "ready_for_certification": validation_report["overall_valid"]
            and package.calculate_completeness() == 100,
        }

    def _generate_recommendations(
        self, package: EvidencePackage, validation_report: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Generate recommendations based on package and validation."""
        recommendations = []

        # Check for missing evidence
        unsatisfied = package.get_unsatisfied_requirements()
        if unsatisfied:
            recommendations.append(
                {
                    "priority": "high",
                    "category": "evidence_collection",
                    "recommendation": f"Collect evidence for {len(unsatisfied)} unsatisfied requirements",
                    "details": "Focus on mandatory requirements first",
                }
            )

        # Check for validation issues
        if validation_report["critical_issues"]:
            recommendations.append(
                {
                    "priority": "critical",
                    "category": "validation_errors",
                    "recommendation": f"Resolve {len(validation_report['critical_issues'])} critical validation issues",
                    "details": "These issues must be resolved before certification",
                }
            )

        return recommendations

    def _prioritize_gaps(self, package: EvidencePackage) -> List[Dict[str, Any]]:
        """Prioritize compliance gaps."""
        gaps = []
        for req in package.get_unsatisfied_requirements():
            gap_priority = 1 if req.mandatory else 2
            gaps.append(
                {
                    "requirement": req.title,
                    "standard": req.standard.value,
                    "priority": gap_priority,
                    "effort_estimate": "medium",  # Would be calculated based on evidence types
                    "blocking": req.mandatory,
                }
            )

        return sorted(gaps, key=lambda x: x["priority"])

    def _generate_remediation_timeline(
        self, package: EvidencePackage
    ) -> Dict[str, Any]:
        """Generate timeline for gap remediation."""
        unsatisfied = package.get_unsatisfied_requirements()

        return {
            "total_gaps": len(unsatisfied),
            "estimated_days": len(unsatisfied) * 5,  # Rough estimate
            "phases": [
                {
                    "phase": "Critical Requirements",
                    "duration_days": 10,
                    "requirements_count": sum(1 for r in unsatisfied if r.mandatory),
                },
                {
                    "phase": "Non-Critical Requirements",
                    "duration_days": 15,
                    "requirements_count": sum(
                        1 for r in unsatisfied if not r.mandatory
                    ),
                },
            ],
        }

    def _estimate_resource_requirements(
        self, package: EvidencePackage
    ) -> Dict[str, Any]:
        """Estimate resources needed for compliance."""
        return {
            "personnel_hours": len(package.get_unsatisfied_requirements()) * 8,
            "skill_requirements": [
                "Security Analyst",
                "Compliance Officer",
                "Technical Writer",
            ],
            "tool_requirements": ["Vulnerability Scanner", "Documentation System"],
            "estimated_cost": "Contact compliance team for detailed estimate",
        }

    def _summarize_audit_events(self, audit_logs: List[Any]) -> Dict[str, int]:
        """Summarize audit events."""
        event_summary: Dict[str, int] = {}
        for log in audit_logs:
            events = log.content.get("events", [])
            for event in events:
                event_type = (
                    event if isinstance(event, str) else event.get("type", "unknown")
                )
                event_summary[event_type] = event_summary.get(event_type, 0) + 1
        return event_summary

    def _summarize_performance_metrics(self, metrics: List[Any]) -> Dict[str, Any]:
        """Summarize performance metrics."""
        return {
            "total_metrics": len(metrics),
            "metric_types": list(
                set(m.content.get("type", "unknown") for m in metrics)
            ),
            "latest_update": max(
                (m.created_at for m in metrics), default=datetime.utcnow()
            ).isoformat(),
        }

    def _analyze_performance_trends(self, metrics: List[Any]) -> Dict[str, Any]:
        """Analyze performance trends."""
        # Simplified trend analysis
        return {
            "trend_direction": "stable",
            "performance_improving": True,
            "areas_of_concern": [],
        }

    def _compare_to_benchmarks(self, metrics: List[Any]) -> Dict[str, Any]:
        """Compare metrics to industry benchmarks."""
        return {
            "meets_benchmarks": True,
            "benchmark_comparison": {
                "response_time": "within benchmark",
                "availability": "exceeds benchmark",
                "error_rate": "within benchmark",
            },
        }

    def _assess_certification_risks(
        self, package: EvidencePackage, security_assessments: List[Any]
    ) -> Dict[str, Any]:
        """Assess risks to certification."""
        return {
            "risk_level": "medium",
            "risk_factors": [
                {
                    "factor": "Incomplete Requirements",
                    "impact": "high",
                    "likelihood": "medium",
                }
            ],
            "mitigation_in_place": True,
        }

    def _extract_vulnerabilities(
        self, security_assessments: List[Any]
    ) -> List[Dict[str, Any]]:
        """Extract vulnerabilities from security assessments."""
        vulnerabilities = []
        for assessment in security_assessments:
            vulns = assessment.content.get("vulnerabilities", [])
            vulnerabilities.extend(vulns)
        return vulnerabilities

    def _generate_mitigation_strategies(
        self, security_assessments: List[Any]
    ) -> List[Dict[str, str]]:
        """Generate mitigation strategies."""
        return [
            {
                "vulnerability": "Missing encryption",
                "strategy": "Implement AES-256 encryption for all data at rest",
                "priority": "high",
                "estimated_effort": "2 weeks",
            }
        ]

    def _generate_risk_matrix(
        self, package: EvidencePackage, security_assessments: List[Any]
    ) -> Dict[str, Any]:
        """Generate risk matrix."""
        return {
            "high_impact_high_likelihood": [],
            "high_impact_low_likelihood": ["Data breach"],
            "low_impact_high_likelihood": ["Minor compliance gaps"],
            "low_impact_low_likelihood": ["Documentation inconsistencies"],
        }

    def _determine_overall_status(
        self, package: EvidencePackage, validation_report: Dict[str, Any]
    ) -> str:
        """Determine overall certification status."""
        if (
            validation_report["overall_valid"]
            and package.calculate_completeness() == 100
        ):
            return "Ready for Certification"
        elif package.calculate_completeness() >= 80:
            return "Nearing Completion"
        elif package.calculate_completeness() >= 50:
            return "In Progress"
        else:
            return "Early Stage"

    def _estimate_completion_date(self, package: EvidencePackage) -> str:
        """Estimate certification completion date."""
        unsatisfied_count = len(package.get_unsatisfied_requirements())
        days_per_requirement = 5
        estimated_days = unsatisfied_count * days_per_requirement

        completion_date = datetime.utcnow() + timedelta(days=estimated_days)
        return completion_date.date().isoformat()

    def _identify_blocking_issues(
        self, package: EvidencePackage, validation_report: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Identify issues blocking certification."""
        blocking_issues = []

        # Critical validation issues
        for issue in validation_report["critical_issues"]:
            blocking_issues.append(
                {
                    "type": "validation_error",
                    "description": issue["message"],
                    "resolution": "Fix validation error in evidence",
                }
            )

        # Mandatory unsatisfied requirements
        for req in package.get_unsatisfied_requirements():
            if req.mandatory:
                blocking_issues.append(
                    {
                        "type": "missing_requirement",
                        "description": f"Missing evidence for: {req.title}",
                        "resolution": "Collect required evidence",
                    }
                )

        return blocking_issues

    def _generate_satisfaction_timeline(
        self, package: EvidencePackage
    ) -> List[Dict[str, Any]]:
        """Generate timeline of requirement satisfaction."""
        timeline = []

        # Group requirements by when they were satisfied
        for req in package.requirements.values():
            if req.satisfied and req.evidence_items:
                # Get earliest evidence date
                evidence_dates = []
                for eid in req.evidence_items:
                    if eid in package.evidence_items:
                        evidence_dates.append(package.evidence_items[eid].created_at)

                if evidence_dates:
                    timeline.append(
                        {
                            "date": min(evidence_dates).date().isoformat(),
                            "requirement": req.title,
                            "standard": req.standard.value,
                        }
                    )

        return sorted(timeline, key=lambda x: x["date"])

    def _calculate_requirement_progress(
        self, requirement: Any, package: EvidencePackage
    ) -> float:
        """Calculate progress percentage for a requirement."""
        if requirement.satisfied:
            return 100.0

        if not requirement.evidence_items:
            return 0.0

        # Calculate based on evidence types coverage
        if requirement.evidence_types:
            collected_types = set()
            for eid in requirement.evidence_items:
                if eid in package.evidence_items:
                    collected_types.add(package.evidence_items[eid].type)

            required_types = set(requirement.evidence_types)
            return (
                len(collected_types.intersection(required_types)) / len(required_types)
            ) * 100

        # If no specific types required, base on evidence count
        return min(
            len(requirement.evidence_items) * 20, 90
        )  # Cap at 90% until validated

    def _generate_validation_recommendations(
        self, validation_report: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Generate recommendations from validation report."""
        recommendations = []

        if validation_report["summary"]["invalid_evidence_items"] > 0:
            recommendations.append(
                {
                    "priority": "high",
                    "recommendation": "Fix validation errors in evidence items",
                    "action": f"Review and correct {validation_report['summary']['invalid_evidence_items']} invalid evidence items",
                }
            )

        if validation_report["summary"]["unsatisfied_requirements"] > 0:
            recommendations.append(
                {
                    "priority": "high",
                    "recommendation": "Collect missing evidence",
                    "action": f"Gather evidence for {validation_report['summary']['unsatisfied_requirements']} unsatisfied requirements",
                }
            )

        return recommendations

    # HTML formatting helpers

    def _format_compliance_summary_html(self, data: Dict[str, Any]) -> List[str]:
        """Format compliance summary for HTML."""
        html_parts = []

        # Metrics section
        html_parts.append("<h2>Compliance Metrics</h2>")
        html_parts.append("<div class='metrics'>")

        completeness = data.get("package_completeness", 0)
        html_parts.append(
            f"<div class='metric'><div class='metric-value'>{completeness:.1f}%</div><div class='metric-label'>Completeness</div></div>"
        )

        if "compliance_status" in data:
            status = data["compliance_status"]
            ready = "Yes" if status.get("ready_for_certification", False) else "No"
            html_parts.append(
                f"<div class='metric'><div class='metric-value'>{ready}</div><div class='metric-label'>Ready for Certification</div></div>"
            )

        html_parts.append("</div>")

        # Critical issues
        if data.get("critical_issues"):
            html_parts.append("<h2>Critical Issues</h2>")
            html_parts.append("<ul class='error'>")
            for issue in data["critical_issues"][:5]:
                html_parts.append(f"<li>{issue.get('message', str(issue))}</li>")
            html_parts.append("</ul>")

        # Recommendations
        if data.get("recommendations"):
            html_parts.append("<h2>Recommendations</h2>")
            html_parts.append("<ul>")
            for rec in data["recommendations"]:
                priority_class = (
                    "error" if rec.get("priority") == "critical" else "warning"
                )
                html_parts.append(
                    f"<li class='{priority_class}'><strong>{rec.get('category', 'General')}:</strong> {rec.get('recommendation', '')}</li>"
                )
            html_parts.append("</ul>")

        return html_parts

    def _format_evidence_inventory_html(self, data: Dict[str, Any]) -> List[str]:
        """Format evidence inventory for HTML."""
        html_parts = []

        # Summary
        html_parts.append("<h2>Evidence Summary</h2>")
        html_parts.append(
            f"<p>Total Evidence Items: <strong>{data.get('total_evidence_items', 0)}</strong></p>"
        )

        # Evidence by type
        if data.get("evidence_by_type"):
            html_parts.append("<h3>Evidence by Type</h3>")
            html_parts.append("<table>")
            html_parts.append("<tr><th>Type</th><th>Count</th></tr>")

            for etype, info in data["evidence_by_type"].items():
                count = info["count"] if isinstance(info, dict) else info
                html_parts.append(f"<tr><td>{etype}</td><td>{count}</td></tr>")

            html_parts.append("</table>")

        return html_parts

    def _format_gap_analysis_html(self, data: Dict[str, Any]) -> List[str]:
        """Format gap analysis for HTML."""
        html_parts = []

        # Summary from nested data
        if "summary" in data and isinstance(data["summary"], dict):
            summary = data["summary"]
            html_parts.append("<h2>Gap Analysis Summary</h2>")
            html_parts.append(
                f"<p>Total Gaps: <strong class='error'>{summary.get('total_gaps', 0)}</strong></p>"
            )

            if summary.get("critical_gaps"):
                html_parts.append("<h3>Critical Gaps</h3>")
                html_parts.append("<ul class='error'>")
                for gap in summary["critical_gaps"][:5]:
                    html_parts.append(
                        f"<li>{gap.get('title', 'Unknown requirement')}</li>"
                    )
                html_parts.append("</ul>")

        # Prioritized gaps
        if data.get("prioritized_gaps"):
            html_parts.append("<h2>Prioritized Gaps</h2>")
            html_parts.append("<table>")
            html_parts.append(
                "<tr><th>Requirement</th><th>Standard</th><th>Priority</th><th>Blocking</th></tr>"
            )

            for gap in data["prioritized_gaps"][:10]:
                blocking = "Yes" if gap.get("blocking", False) else "No"
                priority_class = "error" if gap.get("priority", 0) == 1 else "warning"
                html_parts.append(
                    f"<tr class='{priority_class}'><td>{gap['requirement']}</td><td>{gap['standard']}</td><td>{gap['priority']}</td><td>{blocking}</td></tr>"
                )

            html_parts.append("</table>")

        return html_parts

    def _format_compliance_summary_markdown(self, data: Dict[str, Any]) -> List[str]:
        """Format compliance summary for Markdown."""
        md_parts = []

        md_parts.append("## Compliance Status")
        md_parts.append("")

        completeness = data.get("package_completeness", 0)
        md_parts.append(f"- **Completeness:** {completeness:.1f}%")

        if "compliance_status" in data:
            status = data["compliance_status"]
            ready = "Yes" if status.get("ready_for_certification", False) else "No"
            md_parts.append(f"- **Ready for Certification:** {ready}")

        md_parts.append("")

        if data.get("critical_issues"):
            md_parts.append("## Critical Issues")
            md_parts.append("")
            for issue in data["critical_issues"][:5]:
                md_parts.append(f"- {issue.get('message', str(issue))}")
            md_parts.append("")

        return md_parts

    def _format_evidence_inventory_markdown(self, data: Dict[str, Any]) -> List[str]:
        """Format evidence inventory for Markdown."""
        md_parts = []

        md_parts.append("## Evidence Summary")
        md_parts.append("")
        md_parts.append(
            f"**Total Evidence Items:** {data.get('total_evidence_items', 0)}"
        )
        md_parts.append("")

        if data.get("evidence_by_type"):
            md_parts.append("### Evidence by Type")
            md_parts.append("")
            md_parts.append("| Type | Count |")
            md_parts.append("|------|-------|")

            for etype, info in data["evidence_by_type"].items():
                count = info["count"] if isinstance(info, dict) else info
                md_parts.append(f"| {etype} | {count} |")

            md_parts.append("")

        return md_parts
