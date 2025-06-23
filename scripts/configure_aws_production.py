#!/usr/bin/env python3
"""
Configure AWS Services for Haven Health Passport Production.

CRITICAL: This script sets up all required AWS services for the healthcare
system. Missing or misconfigured services can prevent patient care.

Services configured:
- AWS HealthLake (FHIR datastore)
- AWS Managed Blockchain
- S3 buckets with encryption
- SNS for notifications
- KMS keys for encryption
- CloudWatch for monitoring
"""

import os
import sys
import json
import time
import boto3
from datetime import datetime
from typing import Dict, Optional, Tuple, List

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.utils.logging import get_logger

logger = get_logger(__name__)


class AWSServiceConfigurator:
    """Configure all AWS services for Haven Health Passport."""
    
    def __init__(self, region: str = "us-east-1", environment: str = "production"):
        self.region = region
        self.environment = environment
        self.account_id = boto3.client('sts').get_caller_identity()['Account']
        
        # Initialize clients
        self.healthlake = boto3.client('healthlake', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        self.sns = boto3.client('sns', region_name=region)
        self.kms = boto3.client('kms', region_name=region)
        self.blockchain = boto3.client('managedblockchain', region_name=region)
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.iam = boto3.client('iam', region_name=region)
        
        # Resource naming
        self.resource_prefix = f"haven-health-{environment}"
        
        logger.info(f"Initialized AWS configurator for {environment} in {region}")
    
    def configure_all_services(self) -> Dict[str, str]:
        """
        Configure all required AWS services.
        
        Returns:
            Dictionary of service IDs and ARNs
        """
        print("\n" + "="*60)
        print("🏥 Configuring AWS Services for Haven Health Passport")
        print(f"Environment: {self.environment}")
        print(f"Region: {self.region}")
        print(f"Account: {self.account_id}")
        print("="*60 + "\n")
        
        config = {}
        
        # 1. Configure KMS keys
        print("1️⃣ Configuring KMS encryption keys...")
        kms_config = self.configure_kms_keys()
        config.update(kms_config)
        
        # 2. Configure S3 buckets
        print("\n2️⃣ Configuring S3 buckets...")
        s3_config = self.configure_s3_buckets()
        config.update(s3_config)
        
        # 3. Configure HealthLake
        print("\n3️⃣ Configuring AWS HealthLake FHIR datastore...")
        healthlake_config = self.configure_healthlake()
        config.update(healthlake_config)
        
        # 4. Configure Managed Blockchain
        print("\n4️⃣ Configuring AWS Managed Blockchain...")
        blockchain_config = self.configure_blockchain()
        config.update(blockchain_config)
        
        # 5. Configure SNS
        print("\n5️⃣ Configuring SNS for notifications...")
        sns_config = self.configure_sns()
        config.update(sns_config)
        
        # 6. Configure CloudWatch
        print("\n6️⃣ Configuring CloudWatch monitoring...")
        cloudwatch_config = self.configure_cloudwatch()
        config.update(cloudwatch_config)
        
        # Save configuration
        self.save_configuration(config)
        
        return config
    
    def configure_kms_keys(self) -> Dict[str, str]:
        """Configure KMS encryption keys."""
        kms_config = {}
        
        key_configs = [
            {
                'alias': f"{self.resource_prefix}-master",
                'description': 'Master encryption key for Haven Health Passport',
                'key_policy': self._get_kms_key_policy('master')
            },
            {
                'alias': f"{self.resource_prefix}-phi",
                'description': 'PHI encryption key for HIPAA compliance',
                'key_policy': self._get_kms_key_policy('phi')
            },
            {
                'alias': f"{self.resource_prefix}-documents",
                'description': 'Document encryption key for medical records',
                'key_policy': self._get_kms_key_policy('documents')
            }
        ]
        
        for config in key_configs:
            try:
                # Check if key exists
                alias = f"alias/{config['alias']}"
                try:
                    response = self.kms.describe_key(KeyId=alias)
                    key_id = response['KeyMetadata']['KeyId']
                    kms_config[config['alias']] = key_id
                    print(f"✅ Using existing KMS key: {alias}")
                except self.kms.exceptions.NotFoundException:
                    # Create new key
                    response = self.kms.create_key(
                        Description=config['description'],
                        KeyUsage='ENCRYPT_DECRYPT',
                        Origin='AWS_KMS',
                        MultiRegion=False,
                        KeyPolicy=json.dumps(config['key_policy'])
                    )
                    
                    key_id = response['KeyMetadata']['KeyId']
                    
                    # Create alias
                    self.kms.create_alias(
                        AliasName=alias,
                        TargetKeyId=key_id
                    )
                    
                    # Enable automatic rotation
                    self.kms.enable_key_rotation(KeyId=key_id)
                    
                    kms_config[config['alias']] = key_id
                    print(f"✅ Created KMS key: {alias}")
                    
            except Exception as e:
                logger.error(f"Failed to configure KMS key {config['alias']}: {e}")
                raise
        
        return kms_config
    
    def configure_s3_buckets(self) -> Dict[str, str]:
        """Configure S3 buckets with encryption and compliance."""
        s3_config = {}
        
        bucket_configs = [
            {
                'name': f"{self.resource_prefix}-medical-records",
                'purpose': 'Medical records and documents',
                'encryption_key': f"{self.resource_prefix}-documents"
            },
            {
                'name': f"{self.resource_prefix}-voice-synthesis",
                'purpose': 'Voice synthesis audio files',
                'encryption_key': f"{self.resource_prefix}-phi"
            },
            {
                'name': f"{self.resource_prefix}-backups",
                'purpose': 'System backups',
                'encryption_key': f"{self.resource_prefix}-master"
            }
        ]
        
        for config in bucket_configs:
            bucket_name = config['name']
            
            try:
                # Check if bucket exists
                try:
                    self.s3.head_bucket(Bucket=bucket_name)
                    print(f"✅ Using existing S3 bucket: {bucket_name}")
                except:
                    # Create bucket
                    if self.region == 'us-east-1':
                        self.s3.create_bucket(Bucket=bucket_name)
                    else:
                        self.s3.create_bucket(
                            Bucket=bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.region}
                        )
                    
                    print(f"✅ Created S3 bucket: {bucket_name}")
                
                # Enable encryption
                kms_key_alias = f"alias/{config['encryption_key']}"
                self.s3.put_bucket_encryption(
                    Bucket=bucket_name,
                    ServerSideEncryptionConfiguration={
                        'Rules': [{
                            'ApplyServerSideEncryptionByDefault': {
                                'SSEAlgorithm': 'aws:kms',
                                'KMSMasterKeyID': kms_key_alias
                            }
                        }]
                    }
                )
                
                # Enable versioning
                self.s3.put_bucket_versioning(
                    Bucket=bucket_name,
                    VersioningConfiguration={'Status': 'Enabled'}
                )
                
                # Enable logging
                self.s3.put_bucket_logging(
                    Bucket=bucket_name,
                    BucketLoggingStatus={
                        'LoggingEnabled': {
                            'TargetBucket': bucket_name,
                            'TargetPrefix': 'access-logs/'
                        }
                    }
                )
                
                # Set lifecycle policy for compliance
                self.s3.put_bucket_lifecycle_configuration(
                    Bucket=bucket_name,
                    LifecycleConfiguration={
                        'Rules': [{
                            'ID': 'HIPAA-retention',
                            'Status': 'Enabled',
                            'Transitions': [{
                                'Days': 90,
                                'StorageClass': 'GLACIER'
                            }],
                            'NoncurrentVersionExpiration': {
                                'NoncurrentDays': 2555  # 7 years
                            }
                        }]
                    }
                )
                
                s3_config[config['purpose']] = bucket_name
                
            except Exception as e:
                logger.error(f"Failed to configure S3 bucket {bucket_name}: {e}")
                raise
        
        return s3_config
    
    def configure_healthlake(self) -> Dict[str, str]:
        """Configure AWS HealthLake FHIR datastore."""
        config = {}
        
        datastore_name = f"{self.resource_prefix}-fhir-datastore"
        
        try:
            # List existing datastores
            response = self.healthlake.list_fhir_datastores()
            
            existing_datastore = None
            for datastore in response.get('DatastorePropertiesList', []):
                if datastore['DatastoreName'] == datastore_name:
                    existing_datastore = datastore
                    break
            
            if existing_datastore:
                datastore_id = existing_datastore['DatastoreId']
                status = existing_datastore['DatastoreStatus']
                
                if status == 'ACTIVE':
                    print(f"✅ Using existing HealthLake datastore: {datastore_name}")
                else:
                    print(f"⏳ HealthLake datastore exists but status is: {status}")
                
                config['HEALTHLAKE_DATASTORE_ID'] = datastore_id
            else:
                # Create new datastore
                print(f"Creating new HealthLake datastore: {datastore_name}")
                
                response = self.healthlake.create_fhir_datastore(
                    DatastoreName=datastore_name,
                    DatastoreTypeVersion='R4',
                    PreloadDataConfig={
                        'PreloadDataType': 'SYNTHEA'  # Use synthetic data for testing
                    },
                    SseConfiguration={
                        'KmsEncryptionConfig': {
                            'CmkType': 'AWS_OWNED_KMS_KEY'
                        }
                    },
                    Tags=[
                        {'Key': 'Application', 'Value': 'HavenHealthPassport'},
                        {'Key': 'Environment', 'Value': self.environment},
                        {'Key': 'HIPAA', 'Value': 'true'}
                    ]
                )
                
                datastore_id = response['DatastoreId']
                config['HEALTHLAKE_DATASTORE_ID'] = datastore_id
                
                print(f"✅ Created HealthLake datastore: {datastore_id}")
                print("⏳ Datastore creation in progress. This may take 10-15 minutes.")
                
                # Wait for datastore to become active
                self._wait_for_healthlake_active(datastore_id)
                
        except Exception as e:
            logger.error(f"Failed to configure HealthLake: {e}")
            raise
        
        return config
    
    def configure_blockchain(self) -> Dict[str, str]:
        """Configure AWS Managed Blockchain."""
        config = {}
        
        network_name = f"{self.resource_prefix}-verification-network"
        
        try:
            # Note: AWS Managed Blockchain setup is complex and requires manual steps
            # This provides the configuration values needed
            
            print("⚠️  AWS Managed Blockchain requires manual setup through console")
            print("   Please create a Hyperledger Fabric network with:")
            print(f"   - Network name: {network_name}")
            print("   - Edition: Starter")
            print("   - Member name: HavenHealthMember")
            
            # For now, return placeholder values
            config['MANAGED_BLOCKCHAIN_NETWORK_ID'] = 'CONFIGURE_AFTER_MANUAL_SETUP'
            config['MANAGED_BLOCKCHAIN_MEMBER_ID'] = 'CONFIGURE_AFTER_MANUAL_SETUP'
            
        except Exception as e:
            logger.error(f"Failed to configure blockchain: {e}")
        
        return config
    
    def configure_sns(self) -> Dict[str, str]:
        """Configure SNS topics for notifications."""
        config = {}
        
        topics = [
            {
                'name': f"{self.resource_prefix}-critical-alerts",
                'display': 'Haven Health Critical Alerts',
                'purpose': 'Critical system and medical alerts'
            },
            {
                'name': f"{self.resource_prefix}-patient-notifications",
                'display': 'Haven Health Patient Notifications',
                'purpose': 'Patient SMS and email notifications'
            }
        ]
        
        for topic_config in topics:
            try:
                # Create or get topic
                response = self.sns.create_topic(
                    Name=topic_config['name'],
                    Attributes={
                        'DisplayName': topic_config['display'],
                        'KmsMasterKeyId': f"alias/{self.resource_prefix}-master"
                    },
                    Tags=[
                        {'Key': 'Application', 'Value': 'HavenHealthPassport'},
                        {'Key': 'Environment', 'Value': self.environment},
                        {'Key': 'Purpose', 'Value': topic_config['purpose']}
                    ]
                )
                
                topic_arn = response['TopicArn']
                config[f"SNS_TOPIC_{topic_config['name'].upper().replace('-', '_')}"] = topic_arn
                
                print(f"✅ Configured SNS topic: {topic_config['name']}")
                
            except Exception as e:
                logger.error(f"Failed to configure SNS topic {topic_config['name']}: {e}")
                raise
        
        return config
    
    def configure_cloudwatch(self) -> Dict[str, str]:
        """Configure CloudWatch monitoring and alarms."""
        config = {}
        
        # Create log groups
        log_groups = [
            f"/aws/lambda/{self.resource_prefix}",
            f"/aws/ecs/{self.resource_prefix}",
            f"/aws/healthlake/{self.resource_prefix}"
        ]
        
        logs_client = boto3.client('logs', region_name=self.region)
        
        for log_group in log_groups:
            try:
                logs_client.create_log_group(
                    logGroupName=log_group,
                    kmsKeyId=f"arn:aws:kms:{self.region}:{self.account_id}:alias/{self.resource_prefix}-master"
                )
                print(f"✅ Created log group: {log_group}")
            except logs_client.exceptions.ResourceAlreadyExistsException:
                print(f"✅ Log group already exists: {log_group}")
            except Exception as e:
                logger.error(f"Failed to create log group {log_group}: {e}")
        
        # Create critical alarms
        alarms = [
            {
                'name': f"{self.resource_prefix}-high-error-rate",
                'metric': 'Errors',
                'threshold': 10,
                'description': 'High error rate detected'
            },
            {
                'name': f"{self.resource_prefix}-api-latency",
                'metric': 'Duration',
                'threshold': 5000,
                'description': 'API latency exceeds 5 seconds'
            }
        ]
        
        # Get SNS topic for alerts
        sns_topic = f"arn:aws:sns:{self.region}:{self.account_id}:{self.resource_prefix}-critical-alerts"
        
        for alarm_config in alarms:
            try:
                self.cloudwatch.put_metric_alarm(
                    AlarmName=alarm_config['name'],
                    ComparisonOperator='GreaterThanThreshold',
                    EvaluationPeriods=2,
                    MetricName=alarm_config['metric'],
                    Namespace='HavenHealthPassport',
                    Period=300,
                    Statistic='Sum',
                    Threshold=alarm_config['threshold'],
                    ActionsEnabled=True,
                    AlarmActions=[sns_topic],
                    AlarmDescription=alarm_config['description']
                )
                
                print(f"✅ Created CloudWatch alarm: {alarm_config['name']}")
                
            except Exception as e:
                logger.error(f"Failed to create alarm {alarm_config['name']}: {e}")
        
        config['CLOUDWATCH_CONFIGURED'] = 'true'
        return config
    
    def _wait_for_healthlake_active(self, datastore_id: str, max_wait: int = 900):
        """Wait for HealthLake datastore to become active."""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                response = self.healthlake.describe_fhir_datastore(
                    DatastoreId=datastore_id
                )
                
                status = response['DatastoreProperties']['DatastoreStatus']
                
                if status == 'ACTIVE':
                    print(f"✅ HealthLake datastore is now active!")
                    return
                elif status in ['CREATE_FAILED', 'DELETED']:
                    raise RuntimeError(f"HealthLake datastore creation failed: {status}")
                else:
                    print(f"   Status: {status} - waiting...")
                    time.sleep(30)
                    
            except Exception as e:
                logger.error(f"Error checking datastore status: {e}")
                time.sleep(30)
        
        raise TimeoutError("HealthLake datastore creation timed out")
    
    def _get_kms_key_policy(self, key_type: str) -> Dict:
        """Get KMS key policy for specific key type."""
        # Base policy allowing root account and key administrators
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "Enable IAM User Permissions",
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": f"arn:aws:iam::{self.account_id}:root"
                    },
                    "Action": "kms:*",
                    "Resource": "*"
                },
                {
                    "Sid": "Allow use of the key for encryption",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": [
                            "s3.amazonaws.com",
                            "healthlake.amazonaws.com",
                            "logs.amazonaws.com"
                        ]
                    },
                    "Action": [
                        "kms:Decrypt",
                        "kms:GenerateDataKey"
                    ],
                    "Resource": "*"
                }
            ]
        }
        
        # Add specific permissions based on key type
        if key_type == 'phi':
            # More restrictive for PHI data
            policy['Statement'].append({
                "Sid": "Restrict PHI key usage",
                "Effect": "Deny",
                "Principal": {"AWS": "*"},
                "Action": "kms:*",
                "Resource": "*",
                "Condition": {
                    "StringNotEquals": {
                        "kms:ViaService": [
                            f"s3.{self.region}.amazonaws.com",
                            f"healthlake.{self.region}.amazonaws.com"
                        ]
                    }
                }
            })
        
        return policy
    
    def save_configuration(self, config: Dict[str, str]):
        """Save configuration to file."""
        filename = f"aws-config-{self.environment}-{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        
        with open(filename, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"\n✅ Configuration saved to: {filename}")
        
        # Also generate environment variable exports
        env_filename = f".env.aws.{self.environment}"
        with open(env_filename, 'w') as f:
            f.write(f"# AWS Configuration for {self.environment}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
            
            for key, value in config.items():
                f.write(f"export {key}={value}\n")
        
        print(f"✅ Environment variables saved to: {env_filename}")
        
        # Print summary
        print("\n" + "="*60)
        print("🎉 AWS Configuration Complete!")
        print("\nNext steps:")
        print("1. Review the generated configuration files")
        print("2. Complete manual Blockchain setup if needed")
        print("3. Update .env files with the configuration values")
        print("4. Run scripts/validate_production.py to verify")
        print("="*60)


def main():
    """Main function to configure AWS services."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Configure AWS services for Haven Health Passport'
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
    
    args = parser.parse_args()
    
    # Confirm production deployment
    if args.environment == 'production':
        print("\n⚠️  WARNING: Configuring PRODUCTION AWS services!")
        print("This will create billable resources.")
        response = input("Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return
    
    try:
        configurator = AWSServiceConfigurator(
            region=args.region,
            environment=args.environment
        )
        
        config = configurator.configure_all_services()
        
        print(f"\n✅ Successfully configured {len(config)} AWS services")
        
    except Exception as e:
        logger.error(f"Configuration failed: {e}")
        print(f"\n❌ Configuration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
