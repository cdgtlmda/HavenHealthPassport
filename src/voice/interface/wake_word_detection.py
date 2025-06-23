"""Wake Word Detection Module.

This module implements wake word detection for hands-free activation
of the Haven Health Passport voice interface.

PRODUCTION IMPLEMENTATION:
- Uses Picovoice Porcupine for wake word detection
- Supports multiple languages for refugee populations
- Includes medical emergency wake words
- HIPAA-compliant audio handling
"""

import logging
import os
import queue
import threading
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class WakeWordStatus(Enum):
    """Status of wake word detection."""

    LISTENING = "listening"
    DETECTED = "detected"
    PROCESSING = "processing"
    TIMEOUT = "timeout"
    ERROR = "error"
    DISABLED = "disabled"


class WakeWordModel(Enum):
    """Available wake word detection models."""

    PORCUPINE = "porcupine"  # Picovoice Porcupine
    SNOWBOY = "snowboy"  # Snowboy (deprecated but still used)
    CUSTOM = "custom"  # Custom trained model
    WEBRTC_VAD = "webrtc_vad"  # WebRTC Voice Activity Detection


@dataclass
class WakeWord:
    """Represents a wake word configuration."""

    phrase: str
    sensitivity: float = 0.5  # 0.0 to 1.0
    language: str = "en"
    phonetic_variations: List[str] = field(default_factory=list)
    model_path: Optional[str] = None
    is_emergency: bool = False  # For medical emergency phrases
    custom_model_id: Optional[str] = None  # Picovoice custom model ID

    def __post_init__(self) -> None:
        """Validate wake word configuration."""
        if not 0.0 <= self.sensitivity <= 1.0:
            raise ValueError("Sensitivity must be between 0.0 and 1.0")

        # Validate language code
        valid_languages = ["en", "es", "ar", "fr", "de", "hi", "ja", "pt", "ru", "zh"]
        if self.language not in valid_languages:
            logger.warning(
                "Language '%s' not in supported list: %s",
                self.language,
                valid_languages,
            )


@dataclass
class WakeWordDetection:
    """Represents a detected wake word event."""

    wake_word: WakeWord
    confidence: float
    timestamp: datetime
    audio_segment: Optional[np.ndarray] = None
    energy_level: float = 0.0
    is_emergency: bool = False

    def is_valid(self, min_confidence: float = 0.7) -> bool:
        """Check if detection meets minimum confidence threshold."""
        # Lower threshold for emergency phrases to ensure they're not missed
        if self.is_emergency:
            return self.confidence >= max(0.5, min_confidence - 0.2)
        return self.confidence >= min_confidence


@dataclass
class WakeWordConfig:
    """Configuration for wake word detection."""

    wake_words: List[WakeWord] = field(default_factory=list)
    model_type: WakeWordModel = WakeWordModel.PORCUPINE
    sample_rate: int = 16000
    frame_length: int = 512  # samples per frame
    buffer_duration: float = 2.0  # seconds of audio buffer
    min_confidence: float = 0.7
    activation_timeout: float = 0.5  # seconds after detection
    noise_suppression: bool = True
    voice_activity_detection: bool = True
    emergency_mode: bool = True  # Enable emergency phrase detection
    custom_model_path: Optional[str] = None  # Path to custom Porcupine models

    def __post_init__(self) -> None:
        """Add default wake words if none provided."""
        if not self.wake_words:
            # Production wake words for Haven Health Passport
            self.wake_words = [
                # English wake words
                WakeWord(
                    phrase="Haven Health",
                    sensitivity=0.5,
                    language="en",
                    model_path=os.getenv("HAVEN_HEALTH_MODEL_PATH"),
                    custom_model_id="haven-health-en-v1",
                ),
                WakeWord(
                    phrase="Hey Haven",
                    sensitivity=0.5,
                    language="en",
                    model_path=os.getenv("HEY_HAVEN_MODEL_PATH"),
                    custom_model_id="hey-haven-en-v1",
                ),
                # Emergency phrases - higher sensitivity
                WakeWord(
                    phrase="Medical Emergency",
                    sensitivity=0.7,
                    language="en",
                    is_emergency=True,
                    model_path=os.getenv("EMERGENCY_EN_MODEL_PATH"),
                    custom_model_id="medical-emergency-en-v1",
                ),
                # Multi-language support for refugees
                WakeWord(
                    phrase="مساعدة طبية",  # "Medical help" in Arabic
                    sensitivity=0.6,
                    language="ar",
                    is_emergency=True,
                    model_path=os.getenv("EMERGENCY_AR_MODEL_PATH"),
                    custom_model_id="medical-help-ar-v1",
                ),
                WakeWord(
                    phrase="Ayuda médica",  # "Medical help" in Spanish
                    sensitivity=0.6,
                    language="es",
                    is_emergency=True,
                    model_path=os.getenv("EMERGENCY_ES_MODEL_PATH"),
                    custom_model_id="medical-help-es-v1",
                ),
                WakeWord(
                    phrase="Aide médicale",  # "Medical help" in French
                    sensitivity=0.6,
                    language="fr",
                    is_emergency=True,
                    model_path=os.getenv("EMERGENCY_FR_MODEL_PATH"),
                    custom_model_id="medical-help-fr-v1",
                ),
            ]


