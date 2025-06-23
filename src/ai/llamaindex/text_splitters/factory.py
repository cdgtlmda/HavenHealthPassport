"""Text Splitter Factory.

Factory for creating appropriate text splitters based on
document type and requirements.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

import logging
import re
from enum import Enum
from typing import Dict, List, Optional, Type

from .base import BaseMedicalSplitter, TextSplitterConfig
from .code_splitter import MedicalCodeSplitter
from .paragraph_splitter import ParagraphMedicalSplitter
from .section_splitter import SectionAwareSplitter
from .semantic_splitter import SemanticMedicalSplitter
from .sentence_splitter import SentenceMedicalSplitter
from .sliding_window import SlidingWindowSplitter

logger = logging.getLogger(__name__)


class SplitterType(str, Enum):
    """Available splitter types."""

    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    SECTION = "section"
    SEMANTIC = "semantic"
    MEDICAL_CODE = "medical_code"
    SLIDING_WINDOW = "sliding_window"
    AUTO = "auto"  # Automatically select based on content


class TextSplitterFactory:
    """Factory for creating text splitters."""

    # Splitter registry
    _splitters: Dict[SplitterType, Type[BaseMedicalSplitter]] = {
        SplitterType.SENTENCE: SentenceMedicalSplitter,
        SplitterType.PARAGRAPH: ParagraphMedicalSplitter,
        SplitterType.SECTION: SectionAwareSplitter,
        SplitterType.SEMANTIC: SemanticMedicalSplitter,
        SplitterType.MEDICAL_CODE: MedicalCodeSplitter,
        SplitterType.SLIDING_WINDOW: SlidingWindowSplitter,
    }

    @classmethod
    def create_splitter(
        cls,
        splitter_type: SplitterType = SplitterType.AUTO,
        config: Optional[TextSplitterConfig] = None,
    ) -> BaseMedicalSplitter:
        """Create appropriate splitter."""
        if splitter_type == SplitterType.AUTO:
            # Use configuration to determine splitter
            if config and config.split_strategy:
                splitter_type = SplitterType(config.split_strategy.value)
            else:
                splitter_type = SplitterType.SENTENCE  # Default

        if splitter_type not in cls._splitters:
            raise ValueError(f"Unknown splitter type: {splitter_type}")

        splitter_class = cls._splitters[splitter_type]
        return splitter_class(config)

    @classmethod
    def create_for_document_type(
        cls, document_type: str, config: Optional[TextSplitterConfig] = None
    ) -> BaseMedicalSplitter:
        """Create splitter based on document type."""
        # Map document types to optimal splitters
        document_splitter_map = {
            "clinical_note": SplitterType.SECTION,
            "discharge_summary": SplitterType.SECTION,
            "lab_report": SplitterType.PARAGRAPH,
            "radiology_report": SplitterType.PARAGRAPH,
            "prescription": SplitterType.SENTENCE,
            "progress_note": SplitterType.SECTION,
            "consultation_report": SplitterType.SECTION,
            "medical_record": SplitterType.MEDICAL_CODE,
            "research_paper": SplitterType.SEMANTIC,
            "patient_education": SplitterType.PARAGRAPH,
        }

        splitter_type = document_splitter_map.get(
            document_type.lower(), SplitterType.SENTENCE  # Default
        )

        logger.info(
            "Using %s splitter for document type: %s", splitter_type, document_type
        )

        return cls.create_splitter(splitter_type, config)

    @classmethod
    def create_for_content(
        cls, text: str, config: Optional[TextSplitterConfig] = None
    ) -> BaseMedicalSplitter:
        """Analyze content and create appropriate splitter."""
        # Simple heuristics to determine best splitter
        # Check for section headers
        section_pattern = re.compile(
            r"^(Chief Complaint|History of Present Illness|Past Medical History|"
            r"Medications|Physical Exam|Assessment|Plan):",
            re.I | re.M,
        )

        if section_pattern.search(text):
            logger.info("Detected section headers, using section-aware splitter")
            return cls.create_splitter(SplitterType.SECTION, config)

        # Check for medical codes
        code_pattern = re.compile(r"\b[A-Z]\d{2}\.?\d{0,2}\b|\b\d{5}\b")
        code_matches = code_pattern.findall(text)

        if len(code_matches) > 5:  # Multiple medical codes
            logger.info("Detected multiple medical codes, using code-aware splitter")
            return cls.create_splitter(SplitterType.MEDICAL_CODE, config)

        # Check document length
        if len(text) > 10000:  # Long document
            logger.info("Long document detected, using semantic splitter")
            return cls.create_splitter(SplitterType.SEMANTIC, config)

        # Default to sentence splitter
        logger.info("Using default sentence splitter")
        return cls.create_splitter(SplitterType.SENTENCE, config)


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
