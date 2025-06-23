"""Medical Translation Validation and Feedback System.

This module implements expert validation workflows and feedback loops
for medical translation accuracy, ensuring WHO compliance and clinical safety.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import boto3

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.security.encryption import EncryptionService
from src.translation.medical_terminology import MedicalTerminologyManager
from src.translation.quality.aws_ai.comprehend_medical import ComprehendMedicalValidator
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ValidationStatus(str, Enum):
    """Status of medical translation validation."""

    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class ExpertiseLevel(str, Enum):
    """Medical expertise level of validator."""

    MEDICAL_STUDENT = "medical_student"
    RESIDENT = "resident"
    SPECIALIST = "specialist"
    CONSULTANT = "consultant"
    LINGUIST = "linguist"
    NATIVE_SPEAKER = "native_speaker"


@dataclass
class ValidationFeedback:
    """Feedback from medical expert validation."""

    feedback_id: str = field(default_factory=lambda: str(uuid4()))
    translation_id: str = ""
    validator_id: str = ""
    validator_expertise: ExpertiseLevel = ExpertiseLevel.SPECIALIST
    validation_status: ValidationStatus = ValidationStatus.PENDING
    accuracy_score: float = 0.0  # 0-1 scale
    clinical_safety_score: float = 0.0  # 0-1 scale
    cultural_appropriateness_score: float = 0.0  # 0-1 scale
    comments: str = ""
    suggested_revision: Optional[str] = None
    specific_issues: List[str] = field(default_factory=list)
    validated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MedicalTranslationRecord:
    """Record of a medical translation for validation."""

    translation_id: str = field(default_factory=lambda: str(uuid4()))
    source_text: str = ""
    source_language: str = ""
    target_text: str = ""
    target_language: str = ""
    medical_domain: str = ""
    icd10_codes: List[str] = field(default_factory=list)
    critical_terms: List[str] = field(default_factory=list)
    context: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    validation_feedbacks: List[ValidationFeedback] = field(default_factory=list)
    final_status: Optional[ValidationStatus] = None
    final_translation: Optional[str] = None


class MedicalValidationFeedbackSystem:
    """
    Comprehensive medical translation validation system with expert feedback loops.

    Features:
    - Multi-tier expert validation
    - Automated pre-validation with AWS Comprehend Medical
    - Feedback aggregation and consensus building
    - Continuous improvement through feedback analysis
    - Clinical safety verification
    """

    def __init__(self, region: str = "us-east-1"):
        """Initialize the validation feedback system."""
        self.region = region
        self.comprehend_validator = ComprehendMedicalValidator(region)
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self.terminology_manager = MedicalTerminologyManager()

        # Storage
        self.translation_records: Dict[str, MedicalTranslationRecord] = {}
        self.validator_profiles: Dict[str, Dict[str, Any]] = {}
        self.validation_queue: List[str] = []

        # Feedback analysis
        self.feedback_patterns: Dict[str, List[str]] = {}
        self.improvement_suggestions: List[Dict[str, Any]] = []

        # Initialize AWS services
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.sns = boto3.client("sns", region_name=region)

    @require_phi_access(AccessLevel.WRITE)
    async def submit_for_validation(
        self,
        source_text: str,
        source_language: str,
        target_text: str,
        target_language: str,
        medical_domain: str,
        context: Optional[str] = None,
        icd10_codes: Optional[List[str]] = None,
    ) -> str:
        """
        Submit a medical translation for expert validation.

        Returns:
            Translation ID for tracking
        """
        # Pre-validate with AWS Comprehend Medical
        await self.comprehend_validator.validate_translation(
            source_text, source_language, target_text, target_language
        )

        # Extract critical medical terms
        critical_terms = await self._extract_critical_terms(source_text, medical_domain)

        # Create translation record
        record = MedicalTranslationRecord(
            source_text=source_text,
            source_language=source_language,
            target_text=target_text,
            target_language=target_language,
            medical_domain=medical_domain,
            context=context or "",
            icd10_codes=icd10_codes or [],
            critical_terms=critical_terms,
        )

        # Store record
        self.translation_records[record.translation_id] = record
        self.validation_queue.append(record.translation_id)

        # Notify validators
        await self._notify_validators(record)

        logger.info(
            "Translation %s submitted for validation in domain %s",
            record.translation_id,
            medical_domain,
        )

        return record.translation_id

    async def submit_validation_feedback(
        self,
        translation_id: str,
        validator_id: str,
        feedback: ValidationFeedback,
    ) -> None:
        """Submit expert validation feedback."""
        if translation_id not in self.translation_records:
            raise ValueError(f"Translation {translation_id} not found")

        # Add validator info
        feedback.translation_id = translation_id
        feedback.validator_id = validator_id

        # Store feedback
        record = self.translation_records[translation_id]
        record.validation_feedbacks.append(feedback)

        # Check if we have enough feedback for consensus
        if len(record.validation_feedbacks) >= 3:
            await self._evaluate_consensus(translation_id)

        logger.info(
            "Received validation feedback for %s from validator %s",
            translation_id,
            validator_id,
        )

    async def _evaluate_consensus(self, translation_id: str) -> None:
        """Evaluate consensus among validators."""
        record = self.translation_records[translation_id]
        feedbacks = record.validation_feedbacks

        # Calculate average scores
        accuracy_scores = [f.accuracy_score for f in feedbacks]
        safety_scores = [f.clinical_safety_score for f in feedbacks]

        avg_accuracy = sum(accuracy_scores) / len(accuracy_scores)
        avg_safety = sum(safety_scores) / len(safety_scores)

        # Determine consensus status
        approved_count = sum(
            1 for f in feedbacks if f.validation_status == ValidationStatus.APPROVED
        )
        rejected_count = sum(
            1 for f in feedbacks if f.validation_status == ValidationStatus.REJECTED
        )

        if approved_count >= 2 and avg_accuracy >= 0.9 and avg_safety >= 0.95:
            record.final_status = ValidationStatus.APPROVED
        elif rejected_count >= 2 or avg_safety < 0.8:
            record.final_status = ValidationStatus.REJECTED
        else:
            record.final_status = ValidationStatus.NEEDS_REVISION
            await self._aggregate_revision_suggestions(translation_id)

        # Notify about consensus
        await self._notify_consensus_reached(record)

        # Learn from feedback
        await self._analyze_feedback_patterns(record)

    async def _aggregate_revision_suggestions(self, translation_id: str) -> None:
        """Aggregate revision suggestions from multiple validators."""
        record = self.translation_records[translation_id]
        suggestions = [
            f.suggested_revision
            for f in record.validation_feedbacks
            if f.suggested_revision
        ]

        if suggestions:
            # In production, use NLP to merge similar suggestions
            # For now, take the most detailed suggestion
            record.final_translation = max(suggestions, key=len)

    async def _analyze_feedback_patterns(
        self, record: MedicalTranslationRecord
    ) -> None:
        """Analyze feedback to identify improvement patterns."""
        # Collect issues
        all_issues = []
        for feedback in record.validation_feedbacks:
            all_issues.extend(feedback.specific_issues)

        # Group by pattern
        pattern_key = (
            f"{record.source_language}-{record.target_language}-{record.medical_domain}"
        )
        if pattern_key not in self.feedback_patterns:
            self.feedback_patterns[pattern_key] = []

        self.feedback_patterns[pattern_key].extend(all_issues)

        # Generate improvement suggestions
        if len(self.feedback_patterns[pattern_key]) >= 10:
            suggestion = {
                "pattern": pattern_key,
                "common_issues": self._get_common_issues(
                    self.feedback_patterns[pattern_key]
                ),
                "recommendation": "Update translation model training data",
                "priority": (
                    "high"
                    if record.medical_domain in ["emergency", "medications"]
                    else "medium"
                ),
            }
            self.improvement_suggestions.append(suggestion)

    async def _extract_critical_terms(
        self, text: str, domain: str  # pylint: disable=unused-argument
    ) -> List[str]:
        """Extract critical medical terms that must be accurately translated."""
        # In production, use terminology manager to identify critical terms
        # For now, return empty list
        terms: List[Dict[str, Any]] = []

        # Filter by criticality
        critical_categories = ["medication", "dosage", "procedure", "diagnosis"]
        return [
            term.get("term", "")
            for term in terms
            if term.get("category") in critical_categories
        ]

    async def _notify_validators(self, record: MedicalTranslationRecord) -> None:
        """Notify appropriate validators about new translation."""
        # Select validators based on domain and languages
        validators = await self._select_validators(
            record.medical_domain, record.source_language, record.target_language
        )

        # Send notifications
        for validator_id in validators:
            # In production, send via SNS or email
            logger.info(
                "Notifying validator %s about translation %s",
                validator_id,
                record.translation_id,
            )

    async def _notify_consensus_reached(self, record: MedicalTranslationRecord) -> None:
        """Notify about consensus decision."""
        logger.info(
            "Consensus reached for translation %s: %s",
            record.translation_id,
            record.final_status,
        )

    def _get_common_issues(self, issues: List[str]) -> List[Tuple[str, int]]:
        """Get most common issues from feedback."""
        issue_counts = Counter(issues)
        return issue_counts.most_common(5)

    async def _select_validators(
        self,
        domain: str,  # pylint: disable=unused-argument
        source_lang: str,  # pylint: disable=unused-argument
        target_lang: str,  # pylint: disable=unused-argument
    ) -> List[str]:
        """Select appropriate validators for the translation."""
        # In production, query validator database
        # For now, return mock validator IDs
        return ["validator_1", "validator_2", "validator_3"]

    def get_validation_metrics(self) -> Dict[str, Any]:
        """Get overall validation metrics."""
        total_validations = len(self.translation_records)
        approved = sum(
            1
            for r in self.translation_records.values()
            if r.final_status == ValidationStatus.APPROVED
        )
        rejected = sum(
            1
            for r in self.translation_records.values()
            if r.final_status == ValidationStatus.REJECTED
        )

        return {
            "total_validations": total_validations,
            "approved": approved,
            "rejected": rejected,
            "approval_rate": (
                approved / total_validations if total_validations > 0 else 0
            ),
            "common_issues": dict(self.feedback_patterns),
            "improvement_suggestions": self.improvement_suggestions,
        }
