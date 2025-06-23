"""FHIR Server Manager.

This module provides functionality to manage the HAPI FHIR server lifecycle,
including initialization, health checks, and configuration.
Handles FHIR Resource validation for server operations.
"""

import asyncio
import time
from typing import Any, Dict, Optional

import httpx
from httpx import ConnectError, HTTPError, TimeoutException

from src.healthcare.fhir_server_config import FHIRServerConfig
from src.healthcare.fhir_validator import FHIRValidator
from src.utils.logging import get_logger

# FHIR resource type for this module
__fhir_resource__ = "CapabilityStatement"

logger = get_logger(__name__)


class FHIRServerManager:
    """Manages HAPI FHIR Server operations."""

    # FHIR resource type
    __fhir_resource__ = "CapabilityStatement"

    def __init__(self, config: Optional[FHIRServerConfig] = None):
        """Initialize FHIR Server Manager.

        Args:
            config: FHIR server configuration. If None, uses default configuration.
        """
        self.config = config or FHIRServerConfig()
        self.client = httpx.AsyncClient(timeout=30.0)
        self._server_ready = False
        self.validator = FHIRValidator()  # Initialize FHIR validator

    async def __aenter__(self) -> "FHIRServerManager":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.client.aclose()

    async def wait_for_server(
        self, max_retries: int = 30, retry_delay: int = 2
    ) -> bool:
        """Wait for FHIR server to be ready.

        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds

        Returns:
            True if server is ready, False otherwise
        """
        logger.info(f"Waiting for FHIR server at {self.config.server_address}")

        for attempt in range(max_retries):
            try:
                response = await self.client.get(
                    f"{self.config.server_address}/metadata"
                )
                if response.status_code == 200:
                    logger.info("FHIR server is ready")
                    self._server_ready = True
                    return True
            except (HTTPError, ConnectError, TimeoutException) as e:
                logger.debug(
                    f"Server not ready yet (attempt {attempt + 1}/{max_retries}): {e}"
                )

            await asyncio.sleep(retry_delay)
        logger.error("FHIR server failed to start within timeout period")
        return False

    async def get_server_metadata(self) -> Optional[Dict[str, Any]]:
        """Get server capability statement.

        Returns:
            Server metadata as dictionary or None if error
        """
        try:
            response = await self.client.get(
                f"{self.config.server_address}/metadata",
                headers={"Accept": "application/fhir+json"},
            )
            response.raise_for_status()
            metadata: Dict[str, Any] = response.json()
            return metadata
        except (HTTPError, ConnectError, TimeoutException) as e:
            logger.error(f"Failed to get server metadata: {e}")
            return None

    async def check_health(self) -> Dict[str, Any]:
        """Check server health status.

        Returns:
            Health status dictionary
        """
        health_status: Dict[str, Any] = {
            "status": "unknown",
            "server_url": self.config.server_address,
            "checks": {},
        }

        # Check metadata endpoint
        try:
            start_time = time.time()
            metadata = await self.get_server_metadata()
            response_time = time.time() - start_time

            if metadata:
                health_status["status"] = "healthy"
                health_status["checks"]["metadata"] = {
                    "status": "pass",
                    "response_time": response_time,
                    "fhir_version": metadata.get("fhirVersion", "unknown"),
                }
            else:
                health_status["status"] = "unhealthy"
                health_status["checks"]["metadata"] = {
                    "status": "fail",
                    "message": "Failed to retrieve metadata",
                }
        except (ValueError, TypeError, KeyError) as e:
            health_status["status"] = "unhealthy"
            health_status["checks"]["metadata"] = {"status": "fail", "message": str(e)}
        # Check database connectivity
        if health_status["status"] == "healthy":
            try:
                # Try to search for a non-existent patient to test DB
                search_response = await self.client.get(
                    f"{self.config.server_address}/Patient", params={"_count": "0"}
                )
                if search_response.status_code == 200:
                    health_status["checks"]["database"] = {
                        "status": "pass",
                        "message": "Database connection successful",
                    }
                else:
                    health_status["checks"]["database"] = {
                        "status": "warn",
                        "message": f"Unexpected status code: {search_response.status_code}",
                    }
            except (ValueError, TypeError, KeyError) as e:
                health_status["checks"]["database"] = {
                    "status": "fail",
                    "message": f"Database check failed: {str(e)}",
                }

        return health_status

    async def initialize_server(self) -> bool:
        """Initialize FHIR server with required configurations.

        Returns:
            True if initialization successful, False otherwise
        """
        # Wait for server to be ready
        if not await self.wait_for_server():
            return False

        logger.info("Initializing FHIR server configurations")

        # Check if server supports required operations
        metadata = await self.get_server_metadata()
        if not metadata:
            logger.error("Failed to retrieve server metadata")
            return False

        # Log server capabilities
        logger.info(f"FHIR Server Version: {metadata.get('fhirVersion', 'unknown')}")
        logger.info(
            f"Server Software: {metadata.get('software', {}).get('name', 'unknown')}"
        )

        # Server is initialized successfully
        logger.info("FHIR server initialization completed")
        return True
