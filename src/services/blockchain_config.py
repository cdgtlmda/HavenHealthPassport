"""Blockchain configuration loader for AWS Managed Blockchain."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class BlockchainConfig:
    """Configuration loader for blockchain network settings."""

    def __init__(self) -> None:
        """Initialize blockchain configuration."""
        self._config: Dict[str, Any] = {}
        self._network_info: Optional[Dict[str, Any]] = None
        self._load_configuration()

    def _load_configuration(self) -> None:
        """Load blockchain configuration from various sources."""
        # First, try to load from environment variables
        self._config = {
            "provider": settings.BLOCKCHAIN_PROVIDER,
            "network_id": settings.MANAGED_BLOCKCHAIN_NETWORK_ID,
            "member_id": settings.MANAGED_BLOCKCHAIN_MEMBER_ID,
            "channel": settings.BLOCKCHAIN_CHANNEL,
            "chaincode": settings.BLOCKCHAIN_CHAINCODE,
            "organization": settings.BLOCKCHAIN_ORG,
            "region": settings.AWS_REGION,
        }

        # Then, try to load network info from deployed configuration
        self._load_network_info()

    def _load_network_info(self) -> None:
        """Load network information from deployed configuration file."""
        try:
            # Check multiple possible locations for network info
            possible_paths = [
                Path(settings.BASE_DIR)
                / "blockchain"
                / "aws-managed-blockchain"
                / "deployed-config"
                / "network-info.json",
                Path(settings.BASE_DIR) / "config" / "blockchain" / "network-info.json",
                Path("/opt/haven-health") / "blockchain" / "network-info.json",
            ]

            for path in possible_paths:
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f:
                        self._network_info = json.load(f)
                        logger.info(f"Loaded network info from {path}")

                        # Update config with network info
                        if "networkId" in self._network_info:
                            self._config["network_id"] = self._network_info["networkId"]
                        if "memberId" in self._network_info:
                            self._config["member_id"] = self._network_info["memberId"]
                        if "region" in self._network_info:
                            self._config["region"] = self._network_info["region"]

                        break
            else:
                logger.warning("No network-info.json file found in expected locations")

        except (json.JSONDecodeError, IOError, ValueError) as e:
            logger.error(f"Error loading network info: {e}")

    @property
    def provider(self) -> str:
        """Get blockchain provider type."""
        provider: str = self._config.get("provider", "aws_managed_blockchain")
        return provider

    @property
    def network_id(self) -> Optional[str]:
        """Get AWS Managed Blockchain network ID."""
        return self._config.get("network_id")

    @property
    def member_id(self) -> Optional[str]:
        """Get AWS Managed Blockchain member ID."""
        return self._config.get("member_id")

    @property
    def channel_name(self) -> str:
        """Get Hyperledger Fabric channel name."""
        channel: str = self._config.get("channel", "healthcare-channel")
        return channel

    @property
    def chaincode_name(self) -> str:
        """Get chaincode name."""
        chaincode: str = self._config.get("chaincode", "health-records")
        return chaincode

    @property
    def organization(self) -> str:
        """Get organization name."""
        org: str = self._config.get("organization", "HavenHealthOrg")
        return org

    @property
    def region(self) -> str:
        """Get AWS region."""
        region: str = self._config.get("region", "us-east-1")
        return region

    @property
    def is_configured(self) -> bool:
        """Check if blockchain is properly configured."""
        if self.provider == "aws_managed_blockchain":
            return bool(self.network_id and self.member_id)
        elif self.provider == "hyperledger_fabric":
            return bool(settings.BLOCKCHAIN_PEER)
        else:
            return True  # Mock/local providers are always "configured"

    def get_lambda_function_name(self, function: str) -> str:
        """Get Lambda function name for chaincode invocation."""
        prefix = os.getenv("BLOCKCHAIN_LAMBDA_PREFIX", "haven-health-blockchain")
        return f"{prefix}-{function}"

    def get_peer_endpoints(self) -> list[str]:
        """Get peer endpoints from network info."""
        if self._network_info and "peerEndpoints" in self._network_info:
            endpoints: list[str] = self._network_info["peerEndpoints"]
            return endpoints
        return []

    def get_ca_endpoint(self) -> Optional[str]:
        """Get certificate authority endpoint."""
        if self._network_info and "caEndpoint" in self._network_info:
            endpoint: str = self._network_info["caEndpoint"]
            return endpoint
        return None

    def get_orderer_endpoint(self) -> Optional[str]:
        """Get orderer endpoint."""
        if self._network_info and "ordererEndpoint" in self._network_info:
            endpoint: str = self._network_info["ordererEndpoint"]
            return endpoint
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            "provider": self.provider,
            "network_id": self.network_id,
            "member_id": self.member_id,
            "channel": self.channel_name,
            "chaincode": self.chaincode_name,
            "organization": self.organization,
            "region": self.region,
            "is_configured": self.is_configured,
            "peer_endpoints": self.get_peer_endpoints(),
            "ca_endpoint": self.get_ca_endpoint(),
            "orderer_endpoint": self.get_orderer_endpoint(),
        }


# Global blockchain config instance
_blockchain_config_instance = None


def get_blockchain_config() -> BlockchainConfig:
    """Get blockchain configuration singleton."""
    global _blockchain_config_instance
    if _blockchain_config_instance is None:
        _blockchain_config_instance = BlockchainConfig()
    return _blockchain_config_instance
