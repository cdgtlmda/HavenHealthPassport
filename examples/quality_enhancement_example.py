"""
Example Usage of Document Quality Enhancement

This script demonstrates how to use the document quality enhancement system
to improve document images before OCR processing.
"""

import asyncio
import logging
from pathlib import Path

import numpy as np
from PIL import Image

from src.ai.document_processing import (
    DocumentQualityEnhancer,
    DocumentType,
    EnhancementParameters,
    EnhancementType,
)
from src.audit.audit_logger import AuditLogger
from src.metrics.metrics_collector import MetricsCollector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def enhance_document_example():
    """Example of enhancing a medical document image."""

    # Initialize dependencies
    audit_logger = AuditLogger()
    metrics_collector = MetricsCollector()

    # Create enhancer
    enhancer = DocumentQualityEnhancer(
        audit_logger=audit_logger, metrics_collector=metrics_collector
    )

    # Load a sample image (in production, this would be a real document)
    # For demo, create a synthetic low-quality document
    image = create_sample_document()

    # Enhance with automatic settings
    logger.info("Enhancing document with automatic settings...")
    result = await enhancer.enhance_document(image)

    if result.success:
        logger.info(f"Enhancement successful!")
        logger.info(
            f"Original quality: {result.original_metrics.overall_quality.value}"
        )
        logger.info(
            f"Enhanced quality: {result.enhanced_metrics.overall_quality.value}"
        )
        logger.info(f"Improvement score: {result.improvement_score:.2%}")
        logger.info(
            f"Operations applied: {[op.value for op in result.operations_applied]}"
        )
        logger.info(f"Processing time: {result.processing_time_ms:.2f}ms")

        # Save enhanced image
        enhanced_pil = Image.fromarray(result.enhanced_image)
        enhanced_pil.save("enhanced_document.png")
        logger.info("Enhanced image saved as 'enhanced_document.png'")
    else:
        logger.error(f"Enhancement failed: {result.error_message}")

    # Example with specific enhancements
    logger.info("\nEnhancing with specific operations...")
    params = EnhancementParameters(
        enhancement_types=[
            EnhancementType.CONTRAST,
            EnhancementType.SHARPNESS,
            EnhancementType.DENOISE,
        ],
        contrast_factor=1.5,
        sharpness_factor=2.0,
        denoise_strength=10,
        auto_enhance=False,
    )

    result2 = await enhancer.enhance_document(image, params=params)

    if result2.success:
        logger.info("Custom enhancement successful!")
        logger.info(
            f"Operations applied: {[op.value for op in result2.operations_applied]}"
        )


def create_sample_document():
    """Create a synthetic low-quality document for testing."""
    # Create a document with poor quality characteristics
    width, height = 800, 1000

    # Start with off-white background (simulating old paper)
    image = np.ones((height, width, 3), dtype=np.uint8) * 230

    # Add some text-like content
    import cv2

    # Title
    cv2.putText(
        image,
        "Medical Record",
        (200, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.5,
        (50, 50, 50),
        2,
    )

    # Body text (simulated)
    y_pos = 200
    for i in range(20):
        text = "Lorem ipsum dolor sit amet " * 3
        cv2.putText(
            image,
            text[:60],
            (50, y_pos),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (80, 80, 80),
            1,
        )
        y_pos += 30

    # Add noise
    noise = np.random.normal(0, 20, image.shape).astype(np.uint8)
    image = cv2.add(image, noise)

    # Add some blur (simulating poor scan quality)
    image = cv2.GaussianBlur(image, (3, 3), 0)

    # Reduce contrast
    image = cv2.convertScaleAbs(image, alpha=0.7, beta=30)

    # Add slight rotation (skew)
    rows, cols = image.shape[:2]
    M = cv2.getRotationMatrix2D((cols / 2, rows / 2), 2, 1)  # 2 degree rotation
    image = cv2.warpAffine(image, M, (cols, rows), borderValue=(230, 230, 230))

    return image


async def batch_enhancement_example():
    """Example of enhancing multiple documents."""
    # Initialize enhancer
    audit_logger = AuditLogger()
    metrics_collector = MetricsCollector()
    enhancer = DocumentQualityEnhancer(
        audit_logger=audit_logger, metrics_collector=metrics_collector
    )

    # Process multiple documents
    document_paths = ["prescription1.jpg", "lab_report.png", "insurance_card.jpg"]

    for doc_path in document_paths:
        # In production, load actual images
        # For demo, use synthetic image
        image = create_sample_document()

        logger.info(f"\nProcessing {doc_path}...")
        result = await enhancer.enhance_document(
            image,
            document_type=DocumentType.PRESCRIPTION,  # Would be determined by classifier
        )

        if result.success:
            logger.info(
                f"✓ Enhanced {doc_path}: {result.improvement_score:.2%} improvement"
            )
        else:
            logger.error(f"✗ Failed to enhance {doc_path}")


if __name__ == "__main__":
    # Run the example
    asyncio.run(enhance_document_example())
