"""Custom exceptions for the Haven Health Passport application."""

from typing import Optional


class HavenException(Exception):
    """Base exception for all Haven Health Passport exceptions."""

    def __init__(self, message: str, code: Optional[str] = None):
        """Initialize exception.

        Args:
            message: Error message
            code: Optional error code
        """
        super().__init__(message)
        self.code = code


class AuthenticationException(HavenException):
    """Base exception for authentication errors."""


class MFAException(AuthenticationException):
    """Base exception for MFA-related errors."""


class ValidationError(HavenException):
    """Raised when validation fails."""


class TranslationException(HavenException):
    """Base exception for translation-related errors."""

    def __init__(self, message: str = "Translation operation failed"):
        """Initialize TranslationException."""
        super().__init__(message, "TRANSLATION_ERROR")


class UnsupportedLanguageException(TranslationException):
    """Raised when language is not supported."""

    def __init__(self, message: str = "Language not supported"):
        """Initialize UnsupportedLanguageException."""
        super().__init__(message)
        self.code = "UNSUPPORTED_LANGUAGE"


class MFARequiredException(MFAException):
    """Raised when MFA is required but not configured."""

    def __init__(self, message: str = "Multi-factor authentication is required"):
        """Initialize MFARequiredException."""
        super().__init__(message, "MFA_REQUIRED")


class MFANotConfiguredException(MFAException):
    """Raised when MFA method is not configured."""

    def __init__(self, message: str = "MFA method not configured"):
        """Initialize MFANotConfiguredException."""
        super().__init__(message, "MFA_NOT_CONFIGURED")


class InvalidMFACodeException(MFAException):
    """Raised when MFA code is invalid."""

    def __init__(self, message: str = "Invalid MFA code"):
        """Initialize InvalidMFACodeException."""
        super().__init__(message, "INVALID_MFA_CODE")


class MFAMethodNotEnabledException(MFAException):
    """Raised when MFA method is not enabled."""

    def __init__(self, message: str = "MFA method not enabled"):
        """Initialize MFAMethodNotEnabledException."""
        super().__init__(message, "MFA_METHOD_NOT_ENABLED")


class TooManyAttemptsException(MFAException):
    """Raised when too many failed attempts."""

    def __init__(self, message: str = "Too many failed attempts"):
        """Initialize TooManyAttemptsException."""
        super().__init__(message, "TOO_MANY_ATTEMPTS")


class ValidationException(HavenException):
    """Raised when validation fails."""


class EncryptionException(HavenException):
    """Raised when encryption/decryption fails."""


class BlockchainException(HavenException):
    """Raised when blockchain operations fail."""


class HealthcareStandardsException(HavenException):
    """Raised when healthcare standards validation fails."""


class OfflineSyncException(HavenException):
    """Raised when offline sync operations fail."""


class SMSException(HavenException):
    """Raised when SMS operations fail."""

    def __init__(self, message: str = "SMS operation failed"):
        """Initialize SMSException."""
        super().__init__(message, "SMS_ERROR")


class BiometricException(AuthenticationException):
    """Base exception for biometric authentication errors."""


class BiometricNotEnrolledException(BiometricException):
    """Raised when biometric is not enrolled."""

    def __init__(self, message: str = "Biometric not enrolled"):
        """Initialize BiometricNotEnrolledException."""
        super().__init__(message, "BIOMETRIC_NOT_ENROLLED")


class BiometricVerificationException(BiometricException):
    """Raised when biometric verification fails."""

    def __init__(self, message: str = "Biometric verification failed"):
        """Initialize BiometricVerificationException."""
        super().__init__(message, "BIOMETRIC_VERIFICATION_FAILED")


class BiometricTemplateException(BiometricException):
    """Raised when there's an issue with biometric template."""

    def __init__(self, message: str = "Biometric template error"):
        """Initialize BiometricTemplateException."""
        super().__init__(message, "BIOMETRIC_TEMPLATE_ERROR")


class SessionException(AuthenticationException):
    """Base exception for session-related errors."""


class SessionExpiredException(SessionException):
    """Raised when session has expired."""

    def __init__(self, message: str = "Session has expired"):
        """Initialize SessionExpiredException."""
        super().__init__(message, "SESSION_EXPIRED")


class SessionInvalidException(SessionException):
    """Raised when session is invalid."""

    def __init__(self, message: str = "Session is invalid"):
        """Initialize SessionInvalidException."""
        super().__init__(message, "SESSION_INVALID")


class TooManySessionsException(SessionException):
    """Raised when too many concurrent sessions."""

    def __init__(self, message: str = "Too many concurrent sessions"):
        """Initialize TooManySessionsException."""
        super().__init__(message, "TOO_MANY_SESSIONS")
