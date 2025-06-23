"""
Voice synthesis factory for environment-based service selection.

This module ensures the correct voice synthesis implementation is used
based on the environment, preventing mock implementations in production.

FHIR Compliance: Voice synthesis for medical Resource communication must be validated.
"""

import os
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)


class VoiceSynthesisFactory:
    """Factory for creating appropriate voice synthesis instances."""

    @staticmethod
    def create_synthesizer(force_production: bool = False) -> Any:
        """
        Create appropriate synthesizer based on environment.

        Args:
            force_production: Force use of production synthesizer

        Returns:
            Appropriate synthesizer instance

        Raises:
            RuntimeError: If production synthesizer required but not available
        """
        env = os.getenv("ENVIRONMENT", "development").lower()
        voice_engine = os.getenv("VOICE_SYNTHESIS_ENGINE", "aws_polly")

        # CRITICAL: Production MUST use real voice synthesis
        if env == "production":
            if voice_engine != "aws_polly":
                raise RuntimeError(
                    f"CRITICAL: Production requires AWS Polly, but engine is '{voice_engine}'. "
                    f"Configure VOICE_SYNTHESIS_ENGINE='aws_polly' for patient communications."
                )

            # Validate S3 bucket is configured
            s3_bucket = os.getenv("VOICE_SYNTHESIS_S3_BUCKET")
            if not s3_bucket:
                raise RuntimeError(
                    "CRITICAL: VOICE_SYNTHESIS_S3_BUCKET not configured! "
                    "Required for caching synthesized audio in production."
                )

            # Only import production synthesizer
            try:
                from src.translation.voice.synthesis.production.polly_synthesizer import (
                    PollyMedicalSynthesizer,
                )

                logger.info("Creating production Amazon Polly synthesizer")
                return PollyMedicalSynthesizer()
            except ImportError as e:
                raise RuntimeError(
                    f"CRITICAL: Cannot import production voice synthesizer! "
                    f"Error: {e}. Patient communications require real TTS."
                )

        # Staging should also use production synthesizer
        if env == "staging" or force_production:
            try:
                from src.translation.voice.synthesis.production.polly_synthesizer import (
                    PollyMedicalSynthesizer,
                )

                logger.info("Creating Amazon Polly synthesizer for staging")
                return PollyMedicalSynthesizer()
            except ImportError:
                logger.warning(
                    "Production synthesizer not available in staging, using mock"
                )
                from src.translation.voice.synthesis.voice_synthesizer import (
                    voice_synthesizer,
                )

                return voice_synthesizer

        # Development environment
        if env in ["development", "test", "local"]:
            use_mock = os.getenv("USE_MOCK_VOICE_SYNTHESIS", "true").lower() == "true"

            if not use_mock and voice_engine == "aws_polly":
                try:
                    from src.translation.voice.synthesis.production.polly_synthesizer import (
                        PollyMedicalSynthesizer,
                    )

                    logger.info("Using real Polly synthesizer in development")
                    return PollyMedicalSynthesizer()
                except ImportError:
                    logger.warning("Polly not available, falling back to mock")

            # Use mock for development
            logger.info("Using mock voice synthesizer for development")
            from src.translation.voice.synthesis.voice_synthesizer import (
                voice_synthesizer,
            )

            return voice_synthesizer

        # Unknown environment
        raise RuntimeError(f"Cannot determine voice synthesizer for environment: {env}")

    @staticmethod
    def validate_production_ready() -> bool:
        """
        Validate that production voice synthesis is available.

        Returns:
            True if production synthesis is available
        """
        try:
            from src.translation.voice.synthesis.production.polly_synthesizer import (
                polly_synthesizer,
            )

            return polly_synthesizer is not None
        except ImportError:
            return False


# Module-level validation
def validate_voice_synthesis_configuration() -> None:
    """Validate voice synthesis configuration on module load."""
    env = os.getenv("ENVIRONMENT", "development").lower()

    if env in ["production", "staging"]:
        if not VoiceSynthesisFactory.validate_production_ready():
            logger.error(
                "CRITICAL: Voice synthesis validation failed! "
                "Production environment requires real TTS implementation."
            )
            # Don't raise here - let the factory raise when actually used
        else:
            logger.info("Voice synthesis configuration validated for production")
    else:
        logger.info("Voice synthesis in development mode - mocks will be used")


# Run validation on import
validate_voice_synthesis_configuration()
