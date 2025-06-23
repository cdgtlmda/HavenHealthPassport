"""Biometric authentication configuration.

This module defines configuration settings for biometric authentication
including security thresholds, device requirements, and policy settings.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class BiometricSecurityConfig:
    """Security configuration for biometric authentication."""

    # Quality thresholds
    min_enrollment_quality: float = 0.7
    min_verification_quality: float = 0.6

    # Matching thresholds
    fingerprint_match_threshold: float = 0.95
    face_match_threshold: float = 0.93
    voice_match_threshold: float = 0.90
    iris_match_threshold: float = 0.98
    palm_match_threshold: float = 0.94

    # Liveness detection
    require_liveness: bool = True
    liveness_threshold: float = 0.9
    liveness_timeout_seconds: int = 30

    # Anti-spoofing
    anti_spoofing_enabled: bool = True
    spoof_detection_threshold: float = 0.85

    # Template security
    encrypt_templates: bool = True
    template_encryption_algorithm: str = "AES-256-GCM"
    template_retention_days: int = 365

    # Rate limiting
    max_enrollment_attempts_per_hour: int = 5
    max_verification_attempts_per_minute: int = 3
    lockout_duration_minutes: int = 5

    # Multi-device policy
    max_templates_per_type: int = 5
    allow_cross_device_authentication: bool = True
    require_device_attestation: bool = False


@dataclass
class BiometricDeviceRequirements:
    """Device requirements for biometric capture."""

    # Fingerprint scanners
    fingerprint_min_resolution_dpi: int = 500
    fingerprint_min_capture_area_mm2: int = 225  # 15x15mm
    fingerprint_supported_formats: Optional[List[str]] = None

    # Face cameras
    face_min_resolution_px: tuple = (640, 480)
    face_min_framerate_fps: int = 15
    face_require_depth_sensor: bool = False
    face_supported_formats: Optional[List[str]] = None

    # Voice microphones
    voice_min_sample_rate_hz: int = 16000
    voice_min_bit_depth: int = 16
    voice_max_background_noise_db: float = 40.0

    # Iris scanners
    iris_min_resolution_px: tuple = (640, 480)
    iris_infrared_required: bool = True
    iris_wavelength_nm: tuple = (700, 900)

    def __post_init__(self) -> None:
        """Initialize default supported formats."""
        if self.fingerprint_supported_formats is None:
            self.fingerprint_supported_formats = ["ISO_19794_2", "ANSI_378", "WSQ"]

        if self.face_supported_formats is None:
            self.face_supported_formats = ["JPEG", "PNG", "ISO_19794_5"]


@dataclass
class BiometricPolicyConfig:
    """Policy configuration for biometric authentication."""

    # Enrollment policies
    require_user_consent: bool = True
    require_privacy_notice_acceptance: bool = True
    allow_minor_enrollment: bool = False
    minimum_age_years: int = 13

    # Authentication policies
    allow_passwordless_authentication: bool = True
    require_pin_backup: bool = True
    biometric_as_second_factor_only: bool = False

    # Cross-border policies
    respect_local_biometric_laws: bool = True
    prohibited_countries: Optional[List[str]] = None
    gdpr_compliant_storage: bool = True

    # Accessibility policies
    provide_alternative_authentication: bool = True
    support_accessibility_devices: bool = True

    # Audit policies
    log_all_authentication_attempts: bool = True
    audit_retention_days: int = 90
    anonymize_audit_logs: bool = True

    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.prohibited_countries is None:
            self.prohibited_countries = []


@dataclass
class WebAuthnConfig:
    """WebAuthn/FIDO2 configuration."""

    # Relying party settings
    rp_name: str = "Haven Health Passport"
    rp_id: str = "havenhealthpassport.org"
    rp_origins: Optional[List[str]] = None

    # Authentication settings
    user_verification: str = "required"  # required, preferred, discouraged
    authenticator_attachment: Optional[str] = (
        "platform"  # platform, cross-platform, None
    )
    resident_key: str = "preferred"  # required, preferred, discouraged

    # Attestation settings
    attestation_conveyance: str = "direct"  # none, indirect, direct, enterprise
    attestation_formats: Optional[List[str]] = None

    # Algorithm preferences
    public_key_algorithms: Optional[List[int]] = None  # COSE algorithm identifiers

    # Timeout settings
    registration_timeout_ms: int = 60000
    authentication_timeout_ms: int = 60000

    # Security settings
    require_backup_eligible: bool = False
    require_backup_state: bool = False

    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.rp_origins is None:
            self.rp_origins = [
                "https://havenhealthpassport.org",
                "https://app.havenhealthpassport.org",
            ]

        if self.attestation_formats is None:
            self.attestation_formats = ["packed", "tpm", "android-key", "fido-u2f"]

        if self.public_key_algorithms is None:
            self.public_key_algorithms = [
                -7,  # ES256 (ECDSA w/ SHA-256)
                -257,  # RS256 (RSASSA-PKCS1-v1_5 w/ SHA-256)
                -8,  # EdDSA
            ]


# Default configurations
DEFAULT_SECURITY_CONFIG = BiometricSecurityConfig()
DEFAULT_DEVICE_REQUIREMENTS = BiometricDeviceRequirements()
DEFAULT_POLICY_CONFIG = BiometricPolicyConfig()
DEFAULT_WEBAUTHN_CONFIG = WebAuthnConfig()


def get_biometric_config(config_type: str) -> object:
    """Get biometric configuration by type.

    Args:
        config_type: Type of configuration (security, device, policy, webauthn)

    Returns:
        Configuration object
    """
    configs = {
        "security": DEFAULT_SECURITY_CONFIG,
        "device": DEFAULT_DEVICE_REQUIREMENTS,
        "policy": DEFAULT_POLICY_CONFIG,
        "webauthn": DEFAULT_WEBAUTHN_CONFIG,
    }

    return configs.get(config_type, DEFAULT_SECURITY_CONFIG)
