#!/usr/bin/env python3
"""Check Python version compatibility for LlamaIndex installation."""

import sys


def check_python_version() -> bool:
    """Check if Python version is compatible."""
    current_version = sys.version_info
    min_version = (3, 11)

    print(f"Current Python version: {sys.version}")

    if current_version < min_version:
        print(f"❌ ERROR: Python {min_version[0]}.{min_version[1]}+ is required")
        print(
            f"   You have: Python {current_version.major}.{current_version.minor}.{current_version.micro}"
        )
        return False

    if current_version >= (3, 13):
        print(
            f"⚠️  WARNING: Python {current_version.major}.{current_version.minor} is very new"
        )
        print("   Using flexible requirements for better compatibility")
        print("   Recommended: Use requirements-flexible.txt")
        return True

    print(
        f"✅ Python version {current_version.major}.{current_version.minor} is compatible"
    )
    return True


def get_recommended_requirements() -> str:
    """Get recommended requirements file based on Python version."""
    current_version = sys.version_info

    if current_version >= (3, 13):
        return "requirements-flexible.txt"
    else:
        return "requirements.txt"


def main() -> None:
    """Run main function."""
    print("=" * 60)
    print("LlamaIndex Python Compatibility Check")
    print("=" * 60)

    if check_python_version():
        req_file = get_recommended_requirements()
        print("\n📋 Recommended installation:")
        print(f"   pip install -r {req_file}")

        print("\n💡 Alternative: Install core packages only:")
        print("   pip install llama-index llama-index-core")

        # Try to detect if we're in a virtual environment
        if hasattr(sys, "real_prefix") or (
            hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
        ):
            print("\n✅ Virtual environment detected")
        else:
            print("\n⚠️  No virtual environment detected")
            print("   Consider creating one: python3 -m venv venv")
    else:
        print("\n❌ Please upgrade Python before proceeding")
        sys.exit(1)

    print("=" * 60)


if __name__ == "__main__":
    main()
