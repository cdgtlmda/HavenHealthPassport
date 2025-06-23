#!/usr/bin/env python3
"""Create IAM role for SageMaker with proper permissions."""

import json
import os
import boto3
from botocore.exceptions import ClientError

def create_sagemaker_role():
    """Create IAM role for SageMaker execution."""
    iam = boto3.client('iam')
    environment = os.getenv('ENVIRONMENT', 'development')
    role_name = f'haven-health-sagemaker-role-{environment}'
    
    # Trust policy for SageMaker
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": [
                        "sagemaker.amazonaws.com"
                    ]
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    try:
        # Create role
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description='SageMaker execution role for Haven Health Passport cultural adaptation models',
            Tags=[
                {'Key': 'Project', 'Value': 'HavenHealthPassport'},
                {'Key': 'Environment', 'Value': environment},
                {'Key': 'Service', 'Value': 'SageMaker'},
                {'Key': 'Purpose', 'Value': 'CulturalAdaptation'}
            ]
        )
        
        print(f"✅ Created role: {role_name}")
        role_arn = response['Role']['Arn']
        
        # Attach necessary policies
        policies = [
            'arn:aws:iam::aws:policy/AmazonSageMakerFullAccess',
            'arn:aws:iam::aws:policy/AmazonS3FullAccess',  # For model artifacts
            'arn:aws:iam::aws:policy/CloudWatchLogsFullAccess'  # For logging
        ]
        
        for policy_arn in policies:
            iam.attach_role_policy(
                RoleName=role_name,
                PolicyArn=policy_arn
            )
            print(f"✅ Attached policy: {policy_arn.split('/')[-1]}")
        
        # Create custom policy for KMS access
        kms_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "kms:Decrypt",
                        "kms:GenerateDataKey"
                    ],
                    "Resource": "*",
                    "Condition": {
                        "StringEquals": {
                            "kms:ViaService": [
                                f"s3.{boto3.Session().region_name}.amazonaws.com"
                            ]
                        }
                    }
                }
            ]
        }
        
        policy_name = f'haven-health-sagemaker-kms-policy-{environment}'
        try:
            iam.create_policy(
                PolicyName=policy_name,
                PolicyDocument=json.dumps(kms_policy),
                Description='KMS access for SageMaker encrypted data'
            )
            
            # Get account ID
            sts = boto3.client('sts')
            account_id = sts.get_caller_identity()['Account']
            
            # Attach custom policy
            iam.attach_role_policy(
                RoleName=role_name,
                PolicyArn=f'arn:aws:iam::{account_id}:policy/{policy_name}'
            )
            print(f"✅ Created and attached KMS policy")
        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExists':
                print(f"ℹ️  KMS policy already exists")
            else:
                raise
        
        print(f"\n✅ SageMaker role created successfully!")
        print(f"Role ARN: {role_arn}")
        print(f"\nAdd this to your .env file:")
        print(f"SAGEMAKER_EXECUTION_ROLE_ARN={role_arn}")
        
        return role_arn
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            # Get existing role
            response = iam.get_role(RoleName=role_name)
            role_arn = response['Role']['Arn']
            print(f"ℹ️  Role already exists: {role_name}")
            print(f"Role ARN: {role_arn}")
            return role_arn
        else:
            print(f"❌ Error creating role: {e}")
            raise


if __name__ == "__main__":
    create_sagemaker_role()