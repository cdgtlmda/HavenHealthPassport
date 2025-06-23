"""Remediation process management for compliance issues."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .issue_tracker import ComplianceIssue, IssueSeverity, IssueType


class RemediationPriority(Enum):
    """Priority levels for remediation actions."""

    IMMEDIATE = "immediate"  # Must fix within 24 hours
    URGENT = "urgent"  # Must fix within 1 week
    HIGH = "high"  # Must fix within 2 weeks
    MEDIUM = "medium"  # Must fix within 1 month
    LOW = "low"  # Can fix within 3 months


class RemediationStatus(Enum):
    """Status of remediation actions."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    TESTING = "testing"
    COMPLETED = "completed"
    VERIFIED = "verified"
    FAILED = "failed"
    DEFERRED = "deferred"


class RemediationType(Enum):
    """Types of remediation actions."""

    COLLECT_EVIDENCE = "collect_evidence"
    UPDATE_DOCUMENTATION = "update_documentation"
    FIX_VALIDATION = "fix_validation"
    IMPLEMENT_CONTROL = "implement_control"
    UPDATE_CONFIGURATION = "update_configuration"
    PERFORM_ASSESSMENT = "perform_assessment"
    REVIEW_PROCESS = "review_process"
    TRAINING = "training"


@dataclass
class RemediationAction:
    """Individual remediation action."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    issue_id: str = ""
    type: RemediationType = RemediationType.COLLECT_EVIDENCE
    priority: RemediationPriority = RemediationPriority.MEDIUM
    status: RemediationStatus = RemediationStatus.PLANNED
    title: str = ""
    description: str = ""
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    started_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    estimated_hours: float = 0
    actual_hours: float = 0
    dependencies: List[str] = field(default_factory=list)  # Other action IDs
    verification_steps: List[str] = field(default_factory=list)
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert action to dictionary."""
        return {
            "id": self.id,
            "issue_id": self.issue_id,
            "type": self.type.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "title": self.title,
            "description": self.description,
            "assigned_to": self.assigned_to,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "started_date": (
                self.started_date.isoformat() if self.started_date else None
            ),
            "completed_date": (
                self.completed_date.isoformat() if self.completed_date else None
            ),
            "estimated_hours": self.estimated_hours,
            "actual_hours": self.actual_hours,
            "dependencies": self.dependencies,
            "verification_steps": self.verification_steps,
            "notes": self.notes,
            "metadata": self.metadata,
        }

    def is_overdue(self) -> bool:
        """Check if action is overdue."""
        if self.due_date and self.status not in [
            RemediationStatus.COMPLETED,
            RemediationStatus.VERIFIED,
        ]:
            return datetime.utcnow() > self.due_date
        return False

    def calculate_time_remaining(self) -> Optional[timedelta]:
        """Calculate time remaining until due date."""
        if self.due_date and self.status not in [
            RemediationStatus.COMPLETED,
            RemediationStatus.VERIFIED,
        ]:
            return self.due_date - datetime.utcnow()
        return None


