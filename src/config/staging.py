"""Staging environment configuration."""

from src.config.base import Settings


class StagingSettings(Settings):
    """Staging-specific settings."""

    environment: str = "staging"
    debug: bool = False

    # Staging CORS
    allowed_origins: list[str] = [
        "https://staging.havenhealthpassport.org",
        "https://staging-app.havenhealthpassport.org",
    ]

    # Staging database settings
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Staging logging
    log_level: str = "INFO"
