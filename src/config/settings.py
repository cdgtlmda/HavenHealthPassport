"""Settings module for Haven Health Passport."""

import logging
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Settings:
    """Application settings."""

    # Alert settings
    alert_enabled: bool = True
    alert_webhook_url: Optional[str] = None

    # AWS settings
    aws_region: str = "us-east-1"
    aws_account_id: Optional[str] = None

    # ClamAV settings
    clamav_host: str = "localhost"
    clamav_port: int = 3310
    clamav_timeout: int = 30

    # Scan settings
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    scan_timeout: int = 60

    # Security settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")

    def __init__(self) -> None:
        """Initialize settings."""
        # Validate critical settings
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY environment variable must be set")

        # Comprehensive SECRET_KEY validation
        if len(self.SECRET_KEY) < 50:
            raise ValueError("SECRET_KEY must be at least 50 characters long")

        # Check for character diversity
        has_upper = any(c.isupper() for c in self.SECRET_KEY)
        has_lower = any(c.islower() for c in self.SECRET_KEY)
        has_digit = any(c.isdigit() for c in self.SECRET_KEY)
        has_special = any(not c.isalnum() for c in self.SECRET_KEY)

        if not all([has_upper, has_lower, has_digit, has_special]):
            raise ValueError(
                "SECRET_KEY must contain mixed case letters, numbers, and special characters"
            )

        # Log key rotation reminder (without exposing the key)
        # logging imported at module level
        logger = logging.getLogger(__name__)
        logger.info("SECRET_KEY validated. Length: %d characters", len(self.SECRET_KEY))
