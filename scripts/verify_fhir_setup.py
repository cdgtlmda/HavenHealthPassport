#!/usr/bin/env python3
"""
FHIR Server Setup Verification Script

This script verifies that the HAPI FHIR server is properly installed and configured.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.healthcare.fhir_server_config import FHIRServerConfig
from src.healthcare.fhir_server_manager import FHIRServerManager
from src.utils.logging import setup_logger

logger = setup_logger(__name__)


async def verify_fhir_server_setup():
    """Verify FHIR server installation and configuration"""
    logger.info("Starting FHIR Server Setup Verification")
    logger.info("=" * 60)

    # Load configuration
    config = FHIRServerConfig()
    logger.info(f"Server URL: {config.server_address}")
    logger.info(f"FHIR Version: {config.fhir_version}")
    logger.info(f"CORS Enabled: {config.cors_enabled}")
    logger.info(f"Audit Enabled: {config.audit_enabled}")
    logger.info(
        f"Subscriptions Enabled: REST Hook={config.subscription_resthook_enabled}, WebSocket={config.subscription_websocket_enabled}"
    )
    logger.info(f"Bulk Export Enabled: {config.bulk_export_enabled}")

    # Initialize server manager
    async with FHIRServerManager(config) as manager:
        # Check if server is ready
        logger.info("\nChecking server availability...")
        if not await manager.wait_for_server(max_retries=5):
            logger.error("❌ FHIR server is not accessible")
            logger.error(
                "Please ensure the FHIR server is running with: docker-compose up fhir-server"
            )
            return False

        # Get server metadata
        logger.info("\n✅ Server is accessible")
        logger.info("Retrieving server metadata...")

        metadata = await manager.get_server_metadata()
        if metadata:
            logger.info(
                f"✅ Server Name: {metadata.get('software', {}).get('name', 'Unknown')}"
            )
            logger.info(f"✅ FHIR Version: {metadata.get('fhirVersion', 'Unknown')}")
            logger.info(f"✅ Server ID: {metadata.get('id', 'Unknown')}")
        else:
            logger.error("❌ Failed to retrieve server metadata")
            return False
        # Check server health
        logger.info("\nPerforming health check...")
        health = await manager.check_health()
        logger.info(f"Health Status: {health['status']}")

        for check_name, check_result in health.get("checks", {}).items():
            status_symbol = "✅" if check_result["status"] == "pass" else "❌"
            logger.info(f"{status_symbol} {check_name}: {check_result['status']}")
            if "message" in check_result:
                logger.info(f"   Message: {check_result['message']}")

        # Verify server configuration
        logger.info("\nVerifying server configuration...")
        if config.cors_enabled and health["status"] == "healthy":
            logger.info("✅ CORS is enabled")
        else:
            logger.warning("⚠️  CORS configuration could not be verified")

        logger.info("\n" + "=" * 60)
        logger.info("FHIR Server Setup Verification Complete")

        return health["status"] == "healthy"


def main():
    """Main entry point"""
    try:
        success = asyncio.run(verify_fhir_server_setup())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nVerification cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Verification failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
