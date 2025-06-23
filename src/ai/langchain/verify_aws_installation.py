#!/usr/bin/env python3
"""Verification script for AWS LangChain integration."""

import importlib.util
import sys


def check_package(package_name: str) -> bool:
    """Check if a package is installed."""
    spec = importlib.util.find_spec(package_name)
    return spec is not None


def main() -> int:
    """Execute main function."""
    print("Verifying AWS LangChain Integration...")
    print("=" * 50)

    # Check AWS-specific dependencies
    required_packages = [
        ("boto3", "AWS SDK"),
        ("botocore", "AWS Core"),
        ("langchain_aws", "LangChain AWS"),
        ("langchain_community", "LangChain Community"),
    ]

    all_installed = True

    for package, description in required_packages:
        if check_package(package):
            print(f"✅ {description}: {package}")
        else:
            print(f"❌ {description}: {package} - NOT INSTALLED")
            all_installed = False

    print("=" * 50)

    if all_installed:
        print("✅ All AWS integration packages are installed!")
        return 0
    else:
        print("❌ Some packages are missing. Run: pip install boto3 langchain-aws")
        return 1


if __name__ == "__main__":
    sys.exit(main())
