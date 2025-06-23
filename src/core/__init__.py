"""Core Module.

This module provides core functionality for the Haven Health Passport system.
"""

from .exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    HavenHealthError,
    NetworkError,
    ProcessingError,
    StorageError,
    UnsupportedLanguageError,
    ValidationError,
)

__all__ = [
    "HavenHealthError",
    "ProcessingError",
    "ValidationError",
    "UnsupportedLanguageError",
    "AuthenticationError",
    "AuthorizationError",
    "ConfigurationError",
    "NetworkError",
    "StorageError",
]