class WakeWordDetector(ABC):
    """Abstract base class for wake word detectors."""

    @abstractmethod
    def detect(self, audio_frame: np.ndarray) -> Optional[WakeWordDetection]:
        """Detect wake word in audio frame."""

    @abstractmethod
    def reset(self) -> None:
        """Reset detector state."""

    @abstractmethod
    def cleanup(self) -> None:
        """Clean up resources."""


class ProductionPorcupineDetector(WakeWordDetector):
    """Production wake word detector using Picovoice Porcupine.

    This implementation is designed for production use in medical settings
    with proper error handling, logging, and HIPAA compliance.
    """

    def __init__(self, config: WakeWordConfig):
        """Initialize the Porcupine wake word detector.

        Args:
            config: Wake word detection configuration
        """
        self.config = config
        self.porcupine: Any = None  # Porcupine instance, type is dynamically imported
        self.keyword_paths: List[str] = []
        self.sensitivities: List[float] = []
        self.wake_word_mapping: Dict[int, WakeWord] = (
            {}
        )  # Map keyword index to WakeWord
        self._initialize_porcupine()
        self._detection_count = 0
        self._error_count = 0
        self._last_detection_time: Optional[datetime] = None

    def _initialize_porcupine(self) -> None:
        """Initialize Porcupine engine with production configuration."""
        try:
            import pvporcupine  # noqa: PLC0415
            from pvporcupine import (  # noqa: PLC0415
                PorcupineActivationError,
                PorcupineError,
            )

            # Get Porcupine access key from environment
            access_key = os.getenv("PORCUPINE_ACCESS_KEY")
            if not access_key:
                raise ValueError(
                    "PORCUPINE_ACCESS_KEY environment variable not set. "
                    "This is required for production deployment. "
                    "Get your key at: https://console.picovoice.ai/"
                )

            # Validate and prepare wake word models
            for wake_word in self.config.wake_words:
                if wake_word.model_path and os.path.exists(wake_word.model_path):
                    # Use custom model file
                    self.keyword_paths.append(wake_word.model_path)
                    self.sensitivities.append(wake_word.sensitivity)
                    self.wake_word_mapping[len(self.keyword_paths) - 1] = wake_word
                    logger.info(
                        "Loaded custom wake word model: %s (%s) from %s",
                        wake_word.phrase,
                        wake_word.language,
                        wake_word.model_path,
                    )
                elif wake_word.custom_model_id:
                    # Check for downloaded model in standard location
                    model_dir = os.getenv(
                        "PORCUPINE_MODEL_DIR", "/opt/haven/models/porcupine"
                    )
                    model_path = os.path.join(
                        model_dir, f"{wake_word.custom_model_id}.ppn"
                    )

                    if os.path.exists(model_path):
                        self.keyword_paths.append(model_path)
                        self.sensitivities.append(wake_word.sensitivity)
                        self.wake_word_mapping[len(self.keyword_paths) - 1] = wake_word
                        logger.info(
                            "Loaded wake word model: %s", wake_word.custom_model_id
                        )
                    else:
                        logger.error(
                            "Wake word model not found: %s (%s). Expected at: %s. "
                            "Generate custom models at: https://console.picovoice.ai/ppn",
                            wake_word.phrase,
                            wake_word.language,
                            model_path,
                        )
                else:
                    logger.warning(
                        "Wake word '%s' has no model file. Skipping this wake word.",
                        wake_word.phrase,
                    )
            if not self.keyword_paths:
                raise ValueError(
                    "No valid wake word models found. Please ensure .ppn model files "
                    "are generated and paths are correctly configured."
                )

            # Initialize Porcupine with production settings
            self.porcupine = pvporcupine.create(
                access_key=access_key,
                keyword_paths=self.keyword_paths,
                sensitivities=self.sensitivities,
            )

            if self.porcupine is not None:
                logger.info(
                    "Initialized Porcupine with %d wake words. Frame length: %d, Sample rate: %d",
                    len(self.keyword_paths),
                    self.porcupine.frame_length,
                    self.porcupine.sample_rate,
                )

                # Validate configuration matches
                if self.porcupine.sample_rate != self.config.sample_rate:
                    logger.warning(
                        "Sample rate mismatch: Porcupine expects %d, config specifies %d",
                        self.porcupine.sample_rate,
                        self.config.sample_rate,
                    )

        except ImportError as exc:
            raise ImportError(
                "Porcupine SDK not installed. Install with: pip install pvporcupine. "
                "This is required for production deployment."
            ) from exc
        except PorcupineActivationError as e:
            raise RuntimeError(
                f"Porcupine activation error: {e}. "
                "Please check your access key and internet connection."
            ) from e
        except PorcupineError as e:
            raise RuntimeError(f"Porcupine initialization error: {e}") from e
        except (AttributeError, OSError, ValueError) as e:
            logger.error("Failed to initialize Porcupine: %s", e)
            raise

    def detect(self, audio_frame: np.ndarray) -> Optional[WakeWordDetection]:
        """Detect wake word using Porcupine with production error handling."""
        if self.porcupine is None:
            logger.error("Porcupine not initialized")
            return None

        try:
            # Ensure audio is in the correct format (16-bit PCM)
            if audio_frame.dtype != np.int16:
                # Convert float32 to int16
                if audio_frame.dtype == np.float32 or audio_frame.dtype == np.float64:
                    # Clip to prevent overflow
                    audio_frame = np.clip(audio_frame, -1.0, 1.0)
                    audio_frame = (audio_frame * 32767).astype(np.int16)
                else:
                    logger.error("Unsupported audio format: %s", audio_frame.dtype)
                    return None

            # Validate frame size
            if len(audio_frame) != self.porcupine.frame_length:
                logger.error(
                    "Audio frame size mismatch. Expected %d, got %d. Resampling may be required.",
                    self.porcupine.frame_length,
                    len(audio_frame),
                )
                return None

            # Process audio frame
            keyword_index = self.porcupine.process(audio_frame)

            if keyword_index >= 0:
                # Wake word detected
                if keyword_index not in self.wake_word_mapping:
                    logger.error("Invalid keyword index: %d", keyword_index)
                    return None

                wake_word = self.wake_word_mapping[keyword_index]

                # Calculate energy level for logging
                energy = np.sqrt(np.mean(audio_frame.astype(np.float32) ** 2)) / 32767.0

                # Track detection metrics
                self._detection_count += 1
                detection_time = datetime.now()
                self._last_detection_time = detection_time

                # Log detection (without audio data for HIPAA compliance)
                logger.info(
                    "Wake word detected: '%s' (lang: %s, emergency: %s, energy: %.3f, count: %d)",
                    wake_word.phrase,
                    wake_word.language,
                    wake_word.is_emergency,
                    energy,
                    self._detection_count,
                )

                detection = WakeWordDetection(
                    wake_word=wake_word,
                    confidence=0.95,  # Porcupine doesn't provide confidence scores
                    timestamp=detection_time,
                    audio_segment=(
                        audio_frame if not wake_word.is_emergency else None
                    ),  # Don't store emergency audio
                    energy_level=energy,
                    is_emergency=wake_word.is_emergency,
                )

                # For emergency detections, trigger immediate alert
                if wake_word.is_emergency:
                    self._handle_emergency_detection(detection)

                return detection

            # No wake word detected
            return None

        except (AttributeError, ImportError, OSError, ValueError) as e:
            self._error_count += 1
            logger.error(
                "Porcupine detection error (count: %d): %s",
                self._error_count,
                e,
                exc_info=True,
            )

            # If too many errors, attempt to reinitialize
            if self._error_count > 10:
                logger.warning(
                    "Too many detection errors. Attempting to reinitialize..."
                )
                self.reset()

            return None

    def _handle_emergency_detection(self, detection: WakeWordDetection) -> None:
        """Handle emergency wake word detection with immediate alerts."""
        logger.critical(
            "EMERGENCY WAKE WORD DETECTED: %s at %s",
            detection.wake_word.phrase,
            detection.timestamp.isoformat(),
        )

        # In production, this would trigger:
        # 1. Immediate notification to medical staff
        # 2. GPS location capture
        # 3. Emergency response protocol
        # 4. Priority audio streaming

        # Log to audit trail
        audit_data = {
            "event_type": "emergency_wake_word",
            "timestamp": detection.timestamp.isoformat(),
            "wake_word": detection.wake_word.phrase,
            "language": detection.wake_word.language,
            "energy_level": detection.energy_level,
        }

        # Write to secure audit log
        audit_log_path = os.getenv(
            "EMERGENCY_AUDIT_LOG", "/var/log/haven/emergency.log"
        )
        try:
            os.makedirs(os.path.dirname(audit_log_path), exist_ok=True)
            with open(audit_log_path, "a", encoding="utf-8") as f:
                f.write(f"{audit_data}\n")
        except (AttributeError, ImportError, OSError, ValueError) as e:
            logger.error("Failed to write emergency audit log: %s", e)

    def reset(self) -> None:
        """Reset Porcupine detector state."""
        logger.info("Resetting Porcupine detector")
        self._error_count = 0

        # Attempt to reinitialize if needed
        if self._error_count > 0 or not self.porcupine:
            try:
                self.cleanup()
                self._initialize_porcupine()
            except (AttributeError, ImportError, OSError, ValueError) as e:
                logger.error("Failed to reinitialize Porcupine: %s", e)

    def cleanup(self) -> None:
        """Clean up Porcupine resources."""
        if self.porcupine is not None:
            try:
                self.porcupine.delete()
                self.porcupine = None
                logger.info("Porcupine resources cleaned up")
            except (AttributeError, ImportError, OSError, ValueError) as e:
                logger.error("Error cleaning up Porcupine: %s", e)

    def get_metrics(self) -> Dict[str, Any]:
        """Get detection metrics for monitoring."""
        return {
            "detection_count": self._detection_count,
            "error_count": self._error_count,
            "last_detection": (
                self._last_detection_time.isoformat()
                if self._last_detection_time
                else None
            ),
            "active_wake_words": len(self.keyword_paths),
            "status": "active" if self.porcupine else "inactive",
        }

    def __del__(self) -> None:
        """Ensure cleanup on deletion."""
        self.cleanup()


