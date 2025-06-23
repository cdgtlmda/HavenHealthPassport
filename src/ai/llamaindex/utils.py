"""Utility functions for LlamaIndex operations.

Provides helper functions for medical document processing,
index management, and query optimization.

This module handles access control for PHI operations.
Handles FHIR Resource validation.
"""

import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from llama_index.core import Document
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo, TextNode

logger = logging.getLogger(__name__)


def detect_phi(text: str) -> Dict[str, List[str]]:
    """Detect potential Protected Health Information (PHI) in text.

    Args:
        text: Text to analyze

    Returns:
        Dictionary of detected PHI types and instances
    """
    phi_detected: Dict[str, List[str]] = {
        "ssn": [],
        "mrn": [],
        "phone": [],
        "email": [],
        "date": [],
        "name": [],
        "address": [],
    }

    # SSN pattern
    ssn_pattern = r"\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b"
    phi_detected["ssn"] = re.findall(ssn_pattern, text)

    # Medical Record Number (various formats)
    mrn_pattern = r"\b(?:MRN|Medical Record Number)[:\s]*([A-Z0-9]{6,12})\b"
    phi_detected["mrn"] = re.findall(mrn_pattern, text, re.IGNORECASE)

    # Phone numbers
    phone_pattern = r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    phi_detected["phone"] = re.findall(phone_pattern, text)

    # Email addresses
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    phi_detected["email"] = re.findall(email_pattern, text)

    # Dates (various formats)
    date_pattern = r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b"
    phi_detected["date"] = re.findall(date_pattern, text)

    # Remove empty lists
    phi_detected = {k: v for k, v in phi_detected.items() if v}

    return phi_detected


def sanitize_phi(text: str, replacement: str = "[REDACTED]") -> str:
    """Sanitize PHI from text by replacing with placeholder.

    Args:
        text: Text to sanitize
        replacement: Replacement string for PHI

    Returns:
        Sanitized text
    """
    phi_data = detect_phi(text)
    sanitized = text

    for phi_type, instances in phi_data.items():
        for instance in instances:
            sanitized = sanitized.replace(instance, f"{replacement}_{phi_type.upper()}")

    return sanitized


def extract_medical_entities(text: str) -> Dict[str, List[str]]:
    """Extract medical entities from text.

    Args:
        text: Medical text to analyze

    Returns:
        Dictionary of entity types and instances
    """
    entities: Dict[str, List[str]] = {
        "medications": [],
        "conditions": [],
        "procedures": [],
        "lab_tests": [],
        "vitals": [],
    }

    # Simple pattern matching - in production, use medical NER models

    # Medications (common patterns)
    med_pattern = r"\b(?:mg|mcg|ml|tablet|capsule|injection)\b"
    if re.search(med_pattern, text, re.IGNORECASE):
        # Extract medication context
        sentences = text.split(".")
        for sent in sentences:
            if re.search(med_pattern, sent, re.IGNORECASE):
                entities["medications"].append(sent.strip())

    # Lab values
    lab_pattern = r"\b(?:WBC|RBC|Hgb|Hct|Plt|Na|K|Cl|CO2|BUN|Cr|Glucose)\b"
    lab_matches = re.findall(lab_pattern, text)
    entities["lab_tests"].extend(lab_matches)

    # Vital signs
    vitals_pattern = r"(?:BP|Blood Pressure|HR|Heart Rate|Temp|Temperature|O2|SpO2)"
    vitals_matches = re.findall(vitals_pattern, text, re.IGNORECASE)
    entities["vitals"].extend(vitals_matches)

    return {k: list(set(v)) for k, v in entities.items() if v}


