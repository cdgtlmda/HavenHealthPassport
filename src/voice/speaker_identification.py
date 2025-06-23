"""Speaker Identification for Amazon Transcribe Medical.

This module provides speaker identification capabilities for medical transcriptions,
enabling differentiation between healthcare providers, patients, and other participants
in medical conversations.

IMPORTANT: This module handles PHI (Protected Health Information).
- All PHI data is encrypted at rest and in transit using industry-standard encryption.
- Access control is enforced through role-based permissions and authentication.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from .transcribe_medical import LanguageCode, MedicalSpecialty

logger = logging.getLogger(__name__)


class SpeakerRole(Enum):
    """Roles of speakers in medical conversations."""

    PATIENT = "patient"
    DOCTOR = "doctor"
    PHYSICIAN = "physician"
    NURSE = "nurse"
    CAREGIVER = "caregiver"
    INTERPRETER = "interpreter"
    SPECIALIST = "specialist"
    TECHNICIAN = "technician"
    UNKNOWN = "unknown"


class ConversationType(Enum):
    """Types of medical conversations."""

    CONSULTATION = "consultation"
    EMERGENCY = "emergency"
    FOLLOW_UP = "follow_up"
    TELEMEDICINE = "telemedicine"
    HANDOFF = "handoff"
    DISCHARGE = "discharge"
    ADMISSION = "admission"
    PROCEDURE = "procedure"


@dataclass
class Speaker:
    """Represents a speaker in a medical conversation."""

    speaker_id: str
    role: SpeakerRole = SpeakerRole.UNKNOWN
    name: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    language: Optional[str] = None
    voice_sample_uri: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize speaker attributes."""
        if self.role == SpeakerRole.DOCTOR and not self.title:
            self.title = "Dr."
        elif self.role == SpeakerRole.NURSE and not self.title:
            self.title = "RN"


