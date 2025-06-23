"""Text Splitters for Haven Health Passport.

Specialized text splitting strategies for medical documents that preserve
context, maintain semantic coherence, and respect medical terminology.
"""

from .base import BaseMedicalSplitter, ChunkMetadata, SplitResult, TextSplitterConfig
from .code_splitter import MedicalCodeSplitter
from .factory import SplitterType, TextSplitterFactory
from .paragraph_splitter import ParagraphMedicalSplitter
from .section_splitter import SectionAwareSplitter
from .semantic_splitter import SemanticMedicalSplitter
from .sentence_splitter import SentenceMedicalSplitter
from .sliding_window import SlidingWindowSplitter

__all__ = [
    # Base classes
    "BaseMedicalSplitter",
    "TextSplitterConfig",
    "SplitResult",
    "ChunkMetadata",
    # Specific splitters
    "SentenceMedicalSplitter",
    "SectionAwareSplitter",
    "SemanticMedicalSplitter",
    "MedicalCodeSplitter",
    "ParagraphMedicalSplitter",
    "SlidingWindowSplitter",
    # Factory
    "TextSplitterFactory",
    "SplitterType",
]
