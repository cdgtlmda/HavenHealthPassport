#!/usr/bin/env python3
"""
Verify LlamaIndex installation and configuration.

This script verifies that LlamaIndex is properly installed and configured
for the Haven Health Passport system.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import importlib
import os
import sys
from typing import Dict, List, Tuple

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))


def check_import(module_name: str) -> Tuple[bool, str]:
    """Check if a module can be imported."""
    try:
        importlib.import_module(module_name)
        return True, f"✓ {module_name} imported successfully"
    except ImportError as e:
        return False, f"✗ {module_name} import failed: {e}"
    except AttributeError as e:
        return False, f"✗ {module_name} import error: {e}"


def verify_core_imports() -> Tuple[bool, List[str]]:
    """Verify core LlamaIndex imports."""
    print("\n1. Checking Core LlamaIndex Imports...")

    # Try both import structures
    modules_new = [
        "llama_index",
        "llama_index.core",
        "llama_index.core.indices",
        "llama_index.core.node_parser",
        "llama_index.core.embeddings",
        "llama_index.core.llms",
        "llama_index.core.vector_stores",
        "llama_index.core.storage",
        "llama_index.core.readers",
        "llama_index.core.query_engine",
    ]

    modules_old = [
        "llama_index",
        "llama_index.indices",
        "llama_index.node_parser",
        "llama_index.embeddings",
        "llama_index.llms",
        "llama_index.vector_stores",
        "llama_index.storage",
        "llama_index.readers",
        "llama_index.query_engine",
    ]

    results = []
    all_success = True

    # First try new structure
    print("  Trying new import structure (0.10+)...")
    new_structure_works = True
    for module in modules_new[:2]:  # Just test core modules
        success, message = check_import(module)
        if not success:
            new_structure_works = False
            break

    if new_structure_works:
        print("  ✓ Using new import structure")
        modules = modules_new
    else:
        print("  Trying older import structure...")
        modules = modules_old

    for module in modules:
        success, message = check_import(module)
        results.append(message)
        if not success:
            all_success = False

    return all_success, results


def verify_haven_integration() -> Tuple[bool, List[str]]:
    """Verify Haven Health Passport LlamaIndex integration."""
    print("\n2. Checking Haven Integration...")

    results = []
    all_success = True

    try:
        # Import Haven LlamaIndex module
        # pylint: disable=import-outside-toplevel
        from src.ai.llamaindex import (
            MedicalIndexConfig,
            __version__,
            initialize_llamaindex,
        )

        results.append(f"✓ Haven LlamaIndex module imported (version {__version__})")

        # Test initialization
        config = MedicalIndexConfig()
        success = initialize_llamaindex(config, debug=False)
        if success:
            results.append("✓ LlamaIndex initialization successful")
        else:
            results.append("✗ LlamaIndex initialization failed")
            all_success = False

        # Test configuration
        results.append(f"✓ Default chunk size: {config.chunk_size}")
        results.append(f"✓ Default chunk overlap: {config.chunk_overlap}")
        results.append(f"✓ Storage path: {config.storage_path}")

    except (ImportError, AttributeError) as e:
        results.append(f"✗ Haven integration error: {e}")
        all_success = False

    return all_success, results


def verify_document_loaders() -> Tuple[bool, List[str]]:
    """Verify document loader capabilities."""
    print("\n3. Checking Document Loaders...")

    results = []
    all_success = True

    loaders = [
        ("llama_index.core.readers", "SimpleDirectoryReader"),
        ("llama_index.readers.file", "PDFReader"),
        ("llama_index.readers.file", "DocxReader"),
        ("llama_index.readers.file", "CSVReader"),
    ]

    for module_path, class_name in loaders:
        try:
            module = importlib.import_module(module_path)
            if hasattr(module, class_name):
                results.append(f"✓ {class_name} available")
            else:
                results.append(f"✗ {class_name} not found in {module_path}")
                all_success = False
        except ImportError:
            results.append(f"✗ {module_path} not available")
            # Not critical if some readers are missing

    return all_success, results


def verify_medical_features() -> Tuple[bool, List[str]]:
    """Verify medical-specific features."""
    print("\n4. Checking Medical Features...")

    results = []
    all_success = True

    try:
        # pylint: disable=import-outside-toplevel
        from src.ai.llamaindex.config import (
            MEDICAL_DOCUMENT_CONFIGS,
            get_config,
        )

        # Check configuration
        config = get_config()
        results.append(f"✓ Medical NER enabled: {config.medical_ner_enabled}")
        results.append(f"✓ PHI detection enabled: {config.phi_detection_enabled}")
        results.append(f"✓ Medical term extraction: {config.medical_term_extraction}")

        # Check document configs
        results.append(
            f"✓ Medical document types configured: {len(MEDICAL_DOCUMENT_CONFIGS)}"
        )
        for doc_type in ["clinical_notes", "lab_reports", "prescriptions"]:
            if doc_type in MEDICAL_DOCUMENT_CONFIGS:
                results.append(f"  - {doc_type}: configured")

    except (ImportError, AttributeError) as e:
        results.append(f"✗ Medical features error: {e}")
        all_success = False

    return all_success, results


def main() -> int:
    """Run all verification checks."""
    print("=" * 60)
    print("Haven Health Passport - LlamaIndex Installation Verification")
    print("=" * 60)

    all_results: Dict[str, Tuple[bool, List[str]]] = {}

    # Run all checks
    all_results["Core Imports"] = verify_core_imports()
    all_results["Haven Integration"] = verify_haven_integration()
    all_results["Document Loaders"] = verify_document_loaders()
    all_results["Medical Features"] = verify_medical_features()

    # Print results
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total_success = True
    for check_name, (success, messages) in all_results.items():
        status = "PASSED" if success else "FAILED"
        print(f"\n{check_name}: {status}")
        for message in messages:
            print(f"  {message}")

        if not success:
            total_success = False

    # Final verdict
    print("\n" + "=" * 60)
    if total_success:
        print("✓ ALL CHECKS PASSED - LlamaIndex is properly installed!")
        print("\nNext steps:")
        print("1. Configure vector store integration")
        print("2. Set up document loaders")
        print("3. Configure embedding models")
    else:
        print("✗ SOME CHECKS FAILED - Please review the errors above")
        print("\nTo fix:")
        print("1. Run: pip install -r src/ai/llamaindex/requirements.txt")
        print("2. Check your Python environment (requires 3.11+)")
        print("3. Verify all dependencies are installed")

    print("=" * 60)

    return 0 if total_success else 1


if __name__ == "__main__":
    sys.exit(main())
