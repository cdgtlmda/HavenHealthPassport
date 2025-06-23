"""
Voice synthesis configuration validator.

Ensures all required configuration is present for production voice synthesis.
This is critical for medical communications to refugees.
"""

import os
from typing import Any, Dict, List, Tuple

from src.utils.logging import get_logger

logger = get_logger(__name__)


class VoiceSynthesisConfigValidator:
    """Validates configuration for voice synthesis services."""

    # Required AWS settings for Polly
    REQUIRED_AWS_SETTINGS = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"]

    # Optional but recommended settings
    OPTIONAL_SETTINGS = [
        "S3_BUCKET",  # For audio storage
        "VOICE_SYNTHESIS_CACHE_TTL",  # Cache duration
        "VOICE_SYNTHESIS_DEFAULT_LANGUAGE",  # Default language
    ]

    @classmethod
    def validate_production_config(cls) -> Tuple[bool, List[str]]:
        """
        Validate production configuration for voice synthesis.

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check environment
        env = os.getenv("ENVIRONMENT", "development").lower()
        if env not in ["production", "staging"]:
            return True, []  # Skip validation for development

        logger.info("Validating production voice synthesis configuration...")

        # Check required AWS settings
        for setting in cls.REQUIRED_AWS_SETTINGS:
            value = os.getenv(setting)
            if not value or value.strip() == "":
                errors.append(
                    f"Missing required setting: {setting}. "
                    f"This is required for Amazon Polly voice synthesis."
                )
            else:
                # Mask sensitive values in logs
                masked_value = (
                    f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "***"
                )
                logger.info(f"✓ {setting} is set ({masked_value})")

        # Check AWS region is valid
        aws_region = os.getenv("AWS_REGION", "").lower()
        valid_regions = [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-west-2",
            "eu-west-3",
            "eu-central-1",
            "ap-southeast-1",
            "ap-southeast-2",
            "ap-northeast-1",
            "ap-south-1",
            "ca-central-1",
            "sa-east-1",
        ]

        if aws_region and aws_region not in valid_regions:
            errors.append(
                f"Invalid AWS_REGION: {aws_region}. "
                f"Must be one of: {', '.join(valid_regions)}"
            )

        # Check optional settings
        for setting in cls.OPTIONAL_SETTINGS:
            value = os.getenv(setting)
            if value:
                logger.info(f"✓ {setting} is configured")
            else:
                logger.warning(
                    f"Optional setting {setting} not configured. "
                    f"Consider setting for better performance."
                )

        # Check S3 bucket permissions if configured
        s3_bucket = os.getenv("S3_BUCKET")
        if s3_bucket:
            # In a real implementation, we'd check bucket permissions
            logger.info(f"S3 bucket configured: {s3_bucket}")

        # Validate Polly-specific settings
        if not errors:
            errors.extend(cls._validate_polly_settings())

        is_valid = len(errors) == 0

        if is_valid:
            logger.info("✅ Voice synthesis configuration is valid for production")
        else:
            logger.error(
                f"❌ Voice synthesis configuration has {len(errors)} error(s):\n"
                + "\n".join(f"  - {error}" for error in errors)
            )

        return is_valid, errors

    @classmethod
    def _validate_polly_settings(cls) -> List[str]:
        """Validate Amazon Polly specific settings."""
        errors = []

        # Check if we can import boto3
        try:
            import boto3
        except ImportError:
            errors.append("boto3 not installed. Run: pip install boto3")
            return errors

        # Try to create Polly client (without making actual calls)
        try:
            boto3.client("polly", region_name=os.getenv("AWS_REGION", "us-east-1"))
            # Don't make actual API calls in validation
            logger.info("✓ Can create Polly client")
        except Exception as e:
            errors.append(f"Failed to create Polly client: {str(e)}")

        return errors

    @classmethod
    def get_configuration_report(cls) -> Dict[str, Any]:
        """Get detailed configuration report."""
        env = os.getenv("ENVIRONMENT", "development")

        report: Dict[str, Any] = {
            "environment": env,
            "aws_configured": all(
                os.getenv(setting) for setting in cls.REQUIRED_AWS_SETTINGS
            ),
            "settings": {},
        }

        # Add settings (masked)
        for setting in cls.REQUIRED_AWS_SETTINGS + cls.OPTIONAL_SETTINGS:
            value = os.getenv(setting)
            if value:
                if "KEY" in setting or "SECRET" in setting:
                    # Mask sensitive values
                    masked = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "***"
                    report["settings"][setting] = masked
                else:
                    report["settings"][setting] = value
            else:
                report["settings"][setting] = None

        # Add synthesis-specific info
        report["voice_synthesis"] = {
            "production_ready": False,
            "engine": "mock" if env == "development" else "amazon_polly",
            "languages_supported": [
                "en-US",
                "es-ES",
                "es-MX",
                "ar",
                "hi-IN",
                "bn-IN",
                "fr-FR",
                "pt-BR",
                "zh-CN",
                "ru-RU",
                "de-DE",
            ],
        }

        # Check if production synthesizer available
        try:
            # Import check to verify module availability
            __import__("src.translation.voice.synthesis.production.polly_synthesizer")

            report["voice_synthesis"]["production_ready"] = True
        except ImportError:
            pass

        return report

    @classmethod
    def suggest_env_file_content(cls) -> str:
        """Generate suggested .env file content for voice synthesis."""
        return """
# Voice Synthesis Configuration for Haven Health Passport
# CRITICAL: These settings are required for medical voice communications

# Environment (development, staging, production)
ENVIRONMENT=production

# AWS Configuration (Required for Amazon Polly)
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_REGION=us-east-1

# S3 Configuration (Optional but recommended for audio storage)
S3_BUCKET=haven-health-voice-audio

# Voice Synthesis Settings (Optional)
VOICE_SYNTHESIS_CACHE_TTL=3600  # Cache audio for 1 hour
VOICE_SYNTHESIS_DEFAULT_LANGUAGE=en-US

# Note: In production, use AWS IAM roles or AWS Secrets Manager
# instead of hardcoding credentials in .env files
"""


# Module-level validation
def validate_on_import() -> None:
    """Run validation when module is imported in production."""
    env = os.getenv("ENVIRONMENT", "development").lower()

    if env in ["production", "staging"]:
        is_valid, errors = VoiceSynthesisConfigValidator.validate_production_config()

        if not is_valid:
            # Log errors but don't raise - let the actual usage fail
            logger.error(
                "Voice synthesis configuration errors detected. "
                "Voice synthesis may not work correctly."
            )


# Run validation
validate_on_import()
