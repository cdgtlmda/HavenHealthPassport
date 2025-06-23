"""
Example Usage of Document Classification

This script demonstrates how to use the document classification system
in the Haven Health Passport application.
"""

import asyncio
import logging
from pathlib import Path

from src.ai.document_processing import DocumentClassifier, DocumentType
from src.ai.document_processing.textract_config import TextractClient, TextractConfig
from src.ai.medical_nlp.entity_extraction import MedicalEntityExtractor
from src.audit.audit_logger import AuditLogger
from src.healthcare.medical_terminology import MedicalTerminologyValidator
from src.metrics.metrics_collector import MetricsCollector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def classify_document_example():
    """Example of classifying a medical document."""

    # Initialize dependencies
    textract_config = TextractConfig()
    textract_client = TextractClient(textract_config)
    medical_entity_extractor = MedicalEntityExtractor()
    medical_terminology_validator = MedicalTerminologyValidator()
    audit_logger = AuditLogger()
    metrics_collector = MetricsCollector()

    # Create classifier
    classifier = DocumentClassifier(
        textract_client=textract_client,
        medical_entity_extractor=medical_entity_extractor,
        medical_terminology_validator=medical_terminology_validator,
        audit_logger=audit_logger,
        metrics_collector=metrics_collector,
    )

    # Example document text
    prescription_text = """
    Medical Center of Excellence
    Dr. Sarah Johnson, MD

    PRESCRIPTION

    Patient Name: John Smith
    Date of Birth: 05/15/1985
    Date: 2024-01-25

    Rx: Lisinopril 10mg
    Sig: Take one tablet by mouth once daily
    Quantity: 30 tablets
    Refills: 3

    Dr. Sarah Johnson
    License: MD123456
    """

    # Classify the document
    result = await classifier.classify_document(prescription_text)

    # Display results
    print(f"Document Type: {result.document_type.value}")
    print(f"Confidence: {result.confidence:.2%}")
    print(f"Confidence Level: {result.confidence_level.value}")
    print(f"Method Used: {result.method_used.value}")
    print(f"Processing Time: {result.processing_time_ms:.2f}ms")
    print(f"Reasoning: {result.reasoning}")

    if result.alternative_types:
        print("\nAlternative Classifications:")
        for doc_type, conf in result.alternative_types:
            print(f"  - {doc_type.value}: {conf:.2%}")

    # Example with image bytes (OCR)
    # with open("medical_document.jpg", "rb") as f:
    #     image_bytes = f.read()
    # result = await classifier.classify_document(image_bytes)

    return result


async def batch_classification_example():
    """Example of classifying multiple documents."""

    # Initialize classifier (same as above)
    # ... (initialization code)

    documents = [
        {"id": "doc001", "content": "Lab results showing elevated glucose levels..."},
        {"id": "doc002", "content": "Insurance policy number 12345..."},
        {"id": "doc003", "content": "COVID-19 vaccination card..."},
    ]

    results = []
    for doc in documents:
        result = await classifier.classify_document(doc["content"])
        results.append(
            {
                "id": doc["id"],
                "type": result.document_type.value,
                "confidence": result.confidence,
            }
        )

    return results


if __name__ == "__main__":
    # Run the example
    asyncio.run(classify_document_example())