@dataclass
class RemediationPlan:
    """Complete remediation plan for addressing compliance issues."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    actions: Dict[str, RemediationAction] = field(default_factory=dict)
    issue_mappings: Dict[str, List[str]] = field(
        default_factory=dict
    )  # issue_id -> [action_ids]

    def add_action(self, action: RemediationAction) -> None:
        """Add remediation action to plan."""
        self.actions[action.id] = action
        self.updated_at = datetime.utcnow()

        # Update issue mappings
        if action.issue_id:
            if action.issue_id not in self.issue_mappings:
                self.issue_mappings[action.issue_id] = []
            if action.id not in self.issue_mappings[action.issue_id]:
                self.issue_mappings[action.issue_id].append(action.id)

    def get_actions_for_issue(self, issue_id: str) -> List[RemediationAction]:
        """Get all actions for a specific issue."""
        action_ids = self.issue_mappings.get(issue_id, [])
        return [self.actions[aid] for aid in action_ids if aid in self.actions]

    def get_actions_by_status(
        self, status: RemediationStatus
    ) -> List[RemediationAction]:
        """Get all actions with specific status."""
        return [a for a in self.actions.values() if a.status == status]

    def get_actions_by_priority(
        self, priority: RemediationPriority
    ) -> List[RemediationAction]:
        """Get all actions with specific priority."""
        return [a for a in self.actions.values() if a.priority == priority]

    def get_overdue_actions(self) -> List[RemediationAction]:
        """Get all overdue actions."""
        return [a for a in self.actions.values() if a.is_overdue()]

    def get_assigned_actions(self, assignee: str) -> List[RemediationAction]:
        """Get all actions assigned to specific person."""
        return [a for a in self.actions.values() if a.assigned_to == assignee]

    def calculate_progress(self) -> Dict[str, Any]:
        """Calculate overall remediation progress."""
        total = len(self.actions)
        if total == 0:
            return {"total": 0, "completed": 0, "progress": 0}

        completed = len(
            [
                a
                for a in self.actions.values()
                if a.status in [RemediationStatus.COMPLETED, RemediationStatus.VERIFIED]
            ]
        )
        in_progress = len(
            [
                a
                for a in self.actions.values()
                if a.status == RemediationStatus.IN_PROGRESS
            ]
        )

        return {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": total - completed - in_progress,
            "progress": (completed / total) * 100,
            "overdue": len(self.get_overdue_actions()),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
            "progress": self.calculate_progress(),
            "actions": {aid: a.to_dict() for aid, a in self.actions.items()},
            "issue_mappings": self.issue_mappings,
        }


class RemediationManager:
    """Manages the remediation process for compliance issues."""

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize remediation manager.

        Args:
            storage_path: Path to store remediation data
        """
        self.storage_path = storage_path or Path("certification/remediation")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.plans: Dict[str, RemediationPlan] = {}
        self._load_plans()

    def create_plan(self, plan: RemediationPlan) -> str:
        """Create a new remediation plan.

        Args:
            plan: Remediation plan to create

        Returns:
            Plan ID
        """
        self.plans[plan.id] = plan
        self._save_plans()
        return plan.id

    def get_plan(self, plan_id: str) -> Optional[RemediationPlan]:
        """Get remediation plan by ID."""
        return self.plans.get(plan_id)

    def create_remediation_for_issue(
        self, issue: ComplianceIssue, plan_id: Optional[str] = None
    ) -> List[RemediationAction]:
        """Create remediation actions for a compliance issue.

        Args:
            issue: Compliance issue to remediate
            plan_id: ID of plan to add actions to (creates new if None)

        Returns:
            List of created remediation actions
        """
        actions = []

        # Determine priority based on issue severity
        priority_map = {
            IssueSeverity.CRITICAL: RemediationPriority.IMMEDIATE,
            IssueSeverity.HIGH: RemediationPriority.URGENT,
            IssueSeverity.MEDIUM: RemediationPriority.HIGH,
            IssueSeverity.LOW: RemediationPriority.MEDIUM,
            IssueSeverity.INFO: RemediationPriority.LOW,
        }
        priority = priority_map.get(issue.severity, RemediationPriority.MEDIUM)

        # Create actions based on issue type
        if issue.type == IssueType.MISSING_EVIDENCE:
            action = RemediationAction(
                issue_id=issue.id,
                type=RemediationType.COLLECT_EVIDENCE,
                priority=priority,
                title=f"Collect evidence for {issue.title}",
                description=f"Collect required evidence to address: {issue.description}",
                due_date=self._calculate_due_date(priority),
                verification_steps=[
                    "Collect required evidence items",
                    "Validate evidence meets requirements",
                    "Link evidence to requirement",
                    "Verify requirement satisfaction",
                ],
            )
            actions.append(action)

        elif issue.type == IssueType.FAILED_VALIDATION:
            action = RemediationAction(
                issue_id=issue.id,
                type=RemediationType.FIX_VALIDATION,
                priority=priority,
                title=f"Fix validation issues for {issue.title}",
                description=f"Correct validation failures: {issue.description}",
                due_date=self._calculate_due_date(priority),
                verification_steps=[
                    "Identify validation failures",
                    "Correct invalid data/configuration",
                    "Re-run validation tests",
                    "Verify all validations pass",
                ],
            )
            actions.append(action)

        elif issue.type == IssueType.REQUIREMENT_GAP:
            action = RemediationAction(
                issue_id=issue.id,
                type=RemediationType.IMPLEMENT_CONTROL,
                priority=priority,
                title=f"Implement controls for {issue.title}",
                description=f"Implement missing controls: {issue.description}",
                due_date=self._calculate_due_date(priority),
                verification_steps=[
                    "Design control implementation",
                    "Implement required controls",
                    "Test control effectiveness",
                    "Document control evidence",
                ],
            )
            actions.append(action)

        # Add to plan
        if plan_id and plan_id in self.plans:
            plan = self.plans[plan_id]
        else:
            plan = RemediationPlan(
                name=f"Remediation Plan - {datetime.utcnow().strftime('%Y-%m-%d')}",
                description="Auto-generated remediation plan for compliance issues",
                created_by="RemediationManager",
            )
            self.create_plan(plan)

        for action in actions:
            plan.add_action(action)

        self._save_plans()
        return actions

    def update_action_status(
        self,
        plan_id: str,
        action_id: str,
        new_status: RemediationStatus,
        notes: Optional[str] = None,
    ) -> bool:
        """Update status of a remediation action.

        Args:
            plan_id: Plan ID
            action_id: Action ID
            new_status: New status
            notes: Optional notes about the update

        Returns:
            True if updated successfully
        """
        if plan_id in self.plans and action_id in self.plans[plan_id].actions:
            action = self.plans[plan_id].actions[action_id]
            action.status = new_status

            if new_status == RemediationStatus.IN_PROGRESS and not action.started_date:
                action.started_date = datetime.utcnow()
            elif new_status in [
                RemediationStatus.COMPLETED,
                RemediationStatus.VERIFIED,
            ]:
                action.completed_date = datetime.utcnow()

            if notes:
                action.notes = (
                    f"{action.notes}\n{datetime.utcnow().isoformat()}: {notes}".strip()
                )

            self.plans[plan_id].updated_at = datetime.utcnow()
            self._save_plans()
            return True

        return False

    def generate_remediation_report(
        self, plan_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate remediation status report.

        Args:
            plan_id: Specific plan ID or None for all plans

        Returns:
            Report data
        """
        report: Dict[str, Any] = {
            "generated_at": datetime.utcnow().isoformat(),
            "plans": [],
            "summary": {
                "total_actions": 0,
                "completed_actions": 0,
                "overdue_actions": 0,
                "by_priority": {},
                "by_status": {},
            },
        }

        plans = (
            [self.plans[plan_id]]
            if plan_id and plan_id in self.plans
            else self.plans.values()
        )

        for plan in plans:
            plan_data = {
                "id": plan.id,
                "name": plan.name,
                "progress": plan.calculate_progress(),
                "overdue_actions": [a.to_dict() for a in plan.get_overdue_actions()],
                "immediate_actions": [
                    a.to_dict()
                    for a in plan.get_actions_by_priority(RemediationPriority.IMMEDIATE)
                ],
                "recent_completions": [],
            }

            # Get recently completed actions
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            recent = [
                a
                for a in plan.actions.values()
                if a.completed_date and a.completed_date >= seven_days_ago
            ]
            plan_data["recent_completions"] = [a.to_dict() for a in recent]

            report["plans"].append(plan_data)

            # Update summary
            for action in plan.actions.values():
                report["summary"]["total_actions"] += 1

                if action.status in [
                    RemediationStatus.COMPLETED,
                    RemediationStatus.VERIFIED,
                ]:
                    report["summary"]["completed_actions"] += 1

                if action.is_overdue():
                    report["summary"]["overdue_actions"] += 1

                # Count by priority
                priority_key = action.priority.value
                report["summary"]["by_priority"][priority_key] = (
                    report["summary"]["by_priority"].get(priority_key, 0) + 1
                )

                # Count by status
                status_key = action.status.value
                report["summary"]["by_status"][status_key] = (
                    report["summary"]["by_status"].get(status_key, 0) + 1
                )

        return report

    def _calculate_due_date(self, priority: RemediationPriority) -> datetime:
        """Calculate due date based on priority."""
        now = datetime.utcnow()

        if priority == RemediationPriority.IMMEDIATE:
            return now + timedelta(days=1)
        elif priority == RemediationPriority.URGENT:
            return now + timedelta(days=7)
        elif priority == RemediationPriority.HIGH:
            return now + timedelta(days=14)
        elif priority == RemediationPriority.MEDIUM:
            return now + timedelta(days=30)
        else:  # LOW
            return now + timedelta(days=90)

    def _save_plans(self) -> None:
        """Save remediation plans to storage."""
        plans_file = self.storage_path / "remediation_plans.json"
        plans_data = {
            "version": "1.0",
            "updated_at": datetime.utcnow().isoformat(),
            "plans": {pid: plan.to_dict() for pid, plan in self.plans.items()},
        }

        with open(plans_file, "w") as f:
            json.dump(plans_data, f, indent=2)

    def _load_plans(self) -> None:
        """Load remediation plans from storage."""
        plans_file = self.storage_path / "remediation_plans.json"

        if plans_file.exists():
            try:
                with open(plans_file, "r") as f:
                    plans_data = json.load(f)

                for plan_id, plan_dict in plans_data.get("plans", {}).items():
                    plan = RemediationPlan(
                        id=plan_dict["id"],
                        name=plan_dict["name"],
                        description=plan_dict["description"],
                        created_at=datetime.fromisoformat(plan_dict["created_at"]),
                        updated_at=datetime.fromisoformat(plan_dict["updated_at"]),
                        created_by=plan_dict["created_by"],
                        issue_mappings=plan_dict.get("issue_mappings", {}),
                    )

                    # Load actions
                    for action_id, action_dict in plan_dict.get("actions", {}).items():
                        action = RemediationAction(
                            id=action_dict["id"],
                            issue_id=action_dict["issue_id"],
                            type=RemediationType(action_dict["type"]),
                            priority=RemediationPriority(action_dict["priority"]),
                            status=RemediationStatus(action_dict["status"]),
                            title=action_dict["title"],
                            description=action_dict["description"],
                            assigned_to=action_dict.get("assigned_to"),
                            due_date=(
                                datetime.fromisoformat(action_dict["due_date"])
                                if action_dict.get("due_date")
                                else None
                            ),
                            started_date=(
                                datetime.fromisoformat(action_dict["started_date"])
                                if action_dict.get("started_date")
                                else None
                            ),
                            completed_date=(
                                datetime.fromisoformat(action_dict["completed_date"])
                                if action_dict.get("completed_date")
                                else None
                            ),
                            estimated_hours=action_dict.get("estimated_hours", 0),
                            actual_hours=action_dict.get("actual_hours", 0),
                            dependencies=action_dict.get("dependencies", []),
                            verification_steps=action_dict.get(
                                "verification_steps", []
                            ),
                            notes=action_dict.get("notes", ""),
                            metadata=action_dict.get("metadata", {}),
                        )
                        plan.actions[action_id] = action

                    self.plans[plan_id] = plan
            except Exception as e:
                print(f"Error loading remediation plans: {e}")
