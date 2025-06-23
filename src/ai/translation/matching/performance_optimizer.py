"""
Performance-Optimized Glossary Matcher.

This module provides optimized matching for large medical texts with
caching, parallel processing, and efficient data structures.
"""

import hashlib
import logging
import multiprocessing
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Tuple

from ..glossaries import glossary_manager
from .base_matcher import MatchingOptions, MatchType
from .context_matcher import ContextMatcher, MedicalContext, TermMatch

logger = logging.getLogger(__name__)


@dataclass
class MatchingStats:
    """Statistics for matching performance."""

    total_words: int = 0
    total_matches: int = 0
    exact_matches: int = 0
    fuzzy_matches: int = 0
    context_matches: int = 0
    processing_time: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0

    @property
    def words_per_second(self) -> float:
        """Calculate processing speed."""
        if self.processing_time > 0:
            return self.total_words / self.processing_time
        return 0

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total_lookups = self.cache_hits + self.cache_misses
        if total_lookups > 0:
            return self.cache_hits / total_lookups
        return 0


class OptimizedMatcher(ContextMatcher):
    """Performance-optimized matcher for large texts."""

    def __init__(
        self,
        options: Optional[MatchingOptions] = None,
        max_cache_size: int = 10000,
        enable_parallel: bool = True,
    ):
        """Initialize the optimized matcher with configuration."""
        super().__init__(options)
        self.max_cache_size = max_cache_size
        self.enable_parallel = enable_parallel
        self._match_cache: Dict[str, List[TermMatch]] = {}
        self._context_cache: Dict[str, MedicalContext] = {}
        self.stats = MatchingStats()
        self._precompile_patterns()

    def _precompile_patterns(self) -> None:
        """Precompile regex patterns for common terms."""
        self._compiled_patterns = {}

        # Compile patterns for high-frequency terms
        high_freq_terms = [
            term
            for term_list in self._term_index.values()
            for term in term_list
            if term.priority in ["critical", "high"]
        ]

        for term in high_freq_terms[:1000]:  # Limit to top 1000
            if not term.case_sensitive:
                pattern = re.compile(rf"\b{re.escape(term.term)}\b", re.IGNORECASE)
            else:
                pattern = re.compile(rf"\b{re.escape(term.term)}\b")
            self._compiled_patterns[term.term] = pattern

        logger.info("Precompiled %d patterns", len(self._compiled_patterns))

    def find_matches_optimized(
        self, text: str, chunk_size: int = 5000
    ) -> List[TermMatch]:
        """Find matches with optimization for large texts."""
        start_time = time.time()

        # Check cache first
        text_hash = self._get_text_hash(text)
        if text_hash in self._match_cache:
            self.stats.cache_hits += 1
            logger.debug("Cache hit for text hash %s", text_hash)
            return self._match_cache[text_hash].copy()

        self.stats.cache_misses += 1

        # Process in chunks for very large texts
        if len(text) > chunk_size and self.enable_parallel:
            matches = self._parallel_match(text, chunk_size)
        else:
            matches = self._sequential_match(text)

        # Cache results
        self._cache_matches(text_hash, matches)

        # Update stats
        self.stats.processing_time += time.time() - start_time
        self.stats.total_words += len(text.split())
        self.stats.total_matches += len(matches)

        return matches

    def _get_text_hash(self, text: str) -> str:
        """Get hash of text for caching."""
        return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()

    def _cache_matches(self, text_hash: str, matches: List[TermMatch]) -> None:
        """Cache matches with size limit."""
        if len(self._match_cache) >= self.max_cache_size:
            # Remove oldest entries (simple FIFO)
            oldest_key = next(iter(self._match_cache))
            del self._match_cache[oldest_key]

        self._match_cache[text_hash] = matches.copy()

    def _sequential_match(self, text: str) -> List[TermMatch]:
        """Sequential matching for smaller texts."""
        # Use precompiled patterns for efficiency
        matches = []

        # First pass: Use compiled patterns for high-priority terms
        for term_text, pattern in self._compiled_patterns.items():
            for match in pattern.finditer(text):
                terms = self._term_index.get(term_text.lower(), [])
                for term in terms:
                    if term.term == term_text or term_text in term.aliases:
                        term_match = TermMatch(
                            term=term,
                            matched_text=match.group(),
                            start_pos=match.start(),
                            end_pos=match.end(),
                            match_type=MatchType.EXACT,
                            confidence=1.0,
                            context=self._extract_context(
                                text, match.start(), match.end()
                            ),
                        )
                        matches.append(term_match)
                        self.stats.exact_matches += 1

        # Second pass: Regular matching for remaining terms
        additional_matches = super().find_matches(text)

        # Merge and deduplicate
        all_matches = matches + additional_matches
        return self._deduplicate_matches(all_matches)

    def _parallel_match(self, text: str, chunk_size: int) -> List[TermMatch]:
        """Parallel matching for large texts."""
        chunks = self._create_text_chunks(text, chunk_size)
        matches = []

        # Determine number of workers
        num_workers = min(multiprocessing.cpu_count(), len(chunks))

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit chunks for processing
            future_to_chunk = {
                executor.submit(self._process_chunk, chunk, offset): (chunk, offset)
                for chunk, offset in chunks
            }

            # Collect results
            for future in as_completed(future_to_chunk):
                chunk_matches = future.result()
                matches.extend(chunk_matches)

        # Sort by position
        matches.sort(key=lambda m: m.start_pos)

        return self._deduplicate_matches(matches)

    def _create_text_chunks(self, text: str, chunk_size: int) -> List[Tuple[str, int]]:
        """Create overlapping chunks to avoid missing matches at boundaries."""
        chunks = []
        overlap = 100  # Characters of overlap

        i = 0
        while i < len(text):
            # Find a good break point (word boundary)
            end = min(i + chunk_size, len(text))
            if end < len(text):
                # Look for word boundary
                space_pos = text.rfind(" ", i, end)
                if space_pos > i:
                    end = space_pos

            chunk = text[i:end]
            chunks.append((chunk, i))

            # Move to next chunk with overlap
            i = end - overlap if end < len(text) else end

        return chunks

    def _process_chunk(self, chunk: str, offset: int) -> List[TermMatch]:
        """Process a single chunk of text."""
        # Create a new matcher instance to avoid thread conflicts
        chunk_matcher = ContextMatcher(self.options)
        chunk_matches = chunk_matcher.find_matches(chunk)

        # Adjust positions for chunk offset
        for match in chunk_matches:
            match.start_pos += offset
            match.end_pos += offset

        return chunk_matches

    def _deduplicate_matches(self, matches: List[TermMatch]) -> List[TermMatch]:
        """Remove duplicate matches efficiently."""
        seen: Dict[Tuple[int, int, str], TermMatch] = {}
        unique_matches = []

        for match in matches:
            key = (match.start_pos, match.end_pos, match.term.term)
            if key not in seen or match.confidence > seen[key].confidence:
                seen[key] = match

        # Extract unique matches
        unique_matches = list(seen.values())
        unique_matches.sort(key=lambda m: m.start_pos)

        return unique_matches

    def batch_match(self, texts: List[str]) -> List[List[TermMatch]]:
        """Match multiple texts efficiently."""
        results = []

        if self.enable_parallel and len(texts) > 1:
            with ThreadPoolExecutor(
                max_workers=multiprocessing.cpu_count()
            ) as executor:
                futures = [
                    executor.submit(self.find_matches_optimized, text) for text in texts
                ]

                for future in as_completed(futures):
                    results.append(future.result())
        else:
            for text in texts:
                results.append(self.find_matches_optimized(text))

        return results

    def stream_match(
        self, text_stream: Iterator[str], buffer_size: int = 1000
    ) -> Iterator[List[TermMatch]]:
        """Stream matching for very large documents."""
        buffer = ""

        for chunk in text_stream:
            buffer += chunk

            # Process when buffer is large enough
            if len(buffer) >= buffer_size:
                # Find last complete sentence
                last_period = buffer.rfind(".")
                if last_period > 0:
                    process_text = buffer[: last_period + 1]
                    buffer = buffer[last_period + 1 :]

                    yield self.find_matches_optimized(process_text)

        # Process remaining buffer
        if buffer:
            yield self.find_matches_optimized(buffer)

    def get_performance_report(self) -> Dict[str, Any]:
        """Get detailed performance statistics."""
        return {
            "total_words_processed": self.stats.total_words,
            "total_matches_found": self.stats.total_matches,
            "match_breakdown": {
                "exact": self.stats.exact_matches,
                "fuzzy": self.stats.fuzzy_matches,
                "contextual": self.stats.context_matches,
            },
            "performance": {
                "total_time_seconds": self.stats.processing_time,
                "words_per_second": self.stats.words_per_second,
                "avg_time_per_word_ms": (
                    (self.stats.processing_time * 1000 / self.stats.total_words)
                    if self.stats.total_words > 0
                    else 0
                ),
            },
            "cache": {
                "hits": self.stats.cache_hits,
                "misses": self.stats.cache_misses,
                "hit_rate": self.stats.cache_hit_rate,
                "cache_size": len(self._match_cache),
            },
        }

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._match_cache.clear()
        self._context_cache.clear()
        self.stats = MatchingStats()
        logger.info("Cleared all caches and reset statistics")

    def optimize_for_domain(self, domain: str) -> None:
        """Optimize matcher for specific medical domain."""
        # Load domain-specific glossary to front of index
        if domain in glossary_manager.domain_glossaries:
            domain_glossary = glossary_manager.domain_glossaries[domain]

            # Recompile patterns for domain terms
            domain_patterns = {}
            for term in domain_glossary.terms.values():
                if term.priority in ["critical", "high"]:
                    pattern = re.compile(
                        rf"\b{re.escape(term.term)}\b",
                        re.IGNORECASE if not term.case_sensitive else 0,
                    )
                    domain_patterns[term.term] = pattern

            # Prepend to compiled patterns
            self._compiled_patterns = {**domain_patterns, **self._compiled_patterns}

            logger.info(
                "Optimized for %s domain with %d patterns", domain, len(domain_patterns)
            )
