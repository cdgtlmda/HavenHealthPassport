"""Lazy Loading Module for Translation Resources.

This module provides optimized lazy loading functionality for translation
resources to improve application performance.
"""

from .translation_loader import (
    LazyTranslationLoader,
    LoadConfig,
    LoadStrategy,
    ResourceType,
    TranslationResource,
    lazy_loader,
)

__all__ = [
    "LazyTranslationLoader",
    "LoadStrategy",
    "ResourceType",
    "TranslationResource",
    "LoadConfig",
    "lazy_loader",
]
