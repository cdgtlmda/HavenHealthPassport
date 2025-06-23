"""FHIR Terminology Service.

This module implements a comprehensive terminology service for the Haven Health Passport
FHIR server, supporting code validation, translation, and expansion of value sets.
"""

import json
import threading
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class FHIRTerminologyResource(BaseModel):
    """Base FHIR Terminology resource type."""

    resourceType: Literal["CodeSystem", "ValueSet", "ConceptMap", "NamingSystem"]


class TerminologySystem(str, Enum):
    """Supported terminology systems."""

    SNOMED_CT = "http://snomed.info/sct"
    ICD10 = "http://hl7.org/fhir/sid/icd-10"
    ICD10_CM = "http://hl7.org/fhir/sid/icd-10-cm"
    ICD10_PCS = "http://hl7.org/fhir/sid/icd-10-pcs"
    LOINC = "http://loinc.org"
    RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"
    CPT = "http://www.ama-assn.org/go/cpt"
    UCUM = "http://unitsofmeasure.org"
    CVX = "http://hl7.org/fhir/sid/cvx"
    NDC = "http://hl7.org/fhir/sid/ndc"
    HCPCS = "http://www.cms.gov/Medicare/Coding/HCPCSReleaseCodeSets"


class ConceptProperty(BaseModel):
    """Property of a terminology concept."""

    code: str
    value: Any
    type: str = "string"


class ConceptDesignation(BaseModel):
    """Alternative designation for a concept."""

    language: str
    use: Optional[Dict[str, str]] = None
    value: str


class Concept(BaseModel):
    """Terminology concept."""

    system: str
    code: str
    display: str
    definition: Optional[str] = None
    designations: List[ConceptDesignation] = Field(default_factory=list)
    properties: List[ConceptProperty] = Field(default_factory=list)
    parent_codes: List[str] = Field(default_factory=list)
    child_codes: List[str] = Field(default_factory=list)
    inactive: bool = False


class ValueSetCompose(BaseModel):
    """Value set composition."""

    include: List[Dict[str, Any]] = Field(default_factory=list)
    exclude: List[Dict[str, Any]] = Field(default_factory=list)


class ValueSet(BaseModel):
    """FHIR ValueSet resource."""

    resourceType: Literal["ValueSet"] = "ValueSet"
    id: str
    url: str
    version: Optional[str] = None
    name: str
    title: Optional[str] = None
    status: str = "active"
    description: Optional[str] = None
    compose: ValueSetCompose
    expansion: Optional[Dict[str, Any]] = None


class CodeSystemProperty(BaseModel):
    """Code system property definition."""

    code: str
    uri: Optional[str] = None
    description: Optional[str] = None
    type: str  # code, string, integer, boolean, dateTime, decimal


class CodeSystem(BaseModel):
    """FHIR CodeSystem resource."""

    resourceType: Literal["CodeSystem"] = "CodeSystem"
    id: str
    url: str
    version: Optional[str] = None
    name: str
    title: Optional[str] = None
    status: str = "active"
    content: str = "complete"  # complete, not-present, example, fragment, supplement
    count: Optional[int] = None
    property: List[CodeSystemProperty] = Field(default_factory=list)
    concepts: List[Concept] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """Result of code validation."""

    valid: bool
    message: Optional[str] = None
    display: Optional[str] = None
    system: Optional[str] = None
    version: Optional[str] = None
    issues: List[str] = Field(default_factory=list)


class ExpansionResult(BaseModel):
    """Result of value set expansion."""

    total: int
    offset: int = 0
    contains: List[Dict[str, Any]] = Field(default_factory=list)
    parameter: List[Dict[str, Any]] = Field(default_factory=list)


class TranslationResult(BaseModel):
    """Result of code translation."""

    match: bool
    translations: List[Dict[str, Any]] = Field(default_factory=list)


class SubsumptionResult(BaseModel):
    """Result of subsumption testing."""

    outcome: str  # equivalent, subsumes, subsumed-by, not-subsumed


class LookupResult(BaseModel):
    """Result of code lookup."""

    name: str
    display: str
    definition: Optional[str] = None
    designations: List[ConceptDesignation] = Field(default_factory=list)
    properties: List[ConceptProperty] = Field(default_factory=list)


