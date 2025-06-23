#!/usr/bin/env python3
"""
Deploy AWS HealthLake for Haven Health Passport.

This script deploys and configures AWS HealthLake FHIR datastore
for production use.
"""

import sys
import os
import argparse
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, '/Users/cadenceapeiron/Documents/HavenHealthPassport')

from src.infrastructure.healthlake_deployment import get_healthlake_deployment


def main():
    parser = argparse.ArgumentParser(
        description='Deploy AWS HealthLake for Haven Health Passport'
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
    print(f"Haven Health Passport - AWS HealthLake Deployment")
    print(f"Environment: {args.environment}")
    print(f"Region: {args.region}")
    print(f"Time: {datetime.utcnow().isoformat()}")
    print(f"{'='*60}\n")
    
    # Warning for production
    if args.environment == 'production' and not args.validate_only:
        print("⚠️  WARNING: You are deploying HealthLake for PRODUCTION!")
        print("This will create AWS resources that incur costs.")
        print("Ensure you have proper AWS credentials and permissions.")
        response = input("\nContinue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return
    
    # Set environment
    os.environ['ENVIRONMENT'] = args.environment
    os.environ['AWS_REGION'] = args.region
    
    # Get deployment instance
    deployment = get_healthlake_deployment()
    
    if args.validate_only:
        # Validate existing deployment
        print("\nValidating HealthLake deployment...")
        validation = deployment.validate_deployment()
        
        print(f"\nValidation Results:")
        print(f"  Valid: {'✅' if validation['is_valid'] else '❌'}")
        
        print(f"\nComponent Status:")
        print(f"  Datastore exists: {'✅' if validation['datastore_exists'] else '❌'}")
        print(f"  Datastore active: {'✅' if validation['datastore_active'] else '❌'}")
        print(f"  Encryption enabled: {'✅' if validation['encryption_enabled'] else '❌'}")
        print(f"  S3 bucket exists: {'✅' if validation['s3_bucket_exists'] else '❌'}")
        print(f"  Import role valid: {'✅' if validation['import_role_valid'] else '❌'}")
        print(f"  Export role valid: {'✅' if validation['export_role_valid'] else '❌'}")
        
        if validation['errors']:
            print(f"\nErrors:")
            for error in validation['errors']:
                print(f"  ❌ {error}")
        
        if not validation['is_valid']:
            sys.exit(1)
    else:
        # Deploy HealthLake
        print("\nDeploying AWS HealthLake...")
        print("This may take 10-15 minutes...\n")
        
        results = deployment.deploy_healthlake()
        
        # Display results
        print(f"\nDeployment Results:")
        
        if results['datastore_id']:
            print(f"\n✅ HealthLake Datastore:")
            print(f"  ID: {results['datastore_id']}")
            print(f"  ARN: {results['datastore_arn']}")
            
            print(f"\n✅ S3 Bucket:")
            print(f"  Name: {results['s3_bucket']}")
            print(f"  Import path: s3://{results['s3_bucket']}/imports/")
            print(f"  Export path: s3://{results['s3_bucket']}/exports/")
            
            print(f"\n✅ IAM Roles:")
            print(f"  Import: {results['import_role']}")
            print(f"  Export: {results['export_role']}")
        
        if results['errors']:
            print(f"\n❌ Errors:")
            for error in results['errors']:
                print(f"  - {error}")
            sys.exit(1)
        
        # Validate deployment
        print("\nValidating deployment...")
        validation = results.get('validation', {})
        
        if validation.get('is_valid'):
            print("\n✅ HealthLake deployment complete and validated!")
            
            # Save deployment info
            deployment_file = f"healthlake-deployment-{args.environment}-{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
            with open(deployment_file, 'w') as f:
                json.dump({
                    'environment': args.environment,
                    'region': args.region,
                    'timestamp': datetime.utcnow().isoformat(),
                    'datastore_id': results['datastore_id'],
                    'datastore_arn': results['datastore_arn'],
                    's3_bucket': results['s3_bucket'],
                    'import_role': results['import_role'],
                    'export_role': results['export_role']
                }, f, indent=2)
            
            print(f"\nDeployment info saved to: {deployment_file}")
            
            print("\nNext steps:")
            print(f"1. Update HEALTHLAKE_DATASTORE_ID in environment: {results['datastore_id']}")
            print("2. Update Secrets Manager with the datastore ID")
            print("3. Test FHIR resource creation")
            print("4. Configure data import if needed")
            print("5. Set up CloudWatch dashboards for monitoring")
            
            print("\n⚠️  IMPORTANT:")
            print(f"  Add this to your environment configuration:")
            print(f"  HEALTHLAKE_DATASTORE_ID={results['datastore_id']}")
        else:
            print("\n❌ Deployment validation failed!")
            for error in validation.get('errors', []):
                print(f"  - {error}")
            sys.exit(1)
    
    print(f"\n{'='*60}\n")


if __name__ == '__main__':
    main()
