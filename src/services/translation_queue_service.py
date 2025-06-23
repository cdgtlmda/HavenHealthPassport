"""Translation queue service for managing human translation fallback. Handles FHIR Resource validation.

Security Note: This module processes PHI data. All translation data must be:
- Encrypted at rest using AES-256 encryption
- Subject to role-based access control (RBAC) for PHI protection
"""

import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import requests
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from src.models.callback_task import CallbackTask, CallbackTaskStatus
from src.models.translation_queue import (
    TranslationQueue,
    TranslationQueueAssignment,
    TranslationQueueFeedback,
    TranslationQueuePriority,
    TranslationQueueReason,
    TranslationQueueStatus,
)
from src.services.base import BaseService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class TranslationQueueService(BaseService[TranslationQueue]):
    """Service for managing the human translation queue."""

    model_class = TranslationQueue

    # Queue configuration
    DEFAULT_EXPIRY_HOURS = 72  # 3 days
    MAX_RETRY_ATTEMPTS = 3
    RETRY_BACKOFF_HOURS = [1, 4, 12]  # Exponential backoff

    # Confidence thresholds
    CONFIDENCE_THRESHOLD_CRITICAL = 0.6
    CONFIDENCE_THRESHOLD_HIGH = 0.7
    CONFIDENCE_THRESHOLD_NORMAL = 0.8

    # Medical complexity indicators
    COMPLEX_MEDICAL_INDICATORS = [
        "surgery",
        "procedure",
        "diagnosis",
        "complication",
        "adverse",
        "reaction",
        "allergy",
        "contraindication",
        "dosage adjustment",
        "drug interaction",
    ]

    def __init__(self, session: Session):
        """Initialize translation queue service."""
        super().__init__(session)
        self.notification_service = None  # Will be injected if available

    def should_queue_translation(
        self,
        confidence_score: float,
        medical_validation: Dict[str, Any],
        translation_type: str,
        medical_terms_count: int,
        user_requested: bool = False,
    ) -> Tuple[
        bool, Optional[TranslationQueueReason], Optional[TranslationQueuePriority]
    ]:
        """
        Determine if a translation should be queued for human review.

        Args:
            confidence_score: Bedrock translation confidence
            medical_validation: Medical validation results
            translation_type: Type of translation
            medical_terms_count: Number of medical terms detected
            user_requested: Whether user explicitly requested human translation

        Returns:
            Tuple of (should_queue, reason, priority)
        """
        # Always queue if user requested
        if user_requested:
            return (
                True,
                TranslationQueueReason.USER_REQUEST,
                TranslationQueuePriority.HIGH,
            )

        # Check for validation failures
        if medical_validation and medical_validation.get("errors"):
            return (
                True,
                TranslationQueueReason.VALIDATION_FAILED,
                TranslationQueuePriority.CRITICAL,
            )

        # Check confidence thresholds based on content type
        if translation_type in ["medication", "diagnosis", "procedure"]:
            # Critical medical content - higher standards
            if confidence_score < self.CONFIDENCE_THRESHOLD_HIGH:
                priority = (
                    TranslationQueuePriority.CRITICAL
                    if confidence_score < self.CONFIDENCE_THRESHOLD_CRITICAL
                    else TranslationQueuePriority.HIGH
                )
                return True, TranslationQueueReason.LOW_CONFIDENCE, priority
        else:
            # General content
            if confidence_score < self.CONFIDENCE_THRESHOLD_NORMAL:
                priority = (
                    TranslationQueuePriority.HIGH
                    if confidence_score < self.CONFIDENCE_THRESHOLD_HIGH
                    else TranslationQueuePriority.NORMAL
                )
                return True, TranslationQueueReason.LOW_CONFIDENCE, priority

        # Check for complex medical content
        if medical_terms_count > 5 or (
            medical_validation and len(medical_validation.get("warnings", [])) > 2
        ):
            return (
                True,
                TranslationQueueReason.COMPLEX_MEDICAL,
                TranslationQueuePriority.HIGH,
            )

        # Don't queue - translation is acceptable
        return False, None, None

    def queue_translation(
        self,
        source_text: str,
        source_language: str,
        target_language: str,
        translation_type: str,
        translation_context: str,
        requested_by: UUID,
        queue_reason: TranslationQueueReason,
        priority: TranslationQueuePriority = TranslationQueuePriority.NORMAL,
        bedrock_translation: Optional[str] = None,
        bedrock_confidence_score: Optional[float] = None,
        bedrock_error: Optional[str] = None,
        medical_validation: Optional[Dict[str, Any]] = None,
        medical_terms: Optional[Dict[str, Any]] = None,
        target_dialect: Optional[str] = None,
        patient_id: Optional[UUID] = None,
        document_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
        organization_id: Optional[UUID] = None,
        callback_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TranslationQueue:
        """
        Add a translation to the human review queue.

        Args:
            Various translation parameters and metadata

        Returns:
            Created queue entry
        """
        try:
            # Calculate expiry time based on priority
            expiry_hours = {
                TranslationQueuePriority.CRITICAL: 24,
                TranslationQueuePriority.HIGH: 48,
                TranslationQueuePriority.NORMAL: 72,
                TranslationQueuePriority.LOW: 168,  # 1 week
            }

            expires_at = datetime.utcnow() + timedelta(
                hours=expiry_hours.get(priority, self.DEFAULT_EXPIRY_HOURS)
            )

            # Extract medical category if available
            medical_category = None
            if medical_terms:
                # Determine primary medical category
                categories = list(medical_terms.keys())
                if categories:
                    medical_category = categories[0]

            # Create queue entry
            queue_entry = TranslationQueue(
                source_text=source_text,
                source_language=source_language,
                target_language=target_language,
                target_dialect=target_dialect,
                translation_type=translation_type,
                translation_context=translation_context,
                status=TranslationQueueStatus.PENDING,
                priority=priority,
                queue_reason=queue_reason,
                bedrock_translation=bedrock_translation,
                bedrock_confidence_score=bedrock_confidence_score,
                bedrock_error=bedrock_error,
                bedrock_medical_validation=medical_validation,
                medical_terms_detected=medical_terms,
                medical_category=medical_category,
                patient_id=patient_id,
                document_id=document_id,
                session_id=session_id,
                requested_by=requested_by,
                organization_id=organization_id,
                callback_url=callback_url,
                metadata=metadata,
                expires_at=expires_at,
            )

            self.session.add(queue_entry)
            self.session.commit()

            # Send alerts for critical translations
            if priority == TranslationQueuePriority.CRITICAL:
                self._send_critical_translation_alert(queue_entry)

            # Log queue entry
            logger.info(
                f"Queued translation for human review - "
                f"ID: {queue_entry.id}, Priority: {priority}, "
                f"Reason: {queue_reason}, Languages: {source_language}->{target_language}"
            )

            return queue_entry

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"Error queuing translation: {e}")
            self.session.rollback()
            raise

    def get_pending_translations(
        self,
        translator_id: Optional[UUID] = None,
        language_pair: Optional[Tuple[str, str]] = None,
        priority: Optional[TranslationQueuePriority] = None,
        medical_category: Optional[str] = None,
        limit: int = 10,
    ) -> List[TranslationQueue]:
        """
        Get pending translations from the queue.

        Args:
            translator_id: Filter by assigned translator
            language_pair: Filter by (source, target) language pair
            priority: Filter by priority level
            medical_category: Filter by medical category
            limit: Maximum number of entries to return

        Returns:
            List of pending queue entries
        """
        query = self.session.query(TranslationQueue).filter(
            TranslationQueue.status == TranslationQueueStatus.PENDING,
            or_(
                TranslationQueue.expires_at.is_(None),
                TranslationQueue.expires_at > datetime.utcnow(),
            ),
        )

        # Apply filters
        if translator_id:
            # Get entries assigned to this translator
            assigned_ids = (
                self.session.query(TranslationQueueAssignment.queue_entry_id)
                .filter(
                    TranslationQueueAssignment.translator_id == translator_id,
                    TranslationQueueAssignment.status == "active",
                )
                .subquery()
            )

            # Convert subquery to list for in_ operator
            assigned_ids_list = self.session.query(assigned_ids).all()
            query = query.filter(
                TranslationQueue.id.in_([id[0] for id in assigned_ids_list])
            )

        if language_pair:
            source_lang, target_lang = language_pair
            query = query.filter(
                TranslationQueue.source_language == source_lang,
                TranslationQueue.target_language == target_lang,
            )

        if priority:
            query = query.filter(TranslationQueue.priority == priority)

        if medical_category:
            query = query.filter(TranslationQueue.medical_category == medical_category)

        # Order by priority and creation time
        priority_order = {
            TranslationQueuePriority.CRITICAL: 1,
            TranslationQueuePriority.HIGH: 2,
            TranslationQueuePriority.NORMAL: 3,
            TranslationQueuePriority.LOW: 4,
        }

        entries = (
            query.order_by(
                func.case(priority_order, value=TranslationQueue.priority),
                TranslationQueue.created_at,
            )
            .limit(limit)
            .all()
        )

        return entries

    def assign_translation(
        self,
        queue_entry_id: UUID,
        translator_id: UUID,
        assigned_by: UUID,
        language_pair_certified: bool = False,
        medical_specialty_match: Optional[str] = None,
        dialect_expertise: Optional[str] = None,
        assignment_reason: Optional[str] = None,
    ) -> TranslationQueueAssignment:
        """
        Assign a translation to a specific translator.

        Args:
            queue_entry_id: Queue entry to assign
            translator_id: Translator to assign to
            assigned_by: User making the assignment
            language_pair_certified: Whether translator is certified for this language pair
            medical_specialty_match: Matching medical specialty
            dialect_expertise: Dialect expertise match
            assignment_reason: Reason for assignment

        Returns:
            Assignment record
        """
        try:
            # Update queue entry
            queue_entry = self.get_by_id(queue_entry_id)
            if not queue_entry:
                raise ValueError(f"Queue entry {queue_entry_id} not found")

            if queue_entry.status != TranslationQueueStatus.PENDING:
                raise ValueError(f"Queue entry {queue_entry_id} is not pending")

            # Create assignment
            assignment = TranslationQueueAssignment(
                queue_entry_id=queue_entry_id,
                translator_id=translator_id,
                assigned_by=assigned_by,
                assignment_reason=assignment_reason,
                language_pair_certified=language_pair_certified,
                medical_specialty_match=medical_specialty_match,
                dialect_expertise=dialect_expertise,
                status="active",
            )

            # Update queue entry
            queue_entry.translator_id = translator_id
            queue_entry.assigned_at = datetime.utcnow()  # type: ignore[assignment]

            self.session.add(assignment)
            self.session.commit()

            logger.info(
                f"Assigned translation {queue_entry_id} to translator {translator_id}"
            )

            return assignment

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"Error assigning translation: {e}")
            self.session.rollback()
            raise

    def start_translation(
        self, queue_entry_id: UUID, translator_id: UUID
    ) -> TranslationQueue:
        """
        Mark a translation as started by a translator.

        Args:
            queue_entry_id: Queue entry ID
            translator_id: Translator starting the work

        Returns:
            Updated queue entry
        """
        try:
            queue_entry = self.get_by_id(queue_entry_id)
            if not queue_entry:
                raise ValueError(f"Queue entry {queue_entry_id} not found")

            if queue_entry.translator_id != translator_id:
                raise ValueError(
                    f"Translation not assigned to translator {translator_id}"
                )

            if queue_entry.status not in [
                TranslationQueueStatus.PENDING,
                TranslationQueueStatus.FAILED,
            ]:
                raise ValueError(f"Invalid status for starting: {queue_entry.status}")

            queue_entry.status = TranslationQueueStatus.IN_PROGRESS.value  # type: ignore[assignment]
            queue_entry.started_at = datetime.utcnow()  # type: ignore[assignment]

            self.session.commit()

            logger.info(f"Started translation {queue_entry_id}")

            return queue_entry

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"Error starting translation: {e}")
            self.session.rollback()
            raise

    def complete_translation(
        self,
        queue_entry_id: UUID,
        translator_id: UUID,
        human_translation: str,
        translation_notes: Optional[str] = None,
        quality_score: Optional[float] = None,
        cultural_notes: Optional[List[str]] = None,
    ) -> TranslationQueue:
        """
        Complete a human translation.

        Args:
            queue_entry_id: Queue entry ID
            translator_id: Translator completing the work
            human_translation: The translated text
            translation_notes: Notes from translator
            quality_score: Self-assessed quality score
            cultural_notes: Cultural considerations

        Returns:
            Updated queue entry
        """
        try:
            queue_entry = self.get_by_id(queue_entry_id)
            if not queue_entry:
                raise ValueError(f"Queue entry {queue_entry_id} not found")

            if queue_entry.translator_id != translator_id:
                raise ValueError(
                    f"Translation not assigned to translator {translator_id}"
                )

            if queue_entry.status != TranslationQueueStatus.IN_PROGRESS:
                raise ValueError(f"Translation not in progress: {queue_entry.status}")

            # Update queue entry
            queue_entry.status = TranslationQueueStatus.COMPLETED.value  # type: ignore[assignment]
            queue_entry.human_translation = human_translation  # type: ignore[assignment]
            queue_entry.translation_notes = translation_notes  # type: ignore[assignment]
            queue_entry.quality_score = quality_score  # type: ignore[assignment]
            queue_entry.cultural_notes = cultural_notes
            queue_entry.completed_at = datetime.utcnow()  # type: ignore[assignment]

            # Update assignment
            assignment = (
                self.session.query(TranslationQueueAssignment)
                .filter(
                    TranslationQueueAssignment.queue_entry_id == queue_entry_id,
                    TranslationQueueAssignment.translator_id == translator_id,
                    TranslationQueueAssignment.status == "active",
                )
                .first()
            )

            if assignment:
                assignment.status = "completed"
                assignment.completed_at = datetime.utcnow()

            self.session.commit()

            # Trigger callback if configured
            if queue_entry.callback_url:
                self._trigger_completion_callback(queue_entry)

            logger.info(f"Completed translation {queue_entry_id}")

            return queue_entry

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"Error completing translation: {e}")
            self.session.rollback()
            raise

    def retry_translation(
        self, queue_entry_id: UUID, retry_reason: str
    ) -> TranslationQueue:
        """
        Retry a failed translation.

        Args:
            queue_entry_id: Queue entry to retry
            retry_reason: Reason for retry

        Returns:
            Updated queue entry
        """
        try:
            queue_entry = self.get_by_id(queue_entry_id)
            if not queue_entry:
                raise ValueError(f"Queue entry {queue_entry_id} not found")

            if queue_entry.retry_count >= self.MAX_RETRY_ATTEMPTS:
                raise ValueError(
                    f"Maximum retry attempts ({self.MAX_RETRY_ATTEMPTS}) exceeded"
                )

            # Reset status and increment retry count
            queue_entry.status = TranslationQueueStatus.PENDING.value  # type: ignore[assignment]
            queue_entry.retry_count = queue_entry.retry_count + 1  # type: ignore[assignment]
            queue_entry.last_retry_at = datetime.utcnow()  # type: ignore[assignment]

            # Update metadata with retry info
            if not queue_entry.metadata:
                queue_entry.metadata = {}

            if "retry_history" not in queue_entry.metadata:
                queue_entry.metadata["retry_history"] = []

            queue_entry.metadata["retry_history"].append(
                {
                    "attempt": queue_entry.retry_count,
                    "reason": retry_reason,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            # Extend expiry if needed
            retry_index = min(int(queue_entry.retry_count) - 1, 2)
            new_expiry = datetime.utcnow() + timedelta(
                hours=self.RETRY_BACKOFF_HOURS[retry_index]
            )
            if not queue_entry.expires_at or queue_entry.expires_at < new_expiry:
                queue_entry.expires_at = new_expiry

            self.session.commit()

            logger.info(
                f"Retrying translation {queue_entry_id} (attempt {queue_entry.retry_count})"
            )

            return queue_entry

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"Error retrying translation: {e}")
            self.session.rollback()
            raise

    def add_feedback(
        self,
        queue_entry_id: UUID,
        feedback_by: UUID,
        feedback_type: str,
        rating: int,
        feedback_role: str,
        comments: Optional[str] = None,
        terminology_issues: Optional[List[Dict[str, str]]] = None,
        suggested_corrections: Optional[Dict[str, str]] = None,
    ) -> TranslationQueueFeedback:
        """
        Add feedback for a completed translation.

        Args:
            queue_entry_id: Queue entry to provide feedback for
            feedback_by: User providing feedback
            feedback_type: Type of feedback (accuracy, clarity, terminology)
            rating: Rating 1-5
            feedback_role: Role of feedback provider
            comments: Additional comments
            terminology_issues: Issues with medical terminology
            suggested_corrections: Suggested corrections

        Returns:
            Feedback record
        """
        try:
            # Validate queue entry exists and is completed
            queue_entry = self.get_by_id(queue_entry_id)
            if not queue_entry:
                raise ValueError(f"Queue entry {queue_entry_id} not found")

            if queue_entry.status != TranslationQueueStatus.COMPLETED:
                raise ValueError("Can only provide feedback for completed translations")

            # Validate rating
            if rating < 1 or rating > 5:
                raise ValueError("Rating must be between 1 and 5")

            # Create feedback
            feedback = TranslationQueueFeedback(
                queue_entry_id=queue_entry_id,
                feedback_type=feedback_type,
                rating=rating,
                comments=comments,
                feedback_by=feedback_by,
                feedback_role=feedback_role,
                terminology_issues=terminology_issues,
                suggested_corrections=suggested_corrections,
            )

            self.session.add(feedback)

            # Update average quality score for the queue entry
            avg_rating = (
                self.session.query(func.avg(TranslationQueueFeedback.rating))
                .filter(TranslationQueueFeedback.queue_entry_id == queue_entry_id)
                .scalar()
            )

            if avg_rating is not None:
                queue_entry.quality_score = avg_rating

            self.session.commit()

            logger.info(f"Added feedback for translation {queue_entry_id}")

            return feedback

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"Error adding feedback: {e}")
            self.session.rollback()
            raise

    def get_queue_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        organization_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Get queue statistics.

        Args:
            start_date: Start date for statistics
            end_date: End date for statistics
            organization_id: Filter by organization

        Returns:
            Dictionary of statistics
        """
        query = self.session.query(TranslationQueue)

        if start_date:
            query = query.filter(TranslationQueue.created_at >= start_date)
        if end_date:
            query = query.filter(TranslationQueue.created_at <= end_date)
        if organization_id:
            query = query.filter(TranslationQueue.organization_id == organization_id)

        # Status counts
        status_counts = {}
        for status in TranslationQueueStatus:
            count = query.filter(TranslationQueue.status == status).count()
            status_counts[status.value] = count

        # Priority counts
        priority_counts = {}
        for priority in TranslationQueuePriority:
            count = query.filter(TranslationQueue.priority == priority).count()
            priority_counts[priority.value] = count

        # Reason counts
        reason_counts = {}
        for reason in TranslationQueueReason:
            count = query.filter(TranslationQueue.queue_reason == reason).count()
            reason_counts[reason.value] = count

        # Average processing time for completed translations
        completed_query = query.filter(
            TranslationQueue.status == TranslationQueueStatus.COMPLETED,
            TranslationQueue.started_at.isnot(None),
            TranslationQueue.completed_at.isnot(None),
        )

        avg_processing_time = None
        completed_entries = completed_query.all()
        if completed_entries:
            total_time = timedelta()
            for entry in completed_entries:
                total_time += entry.completed_at - entry.started_at
            avg_processing_time = total_time / len(completed_entries)

        # Language pair statistics
        language_pairs = (
            self.session.query(
                TranslationQueue.source_language,
                TranslationQueue.target_language,
                func.count(TranslationQueue.id),  # pylint: disable=not-callable
            )
            .group_by(
                TranslationQueue.source_language, TranslationQueue.target_language
            )
            .all()
        )

        language_pair_stats = {
            f"{src}->{tgt}": count for src, tgt, count in language_pairs
        }

        # Average quality scores
        avg_quality = (
            self.session.query(func.avg(TranslationQueue.quality_score))
            .filter(TranslationQueue.quality_score.isnot(None))
            .scalar()
        )

        return {
            "total_entries": query.count(),
            "status_breakdown": status_counts,
            "priority_breakdown": priority_counts,
            "reason_breakdown": reason_counts,
            "average_processing_time": (
                str(avg_processing_time) if avg_processing_time else None
            ),
            "language_pairs": language_pair_stats,
            "average_quality_score": float(avg_quality) if avg_quality else None,
            "pending_critical": query.filter(
                TranslationQueue.status == TranslationQueueStatus.PENDING,
                TranslationQueue.priority == TranslationQueuePriority.CRITICAL,
            ).count(),
        }

    def cleanup_expired_entries(self) -> int:
        """
        Clean up expired queue entries.

        Returns:
            Number of entries cleaned up
        """
        try:
            expired_entries = (
                self.session.query(TranslationQueue)
                .filter(
                    TranslationQueue.status == TranslationQueueStatus.PENDING,
                    TranslationQueue.expires_at <= datetime.utcnow(),
                )
                .all()
            )

            count = 0
            for entry in expired_entries:
                entry.status = TranslationQueueStatus.EXPIRED
                count += 1

            if count > 0:
                self.session.commit()
                logger.info(f"Marked {count} queue entries as expired")

            return count

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"Error cleaning up expired entries: {e}")
            self.session.rollback()
            return 0

    def _send_critical_translation_alert(self, queue_entry: TranslationQueue) -> None:
        """Send alert for critical translation requests."""
        try:
            message = (
                f"Critical translation request queued:\n"
                f"Languages: {queue_entry.source_language} -> {queue_entry.target_language}\n"
                f"Type: {queue_entry.translation_type}\n"
                f"Reason: {queue_entry.queue_reason}\n"
                f"Patient ID: {queue_entry.patient_id}"
            )

            # Alert disabled - send_alert not available
            logger.critical(message)
        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"Error sending critical translation alert: {e}")

    def _trigger_completion_callback(self, queue_entry: TranslationQueue) -> None:
        """Trigger callback URL when translation is completed."""
        try:
            if not queue_entry.callback_url:
                return

            # In production, this would make an HTTP POST request
            logger.info(
                f"Triggering callback for translation {queue_entry.id} "
                f"to URL: {queue_entry.callback_url}"
            )

            # Prepare callback data
            callback_data = {
                "translation_id": str(queue_entry.id),
                "status": queue_entry.status.value,
                "human_translation": queue_entry.human_translation,
                "source_language": queue_entry.source_language,
                "target_language": queue_entry.target_language,
                "translation_type": queue_entry.translation_type,
                "quality_score": queue_entry.quality_score,
                "completed_at": (
                    queue_entry.completed_at.isoformat()
                    if queue_entry.completed_at
                    else None
                ),
                "metadata": queue_entry.metadata or {},
            }

            # Add medical context if present
            if queue_entry.translation_type == "medical":
                callback_data["medical_context"] = {
                    "terminology_used": (
                        queue_entry.metadata.get("medical_terms", [])
                        if queue_entry.metadata
                        else []
                    ),
                    "dosage_conversions": (
                        queue_entry.metadata.get("dosage_conversions", {})
                        if queue_entry.metadata
                        else {}
                    ),
                    "warnings": (
                        queue_entry.metadata.get("translation_warnings", [])
                        if queue_entry.metadata
                        else []
                    ),
                }

            headers = {
                "Content-Type": "application/json",
                "X-Translation-ID": str(queue_entry.id),
                "X-Haven-Signature": self._generate_webhook_signature(callback_data),
            }

            # Queue the callback for async processing
            # This avoids blocking the main thread and allows for proper retry logic
            self._queue_async_callback(
                queue_entry.id, queue_entry.callback_url, callback_data, headers
            )

            logger.info(f"Queued callback for translation {queue_entry.id}")

        except (ValueError, KeyError, AttributeError, TypeError) as e:
            logger.error(f"Error triggering completion callback: {e}")

    def _queue_async_callback(
        self,
        translation_id: UUID,
        callback_url: str,
        callback_data: Dict[str, Any],
        headers: Dict[str, str],
    ) -> None:
        """Queue callback for async processing via task queue."""
        try:
            # Create a callback task entry in the database
            callback_task = CallbackTask(
                entity_type="translation_queue",
                entity_id=translation_id,
                callback_url=callback_url,
                payload=callback_data,
                headers=headers,
                status=CallbackTaskStatus.PENDING,
                max_retries=3,
                retry_count=0,
                priority=(
                    "high"
                    if callback_data.get("translation_type") == "medical"
                    else "normal"
                ),
            )

            self.session.add(callback_task)
            self.session.commit()

            logger.info(f"Created callback task for translation {translation_id}")

        except (ValueError, KeyError, AttributeError, TypeError) as e:
            # If we can't queue it, try synchronous as a fallback
            logger.error(f"Failed to queue callback task: {e}")
            self._execute_sync_callback(callback_url, callback_data, headers)

    def _execute_sync_callback(
        self, callback_url: str, callback_data: Dict[str, Any], headers: Dict[str, str]
    ) -> None:
        """Execute callback synchronously as a fallback."""
        try:
            # Make synchronous request with short timeout
            response = requests.post(
                callback_url,
                json=callback_data,
                headers=headers,
                timeout=5,  # 5 second timeout for sync calls
            )

            if response.status_code in [200, 201, 204]:
                logger.info(
                    f"Sync callback successful for translation {callback_data['translation_id']}"
                )
            else:
                logger.warning(
                    f"Sync callback failed with status {response.status_code} "
                    f"for translation {callback_data['translation_id']}"
                )

        except (requests.RequestException, ValueError, KeyError, TypeError) as e:
            logger.error(
                f"Sync callback failed for translation {callback_data['translation_id']}: {e}"
            )

    def _generate_webhook_signature(self, data: Dict[str, Any]) -> str:
        """Generate HMAC signature for webhook security."""
        webhook_secret = os.getenv("WEBHOOK_SECRET", "default-secret")
        payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
        signature = hmac.new(
            webhook_secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()

        return signature

    def validate_translation_data(self, translation_data: Dict[str, Any]) -> bool:
        """Validate translation data."""
        required_fields = ["source_text", "source_language", "target_language"]
        for field in required_fields:
            if field not in translation_data or not translation_data[field]:
                return False
        return True
