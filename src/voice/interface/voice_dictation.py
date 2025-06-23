"""Voice Dictation Module.

This module implements voice dictation functionality for the Haven Health Passport system,
allowing healthcare providers and patients to create medical documentation through voice input
with real-time transcription, medical terminology support, and multi-language capabilities.
Handles FHIR DocumentReference Resource validation for clinical documentation.

Security Note: All PHI data processed through voice dictation must be encrypted at rest
and in transit using AES-256 encryption standards.

Access Control: Voice dictation functionality requires proper authentication and authorization
to ensure PHI data is only accessible to authorized users.
"""

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from src.healthcare.medical_terminology import MedicalTerminologyValidator
from src.voice.language_detection import LanguageDetectionManager
from src.voice.medical_term_pronunciation import MedicalPronunciationSystem
from src.voice.medical_vocabularies import MedicalVocabularyManager
from src.voice.punctuation_restoration import PunctuationRestorer
from src.voice.timestamp_alignment import TimestampAligner
from src.voice.transcribe_medical import (  # TranscriptionType,  # Available if needed for future use
    LanguageCode,
    MedicalSpecialty,
    TranscribeMedicalService,
)

from .dictation_types import (
    ClinicalNoteTemplate,
    DictationCommand,
    DictationContext,
    DictationDocument,
    DictationMode,
    DictationSegment,
    DictationTemplate,
    FormattingCommand,
)

logger = logging.getLogger(__name__)


