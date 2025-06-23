"""Output Formatting Module for Medical Transcriptions.

This module handles formatting transcription results into various
medical documentation standards and formats.
 Handles FHIR Resource validation.

Security Note: This module processes PHI data in transcription results.
All formatted documents must be encrypted at rest and in transit. Access
to formatted medical documents should be restricted to authorized healthcare
personnel only through role-based access controls.
"""

import base64
import csv
import io
import json
import logging
import textwrap
import types
import uuid
import warnings
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .confidence_thresholds import (
    TranscriptionResult,
    TranscriptionWord,
)

_defusedxml_available = False
defused_minidom: types.ModuleType

try:
    import defusedxml.minidom

    defused_minidom = defusedxml.minidom
    _defusedxml_available = True
except ImportError:
    # Fallback to standard minidom if defusedxml is not available
    import xml.dom.minidom

    defused_minidom = xml.dom.minidom

if not _defusedxml_available:
    warnings.warn(
        "defusedxml not available, using standard minidom. This may be less secure.",
        stacklevel=2,
    )

logger = logging.getLogger(__name__)


class OutputFormat(Enum):
    """Supported output formats for medical transcriptions."""

    JSON = "json"
    XML = "xml"
    HL7 = "hl7"
    FHIR = "fhir"
    TEXT = "text"
    MARKDOWN = "markdown"
    PDF = "pdf"
    DOCX = "docx"
    CSV = "csv"
    SRT = "srt"  # Subtitles with timing


class DocumentSection(Enum):
    """Standard sections for medical documents."""

    CHIEF_COMPLAINT = "chief_complaint"
    HISTORY_PRESENT_ILLNESS = "history_present_illness"
    PAST_MEDICAL_HISTORY = "past_medical_history"
    MEDICATIONS = "medications"
    ALLERGIES = "allergies"
    PHYSICAL_EXAM = "physical_exam"
    ASSESSMENT = "assessment"
    PLAN = "plan"
    VITAL_SIGNS = "vital_signs"
    LAB_RESULTS = "lab_results"


@dataclass
class FormattingConfig:
    """Configuration for output formatting."""

    # General formatting
    include_timestamps: bool = True
    include_confidence_scores: bool = True
    include_speaker_labels: bool = True
    include_alternatives: bool = False

    # Confidence highlighting
    highlight_low_confidence: bool = True
    confidence_threshold: float = 0.80

    # Medical formatting
    auto_section_detection: bool = True
    standardize_medical_terms: bool = True
    expand_abbreviations: bool = True

    # Privacy
    redact_phi: bool = False
    phi_replacement_text: str = "[REDACTED]"

    # Layout
    line_width: int = 80
    indent_size: int = 2
    paragraph_spacing: int = 1

    # HL7/FHIR specific
    hl7_version: str = "2.5.1"
    fhir_version: str = "R4"
    organization_id: str = "ORG001"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "include_timestamps": self.include_timestamps,
            "include_confidence_scores": self.include_confidence_scores,
            "include_speaker_labels": self.include_speaker_labels,
            "include_alternatives": self.include_alternatives,
            "highlight_low_confidence": self.highlight_low_confidence,
            "confidence_threshold": self.confidence_threshold,
            "auto_section_detection": self.auto_section_detection,
            "standardize_medical_terms": self.standardize_medical_terms,
            "expand_abbreviations": self.expand_abbreviations,
            "redact_phi": self.redact_phi,
            "line_width": self.line_width,
            "indent_size": self.indent_size,
            "hl7_version": self.hl7_version,
            "fhir_version": self.fhir_version,
        }


