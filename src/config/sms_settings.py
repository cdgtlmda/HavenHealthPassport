"""SMS configuration settings.

This module provides environment-based configuration for SMS services.
"""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class SMSSettings(BaseSettings):
    """SMS configuration from environment variables."""

    # Twilio settings
    twilio_enabled: bool = Field(default=False)
    twilio_account_sid: Optional[str] = Field(default=None)
    twilio_auth_token: Optional[str] = Field(default=None)
    twilio_from_number: Optional[str] = Field(default=None)

    # AWS SNS settings
    aws_sns_enabled: bool = Field(default=False)
    aws_sns_region: str = Field(default="us-east-1")
    aws_sns_sender_id: Optional[str] = Field(default=None)

    # SMS backup settings
    sms_backup_enabled: bool = Field(default=True)
    sms_code_length: int = Field(default=6)
    sms_code_validity_minutes: int = Field(default=10)
    sms_max_attempts: int = Field(default=3)
    sms_cooldown_minutes: int = Field(default=1)
    sms_daily_limit: int = Field(default=10)

    # Message templates
    sms_template: str = Field(
        default="Your Haven Health Passport verification code is: {code}. Valid for {minutes} minutes."
    )
    sms_resend_template: str = Field(
        default="Your new Haven Health Passport verification code is: {code}. Valid for {minutes} minutes."
    )

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
sms_settings = SMSSettings()
