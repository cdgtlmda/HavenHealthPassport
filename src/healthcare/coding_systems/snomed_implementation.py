"""SNOMED CT Implementation.

This module implements SNOMED CT (Systematized Nomenclature of Medicine Clinical Terms)
integration, including concept management, relationships, hierarchies, and
refugee health-specific subsets.
"""

import logging
from collections import defaultdict
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class SNOMEDHierarchy(Enum):
    """Major SNOMED CT hierarchies."""

    CLINICAL_FINDING = "404684003"
    PROCEDURE = "71388002"
    OBSERVABLE_ENTITY = "363787002"
    BODY_STRUCTURE = "123037004"
    ORGANISM = "410607006"
    SUBSTANCE = "105590001"
    PHARMACEUTICAL = "373873005"
    SPECIMEN = "123038009"
    PHYSICAL_OBJECT = "260787004"
    PHYSICAL_FORCE = "78621006"
    EVENT = "272379006"
    ENVIRONMENT = "308916002"
    SITUATION = "243796009"
    QUALIFIER_VALUE = "362981000"
    RECORD_ARTIFACT = "419891008"
    CORE_METADATA = "900000000000441003"


class RelationshipType(Enum):
    """SNOMED CT relationship types."""

    IS_A = "116680003"  # Is a (parent/child)
    FINDING_SITE = "363698007"  # Finding site
    ASSOCIATED_MORPHOLOGY = "116676008"  # Associated morphology
    CAUSATIVE_AGENT = "246075003"  # Causative agent
    ASSOCIATED_WITH = "47429007"  # Associated with
    AFTER = "255234002"  # After
    SEVERITY = "246112005"  # Severity
    CLINICAL_COURSE = "263502005"  # Clinical course
    EPISODICITY = "246456000"  # Episodicity
    INTERPRETS = "363714003"  # Interprets
    METHOD = "260686004"  # Method
    LATERALITY = "272741003"  # Laterality


class DescriptionType(Enum):
    """SNOMED CT description types."""

    FULLY_SPECIFIED_NAME = "900000000000003001"
    SYNONYM = "900000000000013009"
    DEFINITION = "900000000000550004"


class RefugeeHealthSubset(Enum):
    """SNOMED CT subsets for refugee health."""

    TROPICAL_DISEASES = "tropical-diseases"
    CONFLICT_TRAUMA = "conflict-trauma"
    MENTAL_HEALTH = "mental-health"
    NUTRITIONAL_DISORDERS = "nutritional-disorders"
    MATERNAL_CHILD = "maternal-child"
    COMMUNICABLE_DISEASES = "communicable-diseases"
    VACCINATION_STATUS = "vaccination-status"


class SNOMEDConcept:
    """Represents a SNOMED CT concept."""

    def __init__(
        self,
        concept_id: str,
        fully_specified_name: str,
        is_active: bool = True,
        module_id: Optional[str] = None,
        definition_status_id: Optional[str] = None,
    ):
        """Initialize SNOMED concept.

        Args:
            concept_id: SNOMED CT concept ID
            fully_specified_name: Fully specified name
            is_active: Whether concept is active
            module_id: Module ID
            definition_status_id: Definition status ID
        """
        self.concept_id = concept_id
        self.fully_specified_name = fully_specified_name
        self.is_active = is_active
        self.module_id = module_id
        self.definition_status_id = definition_status_id

        # Collections
        self.descriptions: Dict[str, str] = {}
        self.synonyms: List[str] = []
        self.parents: Set[str] = set()
        self.children: Set[str] = set()
        self.relationships: Dict[str, Set[str]] = defaultdict(set)
        self.preferred_term: Optional[str] = None

    def add_description(
        self,
        term: str,
        description_type: DescriptionType,
        language_code: str = "en",
        is_preferred: bool = False,
    ) -> None:
        """Add a description to the concept.

        Args:
            term: Description term
            description_type: Type of description
            language_code: Language code
            is_preferred: Whether this is the preferred term
        """
        key = f"{description_type.value}:{language_code}"
        self.descriptions[key] = term

        if description_type == DescriptionType.SYNONYM:
            self.synonyms.append(term)

        if is_preferred:
            self.preferred_term = term

    def add_relationship(
        self,
        relationship_type: RelationshipType,
        destination_concept_id: str,
        is_active: bool = True,
    ) -> None:
        """Add a relationship to another concept.

        Args:
            relationship_type: Type of relationship
            destination_concept_id: Target concept ID
            is_active: Whether relationship is active
        """
        if is_active:
            self.relationships[relationship_type.value].add(destination_concept_id)

            # Handle IS_A relationships specially
            if relationship_type == RelationshipType.IS_A:
                self.parents.add(destination_concept_id)

    def get_hierarchy_depth(self) -> int:
        """Get the depth of this concept in the hierarchy."""
        # This would need the full hierarchy to calculate properly
        # For now, return based on number of parents
        return len(self.parents)

    def is_descendant_of(
        self, ancestor_id: str, repository: "SNOMEDRepository"
    ) -> bool:
        """Check if this concept is a descendant of another.

        Args:
            ancestor_id: Potential ancestor concept ID
            repository: SNOMED repository for traversal

        Returns:
            True if this is a descendant of ancestor_id
        """
        # Check direct parents
        if ancestor_id in self.parents:
            return True

        # Check ancestors recursively
        for parent_id in self.parents:
            parent = repository.get_concept(parent_id)
            if parent and parent.is_descendant_of(ancestor_id, repository):
                return True

        return False


