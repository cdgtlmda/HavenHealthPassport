"""Patient Link Relationships.

This module defines patient link relationships for tracking family connections,
care relationships, and record linkages across different systems, with special
focus on refugee family reunification and cross-border record tracking.
Handles FHIR Patient Resource validation for linked records.

COMPLIANCE NOTE: This module handles PHI including family relationships,
patient linkages, and cross-system patient matching. All relationship data
must be encrypted. Access control is essential - family relationship data
requires patient consent for sharing. Implement safeguards for vulnerable
populations and family separation cases. Audit all relationship queries
and modifications.
"""

import hashlib
import json
import logging
import re
import unicodedata
from datetime import date, datetime
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, cast

from src.database import get_db
from src.healthcare.fhir_validator import FHIRValidator
from src.healthcare.hipaa_access_control import (
    AccessLevel,
    require_phi_access,
)
from src.models.patient import Patient
from src.services.encryption_service import EncryptionService

logger = logging.getLogger(__name__)

# FHIR resource type for this module
__fhir_resource__ = "Patient"


class LinkType(Enum):
    """Types of patient relationships and record links."""

    # FHIR standard link types
    REPLACED_BY = "replaced-by"  # Patient record replaced by another
    REPLACES = "replaces"  # Patient record replaces another
    REFER = "refer"  # Patient referred to another record
    SEE_ALSO = "seealso"  # Additional related patient record

    # Family relationships
    PARENT = "parent"  # Parent of patient
    CHILD = "child"  # Child of patient
    SPOUSE = "spouse"  # Spouse/partner
    SIBLING = "sibling"  # Brother/sister
    GRANDPARENT = "grandparent"  # Grandparent
    GRANDCHILD = "grandchild"  # Grandchild
    GUARDIAN = "guardian"  # Legal guardian
    FOSTER = "foster"  # Foster parent/child

    # Extended family
    AUNT_UNCLE = "aunt-uncle"  # Aunt or uncle
    NIECE_NEPHEW = "niece-nephew"  # Niece or nephew
    COUSIN = "cousin"  # Cousin
    IN_LAW = "in-law"  # In-law relationship
    STEP = "step"  # Step-family relationship

    # Refugee-specific relationships
    FAMILY_GROUP = "family-group"  # Member of same family group
    TRAVELING_COMPANION = "traveling-companion"  # Traveled together
    CAREGIVER = "caregiver"  # Informal caregiver
    DEPENDENT = "dependent"  # Dependent (not child)
    SPONSOR = "sponsor"  # Resettlement sponsor
    HOST_FAMILY = "host-family"  # Host family member

    # Institutional relationships
    CASE_WORKER = "case-worker"  # Assigned case worker
    INTERPRETER = "interpreter"  # Regular interpreter
    COMMUNITY_LEADER = "community-leader"  # Community representative

    # Record linkages
    SAME_PERSON = "same-person"  # Different records, same person
    POSSIBLE_MATCH = "possible-match"  # Potential duplicate
    CROSS_BORDER = "cross-border"  # Record in another country
    PREVIOUS_CAMP = "previous-camp"  # Record from previous location
    MERGED_FROM = "merged-from"  # Record merged from this one
    MERGED_TO = "merged-to"  # Record merged into this one


class LinkStatus(Enum):
    """Status of the link relationship."""

    ACTIVE = "active"  # Currently active relationship
    INACTIVE = "inactive"  # No longer active
    PENDING = "pending"  # Pending verification
    DISPUTED = "disputed"  # Relationship disputed
    LOST_CONTACT = "lost-contact"  # Lost contact (missing person)
    DECEASED = "deceased"  # Linked person is deceased
    REUNITED = "reunited"  # Successfully reunited
    SEARCHING = "searching"  # Actively searching for person


class VerificationMethod(Enum):
    """Methods used to verify relationships."""

    SELF_REPORTED = "self-reported"
    DOCUMENT = "document"  # Official documentation
    BIOMETRIC = "biometric"  # Biometric matching
    DNA = "dna"  # DNA testing
    WITNESS = "witness"  # Third-party witness
    PHOTO = "photo"  # Photo verification
    UNHCR_VERIFIED = "unhcr"  # UNHCR verification
    GOVERNMENT = "government"  # Government verification
    NGO = "ngo"  # NGO verification
    COMMUNITY = "community"  # Community verification


