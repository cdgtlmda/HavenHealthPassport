"""Unicode Bidirectional Algorithm implementation."""

import unicodedata
from typing import List, Tuple

from .mixed_content import MixedContentHandler
from .types import DirectionType


class BidiAlgorithm:
    """
    Implementation of the Unicode Bidirectional Algorithm (UBA).

    This implements a simplified version of the Unicode Bidirectional Algorithm
    for proper rendering of mixed directional text.
    """

    def __init__(self) -> None:
        """Initialize BidiAlgorithm."""
        self.mixed_content_handler = MixedContentHandler()
        self.max_depth = 125  # Maximum embedding depth as per Unicode standard

    def apply_bidi_algorithm(
        self, text: str, base_direction: DirectionType = DirectionType.LTR
    ) -> str:
        """
        Apply the Unicode Bidirectional Algorithm to text.

        Args:
            text: Input text to process
            base_direction: Base direction of the paragraph

        Returns:
            Text with proper directional formatting
        """
        # Step 1: Determine paragraph direction
        paragraph_direction = self._determine_paragraph_direction(text, base_direction)

        # Step 2: Compute embedding levels
        embedding_levels = self._compute_embedding_levels(text, paragraph_direction)

        # Step 3: Resolve neutral and weak types
        resolved_types = self._resolve_neutral_weak_types(text, embedding_levels)

        # Step 4: Apply directional runs
        directional_runs = self._identify_directional_runs(
            text, embedding_levels, resolved_types
        )

        # Step 5: Reorder text based on levels
        reordered_text = self._reorder_text(text, directional_runs, embedding_levels)

        return reordered_text

    def _determine_paragraph_direction(
        self, text: str, base_direction: DirectionType
    ) -> DirectionType:
        """Determine the paragraph direction (P2-P3 of UBA)."""
        # Look for first strong character
        for char in text:
            bidi_cat = unicodedata.bidirectional(char)
            if bidi_cat in ["L", "AL", "R"]:
                if bidi_cat == "L":
                    return DirectionType.LTR
                else:
                    return DirectionType.RTL

        return base_direction

    def _compute_embedding_levels(
        self, text: str, paragraph_direction: DirectionType
    ) -> List[int]:
        """
        Compute embedding levels for each character (X1-X10 of UBA).

        Returns:
            List of embedding levels for each character
        """
        length = len(text)
        levels = [0] * length
        base_level = 0 if paragraph_direction == DirectionType.LTR else 1

        # Initialize all characters to base embedding level
        for i in range(length):
            levels[i] = base_level

        # Stack for tracking embedding/override status
        directional_status_stack = [(base_level, "neutral")]
        current_level = base_level

        for i, char in enumerate(text):
            # Handle explicit directional embeddings and overrides
            if char == "\u202a":  # LRE
                if current_level < self.max_depth:
                    current_level = (
                        (current_level + 1) // 2
                    ) * 2 + 2  # Next even level
                    directional_status_stack.append((current_level, "neutral"))
            elif char == "\u202b":  # RLE
                if current_level < self.max_depth:
                    current_level = ((current_level + 2) // 2) * 2 + 1  # Next odd level
                    directional_status_stack.append((current_level, "neutral"))
            elif char == "\u202d":  # LRO
                if current_level < self.max_depth:
                    current_level = (
                        (current_level + 1) // 2
                    ) * 2 + 2  # Next even level
                    directional_status_stack.append((current_level, "LTR"))
            elif char == "\u202e":  # RLO
                if current_level < self.max_depth:
                    current_level = ((current_level + 2) // 2) * 2 + 1  # Next odd level
                    directional_status_stack.append((current_level, "RTL"))
            elif char == "\u202c":  # PDF
                if len(directional_status_stack) > 1:
                    directional_status_stack.pop()
                    current_level, _ = directional_status_stack[-1]

            levels[i] = current_level

        return levels

    def _resolve_neutral_weak_types(
        self, text: str, embedding_levels: List[int]
    ) -> List[str]:
        """
        Resolve neutral and weak character types (W1-W7, N1-N2 of UBA).

        Returns:
            List of resolved bidi types for each character
        """
        resolved_types = []
        prev_strong_type = "L" if embedding_levels[0] % 2 == 0 else "R"

        for i, char in enumerate(text):
            bidi_cat = unicodedata.bidirectional(char)

            # Strong types remain unchanged
            if bidi_cat in ["L", "R", "AL"]:
                resolved_types.append(bidi_cat)
                prev_strong_type = bidi_cat
            # European numbers in Arabic context become Arabic numbers
            elif bidi_cat == "EN" and prev_strong_type == "AL":
                resolved_types.append("AN")
            # Neutral types take the direction of surrounding text
            elif bidi_cat in ["WS", "ON", "B", "S"]:
                # Look ahead to find next strong type
                next_strong_type = None
                for j in range(i + 1, len(text)):
                    next_bidi = unicodedata.bidirectional(text[j])
                    if next_bidi in ["L", "R", "AL"]:
                        next_strong_type = next_bidi
                        break

                # If surrounded by same type, adopt that type
                if prev_strong_type == next_strong_type:
                    resolved_types.append(prev_strong_type)
                else:
                    # Otherwise, use embedding direction
                    resolved_types.append("L" if embedding_levels[i] % 2 == 0 else "R")
            else:
                resolved_types.append(bidi_cat)

        return resolved_types

    def _identify_directional_runs(
        self, text: str, levels: List[int], _types: List[str]
    ) -> List[Tuple[int, int, int]]:
        """
        Identify contiguous runs of characters with the same embedding level.

        Returns:
            List of tuples (start_index, end_index, level)
        """
        runs = []
        start = 0
        current_level = levels[0]

        for i in range(1, len(text)):
            if levels[i] != current_level:
                runs.append((start, i - 1, current_level))
                start = i
                current_level = levels[i]

        # Add the last run
        runs.append((start, len(text) - 1, current_level))

        return runs

    def _reorder_text(
        self, text: str, runs: List[Tuple[int, int, int]], levels: List[int]
    ) -> str:
        """
        Reorder text based on embedding levels (L1-L4 of UBA).

        Args:
            text: Original text
            runs: Directional runs identified
            levels: Embedding levels for each character

        Returns:
            Reordered text
        """
        # Find highest level
        max_level = max(levels)

        # Process from highest level to lowest
        text_array = list(text)

        for level in range(max_level, -1, -1):
            # Find runs at this level
            for start, end, run_level in runs:
                if run_level >= level:
                    # Reverse RTL runs (odd levels)
                    if level % 2 == 1:
                        text_array[start : end + 1] = text_array[start : end + 1][::-1]

        return "".join(text_array)
