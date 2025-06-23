# pylint: disable=too-many-lines
"""RxNorm Mapping System.

Comprehensive RxNorm drug terminology mapping for Haven Health Passport.

Features:
- Drug name normalization
- Brand to generic mapping
- Ingredient extraction
- Dose form and strength parsing
- Drug interaction checking
- Multi-source drug mapping (NDC, SNOMED, etc.)
- Prescription sig parsing
"""

import asyncio
import json
import logging
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# For fuzzy matching
try:
    from fuzzywuzzy import fuzz, process

    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False

# For unit conversion
try:
    import pint

    UNIT_CONVERSION_AVAILABLE = True
except ImportError:
    UNIT_CONVERSION_AVAILABLE = False


class TermType(Enum):
    """RxNorm term types (TTY)."""

    IN = "Ingredient"
    PIN = "Precise Ingredient"
    MIN = "Multiple Ingredients"
    BN = "Brand Name"
    SBD = "Semantic Branded Drug"
    SBDC = "Semantic Branded Drug Component"
    SBDF = "Semantic Branded Dose Form"
    SCD = "Semantic Clinical Drug"
    SCDC = "Semantic Clinical Drug Component"
    SCDF = "Semantic Clinical Dose Form"
    BPCK = "Brand Name Pack"
    GPCK = "Generic Pack"
    DF = "Dose Form"
    DFG = "Dose Form Group"


class RelationshipType(Enum):
    """RxNorm relationship types."""

    HAS_INGREDIENT = "has_ingredient"
    HAS_BRAND_NAME = "has_brand_name"
    HAS_DOSE_FORM = "has_dose_form"
    HAS_TRADENAME = "has_tradename"
    CONSISTS_OF = "consists_of"
    CONTAINS = "contains"
    INGREDIENT_OF = "ingredient_of"
    BRAND_NAME_OF = "brand_name_of"
    DOSE_FORM_OF = "dose_form_of"
    TRADENAME_OF = "tradename_of"
    HAS_STRENGTH = "has_strength"
    MAY_TREAT = "may_treat"
    MAY_PREVENT = "may_prevent"
    CI_WITH = "contraindicated_with"
    MAY_DIAGNOSE = "may_diagnose"


class DrugStatus(Enum):
    """Drug availability status."""

    ACTIVE = "active"
    OBSOLETE = "obsolete"
    RETIRED = "retired"
    NEVER_ACTIVE = "never_active"


@dataclass
class RxNormConcept:
    """Represents an RxNorm concept."""

    rxcui: str  # RxNorm Concept Unique Identifier
    name: str
    tty: TermType
    language: str = "ENG"
    suppress: bool = False
    status: DrugStatus = DrugStatus.ACTIVE
    synonyms: List[str] = field(default_factory=list)

    # Relationships
    ingredients: List[str] = field(default_factory=list)
    strength: Optional[str] = None
    dose_form: Optional[str] = None
    brand_names: List[str] = field(default_factory=list)
    generic_name: Optional[str] = None

    # Additional attributes
    atc_codes: List[str] = field(default_factory=list)
    ndc_codes: List[str] = field(default_factory=list)
    snomed_codes: List[str] = field(default_factory=list)
    umls_cui: Optional[str] = None

    # Clinical attributes
    route: Optional[str] = None
    schedule: Optional[str] = None  # DEA schedule
    prescribable: bool = True
    human_drug: bool = True

    def is_ingredient(self) -> bool:
        """Check if this is an ingredient concept."""
        return self.tty in [TermType.IN, TermType.PIN, TermType.MIN]

    def is_brand(self) -> bool:
        """Check if this is a brand name concept."""
        return self.tty in [
            TermType.BN,
            TermType.SBD,
            TermType.SBDC,
            TermType.SBDF,
            TermType.BPCK,
        ]

    def is_clinical_drug(self) -> bool:
        """Check if this is a clinical drug concept."""
        return self.tty in [TermType.SCD, TermType.SCDC, TermType.SCDF, TermType.GPCK]

    def get_display_name(self) -> str:
        """Get display name with strength and form."""
        parts = [self.name]
        if self.strength:
            parts.append(self.strength)
        if self.dose_form:
            parts.append(self.dose_form)
        return " ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "rxcui": self.rxcui,
            "name": self.name,
            "tty": self.tty.name,
            "language": self.language,
            "suppress": self.suppress,
            "status": self.status.value,
            "synonyms": self.synonyms,
            "ingredients": self.ingredients,
            "strength": self.strength,
            "dose_form": self.dose_form,
            "brand_names": self.brand_names,
            "generic_name": self.generic_name,
            "atc_codes": self.atc_codes,
            "ndc_codes": self.ndc_codes,
            "snomed_codes": self.snomed_codes,
            "umls_cui": self.umls_cui,
            "route": self.route,
            "schedule": self.schedule,
            "prescribable": self.prescribable,
            "human_drug": self.human_drug,
        }


