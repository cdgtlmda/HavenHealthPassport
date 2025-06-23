"""
Pytest fixtures for real blockchain testing.

CRITICAL: These fixtures set up REAL blockchain networks for testing.
No mocks are used - actual smart contracts are deployed and tested.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Generator

import pytest

from src.config import settings
from src.services.blockchain_service import HyperledgerFabricService
from src.utils.logging import get_logger
from tests.infrastructure.blockchain.test_network_setup import (
    HyperledgerTestNetwork,
    setup_blockchain_test_network,
    teardown_blockchain_test_network,
)

logger = get_logger(__name__)


@pytest.fixture(scope="session")
def blockchain_test_network() -> Generator[HyperledgerTestNetwork, None, None]:
    """
    Session-scoped fixture that sets up a real Hyperledger Fabric test network.

    This fixture:
    1. Downloads Fabric binaries if needed
    2. Starts a real blockchain network
    3. Creates channels
    4. Deploys actual smart contracts
    5. Provides connection details for tests

    The network stays up for the entire test session for efficiency.
    """
    logger.info("Setting up real blockchain test network for session...")

    # Set up the network
    network = setup_blockchain_test_network()

    # Wait for network to fully stabilize
    import time

    time.sleep(10)

    yield network

    # Teardown after all tests
    logger.info("Tearing down blockchain test network...")
    teardown_blockchain_test_network()


@pytest.fixture(scope="function")
def blockchain_service(
    blockchain_test_network: HyperledgerTestNetwork,
) -> Generator[HyperledgerFabricService, None, None]:
    """
    Function-scoped fixture that provides a configured blockchain service.

    Each test gets a fresh service instance connected to the real test network.
    """
    # Get connection profile from test network
    connection_profile = blockchain_test_network.get_connection_profile()

    # Save connection profile to temp file
    profile_path = Path("/tmp/haven-test-connection-profile.json")
    profile_path.write_text(json.dumps(connection_profile, indent=2))

    # Save original attributes if they exist
    original_config = getattr(settings, "BLOCKCHAIN_NETWORK_CONFIG", None)
    original_org = getattr(settings, "BLOCKCHAIN_ORG_NAME", None)
    original_channel = getattr(settings, "BLOCKCHAIN_CHANNEL_NAME", None)

    try:
        # Configure test settings
        settings.BLOCKCHAIN_NETWORK_CONFIG = str(profile_path)
        settings.BLOCKCHAIN_ORG_NAME = blockchain_test_network.org1_name
        settings.BLOCKCHAIN_CHANNEL_NAME = blockchain_test_network.channel_name

        # Create real blockchain service
        service = HyperledgerFabricService()

        yield service

    finally:
        # Restore original settings or remove attributes
        if original_config is not None:
            settings.BLOCKCHAIN_NETWORK_CONFIG = original_config
        else:
            delattr(settings, "BLOCKCHAIN_NETWORK_CONFIG")

        if original_org is not None:
            settings.BLOCKCHAIN_ORG_NAME = original_org
        else:
            delattr(settings, "BLOCKCHAIN_ORG_NAME")

        if original_channel is not None:
            settings.BLOCKCHAIN_CHANNEL_NAME = original_channel
        else:
            delattr(settings, "BLOCKCHAIN_CHANNEL_NAME")

        # Clean up temp file
        if profile_path.exists():
            profile_path.unlink()


@pytest.fixture
def test_patient_data() -> Dict[str, Any]:
    """Provide test patient data for blockchain operations."""
    return {
        "patient_id": "test_patient_123",
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-15",
        "blood_type": "O+",
        "allergies": ["penicillin", "peanuts"],
        "medications": [{"name": "Lisinopril", "dosage": "10mg", "frequency": "daily"}],
        "medical_history": [
            {
                "condition": "Hypertension",
                "diagnosed": "2020-03-10",
                "status": "managed",
            }
        ],
    }


@pytest.fixture
def test_health_record() -> Dict[str, Any]:
    """Provide test health record data."""
    return {
        "record_type": "vaccination",
        "patient_id": "test_patient_123",
        "provider_id": "provider_456",
        "provider_name": "Haven Health Clinic",
        "record_date": "2024-01-15",
        "data": {
            "vaccine_name": "COVID-19",
            "vaccine_type": "mRNA",
            "dose_number": 3,
            "lot_number": "EL9261",
            "administration_site": "left_arm",
            "administered_by": "Dr. Jane Smith",
        },
        "verified": True,
        "verification_method": "provider_signature",
    }


@pytest.fixture
async def deployed_health_record(
    blockchain_service: HyperledgerFabricService,
    test_patient_data: Dict[str, Any],
    test_health_record: Dict[str, Any],
) -> Dict[str, Any]:
    """Deploy a test health record to the blockchain and return details."""
    # Create record hash
    record_hash = blockchain_service.create_record_hash(test_health_record)

    # Mock encryption key hash (in real scenario, this would be from KMS)
    encryption_key_hash = blockchain_service.create_record_hash({"key": "test_key_123"})

    # Submit to blockchain
    result = await blockchain_service.submit_health_record(
        patient_id=test_patient_data["patient_id"],
        record_type=test_health_record["record_type"],
        record_hash=record_hash,
        encryption_key_hash=encryption_key_hash,
        access_controls={
            "organizations": ["Haven Health Clinic", "Emergency Services"],
            "consent_required": True,
        },
    )

    return {
        "patient_id": test_patient_data["patient_id"],
        "record_hash": record_hash,
        "tx_id": result["tx_id"],
        "block_number": result.get("block_number"),
        "timestamp": result["timestamp"],
    }


@pytest.mark.blockchain
class BlockchainTestBase:
    """Base class for blockchain integration tests."""

    @pytest.fixture(autouse=True)
    def setup_blockchain_test(self, real_blockchain_service):
        """Automatically inject blockchain service into test classes."""
        self.blockchain_service = real_blockchain_service
        self.loop = asyncio.get_event_loop()

    def run_async(self, coro):
        """Run async functions in sync tests."""
        return self.loop.run_until_complete(coro)
