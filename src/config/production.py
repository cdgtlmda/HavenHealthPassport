"""Production environment configuration."""

from src.config.base import Settings


class ProductionSettings(Settings):
    """Production-specific settings."""

    environment: str = "production"
    debug: bool = False

    # Strict CORS for production
    allowed_origins: list[str] = [
        "https://havenhealthpassport.org",
        "https://app.havenhealthpassport.org",
    ]

    # Production database settings
    database_pool_size: int = 20
    database_max_overflow: int = 40

    # Redis settings
    redis_pool_size: int = 50

    # Security
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Production logging
    log_level: str = "WARNING"
