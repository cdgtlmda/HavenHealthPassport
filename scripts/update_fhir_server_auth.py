"""
Update FHIR Server with Authorization Configuration

This script updates the existing FHIR server configuration to enable
and configure authorization.
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.healthcare.fhir_authorization_config import (
    FHIRAuthorizationConfig,
    get_authorization_configurator,
)
from src.healthcare.fhir_server_config import FHIRServerConfig
from src.utils.logging import setup_logger

logger = setup_logger(__name__)


def update_fhir_server_auth():
    """Update FHIR server with authorization configuration"""

    logger.info("Updating FHIR server authorization configuration...")

    # Check for existing HAPI FHIR configuration
    hapi_config_path = (
        Path(project_root) / "fhir-server" / "hapi-fhir-server.properties"
    )

    if not hapi_config_path.exists():
        logger.warning(f"HAPI FHIR config not found at {hapi_config_path}")
        logger.info("Creating new configuration...")
        hapi_config_path.parent.mkdir(exist_ok=True)

    # Get authorization configurator
    configurator = get_authorization_configurator()

    # Generate authorization properties
    auth_props = [
        "# Authorization Configuration",
        "hapi.fhir.security.authorization.enabled=true",
        "hapi.fhir.security.authorization.type=combined",
        "",
        "# Role-Based Access Control",
        "hapi.fhir.security.rbac.enabled=true",
        "hapi.fhir.security.rbac.default.roles=patient",
        "",
        "# Attribute-Based Access Control",
        "hapi.fhir.security.abac.enabled=true",
        "",
        "# Consent Management",
        "hapi.fhir.security.consent.enabled=true",
        "hapi.fhir.security.consent.default.policy=opt-in",
        "",
        "# Emergency Access",
        "hapi.fhir.security.emergency.access.enabled=true",
        "hapi.fhir.security.emergency.access.duration.hours=24",
        "hapi.fhir.security.emergency.access.requires.justification=true",
        "",
        "# Audit Configuration",
        "hapi.fhir.security.audit.authorization.enabled=true",
        "hapi.fhir.security.audit.failed.attempts=true",
        "hapi.fhir.security.audit.success.attempts=true",
        "",
        "# Performance Settings",
        "hapi.fhir.security.cache.authorization.decisions=true",
        "hapi.fhir.security.cache.ttl.seconds=300",
        "",
        "# Data Isolation",
        "hapi.fhir.security.patient.data.isolation=true",
        "hapi.fhir.security.practitioner.org.isolation=true",
        "",
        "# HIPAA Compliance",
        "hapi.fhir.security.enforce.minimum.necessary=true",
        "hapi.fhir.security.enforce.purpose.of.use=true",
    ]

    # Write or append to config file
    with open(hapi_config_path, "a") as f:
        f.write("\n\n")
        f.write("\n".join(auth_props))
        f.write("\n")

    logger.info(f"Updated HAPI FHIR configuration at {hapi_config_path}")

    # Create authorization interceptor configuration
    interceptor_config = configurator.configure_hapi_fhir_interceptors()
    interceptor_config_path = (
        Path(project_root) / "fhir-server" / "authorization-interceptors.json"
    )

    with open(interceptor_config_path, "w") as f:
        json.dump(interceptor_config, f, indent=2)

    logger.info(f"Created interceptor configuration at {interceptor_config_path}")

    # Update environment variables
    env_updates = {
        "FHIR_AUTH_ENABLED": "true",
        "FHIR_AUTHORIZATION_ENABLED": "true",
        "FHIR_AUTHORIZATION_MODE": "combined",
        "FHIR_RBAC_ENABLED": "true",
        "FHIR_ABAC_ENABLED": "true",
        "FHIR_CONSENT_BASED_ACCESS": "true",
        "FHIR_EMERGENCY_ACCESS_ENABLED": "true",
    }

    # Check for .env file
    env_path = Path(project_root) / ".env"
    if env_path.exists():
        with open(env_path, "a") as f:
            f.write("\n# FHIR Authorization Settings\n")
            for key, value in env_updates.items():
                f.write(f"{key}={value}\n")
        logger.info("Updated .env file with authorization settings")

    logger.info("FHIR server authorization configuration update complete!")


if __name__ == "__main__":
    update_fhir_server_auth()
