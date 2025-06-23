"""User model for the Haven Health Passport system."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class User:
    """User model with permissions and metadata."""

    id: str
    email: str
    name: str
    permissions: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Initialize default values for optional fields."""
        if self.permissions is None:
            self.permissions = []
        if self.metadata is None:
            self.metadata = {}
