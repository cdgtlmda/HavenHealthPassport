#!/usr/bin/env python3
"""Verification script for LangChain Core Library installation."""

import importlib.util
import sys


def check_package(package_name: str) -> bool:
    """Check if a package is installed."""
    spec = importlib.util.find_spec(package_name)
    return spec is not None


def main() -> int:
    """Execute main function."""
    print("Verifying LangChain Core Library Installation...")
    print("=" * 50)

    # Check core dependencies
    required_packages = [
        ("langchain", "LangChain Core"),
        ("langchain_core", "LangChain Core Components"),
        ("langchain_text_splitters", "Text Splitters"),
        ("pydantic", "Pydantic"),
        ("tenacity", "Tenacity"),
        ("aiohttp", "Async HTTP"),
        ("requests", "Requests"),
        ("numpy", "NumPy"),
        ("sqlalchemy", "SQLAlchemy"),
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
        print("✅ All required packages are installed!")
        return 0
    else:
        print("❌ Some packages are missing. Run: pip install -r requirements.txt")
        return 1


if __name__ == "__main__":
    sys.exit(main())