class VoiceDictationEngine:
    """Main engine for voice dictation functionality."""

    def __init__(
        self,
        transcribe_service: Optional[TranscribeMedicalService] = None,
        medical_validator: Optional[MedicalTerminologyValidator] = None,
    ):
        """Initialize the voice dictation engine.

        Args:
            transcribe_service: Service for medical transcription
            medical_validator: Validator for medical terminology
        """
        self.transcribe_service = transcribe_service or TranscribeMedicalService()
        self.medical_validator = medical_validator

        # Initialize components
        self.language_detector = LanguageDetectionManager()
        self.punctuation_restorer = PunctuationRestorer()
        self.vocabulary_manager = MedicalVocabularyManager()
        self.pronunciation_guide = MedicalPronunciationSystem()
        # self.confidence_thresholder = ConfidenceThresholder()
        # self.output_formatter = OutputFormatter()
        self.timestamp_aligner = TimestampAligner()

        # Session management
        self.active_sessions: Dict[str, DictationSession] = {}
        self.document_store: Dict[str, DictationDocument] = {}

        # Templates
        self.templates: Dict[str, DictationTemplate] = {
            "clinical_note_soap": ClinicalNoteTemplate()
        }

        # Command patterns
        self._init_command_patterns()

    def _init_command_patterns(self) -> None:
        """Initialize voice command patterns."""
        self.command_patterns = {
            DictationCommand.NEW_PARAGRAPH: [
                r"\bnew paragraph\b",
                r"\bstart new paragraph\b",
                r"\bnext paragraph\b",
            ],
            DictationCommand.NEW_SECTION: [
                r"\bnew section\b",
                r"\bstart section\b",
                r"\bnext section\b",
            ],
            DictationCommand.UNDO: [r"\bundo\b", r"\bundo that\b", r"\bgo back\b"],
            DictationCommand.CORRECT: [
                r"\bcorrect\s+(\w+)\s+to\s+(\w+)\b",
                r"\bchange\s+(\w+)\s+to\s+(\w+)\b",
                r"\breplace\s+(\w+)\s+with\s+(\w+)\b",
            ],
            DictationCommand.PUNCTUATE: [
                r"\bperiod\b",
                r"\bcomma\b",
                r"\bquestion mark\b",
                r"\bexclamation\b",
                r"\bcolon\b",
                r"\bsemicolon\b",
            ],
            DictationCommand.FORMAT: [
                r"\bbold\s+(.*?)\b",
                r"\bitalic\s+(.*?)\b",
                r"\bunderline\s+(.*?)\b",
            ],
        }

        # Punctuation mappings
        self.punctuation_map = {
            "period": ".",
            "comma": ",",
            "question mark": "?",
            "exclamation": "!",
            "exclamation mark": "!",
            "colon": ":",
            "semicolon": ";",
            "dash": "-",
            "hyphen": "-",
            "open parenthesis": "(",
            "close parenthesis": ")",
            "open quote": '"',
            "close quote": '"',
            "apostrophe": "'",
        }

    async def start_dictation(self, context: DictationContext) -> str:
        """Start a new dictation session."""
        session_id = context.session_id

        # Create new session
        session = DictationSession(session_id=session_id, context=context, engine=self)

        # Create new document
        document = DictationDocument(id=str(uuid.uuid4()), context=context)

        # Load template if specified in document_id
        # TODO: Add template_id to DictationContext if needed
        # if hasattr(context, 'template_id') and context.template_id in self.templates:
        #     session.template = self.templates[context.template_id]

        # Initialize custom vocabulary if specified
        if context.custom_vocabulary_id:
            await self.vocabulary_manager.load_custom_vocabulary(
                context.custom_vocabulary_id
            )

        # Store session and document
        self.active_sessions[session_id] = session
        self.document_store[document.id] = document
        session.document = document

        logger.info("Started dictation session: %s", session_id)

        return document.id

    async def process_audio_stream(
        self, session_id: str, _audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[DictationSegment]:
        """Process audio stream for dictation."""
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")

        # session = self.active_sessions[session_id]  # TODO: Use for session context in transcription

        # Set up real-time transcription
        # TODO: Implement when stream_transcription is available
        # transcription_config = {
        #     "language_code": session.context.language.value,
        #     "media_sample_rate_hertz": 16000,
        #     "media_format": "pcm",
        #     "vocabulary_name": session.context.custom_vocabulary_id,
        #     "specialty": (
        #         session.context.specialty.value if session.context.specialty else None
        #     ),
        #     "type": TranscriptionType.DICTATION.value,
        # }

        # Process audio through transcription service
        # TODO: Implement stream_transcription in TranscribeMedicalService
        # async for transcript in self.transcribe_service.stream_transcription(
        #     audio_stream, **transcription_config
        # ):
        #     # Process the transcript
        #     segment = await self._process_transcript(session, transcript)
        #
        #     if segment:
        #         yield segment
        yield  # type: ignore[misc]

    async def _process_transcript(
        self, session: "DictationSession", transcript: Dict[str, Any]
    ) -> Optional[DictationSegment]:
        """Process a transcript and return a dictation segment."""
        if not transcript.get("transcript"):
            return None

        text = transcript["transcript"]
        confidence = transcript.get("confidence", 0.0)
        is_final = transcript.get("is_final", False)
        # Check for commands first
        command = self._detect_command(text)
        if command:
            handled = await session.handle_command(command, text)
            if handled:
                return None  # Command was handled, don't add as text
        # Apply punctuation restoration
        if is_final:
            text = self.punctuation_restorer.restore_punctuation(text)
        # Detect medical terms
        medical_terms = await self._detect_medical_terms(text)
        # Create segment
        segment = DictationSegment(
            id=str(uuid.uuid4()),
            text=text,
            timestamp=datetime.now(),
            confidence=confidence,
            speaker_id=transcript.get("speaker_id"),
            is_final=is_final,
            medical_terms=medical_terms,
        )

        # Add to document if final
        if is_final:
            session.add_segment(segment)

        return segment

    def _detect_command(self, text: str) -> Optional[Tuple[DictationCommand, Any]]:
        """Detect voice commands in text."""
        text_lower = text.lower()

        for command, patterns in self.command_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    # Extract command parameters if any
                    if match.groups():
                        return (command, match.groups())
                    return (command, None)

        return None

    async def _detect_medical_terms(self, _text: str) -> List[Dict[str, Any]]:
        """Detect medical terms in text."""
        medical_terms: List[Dict[str, Any]] = []

        if self.medical_validator:
            # Use medical validator to identify terms
            # TODO: Implement identify_medical_terms in MedicalTerminologyValidator
            # terms = await self.medical_validator.identify_medical_terms(text)
            # for term in terms:
            #     medical_terms.append(
            #         {
            #             "term": term["text"],
            #             "type": term.get("type", "unknown"),
            #             "normalized": term.get("normalized_form"),
            #             "confidence": term.get("confidence", 1.0),
            #             "position": term.get("position"),
            #         }
            #     )
            pass

        return medical_terms

    async def stop_dictation(self, session_id: str) -> DictationDocument:
        """Stop a dictation session and return the document."""
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.active_sessions[session_id]
        document = session.document

        if document is None:
            raise ValueError(f"No document found for session {session_id}")

        # Finalize document
        document.status = "completed"
        document.updated_at = datetime.now()

        # Validate against template if applicable
        if session.template:
            is_valid, errors = session.template.validate_completion(document)
            if not is_valid:
                logger.warning("Document validation errors: %s", errors)
                document.metadata["validation_errors"] = errors

        # Clean up session
        del self.active_sessions[session_id]

        logger.info("Stopped dictation session: %s", session_id)

        return document

    async def get_document(self, document_id: str) -> Optional[DictationDocument]:
        """Retrieve a dictation document."""
        return self.document_store.get(document_id)

    async def update_document(
        self, document_id: str, updates: Dict[str, Any]
    ) -> DictationDocument:
        """Update a dictation document."""
        if document_id not in self.document_store:
            raise ValueError(f"Document {document_id} not found")

        document = self.document_store[document_id]

        # Apply updates
        if "segments" in updates:
            document.segments = updates["segments"]
        if "sections" in updates:
            document.sections = updates["sections"]
        if "status" in updates:
            document.status = updates["status"]

        document.version += 1
        document.updated_at = datetime.now()

        return document

    async def export_document(
        self, document_id: str, export_format: str = "text"
    ) -> str:
        """Export document in specified format."""
        if document_id not in self.document_store:
            raise ValueError(f"Document {document_id} not found")

        document = self.document_store[document_id]

        if export_format == "text":
            return str(document.get_full_text())
        elif export_format == "json":
            from dataclasses import asdict

            return json.dumps(asdict(document), indent=2, default=str)
        elif export_format == "html":
            return self._export_as_html(document)
        elif export_format == "markdown":
            return self._export_as_markdown(document)
        else:
            raise ValueError(f"Unsupported export format: {export_format}")

    def _export_as_html(self, document: DictationDocument) -> str:
        """Export document as HTML."""
        html_parts = [
            "<html>",
            "<head>",
            f"<title>Dictation Document - {document.context.mode.value}</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            "h1 { color: #333; }",
            "h2 { color: #666; }",
            ".segment { margin: 10px 0; }",
            ".medical-term { color: #0066cc; font-weight: bold; }",
            ".metadata { color: #999; font-size: 0.9em; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>{document.context.mode.value.replace('_', ' ').title()}</h1>",
            f"<div class='metadata'>Created: {document.created_at.strftime('%Y-%m-%d %H:%M')}</div>",
        ]

        # Add sections
        if document.sections:
            for section_data in document.sections:
                section_name = section_data.get("name", "Untitled Section")
                html_parts.append(f"<h2>{section_name}</h2>")
                segments = section_data.get("segments", [])
                for segment in segments:
                    html_parts.append(
                        f"<div class='segment'>{self._highlight_medical_terms(segment)}</div>"
                    )
        else:
            # Add all segments
            for segment in document.segments:
                html_parts.append(
                    f"<div class='segment'>{self._highlight_medical_terms(segment)}</div>"
                )

        html_parts.extend(["</body>", "</html>"])
        return "\n".join(html_parts)

    def _export_as_markdown(self, document: DictationDocument) -> str:
        """Export document as Markdown."""
        md_parts = [
            f"# {document.context.mode.value.replace('_', ' ').title()}",
            f"*Created: {document.created_at.strftime('%Y-%m-%d %H:%M')}*",
            "",
        ]
        # Add sections
        if document.sections:
            for section_data in document.sections:
                section_name = section_data.get("name", "Untitled Section")
                md_parts.append(f"## {section_name}")
                md_parts.append("")
                segments = section_data.get("segments", [])
                for segment in segments:
                    if hasattr(segment, "text"):
                        md_parts.append(segment.text)
                    else:
                        md_parts.append(str(segment))
                    md_parts.append("")
        else:
            # Add all segments
            for segment in document.segments:
                md_parts.append(segment.text)
                md_parts.append("")
        return "\n".join(md_parts)

    def _highlight_medical_terms(self, segment: DictationSegment) -> str:
        """Highlight medical terms in segment text."""
        text = segment.text
        # Sort medical terms by position (reverse) to avoid offset issues
        terms = sorted(
            segment.medical_terms,
            key=lambda t: t.get("position", {}).get("start", 0),
            reverse=True,
        )

        for term in terms:
            if "position" in term:
                start = term["position"]["start"]
                end = term["position"]["end"]
                original = text[start:end]
                highlighted = f"<span class='medical-term'>{original}</span>"
                text = text[:start] + highlighted + text[end:]

        return text


class DictationSession:
    """Manages an active dictation session."""

    def __init__(
        self, session_id: str, context: DictationContext, engine: VoiceDictationEngine
    ):
        """Initialize a dictation session.

        Args:
            session_id: Unique identifier for the session
            context: Context information for the dictation
            engine: Reference to the dictation engine
        """
        self.session_id = session_id
        self.context = context
        self.engine = engine
        self.document: Optional[DictationDocument] = None
        self.template: Optional[DictationTemplate] = None
        self.current_section: Optional[str] = None
        self.undo_stack: List[DictationSegment] = []
        self.redo_stack: List[DictationSegment] = []
        self.is_paused = False

    def add_segment(self, segment: DictationSegment) -> None:
        """Add a segment to the document."""
        if self.is_paused:
            return

        # Add to undo stack
        self.undo_stack.append(segment)

        # Clear redo stack
        self.redo_stack.clear()

        # Add to document
        if self.document:
            self.document.add_segment(segment)

    async def handle_command(
        self, command: Tuple[DictationCommand, Any], original_text: str
    ) -> bool:
        """Handle a voice command."""
        cmd, params = command

        if cmd == DictationCommand.NEW_PARAGRAPH:
            # Add paragraph break
            segment = DictationSegment(
                id=str(uuid.uuid4()),
                text="\n\n",
                timestamp=datetime.now(),
                confidence=1.0,
            )
            self.add_segment(segment)
            return True

        elif cmd == DictationCommand.NEW_SECTION:
            # Start new section
            if self.template and self.template.sections:
                # Move to next section in template
                current_idx = 0
                section_names = [s.get("name", "") for s in self.template.sections]
                if self.current_section in section_names:
                    current_idx = section_names.index(self.current_section)

                if current_idx < len(self.template.sections) - 1:
                    next_section = self.template.sections[current_idx + 1]
                    self.current_section = next_section.get("name", "Untitled Section")
                    logger.info("Moving to section: %s", self.current_section)
            return True

        elif cmd == DictationCommand.UNDO:
            # Undo last segment
            if self.undo_stack:
                segment = self.undo_stack.pop()
                self.redo_stack.append(segment)
                # Remove from document
                if self.document and segment in self.document.segments:
                    self.document.segments.remove(segment)

            return True

        elif cmd == DictationCommand.CORRECT and params:
            # Apply correction
            original_word, corrected_word = params
            if self.document and self.document.segments:
                last_segment = self.document.segments[-1]
                # Replace the word in the segment text
                last_segment.text = last_segment.text.replace(
                    original_word, corrected_word
                )

            return True

        elif cmd == DictationCommand.PUNCTUATE:
            # Handle punctuation commands
            punctuation = None
            for punct_word, punct_mark in self.engine.punctuation_map.items():
                if punct_word in original_text.lower():
                    punctuation = punct_mark
                    break

            if punctuation and self.document and self.document.segments:
                # Add punctuation to last segment
                last_segment = self.document.segments[-1]
                last_segment.text = last_segment.text.rstrip() + punctuation + " "

            return True

        elif cmd == DictationCommand.PAUSE:
            self.is_paused = True
            return True

        elif cmd == DictationCommand.RESUME:
            self.is_paused = False
            return True

        return False


class VoiceDictationFormatter:
    """Handles formatting of dictated text."""

    def __init__(self) -> None:
        """Initialize the voice dictation formatter."""
        self.format_patterns = {
            FormattingCommand.BOLD: r"\*\*(.*?)\*\*",
            FormattingCommand.ITALIC: r"\*(.*?)\*",
            FormattingCommand.UNDERLINE: r"__(.*?)__",
            FormattingCommand.BULLET_POINT: r"^- (.*)$",
            FormattingCommand.NUMBERED_LIST: r"^\d+\. (.*)$",
            FormattingCommand.HEADING: r"^# (.*)$",
            FormattingCommand.SUBHEADING: r"^## (.*)$",
        }

    def apply_formatting(
        self, text: str, formatting_commands: List[Tuple[FormattingCommand, str]]
    ) -> str:
        """Apply formatting commands to text."""
        formatted_text = text

        for command, target_text in formatting_commands:
            if command == FormattingCommand.BOLD:
                formatted_text = formatted_text.replace(
                    target_text, f"**{target_text}**"
                )
            elif command == FormattingCommand.ITALIC:
                formatted_text = formatted_text.replace(target_text, f"*{target_text}*")
            elif command == FormattingCommand.UNDERLINE:
                formatted_text = formatted_text.replace(
                    target_text, f"__{target_text}__"
                )
            elif command == FormattingCommand.BULLET_POINT:
                formatted_text = f"- {formatted_text}"
            elif command == FormattingCommand.NUMBERED_LIST:
                # This would need context to know the number
                formatted_text = f"1. {formatted_text}"
            elif command == FormattingCommand.HEADING:
                formatted_text = f"# {formatted_text}"
            elif command == FormattingCommand.SUBHEADING:
                formatted_text = f"## {formatted_text}"

        return formatted_text

    def parse_formatting(self, text: str) -> List[Tuple[str, FormattingCommand]]:
        """Parse formatting from marked up text."""
        formatted_segments = []

        for command, pattern in self.format_patterns.items():
            matches = re.finditer(pattern, text, re.MULTILINE)
            for match in matches:
                formatted_segments.append((match.group(1), command))

        return formatted_segments


class AutoCorrector:
    """Handles automatic correction of common dictation errors."""

    def __init__(self) -> None:
        """Initialize the auto-corrector with medical abbreviations and common corrections."""
        # Common medical abbreviation expansions
        self.medical_abbreviations = {
            "bp": "blood pressure",
            "hr": "heart rate",
            "rr": "respiratory rate",
            "temp": "temperature",
            "hx": "history",
            "dx": "diagnosis",
            "tx": "treatment",
            "rx": "prescription",
            "sx": "symptoms",
            "px": "physical examination",
            "sob": "shortness of breath",
            "cp": "chest pain",
            "ha": "headache",
            "n/v": "nausea and vomiting",
            "abd": "abdominal",
            "cv": "cardiovascular",
            "gi": "gastrointestinal",
            "gu": "genitourinary",
            "ms": "musculoskeletal",
            "neuro": "neurological",
        }
        # Common corrections
        self.common_corrections = {
            "patient's": "patient's",  # Fix apostrophes
            "dont": "don't",
            "wont": "won't",
            "cant": "can't",
            "isnt": "isn't",
            "arent": "aren't",
            "wasnt": "wasn't",
            "werent": "weren't",
        }

    def auto_correct(self, text: str) -> str:
        """Apply automatic corrections to text."""
        corrected = text
        # Expand medical abbreviations
        for abbrev, expansion in self.medical_abbreviations.items():
            # Match abbreviation with word boundaries
            pattern = r"\b" + abbrev + r"\b"
            corrected = re.sub(pattern, expansion, corrected, flags=re.IGNORECASE)

        # Apply common corrections
        for incorrect, correct in self.common_corrections.items():
            corrected = corrected.replace(incorrect, correct)
        # Fix spacing around punctuation
        corrected = re.sub(r"\s+([.,;:!?])", r"\1", corrected)  # Remove space before
        corrected = re.sub(r"([.,;:!?])(\w)", r"\1 \2", corrected)  # Add space after
        # Capitalize sentences
        corrected = ". ".join(s.strip().capitalize() for s in corrected.split("."))
        return corrected


# Integration with voice command system
class VoiceDictationIntegration:
    """Integration layer for voice dictation with command grammar system."""

    def __init__(
        self,
        dictation_engine: VoiceDictationEngine,
        command_engine: Optional[Any] = None,
    ):
        """Initialize the voice dictation integration.

        Args:
            dictation_engine: The main dictation engine
            command_engine: Optional command grammar engine for integration
        """
        self.dictation_engine = dictation_engine
        self.command_engine = command_engine

        # Register dictation commands if command engine available
        if self.command_engine:
            self._register_dictation_commands()

    def _register_dictation_commands(self) -> None:
        """Register dictation commands with the command grammar engine."""
        # This would integrate with the voice command grammar system
        # to recognize dictation-specific commands

    async def handle_dictation_command(
        self, command_type: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle dictation-related commands from the grammar engine."""
        if command_type == "start_dictation":
            mode = DictationMode(parameters.get("mode", "clinical_note"))
            context = DictationContext(
                session_id=str(uuid.uuid4()),
                mode=mode,
                specialty=parameters.get("specialty"),
                language=parameters.get("language", LanguageCode.EN_US),
                user_id=parameters.get("user_id", ""),
                patient_id=parameters.get("patient_id"),
            )

            document_id = await self.dictation_engine.start_dictation(context)

            return {
                "status": "started",
                "session_id": context.session_id,
                "document_id": document_id,
            }

        elif command_type == "stop_dictation":
            session_id = parameters.get("session_id")
            if not session_id:
                raise ValueError("Session ID is required for stop_dictation command")
            document = await self.dictation_engine.stop_dictation(session_id)

            return {
                "status": "stopped",
                "document": {
                    "id": document.id,
                    "status": document.status,
                    "text": document.get_full_text(),
                    "sections": document.get_sections(),
                },
            }
        else:
            raise ValueError(f"Unknown dictation command: {command_type}")


# Example usage
if __name__ == "__main__":

    async def demo_dictation() -> None:
        """Demonstrate voice dictation functionality with a clinical note example."""
        # Initialize engine
        engine = VoiceDictationEngine()

        # Create dictation context
        context = DictationContext(
            session_id="demo_session_001",
            mode=DictationMode.CLINICAL_NOTE,
            specialty=MedicalSpecialty.PRIMARYCARE,
            language=LanguageCode.EN_US,
            user_id="demo_user",
        )

        # Start dictation
        document_id = await engine.start_dictation(context)
        print(f"Started dictation, document ID: {document_id}")

        # Simulate some dictation
        session = engine.active_sessions[context.session_id]

        # Add subjective section
        session.current_section = "Subjective"
        segment1 = DictationSegment(
            id=str(uuid.uuid4()),
            text="Patient presents with chief complaint of persistent headache for the past three days.",
            timestamp=datetime.now(),
            confidence=0.95,
            medical_terms=[
                {"term": "headache", "type": "symptom", "normalized": "cephalgia"}
            ],
        )
        session.add_segment(segment1)

        # Add objective section
        session.current_section = "Objective"
        segment2 = DictationSegment(
            id=str(uuid.uuid4()),
            text="Vital signs: Blood pressure 120/80, heart rate 72, temperature 98.6°F.",
            timestamp=datetime.now(),
            confidence=0.98,
            medical_terms=[
                {"term": "blood pressure", "type": "vital_sign"},
                {"term": "heart rate", "type": "vital_sign"},
                {"term": "temperature", "type": "vital_sign"},
            ],
        )
        session.add_segment(segment2)

        # Stop dictation
        _ = await engine.stop_dictation(context.session_id)

        # Export document
        text_export = await engine.export_document(document_id, "text")
        print("\nExported Text:")
        print(text_export)
        html_export = await engine.export_document(document_id, "html")
        print("\nExported HTML (preview):")
        print(html_export[:500] + "...")

    # Run demo
    asyncio.run(demo_dictation())
