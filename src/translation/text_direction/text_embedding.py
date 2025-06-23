"""Text embedding for directional control."""

from typing import List, Tuple

from .types import DirectionType


class TextEmbedding:
    """
    Implements text embedding for directional control.

    Embedding allows changing the direction of a text segment while maintaining
    the ability to return to the previous direction.
    """

    def __init__(self) -> None:
        """Initialize TextEmbedding."""
        self.embedding_chars = {
            "lre": "\u202a",  # Left-to-Right Embedding
            "rle": "\u202b",  # Right-to-Left Embedding
            "pdf": "\u202c",  # Pop Directional Format
        }
        self.embedding_stack: list[str] = []

    def configure_embedding(
        self, text: str, embedding_regions: List[Tuple[int, int, DirectionType]]
    ) -> str:
        """
        Configure text with embedding markers for specified regions.

        Args:
            text: The original text
            embedding_regions: List of (start, end, direction) tuples

        Returns:
            Text with embedding markers
        """
        # Sort regions by start position
        sorted_regions = sorted(embedding_regions, key=lambda x: x[0])

        result = []
        last_pos = 0

        for start, end, direction in sorted_regions:
            # Add text before this region
            result.append(text[last_pos:start])

            # Add embedding marker
            if direction == DirectionType.LTR:
                result.append(self.embedding_chars["lre"])
            else:
                result.append(self.embedding_chars["rle"])

            # Add embedded text
            result.append(text[start:end])

            # Add pop marker
            result.append(self.embedding_chars["pdf"])

            last_pos = end

        # Add remaining text
        result.append(text[last_pos:])

        return "".join(result)

    def create_nested_embedding(self, segments: List[Tuple[str, DirectionType]]) -> str:
        """
        Create text with nested embedding levels.

        Args:
            segments: List of (text, direction) tuples

        Returns:
            Text with proper nested embedding
        """
        result = []
        embedding_depth = 0

        for text, direction in segments:
            # Check if we need to change direction
            current_direction = self._get_current_direction(embedding_depth)

            if direction != current_direction:
                # Push new embedding
                if direction == DirectionType.LTR:
                    result.append(self.embedding_chars["lre"])
                else:
                    result.append(self.embedding_chars["rle"])
                embedding_depth += 1

            result.append(text)

            # Pop embedding if we added one
            if direction != current_direction:
                result.append(self.embedding_chars["pdf"])
                embedding_depth -= 1

        return "".join(result)

    def _get_current_direction(self, embedding_depth: int) -> DirectionType:
        """Get current direction based on embedding depth."""
        # Even depth = LTR, Odd depth = RTL (simplified)
        return DirectionType.LTR if embedding_depth % 2 == 0 else DirectionType.RTL