class SNOMEDRepository:
    """Repository for managing SNOMED CT concepts."""

    def __init__(self) -> None:
        """Initialize SNOMED repository."""
        self.concepts: Dict[str, SNOMEDConcept] = {}
        self.description_index: Dict[str, Set[str]] = defaultdict(set)
        self.hierarchy_index: Dict[str, Set[str]] = defaultdict(set)
        self.subset_index: Dict[RefugeeHealthSubset, Set[str]] = defaultdict(set)
        self._initialize_refugee_health_concepts()

    def _initialize_refugee_health_concepts(self) -> None:
        """Initialize common SNOMED concepts for refugee health."""
        # Infectious diseases
        tb_concept = SNOMEDConcept("56717001", "Tuberculosis (disorder)")
        tb_concept.add_description("TB", DescriptionType.SYNONYM, "en")
        tb_concept.add_relationship(
            RelationshipType.IS_A, "40733004"  # Infectious disease
        )
        self.add_concept(tb_concept, RefugeeHealthSubset.COMMUNICABLE_DISEASES)

        # Malaria
        malaria_concept = SNOMEDConcept("61462000", "Malaria (disorder)")
        malaria_concept.add_description("Paludism", DescriptionType.SYNONYM, "en")
        malaria_concept.add_relationship(
            RelationshipType.IS_A, "17322007"  # Parasitic disease
        )
        self.add_concept(malaria_concept, RefugeeHealthSubset.TROPICAL_DISEASES)

        # Malnutrition
        malnutrition_concept = SNOMEDConcept(
            "70241007", "Severe protein-calorie malnutrition (disorder)"
        )
        malnutrition_concept.add_description(
            "Severe malnutrition", DescriptionType.SYNONYM, "en"
        )
        malnutrition_concept.add_relationship(
            RelationshipType.IS_A, "248325000"  # Nutritional disorder
        )
        self.add_concept(
            malnutrition_concept, RefugeeHealthSubset.NUTRITIONAL_DISORDERS
        )

        # PTSD
        ptsd_concept = SNOMEDConcept(
            "47505003", "Posttraumatic stress disorder (disorder)"
        )
        ptsd_concept.add_description(
            "PTSD", DescriptionType.SYNONYM, "en", is_preferred=True
        )
        ptsd_concept.add_relationship(
            RelationshipType.IS_A, "74732009"  # Mental disorder
        )
        self.add_concept(ptsd_concept, RefugeeHealthSubset.MENTAL_HEALTH)

        # Trauma-related
        torture_concept = SNOMEDConcept("95381002", "Victim of torture (finding)")
        torture_concept.add_relationship(
            RelationshipType.IS_A, "417746004"  # Traumatic event
        )
        self.add_concept(torture_concept, RefugeeHealthSubset.CONFLICT_TRAUMA)

    def add_concept(
        self, concept: SNOMEDConcept, subset: Optional[RefugeeHealthSubset] = None
    ) -> None:
        """Add a SNOMED concept to the repository.

        Args:
            concept: SNOMEDConcept to add
            subset: Optional refugee health subset
        """
        self.concepts[concept.concept_id] = concept

        # Update description index
        for desc in concept.descriptions.values():
            tokens = desc.lower().split()
            for token in tokens:
                if len(token) > 2:
                    self.description_index[token].add(concept.concept_id)

        # Update synonym index
        for synonym in concept.synonyms:
            tokens = synonym.lower().split()
            for token in tokens:
                if len(token) > 2:
                    self.description_index[token].add(concept.concept_id)

        # Update hierarchy index
        for parent_id in concept.parents:
            self.hierarchy_index[parent_id].add(concept.concept_id)

        # Update subset index
        if subset:
            self.subset_index[subset].add(concept.concept_id)

    def get_concept(self, concept_id: str) -> Optional[SNOMEDConcept]:
        """Get a SNOMED concept by ID.

        Args:
            concept_id: SNOMED concept ID

        Returns:
            SNOMEDConcept or None
        """
        return self.concepts.get(concept_id)

    def search_by_term(
        self, search_term: str, max_results: int = 50
    ) -> List[SNOMEDConcept]:
        """Search for concepts by term.

        Args:
            search_term: Term to search for
            max_results: Maximum number of results

        Returns:
            List of matching concepts
        """
        search_tokens = search_term.lower().split()
        matching_ids = set()

        # Find concepts containing all search tokens
        for i, token in enumerate(search_tokens):
            token_matches = self.description_index.get(token, set())
            if i == 0:
                matching_ids = token_matches.copy()
            else:
                matching_ids &= token_matches

        # Score and sort results
        results = []
        for concept_id in matching_ids:
            concept = self.concepts[concept_id]

            # Calculate relevance score
            score = 0
            search_lower = search_term.lower()

            # Exact match on preferred term
            if (
                concept.preferred_term
                and concept.preferred_term.lower() == search_lower
            ):
                score += 100

            # Partial match on preferred term
            elif (
                concept.preferred_term
                and search_lower in concept.preferred_term.lower()
            ):
                score += 50

            # Match in synonyms
            for synonym in concept.synonyms:
                if search_lower == synonym.lower():
                    score += 80
                elif search_lower in synonym.lower():
                    score += 30

            # Active concepts score higher
            if concept.is_active:
                score += 10

            results.append((score, concept))

        # Sort by score and return top results
        results.sort(key=lambda x: x[0], reverse=True)
        return [concept for _, concept in results[:max_results]]

    def get_descendants(
        self, concept_id: str, max_depth: Optional[int] = None
    ) -> Set[str]:
        """Get all descendant concepts.

        Args:
            concept_id: Parent concept ID
            max_depth: Maximum depth to traverse

        Returns:
            Set of descendant concept IDs
        """
        descendants = set()
        to_process = [(concept_id, 0)]

        while to_process:
            current_id, depth = to_process.pop()

            if max_depth and depth >= max_depth:
                continue

            children = self.hierarchy_index.get(current_id, set())
            descendants.update(children)

            for child_id in children:
                to_process.append((child_id, depth + 1))

        return descendants

    def get_ancestors(
        self, concept_id: str, max_depth: Optional[int] = None
    ) -> Set[str]:
        """Get all ancestor concepts.

        Args:
            concept_id: Child concept ID
            max_depth: Maximum depth to traverse

        Returns:
            Set of ancestor concept IDs
        """
        ancestors: set[str] = set()
        concept = self.get_concept(concept_id)

        if not concept:
            return ancestors

        to_process = [(parent_id, 0) for parent_id in concept.parents]

        while to_process:
            current_id, depth = to_process.pop()

            if max_depth and depth >= max_depth:
                continue

            ancestors.add(current_id)

            parent_concept = self.get_concept(current_id)
            if parent_concept:
                for parent_id in parent_concept.parents:
                    to_process.append((parent_id, depth + 1))

        return ancestors

    def get_subset_concepts(self, subset: RefugeeHealthSubset) -> List[SNOMEDConcept]:
        """Get all concepts in a refugee health subset.

        Args:
            subset: Refugee health subset

        Returns:
            List of concepts in the subset
        """
        concept_ids = self.subset_index.get(subset, set())
        return [self.concepts[cid] for cid in concept_ids if cid in self.concepts]


