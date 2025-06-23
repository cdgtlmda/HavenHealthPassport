"""Comprehensive text direction support for Haven Health Passport."""

import re
from typing import Any, Dict, List, Optional, Tuple

from .bidi_algorithm import BidiAlgorithm
from .directional_override import DirectionalOverride
from .mixed_content import MixedContentHandler
from .text_embedding import TextEmbedding
from .text_isolation import TextIsolation
from .types import DirectionType, TextSegment


class TextDirectionSupport:
    """
    Comprehensive text direction support for Haven Health Passport.

    This class integrates all bidirectional text handling components:
    - Mixed content configuration
    - Bidi algorithm implementation
    - Text isolation
    - Text embedding
    - Directional overrides
    """

    def __init__(self) -> None:
        """Initialize TextDirectionSupport."""
        self.mixed_content_handler = MixedContentHandler()
        self.bidi_algorithm = BidiAlgorithm()
        self.text_isolation = TextIsolation()
        self.text_embedding = TextEmbedding()
        self.directional_override = DirectionalOverride()

        # Language direction mapping
        self.rtl_languages = {
            "ar",
            "ara",  # Arabic
            "he",
            "heb",  # Hebrew
            "fa",
            "fas",  # Persian/Farsi
            "ur",
            "urd",  # Urdu
            "ps",
            "pus",  # Pashto
            "sd",
            "snd",  # Sindhi
            "ku",
            "kur",  # Kurdish (some variants)
            "dv",
            "div",  # Dhivehi
            "yi",
            "yid",  # Yiddish
        }

    def process_text(
        self, text: str, language_code: str, options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Process text with full bidirectional support.

        Args:
            text: The text to process
            language_code: ISO language code
            options: Processing options
                - isolate_medical_terms: bool
                - override_numbers: DirectionType
                - auto_detect_direction: bool

        Returns:
            Processed text with proper directional formatting
        """
        options = options or {}

        # Determine base direction
        base_direction = self._get_language_direction(language_code)
        if options.get("auto_detect_direction", False):
            base_direction = self.mixed_content_handler.extract_base_direction(text)

        # Check if text has mixed content
        if self.mixed_content_handler.detect_mixed_content(text):
            # Apply full bidi processing
            text = self.bidi_algorithm.apply_bidi_algorithm(text, base_direction)

            # Configure mixed content
            text = self.mixed_content_handler.configure_mixed_content(
                text, base_direction
            )

        # Handle medical term isolation if requested
        if options.get("isolate_medical_terms") and "medical_terms" in options:
            text = self.text_isolation.auto_isolate_medical_terms(
                text, options["medical_terms"]
            )

        # Handle number direction override if requested
        if "override_numbers" in options:
            text = self.directional_override.override_numbers_direction(
                text, options["override_numbers"]
            )

        return text

    def _get_language_direction(self, language_code: str) -> DirectionType:
        """Get the text direction for a language."""
        # Handle both 2-letter and 3-letter codes
        lang_code = language_code.lower()[:2]
        return (
            DirectionType.RTL if lang_code in self.rtl_languages else DirectionType.LTR
        )

    def get_language_direction(self, language_code: str) -> DirectionType:
        """Public method to get the text direction for a language."""
        return self._get_language_direction(language_code)

    def format_mixed_language_text(self, segments: List[Tuple[str, str]]) -> str:
        """
        Format text containing multiple language segments.

        Args:
            segments: List of (text, language_code) tuples

        Returns:
            Properly formatted multilingual text
        """
        processed_segments = []

        for text, lang_code in segments:
            direction = self._get_language_direction(lang_code)

            # Create text segment
            segment = TextSegment(
                text=text,
                direction=direction,
                bidi_type=self.mixed_content_handler.get_bidi_type(text),
                is_isolated=True,  # Isolate language segments
            )
            processed_segments.append(segment)

        # Apply isolation to all segments
        return self.text_isolation.implement_isolation("", processed_segments)

    def prepare_for_display(self, text: str, display_context: str) -> str:
        """
        Prepare text for specific display contexts.

        Args:
            text: The text to prepare
            display_context: Context like 'web', 'mobile', 'pdf', 'terminal'

        Returns:
            Text prepared for the specific display context
        """
        if display_context == "web":
            # Web browsers handle bidi well, minimal intervention needed
            return text
        elif display_context == "mobile":
            # Mobile may need more explicit markers
            return self._add_explicit_markers(text)
        elif display_context == "pdf":
            # PDFs may need special handling
            return self._prepare_for_pdf(text)
        elif display_context == "terminal":
            # Terminals often have poor bidi support
            return self._prepare_for_terminal(text)
        else:
            return text

    def _add_explicit_markers(self, text: str) -> str:
        """Add explicit directional markers for contexts with limited bidi support."""
        # Add LRM after punctuation in LTR context
        text = re.sub(r"([.!?])\s+", r"\1\u200E ", text)
        # Add RLM after Arabic/Hebrew punctuation
        text = re.sub(r"([؟،؛])\s+", r"\1\u200F ", text)
        return text

    def _prepare_for_pdf(self, text: str) -> str:
        """Prepare text for PDF rendering."""
        # PDFs may need more aggressive isolation
        segments = self.mixed_content_handler.analyze_text_segments(text)
        return self.text_isolation.implement_isolation(text, segments)

    def _prepare_for_terminal(self, text: str) -> str:
        """Prepare text for terminal display."""
        # Many terminals don't support bidi at all
        # This is a simplified approach - real implementation would be more complex
        if self.mixed_content_handler.detect_mixed_content(text):
            # Add visual separators
            text = re.sub(r"(\p{Arabic}+)", r"[\1]", text)
            text = re.sub(r"(\p{Hebrew}+)", r"[\1]", text)
        return text

    def validate_directional_formatting(self, text: str) -> Dict[str, Any]:
        """
        Validate that text has proper directional formatting.

        Returns:
            Validation results with any issues found
        """
        issues = []

        # Check for unpaired directional marks
        lre_count = text.count("\u202a")
        rle_count = text.count("\u202b")
        lro_count = text.count("\u202d")
        rlo_count = text.count("\u202e")
        pdf_count = text.count("\u202c")

        total_embeddings = lre_count + rle_count + lro_count + rlo_count
        if total_embeddings != pdf_count:
            issues.append(
                f"Unpaired directional marks: {total_embeddings} embeddings, {pdf_count} pops"
            )

        # Check for unpaired isolates
        lri_count = text.count("\u2066")
        rli_count = text.count("\u2067")
        fsi_count = text.count("\u2068")
        pdi_count = text.count("\u2069")

        total_isolates = lri_count + rli_count + fsi_count
        if total_isolates != pdi_count:
            issues.append(
                f"Unpaired isolates: {total_isolates} isolates, {pdi_count} pops"
            )

        # Check for excessive nesting
        max_depth = self._calculate_max_nesting_depth(text)
        if max_depth > 10:
            issues.append(f"Excessive nesting depth: {max_depth}")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "stats": {
                "has_mixed_content": self.mixed_content_handler.detect_mixed_content(
                    text
                ),
                "embeddings": total_embeddings,
                "isolates": total_isolates,
                "max_nesting_depth": max_depth,
            },
        }

    def _calculate_max_nesting_depth(self, text: str) -> int:
        """Calculate maximum nesting depth of directional formatting."""
        depth = 0
        max_depth = 0

        for char in text:
            if char in [
                "\u202a",
                "\u202b",
                "\u202d",
                "\u202e",
                "\u2066",
                "\u2067",
                "\u2068",
            ]:
                depth += 1
                max_depth = max(max_depth, depth)
            elif char in ["\u202c", "\u2069"]:
                depth = max(0, depth - 1)

        return max_depth
