#!/usr/bin/env python3
"""
Install Vector Store Integrations for LlamaIndex.

This script installs the required dependencies for vector store integrations
in the Haven Health Passport project.
"""

import subprocess
import sys
from pathlib import Path


def install_vector_stores() -> bool:
    """Install vector store dependencies."""
    # Get the directory of this script
    script_dir = Path(__file__).parent
    requirements_file = script_dir / "requirements-vector-stores.txt"

    if not requirements_file.exists():
        print(f"Error: {requirements_file} not found!")
        return False

    print("Installing LlamaIndex vector store integrations...")
    print(f"Using requirements file: {requirements_file}")

    try:
        # Install the dependencies
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
        )

        print("\n✅ Vector store integrations installed successfully!")
        return True

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error installing vector stores: {e}")
        return False


def verify_installation() -> bool:
    """Verify that vector stores can be imported."""
    print("\nVerifying vector store installations...")

    stores_to_check = [
        ("opensearch-py", "opensearchpy"),
        (
            "llama-index-vector-stores-opensearch",
            "llama_index.vector_stores.opensearch",
        ),
        ("chromadb", "chromadb"),
        ("llama-index-vector-stores-chroma", "llama_index.vector_stores.chroma"),
    ]

    all_good = True
    for package_name, import_name in stores_to_check:
        try:
            __import__(import_name)
            print(f"✅ {package_name}: OK")
        except ImportError as e:
            print(f"❌ {package_name}: FAILED - {e}")
            all_good = False

    return all_good


if __name__ == "__main__":
    print("Haven Health Passport - Vector Store Integration Setup")
    print("=" * 60)

    if install_vector_stores():
        if verify_installation():
            print("\n🎉 All vector store integrations are ready!")
        else:
            print("\n⚠️  Some imports failed. Check the errors above.")
            sys.exit(1)
    else:
        print("\n❌ Installation failed!")
        sys.exit(1)
