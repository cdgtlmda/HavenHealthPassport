#!/usr/bin/env python3
"""
CloudHSM Deployment Script for Haven Health Passport.

CRITICAL: This script deploys AWS CloudHSM for hardware-based encryption
of patient data. CloudHSM provides FIPS 140-2 Level 3 validated hardware
security modules.

Usage:
    python deploy_cloudhsm.py --environment production --vpc-id vpc-xxx
"""

import argparse
import json
import time
import boto3
from botocore.exceptions import ClientError

def create_hsm_cluster(cloudhsm_client, vpc_id, subnet_ids, environment):
    """Create CloudHSM cluster."""
    print("\n=== Creating CloudHSM Cluster ===")
    
    try:
        response = cloudhsm_client.create_cluster(
            SubnetIds=subnet_ids,
            HsmType='hsm1.medium',  # Or hsm1.large for higher performance
            Tags=[
                {'Key': 'Project', 'Value': 'HavenHealthPassport'},
                {'Key': 'Environment', 'Value': environment},
                {'Key': 'Purpose', 'Value': 'Patient data encryption'},
                {'Key': 'Compliance', 'Value': 'HIPAA'}
            ]
        )
        
        cluster_id = response['Cluster']['ClusterId']
        print(f"✓ Created CloudHSM cluster: {cluster_id}")
        
        # Wait for cluster to be initialized
        print("Waiting for cluster initialization...")
        waiter = cloudhsm_client.get_waiter('cluster_initialized')
        waiter.wait(ClusterIds=[cluster_id])
        
        return cluster_id
        
    except ClientError as e:
        print(f"✗ Error creating CloudHSM cluster: {e}")
        raise

def create_hsm_instance(cloudhsm_client, cluster_id, availability_zone):
    """Create HSM instance in the cluster."""
    print("\n=== Creating HSM Instance ===")
    
    try:
        response = cloudhsm_client.create_hsm(
            ClusterId=cluster_id,
            AvailabilityZone=availability_zone
        )
        
        hsm_id = response['Hsm']['HsmId']
        print(f"✓ Created HSM instance: {hsm_id}")
        
        # Wait for HSM to be active
        print("Waiting for HSM activation (this may take 10-15 minutes)...")
        while True:
            response = cloudhsm_client.describe_clusters(ClusterIds=[cluster_id])
            cluster = response['Clusters'][0]
            hsms = cluster.get('Hsms', [])
            
            if hsms and hsms[0]['State'] == 'ACTIVE':
                hsm_ip = hsms[0]['EniIp']
                print(f"✓ HSM active with IP: {hsm_ip}")
                return hsm_id, hsm_ip
            
            time.sleep(30)
            print(".", end="", flush=True)
            
    except ClientError as e:
        print(f"\n✗ Error creating HSM instance: {e}")
        raise

def initialize_cluster(cluster_id, cluster_csr_path):
    """Initialize the CloudHSM cluster with certificates."""
    print("\n=== Initializing CloudHSM Cluster ===")
    print(f"1. Download and install CloudHSM client software")
    print(f"2. Retrieve the cluster CSR:")
    print(f"   aws cloudhsmv2 describe-clusters --cluster-ids {cluster_id}")
    print(f"3. Sign the CSR with your certificate authority")
    print(f"4. Initialize the cluster with signed certificate")
    print(f"\nManual steps required - see AWS CloudHSM documentation")
    
    return True

def create_crypto_user(hsm_ip):
    """Create crypto user for application access."""
    print("\n=== Creating Crypto User ===")
    print(f"Connect to HSM at {hsm_ip} and run:")
    print("1. loginmgr login -u CO -p <CO_PASSWORD>")
    print("2. user create -u haven_crypto_user -r CU")
    print("3. Set password when prompted")
    print("\nStore credentials securely in AWS Secrets Manager")

def setup_backup(cloudhsm_client, cluster_id):
    """Configure automated backups."""
    print("\n=== Configuring Backups ===")
    
    try:
        # CloudHSM automatically backs up every 24 hours
        # Configure backup retention
        response = cloudhsm_client.modify_backup_attributes(
            BackupId='PERSISTENT',
            NeverExpires=False,
            DeleteAfterDays=90  # Keep backups for 90 days
        )
        print("✓ Configured backup retention: 90 days")
        
    except Exception as e:
        print(f"Note: Backup configuration may require manual setup: {e}")

def main():
    parser = argparse.ArgumentParser(description='Deploy CloudHSM for Haven Health Passport')
    parser.add_argument('--environment', required=True, choices=['production', 'staging'])
    parser.add_argument('--vpc-id', required=True, help='VPC ID for HSM cluster')
    parser.add_argument('--subnet-ids', required=True, nargs='+', help='Subnet IDs (2 required)')
    parser.add_argument('--availability-zone', required=True, help='AZ for first HSM')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    args = parser.parse_args()
    
    if len(args.subnet_ids) < 2:
        print("ERROR: At least 2 subnets required for CloudHSM cluster")
        return
    
    print(f"\n🔐 Haven Health Passport - CloudHSM Deployment")
    print(f"Environment: {args.environment}")
    print(f"VPC: {args.vpc_id}")
    print(f"Subnets: {', '.join(args.subnet_ids)}")
    print("\n⚠️  WARNING: CloudHSM has hourly charges!")
    print("Estimated cost: ~$1.60/hour per HSM instance")
    
    confirm = input("\nContinue with deployment? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Deployment cancelled.")
        return
    
    # Initialize client
    cloudhsm_client = boto3.client('cloudhsmv2', region_name=args.region)
    
    try:
        # Create cluster
        cluster_id = create_hsm_cluster(
            cloudhsm_client,
            args.vpc_id,
            args.subnet_ids,
            args.environment
        )
        
        # Create HSM instance
        hsm_id, hsm_ip = create_hsm_instance(
            cloudhsm_client,
            cluster_id,
            args.availability_zone
        )
        
        # Initialize cluster (manual steps)
        initialize_cluster(cluster_id, f"/tmp/cluster-{cluster_id}-csr.pem")
        
        # Create crypto user (manual)
        create_crypto_user(hsm_ip)
        
        # Setup backups
        setup_backup(cloudhsm_client, cluster_id)
        
        print("\n✅ CloudHSM deployment complete!")
        print("\nNext steps:")
        print("1. Complete cluster initialization with signed certificate")
        print("2. Create crypto user for application")
        print("3. Update environment variables:")
        print(f"   CLOUDHSM_CLUSTER_ID={cluster_id}")
        print(f"   CLOUDHSM_IP={hsm_ip}")
        print("   CLOUDHSM_CRYPTO_USER=haven_crypto_user")
        print("   CLOUDHSM_CRYPTO_PASSWORD=<set in secrets manager>")
        
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        raise

if __name__ == '__main__':
    main()
