"""
Phonetic Search for Medical Terms.

This module provides phonetic search capabilities for finding medical terms
even when spelled incorrectly or pronounced differently across languages.
"""

import re
import unicodedata
from dataclasses import dataclass
from difflib import get_close_matches
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import jellyfish  # For phonetic algorithms
from metaphone import doublemetaphone

from src.utils.logging import get_logger

logger = get_logger(__name__)


class PhoneticAlgorithm(str, Enum):
    """Phonetic matching algorithms."""

    SOUNDEX = "soundex"
    METAPHONE = "metaphone"
    DOUBLE_METAPHONE = "double_metaphone"
    NYSIIS = "nysiis"  # New York State Identification and Intelligence System
    MATCH_RATING = "match_rating"
    CAVERPHONE = "caverphone"  # For names/words
    CUSTOM_MEDICAL = "custom_medical"  # Custom for medical terms


@dataclass
class PhoneticMatch:
    """Result of phonetic search."""

    term: str
    code: str  # Medical code (ICD, SNOMED, etc.)
    match_score: float  # 0-1
    algorithm_used: PhoneticAlgorithm
    exact_match: bool
    language: str
    medical_category: Optional[str] = None


@dataclass
class PhoneticRule:
    """Language-specific phonetic rule."""

    language: str
    pattern: str  # Regex pattern
    replacement: str
    description: str
    priority: int = 0  # Higher priority rules applied first


