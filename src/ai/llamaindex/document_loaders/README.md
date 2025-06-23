# Document Loaders for Haven Health Passport

## Overview

This module provides specialized document loaders for medical documents with built-in PHI protection, medical term extraction, and multi-format support. Each loader is optimized for healthcare data and HIPAA compliance.

## Features

### Core Capabilities
- **PHI Detection & Anonymization**: Automatic detection and redaction of Protected Health Information
- **Medical Term Extraction**: Extract ICD-10, CPT, SNOMED, and LOINC codes
- **Multi-language Support**: Detect and handle documents in 50+ languages
- **Quality Assessment**: Automatic quality scoring for loaded documents
- **Metadata Extraction**: Rich metadata including document type, specialty, and dates

### Supported Document Types

1. **PDF Documents** (`PDFMedicalLoader`)
   - Clinical notes, lab reports, imaging reports
   - Table extraction for structured data
   - OCR fallback for scanned PDFs
   - Multi-page support with page-level processing

2. **Images** (`ImageMedicalLoader`)
   - Scanned documents, handwritten notes
   - Medical forms and prescriptions
   - Preprocessing for optimal OCR results
   - Quality assessment of extracted text

3. **Text Files** (`TextMedicalLoader`)
   - Clinical notes, discharge summaries
   - Section detection for structured documents
   - Multiple encoding support
   - Automatic structure detection

4. **Office Documents** (Coming Soon)
   - Word documents (.doc, .docx)
   - Excel files with patient data (.xls, .xlsx)

5. **DICOM Files** (Coming Soon)
   - Medical imaging metadata extraction
   - Patient information handling

6. **HL7 Messages** (Coming Soon)
   - Parse HL7 v2 and FHIR messages
   - Extract clinical data

## Quick Start

```python
from haven_health_passport.ai.llamaindex.document_loaders import (
    DocumentLoaderFactory,
    DocumentLoaderConfig,
    DocumentType
)

# Basic usage
result = DocumentLoaderFactory.load_document("path/to/medical_report.pdf")

if result.success:
    for doc in result.documents:
        print(f"Page: {doc.metadata.get('page_number', 1)}")
        print(f"Text: {doc.text[:200]}...")
        print(f"ICD Codes: {result.metadata.icd_codes}")

# With configuration
config = DocumentLoaderConfig(
    extract_metadata=True,
    detect_phi=True,
    anonymize_phi=True,
    extract_medical_terms=True,
    chunk_size=1000,
    min_quality_score=DocumentQuality.MEDIUM
)

result = DocumentLoaderFactory.load_document(
    "clinical_note.txt",
    config=config
)

# Batch processing
file_paths = [
    "lab_report.pdf",
    "prescription.jpg",
    "discharge_summary.txt"
]

results = DocumentLoaderFactory.load_documents_batch(file_paths, config)

for file_path, result in results.items():
    print(f"{file_path}: {'Success' if result.success else 'Failed'}")
    if result.errors:
        print(f"  Errors: {result.errors}")
```

## Configuration Options

```python
config = DocumentLoaderConfig(
    # Processing options
    extract_metadata=True,          # Extract document metadata
    detect_phi=True,               # Detect Protected Health Information
    anonymize_phi=True,            # Anonymize detected PHI
    extract_medical_terms=True,    # Extract medical codes and terms

    # Quality settings
    min_quality_score=DocumentQuality.LOW,  # Minimum acceptable quality
    confidence_threshold=0.7,      # OCR confidence threshold

    # Language settings
    detect_language=True,          # Auto-detect document language
    target_language=None,          # Target language for translation

    # Performance settings
    chunk_size=1000,              # Text chunk size
    chunk_overlap=200,            # Overlap between chunks
    max_file_size_mb=100,         # Maximum file size to process
    timeout_seconds=300,          # Processing timeout

    # Security settings
    verify_compliance=True,        # Verify HIPAA compliance
    encrypt_sensitive_data=False,  # Encrypt sensitive extracts

    # Output settings
    include_page_numbers=True,     # Include page numbers in metadata
    preserve_formatting=False,     # Preserve original formatting
    extract_tables=True,          # Extract tables from documents
    extract_images=True           # Extract embedded images
)
```

## Document Metadata

Each loaded document includes rich metadata:

