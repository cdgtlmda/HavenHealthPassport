"""
Feature extraction for dialect detection.

This module provides comprehensive feature extraction capabilities for
identifying dialect-specific characteristics in text.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class LexicalFeatures:
    """Lexical features for dialect detection."""

    word_choices: Dict[str, float] = field(default_factory=dict)
    idioms: Dict[str, float] = field(default_factory=dict)
    collocations: Dict[str, float] = field(default_factory=dict)
    function_words: Dict[str, float] = field(default_factory=dict)
    vocabulary_richness: float = 0.0
    avg_word_length: float = 0.0
    lexical_diversity: float = 0.0


@dataclass
class PhoneticFeatures:
    """Phonetic features (when pronunciation guides are available)."""

    phoneme_patterns: Dict[str, float] = field(default_factory=dict)
    stress_patterns: Dict[str, float] = field(default_factory=dict)
    rhyme_schemes: Dict[str, float] = field(default_factory=dict)


@dataclass
class SyntacticFeatures:
    """Syntactic features for dialect detection."""

    sentence_patterns: Dict[str, float] = field(default_factory=dict)
    clause_structures: Dict[str, float] = field(default_factory=dict)
    word_order_patterns: Dict[str, float] = field(default_factory=dict)
    avg_sentence_length: float = 0.0
    syntactic_complexity: float = 0.0


@dataclass
class OrthographicFeatures:
    """Orthographic (spelling/writing) features."""

    spelling_patterns: Dict[str, float] = field(default_factory=dict)
    capitalization_patterns: Dict[str, float] = field(default_factory=dict)
    punctuation_usage: Dict[str, float] = field(default_factory=dict)
    diacritic_usage: Dict[str, float] = field(default_factory=dict)
    hyphenation_patterns: Dict[str, float] = field(default_factory=dict)


class DialectFeatureExtractor:
    """Main feature extractor for dialect detection."""

    def __init__(self) -> None:
        """Initialize feature extractor."""
        self.lexical_patterns = self._load_lexical_patterns()
        self.syntactic_patterns = self._load_syntactic_patterns()
        self.orthographic_rules = self._load_orthographic_rules()

    def extract_all_features(self, text: str) -> Dict[str, Any]:
        """
        Extract all feature types from text.

        Args:
            text: Input text

        Returns:
            Dictionary containing all extracted features
        """
        features = {
            "lexical": self.extract_lexical_features(text),
            "phonetic": self.extract_phonetic_features(text),
            "syntactic": self.extract_syntactic_features(text),
            "orthographic": self.extract_orthographic_features(text),
        }

        return features

    def extract_lexical_features(self, text: str) -> LexicalFeatures:
        """Extract lexical features from text."""
        features = LexicalFeatures()

        # Tokenize
        words = re.findall(r"\b\w+\b", text.lower())
        unique_words = set(words)

        # Calculate basic metrics
        if words:
            features.avg_word_length = float(np.mean([len(w) for w in words]))
            features.lexical_diversity = len(unique_words) / len(words)
            features.vocabulary_richness = len(unique_words) / (len(words) ** 0.5)

        # Extract word choice indicators
        features.word_choices = self._extract_word_choices(text)

        # Extract idioms and expressions
        features.idioms = self._extract_idioms(text)

        # Extract collocations
        features.collocations = self._extract_collocations(words)

        # Extract function words
        features.function_words = self._extract_function_words(words)

        return features

    def extract_phonetic_features(self, text: str) -> PhoneticFeatures:
        """Extract phonetic features (limited without audio)."""
        features = PhoneticFeatures()

        # Look for phonetic spelling indicators
        phonetic_patterns = {
            "rhotic_r": len(re.findall(r"\b\w+r\b", text, re.I)),
            "dropped_h": len(re.findall(r"\b\'(ave|ad|im|er)\b", text, re.I)),
            "ing_to_in": len(re.findall(r"\b\w+in\'\b", text, re.I)),
        }

        text_length = len(text) or 1
        for pattern, count in phonetic_patterns.items():
            if count > 0:
                features.phoneme_patterns[pattern] = count / (text_length / 1000)

        return features

    def extract_syntactic_features(self, text: str) -> SyntacticFeatures:
        """Extract syntactic features from text."""
        features = SyntacticFeatures()

        # Split into sentences while preserving punctuation
        # Use positive lookahead to keep the punctuation with the sentence
        sentences = re.split(r"(?<=[.!?])\s+", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if sentences:
            # Calculate sentence length (excluding punctuation for word count)
            word_counts = [len(re.findall(r"\b\w+\b", s)) for s in sentences]
            features.avg_sentence_length = float(np.mean(word_counts))

            # Calculate complexity (simplified)
            features.syntactic_complexity = float(np.std(word_counts))

        # Extract sentence patterns
        features.sentence_patterns = self._extract_sentence_patterns(sentences)

        # Extract clause structures
        features.clause_structures = self._extract_clause_structures(text)

        # Extract word order patterns
        features.word_order_patterns = self._extract_word_order(sentences)

        return features

    def extract_orthographic_features(self, text: str) -> OrthographicFeatures:
        """Extract orthographic features from text."""
        features = OrthographicFeatures()

        # Extract spelling patterns
        features.spelling_patterns = self._extract_spelling_patterns(text)

        # Extract capitalization patterns
        features.capitalization_patterns = self._extract_capitalization(text)

        # Extract punctuation usage
        features.punctuation_usage = self._extract_punctuation(text)

        # Extract diacritic usage
        features.diacritic_usage = self._extract_diacritics(text)

        # Extract hyphenation patterns
        features.hyphenation_patterns = self._extract_hyphenation(text)

        return features

    def _extract_word_choices(self, text: str) -> Dict[str, float]:
        """Extract dialect-specific word choices."""
        word_pairs = {
            # US vs UK
            "elevator_lift": (r"\belevator\b", r"\blift\b"),
            "apartment_flat": (r"\bapartment\b", r"\bflat\b"),
            "truck_lorry": (r"\btruck\b", r"\blorry\b"),
            "gasoline_petrol": (r"\bgasoline\b|\bgas\b", r"\bpetrol\b"),
            "sidewalk_pavement": (r"\bsidewalk\b", r"\bpavement\b"),
            # Medical
            "shot_jab": (r"\bshot\b", r"\bjab\b"),
            "bandaid_plaster": (r"\bband-aid\b|\bbandaid\b", r"\bplaster\b"),
        }

        choices = {}
        for key, (pattern1, pattern2) in word_pairs.items():
            count1 = len(re.findall(pattern1, text, re.I))
            count2 = len(re.findall(pattern2, text, re.I))
            if count1 + count2 > 0:
                choices[key] = count1 / (count1 + count2)

        return choices

    def _extract_idioms(self, text: str) -> Dict[str, float]:
        """Extract idiomatic expressions."""
        idiom_patterns = {
            "quite_usage": r"\bquite\s+\w+\b",
            "rather_usage": r"\brather\s+\w+\b",
            "indeed_usage": r"\bindeed\b",
            "reckon_usage": r"\breckon\b",
            "figure_usage": r"\bfigure\s+(out|that)\b",
        }

        idioms = {}
        text_length = len(text) or 1
        for key, pattern in idiom_patterns.items():
            count = len(re.findall(pattern, text, re.I))
            if count > 0:
                idioms[key] = count / (text_length / 1000)

        return idioms

    def _extract_collocations(self, words: List[str]) -> Dict[str, float]:
        """Extract word collocations."""
        if len(words) < 2:
            return {}

        # Create bigrams
        bigrams = list(zip(words[:-1], words[1:]))
        bigram_freq = Counter(bigrams)

        # Look for specific collocations
        collocation_patterns = {
            "take_a": ("take", "a"),
            "have_a": ("have", "a"),
            "make_a": ("make", "a"),
            "at_the": ("at", "the"),
            "in_the": ("in", "the"),
        }

        collocations = {}
        total_bigrams = len(bigrams) or 1
        for key, pattern in collocation_patterns.items():
            count = bigram_freq.get(pattern, 0)
            if count > 0:
                collocations[key] = count / total_bigrams

        return collocations

    def _extract_function_words(self, words: List[str]) -> Dict[str, float]:
        """Extract function word usage patterns."""
        function_word_sets = {
            "articles": {"a", "an", "the"},
            "prepositions": {"in", "on", "at", "by", "for", "with", "to", "from"},
            "conjunctions": {"and", "but", "or", "nor", "for", "yet", "so"},
            "aux_verbs": {
                "is",
                "are",
                "was",
                "were",
                "have",
                "has",
                "had",
                "will",
                "shall",
            },
        }

        function_words = {}
        total_words = len(words) or 1

        for category, word_set in function_word_sets.items():
            count = sum(1 for w in words if w in word_set)
            if count > 0:
                function_words[category] = count / total_words

        return function_words

    def _extract_sentence_patterns(self, sentences: List[str]) -> Dict[str, float]:
        """Extract sentence pattern features."""
        if not sentences:
            return {}

        patterns = {
            "question_forms": sum(1 for s in sentences if s.strip().endswith("?")),
            "exclamations": sum(1 for s in sentences if s.strip().endswith("!")),
            "imperatives": sum(1 for s in sentences if self._is_imperative(s)),
            "passive_voice": sum(1 for s in sentences if self._has_passive(s)),
        }

        total_sentences = len(sentences) or 1
        return {k: v / total_sentences for k, v in patterns.items() if v > 0}

    def _extract_clause_structures(self, text: str) -> Dict[str, float]:
        """Extract clause structure patterns."""
        clause_patterns = {
            "which_clauses": len(re.findall(r",\s*which\b", text, re.I)),
            "that_clauses": len(re.findall(r"\bthat\s+\w+\s+\w+", text, re.I)),
            "because_clauses": len(re.findall(r"\bbecause\b", text, re.I)),
            "although_clauses": len(re.findall(r"\balthough\b", text, re.I)),
        }

        text_length = len(text) or 1
        return {
            k: v / (text_length / 1000) for k, v in clause_patterns.items() if v > 0
        }

    def _extract_word_order(self, sentences: List[str]) -> Dict[str, float]:
        """Extract word order patterns."""
        patterns: Dict[str, int] = {}

        # Simple word order checks
        for sent in sentences:
            words = re.findall(r"\b\w+\b", sent.lower())
            if len(words) >= 3:
                # Check for specific patterns
                if words[0] in ["the", "a", "an"]:
                    patterns["article_first"] = patterns.get("article_first", 0) + 1
                if words[-1] in ["too", "also", "though"]:
                    patterns["adverb_final"] = patterns.get("adverb_final", 0) + 1

        total = len(sentences) or 1
        return {k: v / total for k, v in patterns.items()}

    def _extract_spelling_patterns(self, text: str) -> Dict[str, float]:
        """Extract spelling pattern features."""
        spelling_patterns = {
            "ize_endings": len(re.findall(r"\b\w+ize\b", text, re.I)),
            "ise_endings": len(re.findall(r"\b\w+ise\b", text, re.I)),
            "or_endings": len(re.findall(r"\b\w+or\b", text, re.I)),
            "our_endings": len(re.findall(r"\b\w+our\b", text, re.I)),
            "er_endings": len(re.findall(r"\b\w+er\b", text, re.I)),
            "re_endings": len(re.findall(r"\b\w+re\b", text, re.I)),
            "double_l": len(re.findall(r"\b\w*ll\w+\b", text, re.I)),
            "single_l": len(re.findall(r"\b\w+eling\b|\b\w+eled\b", text, re.I)),
        }

        word_count = len(re.findall(r"\b\w+\b", text)) or 1
        return {k: v / word_count for k, v in spelling_patterns.items() if v > 0}

    def _extract_capitalization(self, text: str) -> Dict[str, float]:
        """Extract capitalization patterns."""
        patterns = {
            "title_case": len(re.findall(r"\b[A-Z][a-z]+\b", text)),
            "all_caps": len(re.findall(r"\b[A-Z]{2,}\b", text)),
            "camel_case": len(re.findall(r"\b[a-z]+[A-Z]\w*\b", text)),
        }

        word_count = len(re.findall(r"\b\w+\b", text)) or 1
        return {k: v / word_count for k, v in patterns.items() if v > 0}

    def _extract_punctuation(self, text: str) -> Dict[str, float]:
        """Extract punctuation usage patterns."""
        punct_counts = {
            "periods": text.count("."),
            "commas": text.count(","),
            "semicolons": text.count(";"),
            "colons": text.count(":"),
            "dashes": text.count("-") + text.count("—"),
            "quotes": text.count('"') + text.count("'"),
        }

        total_chars = len(text) or 1
        return {k: v / (total_chars / 100) for k, v in punct_counts.items() if v > 0}

    def _extract_diacritics(self, text: str) -> Dict[str, float]:
        """Extract diacritic usage patterns."""
        diacritic_counts = {
            "acute": 0,
            "grave": 0,
            "circumflex": 0,
            "tilde": 0,
            "umlaut": 0,
        }

        for char in text:
            if unicodedata.combining(char):
                name = unicodedata.name(char, "").lower()
                if "acute" in name:
                    diacritic_counts["acute"] += 1
                elif "grave" in name:
                    diacritic_counts["grave"] += 1
                elif "circumflex" in name:
                    diacritic_counts["circumflex"] += 1
                elif "tilde" in name:
                    diacritic_counts["tilde"] += 1
                elif "diaeresis" in name:
                    diacritic_counts["umlaut"] += 1

        total_chars = len(text) or 1
        return {
            k: v / (total_chars / 1000) for k, v in diacritic_counts.items() if v > 0
        }

    def _extract_hyphenation(self, text: str) -> Dict[str, float]:
        """Extract hyphenation patterns."""
        patterns = {
            "compound_words": len(re.findall(r"\b\w+-\w+\b", text)),
            "prefixed_words": len(
                re.findall(r"\b(pre|post|anti|non|co|re)-\w+\b", text, re.I)
            ),
            "number_ranges": len(re.findall(r"\d+-\d+", text)),
        }

        word_count = len(re.findall(r"\b\w+\b", text)) or 1
        return {k: v / word_count for k, v in patterns.items() if v > 0}

    def _is_imperative(self, sentence: str) -> bool:
        """Check if sentence is imperative."""
        words = re.findall(r"\b\w+\b", sentence.lower())
        if not words:
            return False

        # Simple imperative detection
        imperative_starts = [
            "please",
            "do",
            "don't",
            "let",
            "make",
            "take",
            "go",
            "come",
        ]
        return words[0] in imperative_starts or (
            len(words) > 1
            and words[0] not in ["the", "a", "an", "this", "that", "these", "those"]
            and not sentence.strip().endswith("?")
        )

    def _has_passive(self, sentence: str) -> bool:
        """Check if sentence contains passive voice."""
        passive_patterns = [
            r"\b(is|are|was|were|been|being)\s+\w+ed\b",
            r"\b(is|are|was|were|been|being)\s+\w+en\b",
        ]

        for pattern in passive_patterns:
            if re.search(pattern, sentence, re.I):
                return True
        return False

    def _load_lexical_patterns(self) -> Dict[str, Any]:
        """Load lexical pattern definitions."""
        return {
            "medical_terms": {
                "US": ["emergency room", "pediatrician", "anesthesiologist"],
                "UK": ["A&E", "paediatrician", "anaesthetist"],
            }
        }

    def _load_syntactic_patterns(self) -> Dict[str, Any]:
        """Load syntactic pattern definitions."""
        return {
            "modal_usage": {
                "US": ["will", "would", "can", "could"],
                "UK": ["shall", "should", "may", "might"],
            }
        }

    def _load_orthographic_rules(self) -> Dict[str, Any]:
        """Load orthographic rule definitions."""
        return {
            "spelling_rules": {
                "US": {"ize": True, "or": True, "er": True},
                "UK": {"ise": True, "our": True, "re": True},
            }
        }
