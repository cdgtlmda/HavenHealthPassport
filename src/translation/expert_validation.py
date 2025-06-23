"""Expert Validation System for Medical Translations.

This module implements expert validation for medical translations,
including expert profiling, validation workflows, and quality scoring.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Session

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.models.base import BaseModel
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ExpertiseLevel(str, Enum):
    """Levels of medical expertise."""

    STUDENT = "student"
    RESIDENT = "resident"
    SPECIALIST = "specialist"
    CONSULTANT = "consultant"
    PROFESSOR = "professor"


class MedicalSpecialty(str, Enum):
    """Medical specialties for expert validation."""

    GENERAL_PRACTICE = "general_practice"
    INTERNAL_MEDICINE = "internal_medicine"
    PEDIATRICS = "pediatrics"
    OBSTETRICS_GYNECOLOGY = "obstetrics_gynecology"
    EMERGENCY_MEDICINE = "emergency_medicine"
    INFECTIOUS_DISEASES = "infectious_diseases"
    TROPICAL_MEDICINE = "tropical_medicine"
    PUBLIC_HEALTH = "public_health"
    PSYCHIATRY = "psychiatry"
    PHARMACY = "pharmacy"
    NURSING = "nursing"


class ValidationDomain(str, Enum):
    """Domains of validation expertise."""

    CLINICAL_ACCURACY = "clinical_accuracy"
    PHARMACOLOGY = "pharmacology"
    MEDICAL_PROCEDURES = "medical_procedures"
    DIAGNOSTIC_INTERPRETATION = "diagnostic_interpretation"
    PATIENT_COMMUNICATION = "patient_communication"
    CULTURAL_APPROPRIATENESS = "cultural_appropriateness"


@dataclass
class ExpertProfile:
    """Profile of a medical expert validator."""

    expert_id: UUID
    name: str
    credentials: List[str]  # MD, PharmD, RN, etc.
    specialties: List[MedicalSpecialty]
    expertise_level: ExpertiseLevel
    languages: List[str]  # Languages they can validate
    validation_domains: List[ValidationDomain]
    years_experience: int
    refugee_health_experience: bool = False
    certifications: List[str] = field(default_factory=list)
    availability_hours_per_week: int = 10


@dataclass
class ValidationRequest:
    """Request for expert validation."""

    request_id: UUID
    translation_id: UUID
    source_text: str
    translated_text: str
    source_language: str
    target_language: str
    content_type: str
    medical_context: Dict[str, Any]
    required_expertise: List[ValidationDomain]
    priority: str
    deadline: datetime


@dataclass
class ExpertValidationResult:
    """Result of expert validation."""

    validation_id: UUID
    request_id: UUID
    expert_id: UUID
    is_clinically_accurate: bool
    confidence_score: float  # 0-1
    issues_found: List[Dict[str, Any]]
    recommendations: List[str]
    approved_with_changes: bool
    suggested_changes: Optional[str]
    validation_notes: str
    validated_at: datetime


class MedicalExpert(BaseModel):
    """Database model for medical experts."""

    __tablename__ = "medical_experts"

    # Expert identification
    expert_id = Column(String(36), default=lambda: str(uuid4()), unique=True)
    user_id = Column(String(36), nullable=False, unique=True)

    # Professional information
    full_name = Column(String(200), nullable=False)
    credentials = Column(JSON, default=list)
    specialties = Column(JSON, default=list)
    expertise_level = Column(String(30), nullable=False)

    # Qualifications
    medical_license_number = Column(String(100))
    license_country = Column(String(100))
    years_experience = Column(Integer, default=0)
    certifications = Column(JSON, default=list)

    # Validation capabilities
    languages = Column(JSON, default=list)
    validation_domains = Column(JSON, default=list)
    refugee_health_experience = Column(Boolean, default=False)

    # Performance metrics
    validations_completed = Column(Integer, default=0)
    average_confidence_score = Column(Float, default=0.0)
    approval_rate = Column(Float, default=0.0)
    average_response_time_hours = Column(Float, default=0.0)

    # Availability
    is_active = Column(Boolean, default=True)
    availability_hours_per_week = Column(Integer, default=10)
    preferred_content_types = Column(JSON, default=list)

    # Metadata
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_validation_at = Column(DateTime)
    verification_status = Column(String(30), default="pending")
    verified_at = Column(DateTime)


class ExpertValidation(BaseModel):
    """Database model for expert validations."""

    __tablename__ = "expert_validations"

    # Validation identification
    validation_id = Column(String(36), default=lambda: str(uuid4()), unique=True)
    request_id = Column(String(36), nullable=False, index=True)
    expert_id = Column(String(36), nullable=False, index=True)

    # Content
    source_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=False)
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)
    content_type = Column(String(50))

    # Validation results
    is_clinically_accurate = Column(Boolean, nullable=False)
    confidence_score = Column(Float, nullable=False)
    approved_with_changes = Column(Boolean, default=False)
    suggested_changes = Column(Text)

    # Detailed findings
    issues_found = Column(JSON, default=list)
    recommendations = Column(JSON, default=list)
    validation_notes = Column(Text)

    # Clinical checks performed
    terminology_checked = Column(Boolean, default=False)
    dosage_verified = Column(Boolean, default=False)
    contraindications_reviewed = Column(Boolean, default=False)
    cultural_appropriateness_checked = Column(Boolean, default=False)

    # Metadata
    requested_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    time_spent_minutes = Column(Integer)


class ExpertValidationService:
    """Service for managing expert validation of medical translations."""

    # Expertise requirements by content type
    CONTENT_EXPERTISE_MAP = {
        "prescription": [
            ValidationDomain.PHARMACOLOGY,
            ValidationDomain.CLINICAL_ACCURACY,
        ],
        "diagnosis": [
            ValidationDomain.CLINICAL_ACCURACY,
            ValidationDomain.DIAGNOSTIC_INTERPRETATION,
        ],
        "procedure": [
            ValidationDomain.MEDICAL_PROCEDURES,
            ValidationDomain.CLINICAL_ACCURACY,
        ],
        "patient_instructions": [
            ValidationDomain.PATIENT_COMMUNICATION,
            ValidationDomain.CULTURAL_APPROPRIATENESS,
        ],
        "lab_results": [
            ValidationDomain.DIAGNOSTIC_INTERPRETATION,
            ValidationDomain.CLINICAL_ACCURACY,
        ],
    }

    # Minimum expertise levels by content type
    MIN_EXPERTISE_LEVEL = {
        "prescription": ExpertiseLevel.SPECIALIST,
        "diagnosis": ExpertiseLevel.SPECIALIST,
        "procedure": ExpertiseLevel.CONSULTANT,
        "patient_instructions": ExpertiseLevel.RESIDENT,
        "lab_results": ExpertiseLevel.SPECIALIST,
    }

    def __init__(self, session: Session):
        """Initialize expert validation service."""
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default", region="us-east-1"
        )
        self.session = session

    def register_expert(self, user_id: UUID, profile: ExpertProfile) -> MedicalExpert:
        """Register a new medical expert."""
        expert = MedicalExpert(
            user_id=str(user_id),
            full_name=profile.name,
            credentials=profile.credentials,
            specialties=[s.value for s in profile.specialties],
            expertise_level=profile.expertise_level.value,
            years_experience=profile.years_experience,
            languages=profile.languages,
            validation_domains=[d.value for d in profile.validation_domains],
            refugee_health_experience=profile.refugee_health_experience,
            certifications=profile.certifications,
            availability_hours_per_week=profile.availability_hours_per_week,
        )

        self.session.add(expert)
        self.session.commit()

        logger.info(f"Registered medical expert: {expert.expert_id}")

        return expert

    @require_phi_access(AccessLevel.READ)
    def request_validation(
        self,
        translation_id: UUID,
        source_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
        content_type: str,
        medical_context: Optional[Dict] = None,
        priority: str = "normal",
        deadline_hours: int = 48,
    ) -> ValidationRequest:
        """Create a validation request."""
        # Determine required expertise
        required_expertise = self.CONTENT_EXPERTISE_MAP.get(
            content_type, [ValidationDomain.CLINICAL_ACCURACY]
        )

        request = ValidationRequest(
            request_id=uuid4(),
            translation_id=translation_id,
            source_text=source_text,
            translated_text=translated_text,
            source_language=source_language,
            target_language=target_language,
            content_type=content_type,
            medical_context=medical_context or {},
            required_expertise=required_expertise,
            priority=priority,
            deadline=datetime.utcnow() + timedelta(hours=deadline_hours),
        )

        # Find and assign suitable expert
        expert = self._find_suitable_expert(request)

        if expert:
            self._assign_expert_to_validation(expert, request)
            logger.info(
                f"Validation request created and assigned: {request.request_id}"
            )
        else:
            logger.warning(
                f"No suitable expert found for validation: {request.request_id}"
            )

        return request

    def submit_validation(
        self,
        request_id: UUID,
        expert_id: UUID,
        is_accurate: bool,
        confidence: float,
        issues: Optional[List[Dict]] = None,
        recommendations: Optional[List[str]] = None,
        suggested_changes: Optional[str] = None,
        notes: str = "",
    ) -> ExpertValidationResult:
        """Submit expert validation results."""
        # Create validation record
        validation = ExpertValidation(
            request_id=str(request_id),
            expert_id=str(expert_id),
            is_clinically_accurate=is_accurate,
            confidence_score=confidence,
            approved_with_changes=bool(suggested_changes),
            suggested_changes=suggested_changes,
            issues_found=issues or [],
            recommendations=recommendations or [],
            validation_notes=notes,
            completed_at=datetime.utcnow(),
        )

        # Get request details to populate validation
        # (In production, would fetch from request storage)

        self.session.add(validation)

        # Update expert metrics
        expert = (
            self.session.query(MedicalExpert)
            .filter(MedicalExpert.expert_id == str(expert_id))
            .first()
        )

        if expert:
            expert.validations_completed += 1
            expert.last_validation_at = datetime.utcnow()

            # Update average confidence score
            total_score = expert.average_confidence_score * (
                expert.validations_completed - 1
            )
            expert.average_confidence_score = (
                total_score + confidence
            ) / expert.validations_completed

            # Update approval rate
            if is_accurate:
                total_approvals = expert.approval_rate * (
                    expert.validations_completed - 1
                )
                expert.approval_rate = (
                    total_approvals + 1
                ) / expert.validations_completed

        self.session.commit()

        result = ExpertValidationResult(
            validation_id=uuid4(),
            request_id=request_id,
            expert_id=expert_id,
            is_clinically_accurate=is_accurate,
            confidence_score=confidence,
            issues_found=issues or [],
            recommendations=recommendations or [],
            approved_with_changes=bool(suggested_changes),
            suggested_changes=suggested_changes,
            validation_notes=notes,
            validated_at=datetime.utcnow(),
        )

        logger.info(f"Expert validation submitted: {validation.validation_id}")

        return result

    def _find_suitable_expert(
        self, request: ValidationRequest
    ) -> Optional[MedicalExpert]:
        """Find suitable expert for validation request."""
        query = self.session.query(MedicalExpert).filter(
            MedicalExpert.is_active.is_(True),
            MedicalExpert.verification_status == "verified",
        )

        # Filter by language capability
        # Note: In production, would use proper array contains query
        suitable_experts = []

        for expert in query.all():
            # Check language match
            if (
                request.source_language in expert.languages
                and request.target_language in expert.languages
            ):

                # Check expertise match
                expert_domains = set(expert.validation_domains)
                required_domains = set(d.value for d in request.required_expertise)

                if required_domains.issubset(expert_domains):
                    # Check expertise level
                    min_level = self.MIN_EXPERTISE_LEVEL.get(
                        request.content_type, ExpertiseLevel.SPECIALIST
                    )

                    if self._meets_expertise_level(expert.expertise_level, min_level):
                        suitable_experts.append(expert)

        if not suitable_experts:
            return None

        # Sort by suitability score
        scored_experts = []
        for expert in suitable_experts:
            score = self._calculate_expert_suitability_score(expert, request)
            scored_experts.append((score, expert))

        scored_experts.sort(key=lambda x: x[0], reverse=True)

        return scored_experts[0][1] if scored_experts else None

    def _calculate_expert_suitability_score(
        self, expert: MedicalExpert, request: ValidationRequest
    ) -> float:
        """Calculate suitability score for expert-request matching."""
        score = 0.0

        # Base score from performance metrics
        confidence_score = float(expert.average_confidence_score or 0.0)
        approval_rate = float(expert.approval_rate or 0.0)
        score += confidence_score * 20
        score += approval_rate * 20

        # Specialty match bonus
        if request.content_type in expert.preferred_content_types:
            score += 10

        # Refugee health experience bonus
        if expert.refugee_health_experience:
            score += 15

        # Availability bonus
        if expert.availability_hours_per_week > 20:
            score += 10

        # Response time factor
        if expert.average_response_time_hours < 24:
            score += 10

        # Experience factor
        if expert.years_experience > 10:
            score += 10
        elif expert.years_experience > 5:
            score += 5

        return score

    def _meets_expertise_level(
        self, expert_level: str, required_level: ExpertiseLevel
    ) -> bool:
        """Check if expert meets minimum expertise level."""
        level_hierarchy = {
            ExpertiseLevel.STUDENT: 1,
            ExpertiseLevel.RESIDENT: 2,
            ExpertiseLevel.SPECIALIST: 3,
            ExpertiseLevel.CONSULTANT: 4,
            ExpertiseLevel.PROFESSOR: 5,
        }

        # Convert string to enum
        try:
            expert_level_enum = ExpertiseLevel(expert_level)
        except ValueError:
            return False

        expert_rank = level_hierarchy.get(expert_level_enum, 0)
        required_rank = level_hierarchy.get(required_level, 3)

        return expert_rank >= required_rank

    def _assign_expert_to_validation(
        self, expert: MedicalExpert, request: ValidationRequest
    ) -> None:
        """Assign expert to validation request."""
        # In production, would create assignment record
        # and notify expert
        logger.info(
            f"Assigned expert {expert.expert_id} to validation {request.request_id}"
        )

    def get_expert_statistics(self, expert_id: UUID) -> Dict[str, Any]:
        """Get statistics for an expert."""
        expert = (
            self.session.query(MedicalExpert)
            .filter(MedicalExpert.expert_id == str(expert_id))
            .first()
        )

        if not expert:
            return {}

        validations = (
            self.session.query(ExpertValidation)
            .filter(ExpertValidation.expert_id == str(expert_id))
            .all()
        )

        stats = {
            "total_validations": expert.validations_completed,
            "average_confidence": expert.average_confidence_score,
            "approval_rate": expert.approval_rate,
            "average_response_time": expert.average_response_time_hours,
            "specialties": expert.specialties,
            "languages": expert.languages,
            "by_content_type": {},
            "by_language_pair": {},
            "recent_validations": [],
        }

        # Group by content type
        content_type_counts: Dict[str, int] = {}
        for validation in validations:
            ct = validation.content_type
            content_type_counts[ct] = content_type_counts.get(ct, 0) + 1
        stats["by_content_type"] = content_type_counts

        # Recent validations
        recent = sorted(
            validations, key=lambda v: v.completed_at or datetime.min, reverse=True
        )[:10]
        stats["recent_validations"] = [
            {
                "validation_id": v.validation_id,
                "completed_at": v.completed_at.isoformat() if v.completed_at else None,
                "is_accurate": v.is_clinically_accurate,
                "confidence": v.confidence_score,
            }
            for v in recent
        ]

        return stats

    def verify_expert_credentials(
        self, expert_id: UUID, _verification_details: Dict[str, Any]
    ) -> bool:
        """Verify expert credentials."""
        expert = (
            self.session.query(MedicalExpert)
            .filter(MedicalExpert.expert_id == str(expert_id))
            .first()
        )

        if not expert:
            return False

        # In production, would perform actual credential verification
        # with medical boards, universities, etc.

        expert.verification_status = "verified"
        expert.verified_at = datetime.utcnow()

        self.session.commit()

        logger.info(f"Expert credentials verified: {expert_id}")

        return True


# Validation quality metrics
class ValidationQualityMetrics:
    """Metrics for measuring validation quality."""

    @staticmethod
    def calculate_inter_rater_agreement(validations: List[ExpertValidation]) -> float:
        """Calculate agreement between multiple validators."""
        if len(validations) < 2:
            return 1.0

        # Calculate percentage of agreement on clinical accuracy
        accurate_count = sum(1 for v in validations if v.is_clinically_accurate)
        agreement = accurate_count / len(validations)

        # Perfect agreement is 1.0 or 0.0
        return 1.0 - abs(0.5 - agreement) * 2

    @staticmethod
    def calculate_confidence_variance(validations: List[ExpertValidation]) -> float:
        """Calculate variance in confidence scores."""
        if not validations:
            return 0.0

        scores = [float(v.confidence_score) for v in validations]
        mean = sum(scores) / len(scores)
        variance = sum((score - mean) ** 2 for score in scores) / len(scores)

        return variance
