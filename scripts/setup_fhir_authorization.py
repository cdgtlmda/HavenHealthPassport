"""
FHIR Authorization Setup Script

This script initializes and configures the FHIR authorization system
for the Haven Health Passport server.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.healthcare.fhir_authorization import (
    AuthorizationPolicy,
    ConsentRecord,
    FHIRRole,
    ResourcePermission,
    get_authorization_handler,
)
from src.healthcare.fhir_authorization_config import (
    FHIRAuthorizationConfig,
    configure_fhir_authorization,
)
from src.healthcare.fhir_server_config import FHIRServerConfig
from src.utils.logging import setup_logger

logger = setup_logger(__name__)


def setup_fhir_authorization():
    """Setup and configure FHIR authorization"""

    logger.info("Setting up FHIR authorization...")

    # Create authorization configuration
    auth_config = FHIRAuthorizationConfig(
        authorization_enabled=True,
        authorization_mode="combined",
        rbac_enabled=True,
        abac_enabled=True,
        consent_based_access=True,
        emergency_access_enabled=True,
        authorization_audit_enabled=True,
        cache_authorization_decisions=True,
        patient_data_isolation=True,
        enforce_minimum_necessary=True,
    )

    # Create server configuration
    server_config = FHIRServerConfig(auth_enabled=True, authorization_enabled=True)

    # Configure authorization
    configurator = configure_fhir_authorization(auth_config, server_config)

    # Add custom policies for Haven Health Passport
    handler = get_authorization_handler()

    # Add refugee-specific policies
    refugee_policy = AuthorizationPolicy(
        id="refugee-data-access",
        name="Refugee Data Access Policy",
        description="Allow refugee officers to access refugee health data with consent",
        priority=75,
        enabled=True,
        conditions={"purpose_of_use": "refugee_assistance"},
        effect="allow",
        resource_types=["Patient", "Observation", "Immunization", "DocumentReference"],
        actions=[ResourcePermission.READ, ResourcePermission.SEARCH],
    )
    handler.add_policy(refugee_policy)

    # Add cross-border data access policy
    cross_border_policy = AuthorizationPolicy(
        id="cross-border-access",
        name="Cross-Border Data Access",
        description="Enable data access across borders for refugee healthcare",
        priority=80,
        enabled=True,
        conditions={"cross_border": True, "verified_healthcare_provider": True},
        effect="allow",
        resource_types=["*"],
        actions=[ResourcePermission.READ],
    )
    handler.add_policy(cross_border_policy)

    # Update server configuration
    configurator.update_server_config_with_auth()

    # Generate HAPI FHIR configuration
    hapi_config = configurator.configure_hapi_fhir_interceptors()

    # Validate configuration
    warnings = configurator.validate_configuration()
    if warnings:
        logger.warning("Configuration warnings:")
        for warning in warnings:
            logger.warning(f"  - {warning}")

    # Display configuration summary
    auth_config_dict = configurator.get_server_authorization_config()

    logger.info("Authorization configuration complete!")
    logger.info(f"Mode: {auth_config_dict['authorization']['mode']}")
    logger.info(f"RBAC: {auth_config_dict['authorization']['rbac']['enabled']}")
    logger.info(f"ABAC: {auth_config_dict['authorization']['abac']['enabled']}")
    logger.info(f"Consent: {auth_config_dict['authorization']['consent']['enabled']}")
    logger.info(
        f"Emergency Access: {auth_config_dict['authorization']['emergency_access']['enabled']}"
    )
    logger.info(f"Audit: {auth_config_dict['authorization']['audit']['enabled']}")

    return configurator


if __name__ == "__main__":
    setup_fhir_authorization()
