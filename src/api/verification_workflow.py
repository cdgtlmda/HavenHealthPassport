"""Verification Workflow System.

This module implements a comprehensive workflow engine for managing
verification processes in Haven Health Passport, including state
transitions, approval chains, and business rules.
"""

import os
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import strawberry
from sqlalchemy.orm import Session

from src.models.verification import (
    Verification,
    VerificationLevel,
    VerificationStatus,
)
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService
from src.services.notification_service import NotificationService
from src.utils.logging import get_logger

logger = get_logger(__name__)


# Workflow States
@strawberry.enum
class WorkflowState(Enum):
    """Verification workflow states."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    ADDITIONAL_INFO_REQUIRED = "additional_info_required"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED = "revoked"
    COMPLETED = "completed"


@strawberry.enum
class WorkflowAction(Enum):
    """Actions that can be performed in workflow."""

    CREATE = "create"
    SUBMIT = "submit"
    ASSIGN_REVIEWER = "assign_reviewer"
    START_REVIEW = "start_review"
    REQUEST_INFO = "request_info"
    PROVIDE_INFO = "provide_info"
    APPROVE = "approve"
    REJECT = "reject"
    COMPLETE = "complete"
    EXPIRE = "expire"
    REVOKE = "revoke"
    ESCALATE = "escalate"
    REASSIGN = "reassign"


@strawberry.type
class WorkflowTransition:
    """Represents a state transition in the workflow."""

    id: UUID
    from_state: WorkflowState
    to_state: WorkflowState
    action: WorkflowAction
    performed_by: UUID
    performed_at: datetime
    reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@strawberry.type
class WorkflowStep:
    """Represents a step in the workflow process."""

    id: UUID
    name: str
    description: str
    state: WorkflowState
    required_actions: List[WorkflowAction]
    assigned_to: Optional[UUID] = None
    due_date: Optional[datetime] = None
    completed: bool = False
    completed_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


@strawberry.type
class ApprovalChain:
    """Represents an approval chain for verification."""

    id: UUID
    name: str
    steps: List["ApprovalStep"]
    current_step: int = 0
    completed: bool = False


@strawberry.type
class ApprovalStep:
    """Single step in an approval chain."""

    order: int
    role: str
    approver_id: Optional[UUID] = None
    approved: bool = False
    approved_at: Optional[datetime] = None
    comments: Optional[str] = None
    required: bool = True


class WorkflowEngine:
    """Main workflow engine for managing verification workflows."""

    def __init__(self, session: Session):
        """Initialize the workflow engine with a database session."""
        self.session = session
        self.notification_service = NotificationService(session)
        self._state_transitions = self._define_state_transitions()
        self._workflow_rules = self._define_workflow_rules()
        # Get KMS key ID from environment or config
        kms_key_id = os.environ.get("KMS_KEY_ID", "alias/haven-health-default")
        self.encryption_service = EncryptionService(kms_key_id=kms_key_id)

    def _define_state_transitions(
        self,
    ) -> Dict[WorkflowState, Dict[WorkflowAction, WorkflowState]]:
        """Define valid state transitions."""
        return {
            WorkflowState.DRAFT: {
                WorkflowAction.SUBMIT: WorkflowState.SUBMITTED,
            },
            WorkflowState.SUBMITTED: {
                WorkflowAction.ASSIGN_REVIEWER: WorkflowState.UNDER_REVIEW,
                WorkflowAction.REJECT: WorkflowState.REJECTED,
            },
            WorkflowState.UNDER_REVIEW: {
                WorkflowAction.REQUEST_INFO: WorkflowState.ADDITIONAL_INFO_REQUIRED,
                WorkflowAction.APPROVE: WorkflowState.PENDING_APPROVAL,
                WorkflowAction.REJECT: WorkflowState.REJECTED,
            },
            WorkflowState.ADDITIONAL_INFO_REQUIRED: {
                WorkflowAction.PROVIDE_INFO: WorkflowState.UNDER_REVIEW,
                WorkflowAction.EXPIRE: WorkflowState.EXPIRED,
            },
            WorkflowState.PENDING_APPROVAL: {
                WorkflowAction.APPROVE: WorkflowState.APPROVED,
                WorkflowAction.REJECT: WorkflowState.REJECTED,
                WorkflowAction.REQUEST_INFO: WorkflowState.ADDITIONAL_INFO_REQUIRED,
            },
            WorkflowState.APPROVED: {
                WorkflowAction.COMPLETE: WorkflowState.COMPLETED,
                WorkflowAction.REVOKE: WorkflowState.REVOKED,
            },
        }

    def _define_workflow_rules(self) -> Dict[str, Callable]:
        """Define business rules for workflow actions."""
        return {
            "require_biometric_for_high_level": self._require_biometric_for_high_level,
            "validate_evidence_count": self._validate_evidence_count,
            "check_reviewer_authority": self._check_reviewer_authority,
            "validate_approval_chain": self._validate_approval_chain,
            "check_expiration": self._check_expiration,
        }

    def create_workflow(
        self,
        verification_id: UUID,
        workflow_type: str,
        created_by: UUID,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new workflow for a verification."""
        workflow_id = uuid4()

        # Create initial workflow state
        workflow = {
            "id": workflow_id,
            "verification_id": verification_id,
            "type": workflow_type,
            "state": WorkflowState.DRAFT,
            "created_by": created_by,
            "created_at": datetime.utcnow(),
            "transitions": [],
            "steps": self._create_workflow_steps(workflow_type),
            "metadata": metadata or {},
        }

        # Store workflow in verification metadata
        verification = self.session.query(Verification).get(verification_id)
        if verification:
            if not verification.metadata:
                verification.metadata = {}
            verification.metadata["workflow"] = workflow
            self.session.flush()

        # Log initial transition
        self._log_transition(
            workflow_id,
            None,
            WorkflowState.DRAFT,
            WorkflowAction.CREATE,
            created_by,
            "Workflow created",
        )

        return workflow

    @audit_phi_access("phi_access__create_workflow_steps")
    @require_permission(AccessPermission.READ_PHI)
    def _create_workflow_steps(self, workflow_type: str) -> List[WorkflowStep]:
        """Create workflow steps based on type."""
        if workflow_type == "identity_verification":
            return [
                WorkflowStep(
                    id=uuid4(),
                    name="Document Collection",
                    description="Collect required identity documents",
                    state=WorkflowState.DRAFT,
                    required_actions=[WorkflowAction.SUBMIT],
                    due_date=datetime.utcnow() + timedelta(days=7),
                    completed=False,
                ),
                WorkflowStep(
                    id=uuid4(),
                    name="Initial Review",
                    description="Review submitted documents",
                    state=WorkflowState.SUBMITTED,
                    required_actions=[WorkflowAction.START_REVIEW],
                    due_date=datetime.utcnow() + timedelta(days=3),
                    completed=False,
                ),
                WorkflowStep(
                    id=uuid4(),
                    name="Verification",
                    description="Verify authenticity of documents",
                    state=WorkflowState.UNDER_REVIEW,
                    required_actions=[WorkflowAction.APPROVE, WorkflowAction.REJECT],
                    due_date=datetime.utcnow() + timedelta(days=5),
                    completed=False,
                ),
                WorkflowStep(
                    id=uuid4(),
                    name="Final Approval",
                    description="Final approval by authorized personnel",
                    state=WorkflowState.PENDING_APPROVAL,
                    required_actions=[WorkflowAction.APPROVE],
                    due_date=datetime.utcnow() + timedelta(days=2),
                    completed=False,
                ),
            ]
        elif workflow_type == "medical_record_verification":
            return self._create_medical_verification_steps()  # type: ignore[no-any-return]
        else:
            return self._create_default_steps()  # type: ignore[no-any-return]

    async def transition_state(
        self,
        verification_id: UUID,
        action: WorkflowAction,
        performed_by: UUID,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Transition workflow to a new state."""
        try:
            verification = self.session.query(Verification).get(verification_id)
            if not verification or not verification.metadata.get("workflow"):
                return False, "No workflow found for verification"

            workflow = verification.metadata["workflow"]
            current_state = WorkflowState(workflow["state"])

            # Check if transition is valid
            if current_state not in self._state_transitions:
                return False, f"No transitions defined for state {current_state.value}"

            valid_transitions = self._state_transitions[current_state]
            if action not in valid_transitions:
                return (
                    False,
                    f"Action {action.value} not valid for state {current_state.value}",
                )

            new_state = valid_transitions[action]

            # Run business rules
            for rule_name, rule_func in self._workflow_rules.items():
                valid, error = rule_func(verification, action, metadata)
                if not valid:
                    return False, f"Rule {rule_name} failed: {error}"

            # Update workflow state
            workflow["state"] = new_state.value
            workflow["updated_at"] = datetime.utcnow().isoformat()

            # Log transition
            transition = self._log_transition(
                workflow["id"],
                current_state,
                new_state,
                action,
                performed_by,
                reason,
                metadata,
            )
            workflow["transitions"].append(transition)

            # Update verification status
            self._update_verification_status(verification, new_state)

            # Send notifications
            await self._send_workflow_notifications(verification, action, new_state)

            self.session.flush()

            return True, None

        except (ValueError, AttributeError, KeyError, TypeError) as e:
            logger.error("Error transitioning workflow state: %s", str(e))
            return False, str(e)

    def _log_transition(
        self,
        workflow_id: UUID,
        from_state: Optional[WorkflowState],
        to_state: WorkflowState,
        action: WorkflowAction,
        performed_by: UUID,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Log a workflow state transition."""
        transition = {
            "id": str(uuid4()),
            "from_state": from_state.value if from_state else None,
            "to_state": to_state.value,
            "action": action.value,
            "performed_by": str(performed_by),
            "performed_at": datetime.utcnow().isoformat(),
            "reason": reason,
            "metadata": metadata or {},
        }

        logger.info(
            f"Workflow {workflow_id} transitioned from {from_state} to {to_state} "
            f"via {action.value} by {performed_by}"
        )

        return transition

    @audit_phi_access("phi_access__update_verification_status")
    @require_permission(AccessPermission.READ_PHI)
    def _update_verification_status(
        self,
        verification: Verification,
        state: WorkflowState,  # pylint: disable=unused-argument
    ) -> None:
        """Update verification status based on workflow state."""
        status_mapping = {
            WorkflowState.DRAFT: VerificationStatus.PENDING,
            WorkflowState.SUBMITTED: VerificationStatus.PENDING,
            WorkflowState.UNDER_REVIEW: VerificationStatus.IN_PROGRESS,
            WorkflowState.ADDITIONAL_INFO_REQUIRED: VerificationStatus.IN_PROGRESS,
            WorkflowState.PENDING_APPROVAL: VerificationStatus.IN_PROGRESS,
            WorkflowState.APPROVED: VerificationStatus.COMPLETED,
            WorkflowState.REJECTED: VerificationStatus.FAILED,
            WorkflowState.EXPIRED: VerificationStatus.EXPIRED,
            WorkflowState.REVOKED: VerificationStatus.REVOKED,
            WorkflowState.COMPLETED: VerificationStatus.COMPLETED,
        }

        if state in status_mapping:
            verification.status = status_mapping[state]

    async def _send_workflow_notifications(
        self,
        verification: Verification,
        action: WorkflowAction,
        new_state: WorkflowState,  # pylint: disable=unused-argument
    ) -> None:
        """Send notifications based on workflow events."""
        notifications: List[Dict[str, Any]] = []

        if action == WorkflowAction.SUBMIT:
            notifications.append(
                {
                    "type": "verification_submitted",
                    "recipient": verification.verifier_id,
                    "subject": "New verification request submitted",
                    "data": {
                        "verification_id": str(verification.id),
                        "patient_id": str(verification.patient_id),
                        "type": verification.verification_type,
                    },
                }
            )
        elif action == WorkflowAction.REQUEST_INFO:
            notifications.append(
                {
                    "type": "additional_info_required",
                    "recipient": verification.patient_id,
                    "subject": "Additional information required for verification",
                    "data": {"verification_id": str(verification.id)},
                }
            )
        elif action == WorkflowAction.APPROVE:
            notifications.append(
                {
                    "type": "verification_approved",
                    "recipient": verification.patient_id,
                    "subject": "Your verification has been approved",
                    "data": {
                        "verification_id": str(verification.id),
                        "level": verification.verification_level.value,
                    },
                }
            )
        elif action == WorkflowAction.REJECT:
            notifications.append(
                {
                    "type": "verification_rejected",
                    "recipient": verification.patient_id,
                    "subject": "Verification request rejected",
                    "data": {"verification_id": str(verification.id)},
                }
            )

        # Send all notifications
        for notification in notifications:
            try:
                notification_data = notification.get("data")
                data_dict = (
                    notification_data if isinstance(notification_data, dict) else None
                )

                await self.notification_service.send_notification(
                    user_id=UUID(str(notification["recipient"])),
                    notification_type=str(notification["type"]),
                    title=str(notification["subject"]),
                    message=str(
                        notification["subject"]
                    ),  # Using subject as message too
                    data=data_dict,
                )
            except (ValueError, AttributeError, RuntimeError) as e:
                logger.error("Failed to send notification: %s", e)

    # Business Rules
    def _require_biometric_for_high_level(
        self,
        verification: Verification,
        action: WorkflowAction,
        metadata: Optional[Dict[str, Any]],  # pylint: disable=unused-argument
    ) -> Tuple[bool, Optional[str]]:
        """Require biometric verification for high-level verifications."""
        if action == WorkflowAction.APPROVE and verification.verification_level in [
            VerificationLevel.HIGH,
            VerificationLevel.VERY_HIGH,
        ]:
            # Check if biometric evidence exists
            evidence = verification.evidence or []
            has_biometric = any(e.get("type") == "biometric" for e in evidence)

            if not has_biometric:
                return False, "Biometric evidence required for high-level verification"

        return True, None

    def _validate_evidence_count(
        self,
        verification: Verification,
        action: WorkflowAction,
        metadata: Optional[Dict[str, Any]],  # pylint: disable=unused-argument
    ) -> Tuple[bool, Optional[str]]:
        """Validate minimum evidence count for approval."""
        if action == WorkflowAction.APPROVE:
            evidence_count = len(verification.evidence or [])
            min_evidence = {
                VerificationLevel.LOW: 1,
                VerificationLevel.MEDIUM: 2,
                VerificationLevel.HIGH: 3,
                VerificationLevel.VERY_HIGH: 4,
            }

            required = min_evidence.get(verification.verification_level, 2)
            if evidence_count < required:
                return False, f"At least {required} pieces of evidence required"

        return True, None

    def _check_reviewer_authority(
        self,
        verification: Verification,
        action: WorkflowAction,
        metadata: Optional[Dict[str, Any]],
    ) -> Tuple[bool, Optional[str]]:
        """Check if reviewer has authority for the action."""
        if action in [WorkflowAction.APPROVE, WorkflowAction.REJECT]:
            # In a real implementation, this would check user roles/permissions
            # For now, we'll just ensure the reviewer is not the patient
            reviewer_id = metadata.get("reviewer_id") if metadata else None
            if reviewer_id == str(verification.patient_id):
                return False, "Reviewer cannot be the patient"

        return True, None

    def _validate_approval_chain(
        self,
        verification: Verification,
        action: WorkflowAction,  # pylint: disable=unused-argument
        metadata: Optional[Dict[str, Any]],  # pylint: disable=unused-argument
    ) -> Tuple[bool, Optional[str]]:
        """Validate approval chain requirements."""
        if action == WorkflowAction.COMPLETE:
            workflow = verification.metadata.get("workflow", {})
            approval_chain = workflow.get("approval_chain")

            if approval_chain:
                # Check if all required approvals are complete
                for step in approval_chain.get("steps", []):
                    if step["required"] and not step["approved"]:
                        return False, f"Approval required from {step['role']}"

        return True, None

    def _check_expiration(
        self,
        verification: Verification,
        action: WorkflowAction,
        metadata: Optional[Dict[str, Any]],
    ) -> Tuple[bool, Optional[str]]:
        """Check if workflow has expired."""
        _ = action  # Intentionally unused
        _ = metadata  # Intentionally unused
        workflow = verification.metadata.get("workflow", {})
        created_at = datetime.fromisoformat(
            workflow.get("created_at", datetime.utcnow().isoformat())
        )

        # Workflow expires after 30 days
        if datetime.utcnow() - created_at > timedelta(days=30):
            return False, "Workflow has expired"

        return True, None

    @audit_phi_access("phi_access__create_medical_verification_steps")
    @require_permission(AccessPermission.READ_PHI)
    def _create_medical_verification_steps(self) -> List[WorkflowStep]:
        """Create steps for medical record verification."""
        return [
            WorkflowStep(
                id=uuid4(),
                name="Medical Document Submission",
                description="Submit medical records for verification",
                state=WorkflowState.DRAFT,
                required_actions=[WorkflowAction.SUBMIT],
                due_date=datetime.utcnow() + timedelta(days=14),
                completed=False,
            ),
            WorkflowStep(
                id=uuid4(),
                name="Medical Professional Review",
                description="Review by qualified medical professional",
                state=WorkflowState.UNDER_REVIEW,
                required_actions=[WorkflowAction.START_REVIEW],
                due_date=datetime.utcnow() + timedelta(days=7),
                completed=False,
            ),
            WorkflowStep(
                id=uuid4(),
                name="Cross-Reference Check",
                description="Cross-reference with medical databases",
                state=WorkflowState.UNDER_REVIEW,
                required_actions=[WorkflowAction.APPROVE, WorkflowAction.REQUEST_INFO],
                due_date=datetime.utcnow() + timedelta(days=5),
                completed=False,
            ),
        ]

    @audit_phi_access("phi_access__create_default_steps")
    @require_permission(AccessPermission.READ_PHI)
    def _create_default_steps(self) -> List[WorkflowStep]:
        """Create default workflow steps."""
        return [
            WorkflowStep(
                id=uuid4(),
                name="Submission",
                description="Submit verification request",
                state=WorkflowState.DRAFT,
                required_actions=[WorkflowAction.SUBMIT],
                due_date=datetime.utcnow() + timedelta(days=7),
                completed=False,
            ),
            WorkflowStep(
                id=uuid4(),
                name="Review",
                description="Review and approve/reject",
                state=WorkflowState.UNDER_REVIEW,
                required_actions=[WorkflowAction.APPROVE, WorkflowAction.REJECT],
                due_date=datetime.utcnow() + timedelta(days=5),
                completed=False,
            ),
        ]

    def _validate_approval_chain_step(self, step: WorkflowStep) -> bool:
        """Validate approval chain step."""
        return True

    def _create_additional_steps(self) -> List[WorkflowStep]:
        """Create additional workflow steps."""
        return [
            WorkflowStep(
                id=uuid4(),
                name="Final Approval",
                description="Final approval step",
                state=WorkflowState.PENDING_APPROVAL,
                required_actions=[WorkflowAction.APPROVE],
                due_date=datetime.utcnow() + timedelta(days=3),
                completed=False,
            ),
        ]

    def create_approval_chain(
        self, verification_id: UUID, chain_name: str, steps: List[Dict[str, Any]]
    ) -> ApprovalChain:
        """Create an approval chain for a verification."""
        chain = ApprovalChain(
            id=uuid4(), name=chain_name, steps=[], current_step=0, completed=False
        )

        for i, step_data in enumerate(steps):
            step = ApprovalStep(
                order=i,
                role=step_data["role"],
                approver_id=step_data.get("approver_id"),
                approved=False,
                required=step_data.get("required", True),
            )
            chain.steps.append(step)

        # Store in verification metadata
        verification = self.session.query(Verification).get(verification_id)
        if verification:
            if not verification.metadata:
                verification.metadata = {}
            if "workflow" not in verification.metadata:
                verification.metadata["workflow"] = {}
            verification.metadata["workflow"]["approval_chain"] = {
                "id": str(chain.id),
                "name": chain.name,
                "steps": [
                    {
                        "order": s.order,
                        "role": s.role,
                        "approver_id": str(s.approver_id) if s.approver_id else None,
                        "approved": s.approved,
                        "approved_at": (
                            s.approved_at.isoformat() if s.approved_at else None
                        ),
                        "comments": s.comments,
                        "required": s.required,
                    }
                    for s in chain.steps
                ],
                "current_step": chain.current_step,
                "completed": chain.completed,
            }
            self.session.flush()

        return chain

    def get_workflow_status(self, verification_id: UUID) -> Optional[Dict[str, Any]]:
        """Get the current workflow status for a verification."""
        verification = self.session.query(Verification).get(verification_id)
        if not verification or not verification.metadata.get("workflow"):
            return None

        workflow = verification.metadata["workflow"]
        return {
            "id": workflow["id"],
            "state": workflow["state"],
            "created_at": workflow["created_at"],
            "updated_at": workflow.get("updated_at"),
            "transitions": workflow.get("transitions", []),
            "current_step": self._get_current_step(workflow),
            "approval_chain": workflow.get("approval_chain"),
            "completion_percentage": self._calculate_completion_percentage(workflow),
        }

    def _get_current_step(self, workflow: Dict[str, Any]) -> Optional[WorkflowStep]:
        """Get the current active step in the workflow."""
        steps = workflow.get("steps", [])
        for step in steps:
            if not step.get("completed", False):
                return WorkflowStep(**step)
        return None

    def _calculate_completion_percentage(self, workflow: Dict[str, Any]) -> float:
        """Calculate workflow completion percentage."""
        steps = workflow.get("steps", [])
        if not steps:
            return 0.0

        completed = sum(1 for step in steps if step.get("completed", False))
        return (completed / len(steps)) * 100


# Export workflow components
__all__ = [
    "WorkflowState",
    "WorkflowAction",
    "WorkflowTransition",
    "WorkflowStep",
    "ApprovalChain",
    "ApprovalStep",
    "WorkflowEngine",
]
