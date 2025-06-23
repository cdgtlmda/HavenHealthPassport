"""Data types and structures for Speaker Age Estimation Module."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union


class AgeGroup(Enum):
    """Age groups for classification."""

    CHILD = "child"  # 3-12 years
    ADOLESCENT = "adolescent"  # 13-17 years
    YOUNG_ADULT = "young_adult"  # 18-30 years
    MIDDLE_AGED = "middle_aged"  # 31-50 years
    OLDER_ADULT = "older_adult"  # 51-70 years
    ELDERLY = "elderly"  # 71+ years


class VoiceMaturity(Enum):
    """Voice maturity stages."""

    PRE_PUBERTAL = "pre_pubertal"
    PUBERTAL = "pubertal"
    POST_PUBERTAL = "post_pubertal"
    MATURE = "mature"
    AGING = "aging"
    ADVANCED_AGING = "advanced_aging"


@dataclass
class AgeEstimationConfig:
    """Configuration for age estimation."""

    sample_rate: int = 16000
    frame_length_ms: int = 25
    frame_shift_ms: int = 10
    min_segment_duration: float = 1.0
    pitch_floor: float = 50.0
    pitch_ceiling: float = 500.0
    use_deep_features: bool = True
    confidence_threshold: float = 0.6
    enable_gender_detection: bool = True
    use_spectral_features: bool = True
    use_voice_quality: bool = True
    use_speaking_rate: bool = True


@dataclass
class AgeFeatures:
    """Features extracted for age estimation."""

    # Acoustic features
    f0_mean: float = 0.0
    f0_std: float = 0.0
    f0_range: float = 0.0
    f0_slope: float = 0.0

    # Formant features
    f1_mean: float = 0.0
    f2_mean: float = 0.0
    f3_mean: float = 0.0
    f4_mean: float = 0.0
    formant_dispersion: float = 0.0
    vtl_estimate: float = 0.0

    # Voice quality
    jitter: float = 0.0
    shimmer: float = 0.0
    hnr: float = 0.0
    cpp: float = 0.0

    # Spectral features
    spectral_slope: float = 0.0
    spectral_centroid: float = 0.0
    spectral_spread: float = 0.0
    spectral_flux: float = 0.0
    high_freq_energy: float = 0.0

    # Temporal features
    speaking_rate: float = 0.0
    pause_frequency: float = 0.0
    articulation_rate: float = 0.0

    # MFCC statistics
    mfcc_means: List[float] = field(default_factory=list)
    mfcc_stds: List[float] = field(default_factory=list)

    # Gender-related
    gender_score: float = 0.5  # 0=male, 1=female

    def to_dict(self) -> Dict[str, float]:
        """Convert features to dictionary."""
        return {
            "f0_mean": self.f0_mean,
            "f0_std": self.f0_std,
            "f0_range": self.f0_range,
            "f0_slope": self.f0_slope,
            "f1_mean": self.f1_mean,
            "f2_mean": self.f2_mean,
            "f3_mean": self.f3_mean,
            "f4_mean": self.f4_mean,
            "formant_dispersion": self.formant_dispersion,
            "vtl_estimate": self.vtl_estimate,
            "jitter": self.jitter,
            "shimmer": self.shimmer,
            "hnr": self.hnr,
            "cpp": self.cpp,
            "spectral_slope": self.spectral_slope,
            "spectral_centroid": self.spectral_centroid,
            "spectral_spread": self.spectral_spread,
            "spectral_flux": self.spectral_flux,
            "high_freq_energy": self.high_freq_energy,
            "speaking_rate": self.speaking_rate,
            "pause_frequency": self.pause_frequency,
            "articulation_rate": self.articulation_rate,
            "gender_score": self.gender_score,
        }


@dataclass
class AgeEstimationResult:
    """Result of age estimation analysis."""

    estimated_age: float
    age_group: AgeGroup
    confidence_score: float
    voice_maturity: VoiceMaturity
    likely_gender: Optional[str] = None
    gender_confidence: float = 0.0
    features: Optional[AgeFeatures] = None
    quality_warnings: List[str] = field(default_factory=list)
    processing_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(
        self,
    ) -> Dict[str, Union[List[str], float, str, None, Dict[str, float]]]:
        """Convert the result to a dictionary."""
        result: Dict[str, Union[List[str], float, str, None, Dict[str, float]]] = {
            "estimated_age": self.estimated_age,
            "age_group": self.age_group.value,
            "confidence_score": self.confidence_score,
            "voice_maturity": self.voice_maturity.value,
            "likely_gender": self.likely_gender,
            "gender_confidence": self.gender_confidence,
            "quality_warnings": self.quality_warnings,
            "processing_time": self.processing_time,
            "timestamp": self.timestamp.isoformat(),
        }

        if self.features:
            result["features"] = self.features.to_dict()

        return result

    @property
    def age_range(self) -> Tuple[int, int]:
        """Get age range for the estimated age group."""
        ranges = {
            AgeGroup.CHILD: (3, 12),
            AgeGroup.ADOLESCENT: (13, 17),
            AgeGroup.YOUNG_ADULT: (18, 30),
            AgeGroup.MIDDLE_AGED: (31, 50),
            AgeGroup.OLDER_ADULT: (51, 70),
            AgeGroup.ELDERLY: (71, 100),
        }
        return ranges.get(self.age_group, (0, 100))
