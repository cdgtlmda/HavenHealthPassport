"""Text isolation for bidirectional content."""

import re
from typing import List

from .types import BidiCharacterType, DirectionType, TextSegment


class TextIsolation:
    """
    Implements text isolation for bidirectional content.

    Isolation prevents text from affecting the directionality of surrounding content,
    which is crucial for proper display of mixed-direction text.
    """

    def __init__(self) -> None:
        """Initialize TextIsolation."""
        self.isolation_chars = {
            "lri": "\u2066",  # Left-to-Right Isolate
            "rli": "\u2067",  # Right-to-Left Isolate
            "fsi": "\u2068",  # First Strong Isolate
            "pdi": "\u2069",  # Pop Directional Isolate
        }

    def implement_isolation(self, _text: str, segments: List[TextSegment]) -> str:
        """
        Implement isolation for text segments that need it.

        Args:
            text: Original text
            segments: List of text segments with directional information

        Returns:
            Text with proper isolation markers
        """
        result = []

        for segment in segments:
            if segment.is_isolated or self._needs_isolation(segment, segments):
                # Wrap segment in isolation markers
                if segment.direction == DirectionType.RTL:
                    result.append(self.isolation_chars["rli"])
                elif segment.direction == DirectionType.LTR:
                    result.append(self.isolation_chars["lri"])
                else:
                    result.append(self.isolation_chars["fsi"])

                result.append(segment.text)
                result.append(self.isolation_chars["pdi"])
            else:
                result.append(segment.text)

        return "".join(result)

    def _needs_isolation(
        self, segment: TextSegment, all_segments: List[TextSegment]
    ) -> bool:
        """
        Determine if a segment needs isolation based on context.

        Args:
            segment: The segment to check
            all_segments: All segments in the text

        Returns:
            True if the segment should be isolated
        """
        # Find segment index
        try:
            idx = all_segments.index(segment)
        except ValueError:
            return False

        # Check if surrounded by different direction
        prev_direction = all_segments[idx - 1].direction if idx > 0 else None
        next_direction = (
            all_segments[idx + 1].direction if idx < len(all_segments) - 1 else None
        )

        # Isolate if surrounded by opposite direction
        if prev_direction and next_direction:
            if (
                segment.direction == DirectionType.RTL
                and prev_direction == DirectionType.LTR
                and next_direction == DirectionType.LTR
            ):
                return True
            if (
                segment.direction == DirectionType.LTR
                and prev_direction == DirectionType.RTL
                and next_direction == DirectionType.RTL
            ):
                return True

        # Isolate numbers and weak types between different directions
        if segment.bidi_type in [BidiCharacterType.EN, BidiCharacterType.AN]:
            if prev_direction != next_direction:
                return True

        return False

    def auto_isolate_medical_terms(self, text: str, medical_terms: List[str]) -> str:
        """
        Automatically isolate medical terms to preserve their formatting.

        Args:
            text: The text containing medical terms
            medical_terms: List of medical terms to isolate

        Returns:
            Text with isolated medical terms
        """
        result = text

        for term in medical_terms:
            # Find all occurrences of the term
            pattern = re.escape(term)
            matches = list(re.finditer(pattern, result, re.IGNORECASE))

            # Process from end to beginning to maintain positions
            for match in reversed(matches):
                start, end = match.span()
                isolated_term = (
                    self.isolation_chars["fsi"]
                    + match.group()
                    + self.isolation_chars["pdi"]
                )
                result = result[:start] + isolated_term + result[end:]

        return result
