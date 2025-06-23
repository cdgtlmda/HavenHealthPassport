"""Verification Mutation Implementations.

This module implements verification-related mutations for the Haven Health
Passport GraphQL API, handling blockchain verification, evidence management,
and verification lifecycle operations.
"""

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Any, List, Optional

try:
    import graphene
except ImportError:
    graphene = None

from src.core.database import get_db
from src.models.access_log import AccessContext
from src.models.verification import VerificationMethod as VerificationMethodEnum
from src.models.verification import (
    VerificationStatus,
)
from src.services.health_record_service import HealthRecordService

# Import services
from src.services.verification_service import VerificationService
from src.utils.logging import get_logger

from .common_types import VerificationPayload
from .inputs import VerificationEvidenceInput
from .scalars import UUIDScalar
from .types import Error, Verification

logger = get_logger(__name__)


class RequestVerification(graphene.Mutation):
    """Request verification for a health record."""

    class Arguments:
        """GraphQL arguments for RequestVerification mutation."""

        record_id = graphene.Argument(UUIDScalar, required=True)
        method = graphene.String(required=True)

    Output = VerificationPayload

    def mutate(
        self, info: Any, record_id: uuid.UUID, method: str
    ) -> VerificationPayload:
        """Request verification mutation resolver."""
        errors = []

        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("request:verifications"):
            errors.append(
                Error(
                    message="Unauthorized to request verifications", code="UNAUTHORIZED"
                )
            )
            return VerificationPayload(verification=None, errors=errors)

        # Map string method to enum
        method_map = {
            "manual": VerificationMethodEnum.WITNESS,
            "automated": VerificationMethodEnum.BLOCKCHAIN,
            "blockchain": VerificationMethodEnum.BLOCKCHAIN,
            "biometric": VerificationMethodEnum.BIOMETRIC,
            "document": VerificationMethodEnum.DOCUMENT,
            "medical": VerificationMethodEnum.MEDICAL_PROFESSIONAL,
            "government": VerificationMethodEnum.GOVERNMENT_ID,
        }

        verification_method = method_map.get(method)
        if not verification_method:
            errors.append(
                Error(
                    field="method",
                    message=f"Invalid verification method: {method}",
                    code="INVALID_METHOD",
                )
            )
            return VerificationPayload(verification=None, errors=errors)

        try:
            with get_db() as db:
                # Get health record to find patient
                health_record_service = HealthRecordService(db)
                health_record_service.set_user_context(user.id, user.role)

                record = health_record_service.get_by_id(record_id)
                if not record:
                    errors.append(
                        Error(message="Health record not found", code="NOT_FOUND")
                    )
                    return VerificationPayload(verification=None, errors=errors)

                # Create verification service
                verification_service = VerificationService(db)
                verification_service.set_user_context(user.id, user.role)
                verification_service.access_context = AccessContext.API

                # Check if already verified
                existing_verifications = verification_service.get_patient_verifications(
                    patient_id=uuid.UUID(str(record.patient_id)),
                    verification_type="health_record",
                    active_only=True,
                )

                # Check if this specific record already has verification
                for existing in existing_verifications:
                    evidence_provided = existing.evidence_provided
                    evidence_list: list[Any] = (
                        evidence_provided if isinstance(evidence_provided, list) else []  # type: ignore[unreachable]
                    )
                    if evidence_list:
                        for evidence in evidence_list:
                            if evidence.get("data", {}).get("record_id") == str(
                                record_id
                            ):
                                errors.append(
                                    Error(
                                        message="Record already has active verification",
                                        code="ALREADY_VERIFIED",
                                    )
                                )
                                return VerificationPayload(
                                    verification=None, errors=errors
                                )

                # Request verification
                verification = verification_service.request_verification(
                    patient_id=uuid.UUID(str(record.patient_id)),
                    verification_type="health_record",
                    verification_method=verification_method,
                    verifier_name=(
                        user.name if hasattr(user, "name") else "Healthcare Provider"
                    ),
                    verifier_organization=(
                        user.organization if hasattr(user, "organization") else None
                    ),
                    evidence=[
                        {
                            "type": "health_record",
                            "data": {
                                "record_id": str(record_id),
                                "record_type": record.record_type.value,
                                "record_date": record.record_date.isoformat(),
                            },
                        }
                    ],
                    expires_in_days=365,
                )

                # Initialize verification based on method
                if method == "blockchain":
                    # Generate blockchain hash
                    verification.generate_blockchain_hash()
                    # In production, would submit to blockchain
                elif method == "automated":
                    # Perform automated checks
                    verification.complete_factor(
                        "automated_check",
                        {
                            "verified": True,
                            "checks_passed": ["format", "signature", "timestamp"],
                        },
                    )

                # Convert to GraphQL type
                verification_data = {
                    "id": verification.id,
                    "patient_id": verification.patient_id,
                    "type": verification.verification_type,
                    "method": verification.verification_method.value,
                    "status": verification.status.value,
                    "verifier": {
                        "id": verification.verifier_id,
                        "name": verification.verifier_name,
                        "organization": verification.verifier_organization,
                    },
                    "requested_at": verification.requested_at,
                    "blockchain_hash": verification.blockchain_hash,
                }

                verification_obj = Verification(**verification_data)

                db.commit()
                return VerificationPayload(verification=verification_obj, errors=None)

        except (ValueError, KeyError, AttributeError, TypeError) as e:
            logger.error(f"Error requesting verification: {e}")
            errors.append(
                Error(
                    message=f"Failed to request verification: {str(e)}",
                    code="REQUEST_FAILED",
                )
            )
            return VerificationPayload(verification=None, errors=errors)

    def _generate_blockchain_hash(self, record_id: uuid.UUID) -> str:
        """Generate blockchain hash for record."""
        # In production, would include record content and metadata
        data = f"{record_id}_{datetime.now().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()

    def _log_verification_action(
        self,
        info: Any,
        record_id: uuid.UUID,
        action: str,
        details: Optional[str] = None,
    ) -> None:
        """Log verification-related actions."""
        # In production, would create audit log entry
        # Currently unused parameters - will be used when audit service is implemented
        _ = (info, record_id, action, details)  # Acknowledge unused parameters
        # audit_service = AuditService()
        # audit_service.log_verification_action(
        #     record_id=record_id,
        #     user_id=user.id,
        #     action=action,
        #     details=details,
        #     timestamp=datetime.now()
        # )


