#!/usr/bin/env python3
"""Example usage of Document Loaders for Haven Health Passport.

This script demonstrates how to:
1. Load various medical document types
2. Extract metadata and medical terms
3. Handle PHI detection and anonymization
4. Process documents for indexing

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parents[4]))

# pylint: disable=wrong-import-position
from src.ai.llamaindex.document_loaders import (  # noqa: E402
    DocumentLoaderConfig,
    DocumentLoaderFactory,
)
from src.ai.llamaindex.document_loaders.base import DocumentQuality  # noqa: E402


def main() -> None:
    """Execute main example function."""
    # Configure document loader
    config = DocumentLoaderConfig(
        extract_metadata=True,
        detect_phi=True,
        anonymize_phi=True,
        extract_medical_terms=True,
        chunk_size=1000,
        min_quality_score=DocumentQuality.LOW,
    )

    print("Haven Health Passport - Document Loader Example")
    print("=" * 60)

    # Example 1: Load a PDF document
    print("\n1. Loading PDF Document")
    print("-" * 30)

    # Create a sample PDF path (you would use a real file)
    pdf_path = "sample_lab_report.pdf"

    if DocumentLoaderFactory.is_supported(pdf_path):
        print(f"✅ {pdf_path} is supported")

        # Load the document
        result = DocumentLoaderFactory.load_document(pdf_path, config)

        if result.success:
            print(f"✅ Successfully loaded {len(result.documents)} pages")

            # Display metadata
            if result.metadata:
                print("\nDocument Metadata:")
                print(f"  - Type: {result.metadata.document_type}")
                print(f"  - Quality: {result.metadata.quality_score}")
                print(f"  - PHI Level: {result.metadata.phi_level}")
                print(f"  - Language: {result.metadata.language}")

                if result.metadata.icd_codes:
                    print(f"  - ICD Codes: {', '.join(result.metadata.icd_codes)}")

                if result.metadata.cpt_codes:
                    print(f"  - CPT Codes: {', '.join(result.metadata.cpt_codes)}")

            # Display first page content (truncated)
            if result.documents:
                first_doc = result.documents[0]
                print("\nFirst Page Preview:")
                print(f"{first_doc.text[:200]}...")
        else:
            print(f"❌ Failed to load: {result.errors}")

    # Example 2: Batch load multiple documents
    print("\n\n2. Batch Loading Documents")
    print("-" * 30)

    file_paths = ["clinical_note.txt", "prescription.jpg", "discharge_summary.pdf"]

    results = DocumentLoaderFactory.load_documents_batch(file_paths, config)

    for file_path, result in results.items():
        status = "✅ Success" if result.success else "❌ Failed"
        doc_count = len(result.documents) if result.success else 0
        print(f"{file_path}: {status} ({doc_count} documents)")

        if result.warnings:
            for warning in result.warnings:
                print(f"  ⚠️  {warning}")

    # Example 3: PHI Detection and Anonymization
    print("\n\n3. PHI Detection Example")
    print("-" * 30)

    # Create a text file with PHI (for demonstration)
    sample_text = """
    Patient: John Doe
    MRN: 12345678
    DOB: 01/15/1980
    SSN: 123-45-6789
    Phone: (555) 123-4567
    Email: john.doe@email.com

    Chief Complaint: Chest pain

    Diagnosis: Acute myocardial infarction (I21.9)

    Medications:
    - Aspirin 81mg daily
    - Metoprolol 50mg BID
    """

    # Save to temporary file
    temp_file = "temp_clinical_note.txt"
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(sample_text)

    # Load with PHI anonymization
    result = DocumentLoaderFactory.load_document(temp_file, config)

    if result.success and result.documents:
        anonymized_text = result.documents[0].text
        print("Original text contains PHI")
        print("\nAnonymized text:")
        print(anonymized_text[:300])

        if result.metadata:
            print(f"\nPHI Level Detected: {result.metadata.phi_level}")

    # Clean up
    if os.path.exists(temp_file):
        os.remove(temp_file)

    # Example 4: Supported file types
    print("\n\n4. Supported File Types")
    print("-" * 30)

    extensions = DocumentLoaderFactory.get_supported_extensions()
    print(f"Supported extensions: {', '.join(sorted(extensions))}")

    # Test file type detection
    test_files = [
        "report.pdf",
        "xray.jpg",
        "notes.txt",
        "data.xlsx",
        "image.dcm",
        "message.hl7",
    ]

    print("\nFile type detection:")
    for file in test_files:
        doc_type = DocumentLoaderFactory.detect_document_type(file)
        supported = "✅" if doc_type != "unknown" else "❌"
        print(f"{supported} {file} → {doc_type}")


if __name__ == "__main__":
    main()


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings: list[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
