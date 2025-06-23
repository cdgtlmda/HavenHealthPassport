"""Organization Service for Haven Health Passport.

This service manages organization operations including patient relationships,
member management, and organizational access control. Validates organization
data for FHIR Resource compliance and healthcare standards.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from src.models.associations import (
    patient_organization_association,
    provider_organization_association,
)
from src.models.organization import Organization
from src.models.patient import Patient
from src.services.access_control_service import AccessControlService

logger = logging.getLogger(__name__)


class OrganizationService:
    """Service for managing organizations and their relationships."""

    def __init__(self, db: Session):
        """Initialize the Organization Service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.access_control = AccessControlService(db)

    def validate_organization_data(self, organization_data: Dict[str, Any]) -> bool:
        """Validate organization data for FHIR compliance.

        Args:
            organization_data: Dictionary containing organization information

        Returns:
            bool: True if data is valid, False otherwise
        """
        if not organization_data:
            return False

        # Ensure required fields are present
        required_fields = ["name", "type"]
        for field in required_fields:
            if field not in organization_data:
                logger.error(
                    "Missing required field for FHIR Organization Resource: %s", field
                )
                return False

        return True

    def check_organization_patient_access(
        self, organization_id: str, patient_id: str
    ) -> bool:
        """Check if an organization has access to a patient's records.

        This is a convenience method that delegates to AccessControlService.

        Args:
            organization_id: UUID of the organization
            patient_id: UUID of the patient

        Returns:
            bool: True if organization has valid access, False otherwise
        """
        return self.access_control.check_organization_patient_access(
            organization_id=organization_id, patient_id=patient_id, log_access=True
        )

    def get_organization_patients(
        self,
        organization_id: str,
        camp_location: Optional[str] = None,
        program: Optional[str] = None,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get all patients associated with an organization.

        Args:
            organization_id: UUID of the organization
            camp_location: Optional filter by camp location
            program: Optional filter by program enrollment
            active_only: Whether to only return active relationships
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of patient records with relationship details
        """
        try:
            # Build the query
            query = (
                self.db.query(
                    Patient,
                    patient_organization_association.c.relationship_type,
                    patient_organization_association.c.valid_from,
                    patient_organization_association.c.valid_until,
                    patient_organization_association.c.camp_location,
                    patient_organization_association.c.program_enrollment,
                )
                .join(
                    patient_organization_association,
                    Patient.id == patient_organization_association.c.patient_id,
                )
                .filter(
                    patient_organization_association.c.organization_id
                    == organization_id
                )
            )

            # Apply filters
            if active_only:
                now = datetime.utcnow()
                query = query.filter(
                    and_(
                        patient_organization_association.c.consent_given.is_(True),
                        or_(
                            patient_organization_association.c.valid_until.is_(None),
                            patient_organization_association.c.valid_until > now,
                        ),
                    )
                )

            if camp_location:
                query = query.filter(
                    patient_organization_association.c.camp_location == camp_location
                )

            if program:
                query = query.filter(
                    patient_organization_association.c.program_enrollment.contains(
                        program
                    )
                )

            # Apply pagination
            # Count total results for pagination metadata
            # total_count = query.count()
            results = query.limit(limit).offset(offset).all()

            # Format results
            patients = []
            for patient, rel_type, valid_from, valid_until, camp, programs in results:
                patient_dict = patient.to_dict()
                patient_dict["relationship"] = {
                    "type": rel_type,
                    "valid_from": valid_from.isoformat() if valid_from else None,
                    "valid_until": valid_until.isoformat() if valid_until else None,
                    "camp_location": camp,
                    "programs": programs,
                }
                patients.append(patient_dict)

            return patients

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("Error getting organization patients: %s", str(e))
            return []

    def add_provider_to_organization(
        self,
        provider_id: str,
        organization_id: str,
        role: str = "healthcare_provider",
        department: Optional[str] = None,
    ) -> bool:
        """Add a provider to an organization.

        Args:
            provider_id: UUID of the provider
            organization_id: UUID of the organization
            role: Role of the provider in the organization
            department: Optional department within the organization

        Returns:
            bool: True if provider was added successfully
        """
        try:
            # Check if relationship already exists
            existing = (
                self.db.query(provider_organization_association)
                .filter(
                    and_(
                        provider_organization_association.c.provider_id == provider_id,
                        provider_organization_association.c.organization_id
                        == organization_id,
                    )
                )
                .first()
            )

            if existing:
                # Update existing relationship
                self.db.execute(
                    provider_organization_association.update()
                    .where(
                        and_(
                            provider_organization_association.c.provider_id
                            == provider_id,
                            provider_organization_association.c.organization_id
                            == organization_id,
                        )
                    )
                    .values(
                        role=role,
                        department=department,
                        active=True,
                        updated_at=datetime.utcnow(),
                    )
                )
            else:
                # Create new relationship
                self.db.execute(
                    provider_organization_association.insert().values(
                        provider_id=provider_id,
                        organization_id=organization_id,
                        role=role,
                        department=department,
                        active=True,
                    )
                )

            # Update organization member count
            self._update_member_count(organization_id)

            self.db.commit()
            logger.info(
                "Added provider %s to organization %s", provider_id, organization_id
            )
            return True

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("Error adding provider to organization: %s", str(e))
            self.db.rollback()
            return False

    def grant_organization_patient_access(
        self,
        organization_id: str,
        patient_id: str,
        relationship_type: str = "care_provider",
        consent_scope: Optional[List[str]] = None,
        valid_until: Optional[datetime] = None,
        camp_location: Optional[str] = None,
        program_enrollment: Optional[str] = None,
        created_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """Grant an organization access to a patient's records.

        Args:
            organization_id: UUID of the organization
            patient_id: UUID of the patient
            relationship_type: Type of relationship
            consent_scope: List of scopes granted
            valid_until: When the access expires
            camp_location: Specific camp/location where relationship is valid
            program_enrollment: Programs the patient is enrolled in
            created_by: UUID of the user creating this relationship
            notes: Optional notes about the relationship

        Returns:
            bool: True if access was granted successfully
        """
        try:
            # Check if relationship already exists
            existing = (
                self.db.query(patient_organization_association)
                .filter(
                    and_(
                        patient_organization_association.c.organization_id
                        == organization_id,
                        patient_organization_association.c.patient_id == patient_id,
                    )
                )
                .first()
            )

            if existing:
                # Update existing relationship
                self.db.execute(
                    patient_organization_association.update()
                    .where(
                        and_(
                            patient_organization_association.c.organization_id
                            == organization_id,
                            patient_organization_association.c.patient_id == patient_id,
                        )
                    )
                    .values(
                        consent_given=True,
                        consent_scope=(
                            json.dumps(consent_scope) if consent_scope else None
                        ),
                        valid_until=valid_until,
                        relationship_type=relationship_type,
                        camp_location=camp_location,
                        program_enrollment=program_enrollment,
                        notes=notes,
                    )
                )
            else:
                # Create new relationship
                self.db.execute(
                    patient_organization_association.insert().values(
                        organization_id=organization_id,
                        patient_id=patient_id,
                        relationship_type=relationship_type,
                        consent_given=True,
                        consent_scope=(
                            json.dumps(consent_scope) if consent_scope else None
                        ),
                        valid_until=valid_until,
                        camp_location=camp_location,
                        program_enrollment=program_enrollment,
                        created_by=created_by,
                        notes=notes,
                    )
                )

            # Update organization patient count
            self._update_patient_count(organization_id)

            self.db.commit()
            logger.info(
                "Granted organization %s access to patient %s",
                organization_id,
                patient_id,
            )
            return True

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("Error granting organization access: %s", str(e))
            self.db.rollback()
            return False

    def _update_member_count(self, organization_id: str) -> None:
        """Update the member count for an organization."""
        try:
            count = (
                self.db.query(provider_organization_association)
                .filter(
                    and_(
                        provider_organization_association.c.organization_id
                        == organization_id,
                        provider_organization_association.c.active.is_(True),
                    )
                )
                .count()
            )

            self.db.query(Organization).filter(
                Organization.id == organization_id
            ).update({"member_count": count})

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("Error updating member count: %s", str(e))

    def _update_patient_count(self, organization_id: str) -> None:
        """Update the patient count for an organization."""
        try:
            now = datetime.utcnow()
            count = (
                self.db.query(patient_organization_association)
                .filter(
                    and_(
                        patient_organization_association.c.organization_id
                        == organization_id,
                        patient_organization_association.c.consent_given.is_(True),
                        or_(
                            patient_organization_association.c.valid_until.is_(None),
                            patient_organization_association.c.valid_until > now,
                        ),
                    )
                )
                .count()
            )

            self.db.query(Organization).filter(
                Organization.id == organization_id
            ).update({"patient_count": count})

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("Error updating patient count: %s", str(e))

    def get_organization_by_id(self, organization_id: str) -> Optional[Organization]:
        """Get an organization by its ID.

        Args:
            organization_id: UUID of the organization

        Returns:
            Organization object or None
        """
        try:
            return (
                self.db.query(Organization)
                .filter(Organization.id == organization_id)
                .first()
            )
        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("Error getting organization: %s", str(e))
            return None