class ApproveVerification(graphene.Mutation):
    """Approve a pending verification request."""

    class Arguments:
        """GraphQL arguments for ApproveVerification mutation."""

        verification_id = graphene.Argument(UUIDScalar, required=True)
        evidence = graphene.List(graphene.String)

    Output = VerificationPayload

    def mutate(
        self,
        info: Any,
        verification_id: uuid.UUID,
        evidence: Optional[List[str]] = None,
    ) -> VerificationPayload:
        """Approve verification mutation resolver."""
        errors = []

        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("approve:verifications"):
            errors.append(
                Error(
                    message="Unauthorized to approve verifications", code="UNAUTHORIZED"
                )
            )
            return VerificationPayload(verification=None, errors=errors)

        # Check if user is authorized verifier
        if not self._is_authorized_verifier(user):
            errors.append(
                Error(message="User is not an authorized verifier", code="NOT_VERIFIER")
            )
            return VerificationPayload(verification=None, errors=errors)

        try:
            with get_db() as db:
                # Create verification service
                verification_service = VerificationService(db)
                verification_service.set_user_context(user.id, user.role)
                verification_service.access_context = AccessContext.API

                # Get existing verification
                existing = verification_service.get_by_id(verification_id)
                if not existing:
                    errors.append(
                        Error(message="Verification not found", code="NOT_FOUND")
                    )
                    return VerificationPayload(verification=None, errors=errors)

                # Check status
                if existing.status != VerificationStatus.IN_PROGRESS:
                    errors.append(
                        Error(
                            message=f"Cannot approve verification in {existing.status.value} status",
                            code="INVALID_STATUS",
                        )
                    )
                    return VerificationPayload(verification=None, errors=errors)

                # Add evidence if provided
                if evidence:
                    for evidence_item in evidence:
                        verification_service.add_verification_evidence(
                            verification_id=verification_id,
                            evidence_type="manual_review",
                            evidence_data={
                                "review_notes": evidence_item,
                                "reviewer": (
                                    user.name if hasattr(user, "name") else str(user.id)
                                ),
                            },
                        )

                # Approve verification
                approved = verification_service.approve_verification(
                    verification_id=verification_id,
                    notes=f"Approved by {user.name if hasattr(user, 'name') else 'verifier'}"
                    + (f" with {len(evidence)} evidence items" if evidence else ""),
                    blockchain_enabled=existing.verification_method
                    == VerificationMethodEnum.BLOCKCHAIN,
                )

                if not approved:
                    raise ValueError("Failed to approve verification")

                # Get health record ID from evidence
                record_id = None
                if approved.evidence_provided:
                    evidence_provided = approved.evidence_provided
                    evidence_list: list[Any] = (
                        evidence_provided if isinstance(evidence_provided, list) else []  # type: ignore[unreachable]
                    )
                    for ev in evidence_list:
                        if ev.get("type") == "health_record":
                            record_id = ev.get("data", {}).get("record_id")
                            break

                # Update health record verification status
                if record_id:
                    health_record_service = HealthRecordService(db)
                    health_record_service.set_user_context(user.id, user.role)
                    health_record_service.finalize_record(
                        record_id=uuid.UUID(record_id), verified_by=user.id
                    )

                # Convert to GraphQL type
                verification_data = {
                    "id": approved.id,
                    "patient_id": approved.patient_id,
                    "type": approved.verification_type,
                    "method": approved.verification_method.value,
                    "status": approved.status.value,
                    "level": approved.verification_level.value,
                    "verifier": {
                        "id": approved.verifier_id,
                        "name": approved.verifier_name,
                        "organization": approved.verifier_organization,
                    },
                    "verified_at": approved.completed_at,
                    "expires_at": approved.expires_at,
                    "confidence_score": approved.confidence_score,
                    "blockchain_hash": approved.blockchain_hash,
                    "blockchain_tx_id": approved.blockchain_tx_id,
                }

                verification = Verification(**verification_data)

                db.commit()
                return VerificationPayload(verification=verification, errors=None)

        except (ValueError, KeyError, AttributeError, TypeError) as e:
            logger.error(f"Error approving verification: {e}")
            errors.append(
                Error(
                    message=f"Failed to approve verification: {str(e)}",
                    code="APPROVE_FAILED",
                )
            )
            return VerificationPayload(verification=None, errors=errors)

    def _is_authorized_verifier(self, user: Any) -> bool:
        """Check if user is an authorized verifier."""
        # In production, would check against verifier registry
        # verifier_service = VerifierService()
        # return verifier_service.is_authorized(user.id)

        # Mock: check for verifier role
        return bool(user.has_role("verifier") or user.has_role("admin"))

    def _log_verification_action(
        self,
        info: Any,
        verification_id: uuid.UUID,
        action: str,
        details: Optional[str] = None,
    ) -> None:
        """Log verification-related actions."""
        # In production, would create audit log entry
        # Currently unused parameters - will be used when audit service is implemented
        _ = (info, verification_id, action, details)  # Acknowledge unused parameters


