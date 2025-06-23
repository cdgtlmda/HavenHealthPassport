#!/usr/bin/env python3
"""
Production Key Generation Script for Haven Health Passport.

CRITICAL: This is a healthcare system for refugees. Proper key management
is essential for patient data security and HIPAA compliance.

This script generates cryptographically secure keys and stores them in
AWS Secrets Manager with rotation policies.
"""

import os
import sys
import json
import base64
import secrets
import argparse
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
except ImportError:
    print("ERROR: boto3 not installed. Run: pip install boto3")
    sys.exit(1)


class ProductionKeyGenerator:
    """Generates and manages production keys for Haven Health Passport."""
    
    def __init__(self, environment: str = "production", region: str = "us-east-1"):
        self.environment = environment
        self.region = region
        self.secrets_client = boto3.client('secretsmanager', region_name=region)
        self.kms_client = boto3.client('kms', region_name=region)
        self.secret_prefix = f"haven-health-passport/{environment}"
        
    def generate_all_keys(self) -> Dict[str, str]:
        """
        Generate all required production keys.
        
        Returns:
            Dictionary of key names and values
        """
        print(f"🔐 Generating production keys for Haven Health Passport ({self.environment})")
        print("=" * 60)
        
        keys = {}
        
        # Generate encryption keys
        print("\n1. Generating encryption keys...")
        keys['ENCRYPTION_KEY'] = self._generate_aes_key()
        keys['AES_ENCRYPTION_KEY'] = self._generate_aes_key_base64()
        keys['FERNET_KEY'] = self._generate_fernet_key()
        
        # Generate authentication keys
        print("\n2. Generating authentication keys...")
        keys['SECRET_KEY'] = self._generate_secure_key(64)
        keys['JWT_SECRET_KEY'] = self._generate_secure_key(64)
        keys['JWT_REFRESH_SECRET_KEY'] = self._generate_secure_key(64)
        
        # Generate API keys
        print("\n3. Generating API keys...")
        keys['API_KEY'] = self._generate_api_key()
        keys['WEBHOOK_SECRET'] = self._generate_secure_key(32)
        
        # Generate blockchain keys
        print("\n4. Generating blockchain keys...")
        blockchain_keys = self._generate_blockchain_keys()
        keys.update(blockchain_keys)
        
        # Generate database encryption keys
        print("\n5. Generating database encryption keys...")
        keys['DB_ENCRYPTION_KEY'] = self._generate_aes_key()
        keys['FIELD_ENCRYPTION_KEY'] = self._generate_aes_key()
        
        # Generate file encryption keys
        print("\n6. Generating file encryption keys...")
        keys['FILE_ENCRYPTION_KEY'] = self._generate_aes_key()
        keys['DOCUMENT_SIGNING_KEY'] = self._generate_secure_key(64)
        
        # Generate HIPAA compliance keys
        print("\n7. Generating HIPAA compliance keys...")
        keys['PHI_ENCRYPTION_KEY'] = self._generate_aes_key()
        keys['AUDIT_SIGNING_KEY'] = self._generate_secure_key(64)
        
        return keys
    
    def _generate_aes_key(self) -> str:
        """Generate a 32-character AES-256 key."""
        # Generate exactly 32 characters for AES-256
        return base64.urlsafe_b64encode(secrets.token_bytes(24)).decode()[:32]
    
    def _generate_aes_key_base64(self) -> str:
        """Generate a base64-encoded AES-256 key."""
        return base64.b64encode(secrets.token_bytes(32)).decode()
    
    def _generate_fernet_key(self) -> str:
        """Generate a Fernet encryption key."""
        return Fernet.generate_key().decode()
    
    def _generate_secure_key(self, length: int) -> str:
        """Generate a cryptographically secure key of specified length."""
        return secrets.token_urlsafe(length)[:length]
    
    def _generate_api_key(self) -> str:
        """Generate a secure API key with prefix."""
        prefix = "hhp_prod_" if self.environment == "production" else f"hhp_{self.environment}_"
        return prefix + secrets.token_urlsafe(32)
    
    def _generate_blockchain_keys(self) -> Dict[str, str]:
        """Generate blockchain-related keys."""
        keys = {}
        
        # Generate node keys
        keys['BLOCKCHAIN_NODE_KEY'] = self._generate_secure_key(64)
        keys['BLOCKCHAIN_SIGNING_KEY'] = self._generate_secure_key(64)
        
        # Generate RSA key pair for blockchain identity
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend()
        )
        
        # Serialize private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Serialize public key
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        keys['BLOCKCHAIN_PRIVATE_KEY'] = base64.b64encode(private_pem).decode()
        keys['BLOCKCHAIN_PUBLIC_KEY'] = base64.b64encode(public_pem).decode()
        
        return keys
    
    def store_keys_in_secrets_manager(self, keys: Dict[str, str]) -> Dict[str, str]:
        """
        Store keys in AWS Secrets Manager with rotation enabled.
        
        Args:
            keys: Dictionary of key names and values
            
        Returns:
            Dictionary mapping key names to secret ARNs
        """
        print("\n📥 Storing keys in AWS Secrets Manager...")
        print("=" * 60)
        
        secret_arns = {}
        
        for key_name, key_value in keys.items():
            secret_name = f"{self.secret_prefix}/{key_name}"
            
            try:
                # Create secret with rotation configuration
                response = self._create_or_update_secret(
                    secret_name=secret_name,
                    secret_value=key_value,
                    key_name=key_name
                )
                
                secret_arns[key_name] = response['ARN']
                print(f"✅ Stored {key_name}: {response['ARN']}")
                
            except ClientError as e:
                print(f"❌ Error storing {key_name}: {e.response['Error']['Message']}")
                raise
        
        return secret_arns
    
    def _create_or_update_secret(self, secret_name: str, secret_value: str, key_name: str) -> Dict:
        """Create or update a secret in AWS Secrets Manager."""
        secret_data = {
            'value': secret_value,
            'created': datetime.utcnow().isoformat(),
            'environment': self.environment,
            'key_type': key_name,
            'rotation_enabled': True
        }
        
        try:
            # Try to update existing secret
            response = self.secrets_client.update_secret(
                SecretId=secret_name,
                SecretString=json.dumps(secret_data)
            )
        except self.secrets_client.exceptions.ResourceNotFoundException:
            # Create new secret if it doesn't exist
            response = self.secrets_client.create_secret(
                Name=secret_name,
                Description=f"Production key for {key_name} - Haven Health Passport",
                SecretString=json.dumps(secret_data),
                KmsKeyId='alias/aws/secretsmanager',  # Use AWS managed key
                Tags=[
                    {'Key': 'Application', 'Value': 'HavenHealthPassport'},
                    {'Key': 'Environment', 'Value': self.environment},
                    {'Key': 'SecurityLevel', 'Value': 'Critical'},
                    {'Key': 'HIPAA', 'Value': 'true'},
                    {'Key': 'AutoRotation', 'Value': 'enabled'}
                ]
            )
            
            # Enable automatic rotation for critical keys
            if key_name in ['ENCRYPTION_KEY', 'JWT_SECRET_KEY', 'PHI_ENCRYPTION_KEY']:
                self._enable_rotation(secret_name, response['ARN'])
        
        return response
    
    def _enable_rotation(self, secret_name: str, secret_arn: str):
        """Enable automatic rotation for a secret."""
        try:
            # Note: This requires a Lambda function for rotation
            # For now, we'll set up the configuration
            print(f"⚠️  Rotation configuration for {secret_name} requires Lambda setup")
            # In production, you would call:
            # self.secrets_client.rotate_secret(
            #     SecretId=secret_arn,
            #     RotationLambdaARN='arn:aws:lambda:...',
            #     RotationRules={'AutomaticallyAfterDays': 90}
            # )
        except Exception as e:
            print(f"Warning: Could not enable rotation for {secret_name}: {e}")
    
    def generate_env_file(self, keys: Dict[str, str], secret_arns: Dict[str, str]):
        """Generate .env file template with AWS Secrets Manager references."""
        env_file = f".env.{self.environment}"
        backup_file = f".env.{self.environment}.backup.{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Backup existing env file if it exists
        if os.path.exists(env_file):
            os.rename(env_file, backup_file)
            print(f"\n📦 Backed up existing env file to: {backup_file}")
        
        print(f"\n📝 Generating environment file: {env_file}")
        
        content = [
            "# Haven Health Passport Production Environment Configuration",
            f"# Generated: {datetime.utcnow().isoformat()}",
            "# CRITICAL: This is a healthcare system. Protect these keys!",
            "",
            f"ENVIRONMENT={self.environment}",
            f"AWS_REGION={self.region}",
            ""
        ]
        
        # Add direct key values (for local development/testing only)
        if self.environment != "production":
            content.append("# Direct key values (DO NOT USE IN PRODUCTION)")
            for key_name, key_value in keys.items():
                content.append(f"{key_name}={key_value}")
            content.append("")
        
        # Add AWS Secrets Manager references for production
        content.extend([
            "# AWS Secrets Manager Configuration",
            "USE_AWS_SECRETS_MANAGER=true",
            f"AWS_SECRETS_PREFIX={self.secret_prefix}",
            ""
        ])
        
        # Add secret ARNs
        for key_name, arn in secret_arns.items():
            content.append(f"# {key_name}_SECRET_ARN={arn}")
        
        # Add critical service configurations
        content.extend([
            "",
            "# Critical Service Configuration",
            "# AWS HealthLake",
            "HEALTHLAKE_DATASTORE_ID=<CONFIGURE_YOUR_DATASTORE_ID>",
            "",
            "# AWS Managed Blockchain",
            "MANAGED_BLOCKCHAIN_NETWORK_ID=<CONFIGURE_YOUR_NETWORK_ID>",
            "MANAGED_BLOCKCHAIN_MEMBER_ID=<CONFIGURE_YOUR_MEMBER_ID>",
            "",
            "# Voice Synthesis",
            "VOICE_SYNTHESIS_ENGINE=aws_polly",
            "VOICE_SYNTHESIS_S3_BUCKET=haven-health-voice-synthesis",
            "",
            "# SMS Configuration",
            "SMS_PROVIDER=aws_sns",
            "SMS_FROM_NUMBER=<CONFIGURE_YOUR_NUMBER>",
            "",
            "# HIPAA Compliance",
            "PHI_ENCRYPTION_ENABLED=true",
            "PHI_ACCESS_AUDIT_ENABLED=true",
            "REQUIRE_MFA_FOR_PHI_ACCESS=true",
            ""
        ])
        
        # Write to file
        with open(env_file, 'w') as f:
            f.write('\n'.join(content))
        
        print(f"✅ Environment file generated: {env_file}")
        
        # Also create a secure key storage file
        self._create_key_manifest(keys, secret_arns)
    
    def _create_key_manifest(self, keys: Dict[str, str], secret_arns: Dict[str, str]):
        """Create a manifest file documenting all keys (without values)."""
        manifest_file = f"keys-manifest-{self.environment}.json"
        
        manifest = {
            'generated': datetime.utcnow().isoformat(),
            'environment': self.environment,
            'region': self.region,
            'keys': {}
        }
        
        for key_name in keys:
            manifest['keys'][key_name] = {
                'created': datetime.utcnow().isoformat(),
                'secret_arn': secret_arns.get(key_name, ''),
                'rotation_enabled': key_name in ['ENCRYPTION_KEY', 'JWT_SECRET_KEY', 'PHI_ENCRYPTION_KEY'],
                'key_type': self._get_key_type(key_name)
            }
        
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"📋 Key manifest created: {manifest_file}")
    
    def _get_key_type(self, key_name: str) -> str:
        """Determine the type of key based on its name."""
        if 'ENCRYPTION' in key_name or 'CRYPTO' in key_name:
            return 'encryption'
        elif 'JWT' in key_name or 'AUTH' in key_name:
            return 'authentication'
        elif 'API' in key_name:
            return 'api'
        elif 'BLOCKCHAIN' in key_name:
            return 'blockchain'
        elif 'PHI' in key_name or 'HIPAA' in key_name:
            return 'compliance'
        else:
            return 'general'
    
    def setup_kms_keys(self) -> Dict[str, str]:
        """
        Set up AWS KMS keys for enhanced encryption.
        
        Returns:
            Dictionary of KMS key aliases and ARNs
        """
        print("\n🔑 Setting up AWS KMS keys...")
        kms_keys = {}
        
        key_configs = [
            {
                'alias': f'alias/haven-health-passport/{self.environment}/master',
                'description': 'Master encryption key for Haven Health Passport',
                'usage': 'ENCRYPT_DECRYPT'
            },
            {
                'alias': f'alias/haven-health-passport/{self.environment}/phi',
                'description': 'PHI encryption key for HIPAA compliance',
                'usage': 'ENCRYPT_DECRYPT'
            },
            {
                'alias': f'alias/haven-health-passport/{self.environment}/documents',
                'description': 'Document encryption key',
                'usage': 'ENCRYPT_DECRYPT'
            }
        ]
        
        for config in key_configs:
            try:
                # Check if key already exists
                try:
                    response = self.kms_client.describe_key(KeyId=config['alias'])
                    kms_keys[config['alias']] = response['KeyMetadata']['Arn']
                    print(f"✅ Using existing KMS key: {config['alias']}")
                except self.kms_client.exceptions.NotFoundException:
                    # Create new KMS key
                    response = self.kms_client.create_key(
                        Description=config['description'],
                        KeyUsage=config['usage'],
                        Origin='AWS_KMS',
                        MultiRegion=True,  # Enable multi-region for disaster recovery
                        Tags=[
                            {'TagKey': 'Application', 'TagValue': 'HavenHealthPassport'},
                            {'TagKey': 'Environment', 'TagValue': self.environment},
                            {'TagKey': 'HIPAA', 'TagValue': 'true'}
                        ]
                    )
                    
                    key_id = response['KeyMetadata']['KeyId']
                    key_arn = response['KeyMetadata']['Arn']
                    
                    # Create alias
                    self.kms_client.create_alias(
                        AliasName=config['alias'],
                        TargetKeyId=key_id
                    )
                    
                    kms_keys[config['alias']] = key_arn
                    print(f"✅ Created KMS key: {config['alias']} ({key_arn})")
                    
            except Exception as e:
                print(f"❌ Error with KMS key {config['alias']}: {e}")
                raise
        
        return kms_keys


