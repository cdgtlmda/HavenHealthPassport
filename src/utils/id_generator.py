"""ID generation utilities for Haven Health Passport.

This module provides utilities for generating unique identifiers.
"""

import uuid
from typing import Optional


def generate_id(prefix: Optional[str] = None) -> str:
    """Generate a unique ID with optional prefix.

    Args:
        prefix: Optional prefix for the ID

    Returns:
        Generated unique ID
    """
    base_id = str(uuid.uuid4())

    if prefix:
        return f"{prefix}_{base_id}"

    return base_id


def generate_short_id() -> str:
    """Generate a shorter unique ID.

    Returns:
        8-character unique ID
    """
    return str(uuid.uuid4())[:8]
