"""GraphQL Custom Scalar Type Definitions.

This module implements custom scalar types for the Haven Health Passport
GraphQL API, providing proper serialization and validation for common
data types used throughout the system.
"""

import json
import re
import uuid
from datetime import date, datetime
from typing import Any, BinaryIO, Optional

from graphql import (
    FloatValueNode,
    GraphQLError,
    GraphQLScalarType,
    IntValueNode,
    StringValueNode,
    ValueNode,
)
from graphql.language import ast
from graphql.pyutils import inspect

# DateTime Scalar - ISO 8601 datetime strings


def serialize_datetime(value: Any) -> str:
    """Serialize datetime to ISO 8601 string."""
    if isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, str):
        # Validate ISO format
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return value
        except ValueError as exc:
            raise GraphQLError(
                f"DateTime cannot represent value: {inspect(value)}"
            ) from exc
    else:
        raise GraphQLError(
            f"DateTime cannot represent non-datetime value: {inspect(value)}"
        )


def coerce_datetime(value: Any) -> datetime:
    """Coerce input value to datetime."""
    if isinstance(value, datetime):
        return value
    elif isinstance(value, str):
        try:
            # Handle ISO format with Z timezone
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise GraphQLError(
                f"DateTime cannot parse value: {inspect(value)}"
            ) from exc
    else:
        raise GraphQLError(f"DateTime cannot parse non-string value: {inspect(value)}")


def parse_datetime_literal(
    ast_node: ValueNode, _variables: Optional[dict] = None
) -> datetime:
    """Parse GraphQL AST literal to datetime."""
    if isinstance(ast_node, StringValueNode):
        return coerce_datetime(ast_node.value)
    else:
        raise GraphQLError(
            f"DateTime cannot parse non-string value: {inspect(ast_node)}", ast_node
        )


DateTimeScalar = GraphQLScalarType(
    name="DateTime",
    description="ISO 8601 datetime string",
    serialize=serialize_datetime,
    parse_value=coerce_datetime,
    parse_literal=parse_datetime_literal,
)

# Date Scalar - ISO 8601 date strings (YYYY-MM-DD)


def serialize_date(value: Any) -> str:
    """Serialize date to ISO 8601 string."""
    if isinstance(value, date):
        return value.isoformat()
    elif isinstance(value, datetime):
        return value.date().isoformat()
    elif isinstance(value, str):
        # Validate date format
        try:
            date.fromisoformat(value)
            return value
        except ValueError as exc:
            raise GraphQLError(
                f"Date cannot represent value: {inspect(value)}"
            ) from exc
    else:
        raise GraphQLError(f"Date cannot represent non-date value: {inspect(value)}")


