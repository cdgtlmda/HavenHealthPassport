"""GraphQL Workflow Operations.

This module provides GraphQL queries and mutations for managing
verification workflows.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

# from src.api.graphql_setup import JSON
from src.api.graphql_versioning import VersionedField
from src.api.verification_workflow import (
    WorkflowAction,
    WorkflowEngine,
    WorkflowStep,
)
from src.utils.logging import get_logger

if TYPE_CHECKING:
    import strawberry
    from strawberry.types import Info
else:
    try:
        import strawberry
        from strawberry.types import Info
    except ImportError:
        strawberry = None
        Info = None

logger = get_logger(__name__)


# Define strawberry types only when strawberry is available
if strawberry:
    # Input Types
    @strawberry.input
    class CreateWorkflowInput:
        """Input for creating a workflow."""

        verification_id: UUID
        workflow_type: str
        metadata: Optional[Dict[str, Any]] = None

    @strawberry.input
    class TransitionWorkflowInput:
        """Input for transitioning workflow state."""

        verification_id: UUID
        action: WorkflowAction
        reason: Optional[str] = None
        metadata: Optional[Dict[str, Any]] = None

    @strawberry.input
    class CreateApprovalChainInput:
        """Input for creating an approval chain."""

        verification_id: UUID
        chain_name: str
        steps: List[Dict[str, Any]]

    # Output Types

    @strawberry.type
    class WorkflowStatus:
        """Current workflow status."""

        id: str
        state: str
        created_at: str
        updated_at: Optional[str]
        transitions: List[Dict[str, Any]]
        current_step: Optional[WorkflowStep]
        approval_chain: Optional[Dict[str, Any]]
        completion_percentage: float

    @strawberry.type
    class WorkflowOperationResult:
        """Result of a workflow operation."""

        success: bool
        message: Optional[str] = None
        workflow_status: Optional[WorkflowStatus] = None

    # Workflow Queries

    @strawberry.type
    class WorkflowQuery:
        """Workflow-related queries."""

        @strawberry.field
        @VersionedField(added_in="2.0")
        async def workflow_status(
            self, info: Info, verification_id: UUID
        ) -> Optional[WorkflowStatus]:
            """Get workflow status for a verification."""
            try:
                db = info.context["db"]
                engine = WorkflowEngine(db)

                status = engine.get_workflow_status(verification_id)
                if not status:
                    return None

                return WorkflowStatus(
                    id=status["id"],
                    state=status["state"],
                    created_at=status["created_at"],
                    updated_at=status.get("updated_at"),
                    transitions=status.get("transitions", []),
                    current_step=status.get("current_step"),
                    approval_chain=status.get("approval_chain"),
                    completion_percentage=status.get("completion_percentage", 0.0),
                )

            except (ValueError, AttributeError, KeyError) as e:
                logger.error("Error getting workflow status: %s", e)
                return None

    # Workflow Mutations

    @strawberry.type
    class WorkflowMutation:
        """Workflow-related mutations."""

        @strawberry.mutation
        @VersionedField(added_in="2.0")
        async def create_workflow(
            self, info: Info, workflow_input: CreateWorkflowInput
        ) -> WorkflowOperationResult:
            """Create a new workflow for a verification."""
            try:
                db = info.context["db"]
                user = info.context["user"]
                engine = WorkflowEngine(db)

                workflow = engine.create_workflow(
                    verification_id=workflow_input.verification_id,
                    workflow_type=workflow_input.workflow_type,
                    created_by=UUID(user["sub"]),
                    metadata=workflow_input.metadata,
                )

                db.commit()

                return WorkflowOperationResult(
                    success=True,
                    message="Workflow created successfully",
                    workflow_status=WorkflowStatus(
                        id=workflow["id"],
                        state=workflow["state"],
                        created_at=workflow["created_at"],
                        updated_at=workflow.get("updated_at"),
                        transitions=workflow.get("transitions", []),
                        current_step=None,
                        approval_chain=None,
                        completion_percentage=0.0,
                    ),
                )

            except (ValueError, AttributeError, KeyError, TypeError) as e:
                logger.error("Error creating workflow: %s", e)
                db.rollback()
                return WorkflowOperationResult(success=False, message=str(e))

        @strawberry.mutation
        @VersionedField(added_in="2.0")
        async def transition_workflow(
            self, info: Info, transition_input: TransitionWorkflowInput
        ) -> WorkflowOperationResult:
            """Transition workflow to a new state."""
            try:
                db = info.context["db"]
                user = info.context["user"]
                engine = WorkflowEngine(db)

                # Add reviewer info to metadata
                metadata = transition_input.metadata or {}
                metadata["reviewer_id"] = user["sub"]

                success, error = await engine.transition_state(
                    verification_id=transition_input.verification_id,
                    action=transition_input.action,
                    performed_by=UUID(user["sub"]),
                    reason=transition_input.reason,
                    metadata=metadata,
                )

                if success:
                    db.commit()
                    status = engine.get_workflow_status(
                        transition_input.verification_id
                    )

                    return WorkflowOperationResult(
                        success=True,
                        message=f"Workflow transitioned via {transition_input.action.value}",
                        workflow_status=(
                            WorkflowStatus(
                                id=status["id"],
                                state=status["state"],
                                created_at=status["created_at"],
                                updated_at=status.get("updated_at"),
                                transitions=status.get("transitions", []),
                                current_step=status.get("current_step"),
                                approval_chain=status.get("approval_chain"),
                                completion_percentage=status.get(
                                    "completion_percentage", 0.0
                                ),
                            )
                            if status
                            else None
                        ),
                    )
                else:
                    db.rollback()
                    return WorkflowOperationResult(success=False, message=error)

            except (ValueError, AttributeError, KeyError, TypeError) as e:
                logger.error("Error transitioning workflow: %s", e)
                db.rollback()
                return WorkflowOperationResult(success=False, message=str(e))

        @strawberry.mutation
        @VersionedField(added_in="2.0")
        async def create_approval_chain(
            self, info: Info, chain_input: CreateApprovalChainInput
        ) -> WorkflowOperationResult:
            """Create an approval chain for a verification."""
            try:
                db = info.context["db"]
                engine = WorkflowEngine(db)

                _ = engine.create_approval_chain(
                    verification_id=chain_input.verification_id,
                    chain_name=chain_input.chain_name,
                    steps=chain_input.steps,
                )

                db.commit()

                return WorkflowOperationResult(
                    success=True,
                    message=f"Approval chain '{chain_input.chain_name}' created with {len(chain_input.steps)} steps",
                )

            except (ValueError, AttributeError, KeyError, TypeError) as e:
                logger.error("Error creating approval chain: %s", e)
                db.rollback()
                return WorkflowOperationResult(success=False, message=str(e))

else:
    # Define placeholder classes when strawberry is not available
    class CreateWorkflowInput:  # type: ignore[no-redef]
        """Input for creating a workflow."""

    class TransitionWorkflowInput:  # type: ignore[no-redef]
        """Input for transitioning workflow state."""

    class CreateApprovalChainInput:  # type: ignore[no-redef]
        """Input for creating an approval chain."""

    class WorkflowStatus:  # type: ignore[no-redef]
        """Current workflow status."""

    class WorkflowOperationResult:  # type: ignore[no-redef]
        """Result of a workflow operation."""

    class WorkflowQuery:  # type: ignore[no-redef]
        """Workflow-related queries."""

    class WorkflowMutation:  # type: ignore[no-redef]
        """Workflow-related mutations."""


# Export components
__all__ = [
    "CreateWorkflowInput",
    "TransitionWorkflowInput",
    "CreateApprovalChainInput",
    "WorkflowStatus",
    "WorkflowOperationResult",
    "WorkflowQuery",
    "WorkflowMutation",
]
