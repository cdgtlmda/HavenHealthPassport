"""ICD-10 Code Mapper.

Maps medical conditions to ICD-10 codes with advanced features:
- Hierarchical code structure support
- Fuzzy matching for variations
- Synonym and abbreviation handling
- Confidence scoring
- Multi-language support
- Clinical context awareness
"""

import asyncio
import json
import logging
import pickle
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

# For fuzzy matching
try:
    from fuzzywuzzy import fuzz, process

    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False

# For semantic similarity
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False
    TfidfVectorizer = None
    cosine_similarity = None

# For abbreviation handling
from .acronym_expander import MedicalAcronymExpander


class MatchType(Enum):
    """Types of ICD-10 code matches."""

    EXACT = "exact"
    PARTIAL = "partial"
    SYNONYM = "synonym"
    ABBREVIATION = "abbreviation"
    FUZZY = "fuzzy"
    SEMANTIC = "semantic"
    HIERARCHY = "hierarchy"
    CLINICAL_VARIANT = "clinical_variant"


@dataclass
class ICD10Code:
    """Comprehensive ICD-10 code representation."""

    code: str
    description: str
    category: Optional[str] = None
    parent_code: Optional[str] = None
    children_codes: List[str] = field(default_factory=list)
    is_billable: bool = True
    confidence: float = 1.0
    match_type: MatchType = MatchType.EXACT
    clinical_notes: Optional[str] = None
    excludes1: List[str] = field(default_factory=list)
    excludes2: List[str] = field(default_factory=list)
    includes: List[str] = field(default_factory=list)
    code_also: List[str] = field(default_factory=list)
    use_additional_code: List[str] = field(default_factory=list)
    laterality: Optional[str] = None  # left, right, bilateral
    severity: Optional[str] = None
    encounter_type: Optional[str] = None  # initial, subsequent, sequela
    trimester: Optional[int] = None  # for pregnancy codes

    def get_hierarchy_level(self) -> int:
        """Get the hierarchical level of the code."""
        if "." not in self.code:
            return 1  # Chapter or category
        _, extension = self.code.split(".", 1)
        return 2 + len(extension)

    def is_parent_of(self, other_code: str) -> bool:
        """Check if this code is a parent of another code."""
        return other_code.startswith(self.code) and len(other_code) > len(self.code)

    def copy(self) -> "ICD10Code":
        """Create a copy of this ICD10Code."""
        return ICD10Code(
            code=self.code,
            description=self.description,
            category=self.category,
            parent_code=self.parent_code,
            children_codes=self.children_codes.copy() if self.children_codes else [],
            is_billable=self.is_billable,
            confidence=self.confidence,
            match_type=self.match_type,
            clinical_notes=self.clinical_notes,
            excludes1=self.excludes1.copy() if self.excludes1 else [],
            excludes2=self.excludes2.copy() if self.excludes2 else [],
            includes=self.includes.copy() if self.includes else [],
            code_also=self.code_also.copy() if self.code_also else [],
            use_additional_code=(
                self.use_additional_code.copy() if self.use_additional_code else []
            ),
            laterality=self.laterality,
            severity=self.severity,
            encounter_type=self.encounter_type,
            trimester=self.trimester,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "code": self.code,
            "description": self.description,
            "category": self.category,
            "parent_code": self.parent_code,
            "children_codes": self.children_codes,
            "is_billable": self.is_billable,
            "confidence": self.confidence,
            "match_type": self.match_type.value,
            "clinical_notes": self.clinical_notes,
            "excludes1": self.excludes1,
            "excludes2": self.excludes2,
            "includes": self.includes,
            "code_also": self.code_also,
            "use_additional_code": self.use_additional_code,
            "laterality": self.laterality,
            "severity": self.severity,
            "encounter_type": self.encounter_type,
            "trimester": self.trimester,
        }


@dataclass
class ICD10SearchResult:
    """Search result with multiple potential matches."""

    query: str
    codes: List[ICD10Code]
    processing_time: float
    search_metadata: Dict[str, Any] = field(default_factory=dict)


