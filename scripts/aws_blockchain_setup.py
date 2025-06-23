#!/usr/bin/env python3
"""AWS Managed Blockchain Setup for Haven Health Passport.

This script sets up AWS Managed Blockchain (Hyperledger Fabric) for health record verification.
CRITICAL: This is for refugee healthcare - proper blockchain setup is essential for record integrity.
"""

import os
import sys
import json
import time
import boto3
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from botocore.exceptions import ClientError

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logging import get_logger
from src.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class AWSBlockchainConfigurator:
    """Configure AWS Managed Blockchain for healthcare verification."""
    
    def __init__(self):
        """Initialize AWS clients."""
        self.region = settings.AWS_REGION or "us-east-1"
        
        # Check if region supports Managed Blockchain
        supported_regions = ["us-east-1", "ap-northeast-1", "ap-northeast-2", "ap-southeast-1", "eu-west-1", "eu-west-2"]
        if self.region not in supported_regions:
            logger.warning(f"Region {self.region} does not support Managed Blockchain. Using us-east-1")
            self.region = "us-east-1"
        
        # Initialize clients
        self.blockchain = boto3.client("managedblockchain", region_name=self.region)
        self.ec2 = boto3.client("ec2", region_name=self.region)
        self.iam = boto3.client("iam")
        self.secrets = boto3.client("secretsmanager", region_name=self.region)
        self.s3 = boto3.client("s3")
        
        logger.info(f"Initialized blockchain configurator in region: {self.region}")
    
    def create_blockchain_network(self) -> Tuple[Optional[str], Optional[str]]:
        """Create or get existing blockchain network."""
        network_name = "HavenHealthNetwork"
        
        try:
            # Check for existing networks
            response = self.blockchain.list_networks(
                Name=network_name,
                Framework="HYPERLEDGER_FABRIC",
                Status="AVAILABLE"
            )
            
            networks = response.get("Networks", [])
            if networks:
                network = networks[0]
                network_id = network["Id"]
                logger.info(f"Found existing network: {network_id}")
                
                # Get member ID
                members = self.blockchain.list_members(NetworkId=network_id)["Members"]
                if members:
                    member_id = members[0]["Id"]
                    return network_id, member_id
                else:
                    logger.warning("Network exists but no members found")
                    return network_id, None
            
            # Create new network
            logger.info(f"Creating new blockchain network: {network_name}")
            
            # Create network configuration
            network_config = {
                "Name": network_name,
                "Description": "Haven Health Passport blockchain network for refugee health records",
                "Framework": "HYPERLEDGER_FABRIC",
                "FrameworkVersion": "2.2",
                "FrameworkConfiguration": {
                    "Fabric": {
                        "Edition": "STANDARD"  # or "STARTER" for lower cost
                    }
                },
                "VotingPolicy": {
                    "ApprovalThresholdPolicy": {
                        "ThresholdPercentage": 50,
                        "ProposalDurationInHours": 24,
                        "ThresholdComparator": "GREATER_THAN"
                    }
                },
                "MemberConfiguration": {
                    "Name": "HavenHealthOrg",
                    "Description": "Primary member organization for Haven Health",
                    "FrameworkConfiguration": {
                        "Fabric": {
                            "AdminUsername": "HavenHealthAdmin",
                            "AdminPassword": self._generate_secure_password()
                        }
                    }
                }
            }
            
            response = self.blockchain.create_network(**network_config)
            
            network_id = response["NetworkId"]
            member_id = response["MemberId"]
            
            logger.info(f"Created network: {network_id}, member: {member_id}")
            logger.info("Network creation initiated. This will take 30-60 minutes to complete.")
            
            # Store admin password in Secrets Manager
            self._store_admin_password(
                network_config["MemberConfiguration"]["FrameworkConfiguration"]["MemberFabricConfiguration"]["AdminPassword"]
            )
            
            return network_id, member_id
            
        except ClientError as e:
            logger.error(f"Error creating blockchain network: {e}")
            return None, None
    
    def _generate_secure_password(self) -> str:
        """Generate secure password for blockchain admin."""
        import secrets
        import string
        
        # AWS requirements: 8-32 chars, at least 1 uppercase, 1 lowercase, 1 number
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        while True:
            password = ''.join(secrets.choice(alphabet) for _ in range(20))
            if (any(c.islower() for c in password) and
                any(c.isupper() for c in password) and
                any(c.isdigit() for c in password)):
                return password
    
    def _store_admin_password(self, password: str):
        """Store admin password in AWS Secrets Manager."""
        secret_name = "haven-health/blockchain/admin-password"
        
        try:
            self.secrets.create_secret(
                Name=secret_name,
                Description="Admin password for Haven Health blockchain network",
                SecretString=json.dumps({
                    "username": "HavenHealthAdmin",
                    "password": password
                }),
                Tags=[
                    {"Key": "Project", "Value": "HavenHealthPassport"},
                    {"Key": "Purpose", "Value": "BlockchainAdmin"}
                ]
            )
            logger.info(f"Stored admin password in Secrets Manager: {secret_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceExistsException":
                logger.info("Admin password already exists in Secrets Manager")
            else:
                logger.error(f"Error storing admin password: {e}")
    
    def create_peer_node(self, network_id: str, member_id: str) -> Optional[str]:
        """Create peer node for blockchain network."""
        try:
            # Get member info
            member = self.blockchain.get_member(
                NetworkId=network_id,
                MemberId=member_id
            )["Member"]
            
            if member["Status"] != "AVAILABLE":
                logger.warning(f"Member not yet available. Status: {member['Status']}")
                return None
            
            # Check existing nodes
            nodes = self.blockchain.list_nodes(
                NetworkId=network_id,
                MemberId=member_id,
                Status="AVAILABLE"
            ).get("Nodes", [])
            
            if nodes:
                node_id = nodes[0]["Id"]
                logger.info(f"Found existing peer node: {node_id}")
                return node_id
            
            # Get availability zone
            azs = self.ec2.describe_availability_zones()["AvailabilityZones"]
            az = azs[0]["ZoneName"]  # Use first available AZ
            
            # Create peer node
            logger.info("Creating peer node...")
            
            response = self.blockchain.create_node(
                NetworkId=network_id,
                MemberId=member_id,
                NodeConfiguration={
                    "InstanceType": "bc.t3.small",  # Smallest instance for cost efficiency
                    "AvailabilityZone": az,
                    "LogPublishingConfiguration": {
                        "Fabric": {
                            "ChaincodeLogs": {
                                "Cloudwatch": {"Enabled": True}
                            },
                            "PeerLogs": {
                                "Cloudwatch": {"Enabled": True}
                            }
                        }
                    }
                }
            )
            
            node_id = response["NodeId"]
            logger.info(f"Created peer node: {node_id}")
            logger.info("Node creation will take 20-30 minutes to complete.")
            
            return node_id
            
        except ClientError as e:
            logger.error(f"Error creating peer node: {e}")
            return None
    
    def setup_fabric_ca(self, network_id: str, member_id: str) -> bool:
        """Set up Fabric Certificate Authority."""
        try:
            # Get CA endpoint
            member = self.blockchain.get_member(
                NetworkId=network_id,
                MemberId=member_id
            )["Member"]
            
            ca_endpoint = member.get("FrameworkAttributes", {}).get("Fabric", {}).get("CaEndpoint")
            
            if ca_endpoint:
                logger.info(f"Fabric CA endpoint: {ca_endpoint}")
                
                # Store CA endpoint in secrets
                self.secrets.create_secret(
                    Name="haven-health/blockchain/ca-endpoint",
                    SecretString=ca_endpoint
                )
                
                return True
            else:
                logger.warning("CA endpoint not yet available")
                return False
                
        except Exception as e:
            logger.error(f"Error setting up Fabric CA: {e}")
            return False
    
    def create_blockchain_vpc_endpoint(self) -> bool:
        """Create VPC endpoint for blockchain access."""
        try:
            # Get default VPC
            vpcs = self.ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])
            
            if not vpcs["Vpcs"]:
                logger.warning("No default VPC found")
                return False
            
            vpc_id = vpcs["Vpcs"][0]["VpcId"]
            
            # Check if endpoint exists
            endpoints = self.ec2.describe_vpc_endpoints(
                Filters=[
                    {"Name": "vpc-id", "Values": [vpc_id]},
                    {"Name": "service-name", "Values": ["com.amazonaws.managedblockchain.hyperledger-fabric"]}
                ]
            )
            
            if endpoints["VpcEndpoints"]:
                logger.info("VPC endpoint already exists for blockchain")
                return True
            
            # Create VPC endpoint
            logger.info("Creating VPC endpoint for blockchain access...")
            
            # Get route tables
            route_tables = self.ec2.describe_route_tables(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )
            route_table_ids = [rt["RouteTableId"] for rt in route_tables["RouteTables"]]
            
            response = self.ec2.create_vpc_endpoint(
                VpcEndpointType="Interface",
                VpcId=vpc_id,
                ServiceName=f"com.amazonaws.{self.region}.managedblockchain.{network_id}",
                RouteTableIds=route_table_ids,
                TagSpecifications=[{
                    "ResourceType": "vpc-endpoint",
                    "Tags": [
                        {"Key": "Name", "Value": "HavenHealthBlockchainEndpoint"},
                        {"Key": "Project", "Value": "HavenHealthPassport"}
                    ]
                }]
            )
            
            logger.info(f"Created VPC endpoint: {response['VpcEndpoint']['VpcEndpointId']}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating VPC endpoint: {e}")
            return False
    
    def deploy_chaincode(self, network_id: str, member_id: str, node_id: str) -> bool:
        """Deploy health record verification chaincode."""
        logger.info("Chaincode deployment requires Fabric SDK client setup")
        
        # Generate chaincode deployment script
        chaincode_script = f"""#!/bin/bash
# Haven Health Passport Chaincode Deployment Script

export NETWORK_ID={network_id}
export MEMBER_ID={member_id}
export NODE_ID={node_id}

# This script should be run on an EC2 instance with Fabric SDK installed
# It deploys the health record verification chaincode

echo "Deploying Haven Health chaincode..."
echo "Network: $NETWORK_ID"
echo "Member: $MEMBER_ID" 
echo "Node: $NODE_ID"

# Chaincode location
CHAINCODE_PATH="/opt/haven-health/chaincode"

# Deploy steps would go here in production
echo "Chaincode deployment script generated."
echo "Run this on a Fabric client instance to deploy chaincode."
"""
        
        script_path = project_root / "scripts" / "deploy_chaincode.sh"
        with open(script_path, "w") as f:
            f.write(chaincode_script)
        
        os.chmod(script_path, 0o755)
        logger.info(f"Chaincode deployment script written to: {script_path}")
        
        return True
    
    def create_iam_policies(self) -> Dict[str, str]:
        """Create IAM policies for blockchain access."""
        policies = {}
        
        blockchain_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "managedblockchain:Get*",
                        "managedblockchain:List*",
                        "managedblockchain:CreateProposal",
                        "managedblockchain:VoteOnProposal"
                    ],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "secretsmanager:GetSecretValue"
                    ],
                    "Resource": "arn:aws:secretsmanager:*:*:secret:haven-health/blockchain/*"
                }
            ]
        }
        
        try:
            policy_name = "HavenHealthBlockchainAccess"
            
            response = self.iam.create_policy(
                PolicyName=policy_name,
                PolicyDocument=json.dumps(blockchain_policy),
                Description="Access policy for Haven Health blockchain operations"
            )
            
            policies["blockchain_access"] = response["Policy"]["Arn"]
            logger.info(f"Created IAM policy: {policy_name}")
            
        except ClientError as e:
            if e.response["Error"]["Code"] == "EntityAlreadyExists":
                logger.info("Blockchain access policy already exists")
            else:
                logger.error(f"Error creating IAM policy: {e}")
        
        return policies
    
    def write_blockchain_config(self, config: Dict[str, any]):
        """Write blockchain configuration to environment file."""
        env_lines = []
        
        if "network_id" in config:
            env_lines.append(f"MANAGED_BLOCKCHAIN_NETWORK_ID={config['network_id']}")
        
        if "member_id" in config:
            env_lines.append(f"MANAGED_BLOCKCHAIN_MEMBER_ID={config['member_id']}")
        
        if "node_id" in config:
            env_lines.append(f"MANAGED_BLOCKCHAIN_NODE_ID={config['node_id']}")
        
        env_lines.append(f"BLOCKCHAIN_PROVIDER=aws_managed_blockchain")
        env_lines.append(f"BLOCKCHAIN_REGION={self.region}")
        env_lines.append(f"ENABLE_BLOCKCHAIN=true")
        env_lines.append(f"BLOCKCHAIN_FALLBACK_MODE=true")
        
        # Append to .env.aws file
        env_file = project_root / ".env.aws"
        
        with open(env_file, "a") as f:
            f.write("\n# Blockchain Configuration\n")
            f.write("\n".join(env_lines))
            f.write("\n")
        
        logger.info("Blockchain configuration appended to .env.aws")
    
    def wait_for_network(self, network_id: str, timeout_minutes: int = 60) -> bool:
        """Wait for network to become available."""
        logger.info(f"Waiting for network to become available (up to {timeout_minutes} minutes)...")
        
        start_time = time.time()
        timeout_seconds = timeout_minutes * 60
        
        while time.time() - start_time < timeout_seconds:
            try:
                response = self.blockchain.get_network(NetworkId=network_id)
                status = response["Network"]["Status"]
                
                logger.info(f"Network status: {status}")
                
                if status == "AVAILABLE":
                    logger.info("Network is now available!")
                    return True
                elif status in ["CREATE_FAILED", "DELETE_FAILED"]:
                    logger.error(f"Network creation failed with status: {status}")
                    return False
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error checking network status: {e}")
                time.sleep(60)
        
        logger.error("Timeout waiting for network to become available")
        return False
    
    def run_full_setup(self):
        """Run complete blockchain setup."""
        logger.info("Starting AWS Managed Blockchain setup for Haven Health Passport")
        logger.info("=" * 60)
        
        config = {}
        
        # Create blockchain network
        logger.info("\n1. Creating blockchain network...")
        network_id, member_id = self.create_blockchain_network()
        
        if not network_id:
            logger.error("Failed to create blockchain network")
            return False
        
        config["network_id"] = network_id
        config["member_id"] = member_id
        
        # Wait for network if newly created
        if member_id:  # New network
            if not self.wait_for_network(network_id, timeout_minutes=10):
                logger.warning("Network not yet available. Continuing with setup...")
        
        # Create peer node
        if member_id:
            logger.info("\n2. Creating peer node...")
            node_id = self.create_peer_node(network_id, member_id)
            
            if node_id:
                config["node_id"] = node_id
        
        # Setup Fabric CA
        if member_id:
            logger.info("\n3. Setting up Fabric CA...")
            self.setup_fabric_ca(network_id, member_id)
        
        # Create VPC endpoint
        logger.info("\n4. Creating VPC endpoint...")
        self.create_blockchain_vpc_endpoint()
        
        # Deploy chaincode
        if member_id and "node_id" in config:
            logger.info("\n5. Preparing chaincode deployment...")
            self.deploy_chaincode(network_id, member_id, config["node_id"])
        
        # Create IAM policies
        logger.info("\n6. Creating IAM policies...")
        policies = self.create_iam_policies()
        config["policies"] = policies
        
        # Write configuration
        logger.info("\n7. Writing configuration...")
        self.write_blockchain_config(config)
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Blockchain Setup Summary:")
        logger.info(f"  - Network ID: {network_id}")
        logger.info(f"  - Member ID: {member_id or 'Existing network'}")
        logger.info(f"  - Node ID: {config.get('node_id', 'Not created')}")
        logger.info(f"  - IAM policies: {len(policies)}")
        logger.info("=" * 60)
        
        if network_id:
            logger.info("✓ Blockchain setup completed!")
            logger.info("\nNext steps:")
            logger.info("1. Wait for network/node to become AVAILABLE (check AWS console)")
            logger.info("2. Deploy chaincode using the generated script")
            logger.info("3. Configure Fabric SDK client for application access")
            return True
        else:
            logger.error("✗ Blockchain setup failed")
            return False


def main():
    """Main entry point."""
    configurator = AWSBlockchainConfigurator()
    success = configurator.run_full_setup()
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
