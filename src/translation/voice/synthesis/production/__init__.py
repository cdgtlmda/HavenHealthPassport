"""
Production voice synthesis integration module.

This module integrates the production Amazon Polly synthesizer into the
existing voice synthesis system, replacing mock implementations with
real AWS services for medical communications.
"""

import os
from typing import Any, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


def get_production_synthesizer() -> Any:
    """Get the appropriate synthesizer based on environment."""
    env = os.getenv("ENVIRONMENT", "development").lower()

    if env in ["production", "staging"]:
        # Use production Polly synthesizer
        try:
            from src.translation.voice.synthesis.production.polly_synthesizer import (
                polly_synthesizer,
            )

            logger.info("Using production Amazon Polly synthesizer")
            return polly_synthesizer
        except ImportError as e:
            logger.error(f"Failed to import production synthesizer: {e}")
            raise RuntimeError(
                "CRITICAL: Production voice synthesis not available. "
                "This is required for medical communications!"
            )
    else:
        # Development mode - return None to use existing mock
        logger.warning(
            "Using mock voice synthesis in development. "
            "Set ENVIRONMENT=production for real synthesis."
        )
        return None


# Initialize on module load
production_synthesizer = get_production_synthesizer()