class FamilyRole(Enum):
    """Roles within a family unit."""

    HEAD_OF_HOUSEHOLD = "head"
    SPOUSE_OF_HEAD = "spouse-head"
    CHILD_OF_HEAD = "child-head"
    PARENT_OF_HEAD = "parent-head"
    OTHER_RELATIVE = "other-relative"
    NON_RELATIVE = "non-relative"


class PatientLink:
    """Represents a link between patients or records."""

    def __init__(self, link_type: LinkType, target_id: str):
        """Initialize patient link.

        Args:
            link_type: Type of relationship
            target_id: ID of linked patient/record
        """
        self.type = link_type
        self.target_id = target_id
        self.target_system: Optional[str] = None
        self.status = LinkStatus.ACTIVE
        self.verification_method: Optional[VerificationMethod] = None
        self.verified_date: Optional[date] = None
        self.verified_by: Optional[str] = None
        self.start_date: Optional[date] = None
        self.end_date: Optional[date] = None
        self.notes: Optional[str] = None
        self.metadata: Dict[str, Any] = {}
        self.validator = FHIRValidator()
        self.encryption_service = EncryptionService()

    @require_phi_access(AccessLevel.READ)
    def validate_link(self) -> bool:
        """Validate patient link.

        Returns:
            True if valid
        """
        try:
            # Validate required fields
            if not self.type or not self.target_id:
                return False

            # Validate dates if present
            if self.start_date and self.end_date:
                if self.start_date > self.end_date:
                    return False

            return True
        except (AttributeError, KeyError, TypeError, ValueError):
            return False

    def set_target_system(self, system: str) -> "PatientLink":
        """Set the system where target record exists."""
        self.target_system = system
        return self

    def set_status(self, status: LinkStatus) -> "PatientLink":
        """Set link status."""
        self.status = status
        return self

    def set_verification(
        self,
        method: VerificationMethod,
        verified_by: str,
        verified_date: Optional[date] = None,
    ) -> "PatientLink":
        """Set verification details."""
        self.verification_method = method
        self.verified_by = verified_by
        self.verified_date = verified_date or date.today()
        return self

    def set_period(self, start: date, end: Optional[date] = None) -> "PatientLink":
        """Set time period for relationship."""
        self.start_date = start
        self.end_date = end
        return self

    def add_metadata(self, key: str, value: Any) -> "PatientLink":
        """Add metadata to link."""
        self.metadata[key] = value
        return self

    def set_notes(self, notes: str) -> "PatientLink":
        """Set additional notes."""
        self.notes = notes
        return self

    def to_fhir(self) -> Dict[str, Any]:
        """Convert to FHIR PatientLink structure."""
        link: Dict[str, Any] = {
            "other": {"reference": f"Patient/{self.target_id}"},
            "type": self.type.value,
        }

        if self.target_system:
            other = link["other"]
            if isinstance(other, dict):
                other["identifier"] = {
                    "system": self.target_system,
                    "value": self.target_id,
                }

        # Add extensions for additional data
        extensions: List[Dict[str, Any]] = []

        # Status extension
        extensions.append(
            {
                "url": "http://havenhealthpassport.org/fhir/extension/link-status",
                "valueCode": self.status.value,
            }
        )

        # Verification extension
        if self.verification_method:
            verification_ext: Dict[str, Any] = {
                "url": "http://havenhealthpassport.org/fhir/extension/link-verification",
                "extension": [
                    {"url": "method", "valueCode": self.verification_method.value}
                ],
            }

            if self.verified_by:
                verification_ext["extension"].append(
                    {"url": "verifier", "valueString": self.verified_by}
                )

            if self.verified_date:
                verification_ext["extension"].append(
                    {"url": "date", "valueDate": self.verified_date.isoformat()}
                )

            extensions.append(verification_ext)

        # Period extension
        if self.start_date:
            period_ext: Dict[str, Any] = {
                "url": "http://havenhealthpassport.org/fhir/extension/link-period",
                "valuePeriod": {"start": self.start_date.isoformat()},
            }

            if self.end_date:
                period = period_ext["valuePeriod"]
                if isinstance(period, dict):
                    period["end"] = self.end_date.isoformat()

            extensions.append(period_ext)

        # Notes extension
        if self.notes:
            extensions.append(
                {
                    "url": "http://havenhealthpassport.org/fhir/extension/link-notes",
                    "valueString": self.notes,
                }
            )

        # Metadata extensions
        for key, value in self.metadata.items():
            extensions.append(
                {
                    "url": f"http://havenhealthpassport.org/fhir/extension/link-{key}",
                    "valueString": str(value),
                }
            )

        if extensions:
            link["extension"] = extensions

        return link


