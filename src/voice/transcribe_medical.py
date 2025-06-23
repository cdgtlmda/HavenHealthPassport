"""
Amazon Transcribe Medical Service Configuration and Implementation.

This module provides integration with Amazon Transcribe Medical for
medical voice transcription with high accuracy for healthcare terminology.
"""

# pylint: disable=too-many-lines

import asyncio
import json
import logging
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Union, cast

import boto3
import numpy as np
from botocore.exceptions import ClientError

# Import accent adaptation components
from .accent_adaptation import (
    AccentAdapter,
    AccentDatabase,
    AccentDetectionResult,
    AccentDetector,
    AccentProfile,
    AccentRegion,
    AdaptationStrategy,
    MedicalPronunciationDatabase,
)

# Import channel identification components
from .channel_identification import (
    ChannelIdentificationConfig,
    ChannelMapping,
    ChannelProcessor,
    ChannelRole,
    ChannelSegment,
    ChannelTranscriptionManager,
    PredefinedConfigs,
)

# Import language detection components
from .language_detection import (
    ExtendedLanguageCode,
    LanguageDetectionManager,
    LanguageDetectionResult,
    MedicalContext,
    MultiLanguageSegment,
)

logger = logging.getLogger(__name__)


class MedicalSpecialty(Enum):
    """Medical specialties supported by Amazon Transcribe Medical."""

    PRIMARYCARE = "PRIMARYCARE"
    CARDIOLOGY = "CARDIOLOGY"
    NEUROLOGY = "NEUROLOGY"
    ONCOLOGY = "ONCOLOGY"
    RADIOLOGY = "RADIOLOGY"
    UROLOGY = "UROLOGY"
    # Additional specialties can be added as supported


class AudioFormat(Enum):
    """Supported audio formats."""

    MP3 = "mp3"
    MP4 = "mp4"
    WAV = "wav"
    FLAC = "flac"
    OGG = "ogg"
    AMR = "amr"
    WEBM = "webm"


class LanguageCode(Enum):
    """Supported language codes for medical transcription."""

    EN_US = "en-US"  # US English
    EN_GB = "en-GB"  # British English
    ES_US = "es-US"  # US Spanish


class TranscriptionStatus(Enum):
    """Status of transcription job."""

    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TranscriptionType(Enum):
    """Type of medical transcription."""

    CONVERSATION = "CONVERSATION"
    DICTATION = "DICTATION"


@dataclass
class TranscribeMedicalConfig:
    """Configuration for Amazon Transcribe Medical service."""

    region: str = "us-east-1"
    specialty: MedicalSpecialty = MedicalSpecialty.PRIMARYCARE
    type: TranscriptionType = TranscriptionType.CONVERSATION
    language_code: LanguageCode = LanguageCode.EN_US
    max_speaker_labels: int = 2
    show_speaker_labels: bool = True
    channel_identification: bool = False
    channel_config: Optional[ChannelIdentificationConfig] = None
    vocabulary_name: Optional[str] = None
    content_redaction: bool = True  # Redact PHI
    output_bucket: str = "haven-health-transcriptions"
    output_encryption: bool = True
    sample_rate: int = 16000  # Hz

    # Language detection settings
    auto_detect_language: bool = False
    preferred_languages: List[ExtendedLanguageCode] = field(default_factory=list)
    language_detection_confidence_threshold: float = 0.7
    enable_multi_language_detection: bool = False

    # Accent adaptation settings
    enable_accent_adaptation: bool = False
    accent_detection_enabled: bool = False
    adaptation_strategy: AdaptationStrategy = AdaptationStrategy.COMBINED
    accent_confidence_threshold: float = 0.6
    apply_medical_pronunciation_variants: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "region": self.region,
            "specialty": self.specialty.value,
            "type": self.type.value,
            "language_code": self.language_code.value,
            "max_speaker_labels": self.max_speaker_labels,
            "show_speaker_labels": self.show_speaker_labels,
            "channel_identification": self.channel_identification,
            "channel_config": (
                self.channel_config.to_dict() if self.channel_config else None
            ),
            "vocabulary_name": self.vocabulary_name,
            "content_redaction": self.content_redaction,
            "output_bucket": self.output_bucket,
            "output_encryption": self.output_encryption,
            "sample_rate": self.sample_rate,
            "auto_detect_language": self.auto_detect_language,
            "preferred_languages": [lang.value for lang in self.preferred_languages],
            "language_detection_confidence_threshold": self.language_detection_confidence_threshold,
            "enable_multi_language_detection": self.enable_multi_language_detection,
            "enable_accent_adaptation": self.enable_accent_adaptation,
            "accent_detection_enabled": self.accent_detection_enabled,
            "adaptation_strategy": self.adaptation_strategy.value,
            "accent_confidence_threshold": self.accent_confidence_threshold,
            "apply_medical_pronunciation_variants": self.apply_medical_pronunciation_variants,
        }


@dataclass
class MedicalTrait:
    """Medical trait detected in text."""

    name: str
    score: float


@dataclass
class MedicalEntity:
    """Medical entity detected in text."""

    text: str
    category: str
    type: str
    score: float
    begin_offset: int
    end_offset: int
    traits: List[MedicalTrait] = field(default_factory=list)


@dataclass
class TranscriptionWord:
    """Individual word in transcription."""

    word: str
    start_time: float
    end_time: float
    confidence: float
    speaker_label: Optional[str] = None


@dataclass
class TranscriptionSegment:
    """Individual segment of transcription."""

    start_time: float
    end_time: float
    text: str
    speaker: Optional[str] = None
    confidence: float = 0.0
    alternatives: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TranscriptionResult:
    """Result of medical transcription."""

    job_name: str
    status: TranscriptionStatus
    language_code: str
    specialty: str
    transcription_type: str
    start_time: datetime
    completion_time: Optional[datetime] = None
    transcript_text: Optional[str] = None
    segments: List[TranscriptionSegment] = field(default_factory=list)
    medical_entities: List[Dict[str, Any]] = field(default_factory=list)
    confidence_score: float = 0.0
    transcript_file_uri: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "job_name": self.job_name,
            "status": self.status.value,
            "language_code": self.language_code,
            "specialty": self.specialty,
            "transcription_type": self.transcription_type,
            "start_time": self.start_time.isoformat(),
            "completion_time": (
                self.completion_time.isoformat() if self.completion_time else None
            ),
            "transcript_text": self.transcript_text,
            "segments": [
                {
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "text": s.text,
                    "speaker": s.speaker,
                    "confidence": s.confidence,
                }
                for s in self.segments
            ],
            "medical_entities": self.medical_entities,
            "confidence_score": self.confidence_score,
            "transcript_file_uri": self.transcript_file_uri,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


