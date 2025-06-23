"""SNOMED CT Integration.

Comprehensive SNOMED CT (Systematized Nomenclature of Medicine Clinical Terms)
integration for Haven Health Passport.

Features:
- Concept search and retrieval
- Hierarchical navigation
- Relationship traversal
- Expression constraint language (ECL) support
- Multi-language support via language reference sets
- Post-coordination support
- Subset/reference set management
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
from typing import Any, Dict, List, Optional, Set, Tuple

# For fuzzy matching
try:
    from fuzzywuzzy import fuzz, process

    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False

# For graph operations
try:
    import networkx as nx

    GRAPH_AVAILABLE = True
except ImportError:
    GRAPH_AVAILABLE = False


class ConceptStatus(Enum):
    """SNOMED CT concept status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DUPLICATE = "duplicate"
    OUTDATED = "outdated"
    AMBIGUOUS = "ambiguous"
    ERRONEOUS = "erroneous"
    LIMITED = "limited"
    MOVED_ELSEWHERE = "moved_elsewhere"


class DescriptionType(Enum):
    """SNOMED CT description types."""

    FSN = "fully_specified_name"
    PREFERRED = "preferred_term"
    SYNONYM = "synonym"
    DEFINITION = "definition"


class RelationshipType(Enum):
    """Common SNOMED CT relationship types."""

    IS_A = "116680003"  # Is a (attribute)
    FINDING_SITE = "363698007"  # Finding site
    ASSOCIATED_MORPHOLOGY = "116676008"  # Associated morphology
    CAUSATIVE_AGENT = "246075003"  # Causative agent
    PART_OF = "123005000"  # Part of
    LATERALITY = "272741003"  # Laterality
    HAS_ACTIVE_INGREDIENT = "127489000"  # Has active ingredient
    HAS_DOSE_FORM = "411116001"  # Has dose form


class Hierarchy(Enum):
    """SNOMED CT top-level hierarchies."""

    BODY_STRUCTURE = "123037004"
    CLINICAL_FINDING = "404684003"
    PROCEDURE = "71388002"
    OBSERVABLE_ENTITY = "363787002"
    EVENT = "272379006"
    PHARMACEUTICAL = "373873005"
    PHYSICAL_OBJECT = "260787004"
    PHYSICAL_FORCE = "78621006"
    ORGANISM = "410607006"
    SUBSTANCE = "105590001"
    QUALIFIER_VALUE = "362981000"
    SOCIAL_CONTEXT = "48176007"
    ENVIRONMENT = "308916002"
    SITUATION = "243796009"
    SPECIMEN = "123038009"
    STAGING_SCALE = "254291000"


@dataclass
class SnomedConcept:
    """Represents a SNOMED CT concept."""

    concept_id: str
    fsn: str  # Fully Specified Name
    preferred_term: str
    status: ConceptStatus = ConceptStatus.ACTIVE
    module_id: str = ""
    definition_status: str = "primitive"
    effective_time: Optional[datetime] = None
    synonyms: List[str] = field(default_factory=list)
    parents: List[str] = field(default_factory=list)
    children: List[str] = field(default_factory=list)
    relationships: Dict[str, List[str]] = field(default_factory=dict)
    descriptions: Dict[str, Dict[str, str]] = field(default_factory=dict)
    language_refsets: Dict[str, str] = field(default_factory=dict)
    hierarchy: Optional[Hierarchy] = None
    semantic_tag: Optional[str] = None

    def get_semantic_tag(self) -> Optional[str]:
        """Extract semantic tag from FSN."""
        if self.semantic_tag:
            return self.semantic_tag

        match = re.search(r"\(([^)]+)\)$", self.fsn)
        if match:
            self.semantic_tag = match.group(1)
        return self.semantic_tag

    def is_primitive(self) -> bool:
        """Check if concept is primitive (vs fully defined)."""
        return self.definition_status == "primitive"

    def is_active(self) -> bool:
        """Check if concept is active."""
        return self.status == ConceptStatus.ACTIVE

    def get_hierarchy_root(self) -> Optional[str]:
        """Get the top-level hierarchy this concept belongs to."""
        if self.hierarchy:
            return self.hierarchy.value
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "concept_id": self.concept_id,
            "fsn": self.fsn,
            "preferred_term": self.preferred_term,
            "status": self.status.value,
            "module_id": self.module_id,
            "definition_status": self.definition_status,
            "effective_time": (
                self.effective_time.isoformat() if self.effective_time else None
            ),
            "synonyms": self.synonyms,
            "parents": self.parents,
            "children": self.children,
            "relationships": self.relationships,
            "descriptions": self.descriptions,
            "language_refsets": self.language_refsets,
            "hierarchy": self.hierarchy.value if self.hierarchy else None,
            "semantic_tag": self.semantic_tag,
        }