class FamilyGroup:
    """Represents a family group for refugee tracking."""

    def __init__(self, group_id: str):
        """Initialize family group.

        Args:
            group_id: Unique family group identifier
        """
        self.group_id = group_id
        self.members: List[Dict[str, Any]] = []
        self.head_of_household: Optional[str] = None
        self.case_number: Optional[str] = None
        self.camp_location: Optional[str] = None
        self.registration_date: Optional[date] = None
        self.last_verified: Optional[date] = None
        self.missing_members: List[Dict[str, Any]] = []
        self.separation_details: Optional[Dict[str, Any]] = None
        # Verification tracking fields
        self.verified_by: Optional[str] = None
        self.verified_at: Optional[datetime] = None
        self.verification_method: Optional[str] = None
        self.verification_evidence: Optional[Dict[str, Any]] = None

    def add_member(
        self,
        patient_id: str,
        role: FamilyRole,
        relationship_to_head: Optional[LinkType] = None,
    ) -> "FamilyGroup":
        """Add family member."""
        member = {
            "patient_id": patient_id,
            "role": role.value,
            "joined_date": date.today().isoformat(),
        }

        if relationship_to_head:
            member["relationship_to_head"] = relationship_to_head.value

        if role == FamilyRole.HEAD_OF_HOUSEHOLD:
            self.head_of_household = patient_id

        self.members.append(member)
        return self

    def add_missing_member(
        self,
        name: str,
        relationship: LinkType,
        last_seen_date: Optional[date] = None,
        last_seen_location: Optional[str] = None,
    ) -> "FamilyGroup":
        """Add missing family member for tracing."""
        missing = {
            "name": name,
            "relationship": relationship.value,
            "reported_missing": date.today().isoformat(),
        }

        if last_seen_date:
            missing["last_seen_date"] = last_seen_date.isoformat()

        if last_seen_location:
            missing["last_seen_location"] = last_seen_location

        self.missing_members.append(missing)
        return self

    def set_separation_details(
        self, date_separated: date, location_separated: str, circumstances: str
    ) -> "FamilyGroup":
        """Set family separation details."""
        self.separation_details = {
            "date": date_separated.isoformat(),
            "location": location_separated,
            "circumstances": circumstances,
        }
        return self

    def set_case_number(self, case_number: str) -> "FamilyGroup":
        """Set UNHCR or other case number."""
        self.case_number = case_number
        return self

    def set_location(self, location: str) -> "FamilyGroup":
        """Set current location."""
        self.camp_location = location
        return self

    def verify(self, verified_by: str) -> "FamilyGroup":
        """Mark family composition as verified."""
        self.verified_by = verified_by
        self.verified_at = datetime.now()
        self.verification_method = "manual_verification"
        self.last_verified = date.today()

        # Create verification audit log
        if hasattr(self, "_create_verification_audit"):
            self._create_verification_audit(verified_by)

        return self

    def get_family_size(self) -> int:
        """Get total family size including missing members."""
        return len(self.members) + len(self.missing_members)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "group_id": self.group_id,
            "case_number": self.case_number,
            "head_of_household": self.head_of_household,
            "members": self.members,
            "missing_members": self.missing_members,
            "family_size": self.get_family_size(),
            "location": self.camp_location,
            "registration_date": (
                self.registration_date.isoformat() if self.registration_date else None
            ),
            "last_verified": (
                self.last_verified.isoformat() if self.last_verified else None
            ),
            "separation_details": self.separation_details,
            # Verification information
            "verified_by": self.verified_by,
            "verified_at": (self.verified_at.isoformat() if self.verified_at else None),
            "verification_method": self.verification_method,
            "verification_evidence": self.verification_evidence,
        }


