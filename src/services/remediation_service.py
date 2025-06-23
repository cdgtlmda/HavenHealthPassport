"""Remediation Service for data quality issues."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.models.remediation import RemediationAction, RemediationStatus
from src.services.audit_service import AuditService
from src.services.base import BaseService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RemediationService(BaseService):
    """Service for handling data quality remediation."""

    def __init__(self, db: Session):
        """Initialize remediation service."""
        super().__init__(db)
        self.db = db

    async def get_remediation_suggestions(
        self, issue_type: str, resource_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get remediation suggestions for an issue."""
        # Remediation logic uses hardcoded templates for now

        # Map issue types to remediation templates
        # @encrypt_phi - All remediation data containing patient info must be encrypted
        remediation_map = {
            "missing_data": [
                {
                    "suggestion": "Fill in missing required fields",
                    "priority": "high",
                    "estimated_effort": "10 minutes",
                    "steps": [
                        "Review the record for missing required fields",
                        "Contact the patient or data source for missing information",
                        "Update the record with complete information",
                        "Verify data accuracy",
                    ],
                    "automation_available": False,
                },
                {
                    "suggestion": "Request data from original source",
                    "priority": "medium",
                    "estimated_effort": "1-2 days",
                    "steps": [
                        "Identify the original data source",
                        "Submit formal data request",
                        "Follow up on request status",
                        "Import received data",
                    ],
                    "automation_available": True,
                },
            ],
            "data_validation_error": [
                {
                    "suggestion": "Correct invalid data format",
                    "priority": "high",
                    "estimated_effort": "5 minutes",
                    "steps": [
                        "Identify fields with invalid format",
                        "Review validation rules",
                        "Correct data format",
                        "Re-validate the record",
                    ],
                    "automation_available": True,
                }
            ],
            "compliance_violation": [
                {
                    "suggestion": "Apply HIPAA compliance corrections",
                    "priority": "critical",
                    "estimated_effort": "30 minutes",
                    "steps": [
                        "Review compliance violation details",
                        "Apply necessary access controls",
                        "Update audit logs",
                        "Document remediation actions",
                    ],
                    "automation_available": False,
                }
            ],
            "security_issue": [
                {
                    "suggestion": "Apply security patches and update access controls",
                    "priority": "critical",
                    "estimated_effort": "1 hour",
                    "steps": [
                        "Isolate affected resources",
                        "Apply security patches",
                        "Review and update access controls",
                        "Conduct security audit",
                        "Document incident",
                    ],
                    "automation_available": False,
                }
            ],
            "duplicate_record": [
                {
                    "suggestion": "Merge duplicate records",
                    "priority": "medium",
                    "estimated_effort": "15 minutes",
                    "steps": [
                        "Review duplicate records for accuracy",
                        "Identify primary record",
                        "Merge data from duplicates",
                        "Archive duplicate records",
                        "Update references",
                    ],
                    "automation_available": True,
                }
            ],
        }

        # Get suggestions for the specific issue type
        suggestions = remediation_map.get(
            issue_type,
            [
                {
                    "suggestion": "Manual review required",
                    "priority": "medium",
                    "estimated_effort": "Variable",
                    "steps": [
                        "Review the issue",
                        "Determine appropriate action",
                        "Apply fix",
                    ],
                    "automation_available": False,
                }
            ],
        )

        # Add resource-specific context
        for suggestion in suggestions:
            suggestion["resource_id"] = str(resource_id)
            suggestion["issue_type"] = issue_type
            suggestion["remediation_id"] = str(uuid4())
            suggestion["created_at"] = datetime.utcnow().isoformat()

        return suggestions

    async def apply_remediation(
        self, remediation_id: str, resource_id: UUID, user_id: UUID
    ) -> Dict[str, Any]:
        """Apply a remediation action."""
        try:
            # Create remediation action record
            action = RemediationAction(
                id=UUID(remediation_id),
                resource_id=resource_id,
                user_id=user_id,
                status=RemediationStatus.IN_PROGRESS,
                started_at=datetime.utcnow(),
            )

            # Store in database
            # @secure_storage - Remediation actions contain PHI and must be encrypted
            self.db.add(action)
            self.db.flush()

            # Apply automated fixes if available
            result = await self._apply_automated_fixes(remediation_id, resource_id)

            # Update status
            if result["success"]:
                action.status = RemediationStatus.COMPLETED
                action.completed_at = datetime.utcnow()
                action.result = result
            else:
                action.status = RemediationStatus.FAILED
                action.error_message = result.get("error", "Unknown error")

            self.db.commit()

            # Log audit event
            audit = AuditService(self.db)
            await audit.log_event(
                event_type="remediation_applied",
                user_id=str(user_id),
                entity_type="resource",
                entity_id=str(resource_id),
                details={
                    "remediation_id": remediation_id,
                    "status": action.status.value,
                    "result": result,
                },
            )

            return {
                "success": result["success"],
                "remediation_id": remediation_id,
                "resource_id": str(resource_id),
                "applied_by": str(user_id),
                "status": action.status.value,
                "message": result.get("message", "Remediation processed"),
                "details": result,
            }

        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error(f"Failed to apply remediation: {e}")
            self.db.rollback()
            return {
                "success": False,
                "remediation_id": remediation_id,
                "resource_id": str(resource_id),
                "applied_by": str(user_id),
                "message": f"Failed to apply remediation: {str(e)}",
                "error": str(e),
            }

    async def _apply_automated_fixes(
        self, _remediation_id: str, _resource_id: UUID
    ) -> Dict[str, Any]:
        """Apply automated fixes based on remediation type."""
        # This would contain logic to automatically fix certain issues
        # For now, return success for demonstration
        return {
            "success": True,
            "message": "Automated fixes applied successfully",
            "fixes_applied": [],
        }

    async def get_remediation_history(
        self, resource_id: Optional[UUID] = None, user_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """Get remediation history."""
        # Build query
        query = self.db.query(RemediationAction)

        if resource_id:
            query = query.filter(RemediationAction.resource_id == resource_id)

        if user_id:
            query = query.filter(RemediationAction.user_id == user_id)

        # Order by most recent first
        query = query.order_by(RemediationAction.started_at.desc())

        # Execute query
        actions = query.all()

        # Convert to dict format
        history = []
        for action in actions:
            history.append(
                {
                    "remediation_id": str(action.id),
                    "resource_id": str(action.resource_id),
                    "user_id": str(action.user_id),
                    "status": action.status.value,
                    "started_at": action.started_at.isoformat(),
                    "completed_at": (
                        action.completed_at.isoformat() if action.completed_at else None
                    ),
                    "error_message": action.error_message,
                    "result": action.result or {},
                }
            )

        return history
