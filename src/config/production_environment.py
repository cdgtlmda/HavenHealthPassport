"""
Production Environment Configuration for Haven Health Passport.

CRITICAL: This module manages production environment variables and ensures
all required configuration is properly set before the application starts.

HIPAA Compliance: Environment configuration requires:
- Access control for viewing/modifying production configuration
- Audit logging of all configuration access and changes
- Role-based permissions for environment variable management
- Secure handling of sensitive configuration values
"""

import os
from typing import Any, Dict, Optional

from pydantic import ValidationError

from src.utils.logging import get_logger

logger = get_logger(__name__)


class ProductionEnvironmentConfig:
    """
    Manages production environment configuration.

    This ensures:
    - All required environment variables are set
    - Configuration is validated before app startup
    - Sensitive data is never exposed in logs
    - HIPAA compliance requirements are met
    """

    def __init__(self) -> None:
        """Initialize the production environment validator."""
        self.environment = os.getenv("ENVIRONMENT", "production")

        # Define all required environment variables
        self.required_env_vars = {
            # Core configuration
            "ENVIRONMENT": {
                "description": "Deployment environment",
                "default": "production",
                "sensitive": False,
                "validation": lambda x: x in ["production", "staging", "development"],
            },
            "AWS_REGION": {
                "description": "AWS region for services",
                "default": "us-east-1",
                "sensitive": False,
                "validation": lambda x: x.startswith("us-") or x.startswith("eu-"),
            },
            # AWS configuration
            "USE_AWS_SECRETS_MANAGER": {
                "description": "Enable AWS Secrets Manager",
                "default": "true",
                "sensitive": False,
                "validation": lambda x: x.lower() in ["true", "false"],
            },
            "AWS_SECRETS_PREFIX": {
                "description": "Prefix for secrets in AWS Secrets Manager",
                "default": "haven-health-passport/production",
                "sensitive": False,
            },
            # Application configuration
            "APP_NAME": {
                "description": "Application name",
                "default": "Haven Health Passport",
                "sensitive": False,
            },
            "APP_VERSION": {
                "description": "Application version",
                "required": True,
                "sensitive": False,
            },
            "LOG_LEVEL": {
                "description": "Logging level",
                "default": "INFO",
                "sensitive": False,
                "validation": lambda x: x
                in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            },
            # Database configuration
            "DATABASE_POOL_SIZE": {
                "description": "Database connection pool size",
                "default": "20",
                "sensitive": False,
                "validation": lambda x: x.isdigit() and int(x) > 0,
            },
            "DATABASE_MAX_OVERFLOW": {
                "description": "Maximum overflow connections",
                "default": "10",
                "sensitive": False,
                "validation": lambda x: x.isdigit() and int(x) >= 0,
            },
            # Redis configuration
            "REDIS_MAX_CONNECTIONS": {
                "description": "Redis connection pool size",
                "default": "50",
                "sensitive": False,
                "validation": lambda x: x.isdigit() and int(x) > 0,
            },
            "CACHE_TTL": {
                "description": "Default cache TTL in seconds",
                "default": "300",
                "sensitive": False,
                "validation": lambda x: x.isdigit() and int(x) > 0,
            },
            # Security configuration
            "PHI_ENCRYPTION_ENABLED": {
                "description": "Enable PHI encryption",
                "default": "true",
                "sensitive": False,
                "validation": lambda x: x.lower()
                == "true",  # Must be true in production
            },
            "PHI_ACCESS_AUDIT_ENABLED": {
                "description": "Enable PHI access auditing",
                "default": "true",
                "sensitive": False,
                "validation": lambda x: x.lower()
                == "true",  # Must be true in production
            },
            "REQUIRE_MFA_FOR_PHI_ACCESS": {
                "description": "Require MFA for PHI access",
                "default": "true",
                "sensitive": False,
                "validation": lambda x: x.lower() in ["true", "false"],
            },
            "SESSION_LIFETIME_MINUTES": {
                "description": "Session lifetime in minutes",
                "default": "30",
                "sensitive": False,
                "validation": lambda x: x.isdigit() and int(x) > 0 and int(x) <= 60,
            },
            # API configuration
            "API_RATE_LIMIT": {
                "description": "API rate limit per minute",
                "default": "100",
                "sensitive": False,
                "validation": lambda x: x.isdigit() and int(x) > 0,
            },
            "API_TIMEOUT_SECONDS": {
                "description": "API request timeout",
                "default": "30",
                "sensitive": False,
                "validation": lambda x: x.isdigit() and int(x) > 0,
            },
            "CORS_ORIGINS": {
                "description": "Allowed CORS origins (comma-separated)",
                "default": "https://havenhealthpassport.org",
                "sensitive": False,
            },
            # Healthcare service configuration
            "FHIR_VERSION": {
                "description": "FHIR version",
                "default": "R4",
                "sensitive": False,
                "validation": lambda x: x in ["R4", "STU3"],
            },
            "MEDICAL_TERMINOLOGY_CACHE_TTL": {
                "description": "Medical terminology cache TTL in seconds",
                "default": "3600",
                "sensitive": False,
                "validation": lambda x: x.isdigit() and int(x) > 0,
            },
            # Voice service configuration
            "VOICE_SYNTHESIS_ENGINE": {
                "description": "Voice synthesis engine",
                "default": "aws_polly",
                "sensitive": False,
                "validation": lambda x: x
                in ["aws_polly", "azure_speech", "google_tts"],
            },
            "VOICE_SYNTHESIS_S3_BUCKET": {
                "description": "S3 bucket for voice synthesis cache",
                "required": True,
                "sensitive": False,
            },
            # SMS configuration
            "SMS_PROVIDER": {
                "description": "SMS service provider",
                "default": "aws_sns",
                "sensitive": False,
                "validation": lambda x: x in ["aws_sns", "twilio"],
            },
            "SMS_FROM_NUMBER": {
                "description": "SMS sender number",
                "required": True,
                "sensitive": False,
            },
            "SMS_RATE_LIMIT_PER_HOUR": {
                "description": "SMS rate limit per hour",
                "default": "10",
                "sensitive": False,
                "validation": lambda x: x.isdigit() and int(x) > 0,
            },
            # Monitoring configuration
            "ENABLE_APM": {
                "description": "Enable application performance monitoring",
                "default": "true",
                "sensitive": False,
                "validation": lambda x: x.lower() in ["true", "false"],
            },
            "METRICS_EXPORT_INTERVAL": {
                "description": "Metrics export interval in seconds",
                "default": "60",
                "sensitive": False,
                "validation": lambda x: x.isdigit() and int(x) > 0,
            },
            # Feature flags
            "ENABLE_BLOCKCHAIN_VERIFICATION": {
                "description": "Enable blockchain verification",
                "default": "true",
                "sensitive": False,
                "validation": lambda x: x.lower() in ["true", "false"],
            },
            "ENABLE_OFFLINE_MODE": {
                "description": "Enable offline mode support",
                "default": "true",
                "sensitive": False,
                "validation": lambda x: x.lower() in ["true", "false"],
            },
            "ENABLE_VOICE_INTERFACE": {
                "description": "Enable voice interface",
                "default": "true",
                "sensitive": False,
                "validation": lambda x: x.lower() in ["true", "false"],
            },
        }

    def configure_environment(self) -> Dict[str, Any]:
        """
        Configure all environment variables.

        Returns:
            Dictionary with configuration results
        """
        logger.info("Configuring production environment variables...")

        results: Dict[str, Any] = {
            "configured": {},
            "missing": [],
            "invalid": [],
            "warnings": [],
            "is_valid": True,
        }

        # Check each required variable
        for var_name, config in self.required_env_vars.items():
            value = os.getenv(var_name, config.get("default"))

            # Check if required variable is missing
            if config.get("required", False) and not value:
                results["missing"].append(var_name)
                results["is_valid"] = False
                continue

            # Set default if not present
            if not value and "default" in config:
                value = config["default"]
                os.environ[var_name] = str(value)
                results["configured"][var_name] = "default"
            else:
                results["configured"][var_name] = "set"

            # Validate value
            if value and "validation" in config:
                try:
                    validation_fn = config["validation"]
                    if callable(validation_fn) and not validation_fn(value):
                        results["invalid"].append(f"{var_name}={value}")
                        results["is_valid"] = False
                except (TypeError, ValidationError, ValueError) as e:
                    results["invalid"].append(f"{var_name}: {e}")
                    results["is_valid"] = False

        # Production-specific validations
        if self.environment == "production":
            # Ensure critical security settings
            if os.getenv("PHI_ENCRYPTION_ENABLED", "true").lower() != "true":
                results["invalid"].append(
                    "PHI_ENCRYPTION_ENABLED must be 'true' in production"
                )
                results["is_valid"] = False

            if os.getenv("PHI_ACCESS_AUDIT_ENABLED", "true").lower() != "true":
                results["invalid"].append(
                    "PHI_ACCESS_AUDIT_ENABLED must be 'true' in production"
                )
                results["is_valid"] = False

            if os.getenv("USE_AWS_SECRETS_MANAGER", "true").lower() != "true":
                results["invalid"].append(
                    "USE_AWS_SECRETS_MANAGER must be 'true' in production"
                )
                results["is_valid"] = False

            # Warn about security settings
            if os.getenv("REQUIRE_MFA_FOR_PHI_ACCESS", "true").lower() != "true":
                results["warnings"].append(
                    "MFA for PHI access is disabled - security risk!"
                )

            if os.getenv("LOG_LEVEL", "INFO") == "DEBUG":
                results["warnings"].append(
                    "DEBUG logging enabled in production - may expose sensitive data!"
                )

        # Log configuration status
        logger.info(
            f"Environment configuration complete: {len(results['configured'])} variables configured"
        )

        if results["missing"]:
            logger.error(f"Missing required variables: {results['missing']}")

        if results["invalid"]:
            logger.error(f"Invalid variable values: {results['invalid']}")

        if results["warnings"]:
            for warning in results["warnings"]:
                logger.warning(warning)

        return results

    def generate_env_template(self, output_file: str = ".env.template") -> None:
        """Generate environment variable template file."""
        try:
            content = [
                "# Haven Health Passport - Production Environment Variables",
                f"# Generated: {os.popen('date').read().strip()}",
                "# CRITICAL: This is a medical system - configure all variables properly!",
                "",
                "# Copy this file to .env and configure all values",
                "# DO NOT commit .env files to version control!",
                "",
            ]

            # Group variables by category
            categories = {
                "Core Configuration": [
                    "ENVIRONMENT",
                    "AWS_REGION",
                    "APP_NAME",
                    "APP_VERSION",
                    "LOG_LEVEL",
                ],
                "AWS Services": ["USE_AWS_SECRETS_MANAGER", "AWS_SECRETS_PREFIX"],
                "Database": ["DATABASE_POOL_SIZE", "DATABASE_MAX_OVERFLOW"],
                "Redis/Cache": ["REDIS_MAX_CONNECTIONS", "CACHE_TTL"],
                "Security": [
                    "PHI_ENCRYPTION_ENABLED",
                    "PHI_ACCESS_AUDIT_ENABLED",
                    "REQUIRE_MFA_FOR_PHI_ACCESS",
                    "SESSION_LIFETIME_MINUTES",
                ],
                "API": ["API_RATE_LIMIT", "API_TIMEOUT_SECONDS", "CORS_ORIGINS"],
                "Healthcare": ["FHIR_VERSION", "MEDICAL_TERMINOLOGY_CACHE_TTL"],
                "Voice Services": [
                    "VOICE_SYNTHESIS_ENGINE",
                    "VOICE_SYNTHESIS_S3_BUCKET",
                ],
                "SMS Services": [
                    "SMS_PROVIDER",
                    "SMS_FROM_NUMBER",
                    "SMS_RATE_LIMIT_PER_HOUR",
                ],
                "Monitoring": ["ENABLE_APM", "METRICS_EXPORT_INTERVAL"],
                "Feature Flags": [
                    "ENABLE_BLOCKCHAIN_VERIFICATION",
                    "ENABLE_OFFLINE_MODE",
                    "ENABLE_VOICE_INTERFACE",
                ],
            }

            for category, var_names in categories.items():
                content.append(f"# {category}")
                content.append("# " + "-" * 50)

                for var_name in var_names:
                    if var_name in self.required_env_vars:
                        config = self.required_env_vars[var_name]
                        content.append(f"# {config['description']}")

                        if config.get("required"):
                            content.append("# REQUIRED")

                        if "validation" in config:
                            content.append("# Validation: see configuration docs")

                        if "default" in config:
                            content.append(f"{var_name}={config['default']}")
                        else:
                            content.append(f"{var_name}=")

                        content.append("")

                content.append("")

            # Write template file
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("\n".join(content))

            logger.info("Environment template written to: %s", output_file)

        except (
            OSError,
            TypeError,
            ValidationError,
            ValueError,
        ) as e:
            logger.error(f"Failed to generate environment template: {e}")
            raise

    def validate_environment(self) -> bool:
        """
        Validate that environment is properly configured for production.

        Returns:
            True if environment is valid
        """
        results = self.configure_environment()

        if not results["is_valid"]:
            logger.error("Environment configuration is invalid!")

            if results["missing"]:
                print("\n❌ Missing required environment variables:")
                for var in results["missing"]:
                    print(f"  - {var}")

            if results["invalid"]:
                print("\n❌ Invalid environment variable values:")
                for var in results["invalid"]:
                    print(f"  - {var}")

            print(
                "\nRun 'python scripts/configure_environment.py' to fix these issues."
            )

            return False

        logger.info("✅ Environment configuration validated successfully")
        return True


# Global instance
_env_config: Optional[ProductionEnvironmentConfig] = None


def get_environment_config() -> ProductionEnvironmentConfig:
    """Get or create environment configuration instance."""
    global _env_config  # pylint: disable=global-statement  # Singleton pattern for config instance
    if _env_config is None:
        _env_config = ProductionEnvironmentConfig()
    return _env_config


def configure_production_environment() -> bool:
    """
    Configure and validate production environment.

    Returns:
        True if configuration is valid
    """
    config = get_environment_config()
    results = config.configure_environment()

    if not results["is_valid"]:
        if os.getenv("ENVIRONMENT") == "production":
            raise RuntimeError(
                "Invalid environment configuration in production! "
                f"Missing: {results['missing']}, Invalid: {results['invalid']}"
            )

    return bool(results["is_valid"])
