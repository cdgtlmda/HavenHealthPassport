"""Configuration module for Haven Health Passport."""

from src.config.base import Settings
from src.config.loader import get_settings

# Create the settings instance that can be imported directly
settings = get_settings()

__all__ = ["Settings", "get_settings", "settings"]
