#!/usr/bin/env python3
"""Verify AWS credentials are properly configured."""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import boto3
from botocore.exceptions import ClientError

from src.config import get_settings


def verify_aws_credentials():
    """Verify AWS credentials from configuration."""
    settings = get_settings()
    
    print("Checking AWS configuration...")
    print(f"Region: {settings.aws_region}")
    print(f"Access Key ID: {settings.aws_access_key_id[:10]}..." if settings.aws_access_key_id else "Access Key ID: Not set")
    
    # Create STS client with explicit credentials
    try:
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            sts = boto3.client(
                'sts',
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key
            )
        else:
            print("AWS credentials not found in configuration")
            return False
            
        # Verify credentials
        response = sts.get_caller_identity()
        print("\n✅ AWS credentials are valid!")
        print(f"Account: {response['Account']}")
        print(f"User ARN: {response['Arn']}")
        print(f"User ID: {response['UserId']}")
        return True
        
    except ClientError as e:
        print(f"\n❌ AWS credentials error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    verify_aws_credentials()