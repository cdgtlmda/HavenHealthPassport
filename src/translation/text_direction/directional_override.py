"""Directional override functionality."""

import re
from typing import List, Tuple

from .types import DirectionType


class DirectionalOverride:
    """
    Implements directional override functionality.

    Override forces text to be treated as a specific direction regardless
    of the actual character types.
    """

    def __init__(self) -> None:
        """Initialize DirectionalOverride."""
        self.override_chars = {
            "lro": "\u202d",  # Left-to-Right Override
            "rlo": "\u202e",  # Right-to-Left Override
            "pdf": "\u202c",  # Pop Directional Format
        }

    def setup_overrides(
        self, text: str, override_regions: List[Tuple[int, int, DirectionType]]
    ) -> str:
        """
        Set up directional overrides for specified text regions.

        Args:
            text: The original text
            override_regions: List of (start, end, direction) tuples

        Returns:
            Text with override markers
        """
        # Sort regions by start position
        sorted_regions = sorted(override_regions, key=lambda x: x[0])

        result = []
        last_pos = 0

        for start, end, direction in sorted_regions:
            # Add text before this region
            result.append(text[last_pos:start])

            # Add override marker
            if direction == DirectionType.LTR:
                result.append(self.override_chars["lro"])
            else:
                result.append(self.override_chars["rlo"])

            # Add overridden text
            result.append(text[start:end])

            # Add pop marker
            result.append(self.override_chars["pdf"])

            last_pos = end

        # Add remaining text
        result.append(text[last_pos:])

        return "".join(result)

    def override_numbers_direction(self, text: str, direction: DirectionType) -> str:
        """
        Override the direction of all numbers in the text.

        Args:
            text: The text containing numbers
            direction: The direction to force for numbers

        Returns:
            Text with numbers displayed in specified direction
        """
        # Find all number sequences
        number_pattern = r"\d+(?:[.,]\d+)*"
        matches = list(re.finditer(number_pattern, text))

        if not matches:
            return text

        # Process from end to beginning
        result = text
        for match in reversed(matches):
            start, end = match.span()

            # Wrap number in override
            override_marker = (
                self.override_chars["lro"]
                if direction == DirectionType.LTR
                else self.override_chars["rlo"]
            )
            overridden_number = (
                override_marker + match.group() + self.override_chars["pdf"]
            )

            result = result[:start] + overridden_number + result[end:]

        return result
