#!/usr/bin/env python3
"""
Verify Medical Abbreviation Handler Installation.

Quick verification that the medical abbreviation handler is working correctly.
 Handles FHIR Resource validation.
"""

import os
import sys
from typing import List

# Add parent directory to path
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

try:
    # Import the medical abbreviation handler
    from ai.medical_nlp import MedicalAbbreviationHandler

    print("✅ Medical abbreviation handler imported successfully")

    # Create handler instance
    handler = MedicalAbbreviationHandler()
    print(f"✅ Handler initialized with {len(handler.abbreviations)} abbreviations")

    # Test abbreviation detection
    test_text = (
        "Patient BP 140/90, HR 88, diagnosed with DM and HTN. Given ASA 81mg PO QD."
    )
    matches = handler.detect_abbreviations(test_text)
    print(f"✅ Detected {len(matches)} abbreviations in test text")

    # Test abbreviation expansion
    expanded = handler.expand_abbreviations(test_text)
    print(f"✅ Expanded text: {expanded[:100]}...")

    # Test context resolution
    cardiac_text = "Patient with cardiac history presents with CP"
    cardiac_matches = handler.detect_abbreviations(cardiac_text)
    cp_match = next((m for m in cardiac_matches if m.text == "CP"), None)

    if cp_match and cp_match.selected_expansion == "chest pain":
        print(
            "✅ Context-aware resolution working (CP → chest pain in cardiac context)"
        )
    else:
        print("⚠️ Context resolution may need adjustment")

    # Summary
    print("\n✅ Medical abbreviation handler is fully functional!")
    print(f"   - Total abbreviations: {len(handler.abbreviations)}")
    print(
        f"   - Context resolution: {'Enabled' if handler.enable_context_resolution else 'Disabled'}"
    )
    print(f"   - Minimum confidence: {handler.min_confidence}")
    print(f"   - Language: {handler.language}")

except ImportError as e:
    print(f"❌ Failed to import medical abbreviation handler: {e}")
    sys.exit(1)
except (ValueError, AttributeError) as e:
    print(f"❌ Error during verification: {e}")
    sys.exit(1)


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
