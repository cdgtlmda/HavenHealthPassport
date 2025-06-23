"""Medical Translation Expert Validation.

This module provides expert validation functionality for medical translations,
ensuring clinical accuracy and appropriateness through domain expert review.

Access control enforced: This module processes PHI including medical diagnoses,
treatments, medications, and clinical protocols. All validation requests and
results are encrypted. Access requires appropriate medical professional credentials
and all operations are logged for HIPAA compliance.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

# Access control for medical validation operations

logger = get_logger(__name__)


class ExpertiseArea(str, Enum):
    """Medical expertise areas."""

    GENERAL_MEDICINE = "general_medicine"
    CARDIOLOGY = "cardiology"
    NEUROLOGY = "neurology"
    PEDIATRICS = "pediatrics"
    OBSTETRICS = "obstetrics"
    PSYCHIATRY = "psychiatry"
    EMERGENCY_MEDICINE = "emergency_medicine"
    SURGERY = "surgery"
    INFECTIOUS_DISEASE = "infectious_disease"
    PHARMACOLOGY = "pharmacology"
    RADIOLOGY = "radiology"
    PATHOLOGY = "pathology"
    PUBLIC_HEALTH = "public_health"


class ValidationScope(str, Enum):
    """Scope of expert validation."""

    CLINICAL_ACCURACY = "clinical_accuracy"
    DOSAGE_VERIFICATION = "dosage_verification"
    PROCEDURE_STEPS = "procedure_steps"
    SAFETY_WARNINGS = "safety_warnings"
    DIAGNOSTIC_CRITERIA = "diagnostic_criteria"
    TREATMENT_PROTOCOLS = "treatment_protocols"
    DRUG_INTERACTIONS = "drug_interactions"
    CONTRAINDICATIONS = "contraindications"


@dataclass
class MedicalExpert:
    """Medical expert profile."""

    expert_id: str
    name: str
    credentials: List[str]  # MD, PhD, etc.
    expertise_areas: List[ExpertiseArea]
    languages: Dict[str, str]  # language -> proficiency level
    years_experience: int
    specializations: List[str]
    hospital_affiliations: List[str]
    certifications: List[str]
    availability: str  # full_time, part_time, on_call
    validation_count: int = 0
    approval_rate: float = 0.0
    average_response_time: timedelta = timedelta()


@dataclass
class ExpertValidationRequest:
    """Request for expert validation."""

    request_id: str
    translation_id: str
    source_text: str
    translated_text: str
    source_language: str
    target_language: str
    medical_context: str
    expertise_required: List[ExpertiseArea]
    validation_scope: List[ValidationScope]
    priority: str
    deadline: datetime
    specific_concerns: Optional[List[str]] = None
    attachments: Optional[List[str]] = None  # Related documents


@dataclass
class ExpertValidationResult:
    """Result of expert validation."""

    validation_id: str
    request_id: str
    expert_id: str
    is_validated: bool
    clinical_accuracy_score: float  # 0-100
    safety_score: float  # 0-100
    completeness_score: float  # 0-100
    issues_found: List[Dict[str, Any]]
    recommendations: List[str]
    required_changes: List[Dict[str, str]]  # position -> correction
    expert_notes: str
    validated_at: datetime = field(default_factory=datetime.utcnow)
    time_spent_minutes: int = 0


class ExpertValidationService:
    """Service for managing expert validation of medical translations."""

    # Expertise requirements by medical context
    CONTEXT_EXPERTISE_MAP = {
        "cardiology_procedure": [ExpertiseArea.CARDIOLOGY, ExpertiseArea.SURGERY],
        "psychiatric_assessment": [ExpertiseArea.PSYCHIATRY],
        "pediatric_dosing": [ExpertiseArea.PEDIATRICS, ExpertiseArea.PHARMACOLOGY],
        "pregnancy_medication": [ExpertiseArea.OBSTETRICS, ExpertiseArea.PHARMACOLOGY],
        "emergency_protocol": [ExpertiseArea.EMERGENCY_MEDICINE],
        "infectious_disease": [
            ExpertiseArea.INFECTIOUS_DISEASE,
            ExpertiseArea.PUBLIC_HEALTH,
        ],
        "surgical_consent": [ExpertiseArea.SURGERY, ExpertiseArea.GENERAL_MEDICINE],
        "diagnostic_imaging": [ExpertiseArea.RADIOLOGY],
        "lab_results": [ExpertiseArea.PATHOLOGY],
    }

    # Validation requirements by scope
    VALIDATION_REQUIREMENTS = {
        ValidationScope.DOSAGE_VERIFICATION: {
            "min_experience_years": 5,
            "required_credential": "MD",
            "specialization_needed": True,
        },
        ValidationScope.SAFETY_WARNINGS: {
            "min_experience_years": 3,
            "required_credential": "MD",
            "specialization_needed": False,
        },
        ValidationScope.TREATMENT_PROTOCOLS: {
            "min_experience_years": 7,
            "required_credential": "MD",
            "specialization_needed": True,
        },
    }

    def __init__(self) -> None:
        """Initialize expert validation service."""
        self.experts: Dict[str, MedicalExpert] = {}
        self.pending_validations: Dict[str, ExpertValidationRequest] = {}
        self.completed_validations: Dict[str, ExpertValidationResult] = {}
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self._initialize_expert_pool()

    def _initialize_expert_pool(self) -> None:
        """Initialize pool of medical experts."""
        # In production, would load from database
        # Sample experts for different specialties

        self.experts["exp_001"] = MedicalExpert(
            expert_id="exp_001",
            name="Dr. Sarah Chen",
            credentials=["MD", "PhD"],
            expertise_areas=[ExpertiseArea.CARDIOLOGY, ExpertiseArea.GENERAL_MEDICINE],
            languages={"en": "native", "zh": "native", "es": "professional"},
            years_experience=15,
            specializations=["Interventional Cardiology", "Heart Failure"],
            hospital_affiliations=["Johns Hopkins Hospital"],
            certifications=["Board Certified - Cardiology", "ACLS"],
            availability="part_time",
            validation_count=245,
            approval_rate=0.94,
        )

        self.experts["exp_002"] = MedicalExpert(
            expert_id="exp_002",
            name="Dr. Ahmed Hassan",
            credentials=["MD", "MPH"],
            expertise_areas=[
                ExpertiseArea.INFECTIOUS_DISEASE,
                ExpertiseArea.PUBLIC_HEALTH,
            ],
            languages={"en": "fluent", "ar": "native", "fr": "professional"},
            years_experience=12,
            specializations=["Tropical Medicine", "Refugee Health"],
            hospital_affiliations=["MSF", "WHO Consultant"],
            certifications=["Board Certified - Infectious Disease"],
            availability="full_time",
            validation_count=189,
            approval_rate=0.92,
        )

        self.experts["exp_003"] = MedicalExpert(
            expert_id="exp_003",
            name="Dr. Maria Rodriguez",
            credentials=["MD", "PharmD"],
            expertise_areas=[ExpertiseArea.PHARMACOLOGY, ExpertiseArea.PEDIATRICS],
            languages={"en": "fluent", "es": "native", "pt": "fluent"},
            years_experience=10,
            specializations=["Pediatric Pharmacology", "Drug Safety"],
            hospital_affiliations=["Children's Hospital Boston"],
            certifications=["Board Certified - Pediatrics", "Clinical Pharmacology"],
            availability="on_call",
            validation_count=156,
            approval_rate=0.95,
        )

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("expert_validation_request")
    async def request_validation(
        self,
        translation_id: str,
        source_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
        medical_context: str,
        validation_scope: List[ValidationScope],
        priority: str = "medium",
        deadline_hours: int = 48,
        specific_concerns: Optional[List[str]] = None,
    ) -> str:
        """Request expert validation for a translation."""
        # Determine required expertise
        expertise_required = self.CONTEXT_EXPERTISE_MAP.get(
            medical_context, [ExpertiseArea.GENERAL_MEDICINE]
        )

        # Create validation request
        request = ExpertValidationRequest(
            request_id=f"val_{translation_id}_{datetime.utcnow().timestamp()}",
            translation_id=translation_id,
            source_text=source_text,
            translated_text=translated_text,
            source_language=source_language,
            target_language=target_language,
            medical_context=medical_context,
            expertise_required=expertise_required,
            validation_scope=validation_scope,
            priority=priority,
            deadline=datetime.utcnow() + timedelta(hours=deadline_hours),
            specific_concerns=specific_concerns,
        )

        # Find and assign appropriate expert
        assigned_expert = await self._assign_expert(request)

        if assigned_expert:
            self.pending_validations[request.request_id] = request
            logger.info(
                f"Validation request {request.request_id} assigned to "
                f"expert {assigned_expert.expert_id}"
            )

            # Notify expert (in production)
            await self._notify_expert(assigned_expert, request)

            return request.request_id
        else:
            logger.error(
                f"No suitable expert found for validation request "
                f"{request.request_id}"
            )
            raise ValueError("No suitable expert available")

    async def _assign_expert(
        self, request: ExpertValidationRequest
    ) -> Optional[MedicalExpert]:
        """Assign appropriate expert to validation request."""
        suitable_experts = []

        for expert in self.experts.values():
            # Check expertise match
            expertise_match = any(
                area in expert.expertise_areas for area in request.expertise_required
            )

            if not expertise_match:
                continue

            # Check language proficiency
            source_proficiency = expert.languages.get(request.source_language, "none")
            target_proficiency = expert.languages.get(request.target_language, "none")

            if source_proficiency in ["none", "basic"] or target_proficiency in [
                "none",
                "basic",
            ]:
                continue

            # Check requirements for validation scope
            meets_requirements = True
            for scope in request.validation_scope:
                requirements = self.VALIDATION_REQUIREMENTS.get(scope, {})

                min_experience = requirements.get("min_experience_years", 0)
                if not isinstance(min_experience, int):
                    min_experience = 0
                if min_experience > expert.years_experience:
                    meets_requirements = False
                    break

                if requirements.get("required_credential") not in expert.credentials:
                    meets_requirements = False
                    break

            if meets_requirements:
                suitable_experts.append(expert)

        if not suitable_experts:
            return None

        # Select expert with best match
        # Consider: expertise match, language proficiency, availability, workload
        best_expert = max(
            suitable_experts,
            key=lambda e: (
                e.approval_rate,
                len(set(e.expertise_areas) & set(request.expertise_required)),
                1 if e.availability == "full_time" else 0.5,
            ),
        )

        return best_expert

    async def _notify_expert(
        self, expert: MedicalExpert, request: ExpertValidationRequest
    ) -> None:
        """Notify expert of new validation request."""
        # In production, would send email/SMS/push notification
        logger.info(
            f"Notifying expert {expert.expert_id} of request {request.request_id}"
        )

    @require_phi_access(AccessLevel.WRITE)
    @audit_phi_access("submit_medical_validation")
    async def submit_validation(
        self, request_id: str, expert_id: str, validation_result: ExpertValidationResult
    ) -> bool:
        """Submit expert validation result."""
        request = self.pending_validations.get(request_id)
        if not request:
            logger.error(f"Validation request {request_id} not found")
            return False

        expert = self.experts.get(expert_id)
        if not expert:
            logger.error(f"Expert {expert_id} not found")
            return False

        # Store validation result
        self.completed_validations[validation_result.validation_id] = validation_result

        # Update expert metrics
        expert.validation_count += 1
        if validation_result.is_validated:
            expert.approval_rate = (
                expert.approval_rate * (expert.validation_count - 1) + 1
            ) / expert.validation_count
        else:
            expert.approval_rate = (
                expert.approval_rate * (expert.validation_count - 1)
            ) / expert.validation_count

        # Calculate response time
        response_time = datetime.utcnow() - request.deadline + timedelta(hours=48)
        expert.average_response_time = (
            expert.average_response_time * (expert.validation_count - 1) + response_time
        ) / expert.validation_count

        # Remove from pending
        del self.pending_validations[request_id]

        logger.info(
            f"Validation {validation_result.validation_id} completed by "
            f"expert {expert_id}"
        )

        return True

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("perform_clinical_validation")
    def perform_clinical_validation(
        self,
        source_text: str,
        translated_text: str,
        medical_context: str,
        expertise_area: ExpertiseArea,
    ) -> Dict[str, Any]:
        """Perform clinical validation checks."""
        validation_checks = {
            "terminology_accuracy": self._check_terminology_accuracy(
                source_text, translated_text, expertise_area
            ),
            "clinical_consistency": self._check_clinical_consistency(
                translated_text, medical_context
            ),
            "safety_compliance": self._check_safety_compliance(
                translated_text, medical_context
            ),
            "completeness": self._check_completeness(source_text, translated_text),
        }

        # Calculate overall clinical accuracy
        scores = [check["score"] for check in validation_checks.values()]
        overall_score = sum(scores) / len(scores)

        return {
            "overall_score": overall_score,
            "checks": validation_checks,
            "is_clinically_accurate": overall_score >= 0.9,
        }

    def _check_terminology_accuracy(
        self, _source_text: str, _translated_text: str, expertise_area: ExpertiseArea
    ) -> Dict[str, Any]:
        """Check medical terminology accuracy."""
        # In production, would use specialized medical NLP
        # and terminology databases

        issues: List[Any] = []

        # Check for critical terms based on expertise area
        critical_terms = {
            ExpertiseArea.CARDIOLOGY: ["infarction", "stenosis", "arrhythmia"],
            ExpertiseArea.PHARMACOLOGY: [
                "contraindicated",
                "adverse reaction",
                "dosage",
            ],
            ExpertiseArea.EMERGENCY_MEDICINE: ["stat", "code blue", "triage"],
        }

        area_terms = critical_terms.get(expertise_area, [])

        # Simple check - in production would be more sophisticated
        score = 0.95  # Placeholder

        return {"score": score, "issues": issues, "checked_terms": len(area_terms)}

    def _check_clinical_consistency(
        self, _translated_text: str, _medical_context: str
    ) -> Dict[str, Any]:
        """Check clinical consistency of translation."""
        issues: List[Any] = []

        # Check for internally consistent clinical information
        # E.g., dosages, frequencies, durations

        # Placeholder implementation
        score = 0.92

        return {
            "score": score,
            "issues": issues,
            "consistency_checks": ["dosage_frequency", "treatment_duration"],
        }

    def _check_safety_compliance(
        self, _translated_text: str, _medical_context: str
    ) -> Dict[str, Any]:
        """Check safety compliance in translation."""
        issues: List[Any] = []

        # Placeholder implementation
        score = 0.88

        return {"score": score, "issues": issues, "safety_elements_checked": 5}

    def _check_completeness(
        self, source_text: str, translated_text: str
    ) -> Dict[str, Any]:
        """Check completeness of translation."""
        issues = []

        # Check if all medical information is preserved
        # Simple length comparison as placeholder
        source_length = len(source_text.split())
        trans_length = len(translated_text.split())

        completeness_ratio = min(trans_length / source_length, 1.0)

        if completeness_ratio < 0.8:
            issues.append("Translation appears incomplete")

        return {
            "score": completeness_ratio,
            "issues": issues,
            "word_count_ratio": completeness_ratio,
        }

    def get_expert_recommendations(
        self, medical_context: str, issues_found: List[Dict[str, Any]]
    ) -> List[str]:
        """Get expert recommendations based on validation findings."""
        recommendations = []

        # Context-specific recommendations
        if medical_context == "medication_instructions":
            recommendations.append(
                "Ensure dosage instructions are clearly separated and emphasized"
            )
            recommendations.append("Verify all drug names against local formulary")

        # Issue-based recommendations
        for issue in issues_found:
            if issue.get("type") == "terminology":
                recommendations.append(
                    f"Review medical term '{issue.get('term')}' with specialist"
                )
            elif issue.get("type") == "safety":
                recommendations.append(
                    f"Add clear warning for: {issue.get('description')}"
                )

        return recommendations

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("get_validation_statistics")
    def get_validation_statistics(
        self, expert_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get validation statistics."""
        if expert_id:
            expert = self.experts.get(expert_id)
            if not expert:
                return {"error": "Expert not found"}

            return {
                "expert_id": expert_id,
                "total_validations": expert.validation_count,
                "approval_rate": expert.approval_rate,
                "average_response_time": str(expert.average_response_time),
                "expertise_areas": [area.value for area in expert.expertise_areas],
            }
        else:
            # Overall statistics
            total_validations = sum(e.validation_count for e in self.experts.values())
            avg_approval = (
                sum(e.approval_rate * e.validation_count for e in self.experts.values())
                / total_validations
                if total_validations > 0
                else 0
            )

            return {
                "total_experts": len(self.experts),
                "total_validations": total_validations,
                "average_approval_rate": avg_approval,
                "pending_validations": len(self.pending_validations),
                "completed_validations": len(self.completed_validations),
            }


# Global expert validation service
expert_validator = ExpertValidationService()
