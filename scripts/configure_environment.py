#!/usr/bin/env python3
"""
Configure production environment variables for Haven Health Passport.

This script helps set up and validate all required environment variables
for production deployment.
"""

import sys
import os
import argparse
from datetime import datetime

# Add src to path
sys.path.insert(0, '/Users/cadenceapeiron/Documents/HavenHealthPassport')

from src.config.production_environment import get_environment_config


def main():
    parser = argparse.ArgumentParser(
        description='Configure production environment for Haven Health Passport'
    )
    parser.add_argument(
        '--environment',
        choices=['production', 'staging', 'development'],
        default='production',
        help='Target environment'
    )
    parser.add_argument(
        '--generate-template',
        action='store_true',
        help='Generate .env.template file'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate existing configuration'
    )
    parser.add_argument(
        '--from-file',
        help='Load environment from file'
    )
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"Haven Health Passport - Environment Configuration")
    print(f"Environment: {args.environment}")
    print(f"Time: {datetime.utcnow().isoformat()}")
    print(f"{'='*60}\n")
    
    # Set environment
    os.environ['ENVIRONMENT'] = args.environment
    
    # Get environment configuration
    env_config = get_environment_config()
    
    if args.generate_template:
        # Generate template file
        template_file = f'.env.{args.environment}.template'
        print(f"Generating environment template: {template_file}")
        env_config.generate_env_template(template_file)
        
        print(f"\n✅ Template generated: {template_file}")
        print("\nNext steps:")
        print(f"1. Copy {template_file} to .env.{args.environment}")
        print("2. Configure all required values")
        print("3. Run validation: python scripts/configure_environment.py --validate-only")
        
    elif args.from_file:
        # Load environment from file
        print(f"Loading environment from: {args.from_file}")
        
        if not os.path.exists(args.from_file):
            print(f"❌ File not found: {args.from_file}")
            sys.exit(1)
        
        # Load variables from file
        loaded = 0
        with open(args.from_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
                    loaded += 1
        
        print(f"Loaded {loaded} environment variables")
        
        # Validate configuration
        results = env_config.configure_environment()
        
        if results['is_valid']:
            print("\n✅ Environment configuration is valid!")
        else:
            print("\n❌ Environment configuration has errors!")
            if results['missing']:
                print(f"\nMissing variables: {results['missing']}")
            if results['invalid']:
                print(f"\nInvalid values: {results['invalid']}")
            sys.exit(1)
            
    elif args.validate_only:
        # Validate existing configuration
        print("Validating environment configuration...")
        
        results = env_config.configure_environment()
        
        print(f"\nConfiguration Status:")
        print(f"  Valid: {'✅' if results['is_valid'] else '❌'}")
        print(f"  Configured: {len(results['configured'])} variables")
        
        # Show details
        print(f"\nVariable Status:")
        for var_name, status in sorted(results['configured'].items()):
            value = os.getenv(var_name, 'NOT SET')
            if env_config.required_env_vars.get(var_name, {}).get('sensitive', False):
                value = '***'
            elif len(value) > 50:
                value = value[:50] + '...'
            
            status_icon = '✅' if status == 'set' else '⚠️'
            print(f"  {status_icon} {var_name}: {value} ({status})")
        
        if results['missing']:
            print(f"\n❌ Missing Required Variables:")
            for var in results['missing']:
                desc = env_config.required_env_vars[var]['description']
                print(f"  - {var}: {desc}")
        
        if results['invalid']:
            print(f"\n❌ Invalid Values:")
            for var in results['invalid']:
                print(f"  - {var}")
        
        if results['warnings']:
            print(f"\n⚠️  Warnings:")
            for warning in results['warnings']:
                print(f"  - {warning}")
        
        if not results['is_valid']:
            sys.exit(1)
            
    else:
        # Interactive configuration
        print("Starting interactive environment configuration...")
        
        # First, load any existing environment
        env_file = f'.env.{args.environment}'
        if os.path.exists(env_file):
            response = input(f"\nFound existing {env_file}. Load it? (yes/no): ")
            if response.lower() == 'yes':
                os.system(f'python {__file__} --from-file {env_file}')
                return
        
        # Configure each variable
        print("\nConfiguring environment variables...")
        print("Press Enter to use default value, or enter a new value.\n")
        
        for var_name, config in env_config.required_env_vars.items():
            current_value = os.getenv(var_name, config.get('default', ''))
            
            print(f"\n{var_name}")
            print(f"  Description: {config['description']}")
            if config.get('required'):
                print("  REQUIRED")
            if current_value:
                if config.get('sensitive', False):
                    print(f"  Current: ***")
                else:
                    print(f"  Current: {current_value}")
            
            if config.get('sensitive', False):
                import getpass
                new_value = getpass.getpass("  New value (hidden): ")
            else:
                new_value = input("  New value: ")
            
            if new_value:
                os.environ[var_name] = new_value
            elif not current_value and config.get('default'):
                os.environ[var_name] = config['default']
        
        # Validate configuration
        print("\nValidating configuration...")
        results = env_config.configure_environment()
        
        if results['is_valid']:
            print("\n✅ Configuration is valid!")
            
            # Save to file
            save_file = f'.env.{args.environment}'
            response = input(f"\nSave to {save_file}? (yes/no): ")
            if response.lower() == 'yes':
                with open(save_file, 'w') as f:
                    f.write(f"# Haven Health Passport - {args.environment} Environment\n")
                    f.write(f"# Generated: {datetime.utcnow().isoformat()}\n\n")
                    
                    for var_name in sorted(env_config.required_env_vars.keys()):
                        value = os.getenv(var_name, '')
                        if value:
                            f.write(f"{var_name}={value}\n")
                
                print(f"\n✅ Configuration saved to: {save_file}")
                print("\n⚠️  IMPORTANT: Add this file to .gitignore!")
        else:
            print("\n❌ Configuration has errors!")
            sys.exit(1)
    
    print(f"\n{'='*60}\n")


if __name__ == '__main__':
    main()
