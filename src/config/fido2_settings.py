"""FIDO2 key specific configuration settings.

This module provides configuration specific to FIDO2 security keys,
extending the base WebAuthn configuration with FIDO2-specific parameters.
"""

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.config.webauthn_settings import WebAuthnSettings


@dataclass
class Fido2KeyRequirements:
    """FIDO2 key requirements configuration."""

    # Minimum authenticator assurance level
    min_aaguid_certification_level: int = 1  # FIDO L1 minimum

    # Required authenticator capabilities
    require_user_verification: bool = True
    require_resident_key_capable: bool = False
    require_platform_authenticator: bool = False

    # Allowed transports
    allowed_transports: Optional[List[str]] = None

    # Banned AAGUIDs (for compromised authenticators)
    banned_aaguids: Optional[List[str]] = None

    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.allowed_transports is None:
            self.allowed_transports = ["usb", "nfc", "ble"]

        if self.banned_aaguids is None:
            self.banned_aaguids = []


class Fido2Settings(WebAuthnSettings):
    """FIDO2-specific settings extending WebAuthn configuration."""

    def __init__(self) -> None:
        """Initialize FIDO2 settings."""
        super().__init__()
        self._load_fido2_settings()

    def _load_fido2_settings(self) -> None:
        """Load FIDO2-specific configuration."""
        # FIDO2 key requirements
        self.fido2_requirements = Fido2KeyRequirements(
            min_aaguid_certification_level=int(
                os.getenv("FIDO2_MIN_CERTIFICATION_LEVEL", "1")
            ),
            require_user_verification=os.getenv(
                "FIDO2_REQUIRE_USER_VERIFICATION", "true"
            ).lower()
            == "true",
            require_resident_key_capable=os.getenv(
                "FIDO2_REQUIRE_RESIDENT_KEY", "false"
            ).lower()
            == "true",
            require_platform_authenticator=os.getenv(
                "FIDO2_REQUIRE_PLATFORM_AUTH", "false"
            ).lower()
            == "true",
        )

        # Allowed transports
        transports_str = os.getenv("FIDO2_ALLOWED_TRANSPORTS", "usb,nfc,ble")
        self.fido2_requirements.allowed_transports = [
            t.strip() for t in transports_str.split(",")
        ]

        # Banned AAGUIDs
        banned_str = os.getenv("FIDO2_BANNED_AAGUIDS", "")
        if banned_str:
            self.fido2_requirements.banned_aaguids = [
                a.strip() for a in banned_str.split(",")
            ]

        # FIDO2-specific attestation settings
        self.fido2_attestation_preference = os.getenv("FIDO2_ATTESTATION", "direct")

        # Enterprise attestation support
        self.support_enterprise_attestation = (
            os.getenv("FIDO2_ENTERPRISE_ATTESTATION", "false").lower() == "true"
        )

        # Metadata service configuration
        self.use_mds = os.getenv("FIDO2_USE_MDS", "true").lower() == "true"
        self.mds_endpoint = os.getenv(
            "FIDO2_MDS_ENDPOINT", "https://mds.fidoalliance.org"
        )
        self.mds_access_token = os.getenv("FIDO2_MDS_ACCESS_TOKEN", "")

        # Key lifecycle settings
        self.max_key_age_days = int(
            os.getenv("FIDO2_MAX_KEY_AGE_DAYS", "730")
        )  # 2 years
        self.require_key_rotation = (
            os.getenv("FIDO2_REQUIRE_KEY_ROTATION", "false").lower() == "true"
        )

        # Additional security settings
        self.require_pin = os.getenv("FIDO2_REQUIRE_PIN", "true").lower() == "true"
        self.min_pin_length = int(os.getenv("FIDO2_MIN_PIN_LENGTH", "4"))

    def get_fido2_registration_options(self) -> Dict[str, Any]:
        """Get FIDO2-specific registration options."""
        options: Dict[str, Any] = {
            "authenticatorSelection": {
                "authenticatorAttachment": "cross-platform",
                "requireResidentKey": self.fido2_requirements.require_resident_key_capable,
                "residentKey": "discouraged",
                "userVerification": (
                    "required"
                    if self.fido2_requirements.require_user_verification
                    else "preferred"
                ),
            },
            "attestation": self.fido2_attestation_preference,
            "extensions": {},
        }

        # Add credProtect extension for enhanced security
        options["extensions"]["credProtect"] = {
            "credentialProtectionPolicy": "userVerificationRequired",
            "enforceCredentialProtectionPolicy": True,
        }

        # Add minimum PIN length if required
        if self.require_pin:
            options["extensions"]["minPinLength"] = self.min_pin_length

        return options

    def validate_fido2_authenticator(
        self, authenticator_data: Dict
    ) -> Tuple[bool, Optional[str]]:
        """Validate FIDO2 authenticator against requirements.

        Args:
            authenticator_data: Authenticator data from registration

        Returns:
            Tuple of (valid, error_message)
        """
        # Check AAGUID against banned list
        aaguid = authenticator_data.get("aaguid")
        if (
            aaguid
            and self.fido2_requirements.banned_aaguids is not None
            and aaguid in self.fido2_requirements.banned_aaguids
        ):
            return False, "Authenticator is not allowed"

        # Validate transports
        transports = authenticator_data.get("transports", [])
        if transports and self.fido2_requirements.allowed_transports is not None:
            valid_transport = any(
                t in self.fido2_requirements.allowed_transports for t in transports
            )
            if not valid_transport:
                return (
                    False,
                    f"Authenticator transport not allowed. Allowed: {self.fido2_requirements.allowed_transports}",
                )

        # Check user verification capability
        if self.fido2_requirements.require_user_verification:
            if not authenticator_data.get("user_verified", False):
                return False, "User verification is required"

        # Validate certification level if MDS is enabled
        if self.use_mds and aaguid:
            cert_level = self._get_certification_level(aaguid)
            if cert_level < self.fido2_requirements.min_aaguid_certification_level:
                return (
                    False,
                    f"Authenticator certification level {cert_level} is below minimum {self.fido2_requirements.min_aaguid_certification_level}",
                )

        return True, None

    def _get_certification_level(self, _aaguid: str) -> int:
        """Get FIDO certification level for an AAGUID.

        Args:
            aaguid: Authenticator AAGUID

        Returns:
            Certification level (0 if unknown)
        """
        # This would query the FIDO MDS service in a real implementation
        # For now, return a default level
        return 1

    def get_recommended_authenticators(self) -> List[Dict[str, Any]]:
        """Get list of recommended FIDO2 authenticators."""
        return [
            {
                "name": "YubiKey 5 Series",
                "vendor": "Yubico",
                "certification": "FIDO2 L2",
                "features": ["USB-A", "USB-C", "NFC", "FIPS"],
            },
            {
                "name": "Titan Security Key",
                "vendor": "Google",
                "certification": "FIDO2 L1",
                "features": ["USB-A", "USB-C", "NFC", "Bluetooth"],
            },
            {
                "name": "Solo V2",
                "vendor": "SoloKeys",
                "certification": "FIDO2 L1",
                "features": ["USB-A", "USB-C", "NFC", "Open Source"],
            },
            {
                "name": "Feitian ePass FIDO2",
                "vendor": "Feitian",
                "certification": "FIDO2 L2",
                "features": ["USB-A", "USB-C", "NFC", "Bluetooth", "FIPS"],
            },
        ]


# Module-level singleton holder
class _SettingsHolder:
    """Holds the singleton FIDO2 settings instance."""

    instance: Optional[Fido2Settings] = None


def get_fido2_settings() -> Fido2Settings:
    """Get FIDO2 settings singleton instance."""
    if _SettingsHolder.instance is None:
        _SettingsHolder.instance = Fido2Settings()
    return _SettingsHolder.instance