class WakeWordEngine:
    """Production wake word detection engine for Haven Health Passport.

    Features:
    - Multi-language wake word support for refugees
    - Emergency phrase detection with priority handling
    - HIPAA-compliant audio processing
    - Automatic error recovery
    - Performance monitoring
    """

    def __init__(self, config: WakeWordConfig):
        """Initialize the wake word detection engine.

        Args:
            config: Wake word detection configuration
        """
        self.config = config
        self.status = WakeWordStatus.DISABLED
        self.detector: Optional[WakeWordDetector] = None
        self.audio_buffer: deque[np.ndarray] = deque(
            maxlen=int(config.sample_rate * config.buffer_duration)
        )
        self.detection_callbacks: List[Callable[[WakeWordDetection], None]] = []
        self.emergency_callbacks: List[Callable[[WakeWordDetection], None]] = []
        self.last_detection: Optional[WakeWordDetection] = None
        self._processing_thread: Optional[threading.Thread] = None
        self._audio_queue: queue.Queue = queue.Queue(maxsize=1000)  # Limit queue size
        self._stop_event = threading.Event()
        self._metrics = {
            "processed_frames": 0,
            "dropped_frames": 0,
            "detections": 0,
            "emergency_detections": 0,
            "errors": 0,
        }

        self._initialize_detector()
        self._start_monitoring()

    def _initialize_detector(self) -> None:
        """Initialize the appropriate wake word detector."""
        try:
            if self.config.model_type == WakeWordModel.PORCUPINE:
                self.detector = ProductionPorcupineDetector(self.config)
                logger.info("Initialized production Porcupine detector")
            else:
                raise NotImplementedError(
                    f"Model type {self.config.model_type} not implemented. "
                    "Only PORCUPINE is supported in production."
                )
        except (AttributeError, ImportError, OSError, ValueError) as e:
            logger.error("Failed to initialize detector: %s", e)
            self.status = WakeWordStatus.ERROR
            raise

    def _start_monitoring(self) -> None:
        """Start performance monitoring thread."""

        def monitor() -> None:
            while not self._stop_event.is_set():
                if self.status == WakeWordStatus.LISTENING:
                    # Log metrics every 60 seconds
                    logger.info(
                        "Wake word engine metrics: %s, queue size: %d",
                        self._metrics,
                        self._audio_queue.qsize(),
                    )
                self._stop_event.wait(60)

        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()

    def start(self) -> None:
        """Start wake word detection."""
        if self.status == WakeWordStatus.ERROR:
            logger.error("Cannot start - engine in error state")
            raise RuntimeError("Wake word engine in error state")

        if self.status != WakeWordStatus.DISABLED:
            logger.warning("Wake word detection already running")
            return

        try:
            self.status = WakeWordStatus.LISTENING
            self._stop_event.clear()
            self._processing_thread = threading.Thread(
                target=self._process_audio, daemon=True, name="WakeWordProcessor"
            )
            self._processing_thread.start()
            logger.info("Wake word detection started")

        except (AttributeError, ImportError, OSError, ValueError) as e:
            logger.error("Failed to start wake word detection: %s", e)
            self.status = WakeWordStatus.ERROR
            raise

    def stop(self) -> None:
        """Stop wake word detection."""
        if self.status == WakeWordStatus.DISABLED:
            return

        logger.info("Stopping wake word detection")
        self._stop_event.set()

        # Clear the queue to unblock processing thread
        try:
            while not self._audio_queue.empty():
                self._audio_queue.get_nowait()
        except queue.Empty:
            pass

        if self._processing_thread:
            self._processing_thread.join(timeout=2.0)
            if self._processing_thread.is_alive():
                logger.warning("Processing thread did not stop cleanly")

        self.status = WakeWordStatus.DISABLED
        logger.info("Wake word detection stopped. Final metrics: %s", self._metrics)

    def process_audio(self, audio_data: np.ndarray) -> None:
        """Process audio data for wake word detection.

        Args:
            audio_data: Audio samples to process
        """
        if self.status != WakeWordStatus.LISTENING:
            return

        try:
            # Add to queue for processing
            self._audio_queue.put_nowait(audio_data)
        except queue.Full:
            # Queue is full, drop the frame
            self._metrics["dropped_frames"] += 1
            if self._metrics["dropped_frames"] % 100 == 0:
                logger.warning(
                    "Dropped %d audio frames. Consider increasing queue size or processing speed.",
                    self._metrics["dropped_frames"],
                )

    def _process_audio(self) -> None:
        """Background thread for processing audio."""
        frame_buffer = []
        frame_size = self.config.frame_length
        consecutive_errors = 0

        while not self._stop_event.is_set():
            try:
                # Get audio from queue with timeout
                audio_data = self._audio_queue.get(timeout=0.1)

                # Add to buffer
                self.audio_buffer.extend(audio_data)
                frame_buffer.extend(audio_data)

                # Process complete frames
                while len(frame_buffer) >= frame_size:
                    frame = np.array(frame_buffer[:frame_size])
                    frame_buffer = frame_buffer[frame_size:]

                    # Detect wake word
                    detection = self.detector.detect(frame) if self.detector else None
                    self._metrics["processed_frames"] += 1

                    if detection and detection.is_valid(self.config.min_confidence):
                        self._handle_detection(detection)

                    # Reset error counter on successful processing
                    consecutive_errors = 0

            except queue.Empty:
                continue
            except (AttributeError, ImportError, OSError, ValueError) as e:
                logger.error("Error processing audio: %s", e, exc_info=True)
                self._metrics["errors"] += 1
                consecutive_errors += 1

                # If too many consecutive errors, go into error state
                if consecutive_errors > 10:
                    logger.critical("Too many consecutive errors in audio processing")
                    self.status = WakeWordStatus.ERROR
                    break

    def _handle_detection(self, detection: WakeWordDetection) -> None:
        """Handle wake word detection with priority for emergencies."""
        logger.info(
            "Wake word '%s' detected with confidence %.2f",
            detection.wake_word.phrase,
            detection.confidence,
        )

        self.last_detection = detection
        self.status = WakeWordStatus.DETECTED
        self._metrics["detections"] += 1

        if detection.is_emergency:
            self._metrics["emergency_detections"] += 1

            # Emergency detections get priority handling
            logger.critical(
                "EMERGENCY wake word detected: %s", detection.wake_word.phrase
            )

            # Notify emergency callbacks first
            for callback in self.emergency_callbacks:
                try:
                    callback(detection)
                except (AttributeError, ImportError, OSError, ValueError) as e:
                    logger.error("Error in emergency callback: %s", e, exc_info=True)

        # Notify regular callbacks
        for callback in self.detection_callbacks:
            try:
                callback(detection)
            except (AttributeError, ImportError, OSError, ValueError) as e:
                logger.error("Error in detection callback: %s", e, exc_info=True)

        # Reset after timeout (unless emergency)
        if not detection.is_emergency:
            threading.Timer(
                self.config.activation_timeout, self._reset_after_activation
            ).start()
        else:
            # Emergency mode stays active longer
            threading.Timer(
                self.config.activation_timeout * 3, self._reset_after_activation
            ).start()

    def _reset_after_activation(self) -> None:
        """Reset to listening state after activation timeout."""
        if self.status == WakeWordStatus.DETECTED:
            self.status = WakeWordStatus.LISTENING
            if self.detector:
                self.detector.reset()
            logger.debug("Reset to listening state")

    def add_callback(
        self, callback: Callable[[WakeWordDetection], None], is_emergency: bool = False
    ) -> None:
        """Add callback for wake word detection.

        Args:
            callback: Function to call on detection
            is_emergency: Whether this is an emergency callback
        """
        if is_emergency:
            self.emergency_callbacks.append(callback)
        else:
            self.detection_callbacks.append(callback)

    def remove_callback(self, callback: Callable[[WakeWordDetection], None]) -> None:
        """Remove detection callback."""
        if callback in self.detection_callbacks:
            self.detection_callbacks.remove(callback)
        if callback in self.emergency_callbacks:
            self.emergency_callbacks.remove(callback)

    def add_wake_word(self, wake_word: WakeWord) -> None:
        """Add a new wake word dynamically.

        Note: Requires restart to take effect with new model.
        """
        self.config.wake_words.append(wake_word)
        logger.info("Added wake word: %s. Restart required.", wake_word.phrase)

    def remove_wake_word(self, phrase: str) -> None:
        """Remove a wake word by phrase."""
        self.config.wake_words = [
            w for w in self.config.wake_words if w.phrase.lower() != phrase.lower()
        ]
        logger.info("Removed wake word: %s. Restart required.", phrase)

    def get_status(self) -> WakeWordStatus:
        """Get current detection status."""
        return self.status

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        metrics = self._metrics.copy()
        if self.detector and hasattr(self.detector, "get_metrics"):
            metrics.update(self.detector.get_metrics())
        return metrics

    def get_audio_buffer(self) -> np.ndarray:
        """Get current audio buffer (for diagnostics only)."""
        # Note: Accessing audio buffer should be logged for HIPAA compliance
        logger.warning("Audio buffer accessed - ensure HIPAA compliance")
        return np.array(self.audio_buffer)

    def clear_buffer(self) -> None:
        """Clear audio buffer."""
        self.audio_buffer.clear()
        logger.info("Audio buffer cleared")

    def cleanup(self) -> None:
        """Clean up all resources."""
        self.stop()
        if self.detector:
            self.detector.cleanup()