class TranscribeMedicalService:
    """
    Service for medical voice transcription using Amazon Transcribe Medical.

    Features:
    - Medical specialty vocabularies
    - Speaker identification
    - PHI redaction
    - Multi-channel support
    - Real-time and batch processing
    - High accuracy for medical terminology
    """

    _service_available: bool

    def __init__(self, config: Optional[TranscribeMedicalConfig] = None):
        """Initialize Transcribe Medical service."""
        self.config = config or TranscribeMedicalConfig()

        # Initialize AWS client
        self.transcribe_client = boto3.client(
            "transcribe", region_name=self.config.region
        )
        self.s3_client = boto3.client("s3", region_name=self.config.region)
        self.comprehend_medical = boto3.client(
            "comprehendmedical", region_name=self.config.region
        )

        # Initialize IAM role ARN and confidence adjustment
        self._transcribe_role_arn: Optional[str] = None
        self._confidence_adjustment: float = 0.0

        # Initialize channel processor if channel identification is enabled
        self.channel_processor = None
        self.channel_transcription_manager = None
        if self.config.channel_identification and self.config.channel_config:
            self.channel_processor = ChannelProcessor(self.config.channel_config)
            self.channel_transcription_manager = ChannelTranscriptionManager(
                self.config.channel_config
            )

        # Initialize language detection manager
        self.language_detection_manager = LanguageDetectionManager(
            region_name=self.config.region
        )

        # Initialize accent adaptation components
        self.accent_database = AccentDatabase()
        self.accent_detector = AccentDetector(self.accent_database)
        self.accent_adapter = AccentAdapter(self.accent_database)
        self.medical_pronunciation_db = MedicalPronunciationDatabase()

        # Active jobs tracking
        self._active_jobs: Dict[str, TranscriptionResult] = {}

        # Service availability check
        self._service_available = False
        self._check_service_availability()

        logger.info("TranscribeMedical service initialized in %s", self.config.region)

    def _check_service_availability(self) -> None:
        """Check if Transcribe Medical is available in the region."""
        try:
            # Try to list medical vocabularies to check service availability
            self.transcribe_client.list_medical_vocabularies(MaxResults=1)
            self._service_available = True
            logger.info("Amazon Transcribe Medical service is available")
        except ClientError as e:
            if e.response["Error"]["Code"] == "UnrecognizedClientException":
                logger.error(
                    "Transcribe Medical not available in %s", self.config.region
                )
                self._service_available = False
            else:
                logger.error("Error checking Transcribe Medical availability: %s", e)
                self._service_available = False
        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("Unexpected error checking service: %s", e)
            self._service_available = False

    async def enable_service(self) -> bool:
        """
        Enable Transcribe Medical service with necessary configurations.

        Returns:
            True if service is successfully enabled
        """
        if self._service_available:
            logger.info("Transcribe Medical service already available")
            return True

        try:
            # Create output S3 bucket if it doesn't exist
            await self._ensure_output_bucket()

            # Set up IAM permissions
            await self._setup_iam_permissions()

            # Re-check availability
            self._check_service_availability()

            if self._service_available:
                logger.info("Transcribe Medical service successfully enabled")  # type: ignore[unreachable]
                return True
            else:
                logger.error("Failed to enable Transcribe Medical service")
                return False

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("Error enabling Transcribe Medical service: %s", e)
            return False

    async def _ensure_output_bucket(self) -> None:
        """Ensure S3 bucket exists for transcription outputs."""
        try:
            # Check if bucket exists
            self.s3_client.head_bucket(Bucket=self.config.output_bucket)
            logger.info("Output bucket %s exists", self.config.output_bucket)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                # Create bucket
                try:
                    if self.config.region == "us-east-1":
                        self.s3_client.create_bucket(Bucket=self.config.output_bucket)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.config.output_bucket,
                            CreateBucketConfiguration={
                                "LocationConstraint": self.config.region
                            },
                        )

                    # Enable encryption
                    if self.config.output_encryption:
                        self.s3_client.put_bucket_encryption(
                            Bucket=self.config.output_bucket,
                            ServerSideEncryptionConfiguration={
                                "Rules": [
                                    {
                                        "ApplyServerSideEncryptionByDefault": {
                                            "SSEAlgorithm": "AES256"
                                        }
                                    }
                                ]
                            },
                        )

                    logger.info("Created output bucket %s", self.config.output_bucket)
                except Exception as create_error:
                    logger.error("Failed to create bucket: %s", create_error)
                    raise
            else:
                logger.error("Error accessing bucket: %s", e)
                raise

    async def _setup_iam_permissions(self) -> None:
        """Set up necessary IAM permissions for Transcribe Medical."""
        try:
            # Initialize IAM client
            iam_client = boto3.client("iam")

            # Define the trust policy for Transcribe Medical
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "transcribe.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            }

            # Define the permissions policy for S3 and KMS access
            permissions_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:GetObject", "s3:ListBucket"],
                        "Resource": [
                            f"arn:aws:s3:::{self.config.output_bucket}/*",
                            f"arn:aws:s3:::{self.config.output_bucket}",
                        ],
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["kms:Decrypt", "kms:DescribeKey"],
                        "Resource": "*",
                        "Condition": {
                            "StringEquals": {
                                "kms:ViaService": f"s3.{self.config.region}.amazonaws.com"
                            }
                        },
                    },
                ],
            }

            role_name = f"HavenHealthTranscribeMedicalRole-{self.config.region}"
            policy_name = f"HavenHealthTranscribeMedicalPolicy-{self.config.region}"

            try:
                # Check if role exists
                iam_client.get_role(RoleName=role_name)
                logger.info("IAM role %s already exists", role_name)

                # Update the trust policy
                iam_client.update_assume_role_policy(
                    RoleName=role_name, PolicyDocument=json.dumps(trust_policy)
                )

            except iam_client.exceptions.NoSuchEntityException:
                # Create the role if it doesn't exist
                logger.info("Creating IAM role %s", role_name)
                iam_client.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description="Role for Haven Health Transcribe Medical service",
                    Tags=[
                        {"Key": "Project", "Value": "HavenHealthPassport"},
                        {"Key": "Service", "Value": "TranscribeMedical"},
                        {"Key": "Environment", "Value": self.config.region},
                    ],
                )

            # Create or update the inline policy
            try:
                iam_client.put_role_policy(
                    RoleName=role_name,
                    PolicyName=policy_name,
                    PolicyDocument=json.dumps(permissions_policy),
                )
                logger.info("Updated IAM policy %s for role %s", policy_name, role_name)
            except Exception as e:
                logger.error("Failed to update IAM policy: %s", e)
                raise

            # Store the role ARN for later use
            response = iam_client.get_role(RoleName=role_name)
            self._transcribe_role_arn = response["Role"]["Arn"]

            logger.info(
                "IAM permissions setup completed. Role ARN: %s",
                self._transcribe_role_arn,
            )

        except Exception as e:
            logger.error("Failed to setup IAM permissions: %s", e)
            raise RuntimeError(f"IAM setup failed: {str(e)}") from e

    async def transcribe_audio_file(
        self,
        audio_file_path: Union[str, Path],
        job_name: Optional[str] = None,
        specialty: Optional[MedicalSpecialty] = None,
        custom_vocabulary: Optional[str] = None,
        settings_override: Optional[Dict[str, Any]] = None,
    ) -> TranscriptionResult:
        """
        Transcribe a medical audio file.

        Args:
            audio_file_path: Path to audio file or S3 URI
            job_name: Optional custom job name
            specialty: Medical specialty for better accuracy
            custom_vocabulary: Optional custom vocabulary name

        Returns:
            TranscriptionResult object
        """
        if not self._service_available:
            raise RuntimeError("Transcribe Medical service not available")

        # Generate job name if not provided
        if not job_name:
            job_name = f"medical_transcription_{uuid.uuid4().hex[:8]}"

        # Upload file to S3 if local path
        if isinstance(audio_file_path, Path) or not audio_file_path.startswith("s3://"):
            s3_uri = await self._upload_audio_to_s3(audio_file_path, job_name)
        else:
            s3_uri = audio_file_path

        # Use configured specialty or override
        medical_specialty = specialty or self.config.specialty

        # Create transcription result
        result = TranscriptionResult(
            job_name=job_name,
            status=TranscriptionStatus.QUEUED,
            language_code=self.config.language_code.value,
            specialty=medical_specialty.value,
            transcription_type=self.config.type.value,
            start_time=datetime.utcnow(),
        )

        try:
            # Start transcription job
            settings: dict[str, Any] = {
                "ShowSpeakerLabels": self.config.show_speaker_labels,
                "MaxSpeakerLabels": self.config.max_speaker_labels,
            }

            if self.config.channel_identification:
                settings["ChannelIdentification"] = True

            if self.config.vocabulary_name or custom_vocabulary:
                settings["VocabularyName"] = (
                    custom_vocabulary or self.config.vocabulary_name
                )

            # Apply settings override if provided
            if settings_override:
                settings.update(settings_override)

            self.transcribe_client.start_medical_transcription_job(
                MedicalTranscriptionJobName=job_name,
                LanguageCode=self.config.language_code.value,
                MediaSampleRateHertz=self.config.sample_rate,
                MediaFormat=self._detect_audio_format(s3_uri),
                Media={"MediaFileUri": s3_uri},
                OutputBucketName=self.config.output_bucket,
                OutputEncryptionKMSKeyId=(
                    "alias/aws/s3" if self.config.output_encryption else None
                ),
                Settings=settings,
                ContentIdentificationType=(
                    "PHI" if self.config.content_redaction else None
                ),
                Specialty=medical_specialty.value,
                Type=self.config.type.value,
            )

            result.status = TranscriptionStatus.IN_PROGRESS
            self._active_jobs[job_name] = result

            logger.info("Started medical transcription job: %s", job_name)

        except ClientError as e:
            result.status = TranscriptionStatus.FAILED
            result.error_message = str(e)
            logger.error("Failed to start transcription job: %s", e)
            raise

        return result

    async def _upload_audio_to_s3(
        self, audio_file_path: Union[str, Path], job_name: str
    ) -> str:
        """Upload audio file to S3."""
        file_path = Path(audio_file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        # Generate S3 key
        file_extension = file_path.suffix
        s3_key = f"audio-inputs/{job_name}{file_extension}"

        try:
            # Upload file
            self.s3_client.upload_file(
                str(file_path), self.config.output_bucket, s3_key
            )

            s3_uri = f"s3://{self.config.output_bucket}/{s3_key}"
            logger.info("Uploaded audio file to %s", s3_uri)

            return s3_uri

        except Exception as e:
            logger.error("Failed to upload audio file: %s", e)
            raise

    async def _extract_audio_segment(
        self,
        audio_file_path: Union[str, Path],
        start_time: float,
        end_time: float,
        segment_name: str,
    ) -> Path:
        """Extract a segment from an audio file using ffmpeg."""
        import subprocess  # noqa: PLC0415

        # Create temporary output file
        output_dir = Path(tempfile.gettempdir()) / "haven_health_segments"
        output_dir.mkdir(exist_ok=True)

        # Determine file format
        input_path = Path(audio_file_path)
        output_path = output_dir / f"{segment_name}{input_path.suffix}"

        # Build ffmpeg command
        duration = end_time - start_time
        cmd = [
            "ffmpeg",
            "-i",
            str(input_path),
            "-ss",
            str(start_time),  # Start time
            "-t",
            str(duration),  # Duration
            "-acodec",
            "copy",  # Copy audio codec (no re-encoding)
            "-y",  # Overwrite output file
            str(output_path),
        ]

        try:
            # Execute ffmpeg
            subprocess.run(cmd, capture_output=True, text=True, check=True)

            logger.info(
                "Extracted audio segment: %.1fs - %.1fs (%.1fs) -> %s",
                start_time,
                end_time,
                duration,
                output_path.name,
            )

            return output_path

        except subprocess.CalledProcessError as e:
            logger.error("ffmpeg failed: %s", e.stderr)
            raise RuntimeError(f"Failed to extract audio segment: {e.stderr}") from e
        except FileNotFoundError as exc:
            logger.error("ffmpeg not found. Please install ffmpeg.")
            raise RuntimeError(
                "ffmpeg is required for audio segment extraction. "
                "Install it with: apt-get install ffmpeg (Linux) or brew install ffmpeg (Mac)"
            ) from exc

    def _detect_audio_format(self, file_path: str) -> str:
        """Detect audio format from file extension."""
        extension = file_path.lower().split(".")[-1]

        format_map = {
            "mp3": "mp3",
            "mp4": "mp4",
            "m4a": "mp4",
            "wav": "wav",
            "flac": "flac",
            "ogg": "ogg",
            "amr": "amr",
            "webm": "webm",
        }

        return format_map.get(extension, "mp3")

    async def get_transcription_status(self, job_name: str) -> TranscriptionResult:
        """Get status of a transcription job."""
        try:
            response = self.transcribe_client.get_medical_transcription_job(
                MedicalTranscriptionJobName=job_name
            )

            job = response["MedicalTranscriptionJob"]

            # Update result from active jobs or create new
            if job_name in self._active_jobs:
                result = self._active_jobs[job_name]
            else:
                result = TranscriptionResult(
                    job_name=job_name,
                    status=TranscriptionStatus.IN_PROGRESS,
                    language_code=job["LanguageCode"],
                    specialty=job["Specialty"],
                    transcription_type=job["Type"],
                    start_time=job["CreationTime"],
                )

            # Update status
            status_map = {
                "QUEUED": TranscriptionStatus.QUEUED,
                "IN_PROGRESS": TranscriptionStatus.IN_PROGRESS,
                "COMPLETED": TranscriptionStatus.COMPLETED,
                "FAILED": TranscriptionStatus.FAILED,
            }

            result.status = status_map.get(
                job["TranscriptionJobStatus"], TranscriptionStatus.IN_PROGRESS
            )

            # If completed, get transcript
            if result.status == TranscriptionStatus.COMPLETED:
                result.completion_time = job.get("CompletionTime")
                result.transcript_file_uri = job["Transcript"]["TranscriptFileUri"]

                # Download and parse transcript
                await self._parse_transcript(result)

            elif result.status == TranscriptionStatus.FAILED:
                result.error_message = job.get("FailureReason", "Unknown error")

            return result

        except ClientError as e:
            logger.error("Failed to get transcription status: %s", e)
            raise

    async def _parse_transcript(self, result: TranscriptionResult) -> None:
        """Parse and extract information from completed transcript."""
        if not result.transcript_file_uri:
            return

        try:
            # Download transcript from S3
            transcript_data = await self._download_transcript(
                result.transcript_file_uri
            )

            # Parse JSON transcript
            if "results" in transcript_data:
                results = transcript_data["results"]

                # Extract full transcript text
                if "transcripts" in results and results["transcripts"]:
                    result.transcript_text = results["transcripts"][0]["transcript"]

                # Extract segments with speaker labels
                if (
                    "speaker_labels" in results
                    and "segments" in results["speaker_labels"]
                ):
                    for segment in results["speaker_labels"]["segments"]:
                        for item in segment.get("items", []):
                            if "start_time" in item:
                                seg = TranscriptionSegment(
                                    start_time=float(item["start_time"]),
                                    end_time=float(item["end_time"]),
                                    text=item.get("content", ""),
                                    speaker=item.get("speaker_label"),
                                    confidence=float(item.get("confidence", 0)),
                                )
                                result.segments.append(seg)

                # Extract medical entities if available
                if "clinical_entities" in results:
                    result.medical_entities = results["clinical_entities"]

                # Calculate average confidence
                if result.segments:
                    confidences = [
                        s.confidence for s in result.segments if s.confidence > 0
                    ]
                    if confidences:
                        result.confidence_score = sum(confidences) / len(confidences)

        except (ValueError, KeyError, AttributeError) as e:
            logger.error("Failed to parse transcript: %s", e)
            result.error_message = f"Failed to parse transcript: {e}"

    async def _download_transcript(self, transcript_uri: str) -> Dict[str, Any]:
        """Download transcript JSON from S3."""
        # Parse S3 URI
        if transcript_uri.startswith("https://"):
            # Convert HTTPS URL to S3 bucket/key
            parts = transcript_uri.replace("https://", "").split("/")
            bucket = parts[0].split(".")[0]
            key = "/".join(parts[1:])
        else:
            # Parse s3:// URI
            parts = transcript_uri.replace("s3://", "").split("/", 1)
            bucket = parts[0]
            key = parts[1]

        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            transcript_data = json.loads(response["Body"].read().decode("utf-8"))
            return cast(dict[str, Any], transcript_data)
        except Exception as e:
            logger.error("Failed to download transcript: %s", e)
            raise

    async def wait_for_completion(
        self, job_name: str, check_interval: int = 5, max_wait_time: int = 3600
    ) -> TranscriptionResult:
        """
        Wait for transcription job to complete.

        Args:
            job_name: Name of transcription job
            check_interval: Seconds between status checks
            max_wait_time: Maximum seconds to wait

        Returns:
            Completed TranscriptionResult
        """
        start_time = datetime.utcnow()

        while True:
            result = await self.get_transcription_status(job_name)

            if result.status in [
                TranscriptionStatus.COMPLETED,
                TranscriptionStatus.FAILED,
            ]:
                return result

            # Check timeout
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > max_wait_time:
                result.status = TranscriptionStatus.FAILED
                result.error_message = "Transcription timed out"
                return result

            # Wait before next check
            await asyncio.sleep(check_interval)

    def get_service_info(self) -> Dict[str, Any]:
        """Get information about the Transcribe Medical service status."""
        return {
            "service_available": self._service_available,
            "region": self.config.region,
            "configuration": self.config.to_dict(),
            "active_jobs": len(self._active_jobs),
            "supported_specialties": [s.value for s in MedicalSpecialty],
            "supported_languages": [lang.value for lang in LanguageCode],
            "supported_formats": [f.value for f in AudioFormat],
        }

    def enable_channel_identification(
        self,
        config: Optional[ChannelIdentificationConfig] = None,
        preset: Optional[str] = None,
    ) -> None:
        """
        Enable channel identification for multi-channel transcription.

        Args:
            config: Custom channel configuration
            preset: Use predefined configuration ('doctor_patient', 'telemedicine', 'emergency_room')
        """
        if preset:
            presets = {
                "doctor_patient": PredefinedConfigs.doctor_patient_consultation,
                "telemedicine": PredefinedConfigs.telemedicine_session,
                "emergency_room": PredefinedConfigs.emergency_room_recording,
            }

            if preset in presets:
                self.config.channel_config = presets[preset]()
            else:
                raise ValueError(f"Unknown preset: {preset}")
        elif config:
            self.config.channel_config = config
        else:
            # Use default doctor-patient configuration
            self.config.channel_config = PredefinedConfigs.doctor_patient_consultation()

        self.config.channel_identification = True

        # Initialize processors
        self.channel_processor = ChannelProcessor(self.config.channel_config)
        self.channel_transcription_manager = ChannelTranscriptionManager(
            self.config.channel_config
        )

        logger.info("Channel identification enabled")

    async def transcribe_multi_channel_audio(
        self,
        audio_file_path: Union[str, Path],
        job_name: Optional[str] = None,
        process_channels_separately: bool = True,
    ) -> Dict[str, Any]:
        """
        Transcribe multi-channel audio with channel identification.

        Args:
            audio_file_path: Path to multi-channel audio file
            job_name: Optional custom job name
            process_channels_separately: Whether to process each channel separately

        Returns:
            Dictionary with channel-specific transcription results
        """
        if not self.channel_processor:
            raise RuntimeError(
                "Channel identification not enabled. Call enable_channel_identification() first."
            )

        # Generate job name if not provided
        if not job_name:
            job_name = f"multi_channel_{uuid.uuid4().hex[:8]}"

        results: dict[str, Any] = {
            "job_name": job_name,
            "channel_results": {},
            "merged_transcript": None,
            "medical_summary": None,
            "channel_metadata": {},
        }

        try:
            # Process audio file to separate channels
            logger.info("Processing multi-channel audio: %s", audio_file_path)
            channel_data = self.channel_processor.process_file(audio_file_path)

            if process_channels_separately:
                # Export separated channels
                temp_dir = Path(tempfile.gettempdir()) / f"transcribe_{job_name}"
                temp_dir.mkdir(exist_ok=True)

                exported_files = self.channel_processor.export_channels(
                    channel_data, temp_dir
                )

                # Transcribe each channel
                for channel_id, channel_file in exported_files.items():
                    ch_id = channel_id

                    # Get channel mapping
                    mapping = (
                        self.config.channel_config.get_channel_mapping(ch_id)
                        if self.config.channel_config
                        else None
                    )

                    # Transcribe channel
                    channel_job_name = f"{job_name}_ch{ch_id}"
                    result = await self.transcribe_audio_file(
                        channel_file,
                        job_name=channel_job_name,
                        specialty=self._get_specialty_for_role(
                            mapping.role if mapping else None
                        ),
                    )

                    # Wait for completion
                    result = await self.wait_for_completion(channel_job_name)

                    # Add to channel results
                    results["channel_results"][ch_id] = result.to_dict()

                    # Process transcription segments
                    if (
                        result.status == TranscriptionStatus.COMPLETED
                        and result.segments
                    ):
                        for segment in result.segments:
                            channel_segment = ChannelSegment(
                                channel_id=ch_id,
                                start_time=segment.start_time,
                                end_time=segment.end_time,
                                text=segment.text,
                                confidence=segment.confidence,
                                speaker_label=segment.speaker,
                            )
                            if self.channel_transcription_manager:
                                await self.channel_transcription_manager.add_transcription_segment(
                                    ch_id, channel_segment
                                )

                # Clean up temporary files
                import shutil  # pylint: disable=import-outside-toplevel

                shutil.rmtree(temp_dir)

            else:
                # Use AWS Transcribe's built-in channel identification
                # (This requires specific audio format with separate channels)
                result = await self._transcribe_with_channel_identification(
                    audio_file_path, job_name
                )
                results["channel_results"]["combined"] = result.to_dict()

            # Get channel metadata
            results["channel_metadata"] = self.channel_processor.get_channel_summary(
                channel_data
            )

            # Generate merged transcript
            if self.channel_transcription_manager:
                results["merged_transcript"] = (
                    self.channel_transcription_manager.merge_channels()
                )

            # Generate medical summary - Method doesn't exist
            # results["medical_summary"] = (
            #     self.channel_transcription_manager.generate_medical_summary()
            # )

            return results

        except Exception as e:
            logger.error("Error in multi-channel transcription: %s", e)
            raise

    def _get_specialty_for_role(self, role: Optional[ChannelRole]) -> MedicalSpecialty:
        """Get appropriate medical specialty based on channel role."""
        if not role:
            return self.config.specialty

        # Map roles to specialties
        role_specialty_map = {
            ChannelRole.PHYSICIAN: MedicalSpecialty.PRIMARYCARE,
            ChannelRole.SPECIALIST: MedicalSpecialty.CARDIOLOGY,  # Default specialist
            ChannelRole.NURSE: MedicalSpecialty.PRIMARYCARE,
            ChannelRole.TECHNICIAN: MedicalSpecialty.RADIOLOGY,
        }

        return role_specialty_map.get(role, self.config.specialty)

    async def _transcribe_with_channel_identification(
        self, audio_file_path: Union[str, Path], job_name: str
    ) -> TranscriptionResult:
        """
        Transcribe using AWS Transcribe's channel identification feature.

        Args:
            audio_file_path: Path to audio file
            job_name: Job name

        Returns:
            TranscriptionResult with channel information
        """
        # Upload file to S3
        s3_uri = await self._upload_audio_to_s3(audio_file_path, job_name)

        # Create transcription result
        result = TranscriptionResult(
            job_name=job_name,
            status=TranscriptionStatus.QUEUED,
            language_code=self.config.language_code.value,
            specialty=self.config.specialty.value,
            transcription_type=self.config.type.value,
            start_time=datetime.utcnow(),
        )

        try:
            # Configure settings with channel identification
            settings: dict[str, Any] = {
                "ShowSpeakerLabels": self.config.show_speaker_labels,
                "MaxSpeakerLabels": self.config.max_speaker_labels,
                "ChannelIdentification": True,  # Enable channel identification
            }

            if self.config.vocabulary_name:
                settings["VocabularyName"] = self.config.vocabulary_name

            # Start transcription job
            self.transcribe_client.start_medical_transcription_job(
                MedicalTranscriptionJobName=job_name,
                LanguageCode=self.config.language_code.value,
                MediaSampleRateHertz=self.config.sample_rate,
                MediaFormat=self._detect_audio_format(s3_uri),
                Media={"MediaFileUri": s3_uri},
                OutputBucketName=self.config.output_bucket,
                OutputEncryptionKMSKeyId=(
                    "alias/aws/s3" if self.config.output_encryption else None
                ),
                Settings=settings,
                ContentIdentificationType=(
                    "PHI" if self.config.content_redaction else None
                ),
                Specialty=self.config.specialty.value,
                Type=self.config.type.value,
            )

            result.status = TranscriptionStatus.IN_PROGRESS
            self._active_jobs[job_name] = result

            logger.info(
                "Started medical transcription job with channel identification: %s",
                job_name,
            )

        except ClientError as e:
            result.status = TranscriptionStatus.FAILED
            result.error_message = str(e)
            logger.error("Failed to start transcription job: %s", e)
            raise

        return result

    async def process_channel_stream(
        self,
        audio_stream: asyncio.StreamReader,
        channel_id: int,
        sample_rate: int = 16000,
    ) -> AsyncIterator[ChannelSegment]:
        """
        Process real-time audio stream for a specific channel.

        Args:
            audio_stream: Audio stream
            channel_id: Channel identifier
            sample_rate: Sample rate in Hz

        Yields:
            ChannelSegment objects as they are transcribed
        """
        if not self.channel_processor:
            raise RuntimeError("Channel identification not enabled")

        logger.info(
            "Starting real-time transcription for channel %s at %sHz",
            channel_id,
            sample_rate,
        )

        # Initialize streaming client
        from src.voice.realtime_streaming import (  # pylint: disable=import-outside-toplevel
            MedicalStreamingTranscriber,
            StreamingConfig,
        )

        # Create streaming configuration
        stream_config = StreamingConfig(
            region=self.config.region,
            language_code=self.config.language_code.value,
            medical_specialty=self.config.specialty.value,
            sample_rate=sample_rate,
            enable_channel_identification=True,
            number_of_channels=2,
            enable_partial_results=True,
        )

        # Initialize streaming transcriber
        streaming_transcriber = MedicalStreamingTranscriber(stream_config)

        try:
            # Start streaming
            await streaming_transcriber.start_stream()

            # Process audio chunks
            while True:
                # Read audio chunk from stream
                chunk_size = int(sample_rate * 0.1)  # 100ms chunks
                audio_chunk = await audio_stream.read(
                    chunk_size * 2
                )  # 2 bytes per sample

                if not audio_chunk:
                    break

                # Convert bytes to numpy array
                audio_array = np.frombuffer(audio_chunk, dtype=np.int16)

                # Send audio to transcriber
                await streaming_transcriber.send_audio(audio_array)

                # Get results
                # TODO: Implement get_results method in MedicalStreamingTranscriber
                results: List[Any] = []  # await streaming_transcriber.get_results()

                for result in results:
                    # Extract medical entities
                    entities = []
                    if self.comprehend_medical:
                        try:
                            response = self.comprehend_medical.detect_entities_v2(
                                Text=result.transcript
                            )
                            entities = [
                                MedicalEntity(
                                    text=entity["Text"],
                                    category=entity["Category"],
                                    type=entity["Type"],
                                    score=entity["Score"],
                                    begin_offset=entity["BeginOffset"],
                                    end_offset=entity["EndOffset"],
                                    traits=[
                                        MedicalTrait(
                                            name=trait["Name"], score=trait["Score"]
                                        )
                                        for trait in entity.get("Traits", [])
                                    ],
                                )
                                for entity in response.get("Entities", [])
                            ]
                        except (AttributeError, ImportError, OSError, ValueError) as e:
                            logger.error("Error detecting medical entities: %s", e)

                    # Create channel segment
                    segment = ChannelSegment(
                        channel_id=channel_id,
                        start_time=result.start_time,
                        end_time=result.end_time,
                        text=result.transcript,
                        confidence=result.confidence,
                        speaker_label=f"Channel-{channel_id}",
                        medical_entities=[entity.__dict__ for entity in entities],
                    )

                    yield segment

        finally:
            # Stop streaming
            await streaming_transcriber.stop_stream()
            logger.info("Stopped real-time transcription for channel %s", channel_id)

    def export_channel_transcriptions(
        self, output_dir: Union[str, Path]
    ) -> Dict[str, Path]:
        """
        Export all channel transcriptions to files.

        Args:
            output_dir: Output directory

        Returns:
            Dictionary mapping output types to file paths
        """
        if not self.channel_transcription_manager:
            raise RuntimeError("No channel transcriptions available")

        return self.channel_transcription_manager.export_transcriptions(
            output_dir, include_metadata=True
        )

    def get_channel_configuration(self) -> Optional[Dict[str, Any]]:
        """Get current channel identification configuration."""
        if self.config.channel_config:
            return self.config.channel_config.to_dict()
        return None

    def update_channel_mapping(self, _channel_id: int, mapping: ChannelMapping) -> None:
        """
        Update mapping for a specific channel.

        Args:
            channel_id: Channel identifier
            mapping: New channel mapping
        """
        if not self.config.channel_config:
            raise RuntimeError("Channel identification not enabled")

        self.config.channel_config.add_channel_mapping(mapping)

        # Update processor if initialized
        if self.channel_processor:
            self.channel_processor = ChannelProcessor(self.config.channel_config)

        # Duplicate method - commented out
        # def enable_channel_identification(
        #     self,
        #     config: Optional[ChannelIdentificationConfig] = None,
        #     preset: Optional[str] = None,
        # ):
        #     """
        #     Enable channel identification for multi-channel transcription.
        #
        #     Args:
        #         config: Custom channel configuration
        #         preset: Use predefined configuration ('doctor_patient', 'telemedicine', 'emergency_room')
        #     """
        #     if preset:
        #         presets = {
        #             "doctor_patient": PredefinedConfigs.doctor_patient_consultation,
        #             "telemedicine": PredefinedConfigs.telemedicine_session,
        #             "emergency_room": PredefinedConfigs.emergency_room_recording,
        #         }
        #
        #         if preset in presets:
        #             self.config.channel_config = presets[preset]()
        #         else:
        #             raise ValueError(f"Unknown preset: {preset}")
        #     elif config:
        #         self.config.channel_config = config
        #     else:
        #         # Use default doctor-patient configuration
        #         self.config.channel_config = PredefinedConfigs.doctor_patient_consultation()
        #
        #     self.config.channel_identification = True
        #
        #     # Initialize processors
        #     self.channel_processor = ChannelProcessor(self.config.channel_config)
        #     self.channel_transcription_manager = ChannelTranscriptionManager(
        #         self.config.channel_config
        #     )
        #
        #     logger.info("Channel identification enabled")

        # Duplicate method - commented out
        # async def transcribe_multi_channel_audio(
        #     self,
        #     audio_file_path: Union[str, Path],
        #     job_name: Optional[str] = None,
        #     process_channels_separately: bool = True,
        # ) -> Dict[str, Any]:
        # """
        # Transcribe multi-channel audio with channel identification.
        #
        # Args:
        #     audio_file_path: Path to multi-channel audio file
        #     job_name: Optional custom job name
        #     process_channels_separately: Whether to process each channel separately
        #
        # Returns:
        #     Dictionary with channel-specific transcription results
        # """
        # if not self.channel_processor:
        #     raise RuntimeError(
        #         "Channel identification not enabled. Call enable_channel_identification() first."
        #     )
        #
        # # Generate job name if not provided
        # if not job_name:
        #     job_name = f"multi_channel_{uuid.uuid4().hex[:8]}"
        #
        # results = {
        #     "job_name": job_name,
        #     "channel_results": {},
        #     "merged_transcript": None,
        #     "medical_summary": None,
        #     "channel_metadata": {},
        # }
        #
        # try:
        #     # Process audio file to separate channels
        #     logger.info("Processing multi-channel audio: %s", audio_file_path)
        #     channel_data = self.channel_processor.process_file(audio_file_path)
        #
        #     if process_channels_separately:
        #         # Export separated channels
        #         temp_dir = Path(tempfile.gettempdir()) / f"transcribe_{job_name}"
        #         temp_dir.mkdir(exist_ok=True)
        #
        #         exported_files = self.channel_processor.export_channels(
        #             channel_data, temp_dir
        #         )
        #
        #         # Transcribe each channel
        #         for channel_id, channel_file in exported_files.items():
        #             if isinstance(channel_id, str) and channel_id.startswith(
        #                 "channel_"
        #             ):
        #                 ch_id = int(channel_id.split("_")[1])
        #
        #                 # Get channel mapping
        #                 mapping = self.config.channel_config.get_channel_mapping(ch_id)
        #
        #                 # Transcribe channel
        #                 channel_job_name = f"{job_name}_ch{ch_id}"
        #                 result = await self.transcribe_audio_file(
        #                     channel_file,
        #                     job_name=channel_job_name,
        #                     specialty=self._get_specialty_for_role(
        #                         mapping.role if mapping else None
        #                     ),
        #                 )
        #
        #                 # Wait for completion
        #                 result = await self.wait_for_completion(channel_job_name)
        #
        #                 # Add to channel results
        #                 results["channel_results"][ch_id] = result.to_dict()
        #
        #                 # Process transcription segments
        #                 if (
        #                     result.status == TranscriptionStatus.COMPLETED
        #                     and result.segments
        #                 ):
        #                     for segment in result.segments:
        #                         channel_segment = ChannelSegment(
        #                             channel_id=ch_id,
        #                             start_time=segment.start_time,
        #                             end_time=segment.end_time,
        #                             text=segment.text,
        #                             confidence=segment.confidence,
        #                             speaker_label=segment.speaker,
        #                         )
        #                         await self.channel_transcription_manager.add_transcription_segment(
        #                             ch_id, channel_segment
        #                         )
        #
        #         # Clean up temporary files
        #         import shutil  # pylint: disable=import-outside-toplevel
        #
        #         shutil.rmtree(temp_dir)
        #
        #     else:
        #         # Use AWS Transcribe's built-in channel identification
        #         # (This requires specific audio format with separate channels)
        #         result = await self._transcribe_with_channel_identification(
        #             audio_file_path, job_name
        #         )
        #         results["channel_results"]["combined"] = result.to_dict()
        #
        #     # Get channel metadata
        #     results["channel_metadata"] = self.channel_processor.get_channel_summary(
        #         channel_data
        #     )
        #
        #     # Generate merged transcript
        #     results["merged_transcript"] = (
        #         self.channel_transcription_manager.merge_channels()
        #     )
        #
        #     # Generate medical summary - Method doesn't exist
        #     # results["medical_summary"] = (
        #     #     self.channel_transcription_manager.generate_medical_summary()
        #     # )
        #
        #     return results
        #
        # except Exception as e:
        #     logger.error("Error in multi-channel transcription: %s", e)
        #     raise

    async def _transcribe_with_channel_identification_duplicate(
        self, audio_file_path: Union[str, Path], job_name: str
    ) -> TranscriptionResult:
        """
        Transcribe using AWS Transcribe's channel identification feature.

        Args:
            audio_file_path: Path to audio file
            job_name: Job name

        Returns:
            TranscriptionResult with channel information
        """
        # Upload file to S3
        s3_uri = await self._upload_audio_to_s3(audio_file_path, job_name)

        # Create transcription result
        result = TranscriptionResult(
            job_name=job_name,
            status=TranscriptionStatus.QUEUED,
            language_code=self.config.language_code.value,
            specialty=self.config.specialty.value,
            transcription_type=self.config.type.value,
            start_time=datetime.utcnow(),
        )

        try:
            # Configure settings with channel identification
            settings: dict[str, Any] = {
                "ShowSpeakerLabels": self.config.show_speaker_labels,
                "MaxSpeakerLabels": self.config.max_speaker_labels,
                "ChannelIdentification": True,  # Enable channel identification
            }

            if self.config.vocabulary_name:
                settings["VocabularyName"] = self.config.vocabulary_name

            # Start transcription job
            self.transcribe_client.start_medical_transcription_job(
                MedicalTranscriptionJobName=job_name,
                LanguageCode=self.config.language_code.value,
                MediaSampleRateHertz=self.config.sample_rate,
                MediaFormat=self._detect_audio_format(s3_uri),
                Media={"MediaFileUri": s3_uri},
                OutputBucketName=self.config.output_bucket,
                OutputEncryptionKMSKeyId=(
                    "alias/aws/s3" if self.config.output_encryption else None
                ),
                Settings=settings,
                ContentIdentificationType=(
                    "PHI" if self.config.content_redaction else None
                ),
                Specialty=self.config.specialty.value,
                Type=self.config.type.value,
            )

            result.status = TranscriptionStatus.IN_PROGRESS
            self._active_jobs[job_name] = result

            logger.info(
                "Started medical transcription job with channel identification: %s",
                job_name,
            )

        except ClientError as e:
            result.status = TranscriptionStatus.FAILED
            result.error_message = str(e)
            logger.error("Failed to start transcription job: %s", e)
            raise

        return result

    async def transcribe_audio_file_with_language_detection(
        self,
        audio_file_path: Union[str, Path],
        job_name: Optional[str] = None,
        medical_context: Optional[MedicalContext] = None,
        force_language: Optional[ExtendedLanguageCode] = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio file with automatic language detection.

        Args:
            audio_file_path: Path to audio file or S3 URI
            job_name: Optional custom job name
            medical_context: Optional medical context
            force_language: Force specific language instead of auto-detection

        Returns:
            TranscriptionResult object with detected language
        """
        if not self._service_available:
            raise RuntimeError("Transcribe Medical service not available")

        # Detect language if enabled and not forced
        detected_language = None
        if self.config.auto_detect_language and not force_language:
            detection_result = await self.language_detection_manager.detect_language(
                audio_file_path, medical_context=medical_context
            )

            # Check if detected language is supported for medical transcription
            if self.language_detection_manager.is_language_supported(
                detection_result.primary_language, for_medical_transcription=True
            ):
                detected_language = detection_result.primary_language
                logger.info("Using detected language: %s", detected_language.value)
            else:
                # Check alternatives
                for alt_lang, conf in detection_result.alternative_languages:
                    if (
                        conf > self.config.language_detection_confidence_threshold
                        and self.language_detection_manager.is_language_supported(
                            alt_lang, for_medical_transcription=True
                        )
                    ):
                        detected_language = alt_lang
                        logger.info(
                            "Using alternative language: %s", detected_language.value
                        )
                        break

        # Use forced language if provided
        if force_language:
            detected_language = force_language

        # Map to standard LanguageCode for Transcribe Medical
        if detected_language:
            # Map ExtendedLanguageCode to LanguageCode
            language_mapping = {
                ExtendedLanguageCode.EN_US: LanguageCode.EN_US,
                ExtendedLanguageCode.EN_GB: LanguageCode.EN_GB,
                ExtendedLanguageCode.ES_US: LanguageCode.ES_US,
            }

            transcribe_language = language_mapping.get(
                detected_language, self.config.language_code
            )
        else:
            transcribe_language = self.config.language_code

        # Update config temporarily for this transcription
        original_language = self.config.language_code
        self.config.language_code = transcribe_language

        try:
            # Perform transcription with detected/selected language
            result = await self.transcribe_audio_file(
                audio_file_path,
                job_name=job_name,
                specialty=self.config.specialty,
                custom_vocabulary=self.config.vocabulary_name,
            )

            # Add language detection metadata
            if detected_language:
                result.metadata["detected_language"] = detected_language.value
                result.metadata["language_detection_confidence"] = (
                    detection_result.confidence
                    if "detection_result" in locals()
                    else None
                )

            return result

        finally:
            # Restore original language config
            self.config.language_code = original_language

    async def detect_multi_language_segments(
        self,
        audio_file_path: Union[str, Path],
        window_size: float = 30.0,
        overlap: float = 5.0,
    ) -> List[MultiLanguageSegment]:
        """
        Detect language changes throughout an audio file.

        This method identifies segments where different languages are spoken,
        which is useful for multi-speaker or code-switching scenarios.

        Args:
            audio_file_path: Path to audio file
            window_size: Analysis window size in seconds
            overlap: Overlap between windows in seconds

        Returns:
            List of MultiLanguageSegment objects
        """
        if not self.config.enable_multi_language_detection:
            logger.warning("Multi-language detection not enabled. Enable it first.")
            return []

        logger.info("Detecting multi-language segments in: %s", audio_file_path)

        segments = await self.language_detection_manager.detect_multi_language_segments(
            audio_file_path, window_size=window_size, overlap=overlap
        )

        # Log summary
        if segments:
            languages_found = set(seg.primary_language for seg in segments)
            logger.info(
                "Found %d different languages in %d segments",
                len(languages_found),
                len(segments),
            )

            # Log code-switching events
            code_switch_count = sum(1 for seg in segments if seg.is_code_switching)
            if code_switch_count > 0:
                logger.info("Detected %d code-switching events", code_switch_count)

        return segments

    async def transcribe_multi_language_audio(
        self,
        audio_file_path: Union[str, Path],
        job_name_prefix: Optional[str] = None,
        medical_context: Optional[MedicalContext] = None,
    ) -> Dict[str, Any]:
        """
        Transcribe audio containing multiple languages.

        This method detects language segments and transcribes each segment
        with the appropriate language setting.

        Args:
            audio_file_path: Path to audio file
            job_name_prefix: Prefix for transcription job names
            medical_context: Optional medical context

        Returns:
            Dictionary containing segment transcriptions and metadata
        """
        if not self.config.enable_multi_language_detection:
            raise RuntimeError("Multi-language detection must be enabled first")

        # Detect language segments
        segments = await self.detect_multi_language_segments(audio_file_path)

        if not segments:
            logger.warning("No language segments detected")
            return {"segments": [], "error": "No language segments detected"}

        results: dict[str, Any] = {
            "audio_file": str(audio_file_path),
            "total_segments": len(segments),
            "languages_detected": list(
                set(seg.primary_language.value for seg in segments)
            ),
            "segment_results": [],
            "merged_transcript": "",
            "medical_context": medical_context.value if medical_context else None,
        }

        # Process each segment
        for i, segment in enumerate(segments):
            segment_job_name = f"{job_name_prefix or 'multi_lang'}_{i:03d}"

            logger.info(
                "Processing segment %d/%d: %s (%.1fs - %.1fs)",
                i + 1,
                len(segments),
                segment.primary_language.value,
                segment.start_time,
                segment.end_time,
            )

            # Skip if language not supported for medical transcription
            if not self.language_detection_manager.is_language_supported(
                segment.primary_language, for_medical_transcription=True
            ):
                logger.warning(
                    "Language %s not supported for medical transcription. Skipping segment.",
                    segment.primary_language.value,
                )
                results["segment_results"].append(
                    {
                        "segment_index": i,
                        "language": segment.primary_language.value,
                        "error": "Language not supported for medical transcription",
                    }
                )
                continue

            try:
                # Extract and transcribe segment
                # Upload original audio to S3 if needed
                if isinstance(audio_file_path, Path) or not str(
                    audio_file_path
                ).startswith("s3://"):
                    await self._upload_audio_to_s3(
                        audio_file_path, f"{segment_job_name}_full"
                    )
                else:
                    # S3 URI would be constructed here
                    str(audio_file_path)

                # Extract audio segment using ffmpeg or similar
                segment_file_path = await self._extract_audio_segment(
                    audio_file_path,
                    segment.start_time,
                    segment.end_time,
                    segment_job_name,
                )

                # Upload segment to S3
                segment_s3_uri = await self._upload_audio_to_s3(
                    segment_file_path, segment_job_name
                )

                # Transcribe the segment with appropriate language
                segment_result = await self.transcribe_audio_file(
                    segment_s3_uri,
                    job_name=segment_job_name,
                    specialty=MedicalSpecialty.PRIMARYCARE if medical_context else None,
                    custom_vocabulary=self.config.vocabulary_name,
                )

                # Wait for completion
                segment_result = await self.wait_for_completion(segment_job_name)

                if segment_result.status == TranscriptionStatus.COMPLETED:
                    results["segment_results"].append(
                        {
                            "segment_index": i,
                            "language": segment.primary_language.value,
                            "start_time": segment.start_time,
                            "end_time": segment.end_time,
                            "transcript": segment_result.transcript_text,
                            "confidence": segment.confidence,
                            "is_code_switching": segment.is_code_switching,
                        }
                    )

                    # Add to merged transcript
                    if segment_result.transcript_text:
                        results[
                            "merged_transcript"
                        ] += f"[{segment.primary_language.value}] "
                        results["merged_transcript"] += (
                            segment_result.transcript_text + " "
                        )
                else:
                    results["segment_results"].append(
                        {
                            "segment_index": i,
                            "language": segment.primary_language.value,
                            "error": segment_result.error_message
                            or "Transcription failed",
                        }
                    )

            except (ValueError, KeyError, RuntimeError) as e:
                logger.error("Error processing segment %d: %s", i, e)
                results["segment_results"].append(
                    {
                        "segment_index": i,
                        "language": segment.primary_language.value,
                        "error": str(e),
                    }
                )

        # Generate summary
        successful_segments = [
            r for r in results["segment_results"] if "error" not in r
        ]
        results["summary"] = {
            "successful_segments": len(successful_segments),
            "failed_segments": len(results["segment_results"])
            - len(successful_segments),
            "total_duration": max(seg.end_time for seg in segments) if segments else 0,
            "code_switching_detected": any(seg.is_code_switching for seg in segments),
        }

        return results

    def get_language_detection_info(self) -> Dict[str, Any]:
        """Get current language detection configuration and capabilities."""
        return {
            "enabled": self.config.auto_detect_language,
            "preferred_languages": [
                lang.value for lang in self.config.preferred_languages
            ],
            "confidence_threshold": self.config.language_detection_confidence_threshold,
            "multi_language_enabled": self.config.enable_multi_language_detection,
            "supported_languages": {
                "all": [
                    lang.value
                    for lang in self.language_detection_manager.get_supported_languages()
                ],
                "medical_transcription": [
                    lang.value
                    for lang in self.language_detection_manager.get_supported_languages(
                        medical_transcription_only=True
                    )
                ],
            },
        }

    def verify_language_from_transcript(
        self,
        transcript_text: str,
        expected_language: Optional[ExtendedLanguageCode] = None,
    ) -> Tuple[bool, LanguageDetectionResult]:
        """
        Verify the language of a transcribed text.

        This can be used to validate transcription language accuracy
        or detect potential language mismatches.

        Args:
            transcript_text: The transcribed text
            expected_language: The expected language (if known)

        Returns:
            Tuple of (matches_expected, detection_result)
        """
        # Run synchronous version of language detection
        result = asyncio.run(
            self.language_detection_manager.detect_language_from_text(transcript_text)
        )

        matches_expected = True
        if expected_language:
            matches_expected = result.primary_language == expected_language

            if not matches_expected:
                logger.warning(
                    "Language mismatch: expected %s, detected %s",
                    expected_language.value,
                    result.primary_language.value,
                )

        return matches_expected, result

    def configure_accent_adaptation(
        self,
        enable: bool = True,
        detection_enabled: bool = True,
        strategy: AdaptationStrategy = AdaptationStrategy.COMBINED,
        confidence_threshold: float = 0.6,
        apply_medical_variants: bool = True,
    ) -> None:
        """
        Configure accent adaptation settings.

        Args:
            enable: Enable accent adaptation
            detection_enabled: Enable automatic accent detection
            strategy: Adaptation strategy to use
            confidence_threshold: Minimum confidence for accent detection
            apply_medical_variants: Apply medical pronunciation variants
        """
        self.config.enable_accent_adaptation = enable
        self.config.accent_detection_enabled = detection_enabled
        self.config.adaptation_strategy = strategy
        self.config.accent_confidence_threshold = confidence_threshold
        self.config.apply_medical_pronunciation_variants = apply_medical_variants

        logger.info(
            "Accent adaptation configured: enabled=%s, strategy=%s",
            enable,
            strategy.value,
        )

    async def detect_accent(
        self, audio_file_path: Union[str, Path], quick_detection: bool = False
    ) -> "AccentDetectionResult":
        """
        Detect speaker accent from audio file.

        Args:
            audio_file_path: Path to audio file
            quick_detection: Use faster but less accurate detection

        Returns:
            AccentDetectionResult with detected accent information
        """
        logger.info("Detecting accent from: %s", audio_file_path)

        result = await self.accent_detector.detect_accent(
            audio_file_path, quick_detection=quick_detection
        )

        logger.info(
            "Detected accent: %s (strength: %s, confidence: %.2f%%)",
            result.primary_accent.value,
            result.accent_strength.value,
            result.confidence * 100,
        )

        if result.alternative_accents:
            alternatives = ", ".join(
                f"{acc.value}:{conf:.2f}"
                for acc, conf in result.alternative_accents[:3]
            )
            logger.info("Alternative accents: %s", alternatives)

        return result

    async def transcribe_with_accent_adaptation(
        self,
        audio_file_path: Union[str, Path],
        job_name: Optional[str] = None,
        force_accent: Optional[AccentRegion] = None,
        detect_language: bool = True,
    ) -> TranscriptionResult:
        """
        Transcribe audio with accent adaptation.

        Args:
            audio_file_path: Path to audio file
            job_name: Optional custom job name
            force_accent: Force specific accent instead of detection
            detect_language: Also detect language

        Returns:
            TranscriptionResult with accent adaptations applied
        """
        if not self._service_available:
            raise RuntimeError("Transcribe Medical service not available")

        # Detect accent if enabled and not forced
        accent_adaptations = None
        detected_accent = None

        if self.config.accent_detection_enabled and not force_accent:
            accent_result = await self.detect_accent(
                audio_file_path, quick_detection=True
            )

            # Check confidence threshold
            if accent_result.confidence >= self.config.accent_confidence_threshold:
                detected_accent = accent_result

                # Generate adaptations
                accent_adaptations = self.accent_adapter.adapt_for_speaker(
                    accent_result, strategy=self.config.adaptation_strategy
                )

                logger.info(
                    "Applied accent adaptations: %s",
                    self.accent_adapter.get_adaptation_summary(accent_adaptations),
                )

        # Use forced accent if provided
        if force_accent:
            accent_profile = self.accent_database.get_profile(force_accent)
            if accent_profile:
                # Create mock detection result for forced accent
                from .accent_adaptation.accent_detector import AccentConfidence

                accent_result = AccentDetectionResult(
                    primary_accent=force_accent,
                    accent_strength=accent_profile.accent_strength,
                    confidence=1.0,
                    confidence_level=AccentConfidence.HIGH,
                )
                accent_adaptations = self.accent_adapter.adapt_for_speaker(
                    accent_result, strategy=self.config.adaptation_strategy
                )

        # Update vocabulary with pronunciation variants if enabled
        custom_vocabulary = self.config.vocabulary_name
        if accent_adaptations and self.config.apply_medical_pronunciation_variants:
            # Create temporary custom vocabulary with accent variants
            vocabulary_updates = self._prepare_accent_vocabulary(accent_adaptations)
            if vocabulary_updates:
                # Update AWS Transcribe custom vocabulary
                try:
                    vocabulary_name = f"{self.config.vocabulary_name}_accent_{job_name}"

                    # Get existing vocabulary if it exists
                    existing_phrases = []
                    try:
                        vocab_response = self.transcribe_client.get_medical_vocabulary(
                            VocabularyName=self.config.vocabulary_name
                        )
                        if vocab_response.get("DownloadUri"):
                            # Download and parse existing vocabulary
                            import requests

                            resp = requests.get(
                                vocab_response["DownloadUri"], timeout=30
                            )
                            existing_phrases = resp.text.strip().split("\n")
                    except ClientError:
                        logger.info("No existing vocabulary found, creating new one")

                    # Combine existing and new phrases
                    new_phrases = []
                    for variants in vocabulary_updates.values():
                        new_phrases.extend(variants)
                    all_phrases = list(set(existing_phrases + new_phrases))

                    # Create vocabulary file content
                    vocabulary_content = "\n".join(all_phrases)

                    # Upload to S3
                    vocab_s3_key = f"vocabularies/{vocabulary_name}.txt"
                    self.s3_client.put_object(
                        Bucket=self.config.output_bucket,
                        Key=vocab_s3_key,
                        Body=vocabulary_content.encode("utf-8"),
                    )

                    # Create or update vocabulary
                    vocab_s3_uri = f"s3://{self.config.output_bucket}/{vocab_s3_key}"
                    try:
                        self.transcribe_client.create_medical_vocabulary(
                            VocabularyName=vocabulary_name,
                            LanguageCode=self.config.language_code.value,
                            VocabularyFileUri=vocab_s3_uri,
                        )
                        logger.info(
                            "Created accent-adapted vocabulary: %s", vocabulary_name
                        )
                    except ClientError as e:
                        if e.response["Error"]["Code"] == "ConflictException":
                            # Vocabulary exists, update it
                            self.transcribe_client.update_medical_vocabulary(
                                VocabularyName=vocabulary_name,
                                LanguageCode=self.config.language_code.value,
                                VocabularyFileUri=vocab_s3_uri,
                            )
                            logger.info(
                                "Updated accent-adapted vocabulary: %s", vocabulary_name
                            )
                        else:
                            raise

                    # Use the new vocabulary for transcription
                    custom_vocabulary = vocabulary_name

                    logger.info(
                        "Added %d pronunciation variants", len(vocabulary_updates)
                    )

                except (AttributeError, ImportError, OSError, ValueError) as e:
                    logger.error(
                        "Failed to update vocabulary with accent variants: %s", e
                    )
                    # Continue with default vocabulary

        # Perform transcription with adaptations
        try:
            # Adjust confidence threshold if needed
            settings_override = {}
            if accent_adaptations and "adaptations" in accent_adaptations:
                if "confidence" in accent_adaptations["adaptations"]:
                    confidence_adj = accent_adaptations["adaptations"]["confidence"]
                    # Adjust AWS Transcribe settings based on accent
                    base_adjustment = confidence_adj.get("base_adjustment", 0.0)

                    # AWS Transcribe doesn't directly expose confidence threshold adjustment,
                    # but we can use settings that affect accuracy
                    if base_adjustment < 0:
                        # Lower confidence expected, use more conservative settings
                        settings_override = {
                            "ShowAlternatives": True,
                            "MaxAlternatives": 3,
                            "ChannelIdentification": False,  # Disable if single speaker
                        }

                    # Store the adjustment for post-processing
                    self._confidence_adjustment = base_adjustment

                    logger.info(
                        "Adjusted transcription settings for accent. Base adjustment: %+.2f",
                        base_adjustment,
                    )

            # Transcribe with language detection if requested
            if detect_language:
                result = await self.transcribe_audio_file_with_language_detection(
                    audio_file_path, job_name=job_name
                )
            else:
                result = await self.transcribe_audio_file(
                    audio_file_path,
                    job_name=job_name,
                    custom_vocabulary=custom_vocabulary,
                    settings_override=settings_override,
                )

            # Add accent metadata to result
            if detected_accent:
                result.metadata["detected_accent"] = (
                    detected_accent.primary_accent.value
                )
                result.metadata["accent_strength"] = (
                    detected_accent.accent_strength.value
                )
                result.metadata["accent_confidence"] = detected_accent.confidence
                result.metadata["accent_adaptations_applied"] = True

            return result

        finally:
            # Restore original settings if changed
            # Note: original_config restoration removed as it was not defined
            pass

    def _prepare_accent_vocabulary(
        self, accent_adaptations: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Prepare vocabulary updates based on accent adaptations."""
        vocabulary_updates = {}

        if "adaptations" in accent_adaptations:
            # Add pronunciation variants
            if "pronunciation_variants" in accent_adaptations["adaptations"]:
                vocabulary_updates.update(
                    accent_adaptations["adaptations"]["pronunciation_variants"]
                )

            # Add medical term variants
            if "vocabulary" in accent_adaptations["adaptations"]:
                vocab_adapt = accent_adaptations["adaptations"]["vocabulary"]
                if "medical_variants" in vocab_adapt:
                    vocabulary_updates.update(vocab_adapt["medical_variants"])

        return vocabulary_updates

    def get_accent_profile(
        self, accent_region: AccentRegion
    ) -> Optional[AccentProfile]:
        """Get accent profile for a specific region."""
        return self.accent_database.get_profile(accent_region)

    def get_medical_pronunciation_variants(
        self, term: str, accent_region: Optional[AccentRegion] = None
    ) -> List[str]:
        """
        Get pronunciation variants for a medical term.

        Args:
            term: Medical term
            accent_region: Optional specific accent region

        Returns:
            List of pronunciation variants
        """
        variants = self.medical_pronunciation_db.get_variants(term, accent_region)
        return [v.variant for v in variants]

    def get_accent_adaptation_info(self) -> Dict[str, Any]:
        """Get current accent adaptation configuration and capabilities."""
        return {
            "enabled": self.config.enable_accent_adaptation,
            "detection_enabled": self.config.accent_detection_enabled,
            "strategy": self.config.adaptation_strategy.value,
            "confidence_threshold": self.config.accent_confidence_threshold,
            "medical_variants_enabled": self.config.apply_medical_pronunciation_variants,
            "supported_accents": [region.value for region in AccentRegion],
            "accent_profiles_loaded": len(self.accent_database.profiles),
            "medical_terms_with_variants": len(self.medical_pronunciation_db.terms),
        }
