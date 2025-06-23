#!/usr/bin/env python3
"""
Configure AWS KMS for Haven Health Passport.

This script sets up all KMS keys required for production use.
Run this as part of infrastructure setup before deploying the application.
"""

import sys
import argparse
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, '/Users/cadenceapeiron/Documents/HavenHealthPassport')

from src.security.key_management.kms_configuration import get_kms_configuration


def main():
    parser = argparse.ArgumentParser(
        description='Configure AWS KMS for Haven Health Passport'
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
        help='Only validate existing configuration'
    )
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"Haven Health Passport - KMS Configuration")
    print(f"Environment: {args.environment}")
    print(f"Region: {args.region}")
    print(f"Time: {datetime.utcnow().isoformat()}")
    print(f"{'='*60}\n")
    
    # Warning for production
    if args.environment == 'production' and not args.validate_only:
        print("⚠️  WARNING: You are configuring KMS for PRODUCTION!")
        print("This will create encryption keys for protecting patient data.")
        response = input("\nContinue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return
    
    # Set environment
    import os
    os.environ['ENVIRONMENT'] = args.environment
    os.environ['AWS_REGION'] = args.region
    
    # Get KMS configuration
    kms_config = get_kms_configuration()
    
    if args.validate_only:
        # Validate existing configuration
        print("\nValidating KMS configuration...")
        validation = kms_config.validate_kms_configuration()
        
        print(f"\nValidation Results:")
        print(f"  Valid: {validation['is_valid']}")
        print(f"\nKeys Accessible:")
        for key_type, accessible in validation['keys_accessible'].items():
            print(f"  - {key_type}: {'✅' if accessible else '❌'}")
        
        print(f"\nRotation Enabled:")
        for key_type, enabled in validation['rotation_enabled'].items():
            print(f"  - {key_type}: {'✅' if enabled else '❌'}")
        
        if validation['errors']:
            print(f"\nErrors:")
            for error in validation['errors']:
                print(f"  ❌ {error}")
        
        if not validation['is_valid']:
            sys.exit(1)
    else:
        # Configure KMS
        print("\nConfiguring KMS...")
        results = kms_config.configure_kms()
        
        # Display results
        print(f"\nConfiguration Results:")
        print(f"\nKeys Created:")
        for key_type, key_id in results['keys_created'].items():
            print(f"  - {key_type}: {key_id}")
        
        print(f"\nAliases Created:")
        for key_type, alias in results['aliases_created'].items():
            print(f"  - {key_type}: {alias}")
        
        print(f"\nRotation Configured:")
        for key_type, enabled in results['rotation_configured'].items():
            print(f"  - {key_type}: {'✅' if enabled else '❌'}")
        
        if results['errors']:
            print(f"\nErrors:")
            for error in results['errors']:
                print(f"  ❌ {error}")
            sys.exit(1)
        
        # Validate configuration
        print("\nValidating configuration...")
        validation = kms_config.validate_kms_configuration()
        
        if validation['is_valid']:
            print("\n✅ KMS configuration complete and validated!")
            
            # Save configuration summary
            config_file = f"kms-config-{args.environment}-{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
            with open(config_file, 'w') as f:
                json.dump({
                    'environment': args.environment,
                    'region': args.region,
                    'timestamp': datetime.utcnow().isoformat(),
                    'results': results,
                    'validation': validation
                }, f, indent=2)
            
            print(f"\nConfiguration saved to: {config_file}")
            
            print("\nNext steps:")
            print("1. Update IAM roles with KMS key permissions")
            print("2. Configure application to use KMS keys")
            print("3. Test encryption/decryption operations")
            print("4. Set up key usage monitoring")
        else:
            print("\n❌ Configuration validation failed!")
            for error in validation['errors']:
                print(f"  - {error}")
            sys.exit(1)
    
    print(f"\n{'='*60}\n")


if __name__ == '__main__':
    main()
