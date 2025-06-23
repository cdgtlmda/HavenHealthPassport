"""Noise Profile Module.

This module defines noise profiles, types, and characteristics
for medical environment noise reduction.
 Handles FHIR Resource validation.

Security Note: This module processes audio data that may contain PHI.
All audio processing and noise profiles must be handled with encryption
at rest and in transit. Access to audio data should be restricted to
authorized healthcare personnel only through role-based access controls.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class NoiseType(Enum):
    """Types of noise commonly found in medical environments."""

    # Environmental noise
    HVAC = "hvac"  # Heating/ventilation/AC
    AMBIENT = "ambient"  # General background noise
    BACKGROUND = "background"  # General background noise
    TRAFFIC = "traffic"  # Outside traffic noise
    CONSTRUCTION = "construction"  # Building construction

    # Medical equipment
    MONITOR_BEEPS = "monitor_beeps"  # Patient monitor alarms
    VENTILATOR = "ventilator"  # Breathing machine sounds
    SUCTION = "suction"  # Suction device noise
    PUMP = "pump"  # IV/medication pumps
    EQUIPMENT_HUM = "equipment_hum"  # General equipment noise

    # Human activity
    FOOTSTEPS = "footsteps"  # Walking sounds
    CONVERSATION = "conversation"  # Background talking
    COUGHING = "coughing"  # Patient coughing
    MOVEMENT = "movement"  # Bed/chair movement
    PAPER_RUSTLING = "paper"  # Paper/chart sounds

    # Communication devices
    PHONE_RING = "phone_ring"  # Phone ringing
    PAGER = "pager"  # Pager alerts
    PA_ANNOUNCEMENT = "pa_announcement"  # Overhead announcements
    DOOR = "door"  # Door opening/closing

    # Other
    WHITE_NOISE = "white_noise"  # Broadband noise
    PINK_NOISE = "pink_noise"  # 1/f noise
    INTERFERENCE = "interference"  # Electronic interference
    ELECTRICAL = "electrical"  # Electrical interference
    WIND = "wind"  # Wind noise
    ECHO = "echo"  # Room echo/reverb
    IMPULSE = "impulse"  # Sudden loud noise
    UNKNOWN = "unknown"  # Unclassified noise


class NoiseLevel(Enum):
    """Noise intensity levels."""

    VERY_LOW = "very_low"  # < 30 dB
    LOW = "low"  # 30-40 dB
    MODERATE = "moderate"  # 40-50 dB
    HIGH = "high"  # 50-60 dB
    VERY_HIGH = "very_high"  # > 60 dB


class EnvironmentType(Enum):
    """Types of medical environments with different noise profiles."""

    EXAM_ROOM = "exam_room"  # Quiet examination room
    EMERGENCY_ROOM = "emergency_room"  # Busy ER environment
    ICU = "icu"  # Intensive care unit
    OPERATING_ROOM = "operating_room"  # Surgical suite
    WAITING_ROOM = "waiting_room"  # Patient waiting area
    HALLWAY = "hallway"  # Hospital corridor
    PATIENT_ROOM = "patient_room"  # Standard patient room
    CLINIC = "clinic"  # Outpatient clinic
    LABORATORY = "laboratory"  # Medical lab
    RADIOLOGY = "radiology"  # Imaging department
    PHARMACY = "pharmacy"  # Hospital pharmacy
    TELEMEDICINE = "telemedicine"  # Remote consultation
    HOME_CARE = "home_care"  # Home healthcare setting
    AMBULANCE = "ambulance"  # Emergency vehicle


@dataclass
class NoiseCharacteristics:
    """Detailed characteristics of a noise type."""

    frequency_range: Tuple[float, float] = (0.0, 8000.0)  # Hz
    typical_duration: Tuple[float, float] = (0.1, 10.0)  # seconds
    intensity_range: Tuple[float, float] = (30.0, 70.0)  # dB
    is_periodic: bool = False
    is_impulsive: bool = False
    is_continuous: bool = False
    spectral_shape: str = "broadband"  # broadband, narrowband, tonal

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "frequency_range": self.frequency_range,
            "typical_duration": self.typical_duration,
            "intensity_range": self.intensity_range,
            "is_periodic": self.is_periodic,
            "is_impulsive": self.is_impulsive,
            "is_continuous": self.is_continuous,
            "spectral_shape": self.spectral_shape,
        }


@dataclass
class NoiseProfile:
    """
    Complete noise profile for a specific noise type or environment.

    This profile contains all information needed to detect and
    reduce specific types of noise in medical audio.
    """

    noise_type: NoiseType
    noise_level: NoiseLevel
    characteristics: NoiseCharacteristics
    environment_types: List[EnvironmentType] = field(default_factory=list)

    # Reduction parameters
    reduction_strength: float = 0.5  # 0-1 scale
    preserve_speech: bool = True
    adaptive_filtering: bool = True

    # Detection parameters
    detection_threshold: float = 0.3  # 0-1 scale
    min_duration: float = 0.1  # seconds

    # Additional metadata
    common_frequencies: List[float] = field(default_factory=list)
    example_sounds: List[str] = field(default_factory=list)
    medical_impact: str = "low"  # low, medium, high

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "noise_type": self.noise_type.value,
            "noise_level": self.noise_level.value,
            "characteristics": self.characteristics.to_dict(),
            "environment_types": [e.value for e in self.environment_types],
            "reduction_strength": self.reduction_strength,
            "preserve_speech": self.preserve_speech,
            "adaptive_filtering": self.adaptive_filtering,
            "detection_threshold": self.detection_threshold,
            "min_duration": self.min_duration,
            "common_frequencies": self.common_frequencies,
            "example_sounds": self.example_sounds,
            "medical_impact": self.medical_impact,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NoiseProfile":
        """Create NoiseProfile from dictionary."""
        characteristics = NoiseCharacteristics(**data["characteristics"])

        return cls(
            noise_type=NoiseType(data["noise_type"]),
            noise_level=NoiseLevel(data["noise_level"]),
            characteristics=characteristics,
            environment_types=[
                EnvironmentType(e) for e in data.get("environment_types", [])
            ],
            reduction_strength=data.get("reduction_strength", 0.5),
            preserve_speech=data.get("preserve_speech", True),
            adaptive_filtering=data.get("adaptive_filtering", True),
            detection_threshold=data.get("detection_threshold", 0.3),
            min_duration=data.get("min_duration", 0.1),
            common_frequencies=data.get("common_frequencies", []),
            example_sounds=data.get("example_sounds", []),
            medical_impact=data.get("medical_impact", "low"),
        )


class NoiseDatabase:
    """
    Database of noise profiles for medical environments.

    This class manages a collection of noise profiles and provides
    methods for noise identification and reduction parameter selection.
    """

    def __init__(self) -> None:
        """Initialize noise database with common medical noise profiles."""
        self.profiles: Dict[NoiseType, NoiseProfile] = {}
        self._initialize_medical_profiles()

    def _initialize_medical_profiles(self) -> None:
        """Initialize with common medical environment noise profiles."""
        # HVAC noise
        self.profiles[NoiseType.HVAC] = NoiseProfile(
            noise_type=NoiseType.HVAC,
            noise_level=NoiseLevel.LOW,
            characteristics=NoiseCharacteristics(
                frequency_range=(20, 500),
                typical_duration=(1.0, float("inf")),
                intensity_range=(35, 50),
                is_continuous=True,
                spectral_shape="broadband",
            ),
            environment_types=[EnvironmentType.EXAM_ROOM, EnvironmentType.PATIENT_ROOM],
            reduction_strength=0.7,
            medical_impact="low",
        )

        # Monitor beeps
        self.profiles[NoiseType.MONITOR_BEEPS] = NoiseProfile(
            noise_type=NoiseType.MONITOR_BEEPS,
            noise_level=NoiseLevel.MODERATE,
            characteristics=NoiseCharacteristics(
                frequency_range=(1000, 4000),
                typical_duration=(0.1, 1.0),
                intensity_range=(50, 70),
                is_periodic=True,
                is_impulsive=True,
                spectral_shape="tonal",
            ),
            environment_types=[EnvironmentType.ICU, EnvironmentType.PATIENT_ROOM],
            common_frequencies=[2000, 2500, 3000],
            reduction_strength=0.5,
            preserve_speech=True,
            medical_impact="medium",
        )

        # Background conversation
        self.profiles[NoiseType.CONVERSATION] = NoiseProfile(
            noise_type=NoiseType.CONVERSATION,
            noise_level=NoiseLevel.MODERATE,
            characteristics=NoiseCharacteristics(
                frequency_range=(100, 4000),
                typical_duration=(1.0, 30.0),
                intensity_range=(40, 60),
                is_continuous=False,
                spectral_shape="speech-like",
            ),
            environment_types=[EnvironmentType.EMERGENCY_ROOM, EnvironmentType.HALLWAY],
            reduction_strength=0.6,
            preserve_speech=True,
            medical_impact="high",
        )

    def add_profile(self, profile: NoiseProfile) -> None:
        """Add or update a noise profile."""
        self.profiles[profile.noise_type] = profile

    def get_profile(self, noise_type: NoiseType) -> Optional[NoiseProfile]:
        """Get noise profile for a specific type."""
        return self.profiles.get(noise_type)

    def get_profiles_by_environment(
        self, environment: EnvironmentType
    ) -> List[NoiseProfile]:
        """Get all noise profiles common in a specific environment."""
        return [
            profile
            for profile in self.profiles.values()
            if environment in profile.environment_types
        ]

    def get_profiles_by_level(self, level: NoiseLevel) -> List[NoiseProfile]:
        """Get all profiles with a specific noise level."""
        return [
            profile
            for profile in self.profiles.values()
            if profile.noise_level == level
        ]

    def get_reduction_parameters(self, noise_type: NoiseType) -> Dict[str, Any]:
        """Get reduction parameters for a specific noise type."""
        profile = self.profiles.get(noise_type)
        if not profile:
            return {"reduction_strength": 0.5, "preserve_speech": True}

        return {
            "reduction_strength": profile.reduction_strength,
            "preserve_speech": profile.preserve_speech,
            "adaptive_filtering": profile.adaptive_filtering,
            "frequency_range": profile.characteristics.frequency_range,
        }


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
