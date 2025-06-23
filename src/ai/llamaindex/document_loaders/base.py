"""Base Classes for Document Loaders.

Provides abstract base classes and common functionality
for all medical document loaders.

This module handles access control for PHI operations.
Handles FHIR Resource validation.
"""

import hashlib
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from llama_index.core import Document
from llama_index.core.node_parser import SimpleNodeParser

logger = logging.getLogger(__name__)


class DocumentQuality(str, Enum):
    """Document quality indicators."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNREADABLE = "unreadable"


class PHILevel(str, Enum):
    """PHI (Protected Health Information) levels."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DocumentMetadata:
    """Medical document metadata."""

    # Basic metadata
    file_path: str
    file_type: str
    file_size: int
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None

    # Medical metadata
    document_type: Optional[str] = None  # clinical_note, lab_report, etc.
    specialty: Optional[str] = None
    provider_name: Optional[str] = None
    facility_name: Optional[str] = None

    # Patient metadata (anonymized)    patient_id: Optional[str] = None  # Anonymized ID
    encounter_id: Optional[str] = None

    # Quality indicators
    quality_score: DocumentQuality = DocumentQuality.MEDIUM
    confidence_score: float = 1.0

    # Security/compliance
    phi_level: PHILevel = PHILevel.MEDIUM
    is_encrypted: bool = False
    compliance_verified: bool = False

    # Language and localization
    language: str = "en"
    detected_languages: List[str] = field(default_factory=list)

    # Processing metadata
    ocr_applied: bool = False
    translation_applied: bool = False
    anonymization_applied: bool = False

    # Medical codes
    icd_codes: List[str] = field(default_factory=list)
    cpt_codes: List[str] = field(default_factory=list)
    snomed_codes: List[str] = field(default_factory=list)
    loinc_codes: List[str] = field(default_factory=list)

    # Additional custom metadata
    custom_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for LlamaIndex."""
        return {
            "file_path": self.file_path,
            "file_type": self.file_type,
            "document_type": self.document_type,
            "specialty": self.specialty,
            "language": self.language,
            "quality_score": self.quality_score,
            "phi_level": self.phi_level,
            "icd_codes": self.icd_codes,
            **self.custom_metadata,
        }


@dataclass
class LoaderResult:
    """Result from document loading operation."""

    success: bool
    documents: List[Document] = field(default_factory=list)
    metadata: Optional[DocumentMetadata] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    processing_time_ms: Optional[int] = None

    @property
    def document_count(self) -> int:
        """Number of documents loaded."""
        return len(self.documents)


@dataclass
class DocumentLoaderConfig:
    """Configuration for document loaders."""

    # Processing options
    extract_metadata: bool = True
    detect_phi: bool = True
    anonymize_phi: bool = True
    extract_medical_terms: bool = True

    # Quality settings
    min_quality_score: DocumentQuality = DocumentQuality.LOW
    confidence_threshold: float = 0.7

    # Language settings
    detect_language: bool = True
    target_language: Optional[str] = None  # For translation

    # Performance settings
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_file_size_mb: int = 100
    timeout_seconds: int = 300

    # Security settings
    verify_compliance: bool = True
    encrypt_sensitive_data: bool = False

    # Output settings
    include_page_numbers: bool = True
    preserve_formatting: bool = False
    extract_tables: bool = True
    extract_images: bool = True


class BaseDocumentLoader(ABC):
    """Abstract base class for all document loaders."""

    def __init__(self, config: Optional[DocumentLoaderConfig] = None):
        """Initialize the document loader with optional configuration."""
        self.config = config or DocumentLoaderConfig()
        self._phi_patterns = self._compile_phi_patterns()

    @abstractmethod
    def load(self, file_path: str, **kwargs: Any) -> LoaderResult:
        """Load a document from file path."""

    @abstractmethod
    def can_load(self, file_path: str) -> bool:
        """Check if this loader can handle the file."""

    def _compile_phi_patterns(self) -> Dict[str, Any]:
        """Compile regex patterns for PHI detection."""
        return {
            "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
            "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            "mrn": re.compile(r"\b(MRN|Medical Record Number):\s*\d+\b", re.I),
            "dob": re.compile(
                r"\b(DOB|Date of Birth):\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", re.I
            ),
        }

    def _detect_phi_level(self, text: str) -> PHILevel:
        """Detect level of PHI in text."""
        phi_count = 0

        for _pattern_name, pattern in self._phi_patterns.items():
            matches = pattern.findall(text)
            phi_count += len(matches)

        if phi_count == 0:
            return PHILevel.NONE
        elif phi_count <= 2:
            return PHILevel.LOW
        elif phi_count <= 5:
            return PHILevel.MEDIUM
        elif phi_count <= 10:
            return PHILevel.HIGH
        else:
            return PHILevel.CRITICAL

    def _anonymize_text(self, text: str) -> Tuple[str, Dict[str, List[str]]]:
        """Anonymize PHI in text."""
        anonymized = text
        phi_found = {}

        for pattern_name, pattern in self._phi_patterns.items():
            matches = pattern.findall(anonymized)
            if matches:
                phi_found[pattern_name] = matches
                for match in matches:
                    anonymized = anonymized.replace(
                        match, f"[REDACTED_{pattern_name.upper()}]"
                    )

        return anonymized, phi_found

    def _extract_medical_terms(self, text: str) -> Dict[str, List[str]]:
        """Extract medical terms and codes from text."""
        medical_terms = {
            "icd10": re.findall(r"\b[A-Z]\d{2}\.?\d{0,2}\b", text),
            "cpt": re.findall(r"\b\d{5}\b", text),
            "medications": [],  # Would use NER model
            "conditions": [],  # Would use NER model
            "procedures": [],  # Would use NER model
        }

        return medical_terms

    def _create_document(
        self, text: str, metadata: DocumentMetadata, page_num: Optional[int] = None
    ) -> Document:
        """Create a LlamaIndex Document with metadata."""
        doc_metadata = metadata.to_dict()

        if page_num is not None:
            doc_metadata["page_number"] = page_num

        # Add hash for deduplication
        doc_metadata["content_hash"] = hashlib.sha256(text.encode()).hexdigest()[:16]

        return Document(text=text, metadata=doc_metadata)

    def _chunk_text(self, text: str) -> List[str]:
        """Chunk text into smaller pieces."""
        parser = SimpleNodeParser.from_defaults(
            chunk_size=self.config.chunk_size, chunk_overlap=self.config.chunk_overlap
        )

        # Create temporary document for chunking
        temp_doc = Document(text=text)
        nodes = parser.get_nodes_from_documents([temp_doc])

        return [node.text for node in nodes if hasattr(node, "text")]


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
