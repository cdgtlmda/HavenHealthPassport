"""Core Exceptions Module.

This module defines custom exceptions used throughout the Haven Health Passport system.
"""


class HavenHealthError(Exception):
    """Base exception for all Haven Health Passport errors."""


class ProcessingError(HavenHealthError):
    """Raised when document or data processing fails."""


class ValidationError(HavenHealthError):
    """Raised when data validation fails."""


class UnsupportedLanguageError(HavenHealthError):
    """Raised when an unsupported language is encountered."""


class AuthenticationError(HavenHealthError):
    """Raised when authentication fails."""


class AuthorizationError(HavenHealthError):
    """Raised when authorization fails."""


class ConfigurationError(HavenHealthError):
    """Raised when configuration is invalid or missing."""


class NetworkError(HavenHealthError):
    """Raised when network operations fail."""


class StorageError(HavenHealthError):
    """Raised when storage operations fail."""
