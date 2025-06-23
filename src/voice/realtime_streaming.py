"""Real-time Streaming Module for Amazon Transcribe Medical.

This module implements real-time streaming transcription
for medical audio with WebSocket support.

Security Note: This module processes real-time PHI data through audio streams.
All streaming connections must use encrypted WebSocket (WSS) protocol. Audio
data must be encrypted in transit and access to streaming functionality should
be restricted to authorized healthcare personnel only through role-based access
controls.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import numpy as np

try:
    from amazon_transcribe.client import TranscribeStreamingClient
    from amazon_transcribe.handlers import TranscriptResultStreamHandler
    from amazon_transcribe.model import TranscriptEvent

    AMAZON_TRANSCRIBE_AVAILABLE = True
except ImportError:
    # Define placeholder classes
    TranscribeStreamingClient = None
    TranscriptResultStreamHandler = object
    TranscriptEvent = object
    AMAZON_TRANSCRIBE_AVAILABLE = False

from .confidence_thresholds import ConfidenceManager, TranscriptionWord
from .noise_reduction import NoiseReductionProcessor

logger = logging.getLogger(__name__)


class StreamingState(Enum):
    """States for streaming transcription."""

    IDLE = "idle"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class StreamingConfig:
    """Configuration for real-time streaming."""

    region: str = "us-east-1"
    language_code: str = "en-US"
    medical_specialty: str = "PRIMARYCARE"
    sample_rate: int = 16000
    # Streaming parameters
    enable_partial_results: bool = True
    enable_channel_identification: bool = False
    number_of_channels: int = 1
    enable_speaker_partitioning: bool = True

    # Audio chunking
    chunk_duration_ms: int = 100  # Send audio in 100ms chunks
    audio_queue_size: int = 100

    # Noise reduction
    enable_noise_reduction: bool = True
    noise_reduction_aggressiveness: float = 0.5

    # Vocabulary
    vocabulary_name: Optional[str] = None
    vocabulary_filter_name: Optional[str] = None

    # Callbacks
    on_partial_result: Optional[Callable] = None
    on_final_result: Optional[Callable] = None
    on_error: Optional[Callable] = None
    on_state_change: Optional[Callable] = None


@dataclass
class StreamingResult:
    """Result from streaming transcription."""

    transcript: str
    is_partial: bool
    is_final: bool

    # Timing
    start_time: float
    end_time: float

    # Confidence
    confidence: float
    words: List[TranscriptionWord] = field(default_factory=list)

    # Speaker
    speaker_label: Optional[str] = None
    channel_id: Optional[int] = None

    # Alternatives
    alternatives: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "transcript": self.transcript,
            "is_partial": self.is_partial,
            "is_final": self.is_final,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "confidence": self.confidence,
            "words": [w.__dict__ for w in self.words],
            "speaker_label": self.speaker_label,
            "channel_id": self.channel_id,
            "alternatives": self.alternatives,
        }


class StreamingTranscriptionHandler(TranscriptResultStreamHandler):
    """Custom handler for processing streaming transcription results."""

    def __init__(self, config: StreamingConfig, confidence_manager: ConfidenceManager):
        """Initialize the handler."""
        super().__init__(transcript_result_stream=None)
        self.config = config
        self.confidence_manager = confidence_manager
        self.results: List[StreamingResult] = []

    async def handle_transcript_event(self, transcript_event: TranscriptEvent) -> None:
        """Handle incoming transcript events."""
        results = transcript_event.results

        for result in results:
            if not result.alternatives:
                continue

            # Get the best alternative
            alternative = result.alternatives[0]

            # Extract words
            words = []
            for item in alternative.items or []:
                if hasattr(item, "content"):
                    word = TranscriptionWord(
                        text=item.content,
                        confidence=item.confidence or 0.0,
                        start_time=item.start_time or 0.0,
                        end_time=item.end_time or 0.0,
                        speaker=item.speaker or None,
                    )
                    words.append(word)

            # Create streaming result
            streaming_result = StreamingResult(
                transcript=alternative.transcript,
                is_partial=result.is_partial,
                is_final=not result.is_partial,
                start_time=result.start_time or 0.0,
                end_time=result.end_time or 0.0,
                confidence=alternative.confidence or 0.0,
                words=words,
                speaker_label=result.speaker or None,
                alternatives=[
                    {"transcript": alt.transcript, "confidence": alt.confidence}
                    for alt in result.alternatives[1:]
                ],
            )
            # Store result
            self.results.append(streaming_result)

            # Trigger callbacks
            if result.is_partial and self.config.on_partial_result:
                await self.config.on_partial_result(streaming_result)
            elif not result.is_partial and self.config.on_final_result:
                await self.config.on_final_result(streaming_result)


class MedicalStreamingTranscriber:
    """
    Real-time medical transcription with streaming support.

    Handles WebSocket connections to Amazon Transcribe Medical
    for live transcription of medical consultations.
    """

    def __init__(self, config: StreamingConfig):
        """
        Initialize the streaming transcriber.

        Args:
            config: Streaming configuration
        """
        self.config = config
        self.state = StreamingState.IDLE

        # AWS clients
        self.transcribe_client: Optional[Any] = None  # TranscribeStreamingClient
        self.stream: Optional[Any] = None  # TranscriptionStream

        # Audio handling
        self.audio_queue: asyncio.Queue[bytes] = asyncio.Queue(
            maxsize=config.audio_queue_size
        )
        self.chunk_size = int(config.sample_rate * config.chunk_duration_ms / 1000)

        # Components
        self.confidence_manager = ConfidenceManager()
        self.noise_processor: Optional[NoiseReductionProcessor] = None
        if config.enable_noise_reduction:
            self.noise_processor = NoiseReductionProcessor(
                sample_rate=config.sample_rate
            )

        # Results storage
        self.session_results: List[StreamingResult] = []
        self.current_speaker = None

        # Tasks
        self.streaming_task: Optional[asyncio.Task[None]] = None
        self.audio_sender_task: Optional[asyncio.Task[None]] = None
        logger.info(
            "MedicalStreamingTranscriber initialized with language=%s, specialty=%s",
            config.language_code,
            config.medical_specialty,
        )

    async def start_stream(self) -> None:
        """Start the streaming transcription session."""
        try:
            self._set_state(StreamingState.CONNECTING)

            # Initialize Transcribe streaming client
            self.transcribe_client = TranscribeStreamingClient(
                region=self.config.region
            )

            # Create stream
            self.stream = await self.transcribe_client.start_medical_stream_transcription(
                language_code=self.config.language_code,
                media_sample_rate_hz=self.config.sample_rate,
                media_encoding="pcm",
                specialty=self.config.medical_specialty,
                enable_channel_identification=self.config.enable_channel_identification,
                number_of_channels=self.config.number_of_channels,
                enable_speaker_partitioning=self.config.enable_speaker_partitioning,
                vocabulary_name=self.config.vocabulary_name,
                content_identification_type="PHI",  # Protected Health Information
            )

            # Set up handler
            handler = StreamingTranscriptionHandler(
                self.config, self.confidence_manager
            )

            # Start streaming tasks
            self.streaming_task = asyncio.create_task(self._handle_stream(handler))
            self.audio_sender_task = asyncio.create_task(self._send_audio_chunks())

            self._set_state(StreamingState.STREAMING)
            logger.info("Streaming transcription started")

        except Exception as e:
            logger.error("Failed to start stream: %s", str(e), exc_info=True)
            self._set_state(StreamingState.ERROR)
            if self.config.on_error:
                await self.config.on_error(e)
            raise

    async def stop_stream(self) -> None:
        """Stop the streaming transcription session."""
        try:
            self._set_state(StreamingState.STOPPING)

            # Cancel tasks
            if self.audio_sender_task:
                self.audio_sender_task.cancel()

            if self.streaming_task:
                self.streaming_task.cancel()

            # Close stream
            if self.stream:
                await self.stream.close()

            self._set_state(StreamingState.STOPPED)
            logger.info("Streaming transcription stopped")

        except (RuntimeError, ValueError, asyncio.CancelledError) as e:
            logger.error("Error stopping stream: %s", str(e), exc_info=True)
            self._set_state(StreamingState.ERROR)

    async def pause_stream(self) -> None:
        """Pause the streaming session."""
        if self.state == StreamingState.STREAMING:
            self._set_state(StreamingState.PAUSED)
            logger.info("Streaming paused")

    async def resume_stream(self) -> None:
        """Resume the streaming session."""
        if self.state == StreamingState.PAUSED:
            self._set_state(StreamingState.STREAMING)
            logger.info("Streaming resumed")

    async def send_audio(self, audio_data: np.ndarray) -> None:
        """
        Send audio data for transcription.

        Args:
            audio_data: Audio samples as numpy array
        """
        if self.state not in [StreamingState.STREAMING, StreamingState.PAUSED]:
            logger.warning("Cannot send audio in state: %s", self.state)
            return
        # Don't process if paused
        if self.state == StreamingState.PAUSED:
            return

        # Apply noise reduction if enabled
        if self.noise_processor and self.config.enable_noise_reduction:
            reduction_config = self.noise_processor.config
            reduction_config.aggressiveness = self.config.noise_reduction_aggressiveness

            result = await self.noise_processor.process_audio(
                audio_data, detect_noise=False
            )
            audio_data = result.processed_audio

        # Convert to bytes (16-bit PCM)
        audio_bytes = (audio_data * 32767).astype(np.int16).tobytes()

        # Add to queue
        try:
            await self.audio_queue.put(audio_bytes)
        except asyncio.QueueFull:
            logger.warning("Audio queue full, dropping audio chunk")

    async def _send_audio_chunks(self) -> None:
        """Send audio chunks to Transcribe stream."""
        try:
            while self.state in [StreamingState.STREAMING, StreamingState.PAUSED]:
                # Get audio from queue
                audio_chunk = await self.audio_queue.get()

                if self.state == StreamingState.STREAMING and self.stream:
                    # Send to Transcribe
                    await self.stream.send_audio_event(audio_chunk=audio_chunk)

                # Small delay to prevent overwhelming
                await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            logger.info("Audio sender task cancelled")
        except (RuntimeError, ValueError, AttributeError) as e:
            logger.error("Error sending audio: %s", str(e), exc_info=True)
            if self.config.on_error:
                await self.config.on_error(e)

    async def _handle_stream(self, handler: StreamingTranscriptionHandler) -> None:
        """Handle the transcription stream."""
        try:
            if self.stream is None:
                raise RuntimeError("Stream not initialized")
            async for event in self.stream.transcript_result_stream:
                await handler.handle_transcript_event(event)

                # Store results
                self.session_results.extend(handler.results)
                handler.results.clear()

        except asyncio.CancelledError:
            logger.info("Stream handler task cancelled")
        except (RuntimeError, ValueError, AttributeError) as e:
            logger.error("Error handling stream: %s", str(e), exc_info=True)
            if self.config.on_error:
                await self.config.on_error(e)

    def _set_state(self, state: StreamingState) -> None:
        """Set the streaming state and trigger callback."""
        old_state = self.state
        self.state = state

        if self.config.on_state_change:
            asyncio.create_task(self.config.on_state_change(old_state, state))

    def get_session_transcript(self) -> str:
        """Get the complete transcript for the current session."""
        final_results = [r for r in self.session_results if r.is_final]

        return " ".join(r.transcript for r in final_results)

    def get_session_results(self) -> List[StreamingResult]:
        """Get all results from the current session."""
        return self.session_results.copy()

    def clear_session(self) -> None:
        """Clear the current session data."""
        self.session_results.clear()
        self.current_speaker = None
        logger.info("Session data cleared")

    async def export_session(self, filepath: str) -> None:
        """Export session transcript to file."""
        export_data = {
            "session_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "language_code": self.config.language_code,
            "medical_specialty": self.config.medical_specialty,
            "transcript": self.get_session_transcript(),
            "results": [r.to_dict() for r in self.session_results],
            "statistics": self._calculate_session_statistics(),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)

        logger.info("Session exported to %s", filepath)

    def _calculate_session_statistics(self) -> Dict[str, Any]:
        """Calculate statistics for the current session."""
        if not self.session_results:
            return {}

        final_results = [r for r in self.session_results if r.is_final]

        # Calculate confidence stats
        confidences = [r.confidence for r in final_results if r.confidence > 0]

        # Count speakers
        speakers = set(r.speaker_label for r in final_results if r.speaker_label)

        # Calculate duration
        if final_results:
            start_time = min(r.start_time for r in final_results)
            end_time = max(r.end_time for r in final_results)
            duration = end_time - start_time
        else:
            duration = 0

        return {
            "total_segments": len(final_results),
            "total_words": sum(len(r.words) for r in final_results),
            "average_confidence": np.mean(confidences) if confidences else 0,
            "min_confidence": np.min(confidences) if confidences else 0,
            "max_confidence": np.max(confidences) if confidences else 0,
            "number_of_speakers": len(speakers),
            "duration_seconds": duration,
        }
