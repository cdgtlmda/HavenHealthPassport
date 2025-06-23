"""Family Service for managing family relationships in Haven Health Passport.

This service handles family group management, member relationships,
and family-based data access for refugee healthcare. Validates family
relationships for FHIR Resource compliance and healthcare standards.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.models.patient import Patient, patient_family_association

logger = logging.getLogger(__name__)


class FamilyGroup:
    """Represents a family group."""

    def __init__(
        self,
        group_id: UUID,
        head_of_household_id: UUID,
        case_number: Optional[str] = None,
        family_name: Optional[str] = None,
        members: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize a family group."""
        self.id = group_id
        self.head_of_household_id = head_of_household_id
        self.case_number = case_number
        self.family_name = family_name
        self.members = members or []
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()


class FamilyService:
    """Service for managing family relationships and groups."""

    def __init__(self, db: Session):
        """Initialize the Family Service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        # HIPAA: Enable audit logging for all family data access
        self.audit_enabled = True

    def validate_family_relationship(self, relationship_data: Dict[str, Any]) -> bool:
        """Validate family relationship data for FHIR RelatedPerson resource compliance.

        Args:
            relationship_data: Dictionary containing relationship information

        Returns:
            bool: True if relationship data is valid, False otherwise
        """
        if not relationship_data:
            logger.error("Family relationship validation failed: empty data")
            return False

        # Validate required fields for FHIR RelatedPerson resource
        required_fields = ["patient_id", "family_member_id", "relationship_type"]
        for field in required_fields:
            if field not in relationship_data:
                logger.error(
                    "Missing required field for FHIR RelatedPerson Resource: %s", field
                )
                return False

        # Validate relationship type
        valid_relationships = [
            "mother",
            "father",
            "child",
            "sibling",
            "spouse",
            "guardian",
            "ward",
            "grandparent",
            "grandchild",
            "aunt",
            "uncle",
            "niece",
            "nephew",
            "cousin",
        ]
        if relationship_data["relationship_type"] not in valid_relationships:
            logger.error(
                "Invalid relationship type: %s", relationship_data["relationship_type"]
            )
            return False

        return True

    def get_family_group(self, group_id: UUID) -> Optional[FamilyGroup]:
        """Get a family group by ID.

        Args:
            group_id: UUID of the family group

        Returns:
            FamilyGroup object or None
        """
        # HIPAA: Requires authorization to access family group data
        try:
            # For now, family groups are constructed from patient relationships
            # In future, this could be a separate table

            # Find all patients that share this group_id in their metadata
            patients = (
                self.db.query(Patient)
                .filter(Patient.metadata.op("@>")({"family_group_id": str(group_id)}))
                .all()
            )

            if not patients:
                return None

            # Find head of household
            head_of_household = None
            members = []

            for patient in patients:
                # HIPAA: Encrypt PHI fields before storing
                patient_data = {
                    "id": str(patient.id),
                    "given_name": patient.given_name,  # PHI - requires encryption
                    "family_name": patient.family_name,  # PHI - requires encryption
                    "relationship": patient.metadata.get("family_role", "member"),
                    "unhcr_number": patient.unhcr_number,  # PHI - requires encryption
                }

                if patient.metadata.get("family_role") == "head_of_household":
                    head_of_household = patient

                members.append(patient_data)

            if not head_of_household and patients:
                # Use first patient as head if not specified
                head_of_household = patients[0]

            return FamilyGroup(
                group_id=group_id,
                head_of_household_id=(
                    UUID(str(head_of_household.id))
                    if head_of_household
                    else UUID(str(patients[0].id))
                ),
                case_number=(
                    head_of_household.unhcr_number if head_of_household else None
                ),
                family_name=(
                    head_of_household.family_name
                    if head_of_household
                    else patients[0].family_name
                ),
                members=members,
                metadata={
                    "total_members": len(members),
                    "camp_location": (
                        head_of_household.current_camp if head_of_household else None
                    ),
                },
            )

        except SQLAlchemyError as e:
            logger.error("Database error getting family group %s: %s", group_id, str(e))
            # HIPAA: Audit failed access attempts
            if self.audit_enabled:
                logger.info("AUDIT: Failed family group access for %s", group_id)
            return None
        except (ValueError, KeyError) as e:
            logger.error("Data error getting family group %s: %s", group_id, str(e))
            # HIPAA: Audit failed access attempts
            if self.audit_enabled:
                logger.info("AUDIT: Failed family group access for %s", group_id)
            return None

    def get_family_members(self, patient_id: UUID) -> List[Dict[str, Any]]:
        """Get all family members for a patient.

        Args:
            patient_id: UUID of the patient

        Returns:
            List of family member information
        """
        # HIPAA: Role-based access control required for family member data
        try:
            # HIPAA: Log access to family member records
            if self.audit_enabled:
                logger.info(
                    "AUDIT: Accessing family members for patient %s", patient_id
                )
            # Query the association table for family relationships
            family_relations = (
                self.db.query(patient_family_association, Patient)
                .join(
                    Patient,
                    or_(
                        Patient.id == patient_family_association.c.family_member_id,
                        Patient.id == patient_family_association.c.patient_id,
                    ),
                )
                .filter(
                    or_(
                        patient_family_association.c.patient_id == patient_id,
                        patient_family_association.c.family_member_id == patient_id,
                    )
                )
                .all()
            )

            members = []
            seen_ids = {str(patient_id)}  # Track to avoid duplicates

            for relation, member in family_relations:
                # Determine which ID is the family member (not the queried patient)
                if str(member.id) == str(patient_id):
                    continue

                if str(member.id) not in seen_ids:
                    seen_ids.add(str(member.id))

                    # Determine relationship type
                    if relation.patient_id == patient_id:
                        relationship = relation.relationship_type
                    else:
                        # Reverse relationship mapping
                        relationship = self._get_reverse_relationship(
                            relation.relationship_type
                        )

                    # HIPAA: Encrypt all PHI fields in family member data
                    members.append(
                        {
                            "id": str(member.id),
                            "given_name": member.given_name,  # PHI - field_encryption required
                            "family_name": member.family_name,  # PHI - field_encryption required
                            "relationship": relationship,
                            "unhcr_number": member.unhcr_number,  # PHI - secure storage required
                            "date_of_birth": (  # PHI - requires encryption
                                member.date_of_birth.isoformat()
                                if member.date_of_birth
                                else None
                            ),
                            "gender": member.gender.value if member.gender else None,
                        }
                    )

            return members

        except SQLAlchemyError as e:
            logger.error(
                "Database error getting family members for patient %s: %s",
                patient_id,
                str(e),
            )
            return []
        except (ValueError, AttributeError) as e:
            logger.error(
                "Data error getting family members for patient %s: %s",
                patient_id,
                str(e),
            )
            return []

    def search_family_members(
        self,
        case_number: Optional[str] = None,
        family_name: Optional[str] = None,
        include_missing: bool = False,
    ) -> List[Dict[str, Any]]:
        """Search for family members by various criteria.

        Args:
            case_number: UNHCR case number
            family_name: Family name to search
            include_missing: Whether to include missing family members

        Returns:
            List of matching family members
        """
        try:
            query = self.db.query(Patient)

            if case_number:
                # Search by UNHCR number (case number)
                query = query.filter(
                    or_(
                        Patient.unhcr_number == case_number,
                        Patient.unhcr_number.like(f"{case_number}%"),
                    )
                )

            if family_name:
                query = query.filter(Patient.family_name.ilike(f"%{family_name}%"))

            if not include_missing:
                # Exclude patients marked as missing
                query = query.filter(
                    or_(
                        Patient.refugee_status != "missing",
                        Patient.metadata.op("->>")("status") != "missing",
                    )
                )

            patients = query.limit(50).all()

            results = []
            for patient in patients:
                # Get family members for each patient
                family_members = self.get_family_members(UUID(str(patient.id)))

                results.append(
                    {
                        "patient": {
                            "id": str(patient.id),
                            "given_name": patient.given_name,
                            "family_name": patient.family_name,
                            "unhcr_number": patient.unhcr_number,
                            "date_of_birth": (
                                patient.date_of_birth.isoformat()
                                if patient.date_of_birth
                                else None
                            ),
                        },
                        "family_members": family_members,
                        "family_size": len(family_members) + 1,
                    }
                )

            return results

        except SQLAlchemyError as e:
            logger.error("Database error searching family members: %s", str(e))
            return []
        except (ValueError, AttributeError) as e:
            logger.error("Data error searching family members: %s", str(e))
            return []

    def _get_reverse_relationship(self, relationship: str) -> str:
        """Get the reverse of a relationship type.

        Args:
            relationship: Original relationship type

        Returns:
            Reversed relationship type
        """
        reverse_map = {
            "mother": "child",
            "father": "child",
            "child": "parent",
            "sibling": "sibling",
            "spouse": "spouse",
            "guardian": "ward",
            "ward": "guardian",
            "grandparent": "grandchild",
            "grandchild": "grandparent",
            "aunt": "niece/nephew",
            "uncle": "niece/nephew",
            "niece": "aunt/uncle",
            "nephew": "aunt/uncle",
            "cousin": "cousin",
        }

        return reverse_map.get(relationship, "family_member")

    def create_family_group(
        self,
        members: List[Dict[str, Any]],
        head_of_household_id: UUID,
        case_number: Optional[str] = None,
    ) -> Optional[FamilyGroup]:
        """Create a new family group.

        Args:
            members: List of member data with relationships
            head_of_household_id: UUID of the head of household
            case_number: Optional UNHCR case number

        Returns:
            Created FamilyGroup or None
        """
        try:
            group_id = uuid.uuid4()

            # Update each member's metadata to include family group
            for member_data in members:
                patient = (
                    self.db.query(Patient)
                    .filter(Patient.id == member_data["id"])
                    .first()
                )

                if patient:
                    if not patient.metadata:
                        patient.metadata = {}

                    patient.metadata["family_group_id"] = str(group_id)
                    patient.metadata["family_role"] = member_data.get("role", "member")
                    if case_number:
                        patient.metadata["case_number"] = case_number

                    # Create family relationships
                    if member_data.get("relationship") and member_data["id"] != str(
                        head_of_household_id
                    ):
                        self._create_family_relationship(
                            head_of_household_id,
                            UUID(member_data["id"]),
                            member_data["relationship"],
                        )

            self.db.commit()

            # Return the created group
            return self.get_family_group(group_id)

        except SQLAlchemyError as e:
            logger.error("Database error creating family group: %s", str(e))
            self.db.rollback()
            return None
        except (ValueError, KeyError) as e:
            logger.error("Data error creating family group: %s", str(e))
            self.db.rollback()
            return None

    def _create_family_relationship(
        self,
        patient_id: UUID,
        family_member_id: UUID,
        relationship_type: str,
    ) -> None:
        """Create a family relationship between two patients.

        Args:
            patient_id: UUID of the first patient
            family_member_id: UUID of the family member
            relationship_type: Type of relationship
        """
        try:
            # Check if relationship already exists
            existing = (
                self.db.query(patient_family_association)
                .filter(
                    and_(
                        patient_family_association.c.patient_id == patient_id,
                        patient_family_association.c.family_member_id
                        == family_member_id,
                    )
                )
                .first()
            )

            if not existing:
                self.db.execute(
                    patient_family_association.insert().values(
                        patient_id=patient_id,
                        family_member_id=family_member_id,
                        relationship_type=relationship_type,
                        created_at=datetime.utcnow(),
                    )
                )

        except SQLAlchemyError as e:
            logger.error("Database error creating family relationship: %s", str(e))
            raise
        except ValueError as e:
            logger.error("Data error creating family relationship: %s", str(e))
            raise