@dataclass
class SnomedSearchResult:
    """SNOMED CT search result."""

    query: str
    concepts: List[SnomedConcept]
    total_matches: int
    processing_time: float
    search_metadata: Dict[str, Any] = field(default_factory=dict)
    applied_filters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SnomedExpression:
    """SNOMED CT post-coordinated expression."""

    focus_concepts: List[str]
    refinements: Dict[str, List[Tuple[str, str]]]  # attribute -> [(operator, value)]

    def to_string(self) -> str:
        """Convert to SNOMED CT compositional grammar."""
        expr = " + ".join(self.focus_concepts)

        if self.refinements:
            refinement_strs = []
            for attr, values in self.refinements.items():
                for op, val in values:
                    refinement_strs.append(f"{attr} {op} {val}")
            expr += " : " + " , ".join(refinement_strs)

        return expr


class SnomedCTIntegration:
    """Comprehensive SNOMED CT integration system."""

    def __init__(
        self,
        data_path: Optional[str] = None,
        enable_fuzzy_matching: bool = True,
        enable_graph_operations: bool = True,
        min_confidence: float = 0.7,
        max_results: int = 50,
        language: str = "en-US",
        load_relationships: bool = True,
        enable_ecl: bool = True,
    ):
        """
        Initialize SNOMED CT integration.

        Args:
            data_path: Path to SNOMED CT data files
            enable_fuzzy_matching: Enable fuzzy string matching
            enable_graph_operations: Enable graph-based operations
            min_confidence: Minimum confidence threshold
            max_results: Maximum number of results
            language: Language reference set to use
            load_relationships: Load relationship data
            enable_ecl: Enable Expression Constraint Language
        """
        self.logger = logging.getLogger(__name__)
        self.data_path = Path(
            data_path
            or "/Users/cadenceapeiron/Documents/HavenHealthPassport/data/terminologies/snomed_ct"
        )
        self.enable_fuzzy_matching = enable_fuzzy_matching and FUZZY_AVAILABLE
        self.enable_graph_operations = enable_graph_operations and GRAPH_AVAILABLE
        self.min_confidence = min_confidence
        self.max_results = max_results
        self.language = language
        self.load_relationships = load_relationships
        self.enable_ecl = enable_ecl

        # Data structures
        self.concepts: Dict[str, SnomedConcept] = {}
        self.description_index: Dict[str, List[str]] = defaultdict(list)
        self.fsn_index: Dict[str, str] = {}
        self.preferred_term_index: Dict[str, List[str]] = defaultdict(list)
        self.hierarchy_index: Dict[Hierarchy, Set[str]] = defaultdict(set)
        self.semantic_tag_index: Dict[str, Set[str]] = defaultdict(set)
        self.inactive_concept_map: Dict[str, str] = (
            {}
        )  # Maps inactive to active concepts

        # Relationship graph
        self.concept_graph = None
        if self.enable_graph_operations:
            self.concept_graph = nx.DiGraph()

        # Caching
        self._search_cache: Dict[str, Any] = {}
        self._ecl_cache: Dict[str, Any] = {}
        self._path_cache: Dict[str, Any] = {}

        # Thread pool
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Initialize data
        self._initialize_data()

    def _initialize_data(self) -> None:
        """Initialize SNOMED CT data."""
        try:
            # Create sample data if none exists
            if not self._data_exists():
                self._create_sample_data()

            # Load concepts
            self._load_concepts()

            # Load descriptions
            self._load_descriptions()

            # Load relationships if enabled
            if self.load_relationships:
                self._load_relationships()

            # Build indices
            self._build_indices()

            # Build concept graph if enabled
            if self.enable_graph_operations and self.concept_graph is not None:
                self._build_concept_graph()

            self.logger.info(
                "SNOMED CT integration initialized with %s concepts", len(self.concepts)
            )

        except Exception as e:
            self.logger.error("Error initializing SNOMED CT data: %s", e)
            raise

    def _data_exists(self) -> bool:
        """Check if SNOMED CT data files exist."""
        required_files = ["concepts.json", "descriptions.json"]
        if self.load_relationships:
            required_files.append("relationships.json")
        return all((self.data_path / f).exists() for f in required_files)

    def _create_sample_data(self) -> None:
        """Create sample SNOMED CT data for development."""
        self.logger.info("Creating sample SNOMED CT data...")

        # Ensure directory exists
        self.data_path.mkdir(parents=True, exist_ok=True)
        # Sample concepts
        sample_concepts = {
            # Clinical findings
            "22298006": {
                "fsn": "Myocardial infarction (disorder)",
                "preferred_term": "Myocardial infarction",
                "status": "active",
                "hierarchy": "404684003",
                "parents": ["57809008"],
                "semantic_tag": "disorder",
            },
            "38341003": {
                "fsn": "Hypertensive disorder, systemic arterial (disorder)",
                "preferred_term": "Hypertension",
                "status": "active",
                "hierarchy": "404684003",
                "parents": ["64572001"],
                "semantic_tag": "disorder",
            },
            "73211009": {
                "fsn": "Diabetes mellitus (disorder)",
                "preferred_term": "Diabetes mellitus",
                "status": "active",
                "hierarchy": "404684003",
                "parents": ["362969004"],
                "semantic_tag": "disorder",
            },
            "195967001": {
                "fsn": "Asthma (disorder)",
                "preferred_term": "Asthma",
                "status": "active",
                "hierarchy": "404684003",
                "parents": ["50043002"],
                "semantic_tag": "disorder",
            },
            "82423001": {
                "fsn": "Chronic pain (finding)",
                "preferred_term": "Chronic pain",
                "status": "active",
                "hierarchy": "404684003",
                "parents": ["22253000"],
                "semantic_tag": "finding",
            },
            # Body structures
            "80891009": {
                "fsn": "Heart structure (body structure)",
                "preferred_term": "Heart",
                "status": "active",
                "hierarchy": "123037004",
                "parents": ["39937001"],
                "semantic_tag": "body structure",
            },
            "39057004": {
                "fsn": "Pulmonary valve structure (body structure)",
                "preferred_term": "Pulmonary valve",
                "status": "active",
                "hierarchy": "123037004",
                "parents": ["80891009"],
                "semantic_tag": "body structure",
            },
            # Procedures
            "80146002": {
                "fsn": "Appendectomy (procedure)",
                "preferred_term": "Appendectomy",
                "status": "active",
                "hierarchy": "71388002",
                "parents": ["387713003"],
                "semantic_tag": "procedure",
            },
            "174041007": {
                "fsn": "Computed tomography of chest (procedure)",
                "preferred_term": "CT of chest",
                "status": "active",
                "hierarchy": "71388002",
                "parents": ["77477000"],
                "semantic_tag": "procedure",
            },
            # Pharmaceutical/biological products
            "387207008": {
                "fsn": "Ibuprofen (substance)",
                "preferred_term": "Ibuprofen",
                "status": "active",
                "hierarchy": "373873005",
                "parents": ["35576003"],
                "semantic_tag": "substance",
            },
            "387517004": {
                "fsn": "Paracetamol (substance)",
                "preferred_term": "Paracetamol",
                "status": "active",
                "hierarchy": "373873005",
                "parents": ["35576003"],
                "semantic_tag": "substance",
            },
        }
        # Sample descriptions
        sample_descriptions = {
            "22298006": [
                {
                    "term": "Myocardial infarction",
                    "type": "preferred",
                    "language": "en",
                },
                {"term": "MI", "type": "synonym", "language": "en"},
                {"term": "Heart attack", "type": "synonym", "language": "en"},
                {"term": "Cardiac infarction", "type": "synonym", "language": "en"},
                {"term": "Infarto de miocardio", "type": "preferred", "language": "es"},
            ],
            "38341003": [
                {"term": "Hypertension", "type": "preferred", "language": "en"},
                {"term": "High blood pressure", "type": "synonym", "language": "en"},
                {"term": "HTN", "type": "synonym", "language": "en"},
                {"term": "Hypertensive disease", "type": "synonym", "language": "en"},
                {"term": "Hipertensión", "type": "preferred", "language": "es"},
            ],
            "73211009": [
                {"term": "Diabetes mellitus", "type": "preferred", "language": "en"},
                {"term": "DM", "type": "synonym", "language": "en"},
                {"term": "Diabetes", "type": "synonym", "language": "en"},
                {"term": "Sugar diabetes", "type": "synonym", "language": "en"},
            ],
            "195967001": [
                {"term": "Asthma", "type": "preferred", "language": "en"},
                {"term": "Bronchial asthma", "type": "synonym", "language": "en"},
                {"term": "Asthmatic disease", "type": "synonym", "language": "en"},
            ],
        }

        # Sample relationships
        sample_relationships = {
            "22298006": {
                "116680003": ["57809008"],  # IS-A Ischemic heart disease
                "363698007": ["80891009"],  # Finding site: Heart structure
            },
            "38341003": {
                "116680003": ["64572001"],  # IS-A Disease of cardiovascular system
                "363698007": [
                    "113257007"
                ],  # Finding site: Structure of cardiovascular system
            },
            "195967001": {
                "116680003": ["50043002"],  # IS-A Chronic obstructive lung disease
                "363698007": ["955009"],  # Finding site: Bronchial structure
            },
        }
        # Save sample data
        with open(self.data_path / "concepts.json", "w", encoding="utf-8") as f:
            json.dump(sample_concepts, f, indent=2)

        with open(self.data_path / "descriptions.json", "w", encoding="utf-8") as f:
            json.dump(sample_descriptions, f, indent=2)

        with open(self.data_path / "relationships.json", "w", encoding="utf-8") as f:
            json.dump(sample_relationships, f, indent=2)

    def _load_concepts(self) -> None:
        """Load SNOMED CT concepts."""
        concepts_file = self.data_path / "concepts.json"

        try:
            with open(concepts_file, "r", encoding="utf-8") as f:
                concepts_data = json.load(f)

            for concept_id, data in concepts_data.items():
                concept = SnomedConcept(
                    concept_id=concept_id,
                    fsn=data.get("fsn", ""),
                    preferred_term=data.get("preferred_term", ""),
                    status=ConceptStatus(data.get("status", "active")),
                    module_id=data.get("module_id", ""),
                    definition_status=data.get("definition_status", "primitive"),
                    parents=data.get("parents", []),
                    semantic_tag=data.get("semantic_tag"),
                )

                # Set hierarchy
                hierarchy_id = data.get("hierarchy")
                if hierarchy_id:
                    for h in Hierarchy:
                        if h.value == hierarchy_id:
                            concept.hierarchy = h
                            break

                self.concepts[concept_id] = concept

        except Exception as e:
            self.logger.error("Error loading concepts: %s", e)
            raise

    def _load_descriptions(self) -> None:
        """Load SNOMED CT descriptions."""
        descriptions_file = self.data_path / "descriptions.json"

        try:
            with open(descriptions_file, "r", encoding="utf-8") as f:
                descriptions_data = json.load(f)

            for concept_id, descriptions in descriptions_data.items():
                if concept_id not in self.concepts:
                    continue

                concept = self.concepts[concept_id]

                for desc in descriptions:
                    term = desc.get("term", "")
                    desc_type = desc.get("type", "synonym")
                    language = desc.get("language", "en")

                    # Add to appropriate collection
                    if desc_type == "preferred" and language == "en":
                        concept.preferred_term = term
                    elif desc_type == "synonym":
                        concept.synonyms.append(term)

                    # Add to language reference sets
                    if desc_type == "preferred":
                        concept.language_refsets[language] = term

                    # Store in descriptions dict
                    if language not in concept.descriptions:
                        concept.descriptions[language] = {}
                    concept.descriptions[language][desc_type] = term

        except Exception as e:
            self.logger.error("Error loading descriptions: %s", e)
            raise

    def _load_relationships(self) -> None:
        """Load SNOMED CT relationships."""
        relationships_file = self.data_path / "relationships.json"

        try:
            if not relationships_file.exists():
                self.logger.warning(
                    "Relationships file not found, skipping relationship loading"
                )
                return

            with open(relationships_file, "r", encoding="utf-8") as f:
                relationships_data = json.load(f)

            for source_id, relationships in relationships_data.items():
                if source_id not in self.concepts:
                    continue

                concept = self.concepts[source_id]

                for rel_type, targets in relationships.items():
                    concept.relationships[rel_type] = targets

                    # Update parent-child relationships for IS-A
                    if rel_type == RelationshipType.IS_A.value:
                        for target_id in targets:
                            if target_id in self.concepts:
                                self.concepts[target_id].children.append(source_id)

        except Exception as e:
            self.logger.error("Error loading relationships: %s", e)
            raise

    def _build_indices(self) -> None:
        """Build search indices."""
        for concept_id, concept in self.concepts.items():
            # Index by FSN words
            fsn_words = self._tokenize(concept.fsn.lower())
            for word in fsn_words:
                self.description_index[word].append(concept_id)

            # Index full FSN
            self.fsn_index[concept.fsn.lower()] = concept_id

            # Index by preferred term
            pref_words = self._tokenize(concept.preferred_term.lower())
            for word in pref_words:
                if concept_id not in self.preferred_term_index[word]:
                    self.preferred_term_index[word].append(concept_id)
            # Index by synonyms
            for synonym in concept.synonyms:
                syn_words = self._tokenize(synonym.lower())
                for word in syn_words:
                    if concept_id not in self.description_index[word]:
                        self.description_index[word].append(concept_id)

            # Index by hierarchy
            if concept.hierarchy:
                self.hierarchy_index[concept.hierarchy].add(concept_id)

            # Index by semantic tag
            tag = concept.get_semantic_tag()
            if tag:
                self.semantic_tag_index[tag].add(concept_id)

            # Map inactive concepts to active replacements
            if not concept.is_active() and concept.relationships:
                # Look for "replaced by" relationship
                replaced_by = concept.relationships.get("370124000", [])
                if replaced_by:
                    self.inactive_concept_map[concept_id] = replaced_by[0]

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for indexing."""
        # Remove punctuation and split
        text = re.sub(r"[^\w\s]", " ", text)
        tokens = text.split()

        # Filter out stop words and short tokens
        stop_words = {
            "the",
            "of",
            "and",
            "to",
            "in",
            "with",
            "for",
            "on",
            "at",
            "by",
            "from",
            "or",
            "a",
            "an",
        }
        tokens = [t for t in tokens if len(t) > 1 and t not in stop_words]

        return tokens

    def _build_concept_graph(self) -> None:
        """Build NetworkX graph of concepts."""
        if not self.concept_graph:
            return

        for concept_id, concept in self.concepts.items():
            # Add node with attributes
            self.concept_graph.add_node(
                concept_id,
                fsn=concept.fsn,
                preferred_term=concept.preferred_term,
                hierarchy=concept.hierarchy.value if concept.hierarchy else None,
                active=concept.is_active(),
            )
            # Add edges for all relationships
            for rel_type, targets in concept.relationships.items():
                for target_id in targets:
                    if target_id in self.concepts:
                        self.concept_graph.add_edge(
                            concept_id, target_id, relationship=rel_type
                        )

    def search(
        self,
        query: str,
        hierarchies: Optional[List[Hierarchy]] = None,
        semantic_tags: Optional[List[str]] = None,
        active_only: bool = True,
        include_fsn: bool = True,
        max_results: Optional[int] = None,
    ) -> SnomedSearchResult:
        """
        Search for SNOMED CT concepts.

        Args:
            query: Search query
            hierarchies: Filter by specific hierarchies
            semantic_tags: Filter by semantic tags
            active_only: Only return active concepts
            include_fsn: Search in Fully Specified Names
            max_results: Maximum results to return

        Returns:
            SnomedSearchResult with matching concepts
        """
        start_time = datetime.now()
        max_results = max_results or self.max_results

        # Normalize query
        query_lower = query.lower().strip()

        # Check if it's a concept ID
        if query_lower.isdigit() and query_lower in self.concepts:
            concept = self.concepts[query_lower]
            if not active_only or concept.is_active():
                result = SnomedSearchResult(
                    query=query,
                    concepts=[concept],
                    total_matches=1,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                )
                return result
        # Collect all matches
        all_matches = set()

        # 1. Exact FSN match
        if include_fsn and query_lower in self.fsn_index:
            all_matches.add(self.fsn_index[query_lower])

        # 2. Word-based search
        query_tokens = self._tokenize(query_lower)

        # Search in descriptions
        for token in query_tokens:
            if token in self.description_index:
                all_matches.update(self.description_index[token])

            if token in self.preferred_term_index:
                all_matches.update(self.preferred_term_index[token])

        # 3. Fuzzy search if enabled and few results
        if self.enable_fuzzy_matching and len(all_matches) < max_results:
            fuzzy_matches = self._fuzzy_search(
                query_lower, max_results - len(all_matches)
            )
            all_matches.update(fuzzy_matches)

        # Convert to concept objects and apply filters
        filtered_concepts = []

        for concept_id in all_matches:
            concept = self.concepts[concept_id]

            # Apply filters
            if active_only and not concept.is_active():
                # Try to find active replacement
                if concept_id in self.inactive_concept_map:
                    replacement_id = self.inactive_concept_map[concept_id]
                    if replacement_id in self.concepts:
                        concept = self.concepts[replacement_id]
                    else:
                        continue
                else:
                    continue

            if hierarchies and concept.hierarchy not in hierarchies:
                continue

            if semantic_tags:
                tag = concept.get_semantic_tag()
                if not tag or tag not in semantic_tags:
                    continue

            filtered_concepts.append(concept)
        # Sort by relevance
        filtered_concepts = self._rank_results(filtered_concepts, query_lower)

        # Limit results
        final_concepts = filtered_concepts[:max_results]

        # Create result
        result = SnomedSearchResult(
            query=query,
            concepts=final_concepts,
            total_matches=len(filtered_concepts),
            processing_time=(datetime.now() - start_time).total_seconds(),
            search_metadata={
                "total_candidates": len(all_matches),
                "search_methods": self._get_search_methods(all_matches),
            },
            applied_filters={
                "hierarchies": [h.value for h in hierarchies] if hierarchies else None,
                "semantic_tags": semantic_tags,
                "active_only": active_only,
            },
        )

        return result

    def _fuzzy_search(self, query: str, limit: int) -> Set[str]:
        """Perform fuzzy string matching."""
        if not FUZZY_AVAILABLE:
            return set()

        matches = set()

        # Collect all searchable terms
        search_terms = []
        for concept_id, concept in self.concepts.items():
            search_terms.append((concept_id, concept.preferred_term))
            if concept.fsn != concept.preferred_term:
                search_terms.append((concept_id, concept.fsn))

        # Find fuzzy matches
        term_list = [term for _, term in search_terms]
        fuzzy_matches = process.extract(
            query, term_list, scorer=fuzz.token_sort_ratio, limit=limit * 2
        )

        for match_term, score in fuzzy_matches:
            if score >= 70:  # Minimum score
                for concept_id, term in search_terms:
                    if term == match_term:
                        matches.add(concept_id)
                        break

        return matches

    def _rank_results(
        self, concepts: List[SnomedConcept], query: str
    ) -> List[SnomedConcept]:
        """Rank search results by relevance."""
        scored_concepts = []

        for concept in concepts:
            score = 0.0

            # Exact match scores highest
            if concept.concept_id == query:
                score = 1.0
            elif concept.preferred_term.lower() == query:
                score = 0.95
            elif concept.fsn.lower() == query:
                score = 0.9
            # Partial matches
            elif query in concept.preferred_term.lower():
                score = 0.8
            elif query in concept.fsn.lower():
                score = 0.75
            # Token matches
            else:
                query_tokens = set(self._tokenize(query))
                pref_tokens = set(self._tokenize(concept.preferred_term.lower()))
                fsn_tokens = set(self._tokenize(concept.fsn.lower()))

                pref_overlap = (
                    len(query_tokens & pref_tokens) / len(query_tokens)
                    if query_tokens
                    else 0
                )
                fsn_overlap = (
                    len(query_tokens & fsn_tokens) / len(query_tokens)
                    if query_tokens
                    else 0
                )

                score = max(pref_overlap * 0.7, fsn_overlap * 0.65)

            # Boost for active concepts
            if concept.is_active():
                score *= 1.1

            scored_concepts.append((score, concept))

        # Sort by score descending
        scored_concepts.sort(key=lambda x: x[0], reverse=True)

        return [concept for _, concept in scored_concepts]

    def _get_search_methods(self, matches: Set[str]) -> List[str]:
        """Determine which search methods found results."""
        methods = []
        if any(
            self.concepts[cid].concept_id in matches
            for cid in matches
            if cid in self.concepts
        ):
            methods.append("concept_id")
        if self.fsn_index:
            methods.append("fsn")
        methods.extend(["preferred_term", "synonym"])
        return methods

    def get_concept(self, concept_id: str) -> Optional[SnomedConcept]:
        """Get a concept by ID."""
        return self.concepts.get(concept_id)

    def get_parents(self, concept_id: str) -> List[SnomedConcept]:
        """Get parent concepts."""
        concept = self.get_concept(concept_id)
        if not concept:
            return []

        parents = []
        for parent_id in concept.parents:
            parent = self.get_concept(parent_id)
            if parent:
                parents.append(parent)

        return parents

    def get_children(self, concept_id: str) -> List[SnomedConcept]:
        """Get child concepts."""
        concept = self.get_concept(concept_id)
        if not concept:
            return []

        children = []
        for child_id in concept.children:
            child = self.get_concept(child_id)
            if child:
                children.append(child)

        return children

    def get_ancestors(
        self, concept_id: str, max_depth: int = 10
    ) -> List[List[SnomedConcept]]:
        """Get all ancestors organized by level."""
        ancestors_by_level = []
        current_level = [concept_id]
        visited = {concept_id}
        depth = 0

        while current_level and depth < max_depth:
            next_level = []
            level_concepts = []

            for cid in current_level:
                concept = self.get_concept(cid)
                if concept:
                    for parent_id in concept.parents:
                        if parent_id not in visited:
                            visited.add(parent_id)
                            next_level.append(parent_id)
                            parent = self.get_concept(parent_id)
                            if parent:
                                level_concepts.append(parent)
            if level_concepts:
                ancestors_by_level.append(level_concepts)

            current_level = next_level
            depth += 1

        return ancestors_by_level

    def get_descendants(
        self, concept_id: str, max_depth: int = 10
    ) -> List[SnomedConcept]:
        """Get all descendant concepts."""
        descendants = []
        visited = {concept_id}
        queue = [(concept_id, 0)]

        while queue:
            current_id, depth = queue.pop(0)

            if depth >= max_depth:
                continue

            concept = self.get_concept(current_id)
            if concept:
                for child_id in concept.children:
                    if child_id not in visited:
                        visited.add(child_id)
                        child = self.get_concept(child_id)
                        if child:
                            descendants.append(child)
                            queue.append((child_id, depth + 1))

        return descendants

    def get_relationships(
        self, concept_id: str, relationship_type: Optional[str] = None
    ) -> Dict[str, List[SnomedConcept]]:
        """Get concept relationships."""
        concept = self.get_concept(concept_id)
        if not concept:
            return {}

        relationships = {}

        for rel_type, target_ids in concept.relationships.items():
            if relationship_type and rel_type != relationship_type:
                continue

            targets = []
            for target_id in target_ids:
                target = self.get_concept(target_id)
                if target:
                    targets.append(target)

            if targets:
                relationships[rel_type] = targets

        return relationships

    def find_path(self, source_id: str, target_id: str) -> Optional[List[str]]:
        """Find shortest path between two concepts."""
        if not self.concept_graph or not GRAPH_AVAILABLE:
            return None

        try:
            path = nx.shortest_path(self.concept_graph, source_id, target_id)
            return list(path)  # Convert to list to ensure correct type
        except nx.NetworkXNoPath:
            return None

    def get_common_ancestors(self, concept_ids: List[str]) -> List[SnomedConcept]:
        """Find common ancestors of multiple concepts."""
        if not concept_ids:
            return []

        # Get ancestors for each concept
        ancestor_sets = []
        for concept_id in concept_ids:
            ancestors: Set[str] = set()
            for level in self.get_ancestors(concept_id):
                ancestors.update(c.concept_id for c in level)
            ancestor_sets.append(ancestors)

        # Find intersection
        common = set.intersection(*ancestor_sets) if ancestor_sets else set()

        # Convert to concepts
        # Convert to concepts, filtering out None values
        concepts: List[SnomedConcept] = []
        for cid in common:
            concept = self.get_concept(cid)
            if concept:
                concepts.append(concept)
        return concepts

    def execute_ecl(self, expression: str) -> List[SnomedConcept]:
        """
        Execute Expression Constraint Language query.

        Simple ECL support for common patterns:
        - < 404684003 (descendants of clinical finding)
        - > 22298006 (ancestors of MI)
        - << 73211009 (self and descendants of diabetes)
        - >> 195967001 (self and ancestors of asthma)
        """
        if not self.enable_ecl:
            raise ValueError("ECL support is disabled")

        expression = expression.strip()

        # Simple descendant query
        if expression.startswith("<<"):
            concept_id = expression[2:].strip()
            concepts = [self.get_concept(concept_id)]
            concepts.extend(self.get_descendants(concept_id))
            return [c for c in concepts if c]
        elif expression.startswith("<"):
            concept_id = expression[1:].strip()
            return self.get_descendants(concept_id)

        # Simple ancestor query
        elif expression.startswith(">>"):
            concept_id = expression[2:].strip()
            concepts = [self.get_concept(concept_id)]
            for level in self.get_ancestors(concept_id):
                concepts.extend(level)
            return [c for c in concepts if c]

        elif expression.startswith(">"):
            concept_id = expression[1:].strip()
            ancestors = []
            for level in self.get_ancestors(concept_id):
                ancestors.extend(level)
            return ancestors

        # Direct concept reference
        else:
            concept = self.get_concept(expression)
            return [concept] if concept else []

    def create_expression(
        self,
        focus_concepts: List[str],
        refinements: Optional[Dict[str, List[Tuple[str, str]]]] = None,
    ) -> SnomedExpression:
        """Create a post-coordinated expression."""
        return SnomedExpression(
            focus_concepts=focus_concepts, refinements=refinements or {}
        )

    def get_translation(self, concept_id: str, language: str) -> Optional[str]:
        """Get concept translation for a specific language."""
        concept = self.get_concept(concept_id)
        if not concept:
            return None

        # Check language reference sets
        if language in concept.language_refsets:
            return concept.language_refsets[language]

        # Check descriptions
        if language in concept.descriptions:
            lang_descs = concept.descriptions[language]
            return lang_descs.get("preferred") or lang_descs.get("synonym")

        return None

    def get_hierarchy_concepts(self, hierarchy: Hierarchy) -> List[SnomedConcept]:
        """Get all concepts in a specific hierarchy."""
        concept_ids = self.hierarchy_index.get(hierarchy, set())
        # Convert to concepts, filtering out None values
        concepts: List[SnomedConcept] = []
        for cid in concept_ids:
            concept = self.get_concept(cid)
            if concept:
                concepts.append(concept)
        return concepts

    def get_statistics(self) -> Dict[str, Any]:
        """Get integration statistics."""
        active_count = sum(1 for c in self.concepts.values() if c.is_active())

        hierarchy_counts = {}
        for hierarchy in Hierarchy:
            hierarchy_counts[hierarchy.name] = len(
                self.hierarchy_index.get(hierarchy, set())
            )

        return {
            "total_concepts": len(self.concepts),
            "active_concepts": active_count,
            "inactive_concepts": len(self.concepts) - active_count,
            "total_descriptions": sum(
                len(c.synonyms) + 2 for c in self.concepts.values()
            ),  # +2 for FSN and preferred
            "hierarchies": hierarchy_counts,
            "languages": len(
                set(
                    lang
                    for c in self.concepts.values()
                    for lang in c.language_refsets.keys()
                )
            ),
            "graph_enabled": self.concept_graph is not None,
            "graph_nodes": (
                self.concept_graph.number_of_nodes() if self.concept_graph else 0
            ),
            "graph_edges": (
                self.concept_graph.number_of_edges() if self.concept_graph else 0
            ),
        }

    async def batch_search(
        self, queries: List[str], **kwargs: Any
    ) -> Dict[str, SnomedSearchResult]:
        """Batch search for multiple queries."""
        results = {}

        loop = asyncio.get_event_loop()
        tasks = []

        for query in queries:
            task = loop.run_in_executor(
                self.executor,
                self.search,
                query,
                kwargs.get("hierarchies"),
                kwargs.get("semantic_tags"),
                kwargs.get("active_only", True),
                kwargs.get("include_fsn", True),
                kwargs.get("max_results"),
            )
            tasks.append((query, task))
        for query, task in tasks:
            try:
                result = await task
                results[query] = result
            except (KeyError, ValueError, AttributeError) as e:
                self.logger.error("Error searching for '%s': %s", query, e)
                results[query] = SnomedSearchResult(
                    query=query,
                    concepts=[],
                    total_matches=0,
                    processing_time=0,
                    search_metadata={"error": str(e)},
                )

        return results

    def export_subset(
        self,
        concept_ids: List[str],
        output_path: str,
        include_relationships: bool = True,
        include_descriptions: bool = True,
    ) -> None:
        """Export a subset of concepts."""
        subset_data: Dict[str, Any] = {
            "concepts": {},
            "descriptions": {},
            "relationships": {},
        }

        for concept_id in concept_ids:
            concept = self.get_concept(concept_id)
            if concept:
                subset_data["concepts"][concept_id] = concept.to_dict()

                if include_descriptions:
                    subset_data["descriptions"][concept_id] = concept.descriptions

                if include_relationships:
                    subset_data["relationships"][concept_id] = concept.relationships

        output_file = Path(output_path)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(subset_data, f, indent=2)

    def __del__(self) -> None:
        """Cleanup resources."""
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=False)


# Factory function
def create_snomed_ct_integration(**kwargs: Any) -> SnomedCTIntegration:
    """Create SNOMED CT integration instance."""
    return SnomedCTIntegration(**kwargs)