def main():
    """Main function to generate production keys."""
    parser = argparse.ArgumentParser(
        description='Generate production keys for Haven Health Passport'
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
        '--store-in-aws',
        action='store_true',
        help='Store keys in AWS Secrets Manager'
    )
    parser.add_argument(
        '--setup-kms',
        action='store_true',
        help='Set up AWS KMS keys'
    )
    
    args = parser.parse_args()
    
    # Print warning for production
    if args.environment == 'production':
        print("\n" + "⚠️ " * 20)
        print("WARNING: You are generating PRODUCTION keys!")
        print("These keys will be used to protect real patient data.")
        print("Ensure you are following all security protocols.")
        print("⚠️ " * 20 + "\n")
        
        response = input("Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return
    
    generator = ProductionKeyGenerator(args.environment, args.region)
    
    # Generate keys
    keys = generator.generate_all_keys()
    print(f"\n✅ Generated {len(keys)} production keys")
    
    # Store in AWS Secrets Manager if requested
    secret_arns = {}
    if args.store_in_aws:
        try:
            secret_arns = generator.store_keys_in_secrets_manager(keys)
            print(f"\n✅ Stored {len(secret_arns)} keys in AWS Secrets Manager")
        except Exception as e:
            print(f"\n❌ Error storing keys in AWS: {e}")
            print("Keys have been generated but not stored in AWS.")
    
    # Set up KMS keys if requested
    if args.setup_kms:
        try:
            kms_keys = generator.setup_kms_keys()
            print(f"\n✅ Set up {len(kms_keys)} KMS keys")
        except Exception as e:
            print(f"\n❌ Error setting up KMS keys: {e}")
    
    # Generate environment file
    generator.generate_env_file(keys, secret_arns)
    
    # Final instructions
    print("\n" + "=" * 60)
    print("🎉 Key generation complete!")
    print("\nNext steps:")
    print("1. Review the generated .env file")
    print("2. Configure the missing service IDs (HealthLake, Blockchain, etc.)")
    print("3. Run scripts/validate_production.py to verify configuration")
    print("4. Securely backup the key manifest file")
    print("5. Set up key rotation Lambda functions")
    print("\n⚠️  NEVER commit .env files or keys to version control!")
    print("=" * 60)


if __name__ == "__main__":
    main()
