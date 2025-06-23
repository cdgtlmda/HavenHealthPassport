"""Custom exceptions for Haven Health Passport API.

This module defines all custom exceptions used throughout the API,
providing consistent error handling and meaningful error messages.
"""

from typing import Any, Dict, Optional

from fastapi import HTTPException, status


class BaseAPIException(HTTPException):
    """Base exception for all API exceptions."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        headers: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        """Initialize base API exception."""
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code or self.__class__.__name__


# Authentication Exceptions
class AuthenticationError(BaseAPIException):
    """Raised when authentication fails."""

    def __init__(self, detail: str = "Authentication failed"):
        """Initialize authentication error."""
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
            error_code="AUTHENTICATION_ERROR",
        )


class InvalidCredentialsError(AuthenticationError):
    """Raised when credentials are invalid."""

    def __init__(self) -> None:
        """Initialize invalid credentials error."""
        super().__init__(detail="Invalid email or password")
        self.error_code = "INVALID_CREDENTIALS"


class TokenExpiredError(AuthenticationError):
    """Raised when a token has expired."""

    def __init__(self) -> None:
        """Initialize token expired error."""
        super().__init__(detail="Token has expired")
        self.error_code = "TOKEN_EXPIRED"


class InvalidTokenError(AuthenticationError):
    """Raised when a token is invalid."""

    def __init__(self) -> None:
        """Initialize invalid token error."""
        super().__init__(detail="Invalid token")
        self.error_code = "INVALID_TOKEN"


# Authorization Exceptions
class AuthorizationError(BaseAPIException):
    """Raised when authorization fails."""

    def __init__(self, detail: str = "Insufficient permissions"):
        """Initialize authorization error."""
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="AUTHORIZATION_ERROR",
        )


class InsufficientPermissionsError(AuthorizationError):
    """Raised when user lacks required permissions."""

    def __init__(self, required_permission: Optional[str] = None):
        """Initialize insufficient permissions error."""
        detail = "Insufficient permissions"
        if required_permission:
            detail = f"Missing required permission: {required_permission}"
        super().__init__(detail=detail)
        self.error_code = "INSUFFICIENT_PERMISSIONS"


# Validation Exceptions
class ValidationError(BaseAPIException):
    """Raised when input validation fails."""

    def __init__(self, detail: str, field: Optional[str] = None):
        """Initialize validation error."""
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code="VALIDATION_ERROR",
        )
        self.field = field


class RequiredFieldError(ValidationError):
    """Raised when a required field is missing."""

    def __init__(self, field: str):
        """Initialize required field error."""
        super().__init__(detail=f"Missing required field: {field}", field=field)
        self.error_code = "REQUIRED_FIELD_MISSING"


# Resource Exceptions
class ResourceNotFoundError(BaseAPIException):
    """Raised when a requested resource is not found."""

    def __init__(self, resource_type: str, resource_id: Optional[str] = None):
        """Initialize resource not found error."""
        detail = f"{resource_type} not found"
        if resource_id:
            detail = f"{resource_type} with id '{resource_id}' not found"
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            error_code="RESOURCE_NOT_FOUND",
        )


class ResourceAlreadyExistsError(BaseAPIException):
    """Raised when attempting to create a resource that already exists."""

    def __init__(self, resource_type: str, identifier: Optional[str] = None):
        """Initialize resource already exists error."""
        detail = f"{resource_type} already exists"
        if identifier:
            detail = f"{resource_type} with identifier '{identifier}' already exists"
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            error_code="RESOURCE_ALREADY_EXISTS",
        )


class ResourceConflictError(BaseAPIException):
    """Raised when a resource operation conflicts with current state."""

    def __init__(self, detail: str):
        """Initialize resource conflict error."""
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            error_code="RESOURCE_CONFLICT",
        )


# Rate Limiting Exceptions
class RateLimitExceededError(BaseAPIException):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: Optional[int] = None):
        """Initialize rate limit exceeded error."""
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
            headers=headers,
            error_code="RATE_LIMIT_EXCEEDED",
        )


# File Operation Exceptions
class FileOperationError(BaseAPIException):
    """Base class for file operation errors."""

    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        """Initialize file operation error."""
        super().__init__(
            status_code=status_code,
            detail=detail,
            error_code="FILE_OPERATION_ERROR",
        )


class FileTooLargeError(FileOperationError):
    """Raised when uploaded file exceeds size limit."""

    def __init__(self, max_size_mb: int):
        """Initialize file too large error."""
        super().__init__(
            detail=f"File size exceeds maximum allowed size of {max_size_mb}MB"
        )
        self.error_code = "FILE_TOO_LARGE"


class InvalidFileTypeError(FileOperationError):
    """Raised when uploaded file type is not allowed."""

    def __init__(self, allowed_types: Optional[list[str]] = None):
        """Initialize invalid file type error."""
        detail = "Invalid file type"
        if allowed_types:
            detail = f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
        super().__init__(detail=detail)
        self.error_code = "INVALID_FILE_TYPE"


# FHIR Exceptions
class FHIRError(BaseAPIException):
    """Base class for FHIR-related errors."""

    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        """Initialize FHIR error."""
        super().__init__(
            status_code=status_code,
            detail=detail,
            error_code="FHIR_ERROR",
        )


class FHIRValidationError(FHIRError):
    """Raised when FHIR resource validation fails."""

    def __init__(self, resource_type: str, errors: list[str]):
        """Initialize FHIR validation error."""
        detail = f"FHIR {resource_type} validation failed: {'; '.join(errors)}"
        super().__init__(detail=detail)
        self.error_code = "FHIR_VALIDATION_ERROR"
        self.resource_type = resource_type
        self.validation_errors = errors


# External Service Exceptions
class ExternalServiceError(BaseAPIException):
    """Raised when an external service call fails."""

    def __init__(self, service_name: str, detail: Optional[str] = None):
        """Initialize external service error."""
        error_detail = f"{service_name} service error"
        if detail:
            error_detail = f"{service_name} service error: {detail}"
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail,
            error_code="EXTERNAL_SERVICE_ERROR",
        )


# Business Logic Exceptions
class BusinessLogicError(BaseAPIException):
    """Raised when business logic validation fails."""

    def __init__(self, detail: str):
        """Initialize business logic error."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code="BUSINESS_LOGIC_ERROR",
        )


