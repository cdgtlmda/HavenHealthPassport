"""Database type compatibility layer for PostgreSQL and SQLite."""

import os
import uuid
from typing import Any, Optional, Type

from sqlalchemy import CHAR, JSON, String, TypeDecorator
from sqlalchemy.dialects.postgresql import ARRAY as PostgreSQLARRAY
from sqlalchemy.dialects.postgresql import INET as PostgreSQLINET
from sqlalchemy.dialects.postgresql import JSONB as PostgreSQLJSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID


def is_sqlite() -> bool:
    """Check if we're using SQLite (for testing)."""
    database_url = os.getenv("DATABASE_URL", "")
    # Also check for test environment variable
    test_env = os.getenv("TESTING", "").lower() == "true"
    return "sqlite" in database_url or ":memory:" in database_url or test_env


# For SQLite compatibility, we need to use JSON instead of JSONB
if is_sqlite():
    JSONB = JSON

    class INETType(TypeDecorator):
        """INET type that degrades to String for SQLite."""

        impl = String(45)
        cache_ok = True

        def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
            """Process value before binding to database."""
            return str(value) if value is not None else None

        def process_result_value(self, value: Any, dialect: Any) -> Optional[str]:
            """Process value when loading from database."""
            return str(value) if value is not None else None

        def process_literal_param(self, value: Any, dialect: Any) -> str:
            """Process literal parameter."""
            return str(value) if value is not None else ""

        @property
        def python_type(self) -> Type[str]:
            """Python type."""
            return str

    INET = INETType

    def ARRAY(_item_type: Any) -> Any:
        """ARRAY type that degrades to JSON for SQLite.

        Args:
            _item_type: The type of items in the array (reserved for future type checking)
        """

        class ARRAYType(TypeDecorator):
            impl = JSON
            cache_ok = True

            def process_bind_param(self, value: Any, dialect: Any) -> Any:
                """Process value before binding to database."""
                return value

            def process_result_value(self, value: Any, dialect: Any) -> Any:
                """Process value when loading from database."""
                return value if value is not None else []

            def process_literal_param(self, value: Any, dialect: Any) -> Any:
                """Process literal parameter."""
                return value

            @property
            def python_type(self) -> Type[list]:
                """Python type."""
                return list

        return ARRAYType()

    class UUIDType(TypeDecorator):
        """UUID type that degrades to CHAR(36) for SQLite."""

        impl = CHAR(36)
        cache_ok = True

        def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
            """Process value before binding to database."""
            if value is None:
                return None
            if isinstance(value, uuid.UUID):
                return str(value)
            return str(value)

        def process_result_value(self, value: Any, dialect: Any) -> Optional[uuid.UUID]:
            """Process value when loading from database."""
            if value is None:
                return None
            return uuid.UUID(value)

        def process_literal_param(self, value: Any, dialect: Any) -> str:
            """Process literal parameter."""
            if value is None:
                return ""
            if isinstance(value, uuid.UUID):
                return str(value)
            return str(value)

        @property
        def python_type(self) -> Type[uuid.UUID]:
            """Python type."""
            return uuid.UUID

    # Create a callable that returns UUIDType() when called
    # but also make UUID itself an instance for backward compatibility
    UUID = UUIDType

else:
    # Use PostgreSQL types directly
    JSONB = PostgreSQLJSONB  # type: ignore[misc]
    INET = PostgreSQLINET  # type: ignore[misc,assignment]
    ARRAY = PostgreSQLARRAY  # type: ignore[assignment]
    UUID = PostgreSQLUUID  # type: ignore[misc,assignment]
