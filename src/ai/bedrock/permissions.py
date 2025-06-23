"""Permission management for Bedrock model access."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

from .models import ModelAccessLevel, ModelUsageType


class ModelPermissions(BaseModel):
    """Permissions for a specific model."""

    model_id: str
    access_level: ModelAccessLevel = ModelAccessLevel.NONE
    allowed_usage_types: Set[ModelUsageType] = Field(default_factory=set)
    max_requests_per_minute: int = 10
    max_requests_per_day: int = 1000
    max_tokens_per_request: int = 4096
    max_tokens_per_day: int = 100000
    cost_limit_per_day: float = 100.0
    regions: List[str] = Field(default_factory=lambda: ["us-east-1"])

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class UserModelAccess(BaseModel):
    """User's access configuration for all models."""

    user_id: str
    role: str
    department: str = "general"
    access_level: ModelAccessLevel = ModelAccessLevel.BASIC
    model_permissions: Dict[str, ModelPermissions] = Field(default_factory=dict)
    global_rate_limit: int = 60  # requests per minute across all models
    global_cost_limit_per_day: float = 500.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

    def has_model_access(self, model_id: str) -> bool:
        """Check if user has access to a specific model."""
        if model_id not in self.model_permissions:
            return self.access_level != ModelAccessLevel.NONE
        return self.model_permissions[model_id].access_level != ModelAccessLevel.NONE


class ModelAccessManager:
    """Manages model access permissions for users."""

    def __init__(self) -> None:
        """Initialize the Bedrock permissions manager."""
        self.user_access: Dict[str, UserModelAccess] = {}
        self.default_permissions = self._create_default_permissions()

    def _create_default_permissions(self) -> Dict[ModelAccessLevel, Dict[str, Any]]:
        """Create default permissions for each access level."""
        return {
            ModelAccessLevel.BASIC: {
                "max_requests_per_minute": 10,
                "max_requests_per_day": 1000,
                "max_tokens_per_request": 4096,
                "max_tokens_per_day": 100000,
                "cost_limit_per_day": 50.0,
            },
            ModelAccessLevel.STANDARD: {
                "max_requests_per_minute": 30,
                "max_requests_per_day": 5000,
                "max_tokens_per_request": 8192,
                "max_tokens_per_day": 500000,
                "cost_limit_per_day": 200.0,
            },
            ModelAccessLevel.PREMIUM: {
                "max_requests_per_minute": 60,
                "max_requests_per_day": 10000,
                "max_tokens_per_request": 16384,
                "max_tokens_per_day": 2000000,
                "cost_limit_per_day": 1000.0,
            },
            ModelAccessLevel.UNLIMITED: {
                "max_requests_per_minute": 120,
                "max_requests_per_day": 50000,
                "max_tokens_per_request": 32768,
                "max_tokens_per_day": 10000000,
                "cost_limit_per_day": 5000.0,
            },
        }

    def grant_access(
        self,
        user_id: str,
        model_id: str,
        access_level: ModelAccessLevel,
        custom_limits: Optional[Dict] = None,
    ) -> ModelPermissions:
        """Grant access to a specific model for a user."""
        if user_id not in self.user_access:
            raise ValueError(f"User {user_id} not found")

        # Get default limits for access level
        default_limits = self.default_permissions.get(
            access_level, self.default_permissions[ModelAccessLevel.BASIC]
        )

        # Create model permissions
        permissions = ModelPermissions(
            model_id=model_id, access_level=access_level, **default_limits
        )

        # Apply custom limits if provided
        if custom_limits:
            for key, value in custom_limits.items():
                if hasattr(permissions, key):
                    setattr(permissions, key, value)

        # Add to user's permissions
        self.user_access[user_id].model_permissions[model_id] = permissions
        self.user_access[user_id].updated_at = datetime.utcnow()

        return permissions
