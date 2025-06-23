"""Text direction types and enums."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DirectionType(Enum):
    """Text direction types."""

    LTR = "ltr"
    RTL = "rtl"
    NEUTRAL = "neutral"
    WEAK = "weak"


class BidiCharacterType(Enum):
    """Unicode Bidirectional Character Types."""

    # Strong types
    L = "Left-to-Right"  # Latin letters
    R = "Right-to-Left"  # Arabic, Hebrew letters
    AL = "Arabic Letter"  # Arabic letters specifically

    # Weak types
    EN = "European Number"  # European digits 0-9
    ES = "European Separator"  # Plus/minus signs
    ET = "European Terminator"  # Currency symbols, percent
    AN = "Arabic Number"  # Arabic-Indic digits
    CS = "Common Separator"  # Colon, comma
    NSM = "Non-Spacing Mark"  # Combining marks
    BN = "Boundary Neutral"  # Control characters

    # Neutral types
    B = "Paragraph Separator"  # Line/paragraph separators
    S = "Segment Separator"  # Tab
    WS = "Whitespace"  # Space, etc.
    ON = "Other Neutral"  # Other punctuation

    # Explicit formatting
    LRE = "Left-to-Right Embedding"
    RLE = "Right-to-Left Embedding"
    LRO = "Left-to-Right Override"
    RLO = "Right-to-Left Override"
    PDF = "Pop Directional Format"
    LRI = "Left-to-Right Isolate"
    RLI = "Right-to-Left Isolate"
    FSI = "First Strong Isolate"
    PDI = "Pop Directional Isolate"


@dataclass
class TextSegment:
    """Represents a segment of text with direction properties."""

    text: str
    direction: DirectionType
    bidi_type: BidiCharacterType
    embedding_level: int = 0
    is_isolated: bool = False
    override_direction: Optional[DirectionType] = None