```python
metadata = DocumentMetadata(
    # Basic metadata
    file_path="path/to/file.pdf",
    file_type="pdf",
    file_size=1024000,  # bytes
    created_date=datetime,
    modified_date=datetime,

    # Medical metadata
    document_type="lab_report",  # Detected document type
    specialty="cardiology",      # Medical specialty if detected
    provider_name=None,          # Extracted provider info
    facility_name=None,          # Extracted facility info

    # Patient metadata (anonymized)
    patient_id="REDACTED",       # Anonymized patient ID
    encounter_id=None,           # Encounter/visit ID

    # Quality indicators
    quality_score=DocumentQuality.HIGH,
    confidence_score=0.95,       # OCR confidence

    # Security/compliance
    phi_level=PHILevel.MEDIUM,   # Level of PHI detected
    is_encrypted=False,
    compliance_verified=True,

    # Language and localization
    language="en",
    detected_languages=["en", "es"],

    # Processing metadata
    ocr_applied=False,
    translation_applied=False,
    anonymization_applied=True,

    # Medical codes
    icd_codes=["I21.9", "I10"],  # Extracted ICD-10 codes
    cpt_codes=["99213"],         # Extracted CPT codes
    snomed_codes=[],             # Extracted SNOMED codes
    loinc_codes=[]               # Extracted LOINC codes
)
```

## PHI Detection and Anonymization

The loaders automatically detect and can anonymize various types of PHI:

- Social Security Numbers (SSN)
- Phone numbers
- Email addresses
- Medical Record Numbers (MRN)
- Dates of birth
- Patient names (using NER)
- Addresses

Example of anonymized text:
```
Original: "Patient John Doe (MRN: 12345) was seen on 01/15/2024"
Anonymized: "Patient [REDACTED_NAME] (MRN: [REDACTED_MRN]) was seen on [REDACTED_DATE]"
```

## Medical Term Extraction

The loaders extract various medical codes and terms:

1. **ICD-10 Codes**: Disease and diagnosis codes
2. **CPT Codes**: Procedure codes
3. **SNOMED CT**: Clinical terminology (coming soon)
4. **LOINC**: Laboratory observation codes (coming soon)
5. **Medications**: Drug names and dosages (coming soon)
6. **Conditions**: Medical conditions and diagnoses (coming soon)

## Quality Assessment

Documents are assigned quality scores:

- **HIGH**: Clear text, high confidence extraction
- **MEDIUM**: Mostly clear with some issues
- **LOW**: Poor quality but readable
- **UNREADABLE**: Cannot extract meaningful text

## Error Handling

```python
result = DocumentLoaderFactory.load_document("corrupted.pdf")

if not result.success:
    print(f"Failed to load document: {result.errors}")

if result.warnings:
    print(f"Warnings: {result.warnings}")

# Access partial results even on failure
if result.documents:
    print(f"Extracted {len(result.documents)} pages before error")
```

## Performance Considerations

1. **Large Files**: Files are processed in chunks to manage memory
2. **OCR Processing**: OCR is CPU-intensive; consider using GPU acceleration
3. **Batch Processing**: Use batch loading for multiple files
4. **Caching**: Consider caching extracted text for frequently accessed documents

## Security Best Practices

1. **Always enable PHI detection** for medical documents
2. **Use anonymization** when storing or transmitting data
3. **Verify compliance** settings for your use case
4. **Encrypt sensitive data** at rest and in transit
5. **Audit access** to loaded documents

## Testing

```bash
# Run document loader tests
pytest src/ai/llamaindex/document_loaders/tests/

# Test specific loader
pytest src/ai/llamaindex/document_loaders/tests/test_pdf_loader.py
```

## Dependencies

- **PDF Processing**: pypdf, pdfplumber, pdf2image
- **OCR**: pytesseract, opencv-python
- **Image Processing**: Pillow, opencv-python
- **Text Processing**: chardet, langdetect
- **Medical NLP**: (coming soon) scispacy, medspacy

## Future Enhancements

- [ ] DICOM file support for medical imaging
- [ ] HL7/FHIR message parsing
- [ ] Office document support (Word, Excel)
- [ ] Advanced medical NER for entity extraction
- [ ] Handwriting recognition improvements
- [ ] Multi-column layout detection
- [ ] Form field extraction
- [ ] Signature detection and verification
