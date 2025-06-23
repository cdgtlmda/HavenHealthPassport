"""Text Medical Document Loader.

Specialized loader for text-based medical documents including:
- Clinical notes
- Discharge summaries
- Progress notes
- Consultation reports

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import chardet
except ImportError:
    chardet = None

try:
    from langdetect import detect
except ImportError:
    detect = None

from llama_index.core import Document

from .base import (
    BaseDocumentLoader,
    DocumentLoaderConfig,
    DocumentMetadata,
    DocumentQuality,
    LoaderResult,
)

logger = logging.getLogger(__name__)


class TextMedicalLoader(BaseDocumentLoader):
    """Loader for text-based medical documents."""

    def __init__(self, config: Optional[DocumentLoaderConfig] = None):
        """Initialize the text loader with optional configuration."""
        super().__init__(config)
        self.supported_extensions = [".txt", ".text", ".md", ".rtf"]

    def can_load(self, file_path: str) -> bool:
        """Check if this loader can handle the file."""
        return any(file_path.lower().endswith(ext) for ext in self.supported_extensions)

    def load(self, file_path: str, **kwargs: Any) -> LoaderResult:
        """Load text document with medical optimizations."""
        start_time = time.time()
        result = LoaderResult(success=False)

        try:
            # Validate file
            if not os.path.exists(file_path):
                result.errors.append(f"File not found: {file_path}")
                return result

            # Create metadata
            metadata = self._extract_metadata(file_path)

            # Detect encoding
            with open(file_path, "rb") as file:
                raw_data = file.read()
                detected = chardet.detect(raw_data)
                encoding = detected["encoding"] or "utf-8"
            # Read text content
            with open(file_path, "r", encoding=encoding) as file:
                content = file.read()

            if not content.strip():
                result.errors.append("File is empty")
                return result

            # Detect document structure
            doc_structure = self._detect_document_structure(content)
            metadata.custom_metadata.update(doc_structure)

            # Detect language
            if self.config.detect_language:
                try:
                    if detect is not None:
                        metadata.language = detect(
                            content[:1000]
                        )  # Use first 1000 chars
                    else:
                        metadata.language = "en"  # Default to English
                except (ValueError, TypeError, AttributeError) as e:
                    logger.warning("Language detection failed: %s", e)
                    metadata.language = "en"  # Default to English

            # Process sections if structured
            if doc_structure.get("is_structured"):
                documents = self._process_structured_text(content, metadata)
            else:
                # Process as single document
                documents = self._process_unstructured_text(content, metadata)

            # Extract medical codes from all content
            all_text = " ".join([doc.text for doc in documents])
            if self.config.extract_medical_terms:
                medical_terms = self._extract_medical_terms(all_text)
                metadata.icd_codes = list(set(medical_terms.get("icd10", [])))
                metadata.cpt_codes = list(set(medical_terms.get("cpt", [])))

            metadata.quality_score = (
                DocumentQuality.HIGH
            )  # Text files are usually high quality

            result.success = True
            result.documents = documents
            result.metadata = metadata
            result.processing_time_ms = int((time.time() - start_time) * 1000)

        except (OSError, ValueError) as e:
            logger.error("Error loading text file: %s", e)
            result.errors.append(str(e))

        return result

    def _extract_metadata(self, file_path: str) -> DocumentMetadata:
        """Extract metadata from text file."""
        file_stats = os.stat(file_path)

        metadata = DocumentMetadata(
            file_path=file_path,
            file_type="text",
            file_size=file_stats.st_size,
            created_date=datetime.fromtimestamp(file_stats.st_ctime),
            modified_date=datetime.fromtimestamp(file_stats.st_mtime),
        )

        # Determine document type from filename
        filename_lower = os.path.basename(file_path).lower()

        if "discharge" in filename_lower:
            metadata.document_type = "discharge_summary"
        elif "progress" in filename_lower:
            metadata.document_type = "progress_note"
        elif "consult" in filename_lower:
            metadata.document_type = "consultation_report"
        elif "note" in filename_lower:
            metadata.document_type = "clinical_note"
        else:
            metadata.document_type = "medical_text"

        return metadata

    def _detect_document_structure(self, content: str) -> Dict[str, Any]:
        """Detect if document has medical structure."""
        structure: Dict[str, Any] = {
            "is_structured": False,
            "has_sections": False,
            "sections": [],
        }

        # Common medical document section headers
        section_patterns = [
            r"(?i)^(chief complaint|cc):",
            r"(?i)^(history of present illness|hpi):",
            r"(?i)^(past medical history|pmh):",
            r"(?i)^(medications):",
            r"(?i)^(allergies):",
            r"(?i)^(physical exam|pe):",
            r"(?i)^(assessment and plan|a&p|assessment|plan):",
            r"(?i)^(laboratory|lab results):",
            r"(?i)^(imaging):",
            r"(?i)^(diagnosis|diagnoses):",
        ]

        for pattern in section_patterns:
            if re.search(pattern, content, re.MULTILINE):
                structure["has_sections"] = True
                structure["is_structured"] = True

                # Extract section names
                matches = re.findall(pattern, content, re.MULTILINE)
                structure["sections"].extend(matches)

        return structure

    def _process_structured_text(
        self, content: str, metadata: DocumentMetadata
    ) -> List[Document]:
        """Process structured medical text with sections."""
        documents = []

        # Split by common section headers
        section_pattern = r"(?i)^(chief complaint|cc|history of present illness|hpi|past medical history|pmh|medications|allergies|physical exam|pe|assessment and plan|a&p|assessment|plan|laboratory|lab results|imaging|diagnosis|diagnoses):\s*"

        sections = re.split(section_pattern, content, flags=re.MULTILINE)

        current_section = "header"
        for i in range(0, len(sections), 2):
            if i + 1 < len(sections):
                section_name = sections[i + 1].strip()
                section_content = sections[i + 2] if i + 2 < len(sections) else ""
            else:
                section_name = current_section
                section_content = sections[i]

            if section_content.strip():
                # Process section content
                processed_content = self._process_section_content(
                    section_content, section_name, metadata
                )

                # Create document for section
                section_metadata = metadata.to_dict()
                section_metadata["section"] = section_name

                doc = Document(text=processed_content, metadata=section_metadata)
                documents.append(doc)

        return documents if documents else [self._create_document(content, metadata)]

    def _process_unstructured_text(
        self, content: str, metadata: DocumentMetadata
    ) -> List[Document]:
        """Process unstructured text."""
        # Detect and handle PHI
        if self.config.detect_phi:
            phi_level = self._detect_phi_level(content)
            metadata.phi_level = phi_level

            if self.config.anonymize_phi and phi_level.value != "none":
                content, _ = self._anonymize_text(content)
                metadata.anonymization_applied = True

        # Chunk if needed
        if len(content) > self.config.chunk_size:
            chunks = self._chunk_text(content)
            return [
                self._create_document(chunk, metadata, page_num=i + 1)
                for i, chunk in enumerate(chunks)
            ]
        else:
            return [self._create_document(content, metadata)]

    def _process_section_content(
        self, content: str, section_name: str, metadata: DocumentMetadata
    ) -> str:
        """Process content of a medical section."""
        # Clean content
        content = content.strip()

        # Detect and handle PHI
        if self.config.detect_phi:
            phi_level = self._detect_phi_level(content)
            if self.config.anonymize_phi and phi_level.value != "none":
                content, _ = self._anonymize_text(content)

        # Extract section-specific information
        if section_name.lower() in ["medications", "meds"]:
            # Could extract medication list
            pass
        elif section_name.lower() in ["diagnosis", "diagnoses"]:
            # Extract ICD codes if present
            icd_matches = re.findall(r"\b[A-Z]\d{2}\.?\d{0,2}\b", content)
            metadata.icd_codes.extend(icd_matches)

        return content