class PhoneticSearchEngine:
    """Phonetic search engine for medical terms."""

    # Common medical term variations
    MEDICAL_VARIATIONS = {
        "diabetes": ["diabetis", "diabeties", "diabetus", "sugar disease"],
        "hypertension": ["high blood pressure", "hypertenshun", "hyper tension"],
        "pneumonia": ["neumonia", "newmonia", "lung infection"],
        "asthma": ["asma", "azma", "breathing problem"],
        "diarrhea": ["diarrhoea", "diarea", "loose motion", "running stomach"],
        "tuberculosis": ["tb", "tuberclosis", "tuburculosis"],
        "malaria": ["maleria", "malarea", "fever disease"],
        "hepatitis": ["hepatitus", "liver disease", "hepa"],
        "arthritis": ["arthritus", "joint pain", "artritis"],
        "migraine": ["migrane", "megraine", "bad headache"],
    }

    # Language-specific phonetic rules
    PHONETIC_RULES = {
        "en": [
            PhoneticRule("en", r"ph", "f", "Replace ph with f", 10),
            PhoneticRule("en", r"ough", "uf", "Simplify ough", 9),
            PhoneticRule("en", r"tion", "shun", "Replace tion", 8),
            PhoneticRule("en", r"sion", "zhun", "Replace sion", 8),
            PhoneticRule("en", r"ght", "t", "Simplify ght", 7),
            PhoneticRule("en", r"kn", "n", "Simplify kn", 6),
            PhoneticRule("en", r"wr", "r", "Simplify wr", 6),
            PhoneticRule("en", r"mb$", "m", "Simplify final mb", 5),
            PhoneticRule("en", r"[aeiou]+", "a", "Simplify vowels", 1),
        ],
        "es": [
            PhoneticRule("es", r"ll", "y", "LL to Y sound", 10),
            PhoneticRule("es", r"h", "", "Silent H", 9),
            PhoneticRule("es", r"v", "b", "V to B", 8),
            PhoneticRule("es", r"z", "s", "Z to S", 7),
            PhoneticRule("es", r"que", "ke", "QUE to KE", 6),
            PhoneticRule("es", r"gui", "gi", "GUI to GI", 6),
            PhoneticRule("es", r"ñ", "ny", "Ñ to NY", 5),
        ],
        "ar": [
            PhoneticRule("ar", r"ة$", "ه", "Ta marbuta to ha", 10),
            PhoneticRule("ar", r"ال", "", "Remove definite article", 9),
            PhoneticRule("ar", r"[ًٌٍَُِّْ]", "", "Remove diacritics", 8),
            PhoneticRule("ar", r"أ|إ|آ", "ا", "Normalize alef", 7),
            PhoneticRule("ar", r"ى", "ي", "Alef maksura to ya", 6),
            PhoneticRule("ar", r"ؤ", "و", "Waw with hamza to waw", 5),
            PhoneticRule("ar", r"ئ", "ي", "Ya with hamza to ya", 5),
        ],
        "hi": [
            PhoneticRule("hi", r"्", "", "Remove virama", 10),
            PhoneticRule("hi", r"ं|ँ", "n", "Anusvara to n", 9),
            PhoneticRule("hi", r"ः", "h", "Visarga to h", 8),
            PhoneticRule("hi", r"क्ष", "ksh", "Ksha", 7),
            PhoneticRule("hi", r"ज्ञ", "gya", "Gya", 7),
            PhoneticRule("hi", r"[ािीुूृेैोौ]", "a", "Simplify vowel marks", 1),
        ],
    }

    # Medical term phonetic mappings
    MEDICAL_PHONETIC_MAP = {
        "en": {
            "newmonia": "pneumonia",
            "diabeetus": "diabetes",
            "hi pressure": "hypertension",
            "hart atak": "heart attack",
            "strok": "stroke",
            "kanser": "cancer",
            "tumr": "tumor",
            "infekshun": "infection",
            "allerji": "allergy",
            "astma": "asthma",
        },
        "es": {
            "neumonia": "pneumonia",
            "dijabetes": "diabetes",
            "ipertension": "hypertension",
            "atake cardiaco": "heart attack",
            "derrame": "stroke",
            "canser": "cancer",
            "infeccion": "infection",
            "alergia": "allergy",
        },
    }

    def __init__(self) -> None:
        """Initialize phonetic search engine."""
        self.medical_terms_db: Dict[str, List[Dict[str, Any]]] = {}
        self.phonetic_index: Dict[str, Set[str]] = {}
        self._build_phonetic_index()

    def _build_phonetic_index(self) -> None:
        """Build phonetic index for medical terms."""
        # In production, would load from medical dictionaries
        sample_terms = [
            {"term": "diabetes", "code": "E11", "type": "ICD-10"},
            {"term": "hypertension", "code": "I10", "type": "ICD-10"},
            {"term": "pneumonia", "code": "J18", "type": "ICD-10"},
            {"term": "asthma", "code": "J45", "type": "ICD-10"},
            {"term": "tuberculosis", "code": "A15", "type": "ICD-10"},
            {"term": "malaria", "code": "B50", "type": "ICD-10"},
            {"term": "hepatitis B", "code": "B16", "type": "ICD-10"},
            {"term": "migraine", "code": "G43", "type": "ICD-10"},
            {"term": "depression", "code": "F32", "type": "ICD-10"},
            {"term": "anxiety", "code": "F41", "type": "ICD-10"},
        ]

        for term_info in sample_terms:
            term = term_info["term"]
            # Generate phonetic keys
            phonetic_keys = self._generate_phonetic_keys(term, "en")

            # Store in index
            for key in phonetic_keys:
                if key not in self.phonetic_index:
                    self.phonetic_index[key] = set()
                self.phonetic_index[key].add(term)

            # Store term info
            if term not in self.medical_terms_db:
                self.medical_terms_db[term] = []
            self.medical_terms_db[term].append(term_info)

    def search(
        self,
        query: str,
        language: str = "en",
        max_results: int = 10,
        min_score: float = 0.6,
        algorithms: Optional[List[PhoneticAlgorithm]] = None,
    ) -> List[PhoneticMatch]:
        """Search for medical terms using phonetic matching."""
        query = query.lower().strip()
        results = []

        # Check direct mapping first
        if language in self.MEDICAL_PHONETIC_MAP:
            if query in self.MEDICAL_PHONETIC_MAP[language]:
                mapped_term = self.MEDICAL_PHONETIC_MAP[language][query]
                if mapped_term in self.medical_terms_db:
                    for term_info in self.medical_terms_db[mapped_term]:
                        results.append(
                            PhoneticMatch(
                                term=mapped_term,
                                code=term_info["code"],
                                match_score=1.0,
                                algorithm_used=PhoneticAlgorithm.CUSTOM_MEDICAL,
                                exact_match=False,
                                language=language,
                                medical_category=term_info.get("type"),
                            )
                        )

        # Apply language-specific preprocessing
        processed_query = self._preprocess_query(query, language)

        # Try exact match first
        if processed_query in self.medical_terms_db:
            for term_info in self.medical_terms_db[processed_query]:
                results.append(
                    PhoneticMatch(
                        term=processed_query,
                        code=term_info["code"],
                        match_score=1.0,
                        algorithm_used=PhoneticAlgorithm.CUSTOM_MEDICAL,
                        exact_match=True,
                        language=language,
                        medical_category=term_info.get("type"),
                    )
                )

        # Use specified algorithms or defaults
        if algorithms is None:
            algorithms = [
                PhoneticAlgorithm.DOUBLE_METAPHONE,
                PhoneticAlgorithm.SOUNDEX,
                PhoneticAlgorithm.CUSTOM_MEDICAL,
            ]

        # Apply phonetic algorithms
        for algorithm in algorithms:
            matches = self._apply_phonetic_algorithm(
                processed_query, language, algorithm
            )

            for match_term, score in matches:
                if score >= min_score and match_term in self.medical_terms_db:
                    for term_info in self.medical_terms_db[match_term]:
                        results.append(
                            PhoneticMatch(
                                term=match_term,
                                code=term_info["code"],
                                match_score=score,
                                algorithm_used=algorithm,
                                exact_match=False,
                                language=language,
                                medical_category=term_info.get("type"),
                            )
                        )

        # Remove duplicates and sort by score
        unique_results: Dict[str, PhoneticMatch] = {}
        for result in results:
            key = f"{result.term}_{result.code}"
            if (
                key not in unique_results
                or result.match_score > unique_results[key].match_score
            ):
                unique_results[key] = result

        final_results = sorted(
            unique_results.values(), key=lambda x: x.match_score, reverse=True
        )

        return final_results[:max_results]

    def _preprocess_query(self, query: str, language: str) -> str:
        """Preprocess query based on language."""
        # Normalize unicode
        query = unicodedata.normalize("NFKD", query)

        # Apply language-specific rules
        if language in self.PHONETIC_RULES:
            rules = sorted(
                self.PHONETIC_RULES[language], key=lambda r: r.priority, reverse=True
            )

            for rule in rules:
                query = re.sub(rule.pattern, rule.replacement, query)

        # Remove extra spaces
        query = " ".join(query.split())

        return query

    def _generate_phonetic_keys(self, term: str, language: str) -> Set[str]:
        """Generate phonetic keys for a term."""
        keys = set()

        # Normalize term
        normalized = self._preprocess_query(term.lower(), language)
        keys.add(normalized)

        # Soundex
        try:
            soundex_key = jellyfish.soundex(normalized)
            keys.add(soundex_key)
        except Exception:
            pass

        # Metaphone
        try:
            metaphone_key = jellyfish.metaphone(normalized)
            if metaphone_key:
                keys.add(metaphone_key)
        except Exception:
            pass

        # Double Metaphone
        try:
            dm_primary, dm_secondary = doublemetaphone(normalized)
            if dm_primary:
                keys.add(dm_primary)
            if dm_secondary:
                keys.add(dm_secondary)
        except Exception:
            pass

        # NYSIIS
        try:
            nysiis_key = jellyfish.nysiis(normalized)
            if nysiis_key:
                keys.add(nysiis_key)
        except Exception:
            pass

        # Custom medical simplification
        medical_key = self._medical_simplification(normalized)
        if medical_key:
            keys.add(medical_key)

        return keys

    def _medical_simplification(self, term: str) -> str:
        """Apply medical-specific simplification."""
        # Remove common medical suffixes
        suffixes = [
            "itis",
            "osis",
            "emia",
            "ology",
            "pathy",
            "ectomy",
            "otomy",
            "plasty",
        ]
        for suffix in suffixes:
            if term.endswith(suffix):
                term = term[: -len(suffix)]
                break

        # Simplify common patterns
        term = re.sub(r"haem", "hem", term)  # British vs American
        term = re.sub(r"oedema", "edema", term)
        term = re.sub(r"anaes", "anes", term)
        term = re.sub(r"paed", "ped", term)

        # Remove spaces and hyphens
        term = re.sub(r"[\s-]", "", term)

        return term

    def _apply_phonetic_algorithm(
        self, query: str, language: str, algorithm: PhoneticAlgorithm
    ) -> List[Tuple[str, float]]:
        """Apply specific phonetic algorithm."""
        matches = []

        if algorithm == PhoneticAlgorithm.SOUNDEX:
            query_soundex = jellyfish.soundex(query)
            for phonetic_key, terms in self.phonetic_index.items():
                if phonetic_key == query_soundex:
                    for term in terms:
                        score = self._calculate_match_score(query, term, algorithm)
                        matches.append((term, score))

        elif algorithm == PhoneticAlgorithm.DOUBLE_METAPHONE:
            query_dm = doublemetaphone(query)
            for phonetic_key, terms in self.phonetic_index.items():
                if phonetic_key in query_dm:
                    for term in terms:
                        score = self._calculate_match_score(query, term, algorithm)
                        matches.append((term, score))

        elif algorithm == PhoneticAlgorithm.CUSTOM_MEDICAL:
            # Use fuzzy matching with medical variations
            all_terms = list(self.medical_terms_db.keys())

            # Add known variations
            for base_term, variations in self.MEDICAL_VARIATIONS.items():
                if base_term in self.medical_terms_db:
                    for variation in variations:
                        if (
                            query.lower() in variation.lower()
                            or variation.lower() in query.lower()
                        ):
                            score = self._calculate_match_score(
                                query, base_term, algorithm
                            )
                            matches.append((base_term, score))

            # Fuzzy matching
            close_matches = get_close_matches(query, all_terms, n=5, cutoff=0.6)
            for match_str in close_matches:
                score = self._calculate_match_score(query, match_str, algorithm)
                matches.append((match_str, score))

        return matches

    def _calculate_match_score(
        self, query: str, matched_term: str, algorithm: PhoneticAlgorithm
    ) -> float:
        """Calculate match score between query and term."""
        # Start with algorithm base score
        algorithm_weights = {
            PhoneticAlgorithm.SOUNDEX: 0.7,
            PhoneticAlgorithm.METAPHONE: 0.75,
            PhoneticAlgorithm.DOUBLE_METAPHONE: 0.8,
            PhoneticAlgorithm.NYSIIS: 0.75,
            PhoneticAlgorithm.CUSTOM_MEDICAL: 0.85,
        }

        base_score = algorithm_weights.get(algorithm, 0.7)

        # Adjust based on string similarity
        levenshtein_score = 1 - (
            jellyfish.levenshtein_distance(query, matched_term)
            / max(len(query), len(matched_term))
        )

        # Weighted average
        final_score = (base_score * 0.6) + (levenshtein_score * 0.4)

        # Boost for exact substring match
        if query in matched_term or matched_term in query:
            final_score = min(1.0, final_score + 0.1)

        return float(round(final_score, 3))

    def add_medical_term(
        self,
        term: str,
        code: str,
        term_type: str,
        language: str = "en",
        variations: Optional[List[str]] = None,
    ) -> None:
        """Add a medical term to the search index."""
        # Add main term
        if term not in self.medical_terms_db:
            self.medical_terms_db[term] = []

        self.medical_terms_db[term].append(
            {"term": term, "code": code, "type": term_type, "language": language}
        )

        # Generate phonetic keys
        phonetic_keys = self._generate_phonetic_keys(term, language)
        for key in phonetic_keys:
            if key not in self.phonetic_index:
                self.phonetic_index[key] = set()
            self.phonetic_index[key].add(term)

        # Add variations
        if variations:
            if term not in self.MEDICAL_VARIATIONS:
                self.MEDICAL_VARIATIONS[term] = []
            self.MEDICAL_VARIATIONS[term].extend(variations)

    def get_term_variations(self, term: str) -> List[str]:
        """Get known variations of a medical term."""
        variations = []

        # Check predefined variations
        if term in self.MEDICAL_VARIATIONS:
            variations.extend(self.MEDICAL_VARIATIONS[term])

        # Check reverse mapping
        for base_term, vars in self.MEDICAL_VARIATIONS.items():
            if term in vars:
                variations.append(base_term)
                variations.extend([v for v in vars if v != term])

        return list(set(variations))

    def suggest_corrections(
        self, query: str, language: str = "en", max_suggestions: int = 5
    ) -> List[str]:
        """Suggest spelling corrections for medical terms."""
        # Search with lower threshold
        matches = self.search(
            query, language, max_results=max_suggestions * 2, min_score=0.5
        )

        # Extract unique terms
        suggestions = []
        seen = set()

        for match in matches:
            if match.term not in seen:
                suggestions.append(match.term)
                seen.add(match.term)

                if len(suggestions) >= max_suggestions:
                    break

        return suggestions


# Global phonetic search engine
phonetic_search = PhoneticSearchEngine()