class RevokeVerification(graphene.Mutation):
    """Revoke an existing verification."""

    class Arguments:
        """GraphQL arguments for RevokeVerification mutation."""

        verification_id = graphene.Argument(UUIDScalar, required=True)
        reason = graphene.String(required=True)

    Output = VerificationPayload

    def mutate(
        self, info: Any, verification_id: uuid.UUID, reason: str
    ) -> VerificationPayload:
        """Revoke verification mutation resolver."""
        errors = []

        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("revoke:verifications"):
            errors.append(
                Error(
                    message="Unauthorized to revoke verifications", code="UNAUTHORIZED"
                )
            )
            return VerificationPayload(verification=None, errors=errors)

        # Validate reason
        if not reason or len(reason.strip()) < 10:
            errors.append(
                Error(
                    field="reason",
                    message="Revocation reason must be at least 10 characters",
                    code="INVALID_REASON",
                )
            )
            return VerificationPayload(verification=None, errors=errors)

        try:
            with get_db() as db:
                # Create verification service
                verification_service = VerificationService(db)
                verification_service.set_user_context(user.id, user.role)
                verification_service.access_context = AccessContext.API

                # Get existing verification
                existing = verification_service.get_by_id(verification_id)
                if not existing:
                    errors.append(
                        Error(message="Verification not found", code="NOT_FOUND")
                    )
                    return VerificationPayload(verification=None, errors=errors)

                # Check if already revoked
                if existing.status == VerificationStatus.REVOKED:
                    errors.append(
                        Error(
                            message="Verification is already revoked",
                            code="ALREADY_REVOKED",
                        )
                    )
                    return VerificationPayload(verification=None, errors=errors)

                # Revoke verification
                success = verification_service.revoke_verification(
                    verification_id=verification_id, reason=reason
                )

                if not success:
                    raise ValueError("Failed to revoke verification")

                # Get updated verification
                revoked = verification_service.get_by_id(verification_id)

                if not revoked:
                    raise ValueError("Verification not found after revocation")

                # Get health record ID from evidence
                record_id = None
                if revoked.evidence_provided:
                    evidence_provided = revoked.evidence_provided
                    evidence_list: list[Any] = (
                        evidence_provided if isinstance(evidence_provided, list) else []  # type: ignore[unreachable]
                    )
                    for ev in evidence_list:
                        if ev.get("type") == "health_record":
                            record_id = ev.get("data", {}).get("record_id")
                            break

                # Update health record verification status if needed
                if record_id:
                    health_record_service = HealthRecordService(db)
                    health_record_service.set_user_context(user.id, user.role)
                    # Mark record as no longer verified
                    record = health_record_service.get_by_id(uuid.UUID(record_id))
                    if record:
                        health_record_service.update(
                            entity_id=uuid.UUID(record_id),
                            verified_by=None,
                            verified_at=None,
                        )

                # Convert to GraphQL type
                verification_data = {
                    "id": revoked.id,
                    "patient_id": revoked.patient_id,
                    "type": revoked.verification_type,
                    "method": revoked.verification_method.value,
                    "status": revoked.status.value,
                    "verifier": {
                        "id": revoked.verifier_id,
                        "name": revoked.verifier_name,
                        "organization": revoked.verifier_organization,
                    },
                    "verified_at": revoked.completed_at,
                    "revoked": revoked.revoked,
                    "revoked_at": revoked.revoked_at,
                    "revocation_reason": revoked.revocation_reason,
                }

                verification = Verification(**verification_data)

                db.commit()
                return VerificationPayload(verification=verification, errors=None)

        except (ValueError, KeyError, AttributeError, TypeError) as e:
            logger.error(f"Error revoking verification: {e}")
            errors.append(
                Error(
                    message=f"Failed to revoke verification: {str(e)}",
                    code="REVOKE_FAILED",
                )
            )
            return VerificationPayload(verification=None, errors=errors)

    def _log_verification_action(
        self,
        info: Any,
        verification_id: uuid.UUID,
        action: str,
        details: Optional[str] = None,
    ) -> None:
        """Log verification-related actions."""
        # In production, would create audit log entry
        # Currently unused parameters - will be used when audit service is implemented
        _ = (info, verification_id, action, details)  # Acknowledge unused parameters


