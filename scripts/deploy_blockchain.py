#!/usr/bin/env python3
"""
Deploy AWS Managed Blockchain for Haven Health Passport.

This script deploys and configures AWS Managed Blockchain
for immutable medical record verification.
"""

import sys
import os
import argparse
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, '/Users/cadenceapeiron/Documents/HavenHealthPassport')

from src.infrastructure.blockchain_deployment import get_blockchain_deployment


def main():
    parser = argparse.ArgumentParser(
        description='Deploy AWS Managed Blockchain for Haven Health Passport'
    )
    parser.add_argument(
        '--environment',
        choices=['production', 'staging', 'development'],
        default='production',
        help='Target environment'
    )
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate existing deployment'
    )
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"Haven Health Passport - AWS Managed Blockchain Deployment")
    print(f"Environment: {args.environment}")
    print(f"Region: {args.region}")
    print(f"Time: {datetime.utcnow().isoformat()}")
    print(f"{'='*60}\n")
    
    # Warning for production
    if args.environment == 'production' and not args.validate_only:
        print("⚠️  WARNING: You are deploying blockchain for PRODUCTION!")
        print("This will create AWS resources that incur significant costs.")
        print("Hyperledger Fabric network creation can take 30-45 minutes.")
        print("\nEstimated costs:")
        print("  - Network: ~$0.30/hour")
        print("  - Member: ~$0.30/hour")  
        print("  - Peer node: ~$0.20/hour")
        print("\nEnsure you have proper AWS credentials and permissions.")
        response = input("\nContinue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return
    
    # Set environment
    os.environ['ENVIRONMENT'] = args.environment
    os.environ['AWS_REGION'] = args.region
    
    # Get deployment instance
    deployment = get_blockchain_deployment()
    
    if args.validate_only:
        # Validate existing deployment
        print("\nValidating blockchain deployment...")
        validation = deployment.validate_deployment()
        
        print(f"\nValidation Results:")
        print(f"  Valid: {'✅' if validation['is_valid'] else '❌'}")
        
        print(f"\nComponent Status:")
        print(f"  Network exists: {'✅' if validation['network_exists'] else '❌'}")
        print(f"  Network available: {'✅' if validation['network_available'] else '❌'}")
        print(f"  Member exists: {'✅' if validation['member_exists'] else '❌'}")
        print(f"  Member available: {'✅' if validation['member_available'] else '❌'}")
        print(f"  Peer exists: {'✅' if validation['peer_exists'] else '❌'}")
        print(f"  Peer available: {'✅' if validation['peer_available'] else '❌'}")
        print(f"  Endpoints valid: {'✅' if validation['endpoints_valid'] else '❌'}")
        
        if validation['errors']:
            print(f"\nErrors:")
            for error in validation['errors']:
                print(f"  ❌ {error}")
        
        if not validation['is_valid']:
            sys.exit(1)
    else:
        # Deploy blockchain
        print("\nDeploying AWS Managed Blockchain...")
        print("⏱️  This process typically takes 30-45 minutes...")
        print("\nSteps:")
        print("1. Setting up VPC endpoint")
        print("2. Creating Hyperledger Fabric network")
        print("3. Creating member organization")
        print("4. Deploying peer node")
        print("5. Configuring chaincode storage\n")
        
        results = deployment.deploy_blockchain()
        
        # Display results
        print(f"\n{'='*50}")
        print("Deployment Results:")
        print(f"{'='*50}")
        
        if results['network_id']:
            print(f"\n✅ Blockchain Network:")
            print(f"  ID: {results['network_id']}")
            print(f"  Ordering Endpoint: {results['ordering_endpoint']}")
            
            print(f"\n✅ Member Organization:")
            print(f"  ID: {results['member_id']}")
            print(f"  CA Endpoint: {results['ca_endpoint']}")
            
            if results['peer_node_id']:
                print(f"\n✅ Peer Node:")
                print(f"  ID: {results['peer_node_id']}")
            
            print(f"\n✅ VPC Configuration:")
            print(f"  Endpoint ID: {results['vpc_endpoint_id']}")
        
        if results['errors']:
            print(f"\n❌ Errors:")
            for error in results['errors']:
                print(f"  - {error}")
            sys.exit(1)
        
        # Validate deployment
        print("\nValidating deployment...")
        validation = results.get('validation', {})
        
        if validation.get('is_valid'):
            print("\n✅ Blockchain deployment complete and validated!")
            
            # Save deployment info
            deployment_file = f"blockchain-deployment-{args.environment}-{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
            with open(deployment_file, 'w') as f:
                json.dump({
                    'environment': args.environment,
                    'region': args.region,
                    'timestamp': datetime.utcnow().isoformat(),
                    'network_id': results['network_id'],
                    'member_id': results['member_id'],
                    'peer_node_id': results['peer_node_id'],
                    'ca_endpoint': results['ca_endpoint'],
                    'ordering_endpoint': results['ordering_endpoint'],
                    'vpc_endpoint_id': results['vpc_endpoint_id']
                }, f, indent=2)
            
            print(f"\nDeployment info saved to: {deployment_file}")
            
            print("\nNext steps:")
            print(f"1. Update environment configuration:")
            print(f"   MANAGED_BLOCKCHAIN_NETWORK_ID={results['network_id']}")
            print(f"   MANAGED_BLOCKCHAIN_MEMBER_ID={results['member_id']}")
            print(f"2. Update Secrets Manager with these IDs")
            print(f"3. Deploy chaincode to the network")
            print(f"4. Create channels for medical records")
            print(f"5. Set up CloudWatch dashboards for monitoring")
            print(f"6. Configure backup and disaster recovery")
            
            print("\n⚠️  IMPORTANT:")
            print("  - Save the admin password from Secrets Manager")
            print("  - Document all endpoints for client configuration")
            print("  - Set up monitoring alerts for node health")
            print("  - Configure data retention policies")
        else:
            print("\n❌ Deployment validation failed!")
            for error in validation.get('errors', []):
                print(f"  - {error}")
            sys.exit(1)
    
    print(f"\n{'='*60}\n")


if __name__ == '__main__':
    main()
