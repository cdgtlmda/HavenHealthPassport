"""Language Detection for Medical Transcriptions.

This module provides automatic language detection capabilities for medical audio,
enabling multi-language support in healthcare settings with diverse patient populations.

# pylint: disable=too-many-lines

Note: Language detection involves analyzing audio that may contain PHI. Ensure
proper access control is implemented to restrict language detection operations
to authorized personnel only.
"""

import asyncio
import logging
import os
import wave
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import boto3
import numpy as np

from src.security import requires_phi_access

logger = logging.getLogger(__name__)


# Extended language codes for broader support
class ExtendedLanguageCode(Enum):
    """Extended language codes beyond Amazon Transcribe Medical."""

    EN_US = "en-US"  # US English
    EN_GB = "en-GB"  # British English
    ES_US = "es-US"  # US Spanish
    ES_ES = "es-ES"  # Spain Spanish
    FR_FR = "fr-FR"  # France French
    FR_CA = "fr-CA"  # Canadian French
    DE_DE = "de-DE"  # German
    PT_BR = "pt-BR"  # Brazilian Portuguese
    PT_PT = "pt-PT"  # Portugal Portuguese
    ZH_CN = "zh-CN"  # Simplified Chinese
    ZH_TW = "zh-TW"  # Traditional Chinese
    JA_JP = "ja-JP"  # Japanese
    KO_KR = "ko-KR"  # Korean
    IT_IT = "it-IT"  # Italian
    NL_NL = "nl-NL"  # Dutch
    RU_RU = "ru-RU"  # Russian
    AR_SA = "ar-SA"  # Arabic
    HI_IN = "hi-IN"  # Hindi
    SV_SE = "sv-SE"  # Swedish
    NO_NO = "no-NO"  # Norwegian
    DA_DK = "da-DK"  # Danish
    FI_FI = "fi-FI"  # Finnish
    PL_PL = "pl-PL"  # Polish
    TR_TR = "tr-TR"  # Turkish
    HE_IL = "he-IL"  # Hebrew


class LanguageConfidence(Enum):
    """Confidence levels for language detection."""

    HIGH = "high"  # > 0.9 confidence
    MEDIUM = "medium"  # 0.7 - 0.9 confidence
    LOW = "low"  # < 0.7 confidence


class MedicalContext(Enum):
    """Medical context that might influence language detection."""

    EMERGENCY = "emergency"
    CONSULTATION = "consultation"
    PHARMACY = "pharmacy"
    ADMISSION = "admission"
    DISCHARGE = "discharge"
    CONSENT = "consent"
    EDUCATION = "education"


@dataclass
class LanguageDetectionResult:
    """Result of language detection analysis."""

    primary_language: ExtendedLanguageCode
    confidence: float
    confidence_level: LanguageConfidence
    alternative_languages: List[Tuple[ExtendedLanguageCode, float]] = field(
        default_factory=list
    )
    detected_at: datetime = field(default_factory=datetime.utcnow)
    audio_duration: float = 0.0
    sample_rate: int = 0
    medical_context: Optional[MedicalContext] = None
    dialect_info: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "primary_language": self.primary_language.value,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "alternative_languages": [
                {"language": lang.value, "confidence": conf}
                for lang, conf in self.alternative_languages
            ],
            "detected_at": self.detected_at.isoformat(),
            "audio_duration": self.audio_duration,
            "sample_rate": self.sample_rate,
            "medical_context": (
                self.medical_context.value if self.medical_context else None
            ),
            "dialect_info": self.dialect_info,
        }


@dataclass
class MultiLanguageSegment:
    """Segment of audio that might contain multiple languages."""

    start_time: float
    end_time: float
    primary_language: ExtendedLanguageCode
    confidence: float
    is_code_switching: bool = False
    mixed_languages: List[ExtendedLanguageCode] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """Calculate segment duration."""
        return self.end_time - self.start_time


@dataclass
class LanguagePreferences:
    """User or system language preferences."""

    preferred_languages: List[ExtendedLanguageCode] = field(default_factory=list)
    fallback_language: ExtendedLanguageCode = ExtendedLanguageCode.EN_US
    auto_detect: bool = True
    min_confidence_threshold: float = 0.7
    enable_dialect_detection: bool = True
    medical_terminology_languages: List[ExtendedLanguageCode] = field(
        default_factory=list
    )
    enable_code_switching_detection: bool = True
    parallel_detection: bool = False  # Process multiple languages simultaneously


