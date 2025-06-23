"""
Translation Pipeline Integration.

This module integrates glossary matching with the translation pipeline,
providing seamless term preservation and restoration.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..glossaries import TermPriority, glossary_manager
from .performance_optimizer import OptimizedMatcher, TermMatch

logger = logging.getLogger(__name__)


@dataclass
class TranslationSegment:
    """Represents a segment of text for translation."""

    original_text: str
    prepared_text: str
    preserved_terms: Dict[str, Any]
    matches: List[TermMatch]
    source_lang: str
    target_lang: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TranslationResult:
    """Result of translation with glossary matching."""

    original_text: str
    translated_text: str
    preserved_terms: int
    match_count: int
    confidence_score: float
    warnings: List[str] = field(default_factory=list)
    processing_time: float = 0.0


class GlossaryMatchingPipeline:
    """Integrates glossary matching with translation workflow."""

    def __init__(self, matcher: Optional[OptimizedMatcher] = None):
        """Initialize the pipeline integrator with an optional matcher."""
        self.matcher = matcher or OptimizedMatcher()
        self.preservation_counter = 0

    async def prepare_for_translation(
        self, text: str, source_lang: str, target_lang: str
    ) -> TranslationSegment:
        """Prepare text for translation with glossary matching."""
        # Find all matches
        matches = await self._async_find_matches(text)

        # Analyze medical context
        context = self.matcher.analyze_context(text)

        # Prepare text with preserved terms
        prepared_text, preserved_terms = self._prepare_with_preservation(
            text, matches, source_lang, target_lang
        )

        segment = TranslationSegment(
            original_text=text,
            prepared_text=prepared_text,
            preserved_terms=preserved_terms,
            matches=matches,
            source_lang=source_lang,
            target_lang=target_lang,
            metadata={
                "context": context,
                "timestamp": datetime.utcnow().isoformat(),
                "match_count": len(matches),
            },
        )

        return segment

    async def _async_find_matches(self, text: str) -> List[TermMatch]:
        """Asynchronously find matches."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.matcher.find_matches_optimized, text
        )

    def _prepare_with_preservation(
        self, text: str, matches: List[TermMatch], source_lang: str, target_lang: str
    ) -> Tuple[str, Dict[str, Any]]:
        """Prepare text preserving matched terms."""
        preserved_terms = {}
        prepared_text = text

        # Sort matches by position (reverse to maintain indices)
        matches_to_preserve = [m for m in matches if m.should_preserve]
        matches_to_preserve.sort(key=lambda m: m.start_pos, reverse=True)

        for match in matches_to_preserve:
            # Generate placeholder
            placeholder = f"[[GTERM_{self.preservation_counter}]]"
            self.preservation_counter += 1

            # Get translation if available
            translation = glossary_manager.get_translation(
                match.term.term, source_lang, target_lang
            )

            # Store preservation info
            preserved_terms[placeholder] = {
                "original": match.matched_text,
                "term": match.term.term,
                "translation": translation,
                "category": match.term.category.value,
                "priority": match.term.priority.value,
                "confidence": match.confidence,
                "match_type": (
                    match.match_type.value
                    if hasattr(match.match_type, "value")
                    else match.match_type
                ),
                "position": {"start": match.start_pos, "end": match.end_pos},
            }

            # Replace in text
            prepared_text = (
                prepared_text[: match.start_pos]
                + placeholder
                + prepared_text[match.end_pos :]
            )

        return prepared_text, preserved_terms

    async def restore_after_translation(
        self,
        translated_text: str,
        segment: TranslationSegment,
        use_translations: bool = True,
    ) -> TranslationResult:
        """Restore preserved terms after translation."""
        start_time = datetime.utcnow()
        restored_text = translated_text
        warnings = []

        # Check for missing placeholders
        for placeholder, info in segment.preserved_terms.items():
            if placeholder not in translated_text:
                warnings.append(
                    f"Placeholder {placeholder} for term '{info['term']}' "
                    f"not found in translation"
                )

        # Restore terms
        for placeholder, info in segment.preserved_terms.items():
            if placeholder in restored_text:
                if use_translations and info["translation"]:
                    replacement = info["translation"]
                else:
                    replacement = info["original"]

                restored_text = restored_text.replace(placeholder, replacement)
            else:
                # Try to find approximate location
                warnings.append(
                    f"Could not restore term '{info['term']}' - " f"placeholder missing"
                )

        # Validate restoration
        validation_score = await self._validate_restoration(
            segment.original_text,
            restored_text,
            segment.source_lang,
            segment.target_lang,
        )

        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        return TranslationResult(
            original_text=segment.original_text,
            translated_text=restored_text,
            preserved_terms=len(segment.preserved_terms),
            match_count=len(segment.matches),
            confidence_score=validation_score,
            warnings=warnings,
            processing_time=processing_time,
        )

    async def _validate_restoration(
        self, original: str, translated: str, source_lang: str, target_lang: str
    ) -> float:
        """Validate the quality of term restoration."""
        # Use glossary manager's validation
        validation_result = await glossary_manager.validate_translation_quality(
            original, translated, source_lang, target_lang
        )

        return float(validation_result["score"])

    def create_translation_report(self, result: TranslationResult) -> Dict[str, Any]:
        """Create detailed report of translation with glossary matching."""
        return {
            "summary": {
                "terms_preserved": result.preserved_terms,
                "total_matches": result.match_count,
                "confidence_score": result.confidence_score,
                "has_warnings": len(result.warnings) > 0,
                "processing_time_ms": result.processing_time * 1000,
            },
            "quality_metrics": {
                "term_preservation_rate": (
                    result.preserved_terms / result.match_count
                    if result.match_count > 0
                    else 1.0
                ),
                "confidence_level": self._get_confidence_level(result.confidence_score),
                "warning_count": len(result.warnings),
            },
            "warnings": result.warnings,
            "performance": self.matcher.get_performance_report(),
        }

    def _get_confidence_level(self, score: float) -> str:
        """Convert numeric confidence to level."""
        if score >= 0.95:
            return "very_high"
        elif score >= 0.85:
            return "high"
        elif score >= 0.70:
            return "medium"
        elif score >= 0.50:
            return "low"
        else:
            return "very_low"

    async def batch_prepare(
        self, texts: List[str], source_lang: str, target_lang: str
    ) -> List[TranslationSegment]:
        """Prepare multiple texts for translation."""
        tasks = [
            self.prepare_for_translation(text, source_lang, target_lang)
            for text in texts
        ]
        return await asyncio.gather(*tasks)

    async def batch_restore(
        self,
        translations: List[Tuple[str, TranslationSegment]],
        use_translations: bool = True,
    ) -> List[TranslationResult]:
        """Restore multiple translations."""
        tasks = [
            self.restore_after_translation(trans, segment, use_translations)
            for trans, segment in translations
        ]
        return await asyncio.gather(*tasks)

    def optimize_for_language_pair(self, source_lang: str, target_lang: str) -> None:
        """Optimize matching for specific language pair."""
        # Pre-load translations for common terms
        common_terms = []

        # Get high-priority terms
        # Note: Accessing protected _term_index intentionally for optimization
        for (
            term_list
        ) in self.matcher._term_index.values():  # pylint: disable=protected-access
            for term in term_list:
                if term.priority in [TermPriority.CRITICAL, TermPriority.HIGH]:
                    common_terms.append(term.term)

        # Pre-cache translations
        # Pre-cache translations for string terms only
        for term_str in common_terms[:1000]:  # Limit to top 1000
            if isinstance(term_str, str):
                glossary_manager.get_translation(term_str, source_lang, target_lang)

        logger.info(
            "Pre-cached translations for %d terms for %s -> %s",
            len(common_terms),
            source_lang,
            target_lang,
        )


# Global pipeline instance
matching_pipeline = GlossaryMatchingPipeline()