class TerminologyService:
    """Main terminology service implementation.

    Provides code validation, value set expansion, and concept mapping.
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        kms_key_id: Optional[str] = None,
        region: str = "us-east-1",
    ):
        """Initialize terminology service.

        Args:
            data_dir: Directory containing terminology data files
            kms_key_id: KMS key ID for encryption
            region: AWS region
        """
        self.kms_key_id = kms_key_id or "alias/haven-health-key"
        self.region = region
        self._encryption_service = EncryptionService(self.kms_key_id, self.region)
        self.data_dir = data_dir or Path("data/terminology")
        self.code_systems: Dict[str, CodeSystem] = {}
        self.value_sets: Dict[str, ValueSet] = {}
        self.concept_maps: Dict[str, Dict[str, Any]] = {}
        self._concept_cache: Dict[str, Concept] = {}
        self._expansion_cache: Dict[str, ExpansionResult] = {}
        self._initialize_standard_systems()

    def _initialize_standard_systems(self) -> None:
        """Initialize standard terminology systems."""
        # Initialize standard code systems
        self._init_ucum()
        self._init_basic_codes()
        logger.info("Initialized standard terminology systems")

    def _init_ucum(self) -> None:
        """Initialize UCUM units of measure."""
        ucum = CodeSystem(
            id="ucum",
            url=TerminologySystem.UCUM.value,
            name="UCUM",
            title="Unified Code for Units of Measure",
            content="fragment",
            property=[
                CodeSystemProperty(
                    code="unit", type="string", description="Unit symbol"
                )
            ],
        )
        # Add common units
        common_units = [
            ("mg", "milligram", "mass"),
            ("g", "gram", "mass"),
            ("kg", "kilogram", "mass"),
            ("mL", "milliliter", "volume"),
            ("L", "liter", "volume"),
            ("/d", "per day", "frequency"),
            ("/h", "per hour", "frequency"),
            ("mm[Hg]", "millimeter of mercury", "pressure"),
            ("cel", "degree Celsius", "temperature"),
            ("%", "percent", "percentage"),
        ]
        for code, display, category in common_units:
            ucum.concepts.append(
                Concept(
                    system=ucum.url,
                    code=code,
                    display=display,
                    properties=[ConceptProperty(code="category", value=category)],
                )
            )
        self.code_systems[ucum.url] = ucum

    def _init_basic_codes(self) -> None:
        """Initialize basic FHIR code systems."""
        # Administrative Gender
        gender_cs = CodeSystem(
            id="administrative-gender",
            url="http://hl7.org/fhir/administrative-gender",
            name="AdministrativeGender",
            title="Administrative Gender",
            content="complete",
        )
        gender_cs.concepts = [
            Concept(system=gender_cs.url, code="male", display="Male"),
            Concept(system=gender_cs.url, code="female", display="Female"),
            Concept(system=gender_cs.url, code="other", display="Other"),
            Concept(system=gender_cs.url, code="unknown", display="Unknown"),
        ]
        self.code_systems[gender_cs.url] = gender_cs

    def validate_code(
        self,
        system: str,
        code: str,
        version: Optional[str] = None,
        display: Optional[str] = None,
    ) -> ValidationResult:
        """Validate a code against a code system.

        Args:
            system: Code system URI
            code: Code to validate
            version: Code system version
            display: Display text to validate

        Returns:
            Validation result
        """
        result = ValidationResult(valid=False, issues=[])

        # Check if system is supported
        if system not in self.code_systems:
            result.message = f"Code system {system} not supported"
            result.issues = ["unknown-system"]
            return result

        code_system = self.code_systems[system]
        result.system = system
        result.version = version or code_system.version

        # Find concept
        concept = self._find_concept(code_system, code)
        if not concept:
            result.message = f"Code '{code}' not found in {system}"
            result.issues = ["invalid-code"]
            return result

        # Check if concept is active
        if concept.inactive:
            result.issues = ["inactive-code"]
            result.message = f"Code '{code}' is inactive"

        result.valid = True
        result.display = concept.display

        # Validate display if provided
        if display and display != concept.display:
            # Check designations
            valid_display = False
            for designation in concept.designations:
                if designation.value == display:
                    valid_display = True
                    break
            if not valid_display:
                if result.issues:
                    result.issues = result.issues + ["invalid-display"]
                else:
                    result.issues = ["invalid-display"]
                result.message = f"Display '{display}' does not match"

        return result

    def expand_value_set(
        self,
        value_set_url: str,
        filter_text: Optional[str] = None,
        offset: int = 0,
        count: int = 100,
    ) -> ExpansionResult:
        """Expand a value set.

        Args:
            value_set_url: URL of the value set
            filter_text: Text filter for expansion
            offset: Pagination offset
            count: Number of codes to return

        Returns:
            Expansion result
        """
        # Check cache
        cache_key = f"{value_set_url}:{filter_text}:{offset}:{count}"
        if cache_key in self._expansion_cache:
            return self._expansion_cache[cache_key]

        result = ExpansionResult(total=0, offset=offset)

        # Get value set
        if value_set_url not in self.value_sets:
            logger.warning(f"Value set {value_set_url} not found")
            return result

        value_set = self.value_sets[value_set_url]
        all_codes = []

        # Process includes
        for include in value_set.compose.include:
            system = include.get("system")
            if system and system in self.code_systems:
                code_system = self.code_systems[system]

                # Get all codes or specific codes
                if "concept" in include:
                    # Specific codes listed
                    for concept_ref in include["concept"]:
                        concept = self._find_concept(code_system, concept_ref["code"])
                        if concept and not concept.inactive:
                            all_codes.append(concept)
                else:
                    # All codes from system
                    for concept in code_system.concepts:
                        if not concept.inactive:
                            all_codes.append(concept)

        # Apply filter if provided
        if filter_text:
            filter_lower = filter_text.lower()
            all_codes = [
                c
                for c in all_codes
                if filter_lower in c.code.lower() or filter_lower in c.display.lower()
            ]

        # Process excludes
        for exclude in value_set.compose.exclude:
            system = exclude.get("system")
            if system and "concept" in exclude:
                for concept_ref in exclude["concept"]:
                    all_codes = [
                        c
                        for c in all_codes
                        if not (c.system == system and c.code == concept_ref["code"])
                    ]

        # Apply pagination
        result.total = len(all_codes)
        paginated_codes = all_codes[offset : offset + count]

        # Build expansion
        contains_list = []
        for concept in paginated_codes:
            contains_list.append(
                {
                    "system": concept.system,
                    "code": concept.code,
                    "display": concept.display,
                }
            )
        result.contains = contains_list

        # Cache result
        self._expansion_cache[cache_key] = result
        return result

    def lookup_code(
        self, system: str, code: str, _version: Optional[str] = None
    ) -> Optional[LookupResult]:
        """Look up details for a code.

        Args:
            system: Code system URI
            code: Code to look up
            version: Code system version

        Returns:
            Lookup result or None if not found
        """
        if system not in self.code_systems:
            return None

        code_system = self.code_systems[system]
        concept = self._find_concept(code_system, code)

        if not concept:
            return None

        return LookupResult(
            name=code_system.name,
            display=concept.display,
            definition=concept.definition,
            designations=concept.designations,
            properties=concept.properties,
        )

    def test_subsumption(
        self, system: str, code_a: str, code_b: str, _version: Optional[str] = None
    ) -> SubsumptionResult:
        """Test subsumption relationship between codes.

        Args:
            system: Code system URI
            code_a: First code
            code_b: Second code
            version: Code system version

        Returns:
            Subsumption result
        """
        if system not in self.code_systems:
            return SubsumptionResult(outcome="not-subsumed")

        code_system = self.code_systems[system]
        concept_a = self._find_concept(code_system, code_a)
        concept_b = self._find_concept(code_system, code_b)

        if not concept_a or not concept_b:
            return SubsumptionResult(outcome="not-subsumed")

        # Check if codes are equivalent
        if code_a == code_b:
            return SubsumptionResult(outcome="equivalent")

        # Check parent-child relationships
        if code_b in concept_a.parent_codes:
            return SubsumptionResult(outcome="subsumed-by")
        elif code_b in concept_a.child_codes:
            return SubsumptionResult(outcome="subsumes")

        # Check transitive relationships
        if self._is_ancestor(code_system, code_a, code_b):
            return SubsumptionResult(outcome="subsumed-by")
        elif self._is_ancestor(code_system, code_b, code_a):
            return SubsumptionResult(outcome="subsumes")

        return SubsumptionResult(outcome="not-subsumed")

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("load_code_system")
    def load_code_system(self, file_path: Path) -> None:
        """Load a code system from file.

        Args:
            file_path: Path to code system JSON file
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            code_system = CodeSystem(**data)
            self.code_systems[code_system.url] = code_system

            # Index concepts for faster lookup
            for concept in code_system.concepts:
                cache_key = f"{code_system.url}:{concept.code}"
                self._concept_cache[cache_key] = concept

            logger.info(f"Loaded code system: {code_system.name}")

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to load code system from {file_path}: {e}")

    @require_phi_access(AccessLevel.READ)
    @audit_phi_access("load_value_set")
    def load_value_set(self, file_path: Path) -> None:
        """Load a value set from file.

        Args:
            file_path: Path to value set JSON file
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            value_set = ValueSet(**data)
            self.value_sets[value_set.url] = value_set

            logger.info(f"Loaded value set: {value_set.name}")

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to load value set from {file_path}: {e}")

    def _find_concept(self, code_system: CodeSystem, code: str) -> Optional[Concept]:
        """Find a concept in a code system.

        Args:
            code_system: Code system to search
            code: Code to find

        Returns:
            Concept or None if not found
        """
        cache_key = f"{code_system.url}:{code}"
        if cache_key in self._concept_cache:
            return self._concept_cache[cache_key]

        for concept in code_system.concepts:
            if concept.code == code:
                self._concept_cache[cache_key] = concept
                return concept

        return None

    def _is_ancestor(
        self, code_system: CodeSystem, descendant_code: str, ancestor_code: str
    ) -> bool:
        """Check if ancestor_code is an ancestor of descendant_code.

        Args:
            code_system: Code system
            descendant_code: Potential descendant
            ancestor_code: Potential ancestor

        Returns:
            True if ancestor relationship exists
        """
        concept = self._find_concept(code_system, descendant_code)
        if not concept:
            return False

        # Check immediate parents
        if ancestor_code in concept.parent_codes:
            return True

        # Check transitive parents
        for parent_code in concept.parent_codes:
            if self._is_ancestor(code_system, parent_code, ancestor_code):
                return True

        return False

    def add_code_system(self, code_system: CodeSystem) -> None:
        """Add a code system to the service.

        Args:
            code_system: Code system to add
        """
        self.code_systems[code_system.url] = code_system
        logger.info(f"Added code system: {code_system.name}")

    def add_value_set(self, value_set: ValueSet) -> None:
        """Add a value set to the service.

        Args:
            value_set: Value set to add
        """
        self.value_sets[value_set.url] = value_set
        logger.info(f"Added value set: {value_set.name}")

    def get_supported_systems(self) -> List[str]:
        """Get list of supported code systems.

        Returns:
            List of code system URIs
        """
        return list(self.code_systems.keys())

    def get_supported_value_sets(self) -> List[str]:
        """Get list of supported value sets.

        Returns:
            List of value set URLs
        """
        return list(self.value_sets.keys())

    async def map_code(
        self, source_code: str, source_system: str, target_system: str
    ) -> Optional[Dict[str, Any]]:
        """Map a code from one system to another.

        Args:
            source_code: The code to map
            source_system: The source code system URI
            target_system: The target code system URI

        Returns:
            Dictionary with mapping information or None if no mapping found
        """
        # Check if we have a concept map for this translation
        map_key = f"{source_system}|{target_system}"

        if map_key in self.concept_maps:
            concept_map = self.concept_maps[map_key]
            # Look for the source code in the mappings
            for group in concept_map.get("group", []):
                if group.get("source") == source_system:
                    for element in group.get("element", []):
                        if element.get("code") == source_code:
                            # Found a mapping
                            targets = element.get("target", [])
                            if targets:
                                target = targets[0]  # Use first mapping
                                return {
                                    "code": target.get("code"),
                                    "display": target.get("display"),
                                    "system": target_system,
                                    "equivalence": target.get(
                                        "equivalence", "equivalent"
                                    ),
                                }

        # No direct mapping found
        return None


# Singleton instance
# Thread-safe singleton pattern


class _TerminologyServiceSingleton:
    """Thread-safe singleton holder for TerminologyService."""

    _instance: Optional[TerminologyService] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> TerminologyService:
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = TerminologyService()
        return cls._instance


def get_terminology_service() -> TerminologyService:
    """Get singleton terminology service instance."""
    return _TerminologyServiceSingleton.get_instance()
