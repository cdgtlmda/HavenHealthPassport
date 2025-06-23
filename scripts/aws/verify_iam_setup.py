#!/usr/bin/env python3
"""Verify IAM roles for Bedrock are properly configured."""

import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Load AWS credentials
env_path = Path(__file__).parent.parent.parent / ".env.aws"
if env_path.exists():
    with open(env_path, "r") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                key, value = line.strip().split("=", 1)
                os.environ[key] = value


def check_iam_setup():
    """Check IAM setup for Bedrock access."""
    print("=" * 60)
    print("IAM Setup Verification for Bedrock")
    print("=" * 60)

    iam = boto3.client("iam")

    # Expected role name pattern
    environment = os.getenv("ENVIRONMENT", "development")
    expected_role = f"haven-health-passport-bedrock-role-{environment}"

    print(f"\nChecking for IAM role: {expected_role}")

    try:
        # Check if role exists
        response = iam.get_role(RoleName=expected_role)
        role = response["Role"]

        print(f"✅ Role found: {role['Arn']}")
        print(f"   Created: {role['CreateDate']}")

        # Check attached policies
        policies = iam.list_attached_role_policies(RoleName=expected_role)
        print(f"\nAttached policies:")
        for policy in policies["AttachedPolicies"]:
            print(f"   ✅ {policy['PolicyName']}")

        # Check trust relationship
        trust_policy = role["AssumeRolePolicyDocument"]
        print(f"\nTrust relationship allows:")
        for statement in trust_policy["Statement"]:
            if "Service" in statement["Principal"]:
                for service in statement["Principal"]["Service"]:
                    print(f"   ✅ {service}")

        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            print(f"❌ Role not found: {expected_role}")
            print("\nTo create the role, run:")
            print("   cd infrastructure/terraform")
            print("   terraform apply -var-file=environments/development.tfvars")
        else:
            print(f"❌ Error checking role: {e}")

        return False


def check_bedrock_permissions():
    """Verify Bedrock permissions are working."""
    print("\n" + "=" * 60)
    print("Bedrock Permission Test")
    print("=" * 60)

    bedrock = boto3.client("bedrock")

    try:
        # Try to list models as a permission test
        response = bedrock.list_foundation_models()
        print("✅ Successfully called Bedrock API")
        print(f"   Found {len(response.get('modelSummaries', []))} models")
        return True

    except ClientError as e:
        print(f"❌ Failed to call Bedrock API: {e}")
        return False


def main():
    """Main verification function."""
    iam_ok = check_iam_setup()
    bedrock_ok = check_bedrock_permissions()

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    if iam_ok and bedrock_ok:
        print("✅ IAM roles are properly configured for Bedrock access")
    else:
        print("❌ IAM setup needs attention")
        print("\nNext steps:")
        if not iam_ok:
            print("1. Deploy Terraform infrastructure to create IAM roles")
        if not bedrock_ok:
            print("2. Ensure your AWS credentials have Bedrock permissions")


if __name__ == "__main__":
    main()
