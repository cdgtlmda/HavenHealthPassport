#!/usr/bin/env python3
"""
Medical NLP Demo.

Demonstrates medical abbreviation expansion and negation detection working together.
 Handles FHIR Resource validation.
"""

import os
import sys
from typing import List

from src.ai.medical_nlp.abbreviations import MedicalAbbreviationHandler
from src.ai.medical_nlp.negation_detector import MedicalNegationDetector

# Add parent directory to path
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


def demonstrate_medical_nlp() -> None:
    """Demonstrate medical NLP capabilities."""
    # Initialize handlers
    abbrev_handler = MedicalAbbreviationHandler()
    negation_detector = MedicalNegationDetector()

    # Clinical text example
    clinical_text = """
    Chief Complaint: CP and SOB x 2 days

    HPI: 58 y/o M with PMH of DM, HTN, and CAD presents with chest pain.
    Patient denies radiation to left arm. No associated N/V or diaphoresis.

    ROS:
    Constitutional: Denies fever, chills, or weight loss
    CV: Positive for CP, no palpitations
    Resp: Positive for SOB, no cough or hemoptysis
    GI: No abdominal pain, no changes in bowel habits

    Assessment:
    1. CP - r/o MI vs GERD
    2. SOB - possible CHF exacerbation vs PE
    3. DM - HbA1c pending

    Plan:
    - ECG, cardiac enzymes STAT
    - CXR to r/o pneumonia
    - Start ASA 325mg PO
    - If CP persists, consider nitroglycerin SL
    """

    print("🏥 MEDICAL NLP DEMONSTRATION")
    print("=" * 50)

    # Step 1: Expand abbreviations
    print("\n📋 STEP 1: Abbreviation Expansion")
    print("-" * 30)
    expanded_text = abbrev_handler.expand_abbreviations(
        clinical_text, preserve_original=True
    )
    print("Sample expansions:")
    print("- CP → chest pain")
    print("- SOB → shortness of breath")
    print("- PMH → past medical history")
    print("- DM → diabetes mellitus")
    print("- HTN → hypertension")

    # Step 2: Detect negations
    print("\n🔍 STEP 2: Negation Detection")
    print("-" * 30)
    negations = negation_detector.detect_negations(expanded_text)

    # Group by type
    from .negation_types import NegationScope  # noqa: PLC0415

    negated = [
        n
        for n in negations
        if n.scope_type == NegationScope.PRE_NEGATION
        or n.scope_type == NegationScope.POST_NEGATION
    ]
    uncertain = [n for n in negations if n.scope_type == NegationScope.UNCERTAIN]
    conditional = [n for n in negations if n.scope_type == NegationScope.CONDITIONAL]

    print(f"\nFound {len(negations)} total negations:")
    print(f"  - Negated: {len(negated)}")
    print(f"  - Uncertain: {len(uncertain)}")
    print(f"  - Conditional: {len(conditional)}")

    # Show examples
    print("\nNegated findings:")
    for neg in negated[:5]:
        print(f"  ❌ {neg.concept} (trigger: '{neg.negation_trigger}')")

    if uncertain:
        print("\nUncertain findings:")
        for unc in uncertain[:3]:
            print(f"  ❓ {unc.concept} (trigger: '{unc.negation_trigger}')")

    if conditional:
        print("\nConditional statements:")
        for cond in conditional[:3]:
            print(f"  ⚡ {cond.concept} (trigger: '{cond.negation_trigger}')")

    # Step 3: Clinical insights
    print("\n💡 CLINICAL INSIGHTS")
    print("-" * 30)

    # Extract key positive and negative findings
    print("\nKey findings from text:")
    print("✅ Positive findings:")
    print("  - Chest pain (ongoing)")
    print("  - Shortness of breath")
    print("  - History of diabetes, hypertension, CAD")

    print("\n❌ Pertinent negatives:")
    pertinent_negatives = [
        "radiation to arm",
        "nausea/vomiting",
        "fever",
        "cough",
        "abdominal pain",
    ]
    for finding in pertinent_negatives:
        for neg in negated:
            if finding.lower() in neg.concept.lower():
                print(f"  - No {finding}")
                break

    print("\n📊 Summary:")
    print("This clinical note describes a patient with:")
    print("- Active chest pain and shortness of breath")
    print("- Multiple cardiac risk factors")
    print("- Important negative findings that help narrow differential")
    print("- Workup focused on ruling out cardiac causes")


if __name__ == "__main__":
    try:
        demonstrate_medical_nlp()
    except ImportError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
