"""Base Pydantic models for API validation and serialization.

This module provides base model configurations, common fields, and
validation utilities for all API models in Haven Health Passport.
"""

import json
import re
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# Custom JSON encoder for complex types
class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for handling special types."""

    def default(self, o: Any) -> Any:
        """Handle special types during JSON encoding."""
        if isinstance(o, (datetime,)):
            return o.isoformat()
        if isinstance(o, UUID):
            return str(o)
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, Enum):
            return o.value
        if isinstance(o, set):
            return list(o)
        return super().default(o)


# Base model configuration
class BaseAPIModel(BaseModel):
    """Base model for all API models with common configuration."""

    model_config = ConfigDict(
        # JSON encoding configuration
        json_encoders={
            datetime: datetime.isoformat,
            UUID: str,
            Decimal: float,
            set: list,
        },
        # Model behavior
        validate_assignment=True,
        validate_default=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        # Serialization
        populate_by_name=True,
        # Error messages
        str_strip_whitespace=True,
        # JSON schema
        json_schema_extra={"example": "See endpoint documentation for examples"},
    )

    class Config:
        """Additional configuration for backwards compatibility."""

        @staticmethod
        def json_dumps(v: Any, **kwargs: Any) -> str:
            """Dump JSON with enhanced encoder."""
            return json.dumps(v, cls=CustomJSONEncoder, **kwargs)


class TimestampMixin(BaseModel):
    """Mixin for models with timestamp fields."""

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the record was created",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the record was last updated",
    )

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime(cls, value: Any) -> datetime:
        """Parse datetime from various formats."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        raise ValueError(f"Cannot parse datetime from {type(value)}")


class PaginationMixin(BaseModel):
    """Mixin for paginated responses."""

    page: int = Field(default=1, ge=1, description="Current page number")
    page_size: int = Field(
        default=20, ge=1, le=100, description="Number of items per page"
    )
    total: int = Field(default=0, ge=0, description="Total number of items")
    total_pages: int = Field(default=0, ge=0, description="Total number of pages")

    @model_validator(mode="after")
    def calculate_total_pages(self) -> "PaginationMixin":
        """Calculate total pages based on total items and page size."""
        if self.total > 0 and self.page_size > 0:
            self.total_pages = (self.total + self.page_size - 1) // self.page_size
        return self


class ErrorDetail(BaseAPIModel):
    """Model for error details."""

    field: Optional[str] = Field(None, description="Field that caused the error")
    message: str = Field(..., description="Error message")
    code: Optional[str] = Field(None, description="Error code")


class ErrorResponse(BaseAPIModel):
    """Standard error response model."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[list[ErrorDetail]] = Field(
        None, description="Detailed error information"
    )
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Error timestamp"
    )


class HealthCheckResponse(BaseAPIModel):
    """Health check response model."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Check timestamp"
    )
    services: Dict[str, str] = Field(
        default_factory=dict, description="Status of dependent services"
    )


class AuditMixin(BaseModel):
    """Mixin for models requiring audit fields."""

    created_by: Optional[UUID] = Field(
        None, description="ID of the user who created the record"
    )
    updated_by: Optional[UUID] = Field(
        None, description="ID of the user who last updated the record"
    )
    deleted_at: Optional[datetime] = Field(None, description="Soft delete timestamp")
    deleted_by: Optional[UUID] = Field(
        None, description="ID of the user who deleted the record"
    )

    @property
    def is_deleted(self) -> bool:
        """Check if the record is soft deleted."""
        return self.deleted_at is not None


class ResponseEnvelope(BaseAPIModel):
    """Standard response envelope for API responses."""

    success: bool = Field(..., description="Whether the request was successful")
    data: Optional[Any] = Field(None, description="Response data")
    error: Optional[ErrorResponse] = Field(None, description="Error information")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @model_validator(mode="after")
    def validate_response(self) -> "ResponseEnvelope":
        """Ensure either data or error is present, but not both."""
        if self.success:
            if self.error is not None:
                raise ValueError("Successful response cannot have an error")
            if self.data is None:
                raise ValueError("Successful response must have data")
        else:
            if self.error is None:
                raise ValueError("Failed response must have an error")
            if self.data is not None:
                raise ValueError("Failed response cannot have data")
        return self


# Field validators for common use cases
class CommonValidators:
    """Common field validators for reuse across models."""

    @staticmethod
    def validate_email(email: str) -> str:
        """Validate email format."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, email):
            raise ValueError("Invalid email format")
        return email.lower()

    @staticmethod
    def validate_phone(phone: str) -> str:
        """Validate and normalize phone number."""
        # Remove all non-numeric characters
        cleaned = re.sub(r"\D", "", phone)
        if len(cleaned) < 10 or len(cleaned) > 15:
            raise ValueError("Invalid phone number length")
        return cleaned

    @staticmethod
    def validate_uuid(value: Any) -> UUID:
        """Validate UUID format."""
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            try:
                return UUID(value)
            except ValueError as exc:
                raise ValueError("Invalid UUID format") from exc
        raise ValueError(f"Cannot parse UUID from {type(value)}")

    @staticmethod
    def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
        """Sanitize string input."""
        # Strip whitespace
        value = value.strip()
        # Remove null bytes
        value = value.replace("\x00", "")
        # Limit length if specified
        if max_length and len(value) > max_length:
            value = value[:max_length]
        return value


# Export commonly used types
__all__ = [
    "BaseAPIModel",
    "TimestampMixin",
    "PaginationMixin",
    "ErrorDetail",
    "ErrorResponse",
    "HealthCheckResponse",
    "AuditMixin",
    "ResponseEnvelope",
    "CommonValidators",
    "CustomJSONEncoder",
]
