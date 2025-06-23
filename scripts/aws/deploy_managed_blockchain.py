#!/usr/bin/env python3
"""Deploy and configure AWS Managed Blockchain for Haven Health Passport."""

import json
import os
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))


def create_blockchain_network(client, network_name, member_name, admin_password):
    """Create AWS Managed Blockchain network."""
    print(f"Creating blockchain network: {network_name}")
    
    try:
        response = client.create_network(
            Name=network_name,
            Description='Haven Health Passport - Secure healthcare data blockchain',
            Framework='HYPERLEDGER_FABRIC',
            FrameworkVersion='2.2',
            FrameworkConfiguration={
                'Fabric': {
                    'Edition': 'STANDARD'
                }
            },
            VotingPolicy={
                'ApprovalThresholdPolicy': {
                    'ThresholdPercentage': 50,
                    'ProposalDurationInHours': 24,
                    'ThresholdComparator': 'GREATER_THAN'
                }
            },
            MemberConfiguration={
                'Name': member_name,
                'Description': 'Primary member for Haven Health Passport',
                'FrameworkConfiguration': {
                    'Fabric': {
                        'AdminUsername': 'HavenAdmin',
                        'AdminPassword': admin_password
                    }
                }
            }
        )
        
        network_id = response['NetworkId']
        member_id = response['MemberId']
        
        print(f"✅ Network creation initiated")
        print(f"  Network ID: {network_id}")
        print(f"  Member ID: {member_id}")
        
        return network_id, member_id
        
    except ClientError as e:
        print(f"❌ Error creating network: {e}")
        return None, None


def wait_for_network(client, network_id):
    """Wait for network to become available."""
    print("\nWaiting for network to become available...")
    
    max_attempts = 60  # 30 minutes
    attempt = 0
    
    while attempt < max_attempts:
        try:
            response = client.get_network(NetworkId=network_id)
            status = response['Network']['Status']
            
            if status == 'AVAILABLE':
                print("✅ Network is available!")
                return True
            elif status in ['CREATE_FAILED', 'DELETED', 'DELETING']:
                print(f"❌ Network creation failed. Status: {status}")
                return False
            else:
                print(f"  Status: {status} (attempt {attempt + 1}/{max_attempts})")
                time.sleep(30)
                attempt += 1
                
        except Exception as e:
            print(f"❌ Error checking network status: {e}")
            return False
    
    print("❌ Timeout waiting for network")
    return False


def create_peer_node(client, network_id, member_id, availability_zone):
    """Create a peer node."""
    print(f"\nCreating peer node in {availability_zone}...")
    
    try:
        response = client.create_node(
            NetworkId=network_id,
            MemberId=member_id,
            NodeConfiguration={
                'InstanceType': 'bc.t3.small',
                'AvailabilityZone': availability_zone
            }
        )
        
        node_id = response['NodeId']
        print(f"✅ Node creation initiated: {node_id}")
        return node_id
        
    except ClientError as e:
        print(f"❌ Error creating node: {e}")
        return None


def save_configuration(network_id, member_id, network_name, member_name, region):
    """Save network configuration for later use."""
    config = {
        "networkId": network_id,
        "memberId": member_id,
        "networkName": network_name,
        "memberName": member_name,
        "region": region,
        "framework": "HYPERLEDGER_FABRIC",
        "frameworkVersion": "2.2",
        "edition": "STANDARD",
        "deploymentTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    # Save to blockchain config directory
    config_dir = Path(project_root) / "blockchain" / "aws-managed-blockchain" / "deployed-config"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    config_file = config_dir / "network-info.json"
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\n✅ Configuration saved to: {config_file}")
    
    # Also save to .env format
    env_file = config_dir / "blockchain.env"
    with open(env_file, 'w') as f:
        f.write(f"# AWS Managed Blockchain Configuration\n")
        f.write(f"BLOCKCHAIN_PROVIDER=aws_managed_blockchain\n")
        f.write(f"MANAGED_BLOCKCHAIN_NETWORK_ID={network_id}\n")
        f.write(f"MANAGED_BLOCKCHAIN_MEMBER_ID={member_id}\n")
        f.write(f"AWS_REGION={region}\n")
    
    print(f"✅ Environment variables saved to: {env_file}")


def main():
    """Main deployment function."""
    print("=" * 60)
    print("AWS Managed Blockchain Deployment")
    print("=" * 60)
    
    # Get configuration
    region = os.getenv('AWS_REGION', 'us-east-1')
    
    # Initialize client
    client = boto3.client('managedblockchain', region_name=region)
    ec2 = boto3.client('ec2', region_name=region)
    
    # Get available AZs
    print(f"\nRegion: {region}")
    azs = ec2.describe_availability_zones()['AvailabilityZones']
    available_azs = [az['ZoneName'] for az in azs if az['State'] == 'available']
    print(f"Available AZs: {', '.join(available_azs)}")
    
    # Check for existing networks
    print("\nChecking for existing networks...")
    try:
        networks = client.list_networks(Framework='HYPERLEDGER_FABRIC')
        if networks['Networks']:
            print("\n⚠️  Existing networks found:")
            for net in networks['Networks']:
                print(f"  - {net['Name']} (ID: {net['Id']}, Status: {net['Status']})")
            
            use_existing = input("\nUse existing network? (y/n): ").lower() == 'y'
            if use_existing:
                network_id = input("Enter Network ID: ")
                member_id = input("Enter Member ID: ")
                print("\n✅ Using existing network")
                return
    except Exception as e:
        print(f"Note: {e}")
    
    # Get parameters
    print("\nNetwork Configuration:")
    network_name = input("Network Name (default: HavenHealthPassportNetwork): ") or "HavenHealthPassportNetwork"
    member_name = input("Member Name (default: HavenHealthFoundation): ") or "HavenHealthFoundation"
    admin_password = input("Admin Password (min 8 chars): ")
    
    if len(admin_password) < 8:
        print("❌ Password must be at least 8 characters")
        return
    
    # Create network
    network_id, member_id = create_blockchain_network(
        client, network_name, member_name, admin_password
    )
    
    if not network_id:
        return
    
    # Wait for network
    if not wait_for_network(client, network_id):
        return
    
    # Create peer nodes
    create_nodes = input("\nCreate peer nodes? (y/n): ").lower() == 'y'
    if create_nodes:
        num_nodes = int(input("Number of nodes (1-3): ") or "1")
        for i in range(min(num_nodes, len(available_azs))):
            create_peer_node(client, network_id, member_id, available_azs[i])
    
    # Save configuration
    save_configuration(network_id, member_id, network_name, member_name, region)
    
    print("\n" + "=" * 60)
    print("Deployment Complete!")
    print("=" * 60)
    print(f"\nNetwork ID: {network_id}")
    print(f"Member ID: {member_id}")
    print(f"\nAdd these to your .env file:")
    print(f"BLOCKCHAIN_PROVIDER=aws_managed_blockchain")
    print(f"MANAGED_BLOCKCHAIN_NETWORK_ID={network_id}")
    print(f"MANAGED_BLOCKCHAIN_MEMBER_ID={member_id}")
    print("\n⚠️  Save the admin password securely!")


if __name__ == "__main__":
    main()