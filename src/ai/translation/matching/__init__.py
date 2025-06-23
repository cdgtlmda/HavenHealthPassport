"""
Medical Glossary Matching Package.

This package provides comprehensive glossary matching functionality
for medical translation with context awareness and performance optimization.
"""

from .base_matcher import (
    GlossaryMatcher,
    MatchConfidence,
    MatchingOptions,
    MatchType,
    TermMatch,
)
from .context_matcher import ContextClue, ContextMatcher, MedicalContext
from .fuzzy_matcher import FuzzyMatcher
from .performance_optimizer import MatchingStats, OptimizedMatcher
from .pipeline_integration import (
    GlossaryMatchingPipeline,
    TranslationResult,
    TranslationSegment,
    matching_pipeline,
)

__all__ = [
    # Base matcher
    "GlossaryMatcher",
    "TermMatch",
    "MatchType",
    "MatchConfidence",
    "MatchingOptions",
    # Fuzzy matcher
    "FuzzyMatcher",
    # Context matcher
    "ContextMatcher",
    "ContextClue",
    "MedicalContext",
    # Performance optimizer
    "OptimizedMatcher",
    "MatchingStats",
    # Pipeline integration
    "GlossaryMatchingPipeline",
    "TranslationSegment",
    "TranslationResult",
    "matching_pipeline",
]

__version__ = "1.0.0"
