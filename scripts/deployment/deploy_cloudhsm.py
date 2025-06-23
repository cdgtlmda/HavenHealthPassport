#!/usr/bin/env python3
"""
Deploy and Initialize AWS CloudHSM for Haven Health Passport.

CRITICAL: This script sets up hardware security modules for protecting
patient encryption keys and sensitive healthcare data.
"""

import os
import sys
import time
import boto3
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CloudHSMDeployment:
    """Deploy and configure AWS CloudHSM for production use."""
    
    def __init__(self, environment: str = "production"):
        self.environment = environment
        self.region = os.getenv("AWS_REGION", "us-east-1")
        
        # Initialize AWS clients
        self.cloudhsm_client = boto3.client("cloudhsmv2", region_name=self.region)
        self.ec2_client = boto3.client("ec2", region_name=self.region)
        self.kms_client = boto3.client("kms", region_name=self.region)
        
        # Configuration
        self.cluster_name = f"haven-health-{environment}-hsm"
        self.backup_retention_days = 7
        
        logger.info(f"Initialized CloudHSM deployment for {environment} in {self.region}")
    
    def deploy_cluster(self, vpc_id: str, subnet_ids: List[str]) -> Dict[str, Any]:
        """Deploy CloudHSM cluster."""
        try:
            # Create CloudHSM cluster
            logger.info(f"Creating CloudHSM cluster: {self.cluster_name}")
            
            response = self.cloudhsm_client.create_cluster(
                SubnetIds=subnet_ids,
                HsmType="hsm1.medium",
                BackupRetentionPolicy={
                    "Type": "DAYS",
                    "Value": str(self.backup_retention_days)
                },
                TagList=[
                    {"Key": "Name", "Value": self.cluster_name},
                    {"Key": "Environment", "Value": self.environment},
                    {"Key": "Application", "Value": "haven-health-passport"},
                    {"Key": "Purpose", "Value": "patient-data-encryption"},
                    {"Key": "Compliance", "Value": "HIPAA-GDPR"}
                ]
            )
            
            cluster_id = response["Cluster"]["ClusterId"]
            logger.info(f"Created CloudHSM cluster: {cluster_id}")
            
            # Wait for cluster to be initialized
            logger.info("Waiting for cluster initialization...")
            self._wait_for_cluster_state(cluster_id, "UNINITIALIZED")
            
            # Create HSM instance
            logger.info("Creating HSM instance in cluster...")
            hsm_response = self.cloudhsm_client.create_hsm(
                ClusterId=cluster_id,
                AvailabilityZone=self._get_availability_zone(subnet_ids[0])
            )
            
            hsm_id = hsm_response["Hsm"]["HsmId"]
            logger.info(f"Created HSM: {hsm_id}")
            
            # Wait for HSM to be active
            self._wait_for_hsm_state(cluster_id, hsm_id, "ACTIVE")
            
            # Initialize cluster
            cluster_info = self._initialize_cluster(cluster_id)
            
            return {
                "cluster_id": cluster_id,
                "hsm_id": hsm_id,
                "cluster_state": cluster_info["State"],
                "security_group": cluster_info["SecurityGroup"],
                "certificates": cluster_info["Certificates"]
            }
            
        except Exception as e:
            logger.error(f"Failed to deploy CloudHSM cluster: {e}")
            raise
    
    def _wait_for_cluster_state(self, cluster_id: str, target_state: str, timeout: int = 600):
        """Wait for cluster to reach target state."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            response = self.cloudhsm_client.describe_clusters(
                Filters={"clusterIds": [cluster_id]}
            )
            
            if response["Clusters"]:
                cluster = response["Clusters"][0]
                current_state = cluster["State"]
                
                if current_state == target_state:
                    logger.info(f"Cluster reached state: {target_state}")
                    return
                elif current_state in ["CREATE_IN_PROGRESS", "INITIALIZE_IN_PROGRESS"]:
                    logger.info(f"Cluster state: {current_state}, waiting...")
                else:
                    raise RuntimeError(f"Unexpected cluster state: {current_state}")
            
            time.sleep(10)
        
        raise TimeoutError(f"Cluster did not reach {target_state} within {timeout} seconds")
    
    def _wait_for_hsm_state(self, cluster_id: str, hsm_id: str, target_state: str, timeout: int = 300):
        """Wait for HSM to reach target state."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            response = self.cloudhsm_client.describe_clusters(
                Filters={"clusterIds": [cluster_id]}
            )
            
            if response["Clusters"]:
                cluster = response["Clusters"][0]
                for hsm in cluster.get("Hsms", []):
                    if hsm["HsmId"] == hsm_id:
                        current_state = hsm["State"]
                        
                        if current_state == target_state:
                            logger.info(f"HSM reached state: {target_state}")
                            return
                        else:
                            logger.info(f"HSM state: {current_state}, waiting...")
                        break
            
            time.sleep(5)
        
        raise TimeoutError(f"HSM did not reach {target_state} within {timeout} seconds")
    
    def _get_availability_zone(self, subnet_id: str) -> str:
        """Get availability zone for subnet."""
        response = self.ec2_client.describe_subnets(SubnetIds=[subnet_id])
        return response["Subnets"][0]["AvailabilityZone"]
    
    def _initialize_cluster(self, cluster_id: str) -> Dict[str, Any]:
        """Initialize CloudHSM cluster."""
        logger.info("Initializing CloudHSM cluster...")
        
        # Get cluster certificate
        response = self.cloudhsm_client.describe_clusters(
            Filters={"clusterIds": [cluster_id]}
        )
        
        cluster = response["Clusters"][0]
        cluster_csr = cluster.get("ClusterCertificate", {}).get("ClusterCsr")
        
        if not cluster_csr:
            raise RuntimeError("Cluster CSR not available")
        
        # In production, this CSR would be signed by your CA
        # For now, we'll note that manual initialization is required
        logger.warning(
            "Cluster CSR generated. Manual steps required:\n"
            "1. Sign the CSR with your issuing certificate\n"
            "2. Initialize the cluster with signed certificate\n"
            "3. Create Crypto User (CU) for application access"
        )
        
        # Save CSR for manual processing
        csr_filename = f"cloudhsm_{cluster_id}_csr.pem"
        with open(csr_filename, "w") as f:
            f.write(cluster_csr)
        
        logger.info(f"Cluster CSR saved to: {csr_filename}")
        
        return {
            "State": cluster["State"],
            "SecurityGroup": cluster["SecurityGroup"],
            "Certificates": {
                "ClusterCsr": csr_filename,
                "AwsHardwareCertificate": cluster["Certificates"]["AwsHardwareCertificate"],
                "ManufacturerHardwareCertificate": cluster["Certificates"]["ManufacturerHardwareCertificate"]
            }
        }
    
    def configure_kms_integration(self, cluster_id: str) -> Dict[str, Any]:
        """Configure KMS custom key store with CloudHSM."""
        try:
            # Create custom key store
            keystore_name = f"{self.cluster_name}-keystore"
            
            logger.info(f"Creating KMS custom key store: {keystore_name}")
            
            # Get cluster info
            response = self.cloudhsm_client.describe_clusters(
                Filters={"clusterIds": [cluster_id]}
            )
            cluster = response["Clusters"][0]
            
            # Create custom key store
            kms_response = self.kms_client.create_custom_key_store(
                CustomKeyStoreName=keystore_name,
                CloudHsmClusterId=cluster_id,
                TrustAnchorCertificate=cluster["Certificates"]["ClusterCertificate"],
                KeyStorePassword="CHANGE_ME_IN_PRODUCTION"  # Must be changed after creation
            )
            
            keystore_id = kms_response["CustomKeyStoreId"]
            logger.info(f"Created custom key store: {keystore_id}")
            
            return {
                "keystore_id": keystore_id,
                "keystore_name": keystore_name,
                "cluster_id": cluster_id
            }
            
        except Exception as e:
            logger.error(f"Failed to configure KMS integration: {e}")
            raise
    
    def create_encryption_keys(self, keystore_id: str) -> Dict[str, Any]:
        """Create encryption keys in CloudHSM."""
        keys_created = {}
        
        key_configs = [
            {
                "alias": f"alias/haven-health-{self.environment}-patient-data",
                "description": "Patient data encryption key",
                "key_usage": "ENCRYPT_DECRYPT"
            },
            {
                "alias": f"alias/haven-health-{self.environment}-biometric",
                "description": "Biometric template encryption key",
                "key_usage": "ENCRYPT_DECRYPT"
            },
            {
                "alias": f"alias/haven-health-{self.environment}-backup",
                "description": "Backup encryption key",
                "key_usage": "ENCRYPT_DECRYPT"
            }
        ]
        
        for config in key_configs:
            try:
                # Create key
                response = self.kms_client.create_key(
                    Description=config["description"],
                    KeyUsage=config["key_usage"],
                    Origin="AWS_CLOUDHSM",
                    CustomKeyStoreId=keystore_id,
                    Tags=[
                        {"TagKey": "Environment", "TagValue": self.environment},
                        {"TagKey": "Application", "TagValue": "haven-health-passport"}
                    ]
                )
                
                key_id = response["KeyMetadata"]["KeyId"]
                
                # Create alias
                self.kms_client.create_alias(
                    AliasName=config["alias"],
                    TargetKeyId=key_id
                )
                
                keys_created[config["alias"]] = key_id
                logger.info(f"Created key: {config['alias']} -> {key_id}")
                
            except Exception as e:
                logger.error(f"Failed to create key {config['alias']}: {e}")
                raise
        
        return keys_created
    
    def generate_deployment_config(self, deployment_info: Dict[str, Any]) -> None:
        """Generate deployment configuration file."""
        config = {
            "cloudhsm": {
                "cluster_id": deployment_info["cluster_id"],
                "hsm_id": deployment_info["hsm_id"],
                "security_group": deployment_info["security_group"],
                "region": self.region,
                "environment": self.environment
            },
            "kms": {
                "keystore_id": deployment_info.get("keystore_id"),
                "keys": deployment_info.get("keys", {})
            },
            "deployment": {
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0"
            }
        }
        
        config_filename = f"cloudhsm_{self.environment}_config.json"
        with open(config_filename, "w") as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Deployment configuration saved to: {config_filename}")
        
        # Generate initialization script
        self._generate_init_script(deployment_info)
    
    def _generate_init_script(self, deployment_info: Dict[str, Any]) -> None:
        """Generate initialization script for manual steps."""
        script_content = f"""#!/bin/bash
# CloudHSM Initialization Script for {self.environment}
# Generated on {datetime.utcnow().isoformat()}

CLUSTER_ID="{deployment_info['cluster_id']}"
REGION="{self.region}"

echo "CloudHSM Cluster Initialization Steps"
echo "===================================="

# Step 1: Download and install CloudHSM client
echo "1. Installing CloudHSM client..."
wget https://s3.amazonaws.com/cloudhsmv2-software/CloudHsmClient/EL7/cloudhsm-client-latest.el7.x86_64.rpm
sudo yum install -y ./cloudhsm-client-latest.el7.x86_64.rpm

# Step 2: Configure the client
echo "2. Configuring CloudHSM client..."
sudo /opt/cloudhsm/bin/configure -a $CLUSTER_ID

# Step 3: Initialize the cluster (requires signed certificate)
echo "3. Initialize cluster with signed certificate..."
echo "   - Sign the CSR: {deployment_info['cluster_id']}_csr.pem"
echo "   - Run: cloudhsm_mgmt_util /opt/cloudhsm/etc/cloudhsm_mgmt_util.cfg"
echo "   - Initialize with: initialize -label haven-health-{self.environment}"

# Step 4: Create Crypto User
echo "4. Create Crypto User for application..."
echo "   - In cloudhsm_mgmt_util:"
echo "   - loginHSM CO admin password"
echo "   - createUser CU haven-app-user <password>"
echo "   - changePswd CU haven-app-user -1 <new-password>"

# Step 5: Test connection
echo "5. Testing connection..."
/opt/cloudhsm/bin/cloudhsm_mgmt_util /opt/cloudhsm/etc/cloudhsm_mgmt_util.cfg

echo "Manual initialization required - see documentation"
"""
        
        script_filename = f"init_cloudhsm_{self.environment}.sh"
        with open(script_filename, "w") as f:
            f.write(script_content)
        
        os.chmod(script_filename, 0o755)
        logger.info(f"Initialization script saved to: {script_filename}")


