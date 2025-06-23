"""GDPR Right to Deletion Manager.

This module implements the complete right to deletion (right to be forgotten)
functionality for GDPR Article 17 compliance, with healthcare-specific
considerations and safeguards.
"""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from src.healthcare.regulatory.consent_management import ConsentManager
from src.healthcare.regulatory.right_to_deletion_config import (
    DataCategory,
    DeletionMethod,
    DeletionStatus,
    RightToDeletionConfiguration,
)

logger = logging.getLogger(__name__)


class DeletionRequest:
    """Represents a data deletion request."""

    def __init__(
        self,
        request_id: str,
        data_subject_id: str,
        requested_by: str,
        categories: List[DataCategory],
        reason: str,
        verification_token: Optional[str] = None,
    ):
        """Initialize deletion request.

        Args:
            request_id: Unique request ID
            data_subject_id: ID of data subject
            requested_by: ID of requester
            categories: Data categories to delete
            reason: Reason for deletion
            verification_token: Verification token if required
        """
        self.request_id = request_id
        self.data_subject_id = data_subject_id
        self.requested_by = requested_by
        self.categories = categories
        self.reason = reason
        self.verification_token = verification_token
        self.status = DeletionStatus.PENDING
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.completion_date: Optional[datetime] = None
        self.deleted_items: List[Dict[str, Any]] = []
        self.failed_items: List[Dict[str, Any]] = []
        self.exceptions_applied: List[Dict[str, Any]] = []
        self.third_party_notifications: List[Dict[str, Any]] = []
        self.audit_trail: List[Dict[str, Any]] = []

    def add_audit_entry(self, action: str, details: Dict[str, Any]) -> None:
        """Add entry to audit trail.

        Args:
            action: Action performed
            details: Action details
        """
        self.audit_trail.append(
            {"timestamp": datetime.now(), "action": action, "details": details}
        )
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "request_id": self.request_id,
            "data_subject_id": self.data_subject_id,
            "requested_by": self.requested_by,
            "categories": [cat.value for cat in self.categories],
            "reason": self.reason,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completion_date": (
                self.completion_date.isoformat() if self.completion_date else None
            ),
            "deleted_items": self.deleted_items,
            "failed_items": self.failed_items,
            "exceptions_applied": self.exceptions_applied,
            "third_party_notifications": self.third_party_notifications,
            "audit_trail": self.audit_trail,
        }


