"""Issue tracking system for certification compliance."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .evidence_package import CertificationStandard


class IssueType(Enum):
    """Types of compliance issues."""

    MISSING_EVIDENCE = "missing_evidence"
    FAILED_VALIDATION = "failed_validation"
    REQUIREMENT_GAP = "requirement_gap"
    SECURITY_VULNERABILITY = "security_vulnerability"
    PERFORMANCE_ISSUE = "performance_issue"
    DOCUMENTATION_GAP = "documentation_gap"
    CONFIGURATION_ERROR = "configuration_error"
    INTEROPERABILITY_FAILURE = "interoperability_failure"
    COMPLIANCE_VIOLATION = "compliance_violation"


class IssueSeverity(Enum):
    """Severity levels for compliance issues."""

    CRITICAL = "critical"  # Blocks certification
    HIGH = "high"  # Must fix before certification
    MEDIUM = "medium"  # Should fix before certification
    LOW = "low"  # Nice to fix
    INFO = "info"  # Informational only


class IssueStatus(Enum):
    """Status of compliance issues."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    VERIFIED = "verified"
    CLOSED = "closed"
    DEFERRED = "deferred"
    WONT_FIX = "wont_fix"


@dataclass
class ComplianceIssue:
    """Individual compliance issue."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: IssueType = IssueType.MISSING_EVIDENCE
    severity: IssueSeverity = IssueSeverity.MEDIUM
    status: IssueStatus = IssueStatus.OPEN
    title: str = ""
    description: str = ""
    affected_standard: Optional[CertificationStandard] = None
    affected_requirements: List[str] = field(default_factory=list)
    affected_evidence: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    assigned_to: Optional[str] = None
    resolution: Optional[str] = None
    resolution_date: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert issue to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "severity": self.severity.value,
            "status": self.status.value,
            "title": self.title,
            "description": self.description,
            "affected_standard": (
                self.affected_standard.value if self.affected_standard else None
            ),
            "affected_requirements": self.affected_requirements,
            "affected_evidence": self.affected_evidence,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
            "assigned_to": self.assigned_to,
            "resolution": self.resolution,
            "resolution_date": (
                self.resolution_date.isoformat() if self.resolution_date else None
            ),
            "tags": self.tags,
            "metadata": self.metadata,
        }

    def update_status(
        self, new_status: IssueStatus, resolution: Optional[str] = None
    ) -> None:
        """Update issue status."""
        self.status = new_status
        self.updated_at = datetime.utcnow()

        if new_status in [IssueStatus.RESOLVED, IssueStatus.CLOSED]:
            self.resolution = resolution or "Issue resolved"
            self.resolution_date = datetime.utcnow()

    def assign_to(self, assignee: str) -> None:
        """Assign issue to a person."""
        self.assigned_to = assignee
        self.updated_at = datetime.utcnow()

    def add_tag(self, tag: str) -> None:
        """Add a tag to the issue."""
        if tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.utcnow()

    def is_blocking(self) -> bool:
        """Check if issue blocks certification."""
        return self.severity in [IssueSeverity.CRITICAL, IssueSeverity.HIGH]


class IssueTracker:
    """Tracks and manages certification compliance issues."""

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize issue tracker.

        Args:
            storage_path: Path to store issue data
        """
        self.storage_path = storage_path or Path("certification/issues")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.issues: Dict[str, ComplianceIssue] = {}
        self._load_issues()

    def create_issue(self, issue: ComplianceIssue) -> str:
        """Create a new compliance issue.

        Args:
            issue: Compliance issue to create

        Returns:
            Issue ID
        """
        self.issues[issue.id] = issue
        self._save_issues()
        return issue.id

    def get_issue(self, issue_id: str) -> Optional[ComplianceIssue]:
        """Get issue by ID.

        Args:
            issue_id: Issue ID

        Returns:
            Compliance issue or None
        """
        return self.issues.get(issue_id)

    def update_issue(self, issue_id: str, **kwargs: Any) -> bool:
        """Update issue properties.

        Args:
            issue_id: Issue ID
            **kwargs: Properties to update

        Returns:
            True if updated successfully
        """
        if issue_id in self.issues:
            issue = self.issues[issue_id]
            for key, value in kwargs.items():
                if hasattr(issue, key):
                    setattr(issue, key, value)
            issue.updated_at = datetime.utcnow()
            self._save_issues()
            return True
        return False

    def get_issues_by_status(self, status: IssueStatus) -> List[ComplianceIssue]:
        """Get all issues with specific status.

        Args:
            status: Issue status to filter by

        Returns:
            List of issues
        """
        return [i for i in self.issues.values() if i.status == status]

    def get_issues_by_severity(self, severity: IssueSeverity) -> List[ComplianceIssue]:
        """Get all issues with specific severity.

        Args:
            severity: Issue severity to filter by

        Returns:
            List of issues
        """
        return [i for i in self.issues.values() if i.severity == severity]

    def get_issues_by_standard(
        self, standard: CertificationStandard
    ) -> List[ComplianceIssue]:
        """Get all issues for a specific certification standard.

        Args:
            standard: Certification standard

        Returns:
            List of issues
        """
        return [i for i in self.issues.values() if i.affected_standard == standard]

    def get_blocking_issues(self) -> List[ComplianceIssue]:
        """Get all issues that block certification.

        Returns:
            List of blocking issues
        """
        return [
            i
            for i in self.issues.values()
            if i.is_blocking() and i.status != IssueStatus.RESOLVED
        ]

    def get_open_issues(self) -> List[ComplianceIssue]:
        """Get all open issues.

        Returns:
            List of open issues
        """
        open_statuses = [IssueStatus.OPEN, IssueStatus.IN_PROGRESS]
        return [i for i in self.issues.values() if i.status in open_statuses]

    def get_issue_statistics(self) -> Dict[str, Any]:
        """Get issue statistics.

        Returns:
            Dictionary with issue statistics
        """
        stats: Dict[str, Any] = {
            "total_issues": len(self.issues),
            "by_status": {},
            "by_severity": {},
            "by_type": {},
            "by_standard": {},
            "blocking_issues": len(self.get_blocking_issues()),
            "resolution_rate": 0,
        }

        # Count by status
        for status in IssueStatus:
            count = len(self.get_issues_by_status(status))
            if count > 0:
                stats["by_status"][status.value] = count

        # Count by severity
        for severity in IssueSeverity:
            count = len(self.get_issues_by_severity(severity))
            if count > 0:
                stats["by_severity"][severity.value] = count

        # Count by type
        for issue in self.issues.values():
            type_key = issue.type.value
            stats["by_type"][type_key] = stats["by_type"].get(type_key, 0) + 1

        # Count by standard
        for issue in self.issues.values():
            if issue.affected_standard:
                std_key = issue.affected_standard.value
                stats["by_standard"][std_key] = stats["by_standard"].get(std_key, 0) + 1

        # Calculate resolution rate
        resolved = len(
            [
                i
                for i in self.issues.values()
                if i.status in [IssueStatus.RESOLVED, IssueStatus.CLOSED]
            ]
        )
        if stats["total_issues"] > 0:
            stats["resolution_rate"] = (resolved / stats["total_issues"]) * 100

        return stats

    def generate_issue_report(self) -> Dict[str, Any]:
        """Generate comprehensive issue report.

        Returns:
            Issue report data
        """
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "statistics": self.get_issue_statistics(),
            "critical_issues": [
                i.to_dict() for i in self.get_issues_by_severity(IssueSeverity.CRITICAL)
            ],
            "blocking_issues": [i.to_dict() for i in self.get_blocking_issues()],
            "recent_issues": [],
            "overdue_issues": [],
        }

        # Get recent issues (created in last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent = [i for i in self.issues.values() if i.created_at >= seven_days_ago]
        report["recent_issues"] = [
            i.to_dict()
            for i in sorted(recent, key=lambda x: x.created_at, reverse=True)[:10]
        ]

        # Get overdue issues (open for more than 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        overdue = [i for i in self.get_open_issues() if i.created_at <= thirty_days_ago]
        report["overdue_issues"] = [i.to_dict() for i in overdue]

        return report

    def _save_issues(self) -> None:
        """Save issues to storage."""
        issues_file = self.storage_path / "issues.json"
        issues_data = {
            "version": "1.0",
            "updated_at": datetime.utcnow().isoformat(),
            "issues": {id: issue.to_dict() for id, issue in self.issues.items()},
        }

        with open(issues_file, "w") as f:
            json.dump(issues_data, f, indent=2)

    def _load_issues(self) -> None:
        """Load issues from storage."""
        issues_file = self.storage_path / "issues.json"

        if issues_file.exists():
            try:
                with open(issues_file, "r") as f:
                    issues_data = json.load(f)

                for issue_id, issue_dict in issues_data.get("issues", {}).items():
                    issue = ComplianceIssue(
                        id=issue_dict["id"],
                        type=IssueType(issue_dict["type"]),
                        severity=IssueSeverity(issue_dict["severity"]),
                        status=IssueStatus(issue_dict["status"]),
                        title=issue_dict["title"],
                        description=issue_dict["description"],
                        affected_standard=(
                            CertificationStandard(issue_dict["affected_standard"])
                            if issue_dict.get("affected_standard")
                            else None
                        ),
                        affected_requirements=issue_dict.get(
                            "affected_requirements", []
                        ),
                        affected_evidence=issue_dict.get("affected_evidence", []),
                        created_at=datetime.fromisoformat(issue_dict["created_at"]),
                        updated_at=datetime.fromisoformat(issue_dict["updated_at"]),
                        created_by=issue_dict["created_by"],
                        assigned_to=issue_dict.get("assigned_to"),
                        resolution=issue_dict.get("resolution"),
                        resolution_date=(
                            datetime.fromisoformat(issue_dict["resolution_date"])
                            if issue_dict.get("resolution_date")
                            else None
                        ),
                        tags=issue_dict.get("tags", []),
                        metadata=issue_dict.get("metadata", {}),
                    )
                    self.issues[issue_id] = issue
            except Exception as e:
                print(f"Error loading issues: {e}")