class MultilingualWakeWordEngine(WakeWordEngine):
    """Wake word engine with enhanced multi-language support for refugee populations."""

    def __init__(self, config: WakeWordConfig):
        """Initialize the multilingual wake word engine.

        Args:
            config: Wake word detection configuration
        """
        super().__init__(config)
        self.language_models: Dict[str, ProductionPorcupineDetector] = {}
        self.active_languages: List[str] = []
        self._initialize_language_models()

    def _initialize_language_models(self) -> None:
        """Initialize language-specific models for better accuracy."""
        # Group wake words by language
        language_groups: Dict[str, List[WakeWord]] = {}
        for wake_word in self.config.wake_words:
            lang = wake_word.language
            if lang not in language_groups:
                language_groups[lang] = []
            language_groups[lang].append(wake_word)

        # Create detector for each language
        for lang, words in language_groups.items():
            try:
                lang_config = WakeWordConfig(
                    wake_words=words,
                    model_type=self.config.model_type,
                    sample_rate=self.config.sample_rate,
                    frame_length=self.config.frame_length,
                    min_confidence=self.config.min_confidence,
                    emergency_mode=self.config.emergency_mode,
                )

                self.language_models[lang] = ProductionPorcupineDetector(lang_config)
                self.active_languages.append(lang)
                logger.info(
                    "Initialized %s language model with %d wake words", lang, len(words)
                )

            except (AttributeError, ImportError, OSError, ValueError) as e:
                logger.error("Failed to initialize %s language model: %s", lang, e)

        if not self.language_models:
            raise RuntimeError("No language models could be initialized")

        logger.info(
            "Multilingual engine initialized with languages: %s",
            ", ".join(self.active_languages),
        )

    def detect_multilingual(
        self, audio_frame: np.ndarray, language_hint: Optional[str] = None
    ) -> Optional[WakeWordDetection]:
        """Detect wake word with language preference.

        Args:
            audio_frame: Audio samples to process
            language_hint: Preferred language to check first

        Returns:
            Wake word detection result if found
        """
        detections = []

        # If language hint provided, try that first
        if language_hint and language_hint in self.language_models:
            detection = self.language_models[language_hint].detect(audio_frame)
            if detection:
                return detection

        # Try all other languages
        for lang, detector in self.language_models.items():
            if lang != language_hint:  # Skip if already tried
                try:
                    detection = detector.detect(audio_frame)
                    if detection:
                        detections.append(detection)
                except (AttributeError, ImportError, OSError, ValueError) as e:
                    logger.error("Error in %s detector: %s", lang, e)

        # Return highest confidence detection
        if detections:
            best_detection = max(detections, key=lambda d: d.confidence)
            logger.info(
                "Multilingual detection: %s (%s) confidence: %.2f",
                best_detection.wake_word.phrase,
                best_detection.wake_word.language,
                best_detection.confidence,
            )
            return best_detection

        return None

    def get_language_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for each language model."""
        metrics = {}
        for lang, detector in self.language_models.items():
            if hasattr(detector, "get_metrics"):
                metrics[lang] = detector.get_metrics()
        return metrics

    def cleanup(self) -> None:
        """Clean up all language models."""
        super().cleanup()
        for detector in self.language_models.values():
            detector.cleanup()


# Production configuration generator
def create_production_config() -> WakeWordConfig:
    """Create production wake word configuration with all safety features."""
    config = WakeWordConfig(
        model_type=WakeWordModel.PORCUPINE,
        sample_rate=16000,
        frame_length=512,
        buffer_duration=2.0,
        min_confidence=0.7,
        activation_timeout=0.5,
        noise_suppression=True,
        voice_activity_detection=True,
        emergency_mode=True,
    )

    # Ensure all required environment variables are set
    required_vars = [
        "PORCUPINE_ACCESS_KEY",
        "PORCUPINE_MODEL_DIR",
        "EMERGENCY_AUDIT_LOG",
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.warning(
            "Missing required environment variables: %s. Some features may not work correctly.",
            ", ".join(missing_vars),
        )

    return config


# Model download instructions
PORCUPINE_MODEL_INSTRUCTIONS = """
# Haven Health Passport - Wake Word Model Setup

To use custom wake words in production, you need to generate .ppn model files:

1. Go to https://console.picovoice.ai/
2. Sign up for a free account and get your access key
3. Create custom wake word models for:
   - "Haven Health" (English)
   - "Hey Haven" (English)
   - "Medical Emergency" (English)
   - "مساعدة طبية" (Arabic)
   - "Ayuda médica" (Spanish)
   - "Aide médicale" (French)
4. Download the .ppn files and place them in:
   /opt/haven/models/porcupine/
5. Set environment variables:
   export PORCUPINE_ACCESS_KEY="your-access-key"
   export PORCUPINE_MODEL_DIR="/opt/haven/models/porcupine"
   export HAVEN_HEALTH_MODEL_PATH="/opt/haven/models/porcupine/haven-health-en-v1.ppn"
   # ... set paths for all models

6. For production deployment, store the access key in AWS Secrets Manager:
   aws secretsmanager create-secret \\
     --name /haven/porcupine/access-key \\
     --secret-string "your-access-key"

Note: Each .ppn file is specific to the exact phrase and language.
Test thoroughly with speakers of different accents and ages.
"""

# Export the instructions for documentation
if __name__ == "__main__":
    print(PORCUPINE_MODEL_INSTRUCTIONS)
