"""Issue analyzer for detecting compliance issues from evidence packages."""

from datetime import datetime
from typing import List

from .evidence_package import EvidencePackage
from .evidence_validator import EvidenceValidator
from .issue_tracker import (
    ComplianceIssue,
    IssueSeverity,
    IssueStatus,
    IssueTracker,
    IssueType,
)


class IssueAnalyzer:
    """Analyzes evidence packages to detect compliance issues."""

    def __init__(self, issue_tracker: IssueTracker):
        """Initialize issue analyzer.

        Args:
            issue_tracker: Issue tracker instance
        """
        self.issue_tracker = issue_tracker
        self.validator = EvidenceValidator()

    def analyze_package(self, package: EvidencePackage) -> List[ComplianceIssue]:
        """Analyze evidence package for compliance issues.

        Args:
            package: Evidence package to analyze

        Returns:
            List of detected issues
        """
        detected_issues = []

        # Check for missing evidence
        detected_issues.extend(self._check_missing_evidence(package))

        # Check for validation failures
        detected_issues.extend(self._check_validation_failures(package))

        # Check for requirement gaps
        detected_issues.extend(self._check_requirement_gaps(package))

        # Check for outdated evidence
        detected_issues.extend(self._check_outdated_evidence(package))

        # Check for incomplete requirements
        detected_issues.extend(self._check_incomplete_requirements(package))

        # Create issues in tracker
        for issue in detected_issues:
            self.issue_tracker.create_issue(issue)

        return detected_issues

    def _check_missing_evidence(
        self, package: EvidencePackage
    ) -> List[ComplianceIssue]:
        """Check for missing evidence issues."""
        issues = []

        for req in package.requirements.values():
            if req.mandatory and not req.evidence_items:
                issue = ComplianceIssue(
                    type=IssueType.MISSING_EVIDENCE,
                    severity=IssueSeverity.CRITICAL,
                    status=IssueStatus.OPEN,
                    title=f"Missing evidence for {req.requirement_id}",
                    description=f"Mandatory requirement '{req.title}' has no supporting evidence",
                    affected_standard=req.standard,
                    affected_requirements=[req.id],
                    created_by="IssueAnalyzer",
                    tags=[
                        "auto-detected",
                        "missing-evidence",
                        req.standard.value.lower(),
                    ],
                )
                issues.append(issue)

        return issues

    def _check_validation_failures(
        self, package: EvidencePackage
    ) -> List[ComplianceIssue]:
        """Check for evidence validation failures."""
        issues = []

        for evidence in package.evidence_items.values():
            validation_results = self.validator.validate_evidence_item(evidence)
            failures = [r for r in validation_results if not r.valid]

            if failures:
                critical_failures = [f for f in failures if f.severity == "critical"]
                severity = (
                    IssueSeverity.CRITICAL if critical_failures else IssueSeverity.HIGH
                )

                issue = ComplianceIssue(
                    type=IssueType.FAILED_VALIDATION,
                    severity=severity,
                    status=IssueStatus.OPEN,
                    title=f"Validation failed for {evidence.title}",
                    description=f"Evidence validation failed with {len(failures)} errors",
                    affected_evidence=[evidence.id],
                    created_by="IssueAnalyzer",
                    tags=["auto-detected", "validation-failure"],
                    metadata={
                        "failures": [f.message for f in failures[:5]]
                    },  # First 5 failures
                )
                issues.append(issue)

        return issues

    def _check_requirement_gaps(
        self, package: EvidencePackage
    ) -> List[ComplianceIssue]:
        """Check for requirement coverage gaps."""
        issues = []

        for standard in package.certification_standards:
            requirements = package.get_requirements_by_standard(standard)
            unsatisfied = [r for r in requirements if not r.satisfied and r.mandatory]

            if len(unsatisfied) > 3:  # More than 3 unsatisfied requirements
                issue = ComplianceIssue(
                    type=IssueType.REQUIREMENT_GAP,
                    severity=IssueSeverity.HIGH,
                    status=IssueStatus.OPEN,
                    title=f"Multiple requirement gaps for {standard.value}",
                    description=f"{len(unsatisfied)} mandatory requirements not satisfied for {standard.value}",
                    affected_standard=standard,
                    affected_requirements=[r.id for r in unsatisfied],
                    created_by="IssueAnalyzer",
                    tags=["auto-detected", "requirement-gap", standard.value.lower()],
                )
                issues.append(issue)

        return issues

    def _check_outdated_evidence(
        self, package: EvidencePackage
    ) -> List[ComplianceIssue]:
        """Check for outdated evidence."""
        issues = []
        now = datetime.utcnow()

        # Group outdated evidence by age
        very_old = []  # > 180 days
        old = []  # > 90 days

        for evidence in package.evidence_items.values():
            age = (now - evidence.created_at).days
            if age > 180:
                very_old.append(evidence)
            elif age > 90:
                old.append(evidence)

        if very_old:
            issue = ComplianceIssue(
                type=IssueType.DOCUMENTATION_GAP,
                severity=IssueSeverity.HIGH,
                status=IssueStatus.OPEN,
                title=f"{len(very_old)} evidence items are severely outdated",
                description="Evidence older than 180 days may not meet certification requirements",
                affected_evidence=[e.id for e in very_old[:10]],  # First 10
                created_by="IssueAnalyzer",
                tags=["auto-detected", "outdated-evidence"],
                metadata={
                    "oldest_days": max((now - e.created_at).days for e in very_old)
                },
            )
            issues.append(issue)

        if old:
            issue = ComplianceIssue(
                type=IssueType.DOCUMENTATION_GAP,
                severity=IssueSeverity.MEDIUM,
                status=IssueStatus.OPEN,
                title=f"{len(old)} evidence items are outdated",
                description="Evidence older than 90 days should be reviewed and updated",
                affected_evidence=[e.id for e in old[:10]],  # First 10
                created_by="IssueAnalyzer",
                tags=["auto-detected", "outdated-evidence"],
            )
            issues.append(issue)

        return issues

    def _check_incomplete_requirements(
        self, package: EvidencePackage
    ) -> List[ComplianceIssue]:
        """Check for requirements with insufficient evidence."""
        issues = []

        for req in package.requirements.values():
            if req.evidence_items and not req.satisfied:
                # Has some evidence but not satisfied
                issue = ComplianceIssue(
                    type=IssueType.REQUIREMENT_GAP,
                    severity=(
                        IssueSeverity.MEDIUM
                        if not req.mandatory
                        else IssueSeverity.HIGH
                    ),
                    status=IssueStatus.OPEN,
                    title=f"Incomplete evidence for {req.requirement_id}",
                    description=f"Requirement has {len(req.evidence_items)} evidence items but is not satisfied",
                    affected_standard=req.standard,
                    affected_requirements=[req.id],
                    affected_evidence=req.evidence_items,
                    created_by="IssueAnalyzer",
                    tags=["auto-detected", "incomplete-requirement"],
                )
                issues.append(issue)

        return issues
