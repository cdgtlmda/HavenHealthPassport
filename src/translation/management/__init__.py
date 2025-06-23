"""Translation Management Module.

Tools for extracting, managing, and validating translations.
"""

from .extraction_tools import ExtractionResult, TranslatableString, TranslationExtractor

__all__ = ["TranslationExtractor", "TranslatableString", "ExtractionResult"]
