"""
Text Direction Support Module.

This module provides comprehensive support for bidirectional text handling,
including mixed content, bidi algorithm implementation, isolation, embedding,
and override functionality for proper RTL/LTR text rendering.
"""

from .bidi_algorithm import BidiAlgorithm
from .directional_override import DirectionalOverride
from .mixed_content import MixedContentHandler
from .text_direction_support import TextDirectionSupport
from .text_embedding import TextEmbedding
from .text_isolation import TextIsolation
from .types import BidiCharacterType, DirectionType, TextSegment
from .utils import (
    add_direction_mark,
    is_rtl_language,
    strip_directional_marks,
)

__all__ = [
    "BidiCharacterType",
    "DirectionType",
    "TextSegment",
    "MixedContentHandler",
    "BidiAlgorithm",
    "TextIsolation",
    "TextEmbedding",
    "DirectionalOverride",
    "TextDirectionSupport",
    "add_direction_mark",
    "is_rtl_language",
    "strip_directional_marks",
]
