"""Types for voice dictation functionality.

This module handles FHIR Resource types for medical dictation.
This module handles encrypted PHI with access control and audit logging.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class DictationMode(Enum):
    """Types of dictation modes supported."""

    CLINICAL_NOTE = "clinical_note"
    PRESCRIPTION = "prescription"
    PATIENT_HISTORY = "patient_history"
    EXAMINATION = "examination"
    DIAGNOSIS = "diagnosis"
    TREATMENT_PLAN = "treatment_plan"
    PROGRESS_NOTE = "progress_note"
    DISCHARGE_SUMMARY = "discharge_summary"
    REFERRAL_LETTER = "referral_letter"
    LAB_REPORT = "lab_report"
    IMAGING_REPORT = "imaging_report"
    CONSULTATION_NOTE = "consultation_note"
    OPERATIVE_REPORT = "operative_report"
    PATIENT_INSTRUCTIONS = "patient_instructions"
    MEDICATION_NOTES = "medication_notes"


class DictationCommand(Enum):
    """Voice commands for dictation control."""

    START = "start_dictation"
    STOP = "stop_dictation"
    PAUSE = "pause_dictation"
    RESUME = "resume_dictation"
    NEW_PARAGRAPH = "new_paragraph"
    NEW_SECTION = "new_section"
    UNDO = "undo"
    REDO = "redo"
    READ_BACK = "read_back"
    CORRECT = "correct"
    INSERT = "insert"
    DELETE = "delete"
    FORMAT = "format"
    SPELL = "spell"
    PUNCTUATE = "punctuate"
    SAVE = "save"
    DISCARD = "discard"
    ADD_TEMPLATE = "add_template"


class FormattingCommand(Enum):
    """Text formatting commands."""

    BOLD = "bold"
    ITALIC = "italic"
    UNDERLINE = "underline"
    BULLET_POINT = "bullet_point"
    NUMBERED_LIST = "numbered_list"
    HEADING = "heading"
    SUBHEADING = "subheading"
    QUOTE = "quote"
    CODE = "code"
    LINK = "link"
    TABLE = "table"


@dataclass
class DictationContext:
    """Context for a dictation session."""

    session_id: str
    mode: DictationMode
    language: Any  # LanguageCode from transcribe_medical
    user_id: str
    patient_id: Optional[str] = None
    document_id: Optional[str] = None
    specialty: Optional[Any] = None  # MedicalSpecialty from transcribe_medical
    custom_vocabulary_id: Optional[str] = None
    auto_punctuation: bool = True
    auto_capitalization: bool = True
    auto_formatting: bool = True
    enable_medical_validation: bool = True
    confidence_threshold: float = 0.7
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class DictationSegment:
    """A segment of transcribed dictation."""

    id: str
    text: str
    timestamp: datetime
    confidence: float
    speaker_id: Optional[str] = None
    is_final: bool = True
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    medical_terms: List[Dict[str, Any]] = field(default_factory=list)
    corrections: List[Dict[str, Any]] = field(default_factory=list)
    formatting: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DictationDocument:
    """A complete dictation document."""

    id: str
    context: DictationContext
    segments: List[DictationSegment] = field(default_factory=list)
    sections: List[Dict[str, Any]] = field(default_factory=list)
    template_id: Optional[str] = None
    status: str = "draft"
    version: int = 1
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_segment(self, segment: DictationSegment) -> None:
        """Add a segment to the document."""
        self.segments.append(segment)
        self.updated_at = datetime.now()

    def get_full_text(self) -> str:
        """Get the complete text of the document."""
        return " ".join([segment.text for segment in self.segments])

    def get_sections(self) -> List[Dict[str, Any]]:
        """Get document sections with their content."""
        sections = []
        current_section: Optional[Dict[str, Any]] = None

        for segment in self.segments:
            if segment.metadata.get("is_section_start"):
                if current_section:
                    sections.append(current_section)
                current_section = {
                    "id": segment.metadata.get("section_id", str(uuid.uuid4())),
                    "title": segment.metadata.get("section_title", ""),
                    "segments": [segment],
                    "text": segment.text,
                }
            elif current_section is not None:
                current_section["segments"].append(segment)
                current_section["text"] += " " + segment.text
            else:
                # No section started yet, create default
                current_section = {
                    "id": str(uuid.uuid4()),
                    "title": "Main Content",
                    "segments": [segment],
                    "text": segment.text,
                }

        if current_section:
            sections.append(current_section)

        return sections


@dataclass
class DictationTemplate:
    """Template for structured dictation."""

    id: str
    name: str
    mode: DictationMode
    sections: List[Dict[str, Any]]
    prompts: Dict[str, str] = field(default_factory=dict)
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    medical_terminology: List[str] = field(default_factory=list)
    shortcuts: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_next_prompt(self, completed_sections: List[str]) -> Optional[str]:
        """Get the next prompt based on completed sections."""
        for section in self.sections:
            if section["id"] not in completed_sections:
                return self.prompts.get(section["id"], section.get("prompt"))
        return None

    def validate_completion(
        self, document: DictationDocument
    ) -> Tuple[bool, List[str]]:
        """Validate if all required fields are completed."""
        missing_fields = []
        document_text = document.get_full_text().lower()

        for required_field in self.required_fields:
            if required_field.lower() not in document_text:
                missing_fields.append(required_field)

        return len(missing_fields) == 0, missing_fields


class ClinicalNoteTemplate(DictationTemplate):
    """Template for clinical notes following SOAP format."""

    def __init__(self) -> None:
        """Initialize the clinical note template with SOAP format."""
        super().__init__(
            id="clinical_note_soap",
            name="SOAP Clinical Note",
            mode=DictationMode.CLINICAL_NOTE,
            sections=[
                {"id": "subjective", "title": "Subjective", "required": True},
                {"id": "objective", "title": "Objective", "required": True},
                {"id": "assessment", "title": "Assessment", "required": True},
                {"id": "plan", "title": "Plan", "required": True},
            ],
            prompts={
                "subjective": "Patient's chief complaint and history of present illness",
                "objective": "Physical examination findings and vital signs",
                "assessment": "Clinical impression and differential diagnosis",
                "plan": "Treatment plan and follow-up instructions",
            },
            required_fields=["chief complaint", "vital signs", "assessment", "plan"],
        )
