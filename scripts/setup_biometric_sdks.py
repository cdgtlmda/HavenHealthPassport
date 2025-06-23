#!/usr/bin/env python3
"""
Biometric SDK Configuration for Haven Health Passport
Configures AWS Rekognition and Neurotechnology SDK for patient identity verification
CRITICAL: This handles real patient biometric data - proper configuration is essential
"""

import os
import sys
import json
import boto3
import argparse
import logging
from datetime import datetime
import subprocess

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BiometricSDKConfigurator:
    """Configures biometric SDKs for production use"""
    
    def __init__(self, environment: str):
        self.environment = environment
        self.secrets_client = boto3.client('secretsmanager')
        self.rekognition_client = boto3.client('rekognition')
        self.iam_client = boto3.client('iam')
        
    def configure_aws_rekognition(self) -> bool:
        """Configure AWS Rekognition for facial recognition"""
        print("\n" + "="*60)
        print("Configuring AWS Rekognition")
        print("="*60)
        
        try:
            # Create Rekognition collection for patient faces
            collection_id = f"haven-health-{self.environment}-patients"
            
            try:
                response = self.rekognition_client.create_collection(
                    CollectionId=collection_id,
                    Tags={
                        'Environment': self.environment,
                        'Service': 'haven-health-passport',
                        'Purpose': 'patient-verification',
                        'Compliance': 'HIPAA'
                    }
                )
                logger.info(f"Created Rekognition collection: {collection_id}")
            except self.rekognition_client.exceptions.ResourceAlreadyExistsException:
                logger.info(f"Rekognition collection already exists: {collection_id}")
            
            # Create IAM role for Rekognition
            role_name = f"HavenHealthRekognition{self.environment.capitalize()}Role"
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "rekognition.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }
            
            try:
                self.iam_client.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description=f"Role for Haven Health Rekognition in {self.environment}",
                    Tags=[
                        {'Key': 'Environment', 'Value': self.environment},
                        {'Key': 'Service', 'Value': 'haven-health-passport'}
                    ]
                )
                
                # Attach necessary policies
                self.iam_client.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn='arn:aws:iam::aws:policy/AmazonRekognitionFullAccess'
                )
                logger.info(f"Created IAM role: {role_name}")
            except self.iam_client.exceptions.EntityAlreadyExistsException:
                logger.info(f"IAM role already exists: {role_name}")
            
            # Store Rekognition configuration
            config = {
                'collection_id': collection_id,
                'role_arn': f"arn:aws:iam::{boto3.client('sts').get_caller_identity()['Account']}:role/{role_name}",
                'configured_at': datetime.utcnow().isoformat(),
                'compliance': 'HIPAA',
                'encryption': 'AES-256'
            }
            
            secret_name = f"haven-health-passport/{self.environment}/biometric/rekognition"
            try:
                self.secrets_client.create_secret(
                    Name=secret_name,
                    SecretString=json.dumps(config),
                    Description=f"AWS Rekognition configuration for {self.environment}"
                )
            except self.secrets_client.exceptions.ResourceExistsException:
                self.secrets_client.update_secret(
                    SecretId=secret_name,
                    SecretString=json.dumps(config)
                )
            
            print("✅ AWS Rekognition configured successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure AWS Rekognition: {str(e)}")
            print("❌ Failed to configure AWS Rekognition")
            return False
    
    def configure_neurotechnology_sdk(self) -> bool:
        """Configure Neurotechnology SDK for fingerprint matching"""
        print("\n" + "="*60)
        print("Configuring Neurotechnology SDK")
        print("="*60)
        
        print("\nNeurotechnology SDK requires manual installation.")
        print("Please ensure you have:")
        print("1. Valid Neurotechnology license file")
        print("2. SDK binaries installed in /opt/neurotechnology/")
        print("3. License server configured")
        
        license_key = input("\nEnter Neurotechnology license key: ").strip()
        license_server = input("Enter license server URL: ").strip()
        
        if not license_key or not license_server:
            print("❌ License key and server are required")
            return False
        
        try:
            # Store Neurotechnology configuration
            config = {
                'license_key': license_key,
                'license_server': license_server,
                'sdk_path': '/opt/neurotechnology',
                'configured_at': datetime.utcnow().isoformat(),
                'compliance': 'HIPAA',
                'algorithm': 'VeriFinger'
            }
            
            secret_name = f"haven-health-passport/{self.environment}/biometric/neurotechnology"
            try:
                self.secrets_client.create_secret(
                    Name=secret_name,
                    SecretString=json.dumps(config),
                    Description=f"Neurotechnology SDK configuration for {self.environment}"
                )
            except self.secrets_client.exceptions.ResourceExistsException:
                self.secrets_client.update_secret(
                    SecretId=secret_name,
                    SecretString=json.dumps(config)
                )
            
            print("✅ Neurotechnology SDK configuration stored")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure Neurotechnology SDK: {str(e)}")
            print("❌ Failed to configure Neurotechnology SDK")
            return False
    
    def configure_all(self) -> None:
        """Configure all biometric SDKs"""
        print("\n" + "="*80)
        print("Haven Health Passport - Biometric SDK Configuration")
        print(f"Environment: {self.environment.upper()}")
        print("="*80)
        print("\n⚠️  CRITICAL: This system handles real patient biometric data.")
        print("Proper configuration is essential for patient identity verification.\n")
        
        rekognition_success = self.configure_aws_rekognition()
        neurotechnology_success = self.configure_neurotechnology_sdk()
        
        print("\n" + "="*80)
        print("Configuration Summary")
        print("="*80)
        print(f"AWS Rekognition: {'✅ Configured' if rekognition_success else '❌ Failed'}")
        print(f"Neurotechnology SDK: {'✅ Configured' if neurotechnology_success else '❌ Failed'}")
        
        if rekognition_success and neurotechnology_success:
            print("\n✅ All biometric SDKs configured successfully!")
            print("System is ready for patient identity verification.")
        else:
            print("\n⚠️  WARNING: Some SDKs failed to configure.")
            print("System is not ready for production!")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Configure biometric SDKs for Haven Health Passport'
    )
    parser.add_argument(
        '--environment',
        choices=['development', 'staging', 'production'],
        required=True,
        help='Target environment for configuration'
    )
    
    args = parser.parse_args()
    
    # Production safety check
    if args.environment == 'production':
        print("\n⚠️  WARNING: Configuring PRODUCTION environment!")
        print("This will handle real patient biometric data.")
        confirm = input("Type 'CONFIGURE PRODUCTION' to continue: ")
        if confirm != 'CONFIGURE PRODUCTION':
            print("Configuration cancelled.")
            sys.exit(0)
    
    # Check AWS credentials
    try:
        boto3.client('sts').get_caller_identity()
    except Exception as e:
        print(f"\n❌ AWS credentials not configured: {str(e)}")
        print("Please configure AWS credentials before running this script.")
        sys.exit(1)
    
    # Run configuration
    configurator = BiometricSDKConfigurator(args.environment)
    configurator.configure_all()


if __name__ == '__main__':
    main()
