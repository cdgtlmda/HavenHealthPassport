"""
Setup FHIR Terminology Service

This script initializes and configures the FHIR terminology service
for the Haven Health Passport system.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.healthcare.fhir_terminology_config import (
    TerminologyServiceConfig,
    initialize_terminology_service,
)
from src.utils.logging import setup_logger

logger = setup_logger(__name__)


def setup_terminology_service():
    """Setup and configure FHIR terminology service"""

    logger.info("Setting up FHIR terminology service...")

    # Create configuration
    config = TerminologyServiceConfig(
        terminology_data_dir=Path(project_root) / "data" / "terminology",
        code_systems_dir=Path(project_root) / "data" / "terminology" / "code-systems",
        value_sets_dir=Path(project_root) / "data" / "terminology" / "value-sets",
        enable_caching=True,
        load_standard_terminologies=True,
        load_custom_terminologies=True,
        supported_languages=["en", "es", "fr", "ar", "sw", "ur", "fa"],
        default_language="en",
    )

    # Initialize service
    service = initialize_terminology_service(config)

    # Display loaded systems
    logger.info("Loaded code systems:")
    for system in service.get_supported_systems():
        logger.info(f"  - {system}")

    logger.info("Loaded value sets:")
    for value_set in service.get_supported_value_sets():
        logger.info(f"  - {value_set}")

    logger.info("Terminology service setup complete!")

    return service


if __name__ == "__main__":
    setup_terminology_service()
