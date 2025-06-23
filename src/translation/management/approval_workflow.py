"""Translation Approval Workflow - Manages approval process for translations."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.translation.management.review_process import (
    ReviewerRole,
    TranslationReviewProcess,
)
from src.translation.management.version_control import TranslationVersionControl
from src.utils.logging import get_logger

logger = get_logger(__name__)


class WorkflowState(Enum):
    """Translation workflow states."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"


@dataclass
class WorkflowStep:
    """A step in the approval workflow."""

    step_id: str
    name: str
    required_role: ReviewerRole
    required_approvals: int = 1
    is_optional: bool = False
    conditions: Dict[str, Any] = field(default_factory=dict)


class ApprovalWorkflow:
    """Manages translation approval workflow."""

    def __init__(self, project_root: str):
        """Initialize approval workflow."""
        self.project_root = Path(project_root)
        self.review_process = TranslationReviewProcess(project_root)
        self.version_control = TranslationVersionControl(project_root)
        self.workflows = self._load_workflow_definitions()
        self.state_tracker: Dict[str, Any] = {}  # Track workflow states
        self._load_state()

    def _load_workflow_definitions(self) -> Dict[str, List[WorkflowStep]]:
        """Load workflow definitions."""
        workflows = {
            "standard": [
                WorkflowStep(
                    step_id="initial_review",
                    name="Initial Review",
                    required_role=ReviewerRole.REVIEWER,
                    required_approvals=1,
                ),
                WorkflowStep(
                    step_id="quality_check",
                    name="Quality Check",
                    required_role=ReviewerRole.LEAD_REVIEWER,
                    required_approvals=1,
                ),
            ],
            "medical": [
                WorkflowStep(
                    step_id="initial_review",
                    name="Initial Review",
                    required_role=ReviewerRole.REVIEWER,
                    required_approvals=1,
                ),
                WorkflowStep(
                    step_id="medical_review",
                    name="Medical Expert Review",
                    required_role=ReviewerRole.MEDICAL_EXPERT,
                    required_approvals=1,
                ),
                WorkflowStep(
                    step_id="final_approval",
                    name="Final Approval",
                    required_role=ReviewerRole.LEAD_REVIEWER,
                    required_approvals=1,
                ),
            ],
        }

        # Load custom workflows from config
        config_file = self.project_root / ".translation" / "workflows.json"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                custom_workflows = json.load(f)
                workflows.update(custom_workflows)

        return workflows

    def _load_state(self) -> None:
        """Load workflow state from storage."""
        state_file = self.project_root / ".translation" / "workflow_state.json"
        if state_file.exists():
            with open(state_file, "r", encoding="utf-8") as f:
                self.state_tracker = json.load(f)

    def _save_state(self) -> None:
        """Save workflow state to storage."""
        state_file = self.project_root / ".translation" / "workflow_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(self.state_tracker, f, indent=2)

    def start_workflow(
        self,
        version_id: str,
        language: str,
        namespace: str,
        workflow_type: str = "standard",
    ) -> str:
        """Start approval workflow for a translation version."""
        if workflow_type not in self.workflows:
            raise ValueError(f"Unknown workflow type: {workflow_type}")

        workflow_id = f"{version_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Initialize workflow state
        self.state_tracker[workflow_id] = {
            "version_id": version_id,
            "language": language,
            "namespace": namespace,
            "workflow_type": workflow_type,
            "current_step": 0,
            "state": WorkflowState.SUBMITTED.value,
            "started_at": datetime.now().isoformat(),
            "completed_steps": [],
            "approvals": {},
        }

        self._save_state()

        # Submit for review with first step requirements
        first_step = self.workflows[workflow_type][0]
        self._submit_for_step(workflow_id, first_step)

        logger.info(
            f"Started {workflow_type} workflow {workflow_id} for {language}/{namespace}"
        )

        return workflow_id

    def _submit_for_step(self, workflow_id: str, step: WorkflowStep) -> None:
        """Submit translation for specific workflow step."""
        state = self.state_tracker[workflow_id]

        # Find reviewers with required role
        reviewers = self._find_reviewers_for_role(step.required_role)

        if len(reviewers) < step.required_approvals:
            logger.warning(
                f"Not enough reviewers for role {step.required_role.value}. "
                f"Required: {step.required_approvals}, Available: {len(reviewers)}"
            )

        # Submit for review
        review = self.review_process.submit_for_review(
            version_id=state["version_id"],
            language=state["language"],
            namespace=state["namespace"],
            submitted_by="workflow_system",
            assigned_reviewers=reviewers[: step.required_approvals],
        )

        state["current_review_id"] = review.review_id
        state["state"] = WorkflowState.IN_REVIEW.value
        self._save_state()

    def _find_reviewers_for_role(self, role: ReviewerRole) -> List[str]:
        """Find available reviewers for a specific role."""
        # Get from review process reviewer registry
        reviewers = []

        for reviewer_id, info in self.review_process.index.get("reviewers", {}).items():
            if info.get("role") == role.value:
                reviewers.append(reviewer_id)

        return reviewers

    def approve_step(
        self, workflow_id: str, approver_id: str, comments: Optional[str] = None
    ) -> bool:
        """Approve current workflow step."""
        if workflow_id not in self.state_tracker:
            raise ValueError(f"Workflow {workflow_id} not found")

        state = self.state_tracker[workflow_id]
        workflow_steps = self.workflows[state["workflow_type"]]
        current_step = workflow_steps[state["current_step"]]

        # Record approval
        if current_step.step_id not in state["approvals"]:
            state["approvals"][current_step.step_id] = []

        state["approvals"][current_step.step_id].append(
            {
                "approver": approver_id,
                "timestamp": datetime.now().isoformat(),
                "comments": comments,
            }
        )

        # Check if step requirements are met
        approvals_count = len(state["approvals"][current_step.step_id])

        if approvals_count >= current_step.required_approvals:
            # Mark step as completed
            state["completed_steps"].append(
                {
                    "step_id": current_step.step_id,
                    "completed_at": datetime.now().isoformat(),
                }
            )

            # Move to next step
            state["current_step"] += 1

            if state["current_step"] < len(workflow_steps):
                # Submit for next step
                next_step = workflow_steps[state["current_step"]]
                self._submit_for_step(workflow_id, next_step)
            else:
                # Workflow completed
                self._complete_workflow(workflow_id)

        self._save_state()
        return True

    def reject_step(self, workflow_id: str, rejector_id: str, reason: str) -> bool:
        """Reject current workflow step."""
        if workflow_id not in self.state_tracker:
            raise ValueError(f"Workflow {workflow_id} not found")

        state = self.state_tracker[workflow_id]

        # Reject current review
        if "current_review_id" in state:
            self.review_process.reject_review(
                review_id=state["current_review_id"],
                rejected_by=rejector_id,
                reason=reason,
            )

        # Update workflow state
        state["state"] = WorkflowState.REJECTED.value
        state["rejected_at"] = datetime.now().isoformat()
        state["rejected_by"] = rejector_id
        state["rejection_reason"] = reason

        self._save_state()

        logger.info(f"Workflow {workflow_id} rejected by {rejector_id}")

        return True

    def _complete_workflow(self, workflow_id: str) -> None:
        """Mark workflow as completed and publish translation."""
        state = self.state_tracker[workflow_id]

        # Approve final review
        if "current_review_id" in state:
            self.review_process.approve_review(
                review_id=state["current_review_id"], approved_by="workflow_system"
            )

        # Update state
        state["state"] = WorkflowState.APPROVED.value
        state["completed_at"] = datetime.now().isoformat()

        # Publish translation (would trigger deployment)
        # This would integrate with deployment system

        logger.info(f"Workflow {workflow_id} completed successfully")

    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get current status of a workflow."""
        if workflow_id not in self.state_tracker:
            return {}

        state = self.state_tracker[workflow_id]
        workflow_steps = self.workflows[state["workflow_type"]]

        status = {
            "workflow_id": workflow_id,
            "state": state["state"],
            "current_step": None,
            "progress": {
                "completed": len(state["completed_steps"]),
                "total": len(workflow_steps),
            },
            "started_at": state["started_at"],
            "completed_at": state.get("completed_at"),
        }

        if state["current_step"] < len(workflow_steps):
            current = workflow_steps[state["current_step"]]
            status["current_step"] = {
                "name": current.name,
                "required_approvals": current.required_approvals,
                "current_approvals": len(state["approvals"].get(current.step_id, [])),
            }

        return status

    def get_pending_approvals(self, reviewer_id: str) -> List[Dict[str, Any]]:
        """Get pending approvals for a reviewer."""
        pending = []

        for workflow_id, state in self.state_tracker.items():
            if state["state"] != WorkflowState.IN_REVIEW.value:
                continue

            # Check if reviewer is assigned to current review
            if "current_review_id" in state:
                review = self.review_process.get_review(state["current_review_id"])
                if review and reviewer_id in review.assigned_reviewers:
                    pending.append(
                        {
                            "workflow_id": workflow_id,
                            "version_id": state["version_id"],
                            "language": state["language"],
                            "namespace": state["namespace"],
                            "workflow_type": state["workflow_type"],
                            "review_id": state["current_review_id"],
                        }
                    )

        return pending
