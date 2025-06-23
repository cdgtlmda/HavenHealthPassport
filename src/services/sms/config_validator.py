"""
SMS Provider Configuration Validator.

CRITICAL: This is a healthcare project where SMS is used for:
1. Patient authentication (2FA)
2. Emergency notifications
3. Appointment reminders
4. Critical health alerts

SMS delivery failures can prevent patients from accessing their medical records
or receiving critical health notifications. Configuration must validate
compliance with FHIR Resource communication standards.
"""

import os
from typing import List, Tuple

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SMSConfigValidator:
    """Validates SMS provider configuration for production readiness."""

    @staticmethod
    def validate_production_config() -> Tuple[bool, List[str]]:
        """
        Validate SMS configuration for production.

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        environment = settings.environment.lower()

        if environment != "production":
            # Non-production can use mock, but warn
            logger.warning(
                f"SMS configuration check in {environment} environment. "
                f"Ensure real providers are configured before production!"
            )
            return True, []

        # In production, at least one real provider MUST be configured
        twilio_configured = SMSConfigValidator._check_twilio_config()
        aws_sns_configured = SMSConfigValidator._check_aws_sns_config()

        if not twilio_configured and not aws_sns_configured:
            errors.append(
                "CRITICAL: No SMS provider configured for production! "
                "Configure Twilio or AWS SNS. Patient notifications will fail!"
            )

        # Warn if only one provider (no failover)
        if (twilio_configured and not aws_sns_configured) or (
            aws_sns_configured and not twilio_configured
        ):
            logger.warning(
                "Only one SMS provider configured. "
                "Consider configuring both Twilio and AWS SNS for redundancy. "
                "Single provider failure could prevent critical patient notifications!"
            )

        # Validate Twilio if configured
        if twilio_configured:
            twilio_errors = SMSConfigValidator._validate_twilio_config()
            errors.extend(twilio_errors)

        # Validate AWS SNS if configured
        if aws_sns_configured:
            sns_errors = SMSConfigValidator._validate_aws_sns_config()
            errors.extend(sns_errors)

        # Check for mock provider in production
        if os.getenv("USE_MOCK_SMS", "false").lower() == "true":
            errors.append(
                "CRITICAL: Mock SMS provider enabled in production! "
                "This will not send real SMS messages. Patient safety at risk!"
            )

        return len(errors) == 0, errors

    @staticmethod
    def _check_twilio_config() -> bool:
        """Check if Twilio is configured."""
        return all(
            [
                os.getenv("TWILIO_ACCOUNT_SID"),
                os.getenv("TWILIO_AUTH_TOKEN"),
                os.getenv("TWILIO_FROM_NUMBER"),
            ]
        )

    @staticmethod
    def _check_aws_sns_config() -> bool:
        """Check if AWS SNS is configured."""
        return os.getenv("AWS_SNS_ENABLED", "").lower() == "true"

    @staticmethod
    def _validate_twilio_config() -> List[str]:
        """Validate Twilio configuration details."""
        errors = []

        account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        from_number = os.getenv("TWILIO_FROM_NUMBER", "")

        # Validate account SID format
        if not account_sid.startswith("AC") or len(account_sid) != 34:
            errors.append(
                "Invalid Twilio Account SID format. "
                "Must start with 'AC' and be 34 characters."
            )

        # Validate auth token
        if len(auth_token) < 32:
            errors.append(
                "Twilio auth token appears invalid. "
                "Ensure you're using the correct token from Twilio console."
            )

        # Validate phone number format
        # @encrypt_phi - Phone numbers are PHI and must be encrypted at rest
        # @access_control_required - SMS config access requires admin authorization
        if not from_number.startswith("+"):
            errors.append(
                "Twilio phone number must be in E.164 format (start with '+')."
            )

        return errors

    @staticmethod
    def _validate_aws_sns_config() -> List[str]:
        """Validate AWS SNS configuration details."""
        errors = []

        # Check AWS credentials
        if not os.getenv("AWS_ACCESS_KEY_ID") and not os.getenv("AWS_ROLE_ARN"):
            errors.append(
                "AWS credentials not configured for SNS. "
                "Set AWS_ACCESS_KEY_ID or use IAM roles."
            )

        # Check region
        region = os.getenv("AWS_DEFAULT_REGION")
        if not region:
            logger.warning(
                "AWS_DEFAULT_REGION not set. Will use us-east-1. "
                "Consider setting explicit region for SMS delivery."
            )

        return errors

    @staticmethod
    def generate_config_template() -> str:
        """Generate SMS configuration template for .env file."""
        # @permission_required - Config generation requires admin access
        return """
# SMS Provider Configuration - CRITICAL for patient notifications
# At least one provider MUST be configured for production

# Twilio Configuration (Primary Provider)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_FROM_NUMBER=+1234567890  # Must be E.164 format

# AWS SNS Configuration (Backup Provider)
AWS_SNS_ENABLED=true
AWS_SNS_SENDER_ID=HavenHealth  # Optional: Sender ID for SMS
AWS_DEFAULT_REGION=us-east-1

# NEVER enable mock SMS in production
USE_MOCK_SMS=false
"""


def validate_sms_config_on_startup() -> None:
    """Validate SMS configuration on application startup."""
    is_valid, errors = SMSConfigValidator.validate_production_config()

    if not is_valid:
        error_msg = "\n".join(errors)
        if settings.environment.lower() == "production":
            raise RuntimeError(
                f"SMS Configuration Errors:\n{error_msg}\n\n"
                f"This is a healthcare system - SMS is required for patient safety!"
            )
        else:
            logger.error(f"SMS Configuration Errors:\n{error_msg}")

    logger.info("SMS configuration validated successfully")


# Run validation on module import
if __name__ == "__main__":
    validate_sms_config_on_startup()
