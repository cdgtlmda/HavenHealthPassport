#!/usr/bin/env python3
"""Bootstrap AWS CDK in the target region."""

import os
import subprocess
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import get_settings


def bootstrap_cdk():
    """Bootstrap CDK with proper AWS credentials."""
    settings = get_settings()

    print("🚀 Bootstrapping AWS CDK...")
    print(f"📍 Region: {settings.aws_region}")
    print(
        f"🔑 Account: {settings.aws_access_key_id[:10]}..."
        if settings.aws_access_key_id
        else "❌ No AWS credentials found"
    )

    if not settings.aws_access_key_id or not settings.aws_secret_access_key:
        print("\n❌ AWS credentials not found in configuration")
        print("Please ensure .env.aws file contains:")
        print("  - AWS_ACCESS_KEY_ID")
        print("  - AWS_SECRET_ACCESS_KEY")
        print("  - AWS_REGION")
        return False

    # Set environment variables for CDK
    env = os.environ.copy()
    env["AWS_ACCESS_KEY_ID"] = settings.aws_access_key_id
    env["AWS_SECRET_ACCESS_KEY"] = settings.aws_secret_access_key
    env["AWS_REGION"] = settings.aws_region

    # Check if CDK is installed
    try:
        result = subprocess.run(["cdk", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            print("\n❌ AWS CDK is not installed")
            print("Please install it with: npm install -g aws-cdk")
            return False
        print(f"✅ CDK Version: {result.stdout.strip()}")
    except FileNotFoundError:
        print("\n❌ AWS CDK is not installed")
        print("Please install it with: npm install -g aws-cdk")
        return False

    # Get AWS account ID
    import boto3

    try:
        sts = boto3.client(
            "sts",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        identity = sts.get_caller_identity()
        account_id = identity["Account"]
        print(f"✅ AWS Account: {account_id}")
    except Exception as e:
        print(f"\n❌ Failed to get AWS account ID: {e}")
        return False

    # Bootstrap CDK
    print(f"\n🔧 Bootstrapping CDK in {settings.aws_region}...")
    try:
        cmd = [
            "cdk",
            "bootstrap",
            f"aws://{account_id}/{settings.aws_region}",
            "--cloudformation-execution-policies",
            "arn:aws:iam::aws:policy/AdministratorAccess",
        ]

        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if result.returncode == 0:
            print("\n✅ CDK bootstrap completed successfully!")
            print(result.stdout)
            return True
        else:
            print(f"\n❌ CDK bootstrap failed:")
            print(result.stderr)
            return False

    except Exception as e:
        print(f"\n❌ Failed to bootstrap CDK: {e}")
        return False


if __name__ == "__main__":
    success = bootstrap_cdk()
    sys.exit(0 if success else 1)