class LinkValidator:
    """Validation for patient links and relationships."""

    # Valid relationship pairs
    RECIPROCAL_RELATIONSHIPS = {
        LinkType.PARENT: LinkType.CHILD,
        LinkType.CHILD: LinkType.PARENT,
        LinkType.SPOUSE: LinkType.SPOUSE,
        LinkType.SIBLING: LinkType.SIBLING,
        LinkType.GRANDPARENT: LinkType.GRANDCHILD,
        LinkType.GRANDCHILD: LinkType.GRANDPARENT,
        LinkType.GUARDIAN: LinkType.DEPENDENT,
        LinkType.DEPENDENT: LinkType.GUARDIAN,
        LinkType.CAREGIVER: LinkType.DEPENDENT,
        LinkType.REPLACED_BY: LinkType.REPLACES,
        LinkType.REPLACES: LinkType.REPLACED_BY,
    }

    @classmethod
    def validate_relationship(
        cls,
        link_type: LinkType,
        source_age: Optional[int] = None,
        target_age: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Validate if relationship is logical.

        Args:
            link_type: Type of relationship
            source_age: Age of source patient
            target_age: Age of target patient

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Age-based validation
        if source_age is not None and target_age is not None:
            age_diff = abs(source_age - target_age)

            if link_type == LinkType.PARENT:
                if source_age <= target_age:
                    return False, "Parent must be older than child"
                if age_diff < 12:
                    return False, "Parent-child age difference too small"

            elif link_type == LinkType.CHILD:
                if source_age >= target_age:
                    return False, "Child must be younger than parent"
                if age_diff < 12:
                    return False, "Parent-child age difference too small"

            elif link_type == LinkType.SPOUSE:
                if source_age < 16 or target_age < 16:
                    return False, "Spouse relationship requires both parties to be 16+"

            elif link_type == LinkType.GRANDPARENT:
                if source_age <= target_age:
                    return False, "Grandparent must be older than grandchild"
                if age_diff < 25:
                    return False, "Grandparent-grandchild age difference too small"

        return True, None

    @classmethod
    def get_reciprocal_relationship(cls, link_type: LinkType) -> Optional[LinkType]:
        """Get the reciprocal relationship type."""
        return cls.RECIPROCAL_RELATIONSHIPS.get(link_type)

    @classmethod
    def validate_family_group(cls, family_group: FamilyGroup) -> Tuple[bool, List[str]]:
        """Validate family group composition.

        Args:
            family_group: Family group to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Must have at least one member
        if not family_group.members:
            errors.append("Family group must have at least one member")

        # Check for head of household
        heads = [
            m
            for m in family_group.members
            if m["role"] == FamilyRole.HEAD_OF_HOUSEHOLD.value
        ]

        if len(heads) == 0:
            errors.append("Family group must have a head of household")
        elif len(heads) > 1:
            errors.append("Family group can only have one head of household")

        # Validate head of household ID matches
        if heads and family_group.head_of_household != heads[0]["patient_id"]:
            errors.append("Head of household ID mismatch")

        return len(errors) == 0, errors


class RelationshipMapper:
    """Maps relationships between different systems and standards."""

    # Mapping to FHIR relationship codes
    FHIR_RELATIONSHIP_MAP = {
        LinkType.PARENT: "PRN",  # Parent
        LinkType.CHILD: "CHILD",  # Child
        LinkType.SPOUSE: "SPS",  # Spouse
        LinkType.SIBLING: "SIB",  # Sibling
        LinkType.GRANDPARENT: "GRPRN",  # Grandparent
        LinkType.GRANDCHILD: "GRNDCHILD",  # Grandchild
        LinkType.AUNT_UNCLE: "AUNT",  # Aunt/Uncle (FHIR uses AUNT for both)
        LinkType.NIECE_NEPHEW: "NEPHEW",  # Niece/Nephew
        LinkType.COUSIN: "COUSN",  # Cousin
        LinkType.GUARDIAN: "GUARD",  # Guardian
        LinkType.FOSTER: "FSTCHILD",  # Foster child
        LinkType.IN_LAW: "INLAW",  # In-law
        LinkType.STEP: "STPCHILD",  # Step relationship
    }

    @classmethod
    def to_fhir_code(cls, link_type: LinkType) -> Optional[str]:
        """Convert to FHIR relationship code."""
        return cls.FHIR_RELATIONSHIP_MAP.get(link_type)

    @classmethod
    def from_fhir_code(cls, fhir_code: str) -> Optional[LinkType]:
        """Convert from FHIR relationship code."""
        for link_type, code in cls.FHIR_RELATIONSHIP_MAP.items():
            if code == fhir_code:
                return link_type
        return None


def create_family_link_network(
    patient_id: str, links: List[PatientLink]
) -> Dict[str, Set[str]]:
    """Create network map of family relationships.

    Args:
        patient_id: Central patient ID
        links: List of patient links

    Returns:
        Dictionary mapping relationship types to sets of patient IDs
    """
    # Since PatientLink only has target_id, we assume links are directional from patient_id
    # Filter links to only include those related to the specified patient
    filtered_links = [link for link in links if link.target_id == patient_id]

    network: Dict[str, Set[str]] = {}

    # Group by relationship type
    for link in filtered_links:
        if link.status != LinkStatus.ACTIVE:
            continue

        link_type = link.type.value
        if link_type not in network:
            network[link_type] = set()

        # Add the target patient ID
        network[link_type].add(link.target_id)

    return network


def _compute_biometric_hash(biometric_data: Any) -> str:
    """Compute hash of biometric data for comparison.

    Args:
        biometric_data: Raw biometric data (fingerprint, face encoding, etc.)

    Returns:
        Hash string for comparison

    Note:
        In production, this would use specialized biometric libraries like:
        - NIST BOZORTH3 for fingerprint matching
        - dlib or OpenCV for face recognition
        - Voice biometric libraries for voice matching
    """
    if isinstance(biometric_data, dict):
        # Normalize the data structure for consistent hashing
        normalized = json.dumps(biometric_data, sort_keys=True)
        return hashlib.sha256(normalized.encode()).hexdigest()
    elif isinstance(biometric_data, (str, bytes)):
        # Handle raw biometric data
        if isinstance(biometric_data, str):
            biometric_data = biometric_data.encode()
        return hashlib.sha256(biometric_data).hexdigest()
    else:
        # Handle other data types
        return hashlib.sha256(str(biometric_data).encode()).hexdigest()


def find_missing_family_members(
    family_group: FamilyGroup, all_patients: List[str]
) -> List[Dict[str, Any]]:
    """Find potentially matching patients for missing family members.

    Args:
        family_group: Family group with missing members
        all_patients: List of all patient IDs to search

    Returns:
        List of potential matches with confidence scores
    """
    matches = []

    # Get database session
    db = next(get_db())

    try:
        # Load all patient records for matching
        patients = (
            db.query(Patient)
            .filter(Patient.id.in_(all_patients), Patient.deleted_at.is_(None))
            .all()
        )

        # Create a patient lookup dictionary for efficient access
        patient_dict = {str(patient.id): patient for patient in patients}

        for missing_member in family_group.missing_members:
            member_matches = []

            # Extract missing member details
            missing_name = missing_member.get("name", "").strip().lower()
            missing_relationship = missing_member.get("relationship", "")
            last_seen_date_str = missing_member.get("last_seen_date")
            last_seen_location = missing_member.get("last_seen_location", "")

            # Parse last seen date if available
            last_seen_date = None
            if last_seen_date_str:
                try:
                    last_seen_date = datetime.fromisoformat(last_seen_date_str).date()
                except (ValueError, TypeError):
                    pass

            # Match against each patient
            for patient_id, patient in patient_dict.items():
                score = 0.0
                match_details: Dict[str, Any] = {
                    "patient_id": patient_id,
                    "reasons": [],
                    "patient_data": {},
                }

                # Name matching with fuzzy logic
                patient_full_name = f"{patient.given_name or ''} {patient.family_name or ''}".strip().lower()
                name_ratio = SequenceMatcher(
                    None, missing_name, patient_full_name
                ).ratio()

                if name_ratio > 0.8:  # Strong name match
                    score += 40
                    match_details["reasons"].append(
                        f"Strong name match ({name_ratio:.0%})"
                    )
                    match_details["patient_data"]["name"] = patient_full_name
                elif name_ratio > 0.6:  # Partial name match
                    score += 20
                    match_details["reasons"].append(
                        f"Partial name match ({name_ratio:.0%})"
                    )
                    match_details["patient_data"]["name"] = patient_full_name

                # Also check individual name parts
                if missing_name:
                    name_parts = missing_name.split()
                    for part in name_parts:
                        if part and len(part) > 2:  # Skip very short parts
                            if (
                                patient.given_name
                                and part in patient.given_name.lower()
                            ):
                                score += 10
                                match_details["reasons"].append(
                                    f"Given name contains '{part}'"
                                )
                            if (
                                patient.family_name
                                and part in patient.family_name.lower()
                            ):
                                score += 10
                                match_details["reasons"].append(
                                    f"Family name contains '{part}'"
                                )

                # Location matching
                if last_seen_location and patient.current_camp:
                    location_ratio = SequenceMatcher(
                        None, last_seen_location.lower(), patient.current_camp.lower()
                    ).ratio()
                    if location_ratio > 0.8:
                        score += 20
                        match_details["reasons"].append(
                            f"Location match: {patient.current_camp}"
                        )
                        match_details["patient_data"]["location"] = patient.current_camp

                # Age estimation based on last seen date
                if last_seen_date and patient.date_of_birth:
                    # Calculate age difference tolerance
                    years_since = (datetime.now().date() - last_seen_date).days / 365.25
                    age_tolerance = 2 + int(
                        years_since
                    )  # More tolerance for older separations

                    patient_age_then = (
                        last_seen_date - patient.date_of_birth
                    ).days / 365.25
                    # Relationship-based age validation
                    if missing_relationship in ["child", "son", "daughter"]:
                        if 0 <= patient_age_then <= 18 + age_tolerance:
                            score += 15
                            match_details["reasons"].append(
                                "Age consistent with child relationship"
                            )
                    elif missing_relationship in ["parent", "mother", "father"]:
                        if patient_age_then >= 18:
                            score += 15
                            match_details["reasons"].append(
                                "Age consistent with parent relationship"
                            )

                # UNHCR number pattern matching (families often have similar numbers)
                if patient.unhcr_number and family_group.case_number:
                    if patient.unhcr_number[:6] == family_group.case_number[:6]:
                        score += 25
                        match_details["reasons"].append(
                            "Similar UNHCR case number pattern"
                        )
                        match_details["patient_data"][
                            "unhcr_number"
                        ] = patient.unhcr_number

                # Origin country matching
                if hasattr(patient, "origin_country"):
                    # Check if any current family member has same origin
                    for member in family_group.members:
                        member_patient_id = member.get("patient_id")
                        member_patient = (
                            patient_dict.get(member_patient_id)
                            if member_patient_id
                            else None
                        )
                        if member_patient and hasattr(member_patient, "origin_country"):
                            if member_patient.origin_country == patient.origin_country:
                                score += 10
                                match_details["reasons"].append(
                                    f"Same origin country: {patient.origin_country}"
                                )
                                break

                # Biometric matching implementation
                if patient.biometric_data_hash and missing_member.get("biometric_data"):
                    try:
                        # Compare biometric hashes for matching
                        # Note: In production, this would use a more sophisticated biometric matching algorithm
                        # such as NIST BOZORTH3 for fingerprints or face recognition algorithms
                        missing_biometric_hash = _compute_biometric_hash(
                            missing_member.get("biometric_data")
                        )

                        if missing_biometric_hash == patient.biometric_data_hash:
                            score += 50  # High confidence for biometric match
                            match_details["reasons"].append("Biometric data matches")
                            match_details["patient_data"]["has_biometrics"] = True
                            match_details["patient_data"]["biometric_match"] = True
                        else:
                            # For similar biometric patterns, we could implement fuzzy biometric matching
                            # This would require specialized biometric libraries
                            match_details["patient_data"]["has_biometrics"] = True
                            match_details["patient_data"]["biometric_match"] = False
                    except (TypeError, ValueError) as e:
                        logger.warning("Biometric comparison failed: %s", str(e))
                        match_details["patient_data"]["has_biometrics"] = True
                        match_details["patient_data"]["biometric_error"] = True

                # Only include matches with reasonable scores
                if score >= 30:  # Minimum threshold
                    match_details["confidence_score"] = min(score, 100)  # Cap at 100
                    match_details["missing_member"] = missing_member
                    member_matches.append(match_details)

            # Sort matches by score and take top 5
            member_matches.sort(key=lambda x: x["confidence_score"], reverse=True)
            matches.extend(member_matches[:5])

    finally:
        db.close()

    return matches


def match_patients(
    patient: Dict[str, Any],
    all_patients: List[Dict[str, Any]],
    matching_config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Implement probabilistic patient matching algorithm.

    This algorithm is designed for refugee populations where:
    - Birth dates may be estimated or unknown
    - Names may have multiple spellings/transliterations
    - Documentation may be missing or inconsistent
    - Biometric data may be available for some patients

    Args:
        patient: Patient profile to match
        all_patients: List of all patient profiles to search
        matching_config: Optional configuration for matching thresholds

    Returns:
        List of matches with confidence scores, sorted by score
    """
    # Default configuration
    config = {
        "min_score": 0.7,  # Minimum match score
        "name_weight": 0.3,
        "dob_weight": 0.3,
        "biometric_weight": 0.3,
        "location_weight": 0.1,
        "allow_year_offset": 2,  # Common in refugee populations
        "use_transliteration": True,
        "use_nicknames": True,
        "max_results": 10,
    }
    if matching_config:
        config.update(matching_config)

    matches = []

    def normalize_name(name: str) -> str:
        """Normalize name for comparison."""
        if not name:
            return ""
        # Remove accents
        name = (
            unicodedata.normalize("NFKD", name)
            .encode("ascii", "ignore")
            .decode("utf-8")
        )
        # Convert to lowercase and remove extra spaces
        name = re.sub(r"\s+", " ", name.lower().strip())
        return name

    def calculate_name_similarity(name1: str, name2: str) -> float:
        """Calculate name similarity with transliteration support."""
        # Normalize names
        norm1 = normalize_name(name1)
        norm2 = normalize_name(name2)

        # Direct comparison
        direct_score = SequenceMatcher(None, norm1, norm2).ratio()

        # Check individual name parts (handles different name orders)
        parts1 = set(norm1.split())
        parts2 = set(norm2.split())

        # Calculate Jaccard similarity for name parts
        intersection = len(parts1.intersection(parts2))
        union = len(parts1.union(parts2))
        part_score = intersection / union if union > 0 else 0

        # Combine scores
        return max(direct_score, part_score * 0.9)  # Slight penalty for part matching

    def calculate_dob_similarity(dob1: Any, dob2: Any, allow_offset: int) -> float:
        """Calculate date of birth similarity."""
        if not dob1 or not dob2:
            return 0.5  # Unknown DOB is neutral

        try:
            # Convert to date objects if needed
            if isinstance(dob1, str):
                dob1 = datetime.fromisoformat(dob1).date()
            if isinstance(dob2, str):
                dob2 = datetime.fromisoformat(dob2).date()

            # Exact match
            if dob1 == dob2:
                return 1.0

            # Calculate year difference
            year_diff = abs(dob1.year - dob2.year)

            # Within allowed offset (common for estimated birth dates)
            if year_diff <= allow_offset:
                # Same day and month but different year
                if dob1.day == dob2.day and dob1.month == dob2.month:
                    return float(0.9 - (year_diff * 0.1))
                # Different day/month but close year
                else:
                    return float(0.7 - (year_diff * 0.1))

            # Too far apart
            return 0.0

        except (ValueError, TypeError, AttributeError):
            return 0.5  # Error in date parsing

    def calculate_location_overlap(
        locations1: List[str], locations2: List[str]
    ) -> float:
        """Calculate overlap in location history."""
        if not locations1 or not locations2:
            return 0.5  # No location data is neutral

        # Normalize locations
        norm_loc1 = {normalize_name(loc) for loc in locations1 if loc}
        norm_loc2 = {normalize_name(loc) for loc in locations2 if loc}

        # Calculate Jaccard similarity
        if not norm_loc1 or not norm_loc2:
            return 0.5

        intersection = len(norm_loc1.intersection(norm_loc2))
        union = len(norm_loc1.union(norm_loc2))

        return intersection / union if union > 0 else 0

    def match_biometrics(bio1: Any, bio2: Any) -> float:
        """Match biometric data."""
        if not bio1 or not bio2:
            return 0.0  # No biometric data means no match

        # If both have biometric hashes, compare them
        if isinstance(bio1, str) and isinstance(bio2, str):
            return 1.0 if bio1 == bio2 else 0.0

        # In production, this would use specialized biometric matching
        # algorithms like NIST BOZORTH3 for fingerprints
        return 0.0

    # Extract patient data for matching
    patient_name = (
        f"{patient.get('given_name', '')} {patient.get('family_name', '')}".strip()
    )
    patient_dob = patient.get("date_of_birth")
    patient_biometrics = patient.get("biometric_data_hash")
    patient_locations = patient.get("location_history", [])

    # Match against each candidate
    for candidate in all_patients:
        # Skip self-matching
        if candidate.get("id") == patient.get("id"):
            continue

        score = 0.0
        match_reasons = []

        # Name matching
        candidate_name = f"{candidate.get('given_name', '')} {candidate.get('family_name', '')}".strip()
        name_score = calculate_name_similarity(patient_name, candidate_name)
        if name_score > 0.6:  # Significant name match
            score += name_score * config["name_weight"]
            match_reasons.append(f"Name match ({name_score:.0%})")

        # Date of birth matching
        candidate_dob = candidate.get("date_of_birth")
        dob_score = calculate_dob_similarity(
            patient_dob, candidate_dob, int(config["allow_year_offset"])
        )
        if dob_score > 0:
            score += dob_score * config["dob_weight"]
            match_reasons.append(f"DOB match ({dob_score:.0%})")

        # Biometric matching
        if patient_biometrics and candidate.get("biometric_data_hash"):
            bio_score = match_biometrics(
                patient_biometrics, candidate.get("biometric_data_hash")
            )
            if bio_score > 0:
                score += bio_score * config["biometric_weight"]
                match_reasons.append(f"Biometric match ({bio_score:.0%})")

        # Location history overlap
        candidate_locations = candidate.get("location_history", [])
        location_score = calculate_location_overlap(
            patient_locations, candidate_locations
        )
        if location_score > 0.5:
            score += location_score * config["location_weight"]
            match_reasons.append(f"Location overlap ({location_score:.0%})")

        # Only include matches above threshold
        if score >= config["min_score"]:
            matches.append(
                {
                    "patient_id": candidate.get("id"),
                    "patient_data": {
                        "name": candidate_name,
                        "date_of_birth": candidate_dob,
                        "gender": candidate.get("gender"),
                        "nationality": candidate.get("nationality"),
                    },
                    "confidence_score": min(score, 1.0),  # Cap at 100%
                    "match_reasons": match_reasons,
                    "match_components": {
                        "name_score": name_score,
                        "dob_score": dob_score,
                        "biometric_score": bio_score if patient_biometrics else None,
                        "location_score": location_score,
                    },
                }
            )

    # Sort by confidence score
    matches.sort(
        key=lambda x: cast(float, x.get("confidence_score", 0)),
        reverse=True,
    )

    # Return top matches
    return matches[: int(config["max_results"])]