def coerce_date(value: Any) -> date:
    """Coerce input value to date."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    elif isinstance(value, datetime):
        return value.date()
    elif isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise GraphQLError(f"Date cannot parse value: {inspect(value)}") from exc
    else:
        raise GraphQLError(f"Date cannot parse non-string value: {inspect(value)}")


def parse_date_literal(ast_node: ValueNode, _variables: Optional[dict] = None) -> date:
    """Parse GraphQL AST literal to date."""
    if isinstance(ast_node, StringValueNode):
        return coerce_date(ast_node.value)
    else:
        raise GraphQLError(
            f"Date cannot parse non-string value: {inspect(ast_node)}", ast_node
        )


DateScalar = GraphQLScalarType(
    name="Date",
    description="ISO 8601 date string (YYYY-MM-DD)",
    serialize=serialize_date,
    parse_value=coerce_date,
    parse_literal=parse_date_literal,
)

# JSON Scalar - Arbitrary JSON values


def serialize_json(value: Any) -> Any:
    """Serialize value as JSON."""
    # Already a basic JSON type
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    # Lists and dicts should be JSON-serializable
    elif isinstance(value, (list, dict)):
        return value
    # Try to convert to dict
    elif hasattr(value, "__dict__"):
        return value.__dict__
    else:
        try:
            # Attempt JSON serialization to validate
            json.dumps(value)
            return value
        except (TypeError, ValueError) as exc:
            raise GraphQLError(
                f"JSON cannot represent value: {inspect(value)}"
            ) from exc


def coerce_json(value: Any) -> Any:
    """Coerce input value to JSON-compatible type."""
    # Basic JSON types are already valid
    if isinstance(value, (str, int, float, bool, type(None), list, dict)):
        return value
    else:
        raise GraphQLError(f"JSON cannot parse value: {inspect(value)}")


def parse_json_literal(ast_node: ValueNode, variables: Optional[dict] = None) -> Any:
    """Parse GraphQL AST literal to JSON value."""
    if isinstance(ast_node, StringValueNode):
        # Try to parse as JSON string
        try:
            return json.loads(ast_node.value)
        except json.JSONDecodeError:
            # Return as plain string if not valid JSON
            return ast_node.value
    elif isinstance(ast_node, IntValueNode):
        return int(ast_node.value)
    elif isinstance(ast_node, FloatValueNode):
        return float(ast_node.value)
    elif isinstance(ast_node, ast.BooleanValueNode):
        return ast_node.value
    elif isinstance(ast_node, ast.NullValueNode):
        return None
    elif isinstance(ast_node, ast.ListValueNode):
        return [parse_json_literal(value, variables) for value in ast_node.values]
    elif isinstance(ast_node, ast.ObjectValueNode):
        return {
            field.name.value: parse_json_literal(field.value, variables)
            for field in ast_node.fields
        }
    elif isinstance(ast_node, ast.VariableNode):
        if variables and ast_node.name.value in variables:
            return variables[ast_node.name.value]
        else:
            raise GraphQLError(
                f"JSON cannot parse variable: {ast_node.name.value}", ast_node
            )
    else:
        raise GraphQLError(f"JSON cannot parse value: {inspect(ast_node)}", ast_node)


JSONScalar = GraphQLScalarType(
    name="JSON",
    description="Arbitrary JSON value",
    serialize=serialize_json,
    parse_value=coerce_json,
    parse_literal=parse_json_literal,
)

# UUID Scalar - UUID v4 strings

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def serialize_uuid(value: Any) -> str:
    """Serialize UUID to string."""
    if isinstance(value, uuid.UUID):
        return str(value)
    elif isinstance(value, str):
        # Validate UUID format
        if UUID_PATTERN.match(value):
            return value
        else:
            raise GraphQLError(f"UUID cannot represent value: {inspect(value)}")
    else:
        raise GraphQLError(f"UUID cannot represent non-UUID value: {inspect(value)}")


def coerce_uuid(value: Any) -> uuid.UUID:
    """Coerce input value to UUID."""
    if isinstance(value, uuid.UUID):
        return value
    elif isinstance(value, str):
        try:
            return uuid.UUID(value)
        except ValueError as exc:
            raise GraphQLError(f"UUID cannot parse value: {inspect(value)}") from exc
    else:
        raise GraphQLError(f"UUID cannot parse non-string value: {inspect(value)}")


def parse_uuid_literal(
    ast_node: ValueNode, _variables: Optional[dict] = None
) -> uuid.UUID:
    """Parse GraphQL AST literal to UUID."""
    if isinstance(ast_node, StringValueNode):
        return coerce_uuid(ast_node.value)
    else:
        raise GraphQLError(
            f"UUID cannot parse non-string value: {inspect(ast_node)}", ast_node
        )


UUIDScalar = GraphQLScalarType(
    name="UUID",
    description="UUID v4 string",
    serialize=serialize_uuid,
    parse_value=coerce_uuid,
    parse_literal=parse_uuid_literal,
)

# Upload Scalar - File upload handling


class Upload:
    """Represents an uploaded file."""

    def __init__(self, filename: str, mimetype: str, stream: BinaryIO):
        """Initialize upload with filename, mimetype, and stream."""
        self.filename = filename
        self.mimetype = mimetype
        self.stream = stream

    def read(self, size: int = -1) -> bytes:
        """Read bytes from the upload stream."""
        return self.stream.read(size)

    def save(self, path: str) -> None:
        """Save the uploaded file to a path."""
        with open(path, "wb") as f:
            chunk_size = 4096
            while True:
                chunk = self.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)


def serialize_upload(value: Any) -> None:
    """Upload scalar should never be serialized."""
    raise GraphQLError("Upload scalar cannot be serialized")


def coerce_upload(value: Any) -> Upload:
    """Coerce input value to Upload."""
    if isinstance(value, Upload):
        return value
    elif (
        hasattr(value, "filename")
        and hasattr(value, "mimetype")
        and hasattr(value, "stream")
    ):
        # Duck typing for file-like objects
        return Upload(value.filename, value.mimetype, value.stream)
    else:
        raise GraphQLError(f"Upload cannot parse value: {inspect(value)}")


def parse_upload_literal(
    ast_node: ValueNode, _variables: Optional[dict] = None
) -> None:
    """Upload scalar cannot be used as a literal."""
    raise GraphQLError("Upload scalar cannot be used as a literal", ast_node)


UploadScalar = GraphQLScalarType(
    name="Upload",
    description="File upload",
    serialize=serialize_upload,
    parse_value=coerce_upload,
    parse_literal=parse_upload_literal,
)

# Additional utility scalars for healthcare data

# EmailAddress Scalar

EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def validate_email(value: str) -> str:
    """Validate email address format."""
    if EMAIL_PATTERN.match(value):
        return value.lower()
    else:
        raise GraphQLError(f"Invalid email address: {value}")


EmailAddressScalar = GraphQLScalarType(
    name="EmailAddress",
    description="RFC 5322 compliant email address",
    serialize=validate_email,
    parse_value=validate_email,
    parse_literal=lambda ast, _: (
        validate_email(ast.value) if isinstance(ast, StringValueNode) else None
    ),
)

# PhoneNumber Scalar

PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{1,14}$")  # E.164 format


def validate_phone(value: str) -> str:
    """Validate phone number format."""
    # Remove spaces and dashes
    cleaned = re.sub(r"[\s\-\(\)]", "", value)
    if PHONE_PATTERN.match(cleaned):
        return cleaned
    else:
        raise GraphQLError(f"Invalid phone number: {value}")


PhoneNumberScalar = GraphQLScalarType(
    name="PhoneNumber",
    description="E.164 format phone number",
    serialize=validate_phone,
    parse_value=validate_phone,
    parse_literal=lambda ast, _: (
        validate_phone(ast.value) if isinstance(ast, StringValueNode) else None
    ),
)

# URL Scalar

URL_PATTERN = re.compile(
    r"^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&\/\/=]*)$"
)


def validate_url(value: str) -> str:
    """Validate URL format."""
    if URL_PATTERN.match(value):
        return value
    else:
        raise GraphQLError(f"Invalid URL: {value}")


URLScalar = GraphQLScalarType(
    name="URL",
    description="URL string",
    serialize=validate_url,
    parse_value=validate_url,
    parse_literal=lambda ast, _: (
        validate_url(ast.value) if isinstance(ast, StringValueNode) else None
    ),
)

# Positive integer scalar


def validate_positive_int(value: Any) -> int:
    """Validate positive integer."""
    if isinstance(value, int) and value > 0:
        return value
    else:
        raise GraphQLError(f"Value must be a positive integer: {value}")


PositiveIntScalar = GraphQLScalarType(
    name="PositiveInt",
    description="Positive integer",
    serialize=validate_positive_int,
    parse_value=validate_positive_int,
    parse_literal=lambda ast, _: (
        validate_positive_int(int(ast.value)) if isinstance(ast, IntValueNode) else None
    ),
)

# Export all scalar types
__all__ = [
    "DateTimeScalar",
    "DateScalar",
    "JSONScalar",
    "UUIDScalar",
    "UploadScalar",
    "EmailAddressScalar",
    "PhoneNumberScalar",
    "URLScalar",
    "PositiveIntScalar",
    "Upload",
]
