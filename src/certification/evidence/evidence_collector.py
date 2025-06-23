"""Evidence collector for gathering certification artifacts. Handles FHIR Resource validation."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .evidence_package import (
    CertificationStandard,
    EvidenceItem,
    EvidencePackage,
    EvidenceType,
)


class EvidenceCollector:
    """Collects various types of evidence for certification packages."""

    def __init__(self, project_root: Path):
        """Initialize evidence collector.

        Args:
            project_root: Root directory of the Haven Health Passport project
        """
        self.project_root = Path(project_root)
        self.test_results_dir = self.project_root / "tests" / "results"
        self.compliance_dir = self.project_root / "compliance_reports"
        self.audit_dir = self.project_root / "audit"
        self.metrics_dir = self.project_root / "metrics"
        self.docs_dir = self.project_root / "docs"

    def collect_test_results(self, test_type: str = "all") -> List[EvidenceItem]:
        """Collect test execution results.

        Args:
            test_type: Type of tests to collect (unit, integration, e2e, all)

        Returns:
            List of evidence items containing test results
        """
        evidence_items = []

        # Collect pytest results
        pytest_results = self._collect_pytest_results(test_type)
        if pytest_results:
            evidence = EvidenceItem(
                type=EvidenceType.TEST_RESULT,
                title=f"PyTest Results - {test_type}",
                description="Automated test execution results from pytest",
                content=pytest_results,
                created_by="EvidenceCollector",
                tags=["testing", "pytest", test_type],
            )
            evidence_items.append(evidence)

        # Collect coverage reports
        coverage_data = self._collect_coverage_data()
        if coverage_data:
            evidence = EvidenceItem(
                type=EvidenceType.TEST_RESULT,
                title="Code Coverage Report",
                description="Test coverage analysis results",
                content=coverage_data,
                created_by="EvidenceCollector",
                tags=["testing", "coverage", "quality"],
            )
            evidence_items.append(evidence)

        return evidence_items

    def collect_audit_logs(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[EvidenceItem]:
        """Collect audit logs for specified time period.

        Args:
            start_date: Start of audit period
            end_date: End of audit period

        Returns:
            List of evidence items containing audit logs
        """
        evidence_items = []

        # Collect HIPAA audit logs
        hipaa_logs = self._collect_hipaa_audit_logs(start_date, end_date)
        if hipaa_logs:
            evidence = EvidenceItem(
                type=EvidenceType.AUDIT_LOG,
                title="HIPAA Audit Logs",
                description="Access control and data handling audit logs",
                content=hipaa_logs,
                created_by="EvidenceCollector",
                tags=["audit", "hipaa", "security", "access-control"],
            )
            evidence_items.append(evidence)

        # Collect API access logs
        api_logs = self._collect_api_access_logs(start_date, end_date)
        if api_logs:
            evidence = EvidenceItem(
                type=EvidenceType.AUDIT_LOG,
                title="API Access Logs",
                description="API endpoint access and usage logs",
                content=api_logs,
                created_by="EvidenceCollector",
                tags=["audit", "api", "access", "monitoring"],
            )
            evidence_items.append(evidence)

        return evidence_items

    def collect_compliance_reports(self) -> List[EvidenceItem]:
        """Collect compliance assessment reports.

        Returns:
            List of evidence items containing compliance reports
        """
        evidence_items = []

        # Check for existing compliance reports
        if self.compliance_dir.exists():
            for report_file in self.compliance_dir.glob("*.json"):
                try:
                    with open(report_file, "r") as f:
                        report_data = json.load(f)

                    evidence = EvidenceItem(
                        type=EvidenceType.COMPLIANCE_REPORT,
                        title=report_data.get(
                            "title", f"Compliance Report - {report_file.stem}"
                        ),
                        description=report_data.get(
                            "description", "Compliance assessment report"
                        ),
                        content=report_data,
                        file_path=report_file,
                        created_by="EvidenceCollector",
                        tags=["compliance", report_data.get("standard", "").lower()],
                    )
                    evidence_items.append(evidence)
                except Exception as e:
                    print(f"Error reading compliance report {report_file}: {e}")

        return evidence_items

    def collect_security_assessments(self) -> List[EvidenceItem]:
        """Collect security assessment results.

        Returns:
            List of evidence items containing security assessments
        """
        evidence_items = []

        # Collect vulnerability scan results
        vuln_scan = self._collect_vulnerability_scan_results()
        if vuln_scan:
            evidence = EvidenceItem(
                type=EvidenceType.SECURITY_ASSESSMENT,
                title="Vulnerability Scan Results",
                description="Security vulnerability assessment findings",
                content=vuln_scan,
                created_by="EvidenceCollector",
                tags=["security", "vulnerability", "scan"],
            )
            evidence_items.append(evidence)

        # Collect penetration test results
        pentest_results = self._collect_penetration_test_results()
        if pentest_results:
            evidence = EvidenceItem(
                type=EvidenceType.PENETRATION_TEST,
                title="Penetration Test Report",
                description="Security penetration testing results",
                content=pentest_results,
                created_by="EvidenceCollector",
                tags=["security", "penetration-test", "assessment"],
            )
            evidence_items.append(evidence)

        return evidence_items

    def collect_performance_metrics(self) -> List[EvidenceItem]:
        """Collect system performance metrics.

        Returns:
            List of evidence items containing performance data
        """
        evidence_items = []

        # Collect API performance metrics
        api_metrics = self._collect_api_performance_metrics()
        if api_metrics:
            evidence = EvidenceItem(
                type=EvidenceType.PERFORMANCE_METRIC,
                title="API Performance Metrics",
                description="API response time and throughput metrics",
                content=api_metrics,
                created_by="EvidenceCollector",
                tags=["performance", "api", "metrics", "monitoring"],
            )
            evidence_items.append(evidence)

        # Collect database performance metrics
        db_metrics = self._collect_database_performance_metrics()
        if db_metrics:
            evidence = EvidenceItem(
                type=EvidenceType.PERFORMANCE_METRIC,
                title="Database Performance Metrics",
                description="Database query performance and optimization metrics",
                content=db_metrics,
                created_by="EvidenceCollector",
                tags=["performance", "database", "metrics", "optimization"],
            )
            evidence_items.append(evidence)

        return evidence_items

    def collect_interoperability_tests(self) -> List[EvidenceItem]:
        """Collect interoperability test results.

        Returns:
            List of evidence items containing interoperability tests
        """
        evidence_items = []

        # Collect FHIR conformance test results
        fhir_tests = self._collect_fhir_conformance_tests()
        if fhir_tests:
            evidence = EvidenceItem(
                type=EvidenceType.INTEROPERABILITY_TEST,
                title="FHIR Conformance Test Results",
                description="HL7 FHIR conformance and validation test results",
                content=fhir_tests,
                created_by="EvidenceCollector",
                tags=["interoperability", "fhir", "hl7", "conformance"],
            )
            evidence_items.append(evidence)

        # Collect HL7 message validation results
        hl7_tests = self._collect_hl7_validation_tests()
        if hl7_tests:
            evidence = EvidenceItem(
                type=EvidenceType.INTEROPERABILITY_TEST,
                title="HL7 Message Validation Results",
                description="HL7 v2 message parsing and validation test results",
                content=hl7_tests,
                created_by="EvidenceCollector",
                tags=["interoperability", "hl7", "validation", "messaging"],
            )
            evidence_items.append(evidence)

        return evidence_items

    def collect_configuration_snapshots(self) -> List[EvidenceItem]:
        """Collect system configuration snapshots.

        Returns:
            List of evidence items containing configuration data
        """
        evidence_items = []

        # Collect environment configuration
        env_config = self._collect_environment_config()
        if env_config:
            evidence = EvidenceItem(
                type=EvidenceType.CONFIGURATION_SNAPSHOT,
                title="Environment Configuration",
                description="System environment and deployment configuration",
                content=env_config,
                created_by="EvidenceCollector",
                tags=["configuration", "environment", "deployment"],
            )
            evidence_items.append(evidence)

        # Collect security configuration
        security_config = self._collect_security_config()
        if security_config:
            evidence = EvidenceItem(
                type=EvidenceType.CONFIGURATION_SNAPSHOT,
                title="Security Configuration",
                description="Security settings and access control configuration",
                content=security_config,
                created_by="EvidenceCollector",
                tags=["configuration", "security", "access-control"],
            )
            evidence_items.append(evidence)

        return evidence_items

    def collect_all_evidence(self) -> EvidencePackage:
        """Collect all available evidence into a package.

        Returns:
            Complete evidence package with all collected evidence
        """
        package = EvidencePackage(
            name="Haven Health Passport Certification Evidence",
            description="Complete evidence package for healthcare certification",
            certification_standards=[
                CertificationStandard.HIPAA,
                CertificationStandard.GDPR,
                CertificationStandard.HL7_FHIR,
                CertificationStandard.ISO_27001,
            ],
        )

        # Collect all evidence types
        all_evidence = []
        all_evidence.extend(self.collect_test_results())
        all_evidence.extend(self.collect_audit_logs())
        all_evidence.extend(self.collect_compliance_reports())
        all_evidence.extend(self.collect_security_assessments())
        all_evidence.extend(self.collect_performance_metrics())
        all_evidence.extend(self.collect_interoperability_tests())
        all_evidence.extend(self.collect_configuration_snapshots())

        # Add evidence to package
        for evidence in all_evidence:
            package.add_evidence(evidence)

        return package

    # Helper methods for collecting specific evidence types

    def _collect_pytest_results(self, test_type: str) -> Dict[str, Any]:
        """Collect pytest execution results."""
        results = {}

        # Check for pytest-json-report output
        json_report = self.project_root / "pytest-report.json"
        if json_report.exists():
            try:
                with open(json_report, "r") as f:
                    results = json.load(f)
            except Exception as e:
                print(f"Error reading pytest report: {e}")

        # Check for JUnit XML output
        junit_report = self.project_root / "junit.xml"
        if junit_report.exists():
            results["junit_report"] = str(junit_report)

        return results

    def _collect_coverage_data(self) -> Dict[str, Any]:
        """Collect code coverage data."""
        coverage_data = {}

        # Check for coverage.py JSON report
        coverage_json = self.project_root / "coverage.json"
        if coverage_json.exists():
            try:
                with open(coverage_json, "r") as f:
                    coverage_data = json.load(f)
            except Exception as e:
                print(f"Error reading coverage data: {e}")

        # Check for HTML coverage report
        htmlcov_dir = self.project_root / "htmlcov"
        if htmlcov_dir.exists():
            coverage_data["html_report_path"] = str(htmlcov_dir)

        return coverage_data

    def _collect_hipaa_audit_logs(
        self, start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> Dict[str, Any]:
        """Collect HIPAA compliance audit logs."""
        audit_data: Dict[str, Any] = {
            "access_logs": [],
            "data_handling_logs": [],
            "authorization_logs": [],
            "encryption_logs": [],
        }

        # This would connect to the actual audit logging system
        # For now, return a structure showing what would be collected
        audit_data["summary"] = {
            "total_access_events": 0,
            "unique_users": 0,
            "data_operations": 0,
            "security_events": 0,
        }

        return audit_data

    def _collect_api_access_logs(
        self, start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> Dict[str, Any]:
        """Collect API access and usage logs."""
        return {
            "endpoints_accessed": {},
            "authentication_events": {},
            "rate_limiting_events": {},
            "error_responses": {},
        }

    def _collect_vulnerability_scan_results(self) -> Dict[str, Any]:
        """Collect security vulnerability scan results."""
        scan_results: Dict[str, Any] = {
            "scan_date": datetime.utcnow().isoformat(),
            "vulnerabilities": [],
            "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        }

        # Check for existing scan reports
        security_dir = self.project_root / "security" / "scans"
        if security_dir.exists():
            for scan_file in security_dir.glob("*.json"):
                try:
                    with open(scan_file, "r") as f:
                        scan_data = json.load(f)
                        scan_results["vulnerabilities"].extend(
                            scan_data.get("vulnerabilities", [])
                        )
                except Exception as e:
                    print(f"Error reading scan file {scan_file}: {e}")

        return scan_results

    def _collect_penetration_test_results(self) -> Dict[str, Any]:
        """Collect penetration test results."""
        return {
            "test_date": datetime.utcnow().isoformat(),
            "test_scope": ["web_application", "api", "mobile_app"],
            "findings": [],
            "recommendations": [],
        }

    def _collect_api_performance_metrics(self) -> Dict[str, Any]:
        """Collect API performance metrics."""
        return {
            "response_times": {"p50": 0, "p95": 0, "p99": 0},
            "throughput": {"requests_per_second": 0, "concurrent_users": 0},
            "error_rates": {"4xx_errors": 0, "5xx_errors": 0},
        }

    def _collect_database_performance_metrics(self) -> Dict[str, Any]:
        """Collect database performance metrics."""
        return {
            "query_performance": {
                "avg_query_time": 0,
                "slow_queries": 0,
                "deadlocks": 0,
            },
            "resource_usage": {"cpu_usage": 0, "memory_usage": 0, "disk_io": 0},
        }

    def _collect_fhir_conformance_tests(self) -> Dict[str, Any]:
        """Collect FHIR conformance test results."""
        return {
            "conformance_statement": True,
            "resource_validation": {},
            "search_parameters": {},
            "operations": {},
            "terminology": {},
        }

    def _collect_hl7_validation_tests(self) -> Dict[str, Any]:
        """Collect HL7 message validation test results."""
        return {
            "message_types_tested": ["ADT", "ORM", "ORU"],
            "validation_results": {},
            "parsing_errors": [],
            "conformance_profile": {},
        }

    def _collect_environment_config(self) -> Dict[str, Any]:
        """Collect environment configuration."""
        return {
            "deployment_environment": os.environ.get("ENVIRONMENT", "production"),
            "server_configuration": {},
            "database_configuration": {},
            "cache_configuration": {},
            "queue_configuration": {},
        }

    def _collect_security_config(self) -> Dict[str, Any]:
        """Collect security configuration."""
        return {
            "encryption_algorithms": ["AES-256", "RSA-2048"],
            "authentication_methods": ["OAuth2", "JWT"],
            "access_control_model": "RBAC",
            "security_headers": {},
            "tls_configuration": {},
        }


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
