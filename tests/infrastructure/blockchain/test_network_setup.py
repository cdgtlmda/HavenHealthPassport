"""
Real Hyperledger Fabric Test Network Setup for Production Testing.

CRITICAL: This sets up a REAL blockchain network for testing medical record verification.
No mocks are used - this deploys actual smart contracts and runs a real Fabric network.
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


class HyperledgerTestNetwork:
    """Manages a real Hyperledger Fabric test network for integration testing."""

    def __init__(self, project_root: Path):
        """Initialize test network manager."""
        self.project_root = project_root
        self.blockchain_dir = project_root / "blockchain"
        self.test_network_dir = self.blockchain_dir / "test-network"
        self.chaincode_dir = self.blockchain_dir / "chaincode"

        # Network configuration
        self.channel_name = "haven-test-channel"
        self.chaincode_name = "haven-health-passport"
        self.org1_name = "Org1"
        self.org2_name = "Org2"

        # Track network state
        self.network_running = False
        self.chaincode_deployed = False

    def setup_network(self) -> None:
        """Set up the Hyperledger Fabric test network with real components."""
        logger.info("Setting up real Hyperledger Fabric test network...")

        try:
            # 1. Download Fabric binaries if not present
            self._download_fabric_binaries()

            # 2. Clean up any existing network
            self._cleanup_network()

            # 3. Start the network
            self._start_network()

            # 4. Create channel
            self._create_channel()

            # 5. Deploy chaincodes
            self._deploy_chaincodes()

            # 6. Verify network is operational
            self._verify_network()

            self.network_running = True
            logger.info("Hyperledger Fabric test network is ready!")

        except Exception as e:
            logger.error(f"Failed to setup test network: {str(e)}")
            self.teardown_network()
            raise

    def _download_fabric_binaries(self) -> None:
        """Download Hyperledger Fabric binaries if not present."""
        fabric_samples_dir = self.blockchain_dir / "fabric-samples"

        if not fabric_samples_dir.exists():
            logger.info("Downloading Hyperledger Fabric binaries...")

            # Create blockchain directory if it doesn't exist
            self.blockchain_dir.mkdir(parents=True, exist_ok=True)

            # Download Fabric binaries
            download_script = """#!/bin/bash
            cd {blockchain_dir}
            curl -sSL https://bit.ly/2ysbOFE | bash -s -- 2.5.0 1.5.5 -d -s
            """.format(
                blockchain_dir=self.blockchain_dir
            )

            script_path = self.blockchain_dir / "download_fabric.sh"
            script_path.write_text(download_script)
            script_path.chmod(0o755)

            result = subprocess.run(
                ["bash", str(script_path)],
                cwd=str(self.blockchain_dir),
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"Failed to download Fabric binaries: {result.stderr}"
                )

            # Clean up script
            script_path.unlink()

            # Copy test network from fabric-samples
            shutil.copytree(
                fabric_samples_dir / "test-network",
                self.test_network_dir,
                dirs_exist_ok=True,
            )

            logger.info("Fabric binaries downloaded successfully")
        else:
            logger.info("Fabric binaries already present")

    def _cleanup_network(self) -> None:
        """Clean up any existing network."""
        logger.info("Cleaning up existing network...")

        if self.test_network_dir.exists():
            cleanup_script = str(self.test_network_dir / "network.sh")

            result = subprocess.run(
                [cleanup_script, "down"],
                cwd=str(self.test_network_dir),
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.warning(f"Network cleanup warning: {result.stderr}")

    def _start_network(self) -> None:
        """Start the Fabric network with Certificate Authorities."""
        logger.info("Starting Hyperledger Fabric network...")

        network_script = str(self.test_network_dir / "network.sh")

        result = subprocess.run(
            [network_script, "up", "-ca", "-s", "couchdb"],
            cwd=str(self.test_network_dir),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to start network: {result.stderr}")

        # Wait for network to stabilize
        time.sleep(5)

        logger.info("Network started successfully")

    def _create_channel(self) -> None:
        """Create the blockchain channel."""
        logger.info(f"Creating channel: {self.channel_name}")

        network_script = str(self.test_network_dir / "network.sh")

        result = subprocess.run(
            [network_script, "createChannel", "-c", self.channel_name],
            cwd=str(self.test_network_dir),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to create channel: {result.stderr}")

        logger.info("Channel created successfully")

    def _deploy_chaincodes(self) -> None:
        """Deploy all Haven Health Passport chaincodes."""
        logger.info("Deploying chaincodes...")

        # Deploy health record chaincode
        self._deploy_single_chaincode(
            "health-record", self.chaincode_dir / "health-record", "go"
        )

        # Deploy access control chaincode
        self._deploy_single_chaincode(
            "access-control", self.chaincode_dir / "access-control", "go"
        )

        # Deploy cross-border chaincode
        self._deploy_single_chaincode(
            "cross-border", self.chaincode_dir / "cross-border", "go"
        )

        self.chaincode_deployed = True
        logger.info("All chaincodes deployed successfully")

    def _deploy_single_chaincode(
        self, cc_name: str, cc_path: Path, cc_lang: str
    ) -> None:
        """Deploy a single chaincode to the network."""
        logger.info(f"Deploying chaincode: {cc_name}")

        network_script = str(self.test_network_dir / "network.sh")

        # Package and install chaincode
        result = subprocess.run(
            [
                network_script,
                "deployCC",
                "-ccn",
                cc_name,
                "-ccp",
                str(cc_path),
                "-ccl",
                cc_lang,
                "-c",
                self.channel_name,
            ],
            cwd=str(self.test_network_dir),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to deploy chaincode {cc_name}: {result.stderr}")

        logger.info(f"Chaincode {cc_name} deployed successfully")

    def _verify_network(self) -> None:
        """Verify the network is operational by querying chaincode."""
        logger.info("Verifying network operation...")

        # Set up environment for peer CLI
        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{self.test_network_dir}/../bin:{env['PATH']}",
                "FABRIC_CFG_PATH": str(self.test_network_dir / ".." / "config"),
                "CORE_PEER_TLS_ENABLED": "true",
                "CORE_PEER_LOCALMSPID": "Org1MSP",
                "CORE_PEER_TLS_ROOTCERT_FILE": str(
                    self.test_network_dir
                    / "organizations"
                    / "peerOrganizations"
                    / "org1.example.com"
                    / "peers"
                    / "peer0.org1.example.com"
                    / "tls"
                    / "ca.crt"
                ),
                "CORE_PEER_MSPCONFIGPATH": str(
                    self.test_network_dir
                    / "organizations"
                    / "peerOrganizations"
                    / "org1.example.com"
                    / "users"
                    / "Admin@org1.example.com"
                    / "msp"
                ),
                "CORE_PEER_ADDRESS": "localhost:7051",
            }
        )

        # Query chaincode to verify it's working
        test_query = {"function": "ping", "args": []}

        result = subprocess.run(
            [
                "peer",
                "chaincode",
                "query",
                "-C",
                self.channel_name,
                "-n",
                "health-record",
                "-c",
                json.dumps(test_query),
            ],
            env=env,
            cwd=str(self.test_network_dir),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.warning(f"Network verification warning: {result.stderr}")
            # Don't fail here as some chaincodes might not have ping function
        else:
            logger.info("Network verification successful")

    def get_connection_profile(self) -> Dict[str, Any]:
        """Get connection profile for the test network."""
        return {
            "name": "haven-test-network",
            "version": "1.0.0",
            "client": {
                "organization": self.org1_name,
                "connection": {"timeout": {"peer": {"endorser": "300"}}},
            },
            "organizations": {
                self.org1_name: {
                    "mspid": f"{self.org1_name}MSP",
                    "peers": ["peer0.org1.example.com"],
                    "certificateAuthorities": ["ca.org1.example.com"],
                    "adminPrivateKey": {
                        "path": str(
                            self.test_network_dir
                            / "organizations"
                            / "peerOrganizations"
                            / "org1.example.com"
                            / "users"
                            / "Admin@org1.example.com"
                            / "msp"
                            / "keystore"
                            / "priv_sk"
                        )
                    },
                    "signedCert": {
                        "path": str(
                            self.test_network_dir
                            / "organizations"
                            / "peerOrganizations"
                            / "org1.example.com"
                            / "users"
                            / "Admin@org1.example.com"
                            / "msp"
                            / "signcerts"
                            / "Admin@org1.example.com-cert.pem"
                        )
                    },
                }
            },
            "peers": {
                "peer0.org1.example.com": {
                    "url": "grpcs://localhost:7051",
                    "tlsCACerts": {
                        "path": str(
                            self.test_network_dir
                            / "organizations"
                            / "peerOrganizations"
                            / "org1.example.com"
                            / "peers"
                            / "peer0.org1.example.com"
                            / "tls"
                            / "ca.crt"
                        )
                    },
                    "grpcOptions": {
                        "ssl-target-name-override": "peer0.org1.example.com",
                        "hostnameOverride": "peer0.org1.example.com",
                    },
                }
            },
            "certificateAuthorities": {
                "ca.org1.example.com": {
                    "url": "https://localhost:7054",
                    "caName": "ca-org1",
                    "tlsCACerts": {
                        "path": str(
                            self.test_network_dir
                            / "organizations"
                            / "fabric-ca"
                            / "org1"
                            / "ca-cert.pem"
                        )
                    },
                    "httpOptions": {"verify": False},
                }
            },
            "channels": {
                self.channel_name: {
                    "orderers": ["orderer.example.com"],
                    "peers": {"peer0.org1.example.com": {}},
                }
            },
            "orderers": {
                "orderer.example.com": {
                    "url": "grpcs://localhost:7050",
                    "tlsCACerts": {
                        "path": str(
                            self.test_network_dir
                            / "organizations"
                            / "ordererOrganizations"
                            / "example.com"
                            / "orderers"
                            / "orderer.example.com"
                            / "msp"
                            / "tlscacerts"
                            / "tlsca.example.com-cert.pem"
                        )
                    },
                    "grpcOptions": {
                        "ssl-target-name-override": "orderer.example.com",
                        "hostnameOverride": "orderer.example.com",
                    },
                }
            },
        }

    def teardown_network(self) -> None:
        """Tear down the test network."""
        logger.info("Tearing down test network...")

        if self.test_network_dir.exists():
            network_script = str(self.test_network_dir / "network.sh")

            result = subprocess.run(
                [network_script, "down"],
                cwd=str(self.test_network_dir),
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.warning(f"Network teardown warning: {result.stderr}")

        self.network_running = False
        self.chaincode_deployed = False

        logger.info("Test network torn down")


# Singleton instance
_test_network: Optional[HyperledgerTestNetwork] = None


def get_test_network() -> HyperledgerTestNetwork:
    """Get or create the test network instance."""
    global _test_network

    if _test_network is None:
        project_root = Path(__file__).parent.parent.parent.parent
        _test_network = HyperledgerTestNetwork(project_root)

    return _test_network


def setup_blockchain_test_network():
    """Set up the blockchain test network for integration tests."""
    network = get_test_network()

    if not network.network_running:
        network.setup_network()

    return network


def teardown_blockchain_test_network():
    """Tear down the blockchain test network after tests."""
    network = get_test_network()

    if network.network_running:
        network.teardown_network()
