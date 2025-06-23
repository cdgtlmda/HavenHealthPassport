#!/usr/bin/env python3
"""Check and configure Bedrock service quotas."""

import os
from pathlib import Path

import boto3

# Load AWS credentials
env_path = Path(__file__).parent.parent.parent / ".env.aws"
if env_path.exists():
    with open(env_path, "r") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                key, value = line.strip().split("=", 1)
                os.environ[key] = value

# Default and recommended quotas
QUOTAS = {
    "default": {
        "Requests per minute": 60,
        "Tokens per minute": 60000,
        "Concurrent requests": 10,
    },
    "development": {
        "Requests per minute": 60,
        "Tokens per minute": 100000,
        "Concurrent requests": 10,
    },
    "production": {
        "Requests per minute": 300,
        "Tokens per minute": 2000000,
        "Concurrent requests": 50,
    },
}


def main():
    """Check service quotas."""
    print("=" * 60)
    print("Bedrock Service Quota Configuration")
    print("=" * 60)

    environment = os.getenv("ENVIRONMENT", "development")

    print(f"\nEnvironment: {environment}")
    print("\nCurrent quotas (defaults):")
    for metric, value in QUOTAS["default"].items():
        print(f"  • {metric}: {value:,}")

    print(f"\nRecommended quotas for {environment}:")
    for metric, value in QUOTAS[environment].items():
        print(f"  • {metric}: {value:,}")

    print("\n" + "=" * 60)
    print("How to Request Quota Increases")
    print("=" * 60)
    print(
        """
1. Sign in to AWS Console
2. Navigate to Service Quotas
3. Search for "Bedrock"
4. Select the quota to increase
5. Click "Request quota increase"
6. Enter the new value and submit

Note: Some Bedrock quotas may need to be requested via AWS Support.

For immediate needs, consider:
- Implementing request queuing
- Using multiple regions for higher throughput
- Optimizing prompt sizes to reduce token usage
"""
    )


if __name__ == "__main__":
    main()
