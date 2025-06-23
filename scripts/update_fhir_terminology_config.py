"""
Update FHIR Server Terminology Configuration

This script updates the FHIR server configuration to enable and configure
the terminology service.
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.healthcare.fhir_server_config import FHIRServerConfig
from src.utils.logging import setup_logger

logger = setup_logger(__name__)


def update_fhir_terminology_config():
    """Update FHIR server with terminology configuration"""

    logger.info("Updating FHIR server terminology configuration...")

    # Check for existing HAPI FHIR configuration
    hapi_config_path = (
        Path(project_root) / "fhir-server" / "hapi-fhir-server.properties"
    )

    if not hapi_config_path.exists():
        logger.warning(f"HAPI FHIR config not found at {hapi_config_path}")
        logger.info("Creating new configuration...")
        hapi_config_path.parent.mkdir(exist_ok=True)

    # Generate terminology properties
    terminology_props = [
        "# Terminology Service Configuration",
        "hapi.fhir.terminology.enabled=true",
        "hapi.fhir.terminology.graphql.enabled=true",
        "hapi.fhir.terminology.validation.enabled=true",
        "",
        "# Code System Support",
        "hapi.fhir.terminology.systems.snomed.enabled=true",
        "hapi.fhir.terminology.systems.loinc.enabled=true",
        "hapi.fhir.terminology.systems.icd10.enabled=true",
        "hapi.fhir.terminology.systems.rxnorm.enabled=true",
        "",
        "# Value Set Support",
        "hapi.fhir.terminology.valueset.preexpand.enabled=true",
        "hapi.fhir.terminology.valueset.preexpand.max.size=1000",
        "",
        "# Terminology Caching",
        "hapi.fhir.terminology.cache.enabled=true",
        "hapi.fhir.terminology.cache.size=10000",
        "hapi.fhir.terminology.cache.ttl=3600",
        "",
        "# Translation Support",
        "hapi.fhir.terminology.translation.enabled=true",
        "hapi.fhir.terminology.translation.languages=en,es,fr,ar,sw,ur,fa",
        "",
        "# Custom Terminology Path",
        "hapi.fhir.terminology.custom.path=data/terminology",
    ]

    # Write or append to config file
    with open(hapi_config_path, "a") as f:
        f.write("\n\n")
        f.write("\n".join(terminology_props))
        f.write("\n")

    logger.info(f"Updated HAPI FHIR configuration at {hapi_config_path}")

    # Create terminology service beans configuration
    beans_config = {
        "beans": {
            "terminologyService": {
                "class": "ca.uhn.fhir.jpa.term.TermLoaderSvcImpl",
                "properties": {
                    "customCodeSystemPath": "data/terminology/code-systems",
                    "customValueSetPath": "data/terminology/value-sets",
                },
            },
            "validationSupport": {
                "class": "ca.uhn.fhir.validation.support.CachingValidationSupport",
                "constructor-args": [{"ref": "terminologyService"}],
            },
        }
    }

    beans_path = Path(project_root) / "fhir-server" / "terminology-beans.json"
    with open(beans_path, "w") as f:
        json.dump(beans_config, f, indent=2)

    logger.info(f"Created terminology beans configuration at {beans_path}")

    # Update environment variables
    env_updates = {
        "FHIR_TERMINOLOGY_ENABLED": "true",
        "TERMINOLOGY_VALIDATION_ENABLED": "true",
        "TERMINOLOGY_SERVER_URL": "http://localhost:8080/fhir",
    }

    # Check for .env file
    env_path = Path(project_root) / ".env"
    if env_path.exists():
        with open(env_path, "a") as f:
            f.write("\n# FHIR Terminology Settings\n")
            for key, value in env_updates.items():
                f.write(f"{key}={value}\n")
        logger.info("Updated .env file with terminology settings")

    logger.info("FHIR server terminology configuration update complete!")


if __name__ == "__main__":
    update_fhir_terminology_config()