class ICD10Mapper:
    """Advanced ICD-10 code mapping system."""

    def __init__(
        self,
        data_path: Optional[str] = None,
        enable_fuzzy_matching: bool = True,
        enable_semantic_matching: bool = True,
        min_confidence: float = 0.7,
        max_results: int = 10,
        language: str = "en",
    ):
        """Initialize ICD-10 mapper with advanced features.

        Args:
            data_path: Path to ICD-10 data files
            enable_fuzzy_matching: Enable fuzzy string matching
            enable_semantic_matching: Enable semantic similarity matching
            min_confidence: Minimum confidence threshold
            max_results: Maximum number of results to return
            language: Primary language for matching
        """
        self.logger = logging.getLogger(__name__)
        self.data_path = Path(
            data_path
            or "/Users/cadenceapeiron/Documents/HavenHealthPassport/data/terminologies/icd10"
        )
        self.enable_fuzzy_matching = enable_fuzzy_matching and FUZZY_AVAILABLE
        self.enable_semantic_matching = enable_semantic_matching and SEMANTIC_AVAILABLE
        self.min_confidence = min_confidence
        self.max_results = max_results
        self.language = language

        # Initialize components
        self.acronym_expander = MedicalAcronymExpander()
        self.entity_recognizer = None  # Lazy load

        # Data structures
        self.codes_by_id: Dict[str, ICD10Code] = {}
        self.description_index: Dict[str, List[str]] = defaultdict(list)
        self.synonym_map: Dict[str, List[str]] = {}
        self.abbreviation_map: Dict[str, List[str]] = {}
        self.hierarchy_tree: Dict[str, List[str]] = defaultdict(list)
        self.clinical_variants: Dict[str, List[str]] = defaultdict(list)
        self.multi_language_map: Dict[str, Dict[str, List[str]]] = defaultdict(dict)
        # Caching
        self._search_cache: Dict[str, Any] = {}
        self._cache_hits = 0
        self._cache_misses = 0

        # Semantic search components
        self.tfidf_vectorizer: Optional[Any] = None
        self.description_vectors: Optional[Any] = None
        self._semantic_code_ids: List[str] = []

        # Thread pool for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Load data
        self._initialize_data()

    def _initialize_data(self) -> None:
        """Initialize all ICD-10 data structures."""
        try:
            # Create sample data if none exists
            if not self._data_exists():
                self._create_sample_data()

            # Load ICD-10 codes
            self._load_icd10_codes()

            # Build indices
            self._build_indices()

            # Load supplementary data
            self._load_synonyms()
            self._load_abbreviations()
            self._load_clinical_variants()
            self._load_multi_language_data()

            # Initialize semantic search if enabled
            if self.enable_semantic_matching:
                self._initialize_semantic_search()

            self.logger.info(
                "ICD-10 mapper initialized with %d codes", len(self.codes_by_id)
            )

        except Exception as e:
            self.logger.error("Error initializing ICD-10 data: %s", e)
            raise

    def _data_exists(self) -> bool:
        """Check if ICD-10 data files exist."""
        required_files = ["icd10_codes.json", "synonyms.json", "abbreviations.json"]
        return all((self.data_path / f).exists() for f in required_files)

    def _create_sample_data(self) -> None:
        """Create sample ICD-10 data for development."""
        self.logger.info("Creating sample ICD-10 data...")

        # Sample ICD-10 codes
        sample_codes = {
            "A00": {
                "description": "Cholera",
                "category": "Intestinal infectious diseases",
                "is_billable": False,
                "children": ["A00.0", "A00.1", "A00.9"],
            },
            "A00.0": {
                "description": "Cholera due to Vibrio cholerae 01, biovar cholerae",
                "parent": "A00",
                "is_billable": True,
            },
            "A00.1": {
                "description": "Cholera due to Vibrio cholerae 01, biovar eltor",
                "parent": "A00",
                "is_billable": True,
            },
            "A00.9": {
                "description": "Cholera, unspecified",
                "parent": "A00",
                "is_billable": True,
            },
            "J00": {
                "description": "Acute nasopharyngitis [common cold]",
                "category": "Acute upper respiratory infections",
                "is_billable": True,
                "includes": ["Coryza (acute)", "Infective nasopharyngitis NOS"],
                "excludes1": [
                    "Acute pharyngitis (J02.-)",
                    "Acute sore throat NOS (J02.9)",
                ],
            },
            "J45": {
                "description": "Asthma",
                "category": "Chronic lower respiratory diseases",
                "is_billable": False,
                "children": [
                    "J45.0",
                    "J45.1",
                    "J45.2",
                    "J45.3",
                    "J45.4",
                    "J45.5",
                    "J45.9",
                ],
                "use_additional_code": ["to identify tobacco use (Z87.891)"],
            },
            "J45.909": {
                "description": "Unspecified asthma, uncomplicated",
                "parent": "J45.90",
                "is_billable": True,
            },
        }
        # Sample synonyms
        sample_synonyms = {
            "J00": [
                "common cold",
                "cold",
                "head cold",
                "coryza",
                "upper respiratory infection",
                "URI",
            ],
            "J45": [
                "asthma",
                "asthmatic",
                "bronchial asthma",
                "reactive airway disease",
            ],
            "A00": ["cholera", "asiatic cholera", "epidemic cholera"],
        }

        # Sample abbreviations
        sample_abbreviations = {
            "URI": ["J00", "J06"],
            "COPD": ["J44"],
            "CHF": ["I50"],
            "DM": ["E11", "E10"],
            "HTN": ["I10"],
            "CAD": ["I25"],
        }

        # Save sample data
        self.data_path.mkdir(parents=True, exist_ok=True)

        with open(self.data_path / "icd10_codes.json", "w", encoding="utf-8") as f:
            json.dump(sample_codes, f, indent=2)

        with open(self.data_path / "synonyms.json", "w", encoding="utf-8") as f:
            json.dump(sample_synonyms, f, indent=2)

        with open(self.data_path / "abbreviations.json", "w", encoding="utf-8") as f:
            json.dump(sample_abbreviations, f, indent=2)

        # Create empty clinical variants file
        with open(
            self.data_path / "clinical_variants.json", "w", encoding="utf-8"
        ) as f:
            json.dump({}, f)

        # Create multi-language data
        sample_multilang = {
            "es": {
                "J00": ["resfriado común", "catarro", "resfriado"],
                "J45": ["asma", "asma bronquial"],
            },
            "fr": {
                "J00": ["rhume", "rhume de cerveau"],
                "J45": ["asthme", "asthme bronchique"],
            },
        }

        with open(self.data_path / "multilanguage.json", "w", encoding="utf-8") as f:
            json.dump(sample_multilang, f, indent=2)

    def _load_icd10_codes(self) -> None:
        """Load ICD-10 codes from data files."""
        codes_file = self.data_path / "icd10_codes.json"

        try:
            with open(codes_file, "r", encoding="utf-8") as f:
                codes_data = json.load(f)

            for code_id, data in codes_data.items():
                code = ICD10Code(
                    code=code_id,
                    description=data.get("description", ""),
                    category=data.get("category"),
                    parent_code=data.get("parent"),
                    children_codes=data.get("children", []),
                    is_billable=data.get("is_billable", True),
                    excludes1=data.get("excludes1", []),
                    excludes2=data.get("excludes2", []),
                    includes=data.get("includes", []),
                    code_also=data.get("code_also", []),
                    use_additional_code=data.get("use_additional_code", []),
                )

                self.codes_by_id[code_id] = code

                # Build hierarchy
                if code.parent_code:
                    self.hierarchy_tree[code.parent_code].append(code_id)

        except Exception as e:
            self.logger.error("Error loading ICD-10 codes: %s", e)
            raise

    def _build_indices(self) -> None:
        """Build search indices for fast lookup."""
        for code_id, code in self.codes_by_id.items():
            # Index by description words
            words = self._tokenize(code.description.lower())
            for word in words:
                self.description_index[word].append(code_id)

            # Index by code prefix
            for i in range(1, len(code_id) + 1):
                prefix = code_id[:i]
                if prefix not in self.description_index:
                    self.description_index[prefix] = []
                if code_id not in self.description_index[prefix]:
                    self.description_index[prefix].append(code_id)

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
        }
        tokens = [t for t in tokens if len(t) > 2 and t not in stop_words]

        return tokens

    def _load_synonyms(self) -> None:
        """Load synonym mappings."""
        synonyms_file = self.data_path / "synonyms.json"

        try:
            if synonyms_file.exists():
                with open(synonyms_file, "r", encoding="utf-8") as f:
                    self.synonym_map = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning("Error loading synonyms: %s", e)

    def _load_abbreviations(self) -> None:
        """Load medical abbreviation mappings."""
        abbrev_file = self.data_path / "abbreviations.json"

        try:
            if abbrev_file.exists():
                with open(abbrev_file, "r", encoding="utf-8") as f:
                    self.abbreviation_map = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning("Error loading abbreviations: %s", e)

    def _load_clinical_variants(self) -> None:
        """Load clinical variant mappings."""
        variants_file = self.data_path / "clinical_variants.json"

        try:
            if variants_file.exists():
                with open(variants_file, "r", encoding="utf-8") as f:
                    self.clinical_variants = defaultdict(list, json.load(f))
        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning("Error loading clinical variants: %s", e)

    def _load_multi_language_data(self) -> None:
        """Load multi-language mappings."""
        multilang_file = self.data_path / "multilanguage.json"

        try:
            if multilang_file.exists():
                with open(multilang_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for lang, mappings in data.items():
                        self.multi_language_map[lang] = mappings
        except (IOError, json.JSONDecodeError) as e:
            self.logger.warning("Error loading multi-language data: %s", e)

    def _initialize_semantic_search(self) -> None:
        """Initialize semantic search components."""
        if not SEMANTIC_AVAILABLE:
            self.logger.warning(
                "Semantic search not available - scikit-learn not installed"
            )
            return

        try:
            # Collect all descriptions
            descriptions = []
            code_ids = []

            for code_id, code in self.codes_by_id.items():
                descriptions.append(code.description.lower())
                code_ids.append(code_id)

            # Create TF-IDF vectors
            if TfidfVectorizer is None:
                raise ImportError("TfidfVectorizer not available")

            self.tfidf_vectorizer = TfidfVectorizer(
                max_features=5000, ngram_range=(1, 3), stop_words="english"
            )

            if self.tfidf_vectorizer is not None:
                self.description_vectors = self.tfidf_vectorizer.fit_transform(
                    descriptions
                )
            else:
                raise ImportError("TfidfVectorizer initialization failed")
            self._semantic_code_ids = code_ids

        except (ValueError, AttributeError, ImportError) as e:
            self.logger.error("Error initializing semantic search: %s", e)
            self.enable_semantic_matching = False

    def search(
        self,
        query: str,
        include_children: bool = False,
        include_non_billable: bool = True,
        category_filter: Optional[List[str]] = None,
        max_results: Optional[int] = None,
    ) -> ICD10SearchResult:
        """
        Search for ICD-10 codes matching the query.

        Args:
            query: Search query (condition, symptom, code)
            include_children: Include child codes in results
            include_non_billable: Include non-billable codes
            category_filter: Filter by specific categories
            max_results: Override default max results

        Returns:
            ICD10SearchResult with matching codes
        """
        start_time = datetime.now()
        max_results = max_results or self.max_results

        # Normalize query
        query_lower = query.lower().strip()

        # Check cache
        cache_key = (
            f"{query_lower}_{include_children}_{include_non_billable}_{category_filter}"
        )
        if cache_key in self._search_cache:
            self._cache_hits += 1
            cached_result = self._search_cache[cache_key]
            cached_result.processing_time = (
                datetime.now() - start_time
            ).total_seconds()
            return cast(ICD10SearchResult, cached_result)

        self._cache_misses += 1

        # Collect all matches
        all_matches = []

        # 1. Exact code match
        if query_lower in self.codes_by_id:
            code = self.codes_by_id[query_lower]
            code.confidence = 1.0
            code.match_type = MatchType.EXACT
            all_matches.append(code)
        elif query_lower.upper() in self.codes_by_id:
            code = self.codes_by_id[query_lower.upper()]
            code.confidence = 1.0
            code.match_type = MatchType.EXACT
            all_matches.append(code)
        # 2. Code prefix match
        if re.match(r"^[A-Z]\d", query_lower.upper()):
            prefix_query = query_lower.upper()
            for code_id, code in self.codes_by_id.items():
                if code_id.startswith(prefix_query):
                    match_code = code.copy()
                    match_code.confidence = 0.95 if code_id == prefix_query else 0.85
                    match_code.match_type = (
                        MatchType.EXACT
                        if code_id == prefix_query
                        else MatchType.PARTIAL
                    )
                    all_matches.append(match_code)

        # 3. Description word match
        query_tokens = self._tokenize(query_lower)
        for token in query_tokens:
            if token in self.description_index:
                for code_id in self.description_index[token]:
                    code = self.codes_by_id[code_id]
                    match_code = code.copy()

                    # Calculate confidence based on match quality
                    desc_lower = code.description.lower()
                    if query_lower in desc_lower:
                        match_code.confidence = 0.9
                    elif all(t in desc_lower for t in query_tokens):
                        match_code.confidence = 0.85
                    else:
                        match_code.confidence = 0.7

                    match_code.match_type = MatchType.PARTIAL
                    all_matches.append(match_code)

        # 4. Synonym match
        all_matches.extend(self._search_synonyms(query_lower))

        # 5. Abbreviation match
        all_matches.extend(self._search_abbreviations(query_lower))

        # 6. Fuzzy matching
        if self.enable_fuzzy_matching and len(all_matches) < max_results:
            all_matches.extend(
                self._fuzzy_search(query_lower, max_results - len(all_matches))
            )

        # 7. Semantic search
        if self.enable_semantic_matching and len(all_matches) < max_results:
            all_matches.extend(
                self._semantic_search(query_lower, max_results - len(all_matches))
            )
        # Filter and deduplicate
        seen_codes = set()
        filtered_matches = []

        for match in all_matches:
            # Skip if already seen
            if match.code in seen_codes:
                continue

            # Apply filters
            if not include_non_billable and not match.is_billable:
                continue

            if category_filter and match.category not in category_filter:
                continue

            if match.confidence < self.min_confidence:
                continue

            seen_codes.add(match.code)
            filtered_matches.append(match)

            # Add children if requested
            if include_children and match.code in self.hierarchy_tree:
                for child_code_id in self.hierarchy_tree[match.code]:
                    if child_code_id not in seen_codes:
                        child_code = self.codes_by_id[child_code_id]
                        if include_non_billable or child_code.is_billable:
                            child_match = ICD10Code(**child_code.to_dict())
                            child_match.confidence = match.confidence * 0.9
                            child_match.match_type = MatchType.HIERARCHY
                            filtered_matches.append(child_match)
                            seen_codes.add(child_code_id)

        # Sort by confidence and limit results
        filtered_matches.sort(key=lambda x: x.confidence, reverse=True)
        final_matches = filtered_matches[:max_results]

        # Create result
        result = ICD10SearchResult(
            query=query,
            codes=final_matches,
            processing_time=(datetime.now() - start_time).total_seconds(),
            search_metadata={
                "cache_hit": False,
                "total_matches": len(all_matches),
                "filtered_matches": len(filtered_matches),
                "search_methods": self._get_search_methods_used(final_matches),
            },
        )

        # Cache result
        self._search_cache[cache_key] = result

        return result

    def _search_synonyms(self, query: str) -> List[ICD10Code]:
        """Search using synonym mappings."""
        matches = []

        for code_id, synonyms in self.synonym_map.items():
            if code_id not in self.codes_by_id:
                continue

            for synonym in synonyms:
                if query in synonym.lower() or synonym.lower() in query:
                    code = self.codes_by_id[code_id]
                    match_code = code.copy()
                    match_code.confidence = 0.85 if query == synonym.lower() else 0.75
                    match_code.match_type = MatchType.SYNONYM
                    matches.append(match_code)
                    break

        return matches

    def _search_abbreviations(self, query: str) -> List[ICD10Code]:
        """Search using abbreviation mappings."""
        matches = []
        query_upper = query.upper()

        # Check if query is an abbreviation
        if query_upper in self.abbreviation_map:
            for code_id in self.abbreviation_map[query_upper]:
                if code_id in self.codes_by_id:
                    code = self.codes_by_id[code_id]
                    match_code = code.copy()
                    match_code.confidence = 0.9
                    match_code.match_type = MatchType.ABBREVIATION
                    matches.append(match_code)

        # Also check expanded form
        expanded, _ = self.acronym_expander.expand_text(query)
        if expanded != query:
            # Search with expanded form
            expanded_tokens = self._tokenize(expanded.lower())
            for token in expanded_tokens:
                if token in self.description_index:
                    for code_id in self.description_index[token][:5]:  # Limit to top 5
                        code = self.codes_by_id[code_id]
                        match_code = code.copy()
                        match_code.confidence = 0.75
                        match_code.match_type = MatchType.ABBREVIATION
                        matches.append(match_code)

        return matches

    def _fuzzy_search(self, query: str, limit: int) -> List[ICD10Code]:
        """Perform fuzzy string matching."""
        if not FUZZY_AVAILABLE:
            return []

        matches = []

        # Collect all descriptions
        descriptions = [
            (code_id, code.description) for code_id, code in self.codes_by_id.items()
        ]

        # Find fuzzy matches
        fuzzy_matches = process.extract(
            query,
            [desc for _, desc in descriptions],
            scorer=fuzz.token_sort_ratio,
            limit=limit * 2,  # Get more to filter
        )

        for match_desc, score in fuzzy_matches:
            if score < 70:  # Minimum fuzzy match score
                continue

            # Find the code for this description
            for code_id, desc in descriptions:
                if desc == match_desc:
                    code = self.codes_by_id[code_id]
                    match_code = code.copy()
                    match_code.confidence = score / 100 * 0.8  # Scale down fuzzy scores
                    match_code.match_type = MatchType.FUZZY
                    matches.append(match_code)
                    break

            if len(matches) >= limit:
                break

        return matches

    def _semantic_search(self, query: str, limit: int) -> List[ICD10Code]:
        """Perform semantic similarity search."""
        if not SEMANTIC_AVAILABLE:
            return []

        if self.description_vectors is None or self.tfidf_vectorizer is None:
            return []

        try:
            matches = []
            # Vectorize query
            query_vector = self.tfidf_vectorizer.transform([query.lower()])

            # Calculate similarities
            similarities = cosine_similarity(query_vector, self.description_vectors)[0]

            # Get top matches
            top_indices = similarities.argsort()[-limit * 2 :][::-1]
            for idx in top_indices:
                if similarities[idx] < 0.3:  # Minimum semantic similarity
                    continue

                code_id = self._semantic_code_ids[idx]
                code = self.codes_by_id[code_id]
                match_code = ICD10Code(**code.to_dict())
                match_code.confidence = float(similarities[idx]) * 0.85
                match_code.match_type = MatchType.SEMANTIC
                matches.append(match_code)

                if len(matches) >= limit:
                    break

        except (ValueError, AttributeError, ImportError) as e:
            self.logger.error("Error in semantic search: %s", e)

        return matches

    def _get_search_methods_used(self, matches: List[ICD10Code]) -> List[str]:
        """Get list of search methods used in results."""
        methods = set()
        for match in matches:
            methods.add(match.match_type.value)
        return list(methods)

    def get_code(self, code_id: str) -> Optional[ICD10Code]:
        """Get a specific ICD-10 code by ID."""
        return self.codes_by_id.get(code_id.upper())

    def get_children(self, code_id: str) -> List[ICD10Code]:
        """Get all child codes for a given code."""
        children = []

        if code_id in self.hierarchy_tree:
            for child_id in self.hierarchy_tree[code_id]:
                if child_id in self.codes_by_id:
                    children.append(self.codes_by_id[child_id])

        return children

    def get_parent(self, code_id: str) -> Optional[ICD10Code]:
        """Get parent code for a given code."""
        code = self.get_code(code_id)
        if code and code.parent_code:
            return self.get_code(code.parent_code)
        return None

    def get_hierarchy_path(self, code_id: str) -> List[ICD10Code]:
        """Get full hierarchy path from root to code."""
        path: List[ICD10Code] = []
        current = self.get_code(code_id)

        while current:
            path.insert(0, current)
            current = self.get_parent(current.code)

        return path

    def is_billable(self, code_id: str) -> bool:
        """Check if a code is billable."""
        code = self.get_code(code_id)
        return code.is_billable if code else False

    def validate_code(self, code_id: str) -> Tuple[bool, Optional[str]]:
        """Validate an ICD-10 code."""
        code = self.get_code(code_id)

        if not code:
            return False, "Code not found"

        if not code.is_billable:
            return False, "Code is not billable"

        return True, None

    def get_exclusions(self, code_id: str) -> Dict[str, List[str]]:
        """Get exclusion codes for a given code."""
        code = self.get_code(code_id)

        if not code:
            return {}

        return {"excludes1": code.excludes1, "excludes2": code.excludes2}

    def check_code_compatibility(
        self, code1: str, code2: str
    ) -> Tuple[bool, Optional[str]]:
        """Check if two codes can be used together."""
        c1 = self.get_code(code1)
        c2 = self.get_code(code2)

        if not c1 or not c2:
            return False, "One or both codes not found"
        # Check Excludes1 (mutually exclusive)
        if code2 in c1.excludes1 or code1 in c2.excludes1:
            return False, "Codes are mutually exclusive (Excludes1)"

        # Check if one is parent of other (generally not coded together)
        if c1.is_parent_of(code2) or c2.is_parent_of(code1):
            return False, "Parent and child codes should not be coded together"

        return True, None

    async def batch_search(self, queries: List[str]) -> Dict[str, ICD10SearchResult]:
        """Perform batch search for multiple queries."""
        results = {}

        # Use thread pool for parallel processing
        loop = asyncio.get_event_loop()

        tasks = []
        for query in queries:
            task = loop.run_in_executor(self.executor, self.search, query)
            tasks.append((query, task))

        for query, task in tasks:
            try:
                result = await task
                results[query] = result
            except (ValueError, AttributeError, KeyError) as e:
                self.logger.error("Error searching for '%s': %s", query, e)
                results[query] = ICD10SearchResult(
                    query=query,
                    codes=[],
                    processing_time=0,
                    search_metadata={"error": str(e)},
                )

        return results

    def export_mappings(self, output_path: str, output_format: str = "json") -> None:
        """Export ICD-10 mappings to file."""
        data = {
            "codes": {
                code_id: code.to_dict() for code_id, code in self.codes_by_id.items()
            },
            "synonyms": self.synonym_map,
            "abbreviations": self.abbreviation_map,
            "clinical_variants": dict(self.clinical_variants),
        }
        output_file = Path(output_path)

        if output_format == "json":
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        elif output_format == "pickle":
            with open(output_file, "wb") as f:
                pickle.dump(data, f)
        else:
            raise ValueError(f"Unsupported format: {output_format}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get mapper statistics."""
        billable_count = sum(
            1 for code in self.codes_by_id.values() if code.is_billable
        )

        return {
            "total_codes": len(self.codes_by_id),
            "billable_codes": billable_count,
            "non_billable_codes": len(self.codes_by_id) - billable_count,
            "categories": len(
                set(
                    code.category for code in self.codes_by_id.values() if code.category
                )
            ),
            "synonym_mappings": len(self.synonym_map),
            "abbreviation_mappings": len(self.abbreviation_map),
            "languages_supported": len(self.multi_language_map) + 1,  # +1 for English
            "cache_size": len(self._search_cache),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": (
                self._cache_hits / (self._cache_hits + self._cache_misses)
                if (self._cache_hits + self._cache_misses) > 0
                else 0
            ),
        }

    def search_multi_language(self, query: str, language: str) -> ICD10SearchResult:
        """Search using multi-language support."""
        # First try regular search
        result = self.search(query)

        # If no good results and different language, check translations
        if language != "en" and language in self.multi_language_map:
            lang_mappings = self.multi_language_map[language]

            # Check if query matches any translated terms
            for code_id, translations in lang_mappings.items():
                for translation in translations:
                    if query.lower() in translation.lower():
                        if code_id in self.codes_by_id:
                            code = self.codes_by_id[code_id]
                            match_code = code.copy()
                            match_code.confidence = 0.9
                            match_code.match_type = MatchType.EXACT
                            result.codes.insert(0, match_code)

        return result

    def clear_cache(self) -> None:
        """Clear search cache."""
        self._search_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        self.logger.info("Search cache cleared")

    def __del__(self) -> None:
        """Cleanup resources."""
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=False)


# Convenience functions
def create_icd10_mapper(**kwargs: Any) -> ICD10Mapper:
    """Create ICD-10 mapper instance."""
    return ICD10Mapper(**kwargs)