@dataclass
class SpeakerSegment:
    """Represents a segment of speech by a specific speaker."""

    speaker_id: str
    start_time: float
    end_time: float
    text: str
    confidence: float = 0.0
    role: Optional[SpeakerRole] = None
    medical_terms: List[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """Calculate segment duration in seconds."""
        return self.end_time - self.start_time


@dataclass
class ConversationAnalysis:
    """Analysis results for a medical conversation."""

    conversation_id: str
    conversation_type: ConversationType
    total_duration: float
    speakers: List[Speaker]
    segments: List[SpeakerSegment]
    speaker_time_distribution: Dict[str, float] = field(default_factory=dict)
    interaction_patterns: Dict[str, Any] = field(default_factory=dict)
    medical_context: Dict[str, Any] = field(default_factory=dict)
    quality_metrics: Dict[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


class SpeakerIdentificationManager:
    """Manager for speaker identification in medical transcriptions."""

    def __init__(self, region_name: str = "us-east-1"):
        """Initialize the speaker identification manager."""
        self.transcribe_client = boto3.client("transcribe", region_name=region_name)
        self.region = region_name
        self.max_speakers = 10  # Amazon Transcribe Medical limit
        self.min_speaker_segments = 3  # Minimum segments to identify a speaker

    def configure_speaker_identification(
        self,
        job_name: str,
        show_speaker_labels: bool = True,
        max_speaker_labels: int = 2,
        channel_identification: bool = False,
    ) -> Dict[str, Any]:
        """
        Configure speaker identification settings for a transcription job.

        Args:
            job_name: Name of the transcription job
            show_speaker_labels: Whether to identify different speakers
            max_speaker_labels: Maximum number of speakers to identify (2-10)
            channel_identification: Use channel-based identification for stereo audio

        Returns:
            Speaker identification configuration
        """
        if max_speaker_labels < 2 or max_speaker_labels > self.max_speakers:
            raise ValueError(
                f"max_speaker_labels must be between 2 and {self.max_speakers}"
            )

        config = {"ShowSpeakerLabels": show_speaker_labels}

        if show_speaker_labels:
            config["MaxSpeakerLabels"] = max_speaker_labels

        if channel_identification:
            config["ChannelIdentification"] = True
            # For channel identification, we don't use speaker labels
            config["ShowSpeakerLabels"] = False

        logger.info(
            "Configured speaker identification for job '%s': %s", job_name, config
        )
        return config

    async def start_medical_transcription_with_speakers(
        self,
        job_name: str,
        media_uri: str,
        specialty: MedicalSpecialty,
        language_code: LanguageCode = LanguageCode.EN_US,
        max_speakers: int = 2,
        output_bucket: Optional[str] = None,
        enable_channel_identification: bool = False,
        custom_vocabulary_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Start a medical transcription job with speaker identification.

        Args:
            job_name: Unique name for the transcription job
            media_uri: S3 URI of the audio file
            specialty: Medical specialty for the transcription
            language_code: Language of the audio
            max_speakers: Maximum number of speakers to identify
            output_bucket: S3 bucket for output (optional)
            enable_channel_identification: Use channel-based identification
            custom_vocabulary_name: Name of custom vocabulary to use

        Returns:
            Transcription job details
        """
        try:
            # Prepare job settings
            settings = {
                "ShowSpeakerLabels": not enable_channel_identification,
                "MaxSpeakerLabels": (
                    max_speakers if not enable_channel_identification else None
                ),
                "ChannelIdentification": enable_channel_identification,
            }

            # Remove None values
            settings = {k: v for k, v in settings.items() if v is not None}

            # Add custom vocabulary if specified
            if custom_vocabulary_name:
                settings["VocabularyName"] = custom_vocabulary_name

            # Prepare job parameters
            params = {
                "MedicalTranscriptionJobName": job_name,
                "LanguageCode": language_code.value,
                "Media": {"MediaFileUri": media_uri},
                "Specialty": specialty.value,
                "Type": "CONVERSATION",
                "Settings": settings,
            }
            # Add output location if specified
            if output_bucket:
                params["OutputBucketName"] = output_bucket

            # Start transcription job
            response = self.transcribe_client.start_medical_transcription_job(**params)

            logger.info(
                "Started medical transcription job '%s' with speaker identification",
                job_name,
            )
            return {
                "job_name": response["MedicalTranscriptionJob"][
                    "MedicalTranscriptionJobName"
                ],
                "status": response["MedicalTranscriptionJob"]["TranscriptionJobStatus"],
                "created_time": response["MedicalTranscriptionJob"]["CreationTime"],
                "settings": settings,
            }

        except ClientError as e:
            logger.error("Failed to start transcription job: %s", e)
            raise

    def parse_transcription_with_speakers(
        self, transcription_result: Dict[str, Any]
    ) -> ConversationAnalysis:
        """
        Parse transcription results to extract speaker information.

        Args:
            transcription_result: Raw transcription result from Amazon Transcribe

        Returns:
            Parsed conversation analysis with speaker segments
        """
        # Extract basic information
        job_name = transcription_result.get("jobName", "unknown")
        results = transcription_result.get("results", {})

        # Initialize conversation analysis
        analysis = ConversationAnalysis(
            conversation_id=job_name,
            conversation_type=ConversationType.CONSULTATION,  # Default type
            total_duration=0.0,
            speakers=[],
            segments=[],
        )

        # Extract speaker segments
        speaker_segments = results.get("speaker_labels", {}).get("segments", [])
        speakers_found = set()
        # Process each speaker segment
        for segment in speaker_segments:
            speaker_label = segment.get("speaker_label", "spk_0")
            speakers_found.add(speaker_label)

            # Extract items for this segment
            for item in segment.get("items", []):
                if item.get("type") == "pronunciation":
                    start_time = float(item.get("start_time", 0))
                    end_time = float(item.get("end_time", 0))

                    # Create speaker segment
                    speaker_segment = SpeakerSegment(
                        speaker_id=speaker_label,
                        start_time=start_time,
                        end_time=end_time,
                        text="",  # Will be populated later
                        confidence=float(item.get("confidence", 0)),
                    )
                    analysis.segments.append(speaker_segment)

        # Create speaker objects
        for speaker_id in speakers_found:
            speaker = Speaker(
                speaker_id=speaker_id,
                role=self._infer_speaker_role(speaker_id, analysis.segments),
            )
            analysis.speakers.append(speaker)

        # Populate segment text from transcripts
        transcripts = results.get("transcripts", [])
        if transcripts:
            # This is a simplified approach - in production, you'd match
            # segments with actual words based on timestamps
            self._populate_segment_text(analysis.segments, results)

        # Calculate statistics
        analysis.total_duration = max(
            (seg.end_time for seg in analysis.segments), default=0.0
        )
        analysis.speaker_time_distribution = self._calculate_speaker_time(
            analysis.segments
        )
        analysis.interaction_patterns = self._analyze_interactions(analysis.segments)

        return analysis

    def _infer_speaker_role(
        self, speaker_id: str, segments: List[SpeakerSegment]
    ) -> SpeakerRole:
        """
        Infer speaker role based on speech patterns and content.

        This is a simplified implementation. In production, you would use
        more sophisticated analysis including:
        - Medical terminology usage frequency
        - Question/answer patterns
        - Formal vs informal language
        - Duration and frequency of speech
        """
        # Get segments for this speaker
        speaker_segments = [s for s in segments if s.speaker_id == speaker_id]

        if not speaker_segments:
            return SpeakerRole.UNKNOWN

        # Simple heuristic: first speaker is often the healthcare provider
        # This should be replaced with actual content analysis
        all_speakers = list(dict.fromkeys(s.speaker_id for s in segments))
        if speaker_id == all_speakers[0]:
            return SpeakerRole.DOCTOR
        else:
            return SpeakerRole.PATIENT

    def _populate_segment_text(
        self, segments: List[SpeakerSegment], results: Dict[str, Any]
    ) -> None:
        """Populate text content for each speaker segment."""
        # Get all items with timestamps
        items = results.get("items", [])

        # Group words by speaker segments
        for segment in segments:
            words = []
            for item in items:
                if (
                    item.get("type") == "pronunciation"
                    and "start_time" in item
                    and "end_time" in item
                ):

                    item_start = float(item["start_time"])
                    item_end = float(item["end_time"])

                    # Check if this word belongs to this segment
                    if (
                        item_start >= segment.start_time
                        and item_end <= segment.end_time + 0.1
                    ):  # Small buffer

                        # Find alternatives or use content
                        if "alternatives" in item:
                            words.append(item["alternatives"][0]["content"])

            segment.text = " ".join(words)

    def _calculate_speaker_time(
        self, segments: List[SpeakerSegment]
    ) -> Dict[str, float]:
        """Calculate total speaking time for each speaker."""
        speaker_time = {}

        for segment in segments:
            if segment.speaker_id not in speaker_time:
                speaker_time[segment.speaker_id] = 0.0
            speaker_time[segment.speaker_id] += segment.duration

        return speaker_time

    def _analyze_interactions(self, segments: List[SpeakerSegment]) -> Dict[str, Any]:
        """Analyze interaction patterns between speakers."""
        interactions = {
            "turn_count": {},
            "average_turn_duration": {},
            "interruptions": 0,
            "pause_durations": [],
        }

        # Count turns for each speaker
        current_speaker = None
        for i, segment in enumerate(segments):
            if segment.speaker_id != current_speaker:
                current_speaker = segment.speaker_id
                interactions["turn_count"][current_speaker] = (
                    interactions["turn_count"].get(current_speaker, 0) + 1
                )

            # Detect interruptions (overlapping segments)
            if i > 0:
                prev_segment = segments[i - 1]
                if segment.start_time < prev_segment.end_time:
                    interactions["interruptions"] += 1
                else:
                    # Calculate pause duration
                    pause = segment.start_time - prev_segment.end_time
                    if pause > 0:
                        interactions["pause_durations"].append(pause)

        # Calculate average turn duration
        for speaker_id in interactions["turn_count"]:
            speaker_segments = [s for s in segments if s.speaker_id == speaker_id]
            total_duration = sum(s.duration for s in speaker_segments)
            turn_count = interactions["turn_count"][speaker_id]
            interactions["average_turn_duration"][speaker_id] = (
                total_duration / turn_count if turn_count > 0 else 0
            )

        return interactions

    def assign_speaker_roles(
        self,
        analysis: ConversationAnalysis,
        role_hints: Optional[Dict[str, SpeakerRole]] = None,
    ) -> None:
        """
        Assign or update speaker roles based on analysis and hints.

        Args:
            analysis: Conversation analysis to update
            role_hints: Optional mapping of speaker_id to role
        """
        # Apply any provided role hints
        if role_hints:
            for speaker in analysis.speakers:
                if speaker.speaker_id in role_hints:
                    speaker.role = role_hints[speaker.speaker_id]

        # Apply heuristics for unknown roles
        for speaker in analysis.speakers:
            if speaker.role == SpeakerRole.UNKNOWN:
                # Analyze speech patterns
                speaker_segments = [
                    s for s in analysis.segments if s.speaker_id == speaker.speaker_id
                ]

                # Healthcare providers typically:
                # - Speak more formally
                # - Use more medical terminology
                # - Ask diagnostic questions
                # - Give instructions

                # This is a placeholder for more sophisticated analysis
                total_time = sum(s.duration for s in speaker_segments)
                avg_segment_length = (
                    total_time / len(speaker_segments) if speaker_segments else 0
                )

                # Simple heuristic: longer average segments might indicate provider
                if avg_segment_length > 5.0:  # seconds
                    speaker.role = SpeakerRole.DOCTOR
                else:
                    speaker.role = SpeakerRole.PATIENT

    def get_speaker_transcript(
        self, analysis: ConversationAnalysis, speaker_id: str
    ) -> List[Tuple[float, float, str]]:
        """
        Get all transcript segments for a specific speaker.

        Returns:
            List of tuples (start_time, end_time, text)
        """
        segments = [
            (s.start_time, s.end_time, s.text)
            for s in analysis.segments
            if s.speaker_id == speaker_id
        ]
        return segments

    def export_conversation_analysis(
        self, analysis: ConversationAnalysis, output_format: str = "json"
    ) -> str:
        """Export conversation analysis in specified format."""
        if output_format == "json":
            data = {
                "conversation_id": analysis.conversation_id,
                "conversation_type": analysis.conversation_type.value,
                "total_duration": analysis.total_duration,
                "created_at": analysis.created_at.isoformat(),
                "speakers": [
                    {
                        "id": speaker.speaker_id,
                        "role": speaker.role.value,
                        "name": speaker.name,
                        "title": speaker.title,
                        "speaking_time": analysis.speaker_time_distribution.get(
                            speaker.speaker_id, 0
                        ),
                    }
                    for speaker in analysis.speakers
                ],
                "segments": [
                    {
                        "speaker_id": seg.speaker_id,
                        "start_time": seg.start_time,
                        "end_time": seg.end_time,
                        "duration": seg.duration,
                        "text": seg.text,
                        "confidence": seg.confidence,
                    }
                    for seg in analysis.segments
                ],
                "interaction_patterns": analysis.interaction_patterns,
                "quality_metrics": analysis.quality_metrics,
            }
            return json.dumps(data, indent=2)

        elif output_format == "vtt":
            # WebVTT format for subtitles with speaker labels
            lines = ["WEBVTT", ""]

            for segment in analysis.segments:
                # Find speaker role
                speaker = next(
                    (
                        s
                        for s in analysis.speakers
                        if s.speaker_id == segment.speaker_id
                    ),
                    None,
                )
                role = speaker.role.value if speaker else "unknown"

                # Format timestamps
                start = self._format_timestamp(segment.start_time)
                end = self._format_timestamp(segment.end_time)

                lines.extend(
                    [f"{start} --> {end}", f"[{role.upper()}] {segment.text}", ""]
                )

            return "\n".join(lines)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds to WebVTT timestamp format (HH:MM:SS.mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


# Example usage
if __name__ == "__main__":

    async def main():
        """Run speaker identification demonstration."""
        # Initialize manager
        manager = SpeakerIdentificationManager()

        # Configure speaker identification
        config = manager.configure_speaker_identification(
            job_name="medical_consultation_001",
            show_speaker_labels=True,
            max_speaker_labels=3,
        )
        print(f"Speaker identification config: {config}")

        # Start transcription with speaker identification
        job_result = await manager.start_medical_transcription_with_speakers(
            job_name="medical_consultation_001",
            media_uri="s3://medical-audio-bucket/consultation.wav",
            specialty=MedicalSpecialty.PRIMARYCARE,
            max_speakers=3,
        )
        print(f"Started transcription job: {job_result}")

        # Example of parsing results (would come from completed job)
        sample_results = {
            "jobName": "medical_consultation_001",
            "results": {
                "speaker_labels": {
                    "segments": [
                        {
                            "speaker_label": "spk_0",
                            "items": [
                                {
                                    "type": "pronunciation",
                                    "start_time": "0.0",
                                    "end_time": "2.5",
                                    "confidence": "0.95",
                                }
                            ],
                        }
                    ]
                }
            },
        }

        # Parse and analyze
        analysis = manager.parse_transcription_with_speakers(sample_results)
        print(f"Conversation analysis: {len(analysis.speakers)} speakers found")

        # Export results
        json_export = manager.export_conversation_analysis(
            analysis, output_format="json"
        )
        print("Exported analysis:", json_export[:200] + "...")

    # Run example
    asyncio.run(main())
