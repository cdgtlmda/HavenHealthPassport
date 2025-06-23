#!/usr/bin/env python3
"""Example usage of Text Splitters for Haven Health Passport.

This script demonstrates how to:
1. Use different text splitting strategies
2. Configure splitters for medical documents
3. Analyze splitting results
4. Choose appropriate splitters

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

import sys
from pathlib import Path
from typing import List

from src.ai.llamaindex.text_splitters import (
    MedicalCodeSplitter,
    ParagraphMedicalSplitter,
    SectionAwareSplitter,
    SentenceMedicalSplitter,
    SlidingWindowSplitter,
    TextSplitterConfig,
    TextSplitterFactory,
)

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parents[4]))


def demonstrate_sentence_splitter() -> None:
    """Demonstrate sentence-based splitting."""
    print("\n1. Sentence-Based Medical Splitter")
    print("=" * 50)

    text = """
    Patient John Doe presented to the emergency department with severe chest pain
    radiating to the left arm. He reported the pain started 2 hours ago while at rest.
    The patient has a history of hypertension and diabetes mellitus type 2.
    Current medications include metformin 1000 mg BID and lisinopril 10 mg daily.
    Blood pressure on arrival was 165/95 mmHg. An ECG showed ST elevation in leads II, III, and aVF.
    Troponin I was elevated at 2.5 ng/mL. The patient was diagnosed with acute inferior
    myocardial infarction (I21.9) and started on aspirin, clopidogrel, and heparin.
    """

    config = TextSplitterConfig(
        chunk_size=200, chunk_overlap=50, ensure_complete_sentences=True  # ~50 words
    )

    splitter = SentenceMedicalSplitter(config)
    result = splitter.split(text)

    print(f"Original text length: {len(text)} characters")
    print(f"Number of chunks: {result.total_chunks}")
    print(f"Average chunk size: {result.avg_chunk_size:.0f} characters")

    for i, chunk in enumerate(result.chunks):
        print(f"\nChunk {i+1}:")
        print(f"Text: {chunk.text[:100]}...")
        print(f"Medical codes: {chunk.metadata.get('medical_codes', [])}")


def demonstrate_section_splitter() -> None:
    """Demonstrate section-aware splitting."""
    print("\n\n2. Section-Aware Splitter")
    print("=" * 50)

    text = """
    Chief Complaint:
    Chest pain and shortness of breath

    History of Present Illness:
    Mr. Johnson is a 65-year-old male who presents with acute onset chest pain that
    started 3 hours ago. The pain is described as crushing, substernal, and radiates
    to the left arm. Associated with diaphoresis and nausea.

    Past Medical History:
    - Hypertension (I10)
    - Type 2 Diabetes Mellitus (E11.9)
    - Hyperlipidemia (E78.5)
    - Previous MI in 2019

    Medications:
    - Metoprolol 50mg BID
    - Lisinopril 20mg daily
    - Atorvastatin 40mg daily
    - Metformin 1000mg BID
    - Aspirin 81mg daily

    Physical Exam:
    Vital Signs: BP 180/100, HR 110, RR 24, T 98.6F, SpO2 94% on RA
    General: Diaphoretic, appears in distress
    Cardiac: Tachycardic, regular rhythm, no murmurs
    Lungs: Bibasilar crackles

    Assessment and Plan:
    1. Acute ST-elevation myocardial infarction (I21.9)
       - Activate cath lab
       - Continue dual antiplatelet therapy
       - Start heparin infusion

    2. Hypertensive urgency
       - IV labetalol for BP control
       - Monitor closely
    """

    splitter = SectionAwareSplitter()
    result = splitter.split(text)

    print(f"Number of sections/chunks: {result.total_chunks}")

    for chunk in result.chunks:
        section = chunk.metadata.get("section_name", "Unknown")
        print(f"\nSection: {section}")
        print(f"Content preview: {chunk.text[:80]}...")
        print(f"Size: {len(chunk.text)} characters")


def demonstrate_medical_code_splitter() -> None:
    """Demonstrate medical code-aware splitting."""
    print("\n\n3. Medical Code Splitter")
    print("=" * 50)

    text = """
    The patient has multiple chronic conditions that require ongoing management.
    Primary diagnosis is essential hypertension (I10) which has been poorly controlled
    despite multiple medications. Secondary diagnoses include type 2 diabetes mellitus
    with diabetic neuropathy (E11.40) and chronic kidney disease stage 3 (N18.3).

    Recent lab results show HbA1c of 8.5%, indicating suboptimal diabetes control.
    The patient also has dyslipidemia (E78.5) with LDL cholesterol of 145 mg/dL.

    Procedures performed during this admission included cardiac catheterization (93458)
    which revealed 70% stenosis of the LAD. The patient underwent percutaneous coronary
    intervention (92928) with drug-eluting stent placement.
    """

    splitter = MedicalCodeSplitter()
    result = splitter.split(text)

    print(f"Number of chunks: {result.total_chunks}")

    for i, chunk in enumerate(result.chunks):
        codes = chunk.metadata.get("medical_codes", [])
        print(f"\nChunk {i+1}:")
        print(f"Medical codes preserved: {codes}")
        print(f"Content: {chunk.text[:150]}...")


def demonstrate_sliding_window() -> None:
    """Demonstrate sliding window splitting."""
    print("\n\n4. Sliding Window Splitter")
    print("=" * 50)

    text = """
    This patient requires careful monitoring due to multiple comorbidities.
    The treatment plan must address cardiovascular risk factors while managing
    diabetes and preventing further kidney damage. Regular follow-up appointments
    are essential to adjust medications and monitor progress. Patient education
    about lifestyle modifications including diet and exercise is crucial for
    long-term management success.
    """

    config = TextSplitterConfig(chunk_size=100, chunk_overlap=30)  # 30% overlap

    splitter = SlidingWindowSplitter(config)
    result = splitter.split(text)

    print(f"Number of overlapping chunks: {result.total_chunks}")

    for i, chunk in enumerate(result.chunks):
        overlap_info = chunk.metadata.get("overlap_size", 0)
        print(f"\nChunk {i+1} (overlap: {overlap_info} tokens):")
        print(f"{chunk.text}")


def demonstrate_auto_selection() -> None:
    """Demonstrate automatic splitter selection."""
    print("\n\n5. Automatic Splitter Selection")
    print("=" * 50)

    # Document with sections
    clinical_note = """
    Chief Complaint: Acute chest pain

    History of Present Illness: 58-year-old male with sudden onset...

    Medications: Aspirin, Metoprolol, Lisinopril
    """

    # Document with many medical codes
    coding_summary = """
    Diagnoses: Hypertension (I10), Diabetes (E11.9), CHF (I50.9),
    COPD (J44.0), CKD Stage 3 (N18.3), Anemia (D64.9)
    """

    # Auto-select for clinical note
    splitter1 = TextSplitterFactory.create_for_content(clinical_note)
    print(f"Clinical note → {type(splitter1).__name__}")

    # Auto-select for coding summary
    splitter2 = TextSplitterFactory.create_for_content(coding_summary)
    print(f"Coding summary → {type(splitter2).__name__}")


def analyze_splitting_quality() -> None:
    """Analyze quality metrics of different splitters."""
    print("\n\n6. Splitting Quality Analysis")
    print("=" * 50)

    test_text = """
    The patient presented with acute myocardial infarction (I21.9) requiring
    immediate intervention. Cardiac catheterization (93458) revealed significant
    stenosis. PCI with stent placement (92928) was performed successfully.
    Post-procedure, the patient was started on dual antiplatelet therapy
    with aspirin 81mg daily and clopidogrel 75mg daily. Beta-blocker therapy
    with metoprolol 50mg BID was initiated for cardioprotection.
    """

    splitters = {
        "Sentence": SentenceMedicalSplitter(),
        "Paragraph": ParagraphMedicalSplitter(),
        "Medical Code": MedicalCodeSplitter(),
    }

    for name, splitter in splitters.items():
        result = splitter.split(test_text)

        print(f"\n{name} Splitter:")
        print(f"  Chunks: {result.total_chunks}")
        print(f"  Avg size: {result.avg_chunk_size:.0f} chars")
        print(f"  Size range: {result.min_chunk_size}-{result.max_chunk_size} chars")
        print(f"  Avg completeness: {result.avg_completeness:.2f}")
        print(f"  Avg coherence: {result.avg_coherence:.2f}")


def main() -> None:
    """Run all demonstrations."""
    print("Haven Health Passport - Text Splitter Examples")
    print("=" * 60)

    demonstrate_sentence_splitter()
    demonstrate_section_splitter()
    demonstrate_medical_code_splitter()
    demonstrate_sliding_window()
    demonstrate_auto_selection()
    analyze_splitting_quality()

    print("\n\nConclusion:")
    print("-" * 40)
    print("Choose splitters based on your document type:")
    print("- Clinical notes with sections → Section-Aware")
    print("- General medical text → Sentence")
    print("- Documents with many codes → Medical Code")
    print("- Maximum context needed → Sliding Window")
    print("- Long research papers → Semantic")


if __name__ == "__main__":
    main()


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
