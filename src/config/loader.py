"""Configuration loader with production support."""

import os
from functools import lru_cache
from typing import TYPE_CHECKING, Union

# Import the appropriate settings based on environment
env = os.getenv("ENVIRONMENT", "development").lower()

if TYPE_CHECKING:
    from src.config.base import Settings as BaseSettings
    from src.config.production_loader import ProductionSettings

    Settings = Union[BaseSettings, ProductionSettings]

    def get_settings() -> Settings:
        """Get cached settings instance."""
        raise NotImplementedError("Test settings not implemented")

elif env in ["production", "staging"]:
    from src.config.production_loader import ProductionSettings as Settings
    from src.config.production_loader import (
        get_settings,
    )
else:
    from src.config.base import Settings

    @lru_cache()
    def get_settings() -> Settings:
        """Get cached settings instance."""
        return Settings()