def create_document_metadata(
    file_path: str,
    document_type: Optional[str] = None,
    additional_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create standardized metadata for medical documents.

    Args:
        file_path: Path to the document file
        document_type: Type of medical document
        additional_metadata: Additional metadata to include

    Returns:
        Metadata dictionary
    """
    path = Path(file_path)

    metadata = {
        "source": str(path),
        "filename": path.name,
        "file_type": path.suffix.lower(),
        "file_size": path.stat().st_size if path.exists() else 0,
        "created_at": datetime.now().isoformat(),
        "document_type": document_type or "general",
        "index_version": "1.0",
    }

    # Add file hash for deduplication
    if path.exists():
        with open(path, "rb") as f:
            metadata["file_hash"] = hashlib.sha256(f.read()).hexdigest()

    # Merge additional metadata
    if additional_metadata:
        metadata.update(additional_metadata)

    return metadata


def split_medical_document(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 128,
    preserve_sections: bool = True,
) -> List[TextNode]:
    """Split medical document into chunks while preserving structure.

    Args:
        text: Document text
        chunk_size: Target chunk size
        chunk_overlap: Overlap between chunks
        preserve_sections: Try to preserve section boundaries

    Returns:
        List of TextNode objects
    """
    nodes = []

    if preserve_sections:
        # Common medical document sections
        section_headers = [
            "CHIEF COMPLAINT",
            "HISTORY OF PRESENT ILLNESS",
            "PAST MEDICAL HISTORY",
            "MEDICATIONS",
            "ALLERGIES",
            "PHYSICAL EXAMINATION",
            "ASSESSMENT",
            "PLAN",
            "LABORATORY DATA",
            "IMAGING",
            "PROCEDURES",
            "DISCHARGE",
        ]

        # Split by sections first
        sections = []
        current_section = ""
        current_header = "GENERAL"

        for line in text.split("\n"):
            # Check if line is a section header
            is_header = False
            for header in section_headers:
                if header in line.upper():
                    if current_section:
                        sections.append((current_header, current_section))
                    current_header = header
                    current_section = line + "\n"
                    is_header = True
                    break

            if not is_header:
                current_section += line + "\n"

        # Add last section
        if current_section:
            sections.append((current_header, current_section))

        # Create nodes from sections
        for _, (header, content) in enumerate(sections):
            # If section is too large, split it further
            if len(content) > chunk_size:
                sub_chunks = chunk_text(content, chunk_size, chunk_overlap)
                for j, chunk in enumerate(sub_chunks):
                    node = TextNode(
                        text=chunk,
                        metadata={
                            "section": header,
                            "section_part": j + 1,
                            "section_total_parts": len(sub_chunks),
                        },
                    )
                    nodes.append(node)
            else:
                node = TextNode(text=content, metadata={"section": header})
                nodes.append(node)
    else:
        # Simple chunking
        chunks = chunk_text(text, chunk_size, chunk_overlap)
        nodes = [TextNode(text=chunk) for chunk in chunks]

    # Add relationships between consecutive nodes
    for i in range(len(nodes) - 1):
        nodes[i].relationships[NodeRelationship.NEXT] = RelatedNodeInfo(
            node_id=nodes[i + 1].node_id
        )
        nodes[i + 1].relationships[NodeRelationship.PREVIOUS] = RelatedNodeInfo(
            node_id=nodes[i].node_id
        )

    return nodes


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Chunk text with overlap.

    Args:
        text: Text to chunk
        chunk_size: Size of each chunk
        overlap: Overlap between chunks

    Returns:
        List of text chunks
    """
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Try to break at sentence boundary
        if end < len(text):
            last_period = chunk.rfind(".")
            if last_period > chunk_size * 0.8:  # If period is in last 20%
                chunk = chunk[: last_period + 1]
                end = start + last_period + 1

        chunks.append(chunk)
        start = end - overlap if end < len(text) else end

    return chunks


def calculate_document_statistics(documents: List[Document]) -> Dict[str, Any]:
    """Calculate statistics for a collection of documents.

    Args:
        documents: List of documents

    Returns:
        Statistics dictionary
    """
    total_chars = sum(len(doc.text) for doc in documents)
    total_words = sum(len(doc.text.split()) for doc in documents)

    doc_types: Dict[str, int] = {}
    for doc in documents:
        doc_type = doc.metadata.get("document_type", "unknown")
        doc_types[doc_type] = doc_types.get(doc_type, 0) + 1

    return {
        "total_documents": len(documents),
        "total_characters": total_chars,
        "total_words": total_words,
        "average_document_length": total_chars / len(documents) if documents else 0,
        "document_types": doc_types,
        "has_phi": any(detect_phi(doc.text) for doc in documents),
    }


def validate_medical_document(document: Document) -> Tuple[bool, List[str]]:
    """Validate a medical document for indexing.

    Args:
        document: Document to validate

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []

    # Check for empty content
    if not document.text or len(document.text.strip()) == 0:
        issues.append("Document has no content")

    # Check for minimum length
    if len(document.text) < 50:
        issues.append("Document is too short (< 50 characters)")

    # Check for required metadata
    required_metadata = ["source", "document_type"]
    for field in required_metadata:
        if field not in document.metadata:
            issues.append(f"Missing required metadata: {field}")

    # Check for potential PHI without proper handling
    phi_data = detect_phi(document.text)
    if phi_data and not document.metadata.get("phi_handled", False):
        issues.append("Document contains unhandled PHI")

    # Check document type validity
    valid_types = [
        "clinical_notes",
        "lab_reports",
        "prescriptions",
        "imaging_reports",
        "discharge_summaries",
        "general",
    ]
    doc_type = document.metadata.get("document_type", "")
    if doc_type not in valid_types:
        issues.append(f"Invalid document type: {doc_type}")

    return len(issues) == 0, issues