def main():
    """Main deployment function."""
    # Get environment
    environment = os.getenv("ENVIRONMENT", "staging")
    
    if environment == "production" and not os.getenv("CONFIRM_PRODUCTION"):
        print("CRITICAL: Deploying CloudHSM to production!")
        print("Set CONFIRM_PRODUCTION=true to proceed")
        sys.exit(1)
    
    # Get VPC configuration
    vpc_id = os.getenv("VPC_ID")
    subnet_ids = os.getenv("SUBNET_IDS", "").split(",")
    
    if not vpc_id or not subnet_ids:
        print("ERROR: VPC_ID and SUBNET_IDS environment variables required")
        print("Example: VPC_ID=vpc-xxx SUBNET_IDS=subnet-xxx,subnet-yyy")
        sys.exit(1)
    
    # Deploy CloudHSM
    deployer = CloudHSMDeployment(environment)
    
    try:
        logger.info("Starting CloudHSM deployment...")
        
        # Deploy cluster
        deployment_info = deployer.deploy_cluster(vpc_id, subnet_ids)
        logger.info(f"CloudHSM cluster deployed: {deployment_info['cluster_id']}")
        
        # Configure KMS integration (if cluster is initialized)
        if deployment_info["cluster_state"] == "INITIALIZED":
            kms_info = deployer.configure_kms_integration(deployment_info["cluster_id"])
            deployment_info.update(kms_info)
            
            # Create encryption keys
            keys = deployer.create_encryption_keys(kms_info["keystore_id"])
            deployment_info["keys"] = keys
        else:
            logger.warning(
                "Cluster not initialized. Complete manual initialization before KMS integration."
            )
        
        # Generate configuration
        deployer.generate_deployment_config(deployment_info)
        
        logger.info("CloudHSM deployment completed successfully!")
        logger.info(f"Cluster ID: {deployment_info['cluster_id']}")
        logger.info("Next steps: Complete manual initialization using the generated script")
        
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
