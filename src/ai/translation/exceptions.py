"""
Translation-specific exceptions.

Provides exception classes for translation errors and edge cases.
"""

from typing import Any, Dict, List, Optional


class TranslationError(Exception):
    """Base exception for translation errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize translation error.

        Args:
            message: Error message
            error_code: Optional error code
            details: Optional error details
        """
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class UnsupportedLanguageError(TranslationError):
    """Raised when a language is not supported."""

    def __init__(self, language: str, supported_languages: Optional[List[str]] = None):
        """
        Initialize unsupported language error.

        Args:
            language: The unsupported language
            supported_languages: List of supported languages
        """
        message = f"Language '{language}' is not supported"
        if supported_languages:
            message += f". Supported languages: {', '.join(supported_languages)}"

        super().__init__(
            message=message,
            error_code="UNSUPPORTED_LANGUAGE",
            details={"language": language, "supported_languages": supported_languages},
        )


class MedicalTerminologyError(TranslationError):
    """Raised when medical terminology cannot be preserved."""

    def __init__(
        self,
        term: str,
        source_language: str,
        target_language: str,
        reason: Optional[str] = None,
    ):
        """
        Initialize medical terminology error.

        Args:
            term: The medical term
            source_language: Source language
            target_language: Target language
            reason: Optional reason for failure
        """
        message = f"Failed to preserve medical term '{term}' from {source_language} to {target_language}"
        if reason:
            message += f": {reason}"

        super().__init__(
            message=message,
            error_code="MEDICAL_TERMINOLOGY_ERROR",
            details={
                "term": term,
                "source_language": source_language,
                "target_language": target_language,
                "reason": reason,
            },
        )


class TranslationQualityError(TranslationError):
    """Raised when translation quality is below threshold."""

    def __init__(
        self,
        confidence_score: float,
        threshold: float,
        quality_metrics: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize translation quality error.

        Args:
            confidence_score: Actual confidence score
            threshold: Required threshold
            quality_metrics: Optional quality metrics
        """
        message = f"Translation quality ({confidence_score:.2f}) below threshold ({threshold:.2f})"

        super().__init__(
            message=message,
            error_code="TRANSLATION_QUALITY_LOW",
            details={
                "confidence_score": confidence_score,
                "threshold": threshold,
                "quality_metrics": quality_metrics or {},
            },
        )


class LanguageDetectionError(TranslationError):
    """Raised when language detection fails."""

    def __init__(
        self, text_sample: str, detected_languages: Optional[Dict[str, float]] = None
    ):
        """
        Initialize language detection error.

        Args:
            text_sample: Sample of the text
            detected_languages: Languages with confidence scores
        """
        message = "Failed to detect source language with sufficient confidence"

        super().__init__(
            message=message,
            error_code="LANGUAGE_DETECTION_FAILED",
            details={
                "text_sample": text_sample[:100],
                "detected_languages": detected_languages or {},
            },
        )


class MetricsStorageError(TranslationError):
    """Raised when metrics storage operations fail."""

    def __init__(
        self,
        operation: str,
        reason: Optional[str] = None,
        storage_type: str = "dynamodb",
    ):
        """
        Initialize metrics storage error.

        Args:
            operation: The operation that failed
            reason: Optional reason for failure
            storage_type: Type of storage system
        """
        message = f"Failed to {operation} metrics in {storage_type}"
        if reason:
            message += f": {reason}"

        super().__init__(
            message=message,
            error_code="METRICS_STORAGE_ERROR",
            details={
                "operation": operation,
                "storage_type": storage_type,
                "reason": reason,
            },
        )


class ReportingError(TranslationError):
    """Raised when report generation or distribution fails."""

    def __init__(
        self,
        report_type: str,
        operation: str,
        reason: Optional[str] = None,
    ):
        """
        Initialize reporting error.

        Args:
            report_type: Type of report
            operation: The operation that failed
            reason: Optional reason for failure
        """
        message = f"Failed to {operation} {report_type} report"
        if reason:
            message += f": {reason}"

        super().__init__(
            message=message,
            error_code="REPORTING_ERROR",
            details={
                "report_type": report_type,
                "operation": operation,
                "reason": reason,
            },
        )
