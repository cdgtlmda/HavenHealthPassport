"""Mixed directional content handler."""

import unicodedata
from typing import List, Optional

from .types import BidiCharacterType, DirectionType, TextSegment


class MixedContentHandler:
    """Handles mixed directional content (LTR text in RTL context and vice versa)."""

    def __init__(self) -> None:
        """Initialize MixedContentHandler."""
        self.direction_markers = {
            "\u200e": "LRM",  # Left-to-Right Mark
            "\u200f": "RLM",  # Right-to-Left Mark
            "\u202a": "LRE",  # Left-to-Right Embedding
            "\u202b": "RLE",  # Right-to-Left Embedding
            "\u202c": "PDF",  # Pop Directional Format
            "\u202d": "LRO",  # Left-to-Right Override
            "\u202e": "RLO",  # Right-to-Left Override
            "\u2066": "LRI",  # Left-to-Right Isolate
            "\u2067": "RLI",  # Right-to-Left Isolate
            "\u2068": "FSI",  # First Strong Isolate
            "\u2069": "PDI",  # Pop Directional Isolate
        }

    def configure_mixed_content(
        self, text: str, base_direction: DirectionType = DirectionType.LTR
    ) -> str:
        """
        Configure text for proper mixed content display.

        Args:
            text: The input text containing mixed directional content
            base_direction: The base direction of the document

        Returns:
            Text with proper directional markers for mixed content
        """
        segments = self._analyze_text_segments(text)
        return self._apply_directional_markers(segments, base_direction)

    def _analyze_text_segments(self, text: str) -> List[TextSegment]:
        """Analyze text and identify directional segments."""
        segments = []
        current_segment = ""
        current_direction: Optional[DirectionType] = None

        for char in text:
            char_direction = self._get_character_direction(char)

            if current_direction is None:
                current_direction = char_direction
                current_segment = char
            elif (
                char_direction == current_direction
                or char_direction == DirectionType.NEUTRAL
            ):
                current_segment += char
            else:
                # Direction change detected
                if current_segment and current_direction is not None:
                    segments.append(
                        TextSegment(
                            text=current_segment,
                            direction=current_direction,
                            bidi_type=self._get_bidi_type(current_segment),
                        )
                    )
                current_segment = char
                current_direction = char_direction

        # Add the last segment
        if current_segment and current_direction is not None:
            segments.append(
                TextSegment(
                    text=current_segment,
                    direction=current_direction,
                    bidi_type=self._get_bidi_type(current_segment),
                )
            )

        return segments

    def _get_character_direction(self, char: str) -> DirectionType:
        """Determine the direction of a character."""
        bidi_category = unicodedata.bidirectional(char)

        if bidi_category in ["L", "LRE", "LRO", "LRI"]:
            return DirectionType.LTR
        elif bidi_category in ["R", "AL", "RLE", "RLO", "RLI"]:
            return DirectionType.RTL
        elif bidi_category in ["EN", "ES", "ET", "AN", "CS", "NSM", "BN"]:
            return DirectionType.WEAK
        else:
            return DirectionType.NEUTRAL

    def _get_bidi_type(self, text: str) -> BidiCharacterType:
        """Get the predominant bidi type of a text segment."""
        # Simple implementation - returns the type of the first strong character
        for char in text:
            bidi_cat = unicodedata.bidirectional(char)
            if bidi_cat == "L":
                return BidiCharacterType.L
            elif bidi_cat == "R":
                return BidiCharacterType.R
            elif bidi_cat == "AL":
                return BidiCharacterType.AL
        return BidiCharacterType.ON

    def _apply_directional_markers(
        self, segments: List[TextSegment], base_direction: DirectionType
    ) -> str:
        """Apply appropriate directional markers to segments."""
        result = []

        for segment in segments:
            # Check if this segment needs isolation
            needs_isolation = (
                segment.direction != base_direction
                and segment.direction != DirectionType.NEUTRAL
            )

            if needs_isolation:
                # Use isolate markers for better handling
                if segment.direction == DirectionType.RTL:
                    result.append("\u2067")  # RLI
                else:
                    result.append("\u2066")  # LRI

                result.append(segment.text)
                result.append("\u2069")  # PDI
            else:
                result.append(segment.text)

        return "".join(result)

    def get_bidi_type(self, text: str) -> BidiCharacterType:
        """Public method to get the predominant bidi type of a text segment."""
        return self._get_bidi_type(text)

    def analyze_text_segments(self, text: str) -> List[TextSegment]:
        """Public method to analyze text and identify directional segments."""
        return self._analyze_text_segments(text)

    def detect_mixed_content(self, text: str) -> bool:
        """
        Detect if text contains mixed directional content.

        Args:
            text: The text to analyze

        Returns:
            True if text contains both RTL and LTR content
        """
        has_rtl = False
        has_ltr = False

        for char in text:
            direction = self._get_character_direction(char)
            if direction == DirectionType.RTL:
                has_rtl = True
            elif direction == DirectionType.LTR:
                has_ltr = True

            if has_rtl and has_ltr:
                return True

        return False

    def extract_base_direction(self, text: str) -> DirectionType:
        """
        Extract the base direction from text by finding the first strong character.

        Args:
            text: The text to analyze

        Returns:
            The base direction of the text
        """
        for char in text:
            direction = self._get_character_direction(char)
            if direction in [DirectionType.LTR, DirectionType.RTL]:
                return direction

        return DirectionType.LTR  # Default to LTR if no strong characters found
