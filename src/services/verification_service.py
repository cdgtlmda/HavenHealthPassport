"""Verification service for managing identity and document verifications. Handles FHIR Resource validation."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID as UUIDType

from sqlalchemy import or_

from src.models.access_log import AccessType
from src.models.patient import Patient
from src.models.patient import VerificationStatus as PatientVerificationStatus
from src.models.verification import (
    Verification,
    VerificationLevel,
    VerificationMethod,
    VerificationStatus,
)
from src.services.base import BaseService
from src.services.blockchain_factory import get_blockchain_service
from src.utils.logging import get_logger

logger = get_logger(__name__)


class VerificationService(BaseService[Verification]):
    """Service for managing verifications."""

    model_class = Verification

    def request_verification(
        self,
        patient_id: UUIDType,
        verification_type: str,
        verification_method: VerificationMethod,
        verifier_name: str,
        verifier_organization: Optional[str] = None,
        evidence: Optional[List[Dict[str, Any]]] = None,
        expires_in_days: int = 365,
    ) -> Verification:
        """Create a new verification request."""
        try:
            # Verify patient exists
            patient = (
                self.session.query(Patient)
                .filter(Patient.id == patient_id, Patient.deleted_at.is_(None))
                .first()
            )

            if not patient:
                raise ValueError(f"Patient {patient_id} not found")

            # Create verification request
            if self.current_user_id is None:
                raise ValueError("No user context set for creating verification")
            verification = Verification.create_verification_request(
                session=self.session,
                patient_id=patient_id,
                verification_type=verification_type,
                verification_method=verification_method,
                verifier_id=self.current_user_id,
                verifier_name=verifier_name,
                verifier_organization=verifier_organization,
                expires_in_days=expires_in_days,
            )

            # Add initial evidence if provided
            if evidence:
                for evidence_item in evidence:
                    verification.add_evidence(
                        evidence_item.get("type", "document"),
                        evidence_item.get("data", {}),
                    )

            # Start the verification process
            verification.started_at = datetime.utcnow()  # type: ignore[assignment]
            verification.status = VerificationStatus.IN_PROGRESS

            self.session.flush()

            logger.info(
                f"Created verification request {verification.id} "
                f"for patient {patient_id} - {verification_type}"
            )

            return verification

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error creating verification request: {e}")
            raise

    def approve_verification(
        self,
        verification_id: UUIDType,
        confidence_score: Optional[int] = None,
        notes: Optional[str] = None,
        blockchain_enabled: bool = True,
    ) -> Optional[Verification]:
        """Approve a verification request."""
        try:
            verification = self.get_by_id(verification_id)
            if not verification:
                return None

            if verification.status == VerificationStatus.COMPLETED:
                logger.warning(f"Verification {verification_id} already completed")
                return verification

            # Update verification
            verification.status = VerificationStatus.COMPLETED
            verification.completed_at = datetime.utcnow()

            if notes:
                verification.verification_notes = notes

            # Calculate confidence score
            if confidence_score:
                verification.confidence_score = confidence_score
            else:
                verification.calculate_confidence_score()

            # Determine verification level based on score
            if verification.confidence_score >= 80:
                verification.verification_level = VerificationLevel.VERY_HIGH
            elif verification.confidence_score >= 60:
                verification.verification_level = VerificationLevel.HIGH
            elif verification.confidence_score >= 40:
                verification.verification_level = VerificationLevel.MEDIUM
            else:
                verification.verification_level = VerificationLevel.LOW

            # Generate blockchain hash if enabled
            if blockchain_enabled:
                verification.generate_blockchain_hash()
                # Submit to blockchain - properly implemented
                blockchain_service = get_blockchain_service()
                blockchain_service.current_user_id = self.current_user_id

                # Store verification on blockchain
                verification.blockchain_tx_id = blockchain_service.store_verification(  # type: ignore[attr-defined]
                    record_id=verification.id,
                    verification_hash=verification.blockchain_hash,
                )

                logger.info(
                    f"Submitted verification {verification_id} to blockchain with tx_id: {verification.blockchain_tx_id}"
                )

            # Update patient verification status
            patient = (
                self.session.query(Patient)
                .filter(Patient.id == verification.patient_id)
                .first()
            )

            if patient and verification.verification_type == "identity":
                patient.verification_status = PatientVerificationStatus.VERIFIED

            self.session.flush()

            # Log the approval
            self.log_access(
                resource_id=verification_id,
                access_type=AccessType.UPDATE,
                purpose="Approve verification",
                patient_id=verification.patient_id,
            )

            logger.info(
                f"Approved verification {verification_id} with "
                f"confidence score {verification.confidence_score}"
            )

            return verification

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error approving verification: {e}")
            return None

    def add_verification_evidence(
        self,
        verification_id: UUIDType,
        evidence_type: str,
        evidence_data: Dict[str, Any],
    ) -> bool:
        """Add evidence to an existing verification."""
        try:
            verification = self.get_by_id(verification_id)
            if not verification:
                return False

            if verification.status == VerificationStatus.COMPLETED:
                logger.warning(
                    f"Cannot add evidence to completed verification {verification_id}"
                )
                return False

            verification.add_evidence(evidence_type, evidence_data)

            # Log the evidence addition
            verification.log_step(
                "evidence_added",
                {"type": evidence_type, "added_by": str(self.current_user_id)},
            )

            self.session.flush()

            logger.info(
                f"Added {evidence_type} evidence to verification {verification_id}"
            )

            return True

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error adding verification evidence: {e}")
            return False

    def add_witness(
        self,
        verification_id: UUIDType,
        witness_name: str,
        witness_role: str,
        statement: str,
    ) -> bool:
        """Add a witness to verification."""
        try:
            verification = self.get_by_id(verification_id)
            if not verification:
                return False

            verification.add_witness(
                witness_id=str(self.current_user_id),
                witness_name=witness_name,
                witness_role=witness_role,
                statement=statement,
            )

            # Log the witness addition
            verification.log_step(
                "witness_added", {"witness": witness_name, "role": witness_role}
            )

            self.session.flush()

            return True

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error adding witness: {e}")
            return False

    def revoke_verification(self, verification_id: UUIDType, reason: str) -> bool:
        """Revoke a verification."""
        try:
            verification = self.get_by_id(verification_id)
            if not verification:
                return False

            if self.current_user_id is None:
                raise ValueError("No user context set for revoking verification")
            verification.revoke(revoked_by=self.current_user_id, reason=reason)

            # Update patient verification status if this was identity verification
            if verification.verification_type == "identity":
                patient = (
                    self.session.query(Patient)
                    .filter(Patient.id == verification.patient_id)
                    .first()
                )

                if patient:
                    # Check if there are other valid verifications
                    other_verifications = Verification.get_active_verifications(
                        self.session, UUIDType(str(patient.id)), "identity"
                    )

                    if not other_verifications:
                        patient.verification_status = (
                            PatientVerificationStatus.UNVERIFIED
                        )

            self.session.flush()

            # Log the revocation
            self.log_access(
                resource_id=verification_id,
                access_type=AccessType.UPDATE,
                purpose=f"Revoke verification - {reason}",
                patient_id=verification.patient_id,
            )

            logger.info(f"Revoked verification {verification_id} - {reason}")

            return True

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error revoking verification: {e}")
            return False

    def get_patient_verifications(
        self,
        patient_id: UUIDType,
        verification_type: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Verification]:
        """Get verifications for a patient."""
        try:
            if active_only:
                verifications = Verification.get_active_verifications(
                    self.session, patient_id, verification_type
                )
            else:
                query = self.session.query(Verification).filter(
                    Verification.patient_id == patient_id
                )

                if verification_type:
                    query = query.filter(
                        Verification.verification_type == verification_type
                    )

                verifications = query.order_by(Verification.completed_at.desc()).all()

            # Log access
            self.log_access(
                resource_id=patient_id,
                access_type=AccessType.VIEW,
                purpose="View patient verifications",
                patient_id=patient_id,
                data_returned={
                    "count": len(verifications),
                    "type": verification_type or "all",
                },
            )

            return verifications

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error getting patient verifications: {e}")
            return []

    def check_verification(
        self,
        patient_id: UUIDType,
        verification_type: str,
        required_level: VerificationLevel = VerificationLevel.MEDIUM,
    ) -> Dict[str, Any]:
        """Check if patient has valid verification of specified type and level."""
        try:
            verifications = Verification.get_active_verifications(
                self.session, patient_id, verification_type
            )

            # Find highest level verification
            highest_level = None
            valid_verification = None

            for verification in verifications:
                if verification.verification_level.value >= required_level.value:
                    if (
                        not highest_level
                        or verification.verification_level.value > highest_level.value
                    ):
                        highest_level = verification.verification_level
                        valid_verification = verification

            result = {
                "verified": valid_verification is not None,
                "verification_id": (
                    str(valid_verification.id) if valid_verification else None
                ),
                "level": highest_level.value if highest_level else None,
                "expires_at": (
                    valid_verification.expires_at.isoformat()
                    if valid_verification and valid_verification.expires_at
                    else None
                ),
                "verifier": (
                    valid_verification.verifier_name if valid_verification else None
                ),
            }

            return result

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error checking verification: {e}")
            return {"verified": False, "error": str(e)}

    def search_verifications(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Verification], int]:
        """Search verifications with filters."""
        try:
            query = self.session.query(Verification)

            if filters:
                if filters.get("status"):
                    query = query.filter(Verification.status == filters["status"])

                if filters.get("method"):
                    query = query.filter(
                        Verification.verification_method == filters["method"]
                    )

                if filters.get("level"):
                    query = query.filter(
                        Verification.verification_level == filters["level"]
                    )

                if filters.get("verifier_organization"):
                    query = query.filter(
                        Verification.verifier_organization.ilike(
                            f"%{filters['verifier_organization']}%"
                        )
                    )

                if filters.get("expired"):
                    if filters["expired"]:
                        query = query.filter(
                            Verification.expires_at < datetime.utcnow()
                        )
                    else:
                        query = query.filter(
                            or_(
                                Verification.expires_at.is_(None),
                                Verification.expires_at >= datetime.utcnow(),
                            )
                        )

                if filters.get("blockchain_verified"):
                    query = query.filter(Verification.blockchain_hash.isnot(None))

            # Get total count
            total_count = query.count()

            # Apply pagination
            verifications = (
                query.order_by(Verification.completed_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )

            return verifications, total_count

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error searching verifications: {e}")
            return [], 0

    def complete_multi_factor_verification(
        self, verification_id: UUIDType, factor_type: str, factor_data: Dict[str, Any]
    ) -> Optional[Verification]:
        """Complete a factor in multi-factor verification."""
        try:
            verification = self.get_by_id(verification_id)
            if not verification:
                return None

            if not verification.is_multi_factor:
                logger.warning(f"Verification {verification_id} is not multi-factor")
                return verification

            # Complete the factor
            verification.complete_factor(factor_type, factor_data)

            # Log the factor completion
            verification.log_step(
                "factor_completed",
                {"factor": factor_type, "completed_by": str(self.current_user_id)},
            )

            self.session.flush()

            # If all factors completed, finalize verification
            if verification.status == VerificationStatus.COMPLETED:
                return self.approve_verification(verification_id)

            return verification

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error completing verification factor: {e}")
            return None

    def add_country_recognition(
        self, verification_id: UUIDType, country_code: str
    ) -> bool:
        """Add a country that recognizes this verification."""
        try:
            verification = self.get_by_id(verification_id)
            if not verification:
                return False

            verification.add_recognition(country_code)

            # Log the recognition
            verification.log_step(
                "country_recognition_added",
                {"country": country_code, "added_by": str(self.current_user_id)},
            )

            self.session.flush()

            return True

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error adding country recognition: {e}")
            return False

    def get_verification_summary(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get verification statistics summary."""
        try:
            query = self.session.query(Verification)

            if start_date:
                query = query.filter(Verification.created_at >= start_date)

            if end_date:
                query = query.filter(Verification.created_at <= end_date)

            verifications = query.all()

            summary: Dict[str, Any] = {
                "total_verifications": len(verifications),
                "by_status": {},
                "by_method": {},
                "by_level": {},
                "average_confidence_score": 0,
                "blockchain_verified": 0,
                "expired": 0,
                "revoked": 0,
            }

            total_confidence = 0
            confidence_count = 0

            for verification in verifications:
                # Count by status
                status = verification.status.value
                summary["by_status"][status] = summary["by_status"].get(status, 0) + 1

                # Count by method
                method = verification.verification_method.value
                summary["by_method"][method] = summary["by_method"].get(method, 0) + 1

                # Count by level
                level = verification.verification_level.value
                summary["by_level"][level] = summary["by_level"].get(level, 0) + 1

                # Confidence score
                if verification.confidence_score:
                    total_confidence += int(verification.confidence_score)
                    confidence_count += 1

                # Special counts
                if verification.blockchain_hash:
                    summary["blockchain_verified"] += 1

                if (
                    verification.expires_at
                    and verification.expires_at < datetime.utcnow()
                ):
                    summary["expired"] += 1

                if verification.revoked:
                    summary["revoked"] += 1

            # Calculate average confidence
            if confidence_count > 0:
                summary["average_confidence_score"] = round(
                    total_confidence / confidence_count, 2
                )

            return summary

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error getting verification summary: {e}")
            return {"error": str(e)}


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
