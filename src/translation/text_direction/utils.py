"""Utility functions for text direction support."""

from .text_direction_support import TextDirectionSupport
from .types import DirectionType


def is_rtl_language(language_code: str) -> bool:
    """Check if a language is RTL."""
    support = TextDirectionSupport()
    return support.get_language_direction(language_code) == DirectionType.RTL


def add_direction_mark(
    text: str, position: str = "start", direction: str = "ltr"
) -> str:
    """
    Add directional mark to text.

    Args:
        text: The text to mark
        position: Where to add mark ('start', 'end', 'both')
        direction: Direction ('ltr' or 'rtl')

    Returns:
        Text with directional marks
    """
    lrm = "\u200e"
    rlm = "\u200f"
    mark = lrm if direction == "ltr" else rlm

    if position == "start":
        return mark + text
    elif position == "end":
        return text + mark
    elif position == "both":
        return mark + text + mark
    else:
        return text


def strip_directional_marks(text: str) -> str:
    """Remove all directional formatting characters from text."""
    # All directional formatting characters
    directional_chars = [
        "\u200e",
        "\u200f",  # LRM, RLM
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",  # LRE, RLE, PDF, LRO, RLO
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",  # LRI, RLI, FSI, PDI
    ]

    for char in directional_chars:
        text = text.replace(char, "")

    return text