class AccountLockedException(BusinessLogicError):
    """Raised when account is locked due to security reasons."""

    def __init__(self, lockout_minutes: Optional[int] = None):
        """Initialize account locked exception."""
        detail = "Account is locked due to too many failed attempts"
        if lockout_minutes:
            detail = f"Account is locked. Try again in {lockout_minutes} minutes"
        super().__init__(detail=detail)
        self.error_code = "ACCOUNT_LOCKED"


class OperationNotAllowedException(BusinessLogicError):
    """Raised when an operation is not allowed in current context."""

    def __init__(self, operation: str, reason: str):
        """Initialize operation not allowed exception."""
        super().__init__(detail=f"Operation '{operation}' not allowed: {reason}")
        self.error_code = "OPERATION_NOT_ALLOWED"


# Export all exceptions
__all__ = [
    "BaseAPIException",
    "AuthenticationError",
    "InvalidCredentialsError",
    "TokenExpiredError",
    "InvalidTokenError",
    "AuthorizationError",
    "InsufficientPermissionsError",
    "ValidationError",
    "RequiredFieldError",
    "ResourceNotFoundError",
    "ResourceAlreadyExistsError",
    "ResourceConflictError",
    "RateLimitExceededError",
    "FileOperationError",
    "FileTooLargeError",
    "InvalidFileTypeError",
    "FHIRError",
    "FHIRValidationError",
    "ExternalServiceError",
    "BusinessLogicError",
    "AccountLockedException",
    "OperationNotAllowedException",
]