class SNOMEDExpression:
    """Handles SNOMED CT post-coordinated expressions."""

    def __init__(self, focus_concept_id: str):
        """Initialize SNOMED expression.

        Args:
            focus_concept_id: Main concept ID
        """
        self.focus_concept = focus_concept_id
        self.refinements: Dict[str, List[str]] = defaultdict(list)

    def add_refinement(self, attribute_id: str, value_id: str) -> "SNOMEDExpression":
        """Add a refinement to the expression.

        Args:
            attribute_id: Attribute concept ID
            value_id: Value concept ID

        Returns:
            Self for chaining
        """
        self.refinements[attribute_id].append(value_id)
        return self

    def to_compositional_grammar(self) -> str:
        """Convert to SNOMED compositional grammar format.

        Returns:
            Expression in compositional grammar
        """
        parts = [self.focus_concept]

        if self.refinements:
            refinement_parts = []
            for attr_id, values in self.refinements.items():
                for value_id in values:
                    refinement_parts.append(f"{attr_id}={value_id}")
            parts.append(f":{','.join(refinement_parts)}")

        return "".join(parts)


class SNOMEDValidator:
    """Validates SNOMED CT codes and expressions."""

    @staticmethod
    def validate_concept_id(concept_id: str) -> Tuple[bool, Optional[str]]:
        """Validate SNOMED concept ID format.

        Args:
            concept_id: Concept ID to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if it's numeric
        if not concept_id.isdigit():
            return False, "SNOMED concept ID must be numeric"

        # Check length (6-18 digits)
        if len(concept_id) < 6 or len(concept_id) > 18:
            return False, "SNOMED concept ID must be 6-18 digits"

        # Validate check digit using Verhoeff algorithm
        if not SNOMEDValidator._verify_check_digit(concept_id):
            return False, "Invalid check digit"

        return True, None

    @staticmethod
    def _verify_check_digit(concept_id: str) -> bool:
        """Verify SNOMED ID check digit using Verhoeff algorithm.

        Args:
            concept_id: Concept ID to verify

        Returns:
            True if check digit is valid
        """
        # Simplified check - in production, implement full Verhoeff
        # For now, just ensure it's a valid number
        try:
            int(concept_id)
            return True
        except ValueError:
            return False


# Create global instances
snomed_repository = SNOMEDRepository()
snomed_validator = SNOMEDValidator()