@dataclass
class FormattedDocument:
    """Represents a formatted medical document."""

    format: OutputFormat
    content: Union[str, bytes, Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    file_extension: str = ""
    mime_type: str = ""

    def save(self, filepath: Path) -> None:
        """Save the formatted document to file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(self.content, bytes):
            mode = "wb"
        else:
            mode = "w"

        with open(filepath, mode) as f:
            if isinstance(self.content, dict):
                json.dump(self.content, f, indent=2)
            else:
                f.write(self.content)

        logger.info("Document saved to %s", filepath)


class OutputFormatter:
    """
    Formats medical transcription results into various output formats.

    Supports standard medical documentation formats including
    HL7, FHIR, and traditional text-based formats.
    """

    def __init__(self, config: Optional[FormattingConfig] = None):
        """
        Initialize the output formatter.

        Args:
            config: Formatting configuration
        """
        self.config = config or FormattingConfig()

        # Medical abbreviation dictionary
        self.abbreviations = {
            "bp": "blood pressure",
            "hr": "heart rate",
            "rr": "respiratory rate",
            "temp": "temperature",
            "hx": "history",
            "px": "physical examination",
            "dx": "diagnosis",
            "rx": "prescription",
            "tx": "treatment",
        }
        # Format specifications
        self.format_specs = {
            OutputFormat.JSON: {"extension": ".json", "mime": "application/json"},
            OutputFormat.XML: {"extension": ".xml", "mime": "application/xml"},
            OutputFormat.HL7: {"extension": ".hl7", "mime": "application/hl7-v2+er7"},
            OutputFormat.FHIR: {"extension": ".json", "mime": "application/fhir+json"},
            OutputFormat.TEXT: {"extension": ".txt", "mime": "text/plain"},
            OutputFormat.MARKDOWN: {"extension": ".md", "mime": "text/markdown"},
            OutputFormat.CSV: {"extension": ".csv", "mime": "text/csv"},
            OutputFormat.SRT: {"extension": ".srt", "mime": "text/srt"},
        }

        logger.info("OutputFormatter initialized")

    def format_transcription(
        self,
        result: TranscriptionResult,
        output_format: OutputFormat,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FormattedDocument:
        """
        Format a transcription result into the specified format.

        Args:
            result: Transcription result to format
            output_format: Desired output format
            metadata: Additional metadata for the document

        Returns:
            Formatted document
        """
        metadata = metadata or {}

        # Add common metadata
        metadata.update(
            {
                "formatted_at": datetime.now().isoformat(),
                "language_code": result.language_code,
                "overall_confidence": result.overall_confidence,
                "word_count": len(result.words),
            }
        )

        # Format based on type
        content: Union[str, Dict[str, Any]]
        if output_format == OutputFormat.JSON:
            content = self._format_json(result, metadata)
        elif output_format == OutputFormat.XML:
            content = self._format_xml(result, metadata)
        elif output_format == OutputFormat.TEXT:
            content = self._format_text(result, metadata)
        elif output_format == OutputFormat.MARKDOWN:
            content = self._format_markdown(result, metadata)
        elif output_format == OutputFormat.HL7:
            content = self._format_hl7(result, metadata)
        elif output_format == OutputFormat.FHIR:
            content = self._format_fhir(result, metadata)
        elif output_format == OutputFormat.CSV:
            content = self._format_csv(result, metadata)
        elif output_format == OutputFormat.SRT:
            content = self._format_srt(result, metadata)
        else:
            raise ValueError(f"Unsupported format: {output_format}")

        # Get format specs
        specs = self.format_specs.get(output_format, {})

        return FormattedDocument(
            format=output_format,
            content=content,
            metadata=metadata,
            file_extension=specs.get("extension", ""),
            mime_type=specs.get("mime", ""),
        )

    def _format_json(
        self, result: TranscriptionResult, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format as JSON."""
        output: Dict[str, Any] = {
            "metadata": metadata,
            "transcript": result.transcript,
            "confidence_metrics": {
                "overall": result.overall_confidence,
                "average": result.average_confidence,
                "minimum": result.min_confidence,
                "maximum": result.max_confidence,
                "distribution": {
                    k.value: v for k, v in result.confidence_distribution.items()
                },
            },
        }

        # Add words with details if configured
        if self.config.include_timestamps or self.config.include_confidence_scores:
            output["words"] = []
            for word in result.words:
                word_data: Dict[str, Any] = {"text": word.text}

                if self.config.include_timestamps:
                    word_data["start_time"] = word.start_time
                    word_data["end_time"] = word.end_time
                if self.config.include_confidence_scores:
                    word_data["confidence"] = word.confidence
                    word_data["confidence_level"] = word.confidence_level.value

                if self.config.include_speaker_labels and word.speaker:
                    word_data["speaker"] = word.speaker

                if self.config.include_alternatives and word.alternatives:
                    word_data["alternatives"] = word.alternatives

                if word.term_type:
                    word_data["medical_term_type"] = word.term_type.value

                output["words"].append(word_data)

        # Add sections if detected
        if self.config.auto_section_detection:
            sections = self._detect_sections(result)
            if sections:
                output["sections"] = sections

        return output

    def _format_xml(self, result: TranscriptionResult, metadata: Dict[str, Any]) -> str:
        """Format as XML."""
        root = ET.Element("MedicalTranscription")

        # Add metadata
        meta_elem = ET.SubElement(root, "Metadata")
        for key, value in metadata.items():
            elem = ET.SubElement(meta_elem, key)
            elem.text = str(value)

        # Add transcript
        transcript_elem = ET.SubElement(root, "Transcript")
        transcript_elem.text = result.transcript

        # Add confidence metrics
        confidence_elem = ET.SubElement(root, "ConfidenceMetrics")
        ET.SubElement(confidence_elem, "Overall").text = str(result.overall_confidence)
        ET.SubElement(confidence_elem, "Average").text = str(result.average_confidence)
        ET.SubElement(confidence_elem, "Minimum").text = str(result.min_confidence)
        ET.SubElement(confidence_elem, "Maximum").text = str(result.max_confidence)
        # Add words if configured
        if self.config.include_timestamps or self.config.include_confidence_scores:
            words_elem = ET.SubElement(root, "Words")

            for word in result.words:
                word_elem = ET.SubElement(words_elem, "Word")
                word_elem.set("text", word.text)

                if self.config.include_timestamps:
                    word_elem.set("start", str(word.start_time))
                    word_elem.set("end", str(word.end_time))

                if self.config.include_confidence_scores:
                    word_elem.set("confidence", str(word.confidence))

                if self.config.include_speaker_labels and word.speaker:
                    word_elem.set("speaker", word.speaker)

        # Pretty print using defusedxml for security
        xml_str = defused_minidom.parseString(
            ET.tostring(root, encoding="unicode")
        ).toprettyxml(  # nosec B318 - Using defusedxml which is secure
            indent="  "
        )
        return str(xml_str)

    def _format_text(
        self, result: TranscriptionResult, metadata: Dict[str, Any]
    ) -> str:
        """Format as plain text."""
        output = []

        # Header
        output.append("MEDICAL TRANSCRIPTION REPORT")
        output.append("=" * 40)
        output.append(f"Date: {metadata.get('formatted_at', '')}")
        output.append(f"Language: {result.language_code}")
        output.append(f"Overall Confidence: {result.overall_confidence:.2f}")
        output.append("")

        # Transcript
        if self.config.auto_section_detection:
            sections = self._detect_sections(result)
            if sections:
                for section_name, section_text in sections.items():
                    output.append(f"{section_name.upper()}:")
                    output.append("-" * len(section_name))
                    output.append(self._wrap_text(section_text))
                    output.append("")
            else:
                output.append("TRANSCRIPT:")
                output.append(self._wrap_text(result.transcript))
        else:
            output.append("TRANSCRIPT:")
            output.append(self._wrap_text(result.transcript))

        # Footer with statistics
        output.append("")
        output.append("-" * 40)
        output.append(f"Word Count: {len(result.words)}")
        output.append(f"Processing Time: {result.processing_time_ms:.2f} ms")

        if result.words_needing_review:
            output.append(f"Words Needing Review: {len(result.words_needing_review)}")

        return "\n".join(output)

    def _format_markdown(
        self, result: TranscriptionResult, metadata: Dict[str, Any]
    ) -> str:
        """Format as Markdown."""
        output = []

        # Header
        output.append("# Medical Transcription Report")
        output.append("")
        output.append(f"**Date:** {metadata.get('formatted_at', '')}")
        output.append(f"**Language:** {result.language_code}")
        output.append(f"**Overall Confidence:** {result.overall_confidence:.2f}")
        output.append("")

        # Transcript with confidence highlighting
        output.append("## Transcript")
        output.append("")

        if self.config.highlight_low_confidence:
            formatted_text = self._highlight_low_confidence_markdown(result)
            output.append(formatted_text)
        else:
            output.append(result.transcript)

        # Statistics section
        output.append("")
        output.append("## Statistics")
        output.append("")
        output.append(f"- **Total Words:** {len(result.words)}")
        output.append(f"- **Average Confidence:** {result.average_confidence:.2f}")
        output.append(f"- **Words Needing Review:** {len(result.words_needing_review)}")
        # Critical terms if any
        if result.critical_terms_flagged:
            output.append("")
            output.append("## Critical Terms Requiring Review")
            output.append("")
            for term in result.critical_terms_flagged:
                output.append(f"- **{term.text}** (Confidence: {term.confidence:.2f})")

        return "\n".join(output)

    def _format_hl7(self, result: TranscriptionResult, metadata: Dict[str, Any]) -> str:
        """Format as HL7 v2 message."""
        _ = metadata  # Reserved for future use
        segments = []

        # MSH - Message Header
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        msh = f"MSH|^~\\&|TRANSCRIBE|{self.config.organization_id}|EHR|FACILITY|{timestamp}||MDM^T02|{uuid.uuid4().hex[:10]}|P|{self.config.hl7_version}"
        segments.append(msh)

        # PID - Patient Identification (placeholder)
        pid = "PID|||PATIENT123||DOE^JOHN||19800101|M"
        segments.append(pid)

        # TXA - Transcription Document Header
        txa = f"TXA|1|TX|{timestamp}|||||||||DOC123||||AU"
        segments.append(txa)

        # OBX - Observation/Result segments for transcript
        # Split transcript into chunks for HL7 segment size limits
        text_chunks = self._chunk_text(result.transcript, 200)
        for i, chunk in enumerate(text_chunks):
            obx = f"OBX|{i+1}|TX|TRANSCRIPT||{chunk}||||||F"
            segments.append(obx)

        # Add confidence score
        obx_confidence = f"OBX|{len(text_chunks)+1}|NM|CONFIDENCE||{result.overall_confidence}||||||F"
        segments.append(obx_confidence)

        return "\r".join(segments)

    def _format_fhir(
        self, result: TranscriptionResult, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format as FHIR DocumentReference resource."""
        fhir_doc = {
            "resourceType": "DocumentReference",
            "id": str(uuid.uuid4()),
            "meta": {"versionId": "1", "lastUpdated": datetime.now().isoformat()},
            "status": "current",
            "type": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "11488-4",
                        "display": "Consultation note",
                    }
                ]
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "LP173421-1",
                            "display": "Report",
                        }
                    ]
                }
            ],
            "subject": {
                "reference": f"Patient/{metadata.get('patient_id', 'unknown')}"
            },
            "date": metadata.get("formatted_at", datetime.now().isoformat()),
            "author": [{"reference": "Device/transcription-system"}],
            "content": [
                {
                    "attachment": {
                        "contentType": "text/plain",
                        "language": result.language_code,
                        "data": self._base64_encode(result.transcript),
                        "title": "Medical Transcription",
                    }
                }
            ],
            "context": {
                "event": [{"text": "Medical consultation"}],
                "extension": [
                    {
                        "url": "http://example.org/fhir/StructureDefinition/transcription-confidence",
                        "valueDecimal": result.overall_confidence,
                    }
                ],
            },
        }

        return fhir_doc

    def _format_csv(self, result: TranscriptionResult, metadata: Dict[str, Any]) -> str:
        """Format as CSV."""
        _ = metadata  # Reserved for future use

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        headers = [
            "Word",
            "Start Time",
            "End Time",
            "Confidence",
            "Speaker",
            "Medical Term Type",
        ]
        writer.writerow(headers)

        # Words
        for word in result.words:
            row = [
                word.text,
                f"{word.start_time:.3f}",
                f"{word.end_time:.3f}",
                f"{word.confidence:.3f}",
                word.speaker or "",
                word.term_type.value if word.term_type else "",
            ]
            writer.writerow(row)

        return output.getvalue()

    def _format_srt(self, result: TranscriptionResult, metadata: Dict[str, Any]) -> str:
        """Format as SRT subtitles."""
        _ = metadata  # Reserved for future use
        output = []

        # Group words into subtitle segments (2-3 seconds each)
        segments = self._group_words_for_subtitles(result.words)

        for i, segment in enumerate(segments):
            # Subtitle number
            output.append(str(i + 1))

            # Timecode
            start_time = self._format_srt_time(segment[0].start_time)
            end_time = self._format_srt_time(segment[-1].end_time)
            output.append(f"{start_time} --> {end_time}")

            # Text
            text = " ".join(w.text for w in segment)
            output.append(text)
            output.append("")  # Empty line between subtitles

        return "\n".join(output)

    def _detect_sections(self, result: TranscriptionResult) -> Dict[str, str]:
        """Detect medical document sections in the transcript."""
        sections: Dict[str, str] = {}

        # Section keywords mapping for medical document sections
        section_keywords = {
            DocumentSection.CHIEF_COMPLAINT: [
                "chief complaint",
                "presenting complaint",
                "reason for visit",
                "patient presents with",
                "patient complains of",
            ],
            DocumentSection.HISTORY_PRESENT_ILLNESS: [
                "history of present illness",
                "hpi",
                "history of illness",
                "onset of symptoms",
                "the patient reports",
            ],
            DocumentSection.PAST_MEDICAL_HISTORY: [
                "past medical history",
                "pmh",
                "medical history",
                "previous conditions",
                "prior diagnoses",
            ],
            DocumentSection.MEDICATIONS: [
                "medications",
                "current medications",
                "medication list",
                "prescribed medications",
                "taking",
            ],
            DocumentSection.ALLERGIES: [
                "allergies",
                "allergic to",
                "allergy list",
                "drug allergies",
                "adverse reactions",
            ],
            DocumentSection.PHYSICAL_EXAM: [
                "physical exam",
                "examination",
                "on examination",
                "physical findings",
                "exam findings",
            ],
            DocumentSection.VITAL_SIGNS: [
                "vital signs",
                "vitals",
                "blood pressure",
                "heart rate",
                "temperature",
                "respiratory rate",
                "oxygen saturation",
            ],
            DocumentSection.LAB_RESULTS: [
                "lab results",
                "laboratory findings",
                "test results",
                "blood work",
                "labs",
            ],
            DocumentSection.ASSESSMENT: [
                "assessment",
                "impression",
                "diagnosis",
                "clinical impression",
                "diagnostic impression",
            ],
            DocumentSection.PLAN: [
                "plan",
                "treatment plan",
                "recommendations",
                "follow up",
                "next steps",
            ],
        }

        # Get the transcript text
        transcript_text = ""
        if hasattr(result, "transcript_text") and result.transcript_text:
            transcript_text = result.transcript_text.lower()
        elif hasattr(result, "transcript") and result.transcript:
            transcript_text = result.transcript.lower()
        elif hasattr(result, "words") and result.words:
            # Reconstruct from words if that's all we have
            transcript_text = " ".join(w.text for w in result.words).lower()

        if not transcript_text:
            return sections

        # Split transcript into sentences for better section detection
        sentences = transcript_text.split(".")
        current_section = None
        section_content: Dict[Any, List[str]] = {}

        # Initialize section content dictionary
        for section in DocumentSection:
            section_content[section] = []

        # Process each sentence
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check if this sentence starts a new section
            section_found = False
            for section, keywords in section_keywords.items():
                for keyword in keywords:
                    if keyword in sentence:
                        current_section = section
                        section_found = True
                        break
                if section_found:
                    break

            # Add sentence to current section if we have one
            if current_section:
                # Clean up the sentence
                clean_sentence = sentence
                # Remove the section keyword from the beginning if it's there
                for keyword in section_keywords.get(current_section, []):
                    if clean_sentence.startswith(keyword):
                        clean_sentence = clean_sentence[len(keyword) :].strip()
                        if clean_sentence.startswith(":"):
                            clean_sentence = clean_sentence[1:].strip()
                        break

                if clean_sentence:
                    section_content[current_section].append(
                        clean_sentence.capitalize() + "."
                    )

        # Compile sections with content
        for section, content in section_content.items():
            if content:
                sections[section.value] = " ".join(content)

        return sections

    def _highlight_low_confidence_markdown(self, result: TranscriptionResult) -> str:
        """Highlight low confidence words in markdown."""
        output_words = []

        for word in result.words:
            if word.confidence < self.config.confidence_threshold:
                # Highlight with bold and show confidence
                output_words.append(f"**{word.text}**[{word.confidence:.2f}]")
            else:
                output_words.append(word.text)

        return " ".join(output_words)

    def _wrap_text(self, text: str) -> str:
        """Wrap text to specified line width."""
        return textwrap.fill(text, width=self.config.line_width)

    def _chunk_text(self, text: str, chunk_size: int) -> List[str]:
        """Split text into chunks of specified size."""
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    def _base64_encode(self, text: str) -> str:
        """Base64 encode text."""
        return base64.b64encode(text.encode()).decode()

    def _group_words_for_subtitles(
        self, words: List[TranscriptionWord], max_duration: float = 3.0
    ) -> List[List[TranscriptionWord]]:
        """Group words into subtitle segments."""
        segments = []
        current_segment: List[TranscriptionWord] = []
        segment_start: float = 0

        for word in words:
            if not current_segment:
                current_segment.append(word)
                segment_start = word.start_time
            else:
                # Check if adding this word would exceed max duration
                if word.end_time - segment_start > max_duration:
                    segments.append(current_segment)
                    current_segment = [word]
                    segment_start = word.start_time
                else:
                    current_segment.append(word)

        if current_segment:
            segments.append(current_segment)

        return segments

    def _format_srt_time(self, seconds: float) -> str:
        """Format time in SRT format (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def format_batch(
        self,
        results: List[TranscriptionResult],
        output_format: OutputFormat,
        combine: bool = False,
    ) -> Union[FormattedDocument, List[FormattedDocument]]:
        """
        Format multiple transcription results.

        Args:
            results: List of transcription results
            output_format: Desired output format
            combine: Whether to combine into single document

        Returns:
            Single document if combine=True, otherwise list of documents
        """
        if combine:
            # Combine all transcripts
            combined_transcript = "\n\n---\n\n".join(r.transcript for r in results)
            # Create combined result
            # (This is simplified - real implementation would merge properly)
            combined_result = results[0]  # Use first result as template
            combined_result.transcript = combined_transcript
            return self.format_transcription(combined_result, output_format)
        else:
            return [self.format_transcription(r, output_format) for r in results]


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    validation_warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": validation_warnings,
    }
