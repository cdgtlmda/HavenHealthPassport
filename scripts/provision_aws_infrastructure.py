#!/usr/bin/env python3
"""
AWS Infrastructure Provisioning for Haven Health Passport
Provisions all required AWS resources for production deployment
CRITICAL: This creates infrastructure for real patient data
"""

import os
import sys
import json
import boto3
import argparse
import logging
from datetime import datetime
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AWSInfrastructureProvisioner:
    """Provisions AWS infrastructure for Haven Health Passport"""
    
    def __init__(self, environment: str, region: str = 'us-east-1'):
        self.environment = environment
        self.region = region
        self.account_id = boto3.client('sts').get_caller_identity()['Account']
        
        # Initialize AWS clients
        self.cloudhsm_client = boto3.client('cloudhsmv2', region_name=region)
        self.s3_client = boto3.client('s3', region_name=region)
        self.sns_client = boto3.client('sns', region_name=region)
        self.ses_client = boto3.client('ses', region_name=region)
        self.healthlake_client = boto3.client('healthlake', region_name=region)
        self.sagemaker_client = boto3.client('sagemaker', region_name=region)
        self.waf_client = boto3.client('wafv2', region_name=region)
        self.ec2_client = boto3.client('ec2', region_name=region)
    
    def provision_cloudhsm_cluster(self) -> bool:
        """Provision CloudHSM cluster for hardware security"""
        print("\n" + "="*60)
        print("Provisioning CloudHSM Cluster")
        print("="*60)
        
        try:
            # Get default VPC and subnets
            vpcs = self.ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
            if not vpcs['Vpcs']:
                logger.error("No default VPC found. Please create a VPC first.")
                return False
            
            vpc_id = vpcs['Vpcs'][0]['VpcId']
            
            # Get subnets in different AZs
            subnets = self.ec2_client.describe_subnets(
                Filters=[
                    {'Name': 'vpc-id', 'Values': [vpc_id]},
                    {'Name': 'state', 'Values': ['available']}
                ]
            )
            
            if len(subnets['Subnets']) < 2:
                logger.error("Need at least 2 subnets in different AZs")
                return False
            
            subnet_ids = [subnet['SubnetId'] for subnet in subnets['Subnets'][:2]]
            
            # Create CloudHSM cluster
            cluster_id = None
            try:
                response = self.cloudhsm_client.create_cluster(
                    SubnetIds=subnet_ids,
                    HsmType='hsm1.medium',
                    TagList=[
                        {'Key': 'Name', 'Value': f'haven-health-{self.environment}'},
                        {'Key': 'Environment', 'Value': self.environment},
                        {'Key': 'Service', 'Value': 'haven-health-passport'},
                        {'Key': 'Compliance', 'Value': 'HIPAA'}
                    ]
                )
                cluster_id = response['Cluster']['ClusterId']
                logger.info(f"Created CloudHSM cluster: {cluster_id}")
                
                # Wait for cluster to be initialized
                print("Waiting for CloudHSM cluster initialization...")
                waiter = self.cloudhsm_client.get_waiter('cluster_initialized')
                waiter.wait(
                    ClusterIds=[cluster_id],
                    WaiterConfig={'Delay': 30, 'MaxAttempts': 40}
                )
                
                print(f"✅ CloudHSM cluster provisioned: {cluster_id}")
                return True
                
            except Exception as e:
                if 'ClusterAlreadyExistsFault' in str(e):
                    print("✅ CloudHSM cluster already exists")
                    return True
                else:
                    logger.error(f"Failed to provision CloudHSM: {str(e)}")
                    return False
                    
        except Exception as e:
            logger.error(f"CloudHSM provisioning error: {str(e)}")
            return False
    
    def provision_s3_buckets(self) -> bool:
        """Provision S3 buckets for different data types"""
        print("\n" + "="*60)
        print("Provisioning S3 Buckets")
        print("="*60)
        
        buckets = [
            {'name': f'haven-health-{self.environment}-medical-records', 'purpose': 'Medical records storage'},
            {'name': f'haven-health-{self.environment}-voice-recordings', 'purpose': 'Voice recording storage'},
            {'name': f'haven-health-{self.environment}-documents', 'purpose': 'Document storage'},
            {'name': f'haven-health-{self.environment}-backups', 'purpose': 'Encrypted backups'},
            {'name': f'haven-health-{self.environment}-audit-logs', 'purpose': 'Audit log storage'},
            {'name': f'haven-health-{self.environment}-ml-models', 'purpose': 'ML model artifacts'}
        ]
        
        success_count = 0
        
        for bucket_config in buckets:
            try:
                bucket_name = bucket_config['name']
                
                # Create bucket
                if self.region == 'us-east-1':
                    self.s3_client.create_bucket(Bucket=bucket_name)
                else:
                    self.s3_client.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={'LocationConstraint': self.region}
                    )
                
                # Enable versioning
                self.s3_client.put_bucket_versioning(
                    Bucket=bucket_name,
                    VersioningConfiguration={'Status': 'Enabled'}
                )
                
                # Enable encryption
                self.s3_client.put_bucket_encryption(
                    Bucket=bucket_name,
                    ServerSideEncryptionConfiguration={
                        'Rules': [{
                            'ApplyServerSideEncryptionByDefault': {
                                'SSEAlgorithm': 'aws:kms',
                                'KMSMasterKeyID': 'alias/aws/s3'
                            }
                        }]
                    }
                )
                
                # Add bucket policy for HIPAA compliance
                bucket_policy = {
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Sid": "DenyInsecureConnections",
                        "Effect": "Deny",
                        "Principal": "*",
                        "Action": "s3:*",
                        "Resource": [
                            f"arn:aws:s3:::{bucket_name}/*",
                            f"arn:aws:s3:::{bucket_name}"
                        ],
                        "Condition": {
                            "Bool": {"aws:SecureTransport": "false"}
                        }
                    }]
                }
                
                self.s3_client.put_bucket_policy(
                    Bucket=bucket_name,
                    Policy=json.dumps(bucket_policy)
                )
                
                # Add tags
                self.s3_client.put_bucket_tagging(
                    Bucket=bucket_name,
                    Tagging={
                        'TagSet': [
                            {'Key': 'Environment', 'Value': self.environment},
                            {'Key': 'Service', 'Value': 'haven-health-passport'},
                            {'Key': 'Purpose', 'Value': bucket_config['purpose']},
                            {'Key': 'Compliance', 'Value': 'HIPAA'}
                        ]
                    }
                )
                
                logger.info(f"Created S3 bucket: {bucket_name}")
                success_count += 1
                
            except self.s3_client.exceptions.BucketAlreadyExists:
                logger.info(f"S3 bucket already exists: {bucket_name}")
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to create bucket {bucket_name}: {str(e)}")
        
        print(f"✅ Provisioned {success_count}/{len(buckets)} S3 buckets")
        return success_count == len(buckets)
    
    def provision_sns_topics(self) -> bool:
        """Provision SNS topics for notifications"""
        print("\n" + "="*60)
        print("Provisioning SNS Topics")
        print("="*60)
        
        topics = [
            {'name': f'haven-health-{self.environment}-critical-alerts', 'display': 'Critical Alerts'},
            {'name': f'haven-health-{self.environment}-physician-pager', 'display': 'Physician Pager'},
            {'name': f'haven-health-{self.environment}-patient-notifications', 'display': 'Patient Notifications'},
            {'name': f'haven-health-{self.environment}-system-events', 'display': 'System Events'},
            {'name': f'haven-health-{self.environment}-compliance-alerts', 'display': 'Compliance Alerts'}
        ]
        
        topic_arns = {}
        success_count = 0
        
        for topic_config in topics:
            try:
                response = self.sns_client.create_topic(
                    Name=topic_config['name'],
                    Tags=[
                        {'Key': 'Environment', 'Value': self.environment},
                        {'Key': 'Service', 'Value': 'haven-health-passport'},
                        {'Key': 'Purpose', 'Value': topic_config['display']}
                    ]
                )
                
                topic_arn = response['TopicArn']
                topic_arns[topic_config['name']] = topic_arn
                
                # Set display name
                self.sns_client.set_topic_attributes(
                    TopicArn=topic_arn,
                    AttributeName='DisplayName',
                    AttributeValue=topic_config['display']
                )
                
                logger.info(f"Created SNS topic: {topic_config['name']}")
                success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to create SNS topic {topic_config['name']}: {str(e)}")
        
        # Store topic ARNs in parameter store
        ssm_client = boto3.client('ssm', region_name=self.region)
        for name, arn in topic_arns.items():
            param_name = f"/haven-health/{self.environment}/sns/{name.split('-')[-1]}"
            try:
                ssm_client.put_parameter(
                    Name=param_name,
                    Value=arn,
                    Type='String',
                    Overwrite=True
                )
            except Exception as e:
                logger.error(f"Failed to store SNS ARN in parameter store: {str(e)}")
        
        print(f"✅ Provisioned {success_count}/{len(topics)} SNS topics")
        return success_count == len(topics)
    
    def provision_healthlake_datastore(self) -> bool:
        """Provision AWS HealthLake FHIR datastore"""
        print("\n" + "="*60)
        print("Provisioning AWS HealthLake FHIR Datastore")
        print("="*60)
        
        try:
            datastore_name = f"haven-health-{self.environment}"
            
            # Create HealthLake datastore
            response = self.healthlake_client.create_fhir_datastore(
                DatastoreName=datastore_name,
                DatastoreTypeVersion='R4',
                PreloadDataConfig={
                    'PreloadDataType': 'SYNTHEA'
                },
                Tags=[
                    {'Key': 'Environment', 'Value': self.environment},
                    {'Key': 'Service', 'Value': 'haven-health-passport'},
                    {'Key': 'Compliance', 'Value': 'HIPAA'}
                ]
            )
            
            datastore_id = response['DatastoreId']
            logger.info(f"Created HealthLake datastore: {datastore_id}")
            
            # Store datastore ID
            ssm_client = boto3.client('ssm', region_name=self.region)
            ssm_client.put_parameter(
                Name=f"/haven-health/{self.environment}/healthlake/datastore-id",
                Value=datastore_id,
                Type='String',
                Overwrite=True
            )
            
            print(f"✅ HealthLake FHIR datastore provisioned: {datastore_id}")
            print("Note: Datastore creation may take 10-15 minutes to complete")
            return True
            
        except Exception as e:
            if 'ConflictException' in str(e):
                print("✅ HealthLake datastore already exists")
                return True
            else:
                logger.error(f"Failed to provision HealthLake: {str(e)}")
                return False
    
    def provision_ses_domain(self) -> bool:
        """Configure SES for email delivery"""
        print("\n" + "="*60)
        print("Configuring Amazon SES")
        print("="*60)
        
        domain = input("Enter your email domain (e.g., example.com): ").strip()
        if not domain:
            print("❌ Domain is required for SES configuration")
            return False
        
        try:
            # Verify domain
            response = self.ses_client.verify_domain_identity(Domain=domain)
            verification_token = response['VerificationToken']
            
            print(f"\n📧 Domain verification required for: {domain}")
            print(f"Add this TXT record to your DNS:")
            print(f"Name: _amazonses.{domain}")
            print(f"Value: {verification_token}")
            print(f"Type: TXT")
            
            # Set up DKIM
            dkim_response = self.ses_client.verify_domain_dkim(Domain=domain)
            print(f"\n🔐 DKIM records for enhanced security:")
            for i, token in enumerate(dkim_response['DkimTokens'], 1):
                print(f"CNAME Record {i}:")
                print(f"Name: {token}._domainkey.{domain}")
                print(f"Value: {token}.dkim.amazonses.com")
            
            # Store domain configuration
            ssm_client = boto3.client('ssm', region_name=self.region)
            ssm_client.put_parameter(
                Name=f"/haven-health/{self.environment}/ses/domain",
                Value=domain,
                Type='String',
                Overwrite=True
            )
            
            print(f"\n✅ SES domain configuration initiated for: {domain}")
            print("Note: DNS propagation may take up to 72 hours")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure SES: {str(e)}")
            return False
    
    def provision_waf_rules(self) -> bool:
        """Configure WAF rules for API protection"""
        print("\n" + "="*60)
        print("Configuring WAF Rules")
        print("="*60)
        
        try:
            # Create IP set for rate limiting
            ip_set_name = f"haven-health-{self.environment}-rate-limit"
            
            response = self.waf_client.create_ip_set(
                Name=ip_set_name,
                Scope='REGIONAL',
                IPAddressVersion='IPV4',
                Addresses=[],
                Tags=[
                    {'Key': 'Environment', 'Value': self.environment},
                    {'Key': 'Service', 'Value': 'haven-health-passport'}
                ]
            )
            
            # Create Web ACL
            web_acl_name = f"haven-health-{self.environment}-acl"
            
            web_acl_response = self.waf_client.create_web_acl(
                Name=web_acl_name,
                Scope='REGIONAL',
                DefaultAction={'Allow': {}},
                Rules=[
                    {
                        'Name': 'RateLimitRule',
                        'Priority': 1,
                        'Statement': {
                            'RateBasedStatement': {
                                'Limit': 2000,
                                'AggregateKeyType': 'IP'
                            }
                        },
                        'Action': {'Block': {}},
                        'VisibilityConfig': {
                            'SampledRequestsEnabled': True,
                            'CloudWatchMetricsEnabled': True,
                            'MetricName': 'RateLimitRule'
                        }
                    }
                ],
                'VisibilityConfig': {
                    'SampledRequestsEnabled': True,
                    'CloudWatchMetricsEnabled': True,
                    'MetricName': web_acl_name
                },
                Tags=[
                    {'Key': 'Environment', 'Value': self.environment},
                    {'Key': 'Service', 'Value': 'haven-health-passport'}
                ]
            )
            
            logger.info(f"Created WAF Web ACL: {web_acl_name}")
            print("✅ WAF rules configured for API protection")
            return True
            
        except Exception as e:
            if 'WAFDuplicateItemException' in str(e):
                print("✅ WAF rules already exist")
                return True
            else:
                logger.error(f"Failed to configure WAF: {str(e)}")
                return False
    
    def provision_all(self) -> None:
        """Provision all AWS infrastructure"""
        print("\n" + "="*80)
        print("Haven Health Passport - AWS Infrastructure Provisioning")
        print(f"Environment: {self.environment.upper()}")
        print(f"Region: {self.region}")
        print(f"Account: {self.account_id}")
        print("="*80)
        print("\n⚠️  CRITICAL: This provisions infrastructure for real patient data.")
        print("Ensure you have appropriate AWS permissions and budget approval.\n")
        
        results = {
            'CloudHSM Cluster': self.provision_cloudhsm_cluster(),
            'S3 Buckets': self.provision_s3_buckets(),
            'SNS Topics': self.provision_sns_topics(),
            'HealthLake FHIR Datastore': self.provision_healthlake_datastore(),
            'SES Domain': self.provision_ses_domain(),
            'WAF Rules': self.provision_waf_rules()
        }
        
        # Summary
        print("\n" + "="*80)
        print("Provisioning Summary")
        print("="*80)
        
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        for component, success in results.items():
            status = "✅ Success" if success else "❌ Failed"
            print(f"{component}: {status}")
        
        print(f"\nTotal: {success_count}/{total_count} components provisioned successfully")
        
        if success_count == total_count:
            print("\n✅ All infrastructure provisioned successfully!")
            print("\nNext steps:")
            print("1. Deploy ML models using deploy_ml_models.py")
            print("2. Configure blockchain infrastructure")
            print("3. Set up monitoring and alerting")
            print("4. Run integration tests")
        else:
            print("\n⚠️  WARNING: Some components failed to provision.")
            print("Please review the errors and retry failed components.")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Provision AWS infrastructure for Haven Health Passport'
    )
    parser.add_argument(
        '--environment',
        choices=['development', 'staging', 'production'],
        required=True,
        help='Target environment for provisioning'
    )
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region for deployment (default: us-east-1)'
    )
    
    args = parser.parse_args()
    
    # Production safety check
    if args.environment == 'production':
        print("\n⚠️  WARNING: Provisioning PRODUCTION infrastructure!")
        print("This will incur AWS costs and handle real patient data.")
        confirm = input("Type 'PROVISION PRODUCTION' to continue: ")
        if confirm != 'PROVISION PRODUCTION':
            print("Provisioning cancelled.")
            sys.exit(0)
    
    # Check AWS credentials
    try:
        account_info = boto3.client('sts').get_caller_identity()
        print(f"\n✅ AWS Account: {account_info['Account']}")
    except Exception as e:
        print(f"\n❌ AWS credentials not configured: {str(e)}")
        print("Please configure AWS credentials before running this script.")
        sys.exit(1)
    
    # Run provisioning
    provisioner = AWSInfrastructureProvisioner(args.environment, args.region)
    provisioner.provision_all()


if __name__ == '__main__':
    main()
