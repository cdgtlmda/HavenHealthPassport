"""
Integration module for Amazon Transcribe Medical with noise reduction.

This module provides the integration between the noise reduction
system and Amazon Transcribe Medical for improved transcription accuracy.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import boto3
import numpy as np

from .noise_reduction import (
    NoiseDetector,
    NoiseReductionConfig,
    NoiseReductionProcessor,
)

logger = logging.getLogger(__name__)


@dataclass
class TranscribeConfig:
    """Configuration for Amazon Transcribe Medical."""

    region: str = "us-east-1"
    language_code: str = "en-US"
    medical_specialty: str = "PRIMARYCARE"
    vocabulary_name: Optional[str] = None
    output_bucket: Optional[str] = None
    enable_speaker_identification: bool = True
    max_speaker_labels: int = 10
    enable_channel_identification: bool = False
    enable_vocabulary_filter: bool = False
    vocabulary_filter_name: Optional[str] = None

    # Audio settings
    sample_rate: int = 16000
    media_format: str = "wav"

    # Noise reduction settings
    enable_noise_reduction: bool = True
    noise_reduction_config: Optional[NoiseReductionConfig] = None


class TranscribeMedicalIntegration:
    """
    Integrates noise reduction with Amazon Transcribe Medical.

    for enhanced medical transcription accuracy.
    """

    def __init__(self, config: TranscribeConfig):
        """
        Initialize the Transcribe Medical integration.

        Args:
            config: Configuration for Transcribe Medical
        """
        self.config = config

        # Initialize AWS client
        self.transcribe_client = boto3.client("transcribe", region_name=config.region)

        # Initialize S3 client if output bucket is specified
        if config.output_bucket:
            self.s3_client = boto3.client("s3", region_name=config.region)
        else:
            self.s3_client = None

        # Initialize noise reduction if enabled
        self.noise_processor: Optional[NoiseReductionProcessor] = None
        self.noise_detector: Optional[NoiseDetector] = None

        if config.enable_noise_reduction:
            self.noise_processor = NoiseReductionProcessor(
                sample_rate=config.sample_rate, config=config.noise_reduction_config
            )
            self.noise_detector = NoiseDetector(sample_rate=config.sample_rate)

        logger.info(
            "TranscribeMedicalIntegration initialized with "
            "language=%s, "
            "specialty=%s, "
            "noise_reduction=%s",
            config.language_code,
            config.medical_specialty,
            "enabled" if config.enable_noise_reduction else "disabled",
        )

    async def transcribe_medical_audio(
        self,
        audio_data: Union[np.ndarray, Path],
        job_name: Optional[str] = None,
        detect_noise: bool = True,
    ) -> Dict[str, Any]:
        """
        Transcribe medical audio with optional noise reduction.

        Args:
            audio_data: Audio data as numpy array or file path
            job_name: Optional name for the transcription job
            detect_noise: Whether to detect noise before processing

        Returns:
            Transcription results including text and metadata
        """
        try:
            # Generate job name if not provided
            if not job_name:
                job_name = f"medical-transcription-{uuid.uuid4().hex[:8]}"

            # Load audio if path is provided
            if isinstance(audio_data, Path):
                # In real implementation, would load audio from file
                audio_array = np.array([])  # Placeholder
            else:
                audio_array = audio_data

            # Apply noise reduction if enabled
            processed_audio = audio_array
            noise_metrics: Dict[str, Any] = {}

            if self.config.enable_noise_reduction and self.noise_processor:
                logger.info("Applying noise reduction...")

                # Detect noise if requested
                detection_result = None
                if detect_noise and self.noise_detector:
                    detection_result = await self.noise_detector.detect_noise(
                        audio_array
                    )
                    noise_metrics["original_noise_level"] = (
                        detection_result.overall_noise_level.value
                    )
                    noise_metrics["original_snr"] = (
                        detection_result.signal_to_noise_ratio
                    )

                    # Auto-configure noise reduction based on detection
                    if not self.config.noise_reduction_config:
                        self.config.noise_reduction_config = (
                            self.noise_processor.get_recommended_config(
                                detection_result.overall_noise_level
                            )
                        )
                # Process audio
                reduction_result = await self.noise_processor.process_audio(
                    audio_array, detect_noise=False  # Already detected
                )

                processed_audio = reduction_result.processed_audio
                noise_metrics["processed_noise_level"] = (
                    reduction_result.processed_noise_level.value
                )
                noise_metrics["snr_improvement"] = reduction_result.snr_improvement
                noise_metrics["processing_warnings"] = reduction_result.warnings

            # Upload audio to S3
            audio_uri = await self._upload_audio_to_s3(processed_audio, job_name)

            # Start transcription job
            await self._start_transcription_job(job_name=job_name, media_uri=audio_uri)

            # Wait for completion
            result = await self._wait_for_transcription(job_name)

            # Add noise metrics to result
            if noise_metrics:
                result["noise_metrics"] = noise_metrics

            return result

        except Exception as e:
            logger.error("Error in medical transcription: %s", str(e), exc_info=True)
            raise

    async def _upload_audio_to_s3(self, audio_data: np.ndarray, job_name: str) -> str:
        """Upload audio data to S3 for transcription."""
        if not self.s3_client or not self.config.output_bucket:
            raise ValueError("S3 bucket not configured")

        # Convert audio to bytes (would use proper audio encoding in real implementation)
        audio_bytes = audio_data.tobytes()

        # Upload to S3
        key = f"transcribe-input/{job_name}.{self.config.media_format}"
        self.s3_client.put_object(
            Bucket=self.config.output_bucket,
            Key=key,
            Body=audio_bytes,
            ContentType=f"audio/{self.config.media_format}",
        )

        # Return S3 URI
        return f"s3://{self.config.output_bucket}/{key}"

    async def _start_transcription_job(
        self, job_name: str, media_uri: str
    ) -> Dict[str, Any]:
        """Start a medical transcription job."""
        job_params = {
            "MedicalTranscriptionJobName": job_name,
            "LanguageCode": self.config.language_code,
            "MediaSampleRateHertz": self.config.sample_rate,
            "MediaFormat": self.config.media_format,
            "Media": {"MediaFileUri": media_uri},
            "OutputBucketName": self.config.output_bucket,
            "Specialty": self.config.medical_specialty,
            "Type": "CONVERSATION",  # or 'DICTATION'
        }

        # Add optional parameters
        if self.config.vocabulary_name:
            job_params["MedicalTranscriptionJobName"] = self.config.vocabulary_name

        if self.config.enable_speaker_identification:
            job_params["Settings"] = {
                "ShowSpeakerLabels": True,
                "MaxSpeakerLabels": self.config.max_speaker_labels,
            }

        # Start the job
        response = self.transcribe_client.start_medical_transcription_job(**job_params)

        logger.info("Started medical transcription job: %s", job_name)
        return dict(response["MedicalTranscriptionJob"])

    async def _wait_for_transcription(self, job_name: str) -> Dict[str, Any]:
        """Wait for transcription job to complete."""
        max_attempts = 60  # 5 minutes with 5-second intervals
        attempt = 0

        while attempt < max_attempts:
            response = self.transcribe_client.get_medical_transcription_job(
                MedicalTranscriptionJobName=job_name
            )

            job = response["MedicalTranscriptionJob"]
            status = job["TranscriptionJobStatus"]

            if status == "COMPLETED":
                # Get transcript
                transcript_uri = job["Transcript"]["TranscriptFileUri"]
                transcript = await self._download_transcript(transcript_uri)

                return {
                    "job_name": job_name,
                    "status": "completed",
                    "transcript": transcript,
                    "completion_time": job.get("CompletionTime"),
                    "medical_specialty": job.get("Specialty"),
                }

            elif status == "FAILED":
                raise RuntimeError(
                    f"Transcription job failed: {job.get('FailureReason')}"
                )

            # Wait before next check
            await asyncio.sleep(5)
            attempt += 1

        raise TimeoutError(f"Transcription job {job_name} timed out")

    async def _download_transcript(self, transcript_uri: str) -> Dict[str, Any]:
        """Download and parse transcript from S3."""
        # Parse S3 URI
        parts = transcript_uri.replace("s3://", "").split("/", 1)
        bucket = parts[0]
        key = parts[1]

        # Download from S3
        response = self.s3_client.get_object(Bucket=bucket, Key=key)
        transcript_data = json.loads(response["Body"].read())

        return dict(transcript_data)

    def create_custom_vocabulary(
        self, vocabulary_name: str, terms: List[Dict[str, str]]
    ) -> None:
        """
        Create a custom medical vocabulary.

        Args:
            vocabulary_name: Name for the vocabulary
            terms: List of medical terms with pronunciations
        """
        vocabulary_params = {
            "VocabularyName": vocabulary_name,
            "LanguageCode": self.config.language_code,
            "Phrases": [term["phrase"] for term in terms],
        }

        self.transcribe_client.create_medical_vocabulary(**vocabulary_params)
        logger.info("Created medical vocabulary: %s", vocabulary_name)

    def update_noise_reduction_config(self, config: NoiseReductionConfig) -> None:
        """Update the noise reduction configuration."""
        self.config.noise_reduction_config = config

        if self.noise_processor:
            self.noise_processor.config = config
            logger.info("Updated noise reduction configuration")

    async def analyze_audio_quality(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """
        Analyze audio quality before transcription.

        Args:
            audio_data: Input audio data

        Returns:
            Quality analysis results
        """
        if not self.noise_detector:
            raise ValueError("Noise detector not initialized")

        # Detect noise
        detection_result = await self.noise_detector.detect_noise(audio_data)

        # Generate quality report
        quality_report = {
            "noise_level": detection_result.overall_noise_level.value,
            "signal_to_noise_ratio": detection_result.signal_to_noise_ratio,
            "noise_types": [
                p.noise_type.value for p in detection_result.noise_profiles
            ],
            "recommendations": detection_result.recommendations,
            "confidence_score": detection_result.confidence_score,
        }

        return quality_report