class LanguageDetectionManager:
    """
    Manager for language detection in medical audio.

    This class provides comprehensive language detection capabilities
    including multi-language support, dialect detection, and code-switching
    identification for medical transcriptions.
    """

    # Supported languages for medical transcription
    MEDICAL_TRANSCRIBE_LANGUAGES = [
        ExtendedLanguageCode.EN_US,
        ExtendedLanguageCode.EN_GB,
        ExtendedLanguageCode.ES_US,
    ]

    # All supported languages for detection
    ALL_SUPPORTED_LANGUAGES = [
        ExtendedLanguageCode.EN_US,
        ExtendedLanguageCode.EN_GB,
        ExtendedLanguageCode.ES_US,
        ExtendedLanguageCode.ES_ES,
        ExtendedLanguageCode.FR_FR,
        ExtendedLanguageCode.FR_CA,
        ExtendedLanguageCode.DE_DE,
        ExtendedLanguageCode.PT_BR,
        ExtendedLanguageCode.PT_PT,
        ExtendedLanguageCode.ZH_CN,
        ExtendedLanguageCode.ZH_TW,
        ExtendedLanguageCode.JA_JP,
        ExtendedLanguageCode.KO_KR,
        ExtendedLanguageCode.IT_IT,
        ExtendedLanguageCode.NL_NL,
        ExtendedLanguageCode.RU_RU,
        ExtendedLanguageCode.AR_SA,
        ExtendedLanguageCode.HI_IN,
        ExtendedLanguageCode.SV_SE,
        ExtendedLanguageCode.NO_NO,
        ExtendedLanguageCode.DA_DK,
        ExtendedLanguageCode.FI_FI,
        ExtendedLanguageCode.PL_PL,
        ExtendedLanguageCode.TR_TR,
        ExtendedLanguageCode.HE_IL,
    ]

    # Common medical terms in various languages for detection
    MEDICAL_INDICATORS = {
        "en": [
            "doctor",
            "hospital",
            "emergency",
            "pain",
            "medication",
            "prescription",
            "symptom",
            "diagnosis",
            "treatment",
            "patient",
            "nurse",
            "surgery",
        ],
        "es": [
            "doctor",
            "hospital",
            "emergencia",
            "dolor",
            "medicamento",
            "receta",
            "síntoma",
            "diagnóstico",
            "tratamiento",
            "paciente",
            "enfermera",
            "cirugía",
        ],
        "fr": [
            "médecin",
            "hôpital",
            "urgence",
            "douleur",
            "médicament",
            "ordonnance",
            "symptôme",
            "diagnostic",
            "traitement",
            "patient",
            "infirmière",
            "chirurgie",
        ],
        "de": [
            "arzt",
            "krankenhaus",
            "notfall",
            "schmerz",
            "medikament",
            "rezept",
            "symptom",
            "diagnose",
            "behandlung",
            "patient",
            "krankenschwester",
            "operation",
        ],
        "pt": [
            "médico",
            "hospital",
            "emergência",
            "dor",
            "medicamento",
            "receita",
            "sintoma",
            "diagnóstico",
            "tratamento",
            "paciente",
            "enfermeira",
            "cirurgia",
        ],
        "zh": [
            "医生",
            "医院",
            "急诊",
            "疼痛",
            "药物",
            "处方",
            "症状",
            "诊断",
            "治疗",
            "患者",
            "护士",
            "手术",
        ],
        "ja": [
            "医者",
            "病院",
            "緊急",
            "痛み",
            "薬",
            "処方箋",
            "症状",
            "診断",
            "治療",
            "患者",
            "看護師",
            "手術",
        ],
        "ko": [
            "의사",
            "병원",
            "응급",
            "통증",
            "약",
            "처방전",
            "증상",
            "진단",
            "치료",
            "환자",
            "간호사",
            "수술",
        ],
        "it": [
            "medico",
            "ospedale",
            "emergenza",
            "dolore",
            "medicina",
            "ricetta",
            "sintomo",
            "diagnosi",
            "trattamento",
            "paziente",
            "infermiera",
            "chirurgia",
        ],
        "nl": [
            "dokter",
            "ziekenhuis",
            "noodgeval",
            "pijn",
            "medicijn",
            "recept",
            "symptoom",
            "diagnose",
            "behandeling",
            "patiënt",
            "verpleegster",
            "operatie",
        ],
    }

    # Language family mappings for dialect detection
    LANGUAGE_FAMILIES = {
        "english": [ExtendedLanguageCode.EN_US, ExtendedLanguageCode.EN_GB],
        "spanish": [ExtendedLanguageCode.ES_US, ExtendedLanguageCode.ES_ES],
        "french": [ExtendedLanguageCode.FR_FR, ExtendedLanguageCode.FR_CA],
        "portuguese": [ExtendedLanguageCode.PT_BR, ExtendedLanguageCode.PT_PT],
        "chinese": [ExtendedLanguageCode.ZH_CN, ExtendedLanguageCode.ZH_TW],
    }

    def __init__(self, region_name: str = "us-east-1"):
        """Initialize the language detection manager."""
        self.transcribe_client = boto3.client("transcribe", region_name=region_name)
        self.comprehend_client = boto3.client(
            "comprehendmedical", region_name=region_name
        )
        self.region = region_name
        self.preferences = LanguagePreferences()
        self._language_models: Dict[str, Any] = {}
        self._detection_cache: Dict[str, Any] = {}

        logger.info("Language detection manager initialized")

    def configure_preferences(
        self,
        preferred_languages: List[ExtendedLanguageCode],
        fallback_language: ExtendedLanguageCode = ExtendedLanguageCode.EN_US,
        auto_detect: bool = True,
        min_confidence: float = 0.7,
        enable_dialect_detection: bool = True,
        enable_code_switching: bool = True,
    ) -> LanguagePreferences:
        """Configure language detection preferences."""
        self.preferences.preferred_languages = preferred_languages
        self.preferences.fallback_language = fallback_language
        self.preferences.auto_detect = auto_detect
        self.preferences.min_confidence_threshold = min_confidence
        self.preferences.enable_dialect_detection = enable_dialect_detection
        self.preferences.enable_code_switching_detection = enable_code_switching

        # Set medical terminology languages based on preferences
        self.preferences.medical_terminology_languages = [
            lang
            for lang in preferred_languages
            if lang in self.MEDICAL_TRANSCRIBE_LANGUAGES
        ]

        logger.info(
            "Configured language preferences: %d languages", len(preferred_languages)
        )
        return self.preferences

    @requires_phi_access("read")
    async def detect_language(
        self,
        audio_file_path: Union[str, Path],
        medical_context: Optional[MedicalContext] = None,
        quick_detection: bool = False,
        _user_id: str = "system",
    ) -> LanguageDetectionResult:
        """
        Detect language from an audio file.

        Args:
            audio_file_path: Path to the audio file
            medical_context: Optional medical context
            quick_detection: Use faster but less accurate detection

        Returns:
            LanguageDetectionResult with detected language information
        """
        audio_file_path = Path(audio_file_path)

        # Check cache first
        cache_key = f"{audio_file_path}:{quick_detection}"
        if cache_key in self._detection_cache:
            logger.info("Using cached language detection for %s", audio_file_path)
            return cast(LanguageDetectionResult, self._detection_cache[cache_key])

        # Read audio file metadata
        audio_duration, sample_rate = self._get_audio_metadata(audio_file_path)

        if quick_detection:
            # Use first 10 seconds for quick detection
            result = await self._detect_language_from_segment(
                audio_file_path, start_time=0, duration=min(10.0, audio_duration)
            )
        else:
            # Analyze multiple segments for more accurate detection
            segments = self._generate_analysis_segments(audio_duration)
            results = []

            for start, duration in segments:
                segment_result = await self._detect_language_from_segment(
                    audio_file_path, start_time=start, duration=duration
                )
                results.append(segment_result)

            # Aggregate results
            result = self._aggregate_detection_results(results)

        # Add metadata
        result.audio_duration = audio_duration
        result.sample_rate = sample_rate
        result.medical_context = medical_context

        # Detect dialect if enabled
        if self.preferences.enable_dialect_detection:
            result.dialect_info = await self._detect_dialect(
                audio_file_path, result.primary_language
            )

        # Cache result
        self._detection_cache[cache_key] = result

        return result

    async def _detect_language_from_segment(
        self, audio_file_path: Path, start_time: float, duration: float
    ) -> LanguageDetectionResult:
        """Detect language from a specific audio segment."""
        try:
            # Use Amazon Transcribe's language identification feature
            job_name = f"lang_detect_{audio_file_path.stem}_{int(start_time)}"

            # Upload audio to S3 (reusing method from transcribe service)
            s3_uri = await self._upload_audio_segment_to_s3(
                audio_file_path, start_time, duration, job_name
            )

            # Start language identification job
            self.transcribe_client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={"MediaFileUri": s3_uri},
                IdentifyLanguage=True,
                LanguageOptions=(
                    [lang.value for lang in self.preferences.preferred_languages]
                    if self.preferences.preferred_languages
                    else None
                ),
            )

            # Wait for job completion
            job_result = await self._wait_for_job_completion(job_name)

            # Parse results
            if job_result and "LanguageIdentification" in job_result:
                lang_results = job_result["LanguageIdentification"]

                # Get primary language
                primary_lang_code = lang_results[0]["LanguageCode"]
                primary_confidence = lang_results[0]["Score"]

                # Map to ExtendedLanguageCode
                primary_language = self._map_to_extended_language(primary_lang_code)

                # Get alternatives
                alternatives = [
                    (
                        self._map_to_extended_language(lang["LanguageCode"]),
                        lang["Score"],
                    )
                    for lang in lang_results[1:3]  # Top 3 alternatives
                    if lang["Score"] > 0.1
                ]

                # Determine confidence level
                if primary_confidence > 0.9:
                    confidence_level = LanguageConfidence.HIGH
                elif primary_confidence > 0.7:
                    confidence_level = LanguageConfidence.MEDIUM
                else:
                    confidence_level = LanguageConfidence.LOW

                return LanguageDetectionResult(
                    primary_language=primary_language,
                    confidence=primary_confidence,
                    confidence_level=confidence_level,
                    alternative_languages=alternatives,
                )
            else:
                # Fallback to default
                return LanguageDetectionResult(
                    primary_language=self.preferences.fallback_language,
                    confidence=0.0,
                    confidence_level=LanguageConfidence.LOW,
                )

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("Error detecting language: %s", e)
            # Return fallback result
            return LanguageDetectionResult(
                primary_language=self.preferences.fallback_language,
                confidence=0.0,
                confidence_level=LanguageConfidence.LOW,
            )

    async def detect_multi_language_segments(
        self,
        audio_file_path: Union[str, Path],
        window_size: float = 30.0,  # 30 second windows
        overlap: float = 5.0,  # 5 second overlap
    ) -> List[MultiLanguageSegment]:
        """
        Detect language changes throughout an audio file.

        This is useful for identifying code-switching or multi-speaker
        scenarios where different languages are used.

        Args:
            audio_file_path: Path to audio file
            window_size: Size of analysis window in seconds
            overlap: Overlap between windows in seconds

        Returns:
            List of MultiLanguageSegment objects
        """
        audio_file_path = Path(audio_file_path)
        audio_duration, _ = self._get_audio_metadata(audio_file_path)

        segments: List[MultiLanguageSegment] = []
        current_position = 0.0

        while current_position < audio_duration:
            # Detect language in current window
            window_duration = min(window_size, audio_duration - current_position)

            detection_result = await self._detect_language_from_segment(
                audio_file_path, current_position, window_duration
            )

            # Check if this is a language switch
            is_code_switching = False
            mixed_languages = []

            if (
                segments
                and detection_result.primary_language != segments[-1].primary_language
            ):
                is_code_switching = True
                # Check if multiple languages have high confidence
                if detection_result.alternative_languages:
                    for lang, conf in detection_result.alternative_languages:
                        if conf > 0.3:  # Significant presence
                            mixed_languages.append(lang)

            segment = MultiLanguageSegment(
                start_time=current_position,
                end_time=current_position + window_duration,
                primary_language=detection_result.primary_language,
                confidence=detection_result.confidence,
                is_code_switching=is_code_switching,
                mixed_languages=mixed_languages,
            )

            segments.append(segment)

            # Move to next window with overlap
            current_position += window_size - overlap

        # Merge consecutive segments with same language
        merged_segments = self._merge_consecutive_segments(segments)

        return merged_segments

    def _get_audio_metadata(self, audio_file_path: Path) -> Tuple[float, int]:
        """Get audio duration and sample rate."""
        try:
            with wave.open(str(audio_file_path), "rb") as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                duration = frames / float(rate)
                return duration, rate
        except (ValueError, OSError, RuntimeError) as e:
            logger.error("Error reading audio metadata: %s", e)
            return 0.0, 16000  # Default values

    def _generate_analysis_segments(
        self, audio_duration: float, max_segments: int = 5
    ) -> List[Tuple[float, float]]:
        """Generate segments for comprehensive language analysis."""
        segments: List[Tuple[float, float]] = []

        if audio_duration <= 30:
            # Analyze entire file for short audio
            segments.append((0, audio_duration))
        else:
            # Sample at beginning, middle, and end
            segment_duration = min(10.0, audio_duration / max_segments)

            # Beginning
            segments.append((0.0, segment_duration))

            # Middle segments
            middle_count = min(max_segments - 2, int(audio_duration / 60))
            for i in range(middle_count):
                start = (i + 1) * (audio_duration / (middle_count + 2))
                segments.append((start, segment_duration))

            # End
            segments.append((audio_duration - segment_duration, segment_duration))

        return segments

    def _aggregate_detection_results(
        self, results: List[LanguageDetectionResult]
    ) -> LanguageDetectionResult:
        """Aggregate multiple detection results into final result."""
        if not results:
            return LanguageDetectionResult(
                primary_language=self.preferences.fallback_language,
                confidence=0.0,
                confidence_level=LanguageConfidence.LOW,
            )

        # Count language occurrences weighted by confidence
        language_scores: Dict[ExtendedLanguageCode, List[float]] = {}

        for result in results:
            lang = result.primary_language
            if lang not in language_scores:
                language_scores[lang] = []
            language_scores[lang].append(result.confidence)

        # Calculate average confidence for each language
        language_avg_scores = {
            lang: sum(scores) / len(scores) for lang, scores in language_scores.items()
        }

        # Sort by average confidence
        sorted_languages = sorted(
            language_avg_scores.items(), key=lambda x: x[1], reverse=True
        )

        # Primary language
        primary_language = sorted_languages[0][0]
        primary_confidence = sorted_languages[0][1]

        # Alternative languages
        alternatives = [
            (lang, conf) for lang, conf in sorted_languages[1:4] if conf > 0.1
        ]

        # Determine confidence level
        if primary_confidence > 0.9:
            confidence_level = LanguageConfidence.HIGH
        elif primary_confidence > 0.7:
            confidence_level = LanguageConfidence.MEDIUM
        else:
            confidence_level = LanguageConfidence.LOW

        return LanguageDetectionResult(
            primary_language=primary_language,
            confidence=primary_confidence,
            confidence_level=confidence_level,
            alternative_languages=alternatives,
        )

    def _map_to_extended_language(self, language_code: str) -> ExtendedLanguageCode:
        """Map AWS language code to ExtendedLanguageCode."""
        # Normalize language code
        normalized = language_code.replace("_", "-")

        # Try direct mapping
        for lang in ExtendedLanguageCode:
            if lang.value.lower() == normalized.lower():
                return lang

        # Try partial matching (e.g., 'en' matches 'en-US')
        lang_prefix = normalized.split("-")[0].lower()
        for lang in ExtendedLanguageCode:
            if lang.value.lower().startswith(lang_prefix):
                return lang

        # Default fallback
        return self.preferences.fallback_language

    def _merge_consecutive_segments(
        self, segments: List[MultiLanguageSegment]
    ) -> List[MultiLanguageSegment]:
        """Merge consecutive segments with the same language."""
        if not segments:
            return []

        merged = [segments[0]]

        for segment in segments[1:]:
            last_segment = merged[-1]

            # Merge if same language and high confidence
            if (
                segment.primary_language == last_segment.primary_language
                and segment.confidence > 0.7
                and not segment.is_code_switching
            ):
                # Extend the last segment
                last_segment.end_time = segment.end_time
                # Update confidence as weighted average
                total_duration = last_segment.duration + segment.duration
                last_segment.confidence = (
                    last_segment.confidence * last_segment.duration
                    + segment.confidence * segment.duration
                ) / total_duration
            else:
                merged.append(segment)

        return merged

    async def _detect_dialect(
        self, audio_file_path: Optional[Path], language: ExtendedLanguageCode
    ) -> Optional[str]:
        """Detect dialect or regional variation of a language using audio features."""
        try:
            # Extract acoustic features for dialect detection
            try:
                import librosa  # noqa: PLC0415
            except ImportError:
                logger.warning("librosa not available for dialect detection")
                return None

            # Load audio file
            if audio_file_path is None:
                return None
            y, sr = librosa.load(str(audio_file_path), sr=16000)

            # Extract dialect-specific features
            # 1. Pitch/F0 contours (dialect-specific intonation patterns)
            f0, _, _ = librosa.pyin(
                y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7")
            )
            f0_mean = np.nanmean(f0[f0 > 0]) if np.any(f0 > 0) else 0
            f0_std = np.nanstd(f0[f0 > 0]) if np.any(f0 > 0) else 0

            # 2. Formant frequencies (vowel characteristics)
            # Using spectral features as proxy
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]

            # 3. Rhythm and timing (stress patterns)
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

            # 4. MFCC features (overall spectral characteristics)
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            mfcc_means = np.mean(mfccs, axis=1)

            # Create feature vector
            features = np.concatenate(
                [
                    [f0_mean, f0_std],
                    [np.mean(spectral_centroids), np.std(spectral_centroids)],
                    [np.mean(spectral_rolloff), np.std(spectral_rolloff)],
                    [tempo],
                    mfcc_means,
                ]
            )

            # Dialect detection based on acoustic patterns
            dialect = self._classify_dialect_from_features(features, language)

            if dialect:
                logger.info("Detected dialect: %s for language %s", dialect, language)
                return dialect

        except (AttributeError, ImportError, OSError, ValueError) as e:
            logger.warning("Failed to detect dialect from audio: %s", str(e))

        # Fallback to language-based mapping
        dialect_map = {
            ExtendedLanguageCode.EN_US: "American English",
            ExtendedLanguageCode.EN_GB: "British English",
            ExtendedLanguageCode.ES_US: "Latin American Spanish",
            ExtendedLanguageCode.ES_ES: "European Spanish",
            ExtendedLanguageCode.FR_FR: "Metropolitan French",
            ExtendedLanguageCode.FR_CA: "Canadian French",
            ExtendedLanguageCode.PT_BR: "Brazilian Portuguese",
            ExtendedLanguageCode.PT_PT: "European Portuguese",
            ExtendedLanguageCode.ZH_CN: "Simplified Chinese (Mandarin)",
            ExtendedLanguageCode.ZH_TW: "Traditional Chinese (Mandarin)",
            ExtendedLanguageCode.AR_SA: "Arabic",
        }

        return dialect_map.get(language, None)

    def _classify_dialect_from_features(
        self, features: np.ndarray, language: ExtendedLanguageCode
    ) -> Optional[str]:
        """Classify dialect based on acoustic features.

        This uses predefined acoustic patterns for different dialects.
        In production, this would use a trained ML model.
        """
        # English dialect detection based on acoustic patterns
        if language.value.startswith("en"):
            # F0 patterns: American English typically has less pitch variation
            f0_mean, f0_std = features[0], features[1]

            if f0_std < 30:  # Less pitch variation
                if f0_mean > 120:  # Higher average pitch
                    return "American English (West Coast)"
                else:
                    return "American English (General)"
            elif f0_std > 50:  # More pitch variation
                if f0_mean > 130:
                    return "British English (RP)"
                else:
                    return "British English (Regional)"
            else:
                return "International English"

        # Spanish dialect detection
        elif language.value.startswith("es"):
            tempo = features[6]
            spectral_mean = features[2]

            if tempo > 120:  # Faster speech rate
                if spectral_mean > 2000:
                    return "European Spanish (Castilian)"
                else:
                    return "European Spanish (Regional)"
            else:  # Slower speech rate
                if spectral_mean < 1800:
                    return "Mexican Spanish"
                else:
                    return "Latin American Spanish (General)"

        # Arabic dialect detection
        elif language.value.startswith("ar"):
            # Pharyngeal consonants affect spectral characteristics
            spectral_rolloff = features[4]
            mfcc1 = features[7]

            if spectral_rolloff > 3000 and mfcc1 < -10:
                return "Egyptian Arabic"
            elif spectral_rolloff < 2500:
                return "Levantine Arabic"
            else:
                return "Gulf Arabic"

        # Chinese dialect detection
        elif language.value.startswith("zh"):
            # Tonal patterns
            f0_std = features[1]

            if f0_std > 60:  # High tonal variation
                return "Cantonese"
            elif f0_std > 40:
                return "Mandarin (Beijing)"
            else:
                return "Mandarin (Standard)"

        return None

    async def _upload_audio_segment_to_s3(
        self, audio_file_path: Path, start_time: float, duration: float, job_name: str
    ) -> str:
        """Upload audio segment to S3 for processing.

        Args:
            audio_file_path: Path to the audio file
            start_time: Start time in seconds
            duration: Duration in seconds
            job_name: Unique job name for this segment

        Returns:
            S3 URI of the uploaded segment
        """
        import io  # noqa: PLC0415

        try:
            from pydub import AudioSegment  # noqa: PLC0415
        except ImportError:
            logger.error("pydub not installed. Install with: pip install pydub")
            raise

        try:
            # Load the audio file
            audio_format = audio_file_path.suffix[1:]  # Remove the dot
            if audio_format == "mp3":
                audio = AudioSegment.from_mp3(str(audio_file_path))
            elif audio_format == "wav":
                audio = AudioSegment.from_wav(str(audio_file_path))
            elif audio_format in ["m4a", "mp4"]:
                audio = AudioSegment.from_file(str(audio_file_path), format="mp4")
            elif audio_format == "flac":
                audio = AudioSegment.from_file(str(audio_file_path), format="flac")
            else:
                # Try to auto-detect format
                audio = AudioSegment.from_file(str(audio_file_path))

            # Extract the segment (times in milliseconds for pydub)
            start_ms = int(start_time * 1000)
            end_ms = int((start_time + duration) * 1000)

            # Ensure we don't exceed audio length
            audio_duration_ms = len(audio)
            if start_ms >= audio_duration_ms:
                logger.warning("Start time %ss exceeds audio duration", start_time)
                start_ms = max(0, audio_duration_ms - 1000)  # Last second

            if end_ms > audio_duration_ms:
                end_ms = audio_duration_ms

            # Extract segment
            segment = audio[start_ms:end_ms]

            # Convert to WAV format for compatibility
            # Set parameters for speech processing
            segment = segment.set_frame_rate(16000)  # 16kHz for speech
            segment = segment.set_channels(1)  # Mono
            segment = segment.set_sample_width(2)  # 16-bit

            # Export to bytes buffer
            buffer = io.BytesIO()
            segment.export(buffer, format="wav")
            buffer.seek(0)

            # Upload to S3
            s3_client = boto3.client("s3")

            # Determine bucket and key
            bucket_name = os.getenv(
                "LANGUAGE_DETECTION_BUCKET", "haven-health-language-detection"
            )
            key = f"audio-segments/{job_name}/{start_time}-{duration}s.wav"

            # Upload with metadata
            s3_client.upload_fileobj(
                buffer,
                bucket_name,
                key,
                ExtraArgs={
                    "ContentType": "audio/wav",
                    "Metadata": {
                        "original-file": audio_file_path.name,
                        "start-time": str(start_time),
                        "duration": str(duration),
                        "sample-rate": "16000",
                        "channels": "1",
                        "job-name": job_name,
                    },
                },
            )

            s3_uri = f"s3://{bucket_name}/{key}"
            logger.info("Uploaded audio segment to %s", s3_uri)

            return s3_uri

        except ImportError:
            logger.error("pydub not installed. Install with: pip install pydub")
            raise
        except (AttributeError, OSError, ValueError) as e:
            logger.error("Failed to upload audio segment: %s", e)
            # Fallback to mock URI for development
            bucket = "haven-health-language-detection"
            key = f"audio-segments/{job_name}/{start_time}-{duration}s.wav"
            return f"s3://{bucket}/{key}"

    async def _wait_for_job_completion(self, job_name: str) -> Optional[Dict[str, Any]]:
        """Wait for transcription job to complete."""
        max_attempts = 60  # 5 minutes with 5-second intervals
        attempts = 0

        while attempts < max_attempts:
            try:
                response = self.transcribe_client.get_transcription_job(
                    TranscriptionJobName=job_name
                )

                status = response["TranscriptionJob"]["TranscriptionJobStatus"]

                if status == "COMPLETED":
                    return cast(Dict[str, Any], response["TranscriptionJob"])
                elif status == "FAILED":
                    logger.error("Transcription job %s failed", job_name)
                    return None

                # Wait before next attempt
                await asyncio.sleep(5)
                attempts += 1

            except (ValueError, RuntimeError, AttributeError) as e:
                logger.error("Error checking job status: %s", e)
                return None

        logger.error("Timeout waiting for job %s", job_name)
        return None

    @requires_phi_access("read")
    async def detect_language_from_text(
        self,
        text: str,
        medical_context: Optional[MedicalContext] = None,
        _user_id: str = "system",
    ) -> LanguageDetectionResult:
        """
        Detect language from transcribed text.

        Note: Text may contain PHI - ensure proper encryption when storing results.

        This is useful for post-transcription language verification
        or when working with text-based medical records.

        Args:
            text: Text to analyze
            medical_context: Optional medical context

        Returns:
            LanguageDetectionResult
        """
        try:
            # Use Amazon Comprehend Medical for language detection
            response = self.comprehend_client.detect_dominant_language(
                Text=text[:5000]  # Comprehend has a character limit
            )

            if "Languages" in response and response["Languages"]:
                # Get primary language
                primary_result = response["Languages"][0]
                language_code = primary_result["LanguageCode"]
                confidence = primary_result["Score"]

                # Map to ExtendedLanguageCode
                primary_language = self._map_comprehend_to_extended(language_code)

                # Get alternatives
                alternatives = []
                for alt in response["Languages"][1:4]:
                    alt_lang = self._map_comprehend_to_extended(alt["LanguageCode"])
                    alternatives.append((alt_lang, alt["Score"]))

                # Determine confidence level
                if confidence > 0.9:
                    confidence_level = LanguageConfidence.HIGH
                elif confidence > 0.7:
                    confidence_level = LanguageConfidence.MEDIUM
                else:
                    confidence_level = LanguageConfidence.LOW
                # Check for medical terminology
                if medical_context:
                    confidence = self._adjust_confidence_for_medical_terms(
                        text, primary_language, confidence
                    )
                return LanguageDetectionResult(
                    primary_language=primary_language,
                    confidence=confidence,
                    confidence_level=confidence_level,
                    alternative_languages=alternatives,
                    medical_context=medical_context,
                )

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("Error detecting language from text: %s", e)
        # Fallback
        return LanguageDetectionResult(
            primary_language=self.preferences.fallback_language,
            confidence=0.0,
            confidence_level=LanguageConfidence.LOW,
            medical_context=medical_context,
        )

    def _map_comprehend_to_extended(self, language_code: str) -> ExtendedLanguageCode:
        """Map Amazon Comprehend language code to ExtendedLanguageCode."""
        # Comprehend uses ISO 639-1 codes (e.g., 'en', 'es', 'fr')
        # We need to map to our extended codes
        comprehend_to_extended = {
            "en": ExtendedLanguageCode.EN_US,  # Default to US English
            "es": ExtendedLanguageCode.ES_US,  # Default to US Spanish
            "fr": ExtendedLanguageCode.FR_FR,  # Default to France French
            "de": ExtendedLanguageCode.DE_DE,
            "pt": ExtendedLanguageCode.PT_BR,  # Default to Brazilian
            "zh": ExtendedLanguageCode.ZH_CN,  # Default to Simplified
            "ja": ExtendedLanguageCode.JA_JP,
            "ko": ExtendedLanguageCode.KO_KR,
            "it": ExtendedLanguageCode.IT_IT,
            "nl": ExtendedLanguageCode.NL_NL,
            "ru": ExtendedLanguageCode.RU_RU,
            "ar": ExtendedLanguageCode.AR_SA,
            "hi": ExtendedLanguageCode.HI_IN,
            "sv": ExtendedLanguageCode.SV_SE,
            "no": ExtendedLanguageCode.NO_NO,
            "da": ExtendedLanguageCode.DA_DK,
            "fi": ExtendedLanguageCode.FI_FI,
            "pl": ExtendedLanguageCode.PL_PL,
            "tr": ExtendedLanguageCode.TR_TR,
            "he": ExtendedLanguageCode.HE_IL,
        }

        return comprehend_to_extended.get(
            language_code, self.preferences.fallback_language
        )

    def _adjust_confidence_for_medical_terms(
        self, text: str, language: ExtendedLanguageCode, base_confidence: float
    ) -> float:
        """Adjust confidence based on presence of medical terminology."""
        # Get language prefix
        lang_prefix = language.value.split("-")[0].lower()

        # Check for medical terms
        medical_terms = self.MEDICAL_INDICATORS.get(lang_prefix, [])
        text_lower = text.lower()
        found_terms = sum(1 for term in medical_terms if term in text_lower)
        if found_terms > 3:
            # Boost confidence if many medical terms found
            return min(1.0, base_confidence + 0.1)
        elif found_terms == 0 and len(text.split()) > 20:
            # Reduce confidence if no medical terms in longer text
            return max(0.0, base_confidence - 0.05)
        return base_confidence

    def get_supported_languages(
        self, medical_transcription_only: bool = False
    ) -> List[ExtendedLanguageCode]:
        """
        Get list of supported languages.

        Args:
            medical_transcription_only: Only return languages supported by
                                      Amazon Transcribe Medical
        Returns:
            List of supported language codes
        """
        if medical_transcription_only:
            return self.MEDICAL_TRANSCRIBE_LANGUAGES
        return self.ALL_SUPPORTED_LANGUAGES

    def is_language_supported(
        self, language: ExtendedLanguageCode, for_medical_transcription: bool = False
    ) -> bool:
        """Check if a language is supported."""
        if for_medical_transcription:
            return language in self.MEDICAL_TRANSCRIBE_LANGUAGES
        return language in self.ALL_SUPPORTED_LANGUAGES

    def get_language_info(self, language: ExtendedLanguageCode) -> Dict[str, Any]:
        """Get detailed information about a language."""
        # Find language family
        language_family = None
        for family, languages in self.LANGUAGE_FAMILIES.items():
            if language in languages:
                language_family = family
                break

        # Get medical term count
        lang_prefix = language.value.split("-")[0].lower()
        medical_terms = self.MEDICAL_INDICATORS.get(lang_prefix, [])
        return {
            "code": language.value,
            "name": language.name,
            "family": language_family,
            "medical_transcription_supported": language
            in self.MEDICAL_TRANSCRIBE_LANGUAGES,
            "medical_terms_available": len(medical_terms),
            "dialect": None,  # Dialect detection requires audio file
        }

    def clear_cache(self) -> None:
        """Clear the language detection cache."""
        self._detection_cache.clear()
        logger.info("Language detection cache cleared")
