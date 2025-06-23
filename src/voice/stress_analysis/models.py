"""Data models and enums for stress analysis module."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class StressLevel(Enum):
    """Stress levels with clinical significance."""

    MINIMAL = "minimal"  # 0-20%
    LOW = "low"  # 20-40%
    MODERATE = "moderate"  # 40-60%
    HIGH = "high"  # 60-80%
    SEVERE = "severe"  # 80-100%
    CRITICAL = "critical"  # >100% (medical emergency)


class StressType(Enum):
    """Types of stress detected."""

    ACUTE = "acute"  # Sudden onset
    CHRONIC = "chronic"  # Long-term
    EPISODIC = "episodic"  # Recurring
    TRAUMATIC = "traumatic"  # PTSD-related
    PHYSICAL = "physical"  # Pain/illness related
    EMOTIONAL = "emotional"  # Psychological
    COGNITIVE = "cognitive"  # Mental overload


class StressIndicator(Enum):
    """Physiological indicators of stress in voice."""

    PITCH_ELEVATION = "pitch_elevation"
    PITCH_VARIABILITY = "pitch_variability"
    VOICE_TREMOR = "voice_tremor"
    SPEAKING_RATE = "speaking_rate"
    PAUSE_PATTERNS = "pause_patterns"
    BREATH_PATTERNS = "breath_patterns"
    VOICE_BREAKS = "voice_breaks"
    MUSCLE_TENSION = "muscle_tension"
    GLOTTAL_PULSE = "glottal_pulse"


@dataclass
class StressFeatures:
    """Voice features relevant to stress detection."""

    # Core stress indicators
    fundamental_frequency_mean: float = 0.0
    fundamental_frequency_std: float = 0.0
    fundamental_frequency_range: float = 0.0

    # Pitch dynamics
    pitch_acceleration: float = 0.0  # Rate of pitch change
    pitch_jerk: float = 0.0  # Rate of acceleration change
    pitch_instability: float = 0.0  # Coefficient of variation

    # Voice quality under stress
    jitter_local: float = 0.0  # Cycle-to-cycle pitch variation
    jitter_rap: float = 0.0  # Relative average perturbation
    shimmer_local: float = 0.0  # Amplitude variation
    shimmer_apq: float = 0.0  # Amplitude perturbation quotient

    # Harmonic structure
    harmonic_to_noise_ratio: float = 0.0
    normalized_noise_energy: float = 0.0
    glottal_to_noise_ratio: float = 0.0

    # Temporal features
    speaking_rate_variability: float = 0.0
    pause_frequency: float = 0.0
    pause_duration_mean: float = 0.0
    pause_duration_std: float = 0.0

    # Breathing patterns
    breath_rate: float = 0.0
    breath_depth_estimate: float = 0.0
    breath_irregularity: float = 0.0

    # Articulation under stress
    vowel_space_area: float = 0.0
    formant_dispersion: float = 0.0
    articulation_rate: float = 0.0

    # Spectral stress markers
    spectral_tilt: float = 0.0  # Energy distribution
    high_frequency_energy_ratio: float = 0.0
    spectral_entropy: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """Convert features to dictionary."""
        return {
            "f0_mean": self.fundamental_frequency_mean,
            "f0_std": self.fundamental_frequency_std,
            "f0_range": self.fundamental_frequency_range,
            "pitch_acceleration": self.pitch_acceleration,
            "pitch_instability": self.pitch_instability,
            "jitter_local": self.jitter_local,
            "jitter_rap": self.jitter_rap,
            "shimmer_local": self.shimmer_local,
            "shimmer_apq": self.shimmer_apq,
            "hnr": self.harmonic_to_noise_ratio,
            "speaking_rate_variability": self.speaking_rate_variability,
            "pause_frequency": self.pause_frequency,
            "breath_rate": self.breath_rate,
            "spectral_tilt": self.spectral_tilt,
            "high_freq_energy": self.high_frequency_energy_ratio,
        }

    def get_stress_score(self) -> float:
        """Calculate overall stress score from features."""
        # Weighted combination of key stress indicators
        weights = {
            "pitch": 0.25,
            "voice_quality": 0.25,
            "temporal": 0.25,
            "spectral": 0.25,
        }

        # Normalize and combine features
        pitch_score = min(
            1.0,
            (
                self.pitch_instability * 2
                + abs(self.pitch_acceleration) / 10
                + (self.fundamental_frequency_std / 50)
            )
            / 3,
        )

        voice_quality_score = min(
            1.0,
            (
                self.jitter_local * 100
                + self.shimmer_local * 20
                + max(0, 20 - self.harmonic_to_noise_ratio) / 20
            )
            / 3,
        )

        temporal_score = min(
            1.0,
            (
                self.speaking_rate_variability
                + self.pause_frequency / 10
                + self.breath_irregularity
            )
            / 3,
        )
        spectral_score = min(
            1.0,
            (
                self.high_frequency_energy_ratio * 2
                + self.spectral_entropy
                + abs(self.spectral_tilt) / 10
            )
            / 3,
        )

        # Weighted combination
        total_score = (
            weights["pitch"] * pitch_score
            + weights["voice_quality"] * voice_quality_score
            + weights["temporal"] * temporal_score
            + weights["spectral"] * spectral_score
        )

        return total_score


@dataclass
class StressAnalysisResult:
    """Complete result of stress analysis."""

    stress_level: StressLevel
    stress_score: float  # 0-1 normalized score
    stress_types: List[StressType] = field(default_factory=list)

    # Detailed indicators
    active_indicators: List[StressIndicator] = field(default_factory=list)
    features: Optional[StressFeatures] = None

    # Temporal analysis
    stress_timeline: List[Tuple[float, float]] = field(
        default_factory=list
    )  # (time, stress_score)
    stress_variability: float = 0.0
    peak_stress_moments: List[float] = field(default_factory=list)  # Timestamps

    # Clinical relevance
    clinical_significance: str = ""
    risk_factors: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    # Confidence and metadata
    confidence_score: float = 0.0
    analysis_duration: float = 0.0
    processing_time_ms: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "stress_level": self.stress_level.value,
            "stress_score": self.stress_score,
            "stress_types": [t.value for t in self.stress_types],
            "active_indicators": [i.value for i in self.active_indicators],
            "features": self.features.to_dict() if self.features else None,
            "stress_timeline": self.stress_timeline,
            "stress_variability": self.stress_variability,
            "peak_stress_moments": self.peak_stress_moments,
            "clinical_significance": self.clinical_significance,
            "risk_factors": self.risk_factors,
            "recommendations": self.recommendations,
            "confidence_score": self.confidence_score,
            "analysis_duration": self.analysis_duration,
            "processing_time_ms": self.processing_time_ms,
            "warnings": self.warnings,
        }

    def get_summary(self) -> str:
        """Get human-readable summary."""
        summary = (
            f"Stress Level: {self.stress_level.value.upper()} ({self.stress_score:.1%})"
        )
        if self.stress_types:
            summary += f"\nTypes: {', '.join(t.value for t in self.stress_types)}"
        if self.clinical_significance:
            summary += f"\nClinical: {self.clinical_significance}"
        return summary


@dataclass
class StressAnalysisConfig:
    """Configuration for stress analysis."""

    # Audio parameters
    sample_rate: int = 16000
    frame_duration_ms: int = 30
    overlap_ratio: float = 0.5

    # Analysis settings
    enable_temporal_analysis: bool = True
    temporal_window_seconds: float = 2.0
    enable_breathing_analysis: bool = True
    enable_muscle_tension_detection: bool = True
    # Stress level thresholds
    stress_thresholds: Dict[str, float] = field(
        default_factory=lambda: {
            "minimal": 0.2,
            "low": 0.4,
            "moderate": 0.6,
            "high": 0.8,
            "severe": 0.9,
            "critical": 1.0,
        }
    )

    # Clinical thresholds
    acute_stress_threshold: float = 0.7
    chronic_stress_min_duration: float = 30.0  # seconds

    # Feature extraction
    use_advanced_features: bool = True
    min_voiced_duration: float = 0.5  # Minimum voiced segment duration