@dataclass
class RxNormSearchResult:
    """Search result for RxNorm queries."""

    query: str
    concepts: List[RxNormConcept]
    total_matches: int
    processing_time: float
    search_metadata: Dict[str, Any] = field(default_factory=dict)
    approximate_match: bool = False


@dataclass
class DrugInteraction:
    """Represents a drug-drug interaction."""

    drug1_rxcui: str
    drug1_name: str
    drug2_rxcui: str
    drug2_name: str
    severity: str  # high, moderate, low
    description: str
    mechanism: Optional[str] = None
    management: Optional[str] = None
    documentation_level: Optional[str] = None
    sources: List[str] = field(default_factory=list)


@dataclass
class PrescriptionSig:
    """Parsed prescription signature."""

    drug_name: str
    rxcui: Optional[str] = None
    dose: Optional[float] = None
    dose_unit: Optional[str] = None
    route: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    prn: bool = False
    instructions: Optional[str] = None
    parsed_components: Dict[str, Any] = field(default_factory=dict)


class RxNormMapper:
    """Comprehensive RxNorm drug mapping system."""

    def __init__(
        self,
        data_path: Optional[str] = None,
        enable_fuzzy_matching: bool = True,
        enable_unit_conversion: bool = True,
        min_confidence: float = 0.7,
        max_results: int = 20,
        include_obsolete: bool = False,
        check_interactions: bool = True,
    ):
        """Initialize RxNorm mapper.

        Args:
            data_path: Path to RxNorm data files
            enable_fuzzy_matching: Enable fuzzy string matching
            enable_unit_conversion: Enable dose unit conversion
            min_confidence: Minimum confidence threshold
            max_results: Maximum number of results
            cache_size: Size of LRU cache
            include_obsolete: Include obsolete drugs in results
            check_interactions: Enable interaction checking
        """
        self.logger = logging.getLogger(__name__)
        self.data_path = Path(
            data_path
            or "/Users/cadenceapeiron/Documents/HavenHealthPassport/data/terminologies/rxnorm"
        )
        self.enable_fuzzy_matching = enable_fuzzy_matching and FUZZY_AVAILABLE
        self.enable_unit_conversion = (
            enable_unit_conversion and UNIT_CONVERSION_AVAILABLE
        )
        self.min_confidence = min_confidence
        self.max_results = max_results
        self.include_obsolete = include_obsolete
        self.check_interactions = check_interactions

        # Initialize unit registry if available
        self.ureg = None
        if self.enable_unit_conversion:
            self.ureg = pint.UnitRegistry()
            self._setup_medical_units()

        # Data structures
        self.concepts: Dict[str, RxNormConcept] = {}
        self.name_index: Dict[str, List[str]] = defaultdict(list)
        self.ingredient_index: Dict[str, List[str]] = defaultdict(list)
        self.brand_index: Dict[str, List[str]] = defaultdict(list)
        self.ndc_to_rxcui: Dict[str, str] = {}
        self.atc_to_rxcui: Dict[str, List[str]] = defaultdict(list)
        self.interactions: Dict[str, List[DrugInteraction]] = defaultdict(list)
        # Route mappings
        self.route_mappings = {
            "po": "oral",
            "by mouth": "oral",
            "orally": "oral",
            "iv": "intravenous",
            "ivpb": "intravenous piggyback",
            "im": "intramuscular",
            "sq": "subcutaneous",
            "subq": "subcutaneous",
            "sl": "sublingual",
            "pr": "rectal",
            "pv": "vaginal",
            "top": "topical",
            "inh": "inhalation",
            "neb": "nebulization",
            "oph": "ophthalmic",
            "otic": "otic",
            "nasal": "nasal",
        }

        # Frequency mappings
        self.frequency_mappings = {
            "qd": "once daily",
            "daily": "once daily",
            "od": "once daily",
            "bid": "twice daily",
            "tid": "three times daily",
            "qid": "four times daily",
            "q4h": "every 4 hours",
            "q6h": "every 6 hours",
            "q8h": "every 8 hours",
            "q12h": "every 12 hours",
            "prn": "as needed",
            "hs": "at bedtime",
            "ac": "before meals",
            "pc": "after meals",
        }

        # Caching
        self._search_cache: Dict[str, Any] = {}
        self._interaction_cache: Dict[str, Any] = {}

        # Thread pool
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Initialize data
        self._initialize_data()

    def _setup_medical_units(self) -> None:
        """Set up medical-specific units."""
        if not self.ureg:
            return

        # Define medical units
        self.ureg.define("tablet = 1 * count = tab = tabs")
        self.ureg.define("capsule = 1 * count = cap = caps")
        self.ureg.define("unit = 1 * count = u = units")
        self.ureg.define("international_unit = 1 * count = iu = IU")
        self.ureg.define("drop = 0.05 * milliliter = drops = gtt")
        self.ureg.define("puff = 1 * count = puffs")
        self.ureg.define("spray = 1 * count = sprays")

    def _initialize_data(self) -> None:
        """Initialize RxNorm data."""
        try:
            # Create sample data if none exists
            if not self._data_exists():
                self._create_sample_data()

            # Load RxNorm concepts
            self._load_concepts()

            # Build indices
            self._build_indices()

            # Load relationships
            self._load_relationships()

            # Load interactions if enabled
            if self.check_interactions:
                self._load_interactions()

            # Load mappings
            self._load_ndc_mappings()
            self._load_atc_mappings()

            self.logger.info(
                "RxNorm mapper initialized with %d concepts", len(self.concepts)
            )

        except Exception as e:
            self.logger.error("Error initializing RxNorm data: %s", e)
            raise

    def _data_exists(self) -> bool:
        """Check if RxNorm data files exist."""
        required_files = ["rxnorm_concepts.json", "relationships.json"]
        if self.check_interactions:
            required_files.append("interactions.json")
        return all((self.data_path / f).exists() for f in required_files)

    def _create_sample_data(self) -> None:
        """Create sample RxNorm data for development."""
        self.logger.info("Creating sample RxNorm data...")

        # Ensure directory exists
        self.data_path.mkdir(parents=True, exist_ok=True)
        # Sample RxNorm concepts
        sample_concepts = {
            # Ingredients
            "1191": {
                "name": "Aspirin",
                "tty": "IN",
                "status": "active",
                "synonyms": ["acetylsalicylic acid", "ASA"],
            },
            "5640": {
                "name": "Ibuprofen",
                "tty": "IN",
                "status": "active",
                "synonyms": ["Brufen"],
            },
            "161": {
                "name": "Acetaminophen",
                "tty": "IN",
                "status": "active",
                "synonyms": ["Paracetamol", "APAP"],
            },
            "6809": {
                "name": "Metformin",
                "tty": "IN",
                "status": "active",
                "synonyms": ["Glucophage"],
            },
            "35636": {
                "name": "Simvastatin",
                "tty": "IN",
                "status": "active",
                "synonyms": ["Zocor"],
            },
            # Brand names
            "215697": {
                "name": "Tylenol",
                "tty": "BN",
                "status": "active",
                "generic_name": "Acetaminophen",
                "ingredients": ["161"],
            },
            "153165": {
                "name": "Advil",
                "tty": "BN",
                "status": "active",
                "generic_name": "Ibuprofen",
                "ingredients": ["5640"],
            },
            # Semantic Clinical Drugs (SCD)
            "198440": {
                "name": "Aspirin 81 MG Oral Tablet",
                "tty": "SCD",
                "status": "active",
                "ingredients": ["1191"],
                "strength": "81 mg",
                "dose_form": "Oral Tablet",
                "route": "oral",
                "prescribable": True,
            },
            "314077": {
                "name": "Ibuprofen 200 MG Oral Tablet",
                "tty": "SCD",
                "status": "active",
                "ingredients": ["5640"],
                "strength": "200 mg",
                "dose_form": "Oral Tablet",
                "route": "oral",
                "prescribable": True,
            },
            "313782": {
                "name": "Acetaminophen 325 MG Oral Tablet",
                "tty": "SCD",
                "status": "active",
                "ingredients": ["161"],
                "strength": "325 mg",
                "dose_form": "Oral Tablet",
                "route": "oral",
                "prescribable": True,
            },
            "861007": {
                "name": "Metformin 500 MG Oral Tablet",
                "tty": "SCD",
                "status": "active",
                "ingredients": ["6809"],
                "strength": "500 mg",
                "dose_form": "Oral Tablet",
                "route": "oral",
                "prescribable": True,
            },
            # Semantic Branded Drugs (SBD)
            "104490": {
                "name": "Tylenol 325 MG Oral Tablet",
                "tty": "SBD",
                "status": "active",
                "brand_names": ["Tylenol"],
                "ingredients": ["161"],
                "strength": "325 mg",
                "dose_form": "Oral Tablet",
                "route": "oral",
                "prescribable": True,
            },
        }
        # Sample relationships
        sample_relationships = {
            "198440": {  # Aspirin 81 MG
                "has_ingredient": ["1191"],
                "has_dose_form": ["Oral Tablet"],
                "has_strength": ["81 mg"],
            },
            "314077": {  # Ibuprofen 200 MG
                "has_ingredient": ["5640"],
                "has_dose_form": ["Oral Tablet"],
                "has_strength": ["200 mg"],
            },
            "215697": {"has_ingredient": ["161"]},  # Tylenol brand
        }

        # Sample interactions
        sample_interactions = [
            {
                "drug1_rxcui": "1191",  # Aspirin
                "drug1_name": "Aspirin",
                "drug2_rxcui": "5640",  # Ibuprofen
                "drug2_name": "Ibuprofen",
                "severity": "moderate",
                "description": "Increased risk of bleeding when NSAIDs are given with antiplatelet agents",
                "mechanism": "Both drugs inhibit platelet function",
                "management": "Monitor for signs of bleeding. Consider using acetaminophen instead.",
            },
            {
                "drug1_rxcui": "6809",  # Metformin
                "drug1_name": "Metformin",
                "drug2_rxcui": "35636",  # Simvastatin
                "drug2_name": "Simvastatin",
                "severity": "low",
                "description": "Potential for increased metformin levels",
                "mechanism": "Simvastatin may inhibit metformin elimination",
                "management": "Monitor blood glucose levels",
            },
        ]

        # Sample mappings
        sample_ndc_mappings = {
            "0363-0160-01": "198440",  # Aspirin 81mg
            "0363-0280-01": "314077",  # Ibuprofen 200mg
            "50580-451-01": "313782",  # Acetaminophen 325mg
        }

        sample_atc_mappings = {
            "B01AC06": ["1191"],  # Aspirin
            "M01AE01": ["5640"],  # Ibuprofen
            "N02BE01": ["161"],  # Acetaminophen
        }
        # Save sample data
        with open(self.data_path / "rxnorm_concepts.json", "w", encoding="utf-8") as f:
            json.dump(sample_concepts, f, indent=2)

        with open(self.data_path / "relationships.json", "w", encoding="utf-8") as f:
            json.dump(sample_relationships, f, indent=2)

        with open(self.data_path / "interactions.json", "w", encoding="utf-8") as f:
            json.dump(sample_interactions, f, indent=2)

        with open(self.data_path / "ndc_mappings.json", "w", encoding="utf-8") as f:
            json.dump(sample_ndc_mappings, f, indent=2)

        with open(self.data_path / "atc_mappings.json", "w", encoding="utf-8") as f:
            json.dump(sample_atc_mappings, f, indent=2)

    def _load_concepts(self) -> None:
        """Load RxNorm concepts."""
        concepts_file = self.data_path / "rxnorm_concepts.json"

        try:
            with open(concepts_file, "r", encoding="utf-8") as f:
                concepts_data = json.load(f)

            for rxcui, data in concepts_data.items():
                # Parse term type
                tty = None
                for term_type in TermType:
                    if term_type.name == data.get("tty"):
                        tty = term_type
                        break

                if not tty:
                    self.logger.warning(
                        "Unknown term type for %s: %s", rxcui, data.get("tty")
                    )
                    continue

                # Parse status
                status = DrugStatus.ACTIVE
                if "status" in data:
                    for s in DrugStatus:
                        if s.value == data["status"]:
                            status = s
                            break
                concept = RxNormConcept(
                    rxcui=rxcui,
                    name=data.get("name", ""),
                    tty=tty,
                    language=data.get("language", "ENG"),
                    suppress=data.get("suppress", False),
                    status=status,
                    synonyms=data.get("synonyms", []),
                    ingredients=data.get("ingredients", []),
                    strength=data.get("strength"),
                    dose_form=data.get("dose_form"),
                    brand_names=data.get("brand_names", []),
                    generic_name=data.get("generic_name"),
                    atc_codes=data.get("atc_codes", []),
                    ndc_codes=data.get("ndc_codes", []),
                    snomed_codes=data.get("snomed_codes", []),
                    umls_cui=data.get("umls_cui"),
                    route=data.get("route"),
                    schedule=data.get("schedule"),
                    prescribable=data.get("prescribable", True),
                    human_drug=data.get("human_drug", True),
                )

                self.concepts[rxcui] = concept

        except Exception as e:
            self.logger.error("Error loading concepts: %s", e)
            raise

    def _build_indices(self) -> None:
        """Build search indices."""
        for rxcui, concept in self.concepts.items():
            # Skip if obsolete and not including obsolete
            if not self.include_obsolete and concept.status != DrugStatus.ACTIVE:
                continue

            # Index by name words
            name_words = self._tokenize(concept.name.lower())
            for word in name_words:
                if rxcui not in self.name_index[word]:
                    self.name_index[word].append(rxcui)

            # Index full name
            if rxcui not in self.name_index[concept.name.lower()]:
                self.name_index[concept.name.lower()].append(rxcui)

            # Index synonyms
            for synonym in concept.synonyms:
                syn_words = self._tokenize(synonym.lower())
                for word in syn_words:
                    if rxcui not in self.name_index[word]:
                        self.name_index[word].append(rxcui)
                if rxcui not in self.name_index[synonym.lower()]:
                    self.name_index[synonym.lower()].append(rxcui)
            # Index by ingredient
            if concept.is_ingredient():
                if rxcui not in self.ingredient_index[concept.name.lower()]:
                    self.ingredient_index[concept.name.lower()].append(rxcui)
                for synonym in concept.synonyms:
                    if rxcui not in self.ingredient_index[synonym.lower()]:
                        self.ingredient_index[synonym.lower()].append(rxcui)

            # Index by brand
            if concept.is_brand():
                if rxcui not in self.brand_index[concept.name.lower()]:
                    self.brand_index[concept.name.lower()].append(rxcui)

            # Also index brand names listed in the concept
            for brand_name in concept.brand_names:
                if rxcui not in self.brand_index[brand_name.lower()]:
                    self.brand_index[brand_name.lower()].append(rxcui)

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for indexing."""
        # Remove punctuation and split
        text = re.sub(r"[^\w\s-]", " ", text)
        tokens = text.split()

        # Filter out very short tokens
        tokens = [t for t in tokens if len(t) > 1]

        return tokens

    def _load_relationships(self) -> None:
        """Load drug relationships."""
        relationships_file = self.data_path / "relationships.json"

        try:
            if relationships_file.exists():
                with open(relationships_file, "r", encoding="utf-8") as f:
                    _ = json.load(f)  # Currently unused, for future extension

                # Relationships are already loaded as part of concepts
                # This method can be extended to load additional relationship types

        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning("Error loading relationships: %s", e)

    def _load_interactions(self) -> None:
        """Load drug-drug interactions."""
        interactions_file = self.data_path / "interactions.json"

        try:
            if interactions_file.exists():
                with open(interactions_file, "r", encoding="utf-8") as f:
                    interactions_data = json.load(f)

                for interaction_data in interactions_data:
                    interaction = DrugInteraction(
                        drug1_rxcui=interaction_data["drug1_rxcui"],
                        drug1_name=interaction_data["drug1_name"],
                        drug2_rxcui=interaction_data["drug2_rxcui"],
                        drug2_name=interaction_data["drug2_name"],
                        severity=interaction_data["severity"],
                        description=interaction_data["description"],
                        mechanism=interaction_data.get("mechanism"),
                        management=interaction_data.get("management"),
                        documentation_level=interaction_data.get("documentation_level"),
                        sources=interaction_data.get("sources", []),
                    )

                    # Index by both drugs
                    self.interactions[interaction.drug1_rxcui].append(interaction)
                    self.interactions[interaction.drug2_rxcui].append(interaction)

        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning("Error loading interactions: %s", e)

    def _load_ndc_mappings(self) -> None:
        """Load NDC to RxCUI mappings."""
        ndc_file = self.data_path / "ndc_mappings.json"

        try:
            if ndc_file.exists():
                with open(ndc_file, "r", encoding="utf-8") as f:
                    self.ndc_to_rxcui = json.load(f)

        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning("Error loading NDC mappings: %s", e)

    def _load_atc_mappings(self) -> None:
        """Load ATC to RxCUI mappings."""
        atc_file = self.data_path / "atc_mappings.json"

        try:
            if atc_file.exists():
                with open(atc_file, "r", encoding="utf-8") as f:
                    self.atc_to_rxcui = defaultdict(list, json.load(f))

        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning("Error loading ATC mappings: %s", e)

    def search(
        self,
        query: str,
        search_type: Optional[str] = None,
        include_brand: bool = True,
        include_generic: bool = True,
        prescribable_only: bool = False,
        max_results: Optional[int] = None,
    ) -> RxNormSearchResult:
        """Search for drug concepts.

        Args:
            query: Search query (drug name, ingredient, etc.)
            search_type: Limit to specific types (ingredient, brand, clinical)
            include_brand: Include brand name drugs
            include_generic: Include generic drugs
            prescribable_only: Only return prescribable drugs
            max_results: Maximum results to return

        Returns:
            RxNormSearchResult with matching concepts
        """
        start_time = datetime.now()
        max_results = max_results or self.max_results

        # Normalize query
        query_lower = query.lower().strip()

        # Check cache
        cache_key = f"{query_lower}_{search_type}_{include_brand}_{include_generic}_{prescribable_only}"
        if cache_key in self._search_cache:
            cached_result = self._search_cache[cache_key]
            # Create a new result with updated processing time
            return RxNormSearchResult(
                query=cached_result.query,
                concepts=cached_result.concepts,
                total_matches=cached_result.total_matches,
                processing_time=(datetime.now() - start_time).total_seconds(),
                search_metadata=cached_result.search_metadata,
                approximate_match=cached_result.approximate_match,
            )

        # Collect all matches
        all_matches = set()

        # 1. Direct RxCUI lookup
        if query_lower.isdigit() and query_lower in self.concepts:
            all_matches.add(query_lower)

        # 2. Name search
        if query_lower in self.name_index:
            all_matches.update(self.name_index[query_lower])

        # 3. Word-based search
        query_tokens = self._tokenize(query_lower)
        for token in query_tokens:
            if token in self.name_index:
                all_matches.update(self.name_index[token])
        # 4. Ingredient-specific search
        if search_type in [None, "ingredient"]:
            if query_lower in self.ingredient_index:
                all_matches.update(self.ingredient_index[query_lower])

        # 5. Brand-specific search
        if search_type in [None, "brand"]:
            if query_lower in self.brand_index:
                all_matches.update(self.brand_index[query_lower])

        # 6. Fuzzy search if enabled and few results
        if self.enable_fuzzy_matching and len(all_matches) < max_results:
            fuzzy_matches = self._fuzzy_search(
                query_lower, max_results - len(all_matches)
            )
            all_matches.update(fuzzy_matches)

        # Convert to concept objects and apply filters
        filtered_concepts = []

        for rxcui in all_matches:
            concept = self.concepts[rxcui]

            # Apply filters
            if not self.include_obsolete and concept.status != DrugStatus.ACTIVE:
                continue

            if prescribable_only and not concept.prescribable:
                continue

            if not include_brand and concept.is_brand():
                continue

            if (
                not include_generic
                and concept.is_clinical_drug()
                and not concept.is_brand()
            ):
                continue

            if search_type:
                if search_type == "ingredient" and not concept.is_ingredient():
                    continue
                elif search_type == "brand" and not concept.is_brand():
                    continue
                elif search_type == "clinical" and not concept.is_clinical_drug():
                    continue

            filtered_concepts.append(concept)
        # Sort by relevance
        filtered_concepts = self._rank_results(filtered_concepts, query_lower)

        # Limit results
        final_concepts = filtered_concepts[:max_results]

        # Determine if this is an approximate match
        approximate = any(
            query_lower not in c.name.lower()
            and query_lower not in " ".join(c.synonyms).lower()
            for c in final_concepts
        )

        # Create result
        result = RxNormSearchResult(
            query=query,
            concepts=final_concepts,
            total_matches=len(filtered_concepts),
            processing_time=(datetime.now() - start_time).total_seconds(),
            search_metadata={
                "total_candidates": len(all_matches),
                "search_type": search_type,
                "filters_applied": {
                    "include_brand": include_brand,
                    "include_generic": include_generic,
                    "prescribable_only": prescribable_only,
                },
            },
            approximate_match=approximate,
        )

        # Cache result
        self._search_cache[cache_key] = result

        return result

    def _fuzzy_search(self, query: str, limit: int) -> Set[str]:
        """Perform fuzzy string matching."""
        if not FUZZY_AVAILABLE:
            return set()

        matches = set()

        # Collect all searchable names
        search_terms = []
        for rxcui, concept in self.concepts.items():
            if not self.include_obsolete and concept.status != DrugStatus.ACTIVE:
                continue
            search_terms.append((rxcui, concept.name))
            for synonym in concept.synonyms:
                search_terms.append((rxcui, synonym))

        # Find fuzzy matches
        term_list = [term for _, term in search_terms]
        fuzzy_matches = process.extract(
            query, term_list, scorer=fuzz.token_sort_ratio, limit=limit * 2
        )

        for match_term, score in fuzzy_matches:
            if score >= 70:  # Minimum score
                for rxcui, term in search_terms:
                    if term == match_term:
                        matches.add(rxcui)
                        break

        return matches

    def _rank_results(
        self, concepts: List[RxNormConcept], query: str
    ) -> List[RxNormConcept]:
        """Rank search results by relevance."""
        scored_concepts = []

        for concept in concepts:
            score = 0.0

            # Exact match scores highest
            if concept.rxcui == query:
                score = 1.0
            elif concept.name.lower() == query:
                score = 0.95
            # Partial matches
            elif query in concept.name.lower():
                score = 0.8
            # Synonym matches
            elif any(query in syn.lower() for syn in concept.synonyms):
                score = 0.75
            # Token matches
            else:
                query_tokens = set(self._tokenize(query))
                name_tokens = set(self._tokenize(concept.name.lower()))

                overlap = (
                    len(query_tokens & name_tokens) / len(query_tokens)
                    if query_tokens
                    else 0
                )
                score = overlap * 0.7

            # Boost for prescribable drugs
            if concept.prescribable:
                score *= 1.05

            # Boost for active drugs
            if concept.status == DrugStatus.ACTIVE:
                score *= 1.05

            # Slight penalty for brand names when searching generically
            if concept.is_brand() and not any(
                brand.lower() in query for brand in concept.brand_names
            ):
                score *= 0.95

            scored_concepts.append((score, concept))

        # Sort by score descending
        scored_concepts.sort(key=lambda x: x[0], reverse=True)

        return [concept for _, concept in scored_concepts]

    def get_concept(self, rxcui: str) -> Optional[RxNormConcept]:
        """Get a concept by RxCUI."""
        return self.concepts.get(rxcui)

    def find_by_ndc(self, ndc: str) -> Optional[RxNormConcept]:
        """Find drug by NDC code."""
        # Normalize NDC (remove hyphens)
        ndc_normalized = ndc.replace("-", "")

        # Try with hyphens first
        rxcui = self.ndc_to_rxcui.get(ndc)
        if not rxcui:
            # Try without hyphens
            rxcui = self.ndc_to_rxcui.get(ndc_normalized)

        if rxcui:
            return self.get_concept(rxcui)
        return None

    def find_by_atc(self, atc_code: str) -> List[RxNormConcept]:
        """Find drugs by ATC code."""
        rxcui_list = self.atc_to_rxcui.get(atc_code, [])
        # Convert to concepts, filtering out None values
        concepts: List[RxNormConcept] = []
        for rxcui in rxcui_list:
            concept = self.get_concept(rxcui)
            if concept:
                concepts.append(concept)
        return concepts

    def get_ingredients(self, rxcui: str) -> List[RxNormConcept]:
        """Get ingredient concepts for a drug."""
        concept = self.get_concept(rxcui)
        if not concept:
            return []

        ingredients = []
        for ing_rxcui in concept.ingredients:
            ing_concept = self.get_concept(ing_rxcui)
            if ing_concept:
                ingredients.append(ing_concept)

        return ingredients

    def get_brand_names(self, rxcui: str) -> List[str]:
        """Get all brand names for a drug."""
        concept = self.get_concept(rxcui)
        if not concept:
            return []

        brand_names = set(concept.brand_names)

        # If this is an ingredient, find all branded drugs
        if concept.is_ingredient():
            for _, other_concept in self.concepts.items():
                if rxcui in other_concept.ingredients and other_concept.is_brand():
                    brand_names.add(other_concept.name)

        return list(brand_names)

    def check_drug_interactions(
        self, rxcui_list: List[str], severity_filter: Optional[str] = None
    ) -> List[DrugInteraction]:
        """Check for interactions between multiple drugs.

        Args:
            rxcui_list: List of RxCUIs to check
            severity_filter: Filter by severity (high, moderate, low)

        Returns:
            List of drug interactions
        """
        if not self.check_interactions:
            return []

        interactions_found = []
        checked_pairs = set()

        for i, rxcui1 in enumerate(rxcui_list):
            for rxcui2 in rxcui_list[i + 1 :]:
                # Skip if already checked
                pair = tuple(sorted([rxcui1, rxcui2]))
                if pair in checked_pairs:
                    continue
                checked_pairs.add(pair)

                # Check interactions for rxcui1
                if rxcui1 in self.interactions:
                    for interaction in self.interactions[rxcui1]:
                        if (
                            interaction.drug2_rxcui == rxcui2
                            or interaction.drug1_rxcui == rxcui2
                        ):
                            if (
                                not severity_filter
                                or interaction.severity == severity_filter
                            ):
                                interactions_found.append(interaction)

        return interactions_found

    def get_interactions(self, rxcui: str) -> List[DrugInteraction]:
        """Get all interactions for a single drug."""
        return self.interactions.get(rxcui, [])

    def parse_sig(self, sig_text: str) -> PrescriptionSig:
        """Parse a prescription sig (signature/directions).

        Args:
            sig_text: Prescription directions text

        Returns:
            Parsed prescription components
        """
        sig_lower = sig_text.lower()
        parsed = PrescriptionSig(drug_name="", parsed_components={})

        # Extract drug name (usually at the beginning)
        drug_match = re.match(r"^([^0-9]+?)(?:\s+\d+|$)", sig_text, re.IGNORECASE)
        if drug_match:
            parsed.drug_name = drug_match.group(1).strip()

            # Try to find RxCUI
            search_result = self.search(parsed.drug_name, max_results=1)
            if search_result.concepts:
                parsed.rxcui = search_result.concepts[0].rxcui

        # Extract dose
        dose_match = re.search(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|unit|iu)", sig_lower)
        if dose_match:
            parsed.dose = float(dose_match.group(1))
            parsed.dose_unit = dose_match.group(2)

        # Extract route
        for abbrev, full_route in self.route_mappings.items():
            if f" {abbrev} " in f" {sig_lower} " or f" {full_route} " in sig_lower:
                parsed.route = full_route
                break

        # Extract frequency
        for abbrev, full_freq in self.frequency_mappings.items():
            if abbrev in sig_lower:
                parsed.frequency = full_freq
                break

        # Check for PRN
        if "prn" in sig_lower or "as needed" in sig_lower:
            parsed.prn = True

        # Extract duration
        duration_match = re.search(r"for\s+(\d+)\s*(day|week|month)", sig_lower)
        if duration_match:
            parsed.duration = f"{duration_match.group(1)} {duration_match.group(2)}s"

        # Store original instructions
        parsed.instructions = sig_text

        return parsed

    def find_related_drugs(
        self, rxcui: str, relationship: str = "same_ingredient"
    ) -> List[RxNormConcept]:
        """Find drugs related by various relationships.

        Args:
            rxcui: Source drug RxCUI
            relationship: Type of relationship (same_ingredient, same_class, etc.)

        Returns:
            List of related drug concepts
        """
        concept = self.get_concept(rxcui)
        if not concept:
            return []

        related = []

        if relationship == "same_ingredient":
            # Find all drugs with the same ingredients
            if concept.ingredients:
                for other_rxcui, other_concept in self.concepts.items():
                    if other_rxcui != rxcui and set(other_concept.ingredients) == set(
                        concept.ingredients
                    ):
                        related.append(other_concept)

        elif relationship == "different_strength":
            # Find same drug with different strengths
            # Note: base_name could be used for fuzzy matching in future enhancement
            for other_rxcui, other_concept in self.concepts.items():
                if (
                    other_rxcui != rxcui
                    and other_concept.tty == concept.tty
                    and other_concept.ingredients == concept.ingredients
                    and other_concept.dose_form == concept.dose_form
                    and other_concept.strength != concept.strength
                ):
                    related.append(other_concept)

        elif relationship == "brand_generic":
            # Find brand/generic equivalents
            if concept.is_brand():
                # Find generic versions
                for _other_rxcui, other_concept in self.concepts.items():
                    if (
                        other_concept.is_clinical_drug()
                        and not other_concept.is_brand()
                        and set(other_concept.ingredients) == set(concept.ingredients)
                        and other_concept.strength == concept.strength
                        and other_concept.dose_form == concept.dose_form
                    ):
                        related.append(other_concept)
            else:
                # Find brand versions
                for _other_rxcui, other_concept in self.concepts.items():
                    if (
                        other_concept.is_brand()
                        and set(other_concept.ingredients) == set(concept.ingredients)
                        and other_concept.strength == concept.strength
                        and other_concept.dose_form == concept.dose_form
                    ):
                        related.append(other_concept)

        return related

    def convert_dose_units(
        self, value: float, from_unit: str, to_unit: str
    ) -> Optional[float]:
        """Convert between dose units.

        Args:
            value: Numeric value to convert
            from_unit: Source unit
            to_unit: Target unit

        Returns:
            Converted value or None if conversion not possible
        """
        if not self.enable_unit_conversion or not self.ureg:
            return None

        try:
            # Create quantity with source unit
            quantity = self.ureg.Quantity(value, from_unit)

            # Convert to target unit
            converted = quantity.to(to_unit)

            return float(converted.magnitude)

        except (ValueError, AttributeError, TypeError) as e:
            self.logger.warning("Unit conversion failed: %s", e)
            return None

    def get_statistics(self) -> Dict[str, Any]:
        """Get mapper statistics."""
        active_count = sum(
            1 for c in self.concepts.values() if c.status == DrugStatus.ACTIVE
        )
        ingredient_count = sum(1 for c in self.concepts.values() if c.is_ingredient())
        brand_count = sum(1 for c in self.concepts.values() if c.is_brand())
        clinical_count = sum(1 for c in self.concepts.values() if c.is_clinical_drug())

        return {
            "total_concepts": len(self.concepts),
            "active_concepts": active_count,
            "ingredient_concepts": ingredient_count,
            "brand_concepts": brand_count,
            "clinical_drug_concepts": clinical_count,
            "ndc_mappings": len(self.ndc_to_rxcui),
            "atc_mappings": sum(len(v) for v in self.atc_to_rxcui.values()),
            "total_interactions": sum(len(v) for v in self.interactions.values())
            // 2,  # Divide by 2 as each is stored twice
            "cache_size": len(self._search_cache),
            "fuzzy_matching_enabled": self.enable_fuzzy_matching,
            "unit_conversion_enabled": self.enable_unit_conversion,
        }

    async def batch_search(
        self, queries: List[str], **kwargs: Any
    ) -> Dict[str, RxNormSearchResult]:
        """Batch search for multiple queries."""
        results = {}

        loop = asyncio.get_event_loop()
        tasks = []

        for query in queries:
            task = loop.run_in_executor(
                self.executor,
                self.search,
                query,
                kwargs.get("search_type"),
                kwargs.get("include_brand", True),
                kwargs.get("include_generic", True),
                kwargs.get("prescribable_only", False),
                kwargs.get("max_results"),
            )
            tasks.append((query, task))

        for query, task in tasks:
            try:
                result = await task
                results[query] = result
            except (ValueError, AttributeError, KeyError) as e:
                self.logger.error("Error searching for '%s': %s", query, e)
                results[query] = RxNormSearchResult(
                    query=query,
                    concepts=[],
                    total_matches=0,
                    processing_time=0,
                    search_metadata={"error": str(e)},
                )

        return results

    def clear_cache(self) -> None:
        """Clear search caches."""
        self._search_cache.clear()
        self._interaction_cache.clear()
        self.logger.info("Caches cleared")

    def __del__(self) -> None:
        """Cleanup resources."""
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=False)


# Factory function
def create_rxnorm_mapper(**kwargs: Any) -> RxNormMapper:
    """Create RxNorm mapper instance."""
    return RxNormMapper(**kwargs)
