"""Evidence validator for certification compliance verification."""

import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from .evidence_package import (
    CertificationStandard,
    EvidenceItem,
    EvidencePackage,
    EvidenceRequirement,
    EvidenceType,
)


class ValidationResult:
    """Result of evidence validation."""

    def __init__(self, valid: bool, message: str, severity: str = "info"):
        """Initialize validation result."""
        self.valid = valid
        self.message = message
        self.severity = severity  # info, warning, error, critical
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert validation result to dictionary."""
        return {
            "valid": self.valid,
            "message": self.message,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
        }


class EvidenceValidator:
    """Validates evidence items and packages for certification compliance."""

    def __init__(self) -> None:
        """Initialize evidence validator."""
        self.validation_rules = self._initialize_validation_rules()
        self.standard_requirements = self._initialize_standard_requirements()

    def validate_evidence_item(self, evidence: EvidenceItem) -> List[ValidationResult]:
        """Validate individual evidence item.

        Args:
            evidence: Evidence item to validate

        Returns:
            List of validation results
        """
        results = []

        # Basic validation
        results.extend(self._validate_basic_fields(evidence))

        # Type-specific validation
        if evidence.type in self.validation_rules:
            results.extend(self.validation_rules[evidence.type](evidence))

        # File validation
        if evidence.file_path:
            results.extend(self._validate_file_evidence(evidence))

        # Content validation
        results.extend(self._validate_content(evidence))

        # Timestamp validation
        results.extend(self._validate_timestamps(evidence))

        return results

    def validate_evidence_package(self, package: EvidencePackage) -> Dict[str, Any]:
        """Validate entire evidence package.

        Args:
            package: Evidence package to validate

        Returns:
            Dictionary containing validation results
        """
        validation_report: Dict[str, Any] = {
            "package_id": package.id,
            "validation_timestamp": datetime.utcnow().isoformat(),
            "overall_valid": True,
            "evidence_validation": {},
            "requirement_validation": {},
            "standard_compliance": {},
            "critical_issues": [],
            "warnings": [],
            "summary": {},
        }

        # Validate all evidence items
        for eid, evidence in package.evidence_items.items():
            results = self.validate_evidence_item(evidence)
            validation_report["evidence_validation"][eid] = {
                "title": evidence.title,
                "type": evidence.type.value,
                "valid": all(r.valid for r in results),
                "results": [r.to_dict() for r in results],
            }

            # Collect critical issues and warnings
            for result in results:
                if not result.valid:
                    if result.severity == "critical":
                        validation_report["critical_issues"].append(
                            {"evidence_id": eid, "message": result.message}
                        )
                        validation_report["overall_valid"] = False
                    elif result.severity == "warning":
                        validation_report["warnings"].append(
                            {"evidence_id": eid, "message": result.message}
                        )

        # Validate requirements
        for rid, requirement in package.requirements.items():
            req_results = self._validate_requirement(requirement, package)
            validation_report["requirement_validation"][rid] = {
                "requirement_id": requirement.requirement_id,
                "title": requirement.title,
                "valid": all(r.valid for r in req_results),
                "results": [r.to_dict() for r in req_results],
            }

        # Validate standard compliance
        for standard in package.certification_standards:
            compliance_results = self._validate_standard_compliance(standard, package)
            validation_report["standard_compliance"][
                standard.value
            ] = compliance_results

            if not compliance_results["compliant"]:
                validation_report["overall_valid"] = False

        # Generate summary
        validation_report["summary"] = self._generate_validation_summary(
            validation_report
        )

        return validation_report

    def validate_requirement_satisfaction(
        self, requirement: EvidenceRequirement, package: EvidencePackage
    ) -> bool:
        """Validate if requirement is properly satisfied.

        Args:
            requirement: Requirement to validate
            package: Evidence package containing evidence

        Returns:
            True if requirement is satisfied
        """
        # Check if requirement has evidence
        if not requirement.evidence_items:
            return False

        # Check if evidence exists and is valid
        valid_evidence = []
        for eid in requirement.evidence_items:
            if eid in package.evidence_items:
                evidence = package.evidence_items[eid]
                results = self.validate_evidence_item(evidence)
                if all(r.valid for r in results):
                    valid_evidence.append(evidence)

        if not valid_evidence:
            return False

        # Check if evidence types match requirement
        if requirement.evidence_types:
            evidence_types = {e.type for e in valid_evidence}
            required_types = set(requirement.evidence_types)
            if not evidence_types.intersection(required_types):
                return False

        return True

    # Validation helper methods

    def _initialize_validation_rules(self) -> Dict[EvidenceType, Any]:
        """Initialize type-specific validation rules."""
        return {
            EvidenceType.TEST_RESULT: self._validate_test_result,
            EvidenceType.AUDIT_LOG: self._validate_audit_log,
            EvidenceType.COMPLIANCE_REPORT: self._validate_compliance_report,
            EvidenceType.SECURITY_ASSESSMENT: self._validate_security_assessment,
            EvidenceType.PERFORMANCE_METRIC: self._validate_performance_metric,
            EvidenceType.INTEROPERABILITY_TEST: self._validate_interoperability_test,
            EvidenceType.CONFIGURATION_SNAPSHOT: self._validate_configuration_snapshot,
            EvidenceType.PENETRATION_TEST: self._validate_penetration_test,
            EvidenceType.CODE_REVIEW: self._validate_code_review,
        }

    def _initialize_standard_requirements(self) -> Dict[CertificationStandard, Dict]:
        """Initialize certification standard requirements."""
        return {
            CertificationStandard.HIPAA: {
                "required_evidence_types": [
                    EvidenceType.AUDIT_LOG,
                    EvidenceType.SECURITY_ASSESSMENT,
                    EvidenceType.CONFIGURATION_SNAPSHOT,
                ],
                "min_evidence_count": 10,
                "max_evidence_age_days": 90,
            },
            CertificationStandard.GDPR: {
                "required_evidence_types": [
                    EvidenceType.COMPLIANCE_REPORT,
                    EvidenceType.AUDIT_LOG,
                    EvidenceType.CONFIGURATION_SNAPSHOT,
                ],
                "min_evidence_count": 8,
                "max_evidence_age_days": 180,
            },
            CertificationStandard.HL7_FHIR: {
                "required_evidence_types": [
                    EvidenceType.INTEROPERABILITY_TEST,
                    EvidenceType.TEST_RESULT,
                    EvidenceType.API_DOCUMENTATION,
                ],
                "min_evidence_count": 5,
                "max_evidence_age_days": 365,
            },
            CertificationStandard.ISO_27001: {
                "required_evidence_types": [
                    EvidenceType.SECURITY_ASSESSMENT,
                    EvidenceType.RISK_ASSESSMENT,
                    EvidenceType.AUDIT_LOG,
                    EvidenceType.INCIDENT_REPORT,
                ],
                "min_evidence_count": 12,
                "max_evidence_age_days": 365,
            },
        }

    def _validate_basic_fields(self, evidence: EvidenceItem) -> List[ValidationResult]:
        """Validate basic required fields."""
        results = []

        if not evidence.title:
            results.append(
                ValidationResult(False, "Evidence title is required", "error")
            )

        if not evidence.description:
            results.append(
                ValidationResult(False, "Evidence description is required", "warning")
            )

        if not evidence.created_by:
            results.append(
                ValidationResult(False, "Evidence creator is required", "error")
            )

        if not evidence.content and not evidence.file_path:
            results.append(
                ValidationResult(
                    False, "Evidence must have content or file", "critical"
                )
            )

        return results

    def _validate_file_evidence(self, evidence: EvidenceItem) -> List[ValidationResult]:
        """Validate file-based evidence."""
        results = []

        if evidence.file_path:
            file_path = Path(evidence.file_path)

            if not file_path.exists():
                results.append(
                    ValidationResult(
                        False, f"Evidence file not found: {file_path}", "critical"
                    )
                )
            else:
                # Verify file hash if provided
                if evidence.file_hash:
                    try:
                        with open(file_path, "rb") as f:
                            calculated_hash = hashlib.sha256(f.read()).hexdigest()

                        if calculated_hash != evidence.file_hash:
                            results.append(
                                ValidationResult(
                                    False, "File hash mismatch", "critical"
                                )
                            )
                        else:
                            results.append(
                                ValidationResult(True, "File hash verified", "info")
                            )
                    except Exception as e:
                        results.append(
                            ValidationResult(
                                False, f"Error verifying file hash: {e}", "error"
                            )
                        )

                # Check file size
                file_size = file_path.stat().st_size
                if file_size == 0:
                    results.append(
                        ValidationResult(False, "Evidence file is empty", "error")
                    )
                elif file_size > 100 * 1024 * 1024:  # 100MB
                    results.append(
                        ValidationResult(
                            False, "Evidence file exceeds size limit", "warning"
                        )
                    )

        return results

    def _validate_content(self, evidence: EvidenceItem) -> List[ValidationResult]:
        """Validate evidence content structure."""
        results = []

        if evidence.content:
            # Check for required fields based on evidence type
            if evidence.type == EvidenceType.TEST_RESULT:
                required_fields = ["test_type", "results", "timestamp"]
            elif evidence.type == EvidenceType.AUDIT_LOG:
                required_fields = ["events", "user_actions", "timestamp"]
            elif evidence.type == EvidenceType.SECURITY_ASSESSMENT:
                required_fields = ["findings", "risk_level", "recommendations"]
            else:
                required_fields = []

            for field in required_fields:
                if field not in evidence.content:
                    results.append(
                        ValidationResult(
                            False, f"Missing required field: {field}", "error"
                        )
                    )

        return results

    def _validate_timestamps(self, evidence: EvidenceItem) -> List[ValidationResult]:
        """Validate evidence timestamps."""
        results = []

        # Check if evidence is too old
        age = datetime.utcnow() - evidence.created_at
        if age > timedelta(days=365):
            results.append(
                ValidationResult(False, "Evidence is older than 1 year", "warning")
            )

        # Check for future timestamps
        if evidence.created_at > datetime.utcnow():
            results.append(
                ValidationResult(False, "Evidence has future timestamp", "critical")
            )

        return results

    # Type-specific validation methods

    def _validate_test_result(self, evidence: EvidenceItem) -> List[ValidationResult]:
        """Validate test result evidence."""
        results = []

        if "results" in evidence.content:
            test_results = evidence.content["results"]
            if isinstance(test_results, dict):
                if "passed" in test_results and "failed" in test_results:
                    if test_results["failed"] > 0:
                        results.append(
                            ValidationResult(
                                False,
                                f"{test_results['failed']} tests failed",
                                "warning",
                            )
                        )
                    else:
                        results.append(
                            ValidationResult(True, "All tests passed", "info")
                        )

        return results

    def _validate_audit_log(self, evidence: EvidenceItem) -> List[ValidationResult]:
        """Validate audit log evidence."""
        results = []

        if "events" in evidence.content:
            events = evidence.content["events"]
            if isinstance(events, list) and len(events) == 0:
                results.append(
                    ValidationResult(False, "Audit log contains no events", "warning")
                )

        return results

    def _validate_compliance_report(
        self, evidence: EvidenceItem
    ) -> List[ValidationResult]:
        """Validate compliance report evidence."""
        results = []

        if "compliance_status" in evidence.content:
            status = evidence.content["compliance_status"]
            if status == "non_compliant":
                results.append(
                    ValidationResult(
                        False, "Compliance report shows non-compliance", "critical"
                    )
                )

        return results

    def _validate_security_assessment(
        self, evidence: EvidenceItem
    ) -> List[ValidationResult]:
        """Validate security assessment evidence."""
        results = []

        if "findings" in evidence.content:
            findings = evidence.content["findings"]
            if isinstance(findings, list):
                critical_findings = [
                    f for f in findings if f.get("severity") == "critical"
                ]
                if critical_findings:
                    results.append(
                        ValidationResult(
                            False,
                            f"{len(critical_findings)} critical security findings",
                            "critical",
                        )
                    )

        return results

    def _validate_performance_metric(
        self, evidence: EvidenceItem
    ) -> List[ValidationResult]:
        """Validate performance metric evidence."""
        results = []

        if "metrics" in evidence.content:
            metrics = evidence.content["metrics"]
            # Check for performance thresholds
            if "response_time_p95" in metrics:
                if metrics["response_time_p95"] > 2000:  # 2 seconds
                    results.append(
                        ValidationResult(
                            False, "Response time exceeds threshold", "warning"
                        )
                    )

        return results

    def _validate_interoperability_test(
        self, evidence: EvidenceItem
    ) -> List[ValidationResult]:
        """Validate interoperability test evidence."""
        results = []

        if "test_results" in evidence.content:
            test_results = evidence.content["test_results"]
            if "conformance" in test_results:
                if not test_results["conformance"]:
                    results.append(
                        ValidationResult(
                            False, "Interoperability test failed conformance", "error"
                        )
                    )

        return results

    def _validate_configuration_snapshot(
        self, evidence: EvidenceItem
    ) -> List[ValidationResult]:
        """Validate configuration snapshot evidence."""
        results = []

        required_configs = ["security_settings", "encryption_config", "access_controls"]
        for config in required_configs:
            if config not in evidence.content:
                results.append(
                    ValidationResult(False, f"Missing configuration: {config}", "error")
                )

        return results

    def _validate_penetration_test(
        self, evidence: EvidenceItem
    ) -> List[ValidationResult]:
        """Validate penetration test evidence."""
        results = []

        if "vulnerabilities" in evidence.content:
            vulns = evidence.content["vulnerabilities"]
            if isinstance(vulns, list):
                high_vulns = [
                    v for v in vulns if v.get("severity") in ["critical", "high"]
                ]
                if high_vulns:
                    results.append(
                        ValidationResult(
                            False,
                            f"{len(high_vulns)} high/critical vulnerabilities found",
                            "critical",
                        )
                    )

        return results

    def _validate_code_review(self, evidence: EvidenceItem) -> List[ValidationResult]:
        """Validate code review evidence."""
        results = []

        if "review_status" in evidence.content:
            if evidence.content["review_status"] != "approved":
                results.append(
                    ValidationResult(False, "Code review not approved", "warning")
                )

        return results

    def _validate_requirement(
        self, requirement: EvidenceRequirement, package: EvidencePackage
    ) -> List[ValidationResult]:
        """Validate a certification requirement."""
        results = []

        # Check if requirement has evidence
        if not requirement.evidence_items:
            if requirement.mandatory:
                results.append(
                    ValidationResult(
                        False,
                        f"Mandatory requirement '{requirement.title}' has no evidence",
                        "critical",
                    )
                )
            else:
                results.append(
                    ValidationResult(
                        False,
                        f"Requirement '{requirement.title}' has no evidence",
                        "warning",
                    )
                )
        else:
            # Validate linked evidence exists
            missing_evidence = []
            for eid in requirement.evidence_items:
                if eid not in package.evidence_items:
                    missing_evidence.append(eid)

            if missing_evidence:
                results.append(
                    ValidationResult(
                        False,
                        f"Requirement references missing evidence: {missing_evidence}",
                        "error",
                    )
                )

            # Check if requirement is properly satisfied
            if not self.validate_requirement_satisfaction(requirement, package):
                results.append(
                    ValidationResult(
                        False,
                        f"Requirement '{requirement.title}' not properly satisfied",
                        "error",
                    )
                )

        return results

    def _validate_standard_compliance(
        self, standard: CertificationStandard, package: EvidencePackage
    ) -> Dict[str, Any]:
        """Validate compliance with specific certification standard."""
        compliance_result: Dict[str, Any] = {
            "standard": standard.value,
            "compliant": True,
            "issues": [],
            "evidence_count": 0,
            "requirement_satisfaction": 0.0,
        }

        if standard in self.standard_requirements:
            std_reqs = self.standard_requirements[standard]

            # Check required evidence types
            evidence_types = set()
            for evidence in package.evidence_items.values():
                evidence_types.add(evidence.type)

                # Check evidence age
                age = datetime.utcnow() - evidence.created_at
                max_age = timedelta(days=std_reqs["max_evidence_age_days"])
                if age > max_age:
                    compliance_result["issues"].append(
                        f"Evidence '{evidence.title}' exceeds maximum age for {standard.value}"
                    )

            # Check if all required evidence types are present
            required_types = set(std_reqs["required_evidence_types"])
            missing_types = required_types - evidence_types
            if missing_types:
                compliance_result["compliant"] = False
                compliance_result["issues"].append(
                    f"Missing required evidence types: {[t.value for t in missing_types]}"
                )

            # Check minimum evidence count
            evidence_count = len(package.get_evidence_by_type(EvidenceType.TEST_RESULT))
            compliance_result["evidence_count"] = evidence_count

            if evidence_count < std_reqs["min_evidence_count"]:
                compliance_result["compliant"] = False
                compliance_result["issues"].append(
                    f"Insufficient evidence: {evidence_count} < {std_reqs['min_evidence_count']}"
                )

            # Calculate requirement satisfaction
            requirements = package.get_requirements_by_standard(standard)
            if requirements:
                satisfied = sum(1 for r in requirements if r.satisfied)
                compliance_result["requirement_satisfaction"] = (
                    satisfied / len(requirements)
                ) * 100

                if compliance_result["requirement_satisfaction"] < 100:
                    compliance_result["compliant"] = False
                    compliance_result["issues"].append(
                        f"Not all requirements satisfied: {compliance_result['requirement_satisfaction']:.1f}%"
                    )

        return compliance_result

    def _generate_validation_summary(
        self, validation_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate summary of validation results."""
        summary = {
            "total_evidence_items": len(validation_report["evidence_validation"]),
            "valid_evidence_items": 0,
            "invalid_evidence_items": 0,
            "total_requirements": len(validation_report["requirement_validation"]),
            "satisfied_requirements": 0,
            "unsatisfied_requirements": 0,
            "compliant_standards": 0,
            "non_compliant_standards": 0,
            "critical_issue_count": len(validation_report["critical_issues"]),
            "warning_count": len(validation_report["warnings"]),
        }

        # Count valid evidence
        for ev_result in validation_report["evidence_validation"].values():
            if ev_result["valid"]:
                summary["valid_evidence_items"] += 1
            else:
                summary["invalid_evidence_items"] += 1

        # Count satisfied requirements
        for req_result in validation_report["requirement_validation"].values():
            if req_result["valid"]:
                summary["satisfied_requirements"] += 1
            else:
                summary["unsatisfied_requirements"] += 1

        # Count compliant standards
        for std_result in validation_report["standard_compliance"].values():
            if std_result["compliant"]:
                summary["compliant_standards"] += 1
            else:
                summary["non_compliant_standards"] += 1

        return summary
