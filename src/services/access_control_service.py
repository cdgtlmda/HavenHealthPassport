"""Access Control Service for Haven Health Passport.

This service manages access control between patients, providers, and organizations.
It handles HIPAA-compliant access verification and audit logging.
Validates access controls for FHIR Resource operations on patient data.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.models.access_log import AccessContext, AccessLog, AccessResult, AccessType
from src.models.associations import (
    patient_organization_association,
    patient_provider_association,
)

logger = logging.getLogger(__name__)


class AccessControlService:
    """Service for managing access control between patients, providers, and organizations."""

    def __init__(self, db: Session):
        """Initialize the Access Control Service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def validate_access_request(self, access_request: Dict[str, Any]) -> bool:
        """Validate access request for FHIR Consent resource compliance.

        Args:
            access_request: Dictionary containing access request information

        Returns:
            bool: True if request is valid for FHIR operations, False otherwise
        """
        if not access_request:
            logger.error("Access request validation failed: empty request")
            return False

        # Validate required fields for FHIR Consent resource
        required_fields = ["patient_id", "requester_id", "access_type", "purpose"]
        for field in required_fields:
            if field not in access_request:
                logger.error(
                    "Missing required field for FHIR Consent Resource: %s", field
                )
                return False

        # Validate access type
        valid_access_types = ["view", "create", "update", "delete", "export"]
        if access_request.get("access_type", "").lower() not in valid_access_types:
            logger.error("Invalid access type: %s", access_request.get("access_type"))
            return False

        return True

    def check_provider_patient_access(
        self,
        provider_id: str,
        patient_id: str,
        required_scope: Optional[str] = None,
        log_access: bool = True,
    ) -> bool:
        """Check if a provider has access to a patient's records.

        Args:
            provider_id: UUID of the provider
            patient_id: UUID of the patient
            required_scope: Optional specific scope required (e.g., 'medications', 'diagnoses')
            log_access: Whether to log this access check

        Returns:
            bool: True if provider has valid access, False otherwise
        """
        try:
            # Query the association table
            query = self.db.query(patient_provider_association).filter(
                and_(
                    patient_provider_association.c.provider_id == provider_id,
                    patient_provider_association.c.patient_id == patient_id,
                    patient_provider_association.c.consent_given.is_(True),
                )
            )

            # Check if relationship exists
            result = query.first()

            if not result:
                if log_access:
                    self._log_access_attempt(
                        user_id=provider_id,
                        patient_id=patient_id,
                        access_type=AccessType.VIEW,
                        result=AccessResult.DENIED,
                        reason="No provider-patient relationship found",
                    )
                return False

            # Check if relationship is still valid
            now = datetime.utcnow()
            if result.valid_until and result.valid_until < now:
                if log_access:
                    self._log_access_attempt(
                        user_id=provider_id,
                        patient_id=patient_id,
                        access_type=AccessType.VIEW,
                        result=AccessResult.DENIED,
                        reason="Provider-patient relationship expired",
                    )
                return False

            # Check if specific scope is required and granted
            if required_scope and result.consent_scope:
                try:
                    consent_scopes = json.loads(result.consent_scope)
                    if (
                        isinstance(consent_scopes, list)
                        and required_scope not in consent_scopes
                    ):
                        if log_access:
                            self._log_access_attempt(
                                user_id=provider_id,
                                patient_id=patient_id,
                                access_type=AccessType.VIEW,
                                result=AccessResult.DENIED,
                                reason=f"Required scope '{required_scope}' not granted",
                            )
                        return False
                except json.JSONDecodeError:
                    logger.error(
                        "Invalid consent_scope JSON for provider %s and patient %s",
                        provider_id,
                        patient_id,
                    )

            # Access granted
            if log_access:
                self._log_access_attempt(
                    user_id=provider_id,
                    patient_id=patient_id,
                    access_type=AccessType.VIEW,
                    result=AccessResult.SUCCESS,
                    reason="Valid provider-patient relationship",
                )

            return True

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.error("Error checking provider-patient access: %s", str(e))
            return False

    def check_organization_patient_access(
        self,
        organization_id: str,
        patient_id: str,
        user_id: Optional[str] = None,
        required_scope: Optional[str] = None,
        log_access: bool = True,
    ) -> bool:
        """Check if an organization has access to a patient's records.

        Args:
            organization_id: UUID of the organization
            patient_id: UUID of the patient
            user_id: Optional UUID of the user making the request
            required_scope: Optional specific scope required
            log_access: Whether to log this access check

        Returns:
            bool: True if organization has valid access, False otherwise
        """
        try:
            # Query the association table
            query = self.db.query(patient_organization_association).filter(
                and_(
                    patient_organization_association.c.organization_id
                    == organization_id,
                    patient_organization_association.c.patient_id == patient_id,
                    patient_organization_association.c.consent_given.is_(True),
                )
            )

            # Check if relationship exists
            result = query.first()

            if not result:
                if log_access and user_id:
                    self._log_access_attempt(
                        user_id=user_id,
                        patient_id=patient_id,
                        access_type=AccessType.VIEW,
                        result=AccessResult.DENIED,
                        reason=f"No relationship between organization {organization_id} and patient",
                    )
                return False

            # Check if relationship is still valid
            now = datetime.utcnow()
            if result.valid_until and result.valid_until < now:
                if log_access and user_id:
                    self._log_access_attempt(
                        user_id=user_id,
                        patient_id=patient_id,
                        access_type=AccessType.VIEW,
                        result=AccessResult.DENIED,
                        reason="Organization-patient relationship expired",
                    )
                return False

            # Check if specific scope is required and granted
            if required_scope and result.consent_scope:
                try:
                    consent_scopes = json.loads(result.consent_scope)
                    if (
                        isinstance(consent_scopes, list)
                        and required_scope not in consent_scopes
                    ):
                        if log_access and user_id:
                            self._log_access_attempt(
                                user_id=user_id,
                                patient_id=patient_id,
                                access_type=AccessType.VIEW,
                                result=AccessResult.DENIED,
                                reason=f"Required scope '{required_scope}' not granted to organization",
                            )
                        return False
                except json.JSONDecodeError:
                    logger.error(
                        "Invalid consent_scope JSON for organization %s and patient %s",
                        organization_id,
                        patient_id,
                    )

            # Access granted
            if log_access and user_id:
                self._log_access_attempt(
                    user_id=user_id,
                    patient_id=patient_id,
                    access_type=AccessType.VIEW,
                    result=AccessResult.SUCCESS,
                    reason=f"Valid organization relationship via {organization_id}",
                )

            return True

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.error("Error checking organization-patient access: %s", str(e))
            return False

    def grant_provider_access(
        self,
        provider_id: str,
        patient_id: str,
        relationship_type: str = "primary_care",
        consent_scope: Optional[List[str]] = None,
        valid_until: Optional[datetime] = None,
        created_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """Grant a provider access to a patient's records.

        Args:
            provider_id: UUID of the provider
            patient_id: UUID of the patient
            relationship_type: Type of relationship (e.g., 'primary_care', 'specialist')
            consent_scope: List of scopes granted (e.g., ['medications', 'diagnoses'])
            valid_until: When the access expires (None for no expiration)
            created_by: UUID of the user creating this relationship
            notes: Optional notes about the relationship

        Returns:
            bool: True if access was granted successfully
        """
        try:
            # Check if relationship already exists
            existing = (
                self.db.query(patient_provider_association)
                .filter(
                    and_(
                        patient_provider_association.c.provider_id == provider_id,
                        patient_provider_association.c.patient_id == patient_id,
                    )
                )
                .first()
            )

            if existing:
                # Update existing relationship
                self.db.execute(
                    patient_provider_association.update()
                    .where(
                        and_(
                            patient_provider_association.c.provider_id == provider_id,
                            patient_provider_association.c.patient_id == patient_id,
                        )
                    )
                    .values(
                        consent_given=True,  # HIPAA: Track consent status with encryption
                        consent_scope=(
                            json.dumps(consent_scope) if consent_scope else None
                        ),
                        valid_until=valid_until,
                        relationship_type=relationship_type,
                        notes=notes,
                    )
                )
            else:
                # Create new relationship
                self.db.execute(
                    patient_provider_association.insert().values(
                        provider_id=provider_id,  # HIPAA: Provider ID requires encryption
                        patient_id=patient_id,  # HIPAA: Patient ID requires field_encryption
                        relationship_type=relationship_type,
                        consent_given=True,  # HIPAA: Track consent status with encryption
                        consent_scope=(
                            json.dumps(consent_scope) if consent_scope else None
                        ),
                        valid_until=valid_until,
                        created_by=created_by,
                        notes=notes,
                    )
                )

            self.db.commit()

            logger.info(
                "Granted provider %s access to patient %s", provider_id, patient_id
            )
            return True

        except (ValueError, TypeError) as e:
            logger.error("Error granting provider access: %s", str(e))
            self.db.rollback()
            return False

    def revoke_provider_access(self, provider_id: str, patient_id: str) -> bool:
        """Revoke a provider's access to a patient's records.

        Args:
            provider_id: UUID of the provider
            patient_id: UUID of the patient

        Returns:
            bool: True if access was revoked successfully
        """
        try:
            self.db.execute(
                patient_provider_association.update()
                .where(
                    and_(
                        patient_provider_association.c.provider_id == provider_id,
                        patient_provider_association.c.patient_id == patient_id,
                    )
                )
                .values(consent_given=False)
            )

            self.db.commit()

            logger.info(
                "Revoked provider %s access to patient %s", provider_id, patient_id
            )
            return True

        except (ValueError, TypeError) as e:
            logger.error("Error revoking provider access: %s", str(e))
            self.db.rollback()
            return False

    def _log_access_attempt(
        self,
        user_id: str,
        patient_id: str,
        access_type: AccessType,
        result: AccessResult,
        reason: str,
    ) -> None:
        """Log an access attempt to the audit log.

        Args:
            user_id: UUID of the user attempting access
            patient_id: UUID of the patient being accessed
            access_type: Type of access attempted
            result: Result of the access attempt
            reason: Reason for the result
        """
        try:
            AccessLog.log_access(
                session=self.db,
                user_id=UUID(user_id),
                resource_type="patient",
                resource_id=UUID(patient_id),
                access_type=access_type,
                access_context=AccessContext.API,
                purpose=reason,
                patient_id=UUID(patient_id),
                access_result=result,
            )
            self.db.commit()
        except (ValueError, TypeError, AttributeError) as e:
            logger.error("Error logging access attempt: %s", str(e))
            # Don't fail the main operation if logging fails
            self.db.rollback()
