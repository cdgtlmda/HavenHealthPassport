"""TOTP configuration settings.

This module provides environment-based configuration for TOTP settings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class TOTPSettings(BaseSettings):
    """TOTP configuration from environment variables."""

    # Basic settings
    totp_issuer_name: str = Field(default="Haven Health Passport")
    totp_issuer_logo_url: str = Field(default="")

    # Algorithm settings
    totp_algorithm: str = Field(default="SHA1")
    totp_digits: int = Field(default=6)
    totp_interval: int = Field(default=30)

    # Security settings
    totp_window: int = Field(default=1)
    totp_reuse_interval: int = Field(default=90)
    totp_max_attempts: int = Field(default=5)

    # QR code settings
    totp_qr_version: int = Field(default=5)
    totp_qr_box_size: int = Field(default=10)
    totp_qr_border: int = Field(default=4)
    totp_qr_error_correction: str = Field(default="M")

    # User experience settings
    totp_setup_timeout_minutes: int = Field(default=10)
    totp_recovery_codes_count: int = Field(default=10)
    totp_show_secret_on_setup: bool = Field(default=True)

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from environment


# Global settings instance
totp_settings = TOTPSettings()