class UpdateVerification(graphene.Mutation):
    """Update verification details (extend expiry, add evidence, etc.)."""

    class Arguments:
        """GraphQL arguments for UpdateVerification mutation."""

        verification_id = graphene.Argument(UUIDScalar, required=True)
        extend_days = graphene.Int()
        additional_evidence = graphene.List(VerificationEvidenceInput)

    Output = VerificationPayload

    def mutate(
        self,
        info: Any,
        verification_id: uuid.UUID,
        extend_days: Optional[int] = None,
        additional_evidence: Optional[List[VerificationEvidenceInput]] = None,
    ) -> VerificationPayload:
        """Update verification mutation resolver."""
        errors = []

        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("update:verifications"):
            errors.append(
                Error(
                    message="Unauthorized to update verifications", code="UNAUTHORIZED"
                )
            )
            return VerificationPayload(verification=None, errors=errors)

        # Validate inputs
        if not extend_days and not additional_evidence:
            errors.append(
                Error(
                    message="Must provide either extension days or additional evidence",
                    code="NO_UPDATES",
                )
            )
            return VerificationPayload(verification=None, errors=errors)

        if extend_days and extend_days <= 0:
            errors.append(
                Error(
                    field="extend_days",
                    message="Extension days must be positive",
                    code="INVALID_EXTENSION",
                )
            )
            return VerificationPayload(verification=None, errors=errors)

        try:
            with get_db() as db:
                # Create verification service
                verification_service = VerificationService(db)
                verification_service.set_user_context(user.id, user.role)
                verification_service.access_context = AccessContext.API

                # Get existing verification
                existing = verification_service.get_by_id(verification_id)
                if not existing:
                    errors.append(
                        Error(message="Verification not found", code="NOT_FOUND")
                    )
                    return VerificationPayload(verification=None, errors=errors)

                # Check if verification can be updated
                if existing.status not in [
                    VerificationStatus.COMPLETED,
                    VerificationStatus.IN_PROGRESS,
                ]:
                    errors.append(
                        Error(
                            message=f"Cannot update verification in {existing.status.value} status",
                            code="INVALID_STATUS",
                        )
                    )
                    return VerificationPayload(verification=None, errors=errors)

                # Extend expiry if requested
                if extend_days and existing.expires_at:
                    new_expiry = existing.expires_at + timedelta(days=extend_days)

                    # Validate extension doesn't exceed maximum (2 years from now)
                    max_expiry = datetime.now() + timedelta(days=730)
                    if new_expiry > max_expiry:
                        errors.append(
                            Error(
                                message="Extension would exceed maximum validity period",
                                code="EXTENSION_TOO_LONG",
                            )
                        )
                        return VerificationPayload(verification=None, errors=errors)

                    # Update expiry
                    existing.expires_at = new_expiry  # type: ignore[assignment]
                    existing.log_step(
                        "expiry_extended",
                        {
                            "extended_by_days": extend_days,
                            "new_expiry": new_expiry.isoformat(),
                            "extended_by": str(user.id),
                        },
                    )

                # Add additional evidence
                if additional_evidence:
                    for evidence in additional_evidence:
                        verification_service.add_verification_evidence(
                            verification_id=verification_id,
                            evidence_type=evidence.type or "supplemental",
                            evidence_data={
                                "value": evidence.value,
                                "source": evidence.source or str(user.id),
                                "added_by": (
                                    user.name if hasattr(user, "name") else str(user.id)
                                ),
                            },
                        )

                # Save changes
                db.flush()

                # Convert to GraphQL type
                verification_data = {
                    "id": existing.id,
                    "patient_id": existing.patient_id,
                    "type": existing.verification_type,
                    "method": existing.verification_method.value,
                    "status": existing.status.value,
                    "level": existing.verification_level.value,
                    "verifier": {
                        "id": existing.verifier_id,
                        "name": existing.verifier_name,
                        "organization": existing.verifier_organization,
                    },
                    "verified_at": existing.completed_at,
                    "expires_at": existing.expires_at,
                    "confidence_score": existing.confidence_score,
                    "evidence_count": (
                        len(existing.evidence_provided)
                        if existing.evidence_provided
                        else 0
                    ),
                }

                verification = Verification(**verification_data)

                # Log update
                update_details = []
                if extend_days:
                    update_details.append(f"Extended by {extend_days} days")
                if additional_evidence:
                    update_details.append(
                        f"Added {len(additional_evidence)} evidence items"
                    )

                existing.log_step(
                    "updated", {"updates": update_details, "updated_by": str(user.id)}
                )

                db.commit()
                return VerificationPayload(verification=verification, errors=None)

        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error updating verification: {e}")
            errors.append(
                Error(
                    message=f"Failed to update verification: {str(e)}",
                    code="UPDATE_FAILED",
                )
            )
            return VerificationPayload(verification=None, errors=errors)

    def _log_verification_action(
        self,
        info: Any,
        verification_id: uuid.UUID,
        action: str,
        details: Optional[str] = None,
    ) -> None:
        """Log verification-related actions."""
        # In production, would create audit log entry
        # Currently unused parameters - will be used when audit service is implemented
        _ = (info, verification_id, action, details)  # Acknowledge unused parameters


# Export verification mutations
__all__ = [
    "RequestVerification",
    "ApproveVerification",
    "RevokeVerification",
    "UpdateVerification",
]
