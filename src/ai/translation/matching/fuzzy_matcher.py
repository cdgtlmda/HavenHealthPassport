"""
Fuzzy Glossary Matcher.

This module provides fuzzy matching capabilities for medical terms,
handling typos, variations, and close matches.
"""

import logging
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Set, Tuple

from .base_matcher import (
    GlossaryMatcher,
    MatchingOptions,
    MatchType,
    MedicalTerm,
    TermMatch,
)

logger = logging.getLogger(__name__)


class FuzzyMatcher(GlossaryMatcher):
    """Fuzzy matching for medical terms with typo tolerance."""

    def __init__(self, options: Optional[MatchingOptions] = None):
        """Initialize the fuzzy matcher with optional configuration."""
        super().__init__(options)
        self._similarity_cache: Dict[Tuple[str, str], float] = {}
        self._build_fuzzy_indices()

    def _build_fuzzy_indices(self) -> None:
        """Build additional indices for fuzzy matching."""
        # Build phonetic index for sound-alike matches
        self._phonetic_index: Dict[str, List[MedicalTerm]] = {}

        # Build n-gram index for partial matches
        self._ngram_index: Dict[str, Set[str]] = {}

        for term_key, terms in self._term_index.items():
            # Add phonetic variations
            phonetic_key = self._get_phonetic_key(term_key)
            for term in terms:
                if phonetic_key not in self._phonetic_index:
                    self._phonetic_index[phonetic_key] = []
                self._phonetic_index[phonetic_key].append(term)

            # Add n-grams
            ngrams = self._get_ngrams(term_key, 3)
            for ngram in ngrams:
                if ngram not in self._ngram_index:
                    self._ngram_index[ngram] = set()
                self._ngram_index[ngram].add(term_key)

    def _get_phonetic_key(self, word: str) -> str:
        """Generate simple phonetic encoding for medical terms."""
        # Basic soundex-like encoding optimized for medical terms
        word = word.lower().strip()

        # Medical-specific replacements
        replacements = [
            (r"ph", "f"),
            (r"sch", "sk"),
            (r"ch", "k"),
            (r"x", "ks"),
            (r"qu", "kw"),
            (r"c(?=[ei])", "s"),
            (r"c", "k"),
            (r"z", "s"),
            (r"y", "i"),
            (r"oo", "u"),
            (r"ee", "i"),
            (r"ae", "e"),
            (r"oe", "e"),
            (r"[aeiou]", ""),  # Remove vowels except first
        ]

        # Keep first letter
        if word:
            first = word[0]
            rest = word[1:]

            for pattern, replacement in replacements:
                rest = re.sub(pattern, replacement, rest)

            # Remove consecutive duplicates
            rest = re.sub(r"(.)\1+", r"\1", rest)

            return first + rest[:6]  # Limit length

        return word

    def _get_ngrams(self, word: str, n: int = 3) -> List[str]:
        """Get n-grams from a word."""
        word = word.lower().strip()
        if len(word) < n:
            return [word]

        ngrams = []
        for i in range(len(word) - n + 1):
            ngrams.append(word[i : i + n])
        return ngrams

    def _calculate_similarity(self, word1: str, word2: str) -> float:
        """Calculate similarity between two words."""
        # Check cache first
        cache_key = (word1, word2) if word1 < word2 else (word2, word1)
        if hasattr(self, "_similarity_cache") and cache_key in self._similarity_cache:
            return self._similarity_cache[cache_key]

        # Use multiple metrics and combine them

        # 1. Sequence matching (good for typos)
        seq_ratio = SequenceMatcher(None, word1.lower(), word2.lower()).ratio()

        # 2. Levenshtein distance normalized
        lev_distance = self._levenshtein_distance(word1.lower(), word2.lower())
        max_len = max(len(word1), len(word2))
        lev_ratio = 1 - (lev_distance / max_len) if max_len > 0 else 0

        # 3. Common prefix/suffix bonus
        prefix_len = len(self._common_prefix(word1, word2))
        suffix_len = len(self._common_suffix(word1, word2))
        affix_bonus = (prefix_len + suffix_len) / (2 * max_len) if max_len > 0 else 0

        # 4. Medical term specific adjustments
        medical_bonus = 0.0
        if self._is_medical_variant(word1, word2):
            medical_bonus = 0.1

        # Combine scores with weights
        similarity = (
            seq_ratio * 0.4 + lev_ratio * 0.4 + affix_bonus * 0.1 + medical_bonus
        )

        result = min(1.0, similarity)

        # Cache the result (limit cache size to prevent memory issues)
        if len(self._similarity_cache) > 10000:
            # Remove oldest entries (simple FIFO)
            self._similarity_cache = dict(list(self._similarity_cache.items())[5000:])
        self._similarity_cache[cache_key] = result

        return result

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
        # Ensure s1 is the longer string for efficiency
        if len(s1) < len(s2):
            s1, s2 = s2, s1

        if len(s2) == 0:
            return len(s1)

        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def _common_prefix(self, s1: str, s2: str) -> str:
        """Find common prefix of two strings."""
        prefix = ""
        for c1, c2 in zip(s1.lower(), s2.lower()):
            if c1 == c2:
                prefix += c1
            else:
                break
        return prefix

    def _common_suffix(self, s1: str, s2: str) -> str:
        """Find common suffix of two strings."""
        return self._common_prefix(s1[::-1], s2[::-1])[::-1]

    def _is_medical_variant(self, word1: str, word2: str) -> bool:
        """Check if words are medical variants of each other."""
        w1, w2 = word1.lower(), word2.lower()

        # Common medical variations
        variations = [
            ("haem", "hem"),  # haemoglobin vs hemoglobin
            ("oedema", "edema"),
            ("anaes", "anes"),  # anaesthesia vs anesthesia
            ("paed", "ped"),  # paediatric vs pediatric
            ("oe", "e"),  # oesophagus vs esophagus
            ("ae", "e"),  # orthopaedic vs orthopedic
            ("ise", "ize"),  # immunise vs immunize
            ("our", "or"),  # tumour vs tumor
        ]

        for brit, amer in variations:
            if (brit in w1 and amer in w2) or (brit in w2 and amer in w1):
                return True

        return False

    def find_fuzzy_matches(
        self, text: str, term_candidates: Optional[List[str]] = None
    ) -> List[TermMatch]:
        """Find fuzzy matches for terms in text."""
        matches = []
        words = re.finditer(r"\b[\w\-\.]+\b", text)

        for word_match in words:
            word = word_match.group()
            word_lower = word.lower()

            # Skip if too short
            if len(word) < 3:
                continue

            # Get candidates based on n-grams
            candidates = self._get_fuzzy_candidates(word_lower)

            # Add specific candidates if provided
            if term_candidates:
                candidates.update(term_candidates)

            # Check each candidate
            for candidate in candidates:
                if candidate == word_lower:
                    continue  # Skip exact matches (handled elsewhere)

                similarity = self._calculate_similarity(word, candidate)

                if similarity >= self.options.fuzzy_threshold:
                    # Get all terms for this candidate
                    terms = self._term_index.get(candidate, [])

                    for term in terms:
                        match = TermMatch(
                            term=term,
                            matched_text=word,
                            start_pos=word_match.start(),
                            end_pos=word_match.end(),
                            match_type=MatchType.FUZZY,
                            confidence=similarity * 0.9,  # Reduce confidence for fuzzy
                            context=self._extract_context(
                                text, word_match.start(), word_match.end()
                            ),
                            matched_variant=candidate,
                        )
                        matches.append(match)

        return matches

    def _get_fuzzy_candidates(self, word: str) -> Set[str]:
        """Get potential fuzzy match candidates for a word."""
        candidates = set()

        # 1. Phonetic matches
        phonetic_key = self._get_phonetic_key(word)
        if phonetic_key in self._phonetic_index:
            for term in self._phonetic_index[phonetic_key]:
                candidates.add(term.term.lower())

        # 2. N-gram based candidates
        ngrams = self._get_ngrams(word, 3)
        ngram_candidates = set()

        for ngram in ngrams:
            if ngram in self._ngram_index:
                ngram_candidates.update(self._ngram_index[ngram])

        # Filter by having enough n-grams in common
        min_common_ngrams = max(1, len(ngrams) // 3)
        for candidate in ngram_candidates:
            candidate_ngrams = set(self._get_ngrams(candidate, 3))
            common_ngrams = len(set(ngrams) & candidate_ngrams)
            if common_ngrams >= min_common_ngrams:
                candidates.add(candidate)

        return candidates

    def find_matches(self, text: str) -> List[TermMatch]:
        """Find all matches including fuzzy matches."""
        # Get base matches
        matches = super().find_matches(text)

        # Add fuzzy matches if enabled
        if self.options.match_fuzzy:
            fuzzy_matches = self.find_fuzzy_matches(text)
            matches.extend(fuzzy_matches)

        # Resolve overlaps again
        matches = self._resolve_overlaps(matches)

        return matches

    def suggest_corrections(
        self, word: str, max_suggestions: int = 5
    ) -> List[Tuple[str, float]]:
        """Suggest corrections for a potentially misspelled medical term."""
        candidates = self._get_fuzzy_candidates(word.lower())

        suggestions = []
        for candidate in candidates:
            similarity = self._calculate_similarity(word, candidate)
            if similarity >= 0.6:  # Lower threshold for suggestions
                suggestions.append((candidate, similarity))

        # Sort by similarity
        suggestions.sort(key=lambda x: x[1], reverse=True)

        return suggestions[:max_suggestions]