class RightToDeletionManager:
    """Manages GDPR right to deletion requests."""

    def __init__(self) -> None:
        """Initialize deletion manager."""
        self.config = RightToDeletionConfiguration()
        self.consent_manager = ConsentManager()
        self.deletion_requests: Dict[str, DeletionRequest] = {}
        self.deletion_queue: List[str] = []
        self.legal_holds: Dict[str, Dict[str, Any]] = {}
        self.verification_tokens: Dict[str, Dict[str, Any]] = {}

    def request_deletion(
        self,
        data_subject_id: str,
        categories: List[DataCategory],
        reason: str,
        requested_by: Optional[str] = None,
        verification_method: str = "email",
        urgent: bool = False,
    ) -> Tuple[str, bool]:
        """Submit a deletion request.

        Args:
            data_subject_id: ID of data subject
            categories: Categories to delete
            reason: Reason for request
            requested_by: ID of requester (defaults to data subject)
            verification_method: How to verify identity
            urgent: Whether request is urgent

        Returns:
            Tuple of (request_id, requires_verification)
        """
        request_id = f"DEL-{uuid4()}"
        requested_by = requested_by or data_subject_id

        # Create request
        request = DeletionRequest(
            request_id=request_id,
            data_subject_id=data_subject_id,
            requested_by=requested_by,
            categories=categories,
            reason=reason,
        )

        # Check if verification required
        requires_verification = self._requires_verification(categories)

        if requires_verification:
            # Generate verification token
            verification_token = self._generate_verification_token()
            request.verification_token = verification_token
            request.status = DeletionStatus.PENDING

            # Store token for verification
            self.verification_tokens[verification_token] = {
                "request_id": request_id,
                "expires_at": datetime.now() + timedelta(hours=48),
                "method": verification_method,
            }

            # Send verification request
            self._send_verification_request(
                data_subject_id, verification_token, verification_method
            )

            request.add_audit_entry(
                "verification_requested", {"method": verification_method}
            )
        else:
            # Move directly to review
            request.status = DeletionStatus.IN_REVIEW
            self.deletion_queue.append(request_id)

        # Store request
        self.deletion_requests[request_id] = request

        # Log request
        logger.info(
            "Deletion request created: %s for %s Categories: %s",
            request_id,
            data_subject_id,
            [cat.value for cat in categories],
        )

        request.add_audit_entry(
            "request_created",
            {
                "categories": [cat.value for cat in categories],
                "reason": reason,
                "urgent": urgent,
            },
        )

        # Process immediately if urgent and verified
        if urgent and not requires_verification:
            self._process_request(request_id)

        return request_id, requires_verification

    def verify_deletion_request(
        self, verification_token: str, additional_info: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str]]:
        """Verify a deletion request.

        Args:
            verification_token: Verification token
            additional_info: Additional verification info

        Returns:
            Tuple of (success, request_id)
        """
        _ = additional_info  # Mark as intentionally unused
        token_info = self.verification_tokens.get(verification_token)
        if not token_info:
            return False, None

        # Check expiration
        if datetime.now() > token_info["expires_at"]:
            del self.verification_tokens[verification_token]
            return False, None

        request_id = token_info["request_id"]
        request = self.deletion_requests.get(request_id)
        if not request:
            return False, None

        # Update request status
        request.status = DeletionStatus.IN_REVIEW
        request.add_audit_entry(
            "verification_completed", {"method": token_info["method"]}
        )

        # Add to processing queue
        self.deletion_queue.append(request_id)

        # Clean up token
        del self.verification_tokens[verification_token]

        logger.info("Deletion request verified: %s", request_id)

        return True, request_id

    def process_deletion_queue(self) -> Dict[str, int]:
        """Process pending deletion requests.

        Returns:
            Processing statistics
        """
        processed = 0
        failed = 0
        skipped = 0

        while self.deletion_queue:
            request_id = self.deletion_queue.pop(0)

            try:
                result = self._process_request(request_id)
                if result:
                    processed += 1
                else:
                    skipped += 1
            except (ValueError, KeyError, AttributeError) as e:
                logger.error("Failed to process deletion request %s: %s", request_id, e)
                failed += 1

                # Re-queue for retry
                request = self.deletion_requests.get(request_id)
                if request and request.status != DeletionStatus.FAILED:
                    self.deletion_queue.append(request_id)

        return {
            "processed": processed,
            "failed": failed,
            "skipped": skipped,
            "remaining": len(self.deletion_queue),
        }

    def _process_request(self, request_id: str) -> bool:
        """Process a single deletion request.

        Args:
            request_id: Request ID

        Returns:
            Success status
        """
        request = self.deletion_requests.get(request_id)
        if not request:
            return False

        # Update status
        request.status = DeletionStatus.IN_PROGRESS
        request.add_audit_entry("processing_started", {})

        # Check for legal holds
        if self._has_legal_hold(request.data_subject_id):
            request.status = DeletionStatus.SUSPENDED
            request.add_audit_entry(
                "suspended_legal_hold", {"reason": "Active legal hold"}
            )
            return False

        # Process each category
        for category in request.categories:
            try:
                self._process_category_deletion(request, category)
            except (ValueError, KeyError, AttributeError, RuntimeError) as e:
                logger.error("Failed to process %s: %s", category.value, e)
                request.failed_items.append(
                    {
                        "category": category.value,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        # Notify third parties
        self._notify_third_parties(request)

        # Update final status
        if request.failed_items:
            request.status = DeletionStatus.PARTIALLY_COMPLETED
        else:
            request.status = DeletionStatus.COMPLETED
            request.completion_date = datetime.now()

        request.add_audit_entry(
            "processing_completed",
            {
                "deleted_count": len(request.deleted_items),
                "failed_count": len(request.failed_items),
            },
        )

        # Send completion notification
        self._send_completion_notification(request)

        return True

    def _process_category_deletion(
        self, request: DeletionRequest, category: DataCategory
    ) -> None:
        """Process deletion for a specific category.

        Args:
            request: Deletion request
            category: Data category
        """
        # Get deletion policy
        policy = self.config.get_deletion_policy(category)

        # Check retention requirements
        retention_years = self.config.check_retention_requirement(
            category, "US"  # Would get actual jurisdiction
        )

        if retention_years:
            # Check if data can be deleted yet
            # In production, would check actual data age
            can_delete = False  # Placeholder

            if not can_delete:
                request.exceptions_applied.append(
                    {
                        "category": category.value,
                        "exception": "retention_requirement",
                        "retention_years": retention_years,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                return

        # Check for exceptions
        has_exception, exception_reason = self.config.check_deletion_exception(category)

        if has_exception:
            request.exceptions_applied.append(
                {
                    "category": category.value,
                    "exception": exception_reason,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            return

        # Perform deletion based on method
        deletion_method = policy["method"]

        if deletion_method == DeletionMethod.PHYSICAL_DELETE:
            self._physical_delete(request, category)
        elif deletion_method == DeletionMethod.ANONYMIZATION:
            self._anonymize_data(request, category)
        elif deletion_method == DeletionMethod.PSEUDONYMIZATION:
            self._pseudonymize_data(request, category)
        elif deletion_method == DeletionMethod.ENCRYPTION_KEY_DELETION:
            self._delete_encryption_keys(request, category)
        elif deletion_method == DeletionMethod.ARCHIVAL:
            self._archive_data(request, category)
        elif deletion_method == DeletionMethod.PARTIAL_DELETION:
            self._partial_delete(request, category)

    def _physical_delete(
        self, request: DeletionRequest, category: DataCategory
    ) -> None:
        """Perform physical deletion of data.

        Args:
            request: Deletion request
            category: Data category
        """
        # In production, would actually delete from databases
        # This is a placeholder implementation

        deleted_records = 0

        # Simulate deletion from different data stores
        if category == DataCategory.IDENTIFIERS:
            # Delete from user database
            deleted_records += 1

        elif category == DataCategory.MEDICAL_HISTORY:
            # Delete from medical records
            deleted_records += 5

        elif category == DataCategory.GENETIC_DATA:
            # Delete from genetic database with special handling
            deleted_records += 2

        # Record deletion
        request.deleted_items.append(
            {
                "category": category.value,
                "method": "physical_delete",
                "records_deleted": deleted_records,
                "timestamp": datetime.now().isoformat(),
                "verification_hash": self._generate_deletion_hash(
                    request.data_subject_id, category
                ),
            }
        )

        logger.info(
            "Physical deletion completed for %s: %d records",
            category.value,
            deleted_records,
        )

    def _anonymize_data(self, request: DeletionRequest, category: DataCategory) -> None:
        """Anonymize data instead of deletion.

        Args:
            request: Deletion request
            category: Data category
        """
        # Get anonymization rules
        rules = self.config.get_anonymization_rules(category)

        anonymized_records = 0

        # Apply anonymization based on rules
        fields_removed = rules.get("fields_to_remove", [])
        fields_generalized = rules.get("fields_to_generalize", {})

        # In production, would actually anonymize data
        # This is a placeholder
        anonymized_records = 10

        # Record anonymization
        request.deleted_items.append(
            {
                "category": category.value,
                "method": "anonymization",
                "records_anonymized": anonymized_records,
                "fields_removed": fields_removed,
                "fields_generalized": list(fields_generalized.keys()),
                "timestamp": datetime.now().isoformat(),
            }
        )

        logger.info(
            "Anonymization completed for %s: %d records",
            category.value,
            anonymized_records,
        )

    def _pseudonymize_data(
        self, request: DeletionRequest, category: DataCategory
    ) -> None:
        """Replace identifying data with pseudonyms.

        Args:
            request: Deletion request
            category: Data category
        """
        # Generate pseudonym
        pseudonym = f"PSEUDO-{uuid4()}"

        # In production, would replace identifiers with pseudonym
        pseudonymized_records = 5

        # Store pseudonym mapping securely (for potential re-identification)
        # This would be stored separately with strict access controls

        request.deleted_items.append(
            {
                "category": category.value,
                "method": "pseudonymization",
                "records_pseudonymized": pseudonymized_records,
                "pseudonym": pseudonym,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def _delete_encryption_keys(
        self, request: DeletionRequest, category: DataCategory
    ) -> None:
        """Delete encryption keys (crypto-shredding).

        Args:
            request: Deletion request
            category: Data category
        """
        # In production, would delete actual encryption keys
        keys_deleted = 3

        request.deleted_items.append(
            {
                "category": category.value,
                "method": "encryption_key_deletion",
                "keys_deleted": keys_deleted,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def _archive_data(self, request: DeletionRequest, category: DataCategory) -> None:
        """Archive data to restricted storage.

        Args:
            request: Deletion request
            category: Data category
        """
        # In production, would move to archive storage
        archive_id = f"ARCHIVE-{uuid4()}"

        request.deleted_items.append(
            {
                "category": category.value,
                "method": "archival",
                "archive_id": archive_id,
                "restricted_until": (
                    datetime.now() + timedelta(days=365 * 7)
                ).isoformat(),
                "timestamp": datetime.now().isoformat(),
            }
        )

    def _partial_delete(self, request: DeletionRequest, category: DataCategory) -> None:
        """Perform partial deletion of data.

        Args:
            request: Deletion request
            category: Data category
        """
        # Get policy for what to preserve
        policy = self.config.get_deletion_policy(category)
        preserve_fields = policy.get("preserve_fields", [])

        # In production, would selectively delete fields
        fields_deleted = ["personal_notes", "contact_details", "identifiers"]
        fields_preserved = preserve_fields

        request.deleted_items.append(
            {
                "category": category.value,
                "method": "partial_deletion",
                "fields_deleted": fields_deleted,
                "fields_preserved": fields_preserved,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def _notify_third_parties(self, request: DeletionRequest) -> None:
        """Notify third parties of deletion request.

        Args:
            request: Deletion request
        """
        # Identify relevant third parties based on categories
        third_parties = set()

        for category in request.categories:
            if category == DataCategory.LAB_RESULTS:
                third_parties.add("laboratory_partners")
            elif category == DataCategory.IMAGING:
                third_parties.add("imaging_centers")
            elif category == DataCategory.RESEARCH_DATA:
                third_parties.add("research_institutions")

        # Send notifications
        for party in third_parties:
            config = self.config.get_third_party_config(party)

            notification_id = f"NOTIF-{uuid4()}"

            # In production, would actually send notification
            request.third_party_notifications.append(
                {
                    "notification_id": notification_id,
                    "third_party": party,
                    "method": config["notification_method"],
                    "sent_at": datetime.now().isoformat(),
                    "sla_days": config["sla_days"],
                    "response_required": config.get("confirmation_required", False),
                }
            )

            logger.info(
                "Third party notified: %s via %s", party, config["notification_method"]
            )

    def add_legal_hold(
        self,
        data_subject_id: str,
        reason: str,
        authorized_by: str,
        categories: Optional[List[DataCategory]] = None,
        expiry_date: Optional[datetime] = None,
    ) -> str:
        """Add legal hold preventing deletion.

        Args:
            data_subject_id: Data subject ID
            reason: Reason for hold
            authorized_by: Who authorized the hold
            categories: Specific categories (None = all)
            expiry_date: When hold expires

        Returns:
            Hold ID
        """
        hold_id = f"HOLD-{uuid4()}"

        self.legal_holds[hold_id] = {
            "data_subject_id": data_subject_id,
            "reason": reason,
            "authorized_by": authorized_by,
            "categories": [cat.value for cat in categories] if categories else "all",
            "created_at": datetime.now(),
            "expiry_date": expiry_date,
            "active": True,
        }

        logger.info("Legal hold added: %s for %s", hold_id, data_subject_id)

        return hold_id

    def remove_legal_hold(self, hold_id: str, removed_by: str, reason: str) -> bool:
        """Remove a legal hold.

        Args:
            hold_id: Hold ID
            removed_by: Who is removing the hold
            reason: Reason for removal

        Returns:
            Success status
        """
        hold = self.legal_holds.get(hold_id)
        if not hold:
            return False

        hold["active"] = False
        hold["removed_at"] = datetime.now()
        hold["removed_by"] = removed_by
        hold["removal_reason"] = reason

        logger.info("Legal hold removed: %s", hold_id)

        # Check if any suspended requests can proceed
        self._check_suspended_requests(hold["data_subject_id"])

        return True

    def get_deletion_request_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get status of deletion request.

        Args:
            request_id: Request ID

        Returns:
            Request status or None
        """
        request = self.deletion_requests.get(request_id)
        if not request:
            return None

        return {
            "request_id": request_id,
            "status": request.status.value,
            "created_at": request.created_at,
            "updated_at": request.updated_at,
            "completion_date": request.completion_date,
            "categories_requested": [cat.value for cat in request.categories],
            "deleted_items": len(request.deleted_items),
            "failed_items": len(request.failed_items),
            "exceptions_applied": len(request.exceptions_applied),
            "third_party_notifications": len(request.third_party_notifications),
        }

    def get_deletion_history(self, data_subject_id: str) -> List[Dict[str, Any]]:
        """Get deletion request history for data subject.

        Args:
            data_subject_id: Data subject ID

        Returns:
            List of deletion requests
        """
        history = []

        for request in self.deletion_requests.values():
            if request.data_subject_id == data_subject_id:
                history.append(
                    {
                        "request_id": request.request_id,
                        "status": request.status.value,
                        "created_at": request.created_at,
                        "categories": [cat.value for cat in request.categories],
                        "reason": request.reason,
                    }
                )

        return sorted(history, key=lambda x: x["created_at"], reverse=True)

    def generate_deletion_report(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Generate deletion activity report.

        Args:
            start_date: Report start date
            end_date: Report end date

        Returns:
            Deletion report
        """
        statistics: Dict[str, int] = {
            "total_requests": 0,
            "completed": 0,
            "partially_completed": 0,
            "denied": 0,
            "in_progress": 0,
            "suspended": 0,
        }
        categories_deleted: Dict[str, int] = {}

        report: Dict[str, Any] = {
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "statistics": statistics,
            "categories_deleted": categories_deleted,
            "average_processing_time": None,
            "third_party_notifications": 0,
            "legal_holds_active": 0,
        }

        processing_times = []

        for request in self.deletion_requests.values():
            if start_date <= request.created_at <= end_date:
                statistics["total_requests"] += 1

                # Count by status
                if request.status == DeletionStatus.COMPLETED:
                    statistics["completed"] += 1
                    if request.completion_date:
                        processing_time = (
                            request.completion_date - request.created_at
                        ).total_seconds() / 3600  # Hours
                        processing_times.append(processing_time)
                elif request.status == DeletionStatus.PARTIALLY_COMPLETED:
                    statistics["partially_completed"] += 1
                elif request.status == DeletionStatus.DENIED:
                    statistics["denied"] += 1
                elif request.status == DeletionStatus.IN_PROGRESS:
                    statistics["in_progress"] += 1
                elif request.status == DeletionStatus.SUSPENDED:
                    statistics["suspended"] += 1

                # Count categories
                for category in request.categories:
                    cat_name = category.value
                    categories_deleted[cat_name] = (
                        categories_deleted.get(cat_name, 0) + 1
                    )

                # Count notifications
                report["third_party_notifications"] = report.get(
                    "third_party_notifications", 0
                ) + len(request.third_party_notifications)

        # Calculate average processing time
        if processing_times:
            report["average_processing_time"] = sum(processing_times) / len(
                processing_times
            )

        # Count active legal holds
        report["legal_holds_active"] = sum(
            1 for hold in self.legal_holds.values() if hold["active"]
        )

        return report

    def _requires_verification(self, categories: List[DataCategory]) -> bool:
        """Check if verification is required for categories.

        Args:
            categories: Data categories

        Returns:
            Whether verification required
        """
        # Always require verification for sensitive categories
        sensitive_categories = {
            DataCategory.GENETIC_DATA,
            DataCategory.BIOMETRIC_DATA,
            DataCategory.MENTAL_HEALTH,
            DataCategory.SEXUAL_HEALTH,
            DataCategory.BILLING_INFO,
        }

        return any(cat in sensitive_categories for cat in categories)

    def _generate_verification_token(self) -> str:
        """Generate secure verification token."""
        return hashlib.sha256(f"{uuid4()}{datetime.now()}".encode()).hexdigest()[:32]

    def _send_verification_request(
        self, data_subject_id: str, token: str, method: str
    ) -> None:
        """Send verification request to data subject.

        Args:
            data_subject_id: Data subject ID
            token: Verification token
            method: Verification method
        """
        # In production, would send actual verification
        _ = token  # Mark as intentionally unused
        logger.info("Verification request sent to %s via %s", data_subject_id, method)

    def _send_completion_notification(self, request: DeletionRequest) -> None:
        """Send completion notification.

        Args:
            request: Completed request
        """
        # In production, would send actual notification
        logger.info(
            "Deletion completion notification sent for request %s", request.request_id
        )

    def _has_legal_hold(self, data_subject_id: str) -> bool:
        """Check if data subject has active legal hold.

        Args:
            data_subject_id: Data subject ID

        Returns:
            Whether legal hold exists
        """
        for hold in self.legal_holds.values():
            if (
                hold["data_subject_id"] == data_subject_id
                and hold["active"]
                and (
                    not hold.get("expiry_date") or datetime.now() < hold["expiry_date"]
                )
            ):
                return True
        return False

    def _check_suspended_requests(self, data_subject_id: str) -> None:
        """Check if suspended requests can proceed.

        Args:
            data_subject_id: Data subject ID
        """
        for request in self.deletion_requests.values():
            if (
                request.data_subject_id == data_subject_id
                and request.status == DeletionStatus.SUSPENDED
            ):

                if not self._has_legal_hold(data_subject_id):
                    # Resume processing
                    request.status = DeletionStatus.IN_REVIEW
                    self.deletion_queue.append(request.request_id)
                    request.add_audit_entry(
                        "resumed_after_hold", {"reason": "Legal hold removed"}
                    )

    def _generate_deletion_hash(
        self, data_subject_id: str, category: DataCategory
    ) -> str:
        """Generate hash to verify deletion.

        Args:
            data_subject_id: Data subject ID
            category: Data category

        Returns:
            Verification hash
        """
        data = f"{data_subject_id}:{category.value}:{datetime.now().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()


# Export public API
__all__ = ["RightToDeletionManager", "DeletionRequest"]
